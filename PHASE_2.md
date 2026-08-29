# Phase 2 — KML/KMZ Contour Upload & Analysis

## 1. Objective

Phase 2 enhances the Village Pond Planning System by adding a **second terrain input workflow**:
1. **Select Terrain from Map** (Phase 1 — map click / polygon ROI / DEM API)
2. **Upload Contour Map (KML/KMZ)** (Phase 2 — vector contour isoline upload)

Both workflows seamlessly converge onto the same underlying terrain and hydrology engine.

---

## 2. Architecture & Design Principles

```
                         VILLAGE POND PLANNING SYSTEM
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
             SELECT FROM MAP                     UPLOAD KML/KMZ
             (DEM API / Tile)                   (Vector Isolines)
                      │                                 │
                      ▼                                 ▼
                 Raster DEM                     KML/KMZ Parser
                      │                                 │
                      │                                 ▼
                      │                         Extract Contours
                      │                      (Elevation + Geometry)
                      │                                 │
                      │                                 ▼
                      │                        Terrain Reconstruction
                      │                       (Delaunay TIN / Interp)
                      │                                 │
                      └────────────────┬────────────────┘
                                       ▼
                             COMMON TERRAIN MODEL
                       (elevation_matrix, bounds, pxm)
                                       │
                                       ▼
                             TERRAIN ANALYSIS ENGINE
                             (Slope, Aspect, Sinks)
                                       │
                                       ▼
                            HYDROLOGY SERVICE (D8)
                         (Flow Direction & Accumulation)
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
               SUITABILITY SCORING             WATERSHED DELINEATION
             (Candidate Site Ranking)         (Upstream Catchment Polygon)
                      │                                 │
                      └────────────────┬────────────────┘
                                       ▼
                            STRUCTURED JSON RESPONSE
```

### Core Design Rules
- **No Duplicate Hydrology Code**: Phase 2 uses the exact same `HydrologyService.compute_d8_flow_direction()`, `compute_flow_accumulation()`, and `delineate_watershed()`, as well as `SuitabilityService.analyze()`.
- **Input Adapter Pattern**: `ContourParserService` and `ContourTerrainService` act strictly as input converters that transform vector contours into the standardized `(elevation_matrix, BoundingBox, pixel_size_m)` tuple.
- **Zero Hardcoding**: All bounds, elevations, intervals, pond coordinates, and catchment areas are calculated dynamically from the uploaded file.

---

## 3. KML/KMZ Parsing Methodology

Implemented in `backend/services/contour_parser_service.py`:
- Handles XML namespaces cleanly via Clark notation.
- Extracts `Placemark` elements containing `LineString` or `Polygon` coordinates.
- **Dynamic Elevation Extraction Hierarchy**:
  1. `<name>` text parsed as floating-point elevation (e.g. `277.0` in `contours_1m.kml`).
  2. `ExtendedData / SchemaData / SimpleData` attributes matching elevation keywords (`elevation`, `elev`, `alt`, `altitude`, `z`, `height`).
  3. Coordinate Z-component in `lon,lat,alt` triplets.
- **KMZ Handling**: Automatically inspects zip contents and decompresses `doc.kml` or the first `.kml` file.
- **Validation**: Ensures minimum 3 contours, at least 2 unique elevation levels, non-degenerate spatial extent, and finite coordinates.

---

## 4. Contour-to-DEM Reconstruction Methodology

Implemented in `backend/services/contour_terrain_service.py`:
1. **Control Point Sampling**: Proportional sampling along contour vertices to preserve density balance.
2. **Delaunay Triangulation & Linear Interpolation**:
   - Uses `scipy.interpolate.LinearNDInterpolator` (Barycentric triangulation).
   - Preserves contour elevation values with zero distortion along isolines.
   - Avoids "bull's-eye" artifacts commonly produced by raw IDW.
3. **Edge Extrapolation**: Nearest-neighbour interpolation fallback for cells outside the convex hull of the contours.
4. **Light Surface Blending**: 3x3 uniform filter pass to eliminate micro-faceting seams.
5. **Physical Metric Units**: Grid dimensions derived in EPSG:4326; `pixel_size_m` calculated via Haversine formula at centroid latitude.

---

## 5. Catchment Estimation & Pond Site Identification

1. **Suitability Ranking**: Reconstructs candidate pond sites using terrain criteria (slope, depression depth, upstream flow accumulation, relative elevation).
2. **Optimal Site Selection**: Highest-scoring candidate cell is designated as the recommended pond outlet.
3. **D8 Catchment Delineation**: Reverse breadth-first traversal from outlet cell along D8 flow direction pointers.
4. **Boundary Polygon Generation**: Unary union of catchment cell polygons with convex hull fallback, yielding exact geographic polygon coordinates `[[lng, lat], ...]`.

---

## 6. API Specification

### Endpoint: `POST /api/contour-analysis/analyzeContour` (and alias `/api/contour-analysis/findCatchment`)
- **Content-Type**: `multipart/form-data`
- **Parameter**: `file` (KML or KMZ binary)

### Example Request
```bash
curl -X POST "http://localhost:8000/api/contour-analysis/analyzeContour" \
  -F "file=@contours_1m.kml"
```

### Example JSON Response
```json
{
  "success": true,
  "error_message": null,
  "input": {
    "filename": "contours_1m.kml",
    "format": "KML",
    "contour_count": 1355,
    "elevation_min_m": 267.0,
    "elevation_max_m": 298.0,
    "contour_interval_m": 1.0
  },
  "terrain": {
    "min_elevation_m": 268.91,
    "max_elevation_m": 295.6,
    "mean_elevation_m": 283.87,
    "grid_rows": 100,
    "grid_cols": 100,
    "pixel_size_m": 33.67,
    "bounds": {
      "min_lat": 21.2393473,
      "max_lat": 21.2640558,
      "min_lon": 81.2807796,
      "max_lon": 81.3132717
    }
  },
  "pond_site": {
    "latitude": 21.251826,
    "longitude": 81.296533,
    "elevation_m": 273.1,
    "slope_deg": 0.9,
    "flow_accumulation": 116,
    "depression_depth_m": 8.9,
    "suitability_score": 69.7,
    "suitability_tier": "Highly Suitable",
    "reason": "✓ Favorable terrain slope; ✓ Natural terrain depression; ✓ Good upstream catchment"
  },
  "catchment": {
    "area_m2": 131505.6,
    "area_km2": 0.132,
    "perimeter_km": 1.85,
    "avg_slope_deg": 2.7,
    "contributing_cells": 116,
    "boundary": [
      [81.2941, 21.2502],
      "..."
    ]
  }
}
```

---

## 7. Frontend Integration

- **Dual-Mode Selector**: Toggle between `[Select from Map]` and `[Upload Contours]`.
- **Upload & Analysis Panel**: Drag-and-drop / file picker for KML/KMZ with validation and progress indicator.
- **Map Visualization**: Renders KML-derived pond site icon and cyan catchment boundary overlay directly onto the interactive map.
