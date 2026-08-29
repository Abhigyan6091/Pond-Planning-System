"""
contour_parser_service.py
=========================
Parses KML and KMZ files into a list of ParsedContour objects.

Design principles
-----------------
- Generalised: works with any KML file, not just the sample.
- No hard-coded coordinates, elevation ranges, or contour counts.
- Elevation extraction supports multiple common KML encoding patterns:
    1. Placemark <name> (float string) — used by sample contours_1m.kml
    2. ExtendedData/SimpleData[@name contains 'elev'|'alt'|'height'|'z']
    3. LookAt/Point altitude
    4. coordinate Z-value (lon,lat,alt triplets)
- KMZ handled by extracting the contained doc.kml / first .kml member.
- XML parsed with Python's stdlib xml.etree.ElementTree (safe, no shell).

The parser is intentionally forgiving: it skips Placemarks without
recoverable elevation but accumulates all that it can parse. Validation
happens afterwards in ContourParserService.validate().

KML Namespace note
------------------
The sample file opens with:
    <Folder xmlns="http://www.opengis.net/kml/2.2" ...>
so the default namespace is always stripped / handled via Clark notation.
"""
from __future__ import annotations

import io
import math
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

from backend.models.contour_analysis_models import ParsedContour, ContourParseResult

# KML namespace URIs we accept
_KML_NAMESPACES = [
    "http://www.opengis.net/kml/2.2",
    "http://earth.google.com/kml/2.1",
    "http://earth.google.com/kml/2.2",
    "",          # no namespace
]


def _ns(tag: str, namespace: str) -> str:
    """Return Clark-notation tag string for an XML namespace."""
    if namespace:
        return f"{{{namespace}}}{tag}"
    return tag


def _find_all_ns(element: ET.Element, tag: str) -> List[ET.Element]:
    """Find all descendants with `tag` across all candidate namespaces."""
    results: List[ET.Element] = []
    for ns in _KML_NAMESPACES:
        results.extend(element.iter(_ns(tag, ns)))
    # Deduplicate by identity (same element may appear for empty namespace)
    seen = set()
    unique = []
    for el in results:
        eid = id(el)
        if eid not in seen:
            seen.add(eid)
            unique.append(el)
    return unique


def _parse_coordinates(coord_text: str) -> List[Tuple[float, float]]:
    """
    Parse a KML <coordinates> text string.

    KML coordinate format: "lon,lat[,alt] lon,lat[,alt] …"
    Returns list of (lon, lat) tuples, ignoring altitude.
    Tolerates whitespace variations.
    """
    coords: List[Tuple[float, float]] = []
    for token in coord_text.split():
        parts = token.strip().split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    coords.append((lon, lat))
            except ValueError:
                continue
    return coords


def _extract_elevation_from_placemark(
    placemark: ET.Element,
    ls_element: Optional[ET.Element] = None,
) -> Optional[float]:
    """
    Attempt to extract a numeric elevation (metres) from a KML Placemark
    representing a contour LineString.

    Priority order:
    1. <name> — most common pattern (e.g. "277.0")
    2. ExtendedData / SchemaData / SimpleData[@name in elev|alt|height|z|elev*]
    3. Any SimpleData text that is purely numeric
    4. Coordinate altitude (Z component) from the LineString coordinates

    Returns None if no elevation can be determined.
    """
    # --- 1. <name> ---
    for name_el in _find_all_ns(placemark, "name"):
        if name_el.text:
            text = name_el.text.strip()
            try:
                val = float(text)
                if -500 <= val <= 9000:       # plausible Earth elevation range
                    return val
            except ValueError:
                pass

    # --- 2. ExtendedData / SimpleData ---
    elev_keywords = {"elev", "elevation", "alt", "altitude", "height", "z", "h"}
    for sd in _find_all_ns(placemark, "SimpleData"):
        attr_name = (sd.get("name") or "").lower()
        text = (sd.text or "").strip()
        if any(kw in attr_name for kw in elev_keywords) and text:
            try:
                val = float(text)
                if -500 <= val <= 9000:
                    return val
            except ValueError:
                pass

    # --- 3. Any purely numeric SimpleData (last resort) ---
    for sd in _find_all_ns(placemark, "SimpleData"):
        text = (sd.text or "").strip()
        try:
            val = float(text)
            if -500 <= val <= 9000:
                return val
        except ValueError:
            continue

    # --- 4. Z-component of first coordinate from LineString ---
    target_elements = [ls_element] if ls_element is not None else _find_all_ns(placemark, "LineString")
    for ls in target_elements:
        for coord_el in _find_all_ns(ls, "coordinates"):
            text = (coord_el.text or "").strip()
            first_token = text.split()[0] if text else ""
            parts = first_token.split(",")
            if len(parts) >= 3:
                try:
                    z = float(parts[2])
                    if -500 <= z <= 9000:
                        return z
                except ValueError:
                    pass

    return None


