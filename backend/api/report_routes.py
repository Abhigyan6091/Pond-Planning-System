"""
report_routes.py
================
Generates an HTML analysis report for the Village Pond Planning System.
The report includes: location, DEM stats, catchment, rainfall, runoff,
pond depth/storage, suitability, methodology, assumptions, data sources.
"""
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/report", tags=["Report"])


class ReportRequest(BaseModel):
    village_name: str = "Selected Location"
    lat: float
    lng: float
    roi_radius_km: Optional[float] = None
    dem_stats: Optional[Dict[str, Any]] = None
    rainfall: Optional[Dict[str, Any]] = None
    catchment: Optional[Dict[str, Any]] = None
    runoff: Optional[Dict[str, Any]] = None
    recommended_site: Optional[Dict[str, Any]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    data_source: str = "OpenTopography COP30 / OpenZenith GLO-30"


@router.post("/generate", response_class=HTMLResponse)
def generate_report(request: ReportRequest):
    """
    Generates a printable HTML analysis report with all pond planning results.
    The report explicitly states it is a planning estimate and not a substitute
    for engineering or site surveys.
    """
    try:
        html = _build_report_html(request)
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


def _build_report_html(req: ReportRequest) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    dem = req.dem_stats or {}
    rf  = req.rainfall or {}
    ct  = req.catchment or {}
    ro  = req.runoff or {}
    rs  = req.recommended_site or {}

    # ── Recommended site section ─────────────────────────────────────
    rec_html = ""
    if rs:
        reasons_html = "".join(
            f"<li>{r}</li>" for r in rs.get("suitability_reasons", [])
        )
        scores = rs.get("scores", {})
        rec_html = f"""
        <section class="section">
          <h2>🎯 Recommended Pond Site</h2>
          <div class="card highlight">
            <div class="stat-grid">
              <div class="stat"><span class="label">Latitude</span><span class="value">{rs.get('lat','—')}°</span></div>
              <div class="stat"><span class="label">Longitude</span><span class="value">{rs.get('lng','—')}°</span></div>
              <div class="stat"><span class="label">Suitability Score</span><span class="value score">{rs.get('scores', {}).get('composite_score', '—')}/100</span></div>
              <div class="stat"><span class="label">Tier</span><span class="value">{rs.get('suitability_tier','—')}</span></div>
              <div class="stat"><span class="label">Elevation</span><span class="value">{rs.get('elevation_m','—')} m</span></div>
              <div class="stat"><span class="label">Avg Slope</span><span class="value">{rs.get('slope_deg','—')}°</span></div>
              <div class="stat"><span class="label">Catchment Area</span><span class="value">{rs.get('catchment_area_km2','—')} km²</span></div>
              <div class="stat"><span class="label">Est. Pond Depth</span><span class="value">{rs.get('estimated_depth_m','—')} m</span></div>
              <div class="stat"><span class="label">Est. Surface Area</span><span class="value">{rs.get('estimated_surface_area_m2','—')} m²</span></div>
              <div class="stat"><span class="label">Est. Storage Volume</span><span class="value">{rs.get('estimated_volume_m3','—')} m³</span></div>
              <div class="stat"><span class="label">Est. Annual Runoff</span><span class="value">{rs.get('estimated_runoff_m3','—')} m³</span></div>
            </div>
            <h3>Score Breakdown</h3>
            <div class="score-bars">
              {_score_bar('Slope Suitability', scores.get('slope_score',0))}
              {_score_bar('Depression Depth', scores.get('depression_score',0))}
              {_score_bar('Catchment/Flow', scores.get('catchment_score',0))}
              {_score_bar('Elevation', scores.get('elevation_score',0))}
              {_score_bar('Rainfall', scores.get('rainfall_score',0))}
            </div>
            <h3>Why This Site?</h3>
            <ul class="reasons">{reasons_html}</ul>
          </div>
        </section>"""

    # ── Rainfall section ─────────────────────────────────────────────
    rf_html = ""
    if rf and rf.get("success"):
        monthly = rf.get("monthly_avg", [])
        month_bars = ""
        if monthly:
            max_rf = max((m.get("avg_mm", 0) for m in monthly), default=1)
            for m in monthly:
                pct = int(m.get("avg_mm", 0) / max(max_rf, 0.1) * 100)
                month_bars += f"""
                <div class="month-bar">
                  <div class="bar" style="height:{pct}px" title="{m.get('month_name')}: {m.get('avg_mm')} mm"></div>
                  <span>{m.get('month_name','')[:3]}</span>
                </div>"""
        rf_html = f"""
        <section class="section">
          <h2>🌧️ Rainfall Analysis</h2>
          <p class="source">Data source: {rf.get('data_source','Open-Meteo')} | Period: {rf.get('start_year','—')}–{rf.get('end_year','—')}</p>
          <div class="stat-grid">
            <div class="stat"><span class="label">Annual Average</span><span class="value">{rf.get('annual_avg_mm','—')} mm</span></div>
            <div class="stat"><span class="label">Annual Maximum</span><span class="value">{rf.get('annual_max_mm','—')} mm</span></div>
            <div class="stat"><span class="label">Annual Minimum</span><span class="value">{rf.get('annual_min_mm','—')} mm</span></div>
            <div class="stat"><span class="label">Monsoon (Jun–Sep)</span><span class="value">{rf.get('monsoon_avg_mm','—')} mm</span></div>
            <div class="stat"><span class="label">Monsoon Fraction</span><span class="value">{round(rf.get('monsoon_fraction',0)*100,1)} %</span></div>
            <div class="stat"><span class="label">Climate Class</span><span class="value">{rf.get('rainfall_class','—')}</span></div>
          </div>
          <div class="monthly-chart">{month_bars}</div>
        </section>"""

    # ── Runoff section ────────────────────────────────────────────────
    ro_html = ""
    if ro and ro.get("success"):
        ro_html = f"""
        <section class="section">
          <h2>💧 Runoff Estimation</h2>
          <div class="formula-box">
            <strong>V = P × A × C</strong><br>
            V = {ro.get('rainfall_mm','?')} mm ÷ 1000 × {ro.get('catchment_area_m2','?')} m² × {ro.get('runoff_coefficient','?')}
            = <strong>{ro.get('runoff_volume_m3','?')} m³</strong>
          </div>
          <div class="stat-grid">
            <div class="stat"><span class="label">Rainfall Input</span><span class="value">{ro.get('rainfall_mm','—')} mm</span></div>
            <div class="stat"><span class="label">Catchment Area</span><span class="value">{ro.get('catchment_area_km2','—')} km²</span></div>
            <div class="stat"><span class="label">Runoff Coefficient (C)</span><span class="value">{ro.get('runoff_coefficient','—')}</span></div>
            <div class="stat"><span class="label">C Preset</span><span class="value">{ro.get('coefficient_label','—')}</span></div>
            <div class="stat"><span class="label">Est. Runoff Volume</span><span class="value">{ro.get('runoff_volume_m3','—')} m³</span></div>
            <div class="stat"><span class="label">Est. Runoff</span><span class="value">{ro.get('runoff_volume_million_m3','—')} million m³</span></div>
          </div>
          <p class="note">⚠ {ro.get('assumption_note','')}</p>
        </section>"""

    # ── DEM / Terrain section ─────────────────────────────────────────
    dem_html = ""
    if dem:
        dem_html = f"""
        <section class="section">
          <h2>🗺️ Terrain Analysis</h2>
          <p class="source">Elevation Source: {dem.get('data_source', req.data_source)}</p>
          <div class="stat-grid">
            <div class="stat"><span class="label">Min Elevation</span><span class="value">{dem.get('min_elevation','—')} m</span></div>
            <div class="stat"><span class="label">Max Elevation</span><span class="value">{dem.get('max_elevation','—')} m</span></div>
            <div class="stat"><span class="label">Mean Elevation</span><span class="value">{dem.get('mean_elevation','—')} m</span></div>
            <div class="stat"><span class="label">Std Deviation</span><span class="value">±{dem.get('std_elevation','—')} m</span></div>
            <div class="stat"><span class="label">DEM Resolution</span><span class="value">{dem.get('width','—')}×{dem.get('height','—')} grid</span></div>
            <div class="stat"><span class="label">Pixel Size</span><span class="value">{dem.get('pixel_size_m','—')} m</span></div>
          </div>
        </section>"""

    # ── Catchment section ─────────────────────────────────────────────
    ct_html = ""
    if ct:
        ct_html = f"""
        <section class="section">
          <h2>🌊 Catchment / Watershed Analysis</h2>
          <p class="method">Method: D8 flow direction model — upstream contributing area delineation.</p>
          <div class="stat-grid">
            <div class="stat"><span class="label">Catchment Area</span><span class="value">{ct.get('catchment_area_km2','—')} km²</span></div>
            <div class="stat"><span class="label">Catchment Area (m²)</span><span class="value">{ct.get('catchment_area_m2','—')} m²</span></div>
            <div class="stat"><span class="label">Perimeter</span><span class="value">{ct.get('perimeter_km','—')} km</span></div>
            <div class="stat"><span class="label">Avg Slope</span><span class="value">{ct.get('avg_slope_deg','—')}°</span></div>
          </div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pond Planning Report – {req.village_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; color: #1a2332; }}
  .header {{ background: linear-gradient(135deg, #0f2d5b, #1a5276); color: white; padding: 2rem 3rem; }}
  .header h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .header .subtitle {{ opacity: 0.75; font-size: 0.9rem; }}
  .header .meta {{ margin-top: 1rem; display: flex; gap: 2rem; font-size: 0.85rem; opacity: 0.9; }}
  .warning {{ background: #fff3cd; border-left: 5px solid #f39c12; padding: 1rem 1.5rem; margin: 1.5rem 3rem; border-radius: 6px; font-size: 0.9rem; color: #7d6608; }}
  .section {{ background: white; margin: 1.5rem 3rem; border-radius: 12px; padding: 1.5rem 2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .section h2 {{ font-size: 1.2rem; color: #0f2d5b; border-bottom: 2px solid #e8f0fe; padding-bottom: 0.5rem; margin-bottom: 1rem; }}
  .section h3 {{ font-size: 1rem; color: #1a5276; margin: 1rem 0 0.5rem; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; margin: 0.75rem 0; }}
  .stat {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; }}
  .stat .label {{ display: block; font-size: 0.75rem; text-transform: uppercase; color: #64748b; margin-bottom: 0.25rem; letter-spacing: 0.05em; }}
  .stat .value {{ font-size: 1.05rem; font-weight: 600; color: #1e3a5f; }}
  .stat .value.score {{ color: #16a34a; font-size: 1.3rem; }}
  .card.highlight {{ border: 2px solid #1a5276; border-radius: 10px; padding: 1.25rem; background: #f0f7ff; }}
  .source {{ font-size: 0.8rem; color: #64748b; margin-bottom: 0.75rem; font-style: italic; }}
  .method {{ font-size: 0.82rem; color: #475569; margin-bottom: 0.75rem; }}
  .formula-box {{ background: #e8f4fd; border: 1px solid #93c5fd; border-radius: 8px; padding: 0.75rem 1.25rem; margin-bottom: 1rem; font-family: monospace; font-size: 0.95rem; color: #1e3a5f; }}
  .note {{ font-size: 0.8rem; color: #92400e; background: #fef3c7; border-radius: 6px; padding: 0.5rem 0.75rem; margin-top: 0.75rem; }}
  .reasons {{ list-style: none; padding-left: 0; }}
  .reasons li {{ padding: 0.35rem 0; font-size: 0.9rem; }}
  .score-bars {{ display: flex; flex-direction: column; gap: 0.5rem; margin: 0.75rem 0; }}
  .score-bar-row {{ display: flex; align-items: center; gap: 0.75rem; font-size: 0.82rem; }}
  .score-bar-row .bar-label {{ width: 150px; color: #475569; }}
  .score-bar-container {{ flex: 1; background: #e2e8f0; border-radius: 999px; height: 10px; }}
  .score-bar-fill {{ height: 10px; border-radius: 999px; background: linear-gradient(90deg, #3b82f6, #10b981); }}
  .score-bar-val {{ width: 45px; text-align: right; color: #1e3a5f; font-weight: 600; }}
  .monthly-chart {{ display: flex; align-items: flex-end; gap: 6px; height: 120px; margin-top: 1rem; padding: 0 0.5rem; }}
  .month-bar {{ display: flex; flex-direction: column; align-items: center; gap: 3px; flex: 1; }}
  .month-bar .bar {{ width: 100%; background: linear-gradient(to top, #3b82f6, #93c5fd); border-radius: 4px 4px 0 0; min-height: 2px; }}
  .month-bar span {{ font-size: 0.65rem; color: #64748b; }}
  .footer {{ text-align: center; padding: 2rem; font-size: 0.8rem; color: #94a3b8; }}
  @media print {{
    body {{ background: white; }}
    .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .warning {{ break-inside: avoid; }}
    .section {{ break-inside: avoid; box-shadow: none; border: 1px solid #e2e8f0; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>🛰️ Village Pond Planning Report</h1>
  <p class="subtitle">AI/GIS-Based Village Pond Planning System — Terrain Analysis Results</p>
  <div class="meta">
    <span>📍 Location: <strong>{req.village_name}</strong></span>
    <span>🌐 Coordinates: <strong>{req.lat:.4f}°N, {req.lng:.4f}°E</strong></span>
    <span>🗓️ Generated: <strong>{ts}</strong></span>
  </div>
</div>

<div class="warning">
  ⚠️ <strong>Important Disclaimer:</strong> All results in this report are <strong>planning-level estimates</strong>
  based on publicly available DEM and rainfall data. They are NOT a substitute for field surveys,
  geotechnical investigation, hydrological modelling, or engineering design.
  The estimated pond depth, volume, and runoff figures require site-specific verification before use in design.
</div>

{dem_html}
{rf_html}
{ct_html}
{ro_html}
{rec_html}

<section class="section">
  <h2>📐 Methodology & Assumptions</h2>
  <ul style="line-height:1.8; font-size:0.9rem; padding-left:1.25rem;">
    <li><strong>Elevation data:</strong> {req.data_source} — 30m resolution global DEM</li>
    <li><strong>Contours:</strong> Marching Squares algorithm on DEM grid</li>
    <li><strong>Flow direction:</strong> D8 steepest-descent algorithm on filled DEM</li>
    <li><strong>Catchment delineation:</strong> Reverse BFS on D8 flow pointers from outlet cell</li>
    <li><strong>Depression detection:</strong> Priority-Flood (Wang & Liu 2006) sink-fill algorithm</li>
    <li><strong>Suitability scoring:</strong> Weighted composite of slope, depression, catchment, elevation, rainfall (each normalised 0–1)</li>
    <li><strong>Runoff estimation:</strong> Rational Method V = P × A × C. Coefficient C is an approximate land-use default</li>
    <li><strong>Rainfall data:</strong> Open-Meteo Archive API — 9 km ERA5 reanalysis, free open-source</li>
    <li><strong>Physical distances:</strong> Haversine geodesic formula; areas use local planar projection</li>
  </ul>
</section>

<section class="section">
  <h2>📚 Data Sources</h2>
  <ul style="line-height:1.9; font-size:0.9rem; padding-left:1.25rem;">
    <li>Elevation: OpenTopography COP30 (Copernicus 30m) / OpenZenith GLO-30 — <a href="https://opentopography.org">opentopography.org</a></li>
    <li>Rainfall: Open-Meteo Archive API — <a href="https://open-meteo.com">open-meteo.com</a></li>
    <li>Base map: OpenStreetMap contributors — <a href="https://openstreetmap.org">openstreetmap.org</a></li>
    <li>Satellite imagery: ESRI World Imagery — <a href="https://esri.com">esri.com</a></li>
    <li>Geocoding: Nominatim / OpenStreetMap</li>
  </ul>
</section>

<div class="footer">
  Generated by Village Pond Planning System &bull; Academic Planning Tool &bull; {ts}<br>
  <em>This report is for planning purposes only. All results require field verification.</em>
</div>

</body>
</html>"""


def _score_bar(label: str, value: float) -> str:
    pct = max(0, min(100, int(value * 100)))
    return f"""
    <div class="score-bar-row">
      <span class="bar-label">{label}</span>
      <div class="score-bar-container">
        <div class="score-bar-fill" style="width:{pct}%"></div>
      </div>
      <span class="score-bar-val">{pct}%</span>
    </div>"""
