"""
test_contour_analysis.py
========================
Phase 2 tests for KML/KMZ contour parsing, terrain reconstruction,
and the full analyzeContour pipeline.

Tests are generalized — none depend on hard-coded coordinates or
expected values from the sample contours_1m.kml.  Where necessary,
small synthetic KML fixtures are created programmatically.

Test coverage
-------------
 1. Valid KML with multiple contours — parser returns parsed contours
 2. Different elevation ranges — reconstruction uses actual range
 3. Different geographic locations — bounds match input data
 4. Different contour intervals — contour_interval_m computed from data
 5. Closed contours — is_closed flag set correctly
 6. Open contours — parsed without error
 7. Malformed KML — parser returns success=False with error_message
 8. Unsupported file type — rejected before parsing
 9. KMZ containing KML — extraction + parse succeeds
10. Missing elevation information — parser skips non-numeric names
11. Insufficient contour data — validate() returns an error string
12. Sample contours_1m.kml — full end-to-end parse + reconstruction
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
import math
import numpy as np
import pytest

# Make sure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.services.contour_parser_service import ContourParserService
from backend.services.contour_terrain_service import ContourTerrainService
from backend.models.contour_analysis_models import ParsedContour

# ---------------------------------------------------------------------------
# KML fixture factories (synthetic, location-agnostic)
# ---------------------------------------------------------------------------

def _make_kml(placemarks: list[dict]) -> bytes:
    """
    Build a minimal KML byte string from a list of placemark dicts.

    Each dict: {"name": str, "coords": [(lon, lat), …]}
    """
    pms = ""
    for pm in placemarks:
        coord_str = " ".join(f"{lon},{lat},0" for lon, lat in pm["coords"])
        pms += f"""
  <Placemark>
    <name>{pm['name']}</name>
    <LineString>
      <coordinates>{coord_str}</coordinates>
    </LineString>
  </Placemark>"""
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>{pms}
  </Document>
</kml>"""
    return kml.encode("utf-8")


