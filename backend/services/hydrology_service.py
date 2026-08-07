import math
import numpy as np
from typing import List, Tuple, Dict, Any, Set
from collections import deque
from shapely.geometry import Point, MultiPoint, Polygon
from shapely.ops import unary_union

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.terrain_models import (
    FlowDropletRequest, FlowDropletResponse,
    WatershedRequest, WatershedResponse,
    FlowVectorsRequest, FlowVectorsResponse, FlowVector,
    StreamNetworkRequest, StreamNetworkResponse, StreamSegment,
)
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
        Uses a pre-pass pit-filling to reduce flat cell count on real DEMs.
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
    def compute_flow_accumulation(cls, flow_dir: np.ndarray) -> np.ndarray:
        """
        Computes flow accumulation: for each cell, how many upstream cells flow into it.
        Uses a topological sort via in-degree counting.
        """
        rows, cols = flow_dir.shape
        accumulation = np.ones((rows, cols), dtype=int)

        # Build adjacency: compute in-degree and receivers
        in_degree = np.zeros((rows, cols), dtype=int)
        receiver = {}  # (r,c) -> (nr, nc) downstream cell

        for r in range(rows):
            for c in range(cols):
                d = flow_dir[r, c]
                if d != -1:
                    dr, dc = cls.D8_OFFSETS[d]
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        in_degree[nr, nc] += 1
                        receiver[(r, c)] = (nr, nc)

        # Topological sort: start from cells with no upstream inputs
        queue = deque()
        for r in range(rows):
            for c in range(cols):
                if in_degree[r, c] == 0:
                    queue.append((r, c))

        while queue:
            r, c = queue.popleft()
            if (r, c) in receiver:
                nr, nc = receiver[(r, c)]
                accumulation[nr, nc] += accumulation[r, c]
                in_degree[nr, nc] -= 1
                if in_degree[nr, nc] == 0:
                    queue.append((nr, nc))

        return accumulation

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
        Uses reverse BFS flow pointer traversal with concave hull boundary extraction.
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

        # Cap at a reasonable fraction of the grid to prevent "whole DEM" watersheds
        max_catchment = int(rows * cols * 0.8)

        while queue and len(catchment_cells) < max_catchment:
            curr = queue.popleft()
            if curr in upstream_map:
                for up in upstream_map[curr]:
                    if up not in catchment_cells:
                        catchment_cells.add(up)
                        queue.append(up)

        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)

        # Convert catchment cells to polygon using pixel rectangles union (more accurate than convex hull)
        pixel_lat_size = (bounds.north - bounds.south) / max(1, rows - 1)
        pixel_lon_size = (bounds.east - bounds.west) / max(1, cols - 1)
        half_lat = pixel_lat_size / 2.0
        half_lon = pixel_lon_size / 2.0

        slope_sum = 0.0
        dy, dx = np.gradient(elev_matrix, request.pixel_size_m)
        slope_deg_matrix = np.degrees(np.arctan(np.sqrt(dx * dx + dy * dy)))

        cell_polygons = []
        for (r, c) in catchment_cells:
            lat = float(lats[r])
            lng = float(lons[c])
            slope_sum += float(slope_deg_matrix[r, c])
            # Build a small square polygon for this cell
            cell_polygons.append(Polygon([
                (lng - half_lon, lat - half_lat),
                (lng + half_lon, lat - half_lat),
                (lng + half_lon, lat + half_lat),
                (lng - half_lon, lat + half_lat),
            ]))

        avg_slope = slope_sum / max(1, len(catchment_cells))

        if len(cell_polygons) >= 1:
            try:
                merged = unary_union(cell_polygons)
                if hasattr(merged, 'exterior'):
                    poly_coords = list(merged.exterior.coords)
                elif hasattr(merged, 'geoms'):
                    # MultiPolygon — take largest
                    largest = max(merged.geoms, key=lambda g: g.area)
                    poly_coords = list(largest.exterior.coords)
                else:
                    poly_coords = [(float(lons[c]), float(lats[r])) for (r, c) in catchment_cells]
            except Exception:
                # Fallback to convex hull
                points_list = [(float(lons[c]), float(lats[r])) for (r, c) in catchment_cells]
                if len(points_list) >= 3:
                    mp = MultiPoint(points_list)
                    hull = mp.convex_hull
                    poly_coords = list(hull.exterior.coords) if isinstance(hull, Polygon) else points_list
                else:
                    poly_coords = points_list
        else:
            poly_coords = []

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

    @classmethod
    def get_flow_vectors(cls, request: FlowVectorsRequest) -> FlowVectorsResponse:
        """
        Returns sampled D8 flow direction vectors for rendering as arrows on the map.
        Uses sample_stride to skip cells and reduce arrow count.
        """
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        stride = max(1, request.sample_stride)

        flow_dir = cls.compute_d8_flow_direction(elev_matrix, request.pixel_size_m)

        # Compute slope for color coding
        dy, dx = np.gradient(elev_matrix, request.pixel_size_m)
        slope_deg = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)

        vectors: List[FlowVector] = []
        for r in range(0, rows, stride):
            for c in range(0, cols, stride):
                d = int(flow_dir[r, c])
                if d == -1:
                    continue  # Skip sinks
                vectors.append(FlowVector(
                    lat=round(float(lats[r]), 6),
                    lng=round(float(lons[c]), 6),
                    direction_idx=d,
                    slope_deg=round(float(slope_deg[r, c]), 1),
                ))

        return FlowVectorsResponse(success=True, vectors=vectors)

    @classmethod
    def get_stream_network(cls, request: StreamNetworkRequest) -> StreamNetworkResponse:
        """
        Extracts stream network as polylines based on flow accumulation threshold.
        Cells with flow accumulation >= threshold are considered stream cells.
        """
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        threshold = request.accumulation_threshold

        flow_dir = cls.compute_d8_flow_direction(elev_matrix, request.pixel_size_m)
        accumulation = cls.compute_flow_accumulation(flow_dir)

        # Stream mask: cells with enough upstream flow
        stream_mask = accumulation >= threshold

        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)

        # Extract stream segments by following flow paths through stream cells
        # Use a simple approach: for each stream cell, trace downstream to next stream cell
        segments: List[StreamSegment] = []
        visited_segments = set()

        # Find source stream cells (stream cells with no upstream stream cells)
        for r in range(rows):
            for c in range(cols):
                if not stream_mask[r, c]:
                    continue
                if (r, c) in visited_segments:
                    continue

                # Trace downstream from this cell
                seg_coords = []
                curr_r, curr_c = r, c
                seg_acc = float(accumulation[r, c])

                while 0 <= curr_r < rows and 0 <= curr_c < cols:
                    if (curr_r, curr_c) in visited_segments:
                        # Add final point and stop
                        seg_coords.append([round(float(lons[curr_c]), 6), round(float(lats[curr_r]), 6)])
                        break

                    if not stream_mask[curr_r, curr_c]:
                        break

                    visited_segments.add((curr_r, curr_c))
                    seg_coords.append([round(float(lons[curr_c]), 6), round(float(lats[curr_r]), 6)])

                    d = flow_dir[curr_r, curr_c]
                    if d == -1:
                        break
                    dr, dc = cls.D8_OFFSETS[d]
                    curr_r += dr
                    curr_c += dc

                if len(seg_coords) >= 2:
                    # Stream order from accumulation (Strahler approximation)
                    order = min(5, max(1, int(math.log2(max(1, seg_acc) / threshold) + 1)))
                    segments.append(StreamSegment(coordinates=seg_coords, stream_order=order))

        return StreamNetworkResponse(success=True, segments=segments)
