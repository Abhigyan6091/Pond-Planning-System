"""
export_service.py
Generates downloadable files (GeoJSON, CSV, JSON reports) for terrain analysis results.
"""
import json
import csv
import io
from typing import List, Dict, Any
from backend.models.phase4_models import ElevationProfilePoint


class ExportService:
    @staticmethod
    def contours_to_geojson(contours: List[Dict[str, Any]], dem_id: str) -> str:
        """
        Converts contour polylines list to standard GeoJSON FeatureCollection.
        """
        features = []
        for c in contours:
            # coordinates are [lat, lng], GeoJSON requires [lng, lat]
            coords = [[pt[1], pt[0]] for pt in c.get('coordinates', [])]
            feature = {
                "type": "Feature",
                "id": c.get('id'),
                "geometry": {
                    "type": "LineString" if not c.get('is_closed') else "Polygon",
                    "coordinates": coords if not c.get('is_closed') else [coords],
                },
                "properties": {
                    "elevation_m": c.get('elevation'),
                    "length_m": c.get('length_m'),
                    "length_km": c.get('length_km'),
                    "vertex_count": c.get('vertex_count'),
                    "is_closed": c.get('is_closed'),
                    "area_m2": c.get('area_m2'),
                    "area_km2": c.get('area_km2'),
                }
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "name": f"Contours_{dem_id}",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            },
            "features": features
        }
        return json.dumps(geojson, indent=2)

    @staticmethod
    def contours_to_csv(contours: List[Dict[str, Any]]) -> str:
        """
        Converts contours to CSV format (id, elevation_m, length_m, is_closed, area_m2).
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["contour_id", "elevation_m", "length_m", "length_km", "vertex_count", "is_closed", "area_m2", "area_km2"])

        for c in contours:
            writer.writerow([
                c.get('id'),
                c.get('elevation'),
                c.get('length_m'),
                c.get('length_km'),
                c.get('vertex_count'),
                c.get('is_closed'),
                c.get('area_m2') or '',
                c.get('area_km2') or '',
            ])
        return output.getvalue()

    @staticmethod
    def profile_to_csv(profile: List[Dict[str, Any]]) -> str:
        """
        Converts elevation profile points to CSV format.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["distance_m", "elevation_m", "latitude", "longitude"])

        for p in profile:
            writer.writerow([
                p.get('distance_m'),
                p.get('elevation'),
                p.get('lat'),
                p.get('lng'),
            ])
        return output.getvalue()
