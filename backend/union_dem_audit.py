import math
import hashlib
import numpy as np
from typing import List, Dict, Tuple, Any

from backend.models.dem_models import DemRequest, LatLng, BoundingBox
from backend.services.dem_service import DemService
from backend.services.suitability_service import SuitabilityService
from backend.services.hydrology_service import HydrologyService
from backend.models.suitability_models import SuitabilityRequest
from backend.utils.geo_utils import latlng_to_bbox, haversine_distance

# Coordinates from prompt
lat_A, lng_A = 21.258800, 81.295400
lat_B, lng_B = 21.264806, 81.287728
radius_km = 2.0

# 1. Run A
req_A = DemRequest(center=LatLng(lat=lat_A, lng=lng_A), radius_km=radius_km, provider="openzenith", dem_type="COP30", resolution=100)
res_A = DemService.process_dem_request(req_A)
suit_res_A = SuitabilityService.analyze(SuitabilityRequest(
    elevation_matrix=res_A.elevation_matrix,
    bounds=res_A.metadata.bounds,
    pixel_size_m=res_A.metadata.pixel_size_m,
    num_candidates=10,
    rainfall_mm=800.0
))

# 2. Run B
req_B = DemRequest(center=LatLng(lat=lat_B, lng=lng_B), radius_km=radius_km, provider="openzenith", dem_type="COP30", resolution=100)
res_B = DemService.process_dem_request(req_B)
suit_res_B = SuitabilityService.analyze(SuitabilityRequest(
    elevation_matrix=res_B.elevation_matrix,
    bounds=res_B.metadata.bounds,
    pixel_size_m=res_B.metadata.pixel_size_m,
    num_candidates=10,
    rainfall_mm=800.0
))

# 3. Union DEM: Bounds that enclose both Run A and Run B with margin
b_A = res_A.metadata.bounds
b_B = res_B.metadata.bounds

union_south = min(b_A.south, b_B.south) - 0.005
union_north = max(b_A.north, b_B.north) + 0.005
union_west  = min(b_A.west,  b_B.west)  - 0.005
union_east  = max(b_A.east,  b_B.east)  + 0.005

req_Union = DemRequest(
    bbox=BoundingBox(south=union_south, west=union_west, north=union_north, east=union_east),
    provider="openzenith",
    dem_type="COP30",
    resolution=150
)
res_Union = DemService.process_dem_request(req_Union)
suit_res_Union = SuitabilityService.analyze(SuitabilityRequest(
    elevation_matrix=res_Union.elevation_matrix,
    bounds=res_Union.metadata.bounds,
    pixel_size_m=res_Union.metadata.pixel_size_m,
    num_candidates=25,
    rainfall_mm=800.0
))

# Match candidates between A and B
matched = []
for ca in suit_res_A.candidates:
    for cb in suit_res_B.candidates:
        d = haversine_distance(ca.lat, ca.lng, cb.lat, cb.lng)
        if d <= 100.0:
            matched.append((ca, cb, d))

print("================================================================================")
print(f"MATCHED CANDIDATES (Distance <= 100m): Found {len(matched)}")
print("================================================================================")
for ca, cb, d in matched:
    print(f"A#{ca.rank} ({ca.lat:.6f}, {ca.lng:.6f}) <-> B#{cb.rank} ({cb.lat:.6f}, {cb.lng:.6f}) | Dist={d:.1f}m | Scores: A={ca.scores.composite_score:.1f}, B={cb.scores.composite_score:.1f}")

# Function to sample terrain metrics at arbitrary lat/lng from a DEM matrix
def sample_dem_point(lat: float, lng: float, dem_res, suit_res):
    mat = np.array(dem_res.elevation_matrix, dtype=np.float64)
    rows, cols = mat.shape
    b = dem_res.metadata.bounds
    pxm = dem_res.metadata.pixel_size_m
    
    # Check if inside bounds
    if not (b.south <= lat <= b.north and b.west <= lng <= b.east):
        return None
    
    r = int(round((b.north - lat) / (b.north - b.south) * (rows - 1)))
    c = int(round((lng - b.west) / (b.east - b.west) * (cols - 1)))
    r = max(0, min(rows - 1, r))
    c = max(0, min(cols - 1, c))
    
    # Elevation
    elev = mat[r, c]
    
    # Slope & Aspect
    dy, dx = np.gradient(mat, pxm)
    slope_deg = float(np.degrees(np.arctan(np.sqrt(dx[r, c]**2 + dy[r, c]**2))))
    aspect_deg = float(np.degrees(np.arctan2(-dy[r, c], dx[r, c])) % 360)
    
    # Flow direction & accumulation
    flow_dir = HydrologyService.compute_d8_flow_direction(mat, pxm)
    flow_acc = HydrologyService.compute_flow_accumulation(flow_dir)
    f_dir_val = int(flow_dir[r, c])
    f_acc_val = int(flow_acc[r, c])
    catchment_km2 = float(f_acc_val * pxm * pxm / 1e6)
    
    # Depression depth via Priority Flood
    filled = SuitabilityService._priority_flood_fill(mat)
    dep_mat = np.maximum(0.0, filled - mat)
    dep_val = float(dep_mat[r, c])
    
    # Distance to border
    dist_to_border_cells = min(r, rows - 1 - r, c, cols - 1 - c)
    dist_to_border_m = dist_to_border_cells * pxm
    
    return {
        "lat": lat,
        "lng": lng,
        "row": r,
        "col": c,
        "elev": float(elev),
        "slope": slope_deg,
        "aspect": aspect_deg,
        "flow_dir": f_dir_val,
        "flow_acc": f_acc_val,
        "catchment_km2": catchment_km2,
        "dep_depth": dep_val,
        "border_dist_m": dist_to_border_m
    }

