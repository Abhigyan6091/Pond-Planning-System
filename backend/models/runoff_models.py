"""
runoff_models.py
================
Pydantic models for runoff volume estimation.

Model: V = P × A × C
  P = precipitation depth (m)
  A = catchment area (m²)
  C = runoff coefficient (dimensionless, 0–1)

Runoff coefficients are approximate land-use defaults.
They do NOT represent site-specific soil science.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


RUNOFF_COEFFICIENT_PRESETS = {
    "low":    {"c": 0.15, "label": "Low (Dense Forest / Permeable Soil)"},
    "medium": {"c": 0.40, "label": "Medium (Mixed / Agricultural Land)"},
    "high":   {"c": 0.70, "label": "High (Degraded / Semi-Impervious)"},
    "urban":  {"c": 0.85, "label": "Very High (Urban / Impervious Surface)"},
}


class RunoffRequest(BaseModel):
    rainfall_mm: float = Field(..., description="Annual (or event) rainfall depth in mm")
    catchment_area_m2: float = Field(..., description="Catchment area in m² from watershed delineation")
    runoff_coefficient: float = Field(
        default=0.40,
        ge=0.05, le=0.95,
        description="Rational Method runoff coefficient C (0.05–0.95)"
    )
    coefficient_preset: Optional[Literal["low", "medium", "high", "urban"]] = None


class RunoffResponse(BaseModel):
    success: bool
    rainfall_mm: float
    catchment_area_m2: float
    catchment_area_km2: float
    runoff_coefficient: float
    coefficient_label: str
    runoff_volume_m3: float         # V = P × A × C (in m³)
    runoff_volume_million_m3: float # same, in million m³
    pond_fill_count: float          # How many times this runoff could fill the recommended pond (filled externally)
    methodology: str = (
        "Rational Method: V = P × A × C  where  "
        "P = rainfall depth (m),  A = catchment area (m²),  "
        "C = runoff coefficient (dimensionless).  "
        "This is a planning-level estimate only."
    )
    assumption_note: str = (
        "Runoff coefficient is an approximate default for the selected land-use class. "
        "Actual runoff depends on soil type, antecedent moisture, slope, and vegetation. "
        "Professional hydrological assessment is required for engineering design."
    )
