"""Cached access to data and plan results, plus the sidebar parameters shared by every page."""

from __future__ import annotations

import streamlit as st

from planning.config import PlanningParameters
from planning.data import DataValidationError, PlanningData, load_planning_data
from planning.pipeline import PlanResult, run_plan

SERVICE_LEVEL_OPTIONS = [0.90, 0.92, 0.95, 0.975, 0.99]

# Parameter combinations already computed in this server process (st.cache_resource is process-wide).
_COMPUTED: set[tuple[float, float, float]] = set()


@st.cache_resource(show_spinner=False)
def get_data() -> PlanningData:
    return load_planning_data()


@st.cache_resource(show_spinner=False)
def get_plan(
    target_service_level: float, annual_holding_rate: float, excess_weeks_of_cover: float
) -> PlanResult:
    params = PlanningParameters(
        target_service_level=target_service_level,
        annual_holding_rate=annual_holding_rate,
        excess_weeks_of_cover=excess_weeks_of_cover,
    )
    return run_plan(get_data(), params)


def sidebar_parameters() -> tuple[float, float, float]:
    """Render the planning-parameter controls in the sidebar and return their values."""
    tsl = st.select_slider(
        "Target service level",
        options=SERVICE_LEVEL_OPTIONS,
        value=0.95,
        format_func=lambda v: f"{v:.1%}".replace(".0%", "%"),
        key="param_tsl",
        help="Cycle service level: the desired probability of not stocking out during a supplier lead time. "
        "Sets the z-value used in safety stock (95% → z = 1.645).",
    )
    holding_pct = st.slider(
        "Annual holding rate",
        min_value=10,
        max_value=40,
        value=20,
        step=5,
        format="%d%%",
        key="param_holding_pct",
        help="Cost of holding one unit for a year as a share of its unit cost. Feeds the EOQ calculation.",
    )
    holding = holding_pct / 100
    excess = st.slider(
        "Excess-stock threshold",
        min_value=8,
        max_value=20,
        value=12,
        step=1,
        format="%d weeks",
        key="param_excess",
        help="Inventory position above this many weeks of forecast demand is flagged as excess stock.",
    )
    return float(tsl), float(holding), float(excess)


def _fmt_tsl(v: float) -> str:
    return f"{v:.1%}".replace(".0%", "%")


def current_plan() -> PlanResult:
    """The plan for the parameters currently selected in the sidebar.

    Loading behaviour:
    * cold start (nothing computed yet): a shimmering skeleton of the page instead of a blank screen;
    * new parameter combination: Streamlit dims the stale page while it recalculates, then a toast
      confirms what changed (no spinner is injected, so the layout never jumps);
    * cached combination: instant.
    """
    key = (
        float(st.session_state.get("param_tsl", 0.95)),
        float(st.session_state.get("param_holding_pct", 20)) / 100,
        float(st.session_state.get("param_excess", 12)),
    )
    if not _COMPUTED:
        from ui.components import loading_skeleton  # local import avoids a cycle at module load

        placeholder = st.empty()
        placeholder.html(
            loading_skeleton("Building the plan: forecasts, safety stock, orders and the 16-week backtest…")
        )
        result = get_plan(*key)
        placeholder.empty()
    else:
        result = get_plan(*key)
    _COMPUTED.add(key)

    previous = st.session_state.get("_last_params")
    if previous is not None and previous != key:
        changes = []
        labels = ("service level", "holding rate", "excess threshold")
        fmts = (_fmt_tsl, lambda v: f"{v:.0%}", lambda v: f"{v:g} weeks")
        for label, fmt, old, new in zip(labels, fmts, previous, key, strict=True):
            if old != new:
                changes.append(f"{label} {fmt(old)} → {fmt(new)}")
        st.toast("Plan recalculated · " + "; ".join(changes), icon=":material/check_circle:")
    st.session_state["_last_params"] = key
    return result


def load_or_stop() -> PlanningData:
    """Load the data, or show a useful error page and stop if the inputs are invalid."""
    try:
        return get_data()
    except DataValidationError as exc:
        st.error("The planning inputs in `data/` could not be loaded.")
        st.markdown("\n".join(f"- {p}" for p in exc.problems))
        st.stop()
    except FileNotFoundError as exc:
        st.error(f"Missing input file: {exc}")
        st.stop()


def _current_key() -> tuple[float, float, float]:
    return (
        float(st.session_state.get("param_tsl", 0.95)),
        float(st.session_state.get("param_holding_pct", 20)) / 100,
        float(st.session_state.get("param_excess", 12)),
    )


@st.cache_data(show_spinner=False, max_entries=64)
def _sku_workbook(sku: str, tsl: float, holding: float, excess: float) -> bytes:
    from planning.excel_export import sku_workbook_bytes

    return sku_workbook_bytes(get_plan(tsl, holding, excess), sku)


def sku_workbook(sku: str) -> bytes:
    """Live-formula Excel workbook for one SKU at the parameters currently selected (cached per SKU + parameters)."""
    return _sku_workbook(sku, *_current_key())
