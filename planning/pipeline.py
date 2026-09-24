"""End-to-end plan: data + parameters -> forecasts -> replenishment table -> projections -> statuses -> backtest.

``run_plan`` is the single entry point the user interface calls. Everything it returns is
plain pandas / dataclasses, so the same result can be inspected in a notebook or a test.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from planning.backtest import BacktestResult, run_backtest
from planning.config import PlanningParameters
from planning.data import PlanningData
from planning.exceptions import Status, classify, explain, rank_attention, recommended_action
from planning.forecasting import SkuForecast, forecast_sku, forecast_summary_table, portfolio_wape
from planning.inventory import build_replenishment_table
from planning.projection import ProjectionResult, project_inventory


@dataclass(frozen=True)
class PlanResult:
    params: PlanningParameters
    data: PlanningData
    forecasts: dict[str, SkuForecast]
    plan: pd.DataFrame
    """One row per SKU: forecast, safety stock, ROP, inventory position, EOQ, order, status, reason."""
    projections: dict[str, ProjectionResult]
    backtest: BacktestResult
    portfolio_wape: float

    def sku_plan(self, sku: str) -> pd.Series:
        rows = self.plan.loc[self.plan["sku"] == sku]
        if rows.empty:
            raise KeyError(f"unknown SKU {sku!r}")
        return rows.iloc[0]

    @property
    def attention(self) -> pd.DataFrame:
        """Non-healthy SKUs, most urgent first."""
        return self.plan.loc[self.plan["status"] != Status.HEALTHY.value].sort_values("attention_rank")

    def status_counts(self) -> dict[str, int]:
        counts = self.plan["status"].value_counts()
        return {s.value: int(counts.get(s.value, 0)) for s in Status}


def run_plan(
    data: PlanningData, params: PlanningParameters | None = None, include_backtest: bool = True
) -> PlanResult:
    params = params or PlanningParameters()

    # 1. Forecast every SKU walk-forward on the most recent evaluation window.
    forecasts = {sku: forecast_sku(sku, data.demand_series(sku), params) for sku in data.skus}
    summary = forecast_summary_table(forecasts)

    # 2. Safety stock -> ROP -> inventory position -> EOQ -> order decision.
    plan = build_replenishment_table(data.sku_master, summary, params)

    # 3. Project each SKU forward with existing POs and today's recommended order.
    projections: dict[str, ProjectionResult] = {}
    for _, row in plan.iterrows():
        projections[row["sku"]] = project_inventory(
            on_hand=row["on_hand"],
            backorders=row["backorders"],
            weekly_forecast=row["weekly_forecast"],
            lead_time_weeks=int(row["lead_time_weeks"]),
            reorder_point=row["reorder_point"],
            open_orders=data.open_orders(row["sku"]),
            recommended_order=int(row["recommended_order"]),
            horizon_weeks=params.projection_weeks,
            scenario=data.scenario,
        )

    # 4. Status, reason and attention ranking.
    statuses, reasons, zero_weeks, zero_in_lt, min_closing, next_trigger = [], [], [], [], [], []
    for _, row in plan.iterrows():
        proj = projections[row["sku"]]
        status = classify(
            zero_within_lead_time=proj.zero_within_lead_time,
            reorder_triggered=bool(row["reorder_triggered"]),
            weeks_of_cover=float(row["weeks_of_cover"]),
            excess_threshold=params.excess_weeks_of_cover,
        )
        statuses.append(status.value)
        reasons.append(explain(row, proj, status, params))
        zero_weeks.append(proj.first_zero_week)
        zero_in_lt.append(proj.zero_within_lead_time)
        min_closing.append(proj.min_closing)
        next_trigger.append(proj.next_review_trigger_week)
    plan["status"] = statuses
    plan["reason"] = reasons
    plan["first_zero_week"] = pd.array(zero_weeks, dtype="Int64")
    plan["zero_within_lead_time"] = zero_in_lt
    plan["min_projected_inventory"] = min_closing
    plan["next_review_trigger_week"] = pd.array(next_trigger, dtype="Int64")
    plan["attention_rank"] = rank_attention(plan)
    plan["action"] = [
        recommended_action(st, trig)
        for st, trig in zip(plan["status"], plan["reorder_triggered"], strict=True)
    ]
    first_po_week = data.purchase_orders.groupby("sku")["due_week"].min()
    plan["next_po_week"] = pd.array(plan["sku"].map(first_po_week), dtype="Int64")

    # 5. Historical policy comparison on the final weeks (no look-ahead).
    backtest = run_backtest(data, params) if include_backtest else BacktestResult.empty()

    return PlanResult(
        params=params,
        data=data,
        forecasts=forecasts,
        plan=plan.sort_values("sku").reset_index(drop=True),
        projections=projections,
        backtest=backtest,
        portfolio_wape=portfolio_wape(forecasts),
    )
