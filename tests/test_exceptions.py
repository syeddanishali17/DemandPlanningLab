"""Status priority and plain-English reasons."""

import pandas as pd

from planning.config import PlanningParameters
from planning.exceptions import Status, classify, explain, rank_attention, recommended_action
from planning.projection import project_inventory


def test_status_priority_order():
    kw = dict(excess_threshold=12)
    assert (
        classify(zero_within_lead_time=True, reorder_triggered=True, weeks_of_cover=1, **kw)
        is Status.STOCKOUT_RISK
    )
    assert (
        classify(zero_within_lead_time=True, reorder_triggered=False, weeks_of_cover=20, **kw)
        is Status.STOCKOUT_RISK
    )
    assert (
        classify(zero_within_lead_time=False, reorder_triggered=True, weeks_of_cover=1, **kw)
        is Status.REORDER_REQUIRED
    )
    assert (
        classify(zero_within_lead_time=False, reorder_triggered=False, weeks_of_cover=12.1, **kw)
        is Status.EXCESS_STOCK
    )
    assert (
        classify(zero_within_lead_time=False, reorder_triggered=False, weeks_of_cover=12.0, **kw)
        is Status.HEALTHY
    )
    assert (
        classify(zero_within_lead_time=False, reorder_triggered=False, weeks_of_cover=5, **kw)
        is Status.HEALTHY
    )


def _row(**overrides) -> pd.Series:
    base = {
        "inventory_position": 455.0,
        "reorder_point": 478.8,
        "weeks_of_cover": 3.1,
        "lead_time_weeks": 3,
        "recommended_order": 760,
        "eoq": 755.2,
        "case_pack": 20,
        "on_order": 380.0,
        "backorders": 0.0,
        "reorder_triggered": True,
        "weekly_forecast": 146.25,
    }
    base.update(overrides)
    return pd.Series(base)


def _projection(row: pd.Series, open_orders=None):
    orders = open_orders if open_orders is not None else pd.DataFrame({"quantity": [], "due_week": []})
    return project_inventory(
        on_hand=row["inventory_position"] - row["on_order"] + row["backorders"],
        backorders=row["backorders"],
        weekly_forecast=row["weekly_forecast"],
        lead_time_weeks=int(row["lead_time_weeks"]),
        reorder_point=row["reorder_point"],
        open_orders=orders,
        recommended_order=int(row["recommended_order"]),
        horizon_weeks=12,
    )


def test_reorder_reason_uses_actual_numbers():
    row = _row()
    text = explain(row, _projection(row), Status.REORDER_REQUIRED, PlanningParameters())
    assert "455 units is 24 units below the reorder point of 479" in text
    assert "approximately 755 units, rounded to 760 (case pack 20)" in text


def test_stockout_reason_mentions_expediting_open_po_when_no_order_is_triggered():
    row = _row(
        inventory_position=334.0,
        reorder_point=242.2,
        on_order=276.0,
        recommended_order=0,
        reorder_triggered=False,
        lead_time_weeks=6,
        weekly_forecast=36.5,
    )
    proj = _projection(row, pd.DataFrame({"quantity": [276], "due_week": [6]}))
    text = explain(row, proj, Status.STOCKOUT_RISK, PlanningParameters())
    assert "reaches zero in week 2" in text
    assert "expedite the open PO" in text
    assert "due in week 6" in text


def test_negative_inventory_position_is_explained_explicitly():
    row = _row(
        inventory_position=-99.0,
        reorder_point=236.6,
        on_order=0.0,
        backorders=99.0,
        recommended_order=624,
        weekly_forecast=189.25,
        lead_time_weeks=1,
    )
    text = explain(row, _projection(row), Status.STOCKOUT_RISK, PlanningParameters())
    assert "backorders of 99 units exceed" in text
    assert "expedite supply" in text


def test_excess_and_healthy_reasons():
    params = PlanningParameters()
    row = _row(weeks_of_cover=14.0, reorder_triggered=False, recommended_order=0)
    assert "14.0 weeks of expected demand, above the 12-week" in explain(
        row, _projection(row), Status.EXCESS_STOCK, params
    )
    row = _row(
        inventory_position=236.0,
        reorder_point=141.3,
        weeks_of_cover=3.9,
        reorder_triggered=False,
        recommended_order=0,
    )
    assert "covers 3.9 weeks" in explain(row, _projection(row), Status.HEALTHY, params)


def test_attention_rank_orders_by_status_then_cover():
    table = pd.DataFrame(
        {
            "status": [
                "HEALTHY",
                "EXCESS STOCK",
                "STOCKOUT RISK",
                "REORDER REQUIRED",
                "EXCESS STOCK",
                "STOCKOUT RISK",
            ],
            "inventory_position": [200, 600, -50, 80, 900, 40],
            "weekly_forecast": [50, 50, 50, 50, 50, 50],
        }
    )
    ranks = rank_attention(table).tolist()
    # stockout with the most negative cover first, then the other stockout, reorder, excess (highest cover first), healthy
    assert ranks == [6, 5, 1, 3, 4, 2]


def test_recommended_action_separates_expediting_from_ordering():
    assert recommended_action("STOCKOUT RISK", True) == "Order now + expedite"
    assert recommended_action("STOCKOUT RISK", False) == "Expedite open PO"
    assert recommended_action("REORDER REQUIRED", True) == "Place order"
    assert recommended_action("EXCESS STOCK", False) == "Hold: no reorder"
    assert recommended_action("HEALTHY", False) == "No action"


def test_ele003_is_an_expedite_case_not_an_order(result):
    row = result.sku_plan("ELE-003")
    assert row["status"] == "STOCKOUT RISK"
    assert row["action"] == "Expedite open PO"
    assert row["recommended_order"] == 0
    assert row["first_zero_week"] == 2 and row["next_po_week"] == 6
