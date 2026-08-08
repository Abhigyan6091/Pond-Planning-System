"""
test_pond.py, test_runoff.py, test_suitability.py
Combined test file for pond detection, runoff estimation, and suitability scoring.
"""
import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.models.dem_models import BoundingBox, LatLng
from backend.models.phase4_models import PondRequest
from backend.models.runoff_models import RunoffRequest
from backend.models.suitability_models import SuitabilityRequest
from backend.services.pond_service import PondService
from backend.services.runoff_service import RunoffService
from backend.services.suitability_service import SuitabilityService


# ─────────────────────────────────────────────────────────────────────
# POND DETECTION TESTS
# ─────────────────────────────────────────────────────────────────────
def make_pond_dem():
    """DEM with a clear depression in the centre."""
    dem = np.ones((10, 10), dtype=float) * 200.0
    # Create a depression in the centre
    dem[4:7, 4:7] = 185.0
    dem[5, 5] = 180.0  # Deepest point
    return dem


def make_pond_request(dem, click_lat=27.025, click_lng=86.025):
    return PondRequest(
        click_point=LatLng(lat=click_lat, lng=click_lng),
        elevation_matrix=dem.tolist(),
        bounds=BoundingBox(south=27.0, west=86.0, north=27.05, east=86.05),
        pixel_size_m=50.0,
    )


class TestPondDetection:
    def test_pond_response_success(self):
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert result.success

    def test_pond_depth_nonnegative(self):
        """Pond depth must never be negative."""
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert result.pond.max_depth >= 0.0, "Pond depth must be ≥ 0"

    def test_pond_volume_nonnegative(self):
        """Pond storage volume must be non-negative."""
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert result.pond.volume_m3 >= 0.0, "Pond volume must be ≥ 0"

    def test_pond_surface_area_positive(self):
        """Pond surface area must be positive."""
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert result.pond.surface_area_m2 > 0.0, "Surface area must be > 0"

    def test_water_level_above_bottom(self):
        """Water level must be above or equal to the bottom elevation."""
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert result.pond.water_level >= result.pond.bottom_elevation, \
            "Water level must be ≥ bottom elevation"

    def test_volume_km3_consistent_with_m3(self):
        """volume_km3 = volume_m3 / 1e9 — consistency check."""
        dem = make_pond_dem()
        req = make_pond_request(dem)
        result = PondService.detect_pond(req)
        assert abs(result.pond.volume_km3 - result.pond.volume_m3 / 1e9) < 1e-15, \
            "volume_km3 must equal volume_m3 / 1e9"


# ─────────────────────────────────────────────────────────────────────
# RUNOFF ESTIMATION TESTS
# ─────────────────────────────────────────────────────────────────────
class TestRunoffEstimation:
    def test_basic_runoff_calculation(self):
        """V = P×A×C: 600mm × 1,000,000 m² × 0.4 = 240,000 m³"""
        req = RunoffRequest(
            rainfall_mm=600.0,
            catchment_area_m2=1_000_000.0,
            runoff_coefficient=0.40,
        )
        result = RunoffService.estimate_runoff(req)
        assert result.success
        expected = (600.0 / 1000.0) * 1_000_000.0 * 0.40  # = 240,000 m³
        assert abs(result.runoff_volume_m3 - expected) < 1.0, \
            f"Expected {expected:.0f} m³, got {result.runoff_volume_m3:.0f} m³"

    def test_runoff_nonnegative(self):
        req = RunoffRequest(rainfall_mm=0.0, catchment_area_m2=500000.0, runoff_coefficient=0.4)
        result = RunoffService.estimate_runoff(req)
        assert result.runoff_volume_m3 >= 0.0

    def test_runoff_increases_with_rainfall(self):
        """More rainfall → more runoff."""
        base = RunoffRequest(rainfall_mm=400.0, catchment_area_m2=1e6, runoff_coefficient=0.4)
        more = RunoffRequest(rainfall_mm=800.0, catchment_area_m2=1e6, runoff_coefficient=0.4)
        r1 = RunoffService.estimate_runoff(base)
        r2 = RunoffService.estimate_runoff(more)
        assert r2.runoff_volume_m3 > r1.runoff_volume_m3

    def test_runoff_increases_with_catchment(self):
        """Larger catchment → more runoff."""
        small = RunoffRequest(rainfall_mm=600.0, catchment_area_m2=1e5, runoff_coefficient=0.4)
        large = RunoffRequest(rainfall_mm=600.0, catchment_area_m2=1e7, runoff_coefficient=0.4)
        r1 = RunoffService.estimate_runoff(small)
        r2 = RunoffService.estimate_runoff(large)
        assert r2.runoff_volume_m3 > r1.runoff_volume_m3

    def test_preset_coefficient_applied(self):
        """Using preset 'low' should set C = 0.15."""
        req = RunoffRequest(
            rainfall_mm=600.0, catchment_area_m2=1e6,
            runoff_coefficient=0.4, coefficient_preset="low"
        )
        result = RunoffService.estimate_runoff(req)
        assert abs(result.runoff_coefficient - 0.15) < 1e-6

    def test_million_m3_consistency(self):
        """runoff_volume_million_m3 must equal runoff_volume_m3 / 1e6."""
        req = RunoffRequest(rainfall_mm=700.0, catchment_area_m2=2e6, runoff_coefficient=0.45)
        result = RunoffService.estimate_runoff(req)
        expected_million = result.runoff_volume_m3 / 1e6
        assert abs(result.runoff_volume_million_m3 - expected_million) < 0.001


