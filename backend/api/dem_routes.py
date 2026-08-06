from fastapi import APIRouter, HTTPException
from backend.models.dem_models import DemRequest, DemResponse
from backend.services.dem_service import DemService

router = APIRouter(prefix="/dem", tags=["DEM"])

@router.post("/download-dem", response_model=DemResponse)
def download_dem(request: DemRequest):
    """
    Downloads or generates DEM for specified region of interest (ROI)
    using OpenZenith, OpenTopography, or high-precision terrain models.
    """
    try:
        return DemService.process_dem_request(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DEM processing failed: {str(e)}")
