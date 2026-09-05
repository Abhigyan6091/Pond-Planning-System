"""
contour_analysis_routes.py
==========================
Phase 2 API endpoint for KML/KMZ contour map upload and terrain/catchment analysis.

Routes
------
POST /api/analyzeContour   — primary route (multipart/form-data, field: file)
POST /api/findCatchment    — alias route (same handler)

Processing pipeline
-------------------
1. File validation (extension, size, parseability)
2. KMZ extraction → KML bytes (if needed)
3. KML parsing  → List[ParsedContour]    (ContourParserService)
4. Contour validation                     (ContourParserService.validate)
5. Terrain reconstruction → elevation_matrix, bounds, pixel_size_m
                                          (ContourTerrainService)
6. Suitability analysis   → candidate sites
                                          (SuitabilityService) — REUSE Phase 1
7. Watershed delineation  → catchment    (HydrologyService)   — REUSE Phase 1
8. Structured JSON response

No rainfall is required; the suitability score uses terrain-only criteria.
"""
from __future__ import annotations

import os
import uuid
import math
import numpy as np
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.models.contour_analysis_models import (
    ContourAnalysisResponse,
    InputInfo,
    TerrainInfo,
    TerrainBounds,
    PondSiteInfo,
    CatchmentInfo,
)
from backend.models.dem_models import BoundingBox, LatLng
from backend.models.suitability_models import SuitabilityRequest
from backend.models.terrain_models import WatershedRequest
from backend.services.dem_service import DemService
from backend.services.contour_parser_service import ContourParserService
from backend.services.contour_terrain_service import ContourTerrainService
from backend.services.suitability_service import SuitabilityService
from backend.services.hydrology_service import HydrologyService

router = APIRouter(prefix="/contour-analysis", tags=["Phase 2 – Contour Analysis"])

# ------------------------------------------------------------------
# Limits
# ------------------------------------------------------------------
MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # 50 MB
ALLOWED_EXTENSIONS = {".kml", ".kmz"}


def _ext(filename: str) -> str:
    """Return lowercase file extension including the dot."""
    idx = filename.rfind(".")
    if idx == -1:
        return ""
    return filename[idx:].lower()


