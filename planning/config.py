"""Planning parameters: the small set of business assumptions that drive every calculation.

The defaults reproduce the Excel validation workbook exactly. Changing a parameter here
(or from the app sidebar) recalculates the whole plan, including the backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True)
class PlanningParameters:
    """Global planning assumptions (all SKUs share them in V1)."""

    target_service_level: float = 0.95
    """Cycle service level: desired probability of not stocking out during a lead time."""

    annual_holding_rate: float = 0.20
    """Cost of holding one unit for a year, as a share of its unit cost (capital, storage, obsolescence)."""

    weeks_per_year: int = 52
    """Used to annualise the weekly forecast for the EOQ calculation."""

    excess_weeks_of_cover: float = 12.0
    """Inventory position above this many weeks of forecast demand is flagged EXCESS STOCK."""

    ses_alpha: float = 0.30
    """Weight on the most recent actual in Simple Exponential Smoothing (fixed, not optimised)."""

    wape_tolerance: float = 0.01
    """If a simpler forecast method is within this many WAPE points of the best, the simpler one wins."""

    evaluation_weeks: int = 52
    """Number of most recent weeks used to score forecast methods and measure forecast error."""

    projection_weeks: int = 12
    """Length of the forward inventory projection."""

    backtest_weeks: int = 16
    """Number of final historical weeks replayed in the policy backtest."""

    baseline_weeks_of_stock: int = 4
    """Backtest baseline policy: order up to this many weeks of trailing 4-week average demand."""

    backtest_opening_cover_weeks: int = 6
    """Both backtest policies start with this many weeks of trailing 8-week average demand on hand."""

    def __post_init__(self) -> None:
        if not 0.5 <= self.target_service_level < 1.0:
            raise ValueError("target_service_level must be between 0.5 and 1.0 (exclusive)")
        if self.annual_holding_rate <= 0:
            raise ValueError("annual_holding_rate must be positive")
        if not 0 < self.ses_alpha <= 1:
            raise ValueError("ses_alpha must be in (0, 1]")
        if self.evaluation_weeks < 13:
            raise ValueError("evaluation_weeks must be at least 13")

    @property
    def z_value(self) -> float:
        """Safety factor: standard-normal quantile of the target service level (95% -> 1.645)."""
        return NormalDist().inv_cdf(self.target_service_level)


DEFAULT_PARAMETERS = PlanningParameters()
