"""Dashboard: the planner's weekly start page. Portfolio health at a glance, what needs attention, what to buy."""

import streamlit as st

from planning.backtest import BASELINE, PROPOSED
from planning.exceptions import Status
from ui.charts import CONFIG, orders_by_supplier_chart, portfolio_demand_chart, status_donut_chart
from ui.components import (
    SKU_PAGE,
    attention_row_html,
    card_head,
    definitions,
    empty_state,
    hero,
    kpi_row,
    pill,
    section,
    status_legend,
)
from ui.state import current_plan
from ui.theme import STATUS_COLOR, STATUS_STYLE, fmt_date, fmt_eur, fmt_eur_short, fmt_pct

result = current_plan()
plan = result.plan
params = result.params
scenario = result.data.scenario
counts = result.status_counts()
bt = result.backtest

hero(
    f"Weekly planning review · {fmt_date(scenario.snapshot_date)}",
    "Which products need attention this week?",
    f"Forecasts, safety stock, reorder points and order quantities for every SKU of {scenario.company}, a fictitious "
    "home & living e-tailer, recalculated from 104 weeks of synthetic demand. Start here, then open any SKU to follow its story.",
    chips=[
        f"<b>{len(plan)}</b> SKUs",
        f"<b>{plan['supplier_id'].nunique()}</b> suppliers",
        f"Service level <b>{params.target_service_level:.1%}</b>".replace(".0%", "%"),
        f"Holding rate <b>{params.annual_holding_rate:.0%}</b>",
        "Synthetic data",
    ],
)

# ---------------------------------------------------------------- KPI row
orders = plan[plan["recommended_order"] > 0]
excess_value = plan.loc[plan["status"] == Status.EXCESS_STOCK.value, "on_hand_value"].sum()
fill_a, fill_b = bt.metric(BASELINE, "fill_rate"), bt.metric(PROPOSED, "fill_rate")
risk_style = STATUS_STYLE[Status.STOCKOUT_RISK.value]
reorder_style = STATUS_STYLE[Status.REORDER_REQUIRED.value]

kpi_row(
    [
        {
            "label": "Stockout risk",
            "icon": "▲",
            "accent": risk_style["color"],
            "soft": risk_style["bg"],
            "value": f"{counts[Status.STOCKOUT_RISK.value]} SKUs",
            "sub": "stock runs out before a new order could land",
        },
        {
            "label": "Orders to place",
            "icon": "⇣",
            "accent": reorder_style["color"],
            "soft": reorder_style["bg"],
            "value": fmt_eur_short(orders["recommended_order_value"].sum()),
            "sub": f"{len(orders)} SKUs · {orders['recommended_order'].sum():,.0f} units",
        },
        {
            "label": "Inventory value",
            "icon": "€",
            "value": fmt_eur_short(plan["on_hand_value"].sum()),
            "sub": f"{fmt_eur_short(excess_value)} of it in excess stock",
        },
        {
            "label": "Accuracy",
            "icon": "◎",
            "accent": "#0891B2",
            "soft": "#ECFEFF",
            "value": fmt_pct(1 - result.portfolio_wape),
            "sub": f"forecast · 1 − WAPE ({fmt_pct(result.portfolio_wape)}), out-of-sample",
        },
        {
            "label": "Backtest fill rate",
            "icon": "✓",
            "accent": "#047857",
            "soft": "#ECFDF5",
            "value": fmt_pct(fill_b),
            "sub": f"{pill(f'{(fill_b - fill_a) * 100:+.1f} pp', fill_b >= fill_a)} vs 4-weeks-of-stock rule",
        },
    ]
)

# ---------------------------------------------------------------- demand vs forecast + status mix
left, right = st.columns([2.1, 1], gap="medium")
with left:
    with st.container(border=True):
        card_head(
            "Portfolio demand: actual vs forecast",
            "All SKUs combined, last 52 weeks. The forecast line is what each week looked like one week ahead.",
            tag="Units / week",
        )
        st.plotly_chart(
            portfolio_demand_chart(result.forecasts, scenario, params.projection_weeks),
            use_container_width=True,
            config=CONFIG,
        )
with right:
    with st.container(border=True):
        card_head("Portfolio health", "One status per SKU, in priority order.")
        st.plotly_chart(status_donut_chart(counts), use_container_width=True, config=CONFIG)
        status_legend(counts, STATUS_COLOR)

# ---------------------------------------------------------------- attention + suppliers
left, right = st.columns([1.35, 1], gap="medium")
with left:
    with st.container(border=True):
        attention = result.attention
        card_head(
            "Needs attention",
            "Most urgent first, with this week's action. Open a SKU to see the full story.",
            tag=f"{len(attention)} SKUs",
        )
        if attention.empty:
            empty_state("All clear", "No SKU needs attention at the current parameters.")
        else:
            top = attention.head(8)
            with st.container(gap=None):
                for _, row in top.iterrows():
                    c1, c2 = st.columns([10, 2.3], vertical_alignment="center", gap="small")
                    with c1:
                        st.html(attention_row_html(row, params.excess_weeks_of_cover))
                    with c2:
                        st.page_link(
                            SKU_PAGE,
                            label="Open",
                            icon=":material/arrow_forward:",
                            query_params={"sku": row["sku"]},
                        )
            if len(attention) > len(top):
                st.page_link(
                    "ui/pages/replenishment.py",
                    label=f"See all {len(attention)} in the Replenishment Plan",
                    icon=":material/list_alt:",
                    query_params={"view": "attention"},
                )
with right:
    with st.container(border=True):
        card_head(
            "Orders to place, by supplier",
            "Recommended order value this week (EOQ, case-pack rounded).",
            tag=fmt_eur(orders["recommended_order_value"].sum()),
        )
        if orders.empty:
            empty_state("No orders this week", "Every SKU is above its reorder point.")
        else:
            st.plotly_chart(orders_by_supplier_chart(plan), use_container_width=True, config=CONFIG)
            st.page_link(
                "ui/pages/replenishment.py",
                label="Review and export the order proposal",
                icon=":material/download:",
            )

section(
    "How to read this dashboard",
    sub="One status per SKU, checked in this priority order. Change the sidebar parameters and every number recalculates.",
)
definitions(
    [
        (
            "Stockout risk",
            STATUS_COLOR[Status.STOCKOUT_RISK.value],
            "Projected stock hits zero before a new order placed today could arrive.",
        ),
        (
            "Reorder required",
            STATUS_COLOR[Status.REORDER_REQUIRED.value],
            "Inventory position (on hand + on order − backorders) is at or below the reorder point.",
        ),
        (
            "Excess stock",
            STATUS_COLOR[Status.EXCESS_STOCK.value],
            f"The inventory position covers more than {params.excess_weeks_of_cover:g} weeks of forecast demand.",
        ),
        (
            "Forecast accuracy",
            "#06B6D4",
            "1 − WAPE on out-of-sample (walk-forward) forecasts, volume-weighted across all SKUs.",
        ),
    ]
)
