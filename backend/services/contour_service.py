import uuid
import math
import numpy as np
from skimage import measure
from typing import List, Tuple, Dict, Any, Optional
from shapely.geometry import Polygon, LineString

from backend.models.dem_models import BoundingBox
from backend.models.contour_models import ContourRequest, ContourResponse, ContourPolyline
from backend.utils.geo_utils import haversine_distance, calculate_polygon_area_m2

class ContourService:
    @classmethod
    def generate_contours(cls, request: ContourRequest) -> ContourResponse:
        """
        Generates contour lines using Marching Squares (skimage.measure.find_contours).
        Transforms matrix pixel coordinates into geographic (lat, lon) polylines.
        Computes polyline length, vertex count, and enclosed area for closed contours.
        """
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        interval = float(request.interval)
        
        min_elev = float(np.nanmin(elev_matrix))
        max_elev = float(np.nanmax(elev_matrix))
        
        # Determine contour levels based on interval
        start_level = math.ceil(min_elev / interval) * interval
        end_level = math.floor(max_elev / interval) * interval
        
        if start_level > end_level:
            levels = [min_elev + (max_elev - min_elev) / 2.0]
        else:
            levels = np.arange(start_level, end_level + interval / 2.0, interval)

        # Coordinate transformation vectors
        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        
        contour_list: List[ContourPolyline] = []
        contour_counter = 0

        for level in levels:
            level_val = float(level)
            # Marching Squares algorithm to extract isolines
            contours = measure.find_contours(elev_matrix, level=level_val)
            
            for contour_idx, contour in enumerate(contours):
                # contour is an array of shape (N, 2) where col 0 is row index, col 1 is col index
                geo_coords: List[List[float]] = []
                for pt in contour:
                    r, c = pt[0], pt[1]
                    
                    # Bilinear coordinate mapping from grid indices (r, c) to (lat, lon)
                    r0, r1 = int(np.floor(r)), min(int(np.ceil(r)), rows - 1)
                    c0, c1 = int(np.floor(c)), min(int(np.ceil(c)), cols - 1)
                    
                    dr = r - r0
                    dc = c - c0
                    
                    lat = lats[r0] + dr * (lats[r1] - lats[r0]) if r0 != r1 else lats[r0]
                    lon = lons[c0] + dc * (lons[c1] - lons[c0]) if c0 != c1 else lons[c0]
                    
                    geo_coords.append([round(float(lon), 6), round(float(lat), 6)])

                if len(geo_coords) < 2:
                    continue

                # Compute polyline length in meters
                length_m = 0.0
                for i in range(len(geo_coords) - 1):
                    p1 = geo_coords[i]
                    p2 = geo_coords[i + 1]
                    length_m += haversine_distance(p1[1], p1[0], p2[1], p2[0])

                length_km = length_m / 1000.0

                # Check if polyline forms a closed contour loop
                first_pt = geo_coords[0]
                last_pt = geo_coords[-1]
                dist_ends = haversine_distance(first_pt[1], first_pt[0], last_pt[1], last_pt[0])
                is_closed = dist_ends < 15.0 or (first_pt[0] == last_pt[0] and first_pt[1] == last_pt[1])

                area_m2: Optional[float] = None
                area_km2: Optional[float] = None

                if is_closed and len(geo_coords) >= 3:
                    area_m2 = calculate_polygon_area_m2(geo_coords)
                    area_km2 = area_m2 / 1_000_000.0

                contour_counter += 1
                poly_item = ContourPolyline(
                    id=f"c_{contour_counter}_{int(level_val)}",
                    elevation=round(level_val, 1),
                    coordinates=geo_coords,
                    length_m=round(length_m, 2),
                    length_km=round(length_km, 3),
                    vertex_count=len(geo_coords),
                    is_closed=is_closed,
                    area_m2=round(area_m2, 2) if area_m2 is not None else None,
                    area_km2=round(area_km2, 4) if area_km2 is not None else None,
                )
                contour_list.append(poly_item)

        dem_id_str = request.dem_id if request.dem_id else f"dem_{uuid.uuid4().hex[:8]}"

        return ContourResponse(
            success=True,
            dem_id=dem_id_str,
            interval=interval,
            total_contours=len(contour_list),
            contours=contour_list,
        )
