import math
import numpy as np
import hashlib
from shapely.geometry import box
from backend.models.dem_models import DemRequest, LatLng
from backend.services.dem_service import DemService
from backend.services.suitability_service import SuitabilityService
from backend.models.suitability_models import SuitabilityRequest
from backend.utils.geo_utils import latlng_to_bbox, haversine_distance

# User's exact run scenarios:
# Initial location: 21.2588, 81.2954
# Scenario 1: Center = (21.2588, 81.2954)
# Scenario 2: If user clicked a candidate or different point e.g. (21.2452, 81.2840) or (21.2648, 81.2877)

lat_A, lng_A = 21.2588, 81.2954
# Run A:
req_A = DemRequest(
    center=LatLng(lat=lat_A, lng=lng_A),
    radius_km=2.0,
    provider="openzenith",
    dem_type="COP30",
    resolution=100
)
res_A = DemService.process_dem_request(req_A)
s_A, w_A, n_A, e_A = res_A.metadata.bounds.south, res_A.metadata.bounds.west, res_A.metadata.bounds.north, res_A.metadata.bounds.east
dem_A = np.array(res_A.elevation_matrix)
hash_A = hashlib.sha256(dem_A.tobytes()).hexdigest()

suit_A = SuitabilityService.analyze(SuitabilityRequest(
    elevation_matrix=res_A.elevation_matrix,
    bounds=res_A.metadata.bounds,
    pixel_size_m=res_A.metadata.pixel_size_m,
    num_candidates=10,
    rainfall_mm=800.0
))

print("=== ALL CANDIDATES IN RUN A ===")
for c in suit_A.candidates:
    print(f"Rank {c.rank}: ({c.lat:.6f}, {c.lng:.6f}) Elev={c.elevation_m}m Slope={c.slope_deg} Dep={c.depression_depth_m}m Catchment={c.catchment_area_km2:.3f}km2 Score={c.scores.composite_score}")

# Notice Candidate in Run A has (21.2648, 81.2877) or (21.2452, 81.2840)!
# Let's check candidates in Run A:
# One of the candidates is (21.264806, 81.287728) (Elev 272.2, Slope 0.1, Dep 1.19, Catchment 0.365, Score 87.3)
# Another candidate or previous center might be (21.2452, 81.2840) (Elev 274.2, Slope 0.4, Dep 1.47, Catchment 0.204, Score 86.4)

# Now let's test if Run B was started from (21.2452, 81.2840) or another center:
lat_B, lng_B = 21.2452, 81.2840
req_B = DemRequest(
    center=LatLng(lat=lat_B, lng=lng_B),
    radius_km=2.0,
    provider="openzenith",
    dem_type="COP30",
    resolution=100
)
res_B = DemService.process_dem_request(req_B)
s_B, w_B, n_B, e_B = res_B.metadata.bounds.south, res_B.metadata.bounds.west, res_B.metadata.bounds.north, res_B.metadata.bounds.east
dem_B = np.array(res_B.elevation_matrix)
hash_B = hashlib.sha256(dem_B.tobytes()).hexdigest()

suit_B = SuitabilityService.analyze(SuitabilityRequest(
    elevation_matrix=res_B.elevation_matrix,
    bounds=res_B.metadata.bounds,
    pixel_size_m=res_B.metadata.pixel_size_m,
    num_candidates=10,
    rainfall_mm=800.0
))

print("\n=== ALL CANDIDATES IN RUN B (Center = 21.2452, 81.2840) ===")
for c in suit_B.candidates:
    print(f"Rank {c.rank}: ({c.lat:.6f}, {c.lng:.6f}) Elev={c.elevation_m}m Slope={c.slope_deg} Dep={c.depression_depth_m}m Catchment={c.catchment_area_km2:.3f}km2 Score={c.scores.composite_score}")

print("\n=== COMPARISON METRICS ===")
dist_m = haversine_distance(lat_A, lng_A, lat_B, lng_B)
print(f"Center A: ({lat_A}, {lng_A})")
print(f"Center B: ({lat_B}, {lng_B})")
print(f"Distance between centers: {dist_m:.2f} m")

poly_A = box(w_A, s_A, e_A, n_A)
poly_B = box(w_B, s_B, e_B, n_B)
inter = poly_A.intersection(poly_B)
pct_overlap = (inter.area / poly_A.area) * 100.0

print(f"Bounds A: S={s_A:.6f}, W={w_A:.6f}, N={n_A:.6f}, E={e_A:.6f}")
print(f"Bounds B: S={s_B:.6f}, W={w_B:.6f}, N={n_B:.6f}, E={e_B:.6f}")
print(f"Width A: {haversine_distance(s_A, w_A, s_A, e_A):.2f}m, Height A: {haversine_distance(s_A, w_A, n_A, w_A):.2f}m")
print(f"Width B: {haversine_distance(s_B, w_B, s_B, e_B):.2f}m, Height B: {haversine_distance(s_B, w_B, n_B, w_B):.2f}m")
print(f"Geographic overlap: {pct_overlap:.2f}%")
print(f"DEM A hash: {hash_A}")
print(f"DEM B hash: {hash_B}")
print(f"DEM A min/max/mean: {dem_A.min():.2f}/{dem_A.max():.2f}/{dem_A.mean():.2f}")
print(f"DEM B min/max/mean: {dem_B.min():.2f}/{dem_B.max():.2f}/{dem_B.mean():.2f}")
