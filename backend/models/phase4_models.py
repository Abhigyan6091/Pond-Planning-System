from pydantic import BaseModel, Field
from typing import List, Optional
from backend.models.dem_models import BoundingBox, LatLng


class PondRequest(BaseModel):
    click_point: LatLng
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float


class PondInfo(BaseModel):
    pond_id: str
    center: LatLng
    bottom_elevation: float
    water_level: float
    max_depth: float
    surface_area_m2: float
    surface_area_km2: float
    volume_m3: float
    volume_km3: float
    catchment_cells: int


class PondResponse(BaseModel):
    success: bool
    pond: Optional[PondInfo] = None
    message: str


class ElevationProfileRequest(BaseModel):
    start_point: LatLng
    end_point: LatLng
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    pixel_size_m: float
    num_samples: int = Field(default=100, ge=10, le=500)


class ElevationProfilePoint(BaseModel):
    distance_m: float
    elevation: float
    lat: float
    lng: float


class ElevationProfileResponse(BaseModel):
    success: bool
    profile: List[ElevationProfilePoint]
    total_distance_m: float
    min_elevation: float
    max_elevation: float
    elevation_gain_m: float
    elevation_loss_m: float


class Terrain3DRequest(BaseModel):
    elevation_matrix: List[List[float]]
    bounds: BoundingBox
    dem_id: str
    downsample: int = Field(default=2, ge=1, le=8)
