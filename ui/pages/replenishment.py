"""Replenishment Plan: the buying decision for every SKU first, the calculation behind it second.

Selection is tracked by SKU code, never by row number, so filtering can never swap the detail panel
to a different SKU. Exports state their scope (filtered vs all) in the button label.
"""

import hashlib

import pandas as pd
import streamlit as st

from planning.exceptions import STATUS_ORDER, Status
from ui.components import (
    callout,
    empty_state,
    hero,
    kpi_row,
    section,
    status_badge,
    status_cell_style,
    status_filter,
)
from ui.state import current_plan
from ui.theme import STATUS_COLOR, STATUS_SHORT, fmt_date, fmt_eur, fmt_eur_short, fmt_units

result = current_plan()
plan = result.plan
params = result.params
scenario = result.data.scenario

attention_view = st.query_params.get("view") == "attention"
hero(
    "Replenishment plan",
    "When to order, and roughly how much",
    "One row per SKU, decision first: what to do, how many units, what it costs and when it arrives. The calculation "
    "behind each decision (forecast → safety stock → reorder point → EOQ) follows in the later columns.",
)

# ---------------------------------------------------------------- filters
f1, f2, f3, f4 = st.columns([5, 2, 2, 2], gap="medium")
with f1:
    default = [s for s in STATUS_ORDER if s != Status.HEALTHY.value] if attention_view else None
    statuses = status_filter(
        f"plan_status_{'att' if attention_view else 'all'}", default=default, show_label=True
    )
with f2:
    categories = st.multiselect("Category", sorted(plan["category"].unique()), placeholder="All categories")
with f3:
    suppliers = st.multiselect("Supplier", sorted(plan["supplier_id"].unique()), placeholder="All suppliers")
with f4:
    search = st.text_input("Search", placeholder="SKU or product name", icon=":material/search:")

view = plan[plan["status"].isin(statuses)]
if categories:
    view = view[view["category"].isin(categories)]
if suppliers:
    view = view[view["supplier_id"].isin(suppliers)]
if search:
    needle = search.strip().lower()
    view = view[
        view["sku"].str.lower().str.contains(needle) | view["product_name"].str.lower().str.contains(needle)
    ]
view = view.sort_values("attention_rank").reset_index(drop=True)
filtered = len(view) < len(plan)

if attention_view:
    callout(
        f"Showing the <b>{int((plan['status'] != Status.HEALTHY.value).sum())} SKUs that need attention</b> "
        "(stockout risk, reorder required, excess stock), as linked from the dashboard. Add <b>Healthy</b> in the status "
        "filter to see every SKU.",
        kind="info",
    )

orders = view[view["recommended_order"] > 0]
all_orders = plan[plan["recommended_order"] > 0]
kpi_row(
    [
        {
            "label": "SKUs shown",
            "value": f"{len(view)}",
            "sub": f"of {len(plan)}" + (" · filtered" if filtered else ""),
        },
        {
            "label": "Orders to place",
            "value": f"{len(orders)}",
            "sub": "SKUs at or below their reorder point",
            "accent": STATUS_COLOR[Status.REORDER_REQUIRED.value],
        },
        {
            "label": "To expedite",
            "value": f"{int((view['action'] == 'Expedite open PO').sum() + (view['action'] == 'Order now + expedite').sum())}",
            "sub": "stock runs out before supply lands",
            "accent": STATUS_COLOR[Status.STOCKOUT_RISK.value],
        },
        {
            "label": "Units to order",
            "value": fmt_units(orders["recommended_order"].sum()),
            "sub": "EOQ rounded up to case packs",
        },
        {
            "label": "Order value",
            "value": fmt_eur_short(orders["recommended_order_value"].sum()),
            "sub": "at unit cost" + (" · filtered" if filtered else ""),
        },
    ]
)

