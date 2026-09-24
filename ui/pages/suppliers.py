"""Supplier View: what to buy from whom, where the stock and the risk sit, and how the policy performs per supplier.

This is a buying view, not a supplier performance scorecard: lead times are fixed inputs and there
is no delivery-reliability data in V1.
"""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from planning.backtest import BASELINE, PROPOSED
from planning.exceptions import STATUS_ORDER, Status
from ui.charts import CONFIG, GRID, base_layout
from ui.components import SKU_PAGE, card_head, empty_state, hero, kpi_row, section, status_cell_style
from ui.state import current_plan
from ui.theme import PRIMARY, SERIES, STATUS_COLOR, STATUS_SHORT, fmt_eur, fmt_eur_short, fmt_pct, fmt_units

result = current_plan()
plan = result.plan
params = result.params
bt = result.backtest

# ---------------------------------------------------------------- per-supplier aggregates
bt_by_sku = bt.sku_summary.merge(plan[["sku", "supplier_id"]], on="sku")
fill = (
    bt_by_sku.groupby(["supplier_id", "policy"])
    .agg(lost=("lost_units", "sum"), demanded=("units_demanded", "sum"))
    .assign(fill=lambda d: 1 - d["lost"] / d["demanded"])["fill"]
    .unstack()
)
# Exact volume-weighted accuracy per supplier: 1 − Σ|walk-forward errors| ÷ Σ actuals over each SKU's evaluation window.
_err = {
    sku: (
        float(fc.errors.abs().sum()),
        float(fc.walk_forward.loc[fc.evaluation_window[0] : fc.evaluation_window[1], "actual"].sum()),
    )
    for sku, fc in result.forecasts.items()
}
_acc = plan[["sku", "supplier_id"]].assign(
    abs_err=lambda d: d["sku"].map(lambda k: _err[k][0]), actual=lambda d: d["sku"].map(lambda k: _err[k][1])
)
suppliers = (
    plan.groupby(["supplier_id", "supplier_name"])
    .agg(
        lead_time=("lead_time_weeks", "first"),
        ordering_cost=("ordering_cost_eur", "first"),
        skus=("sku", "count"),
        inventory_value=("on_hand_value", "sum"),
        order_value=("recommended_order_value", "sum"),
        orders=("recommended_order", lambda s: int((s > 0).sum())),
        units=("recommended_order", "sum"),
        weekly_forecast=("weekly_forecast", "sum"),
    )
    .reset_index()
)
suppliers["accuracy"] = suppliers["supplier_id"].map(
    1 - _acc.groupby("supplier_id")["abs_err"].sum() / _acc.groupby("supplier_id")["actual"].sum()
)
for status in STATUS_ORDER:
    suppliers[status] = (
        suppliers["supplier_id"]
        .map(plan[plan["status"] == status].groupby("supplier_id").size())
        .fillna(0)
        .astype(int)
    )
suppliers["excess_value"] = (
    suppliers["supplier_id"]
    .map(plan[plan["status"] == Status.EXCESS_STOCK.value].groupby("supplier_id")["on_hand_value"].sum())
    .fillna(0)
)
suppliers["fill_baseline"] = suppliers["supplier_id"].map(fill[BASELINE])
suppliers["fill_proposed"] = suppliers["supplier_id"].map(fill[PROPOSED])
suppliers = suppliers.sort_values("order_value", ascending=False).reset_index(drop=True)

hero(
    "Supplier view",
    "What to buy from whom this week",
    "The plan grouped by supplier: this week's purchase orders, where the inventory value and the risk sit, and how the "
    "replenishment policy performs for each lead time. A buying view, not a delivery-performance scorecard: lead times are fixed in V1.",
    chips=[
        f"<b>{len(suppliers)}</b> suppliers",
        f"Lead times <b>{suppliers['lead_time'].min()}–{suppliers['lead_time'].max()}</b> weeks",
    ],
)

kpi_row(
    [
        {
            "label": "Orders this week",
            "icon": "⇣",
            "value": fmt_eur_short(suppliers["order_value"].sum()),
            "sub": f"{int(suppliers['orders'].sum())} order lines across {int((suppliers['orders'] > 0).sum())} suppliers",
        },
        {
            "label": "Largest order",
            "icon": "★",
            "value": fmt_eur_short(suppliers["order_value"].max()),
            "sub": html.escape(suppliers.iloc[0]["supplier_name"]),
        },
        {
            "label": "Inventory at risk",
            "icon": "▲",
            "accent": "#B91C1C",
            "soft": "#FEF2F2",
            "value": f"{int(suppliers[Status.STOCKOUT_RISK.value].sum())} SKUs",
            "sub": "stockout risk, across "
            + f"{int((suppliers[Status.STOCKOUT_RISK.value] > 0).sum())} suppliers",
        },
        {
            "label": "Excess stock value",
            "icon": "■",
            "accent": "#0369A1",
            "soft": "#F0F9FF",
            "value": fmt_eur_short(suppliers["excess_value"].sum()),
            "sub": "on hand, at unit cost",
        },
    ]
)

