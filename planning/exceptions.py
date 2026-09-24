"""Planning statuses and the plain-English reason behind each one.

Only four statuses, evaluated in priority order:

    STOCKOUT RISK     projected stock hits zero before a new order placed today could arrive
    REORDER REQUIRED  inventory position <= reorder point
    EXCESS STOCK      inventory position covers more than the excess threshold (weeks of cover)
    HEALTHY           none of the above

Every non-healthy SKU gets a reason built from its actual numbers, so the planner is told
*why* something needs attention rather than just seeing a coloured row.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd

from planning.config import PlanningParameters
from planning.projection import ProjectionResult


class Status(StrEnum):
    STOCKOUT_RISK = "STOCKOUT RISK"
    REORDER_REQUIRED = "REORDER REQUIRED"
    EXCESS_STOCK = "EXCESS STOCK"
    HEALTHY = "HEALTHY"

    @property
    def priority(self) -> int:
        return _PRIORITY[self]


_PRIORITY = {
    Status.STOCKOUT_RISK: 1,
    Status.REORDER_REQUIRED: 2,
    Status.EXCESS_STOCK: 3,
    Status.HEALTHY: 4,
}

STATUS_ORDER = [s.value for s in _PRIORITY]


def classify(
    *,
    zero_within_lead_time: bool,
    reorder_triggered: bool,
    weeks_of_cover: float,
    excess_threshold: float,
) -> Status:
    if zero_within_lead_time:
        return Status.STOCKOUT_RISK
    if reorder_triggered:
        return Status.REORDER_REQUIRED
    if weeks_of_cover > excess_threshold:
        return Status.EXCESS_STOCK
    return Status.HEALTHY


def _units(value: float) -> str:
    return f"{value:,.0f}"


def explain(row: pd.Series, projection: ProjectionResult, status: Status, params: PlanningParameters) -> str:
    """Compose the reason text from the SKU's own numbers."""
    ip = float(row["inventory_position"])
    rop = float(row["reorder_point"])
    woc = float(row["weeks_of_cover"])
    lead_time = int(row["lead_time_weeks"])
    order = int(row["recommended_order"])
    eoq = float(row["eoq"])
    case_pack = int(row["case_pack"])
    on_order = float(row["on_order"])
    backorders = float(row["backorders"])

    shortage_note = ""
    if ip < 0:
        shortage_note = (
            f" Inventory position is negative: backorders of {_units(backorders)} units exceed "
            f"stock on hand and on order by {_units(-ip)} units."
        )

    if status is Status.STOCKOUT_RISK:
        zero_week = projection.first_zero_week
        text = (
            f"Projected inventory reaches zero in week {zero_week}, before a new order placed now "
            f"could arrive (week {lead_time + 1})."
        )
        if bool(row["reorder_triggered"]):
            text += (
                f" Inventory position of {_units(ip)} units is at or below the reorder point of {_units(rop)}, "
                f"so an order of {_units(order)} units is recommended (EOQ {_units(eoq)}, case pack {case_pack}), "
                f"but it cannot arrive in time: expedite supply or manage the shortfall."
            )
        else:
            due_weeks = sorted(
                int(w) for w in projection.table.loc[projection.table["existing_po_receipt"] > 0, "week"]
            )
            due_text = f" due in week {due_weeks[0]}" if due_weeks else ""
            text += (
                f" No new order is triggered because inventory position of {_units(ip)} units is above the "
                f"reorder point of {_units(rop)}, but the open PO of {_units(on_order)} units{due_text} arrives "
                f"too late: expedite the open PO."
            )
        return text + shortage_note

    if status is Status.REORDER_REQUIRED:
        return (
            f"Inventory position of {_units(ip)} units is {_units(rop - ip)} units below the reorder point of "
            f"{_units(rop)} units. Replenishment is required. EOQ recommends approximately {_units(eoq)} units, "
            f"rounded to {_units(order)} (case pack {case_pack})."
        ) + shortage_note

    if status is Status.EXCESS_STOCK:
        return (
            f"Inventory position represents {woc:.1f} weeks of expected demand, above the "
            f"{params.excess_weeks_of_cover:g}-week excess-stock threshold. No replenishment is triggered."
        )

    return (
        f"Inventory position of {_units(ip)} units is above the reorder point of {_units(rop)} units and covers "
        f"{woc:.1f} weeks of forecast demand. No order needed now."
    )


ACTIONS = {
    "ORDER_AND_EXPEDITE": "Order now + expedite",
    "EXPEDITE_PO": "Expedite open PO",
    "PLACE_ORDER": "Place order",
    "HOLD": "Hold: no reorder",
    "NONE": "No action",
}


def recommended_action(status: str, reorder_triggered: bool) -> str:
    """The planner's action this week, in words.

    A stockout-risk SKU needs expediting either way; whether a new order is *also* placed depends on the
    reorder trigger. Keeping "expedite the open PO" separate from "place an order" matters because a SKU can
    be at stockout risk while its inventory position is comfortably above the reorder point (the PO lands late).
    """
    if status == Status.STOCKOUT_RISK.value:
        return ACTIONS["ORDER_AND_EXPEDITE"] if reorder_triggered else ACTIONS["EXPEDITE_PO"]
    if status == Status.REORDER_REQUIRED.value:
        return ACTIONS["PLACE_ORDER"]
    if status == Status.EXCESS_STOCK.value:
        return ACTIONS["HOLD"]
    return ACTIONS["NONE"]


def rank_attention(table: pd.DataFrame) -> pd.Series:
    """1 = most urgent. Stockout risk first (lowest cover first), then reorder, then excess (highest cover first)."""
    signed_cover = table["inventory_position"] / table["weekly_forecast"].replace(0, float("nan"))
    signed_cover = signed_cover.fillna(0.0)
    priority = table["status"].map({s.value: s.priority for s in Status})
    key = priority * 1000 + signed_cover.where(table["status"] != Status.EXCESS_STOCK.value, -signed_cover)
    return key.rank(method="first").astype(int)
