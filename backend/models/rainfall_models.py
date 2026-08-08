"""
rainfall_models.py
==================
Pydantic models for the rainfall API (Open-Meteo integration).
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class RainfallRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the village/location")
    lng: float = Field(..., description="Longitude of the village/location")
    start_year: int = Field(default=2014, description="First year of historical record (YYYY)")
    end_year: int = Field(default=2023, description="Last year of historical record (YYYY)")


class MonthlyRainfall(BaseModel):
    month: int              # 1..12
    month_name: str         # "January" etc.
    avg_mm: float           # Average monthly rainfall in mm
    total_mm: float         # Total over the period


class RainfallTimeSeries(BaseModel):
    year: int
    annual_total_mm: float


class RainfallResponse(BaseModel):
    success: bool
    message: str
    lat: float
    lng: float
    start_year: int
    end_year: int
    # Aggregated statistics
    annual_avg_mm: float            # Mean annual rainfall over the period
    annual_max_mm: float            # Maximum annual rainfall in one year
    annual_min_mm: float            # Minimum annual rainfall in one year
    monsoon_avg_mm: float           # Mean Jun–Sep rainfall (South Asian monsoon)
    monsoon_fraction: float         # monsoon_avg / annual_avg (0–1)
    monthly_avg: List[MonthlyRainfall]   # 12 items
    yearly_totals: List[RainfallTimeSeries]
    max_rainfall_year: int          # Year with maximum rainfall
    data_source: str = "Open-Meteo (open-meteo.com)"
    rainfall_class: str             # "Arid" / "Semi-Arid" / "Sub-Humid" / "Humid" / "Very Humid"
