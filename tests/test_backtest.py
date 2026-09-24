"""Backtest invariants: unit conservation, no look-ahead, and Excel-style rounding."""

import numpy as np
import pandas as pd
import pytest

from planning.backtest import BASELINE, PROPOSED, _excel_round, run_backtest
from planning.config import PlanningParameters
from planning.data import PlanningData


def test_excel_round_is_half_away_from_zero():
    assert _excel_round(355.5) == 356
    assert _excel_round(356.5) == 357  # Python's round() would give 356
    assert _excel_round(2.4) == 2


def test_units_are_conserved(result):
    detail = result.backtest.detail
    assert np.allclose(detail["actual_demand"], detail["sales"] + detail["lost_sales"])
    assert (detail["closing_stock"] >= 0).all()
    assert (detail["sales"] <= detail["stock_start"]).all()


def test_both_policies_start_from_the_same_position(result):
    detail = result.backtest.detail
    first = detail[detail["week"] == result.backtest.weeks[0]]
    a = first[first["policy"] == BASELINE].set_index("sku")["stock_start"]
    b = first[first["policy"] == PROPOSED].set_index("sku")["stock_start"]
    pd.testing.assert_series_equal(a, b, check_names=False)
    assert (first["on_order"] == 0).all()


def test_summary_metrics_are_consistent_with_detail(result):
    bt = result.backtest
    for policy in (BASELINE, PROPOSED):
        d = bt.detail[bt.detail["policy"] == policy]
        assert bt.metric(policy, "fill_rate") == pytest.approx(d["sales"].sum() / d["actual_demand"].sum())
        assert bt.metric(policy, "stockout_weeks") == (d["lost_sales"] > 0).sum()
        assert bt.metric(policy, "number_of_orders") == (d["order"] > 0).sum()
        assert bt.metric(policy, "average_inventory_units") == pytest.approx(d["closing_stock"].sum() / 16)


def test_no_look_ahead_decisions_do_not_depend_on_later_demand(
    data: PlanningData, params: PlanningParameters
):
    """Orders placed in week t must be identical when demand after week t is changed."""
    base = run_backtest(data, params)
    cutoff = 96  # inside the replay window 89-104

    altered_history = data.demand_history.copy()
    mask = altered_history["week"] > cutoff
    altered_history.loc[mask, "demand"] = altered_history.loc[mask, "demand"] * 5 + 100
    altered = PlanningData(
        scenario=data.scenario,
        sku_master=data.sku_master,
        suppliers=data.suppliers,
        demand_history=altered_history,
        purchase_orders=data.purchase_orders,
    )
    changed = run_backtest(altered, params)

    key = ["sku", "policy", "week"]
    before = base.detail[base.detail["week"] <= cutoff].set_index(key)[["order", "forecast", "reorder_point"]]
    after = changed.detail[changed.detail["week"] <= cutoff].set_index(key)[
        ["order", "forecast", "reorder_point"]
    ]
    pd.testing.assert_frame_equal(before, after)

    # ...and the altered later weeks really did change something, so the test is not vacuous.
    assert not base.detail.equals(changed.detail)


def test_calibration_window_precedes_the_replay(result):
    start, _ = result.backtest.weeks
    assert result.backtest.calibration_window[1] == start - 1
