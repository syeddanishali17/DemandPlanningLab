"""Forecast accuracy metrics and the method-selection rule.

Sign convention used everywhere in this project: **error = forecast - actual**, so a
positive bias means systematic over-forecasting.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def _aligned(actual, forecast) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if a.shape != f.shape:
        raise ValueError("actual and forecast must have the same length")
    mask = ~(np.isnan(a) | np.isnan(f))
    return a[mask], f[mask]


def wape(actual, forecast) -> float:
    """Weighted Absolute Percentage Error = sum |forecast - actual| / sum actual.

    Volume-weighted, so it reflects the units that matter, and it stays defined when
    individual weeks have zero demand (MAPE would divide by zero there).
    """
    a, f = _aligned(actual, forecast)
    total = a.sum()
    return float(np.abs(f - a).sum() / total) if total else float("nan")


def bias(actual, forecast) -> float:
    """Signed bias = sum (forecast - actual) / sum actual. Positive = over-forecasting."""
    a, f = _aligned(actual, forecast)
    total = a.sum()
    return float((f - a).sum() / total) if total else float("nan")


def error_sd(actual, forecast) -> float:
    """Sample standard deviation (ddof=1, like Excel STDEV.S) of the weekly errors (forecast - actual)."""
    a, f = _aligned(actual, forecast)
    if len(a) < 2:
        return float("nan")
    return float(np.std(f - a, ddof=1))


def select_method(
    wape_by_method: Mapping[str, float],
    tolerance: float,
    simplicity_order: Sequence[str],
) -> str:
    """Pick the lowest-WAPE method, preferring a simpler one when it is within ``tolerance``.

    Walk the methods in simplicity order and return the first whose WAPE is no worse than
    ``best + tolerance``. This mirrors the workbook's ``MATCH(TRUE, within_tol, 0)``.
    """
    valid = {m: w for m, w in wape_by_method.items() if w == w}  # drop NaN
    if not valid:
        raise ValueError("no method has a valid WAPE")
    best = min(valid.values())
    for method in simplicity_order:
        if method in valid and valid[method] <= best + tolerance:
            return method
    raise AssertionError("unreachable: the best method is always within tolerance of itself")