# ------------------------------------------------------------------
# Shared handler
# ------------------------------------------------------------------
async def _handle_contour_analysis(file: UploadFile) -> ContourAnalysisResponse:
    """
    Core handler shared by both route paths.

    Raises HTTPException on client errors; returns ContourAnalysisResponse on success.
    """
    filename = file.filename or "upload"
    ext = _ext(filename)

    # ── 1. Extension validation ────────────────────────────────────────────
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Accepted formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    # ── 2. Read file bytes ─────────────────────────────────────────────────
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw_bytes)//1024} KB). Maximum allowed: 50 MB.",
        )

    # ── 3. KMZ extraction → KML bytes ─────────────────────────────────────
    fmt = "KML"
    kml_bytes: bytes
    if ext == ".kmz":
        fmt = "KMZ"
        try:
            kml_bytes = ContourParserService.extract_kml_from_kmz(raw_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    else:
        kml_bytes = raw_bytes

    # ── 4. KML Parsing ────────────────────────────────────────────────────
    parse_result = ContourParserService.parse_kml_bytes(kml_bytes)
    validation_error = ContourParserService.validate(parse_result)
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error)

    contours = parse_result.contours

    # ── 5. Build InputInfo ────────────────────────────────────────────────
    input_info = InputInfo(
        filename=filename,
        format=fmt,
        contour_count=parse_result.contour_count,
        elevation_min_m=parse_result.elevation_min_m,
        elevation_max_m=parse_result.elevation_max_m,
        contour_interval_m=parse_result.contour_interval_m or 1.0,
    )

    # ── 6. Terrain Reconstruction ─────────────────────────────────────────
    try:
        elevation_matrix, bounds, pixel_size_m = ContourTerrainService.reconstruct_dem(
            contours, grid_size=100
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Terrain reconstruction failed: {exc}",
        )

    dem_np = np.array(elevation_matrix, dtype=float)
    rows, cols = dem_np.shape

    terrain_info = TerrainInfo(
        min_elevation_m=round(float(np.min(dem_np)), 2),
        max_elevation_m=round(float(np.max(dem_np)), 2),
        mean_elevation_m=round(float(np.mean(dem_np)), 2),
        grid_rows=rows,
        grid_cols=cols,
        pixel_size_m=round(pixel_size_m, 2),
        bounds=TerrainBounds(
            min_lat=bounds.south,
            max_lat=bounds.north,
            min_lon=bounds.west,
            max_lon=bounds.east,
        ),
    )

    # ── 7. Suitability Analysis — REUSE Phase 1 SuitabilityService ────────
    suit_request = SuitabilityRequest(
        elevation_matrix=elevation_matrix,
        bounds=bounds,
        pixel_size_m=pixel_size_m,
        num_candidates=5,       # top 5; we use rank-1 for pond site
        rainfall_mm=None,       # not required for Phase 2 terrain-only analysis
        runoff_coefficient=0.40,
    )
    try:
        suit_response = SuitabilityService.analyze(suit_request)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Suitability analysis failed: {exc}",
        )

    if not suit_response.candidates:
        raise HTTPException(
            status_code=422,
            detail="No suitable pond candidate sites could be identified in the uploaded terrain.",
        )

    top = suit_response.recommended or suit_response.candidates[0]

    pond_site = PondSiteInfo(
        latitude=top.lat,
        longitude=top.lng,
        elevation_m=top.elevation_m,
        slope_deg=top.slope_deg,
        flow_accumulation=top.flow_accumulation,
        depression_depth_m=top.depression_depth_m,
        suitability_score=top.scores.composite_score,
        suitability_tier=top.suitability_tier,
        reason=_build_reason(top),
    )

    # ── 8. Watershed/Catchment — REUSE Phase 1 HydrologyService ──────────
    outlet_point = LatLng(lat=top.lat, lng=top.lng)
    watershed_request = WatershedRequest(
        outlet_point=outlet_point,
        elevation_matrix=elevation_matrix,
        bounds=bounds,
        pixel_size_m=pixel_size_m,
    )
    try:
        watershed_response = HydrologyService.delineate_watershed(watershed_request)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Catchment delineation failed: {exc}",
        )

    catchment_info = CatchmentInfo(
        area_m2=watershed_response.catchment_area_m2,
        area_km2=watershed_response.catchment_area_km2,
        perimeter_km=watershed_response.perimeter_km,
        avg_slope_deg=watershed_response.avg_slope_deg,
        contributing_cells=int(
            watershed_response.catchment_area_m2 / max(1.0, pixel_size_m ** 2)
        ),
        boundary=watershed_response.catchment_polygon,
    )

    # ── 9. Generate Overlay Images for Leaflet Map ───────────────────────
    dem_id = f"kml_{uuid.uuid4().hex[:8]}"
    elev_overlay_filename = f"{dem_id}_elev.png"
    hillshade_filename = f"{dem_id}_hillshade.png"
    elev_overlay_path = os.path.join(settings.STORAGE_DIR, elev_overlay_filename)
    hillshade_path = os.path.join(settings.STORAGE_DIR, hillshade_filename)

    try:
        DemService._create_elevation_overlay(
            dem_np, terrain_info.min_elevation_m, terrain_info.max_elevation_m, elev_overlay_path
        )
        DemService._create_hillshade_overlay(dem_np, pixel_size_m, hillshade_path)
        elevation_overlay_url = f"/storage/{elev_overlay_filename}"
        hillshade_overlay_url = f"/storage/{hillshade_filename}"
    except Exception as img_exc:
        elevation_overlay_url = None
        hillshade_overlay_url = None

    return ContourAnalysisResponse(
        success=True,
        input=input_info,
        terrain=terrain_info,
        pond_site=pond_site,
        catchment=catchment_info,
        dem_id=dem_id,
        elevation_matrix=elevation_matrix,
        elevation_overlay_url=elevation_overlay_url,
        hillshade_overlay_url=hillshade_overlay_url,
        candidates=suit_response.candidates,
    )


def _build_reason(candidate) -> str:
    """Compose a human-readable justification string from candidate reasons."""
    if candidate.suitability_reasons:
        return "; ".join(candidate.suitability_reasons[:3])
    return (
        f"Terrain-derived selection: slope={candidate.slope_deg:.1f}°, "
        f"flow accumulation={candidate.flow_accumulation} cells, "
        f"depression depth={candidate.depression_depth_m:.2f}m"
    )


# ------------------------------------------------------------------
# Route definitions
# ------------------------------------------------------------------

