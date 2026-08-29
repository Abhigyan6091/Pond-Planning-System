"""
contour_terrain_service.py
==========================
Converts a list of parsed contour lines into a regular elevation grid
(DEM) compatible with the existing Phase 1 hydrology/terrain engine.

Algorithm
---------
Contours are isolines — they define WHERE certain elevations exist,
not a raster surface. To convert them to a grid we:

1. SAMPLE contour coordinates as scattered control points (lon, lat, elev).
   We sub-sample densely-packed contours to avoid over-weighting them
   relative to sparse ones.

2. BUILD a Delaunay triangulation (TIN) over the control points using
   scipy.spatial.Delaunay / scipy.interpolate.LinearNDInterpolator.
   Barycentric linear interpolation inside triangles preserves the
   original elevation values exactly at contour locations and produces
   physically plausible surfaces between them.

3. EXTRAPOLATE to grid cells outside the convex hull using IDW
   (Inverse Distance Weighting) as a conservative fallback. This avoids
   NaN holes near the grid boundaries.

4. PRODUCE a regular NxN elevation_matrix (rows north→south, cols west→east)
   identical in structure to what the existing DEM API returns.

5. COMPUTE pixel_size_m using the haversine distance across one grid
   cell, identical to how the existing DEM pipeline does it.

Why LinearNDInterpolator (not pure IDW)?
---------------------------------------
- IDW produces "bull's-eye" rings around each data point.
- LinearNDInterpolator uses a proper TIN and bilinear interpolation
  within each triangle — smoother and physically better.
- It is already in scipy (no new dependencies).
- IDW is only used as a safety net for the <5% of cells outside the
  convex hull of the contour data.

Coordinate handling
-------------------
KML coordinates are lon/lat (EPSG:4326). All grid construction is done
in geographic coordinates. pixel_size_m is computed via haversine at the
centroid latitude to correctly convert degrees → metres.
"""
from __future__ import annotations

import math
import numpy as np
from typing import List, Tuple

from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import cKDTree

from backend.models.contour_analysis_models import ParsedContour
from backend.models.dem_models import BoundingBox
from backend.utils.geo_utils import haversine_distance


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Maximum number of sample points taken from all contours.
# Balances accuracy vs performance.
MAX_SAMPLE_POINTS = 8000

# Target grid dimension. Matches the existing DEM resolution default (100).
DEFAULT_GRID_SIZE = 100

# For very small or very large extents, clamp resolution.
MIN_GRID_SIZE = 20
MAX_GRID_SIZE = 150


