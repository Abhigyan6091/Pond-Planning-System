import math
import json
import hashlib
import numpy as np
from typing import List, Dict, Any, Tuple
from shapely.geometry import box

from backend.models.dem_models import DemRequest, LatLng
from backend.services.dem_service import DemService
from backend.services.suitability_service import SuitabilityService
from backend.models.suitability_models import SuitabilityRequest, CandidateSite
from backend.utils.geo_utils import latlng_to_bbox, haversine_distance

def run_pipeline(center_lat: float, center_lng: float, radius_km: float = 2.0, rainfall_mm: float = 800.0):
    req = DemRequest(
        center=LatLng(lat=center_lat, lng=center_lng),
        radius_km=radius_km,
        provider="openzenith",
        dem_type="COP30",
        resolution=100
    )
    dem_res = DemService.process_dem_request(req)
    dem_mat = np.array(dem_res.elevation_matrix, dtype=np.float64)
    dem_hash = hashlib.sha256(dem_mat.tobytes()).hexdigest()
    
    suit_req = SuitabilityRequest(
        elevation_matrix=dem_res.elevation_matrix,
        bounds=dem_res.metadata.bounds,
        pixel_size_m=dem_res.metadata.pixel_size_m,
        num_candidates=10,
        rainfall_mm=rainfall_mm
    )
    suit_res = SuitabilityService.analyze(suit_req)
    
    return {
        "dem_res": dem_res,
        "dem_mat": dem_mat,
        "dem_hash": dem_hash,
        "suit_res": suit_res,
        "candidates": suit_res.candidates,
        "recommended": suit_res.recommended
    }

print("================================================================================")
print("FORENSIC CANDIDATE-BY-CANDIDATE REPRODUCIBILITY AUDIT")
print("================================================================================")

# 1. RUN A
lat_A, lng_A = 21.2588, 81.2954
res_A = run_pipeline(lat_A, lng_A)
cands_A = res_A["candidates"]

# 2. RUN B (using candidate #1 of Run A or specified candidate 21.264806, 81.287728)
lat_B, lng_B = 21.264806, 81.287728
res_B = run_pipeline(lat_B, lng_B)
cands_B = res_B["candidates"]

print("\n--- RUN A METADATA ---")
print(f"Center: ({lat_A}, {lng_A})")
b_A = res_A["dem_res"].metadata.bounds
print(f"Bounds: S={b_A.south:.6f}, W={b_A.west:.6f}, N={b_A.north:.6f}, E={b_A.east:.6f}")
print(f"DEM Hash: {res_A['dem_hash']}")
print(f"DEM min/max/mean/std: {res_A['dem_mat'].min():.2f} / {res_A['dem_mat'].max():.2f} / {res_A['dem_mat'].mean():.2f} / {res_A['dem_mat'].std():.2f}")
print(f"Pixel Size: {res_A['dem_res'].metadata.pixel_size_m:.2f} m")

print("\n--- RUN B METADATA ---")
print(f"Center: ({lat_B}, {lng_B})")
b_B = res_B["dem_res"].metadata.bounds
print(f"Bounds: S={b_B.south:.6f}, W={b_B.west:.6f}, N={b_B.north:.6f}, E={b_B.east:.6f}")
print(f"DEM Hash: {res_B['dem_hash']}")
print(f"DEM min/max/mean/std: {res_B['dem_mat'].min():.2f} / {res_B['dem_mat'].max():.2f} / {res_B['dem_mat'].mean():.2f} / {res_B['dem_mat'].std():.2f}")
print(f"Pixel Size: {res_B['dem_res'].metadata.pixel_size_m:.2f} m")

