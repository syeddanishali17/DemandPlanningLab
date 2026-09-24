"""SKU Explorer: the list of all SKUs, and a dedicated page per SKU that tells its planning story.

The selected SKU lives in the URL (``?sku=BTH-002``), so every SKU page can be linked to directly
and the browser's back button returns to the list.
"""

import pandas as pd
import streamlit as st

from planning.exceptions import STATUS_ORDER
from ui.components import empty_state, hero, kpi_row, section, status_cell_style, status_filter
from ui.sku_views import (
    context,
    render_backtest,
    render_calculations,
    render_demand,
    render_hero,
    render_inventory,
    render_story,
)
from ui.state import current_plan, sku_workbook
from ui.theme import STATUS_SHORT, STATUS_STYLE

result = current_plan()
plan = result.plan
skus_by_urgency = plan.sort_values("attention_rank")["sku"].tolist()
selected = st.query_params.get("sku")


def open_sku(sku: str | None) -> None:
    # A fresh table key clears the row selection, so returning to the list does not reopen the SKU.
    st.session_state["explorer_nonce"] = st.session_state.get("explorer_nonce", 0) + 1
    if sku:
        st.query_params["sku"] = sku
    elif "sku" in st.query_params:
        del st.query_params["sku"]
    st.rerun()


# ============================================================================== detail view
if selected in skus_by_urgency:
    idx = skus_by_urgency.index(selected)
    labels = {r["sku"]: f"{r['sku']} · {r['product_name']}" for _, r in plan.iterrows()}

    st.session_state["selected_sku"] = selected  # carried into Policy Backtest ("week by week")
    nav, jump_col = st.columns([1.35, 1], vertical_alignment="center", gap="small")
    with nav:
        with st.container(horizontal=True, gap="small"):
            if st.button("All SKUs", icon=":material/arrow_back:"):
                open_sku(None)
            if st.button("Previous", icon=":material/chevron_left:", disabled=idx == 0):
                open_sku(skus_by_urgency[idx - 1])
            if st.button(
                "Next",
                icon=":material/chevron_right:",
                icon_position="right",
                disabled=idx == len(skus_by_urgency) - 1,
            ):
                open_sku(skus_by_urgency[idx + 1])
    with jump_col:
        jump = st.selectbox(
            "Jump to SKU",
            skus_by_urgency,
            index=idx,
            format_func=lambda s: labels[s],
            label_visibility="collapsed",
            key=f"jump_{selected}",
        )
        if jump != selected:
            open_sku(jump)

    ctx = context(result, selected)
    render_hero(ctx)
    info, export = st.columns([3, 1.15], vertical_alignment="center", gap="small")
    with info:
        st.caption(
            f"SKU {idx + 1} of {len(skus_by_urgency)}, ordered by urgency. The Story tab explains the decision in plain English; "
            "the other tabs show the evidence."
        )
    with export:
        st.download_button(
            "Excel workbook",
            data=sku_workbook(selected),
            file_name=f"{selected}_planning_workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            use_container_width=True,
            key=f"xlsx_{selected}",
            help="This SKU's full calculation as a live-formula Excel workbook, with a check sheet against the app.",
        )
    tabs = st.tabs(["Story", "Demand & forecast", "Inventory & orders", "Calculations", "Backtest"])
    with tabs[0]:
        render_story(ctx)
    with tabs[1]:
        render_demand(ctx)
    with tabs[2]:
        render_inventory(ctx)
    with tabs[3]:
        render_calculations(ctx)
    with tabs[4]:
        render_backtest(ctx)
    st.stop()

# ============================================================================== list view
hero(
    "SKU Explorer",
    "Every product, and the story behind its numbers",
    "Pick any SKU to follow its journey: what customers bought, how the forecast was chosen, how much buffer it needs, "
    "when to reorder, how much to order and what happens over the next 12 weeks.",
)

counts = result.status_counts()
kpi_row(
    [
        {
            "label": STATUS_SHORT[s],
            "value": f"{counts[s]}",
            "sub": "SKUs",
            "icon": STATUS_STYLE[s]["icon"],
            "accent": STATUS_STYLE[s]["color"],
            "soft": STATUS_STYLE[s]["bg"],
        }
        for s in STATUS_ORDER
    ]
)

f1, f2, f3 = st.columns([3.4, 1.6, 2], gap="medium")
with f1:
    statuses = status_filter("explorer_status", show_label=True)
with f2:
    categories = st.multiselect("Category", sorted(plan["category"].unique()), placeholder="All categories")
with f3:
    search = st.text_input("Search", placeholder="SKU code or product name", icon=":material/search:")

view = plan[plan["status"].isin(statuses)]
if categories:
    view = view[view["category"].isin(categories)]
if search:
    needle = search.strip().lower()
    view = view[
        view["sku"].str.lower().str.contains(needle) | view["product_name"].str.lower().str.contains(needle)
    ]
view = view.sort_values("attention_rank")

section(
    "All SKUs",
    count=f"{len(view)} of {len(plan)}",
    sub="Tick the box at the start of a row to open that SKU. Sorted by urgency; the sparkline shows the last 26 weeks of demand.",
    tight=True,
)
if view.empty:
    empty_state(
        "No SKUs match these filters", "Clear a status or category filter, or change the search text."
    )
    st.stop()

matrix = result.data.demand_matrix()
table = pd.DataFrame(
    {
        "Status": view["status"].map(STATUS_SHORT).to_numpy(),
        "SKU": view["sku"].to_numpy(),
        "Product": view["product_name"].to_numpy(),
        "Demand, last 26 wks": [matrix[s].iloc[-26:].tolist() for s in view["sku"]],
        "Forecast / wk": view["weekly_forecast"].to_numpy(),
        "Accuracy": (1 - view["wape"].to_numpy()) * 100,
        "Cover (wks)": view["weeks_of_cover"].to_numpy(),
        "Inv. position": view["inventory_position"].to_numpy(),
        "Reorder point": view["reorder_point"].to_numpy(),
        "Order now": view["recommended_order"].to_numpy(),
    }
)
label_to_status = {v: k for k, v in STATUS_SHORT.items()}
styled = table.style.map(status_cell_style(label_to_status), subset=["Status"])
event = st.dataframe(
    styled,
    hide_index=True,
    use_container_width=True,
    height=min(720, 40 + 37 * len(table)),
    row_height=37,
    on_select="rerun",
    selection_mode="single-row",
    key=f"explorer_table_{st.session_state.get('explorer_nonce', 0)}",
    column_config={
        "Status": st.column_config.TextColumn(width=130),
        "SKU": st.column_config.TextColumn(width=90),
        "Product": st.column_config.TextColumn(width="medium"),
        "Demand, last 26 wks": st.column_config.AreaChartColumn(width=150, y_min=0, color="#4F46E5"),
        "Forecast / wk": st.column_config.NumberColumn(format="%.1f"),
        "Accuracy": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100, width=110),
        "Cover (wks)": st.column_config.NumberColumn(format="%.1f"),
        "Inv. position": st.column_config.NumberColumn(format="%d"),
        "Reorder point": st.column_config.NumberColumn(format="%.0f"),
        "Order now": st.column_config.NumberColumn(format="%d"),
    },
)
rows = event.selection.rows if event and event.selection else []
if rows:
    open_sku(view.iloc[rows[0]]["sku"])
