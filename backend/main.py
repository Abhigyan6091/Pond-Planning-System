import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# Include main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static file directory for serving DEM overlays and exported files
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")

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
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
