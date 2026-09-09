import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.models.dem_models import DemRequest, LatLng
from backend.services.dem_service import DemService


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