# ---------------------------------------------------------------- table: decision first
COLUMNS = {
    "status_label": st.column_config.TextColumn("Status", width=130, pinned=True),
    "sku": st.column_config.TextColumn("SKU", width=85, pinned=True),
    "product_name": st.column_config.TextColumn("Product", width="medium"),
    "action": st.column_config.TextColumn(
        "Action", width=165, help="What to do this week. Expedite = stock runs out before supply lands."
    ),
    "recommended_order": st.column_config.NumberColumn(
        "Order units", format="%d", help="EOQ rounded up to the case pack, if the reorder point is reached."
    ),
    "recommended_order_value": st.column_config.NumberColumn("Order value", format="euro"),
    "arrives": st.column_config.DateColumn(
        "Arrives", format="DD MMM", help="Receipt date of today's order (lead time + 1 week)."
    ),
    "reason": st.column_config.TextColumn("Reason", width="large"),
    "supplier_name": st.column_config.TextColumn("Supplier", width="medium"),
    "weeks_of_cover": st.column_config.NumberColumn(
        "Cover (wks)",
        format="%.1f",
        help="Inventory position ÷ weekly forecast (0 when the position is negative).",
    ),
    "inventory_position": st.column_config.NumberColumn(
        "Inv. position", format="%d", help="On hand + on order − backorders"
    ),
    "reorder_point": st.column_config.NumberColumn(
        "Reorder point", format="%.0f", help="Lead-time demand + safety stock."
    ),
    "on_hand": st.column_config.NumberColumn("On hand", format="%d"),
    "on_order": st.column_config.NumberColumn("On order", format="%d"),
    "backorders": st.column_config.NumberColumn("Backorders", format="%d"),
    "safety_stock": st.column_config.NumberColumn(
        "Safety stock", format="%.0f", help="z × error SD × √lead time"
    ),
    "lead_time_weeks": st.column_config.NumberColumn("LT (wks)", format="%d"),
    "weekly_forecast": st.column_config.NumberColumn("Forecast / wk", format="%.1f"),
    "forecast_method": st.column_config.TextColumn("Method", width="small"),
    "wape_pct": st.column_config.NumberColumn("WAPE", format="%.1f%%"),
    "bias_pct": st.column_config.NumberColumn("Bias", format="%+.1f%%"),
    "error_sd": st.column_config.NumberColumn("Error SD", format="%.1f"),
    "eoq": st.column_config.NumberColumn("EOQ", format="%.0f"),
    "case_pack": st.column_config.NumberColumn("Case pack", format="%d"),
}
display = view.assign(
    status_label=view["status"].map(STATUS_SHORT),
    wape_pct=view["wape"] * 100,
    bias_pct=view["bias"] * 100,
    arrives=[
        pd.Timestamp(scenario.week_start(int(w))) if w > 0 else pd.NaT for w in view["new_order_receipt_week"]
    ],
)
table = display[list(COLUMNS)]
styled = table.style.map(status_cell_style({v: k for k, v in STATUS_SHORT.items()}), subset=["status_label"])

section("Plan by SKU", count=f"{len(view)} shown", tight=True)

# Selection is keyed by SKU code. A new filter state gets a fresh table; the chosen SKU is re-selected
# on its new row if it is still visible, otherwise the selection is cleared.
selected_sku = st.session_state.get("plan_selected_sku")
signature = hashlib.md5(repr((sorted(statuses), categories, suppliers, search)).encode()).hexdigest()[:10]
skus_in_view = view["sku"].tolist()
if table.empty:
    empty_state(
        "No SKUs match these filters",
        "Clear a status, category or supplier filter, or change the search text.",
    )
    event = None
else:
    default_rows = [skus_in_view.index(selected_sku)] if selected_sku in skus_in_view else []
    event = st.dataframe(
        styled,
        column_config=COLUMNS,
        hide_index=True,
        height=min(640, 38 + 35 * len(table)),
        on_select="rerun",
        selection_mode="single-row",
        selection_default={"selection": {"rows": default_rows, "columns": []}},
        key=f"plan_table_{signature}",
    )
    st.caption(
        "Tick the box at the start of a row to see its full reason. The calculation columns follow Reason; scroll sideways to see them."
    )

rows = event.selection.rows if event and event.selection else []
if rows:
    st.session_state["plan_selected_sku"] = skus_in_view[rows[0]]
elif selected_sku and selected_sku not in skus_in_view and not table.empty:
    st.caption(
        f"The previously selected SKU ({selected_sku}) is not in the filtered list, so the selection was cleared."
    )
    st.session_state.pop("plan_selected_sku", None)
elif event is not None and selected_sku in skus_in_view:
    st.session_state.pop("plan_selected_sku", None)  # the user unticked the row

