from fastapi import APIRouter, HTTPException
from backend.models.contour_models import ContourRequest, ContourResponse
from backend.services.contour_service import ContourService

router = APIRouter(prefix="/contours", tags=["Contours"])

@router.post("/generate-contours", response_model=ContourResponse)
def generate_contours(request: ContourRequest):
    """
    Extracts isoline contour polylines from DEM elevation matrix
    using Marching Squares algorithm.
    """
    try:
        if not request.elevation_matrix or len(request.elevation_matrix) == 0:
            raise HTTPException(status_code=400, detail="Elevation matrix is required.")
        return ContourService.generate_contours(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contour extraction failed: {str(e)}")
