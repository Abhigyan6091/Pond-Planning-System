"""
test_stage_storage.py
======================
Tests for the Stage-Storage Curve calculation in PondService.

Conceptually: V = ∫ A(z) dz
Discrete levels: V(z_k) = ∑ max(0, z_k - E) × A_pixel

Sanity Requirements (Phase 12):
1. V >= 0 for all levels
2. V increases monotonically with water level (z_k >= z_{k-1} => V(z_k) >= V(z_{k-1}))
3. Storage at zero depth is zero (V(z_bottom) == 0)
"""
import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.phase4_models import PondRequest
from backend.services.pond_service import PondService


def make_sink_dem():
    """10×10 DEM with a bowl depression in the center."""
    dem = np.ones((10, 10), dtype=float) * 500.0
    dem[3:7, 3:7] = 490.0
    dem[4:6, 4:6] = 485.0
    dem[5, 5]     = 480.0  # Deepest point
    return dem


class TestStageStorageCurve:

    def test_stage_storage_curve_generated(self):
        dem = make_sink_dem()
        req = PondRequest(
            click_point=LatLng(lat=20.0, lng=78.0),
            elevation_matrix=dem.tolist(),
            bounds=BoundingBox(south=19.95, west=77.95, north=20.05, east=78.05),
            pixel_size_m=30.0,
        )
        res = PondService.detect_pond(req)
        assert res.success
        assert res.pond is not None
        curve = res.pond.stage_storage_curve
        assert len(curve) == 10, "Stage-storage curve must contain 10 discrete levels"

    def test_stage_storage_monotonicity(self):
        """Volume and surface area must increase monotonically with depth."""
        dem = make_sink_dem()
        req = PondRequest(
            click_point=LatLng(lat=20.0, lng=78.0),
            elevation_matrix=dem.tolist(),
            bounds=BoundingBox(south=19.95, west=77.95, north=20.05, east=78.05),
            pixel_size_m=30.0,
        )
        res = PondService.detect_pond(req)
        curve = res.pond.stage_storage_curve

        volumes = [pt.volume_m3 for pt in curve]
        depths = [pt.depth_m for pt in curve]

        # Depths must increase monotonically
        for i in range(1, len(depths)):
            assert depths[i] >= depths[i - 1], \
                f"Depth at index {i} ({depths[i]}) < previous ({depths[i-1]})"

        # Volume must increase monotonically
        for i in range(1, len(volumes)):
            assert volumes[i] >= volumes[i - 1], \
                f"Volume at index {i} ({volumes[i]}) < previous ({volumes[i-1]})"

    def test_storage_at_zero_depth_is_zero(self):
        """At zero depth (bottom elevation), volume must be 0 m³."""
        dem = make_sink_dem()
        req = PondRequest(
            click_point=LatLng(lat=20.0, lng=78.0),
            elevation_matrix=dem.tolist(),
            bounds=BoundingBox(south=19.95, west=77.95, north=20.05, east=78.05),
            pixel_size_m=30.0,
        )
        res = PondService.detect_pond(req)
        curve = res.pond.stage_storage_curve
        first_pt = curve[0]

        assert first_pt.depth_m == 0.0, "First stage point must be at depth 0"
        assert first_pt.volume_m3 == 0.0, "Volume at zero depth must be 0 m³"
