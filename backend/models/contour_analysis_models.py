"""
contour_analysis_models.py
==========================
Pydantic v2 models for the Phase 2 KML/KMZ contour analysis endpoint.

These models define the structured JSON response returned by:
    POST /api/analyzeContour
    POST /api/findCatchment

They are deliberately separate from terrain_models.py so that the Phase 2
API surface can evolve without touching Phase 1 models.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Internal parsing models (used by ContourParserService)
# ---------------------------------------------------------------------------

class ParsedContour(BaseModel):
    """A single parsed contour line extracted from a KML/KMZ file."""
    elevation_m: float
    coordinates: List[Tuple[float, float]]   # list of (lon, lat)
    is_closed: bool = False                  # True if first coord == last coord


class ContourParseResult(BaseModel):
    """Result of parsing a KML/KMZ file into contour objects."""
    success: bool
    contours: List[ParsedContour] = []
    error_message: Optional[str] = None

    # Metadata derived during parsing
    contour_count: int = 0
    unique_elevations: List[float] = []
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    contour_interval_m: Optional[float] = None  # median gap between elevation levels
    bounds: Optional[dict] = None               # {"min_lat", "max_lat", "min_lon", "max_lon"}


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class InputInfo(BaseModel):
    """Describes the uploaded file and its contour content."""
    filename: str
    format: str = Field(description="KML or KMZ")
    contour_count: int
    elevation_min_m: float
    elevation_max_m: float
    contour_interval_m: float = Field(description="Approximate median contour interval in metres")


class TerrainBounds(BaseModel):
    """Geographic extent of the reconstructed terrain."""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class TerrainInfo(BaseModel):
    """Statistics of the DEM reconstructed from the uploaded contours."""
    min_elevation_m: float
    max_elevation_m: float
    mean_elevation_m: float
    grid_rows: int
    grid_cols: int
    pixel_size_m: float
    bounds: TerrainBounds


class PondSiteInfo(BaseModel):
    """The recommended pond location derived from terrain/hydrology analysis."""
    latitude: float
    longitude: float
    elevation_m: float
    slope_deg: float
    flow_accumulation: int
    depression_depth_m: float
    suitability_score: float = Field(description="0–100 composite suitability score")
    suitability_tier: str
    reason: str                                  # Human-readable justification


class CatchmentInfo(BaseModel):
    """Watershed/catchment delineated upstream of the recommended pond site."""
    area_m2: float
    area_km2: float
    perimeter_km: float
    avg_slope_deg: float
    contributing_cells: int
    boundary: List[List[float]] = Field(
        description="Catchment polygon as [[lon, lat], …]"
    )


from backend.models.suitability_models import CandidateSite


class ContourAnalysisResponse(BaseModel):
    """
    Top-level response from POST /api/analyzeContour.

    success=True means the full pipeline completed. On error, success=False
    and only the error_message field is meaningful.
    """
    success: bool
    error_message: Optional[str] = None

    input: Optional[InputInfo] = None
    terrain: Optional[TerrainInfo] = None
    pond_site: Optional[PondSiteInfo] = None
    catchment: Optional[CatchmentInfo] = None

    # Full DEM synchronization fields (for unified frontend analysis)
    dem_id: Optional[str] = None
    elevation_matrix: Optional[List[List[float]]] = None
    elevation_overlay_url: Optional[str] = None
    hillshade_overlay_url: Optional[str] = None
    candidates: Optional[List[CandidateSite]] = None