class ContourTerrainService:
    """
    Reconstructs an elevation grid from a set of parsed contour lines.

    Entry point:
        ContourTerrainService.reconstruct_dem(contours, grid_size)
            → (elevation_matrix, BoundingBox, pixel_size_m)

    The returned types are identical to those produced by the existing
    DemService, so they feed directly into HydrologyService and
    SuitabilityService without modification.
    """

    @classmethod
    def reconstruct_dem(
        cls,
        contours: List[ParsedContour],
        grid_size: int = DEFAULT_GRID_SIZE,
    ) -> Tuple[List[List[float]], BoundingBox, float]:
        """
        Reconstruct a regular elevation grid from contour lines.

        Parameters
        ----------
        contours : list of ParsedContour
            Parsed contour lines with elevation_m and coordinates.
        grid_size : int
            Target N for the NxN output grid (rows and cols).

        Returns
        -------
        elevation_matrix : List[List[float]]
            NxN grid, row 0 = northernmost, col 0 = westernmost.
        bounds : BoundingBox
            Geographic extent (south, west, north, east) in EPSG:4326.
        pixel_size_m : float
            Approximate ground sampling distance in metres per pixel.

        Raises
        ------
        ValueError
            If reconstruction fails due to insufficient or degenerate data.
        """
        grid_size = max(MIN_GRID_SIZE, min(MAX_GRID_SIZE, grid_size))

        # --- 1. Compute geographic extent ---------------------------------
        all_lons = [lon for c in contours for lon, lat in c.coordinates]
        all_lats = [lat for c in contours for lon, lat in c.coordinates]

        min_lon, max_lon = float(min(all_lons)), float(max(all_lons))
        min_lat, max_lat = float(min(all_lats)), float(max(all_lats))

        # Expand slightly so boundary contours are not clipped
        margin_lon = (max_lon - min_lon) * 0.02
        margin_lat = (max_lat - min_lat) * 0.02
        min_lon -= margin_lon
        max_lon += margin_lon
        min_lat -= margin_lat
        max_lat += margin_lat

        bounds = BoundingBox(
            south=round(min_lat, 7),
            west=round(min_lon, 7),
            north=round(max_lat, 7),
            east=round(max_lon, 7),
        )

        # --- 2. Sample control points from contours -----------------------
        ctrl_pts, ctrl_elevs = cls._sample_control_points(contours)

        if len(ctrl_pts) < 4:
            raise ValueError(
                f"Too few control points ({len(ctrl_pts)}) for interpolation. "
                "Check that contours have valid coordinates."
            )

        pts_array = np.array(ctrl_pts)    # (N, 2) — (lon, lat)
        elev_array = np.array(ctrl_elevs)  # (N,)   — elevation_m

        # --- 3. Build regular grid ----------------------------------------
        grid_lons = np.linspace(min_lon, max_lon, grid_size)
        grid_lats = np.linspace(max_lat, min_lat, grid_size)  # north→south
        mesh_lons, mesh_lats = np.meshgrid(grid_lons, grid_lats)
        grid_xy = np.column_stack([mesh_lons.ravel(), mesh_lats.ravel()])  # (M, 2)

        # --- 4. Interpolate: Linear/TIN inside hull, Nearest outside ------
        try:
            lin_interp = LinearNDInterpolator(pts_array, elev_array)
            grid_elevs = lin_interp(grid_xy)
        except Exception as exc:
            raise ValueError(f"LinearNDInterpolator failed: {exc}") from exc

        # Fill NaNs (outside convex hull) with nearest-neighbour
        nan_mask = np.isnan(grid_elevs)
        if nan_mask.any():
            nn_interp = NearestNDInterpolator(pts_array, elev_array)
            grid_elevs[nan_mask] = nn_interp(grid_xy[nan_mask])

        # Smooth very lightly to remove triangulation artifacts along contour edges
        grid_matrix = grid_elevs.reshape(grid_size, grid_size)
        grid_matrix = cls._light_smooth(grid_matrix)

        # Final NaN check
        if np.isnan(grid_matrix).any():
            raise ValueError("Elevation grid contains NaN values after interpolation.")

        # Round to 2 decimal places (matching DEM API output)
        grid_matrix = np.round(grid_matrix, 2)

        # --- 5. Compute pixel_size_m via haversine ------------------------
        centre_lat = (max_lat + min_lat) / 2.0
        pixel_size_m = haversine_distance(
            centre_lat, min_lon,
            centre_lat, min_lon + (max_lon - min_lon) / grid_size,
        )
        pixel_size_m = max(1.0, round(pixel_size_m, 2))

        elevation_matrix = grid_matrix.tolist()
        return elevation_matrix, bounds, pixel_size_m

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _sample_control_points(
        cls,
        contours: List[ParsedContour],
    ) -> Tuple[List[Tuple[float, float]], List[float]]:
        """
        Sample (lon, lat) control points from all contours.

        Sub-samples each contour proportionally so that long contours
        do not dominate the interpolation.

        Returns
        -------
        pts   : list of (lon, lat)
        elevs : list of float (elevation_m per point)
        """
        total_pts = sum(len(c.coordinates) for c in contours)
        pts: List[Tuple[float, float]] = []
        elevs: List[float] = []

        for c in contours:
            n = len(c.coordinates)
            if total_pts <= MAX_SAMPLE_POINTS:
                sample_coords = c.coordinates
            else:
                # Sub-sample proportionally, but keep at least 2 points
                target = max(2, int(n * MAX_SAMPLE_POINTS / total_pts))
                step = max(1, n // target)
                sample_coords = c.coordinates[::step]
                # Always include last point to preserve contour end
                if len(sample_coords) and sample_coords[-1] != c.coordinates[-1]:
                    sample_coords = list(sample_coords) + [c.coordinates[-1]]

            for coord in sample_coords:
                pts.append(coord)
                elevs.append(c.elevation_m)

        return pts, elevs

    @staticmethod
    def _light_smooth(matrix: np.ndarray, passes: int = 1) -> np.ndarray:
        """
        Apply a single pass of 3x3 averaging to soften triangulation seams.

        This is mild enough that it doesn't distort the elevation values
        significantly — it only blends at the pixel level.
        """
        from scipy.ndimage import uniform_filter
        for _ in range(passes):
            matrix = uniform_filter(matrix, size=3, mode="nearest")
        return matrix

    @classmethod
    def compute_pixel_size_from_bounds(
        cls, bounds: BoundingBox, grid_size: int
    ) -> float:
        """
        Utility: compute pixel_size_m from a BoundingBox and grid dimensions.
        Used externally when bounds are already known.
        """
        centre_lat = (bounds.north + bounds.south) / 2.0
        lon_span = bounds.east - bounds.west
        pixel_size_m = haversine_distance(
            centre_lat, bounds.west,
            centre_lat, bounds.west + lon_span / grid_size,
        )
        return max(1.0, round(pixel_size_m, 2))
