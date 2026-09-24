"""Simple, explainable forecasting methods evaluated walk-forward.

Four methods only: Naive, 4-week moving average, 8-week moving average and Simple
Exponential Smoothing. Every method returns a series of length ``T + 1``:

* positions ``0 .. T-1`` are the *walk-forward* forecasts for history weeks ``1 .. T``,
  each computed only from earlier actuals (so week 1 has no forecast, MA4 starts in
  week 5, MA8 in week 9);
* position ``T`` is the forecast for the *next* week, i.e. the number the planning
  calculations use.

The forecasting layer exists to give the inventory calculations a reasonable demand
estimate and an honest measure of its error. It is deliberately not a forecasting
competition.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from planning.config import PlanningParameters
from planning.metrics import bias, error_sd, select_method, wape

METHODS: tuple[str, ...] = ("Naive", "MA4", "MA8", "SES")
"""Methods in *simplicity order*; the selection rule prefers earlier entries on a tie."""

METHOD_LABELS = {
    "Naive": "Naive (last week's actual)",
    "MA4": "4-week moving average",
    "MA8": "8-week moving average",
    "SES": "Simple exponential smoothing",
}

METHOD_SHORT = {"Naive": "Naive", "MA4": "MA 4-wk", "MA8": "MA 8-wk", "SES": "SES"}

MIN_WEEKS_FOR_ALL_METHODS = 9
"""First week in which every method has a walk-forward forecast (MA8 needs 8 prior weeks)."""


# --------------------------------------------------------------------------- methods
def naive_forecast(actuals: np.ndarray) -> np.ndarray:
    """F(t) = A(t-1)."""
    a = np.asarray(actuals, dtype=float)
    out = np.full(len(a) + 1, np.nan)
    out[1:] = a
    return out


def moving_average_forecast(actuals: np.ndarray, window: int) -> np.ndarray:
    """F(t) = mean(A(t-window) .. A(t-1)); undefined until ``window`` actuals exist."""
    a = np.asarray(actuals, dtype=float)
    out = np.full(len(a) + 1, np.nan)
    if len(a) >= window:
        cumsum = np.concatenate([[0.0], np.cumsum(a)])
        out[window:] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def ses_forecast(actuals: np.ndarray, alpha: float) -> np.ndarray:
    """F(2) = A(1); F(t) = alpha * A(t-1) + (1 - alpha) * F(t-1)."""
    a = np.asarray(actuals, dtype=float)
    out = np.full(len(a) + 1, np.nan)
    if len(a) == 0:
        return out
    out[1] = a[0]
    for t in range(2, len(a) + 1):
        out[t] = alpha * a[t - 1] + (1.0 - alpha) * out[t - 1]
    return out


def forecast_series(actuals: np.ndarray, method: str, alpha: float) -> np.ndarray:
    if method == "Naive":
        return naive_forecast(actuals)
    if method == "MA4":
        return moving_average_forecast(actuals, 4)
    if method == "MA8":
        return moving_average_forecast(actuals, 8)
    if method == "SES":
        return ses_forecast(actuals, alpha)
    raise ValueError(f"unknown forecast method {method!r}")


def walk_forward_table(actuals: pd.Series, alpha: float) -> pd.DataFrame:
    """Actuals plus the walk-forward forecast of every method, indexed by week (1..T)."""
    values = actuals.to_numpy(dtype=float)
    columns = {"actual": values}
    for method in METHODS:
        columns[method] = forecast_series(values, method, alpha)[:-1]
    table = pd.DataFrame(columns, index=actuals.index)
    table.index.name = "week"
    return table


# --------------------------------------------------------------------------- per SKU
@dataclass(frozen=True)
class SkuForecast:
    """Everything the planning calculations need to know about one SKU's forecast."""

    sku: str
    selected_method: str
    weekly_forecast: float
    """Next-week forecast of the selected method (flat for every future week)."""
    wape: float
    bias: float
    error_sd: float
    """Sample standard deviation of the selected method's walk-forward errors in the window."""
    evaluation_window: tuple[int, int]
    """First and last history week used to score the methods."""
    method_scores: pd.DataFrame
    """Per method: wape, bias, error_sd, next_forecast, within_tolerance, selected."""
    walk_forward: pd.DataFrame
    """Per week: actual and every method's walk-forward forecast (NaN before it is defined)."""

    @property
    def errors(self) -> pd.Series:
        """Walk-forward errors (forecast - actual) of the selected method in the evaluation window."""
        start, end = self.evaluation_window
        window = self.walk_forward.loc[start:end]
        return window[self.selected_method] - window["actual"]


