"""Accuracy metrics and the method-selection rule, checked with hand-computed examples."""

import math

import numpy as np
import pytest

from planning.metrics import bias, error_sd, select_method, wape


def test_wape_mini_example_from_brief():
    # actual 100, 0, 50 ; forecast 90, 10, 60 -> (10 + 10 + 10) / 150 = 20 %
    assert wape([100, 0, 50], [90, 10, 60]) == pytest.approx(0.20)


def test_wape_is_defined_with_zero_demand_weeks():
    # MAPE would divide by zero in week 2; WAPE does not.
    assert math.isfinite(wape([100, 0, 50], [90, 10, 60]))


def test_bias_sign_convention_forecast_minus_actual():
    # errors -10, +10, +10 on volume 150 -> +6.7 % (over-forecast)
    assert bias([100, 0, 50], [90, 10, 60]) == pytest.approx(10 / 150)
    assert bias([100, 100], [90, 90]) < 0  # under-forecasting is negative


def test_error_sd_is_sample_standard_deviation():
    # errors -8, 4, 10, -6 -> STDEV.S = 8.406...
    actual = [100, 100, 100, 100]
    forecast = [92, 104, 110, 94]
    assert error_sd(actual, forecast) == pytest.approx(np.std([-8, 4, 10, -6], ddof=1))


def test_metrics_ignore_weeks_without_a_forecast():
    assert wape([10, 20, 30], [np.nan, 20, 30]) == pytest.approx(0.0)


def test_select_method_prefers_simpler_within_tolerance():
    order = ("Naive", "MA4", "MA8", "SES")
    # MA8 is best, but MA4 is within 1 point -> MA4 wins; Naive is not within tolerance.
    assert select_method({"Naive": 0.136, "MA4": 0.106, "MA8": 0.096, "SES": 0.102}, 0.01, order) == "MA4"
    # With zero tolerance the best method wins outright.
    assert select_method({"Naive": 0.136, "MA4": 0.106, "MA8": 0.096, "SES": 0.102}, 0.0, order) == "MA8"
    # Exact tie -> simplest.
    assert select_method({"Naive": 0.10, "MA4": 0.10, "MA8": 0.10, "SES": 0.10}, 0.0, order) == "Naive"
