from fastapi import APIRouter, HTTPException
from backend.models.terrain_models import FlowDropletRequest, FlowDropletResponse, WatershedRequest, WatershedResponse
from backend.services.hydrology_service import HydrologyService

router = APIRouter(prefix="/hydrology", tags=["Hydrology"])

@router.post("/flow-droplet", response_model=FlowDropletResponse)
def flow_droplet(request: FlowDropletRequest):
    """
    Simulates water droplet downhill flow path along D8 steepest descent vectors.
    """
    try:
        return HydrologyService.trace_droplet_path(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Droplet trace failed: {str(e)}")

@router.post("/watershed", response_model=WatershedResponse)
def watershed(request: WatershedRequest):
    """
    Delineates contributing watershed catchment region for specified outlet lat/lng point.
    """
    try:
        return HydrologyService.delineate_watershed(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Watershed delineation failed: {str(e)}")