# ---------------------------------------------------------------- comparison
left, right = st.columns([1.25, 1], gap="medium")
with left:
    with st.container(border=True):
        card_head("Status mix by supplier", "How many of each supplier's SKUs sit in each status this week.")
        fig = go.Figure()
        names = suppliers["supplier_name"]
        for status in STATUS_ORDER:
            fig.add_bar(
                y=names,
                x=suppliers[status],
                orientation="h",
                name=STATUS_SHORT[status],
                marker=dict(color=STATUS_COLOR[status]),
                hovertemplate="%{y}<br>" + STATUS_SHORT[status] + ": <b>%{x}</b> SKUs<extra></extra>",
            )
        fig.update_layout(base_layout(height=300, barmode="stack", bargap=0.38, xaxis_title="SKUs"))
        fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=12))
        fig.update_xaxes(showgrid=True, gridcolor=GRID, dtick=2)
        st.plotly_chart(fig, use_container_width=True, config=CONFIG)
with right:
    with st.container(border=True):
        card_head(
            "Backtest fill rate by supplier",
            "Replay of weeks "
            + f"{bt.weeks[0]}–{bt.weeks[1]}: share of units demanded that were shipped. Longer lead times gain the most.",
        )
        order = suppliers.sort_values("lead_time")
        labels = [
            f"{sid}<br>{lt} wk lead" for sid, lt in zip(order["supplier_id"], order["lead_time"], strict=True)
        ]
        fig = go.Figure()
        fig.add_bar(
            x=labels,
            y=order["fill_baseline"] * 100,
            name="Baseline: 4 weeks of stock",
            marker=dict(color=SERIES["baseline"], cornerradius=5),
            customdata=order["supplier_name"],
            hovertemplate="%{customdata} (%{x})<br>Baseline fill rate %{y:.1f}%<extra></extra>",
        )
        fig.add_bar(
            x=labels,
            y=order["fill_proposed"] * 100,
            name="Proposed policy",
            marker=dict(color=PRIMARY, cornerradius=5),
            customdata=order["supplier_name"],
            hovertemplate="%{customdata} (%{x})<br>Proposed fill rate %{y:.1f}%<extra></extra>",
        )
        fig.update_layout(base_layout(height=300, barmode="group", bargap=0.3, yaxis_title="Fill rate (%)"))
        fig.update_yaxes(range=[50, 104])
        fig.update_xaxes(tickangle=0, tickfont=dict(size=12))
        st.plotly_chart(fig, use_container_width=True, config=CONFIG)

section("All suppliers", sub="Sorted by this week's order value.", tight=False)
table = pd.DataFrame(
    {
        "Supplier": suppliers["supplier_name"],
        "ID": suppliers["supplier_id"],
        "Lead time (wks)": suppliers["lead_time"],
        "Ordering cost": suppliers["ordering_cost"],
        "SKUs": suppliers["skus"],
        "Risk": suppliers[Status.STOCKOUT_RISK.value],
        "Reorder": suppliers[Status.REORDER_REQUIRED.value],
        "Excess": suppliers[Status.EXCESS_STOCK.value],
        "Inventory value": suppliers["inventory_value"],
        "Order value (this week)": suppliers["order_value"],
        "Forecast accuracy": suppliers["accuracy"] * 100,
        "Fill rate · baseline": suppliers["fill_baseline"] * 100,
        "Fill rate · proposed": suppliers["fill_proposed"] * 100,
    }
)
st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Supplier": st.column_config.TextColumn(width="medium", pinned=True),
        "Lead time (wks)": st.column_config.NumberColumn(format="%d"),
        "Ordering cost": st.column_config.NumberColumn(format="€%d"),
        "Inventory value": st.column_config.NumberColumn(format="euro"),
        "Order value (this week)": st.column_config.NumberColumn(format="euro"),
        "Forecast accuracy": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Fill rate · baseline": st.column_config.NumberColumn(format="%.1f%%"),
        "Fill rate · proposed": st.column_config.NumberColumn(format="%.1f%%"),
    },
)

# ---------------------------------------------------------------- one supplier
st.caption("On narrow screens, scroll the table sideways for the backtest fill-rate columns.")

section("Supplier detail", sub="Pick a supplier to see its SKUs and this week's purchase order draft.")
options = suppliers["supplier_id"].tolist()
label = {r.supplier_id: f"{r.supplier_name} · {r.supplier_id}" for r in suppliers.itertuples()}
picked = (
    st.segmented_control(
        "Supplier",
        options,
        default=options[0],
        format_func=lambda s: label[s],
        key="supplier_pick",
        label_visibility="collapsed",
    )
    or options[0]
)
sup = suppliers[suppliers["supplier_id"] == picked].iloc[0]
rows = plan[plan["supplier_id"] == picked].sort_values("attention_rank")

