"""LOD/LOQ study calculations for the local ADA viewer.

Results are estimates unless the caller explicitly records independently
validated, user-supplied limits.  The module deliberately keeps calculation
and presentation separate from compound identification.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        qualifier = "a positive " if positive else "a finite "
        raise ValueError(f"{name} must be {qualifier}number.")
    return number


def _numbers(values: Any, name: str, minimum: int = 1) -> np.ndarray:
    try:
        result = np.asarray([float(value) for value in values], dtype=float)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must contain numeric values.") from None
    if result.size < minimum or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} requires at least {minimum} finite values.")
    return result


def calculate_study(payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method", "calibration")).strip().lower()
    common = {
        "analyte": str(payload.get("analyte", "Target analyte")).strip() or "Target analyte",
        "formula": str(payload.get("formula", "")).strip(),
        "quantifier_mz": _finite(payload.get("quantifier_mz"), "Quantifier m/z", positive=True),
        "mz_tolerance": _finite(payload.get("mz_tolerance", 0.05), "m/z tolerance", positive=True),
        "concentration_unit": str(payload.get("concentration_unit", "ppb")).strip() or "ppb",
        "matrix": str(payload.get("matrix", "Not specified")).strip() or "Not specified",
        "method": method,
        "validation_status": "Estimated—not independently validated",
    }

    if method in {"calibration", "signal_noise"}:
        rows = payload.get("calibration", [])
        if not isinstance(rows, list) or len(rows) < 3:
            raise ValueError("Enter at least three calibration points.")
        concentrations = _numbers([row.get("concentration") for row in rows], "Calibration concentrations", 3)
        responses = _numbers([row.get("response") for row in rows], "Calibration responses", 3)
        if np.unique(concentrations).size < 2:
            raise ValueError("Calibration requires at least two different concentrations.")
        slope, intercept = np.polyfit(concentrations, responses, 1)
        if not math.isfinite(slope) or slope <= 0:
            raise ValueError("The fitted calibration slope must be positive.")
        predicted = slope * concentrations + intercept
        residuals = responses - predicted
        residual_sigma = float(np.sqrt(np.sum(residuals**2) / max(1, concentrations.size - 2)))
        total = float(np.sum((responses - np.mean(responses)) ** 2))
        r_squared = float(1 - np.sum(residuals**2) / total) if total > 0 else None
        blanks_raw = payload.get("blanks", [])
        blanks = _numbers(blanks_raw, "Blank responses", 2) if len(blanks_raw) >= 2 else np.asarray([], dtype=float)
        blank_mean = float(np.mean(blanks)) if blanks.size else 0.0
        blank_sigma = float(np.std(blanks, ddof=1)) if blanks.size else None
        sigma = blank_sigma if blank_sigma is not None and blank_sigma > 0 else residual_sigma
        if not math.isfinite(sigma) or sigma <= 0:
            raise ValueError("Background or calibration variation must be greater than zero.")

        if method == "calibration":
            lod = 3.3 * sigma / slope
            loq = 10.0 * sigma / slope
            lod_response = intercept + slope * lod
            loq_response = intercept + slope * loq
            method_label = "Calibration curve: 3.3σ/S and 10σ/S"
        else:
            lod_response = blank_mean + 3.0 * sigma
            loq_response = blank_mean + 10.0 * sigma
            lod = max(0.0, (lod_response - intercept) / slope)
            loq = max(0.0, (loq_response - intercept) / slope)
            method_label = "Signal-to-noise estimate: 3:1 and 10:1"

        return common | {
            "method_label": method_label,
            "lod": float(lod), "loq": float(loq),
            "lod_response": float(lod_response), "loq_response": float(loq_response),
            "slope": float(slope), "intercept": float(intercept),
            "sigma": float(sigma), "sigma_source": "blank standard deviation" if blank_sigma is not None and blank_sigma > 0 else "calibration residual standard deviation",
            "blank_mean": blank_mean, "blank_count": int(blanks.size),
            "calibration_count": int(concentrations.size), "r_squared": r_squared,
            "calibration_min": float(np.min(concentrations)), "calibration_max": float(np.max(concentrations)),
            "limitations": "Estimated limits require confirmation with independent samples near the limits and apply only to the recorded analyte, matrix, method and instrument configuration.",
        }

    if method == "user_supplied":
        lod = _finite(payload.get("lod"), "LOD", positive=True)
        loq = _finite(payload.get("loq"), "LOQ", positive=True)
        if loq < lod:
            raise ValueError("LOQ must be greater than or equal to LOD.")
        status = str(payload.get("validation_status", "User-supplied")).strip() or "User-supplied"
        return common | {
            "method_label": "User-supplied limits",
            "validation_status": status,
            "lod": lod, "loq": loq,
            "lod_response": None, "loq_response": None,
            "slope": None, "intercept": None, "sigma": None,
            "r_squared": None, "blank_count": 0, "calibration_count": 0,
            "limitations": "These limits were supplied by the user and were not calculated or verified by ADA Viewer.",
        }

    raise ValueError("Choose calibration, signal_noise, or user_supplied.")


def classify_peak(peak_mz: float, intensity: float, study: dict[str, Any]) -> dict[str, Any]:
    if abs(float(peak_mz) - study["quantifier_mz"]) > study["mz_tolerance"]:
        return {"detection_status": "Not evaluated", "concentration": None, "signal_to_noise": None}
    slope, intercept = study.get("slope"), study.get("intercept")
    concentration = None
    if slope is not None and slope > 0:
        concentration = max(0.0, (float(intensity) - intercept) / slope)
    sigma = study.get("sigma")
    signal_to_noise = None
    if sigma is not None and sigma > 0:
        signal_to_noise = max(0.0, (float(intensity) - study.get("blank_mean", 0.0)) / sigma)
    if concentration is None:
        status = "Requires concentration result"
    elif concentration < study["lod"]:
        status = "Below LOD"
    elif concentration < study["loq"]:
        status = "Detected—not quantifiable"
    elif study.get("calibration_max") is not None and concentration > study["calibration_max"]:
        status = "Above calibration range"
    else:
        status = "Quantifiable"
    return {"detection_status": status, "concentration": concentration, "signal_to_noise": signal_to_noise}
