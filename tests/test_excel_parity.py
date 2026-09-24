"""Excel parity: the Python engine must reproduce the validation workbook for every SKU.

The fixtures in ``tests/fixtures/excel_reference`` were extracted from
``docs/validation/Demand_Inventory_Planning_Model_V1.xlsx`` with
``scripts/extract_excel_reference.py``. These tests are the evidence behind the claim that
the planning logic was prototyped in Excel and then implemented and validated in Python.
"""

import numpy as np
import pandas as pd
import pytest

from planning.backtest import BASELINE, PROPOSED
from planning.forecasting import METHODS
from tests.conftest import FIXTURES, excel_reference

TOL = 1e-9


# ------------------------------------------------------------------ forecasting
def test_forecast_metrics_and_selection_match_excel_for_all_skus(result):
    ref = excel_reference("forecast").set_index("sku")
    assert len(ref) == 48
    for sku, fc in result.forecasts.items():
        row = ref.loc[sku]
        assert fc.selected_method == row["selected_method"], sku
        assert fc.weekly_forecast == pytest.approx(row["weekly_forecast"], abs=TOL), sku
        assert fc.wape == pytest.approx(row["wape"], abs=TOL), sku
        assert fc.bias == pytest.approx(row["bias"], abs=TOL), sku
        assert fc.error_sd == pytest.approx(row["error_sd"], abs=TOL), sku
        for method in METHODS:
            m = method.lower()
            assert fc.method_scores.loc[method, "wape"] == pytest.approx(row[f"wape_{m}"], abs=TOL), (
                sku,
                method,
            )
            assert fc.method_scores.loc[method, "bias"] == pytest.approx(row[f"bias_{m}"], abs=TOL), (
                sku,
                method,
            )
            assert fc.method_scores.loc[method, "error_sd"] == pytest.approx(row[f"sd_{m}"], abs=TOL), (
                sku,
                method,
            )
            assert fc.method_scores.loc[method, "next_forecast"] == pytest.approx(
                row[f"fcst_{m}"], abs=TOL
            ), (sku, method)


def test_portfolio_wape_matches_excel(result):
    expected = float((FIXTURES / "portfolio_wape.txt").read_text())
    assert result.portfolio_wape == pytest.approx(expected, abs=TOL)


# ------------------------------------------------------------------ replenishment plan
NUMERIC_PLAN_COLUMNS = [
    "safety_stock",
    "lead_time_demand",
    "reorder_point",
    "inventory_position",
    "annual_demand",
    "holding_cost_per_unit",
    "eoq",
    "eoq_rounded",
    "recommended_order",
    "on_hand_value",
    "weeks_of_cover_on_hand",
    "attention_rank",
]


def test_replenishment_plan_matches_excel_for_all_skus(result):
    ref = excel_reference("replenishment_plan").set_index("sku")
    plan = result.plan.set_index("sku")
    assert len(plan) == 48
    for sku in plan.index:
        p, x = plan.loc[sku], ref.loc[sku]
        for col in NUMERIC_PLAN_COLUMNS:
            assert float(p[col]) == pytest.approx(float(x[col]), abs=TOL), (sku, col)
        assert p["reorder_triggered"] == (x["reorder_trigger"] == "YES"), sku
        assert p["zero_within_lead_time"] == (x["zero_within_lead_time"] == "YES"), sku
        assert p["status"] == x["status"], sku
        excel_zero = (
            None if str(x["first_zero_week"]) in ("None", "nan") else int(float(x["first_zero_week"]))
        )
        python_zero = None if pd.isna(p["first_zero_week"]) else int(p["first_zero_week"])
        assert python_zero == excel_zero, sku


def test_weeks_of_cover_matches_excel_except_negative_positions_are_floored(result):
    """Excel shows a negative cover when backorders exceed stock; Python shows 0 and a separate shortage."""
    ref = excel_reference("replenishment_plan").set_index("sku")
    plan = result.plan.set_index("sku")
    for sku in plan.index:
        excel_cover = float(ref.loc[sku, "weeks_of_cover_ip"])
        assert plan.loc[sku, "weeks_of_cover"] == pytest.approx(max(excel_cover, 0.0), abs=TOL), sku
        if excel_cover < 0:
            assert plan.loc[sku, "shortage_units"] > 0


def test_status_counts_match_excel(result):
    assert result.status_counts() == {
        "STOCKOUT RISK": 6,
        "REORDER REQUIRED": 11,
        "EXCESS STOCK": 8,
        "HEALTHY": 23,
    }


# ------------------------------------------------------------------ projection
def test_twelve_week_projection_matches_excel_for_all_skus(result):
    ref = excel_reference("projection")
    columns = ["existing_po_receipt", "new_order_receipt", "forecast_demand", "closing_inventory"]
    for sku, proj in result.projections.items():
        expected = ref.loc[ref["sku"] == sku].set_index("week")[columns].astype(float)
        actual = proj.table.set_index("week")[columns].astype(float)
        pd.testing.assert_frame_equal(actual, expected, check_names=False, atol=TOL, rtol=0)


# ------------------------------------------------------------------ backtest
def test_backtest_portfolio_metrics_match_excel(result):
    ref = excel_reference("backtest_totals").set_index("metric")
    for metric in ref.index:
        assert result.backtest.metric(BASELINE, metric) == pytest.approx(
            ref.loc[metric, "baseline"], abs=1e-6
        ), metric
        assert result.backtest.metric(PROPOSED, metric) == pytest.approx(
            ref.loc[metric, "proposed"], abs=1e-6
        ), metric


def test_backtest_weekly_detail_matches_excel_for_both_policies(result):
    ref = excel_reference("backtest_detail").set_index(["sku", "week"])
    detail = result.backtest.detail
    mapping = [
        ("receipts", "receipts"),
        ("stock_start", "stock_start"),
        ("on_order", "on_order"),
        ("inventory_position", "inventory_position"),
        ("order", "order"),
        ("sales", "sales"),
        ("lost_sales", "lost"),
        ("closing_stock", "closing"),
    ]
    for policy, prefix in ((BASELINE, "a_"), (PROPOSED, "b_")):
        rows = detail.loc[detail["policy"] == policy].set_index(["sku", "week"])
        assert len(rows) == 768
        for py_col, xl_col in mapping:
            expected = ref[prefix + xl_col].reindex(rows.index).to_numpy(dtype=float)
            np.testing.assert_allclose(
                rows[py_col].to_numpy(dtype=float), expected, atol=TOL, err_msg=f"{policy}:{py_col}"
            )
    proposed = detail.loc[detail["policy"] == PROPOSED].set_index(["sku", "week"])
    for py_col, xl_col in (
        ("forecast", "b_forecast"),
        ("safety_stock", "b_safety_stock"),
        ("reorder_point", "b_reorder_point"),
        ("eoq", "b_eoq"),
    ):
        np.testing.assert_allclose(
            proposed[py_col].to_numpy(dtype=float),
            ref[xl_col].reindex(proposed.index).to_numpy(dtype=float),
            atol=TOL,
        )
