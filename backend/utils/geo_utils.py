import math
import numpy as np
from typing import Tuple, List, Dict
from shapely.geometry import Polygon, Point

EARTH_RADIUS_KM = 6371.0

def latlng_to_bbox(lat: float, lng: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Computes a bounding box (south, west, north, east) around a central point (lat, lng)
    with specified radius in kilometers.
    """
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    
    south = lat - lat_delta
    north = lat + lat_delta
    west = lng - lng_delta
    east = lng + lng_delta
    
    return (south, west, north, east)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes geodesic distance in meters between two lat/lon points.
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * 1000.0 * c

def calculate_polygon_area_m2(coords: List[List[float]]) -> float:
    """
    Computes approximate surface area in m^2 for a lat/lon polygon.
    coords: List of [lng, lat]
    """
    if len(coords) < 3:
        return 0.0
    
    poly = Polygon(coords)
    centroid_lat = poly.centroid.y
    
    # Scale factors for degrees to meters at centroid latitude
    meters_per_deg_lat = 111000.0
    meters_per_deg_lon = 111000.0 * math.cos(math.radians(centroid_lat))
    
    # Project polygon vertices to local planar meter coordinates
    projected_coords = [
        ((pt[0] - poly.centroid.x) * meters_per_deg_lon,
         (pt[1] - poly.centroid.y) * meters_per_deg_lat)
        for pt in coords
    ]
    
    proj_poly = Polygon(projected_coords)
    return abs(proj_poly.area)

def polygon_bounds(coords: List[List[float]]) -> Tuple[float, float, float, float]:
    """
    Returns (south, west, north, east) for a polygon coordinate list.
    """
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    return (min(lats), min(lons), max(lats), max(lons))
