"""
dem_service.py
==============
Fetches REAL Digital Elevation Model data for any bounding box on Earth.

PIPELINE (in priority order):
  1. OpenZenith  /api/elevation (GLO-30 Copernicus 30m, bilinear interpolation)
     → Used for up to GRID_RES² single-point calls in concurrent batches
  2. OpenTopoData /v1/srtm30m  (SRTM 30m, batch up to 100 pts per request)
     → Batched fallback, returns real terrain elevation grid
  3. SRTM90m     fallback if 30m is unavailable
  4. Deterministic perlin-noise fallback as LAST resort
     → This is only used when ALL network calls fail, and it uses
       true geographic-coordinate-seeded noise (no repeating patterns).

ROOT CAUSE OF OLD CHECKERBOARD BUG (fixed):
  The old code normalised X,Y coordinates to [0, 4π] for every location,
  then used sin/cos with EXACT integer multipliers (1.5×, 3×, 6×, 12×).
  This produces exactly 3, 6, 12, 24 complete sinusoidal cycles across the
  grid → a perfect repeating diamond/checkerboard independent of location.

  The fix is to use REAL elevation data from public APIs.
  The perlin fallback (if needed) uses absolute geographic coordinates as
  spatial inputs, not normalised [0,4π] values, so no repeating pattern occurs.
"""
import os
import uuid
import math
import time
import hashlib
import requests
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from typing import Dict, Any, Tuple, List, Optional
from shapely.geometry import Polygon, Point
from shapely.validation import make_valid
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.config import settings
from backend.models.dem_models import DemRequest, DemResponse, DemMetadata, BoundingBox
from backend.utils.geo_utils import latlng_to_bbox, polygon_bounds, haversine_distance

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────
OPENZENITH_URL = "https://openzenith.cyopsys.com/api/elevation"
OPENTOPODATA_SRTM30_URL = "https://api.opentopodata.org/v1/srtm30m"
OPENTOPODATA_SRTM90_URL = "https://api.opentopodata.org/v1/srtm90m"
OPENTOPODATA_ASTER_URL  = "https://api.opentopodata.org/v1/aster30m"
BATCH_SIZE = 100          # OpenTopoData max points per request
MAX_GRID_RES = 100        # Maximum output DEM grid resolution
# Public point APIs are rate limited. Fetch a smaller real grid and resample
# for display/scoring instead of falling back to synthetic terrain.
OPENTOPODATA_DIRECT_MAX_RES = 32
OPENTOPODATA_FALLBACK_RES = 20
OPENZENITH_DIRECT_MAX_RES = 40
DEFAULT_TIMEOUT = 8.0     # Per-request HTTP timeout (s)
RATE_DELAY = 0.50         # Seconds between OpenTopoData batch calls
CENTER_SNAP_M = 1000.0    # Stabilize village/map analysis against tiny centre drags


