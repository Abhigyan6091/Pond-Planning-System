from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.models.dem_models import BoundingBox, LatLng

class SlopeRequest(BaseModel):
    dem_id: str
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float

class SlopeResponse(BaseModel):
    success: bool
    slope_heatmap_url: str
    min_slope_deg: float
    max_slope_deg: float
    mean_slope_deg: float

class PointQueryRequest(BaseModel):
    lat: float
    lng: float
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float

class PointQueryResponse(BaseModel):
    elevation: float
    slope_deg: float
    aspect_deg: float
    aspect_cardinal: str

class FlowDropletRequest(BaseModel):
    start_point: LatLng
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float

class FlowDropletResponse(BaseModel):
    success: bool
    path: List[LatLng]
    path_elevations: List[float]
    total_distance_m: float
    elevation_drop_m: float

class WatershedRequest(BaseModel):
    outlet_point: LatLng
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float

class WatershedResponse(BaseModel):
    success: bool
    outlet: LatLng
    catchment_polygon: List[List[float]]  # List of [lng, lat]
    catchment_area_km2: float
    catchment_area_m2: float
    perimeter_km: float
    avg_slope_deg: float
