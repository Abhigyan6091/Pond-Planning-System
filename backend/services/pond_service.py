"""
pond_service.py
Detects and analyses local depressions (ponds/sinks) in DEM.

Algorithm:
  1. Fill-and-diff: fill sinks in DEM (priority-queue flood fill, the standard
     Priority-Flood algorithm), then subtract original to find depression depth.
  2. Label connected depression cells via scipy.ndimage.label.
  3. For the clicked cell, recover that depression's label region.
  4. Estimate pond volume by summing (water_level - elev) * pixel_area for each
     cell in the depression (trapezoidal approximation across depth layers).
"""
import uuid
import math
import heapq
import numpy as np
from scipy.ndimage import label as nd_label
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

        # Fill sinks and compute depression depth
        filled = cls._priority_flood_fill(dem)
        depth = filled - dem           # > 0 only at depression cells
        depression_mask = depth > 0.1  # Threshold: ignore trivial noise

        # No depression at this cell
        if not depression_mask[click_r, click_c]:
            return PondResponse(
                success=False,
                message="No significant depression detected at clicked location. Try clicking in a valley or basin."
            )

        # Label connected depression regions
        labeled, num_features = nd_label(depression_mask)
        pond_label = labeled[click_r, click_c]
        pond_cells = np.argwhere(labeled == pond_label)

        # Water level = maximum filled elevation at depression boundary
        # (i.e. lowest spill point = min of filled across depression)
        cell_filled = filled[labeled == pond_label]
        water_level = float(np.min(cell_filled))

        # Elevations inside the depression
        cell_elevs = dem[labeled == pond_label]
        bottom_elev = float(np.min(cell_elevs))
        max_depth = water_level - bottom_elev

        # Surface area
        pixel_area_m2 = pxm * pxm
        surface_area_m2 = float(len(pond_cells)) * pixel_area_m2
        surface_area_km2 = surface_area_m2 / 1_000_000.0

        # Volume by summing depth * pixel_area for each cell
        # (equivalent to trapezoidal integration over horizontal layers)
        depths_per_cell = np.maximum(0.0, water_level - cell_elevs)
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
        return PondResponse(success=True, pond=pond, message="Pond depression detected successfully.")
