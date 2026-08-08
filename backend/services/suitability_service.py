"""
suitability_service.py
======================
Identifies candidate pond sites by scoring each DEM cell on multiple
terrain-derived criteria and returning the top-N ranked candidates.

ALGORITHM OVERVIEW
------------------
1. Compute slope matrix from DEM (TerrainService)
2. Compute D8 flow direction (HydrologyService)
3. Compute flow accumulation (HydrologyService)
4. Fill DEM using Priority-Flood (PondService helper) → depression depth
5. For each cell compute 5 normalized scores:
     slope_score      = 1 / (1 + slope_deg/SLOPE_REF)   normalised to [0,1]
     depression_score = fill_depth / max_fill_depth      normalised to [0,1]
     catchment_score  = log(1 + acc) / max_log_acc       normalised to [0,1]
     elevation_score  = 1 - (elev - min_e)/(max_e - min_e)
     rainfall_score   = min(1, rainfall_mm / RAIN_REF)   (scalar, same for all)
6. Weighted composite → suitability_map
7. Select top-N candidates with minimum spatial separation (grid_radius)
8. For each candidate, estimate:
     catchment_area_m2 ≈ flow_acc × pixel_size_m²
     pond depth        ≈ depression_depth at candidate cell (or local basin min)
     pond volume       ≈ sum((water_level - elev) × px_area) over local basin

SCORE WEIGHTS (defaults)
------------------------
slope:       0.30
depression:  0.30
catchment:   0.25
elevation:   0.05
rainfall:    0.10
"""
import math
import uuid
import heapq
import numpy as np
from scipy.ndimage import uniform_filter
from typing import List, Tuple, Optional

from backend.models.suitability_models import (
    SuitabilityRequest, SuitabilityResponse,
    CandidateSite, SuitabilityScoreComponents,
)
from backend.services.hydrology_service import HydrologyService

# Reference constants
SLOPE_REF  = 8.0    # degrees — slope above this starts scoring poorly
RAIN_REF   = 800.0  # mm/yr  — rainfall above this scores maximum