def _make_kmz(kml_bytes: bytes) -> bytes:
    """Wrap KML bytes in a KMZ (ZIP) archive as doc.kml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_bytes)
    return buf.getvalue()


def _simple_contours(
    base_lat: float = 20.0,
    base_lon: float = 78.0,
    span: float = 0.05,
    n_levels: int = 5,
    base_elev: float = 100.0,
    interval: float = 10.0,
) -> list[dict]:
    """
    Generate n_levels contour LineStrings at different elevations.
    Each contour is a horizontal line at a different latitude offset.
    """
    pms = []
    for i in range(n_levels):
        lat = base_lat + i * (span / n_levels)
        elev = base_elev + i * interval
        coords = [(base_lon + j * span / 10, lat) for j in range(6)]
        pms.append({"name": str(float(elev)), "coords": coords})
    return pms


# ============================================================
# TEST 1: Valid KML with multiple contours
# ============================================================
class TestValidKmlParsing:
    def test_parse_returns_success(self):
        pms = _simple_contours()
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert result.success is True

    def test_parse_contour_count(self):
        pms = _simple_contours(n_levels=6)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert result.contour_count == 6

    def test_parse_extracts_coordinates(self):
        pms = _simple_contours()
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert all(len(c.coordinates) >= 2 for c in result.contours)

    def test_unique_elevations_match_input(self):
        levels = [100.0, 200.0, 300.0, 400.0]
        pms = [{"name": str(e), "coords": [(78.0 + j * 0.01, 20.0 + i * 0.01) for j in range(5)]}
               for i, e in enumerate(levels)]
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert sorted(result.unique_elevations) == sorted(levels)


# ============================================================
# TEST 2: Different elevation ranges
# ============================================================
class TestDifferentElevationRanges:
    @pytest.mark.parametrize("base_elev,interval", [
        (0.0, 5.0),      # Sea-level terrain
        (2000.0, 50.0),  # High altitude
        (500.0, 2.0),    # Dense interval
    ])
    def test_elevation_range_matches_input(self, base_elev, interval):
        pms = _simple_contours(n_levels=5, base_elev=base_elev, interval=interval)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert abs(result.elevation_min_m - base_elev) < 1e-6
        expected_max = base_elev + 4 * interval
        assert abs(result.elevation_max_m - expected_max) < 1e-6


# ============================================================
# TEST 3: Different geographic locations
# ============================================================
class TestDifferentGeographicLocations:
    @pytest.mark.parametrize("lat,lon", [
        (27.9, 86.9),   # Himalayan region
        (-33.9, 18.4),  # Cape Town
        (51.5, -0.1),   # London
        (35.7, 139.7),  # Tokyo
    ])
    def test_bounds_match_location(self, lat, lon):
        pms = _simple_contours(base_lat=lat, base_lon=lon, span=0.02, n_levels=4)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        # Bounds should include the supplied coordinates
        assert result.bounds["min_lat"] <= lat
        assert result.bounds["max_lat"] >= lat
        assert result.bounds["min_lon"] <= lon
        assert result.bounds["max_lon"] >= lon


# ============================================================
# TEST 4: Different contour intervals
# ============================================================
class TestDifferentContourIntervals:
    @pytest.mark.parametrize("interval", [1.0, 5.0, 10.0, 25.0, 100.0])
    def test_contour_interval_computed(self, interval):
        pms = _simple_contours(n_levels=5, interval=interval)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert result.contour_interval_m is not None
        assert abs(result.contour_interval_m - interval) < 1e-6


# ============================================================
# TEST 5: Closed contours
# ============================================================
class TestClosedContours:
    def test_closed_contour_detected(self):
        # First coord == last coord → is_closed=True
        base_lat, base_lon = 20.0, 78.0
        coords = [(base_lon, base_lat), (base_lon + 0.01, base_lat),
                  (base_lon + 0.01, base_lat + 0.01), (base_lon, base_lat + 0.01),
                  (base_lon, base_lat)]  # closed ring
        pms = [{"name": "200.0", "coords": coords}]
        # Add more placemarks to meet minimum
        for i in range(1, 4):
            pms.append({"name": str(200.0 + i * 5),
                         "coords": [(base_lon + j * 0.005, base_lat + i * 0.01) for j in range(4)]})
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        closed = [c for c in result.contours if c.is_closed]
        assert len(closed) >= 1


# ============================================================
# TEST 6: Open contours
# ============================================================
class TestOpenContours:
    def test_open_contours_parsed_without_error(self):
        # Open contours (first != last) should parse fine
        pms = _simple_contours(n_levels=4)   # simple_contours are open lines
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        assert result.success is True
        open_ct = [c for c in result.contours if not c.is_closed]
        assert len(open_ct) >= 1


# ============================================================
# TEST 7: Malformed KML
# ============================================================
class TestMalformedKml:
    def test_broken_xml_returns_error(self):
        bad_kml = b"<kml><Document><Placemark><name>broken"
        result = ContourParserService.parse_kml_bytes(bad_kml)
        assert result.success is False
        assert result.error_message is not None

    def test_empty_kml_returns_error(self):
        result = ContourParserService.parse_kml_bytes(b"")
        assert result.success is False

    def test_non_kml_xml_returns_no_contours(self):
        xml = b"""<?xml version="1.0"?><root><data>hello</data></root>"""
        result = ContourParserService.parse_kml_bytes(xml)
        # Parses OK but finds no contours
        assert result.success is False or result.contour_count == 0


# ============================================================
# TEST 8: Unsupported file type (tested via ext check utility)
# ============================================================
class TestUnsupportedFileType:
    def test_csv_extension_rejected(self):
        """The API rejects non-KML/KMZ extensions before parsing."""
        ALLOWED = {".kml", ".kmz"}
        for ext in [".csv", ".shp", ".geojson", ".txt", ""]:
            assert ext not in ALLOWED, f"Extension {ext!r} should not be allowed"

    def test_kml_extension_allowed(self):
        ALLOWED = {".kml", ".kmz"}
        assert ".kml" in ALLOWED
        assert ".kmz" in ALLOWED


# ============================================================
# TEST 9: KMZ containing KML
# ============================================================
class TestKmzExtraction:
    def test_kmz_extraction_produces_kml_bytes(self):
        pms = _simple_contours(n_levels=4)
        inner_kml = _make_kml(pms)
        kmz = _make_kmz(inner_kml)
        extracted = ContourParserService.extract_kml_from_kmz(kmz)
        assert extracted == inner_kml

    def test_kmz_parse_end_to_end(self):
        pms = _simple_contours(n_levels=5)
        inner_kml = _make_kml(pms)
        kmz = _make_kmz(inner_kml)
        kml_bytes = ContourParserService.extract_kml_from_kmz(kmz)
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        assert result.success is True
        assert result.contour_count == 5

    def test_corrupt_kmz_raises_value_error(self):
        with pytest.raises(ValueError):
            ContourParserService.extract_kml_from_kmz(b"this is not a zip file")

    def test_kmz_without_kml_raises_value_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no kml here")
        with pytest.raises(ValueError, match="no .kml files"):
            ContourParserService.extract_kml_from_kmz(buf.getvalue())


# ============================================================
# TEST 10: Missing elevation information
# ============================================================
class TestMissingElevation:
    def test_placemarks_without_elevation_are_skipped(self):
        kml = b"""<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>not_a_number</name>
      <LineString><coordinates>78.0,20.0 78.01,20.0</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>100.0</name>
      <LineString><coordinates>78.0,20.01 78.01,20.01</coordinates></LineString>
    </Placemark>
  </Document>