def forecast_sku(
    sku: str,
    actuals: pd.Series,
    params: PlanningParameters,
    window_end: int | None = None,
) -> SkuForecast:
    """Score the four methods walk-forward on the evaluation window and pick one.

    ``window_end`` is the last history week that may be used (defaults to the last
    week available). The backtest passes an earlier week so that method selection and
    error SD are calibrated without any knowledge of the replayed weeks.
    """
    actuals = actuals.sort_index()
    last_week = int(actuals.index.max())
    window_end = last_week if window_end is None else int(window_end)
    window_start = max(MIN_WEEKS_FOR_ALL_METHODS, window_end - params.evaluation_weeks + 1)
    if window_end - window_start + 1 < 13:
        raise ValueError(f"{sku}: evaluation window {window_start}-{window_end} is shorter than 13 weeks")

    values = actuals.loc[:window_end].to_numpy(dtype=float)
    table = walk_forward_table(actuals, params.ses_alpha)
    window = table.loc[window_start:window_end]
    window_actual = window["actual"].to_numpy()

    rows = []
    for method in METHODS:
        series = forecast_series(values, method, params.ses_alpha)
        window_forecast = window[method].to_numpy()
        rows.append(
            {
                "method": method,
                "wape": wape(window_actual, window_forecast),
                "bias": bias(window_actual, window_forecast),
                "error_sd": error_sd(window_actual, window_forecast),
                "next_forecast": float(series[-1]),
            }
        )
    scores = pd.DataFrame(rows).set_index("method")

    best_wape = scores["wape"].min()
    scores["within_tolerance"] = scores["wape"] <= best_wape + params.wape_tolerance
    selected = select_method(scores["wape"].to_dict(), params.wape_tolerance, METHODS)
    scores["selected"] = scores.index == selected

    chosen = scores.loc[selected]
    return SkuForecast(
        sku=sku,
        selected_method=selected,
        weekly_forecast=float(chosen["next_forecast"]),
        wape=float(chosen["wape"]),
        bias=float(chosen["bias"]),
        error_sd=float(chosen["error_sd"]),
        evaluation_window=(window_start, window_end),
        method_scores=scores,
        walk_forward=table,
    )


def forecast_summary_table(forecasts: dict[str, SkuForecast]) -> pd.DataFrame:
    """One row per SKU with the selected method, forecast and accuracy metrics."""
    rows = []
    for sku, fc in forecasts.items():
        row = {
            "sku": sku,
            "forecast_method": fc.selected_method,
            "weekly_forecast": fc.weekly_forecast,
            "wape": fc.wape,
            "bias": fc.bias,
            "error_sd": fc.error_sd,
        }
        for method in METHODS:
            row[f"wape_{method.lower()}"] = fc.method_scores.loc[method, "wape"]
        rows.append(row)
    return pd.DataFrame(rows)


def portfolio_wape(forecasts: dict[str, SkuForecast]) -> float:
    """Volume-weighted WAPE of the selected methods across all SKUs (sum |errors| / sum actuals)."""
    abs_error = 0.0
    volume = 0.0
    for fc in forecasts.values():
        start, end = fc.evaluation_window
        window = fc.walk_forward.loc[start:end]
        abs_error += float((window[fc.selected_method] - window["actual"]).abs().sum())
        volume += float(window["actual"].sum())
    return abs_error / volume if volume else float("nan")
