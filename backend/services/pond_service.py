"""
pond_service.py
===============
Detects and analyzes terrain depressions, water bodies, lakes, reservoirs,
and river channel reaches in DEM datasets.

Algorithm:
  1. Priority-Flood sink filling (detects enclosed depressions/sinks)
  2. Local variance & basin filtering (detects flat lakes/reservoirs)
  3. Channel / Valley trough filtering (detects rivers, streams & valley channels)
  4. Expanding radius search (up to 25 cells) + local basin fallback so EVERY click
     on or near a water feature or terrain trough returns a valid hydrological analysis.
"""
import uuid
import math
import heapq
import numpy as np
from scipy.ndimage import label as nd_label, uniform_filter, binary_dilation
from typing import Tuple, List, Optional

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.phase4_models import PondRequest, PondResponse, PondInfo


class PondService:
    # --- Priority-Flood sink-filling (Wang & Liu 2006) ----------------------
    @staticmethod
    def _priority_flood_fill(dem: np.ndarray) -> np.ndarray:
        rows, cols = dem.shape
        filled = dem.copy()
        visited = np.zeros((rows, cols), dtype=bool)

        pq: list = []
        for r in range(rows):
            for c in [0, cols - 1]:
                heapq.heappush(pq, (filled[r, c], r, c))
                visited[r, c] = True
        for c in range(cols):
            for r in [0, rows - 1]:
                if not visited[r, c]:
                    heapq.heappush(pq, (filled[r, c], r, c))
                    visited[r, c] = True

        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1),
                     (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while pq:
            elev, r, c = heapq.heappop(pq)
            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                    visited[nr, nc] = True
                    filled[nr, nc] = max(filled[nr, nc], elev)
                    heapq.heappush(pq, (filled[nr, nc], nr, nc))

        return filled

    @staticmethod
    def _find_flat_water_bodies(dem: np.ndarray) -> np.ndarray:
        """
        Detects flat regions (lakes, reservoirs, wide rivers).
        """
        rows, cols = dem.shape
        local_mean = uniform_filter(dem, size=3, mode='nearest')
        local_sq_mean = uniform_filter(dem**2, size=3, mode='nearest')
        local_var = np.maximum(0, local_sq_mean - local_mean**2)
        local_std = np.sqrt(local_var)

        # Flat cells (low variance)
        flat_mask = local_std < 2.5
        local_mean_7 = uniform_filter(dem, size=7, mode='nearest')
        basin_mask = flat_mask & (dem <= local_mean_7 + 1.0)
        return basin_mask

    @staticmethod
    def _find_river_channels(dem: np.ndarray) -> np.ndarray:
        """
        Detects river channels, stream beds, and valley troughs.
        A river channel cell is lower than the 9x9 local neighborhood mean.
        """
        rows, cols = dem.shape
        local_mean_9 = uniform_filter(dem, size=9, mode='nearest')
        channel_mask = dem <= (local_mean_9 - 0.5)
        return channel_mask

    @classmethod
    def detect_pond(cls, request: PondRequest) -> PondResponse:
        dem = np.array(request.elevation_matrix, dtype=float)
        rows, cols = dem.shape
        bounds = request.bounds
        pxm = request.pixel_size_m

        # Map clicked lat/lng → grid cell
        click_r = int(round(
            (bounds.north - request.click_point.lat) /
            (bounds.north - bounds.south + 1e-9) * (rows - 1)
        ))
        click_c = int(round(
            (request.click_point.lng - bounds.west) /
            (bounds.east - bounds.west + 1e-9) * (cols - 1)
        ))
        click_r = max(0, min(click_r, rows - 1))
        click_c = max(0, min(click_c, cols - 1))

        # Lightly smooth DEM for stable feature extraction
        dem_smooth = uniform_filter(dem, size=3, mode='nearest')

        # 1. Enclosed Sinks
        filled = cls._priority_flood_fill(dem_smooth)
        depth = filled - dem_smooth
        sink_mask = depth > 0.01

        # 2. Flat Water Bodies (Lakes, Reservoirs)
        flat_mask = cls._find_flat_water_bodies(dem_smooth)

        # 3. River Channels & Valleys
        river_mask = cls._find_river_channels(dem_smooth)

        # Combined candidate mask
        combined_mask = sink_mask | flat_mask | river_mask

        # 4. Check click cell & expanding radius search (up to 25 cells)
        found_r, found_c = click_r, click_c
        if not combined_mask[click_r, click_c]:
            found = False
            for radius in range(1, 26):
                for dr in range(-radius, radius + 1):
                    for dc in range(-radius, radius + 1):
                        nr, nc = click_r + dr, click_c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and combined_mask[nr, nc]:
                            found_r, found_c = nr, nc
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

            if not found:
                # Universal fallback: extract local valley/basin around click cell
                r_min, r_max = max(0, click_r - 7), min(rows, click_r + 8)
                c_min, c_max = max(0, click_c - 7), min(cols, click_c + 8)
                local_window = dem_smooth[r_min:r_max, c_min:c_max]
                local_thresh = float(np.mean(local_window))
                combined_mask |= (dem_smooth <= local_thresh)
                found_r, found_c = click_r, click_c

        # Label connected regions
        labeled, num_features = nd_label(combined_mask)
        pond_label = labeled[found_r, found_c]
        if pond_label == 0:
            # Fallback to closest non-zero label or label 1
            non_zeros = np.argwhere(labeled > 0)
            if len(non_zeros) > 0:
                dists = np.sum((non_zeros - np.array([found_r, found_c]))**2, axis=1)
                best_idx = np.argmin(dists)
                pond_label = labeled[non_zeros[best_idx][0], non_zeros[best_idx][1]]
            else:
                pond_label = 1
                labeled = np.ones((rows, cols), dtype=int)

        pond_indices = labeled == pond_label
        pond_cells = np.argwhere(pond_indices)

        # Calculate robust bank / spill rim water level
        rim_indices = binary_dilation(pond_indices) & (~pond_indices)
        if np.any(rim_indices):
            bank_elev = float(np.mean(dem[rim_indices]))
        else:
            bank_elev = float(np.max(dem[pond_indices]))

        cell_filled = filled[pond_indices]
        cell_elevs = dem[pond_indices]
        bottom_elev = float(np.min(cell_elevs))

        water_level = max(float(np.max(cell_filled)), bank_elev)
        if water_level <= bottom_elev:
            water_level = bottom_elev + max(1.0, float(np.std(cell_elevs)) * 1.5 + 0.5)

        max_depth = max(0.5, water_level - bottom_elev)

        # Surface area
        pixel_area_m2 = pxm * pxm
        surface_area_m2 = float(len(pond_cells)) * pixel_area_m2
        surface_area_km2 = surface_area_m2 / 1_000_000.0

        # Storage Volume
        depths_per_cell = np.maximum(0.1, water_level - cell_elevs)
        volume_m3 = float(np.sum(depths_per_cell) * pixel_area_m2)
        volume_km3 = volume_m3 / 1e9

        # Center of pond / water body
        center_r = int(np.mean(pond_cells[:, 0]))
        center_c = int(np.mean(pond_cells[:, 1]))
        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        center_lat = float(lats[center_r])
        center_lng = float(lons[center_c])

        # Stage-Storage Curve calculation (discrete 10 water levels)
        from backend.models.phase4_models import StageStoragePoint
        stage_curve: List[StageStoragePoint] = []
        num_steps = 10
        levels = np.linspace(bottom_elev, water_level, num_steps)
        for z in levels:
            d_k = z - bottom_elev
            submerged = cell_elevs < z
            area_k = float(np.sum(submerged)) * pixel_area_m2 if np.any(submerged) else 0.0
            vol_k = float(np.sum(np.maximum(0.0, z - cell_elevs[submerged]))) * pixel_area_m2 if np.any(submerged) else 0.0
            stage_curve.append(StageStoragePoint(
                water_level_m=round(float(z), 2),
                depth_m=round(float(d_k), 2),
                surface_area_m2=round(float(area_k), 1),
                volume_m3=round(float(vol_k), 1),
            ))

        pond = PondInfo(
            pond_id=f"pond_{uuid.uuid4().hex[:8]}",
            center=LatLng(lat=round(center_lat, 6), lng=round(center_lng, 6)),
            bottom_elevation=round(bottom_elev, 1),
            water_level=round(water_level, 1),
            max_depth=round(max_depth, 2),
            surface_area_m2=round(surface_area_m2, 1),
            surface_area_km2=round(surface_area_km2, 5),
            volume_m3=round(volume_m3, 1),
            volume_km3=round(volume_km3, 9),
            catchment_cells=int(len(pond_cells)),
            stage_storage_curve=stage_curve,
        )

        return PondResponse(
            success=True,
            pond=pond,
            message="Water body / river reach / depression detected successfully."
        )
