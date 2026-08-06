from fastapi import APIRouter, HTTPException
from backend.models.phase4_models import (
    PondRequest, PondResponse,
    ElevationProfileRequest, ElevationProfileResponse,
    Terrain3DRequest
)
from backend.services.pond_service import PondService
from backend.services.profile_service import ProfileService
import numpy as np

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("/pond", response_model=PondResponse)
def detect_pond(request: PondRequest):
    """
    Detects local depression (pond/sink) at clicked point using Priority-Flood algorithm.
    Returns bottom elevation, water level, max depth, surface area, and stored volume.
    """
    try:
        return PondService.detect_pond(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pond detection failed: {str(e)}")


@router.post("/elevation-profile", response_model=ElevationProfileResponse)
def elevation_profile(request: ElevationProfileRequest):
    """
    Samples DEM along a transect line (start → end) using bilinear interpolation.
    Returns distance-elevation profile for Plotly chart rendering.
    """
    try:
        return ProfileService.compute_profile(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile computation failed: {str(e)}")


@router.post("/terrain-3d")
def terrain_3d(request: Terrain3DRequest):
    """
    Returns downsampled elevation matrix with lat/lon meshgrid for Plotly 3D surface.
    """
    try:
        dem = np.array(request.elevation_matrix, dtype=float)
        ds = max(1, request.downsample)
        dem_ds = dem[::ds, ::ds]
        rows, cols = dem_ds.shape
        bounds = request.bounds

        lats = np.linspace(bounds.north, bounds.south, rows).tolist()
        lons = np.linspace(bounds.west, bounds.east, cols).tolist()

        return {
            "success": True,
            "dem_id": request.dem_id,
            "z": dem_ds.tolist(),
            "x": lons,
            "y": lats,
            "min_z": float(np.nanmin(dem_ds)),
            "max_z": float(np.nanmax(dem_ds)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D terrain prep failed: {str(e)}")
