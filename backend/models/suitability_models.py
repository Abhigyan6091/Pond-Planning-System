"""
suitability_models.py
=====================
Pydantic models for land suitability scoring and candidate pond site detection.

Suitability is a weighted composite of terrain-derived criteria:
  - Slope suitability (low slope → good)
  - Depression/sink depth (deeper natural depression → good)
  - Catchment (flow accumulation → more upstream area → good)
  - Elevation within ROI (lower = generally better for collection)
  - Rainfall (provided externally from Open-Meteo)

Each criterion is normalized to [0, 1]. The composite score is [0, 100].
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class SuitabilityScoreComponents(BaseModel):
    slope_score: float          # 0–1: 1 = perfectly flat
    depression_score: float     # 0–1: 1 = deepest natural sink
    catchment_score: float      # 0–1: 1 = highest flow accumulation
    elevation_score: float      # 0–1: 1 = lowest point in ROI
    rainfall_score: float       # 0–1: 1 = >800mm/yr
    composite_score: float      # 0–100: weighted sum
    # Itemized score breakdown points (sums to total out of 100)
    slope_pts: float = 0.0      # Out of 20
    depression_pts: float = 0.0 # Out of 20
    catchment_pts: float = 0.0  # Out of 25
    elevation_pts: float = 0.0  # Out of 15
    rainfall_pts: float = 0.0   # Out of 20


class CandidateSite(BaseModel):
    rank: int
    site_id: str
    lat: float
    lng: float
    elevation_m: float
    # Terrain
    slope_deg: float
    depression_depth_m: float       # Natural sink depth (fill depth)
    flow_accumulation: int          # Upstream cell count
    catchment_area_m2: float        # Estimated from flow accumulation × pixel_area
    catchment_area_km2: float
    # Pond estimates
    estimated_depth_m: float
    estimated_surface_area_m2: float
    estimated_volume_m3: float
    # Rainfall/Runoff (computed if rainfall provided)
    rainfall_mm: Optional[float] = None
    runoff_coefficient: float = 0.40
    estimated_runoff_m3: Optional[float] = None
    # Scores
    scores: SuitabilityScoreComponents
    suitability_tier: str           # "Recommended" / "Highly Suitable" / "Moderately Suitable" / "Poor"
    suitability_reasons: List[str]  # e.g. ["Good catchment", "Natural depression", ...]


class SuitabilityRequest(BaseModel):
    elevation_matrix: List[List[float]]
    bounds: "BoundingBox"           # from dem_models
    pixel_size_m: float
    num_candidates: int = Field(default=10, ge=1, le=50)
    rainfall_mm: Optional[float] = None
    runoff_coefficient: float = Field(default=0.40, ge=0.05, le=0.95)
    # Weights (must sum to 1.0; if not, they are normalized internally)
    weight_slope: float = 0.30
    weight_depression: float = 0.30
    weight_catchment: float = 0.25
    weight_elevation: float = 0.05
    weight_rainfall: float = 0.10


class SuitabilityResponse(BaseModel):
    success: bool
    message: str
    num_candidates: int
    candidates: List[CandidateSite]
    recommended: Optional[CandidateSite] = None     # Top candidate
    # Score explanation
    score_explanation: dict = {
        "slope": "Inverse slope — flatter terrain scores higher. Steep slopes impede excavation.",
        "depression": "Natural terrain sink depth — deeper depressions score higher (natural storage).",
        "catchment": "Flow accumulation proxy — more upstream cells → more potential runoff contribution.",
        "elevation": "Relative lowness within ROI — lower areas are natural collection points.",
        "rainfall": "Annual rainfall — higher rainfall → more potential runoff to fill the pond.",
    }
    methodology_note: str = (
        "Candidate sites identified using terrain-derived suitability scoring on the DEM. "
        "Slope, depression depth, flow accumulation, elevation, and rainfall are combined "
        "as a weighted composite. Results are planning estimates requiring field verification."
    )


# Resolve forward reference
from backend.models.dem_models import BoundingBox
SuitabilityRequest.model_rebuild()
