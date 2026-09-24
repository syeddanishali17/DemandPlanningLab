"""Forward inventory projection: Closing = Opening + Receipts - Forecast Demand, week by week.

Assumptions (stated in the UI as well):

* Week 1 starts on the snapshot date and opens with ``on_hand - backorders``.
* Receipts land at the *start* of a week, before that week's demand.
* Open purchase orders arrive in their due week; today's recommended order arrives in
  week ``lead_time + 1``.
* Demand is the flat weekly forecast.
* Closing inventory is **not floored at zero**: a negative value is the cumulative
  projected shortfall if nothing else is done.
* Only *today's* replenishment decision is included. Future weekly reviews, which
  would normally place further orders once the inventory position crosses the
  reorder point, are not simulated. The projection therefore answers "what happens
  if we take no further action", which is exactly what the stockout-risk flag needs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from planning.data import Scenario


@dataclass(frozen=True)
class ProjectionResult:
    table: pd.DataFrame
    """Per planning week: opening, receipts, forecast demand, closing, projected inventory position."""
    first_zero_week: int | None
    """First week whose closing inventory is at or below zero (None if never within the horizon)."""
    zero_within_lead_time: bool
    """True when stock runs out before a new order placed today could arrive."""
    min_closing: float
    next_review_trigger_week: int | None
    """First week whose projected inventory position is at or below the reorder point (informational)."""


def project_inventory(
    *,
    on_hand: float,
    backorders: float,
    weekly_forecast: float,
    lead_time_weeks: int,
    reorder_point: float,
    open_orders: pd.DataFrame,
    recommended_order: int,
    horizon_weeks: int,
    scenario: Scenario | None = None,
) -> ProjectionResult:
    """Project one SKU forward over ``horizon_weeks``.

    ``open_orders`` needs the columns ``quantity`` and ``due_week`` (1 = week starting
    on the snapshot date); any number of open POs per SKU is supported.
    """
    existing_receipts = {w: 0.0 for w in range(1, horizon_weeks + 1)}
    for _, po in open_orders.iterrows():
        week = int(po["due_week"])
        if 1 <= week <= horizon_weeks:
            existing_receipts[week] += float(po["quantity"])

    new_order_week = lead_time_weeks + 1 if recommended_order > 0 else None
    on_order_outstanding = float(open_orders["quantity"].sum()) + float(recommended_order)

    rows = []
    opening = float(on_hand) - float(backorders)
    for week in range(1, horizon_weeks + 1):
        existing = existing_receipts[week]
        new = float(recommended_order) if week == new_order_week else 0.0
        closing = opening + existing + new - weekly_forecast
        on_order_outstanding -= existing + new
        rows.append(
            {
                "week": week,
                "week_start": scenario.week_start(week) if scenario else None,
                "opening_inventory": opening,
                "existing_po_receipt": existing,
                "new_order_receipt": new,
                "forecast_demand": weekly_forecast,
                "closing_inventory": closing,
                "projected_inventory_position": closing + on_order_outstanding,
            }
        )
        opening = closing

    table = pd.DataFrame(rows)
    at_or_below_zero = table.loc[table["closing_inventory"] <= 0, "week"]
    first_zero = int(at_or_below_zero.iloc[0]) if not at_or_below_zero.empty else None
    at_rop = table.loc[table["projected_inventory_position"] <= reorder_point, "week"]
    next_trigger = int(at_rop.iloc[0]) if not at_rop.empty else None

    return ProjectionResult(
        table=table,
        first_zero_week=first_zero,
        zero_within_lead_time=first_zero is not None and first_zero <= lead_time_weeks,
        min_closing=float(table["closing_inventory"].min()),
        next_review_trigger_week=next_trigger,
    )
