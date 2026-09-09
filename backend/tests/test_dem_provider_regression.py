import numpy as np
import pytest
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.config import settings
from backend.models.dem_models import DemRequest, LatLng
from backend.services.dem_service import DemService


@pytest.fixture(autouse=True)
def isolated_dem_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    DemService._dem_cache.clear()
    yield
    DemService._dem_cache.clear()


def test_requested_opentopodata_provider_is_tried_before_openzenith(monkeypatch):
    calls = []

    def fake_opentopography(cls, south, west, north, east, res, *args, **kwargs):
        calls.append("opentopography")
        return None

    def fake_openzenith(cls, south, west, north, east, res):
        calls.append("openzenith")
        return np.full((res, res), 123.0)

    def fake_opentopodata(cls, south, west, north, east, res, ds_url):
        calls.append("opentopodata")
        return np.full((res, res), 456.0)

    monkeypatch.setattr(DemService, "_fetch_opentopography_official", classmethod(fake_opentopography))
    monkeypatch.setattr(DemService, "_fetch_openzenith_grid", classmethod(fake_openzenith))
    monkeypatch.setattr(DemService, "_fetch_opentopodata_grid", classmethod(fake_opentopodata))
    DemService._dem_cache.clear()

    response = DemService.process_dem_request(DemRequest(
        center=LatLng(lat=21.2588, lng=81.2954),
        radius_km=2.0,
        provider="opentopodata",
        dem_type="COP30",
        resolution=20,
    ))

    assert calls[0] == "opentopodata"
    assert "OpenTopoData" in response.metadata.data_source
    assert response.elevation_matrix[0][0] == 456.0


def test_frontend_resolution_100_is_preserved_for_dense_map_contours(monkeypatch):
    def fake_fetch_real_dem(cls, south, west, north, east, res, *args, **kwargs):
        return np.full((res, res), 280.0), "test-dem"

    monkeypatch.setattr(DemService, "_fetch_real_dem", classmethod(fake_fetch_real_dem))
    DemService._dem_cache.clear()

    response = DemService.process_dem_request(DemRequest(
        center=LatLng(lat=21.2588, lng=81.2954),
        radius_km=2.0,
        provider="opentopodata",
        dem_type="COP30",
        resolution=100,
    ))

    assert response.metadata.width == 100
    assert response.metadata.height == 100
    assert np.array(response.elevation_matrix).shape == (100, 100)


def test_high_resolution_opentopodata_uses_resampled_real_grid_instead_of_perlin(monkeypatch):
    calls = []

    def fake_opentopography(cls, south, west, north, east, res, *args, **kwargs):
        return None

    def fake_openzenith(cls, south, west, north, east, res):
        return None

    def fake_opentopodata(cls, south, west, north, east, res, ds_url):
        calls.append(res)
        if res > 20:
            return None
        base = np.arange(res * res, dtype=float).reshape(res, res)
        return 260.0 + base / base.max()

    monkeypatch.setattr(DemService, "_fetch_opentopography_official", classmethod(fake_opentopography))
    monkeypatch.setattr(DemService, "_fetch_openzenith_grid", classmethod(fake_openzenith))
    monkeypatch.setattr(DemService, "_fetch_opentopodata_grid", classmethod(fake_opentopodata))

    arr, label = DemService._fetch_real_dem(
        21.24, 81.27, 21.28, 81.32, 100,
        provider="opentopodata",
        dem_type="COP30",
    )

    assert 20 in calls
    assert arr.shape == (100, 100)
    assert "OpenTopoData/SRTM-30m" in label
    assert "resampled" in label
    assert "Perlin" not in label
    assert 260.0 <= float(arr.min()) <= float(arr.max()) <= 261.0


def test_identical_map_selection_reuses_persisted_real_dem_after_memory_cache_clear(monkeypatch):
    responses = [
        (np.full((20, 20), 111.0), "first-real-provider"),
        (np.full((20, 20), 222.0), "changed-real-provider"),
    ]

    def fake_fetch_real_dem(cls, south, west, north, east, res, *args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(DemService, "_fetch_real_dem", classmethod(fake_fetch_real_dem))
    DemService._dem_cache.clear()

    request = DemRequest(
        center=LatLng(lat=21.2588, lng=81.2954),
        radius_km=2.0,
        provider="opentopodata",
        dem_type="COP30",
        resolution=20,
    )

    first = DemService.process_dem_request(request)
    DemService._dem_cache.clear()
    second = DemService.process_dem_request(request)

    assert first.metadata.data_source == "first-real-provider"
    assert second.metadata.data_source == "first-real-provider"
    assert second.elevation_matrix[0][0] == 111.0
    assert len(responses) == 1


def test_small_center_jitter_reuses_same_canonical_analysis_window(monkeypatch):
    calls = []

    def fake_fetch_real_dem(cls, south, west, north, east, res, *args, **kwargs):
        calls.append((south, west, north, east, res))
        return np.full((res, res), 333.0), f"fake-real-dem-{len(calls)}"

    monkeypatch.setattr(DemService, "_fetch_real_dem", classmethod(fake_fetch_real_dem))

    first = DemService.process_dem_request(DemRequest(
        center=LatLng(lat=21.258800, lng=81.295400),
        radius_km=2.0,
        provider="opentopodata",
        dem_type="COP30",
        resolution=100,
    ))
    second = DemService.process_dem_request(DemRequest(
        center=LatLng(lat=21.259300, lng=81.295900),
        radius_km=2.0,
        provider="opentopodata",
        dem_type="COP30",
        resolution=100,
    ))

    assert len(calls) == 1
    assert first.metadata.bounds == second.metadata.bounds
    assert first.metadata.data_source == second.metadata.data_source
    assert first.elevation_matrix == second.elevation_matrix
