from fastapi import APIRouter, HTTPException
from backend.models.terrain_models import SlopeRequest, SlopeResponse, PointQueryRequest, PointQueryResponse
from backend.services.terrain_service import TerrainService

router = APIRouter(prefix="/terrain", tags=["Terrain"])

@router.post("/slope", response_model=SlopeResponse)
def compute_slope(request: SlopeRequest):
    """
    Computes slope raster matrix and generates slope heatmap overlay.
    """
    try:
        return TerrainService.process_slope_map(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Slope calculation failed: {str(e)}")

@router.post("/query-point", response_model=PointQueryResponse)
def query_point(request: PointQueryRequest):
    """
    Queries elevation, slope (deg), and aspect (deg + cardinal) for a specific lat/lng point.
    """
    try:
        return TerrainService.query_point_terrain(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Point query failed: {str(e)}")
