from fastapi import APIRouter, HTTPException
from backend.models.suitability_models import SuitabilityRequest, SuitabilityResponse
from backend.services.suitability_service import SuitabilityService

router = APIRouter(prefix="/suitability", tags=["Suitability"])


@router.post("/analyze", response_model=SuitabilityResponse)
def analyze_suitability(request: SuitabilityRequest):
    """
    Analyzes DEM terrain to identify candidate pond construction sites.

    Scoring criteria (each normalized 0–1):
      - Slope suitability: lower slope → higher score
      - Depression depth: deeper natural sink → higher score
      - Catchment/Flow accumulation: more upstream → higher score
      - Elevation: lower within ROI → higher score
      - Rainfall: higher annual rainfall → higher score

    Returns top-N candidates ranked by composite suitability score (0–100).
    The best-ranked candidate is marked as "Recommended".

    Results are planning estimates. Field survey required for engineering design.
    """
    try:
        return SuitabilityService.analyze(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suitability analysis failed: {str(e)}")
