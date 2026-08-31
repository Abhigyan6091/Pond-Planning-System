import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.config import settings
from backend.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="TERRAIN ANALYZER - Advanced DEM Terrain Analysis, Hydrology & Contour API",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main API router under /api
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static file directory for serving DEM overlays and exported files
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")

# Path to built React frontend
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.exists(frontend_dist) and os.path.isdir(os.path.join(frontend_dist, "assets")):
    # Mount Vite static assets (/assets/...)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="static-assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    def root():
        return {
            "status": "online",
            "app": settings.PROJECT_NAME,
            "docs_url": "/docs",
            "dem_endpoint": f"{settings.API_V1_STR}/dem/download-dem"
        }

if __name__ == "__main__":
    import uvicorn
    # Default to 8000 locally, or read PORT environment variable if set
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
