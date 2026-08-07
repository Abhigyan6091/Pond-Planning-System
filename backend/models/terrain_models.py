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


class FlowVectorsRequest(BaseModel):
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float
    sample_stride: int = 4  # Show 1 arrow per N cells (reduces clutter)


class FlowVector(BaseModel):
    lat: float
    lng: float
    direction_idx: int   # 0..7 → E, SE, S, SW, W, NW, N, NE
    slope_deg: float


class FlowVectorsResponse(BaseModel):
    success: bool
    vectors: List[FlowVector]


class StreamNetworkRequest(BaseModel):
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float
    accumulation_threshold: int = 50  # Cells needed upstream to count as stream


class StreamSegment(BaseModel):
    coordinates: List[List[float]]  # [[lng, lat], ...]
    stream_order: int


class StreamNetworkResponse(BaseModel):
    success: bool
    segments: List[StreamSegment]
