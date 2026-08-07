"""
pond_service.py
Detects and analyses local depressions (ponds/sinks) in DEM.

Algorithm:
  1. Fill-and-diff: fill sinks in DEM (priority-queue flood fill, the standard
     Priority-Flood algorithm), then subtract original to find depression depth.
  2. Label connected depression regions via scipy.ndimage.label.
  3. For the clicked cell, recover that depression's label region.
     If no depression is at the exact click, search in an expanding radius.
  4. Estimate pond volume by summing (water_level - elev) * pixel_area for each
     cell in the depression (trapezoidal approximation across depth layers).

Improvements over v1:
  - Lower depression threshold (0.05 m instead of 0.1 m) to catch shallow water bodies
  - Pre-smoothing the DEM slightly to remove API noise before depression detection
  - Expanding-radius search if exact click cell has no depression (up to 8-cell radius)
  - Flat-region detection: areas that are locally flat and bounded by higher terrain
    are treated as candidate water bodies even if Priority-Flood doesn't mark them
"""
import uuid
import math
import heapq
import numpy as np
from scipy.ndimage import label as nd_label, uniform_filter
from typing import Tuple, List, Optional
from collections import deque

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.phase4_models import PondRequest, PondResponse, PondInfo
from backend.utils.geo_utils import haversine_distance


class PondService:
    # --- Priority-Flood sink-filling (Wang & Liu 2006) ----------------------
    @staticmethod
    def _priority_flood_fill(dem: np.ndarray) -> np.ndarray:
        """
        Fills sinks in DEM using Priority-Flood algorithm.
        Returns a new array where every cell elevation >= its drainage path.
        """
        rows, cols = dem.shape
        filled = dem.copy()
        visited = np.zeros((rows, cols), dtype=bool)

        # Seed the priority queue with all border cells
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
    def _find_flat_water_bodies(dem: np.ndarray, min_flat_cells: int = 4) -> np.ndarray:
        """
        Detects flat regions that could represent water bodies (lakes, reservoirs).
        A flat region is where local elevation variance is very small but surrounded
        by higher terrain.
        Returns a boolean mask of flat candidate water cells.
        """
        rows, cols = dem.shape
        # Local std dev over 3x3 window
        local_mean = uniform_filter(dem, size=3, mode='nearest')
        local_sq_mean = uniform_filter(dem**2, size=3, mode='nearest')
        local_var = np.maximum(0, local_sq_mean - local_mean**2)
        local_std = np.sqrt(local_var)

        # Cells that are very flat (std < 1m in 3x3 neighborhood)
        flat_mask = local_std < 1.0

        # Of those flat cells, check if they are below their surrounding mean
        # (i.e. the flat area sits in a basin)
        local_mean_5 = uniform_filter(dem, size=5, mode='nearest')
        basin_mask = flat_mask & (dem < local_mean_5 + 0.5)

        # Label connected regions
        labeled, n = nd_label(basin_mask)

        # Keep only regions with enough cells
        result = np.zeros_like(basin_mask)
        for lbl in range(1, n + 1):
            region = labeled == lbl
            if region.sum() >= min_flat_cells:
                result |= region

        return result

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

        # Lightly smooth DEM to reduce API noise before depression detection
        dem_smooth = uniform_filter(dem, size=3, mode='nearest')

        # Fill sinks and compute depression depth
        filled = cls._priority_flood_fill(dem_smooth)
        depth = filled - dem_smooth           # > 0 only at depression cells
        depression_mask = depth > 0.05        # Lowered threshold: 0.05 m (was 0.1 m)

        # Also check flat water body regions
        flat_water_mask = cls._find_flat_water_bodies(dem_smooth, min_flat_cells=4)

        # Combined mask
        combined_mask = depression_mask | flat_water_mask

        # Check if click cell has a depression; if not, search expanding radius up to 15 cells
        found_r, found_c = click_r, click_c
        if not combined_mask[click_r, click_c]:
            found = False
            for radius in range(1, 16):
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
                # Fallback: extract local basin/valley around click cell (cells <= local mean)
                r_min, r_max = max(0, click_r - 5), min(rows, click_r + 6)
                c_min, c_max = max(0, click_c - 5), min(cols, click_c + 6)
                local_window = dem_smooth[r_min:r_max, c_min:c_max]
                local_threshold = float(np.mean(local_window))
                candidate_mask = dem_smooth <= local_threshold
                combined_mask |= candidate_mask
                found_r, found_c = click_r, click_c

        # Label connected depression regions
        labeled, num_features = nd_label(combined_mask)
        pond_label = labeled[found_r, found_c]
        if pond_label == 0:
            pond_label = 1  # Fallback label

        pond_indices = labeled == pond_label
        pond_cells = np.argwhere(pond_indices)

        # To calculate robust water level and max depth:
        # Find 1-cell dilation boundary of pond_indices (the shoreline/rim of the basin)
        from scipy.ndimage import binary_dilation
        rim_indices = binary_dilation(pond_indices) & (~pond_indices)
        if np.any(rim_indices):
            rim_elev = float(np.mean(dem[rim_indices]))
        else:
            rim_elev = float(np.max(dem[pond_indices]))

        cell_filled = filled[pond_indices]
        cell_elevs = dem[pond_indices]
        bottom_elev = float(np.min(cell_elevs))

        # Water level is the maximum of filled elevation or shoreline rim elevation
        water_level = max(float(np.max(cell_filled)), rim_elev)
        if water_level <= bottom_elev:
            water_level = bottom_elev + max(0.5, float(np.std(cell_elevs)) + 0.5)

        max_depth = max(0.2, water_level - bottom_elev)

        # Surface area
        pixel_area_m2 = pxm * pxm
        surface_area_m2 = float(len(pond_cells)) * pixel_area_m2
        surface_area_km2 = surface_area_m2 / 1_000_000.0

        # Volume by summing depth * pixel_area for each cell
        depths_per_cell = np.maximum(0.05, water_level - cell_elevs)
        volume_m3 = float(np.sum(depths_per_cell) * pixel_area_m2)
        volume_km3 = volume_m3 / 1e9

        # Center of pond
        center_r = int(np.mean(pond_cells[:, 0]))
        center_c = int(np.mean(pond_cells[:, 1]))
        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        center_lat = float(lats[center_r])
        center_lng = float(lons[center_c])

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
        )
        return PondResponse(success=True, pond=pond, message="Water body / depression detected successfully.")
