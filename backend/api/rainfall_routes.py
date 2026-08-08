from fastapi import APIRouter, HTTPException
from backend.models.rainfall_models import RainfallRequest, RainfallResponse
from backend.services.rainfall_service import RainfallService

router = APIRouter(prefix="/rainfall", tags=["Rainfall"])


@router.post("/historical", response_model=RainfallResponse)
def get_historical_rainfall(request: RainfallRequest):
    """
    Fetches historical daily precipitation from Open-Meteo Archive API and
    returns annual, monthly, seasonal (monsoon), and time-series statistics.

    Data source: Open-Meteo.com — free, no API key required.
    Covers 1940–present at ~9 km resolution.
    """
    try:
        return RainfallService.fetch_rainfall(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rainfall fetch failed: {str(e)}")
