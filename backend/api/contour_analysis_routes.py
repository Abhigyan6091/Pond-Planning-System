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
import logging
import time
from backend.services.dem_service import DemService
from backend.services.contour_parser_service import ContourParserService
from backend.services.contour_terrain_service import ContourTerrainService
from backend.services.suitability_service import SuitabilityService
from backend.services.hydrology_service import HydrologyService
from backend.telemetry import get_tracer, metric_instruments

logger = logging.getLogger("village_pond.contour_analysis")
tracer = get_tracer("village-pond-contour-pipeline")

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
    Instrumented with OpenTelemetry distributed tracing child spans,
    metrics recording, and correlated logging.
    """
    analysis_start_time = time.time()
    filename = file.filename or "upload"
    ext = _ext(filename)
    logger.info(f"Initiating village pond terrain & catchment analysis for: '{filename}'")

    # ── 1. Extension validation ────────────────────────────────────────────
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Rejected unsupported file extension: '{ext}' for file '{filename}'")
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
        logger.error(f"Upload rejected: File '{filename}' is empty (0 bytes).")
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        logger.error(f"Upload rejected: File '{filename}' exceeds max size ({len(raw_bytes)//1024} KB).")
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw_bytes)//1024} KB). Maximum allowed: 50 MB.",
        )

    # ── 3 & 4. KMZ extraction & KML Parsing (OpenTelemetry Span) ─────────
    fmt = "KML"
    with tracer.start_as_current_span("parse_contour_kml_kmz") as parse_span:
        parse_span.set_attribute("file.name", filename)
        parse_span.set_attribute("file.extension", ext)
        parse_span.set_attribute("file.size_bytes", len(raw_bytes))

        if ext == ".kmz":
            fmt = "KMZ"
            try:
                kml_bytes = ContourParserService.extract_kml_from_kmz(raw_bytes)
            except ValueError as exc:
                parse_span.record_exception(exc)
                logger.error(f"KMZ archive extraction failed for '{filename}': {exc}")
                raise HTTPException(status_code=422, detail=str(exc))
        else:
            kml_bytes = raw_bytes

        parse_result = ContourParserService.parse_kml_bytes(kml_bytes)
        validation_error = ContourParserService.validate(parse_result)
        if validation_error:
            logger.error(f"Contour validation failed for '{filename}': {validation_error}")
            raise HTTPException(status_code=422, detail=validation_error)

        contours = parse_result.contours
        parse_span.set_attribute("file.format", fmt)
        parse_span.set_attribute("contour.count", parse_result.contour_count)
        parse_span.set_attribute("elevation.min_m", parse_result.elevation_min_m)
        parse_span.set_attribute("elevation.max_m", parse_result.elevation_max_m)
        parse_span.set_attribute("contour.interval_m", parse_result.contour_interval_m or 1.0)
        logger.info(
            f"Successfully parsed {parse_result.contour_count} contours from {filename} "
            f"[{parse_result.elevation_min_m}m to {parse_result.elevation_max_m}m]"
        )

    # Record metrics for contours parsed
    if "contours_parsed" in metric_instruments:
        metric_instruments["contours_parsed"].add(parse_result.contour_count, {"format": fmt})

    # ── 5. Build InputInfo ────────────────────────────────────────────────
    input_info = InputInfo(
        filename=filename,
        format=fmt,
        contour_count=parse_result.contour_count,
        elevation_min_m=parse_result.elevation_min_m,
        elevation_max_m=parse_result.elevation_max_m,
        contour_interval_m=parse_result.contour_interval_m or 1.0,
    )

    # ── 6. Terrain Reconstruction (OpenTelemetry Span) ────────────────────
    with tracer.start_as_current_span("reconstruct_terrain_dem") as dem_span:
        try:
            elevation_matrix, bounds, pixel_size_m = ContourTerrainService.reconstruct_dem(
                contours, grid_size=100
            )
        except ValueError as exc:
            dem_span.record_exception(exc)
            logger.error(f"Terrain reconstruction failed for '{filename}': {exc}")
            raise HTTPException(
                status_code=422,
                detail=f"Terrain reconstruction failed: {exc}",
            )

        dem_np = np.array(elevation_matrix, dtype=float)
        rows, cols = dem_np.shape
        dem_span.set_attribute("dem.grid_rows", rows)
        dem_span.set_attribute("dem.grid_cols", cols)
        dem_span.set_attribute("dem.total_cells", rows * cols)
        dem_span.set_attribute("dem.pixel_size_m", round(pixel_size_m, 2))
        dem_span.set_attribute("dem.elevation_min_m", round(float(np.min(dem_np)), 2))
        dem_span.set_attribute("dem.elevation_max_m", round(float(np.max(dem_np)), 2))
        logger.info(
            f"Reconstructed DEM grid: {rows}x{cols} ({rows*cols} cells) at resolution {pixel_size_m:.2f}m/px"
        )

    # Record DEM cells processed metric
    if "dem_cells_processed" in metric_instruments:
        metric_instruments["dem_cells_processed"].add(rows * cols, {"resolution": f"{pixel_size_m:.1f}m"})

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

    # ── 7. Suitability Analysis (OpenTelemetry Span) ──────────────────────
    suit_request = SuitabilityRequest(
        elevation_matrix=elevation_matrix,
        bounds=bounds,
        pixel_size_m=pixel_size_m,
        num_candidates=5,
        rainfall_mm=None,
        runoff_coefficient=0.40,
    )

    with tracer.start_as_current_span("evaluate_pond_suitability") as suit_span:
        try:
            suit_response = SuitabilityService.analyze(suit_request)
        except Exception as exc:
            suit_span.record_exception(exc)
            logger.error(f"Pond suitability analysis failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Suitability analysis failed: {exc}",
            )

        if not suit_response.candidates:
            logger.warning(f"No suitable pond candidate sites could be identified for '{filename}'")
            raise HTTPException(
                status_code=422,
                detail="No suitable pond candidate sites could be identified in the uploaded terrain.",
            )

        top = suit_response.recommended or suit_response.candidates[0]
        suit_span.set_attribute("suitability.num_candidates", len(suit_response.candidates))
        suit_span.set_attribute("suitability.top_score", top.scores.composite_score)
        suit_span.set_attribute("suitability.top_tier", top.suitability_tier)
        suit_span.set_attribute("suitability.top_lat", top.lat)
        suit_span.set_attribute("suitability.top_lng", top.lng)
        suit_span.set_attribute("suitability.top_elevation_m", top.elevation_m)
        logger.info(
            f"Evaluated {len(suit_response.candidates)} pond candidate sites. "
            f"Optimal Site: ({top.lat:.5f}, {top.lng:.5f}) Score={top.scores.composite_score:.2f} ({top.suitability_tier})"
        )

    # Record pond candidates metric
    if "candidates_found" in metric_instruments:
        metric_instruments["candidates_found"].add(len(suit_response.candidates), {"tier": top.suitability_tier})

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

    # ── 8. Watershed/Catchment Delineation (OpenTelemetry Span) ────────────
    outlet_point = LatLng(lat=top.lat, lng=top.lng)
    watershed_request = WatershedRequest(
        outlet_point=outlet_point,
        elevation_matrix=elevation_matrix,
        bounds=bounds,
        pixel_size_m=pixel_size_m,
    )

    with tracer.start_as_current_span("delineate_catchment_watershed") as ws_span:
        try:
            watershed_response = HydrologyService.delineate_watershed(watershed_request)
        except Exception as exc:
            ws_span.record_exception(exc)
            logger.error(f"Catchment delineation failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Catchment delineation failed: {exc}",
            )

        ws_span.set_attribute("catchment.area_m2", watershed_response.catchment_area_m2)
        ws_span.set_attribute("catchment.area_km2", watershed_response.catchment_area_km2)
        ws_span.set_attribute("catchment.perimeter_km", watershed_response.perimeter_km)
        ws_span.set_attribute("catchment.avg_slope_deg", watershed_response.avg_slope_deg)
        logger.info(
            f"Delineated catchment watershed: {watershed_response.catchment_area_m2:,.1f} m² "
            f"({watershed_response.catchment_area_km2:.3f} km²) contributing to pond site"
        )

    # Record catchment area metric
    if "catchment_area" in metric_instruments:
        metric_instruments["catchment_area"].record(watershed_response.catchment_area_m2, {"status": "success"})

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

    # ── 9. Generate Overlay Images for Leaflet Map (OpenTelemetry Span) ──
    dem_id = f"kml_{uuid.uuid4().hex[:8]}"
    elev_overlay_filename = f"{dem_id}_elev.png"
    hillshade_filename = f"{dem_id}_hillshade.png"
    elev_overlay_path = os.path.join(settings.STORAGE_DIR, elev_overlay_filename)
    hillshade_path = os.path.join(settings.STORAGE_DIR, hillshade_filename)

    with tracer.start_as_current_span("generate_dem_overlays") as img_span:
        img_span.set_attribute("overlay.dem_id", dem_id)
        try:
            DemService._create_elevation_overlay(
                dem_np, terrain_info.min_elevation_m, terrain_info.max_elevation_m, elev_overlay_path
            )
            DemService._create_hillshade_overlay(dem_np, pixel_size_m, hillshade_path)
            elevation_overlay_url = f"/storage/{elev_overlay_filename}"
            hillshade_overlay_url = f"/storage/{hillshade_filename}"
            img_span.set_attribute("overlay.success", True)
        except Exception as img_exc:
            img_span.record_exception(img_exc)
            logger.warning(f"Overlay generation non-fatal error: {img_exc}")
            elevation_overlay_url = None
            hillshade_overlay_url = None

    # Record total analysis latency metric
    total_analysis_sec = time.time() - analysis_start_time
    if "analysis_duration" in metric_instruments:
        metric_instruments["analysis_duration"].record(total_analysis_sec, {"format": fmt, "status": "success"})

    logger.info(
        f"Village pond planning analysis completed successfully for '{filename}' in {total_analysis_sec:.2f}s."
    )

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
