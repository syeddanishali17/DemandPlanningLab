"""Inventory policy formulas checked against the textbook examples in the project brief."""

import pandas as pd
import pytest

from planning.config import PlanningParameters
from planning.inventory import (
    annual_demand,
    build_replenishment_table,
    economic_order_quantity,
    holding_cost_per_unit,
    inventory_position,
    lead_time_demand,
    recommended_order,
    reorder_point,
    reorder_triggered,
    round_up_to_case_pack,
    safety_stock,
    weeks_of_cover,
)


def test_z_value_at_95_percent():
    assert PlanningParameters(target_service_level=0.95).z_value == pytest.approx(1.645, abs=1e-3)
    assert PlanningParameters(target_service_level=0.90).z_value == pytest.approx(1.282, abs=1e-3)
    assert PlanningParameters(target_service_level=0.99).z_value == pytest.approx(2.326, abs=1e-3)


def test_safety_stock_example():
    # z 1.645, error SD 35, lead time 3 weeks -> 1.645 x 35 x 1.7321 = 99.72
    assert safety_stock(1.645, 35, 3) == pytest.approx(99.72, abs=0.01)


def test_safety_stock_grows_with_uncertainty_and_lead_time():
    assert safety_stock(1.645, 70, 3) == pytest.approx(2 * safety_stock(1.645, 35, 3))
    assert safety_stock(1.645, 35, 12) == pytest.approx(2 * safety_stock(1.645, 35, 3))  # sqrt(4) = 2


def test_lead_time_demand_and_reorder_point_examples():
    assert lead_time_demand(100, 3) == 300
    assert reorder_point(300, 90) == 390


def test_inventory_position_includes_on_order_and_subtracts_backorders():
    assert inventory_position(75, 380, 0) == 455
    assert inventory_position(0, 0, 36) == -36


def test_weeks_of_cover_never_negative_and_safe_on_zero_forecast():
    assert weeks_of_cover(600, 50) == 12
    assert weeks_of_cover(-36, 95) == 0.0
    assert weeks_of_cover(100, 0) == 0.0


def test_eoq_example_from_brief():
    # Annual demand 5,200, ordering cost 40, unit cost 20, holding rate 20 % -> EOQ ~ 322
    h = holding_cost_per_unit(20, 0.20)
    assert h == pytest.approx(4.0)
    assert annual_demand(100, 52) == 5200
    assert economic_order_quantity(5200, 40, h) == pytest.approx(322.49, abs=0.01)


def test_eoq_zero_demand_gives_zero_and_rejects_zero_holding_cost():
    assert economic_order_quantity(0, 40, 4) == 0
    with pytest.raises(ValueError):
        economic_order_quantity(5200, 40, 0)


def test_case_pack_rounding_rounds_up_to_full_cases():
    assert round_up_to_case_pack(755.23, 20) == 760
    assert round_up_to_case_pack(760, 20) == 760  # exact multiple is unchanged
    assert round_up_to_case_pack(0, 20) == 0
    assert round_up_to_case_pack(1, 6) == 6


def test_reorder_decision():
    assert reorder_triggered(455, 478.8) is True
    assert reorder_triggered(479, 478.8) is False
    assert reorder_triggered(390, 390) is True  # at the ROP counts as triggered
    assert recommended_order(True, 760) == 760
    assert recommended_order(False, 760) == 0


def _table(on_hand: int, on_order: int, backorders: int = 0) -> pd.DataFrame:
    master = pd.DataFrame(
        {
            "sku": ["X"],
            "lead_time_weeks": [3],
            "ordering_cost_eur": [45.0],
            "unit_cost_eur": [6.0],
            "case_pack": [20],
            "on_hand": [on_hand],
            "on_order": [on_order],
            "backorders": [backorders],
        }
    )
    forecast = pd.DataFrame(
        {
            "sku": ["X"],
            "weekly_forecast": [146.25],
            "error_sd": [14.0635],
            "wape": [0.07],
            "bias": [0.0],
            "forecast_method": ["MA4"],
        }
    )
    return build_replenishment_table(master, forecast, PlanningParameters())


def test_on_order_stock_prevents_a_duplicate_order():
    """The classic bug: ignoring stock already on order recommends ordering twice."""
    with_po = _table(on_hand=75, on_order=380).iloc[0]
    assert with_po["inventory_position"] == 455
    assert with_po["reorder_point"] == pytest.approx(478.82, abs=0.01)
    assert with_po["recommended_order"] == 760  # BTH-002 example from the workbook

    bigger_po = _table(on_hand=75, on_order=500).iloc[0]
    assert bigger_po["inventory_position"] == 575
    assert bigger_po["recommended_order"] == 0  # the open PO already covers the reorder point


def test_negative_inventory_position_is_reported_as_shortage_not_negative_cover():
    row = _table(on_hand=0, on_order=0, backorders=36).iloc[0]
    assert row["inventory_position"] == -36
    assert row["weeks_of_cover"] == 0.0
    assert row["shortage_units"] == 36
    assert row["reorder_triggered"]
