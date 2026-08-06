import os
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from typing import Tuple, Dict, Any

from backend.config import settings
from backend.models.dem_models import BoundingBox
from backend.models.terrain_models import SlopeRequest, SlopeResponse, PointQueryRequest, PointQueryResponse

class TerrainService:
    @staticmethod
    def compute_slope_and_aspect(elev_matrix: np.ndarray, pixel_size_m: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes slope (in degrees) and aspect (in degrees) using DEM gradients.
        Slope = arctan(sqrt((dz/dx)^2 + (dz/dy)^2)) * 180 / pi
        Aspect = atan2(-dy, dx) * 180 / pi (converted to 0..360 clockwise from North)
        """
        dy, dx = np.gradient(elev_matrix, pixel_size_m)
        slope_rad = np.arctan(np.sqrt(dx * dx + dy * dy))
        slope_deg = np.degrees(slope_rad)
        
        aspect_rad = np.arctan2(-dy, dx)
        aspect_deg = np.degrees(aspect_rad)
        # Convert aspect from math angle to compass azimuth (0 = North, 90 = East, 180 = South, 270 = West)
        aspect_compass = (450.0 - aspect_deg) % 360.0
        
        return slope_deg, aspect_compass

    @classmethod
    def process_slope_map(cls, request: SlopeRequest) -> SlopeResponse:
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        slope_deg, aspect_compass = cls.compute_slope_and_aspect(elev_matrix, request.pixel_size_m)
        
        min_slope = float(np.nanmin(slope_deg))
        max_slope = float(np.nanmax(slope_deg))
        mean_slope = float(np.nanmean(slope_deg))
        
        # Generate Slope Heatmap PNG (Spectral/Magma colormap for steep slopes)
        filename = f"{request.dem_id}_slope.png"
        save_path = os.path.join(settings.STORAGE_DIR, filename)
        
        norm_slope = (slope_deg - min_slope) / (max_slope - min_slope + 1e-6)
        cmap = plt.get_cmap('YlOrRd')  # Yellow to Deep Red for slope severity
        rgba = cmap(norm_slope)
        
        # Set background alpha
        rgba[..., 3] = 0.75
        
        img = Image.fromarray((rgba * 255).astype(np.uint8))
        img.save(save_path, "PNG")
        
        return SlopeResponse(
            success=True,
            slope_heatmap_url=f"/storage/{filename}",
            min_slope_deg=round(min_slope, 1),
            max_slope_deg=round(max_slope, 1),
            mean_slope_deg=round(mean_slope, 1),
        )

    @classmethod
    def query_point_terrain(cls, request: PointQueryRequest) -> PointQueryResponse:
        elev_matrix = np.array(request.elevation_matrix, dtype=float)
        rows, cols = elev_matrix.shape
        bounds = request.bounds
        
        # Map lat/lng to grid cell indices
        r = int(round((bounds.north - request.lat) / (bounds.north - bounds.south + 1e-9) * (rows - 1)))
        c = int(round((request.lng - bounds.west) / (bounds.east - bounds.west + 1e-9) * (cols - 1)))
        
        r = max(0, min(r, rows - 1))
        c = max(0, min(c, cols - 1))
        
        slope_matrix, aspect_matrix = cls.compute_slope_and_aspect(elev_matrix, request.pixel_size_m)
        
        elevation = float(elev_matrix[r, c])
        slope = float(slope_matrix[r, c])
        aspect = float(aspect_matrix[r, c])
        
        # Convert aspect degrees to cardinal direction name
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        cardinal_idx = int((aspect + 22.5) // 45) % 8
        cardinal_name = directions[cardinal_idx]
        
        return PointQueryResponse(
            elevation=round(elevation, 1),
            slope_deg=round(slope, 1),
            aspect_deg=round(aspect, 1),
            aspect_cardinal=cardinal_name,
        )
