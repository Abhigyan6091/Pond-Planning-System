from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.services.export_service import ExportService

router = APIRouter(prefix="/export", tags=["Export"])


class ExportContoursRequest(BaseModel):
    dem_id: str
    contours: List[Dict[str, Any]]


class ExportProfileRequest(BaseModel):
    profile: List[Dict[str, Any]]


class ExportCandidatesRequest(BaseModel):
    candidates: List[Dict[str, Any]]


class ExportCatchmentRequest(BaseModel):
    catchment_polygon: List[List[float]]
    properties: Optional[Dict[str, Any]] = {}


class ExportPondSitesRequest(BaseModel):
    candidates: List[Dict[str, Any]]


@router.post("/contours/geojson")
def export_contours_geojson(request: ExportContoursRequest):
    """Exports contour polylines as standard GeoJSON FeatureCollection."""
    try:
        geojson_str = ExportService.contours_to_geojson(request.contours, request.dem_id)
        return Response(
            content=geojson_str,
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename=contours_{request.dem_id}.geojson"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GeoJSON export failed: {str(e)}")


@router.post("/contours/csv")
def export_contours_csv(request: ExportContoursRequest):
    """Exports contour polyline metadata table as CSV file."""
    try:
        csv_str = ExportService.contours_to_csv(request.contours)
        return Response(
            content=csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=contours_{request.dem_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")


@router.post("/profile/csv")
def export_profile_csv(request: ExportProfileRequest):
    """Exports transect line distance-elevation samples as CSV file."""
    try:
        csv_str = ExportService.profile_to_csv(request.profile)
        return Response(
            content=csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=elevation_profile.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile CSV export failed: {str(e)}")


@router.post("/candidates/csv")
def export_candidates_csv(request: ExportCandidatesRequest):
    """Exports candidate pond sites with suitability scores as CSV."""
    try:
        csv_str = ExportService.candidate_sites_to_csv(request.candidates)
        return Response(
            content=csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=candidate_pond_sites.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Candidate CSV export failed: {str(e)}")


@router.post("/catchment/geojson")
def export_catchment_geojson(request: ExportCatchmentRequest):
    """Exports watershed catchment boundary as GeoJSON Polygon."""
    try:
        geojson_str = ExportService.catchment_to_geojson(
            request.catchment_polygon, request.properties or {}
        )
        return Response(
            content=geojson_str,
            media_type="application/geo+json",
            headers={"Content-Disposition": "attachment; filename=catchment.geojson"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Catchment GeoJSON export failed: {str(e)}")


@router.post("/pond-sites/geojson")
def export_pond_sites_geojson(request: ExportPondSitesRequest):
    """Exports candidate pond sites as GeoJSON Point FeatureCollection."""
    try:
        geojson_str = ExportService.pond_sites_to_geojson(request.candidates)
        return Response(
            content=geojson_str,
            media_type="application/geo+json",
            headers={"Content-Disposition": "attachment; filename=pond_sites.geojson"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pond sites GeoJSON export failed: {str(e)}")