print("\n--- RUN A CANDIDATES (Top 10) ---")
for c in cands_A:
    print(f"Rank {c.rank:2d}: ({c.lat:.6f}, {c.lng:.6f}) Elev={c.elevation_m:5.1f}m Slope={c.slope_deg:4.1f}° Dep={c.depression_depth_m:4.2f}m FlowAcc={c.flow_accumulation:4d} Catchment={c.catchment_area_km2:.4f}km² Score={c.scores.composite_score:4.1f} [SlpPts={c.scores.slope_pts:.1f} DepPts={c.scores.depression_pts:.1f} CatPts={c.scores.catchment_pts:.1f} ElvPts={c.scores.elevation_pts:.1f} RnPts={c.scores.rainfall_pts:.1f}] Tier={c.suitability_tier}")

print("\n--- RUN B CANDIDATES (Top 10) ---")
for c in cands_B:
    print(f"Rank {c.rank:2d}: ({c.lat:.6f}, {c.lng:.6f}) Elev={c.elevation_m:5.1f}m Slope={c.slope_deg:4.1f}° Dep={c.depression_depth_m:4.2f}m FlowAcc={c.flow_accumulation:4d} Catchment={c.catchment_area_km2:.4f}km² Score={c.scores.composite_score:4.1f} [SlpPts={c.scores.slope_pts:.1f} DepPts={c.scores.depression_pts:.1f} CatPts={c.scores.catchment_pts:.1f} ElvPts={c.scores.elevation_pts:.1f} RnPts={c.scores.rainfall_pts:.1f}] Tier={c.suitability_tier}")

# 2. MATCHING CANDIDATES
MATCH_TOLERANCE_M = 120.0  # ~2 pixels tolerance

matched_pairs = []
unmatched_A = []
matched_B_indices = set()

for ca in cands_A:
    best_dist = float("inf")
    best_cb = None
    best_idx_b = -1
    for idx_b, cb in enumerate(cands_B):
        d = haversine_distance(ca.lat, ca.lng, cb.lat, cb.lng)
        if d < best_dist:
            best_dist = d
            best_cb = cb
            best_idx_b = idx_b
    if best_dist <= MATCH_TOLERANCE_M and best_idx_b not in matched_B_indices:
        matched_pairs.append((ca, best_cb, best_dist))
        matched_B_indices.add(best_idx_b)
    else:
        unmatched_A.append(ca)

unmatched_B = [cb for idx_b, cb in enumerate(cands_B) if idx_b not in matched_B_indices]

print("\n================================================================================")
print("CANDIDATE MATCHING TABLE (Tolerance: 120m)")
print("================================================================================")
for ca, cb, dist in matched_pairs:
    print(f"MATCH: A#Rank{ca.rank} ({ca.lat:.6f}, {ca.lng:.6f}) <-> B#Rank{cb.rank} ({cb.lat:.6f}, {cb.lng:.6f}) | Dist={dist:.1f}m | Score A={ca.scores.composite_score:.1f} B={cb.scores.composite_score:.1f}")

print("\n--- UNMATCHED CANDIDATES IN RUN A ---")
for ca in unmatched_A:
    print(f"Only in A: #Rank{ca.rank} ({ca.lat:.6f}, {ca.lng:.6f}) Elev={ca.elevation_m}m Dep={ca.depression_depth_m}m Catch={ca.catchment_area_km2:.3f}km² Score={ca.scores.composite_score:.1f}")

print("\n--- UNMATCHED CANDIDATES IN RUN B ---")
for cb in unmatched_B:
    print(f"Only in B: #Rank{cb.rank} ({cb.lat:.6f}, {cb.lng:.6f}) Elev={cb.elevation_m}m Dep={cb.depression_depth_m}m Catch={cb.catchment_area_km2:.3f}km² Score={cb.scores.composite_score:.1f}")

