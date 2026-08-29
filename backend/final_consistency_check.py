import json
import math
import hashlib
import numpy as np
from pathlib import Path

from backend.models.dem_models import DemRequest, LatLng
from backend.services.dem_service import DemService
from backend.services.suitability_service import SuitabilityService
from backend.models.suitability_models import SuitabilityRequest
from backend.utils.geo_utils import latlng_to_bbox, haversine_distance

STORAGE_PATH = Path("backend/tests")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)

def execute_run(center_lat: float, center_lng: float, radius_km: float = 2.0, rainfall_mm: float = 800.0):
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
        "dem": dem_res.model_dump(),
        "dem_hash": dem_hash,
        "suitability": suit_res.model_dump(),
        "candidates": [c.model_dump() for c in suit_res.candidates],
        "recommended": suit_res.recommended.model_dump() if suit_res.recommended else None
    }

# 1. Execute Run A
run_A = execute_run(21.258800, 81.295400, 2.0, 800.0)
with open(STORAGE_PATH / "response_run_A.json", "w") as f:
    json.dump(run_A, f, indent=2)

# 2. Execute Run B
run_B = execute_run(21.264806, 81.287728, 2.0, 800.0)
with open(STORAGE_PATH / "response_run_B.json", "w") as f:
    json.dump(run_B, f, indent=2)

print("=== SAVED FULL JSON RESPONSES ===")
print(f"Run A JSON saved to: {STORAGE_PATH / 'response_run_A.json'}")
print(f"Run B JSON saved to: {STORAGE_PATH / 'response_run_B.json'}")

print("\n=== RUN A EXACT CANDIDATES ===")
for c in run_A["candidates"]:
    sc = c["scores"]
    print(f"Rank {c['rank']:2d}: ({c['lat']:.6f}, {c['lng']:.6f}) Elev={c['elevation_m']}m Slope={c['slope_deg']}° Dep={c['depression_depth_m']}m Acc={c['flow_accumulation']} Catch={c['catchment_area_km2']:.4f}km² Score={sc['composite_score']} [Slp={sc['slope_pts']} Dep={sc['depression_pts']} Cat={sc['catchment_pts']} Elv={sc['elevation_pts']} Rn={sc['rainfall_pts']}]")

print("\n=== RUN B EXACT CANDIDATES ===")
for c in run_B["candidates"]:
    sc = c["scores"]
    print(f"Rank {c['rank']:2d}: ({c['lat']:.6f}, {c['lng']:.6f}) Elev={c['elevation_m']}m Slope={c['slope_deg']}° Dep={c['depression_depth_m']}m Acc={c['flow_accumulation']} Catch={c['catchment_area_km2']:.4f}km² Score={sc['composite_score']} [Slp={sc['slope_pts']} Dep={sc['depression_pts']} Cat={sc['catchment_pts']} Elv={sc['elevation_pts']} Rn={sc['rainfall_pts']}]")

# Let's also check where the screenshot with (21.2452, 81.2840), score 86.4 came from:
# Notice that in Run A, Candidate #2 is at (21.245358, 81.284045), Elev=274.0m, Slope=0.8, Dep=1.55m, Catch=0.1333km2, Score=82.5!
# What if rainfall was slightly different or if the analysis was centered at a slightly different location?
# What if the user had clicked (21.2452, 81.2840)? Let's test running with center = (21.2452, 81.2840)!
run_C = execute_run(21.245200, 81.284000, 2.0, 800.0)
print("\n=== RUN WITH CENTER = (21.2452, 81.2840) ===")
for c in run_C["candidates"][:3]:
    print(f"Rank {c['rank']:2d}: ({c['lat']:.6f}, {c['lng']:.6f}) Elev={c['elevation_m']}m Slope={c['slope_deg']}° Dep={c['depression_depth_m']}m Catch={c['catchment_area_km2']:.3f}km² Score={c['scores']['composite_score']}")

# 5-run determinism verification
print("\n=== 5-RUN REPEATABILITY CHECK ===")
for label, (lat, lng) in [("Run A", (21.258800, 81.295400)), ("Run B", (21.264806, 81.287728))]:
    hashes = []
    recs = []
    cand_tuples = []
    for r_i in range(5):
        res = execute_run(lat, lng, 2.0, 800.0)
        hashes.append(res["dem_hash"])
        rec = res["recommended"]
        recs.append((rec["lat"], rec["lng"], rec["scores"]["composite_score"]))
        cand_tuples.append([(c["lat"], c["lng"], c["scores"]["composite_score"]) for c in res["candidates"]])
    
    hash_det = len(set(hashes)) == 1
    rec_det = len(set(recs)) == 1
    all_cands_det = all(c == cand_tuples[0] for c in cand_tuples)
    print(f"{label} ({lat}, {lng}):")
    print(f"  DEM Hash 100% Identical: {hash_det} ({hashes[0][:16]}...)")
    print(f"  Recommended Site 100% Identical: {rec_det} -> {recs[0]}")
    print(f"  All 10 Candidates 100% Identical: {all_cands_det}")
