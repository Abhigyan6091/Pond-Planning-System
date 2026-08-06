"""
Root Cause Analysis: Tile fetch and Terrarium decode diagnostic.
Run from project root: python backend/debug_tile_test.py
"""
import math, requests, numpy as np
from PIL import Image
from io import BytesIO

def lat_lon_to_tile(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_to_bbox(x, y, z):
    n = 2.0 ** z
    lon_w = x / n * 360.0 - 180.0
    lon_e = (x + 1) / n * 360.0 - 180.0
    lat_rad_n = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_rad_s = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_n = math.degrees(lat_rad_n)
    lat_s = math.degrees(lat_rad_s)
    return lat_s, lon_w, lat_n, lon_e

zoom = 10
test_locations = [
    ("Everest",    28.0,  86.9),
    ("GrandCanyon", 36.1, -112.1),
]

print("=" * 60)
print("OPENZENITH TILE ENDPOINT TEST")
print("=" * 60)

for name, lat, lon in test_locations:
    tx, ty = lat_lon_to_tile(lat, lon, zoom)
    url = f"https://openzenith.cyopsys.com/tiles/terrarium/{zoom}/{tx}/{ty}.png"
    print(f"\n[{name}] z={zoom} tile=({tx},{ty})")
    print(f"  URL: {url}")
    try:
        resp = requests.get(url, timeout=8)
        ct = resp.headers.get("Content-Type", "unknown")
        print(f"  HTTP: {resp.status_code}  Content-Type: {ct}  Size: {len(resp.content)} bytes")

        if resp.status_code == 200 and "image" in ct:
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            arr = np.array(img)
            print(f"  Image shape: {arr.shape}  dtype: {arr.dtype}")
            print(f"  R: {arr[:,:,0].min()}..{arr[:,:,0].max()}  "
                  f"G: {arr[:,:,1].min()}..{arr[:,:,1].max()}  "
                  f"B: {arr[:,:,2].min()}..{arr[:,:,2].max()}")
            # Terrarium: elevation = R*256 + G + B/256 - 32768
            elev = (arr[:,:,0].astype(np.float64) * 256.0 +
                    arr[:,:,1].astype(np.float64) +
                    arr[:,:,2].astype(np.float64) / 256.0 - 32768.0)
            print(f"  Decoded elevation: min={elev.min():.1f}  max={elev.max():.1f}  mean={elev.mean():.1f} m")
            print(f"  Unique elevation count: {len(np.unique(elev.round(1)))}")
        else:
            print(f"  Response preview: {resp.text[:300]}")
    except Exception as e:
        print(f"  ERROR: {e}")

print()
print("=" * 60)
print("SYNTHETIC DEM PATTERN ANALYSIS (Root Cause)")
print("=" * 60)

def gen_synth(south, west, north, east, res=100):
    lats = np.linspace(north, south, res)
    lons = np.linspace(west, east, res)
    LonGrid, LatGrid = np.meshgrid(lons, lats)
    X = (LonGrid - west) / (east - west + 1e-5) * 4 * np.pi
    Y = (north - LatGrid) / (north - south + 1e-5) * 4 * np.pi
    return X, Y

X_ev, Y_ev = gen_synth(27.97, 86.90, 28.01, 86.96)
X_gc, Y_gc = gen_synth(36.08, -112.15, 36.14, -112.08)

print(f"\nEverest  X: {X_ev.min():.4f}..{X_ev.max():.4f}  Y: {Y_ev.min():.4f}..{Y_ev.max():.4f}")
print(f"GCanyon  X: {X_gc.min():.4f}..{X_gc.max():.4f}  Y: {Y_gc.min():.4f}..{Y_gc.max():.4f}")
print()
print("=> DIAGNOSIS: X,Y are always normalized to [0, 4*pi] = [0, 12.566]")
print("   regardless of geographic location.")
print()
print("   freq1 = sin(X*1.5) * cos(Y*1.5)")
cycles_1 = 1.5 * X_ev.max() / (2*math.pi)
print(f"   => {cycles_1:.2f} complete sin cycles in X direction (ALWAYS 3.0)")
print(f"   => 3x3 regular diamond grid -> CHECKERBOARD")
print()
print("   freq3 = cos(6.0*X) * sin(6.0*Y)")
cycles_3 = 6.0 * X_ev.max() / (2*math.pi)
print(f"   => {cycles_3:.2f} complete cycles -> 12x12 fine checkerboard")
print()
print("   freq4 = sin(12.0*X) * cos(12.0*Y)")
cycles_4 = 12.0 * X_ev.max() / (2*math.pi)
print(f"   => {cycles_4:.2f} complete cycles -> 24x24 fine checkerboard")
print()
print("ROOT CAUSE CONFIRMED:")
print("  The normalized [0,4pi] coordinate grid combined with integer-multiple")
print("  sinusoidal frequencies creates an exact repeating diamond/checkerboard")
print("  pattern at EVERY location on Earth.")
print()
print("CORRECT FIX:")
print("  Use OpenZenith Terrarium tiles (real elevation data) rather than")
print("  a synthetic formula. Pipeline:")
print("  1. bbox -> covering XYZ tile list at zoom 10")
print("  2. fetch each tile PNG from openzenith.cyopsys.com/tiles/terrarium/z/x/y.png")
print("  3. decode: elev = R*256 + G + B/256 - 32768")
print("  4. stitch tiles into one large array")
print("  5. crop to exact bbox pixels")
print("  6. return as float64 elevation matrix")
