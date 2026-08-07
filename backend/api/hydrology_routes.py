from fastapi import APIRouter, HTTPException
from backend.models.terrain_models import (
    FlowDropletRequest, FlowDropletResponse,
    WatershedRequest, WatershedResponse,
    FlowVectorsRequest, FlowVectorsResponse,
    StreamNetworkRequest, StreamNetworkResponse,
)
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

@router.post("/flow-vectors", response_model=FlowVectorsResponse)
def flow_vectors(request: FlowVectorsRequest):
    """
    Returns sampled D8 flow direction vectors for map arrow visualization.
    """
    try:
        return HydrologyService.get_flow_vectors(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow vector computation failed: {str(e)}")

@router.post("/stream-network", response_model=StreamNetworkResponse)
def stream_network(request: StreamNetworkRequest):
    """
    Returns stream network polylines derived from D8 flow accumulation.
    """
    try:
        return HydrologyService.get_stream_network(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream network computation failed: {str(e)}")
