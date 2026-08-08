"""
export_service.py
Generates downloadable files (GeoJSON, CSV) for terrain analysis results.

BUG FIX: The original contours_to_geojson() was swapping [lng,lat] coordinates
to [lat,lng] incorrectly. Contour coordinates from ContourService are already
stored as [lng, lat] (GeoJSON standard). No swap needed.
"""
import json
import csv
import io
from typing import List, Dict, Any


class ExportService:
    @staticmethod
    def contours_to_geojson(contours: List[Dict[str, Any]], dem_id: str) -> str:
        """
        Converts contour polylines list to standard GeoJSON FeatureCollection.
        Coordinates are stored as [lng, lat] in ContourService — GeoJSON-compliant.
        """
        features = []
        for c in contours:
            # Coordinates are already [lng, lat] from ContourService — use directly
            coords = c.get('coordinates', [])
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
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
            "features": features
        }
        return json.dumps(geojson, indent=2)

    @staticmethod
    def contours_to_csv(contours: List[Dict[str, Any]]) -> str:
        """Exports contour polyline metadata table as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "contour_id", "elevation_m", "length_m", "length_km",
            "vertex_count", "is_closed", "area_m2", "area_km2"
        ])
        for c in contours:
            writer.writerow([
                c.get('id'), c.get('elevation'), c.get('length_m'),
                c.get('length_km'), c.get('vertex_count'), c.get('is_closed'),
                c.get('area_m2') or '', c.get('area_km2') or '',
            ])
        return output.getvalue()

    @staticmethod
    def profile_to_csv(profile: List[Dict[str, Any]]) -> str:
        """Exports elevation profile points to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["distance_m", "elevation_m", "latitude", "longitude"])
        for p in profile:
            writer.writerow([p.get('distance_m'), p.get('elevation'), p.get('lat'), p.get('lng')])
        return output.getvalue()

    @staticmethod
    def candidate_sites_to_csv(candidates: List[Dict[str, Any]]) -> str:
        """Exports candidate pond sites to CSV with all suitability fields."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "rank", "site_id", "latitude", "longitude", "elevation_m",
            "slope_deg", "depression_depth_m", "flow_accumulation",
            "catchment_area_km2", "est_depth_m", "est_surface_area_m2",
            "est_volume_m3", "rainfall_mm", "est_runoff_m3",
            "suitability_score", "suitability_tier",
            "slope_score", "depression_score", "catchment_score",
            "elevation_score", "rainfall_score",
        ])
        for c in candidates:
            scores = c.get('scores', {})
            writer.writerow([
                c.get('rank'), c.get('site_id'),
                c.get('lat'), c.get('lng'), c.get('elevation_m'),
                c.get('slope_deg'), c.get('depression_depth_m'),
                c.get('flow_accumulation'), c.get('catchment_area_km2'),
                c.get('estimated_depth_m'), c.get('estimated_surface_area_m2'),
                c.get('estimated_volume_m3'), c.get('rainfall_mm') or '',
                c.get('estimated_runoff_m3') or '',
                scores.get('composite_score', ''), c.get('suitability_tier', ''),
                scores.get('slope_score', ''), scores.get('depression_score', ''),
                scores.get('catchment_score', ''), scores.get('elevation_score', ''),
                scores.get('rainfall_score', ''),
            ])
        return output.getvalue()

    @staticmethod
    def catchment_to_geojson(catchment_polygon: List[List[float]], properties: Dict[str, Any]) -> str:
        """Exports catchment polygon as GeoJSON Polygon. coords are [lng, lat]."""
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [catchment_polygon]
                },
                "properties": properties
            }]
        }
        return json.dumps(geojson, indent=2)

    @staticmethod
    def pond_sites_to_geojson(candidates: List[Dict[str, Any]]) -> str:
        """Exports candidate pond sites as GeoJSON PointCollection."""
        features = []
        for c in candidates:
            scores = c.get('scores', {})
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [c.get('lng'), c.get('lat')]
                },
                "properties": {
                    "rank": c.get('rank'),
                    "site_id": c.get('site_id'),
                    "elevation_m": c.get('elevation_m'),
                    "slope_deg": c.get('slope_deg'),
                    "catchment_area_km2": c.get('catchment_area_km2'),
                    "estimated_depth_m": c.get('estimated_depth_m'),
                    "estimated_volume_m3": c.get('estimated_volume_m3'),
                    "suitability_score": scores.get('composite_score'),
                    "suitability_tier": c.get('suitability_tier'),
                }
            })
        return json.dumps({"type": "FeatureCollection", "features": features}, indent=2)