class SuitabilityService:

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def analyze(cls, request: SuitabilityRequest) -> SuitabilityResponse:
        dem    = np.array(request.elevation_matrix, dtype=np.float64)
        rows, cols = dem.shape
        bounds = request.bounds
        pxm    = request.pixel_size_m

        # ── 1. Slope ──────────────────────────────────────────────────
        dy, dx     = np.gradient(dem, pxm)
        slope_deg  = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

        # ── 2. Flow direction + accumulation ─────────────────────────
        flow_dir = HydrologyService.compute_d8_flow_direction(dem, pxm)
        flow_acc = HydrologyService.compute_flow_accumulation(flow_dir)

        # ── 3. Depression depth (Priority-Flood fill) ─────────────────
        filled         = cls._priority_flood_fill(dem)
        depression_depth = np.maximum(0.0, filled - dem)

        # ── 4. Score components ───────────────────────────────────────
        # Slope score: lower slope → higher score
        slope_score_raw  = 1.0 / (1.0 + slope_deg / SLOPE_REF)
        s_min, s_max     = slope_score_raw.min(), slope_score_raw.max()
        slope_score      = (slope_score_raw - s_min) / max(s_max - s_min, 1e-6)

        # Depression score: deeper natural sink → higher
        d_max = depression_depth.max()
        depression_score = depression_depth / max(d_max, 1e-6)

        # Catchment score: more upstream cells → higher (log-scaled)
        log_acc         = np.log1p(flow_acc.astype(np.float64))
        catchment_score = log_acc / max(log_acc.max(), 1e-6)

        # Elevation score: lower within ROI → higher
        e_min, e_max = dem.min(), dem.max()
        elevation_score = 1.0 - (dem - e_min) / max(e_max - e_min, 1e-6)

        # Rainfall score (scalar)
        rf_mm = request.rainfall_mm if request.rainfall_mm else 0.0
        rainfall_score_scalar = min(1.0, rf_mm / RAIN_REF)

        # ── 5. Normalize weights ──────────────────────────────────────
        w = np.array([
            request.weight_slope,
            request.weight_depression,
            request.weight_catchment,
            request.weight_elevation,
            request.weight_rainfall,
        ], dtype=np.float64)
        w = w / w.sum()  # normalize to 1.0

        # ── 6. Composite suitability map [0, 1] ──────────────────────
        suitability = (
            w[0] * slope_score +
            w[1] * depression_score +
            w[2] * catchment_score +
            w[3] * elevation_score +
            w[4] * rainfall_score_scalar    # scalar broadcast across grid
        )

        # Exclude border cells (poor data near DEM edges)
        border = 2
        suitability[:border, :]  = 0.0
        suitability[-border:, :] = 0.0
        suitability[:, :border]  = 0.0
        suitability[:, -border:] = 0.0

        # ── 7. Select top-N with minimum spatial separation ──────────
        min_sep_cells = max(3, min(rows, cols) // 8)
        candidates_raw = cls._select_top_n_separated(
            suitability, request.num_candidates, min_sep_cells
        )

        # ── 8. Build candidate site objects ──────────────────────────
        lats = np.linspace(bounds.north, bounds.south, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        pixel_area_m2 = pxm * pxm

        candidates: List[CandidateSite] = []
        for rank, (r, c) in enumerate(candidates_raw, start=1):
            lat_val   = float(lats[r])
            lng_val   = float(lons[c])
            elev_val  = float(dem[r, c])
            slope_val = float(slope_deg[r, c])
            dep_val   = float(depression_depth[r, c])
            acc_val   = int(flow_acc[r, c])
            suit_val  = float(suitability[r, c])

            # Individual scores at this cell
            s_comp = SuitabilityScoreComponents(
                slope_score      = round(float(slope_score[r, c]),      4),
                depression_score = round(float(depression_score[r, c]), 4),
                catchment_score  = round(float(catchment_score[r, c]),  4),
                elevation_score  = round(float(elevation_score[r, c]),  4),
                rainfall_score   = round(rainfall_score_scalar,         4),
                composite_score  = round(suit_val * 100.0,              2),
            )

            # Catchment area estimate from flow accumulation
            ca_m2   = float(acc_val) * pixel_area_m2
            ca_km2  = ca_m2 / 1_000_000.0

            # Pond geometry from local DEM window
            depth, surf_area_m2, vol_m3 = cls._estimate_local_pond(
                dem, r, c, pxm, dep_val, window_radius=5
            )

            # Runoff estimate
            runoff_m3 = None
            if rf_mm > 0:
                c_coeff = request.runoff_coefficient
                runoff_m3 = (rf_mm / 1000.0) * ca_m2 * c_coeff

            tier, reasons = cls._classify_candidate(s_comp, ca_km2, rf_mm)

            candidates.append(CandidateSite(
                rank=rank,
                site_id=f"site_{uuid.uuid4().hex[:8]}",
                lat=round(lat_val, 6),
                lng=round(lng_val, 6),
                elevation_m=round(elev_val, 1),
                slope_deg=round(slope_val, 1),
                depression_depth_m=round(dep_val, 2),
                flow_accumulation=acc_val,
                catchment_area_m2=round(ca_m2, 1),
                catchment_area_km2=round(ca_km2, 4),
                estimated_depth_m=round(depth, 2),
                estimated_surface_area_m2=round(surf_area_m2, 1),
                estimated_volume_m3=round(vol_m3, 1),
                rainfall_mm=round(rf_mm, 1) if rf_mm else None,
                runoff_coefficient=round(request.runoff_coefficient, 2),
                estimated_runoff_m3=round(runoff_m3, 1) if runoff_m3 else None,
                scores=s_comp,
                suitability_tier=tier,
                suitability_reasons=reasons,
            ))

        recommended = candidates[0] if candidates else None

        return SuitabilityResponse(
            success=True,
            message=f"Identified {len(candidates)} candidate pond site(s).",
            num_candidates=len(candidates),
            candidates=candidates,
            recommended=recommended,
        )

    # ──────────────────────────────────────────────────────────────────
    # PRIORITY-FLOOD FILL (Wang & Liu 2006)
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _priority_flood_fill(dem: np.ndarray) -> np.ndarray:
        rows, cols = dem.shape
        filled  = dem.copy()
        visited = np.zeros((rows, cols), dtype=bool)
        pq: list = []

        for r in range(rows):
            for c_idx in [0, cols - 1]:
                heapq.heappush(pq, (filled[r, c_idx], r, c_idx))
                visited[r, c_idx] = True
        for c_idx in range(cols):
            for r in [0, rows - 1]:
                if not visited[r, c_idx]:
                    heapq.heappush(pq, (filled[r, c_idx], r, c_idx))
                    visited[r, c_idx] = True

        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while pq:
            elev, r, c = heapq.heappop(pq)
            for dr, dc in nbrs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                    visited[nr, nc] = True
                    filled[nr, nc] = max(filled[nr, nc], elev)
                    heapq.heappush(pq, (filled[nr, nc], nr, nc))

        return filled

    # ──────────────────────────────────────────────────────────────────
    # SELECT TOP-N CANDIDATES WITH SPATIAL SEPARATION
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _select_top_n_separated(
        suitability: np.ndarray,
        n: int,
        min_sep: int
    ) -> List[Tuple[int, int]]:
        """Return top-N (row, col) positions with >= min_sep grid cells separation."""
        rows, cols = suitability.shape
        flat = suitability.flatten()
        order = np.argsort(flat)[::-1]

        selected: List[Tuple[int, int]] = []

        for idx in order:
            r, c = divmod(int(idx), cols)
            # Check spatial separation from already-selected candidates
            too_close = False
            for sr, sc in selected:
                dist = math.sqrt((r - sr)**2 + (c - sc)**2)
                if dist < min_sep:
                    too_close = True
                    break
            if not too_close:
                selected.append((r, c))
            if len(selected) >= n:
                break

        return selected

    # ──────────────────────────────────────────────────────────────────
    # LOCAL POND GEOMETRY ESTIMATION
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _estimate_local_pond(
        dem: np.ndarray,
        r: int, c: int,
        pxm: float,
        depression_depth: float,
        window_radius: int = 5
    ) -> Tuple[float, float, float]:
        """
        Estimates pond depth, surface area, and volume from a local DEM window.

        Returns (depth_m, surface_area_m2, volume_m3).
        """
        rows, cols = dem.shape
        r0 = max(0, r - window_radius)
        r1 = min(rows, r + window_radius + 1)
        c0 = max(0, c - window_radius)
        c1 = min(cols, c + window_radius + 1)

        window = dem[r0:r1, c0:c1]
        bottom_elev = float(dem[r, c])

        # Water level: use spill rim approximation
        border_vals = np.concatenate([
            window[0, :], window[-1, :], window[:, 0], window[:, -1]
        ])
        spill_elev = float(np.percentile(border_vals, 25))

        # If no natural spill detected, fall back to depression_depth + 1m
        if depression_depth > 0.1:
            water_level = bottom_elev + depression_depth
        else:
            water_level = bottom_elev + max(1.0, float(np.std(window)) * 1.5)

        water_level = max(water_level, bottom_elev + 0.5)

        # Depth
        depth = water_level - bottom_elev

        # Submerged cells
        pixel_area = pxm * pxm
        submerged  = window < water_level
        depth_arr  = np.maximum(0.0, water_level - window)

        surface_area_m2 = float(np.sum(submerged)) * pixel_area
        volume_m3       = float(np.sum(depth_arr[submerged])) * pixel_area

        return max(0.5, depth), max(pixel_area, surface_area_m2), max(0.0, volume_m3)

    # ──────────────────────────────────────────────────────────────────
    # SUITABILITY TIER + REASON STRINGS
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _classify_candidate(
        scores: SuitabilityScoreComponents,
        catchment_km2: float,
        rainfall_mm: float,
    ) -> Tuple[str, List[str]]:
        composite = scores.composite_score

        reasons: List[str] = []

        if scores.slope_score >= 0.6:
            reasons.append("✓ Favorable terrain slope")
        if scores.depression_score >= 0.4:
            reasons.append("✓ Natural terrain depression")
        if scores.catchment_score >= 0.5:
            reasons.append("✓ Good upstream catchment")
        if catchment_km2 >= 0.5:
            reasons.append(f"✓ Catchment area {catchment_km2:.2f} km²")
        if rainfall_mm >= 500:
            reasons.append(f"✓ Adequate rainfall ({rainfall_mm:.0f} mm/yr)")
        if scores.elevation_score >= 0.5:
            reasons.append("✓ Low-lying collection point")

        # Negative indicators
        if scores.slope_score < 0.3:
            reasons.append("⚠ Steep terrain — excavation difficult")
        if scores.depression_score < 0.2:
            reasons.append("⚠ Minimal natural depression")
        if rainfall_mm > 0 and rainfall_mm < 350:
            reasons.append("⚠ Low annual rainfall")

        if composite >= 70:
            tier = "Recommended"
        elif composite >= 50:
            tier = "Highly Suitable"
        elif composite >= 35:
            tier = "Moderately Suitable"
        else:
            tier = "Poor"

        return tier, reasons
