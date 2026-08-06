from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class LatLng(BaseModel):
    lat: float
    lng: float

class BoundingBox(BaseModel):
    south: float
    west: float
    north: float
    east: float

class PolygonROI(BaseModel):
    coordinates: List[List[float]]  # List of [lng, lat] vertices

class DemRequest(BaseModel):
    center: Optional[LatLng] = None
    radius_km: Optional[float] = Field(default=2.0, description="Bounding box radius in km (e.g. 1, 2, 5, 10)")
    bbox: Optional[BoundingBox] = None
    polygon: Optional[PolygonROI] = None
    provider: Literal["openzenith", "opentopography", "opentopodata", "auto"] = "openzenith"
    dem_type: str = Field(default="COP30", description="Dem dataset: COP30, SRTMGL1, AW3D30, NASADEM")
    resolution: int = Field(default=100, description="Grid dimension resolution (NxN matrix)")

class DemMetadata(BaseModel):
    dem_id: str
    bounds: BoundingBox
    width: int
    height: int
    min_elevation: float
    max_elevation: float
    mean_elevation: float
    std_elevation: float
    median_elevation: float
    pixel_size_m: float
    crs: str = "EPSG:4326"
    data_source: str = "unknown"          # e.g. "OpenZenith GLO-30", "SRTM-30m"
    zoom_level: Optional[int] = None      # tile zoom level used (if tile-based)
    num_api_points: Optional[int] = None  # how many elevation points fetched

class DemResponse(BaseModel):
    success: bool
    message: str
    metadata: DemMetadata
    elevation_matrix: List[List[float]]
    elevation_overlay_url: str
    hillshade_overlay_url: str
    histogram: Dict[str, Any]
