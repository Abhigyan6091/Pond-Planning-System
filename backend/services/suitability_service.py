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
5. Build CHANNEL EXCLUSION MASK
   A cell is classified as an active drainage channel (not a storage site) when
   ALL of the following hold simultaneously:
     a) flow_accumulation >= CHANNEL_ACC_THRESHOLD  (large upstream area)
     b) depression_depth  <  CHANNEL_DEP_THRESHOLD  (no closed basin above it)
     c) the cell has a valid D8 pointer (i.e., water FLOWS THROUGH, not TO)
   Such cells are zeroed in the suitability map before candidate selection.
6. For each non-channel cell compute 5 normalized scores:
     slope_score      = 1 / (1 + slope_deg/SLOPE_REF)   normalised to [0,1]
     depression_score = fill_depth / max_fill_depth      normalised to [0,1]
     catchment_score  = log(1 + acc) / max_log_acc       normalised to [0,1]
     elevation_score  = 1 - (elev - min_e)/(max_e - min_e)
     rainfall_score   = min(1, rainfall_mm / RAIN_REF)   (scalar, same for all)
7. Weighted composite → suitability_map
8. Select top-N candidates with minimum spatial separation (grid_radius)
   using a DETERMINISTIC composite sort key:
     primary:   suitability DESC
     secondary: flow_accumulation DESC  (more catchment → better)
     tertiary:  depression_depth DESC   (deeper storage → better)
     then:      elevation ASC, row ASC, column ASC
9. For each candidate, estimate:
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

NOTE ON RAINFALL SCORE
----------------------
rainfall_score is a spatially UNIFORM scalar (same value for every grid cell).
It therefore adds an identical constant to every candidate’s composite score,
preserving the ranking order.  Changing rainfall_mm between runs does NOT
cause ranking non-determinism.

NOTE ON CHANNEL EXCLUSION
--------------------------
The exclusion mask is derived purely from the DEM-computed stream network.
No real-world river geometry or external water-body layer is used.
This is documented as a limitation: the mask suppresses DEM-inferred
throughflow channels but cannot detect all real-world water bodies.
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

