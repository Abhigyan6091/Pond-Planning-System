from fastapi import APIRouter, HTTPException
from backend.models.runoff_models import RunoffRequest, RunoffResponse
from backend.services.runoff_service import RunoffService

router = APIRouter(prefix="/runoff", tags=["Runoff"])


@router.post("/estimate", response_model=RunoffResponse)
def estimate_runoff(request: RunoffRequest):
    """
    Estimates annual surface runoff volume using the Runoff Coefficient Method:
        V = P × A × C
    where P = rainfall depth (m), A = catchment area (m²), C = runoff coefficient.
    Note: Distinguish total seasonal volume V = P × A × C from peak discharge Q = C · i · A.

    Configurable runoff coefficient presets:
      - low    (C = 0.15): Dense forest / permeable soil
      - medium (C = 0.40): Mixed / agricultural land
      - high   (C = 0.70): Degraded / semi-impervious land
      - urban  (C = 0.85): Urban / impervious surface

    Result is a planning estimate — not a substitute for engineering hydrology.
    """
    try:
        return RunoffService.estimate_runoff(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Runoff estimation failed: {str(e)}")