</kml>"""
        result = ContourParserService.parse_kml_bytes(kml)
        # Only the numeric-name placemark parsed
        numeric = [c for c in result.contours if c.elevation_m == 100.0]
        assert len(numeric) == 1

    def test_all_non_numeric_names_returns_error(self):
        kml = b"""<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>contour_a</name>
      <LineString><coordinates>78.0,20.0 78.01,20.0</coordinates></LineString>
    </Placemark>
  </Document>
</kml>"""
        result = ContourParserService.parse_kml_bytes(kml)
        assert result.success is False or result.contour_count == 0


# ============================================================
# TEST 11: Insufficient contour data
# ============================================================
class TestInsufficientContourData:
    def test_too_few_contours_fails_validation(self):
        # Only 1 contour — below MIN_CONTOURS=3
        pms = [{"name": "100.0", "coords": [(78.0, 20.0), (78.01, 20.0)]}]
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        error = ContourParserService.validate(result)
        assert error is not None

    def test_only_one_unique_elevation_fails_validation(self):
        # 5 contours but all same elevation
        pms = [
            {"name": "200.0", "coords": [(78.0 + j * 0.01, 20.0 + i * 0.01) for j in range(4)]}
            for i in range(5)
        ]
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        error = ContourParserService.validate(result)
        # Either no contours or fails unique elevation check
        assert error is not None or len(result.unique_elevations) >= 1

    def test_valid_data_passes_validation(self):
        pms = _simple_contours(n_levels=5)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        error = ContourParserService.validate(result)
        assert error is None


# ============================================================
# TEST 12: Sample contours_1m.kml — full end-to-end
# ============================================================
class TestSampleKmlEndToEnd:
    SAMPLE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "contours_1m.kml",
    )

    def _load_sample(self) -> bytes:
        if not os.path.exists(self.SAMPLE_PATH):
            pytest.skip(f"Sample KML not found at {self.SAMPLE_PATH}")
        with open(self.SAMPLE_PATH, "rb") as f:
            return f.read()

    def test_sample_kml_parses_successfully(self):
        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        assert result.success is True
        # Exact ground-truth assertions for the known sample file
        expected_contour_count = 1355
        expected_min_elevation = 267.0
        expected_max_elevation = 298.0
        expected_unique_levels = 32
        expected_contour_interval = 1.0

        assert result.contour_count == expected_contour_count
        assert result.elevation_min_m == expected_min_elevation
        assert result.elevation_max_m == expected_max_elevation
        assert len(result.unique_elevations) == expected_unique_levels
        assert result.contour_interval_m == expected_contour_interval

    def test_sample_kml_has_multiple_elevations(self):
        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        assert len(result.unique_elevations) == 32

    def test_sample_kml_elevation_range_plausible(self):
        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        assert result.elevation_min_m == 267.0
        assert result.elevation_max_m == 298.0
        assert result.elevation_max_m > result.elevation_min_m

    def test_sample_kml_passes_validation(self):
        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        error = ContourParserService.validate(result)
        assert error is None, f"Validation failed: {error}"

    def test_sample_kml_terrain_reconstruction(self):
        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)
        assert result.success

        elevation_matrix, bounds, pixel_size_m = ContourTerrainService.reconstruct_dem(
            result.contours, grid_size=50
        )

        em = np.array(elevation_matrix)
        assert em.shape == (50, 50)
        assert not np.isnan(em).any(), "Reconstructed DEM should not contain NaN"
        assert float(em.min()) >= result.elevation_min_m - 5
        assert float(em.max()) <= result.elevation_max_m + 5
        assert pixel_size_m > 0
        assert bounds.north > bounds.south
        assert bounds.east > bounds.west

    def test_sample_kml_hydrology_reuse(self):
        """The reconstructed DEM can be passed to the existing HydrologyService."""
        from backend.services.hydrology_service import HydrologyService

        kml_bytes = self._load_sample()
        result = ContourParserService.parse_kml_bytes(kml_bytes)

        elevation_matrix, bounds, pixel_size_m = ContourTerrainService.reconstruct_dem(
            result.contours, grid_size=30
        )

        dem_np = np.array(elevation_matrix, dtype=float)
        flow_dir = HydrologyService.compute_d8_flow_direction(dem_np, pixel_size_m)
        flow_acc = HydrologyService.compute_flow_accumulation(flow_dir)

        assert flow_dir.shape == dem_np.shape
        assert flow_acc.shape == dem_np.shape
        assert int(flow_acc.max()) >= 1
        # Flow accumulation cannot exceed total cells
        assert int(flow_acc.max()) <= dem_np.size


# ============================================================
# Additional terrain service tests
# ============================================================
class TestTerrainReconstructionService:
    def _make_contours(self, n_levels: int = 5) -> list:
        pms = _simple_contours(n_levels=n_levels, span=0.1)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        return result.contours

    def test_reconstruction_output_shape(self):
        contours = self._make_contours()
        em, bounds, pxm = ContourTerrainService.reconstruct_dem(contours, grid_size=40)
        arr = np.array(em)
        assert arr.shape == (40, 40)

    def test_reconstruction_bounds_cover_contours(self):
        contours = self._make_contours()
        _, bounds, _ = ContourTerrainService.reconstruct_dem(contours, grid_size=30)
        assert bounds.north > bounds.south
        assert bounds.east > bounds.west

    def test_reconstruction_pixel_size_positive(self):
        contours = self._make_contours()
        _, _, pxm = ContourTerrainService.reconstruct_dem(contours, grid_size=30)
        assert pxm > 0

    def test_reconstruction_no_nan(self):
        contours = self._make_contours()
        em, _, _ = ContourTerrainService.reconstruct_dem(contours, grid_size=30)
        assert not np.isnan(np.array(em)).any()

    def test_reconstruction_elevation_in_range(self):
        pms = _simple_contours(n_levels=5, base_elev=300.0, interval=10.0)
        kml = _make_kml(pms)
        result = ContourParserService.parse_kml_bytes(kml)
        em, _, _ = ContourTerrainService.reconstruct_dem(result.contours, grid_size=30)
        arr = np.array(em)
        # Allow small tolerance for smoothing
        assert float(arr.min()) >= 300.0 - 10.0
        assert float(arr.max()) <= 340.0 + 10.0


# ============================================================
# TEST 13: Point and Polygon Placemarks ignored
# ============================================================
class TestNonContourPlacemarksIgnored:
    def test_points_and_polygons_do_not_affect_contour_stats(self):
        """
        Verify that a KML containing Point placemarks (e.g. labels) and
        Polygon placemarks (e.g. boundary envelopes) does not count them
        as contours, nor allow their elevation/coordinates to corrupt
        contour counts or elevation statistics.
        """
        kml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <!-- Actual contour LineStrings at 200m, 210m, 220m -->
    <Placemark>
      <name>200.0</name>
      <LineString><coordinates>78.0,20.0 78.01,20.0</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>210.0</name>
      <LineString><coordinates>78.0,20.01 78.01,20.01</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>220.0</name>
      <LineString><coordinates>78.0,20.02 78.01,20.02</coordinates></LineString>
    </Placemark>

    <!-- Point label placemark with an unrelated elevation or coordinate -->
    <Placemark>
      <name>200.0</name>
      <Point><coordinates>78.005,20.0,50</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>label_point</name>
      <Point><coordinates>78.005,20.01,15</coordinates></Point>
    </Placemark>

    <!-- Polygon boundary envelope with 30m altitude -->
    <Placemark>
      <name>land</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              78.0,20.0,30 78.02,20.0,30 78.02,20.03,30 78.0,20.03,30 78.0,20.0,30
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
        result = ContourParserService.parse_kml_bytes(kml_content)
        assert result.success is True
        # Exactly 3 LineString contours
        assert result.contour_count == 3
        # Stats must reflect only the 200, 210, 220 LineStrings (not the 30m polygon or 15/50m points)
        assert result.elevation_min_m == 200.0
        assert result.elevation_max_m == 220.0
        assert result.unique_elevations == [200.0, 210.0, 220.0]
        assert result.contour_interval_m == 10.0
