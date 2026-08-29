import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from backend.main import app
import json
import time

client = TestClient(app)
start = time.time()
with open("contours_1m.kml", "rb") as f:
    response = client.post(
        "/api/contour-analysis/analyzeContour",
        files={"file": ("contours_1m.kml", f, "application/vnd.google-earth.kml+xml")},
    )
duration = time.time() - start

print(f"Status Code: {response.status_code}")
print(f"Duration: {duration:.2f}s")
data = response.json()
print("Success:", data.get("success"))
print("Input:", json.dumps(data.get("input"), indent=2))
print("Terrain:", json.dumps(data.get("terrain"), indent=2))
print("Pond Site:", json.dumps(data.get("pond_site"), indent=2))
catchment_summary = {k: v for k, v in data.get("catchment", {}).items() if k != "boundary"}
print("Catchment:", json.dumps(catchment_summary, indent=2))
print(f"Boundary points: {len(data.get('catchment', {}).get('boundary', []))}")