print("\n================================================================================")
print("TERRAIN METRIC COMPARISON FOR MATCHED SITES")
print("================================================================================")
for ca, cb, dist in matched_pairs:
    print(f"\n--- Site A#Rank{ca.rank} vs B#Rank{cb.rank} (Distance = {dist:.1f}m) ---")
    print(f"  Coordinates:       A=({ca.lat:.6f}, {ca.lng:.6f})  B=({cb.lat:.6f}, {cb.lng:.6f})")
    print(f"  Elevation (m):     A={ca.elevation_m:5.1f}  B={cb.elevation_m:5.1f}  (Diff = {cb.elevation_m - ca.elevation_m:+.1f})")
    print(f"  Slope (deg):       A={ca.slope_deg:5.1f}  B={cb.slope_deg:5.1f}  (Diff = {cb.slope_deg - ca.slope_deg:+.1f})")
    print(f"  Depression (m):    A={ca.depression_depth_m:5.2f}  B={cb.depression_depth_m:5.2f}  (Diff = {cb.depression_depth_m - ca.depression_depth_m:+.2f})")
    print(f"  Flow Acc (cells):  A={ca.flow_accumulation:5d}  B={cb.flow_accumulation:5d}  (Diff = {cb.flow_accumulation - ca.flow_accumulation:+d})")
    print(f"  Catchment (km²):   A={ca.catchment_area_km2:6.4f} B={cb.catchment_area_km2:6.4f} (Diff = {cb.catchment_area_km2 - ca.catchment_area_km2:+.4f})")
    print(f"  Pond Depth (m):    A={ca.estimated_depth_m:5.2f}  B={cb.estimated_depth_m:5.2f}")
    print(f"  Pond Vol (m³):     A={ca.estimated_volume_m3:7.0f} B={cb.estimated_volume_m3:7.0f}")
    print(f"  Score Breakdown:")
    print(f"    Slope Pts (20):      A={ca.scores.slope_pts:4.1f}  B={cb.scores.slope_pts:4.1f}  (Diff = {cb.scores.slope_pts - ca.scores.slope_pts:+.1f})")
    print(f"    Depression Pts (20): A={ca.scores.depression_pts:4.1f}  B={cb.scores.depression_pts:4.1f}  (Diff = {cb.scores.depression_pts - ca.scores.depression_pts:+.1f})")
    print(f"    Catchment Pts (25):  A={ca.scores.catchment_pts:4.1f}  B={cb.scores.catchment_pts:4.1f}  (Diff = {cb.scores.catchment_pts - ca.scores.catchment_pts:+.1f})")
    print(f"    Elevation Pts (15):  A={ca.scores.elevation_pts:4.1f}  B={cb.scores.elevation_pts:4.1f}  (Diff = {cb.scores.elevation_pts - ca.scores.elevation_pts:+.1f})")
    print(f"    Rainfall Pts (20):   A={ca.scores.rainfall_pts:4.1f}  B={cb.scores.rainfall_pts:4.1f}  (Diff = {cb.scores.rainfall_pts - ca.scores.rainfall_pts:+.1f})")
    print(f"    TOTAL COMPOSITE:     A={ca.scores.composite_score:4.1f}  B={cb.scores.composite_score:4.1f}  (Diff = {cb.scores.composite_score - ca.scores.composite_score:+.1f})")

# 10. DETERMINISM 5x TEST
print("\n================================================================================")
print("5-RUN DETERMINISM TEST")
print("================================================================================")
def test_5_runs(center_lat, center_lng, label):
    print(f"\nTesting 5 consecutive runs for {label} ({center_lat}, {center_lng}):")
    hashes = []
    top_cands = []
    for i in range(5):
        r = run_pipeline(center_lat, center_lng)
        h = r["dem_hash"]
        rec = r["recommended"]
        rec_str = f"({rec.lat:.6f}, {rec.lng:.6f}) Score={rec.scores.composite_score:.1f} Elev={rec.elevation_m}m"
        hashes.append(h)
        top_cands.append(rec_str)
        print(f"  Run {i+1}: Hash={h[:16]}... Rec={rec_str}")
    all_hashes_equal = len(set(hashes)) == 1
    all_recs_equal = len(set(top_cands)) == 1
    print(f"  -> DEM Hashes 100% Identical: {all_hashes_equal}")
    print(f"  -> Recommended Site 100% Identical: {all_recs_equal}")

test_5_runs(lat_A, lng_A, "RUN A Bounds")
test_5_runs(lat_B, lng_B, "RUN B Bounds")
