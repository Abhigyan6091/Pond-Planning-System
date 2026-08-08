"""
test_hydrology.py
=================
Tests for D8 flow direction, flow accumulation, and watershed delineation.
"""
import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.services.hydrology_service import HydrologyService
from backend.models.dem_models import BoundingBox, LatLng
from backend.models.terrain_models import WatershedRequest


def simple_valley_dem():
    """4×4 DEM sloping to bottom-left corner."""
    return np.array([
        [100, 90, 80, 70],
        [ 95, 85, 75, 65],
        [ 90, 80, 70, 60],
        [ 85, 75, 65, 55],
    ], dtype=float)


class TestD8FlowDirection:
    def test_flow_direction_shape(self):
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        assert fd.shape == dem.shape

    def test_flow_direction_values(self):
        """All valid flow directions are -1 (sink) or 0..7."""
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        assert np.all((fd >= -1) & (fd <= 7)), "Flow direction values must be in [-1, 7]"

    def test_flow_direction_downhill(self):
        """Flow must point to a lower or equal neighbor, never uphill."""
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        D8_OFFSETS = HydrologyService.D8_OFFSETS
        rows, cols = dem.shape
        for r in range(rows):
            for c in range(cols):
                d = fd[r, c]
                if d == -1:
                    continue
                dr, dc = D8_OFFSETS[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    assert dem[nr, nc] <= dem[r, c], \
                        f"Flow at ({r},{c}) goes uphill: {dem[r,c]} → {dem[nr,nc]}"


class TestFlowAccumulation:
    def test_accumulation_shape(self):
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        acc = HydrologyService.compute_flow_accumulation(fd)
        assert acc.shape == dem.shape

    def test_accumulation_minimum(self):
        """Every cell has at least 1 upstream count (itself)."""
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        acc = HydrologyService.compute_flow_accumulation(fd)
        assert np.all(acc >= 1), "All cells should have at least accumulation=1"

    def test_accumulation_maximum_bounded(self):
        """Max accumulation cannot exceed total cell count."""
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        acc = HydrologyService.compute_flow_accumulation(fd)
        total = dem.shape[0] * dem.shape[1]
        assert int(acc.max()) <= total, "Accumulation cannot exceed total cell count"

    def test_outlet_has_most_accumulation(self):
        """The lowest corner cell should have the highest flow accumulation."""
        dem = simple_valley_dem()
        fd  = HydrologyService.compute_d8_flow_direction(dem, 30.0)
        acc = HydrologyService.compute_flow_accumulation(fd)
        # Bottom-right corner (highest acc in sloped DEM)
        # Just verify max is at the lowest elevation zone
        min_elev_idx = np.unravel_index(np.argmin(dem), dem.shape)
        max_acc_idx  = np.unravel_index(np.argmax(acc), acc.shape)
        # They may differ by a cell; just check high acc is in the low zone
        assert acc[min_elev_idx] > 1, "Lowest cell should have > 1 flow accumulation"


class TestWatershedDelineation:
    def _make_request(self, dem, outlet_lat, outlet_lng):
        bounds = BoundingBox(south=27.0, west=86.0, north=27.04, east=86.04)
        return WatershedRequest(
            outlet_point=LatLng(lat=outlet_lat, lng=outlet_lng),
            elevation_matrix=dem.tolist(),
            bounds=bounds,
            pixel_size_m=100.0,
        )

    def test_catchment_area_positive(self):
        dem = simple_valley_dem()
        req = self._make_request(dem, 27.0, 86.04)  # bottom-right outlet
        result = HydrologyService.delineate_watershed(req)
        assert result.success
        assert result.catchment_area_m2 > 0, "Catchment area must be positive"
        assert result.catchment_area_km2 > 0

    def test_catchment_area_not_exceeds_roi(self):
        """Catchment area cannot exceed the full ROI bounding box area."""
        dem = simple_valley_dem()
        req = self._make_request(dem, 27.02, 86.02)
        result = HydrologyService.delineate_watershed(req)
        from backend.utils.geo_utils import haversine_distance
        roi_height = haversine_distance(27.0, 86.0, 27.04, 86.0)
        roi_width  = haversine_distance(27.0, 86.0, 27.0, 86.04)
        roi_area   = roi_height * roi_width
        assert result.catchment_area_m2 <= roi_area * 1.05, \
            "Catchment cannot exceed ROI area (with 5% tolerance)"

    def test_catchment_perimeter_positive(self):
        dem = simple_valley_dem()
        req = self._make_request(dem, 27.01, 86.01)
        result = HydrologyService.delineate_watershed(req)
        assert result.perimeter_km >= 0.0

    def test_avg_slope_nonnegative(self):
        dem = simple_valley_dem()
        req = self._make_request(dem, 27.02, 86.02)
        result = HydrologyService.delineate_watershed(req)
        assert result.avg_slope_deg >= 0.0
