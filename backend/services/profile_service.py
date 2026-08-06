"""
profile_service.py
Computes elevation profiles along a user-drawn transect line.

Algorithm:
  Sample DEM at `num_samples` evenly-spaced points along the great-circle arc
  from start_point to end_point, using bilinear interpolation to get sub-pixel
  accurate elevations.  Each sample records cumulative distance from start
  and interpolated elevation.
"""
import math
import numpy as np
from typing import List

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.phase4_models import (
    ElevationProfileRequest, ElevationProfileResponse, ElevationProfilePoint
)
from backend.utils.geo_utils import haversine_distance


class ProfileService:
    @classmethod
    def compute_profile(cls, request: ElevationProfileRequest) -> ElevationProfileResponse:
        dem = np.array(request.elevation_matrix, dtype=float)
        rows, cols = dem.shape
        bounds = request.bounds
        n = request.num_samples

        # Linearly interpolate lat/lng positions along transect
        lats_sample = np.linspace(request.start_point.lat, request.end_point.lat, n)
        lngs_sample = np.linspace(request.start_point.lng, request.end_point.lng, n)

        # Grid coordinate mapping helpers
        lat_range = bounds.north - bounds.south
        lng_range = bounds.east - bounds.west

        profile: List[ElevationProfilePoint] = []
        cum_dist = 0.0
        prev_lat, prev_lng = float(lats_sample[0]), float(lngs_sample[0])

        for i in range(n):
            lat = float(lats_sample[i])
            lng = float(lngs_sample[i])

            # Fractional row / col indices
            r_frac = (bounds.north - lat) / (lat_range + 1e-12) * (rows - 1)
            c_frac = (lng - bounds.west) / (lng_range + 1e-12) * (cols - 1)

            # Clamp to grid
            r_frac = max(0.0, min(r_frac, rows - 1.0))
            c_frac = max(0.0, min(c_frac, cols - 1.0))

            # Bilinear interpolation
            r0, r1 = int(math.floor(r_frac)), min(int(math.ceil(r_frac)), rows - 1)
            c0, c1 = int(math.floor(c_frac)), min(int(math.ceil(c_frac)), cols - 1)
            dr = r_frac - r0
            dc = c_frac - c0

            elev = (
                dem[r0, c0] * (1 - dr) * (1 - dc) +
                dem[r0, c1] * (1 - dr) * dc +
                dem[r1, c0] * dr * (1 - dc) +
                dem[r1, c1] * dr * dc
            )

            if i > 0:
                cum_dist += haversine_distance(prev_lat, prev_lng, lat, lng)
            prev_lat, prev_lng = lat, lng

            profile.append(ElevationProfilePoint(
                distance_m=round(cum_dist, 1),
                elevation=round(float(elev), 1),
                lat=round(lat, 6),
                lng=round(lng, 6),
            ))

        elevs = [p.elevation for p in profile]
        min_elev = float(min(elevs))
        max_elev = float(max(elevs))

        # Cumulative gain and loss
        gain = 0.0
        loss = 0.0
        for i in range(1, len(elevs)):
            diff = elevs[i] - elevs[i - 1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        return ElevationProfileResponse(
            success=True,
            profile=profile,
            total_distance_m=round(cum_dist, 1),
            min_elevation=round(min_elev, 1),
            max_elevation=round(max_elev, 1),
            elevation_gain_m=round(gain, 1),
            elevation_loss_m=round(loss, 1),
        )