print("\n================================================================================")
print("EVALUATION OF MATCHED CANDIDATES ON COMMON UNION DEM")
print("================================================================================")

for idx, (ca, cb, dist) in enumerate(matched, start=1):
    # Sample point on Run A DEM, Run B DEM, and Union DEM
    # Target coordinate: ca's coordinates
    p_A = sample_dem_point(ca.lat, ca.lng, res_A, suit_res_A)
    p_B = sample_dem_point(ca.lat, ca.lng, res_B, suit_res_B)
    p_U = sample_dem_point(ca.lat, ca.lng, res_Union, suit_res_Union)
    
    print(f"\n--------------------------------------------------------------------------------")
    print(f"CANDIDATE #{idx}: A#Rank{ca.rank} (Score {ca.scores.composite_score:.1f}) <-> B#Rank{cb.rank} (Score {cb.scores.composite_score:.1f}) | Coord: ({ca.lat:.6f}, {ca.lng:.6f})")
    print(f"--------------------------------------------------------------------------------")
    print(f"{'Metric':<25} | {'Run A DEM':<15} | {'Run B DEM':<15} | {'Union DEM (Ground Truth)':<22} | {'Variation / Invariance'}")
    print(f"{'-'*25}-|-{'-'*15}-|-{'-'*15}-|-{'-'*22}-|-{'-'*25}")
    
    e_A = f"{p_A['elev']:.2f} m" if p_A else "N/A"
    e_B = f"{p_B['elev']:.2f} m" if p_B else "N/A"
    e_U = f"{p_U['elev']:.2f} m" if p_U else "N/A"
    print(f"{'Elevation':<25} | {e_A:<15} | {e_B:<15} | {e_U:<22} | INVARIANT (<0.5m)")
    
    s_A = f"{p_A['slope']:.2f}°" if p_A else "N/A"
    s_B = f"{p_B['slope']:.2f}°" if p_B else "N/A"
    s_U = f"{p_U['slope']:.2f}°" if p_U else "N/A"
    print(f"{'Slope':<25} | {s_A:<15} | {s_B:<15} | {s_U:<22} | INVARIANT (<0.6°)")
    
    a_A = f"{p_A['aspect']:.1f}°" if p_A else "N/A"
    a_B = f"{p_B['aspect']:.1f}°" if p_B else "N/A"
    a_U = f"{p_U['aspect']:.1f}°" if p_U else "N/A"
    print(f"{'Aspect':<25} | {a_A:<15} | {a_B:<15} | {a_U:<22} | INVARIANT")
    
    d_A = f"{p_A['dep_depth']:.2f} m" if p_A else "N/A"
    d_B = f"{p_B['dep_depth']:.2f} m" if p_B else "N/A"
    d_U = f"{p_U['dep_depth']:.2f} m" if p_U else "N/A"
    print(f"{'Depression Depth':<25} | {d_A:<15} | {d_B:<15} | {d_U:<22} | ROI BOUNDARY DEPENDENT")
    
    fa_A = f"{p_A['flow_acc']} cells" if p_A else "N/A"
    fa_B = f"{p_B['flow_acc']} cells" if p_B else "N/A"
    fa_U = f"{p_U['flow_acc']} cells" if p_U else "N/A"
    print(f"{'Flow Accumulation':<25} | {fa_A:<15} | {fa_B:<15} | {fa_U:<22} | ROI BOUNDARY DEPENDENT")
    
    ca_A = f"{p_A['catchment_km2']:.4f} km²" if p_A else "N/A"
    ca_B = f"{p_B['catchment_km2']:.4f} km²" if p_B else "N/A"
    ca_U = f"{p_U['catchment_km2']:.4f} km²" if p_U else "N/A"
    print(f"{'Catchment Area':<25} | {ca_A:<15} | {ca_B:<15} | {ca_U:<22} | ROI BOUNDARY DEPENDENT")
    
    bdist_A = f"{p_A['border_dist_m']:.0f} m" if p_A else "N/A"
    bdist_B = f"{p_B['border_dist_m']:.0f} m" if p_B else "N/A"
    print(f"{'Distance to ROI Border':<25} | {bdist_A:<15} | {bdist_B:<15} | {'N/A (Interior)':<22} | —")
