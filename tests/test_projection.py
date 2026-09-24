"""Forward projection on small hand-computed cases."""

import pandas as pd
import pytest

from planning.projection import project_inventory


def _orders(*items: tuple[int, int]) -> pd.DataFrame:
    return pd.DataFrame({"quantity": [q for q, _ in items], "due_week": [w for _, w in items]})


def test_projection_matches_hand_calculation():
    # BTH-002 from the workbook: on hand 75, PO 380 due week 1, forecast 146.25, LT 3, order 760.
    proj = project_inventory(
        on_hand=75,
        backorders=0,
        weekly_forecast=146.25,
        lead_time_weeks=3,
        reorder_point=478.8,
        open_orders=_orders((380, 1)),
        recommended_order=760,
        horizon_weeks=12,
    )
    closing = proj.table.set_index("week")["closing_inventory"]
    assert closing[1] == pytest.approx(75 + 380 - 146.25)  # 308.75
    assert closing[3] == pytest.approx(16.25)
    assert closing[4] == pytest.approx(16.25 + 760 - 146.25)  # new order lands week LT + 1 = 4
    assert closing[12] == pytest.approx(-540)
    assert proj.first_zero_week == 9
    assert proj.zero_within_lead_time is False


def test_opening_inventory_is_net_of_backorders_and_zero_within_lead_time_flags_risk():
    proj = project_inventory(
        on_hand=0,
        backorders=36,
        weekly_forecast=95.125,
        lead_time_weeks=2,
        reorder_point=216.7,
        open_orders=_orders(),
        recommended_order=366,
        horizon_weeks=12,
    )
    assert proj.table["opening_inventory"].iloc[0] == -36
    assert proj.first_zero_week == 1
    assert proj.zero_within_lead_time is True
    assert proj.table.loc[proj.table["week"] == 3, "new_order_receipt"].iloc[0] == 366


def test_multiple_open_orders_are_all_received():
    proj = project_inventory(
        on_hand=10,
        backorders=0,
        weekly_forecast=5,
        lead_time_weeks=2,
        reorder_point=15,
        open_orders=_orders((20, 2), (30, 2), (40, 5)),
        recommended_order=0,
        horizon_weeks=6,
    )
    receipts = proj.table.set_index("week")["existing_po_receipt"]
    assert receipts[2] == 50
    assert receipts[5] == 40
    assert receipts.sum() == 90
    assert proj.table["new_order_receipt"].sum() == 0


def test_projected_inventory_position_and_next_review_trigger():
    # No order today; stock 100, forecast 20/week, ROP 50 -> IP crosses 50 at the end of week 3 (100-60=40).
    proj = project_inventory(
        on_hand=100,
        backorders=0,
        weekly_forecast=20,
        lead_time_weeks=1,
        reorder_point=50,
        open_orders=_orders(),
        recommended_order=0,
        horizon_weeks=8,
    )
    ip = proj.table.set_index("week")["projected_inventory_position"]
    assert ip[1] == 80 and ip[3] == 40
    assert proj.next_review_trigger_week == 3


def test_orders_due_beyond_the_horizon_are_ignored_for_receipts():
    proj = project_inventory(
        on_hand=10,
        backorders=0,
        weekly_forecast=1,
        lead_time_weeks=1,
        reorder_point=0,
        open_orders=_orders((99, 20)),
        recommended_order=0,
        horizon_weeks=12,
    )
    assert proj.table["existing_po_receipt"].sum() == 0
    # ...but they still count in the projected inventory position.
    assert proj.table["projected_inventory_position"].iloc[0] == pytest.approx(10 - 1 + 99)