def _parse_kml_element(root: ET.Element) -> List[ParsedContour]:
    """
    Walk a KML element tree and extract contour LineStrings.
    Point and Polygon placemarks are excluded from contour lines.
    """
    contours: List[ParsedContour] = []

    for placemark in _find_all_ns(root, "Placemark"):
        # Contours are represented by LineString features
        linestrings = _find_all_ns(placemark, "LineString")
        if not linestrings:
            continue

        for ls in linestrings:
            elevation = _extract_elevation_from_placemark(placemark, ls_element=ls)
            if elevation is None:
                continue

            for coord_el in _find_all_ns(ls, "coordinates"):
                coords = _parse_coordinates(coord_el.text or "")
                if len(coords) < 2:
                    continue
                is_closed = (
                    len(coords) >= 3
                    and abs(coords[0][0] - coords[-1][0]) < 1e-8
                    and abs(coords[0][1] - coords[-1][1]) < 1e-8
                )
                contours.append(ParsedContour(
                    elevation_m=elevation,
                    coordinates=coords,
                    is_closed=is_closed,
                ))

    return contours


class ContourParserService:
    """
    Parses KML and KMZ byte content into validated ParsedContour lists.
    """

    # Minimum number of contours required to attempt terrain reconstruction
    MIN_CONTOURS = 3
    MIN_UNIQUE_ELEVATIONS = 2

    @classmethod
    def extract_kml_from_kmz(cls, kmz_bytes: bytes) -> bytes:
        """
        Extract the primary KML document from a KMZ (ZIP) archive.

        Raises ValueError for corrupt or empty archives.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as zf:
                # Prefer doc.kml, then the first .kml member
                names = zf.namelist()
                kml_names = [n for n in names if n.lower().endswith(".kml")]
                if not kml_names:
                    raise ValueError(
                        "KMZ archive contains no .kml files. "
                        f"Found members: {names[:10]}"
                    )
                # doc.kml is the canonical name; fall back to first .kml
                target = "doc.kml" if "doc.kml" in kml_names else kml_names[0]
                return zf.read(target)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"KMZ file is not a valid ZIP archive: {exc}") from exc

    @classmethod
    def parse_kml_bytes(cls, kml_bytes: bytes) -> ContourParseResult:
        """
        Parse raw KML bytes into a ContourParseResult.

        This method:
        1. Parses XML safely.
        2. Extracts all LineString Placemarks with recoverable elevation.
        3. Computes metadata (count, elevation range, interval, bounds).
        4. Returns structured result with any errors.
        """
        # --- XML Parsing ---
        try:
            root = ET.fromstring(kml_bytes)
        except ET.ParseError as exc:
            return ContourParseResult(
                success=False,
                error_message=f"Malformed KML XML: {exc}",
            )

        # --- Contour Extraction ---
        try:
            contours = _parse_kml_element(root)
        except Exception as exc:  # pragma: no cover
            return ContourParseResult(
                success=False,
                error_message=f"KML parsing error: {exc}",
            )

        if not contours:
            return ContourParseResult(
                success=False,
                error_message=(
                    "No contour LineStrings with recoverable elevation found in KML. "
                    "Ensure Placemarks have elevation in <name>, ExtendedData, or Z-coordinates."
                ),
            )

        # --- Metadata ---
        elevations = [c.elevation_m for c in contours]
        unique_elevs = sorted(set(elevations))

        # Approximate contour interval = median gap between consecutive unique levels
        gaps = [unique_elevs[i+1] - unique_elevs[i] for i in range(len(unique_elevs)-1)]
        interval = float(sorted(gaps)[len(gaps) // 2]) if gaps else 0.0

        all_lons = [lon for c in contours for lon, lat in c.coordinates]
        all_lats = [lat for c in contours for lon, lat in c.coordinates]

        bounds = {
            "min_lat": float(min(all_lats)),
            "max_lat": float(max(all_lats)),
            "min_lon": float(min(all_lons)),
            "max_lon": float(max(all_lons)),
        }

        return ContourParseResult(
            success=True,
            contours=contours,
            contour_count=len(contours),
            unique_elevations=unique_elevs,
            elevation_min_m=float(min(elevations)),
            elevation_max_m=float(max(elevations)),
            contour_interval_m=interval,
            bounds=bounds,
        )

    @classmethod
    def validate(cls, result: ContourParseResult) -> Optional[str]:
        """
        Validate a ContourParseResult after parsing.

        Returns None if valid, or a human-readable error string.
        """
        if not result.success:
            return result.error_message

        if result.contour_count < cls.MIN_CONTOURS:
            return (
                f"Too few contours ({result.contour_count}). "
                f"At least {cls.MIN_CONTOURS} are required for terrain reconstruction."
            )

        unique_count = len(result.unique_elevations)
        if unique_count < cls.MIN_UNIQUE_ELEVATIONS:
            return (
                f"Only {unique_count} unique elevation level(s) found. "
                f"At least {cls.MIN_UNIQUE_ELEVATIONS} distinct elevations are required."
            )

        if result.bounds:
            lat_span = result.bounds["max_lat"] - result.bounds["min_lat"]
            lon_span = result.bounds["max_lon"] - result.bounds["min_lon"]
            if lat_span < 1e-6 or lon_span < 1e-6:
                return (
                    "Contours have negligible spatial extent "
                    f"(Δlat={lat_span:.8f}°, Δlon={lon_span:.8f}°). "
                    "Data may be degenerate."
                )

        # Validate individual contours
        for i, c in enumerate(result.contours):
            if len(c.coordinates) < 2:
                return f"Contour {i} (elevation {c.elevation_m}m) has fewer than 2 coordinates."
            if not math.isfinite(c.elevation_m):
                return f"Contour {i} has non-finite elevation: {c.elevation_m}"

        return None  # all OK