# ---------------------------------------------------------------- selected SKU detail (by SKU code)
current = st.session_state.get("plan_selected_sku")
if current in skus_in_view:
    row = plan.set_index("sku").loc[current]
    with st.container(border=True):
        head, go_btn = st.columns([4, 1], vertical_alignment="center", gap="large")
        with head:
            st.html(
                f'<div class="dp-product"><span class="dp-product-name" style="font-size:18px">'
                f"{current} · {row['product_name']}</span>{status_badge(row['status'])}"
                f'<span class="dp-card-tag">{row["action"]}</span></div>'
                f'<div class="dp-reason">{row["reason"]}</div>'
            )
            facts = (
                f"Inventory position **{fmt_units(row['inventory_position'])}** vs reorder point **{fmt_units(row['reorder_point'])}** · "
                f"cover **{row['weeks_of_cover']:.1f} wks** (on hand only {row['weeks_of_cover_on_hand']:.1f}) · EOQ **{fmt_units(row['eoq'])}** → "
                f"order **{fmt_units(row['recommended_order'])}**"
            )
            if row["recommended_order"] > 0:
                facts += f" (arrives {fmt_date(scenario.week_start(int(row['new_order_receipt_week'])))}, {fmt_eur(row['recommended_order_value'])})"
            st.caption(facts)
        with go_btn:
            if st.button(
                "Open SKU story",
                type="primary",
                icon=":material/arrow_forward:",
                use_container_width=True,
                key=f"open_{current}",
            ):
                st.switch_page("ui/pages/sku_explorer.py", query_params={"sku": current})

# ---------------------------------------------------------------- downloads: scope is always explicit
section(
    "Export",
    sub="Order proposals list only SKUs with an order this week. The filtered export follows the filters above.",
)
EXPORT_COLS = [
    "sku",
    "product_name",
    "supplier_id",
    "supplier_name",
    "status",
    "action",
    "inventory_position",
    "reorder_point",
    "eoq",
    "case_pack",
    "recommended_order",
    "recommended_order_value",
    "new_order_receipt_week",
    "reason",
]


def _proposal(frame: pd.DataFrame) -> bytes:
    out = frame[frame["recommended_order"] > 0].sort_values("attention_rank")[EXPORT_COLS].copy()
    out.insert(
        out.columns.get_loc("new_order_receipt_week") + 1,
        "expected_receipt_date",
        [scenario.week_start(int(w)) for w in out["new_order_receipt_week"]],
    )
    return out.to_csv(index=False).encode("utf-8")


d1, d2, d3 = st.columns(3)
with d1:
    st.download_button(
        f"Filtered orders · {len(orders)} · {fmt_eur_short(orders['recommended_order_value'].sum())}",
        _proposal(view),
        file_name=f"order_proposal_filtered_{scenario.snapshot_date}.csv",
        mime="text/csv",
        icon=":material/filter_alt:",
        type="primary",
        use_container_width=True,
        disabled=orders.empty,
        help="Only the orders visible with the current filters.",
    )
with d2:
    st.download_button(
        f"All orders · {len(all_orders)} · {fmt_eur_short(all_orders['recommended_order_value'].sum())}",
        _proposal(plan),
        file_name=f"order_proposal_all_{scenario.snapshot_date}.csv",
        mime="text/csv",
        icon=":material/download:",
        use_container_width=True,
        help="Every order this week, ignoring the filters.",
    )
with d3:
    st.download_button(
        f"Full plan · all {len(plan)} SKUs",
        plan.drop(columns=["reorder_triggered"]).to_csv(index=False).encode("utf-8"),
        file_name=f"replenishment_plan_{scenario.snapshot_date}.csv",
        mime="text/csv",
        icon=":material/table_view:",
        use_container_width=True,
        help="Every column of the plan for every SKU.",
    )

callout(
    "<strong>Decision rule.</strong> If inventory position &gt; reorder point → no order. If inventory position ≤ reorder point → "
    "order EOQ rounded up to the case pack. Stockout-risk SKUs also need their supply expedited, because stock runs out before "
    f"a new order could arrive. Settings: target cycle service level {params.target_service_level:.1%} (z = {params.z_value:.3f}), "
    f"holding rate {params.annual_holding_rate:.0%}, excess threshold {params.excess_weeks_of_cover:g} weeks. One EOQ per weekly "
    "review: if the position is far below the reorder point, the next review may order again.",
    kind="note",
)
