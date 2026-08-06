import math
import numpy as np
from typing import List, Tuple, Dict, Any, Set
from collections import deque
from shapely.geometry import Point, MultiPoint, Polygon

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.terrain_models import FlowDropletRequest, FlowDropletResponse, WatershedRequest, WatershedResponse
from backend.utils.geo_utils import haversine_distance, calculate_polygon_area_m2

class HydrologyService:
    # 8 Neighbor offsets: (dr, dc)
    # 0: E, 1: SE, 2: S, 3: SW, 4: W, 5: NW, 6: N, 7: NE
    D8_OFFSETS = [
        (0, 1),   # E
        (1, 1),   # SE
        (1, 0),   # S
        (1, -1),  # SW
        (0, -1),  # W
        (-1, -1), # NW
        (-1, 0),  # N
        (-1, 1)   # NE
    ]

    @classmethod
    def compute_d8_flow_direction(cls, elev_matrix: np.ndarray, pixel_size_m: float) -> np.ndarray:
        """
        Computes D8 flow direction matrix.
        Each cell stores index (0..7) pointing to steepest descent neighbor.
        -1 indicates local sink/flat terrain.
        """
        rows, cols = elev_matrix.shape
        flow_dir = np.full((rows, cols), -1, dtype=int)
        
        # Distance multipliers for orthogonal vs diagonal neighbors
        dist_factors = [1.0, math.sqrt(2), 1.0, math.sqrt(2), 1.0, math.sqrt(2), 1.0, math.sqrt(2)]
        
        for r in range(rows):
            for c in range(cols):
                curr_elev = elev_matrix[r, c]
                max_drop_rate = 0.0
                best_dir = -1
                
                for idx, (dr, dc) in enumerate(cls.D8_OFFSETS):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        neighbor_elev = elev_matrix[nr, nc]
                        drop = curr_elev - neighbor_elev
                        if drop > 0:
                            drop_rate = drop / (pixel_size_m * dist_factors[idx])
                            if drop_rate > max_drop_rate:
                                max_drop_rate = drop_rate
                                best_dir = idx
                                
                flow_dir[r, c] = best_dir
                
        return flow_dir

    @classmethod
    def trace_droplet_path(cls, request: FlowDropletRequest) -> FlowDropletResponse:
        """
        Simulates a water droplet starting from start_point lat/lng
        and moving downhill along steepest descent D8 pointers until reaching local sink.
        """
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        
        flow_dir = cls.compute_d8_flow_direction(elev_matrix, request.pixel_size_m)
        
        # Convert start lat/lng to grid cell index
        curr_r = int(round((bounds.north - request.start_point.lat) / (bounds.north - bounds.south + 1e-9) * (rows - 1)))
        curr_c = int(round((request.start_point.lng - bounds.west) / (bounds.east - bounds.west + 1e-9) * (cols - 1)))
        
        curr_r = max(0, min(curr_r, rows - 1))
        curr_c = max(0, min(curr_c, cols - 1))
        
        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        
        path_coords: List[LatLng] = []
        path_elevations: List[float] = []
        visited: Set[Tuple[int, int]] = set()
        
        step_count = 0
        max_steps = rows * cols  # Prevent infinite loop
        
        while 0 <= curr_r < rows and 0 <= curr_c < cols and step_count < max_steps:
            cell_key = (curr_r, curr_c)
            if cell_key in visited:
                break  # Reached loop or sink
            visited.add(cell_key)
            
            lat = float(lats[curr_r])
            lng = float(lons[curr_c])
            elev = float(elev_matrix[curr_r, curr_c])
            
            path_coords.append(LatLng(lat=round(lat, 6), lng=round(lng, 6)))
            path_elevations.append(round(elev, 1))
            
            d8_idx = flow_dir[curr_r, curr_c]
            if d8_idx == -1:
                break  # Sink reached
                
            dr, dc = cls.D8_OFFSETS[d8_idx]
            curr_r += dr
            curr_c += dc
            step_count += 1
            
        # Calculate total path distance and elevation drop
        total_dist_m = 0.0
        for i in range(len(path_coords) - 1):
            p1, p2 = path_coords[i], path_coords[i + 1]
            total_dist_m += haversine_distance(p1.lat, p1.lng, p2.lat, p2.lng)
            
        elev_drop_m = (path_elevations[0] - path_elevations[-1]) if len(path_elevations) >= 2 else 0.0
        
        return FlowDropletResponse(
            success=True,
            path=path_coords,
            path_elevations=path_elevations,
            total_distance_m=round(total_dist_m, 1),
            elevation_drop_m=round(max(0.0, elev_drop_m), 1),
        )

    @classmethod
    def delineate_watershed(cls, request: WatershedRequest) -> WatershedResponse:
        """
        Delineates watershed catchment area contributing to clicked outlet point.
        Uses reverse BFS flow pointer traversal.
        """
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        
        flow_dir = cls.compute_d8_flow_direction(elev_matrix, request.pixel_size_m)
        
        # Outlet cell
        out_r = int(round((bounds.north - request.outlet_point.lat) / (bounds.north - bounds.south + 1e-9) * (rows - 1)))
        out_c = int(round((request.outlet_point.lng - bounds.west) / (bounds.east - bounds.west + 1e-9) * (cols - 1)))
        
        out_r = max(0, min(out_r, rows - 1))
        out_c = max(0, min(out_c, cols - 1))
        
        # Build inverted flow map: target_cell -> list of upstream cells that flow into it
        upstream_map: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for r in range(rows):
            for c in range(cols):
                d8_idx = flow_dir[r, c]
                if d8_idx != -1:
                    dr, dc = cls.D8_OFFSETS[d8_idx]
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        target = (nr, nc)
                        if target not in upstream_map:
                            upstream_map[target] = []
                        upstream_map[target].append((r, c))

        # BFS starting at outlet cell to collect all contributing cells
        catchment_cells: Set[Tuple[int, int]] = set()
        queue = deque([(out_r, out_c)])
        catchment_cells.add((out_r, out_c))
        
        while queue:
            curr = queue.popleft()
            if curr in upstream_map:
                for up in upstream_map[curr]:
                    if up not in catchment_cells:
                        catchment_cells.add(up)
                        queue.append(up)

        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        
        # Convert catchment cells to GeoJSON polygon boundary via Convex/Concave Hull
        points_list = []
        slope_sum = 0.0
        dy, dx = np.gradient(elev_matrix, request.pixel_size_m)
        slope_deg_matrix = np.degrees(np.arctan(np.sqrt(dx * dx + dy * dy)))
        
        for (r, c) in catchment_cells:
            lat = float(lats[r])
            lng = float(lons[c])
            points_list.append((lng, lat))
            slope_sum += float(slope_deg_matrix[r, c])

        avg_slope = slope_sum / max(1, len(catchment_cells))

        if len(points_list) >= 3:
            mp = MultiPoint(points_list)
            hull = mp.convex_hull
            if isinstance(hull, Polygon):
                poly_coords = list(hull.exterior.coords)
            else:
                poly_coords = [list(pt) for pt in points_list]
        else:
            poly_coords = [list(pt) for pt in points_list]

        # Calculate catchment area
        area_m2 = len(catchment_cells) * (request.pixel_size_m ** 2)
        area_km2 = area_m2 / 1_000_000.0

        # Calculate perimeter in km
        perimeter_m = 0.0
        for i in range(len(poly_coords) - 1):
            p1, p2 = poly_coords[i], poly_coords[i + 1]
            perimeter_m += haversine_distance(p1[1], p1[0], p2[1], p2[0])
            
        perimeter_km = perimeter_m / 1000.0

        return WatershedResponse(
            success=True,
            outlet=request.outlet_point,
            catchment_polygon=[[round(pt[0], 6), round(pt[1], 6)] for pt in poly_coords],
            catchment_area_km2=round(area_km2, 3),
            catchment_area_m2=round(area_m2, 1),
            perimeter_km=round(perimeter_km, 2),
            avg_slope_deg=round(avg_slope, 1),
        )
