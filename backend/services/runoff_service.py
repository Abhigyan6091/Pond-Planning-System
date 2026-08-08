"""
runoff_service.py
=================
Estimates surface runoff volume using the Runoff Coefficient Method:

    V = P × A × C

Where:
    P = precipitation depth (converted from mm to metres)
    A = catchment area in m²
    C = runoff coefficient (dimensionless, 0–1)

Note: This calculates total volume V = P × A × C, distinct from the classical Rational Method for peak discharge Q = C · i · A.
This is a planning-level estimate suitable for pre-feasibility pond sizing.
It is NOT a substitute for site-specific hydrological modelling.
"""
from backend.models.runoff_models import RunoffRequest, RunoffResponse, RUNOFF_COEFFICIENT_PRESETS


class RunoffService:

    @staticmethod
    def estimate_runoff(request: RunoffRequest) -> RunoffResponse:
        # Resolve coefficient from preset if provided
        c = request.runoff_coefficient
        c_label = f"Custom (C = {c:.2f})"

        if request.coefficient_preset and request.coefficient_preset in RUNOFF_COEFFICIENT_PRESETS:
            preset = RUNOFF_COEFFICIENT_PRESETS[request.coefficient_preset]
            c = preset["c"]
            c_label = preset["label"]

        # Clamp to physical range
        c = max(0.05, min(c, 0.95))

        # Convert rainfall from mm to metres
        p_m = request.rainfall_mm / 1000.0

        # Runoff volume: V = P × A × C
        volume_m3 = p_m * request.catchment_area_m2 * c
        volume_million_m3 = volume_m3 / 1_000_000.0

        catchment_km2 = request.catchment_area_m2 / 1_000_000.0

        return RunoffResponse(
            success=True,
            rainfall_mm=round(request.rainfall_mm, 1),
            catchment_area_m2=round(request.catchment_area_m2, 1),
            catchment_area_km2=round(catchment_km2, 4),
            runoff_coefficient=round(c, 2),
            coefficient_label=c_label,
            runoff_volume_m3=round(volume_m3, 1),
            runoff_volume_million_m3=round(volume_million_m3, 4),
            pond_fill_count=0.0,  # Caller may update this once pond volume is known
        )
