"""Forecast methods on tiny hand-checkable series, plus the walk-forward (no look-ahead) property."""

import numpy as np
import pandas as pd
import pytest

from planning.config import PlanningParameters
from planning.forecasting import (
    METHODS,
    forecast_sku,
    moving_average_forecast,
    naive_forecast,
    ses_forecast,
    walk_forward_table,
)

ACTUALS = np.array([100.0, 110.0, 90.0, 100.0, 120.0])


def test_naive_forecast_is_last_actual():
    out = naive_forecast(ACTUALS)
    assert np.isnan(out[0])
    assert out[1:5].tolist() == [100, 110, 90, 100]
    assert out[5] == 120  # next-week forecast


def test_moving_average_uses_only_prior_weeks():
    out = moving_average_forecast(ACTUALS, 4)
    assert np.isnan(out[:4]).all()  # first forecast is for week 5
    assert out[4] == pytest.approx((100 + 110 + 90 + 100) / 4)  # = 100, the brief's example
    assert out[5] == pytest.approx((110 + 90 + 100 + 120) / 4)  # next week


def test_ses_recursion_matches_brief_example():
    # alpha 0.3, last actual 120, last forecast 100 -> 0.3 x 120 + 0.7 x 100 = 106
    out = ses_forecast(np.array([100.0, 120.0]), alpha=0.3)
    assert np.isnan(out[0])
    assert out[1] == 100  # F(2) = A(1)
    assert out[2] == pytest.approx(106)


def test_walk_forward_forecasts_never_use_future_actuals():
    """Changing week 6 onwards must not change any forecast made for weeks <= 6."""
    rng = np.random.default_rng(0)
    base = pd.Series(rng.integers(20, 80, size=30).astype(float), index=range(1, 31))
    altered = base.copy()
    altered.loc[6:] = rng.integers(500, 900, size=25)
    table_base = walk_forward_table(base, alpha=0.3)
    table_alt = walk_forward_table(altered, alpha=0.3)
    for method in METHODS:
        pd.testing.assert_series_equal(table_base.loc[:6, method], table_alt.loc[:6, method])


def test_forecast_sku_scores_every_method_and_selects_one():
    rng = np.random.default_rng(1)
    actuals = pd.Series(50 + rng.normal(0, 5, size=104).round(), index=range(1, 105))
    fc = forecast_sku("TEST", actuals, PlanningParameters())
    assert fc.evaluation_window == (53, 104)
    assert set(fc.method_scores.index) == set(METHODS)
    assert fc.selected_method in METHODS
    assert fc.method_scores["selected"].sum() == 1
    assert fc.weekly_forecast == pytest.approx(fc.method_scores.loc[fc.selected_method, "next_forecast"])
    assert len(fc.errors) == 52


def test_forecast_sku_window_end_hides_later_weeks():
    """Calibrating on an earlier window must not depend on the weeks after it."""
    rng = np.random.default_rng(2)
    actuals = pd.Series(50 + rng.normal(0, 5, size=104).round(), index=range(1, 105))
    altered = actuals.copy()
    altered.loc[89:] = 900
    a = forecast_sku("T", actuals, PlanningParameters(), window_end=88)
    b = forecast_sku("T", altered, PlanningParameters(), window_end=88)
    assert a.selected_method == b.selected_method
    assert a.error_sd == pytest.approx(b.error_sd)
    assert a.weekly_forecast == pytest.approx(b.weekly_forecast)
