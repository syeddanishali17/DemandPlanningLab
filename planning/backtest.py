"""Historical policy backtest: replay the final weeks with two replenishment policies.

Weekly sequence for every SKU and both policies (identical to the Excel workbook):

    start of week t:  (1) receive the order placed in week t - lead time
                      (2) review inventory position = stock + on order
                      (3) place an order if the policy says so (arrives week t + lead time)
                      (4) serve customer demand from stock; unmet demand is a LOST SALE

Policies:

* **Baseline (four weeks of stock)**: if inventory position < 4 x trailing 4-week average
  demand, order up to that level (rounded up to the case pack).
* **Proposed (forecast + safety stock + ROP + EOQ)**: forecast with the method chosen on
  the calibration window; safety stock = z x calibration error SD x sqrt(LT);
  ROP = forecast x LT + SS; if inventory position <= ROP, order EOQ rounded up.

No look-ahead: method choice and error SD come only from weeks *before* the replay,
each weekly forecast uses only earlier actuals, and demand of week t is revealed only
after the order decision. Both policies start with the same opening stock and nothing on
order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from planning.config import PlanningParameters
from planning.data import PlanningData
from planning.forecasting import forecast_sku
from planning.inventory import (
    economic_order_quantity,
    lead_time_demand,
    reorder_point,
    round_up_to_case_pack,
    safety_stock,
)

BASELINE = "baseline"
PROPOSED = "proposed"
POLICY_LABELS = {
    BASELINE: "Baseline: four weeks of stock",
    PROPOSED: "Proposed: forecast + safety stock + ROP + EOQ",
}
METRIC_LABELS = {
    "fill_rate": "Fill rate",
    "stockout_weeks": "Stockout SKU-weeks",
    "average_inventory_units": "Average inventory (units)",
    "number_of_orders": "Number of orders",
    "average_inventory_value": "Average inventory value",
}


def _excel_round(value: float) -> int:
    """Excel ROUND(x, 0): half away from zero (Python's round() is half-to-even)."""
    return int(math.floor(abs(value) + 0.5)) * (1 if value >= 0 else -1)


@dataclass(frozen=True)
class BacktestResult:
    weeks: tuple[int, int]
    """First and last replayed history week."""
    calibration_window: tuple[int, int]
    detail: pd.DataFrame
    """One row per SKU-week-policy with the full weekly state."""
    summary: pd.DataFrame
    """Portfolio metrics, one row per policy."""
    sku_summary: pd.DataFrame
    """Metrics per SKU and policy."""

    @staticmethod
    def empty() -> BacktestResult:
        return BacktestResult((0, 0), (0, 0), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    def metric(self, policy: str, name: str) -> float:
        return float(self.summary.loc[self.summary["policy"] == policy, name].iloc[0])

    def sku_detail(self, sku: str) -> pd.DataFrame:
        return self.detail.loc[self.detail["sku"] == sku]


def _simulate_policy(
    *,
    policy: str,
    weeks: range,
    demand: pd.Series,
    decision_forecast: pd.Series,
    opening_stock: int,
    lead_time: int,
    case_pack: int,
    unit_cost: float,
    ordering_cost: float,
    error_sd: float,
    params: PlanningParameters,
) -> list[dict]:
    """Run one policy for one SKU. ``decision_forecast[t]`` must only use actuals before week t."""
    z = params.z_value
    forecast_by_week = decision_forecast.to_dict()
    demand_by_week = demand.to_dict()
    placed: dict[int, int] = {}  # week placed -> quantity
    closing = float(opening_stock)
    rows = []
    for t in weeks:
        receipts = placed.get(t - lead_time, 0)
        stock_start = closing + receipts
        on_order = sum(q for w, q in placed.items() if t - lead_time < w < t)
        ip = stock_start + on_order
        forecast = float(forecast_by_week[t])

        if policy == BASELINE:
            target = params.baseline_weeks_of_stock * forecast
            order = round_up_to_case_pack(target - ip, case_pack) if ip < target else 0
            ss = rop = eoq = float("nan")
        else:
            ss = safety_stock(z, error_sd, lead_time)
            rop = reorder_point(lead_time_demand(forecast, lead_time), ss)
            eoq = economic_order_quantity(
                forecast * params.weeks_per_year, ordering_cost, unit_cost * params.annual_holding_rate
            )
            order = round_up_to_case_pack(eoq, case_pack) if ip <= rop else 0
            target = rop
        if order > 0:
            placed[t] = order

        actual = float(demand_by_week[t])
        sales = min(stock_start, actual)
        lost = actual - sales
        closing = stock_start - sales
        rows.append(
            {
                "policy": policy,
                "week": t,
                "actual_demand": actual,
                "forecast": forecast,
                "target": target,
                "safety_stock": ss,
                "reorder_point": rop,
                "eoq": eoq,
                "receipts": receipts,
                "stock_start": stock_start,
                "on_order": on_order,
                "inventory_position": ip,
                "order": order,
                "sales": sales,
                "lost_sales": lost,
                "closing_stock": closing,
                "stockout_week": lost > 0,
                "closing_value": closing * unit_cost,
            }
        )
    return rows


def run_backtest(data: PlanningData, params: PlanningParameters) -> BacktestResult:
    last_week = data.scenario.history_weeks
    start_week = last_week - params.backtest_weeks + 1
    calibration_end = start_week - 1
    weeks = range(start_week, last_week + 1)

    rows: list[dict] = []
    for _, sku in data.sku_master.iterrows():
        code = sku["sku"]
        actuals = data.demand_series(code)
        calibrated = forecast_sku(code, actuals, params, window_end=calibration_end)
        walk = calibrated.walk_forward

        opening = _excel_round(params.backtest_opening_cover_weeks * float(walk.loc[start_week, "MA8"]))
        common = dict(
            weeks=weeks,
            demand=actuals,
            opening_stock=opening,
            lead_time=int(sku["lead_time_weeks"]),
            case_pack=int(sku["case_pack"]),
            unit_cost=float(sku["unit_cost_eur"]),
            ordering_cost=float(sku["ordering_cost_eur"]),
            error_sd=calibrated.error_sd,
            params=params,
        )
        for policy, forecast_col in ((BASELINE, "MA4"), (PROPOSED, calibrated.selected_method)):
            for row in _simulate_policy(policy=policy, decision_forecast=walk[forecast_col], **common):
                row.update(sku=code, forecast_method=forecast_col, opening_stock=opening)
                rows.append(row)

    detail = pd.DataFrame(rows)
    n_weeks = params.backtest_weeks

    def summarise(group: pd.DataFrame) -> pd.Series:
        demanded = group["actual_demand"].sum()
        return pd.Series(
            {
                "fill_rate": group["sales"].sum() / demanded if demanded else np.nan,
                "stockout_weeks": int(group["stockout_week"].sum()),
                "average_inventory_units": group["closing_stock"].sum() / n_weeks,
                "number_of_orders": int((group["order"] > 0).sum()),
                "average_inventory_value": group["closing_value"].sum() / n_weeks,
                "lost_units": group["lost_sales"].sum(),
                "units_demanded": demanded,
            }
        )

    summary = detail.groupby("policy", sort=False).apply(summarise, include_groups=False).reset_index()
    sku_summary = (
        detail.groupby(["sku", "policy"], sort=False).apply(summarise, include_groups=False).reset_index()
    )
    return BacktestResult(
        weeks=(start_week, last_week),
        calibration_window=calibrated.evaluation_window,
        detail=detail,
        summary=summary,
        sku_summary=sku_summary,
    )
