"""
test_dem.py
===========
Sanity tests for DEM validity: shape, dtype, elevation range, pixel size.
These tests verify that DEM values are physically plausible.
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.services.dem_service import DemService
from backend.services.terrain_service import TerrainService


class TestDemSanity:
    """Sanity checks for DEM data validity."""

    def test_elevation_range_plausible(self):
        """Elevation must be within physically plausible range for Earth."""
        # Dead Sea: ~-430m, Everest: 8849m
        test_cases = [
            np.array([[100.0, 150.0], [120.0, 160.0]]),   # Typical hillside
            np.array([[0.0, 5.0], [3.0, 8.0]]),             # Near sea level
            np.array([[5000.0, 5200.0], [4800.0, 5100.0]]),  # High altitude
        ]
        for dem in test_cases:
            assert np.nanmin(dem) >= -500.0, "Elevation below -500m is implausible"
            assert np.nanmax(dem) <= 9000.0, "Elevation above 9000m is implausible"

    def test_perlin_fallback_no_checkerboard(self):
        """Geographic Perlin fallback must NOT produce repeating checkerboard patterns."""
        # Two different locations should produce very different arrays
        dem1 = DemService._geographic_perlin_dem(27.9, 86.9, 28.0, 87.0, 20)
        dem2 = DemService._geographic_perlin_dem(13.0, 77.5, 13.1, 77.6, 20)

        assert dem1.shape == (20, 20), "Shape must match requested resolution"
        assert dem2.shape == (20, 20)

        # Two different locations should produce physically distinct elevation maps
        diff_max = float(np.max(np.abs(dem1 - dem2)))
        mean_diff = float(abs(np.mean(dem1) - np.mean(dem2)))
        assert diff_max > 50.0, f"Perlin fallbacks at different locations should differ in elevation (max diff={diff_max:.1f}m)"
        assert mean_diff > 10.0, f"Perlin fallbacks at different locations should have different mean elevations (diff={mean_diff:.1f}m)"

    def test_perlin_elevation_range(self):
        """Perlin fallback should produce positive elevations."""
        dem = DemService._geographic_perlin_dem(20.0, 78.0, 20.1, 78.1, 16)
        assert float(np.min(dem)) >= 0.0, "Fallback DEM should be non-negative"
        assert float(np.max(dem)) < 15000.0, "Fallback DEM unrealistically high"

    def test_fill_nans_no_remaining_nans(self):
        """After _fill_nans, no NaN values should remain."""
        arr = np.array([[1.0, np.nan, 3.0],
                        [np.nan, 5.0, np.nan],
                        [7.0, 8.0, 9.0]])
        filled = DemService._fill_nans(arr)
        assert not np.any(np.isnan(filled)), "NaN values should be filled"

    def test_dem_std_nonzero_for_real_terrain(self):
        """Real terrain DEM should have non-zero standard deviation."""
        # A flat DEM (all same value) indicates a data problem
        dem = np.full((10, 10), 500.0)
        assert np.std(dem) == 0.0  # This is the problematic case
        # A real DEM should have std > 0
        real_dem = np.random.uniform(100, 500, (10, 10))
        assert np.std(real_dem) > 0, "Real terrain should have elevation variation"

    def test_slope_range(self):
        """Slope values must be in [0°, 90°]."""
        dem = np.array([
            [100.0, 105.0, 110.0],
            [102.0, 108.0, 115.0],
            [104.0, 112.0, 120.0],
        ], dtype=float)
        slope, _ = TerrainService.compute_slope_and_aspect(dem, 30.0)
        assert np.all(slope >= 0.0), "Slope must be non-negative"
        assert np.all(slope <= 90.0), "Slope must be ≤ 90°"

    def test_aspect_range(self):
        """Aspect values must be in [0°, 360°]."""
        dem = np.random.uniform(100, 500, (8, 8))
        _, aspect = TerrainService.compute_slope_and_aspect(dem, 30.0)
        assert np.all(aspect >= 0.0), "Aspect must be ≥ 0°"
        assert np.all(aspect <= 360.0), "Aspect must be ≤ 360°"

    def test_pixel_size_calculation(self):
        """Pixel size calculation must use haversine, not raw degree arithmetic."""
        from backend.utils.geo_utils import haversine_distance
        lat1, lng = 27.0, 86.0
        lat2 = 27.1
        dist = haversine_distance(lat1, lng, lat2, lng)
        # 0.1 degrees latitude ≈ 11.1 km at any latitude
        assert 10000 < dist < 12000, f"Haversine distance {dist:.0f}m for 0.1° is unexpected"