class DemService:

    # ─────────────────────────────────────────────────────
    # DEM CACHE  (session-scoped, in-process)
    # Key  = "<s4>_<w4>_<n4>_<e4>_<res>_<provider_sig>"
    # Value = (elev_matrix: np.ndarray, source_label: str)
    # ─────────────────────────────────────────────────────
    _dem_cache: Dict[str, Tuple[np.ndarray, str]] = {}

    @classmethod
    def _dem_cache_key(
        cls, south: float, west: float, north: float, east: float, res: int,
        provider: str = "auto", dem_type: str = "COP30",
    ) -> str:
        """
        Build an explicit, collision-free cache key.

        Bounds are rounded to 4 decimal places (~11 m precision) — enough to
        treat two requests for the same village as identical while keeping
        different geographic areas distinct.

        The provider signature records whether an OpenTopography API key is
        configured so that a key-present run and a key-absent run are never
        mixed in the cache.
        """
        has_key = "1" if settings.OPENTOPOGRAPHY_API_KEY else "0"
        provider_sig = (provider or "auto").lower()
        dem_type_sig = (dem_type or "COP30").upper()
        return (
            f"{round(south, 4)}_"
            f"{round(west,  4)}_"
            f"{round(north, 4)}_"
            f"{round(east,  4)}_"
            f"{res}_{provider_sig}_{dem_type_sig}_k{has_key}"
        )

    @staticmethod
    def _snap_center_to_analysis_grid(lat: float, lng: float) -> Tuple[float, float]:
        lat_step = CENTER_SNAP_M / 111000.0
        snapped_lat = round(lat / lat_step) * lat_step

        lon_m_per_deg = 111000.0 * max(0.01, math.cos(math.radians(snapped_lat)))
        lon_step = CENTER_SNAP_M / lon_m_per_deg
        snapped_lng = round(lng / lon_step) * lon_step

        return snapped_lat, snapped_lng

    @classmethod
    def _disk_cache_path(cls, cache_key: str) -> str:
        cache_dir = os.path.join(settings.STORAGE_DIR, "dem_cache")
        os.makedirs(cache_dir, exist_ok=True)
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return os.path.join(cache_dir, f"{digest}.npz")

    @classmethod
    def _load_from_disk_cache(cls, cache_key: str) -> Optional[Tuple[np.ndarray, str]]:
        path = cls._disk_cache_path(cache_key)
        if not os.path.exists(path):
            return None

        try:
            with np.load(path, allow_pickle=False) as cached:
                elevation = cached["elevation"].astype(np.float64)
                source_label = str(cached["source"].item())
            return elevation, source_label
        except Exception as e:
            print(f"[DemService] Ignoring corrupt DEM disk cache {path}: {e}")
            return None

    @classmethod
    def _save_to_disk_cache(
        cls, cache_key: str, elev_matrix: np.ndarray, source_label: str
    ) -> None:
        if "Perlin" in source_label:
            return

        path = cls._disk_cache_path(cache_key)
        try:
            np.savez_compressed(
                path,
                elevation=elev_matrix.astype(np.float64, copy=False),
                source=np.array(source_label),
            )
        except Exception as e:
            print(f"[DemService] Could not persist DEM disk cache {path}: {e}")

    # ─────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────────────
    @classmethod
    def process_dem_request(cls, request: DemRequest) -> DemResponse:
        dem_id = f"dem_{uuid.uuid4().hex[:10]}"

        # 1. Determine spatial bounds
        if request.polygon and len(request.polygon.coordinates) >= 3:
            south, west, north, east = polygon_bounds(request.polygon.coordinates)
        elif request.bbox:
            south, west, north, east = (request.bbox.south, request.bbox.west,
                                        request.bbox.north, request.bbox.east)
        elif request.center:
            radius = request.radius_km if request.radius_km else 2.0
            center_lat, center_lng = cls._snap_center_to_analysis_grid(
                request.center.lat, request.center.lng
            )
            south, west, north, east = latlng_to_bbox(
                center_lat, center_lng, radius
            )
        else:
            south, west, north, east = 27.95, 86.87, 28.03, 86.97

        res = max(20, min(int(request.resolution), MAX_GRID_RES))

        # 2. Fetch REAL elevation matrix (cache-first)
        cache_key = cls._dem_cache_key(
            south, west, north, east, res, request.provider, request.dem_type
        )
        if cache_key in cls._dem_cache:
            elev_matrix, source_label = cls._dem_cache[cache_key]
            elev_matrix = elev_matrix.copy()   # defensive copy – callers may mutate
            print(f"[DemService] Cache HIT ({cache_key}) | Source: {source_label}")
        else:
            disk_cached = cls._load_from_disk_cache(cache_key)
            if disk_cached is not None:
                elev_matrix, source_label = disk_cached
                print(f"[DemService] Disk cache HIT ({cache_key}) | Source: {source_label}")
            else:
                elev_matrix, source_label = cls._fetch_real_dem(
                    south, west, north, east, res, request.provider, request.dem_type
                )
                cls._save_to_disk_cache(cache_key, elev_matrix, source_label)
                print(f"[DemService] Cache MISS – fetched via {source_label} | "
                      f"shape={elev_matrix.shape} | "
                      f"range=[{elev_matrix.min():.1f}, {elev_matrix.max():.1f}]m | "
                      f"std={elev_matrix.std():.1f}")
            cls._dem_cache[cache_key] = (elev_matrix.copy(), source_label)

        # 3. Apply Polygon Mask (supports any number of vertices ≥ 3)
        if request.polygon and len(request.polygon.coordinates) >= 3:
            elev_matrix, valid_elev, nan_matrix = cls._apply_polygon_mask(
                elev_matrix, request.polygon.coordinates, south, west, north, east, res
            )
        else:
            valid_elev = elev_matrix
            nan_matrix = elev_matrix

        # 4. Statistics
        min_elev   = float(np.nanmin(valid_elev))
        max_elev   = float(np.nanmax(valid_elev))
        mean_elev  = float(np.nanmean(valid_elev))
        std_elev   = float(np.nanstd(valid_elev))
        median_elev = float(np.nanmedian(valid_elev))

        height_m  = haversine_distance(south, west, north, west)
        width_m   = haversine_distance(south, west, south, east)
        pixel_size_m = float((height_m / res + width_m / res) / 2.0)

        # 5. Save GeoTIFF
        geotiff_path = os.path.join(settings.STORAGE_DIR, f"{dem_id}.tif")
        transform = from_bounds(west, south, east, north, res, res)
        with rasterio.open(
            geotiff_path, 'w', driver='GTiff',
            height=res, width=res, count=1,
            dtype=elev_matrix.dtype, crs='EPSG:4326', transform=transform,
        ) as dst:
            dst.write(elev_matrix, 1)

        # 6. Colorised elevation overlay PNG
        overlay_filename = f"{dem_id}_elevation.png"
        overlay_path = os.path.join(settings.STORAGE_DIR, overlay_filename)
        cls._create_elevation_overlay(nan_matrix, min_elev, max_elev, overlay_path)

        # 7. Hillshade PNG (central finite differences gradient)
        hillshade_filename = f"{dem_id}_hillshade.png"
        hillshade_path = os.path.join(settings.STORAGE_DIR, hillshade_filename)
        cls._create_hillshade_overlay(elev_matrix, pixel_size_m, hillshade_path)

        # 8. Histogram
        clean_vals = valid_elev[~np.isnan(valid_elev)] if np.any(~np.isnan(valid_elev)) else elev_matrix.flatten()
        counts, bin_edges = np.histogram(clean_vals, bins=15)
        histogram = {
            "counts": counts.tolist(),
            "bins": [round(float(b), 1) for b in bin_edges.tolist()]
        }

        bounds_model = BoundingBox(south=south, west=west, north=north, east=east)
        is_synthetic = "Perlin" in source_label
        metadata = DemMetadata(
            dem_id=dem_id,
            bounds=bounds_model,
            width=res,
            height=res,
            min_elevation=round(min_elev, 2),
            max_elevation=round(max_elev, 2),
            mean_elevation=round(mean_elev, 2),
            std_elevation=round(std_elev, 2),
            median_elevation=round(median_elev, 2),
            pixel_size_m=round(pixel_size_m, 2),
            data_source=source_label,
            is_synthetic=is_synthetic,
            nodata_count=int(np.sum(np.isnan(valid_elev))),
            num_api_points=res * res,
        )

        return DemResponse(
            success=True,
            message=f"DEM fetched via {source_label}.",
            metadata=metadata,
            elevation_matrix=np.nan_to_num(elev_matrix, nan=0.0).tolist(),
            elevation_overlay_url=f"/storage/{overlay_filename}",
            hillshade_overlay_url=f"/storage/{hillshade_filename}",
            histogram=histogram,
        )

    # ─────────────────────────────────────────────────────
    # STEP 1 – REAL DEM ACQUISITION (ordered by priority)
    # ─────────────────────────────────────────────────────
    @classmethod
    def _fetch_real_dem(
        cls, south: float, west: float, north: float, east: float, res: int,
        provider: str = "auto", dem_type: str = "COP30",
    ) -> Tuple[np.ndarray, str]:
        """
        Try real elevation sources using the requested provider as preference.

        Public point APIs can rate-limit large grids, so OpenTopoData/OpenZenith
        are fetched at a capped real-data resolution and resampled to the
        requested output grid. This keeps map analysis stable and avoids
        silently selecting pond sites from synthetic fallback terrain.
        """
        provider = (provider or "auto").lower()
        if provider not in {"auto", "opentopography", "openzenith", "opentopodata"}:
            provider = "auto"

        preferred_order = {
            "opentopography": ["opentopography", "opentopodata", "openzenith"],
            "openzenith": ["openzenith", "opentopodata", "opentopography"],
            "opentopodata": ["opentopodata", "opentopography", "openzenith"],
            "auto": ["opentopography", "opentopodata", "openzenith"],
        }[provider]

        for source in preferred_order:
            if source == "opentopography":
                try:
                    res_ot = cls._fetch_opentopography_official(
                        south, west, north, east, res, dem_type
                    )
                    if res_ot is not None:
                        return res_ot
                except Exception as e:
                    print(f"[DemService] OpenTopography official API failed: {e}")

            elif source == "opentopodata":
                result = cls._try_opentopodata_sources(south, west, north, east, res)
                if result is not None:
                    return result

            elif source == "openzenith":
                try:
                    fetch_res = min(res, OPENZENITH_DIRECT_MAX_RES)
                    arr = cls._fetch_openzenith_grid(south, west, north, east, fetch_res)
                    if arr is not None:
                        if fetch_res != res:
                            arr = cls._resample_grid(arr, res)
                            return arr, f"OpenZenith GLO-30 (resampled from {fetch_res}x{fetch_res})"
                        return arr, "OpenZenith GLO-30"
                except Exception as e:
                    print(f"[DemService] OpenZenith grid failed: {e}")

        # Last resort remains explicit in metadata via is_synthetic=True.
        print("[DemService] All network sources failed. Using geographic Perlin fallback.")
        return cls._geographic_perlin_dem(south, west, north, east, res), "Perlin-fallback"

    @classmethod
    def _try_opentopodata_sources(
        cls, south: float, west: float, north: float, east: float, res: int
    ) -> Optional[Tuple[np.ndarray, str]]:
        """Fetch OpenTopoData, downshifting public API calls when needed."""
        fetch_res = min(res, OPENTOPODATA_FALLBACK_RES)

        for ds_url, label in [
            (OPENTOPODATA_SRTM30_URL, "SRTM-30m"),
            (OPENTOPODATA_SRTM90_URL, "SRTM-90m"),
            (OPENTOPODATA_ASTER_URL,  "ASTER-30m"),
        ]:
            try:
                arr = cls._fetch_opentopodata_grid(
                    south, west, north, east, fetch_res, ds_url
                )
                if arr is None:
                    continue
                if fetch_res != res:
                    arr = cls._resample_grid(arr, res)
                    return arr, f"OpenTopoData/{label} (resampled from {fetch_res}x{fetch_res})"
                return arr, f"OpenTopoData/{label}"
            except Exception as e:
                print(f"[DemService] {label} failed at {fetch_res}x{fetch_res}: {e}")

        return None

    @staticmethod
    def _resample_grid(arr: np.ndarray, target_res: int) -> np.ndarray:
        """Resample a square DEM grid to target_res while preserving real data range."""
        if arr.shape == (target_res, target_res):
            return arr.astype(np.float64, copy=False)
        from scipy.ndimage import zoom

        zoom_y = target_res / arr.shape[0]
        zoom_x = target_res / arr.shape[1]
        out = zoom(arr.astype(np.float64), (zoom_y, zoom_x), order=1)
        return out[:target_res, :target_res]

    # ─────────────────────────────────────────────────────
    # OPENTOPOGRAPHY OFFICIAL API (COP30 / SRTMGL1)
    # ─────────────────────────────────────────────────────
    @classmethod
    def _fetch_opentopography_official(
        cls, south: float, west: float, north: float, east: float, res: int,
        dem_type: str = "COP30",
    ) -> Optional[Tuple[np.ndarray, str]]:
        """
        Fetch high-res DEM raster directly from OpenTopography API using API Key.
        Returns (elevation_matrix, dataset_label) or None if request fails.
        """
        api_key = settings.OPENTOPOGRAPHY_API_KEY
        if not api_key:
            return None

        # Try requested OpenTopography dataset first, then the supported fallback.
        requested_type = (dem_type or "COP30").upper()
        supported = [("COP30", "OpenTopography COP30"), ("SRTMGL1", "OpenTopography SRTMGL1")]
        ordered = [item for item in supported if item[0] == requested_type]
        ordered.extend(item for item in supported if item[0] != requested_type)

        for current_dem_type, label in ordered:
            params = {
                "demtype": current_dem_type,
                "south": f"{south:.6f}",
                "north": f"{north:.6f}",
                "west": f"{west:.6f}",
                "east": f"{east:.6f}",
                "outputFormat": "GTiff",
                "API_Key": api_key
            }
            try:
                r = requests.get(settings.OPENTOPOGRAPHY_API_URL, params=params, timeout=15)
                if r.status_code == 200 and len(r.content) > 100:
                    from rasterio.io import MemoryFile
                    from rasterio.enums import Resampling
                    with MemoryFile(r.content) as memfile:
                        with memfile.open() as dataset:
                            data = dataset.read(
                                1,
                                out_shape=(res, res),
                                resampling=Resampling.bilinear
                            ).astype(np.float64)
                            nodata = dataset.nodata
                            if nodata is not None:
                                data[data == nodata] = np.nan
                            data[data < -500] = np.nan
                            data = cls._fill_nans(data)
                            print(f"[DemService] OpenTopography {current_dem_type} successfully fetched! shape={data.shape}")
                            return data, label
                else:
                    print(f"[DemService] OpenTopography {current_dem_type} status: {r.status_code}, response: {r.text[:100]}")
            except Exception as e:
                print(f"[DemService] OpenTopography {current_dem_type} failed: {e}")

        return None

    # ─────────────────────────────────────────────────────
    # OPENZENITH  – concurrent single-point grid
    # ─────────────────────────────────────────────────────
    @classmethod
    def _fetch_openzenith_grid(
        cls, south: float, west: float, north: float, east: float, res: int
    ) -> Optional[np.ndarray]:
        """
        Fetch a res×res grid from OpenZenith /api/elevation using a thread pool.
        Returns None if more than 10 % of points fail.
        """
        # Fast pre-flight check to see if OpenZenith endpoint is online and accessible
        try:
            probe_url = f"{OPENZENITH_URL}?lat={north:.6f}&lon={west:.6f}"
            r = requests.get(probe_url, headers={"User-Agent": "ContourAnalyzer/1.0"}, timeout=2.5)
            if r.status_code != 200:
                print(f"[DemService] OpenZenith pre-flight probe returned HTTP {r.status_code} – skipping provider")
                return None
            probe_data = r.json()
            if not isinstance(probe_data, dict) or probe_data.get("elevation") is None:
                print("[DemService] OpenZenith pre-flight probe returned non-elevation response – skipping provider")
                return None
        except Exception as e:
            print(f"[DemService] OpenZenith pre-flight probe failed ({e}) – skipping provider")
            return None

        lats = np.linspace(north, south, res)
        lons = np.linspace(west, east, res)
        LonG, LatG = np.meshgrid(lons, lats)
        coords = list(zip(LatG.flatten(), LonG.flatten()))
        n_pts = len(coords)

        results: Dict[int, Optional[float]] = {}

        def fetch_one(idx: int, lat: float, lon: float) -> Tuple[int, Optional[float]]:
            url = f"{OPENZENITH_URL}?lat={lat:.6f}&lon={lon:.6f}"
            try:
                r = requests.get(url, headers={"User-Agent": "ContourAnalyzer/1.0"}, timeout=DEFAULT_TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    elev = data.get("elevation")
                    if elev is not None:
                        return idx, float(elev)
            except Exception:
                pass
            return idx, None

        # Use thread pool – max 12 concurrent OpenZenith requests
        failed_count = 0
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(fetch_one, i, lat, lon): i
                       for i, (lat, lon) in enumerate(coords)}
            for future in as_completed(futures):
                idx, elev = future.result()
                results[idx] = elev
                if elev is None:
                    failed_count += 1
                    if failed_count > n_pts * 0.10:
                        pool.shutdown(wait=False, cancel_futures=True)
                        print(f"[DemService] OpenZenith: >10% points failed early ({failed_count}/{n_pts}) – aborting")
                        return None

        elevs = [results.get(i) for i in range(n_pts)]
        none_count = sum(1 for e in elevs if e is None)
        if none_count > n_pts * 0.10:
            print(f"[DemService] OpenZenith: {none_count}/{n_pts} points failed – skipping")
            return None

        # Replace None with nearest neighbour interpolation
        arr = np.array([e if e is not None else np.nan for e in elevs], dtype=np.float64)
        arr = arr.reshape(res, res)
        arr = cls._fill_nans(arr)
        return arr

    # ─────────────────────────────────────────────────────
    # OPENTOPODATA  – batched SRTM/ASTER grid
    # ─────────────────────────────────────────────────────
    @classmethod
    def _fetch_opentopodata_grid(
        cls, south: float, west: float, north: float, east: float, res: int,
        ds_url: str
    ) -> Optional[np.ndarray]:
        """
        Fetch a res×res grid from OpenTopoData in batches of 100 points.
        """
        lats = np.linspace(north, south, res)
        lons = np.linspace(west, east, res)
        LonG, LatG = np.meshgrid(lons, lats)
        flat_lats = LatG.flatten()
        flat_lons = LonG.flatten()
        n_pts = len(flat_lats)

        all_elevs: List[Optional[float]] = []

        for start in range(0, n_pts, BATCH_SIZE):
            batch_la = flat_lats[start : start + BATCH_SIZE]
            batch_lo = flat_lons[start : start + BATCH_SIZE]
            loc_str = "|".join([f"{la:.6f},{lo:.6f}" for la, lo in zip(batch_la, batch_lo)])
            url = f"{ds_url}?locations={loc_str}"
            try:
                r = requests.get(url, headers={"User-Agent": "ContourAnalyzer/1.0"}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for pt in data.get("results", []):
                        all_elevs.append(pt.get("elevation"))
                elif r.status_code == 429:
                    print(f"[DemService] OpenTopoData rate-limited on batch {start//BATCH_SIZE+1}")
                    return None
                else:
                    print(f"[DemService] OpenTopoData {r.status_code}: {r.text[:80]}")
                    return None
            except Exception as e:
                print(f"[DemService] OpenTopoData request error: {e}")
                return None

            if start + BATCH_SIZE < n_pts:
                time.sleep(RATE_DELAY)

        if len(all_elevs) != n_pts:
            return None

        none_count = sum(1 for e in all_elevs if e is None)
        if none_count > n_pts * 0.10:
            return None

        arr = np.array([e if e is not None else np.nan for e in all_elevs], dtype=np.float64)
        arr = arr.reshape(res, res)
        arr = cls._fill_nans(arr)
        return arr

    # ─────────────────────────────────────────────────────
    # GEOGRAPHIC PERLIN FALLBACK  – no repeating patterns
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _geographic_perlin_dem(
        south: float, west: float, north: float, east: float, res: int
    ) -> np.ndarray:
        """
        LAST-RESORT fallback when ALL network sources are unavailable.

        Unlike the old code, this uses ABSOLUTE geographic coordinates
        (actual lat/lon values) as spatial inputs to the sinusoidal basis
        functions. This means:
          - The spatial frequencies are fixed in degrees (not in normalised
            grid units), so a 2-km box and a 200-km box produce different
            numbers of cycles and never both tile as a perfect checkerboard.
          - Different locations produce different starting phases because the
            absolute lat/lon values seed the sin/cos arguments.

        The pattern will still look like synthetic terrain, but it will NOT
        repeat identically across locations.
        """
        lats = np.linspace(north, south, res)   # shape (res,)
        lons = np.linspace(west, east, res)      # shape (res,)
        LonG, LatG = np.meshgrid(lons, lats)    # shape (res, res)

        # Use ABSOLUTE geographic coordinates as spatial inputs
        # (degrees are real numbers that change with location)
        Xabs = np.radians(LonG)   # absolute longitude in radians
        Yabs = np.radians(LatG)   # absolute latitude in radians

        # Spatial frequencies in radians/degree  →  chosen so typical
        # ~0.05° bbox (≈5 km) shows 2–4 terrain features, not an integer tile
        # Note: unlike old code, these are NOT integer multiples of 2π/extent,
        # so no standing-wave resonance / checkerboard occurs.
        f1, f2, f3, f4 = 50.0, 130.0, 310.0, 730.0

        freq1 = 200.0  * np.sin(f1 * Xabs) * np.cos(f1 * Yabs)
        freq2 = 110.0  * np.sin(f2 * Xabs + 0.7) * np.sin(f2 * Yabs - 1.1)
        freq3 =  55.0  * np.cos(f3 * Xabs - 0.3) * np.sin(f3 * Yabs + 0.5)
        freq4 =  25.0  * np.sin(f4 * Xabs + 1.3) * np.cos(f4 * Yabs - 0.9)

        # Base elevation from absolute location (not normalised)
        base = (
            abs(math.sin(south * 0.05 + west * 0.03)) * 1500.0
            + abs(math.cos(north * 0.08 - east * 0.02)) * 600.0
            + 200.0
        )

        # Single terrain peak at geographic centre
        clon = math.radians((west + east) / 2.0)
        clat = math.radians((south + north) / 2.0)
        spread = max(math.radians(east - west), math.radians(north - south))
        peak = 400.0 * np.exp(
            -((Xabs - clon)**2 + (Yabs - clat)**2) / (0.5 * spread**2)
        )

        elevation = base + freq1 + freq2 + freq3 + freq4 + peak
        return np.maximum(elevation, 5.0).astype(np.float64)

    # ─────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _fill_nans(arr: np.ndarray) -> np.ndarray:
        """Fill NaN cells with the mean of valid neighbours (simple but effective)."""
        if not np.any(np.isnan(arr)):
            return arr
        from scipy.ndimage import generic_filter

        def _nanmean_filter(values: np.ndarray) -> float:
            valid = values[~np.isnan(values)]
            return float(np.mean(valid)) if len(valid) else 0.0

        filled = generic_filter(arr, _nanmean_filter, size=3, mode='nearest')
        mask = np.isnan(arr)
        arr[mask] = filled[mask]
        if np.any(np.isnan(arr)):
            arr = np.nan_to_num(arr, nan=float(np.nanmean(arr)))
        return arr

    @classmethod
    def _apply_polygon_mask(
        cls,
        elev_matrix: np.ndarray,
        poly_coords: List,
        south: float, west: float, north: float, east: float, res: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply polygon mask; returns (elev_matrix, valid_elev, nan_matrix)."""
        try:
            raw_poly = Polygon(poly_coords)
            poly = make_valid(raw_poly) if not raw_poly.is_valid else raw_poly

            lats = np.linspace(north, south, res)
            lons = np.linspace(west, east, res)
            mask = np.ones((res, res), dtype=bool)

            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    pt = Point(lon, lat)
                    if not (poly.contains(pt) or poly.touches(pt)):
                        mask[i, j] = False

            nan_matrix = np.where(mask, elev_matrix, np.nan)
            valid_elev = elev_matrix[mask] if np.any(mask) else elev_matrix
            return elev_matrix, valid_elev, nan_matrix
        except Exception as e:
            print(f"[DemService] Polygon mask error: {e}")
            return elev_matrix, elev_matrix, elev_matrix

    # ─────────────────────────────────────────────────────
    # IMAGE RENDERERS
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _create_elevation_overlay(
        elev_matrix: np.ndarray, min_e: float, max_e: float, save_path: str
    ) -> None:
        """Vibrant terrain-colourised PNG."""
        norm = (elev_matrix - min_e) / (max_e - min_e + 1e-6)
        cmap = plt.get_cmap('terrain')
        rgba = cmap(norm)
        rgba[np.isnan(elev_matrix), 3] = 0.0
        Image.fromarray((rgba * 255).astype(np.uint8)).save(save_path, "PNG")

    @staticmethod
    def _create_hillshade_overlay(
        elev_matrix: np.ndarray, pixel_size_m: float, save_path: str,
        azimuth: float = 315.0, altitude: float = 45.0
    ) -> None:
        """Hillshade calculation via central finite differences gradient — saved as RGBA so Leaflet ImageOverlay composites correctly."""
        azimuth_rad = np.radians(360.0 - azimuth)
        altitude_rad = np.radians(altitude)

        dy, dx = np.gradient(elev_matrix, pixel_size_m)
        slope  = np.arctan(np.sqrt(dx * dx + dy * dy))
        aspect = np.arctan2(-dy, dx)

        shaded = (
            np.sin(altitude_rad) * np.cos(slope)
            + np.cos(altitude_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
        )
        # Map shaded to [0, 255]
        shaded = np.clip(shaded, -1.0, 1.0)
        # Normalize: dark shadowed areas → 0 brightness, lit areas → 255
        brightness = ((shaded + 1.0) / 2.0 * 255.0).astype(np.uint8)

        # Build RGBA: grayscale brightness in R/G/B channels, varying alpha
        # Lit areas are semi-transparent (so color overlay shows through),
        # very dark shadow areas are more opaque (deep shadow effect)
        h, w = brightness.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0] = brightness          # R
        rgba[:, :, 1] = brightness          # G
        rgba[:, :, 2] = brightness          # B
        # Alpha: shadowed areas (dark) get opacity ~140, lit areas ~60 for natural blend
        alpha = (255 - brightness.astype(np.int16)).clip(0, 255).astype(np.uint8)
        alpha = (alpha * 0.65).astype(np.uint8)
        rgba[:, :, 3] = alpha

        Image.fromarray(rgba, mode='RGBA').save(save_path, "PNG")
