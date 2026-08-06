"""
Full end-to-end verification test for the corrected DEM pipeline.
Run from project root: python backend/verify_dem.py
"""
import requests, time, numpy as np

time.sleep(2)

print("=" * 55)
print("FULL END-TO-END TERRAIN VERIFICATION")
print("=" * 55)
print()

locations = [
    ("Everest",      {"lat": 27.9881, "lng": 86.9250}),
    ("Grand Canyon", {"lat": 36.1069, "lng": -112.1129}),
    ("Mont Blanc",   {"lat": 45.8326, "lng": 6.8652}),
]

matrices = []

for name, coords in locations:
    res = requests.post("http://localhost:8000/api/dem/download-dem", json={
        "center": coords, "radius_km": 2.0, "provider": "openzenith", "resolution": 20
    }).json()

    meta = res["metadata"]
    mat  = np.array(res["elevation_matrix"])
    matrices.append(mat)

    source = meta.get("data_source", "unknown")
    w      = meta["width"]
    h      = meta["height"]
    mn     = meta["min_elevation"]
    mx     = meta["max_elevation"]
    mean_e = meta["mean_elevation"]
    std_e  = meta["std_elevation"]

    print(f"[{name}]")
    print(f"  Source  : {source}")
    print(f"  Grid    : {w}x{h}")
    print(f"  Range   : {mn}m .. {mx}m")
    print(f"  Mean    : {mean_e}m   Std: {std_e}m")
    print()

print("=" * 55)
print("PATTERN UNIQUENESS CHECK")
print("=" * 55)

def normed(m):
    return (m - m.mean()) / (m.std() + 1e-6)

m0, m1, m2 = [normed(mx) for mx in matrices]
c01 = float(np.corrcoef(m0.flatten(), m1.flatten())[0, 1])
c02 = float(np.corrcoef(m0.flatten(), m2.flatten())[0, 1])
c12 = float(np.corrcoef(m1.flatten(), m2.flatten())[0, 1])

print(f"Pattern corr Everest<->GrandCanyon  : {c01:.4f}  (near 0 = unique terrain)")
print(f"Pattern corr Everest<->MontBlanc    : {c02:.4f}  (near 0 = unique terrain)")
print(f"Pattern corr GrandCanyon<->MontBlanc: {c12:.4f}  (near 0 = unique terrain)")
print()
print("Checkerboard bug: correlations would be close to ±1.0 for ALL pairs.")
