"""UI smoke tests: every chart builds for every SKU, and the plan runs at the parameter extremes.

These do not render Streamlit; they exercise the chart and text builders the pages call so a
user clicking through every SKU cannot hit an exception.
"""

import plotly.graph_objects as go
import pytest

from planning.backtest import BASELINE, POLICY_LABELS, PROPOSED
from planning.config import PlanningParameters
from planning.pipeline import run_plan
from ui.charts import (
    backtest_sku_chart,
    backtest_tradeoff_chart,
    cover_strip_chart,
    demand_forecast_chart,
    eoq_cost_chart,
    forecast_error_chart,
    method_comparison_chart,
    orders_by_supplier_chart,
    portfolio_demand_chart,
    projection_chart,
    status_donut_chart,
    value_by_status_chart,
)
from ui.components import status_badge
from ui.theme import STATUS_STYLE


def test_portfolio_charts_build(result):
    assert isinstance(cover_strip_chart(result.plan, result.params.excess_weeks_of_cover), go.Figure)
    assert isinstance(value_by_status_chart(result.plan), go.Figure)
    assert isinstance(backtest_tradeoff_chart(result.backtest.sku_summary, result.plan), go.Figure)
    assert isinstance(portfolio_demand_chart(result.forecasts, result.data.scenario), go.Figure)
    assert isinstance(status_donut_chart(result.status_counts()), go.Figure)
    assert isinstance(orders_by_supplier_chart(result.plan), go.Figure)


def test_every_sku_renders_in_the_deep_dive_and_backtest(result):
    scenario = result.data.scenario
    for sku in result.data.skus:
        row = result.sku_plan(sku)
        fc = result.forecasts[sku]
        proj = result.projections[sku]
        demand_forecast_chart(fc, scenario)
        method_comparison_chart(fc)
        forecast_error_chart(fc, scenario)
        eoq_cost_chart(
            float(row["annual_demand"]),
            float(row["ordering_cost_eur"]),
            float(row["holding_cost_per_unit"]),
            float(row["eoq"]),
            int(row["recommended_order"]),
        )
        projection_chart(
            proj,
            safety_stock=float(row["safety_stock"]),
            reorder_point=float(row["reorder_point"]),
            lead_time_weeks=int(row["lead_time_weeks"]),
            scenario=scenario,
        )
        backtest_sku_chart(result.backtest.sku_detail(sku), POLICY_LABELS[BASELINE], POLICY_LABELS[PROPOSED])
        assert row["status"] in STATUS_STYLE
        assert "dp-badge" in status_badge(row["status"])
        assert len(row["reason"]) > 40


@pytest.mark.parametrize(
    "tsl,holding,excess",
    [(0.90, 0.10, 8.0), (0.99, 0.40, 20.0), (0.975, 0.25, 12.0)],
)
def test_plan_runs_at_parameter_extremes(data, tsl, holding, excess):
    params = PlanningParameters(
        target_service_level=tsl, annual_holding_rate=holding, excess_weeks_of_cover=excess
    )
    res = run_plan(data, params)
    assert len(res.plan) == 48
    assert res.plan["recommended_order"].ge(0).all()
    assert res.plan["weeks_of_cover"].ge(0).all()
    assert set(res.plan["status"]) <= set(STATUS_STYLE)
    assert 0 < res.backtest.metric(PROPOSED, "fill_rate") <= 1


def test_higher_service_level_means_more_safety_stock(data):
    low = run_plan(data, PlanningParameters(target_service_level=0.90), include_backtest=False).plan
    high = run_plan(data, PlanningParameters(target_service_level=0.99), include_backtest=False).plan
    assert (high["safety_stock"] > low["safety_stock"]).all()
    assert (high["reorder_point"] > low["reorder_point"]).all()
    assert high["eoq"].equals(low["eoq"])  # EOQ does not depend on the service level


def test_higher_holding_rate_means_smaller_eoq(data):
    cheap = run_plan(data, PlanningParameters(annual_holding_rate=0.10), include_backtest=False).plan
    dear = run_plan(data, PlanningParameters(annual_holding_rate=0.40), include_backtest=False).plan
    assert (dear["eoq"] < cheap["eoq"]).all()
