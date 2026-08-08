"""
rainfall_service.py
===================
Fetches and summarizes historical rainfall data from the Open-Meteo
Archive API (free, no API key required).

API: https://archive-api.open-meteo.com/v1/archive
Variables: daily precipitation_sum (mm)

Usage example:
    RainfallService.fetch_rainfall(lat=23.5, lng=72.6, start_year=2014, end_year=2023)

Data source credit: Open-Meteo.com – Open-source weather API
"""
import math
import calendar
import requests
from datetime import date
from typing import List, Optional

from backend.models.rainfall_models import (
    RainfallRequest, RainfallResponse,
    MonthlyRainfall, RainfallTimeSeries,
)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
TIMEOUT_S = 20


def _classify_rainfall(annual_mm: float) -> str:
    """Classify annual rainfall into climate aridity classes."""
    if annual_mm < 250:
        return "Arid"
    elif annual_mm < 500:
        return "Semi-Arid"
    elif annual_mm < 750:
        return "Sub-Humid"
    elif annual_mm < 1500:
        return "Humid"
    else:
        return "Very Humid"


class RainfallService:

    @classmethod
    def fetch_rainfall(cls, request: RainfallRequest) -> RainfallResponse:
        """
        Query Open-Meteo Archive API for daily precipitation and aggregate
        into annual, monthly, and seasonal statistics.
        """
        start_year = max(1950, min(request.start_year, date.today().year - 1))
        end_year   = max(start_year, min(request.end_year, date.today().year - 1))

        start_date = f"{start_year}-01-01"
        end_date   = f"{end_year}-12-31"

        params = {
            "latitude":  f"{request.lat:.6f}",
            "longitude": f"{request.lng:.6f}",
            "start_date": start_date,
            "end_date":   end_date,
            "daily":      "precipitation_sum",
            "timezone":   "auto",
        }

        try:
            r = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=TIMEOUT_S)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            # Return a descriptive error response rather than raising
            return RainfallResponse(
                success=False,
                message=f"Rainfall API unavailable: {str(e)}",
                lat=request.lat,
                lng=request.lng,
                start_year=start_year,
                end_year=end_year,
                annual_avg_mm=0.0,
                annual_max_mm=0.0,
                annual_min_mm=0.0,
                monsoon_avg_mm=0.0,
                monsoon_fraction=0.0,
                monthly_avg=[],
                yearly_totals=[],
                max_rainfall_year=start_year,
                rainfall_class="Unknown",
            )

        daily = data.get("daily", {})
        times  = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])

        if not times or not precip:
            return RainfallResponse(
                success=False,
                message="Open-Meteo returned empty precipitation data for this location.",
                lat=request.lat,
                lng=request.lng,
                start_year=start_year,
                end_year=end_year,
                annual_avg_mm=0.0,
                annual_max_mm=0.0,
                annual_min_mm=0.0,
                monsoon_avg_mm=0.0,
                monsoon_fraction=0.0,
                monthly_avg=[],
                yearly_totals=[],
                max_rainfall_year=start_year,
                rainfall_class="Unknown",
            )

        # ── Accumulate by year and month ──────────────────────────────────
        monthly_totals: dict = {}   # (year, month) → total_mm
        yearly_totals:  dict = {}   # year → total_mm

        for t, p in zip(times, precip):
            if p is None:
                continue
            try:
                parts = t.split("-")
                yr = int(parts[0])
                mo = int(parts[1])
            except (ValueError, IndexError):
                continue

            yearly_totals[yr] = yearly_totals.get(yr, 0.0) + float(p)
            key = (yr, mo)
            monthly_totals[key] = monthly_totals.get(key, 0.0) + float(p)

        if not yearly_totals:
            return RainfallResponse(
                success=False,
                message="No valid precipitation records found in the requested period.",
                lat=request.lat,
                lng=request.lng,
                start_year=start_year,
                end_year=end_year,
                annual_avg_mm=0.0,
                annual_max_mm=0.0,
                annual_min_mm=0.0,
                monsoon_avg_mm=0.0,
                monsoon_fraction=0.0,
                monthly_avg=[],
                yearly_totals=[],
                max_rainfall_year=start_year,
                rainfall_class="Unknown",
            )

        annual_values   = list(yearly_totals.values())
        annual_avg_mm   = round(sum(annual_values) / len(annual_values), 1)
        annual_max_mm   = round(max(annual_values), 1)
        annual_min_mm   = round(min(annual_values), 1)
        max_rain_yr     = max(yearly_totals, key=yearly_totals.__getitem__)

        # ── Monthly averages (across all years) ──────────────────────────
        monthly_avg_list: List[MonthlyRainfall] = []
        for mo in range(1, 13):
            month_vals = [
                monthly_totals[(yr, mo)]
                for yr in yearly_totals
                if (yr, mo) in monthly_totals
            ]
            avg  = round(sum(month_vals) / max(1, len(month_vals)), 1)
            tot  = round(sum(month_vals), 1)
            monthly_avg_list.append(MonthlyRainfall(
                month=mo,
                month_name=MONTH_NAMES[mo - 1],
                avg_mm=avg,
                total_mm=tot,
            ))

        # ── Monsoon seasonal total (June–September) ───────────────────────
        monsoon_months = {6, 7, 8, 9}
        monsoon_avg = sum(
            m.avg_mm for m in monthly_avg_list if m.month in monsoon_months
        )
        monsoon_avg = round(monsoon_avg, 1)
        monsoon_frac = round(monsoon_avg / max(0.1, annual_avg_mm), 3)

        # ── Year-wise totals list ─────────────────────────────────────────
        yearly_list = [
            RainfallTimeSeries(year=yr, annual_total_mm=round(tot, 1))
            for yr, tot in sorted(yearly_totals.items())
        ]

        rainfall_class = _classify_rainfall(annual_avg_mm)

        return RainfallResponse(
            success=True,
            message=f"Historical rainfall fetched from Open-Meteo for {start_year}–{end_year}.",
            lat=request.lat,
            lng=request.lng,
            start_year=start_year,
            end_year=end_year,
            annual_avg_mm=annual_avg_mm,
            annual_max_mm=annual_max_mm,
            annual_min_mm=annual_min_mm,
            monsoon_avg_mm=monsoon_avg,
            monsoon_fraction=monsoon_frac,
            monthly_avg=monthly_avg_list,
            yearly_totals=yearly_list,
            max_rainfall_year=max_rain_yr,
            rainfall_class=rainfall_class,
        )