kpi_row(
    [
        {
            "label": "Lead time",
            "value": f"{int(sup['lead_time'])} weeks",
            "sub": f"ordering cost {fmt_eur(sup['ordering_cost'])} per order",
        },
        {
            "label": "SKUs",
            "value": f"{int(sup['skus'])}",
            "sub": f"{fmt_units(sup['weekly_forecast'])} units forecast per week",
        },
        {
            "label": "Inventory value",
            "value": fmt_eur_short(sup["inventory_value"]),
            "sub": f"{fmt_eur_short(sup['excess_value'])} of it excess",
        },
        {
            "label": "Order this week",
            "value": fmt_eur_short(sup["order_value"]),
            "sub": f"{int(sup['orders'])} line{'s' if int(sup['orders']) != 1 else ''} · {fmt_units(sup['units'])} units",
        },
        {
            "label": "Fill rate (backtest)",
            "value": fmt_pct(sup["fill_proposed"]),
            "sub": f"baseline {fmt_pct(sup['fill_baseline'])}",
        },
    ]
)

left, right = st.columns([1.35, 1], gap="medium")
with left:
    with st.container(border=True):
        card_head(
            f"SKUs supplied by {sup['supplier_name']}",
            "Tick the box at the start of a row to open the SKU's story.",
            tag=f"{len(rows)} SKUs",
        )
        sku_table = pd.DataFrame(
            {
                "Status": rows["status"].map(STATUS_SHORT).to_numpy(),
                "SKU": rows["sku"].to_numpy(),
                "Product": rows["product_name"].to_numpy(),
                "Forecast / wk": rows["weekly_forecast"].to_numpy(),
                "Cover (wks)": rows["weeks_of_cover"].to_numpy(),
                "Inv. position": rows["inventory_position"].to_numpy(),
                "Reorder point": rows["reorder_point"].to_numpy(),
                "Order now": rows["recommended_order"].to_numpy(),
            }
        )
        styled = sku_table.style.map(
            status_cell_style({v: k for k, v in STATUS_SHORT.items()}), subset=["Status"]
        )
        nonce = st.session_state.get("supplier_nonce", 0)
        event = st.dataframe(
            styled,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"sup_tbl_{picked}_{nonce}",
            column_config={
                "Status": st.column_config.TextColumn(width=130),
                "Forecast / wk": st.column_config.NumberColumn(format="%.1f"),
                "Cover (wks)": st.column_config.NumberColumn(format="%.1f"),
                "Inv. position": st.column_config.NumberColumn(format="%d"),
                "Reorder point": st.column_config.NumberColumn(format="%.0f"),
                "Order now": st.column_config.NumberColumn(format="%d"),
            },
        )
        if event and event.selection and event.selection.rows:
            st.session_state["supplier_nonce"] = nonce + 1
            st.switch_page(SKU_PAGE, query_params={"sku": rows.iloc[event.selection.rows[0]]["sku"]})
with right:
    with st.container(border=True):
        po_lines = rows[rows["recommended_order"] > 0]
        card_head(
            "Purchase order draft",
            "EOQ quantities rounded to case packs, for SKUs at or below their reorder point.",
            tag=fmt_eur(po_lines["recommended_order_value"].sum()),
        )
        if po_lines.empty:
            empty_state("No order this week", "Every SKU from this supplier is above its reorder point.")
        else:
            draft = pd.DataFrame(
                {
                    "SKU": po_lines["sku"].to_numpy(),
                    "Product": po_lines["product_name"].to_numpy(),
                    "Units": po_lines["recommended_order"].to_numpy(),
                    "Cases": (po_lines["recommended_order"] / po_lines["case_pack"]).astype(int).to_numpy(),
                    "Value": po_lines["recommended_order_value"].to_numpy(),
                }
            )
            st.dataframe(
                draft,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Units": st.column_config.NumberColumn(format="%d"),
                    "Cases": st.column_config.NumberColumn(format="%d"),
                    "Value": st.column_config.NumberColumn(format="euro"),
                },
            )
            export = po_lines.assign(
                cases=(po_lines["recommended_order"] / po_lines["case_pack"]).astype(int),
                expected_receipt_date=[
                    result.data.scenario.week_start(int(w)) for w in po_lines["new_order_receipt_week"]
                ],
            )[
                [
                    "supplier_id",
                    "supplier_name",
                    "sku",
                    "product_name",
                    "recommended_order",
                    "case_pack",
                    "cases",
                    "unit_cost_eur",
                    "recommended_order_value",
                    "expected_receipt_date",
                    "status",
                ]
            ]
            st.download_button(
                "Download PO draft (CSV)",
                export.to_csv(index=False).encode("utf-8"),
                file_name=f"po_draft_{picked}_{result.data.scenario.snapshot_date}.csv",
                mime="text/csv",
                icon=":material/download:",
                type="primary",
                use_container_width=True,
                key=f"po_{picked}",
            )