@router.post(
    "/analyzeContour",
    response_model=ContourAnalysisResponse,
    summary="Analyze a KML/KMZ contour map and return catchment information",
    description="""
## Phase 2 — KML/KMZ Contour Analysis

Upload a contour map in **KML** or **KMZ** format. The system will:

1. Parse contour lines and extract elevation values
2. Reconstruct a terrain elevation grid (DEM) via Delaunay triangulation
3. Identify the most suitable pond location using terrain/hydrology criteria
4. Delineate the upstream catchment using D8 flow direction analysis
5. Return structured JSON with terrain stats, pond site, and catchment geometry

### Supported file formats
- `.kml` — KML 2.2 (OGC standard)
- `.kmz` — ZIP-compressed KML

### Elevation extraction
Elevation is extracted from Placemark `<name>`, `ExtendedData/SimpleData`,
or Z-components of coordinates (in that order of preference).

### Catchment methodology
Uses the existing D8 (deterministic 8-direction) flow direction algorithm
and reverse BFS watershed delineation — the same engine used in Phase 1.
""",
    responses={
        200: {
            "description": "Analysis completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "input": {
                            "filename": "contours_1m.kml",
                            "format": "KML",
                            "contour_count": 120,
                            "elevation_min_m": 274.0,
                            "elevation_max_m": 310.0,
                            "contour_interval_m": 1.0,
                        },
                        "terrain": {
                            "min_elevation_m": 274.0,
                            "max_elevation_m": 310.0,
                            "mean_elevation_m": 287.5,
                            "grid_rows": 100,
                            "grid_cols": 100,
                            "pixel_size_m": 15.3,
                            "bounds": {
                                "min_lat": 21.258,
                                "max_lat": 21.270,
                                "min_lon": 81.280,
                                "max_lon": 81.296,
                            },
                        },
                        "pond_site": {
                            "latitude": 21.263,
                            "longitude": 81.287,
                            "elevation_m": 276.5,
                            "slope_deg": 2.4,
                            "flow_accumulation": 340,
                            "depression_depth_m": 1.2,
                            "suitability_score": 62.3,
                            "suitability_tier": "Highly Suitable",
                            "reason": "✓ Favorable terrain slope; ✓ Natural terrain depression",
                        },
                        "catchment": {
                            "area_m2": 78450.0,
                            "area_km2": 0.078,
                            "perimeter_km": 1.12,
                            "avg_slope_deg": 4.1,
                            "contributing_cells": 334,
                            "boundary": [[81.283, 21.260], ["…"]],
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid file type or empty file"},
        413: {"description": "File too large (> 50 MB)"},
        422: {"description": "Malformed KML/KMZ or insufficient contour data"},
        500: {"description": "Internal processing error"},
    },
)
async def analyze_contour(
    contour_map: Optional[UploadFile] = File(
        None,
        description="KML or KMZ contour map file (Primary evaluation variable name)",
    ),
    file: Optional[UploadFile] = File(
        None,
        description="KML or KMZ contour map file (Compatibility alias)",
    ),
):
    """
    **POST /api/contour-analysis/analyzeContour**

    Accepts a KML or KMZ contour map under 'contour_map' or 'file', reconstructs terrain,
    and returns pond site + catchment information derived from the uploaded file.
    """
    upload = contour_map or file
    if upload is None:
        raise HTTPException(
            status_code=400,
            detail="Missing contour map file. Please upload under form-data key 'contour_map' (or 'file').",
        )
    return await _handle_contour_analysis(upload)


@router.post(
    "/findCatchment",
    response_model=ContourAnalysisResponse,
    summary="[Alias] Analyze KML/KMZ contour map — same as analyzeContour",
    description="Alias for `/analyzeContour`. Provided for API convention compatibility.",
    include_in_schema=True,
)
async def find_catchment(
    contour_map: Optional[UploadFile] = File(
        None,
        description="KML or KMZ contour map file (Primary evaluation variable name)",
    ),
    file: Optional[UploadFile] = File(
        None,
        description="KML or KMZ contour map file (Compatibility alias)",
    ),
):
    """
    **POST /api/contour-analysis/findCatchment**

    Alias for `/api/contour-analysis/analyzeContour`.
    """
    upload = contour_map or file
    if upload is None:
        raise HTTPException(
            status_code=400,
            detail="Missing contour map file. Please upload under form-data key 'contour_map' (or 'file').",
        )
    return await _handle_contour_analysis(upload)
