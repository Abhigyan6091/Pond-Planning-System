from fastapi import APIRouter
from backend.api.dem_routes import router as dem_router
from backend.api.contour_routes import router as contour_router
from backend.api.terrain_routes import router as terrain_router
from backend.api.hydrology_routes import router as hydrology_router
from backend.api.analysis_routes import router as analysis_router
from backend.api.export_routes import router as export_router
from backend.api.rainfall_routes import router as rainfall_router
from backend.api.runoff_routes import router as runoff_router
from backend.api.suitability_routes import router as suitability_router
from backend.api.report_routes import router as report_router
from backend.api.contour_analysis_routes import router as contour_analysis_router  # Phase 2

api_router = APIRouter()

@api_router.get("", summary="API Root Status")
@api_router.get("/", summary="API Root Status")
def api_status():
    return {
        "status": "online",
        "message": "TERRAIN ANALYZER - Advanced DEM & Contour Hydrology API",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "evaluation_endpoints": {
            "analyzeContour": "/api/contour-analysis/analyzeContour",
            "findCatchment": "/api/contour-analysis/findCatchment",
            "analyzeContour_direct": "/api/analyzeContour",
            "findCatchment_direct": "/api/findCatchment",
        }
    }

api_router.include_router(dem_router)
api_router.include_router(contour_router)
api_router.include_router(terrain_router)
api_router.include_router(hydrology_router)
api_router.include_router(analysis_router)
api_router.include_router(export_router)
api_router.include_router(rainfall_router)
api_router.include_router(runoff_router)
api_router.include_router(suitability_router)
api_router.include_router(report_router)
api_router.include_router(contour_analysis_router)  # Phase 2 (/api/contour-analysis/...)

# Direct aliases for evaluation compatibility (/api/analyzeContour & /api/findCatchment)
api_router.add_api_route(
    "/analyzeContour",
    endpoint=contour_analysis_router.routes[0].endpoint,
    methods=["POST"],
    response_model=contour_analysis_router.routes[0].response_model,
    summary="[Evaluation Alias] Analyze KML/KMZ contour map",
    tags=["Phase 2 – Contour Analysis"]
)
api_router.add_api_route(
    "/findCatchment",
    endpoint=contour_analysis_router.routes[1].endpoint,
    methods=["POST"],
    response_model=contour_analysis_router.routes[1].response_model,
    summary="[Evaluation Alias] Find Catchment for KML/KMZ contour map",
    tags=["Phase 2 – Contour Analysis"]
)