# Channel exclusion thresholds
# A cell is treated as an active drainage channel (not a pond site) only when
# BOTH criteria apply simultaneously:
#   1. Its upstream contributing area exceeds CHANNEL_ACC_FRAC * (rows * cols)
#      This is a fractional threshold so it scales with grid size instead of
#      hard-coding a number of cells.
#   2. Its depression depth is below CHANNEL_DEP_THRESHOLD metres
#      (i.e. the fill algorithm cannot form a closed basin above it)
CHANNEL_ACC_FRAC      = 0.05   # top 5% of flow-accumulation values
CHANNEL_DEP_THRESHOLD = 0.30   # metres — must have at least 30 cm closed depression to NOT be a channel


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
        filled           = cls._priority_flood_fill(dem)
        depression_depth = np.maximum(0.0, filled - dem)

        # ── 4. Channel exclusion mask (Storage vs. Through-Flow) ──────
        # A cell is classified as an active throughflow channel (not a pond site) when:
        #   (a) Upstream flow accumulation is high (top 5% of accumulation values), AND
        #   (b) Depression depth is minimal (< 0.30 m, indicating no closed storage basin), AND
        #   (c) The cell has a valid D8 outflow pointer (continuous drainage pathway).
        # Legitimate side depressions and natural basins with large catchment areas are retained.
        # Note: Derived from DEM hydrology; does not access external vector hydrography.
        acc_threshold    = int(np.percentile(flow_acc, (1.0 - CHANNEL_ACC_FRAC) * 100))
        acc_threshold    = max(acc_threshold, 5)
        has_high_acc     = flow_acc >= acc_threshold
        lacks_depression = depression_depth < CHANNEL_DEP_THRESHOLD
        has_outflow      = flow_dir != -1
        channel_mask     = has_high_acc & lacks_depression & has_outflow

        # ── 5. Score components ───────────────────────────────────────
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

        # Rainfall score (scalar — uniform across every grid cell)
        rf_mm = request.rainfall_mm if request.rainfall_mm else 0.0
        rainfall_score_scalar = min(1.0, rf_mm / RAIN_REF)

        # ── 6. Normalize weights ──────────────────────────────────────
        w = np.array([
            request.weight_slope,
            request.weight_depression,
            request.weight_catchment,
            request.weight_elevation,
            request.weight_rainfall,
        ], dtype=np.float64)
        w = w / w.sum()  # normalize to 1.0

        # ── 7. Composite suitability map [0, 1] ──────────────────────
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

        # Exclude DEM-inferred active throughflow channels
        suitability[channel_mask] = 0.0

        # ── 8. Select top-N with spatial separation (deterministic) ───
        min_sep_cells = max(3, min(rows, cols) // 8)
        candidates_raw = cls._select_top_n_separated(
            suitability, request.num_candidates, min_sep_cells,
            flow_acc, depression_depth, dem
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

            # Individual scores and itemized points at this cell (summing to 100)
            slp_sc  = float(slope_score[r, c])
            dep_sc  = float(depression_score[r, c])
            cat_sc  = float(catchment_score[r, c])
            elv_sc  = float(elevation_score[r, c])
            rn_sc   = float(rainfall_score_scalar)

            slp_pts = round(slp_sc * 20.0, 1)
            dep_pts = round(dep_sc * 20.0, 1)
            cat_pts = round(cat_sc * 25.0, 1)
            elv_pts = round(elv_sc * 15.0, 1)
            rn_pts  = round(rn_sc * 20.0, 1)
            tot_pts = round(slp_pts + dep_pts + cat_pts + elv_pts + rn_pts, 1)

            s_comp = SuitabilityScoreComponents(
                slope_score      = round(slp_sc, 4),
                depression_score = round(dep_sc, 4),
                catchment_score  = round(cat_sc, 4),
                elevation_score  = round(elv_sc, 4),
                rainfall_score   = round(rn_sc, 4),
                composite_score  = tot_pts,
                slope_pts        = slp_pts,
                depression_pts   = dep_pts,
                catchment_pts    = cat_pts,
                elevation_pts    = elv_pts,
                rainfall_pts     = rn_pts,
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
    # SELECT TOP-N CANDIDATES WITH SPATIAL SEPARATION (DETERMINISTIC)
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _select_top_n_separated(
        suitability: np.ndarray,
        n: int,
        min_sep: int,
        flow_acc: np.ndarray,
        depression_depth: np.ndarray,
        dem: np.ndarray,
    ) -> List[Tuple[int, int]]:
        """
        Return top-N (row, col) positions with >= min_sep grid cells separation.

        Cells are ordered by a DETERMINISTIC composite key (Python Timsort, stable):
            1. suitability DESC           (primary: highest composite score)
            2. flow_accumulation DESC     (secondary: larger catchment preferred)
            3. depression_depth DESC      (tertiary: deeper storage basin preferred)
            4. elevation ASC              (lower cell preferred for gravity drainage)
            5. row ASC, col ASC           (top-left wins any remaining ties)
            6. flat_index (unique)        (absolute guarantee of unique ordering)

        Negation is used for DESC fields so ascending sort gives descending order.
        """
        rows, cols = suitability.shape

        suit_flat = suitability.flatten()
        acc_flat  = flow_acc.flatten().astype(np.float64)
        dep_flat  = depression_depth.flatten()
        elev_flat = dem.flatten()

        # Consider only non-zero cells (border and channel cells are zeroed)
        non_zero_idx = np.nonzero(suit_flat)[0]

        # Build (sort_key_tuple, flat_index) list
        sort_keys = [
            (
                -suit_flat[i],            # 1. suitability DESC
                -acc_flat[i],             # 2. flow_accumulation DESC
                -dep_flat[i],             # 3. depression_depth DESC
                elev_flat[i],             # 4. elevation ASC
                int(i) // cols,           # 5. row ASC
                int(i) % cols,            # 6. col ASC
                int(i),                   # 7. flat_index (unique tie-breaker)
            )
            for i in non_zero_idx
        ]
        sort_keys.sort()   # Python Timsort — stable and deterministic

        selected: List[Tuple[int, int]] = []
        for key in sort_keys:
            flat_idx = key[-1]
            r, c = divmod(flat_idx, cols)
            too_close = any(
                math.sqrt((r - sr) ** 2 + (c - sc) ** 2) < min_sep
                for sr, sc in selected
            )
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