# ─────────────────────────────────────────────────────────────────────
# SUITABILITY SCORING TESTS
# ─────────────────────────────────────────────────────────────────────
def make_suitability_dem():
    """12×12 DEM with a valley in the centre."""
    dem = np.ones((12, 12), dtype=float) * 300.0
    # Create valley
    for i in range(4, 8):
        for j in range(4, 8):
            dem[i, j] = 280.0 - abs(i - 6) * 5 - abs(j - 6) * 5
    return dem


def make_suitability_request(dem, rainfall_mm=650.0, n=5):
    return SuitabilityRequest(
        elevation_matrix=dem.tolist(),
        bounds=BoundingBox(south=21.0, west=78.0, north=21.1, east=78.1),
        pixel_size_m=100.0,
        num_candidates=n,
        rainfall_mm=rainfall_mm,
        runoff_coefficient=0.40,
    )


class TestSuitabilityScoring:
    def test_returns_candidates(self):
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        assert result.success
        assert len(result.candidates) >= 1

    def test_score_in_range(self):
        """Composite score must be in [0, 100]."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=5)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            score = site.scores.composite_score
            assert 0.0 <= score <= 100.0, f"Score {score} out of [0,100]"

    def test_component_scores_in_01(self):
        """All individual component scores must be in [0, 1]."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            s = site.scores
            for name, val in [
                ("slope", s.slope_score),
                ("depression", s.depression_score),
                ("catchment", s.catchment_score),
                ("elevation", s.elevation_score),
                ("rainfall", s.rainfall_score),
            ]:
                assert 0.0 <= val <= 1.0, f"{name} score {val} out of [0,1]"

    def test_candidates_ranked_descending(self):
        """Candidates must be sorted best-first by composite score."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=5)
        result = SuitabilityService.analyze(req)
        scores = [s.scores.composite_score for s in result.candidates]
        assert scores == sorted(scores, reverse=True), "Candidates not ranked descending"

    def test_recommended_is_first(self):
        """Recommended site must equal the first candidate."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        if result.recommended and result.candidates:
            assert result.recommended.site_id == result.candidates[0].site_id

    def test_catchment_area_nonneg(self):
        """Estimated catchment area must be non-negative."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            assert site.catchment_area_m2 >= 0.0
            assert site.catchment_area_km2 >= 0.0

    def test_pond_depth_positive(self):
        """Estimated pond depth must be positive."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            assert site.estimated_depth_m > 0.0, "Pond depth must be > 0"

    def test_volume_nonneg(self):
        """Estimated pond volume must be non-negative."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=3)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            assert site.estimated_volume_m3 >= 0.0

    def test_runoff_nonneg_when_rainfall_provided(self):
        dem = make_suitability_dem()
        req = make_suitability_request(dem, rainfall_mm=600.0, n=3)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            if site.estimated_runoff_m3 is not None:
                assert site.estimated_runoff_m3 >= 0.0

    def test_spatial_separation(self):
        """No two candidates should occupy the same grid cell."""
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=5)
        result = SuitabilityService.analyze(req)
        coords = [(s.lat, s.lng) for s in result.candidates]
        assert len(set(coords)) == len(coords), "Duplicate candidate locations found"

    def test_tier_classification(self):
        """Every candidate must have a valid tier string."""
        valid_tiers = {"Recommended", "Highly Suitable", "Moderately Suitable", "Poor"}
        dem = make_suitability_dem()
        req = make_suitability_request(dem, n=5)
        result = SuitabilityService.analyze(req)
        for site in result.candidates:
            assert site.suitability_tier in valid_tiers, \
                f"Invalid tier: {site.suitability_tier}"
