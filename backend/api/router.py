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
api_router.include_router(contour_analysis_router)  # Phase 2
