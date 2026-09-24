"""Inventory policy calculations: safety stock, reorder point, inventory position, EOQ and the order decision.

Every step is a small pure function so it can be tested with hand-computed examples. The
formulas are exactly those validated in the Excel workbook:

    Safety Stock          = z x Forecast Error SD x sqrt(Lead Time)
    Lead-Time Demand      = Weekly Forecast x Lead Time
    Reorder Point         = Lead-Time Demand + Safety Stock            ("WHEN to order")
    Inventory Position    = On Hand + On Order - Backorders
    Annual Demand         = Weekly Forecast x 52
    Holding Cost per Unit = Unit Cost x Annual Holding Rate
    EOQ                   = sqrt(2 x Annual Demand x Ordering Cost / Holding Cost per Unit)   ("HOW MUCH")
    Recommended Order     = EOQ rounded up to the case pack if IP <= ROP, else 0
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from planning.config import PlanningParameters


# ------------------------------------------------------------------ scalar building blocks
def safety_stock(z: float, forecast_error_sd: float, lead_time_weeks: float) -> float:
    """Buffer against forecast error over the lead time (fixed lead time, independent weekly errors)."""
    return z * forecast_error_sd * math.sqrt(lead_time_weeks)


def lead_time_demand(weekly_forecast: float, lead_time_weeks: float) -> float:
    """Expected demand while waiting for a new order to arrive."""
    return weekly_forecast * lead_time_weeks


def reorder_point(lead_time_demand_units: float, safety_stock_units: float) -> float:
    """Inventory position at or below which replenishment is triggered."""
    return lead_time_demand_units + safety_stock_units


def inventory_position(on_hand: float, on_order: float, backorders: float) -> float:
    """Stock available or already on its way, net of what is owed to customers."""
    return on_hand + on_order - backorders


def weeks_of_cover(quantity: float, weekly_forecast: float) -> float:
    """How many weeks ``quantity`` lasts at the forecast rate.

    A negative quantity (backorders exceed stock) is reported as 0 weeks of cover; the
    shortage itself is kept as a separate, explicit number rather than a negative
    "cover". A zero forecast also yields 0 to avoid division by zero.
    """
    if weekly_forecast <= 0:
        return 0.0
    return max(quantity, 0.0) / weekly_forecast


def annual_demand(weekly_forecast: float, weeks_per_year: int = 52) -> float:
    return weekly_forecast * weeks_per_year


def holding_cost_per_unit(unit_cost: float, annual_holding_rate: float) -> float:
    return unit_cost * annual_holding_rate


def economic_order_quantity(annual_demand_units: float, ordering_cost: float, holding_cost: float) -> float:
    """Order size that balances ordering cost against holding cost (classic Wilson EOQ)."""
    if holding_cost <= 0:
        raise ValueError("holding cost per unit must be positive")
    if annual_demand_units <= 0:
        return 0.0
    return math.sqrt(2.0 * annual_demand_units * ordering_cost / holding_cost)


def round_up_to_case_pack(quantity: float, case_pack: int) -> int:
    """Suppliers ship full cases: round up to the next multiple of the case pack."""
    if case_pack <= 0:
        raise ValueError("case pack must be positive")
    if quantity <= 0:
        return 0
    return int(math.ceil(quantity / case_pack - 1e-12) * case_pack)


def reorder_triggered(inventory_position_units: float, reorder_point_units: float) -> bool:
    return inventory_position_units <= reorder_point_units


def recommended_order(triggered: bool, eoq_rounded: int) -> int:
    return eoq_rounded if triggered else 0


# ------------------------------------------------------------------ table-level builder
def build_replenishment_table(
    sku_master: pd.DataFrame, forecast_summary: pd.DataFrame, params: PlanningParameters
) -> pd.DataFrame:
    """Apply the policy to every SKU. Input frames are joined on ``sku``.

    Returns one row per SKU with every intermediate value the planner (and the UI)
    needs to explain the decision. Status and reason are added separately by
    :mod:`planning.exceptions` because they also depend on the projection.
    """
    t = sku_master.merge(forecast_summary, on="sku", how="left", validate="one_to_one")
    z = params.z_value

    t["target_service_level"] = params.target_service_level
    t["z_value"] = z
    t["safety_stock"] = z * t["error_sd"] * np.sqrt(t["lead_time_weeks"])
    t["lead_time_demand"] = t["weekly_forecast"] * t["lead_time_weeks"]
    t["reorder_point"] = t["lead_time_demand"] + t["safety_stock"]

    t["inventory_position"] = t["on_hand"] + t["on_order"] - t["backorders"]
    t["shortage_units"] = (-t["inventory_position"]).clip(lower=0)
    t["weeks_of_cover"] = [
        weeks_of_cover(q, f) for q, f in zip(t["inventory_position"], t["weekly_forecast"], strict=True)
    ]
    t["weeks_of_cover_on_hand"] = [
        weeks_of_cover(q, f) for q, f in zip(t["on_hand"], t["weekly_forecast"], strict=True)
    ]

    t["annual_demand"] = t["weekly_forecast"] * params.weeks_per_year
    t["annual_holding_rate"] = params.annual_holding_rate
    t["holding_cost_per_unit"] = t["unit_cost_eur"] * params.annual_holding_rate
    t["eoq"] = [
        economic_order_quantity(d, oc, h)
        for d, oc, h in zip(
            t["annual_demand"], t["ordering_cost_eur"], t["holding_cost_per_unit"], strict=True
        )
    ]
    t["eoq_rounded"] = [round_up_to_case_pack(q, cp) for q, cp in zip(t["eoq"], t["case_pack"], strict=True)]
    t["reorder_triggered"] = t["inventory_position"] <= t["reorder_point"]
    t["recommended_order"] = np.where(t["reorder_triggered"], t["eoq_rounded"], 0).astype(int)
    t["recommended_order_value"] = t["recommended_order"] * t["unit_cost_eur"]
    t["on_hand_value"] = t["on_hand"] * t["unit_cost_eur"]
    t["new_order_receipt_week"] = np.where(t["recommended_order"] > 0, t["lead_time_weeks"] + 1, 0).astype(
        int
    )
    return t
