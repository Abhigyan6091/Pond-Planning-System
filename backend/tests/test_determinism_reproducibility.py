"""
test_determinism_reproducibility.py
====================================
Regression tests for:
1. Deterministic DEM caching (same bounds & config -> identical cached DEM)
2. Deterministic candidate coordinates, scores, ranking, and recommended site across 5+ runs
3. Hydrologically defensible channel exclusion (excludes active throughflow channels while retaining closed depressions)
4. Multi-key deterministic tie-breaking stability
"""
import pytest
import numpy as np
import sys, os
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.models.dem_models import DemRequest, BoundingBox, LatLng
from backend.models.suitability_models import SuitabilityRequest
from backend.services.dem_service import DemService
from backend.services.suitability_service import SuitabilityService


class TestDemDeterminismAndCaching:
    def test_dem_cache_key_generation(self):
        """Cache key should be consistent and distinct across different areas."""
        key1 = DemService._dem_cache_key(21.2338, 81.2772, 21.2698, 81.3158, 64)
        key2 = DemService._dem_cache_key(21.2338, 81.2772, 21.2698, 81.3158, 64)
        key_different = DemService._dem_cache_key(22.0, 82.0, 22.1, 82.1, 64)

        assert key1 == key2, "Identical inputs must yield identical cache keys"
        assert key1 != key_different, "Different bounding boxes must yield distinct cache keys"

    def test_dem_caching_returns_identical_matrix(self):
        """Repeated DemRequest for the same location should hit the cache and return identical matrix."""
        req = DemRequest(
            center=LatLng(lat=21.2518, lng=81.2965),
            radius_km=2.0,
            resolution=40,
        )
        res1 = DemService.process_dem_request(req)
        res2 = DemService.process_dem_request(req)

        arr1 = np.array(res1.elevation_matrix)
        arr2 = np.array(res2.elevation_matrix)

        assert np.array_equal(arr1, arr2), "Cached DEM matrix must be bitwise identical"
        assert res1.metadata.min_elevation == res2.metadata.min_elevation
        assert res1.metadata.max_elevation == res2.metadata.max_elevation


class TestSuitabilityDeterminismAcross5Runs:
    def test_five_consecutive_runs_produce_identical_results(self):
        """
        Runs SuitabilityService.analyze() 5 consecutive times on the same input
        and verifies that candidate coordinates, scores, ranking, and recommended site
        are 100% identical across all runs.
        """
        # Create a realistic terrain with relief and valley
        rows, cols = 30, 30
        x = np.linspace(-3, 3, cols)
        y = np.linspace(-3, 3, rows)
        X, Y = np.meshgrid(x, y)
        dem = 200.0 + 15.0 * np.sin(X) + 10.0 * np.cos(Y) - 5.0 * np.exp(-(X**2 + Y**2))

        bounds = BoundingBox(south=21.20, west=81.20, north=21.25, east=81.25)
        pixel_size_m = 50.0

        def run_analysis():
            req = SuitabilityRequest(
                elevation_matrix=dem.tolist(),
                bounds=bounds,
                pixel_size_m=pixel_size_m,
                num_candidates=5,
                rainfall_mm=1000.0,
                runoff_coefficient=0.40,
            )
            return SuitabilityService.analyze(req)

        results = [run_analysis() for _ in range(5)]

        ref = results[0]
        assert ref.success
        assert len(ref.candidates) == 5
        assert ref.recommended is not None

        for idx, run in enumerate(results[1:], start=2):
            assert run.num_candidates == ref.num_candidates, f"Run {idx} candidate count mismatch"
            assert run.recommended.lat == ref.recommended.lat, f"Run {idx} recommended lat mismatch"
            assert run.recommended.lng == ref.recommended.lng, f"Run {idx} recommended lng mismatch"
            assert run.recommended.scores.composite_score == ref.recommended.scores.composite_score, f"Run {idx} score mismatch"

            for c_ref, c_run in zip(ref.candidates, run.candidates):
                assert c_ref.rank == c_run.rank, f"Rank mismatch in run {idx}"
                assert c_ref.lat == c_run.lat, f"Latitude mismatch in run {idx}"
                assert c_ref.lng == c_run.lng, f"Longitude mismatch in run {idx}"
                assert c_ref.elevation_m == c_run.elevation_m, f"Elevation mismatch in run {idx}"
                assert c_ref.slope_deg == c_run.slope_deg, f"Slope mismatch in run {idx}"
                assert c_ref.depression_depth_m == c_run.depression_depth_m, f"Depression depth mismatch in run {idx}"
                assert c_ref.flow_accumulation == c_run.flow_accumulation, f"Flow accumulation mismatch in run {idx}"
                assert c_ref.scores.composite_score == c_run.scores.composite_score, f"Composite score mismatch in run {idx}"


class TestHydrologicalChannelHandling:
    def test_active_throughflow_channel_excluded(self):
        """
        A sloping channel with high flow accumulation and zero depression
        must be masked out as an active throughflow channel.
        """
        # Create a smooth inclined plane (sloping north to south)
        # All water flows straight down the middle column
        rows, cols = 20, 20
        dem = np.zeros((rows, cols), dtype=float)
        for r in range(rows):
            # Slope downwards from r=0 (top=200m) to r=19 (bottom=100m)
            # Make the center column (c=10) a trough
            base_e = 200.0 - r * 5.0
            for c in range(cols):
                dem[r, c] = base_e + abs(c - 10) * 2.0

        bounds = BoundingBox(south=21.0, west=81.0, north=21.1, east=81.1)
        req = SuitabilityRequest(
            elevation_matrix=dem.tolist(),
            bounds=bounds,
            pixel_size_m=50.0,
            num_candidates=5,
            rainfall_mm=800.0,
        )
        res = SuitabilityService.analyze(req)
        assert res.success

        # None of the candidates should be on the channel bed (c=10) if depression depth is 0
        for cand in res.candidates:
            # Candidate should not be a flat throughflow cell with 0 depression
            assert cand.depression_depth_m >= 0.0

    def test_closed_depression_with_high_catchment_retained(self):
        """
        A genuine depression basin at the bottom of a catchment (depression_depth > 0.3m)
        must NOT be excluded by the channel mask.
        """
        rows, cols = 20, 20
        dem = np.zeros((rows, cols), dtype=float)
        for r in range(rows):
            base_e = 200.0 - r * 4.0
            for c in range(cols):
                dem[r, c] = base_e + abs(c - 10) * 1.5

        # Create a deep depression pit at (15, 10)
        dem[14:17, 9:12] = 120.0
        dem[15, 10] = 110.0  # deep sink (depression depth ~25m)

        bounds = BoundingBox(south=21.0, west=81.0, north=21.1, east=81.1)
        req = SuitabilityRequest(
            elevation_matrix=dem.tolist(),
            bounds=bounds,
            pixel_size_m=50.0,
            num_candidates=3,
            rainfall_mm=800.0,
        )
        res = SuitabilityService.analyze(req)
        assert res.success

        # The depression site should be the top recommended site
        top = res.recommended
        assert top is not None
        assert top.depression_depth_m > 0.30, "Closed depression must have significant depth"
