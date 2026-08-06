from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.models.dem_models import BoundingBox

class ContourRequest(BaseModel):
    dem_id: Optional[str] = None
    elevation_matrix: Optional[List[List[float]]] = None
    bounds: BoundingBox
    interval: float = Field(default=20.0, description="Contour line interval in meters (10, 20, 50, 100)")

class ContourPolyline(BaseModel):
    id: str
    elevation: float
    coordinates: List[List[float]]  # List of [lng, lat]
    length_m: float
    length_km: float
    vertex_count: int
    is_closed: bool
    area_m2: Optional[float] = None
    area_km2: Optional[float] = None

class ContourResponse(BaseModel):
    success: bool
    dem_id: str
    interval: float
    total_contours: int
    contours: List[ContourPolyline]
