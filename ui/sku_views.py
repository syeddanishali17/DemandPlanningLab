"""Everything shown for one SKU in the SKU Explorer: hero, story, demand, inventory, calculations, backtest.

The story is generated from the SKU's own numbers, so it reads like a planner explaining the
decision: what customers bought → how it was forecast → how reliable that is → the buffer →
when to reorder → how much → what happens next → the verdict.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from planning.backtest import BASELINE, POLICY_LABELS, PROPOSED
from planning.data import Scenario
from planning.exceptions import Status
from planning.forecasting import METHOD_LABELS, METHOD_SHORT, METHODS, SkuForecast
from planning.pipeline import PlanResult
from planning.projection import ProjectionResult
from ui.charts import (
    CONFIG,
    backtest_sku_chart,
    demand_forecast_chart,
    eoq_cost_chart,
    forecast_error_chart,
    legend_below,
    method_comparison_chart,
    projection_chart,
)
from ui.components import (
    callout,
    card_head,
    delta,
    gauge_html,
    kpi_row,
    status_badge,
    step_cards,
    story,
    subhead,
)
from ui.theme import STATUS_STYLE, fmt_date, fmt_eur, fmt_pct, fmt_units


@dataclass
class SkuContext:
    result: PlanResult
    sku: str
    row: pd.Series
    fc: SkuForecast
    proj: ProjectionResult
    open_orders: pd.DataFrame
    scenario: Scenario

    @property
    def params(self):
        return self.result.params

    @property
    def lead_time(self) -> int:
        return int(self.row["lead_time_weeks"])


def context(result: PlanResult, sku: str) -> SkuContext:
    return SkuContext(
        result=result,
        sku=sku,
        row=result.sku_plan(sku),
        fc=result.forecasts[sku],
        proj=result.projections[sku],
        open_orders=result.data.open_orders(sku),
        scenario=result.data.scenario,
    )


# ============================================================================== hero
def render_hero(ctx: SkuContext) -> None:
    r, fc = ctx.row, ctx.fc
    stats = [
        ("Forecast / week", fmt_units(fc.weekly_forecast, 1)),
        ("Inventory position", fmt_units(r["inventory_position"])),
        ("Reorder point", fmt_units(r["reorder_point"])),
        ("Order now", fmt_units(r["recommended_order"]) + (" units" if r["recommended_order"] > 0 else "")),
    ]
    stat_html = "".join(f'<div class="dp-sku-stat"><span>{k}</span><b>{v}</b></div>' for k, v in stats)
    lt = ctx.lead_time
    meta = "".join(
        f"<span>{html.escape(item)}</span>"
        for item in (
            f"Supplier {r['supplier_name']}",
            f"Lead time {lt} week{'s' if lt != 1 else ''}",
            f"Unit cost {fmt_eur(r['unit_cost_eur'], 2)}",
            f"Case pack {int(r['case_pack'])}",
        )
    )
    st.html(
        f'<div class="dp-sku-hero"><div>'
        f'<div class="dp-sku-code">{html.escape(r["sku"])} · {html.escape(r["category"]).upper()}</div>'
        f'<div class="dp-sku-name">{html.escape(r["product_name"])}</div>'
        f"{status_badge(r['status'], large=True)}"
        f'<div class="dp-sku-reason">{html.escape(r["reason"])}</div>'
        f'<div class="dp-sku-meta" style="margin-top:12px">{meta}</div>'
        f'</div><div class="dp-sku-grid">{stat_html}</div></div>'
    )


# ============================================================================== story
def _trend(fc: SkuForecast) -> tuple[float, str]:
    actual = fc.walk_forward["actual"]
    recent, before = actual.iloc[-13:].mean(), actual.iloc[-26:-13].mean()
    change = recent / before - 1 if before else 0.0
    if change > 0.08:
        word = "growing"
    elif change < -0.08:
        word = "declining"
    else:
        word = "broadly stable"
    return change, word


def render_story(ctx: SkuContext) -> None:
    r, fc, proj, p = ctx.row, ctx.fc, ctx.proj, ctx.params
    actual = fc.walk_forward["actual"]
    last52 = actual.iloc[-52:]
    change, trend_word = _trend(fc)
    scores = fc.method_scores
    best_method = scores["wape"].idxmin()
    method = fc.selected_method
    lt = ctx.lead_time

    if method == best_method:
        why = f"It had the lowest error of the four ({fmt_pct(fc.wape)} WAPE)."
    else:
        why = (
            f"{METHOD_SHORT[best_method]} scored slightly better ({fmt_pct(scores.loc[best_method, 'wape'])}), but "
            f"{METHOD_SHORT[method]} was within {p.wape_tolerance * 100:.0f} point of it and is simpler, so it wins."
        )
    bias_word = (
        "over-forecast"
        if fc.bias > 0.005
        else ("under-forecast" if fc.bias < -0.005 else "was essentially unbiased")
    )
    bias_text = (
        f"leaned slightly towards <b>{bias_word}</b> ({fmt_pct(fc.bias, signed=True)})"
        if bias_word != "was essentially unbiased"
        else "<b>was essentially unbiased</b>"
    )
    ip, rop = float(r["inventory_position"]), float(r["reorder_point"])
    gap = rop - ip
    decision = bool(r["reorder_triggered"])
    status = r["status"]
    style = STATUS_STYLE[status]

    po_list = [
        f"{int(po['quantity']):,} units arriving week {int(po['due_week'])}"
        for _, po in ctx.open_orders.iterrows()
    ]
    po_text = ("with " + " and ".join(po_list) + " already on order") if po_list else "with nothing on order"
    backorder_text = f", {int(r['backorders'])} units owed to customers" if r["backorders"] > 0 else ""

    if proj.first_zero_week is None:
        next_text = f"Stock stays above zero for all {p.projection_weeks} weeks at the forecast rate."
    elif proj.zero_within_lead_time:
        next_text = (
            f"Stock runs out in <b>week {proj.first_zero_week}</b>, <b>before</b> a new order could arrive "
            f"(week {lt + 1}). That is why this SKU is flagged as a stockout risk."
        )
    else:
        next_text = (
            f"Without any further action stock would run out in week {proj.first_zero_week}, after the lead time. "
            + (
                f"The next weekly review would place an order in week {proj.next_review_trigger_week}, in time."
                if proj.next_review_trigger_week and not decision
                else "Today's order is what prevents it."
            )
        )
    arrivals = []
    if po_list:
        arrivals.append("the open PO (green triangle)")
    if r["recommended_order"] > 0:
        arrivals.append(f"today's order in week {int(r['new_order_receipt_week'])} (star)")
    if arrivals:
        next_text += " The chart shows " + " and ".join(arrivals) + " landing."

    action = {
        Status.STOCKOUT_RISK.value: (
            "Expedite supply or manage the shortfall: a normal order cannot arrive in time."
            if decision
            else "Expedite the open purchase order: it lands after stock runs out."
        ),
        Status.REORDER_REQUIRED.value: f"Place an order for {fmt_units(r['recommended_order'])} units with {html.escape(r['supplier_name'])} this week.",
        Status.EXCESS_STOCK.value: "Do not reorder. Consider slowing inbound supply or a promotion to reduce cover.",
        Status.HEALTHY.value: "No action this week. The next weekly review will reorder when the position reaches the reorder point.",
    }[status]

    steps = [
        {
            "dot": "1",
            "eyebrow": "History",
            "title": "What customers bought",
            "text": f"Over the last 52 weeks customers bought <b>{last52.sum():,.0f} units</b>, about "
            f"<b>{last52.mean():,.0f} a week</b> (between {last52.min():,.0f} and {last52.max():,.0f}). The last quarter ran "
            f"<b>{change:+.0%}</b> against the quarter before, so demand looks <b>{trend_word}</b>.",
            "facts": [
                ("Avg / week", fmt_units(last52.mean()), False),
                ("Last 13 wks vs prior", f"{change:+.0%}", False),
                ("Weeks of history", f"{len(actual)}", False),
            ],
        },
        {
            "dot": "2",
            "eyebrow": "Forecast",
            "dot_bg": "#ECFEFF",
            "dot_fg": "#0891B2",
            "title": "How the forecast was chosen",
            "text": f"Four simple methods were replayed week by week on the last 52 weeks, each using only earlier data. "
            f"The winner is <b>{METHOD_LABELS[method].lower()}</b>. {why} It expects <b>{fc.weekly_forecast:,.1f} units a week</b> "
            f"for the next {p.projection_weeks} weeks.",
            "facts": [
                ("Method", METHOD_SHORT[method], False),
                ("Forecast / week", fmt_units(fc.weekly_forecast, 1), True),
            ]
            + [
                (f"WAPE {METHOD_SHORT[m]}", fmt_pct(scores.loc[m, "wape"]), False)
                for m in METHODS
                if m != method
            ][:2],
        },
        {
            "dot": "3",
            "eyebrow": "Reliability",
            "dot_bg": "#ECFEFF",
            "dot_fg": "#0891B2",
            "title": "How much to trust it",
            "text": f"Out of sample, the forecast was <b>{fmt_pct(1 - fc.wape)} accurate</b> (it missed by {fmt_pct(fc.wape)} of volume) and "
            f"{bias_text}. A typical weekly miss is <b>±{fc.error_sd:,.1f} units</b>: this uncertainty is what the safety stock has to cover.",
            "facts": [
                ("Accuracy", fmt_pct(1 - fc.wape), True),
                ("Bias", fmt_pct(fc.bias, signed=True), False),
                ("Typical miss", f"±{fc.error_sd:,.1f}", False),
            ],
        },
        {
            "dot": "4",
            "eyebrow": "Buffer",
            "dot_bg": "#FFFBEB",
            "dot_fg": "#B45309",
            "title": "The safety stock",
            "text": f"To stay in stock in about <b>{p.target_service_level:.0%} of replenishment cycles</b> over a "
            f"<b>{lt}-week lead time</b>, the plan holds <b>{r['safety_stock']:,.0f} extra units</b>. Bigger forecast misses or longer "
            f"lead times would mean a bigger buffer.",
            "facts": [
                ("Service level", f"{p.target_service_level:.1%}".replace(".0%", "%"), False),
                ("z-value", f"{p.z_value:.3f}", False),
                ("Safety stock", fmt_units(r["safety_stock"]), True),
            ],
            "extra": f'<div class="dp-story-formula">safety stock = z × error SD × √lead time = {p.z_value:.3f} × {fc.error_sd:.1f} × √{lt}</div>',
        },
        {
            "dot": "5",
            "eyebrow": "When to order",
            "dot_bg": "#FEF2F2",
            "dot_fg": "#B91C1C",
            "title": "Reorder point vs where we stand",
            "text": f"While a new order is on its way ({lt} weeks) customers will buy about <b>{r['lead_time_demand']:,.0f} units</b>; add the buffer and the "
            f"<b>reorder point is {rop:,.0f}</b>. Today there are {int(r['on_hand']):,} units on hand {po_text}{backorder_text}, an "
            f"<b>inventory position of {ip:,.0f}</b>: "
            + (
                f"<b>{gap:,.0f} units below</b> the reorder point, so an order is triggered."
                if decision
                else f"<b>{-gap:,.0f} units above</b> the reorder point, so no order yet."
            ),
            "facts": [
                ("Lead-time demand", fmt_units(r["lead_time_demand"]), False),
                ("Reorder point", fmt_units(rop), True),
                ("Inventory position", fmt_units(ip), False),
            ],
            "extra": gauge_html(ip, rop, max(rop * 1.8, ip * 1.15)),
        },
        {
            "dot": "6",
            "eyebrow": "How much",
            "dot_bg": "#ECFDF5",
            "dot_fg": "#047857",
            "title": "The order quantity (EOQ)",
            "text": f"Ordering costs {fmt_eur(r['ordering_cost_eur'])} per order and holding a unit costs {fmt_eur(r['holding_cost_per_unit'], 2)} a year. "
            f"The quantity that balances the two is the <b>EOQ of {r['eoq']:,.0f} units</b> (about {r['eoq'] / fc.weekly_forecast:.1f} weeks of demand, "
            f"~{r['annual_demand'] / r['eoq']:.0f} orders a year), rounded up to full cases of {int(r['case_pack'])}: <b>{int(r['eoq_rounded']):,} units</b>. "
            + (
                f"Recommended now: <b>{int(r['recommended_order']):,} units ({fmt_eur(r['recommended_order_value'])})</b>."
                if r["recommended_order"] > 0
                else "No order is placed this week."
            ),
            "facts": [
                ("EOQ", fmt_units(r["eoq"]), False),
                ("Rounded to case pack", fmt_units(r["eoq_rounded"]), False),
                ("Order now", fmt_units(r["recommended_order"]), True),
            ],
        },
        {
            "dot": "7",
            "eyebrow": "Next 12 weeks",
            "title": "What happens next",
            "text": next_text,
            "facts": [
                ("First zero week", str(proj.first_zero_week) if proj.first_zero_week else "none", False),
                ("Lowest projected stock", fmt_units(proj.min_closing), False),
                ("Weeks of cover", f"{r['weeks_of_cover']:.1f}", False),
            ],
        },
        {
            "dot": style["icon"],
            "eyebrow": "Verdict",
            "dot_bg": style["bg"],
            "dot_fg": style["color"],
            "title": "Decision for this week",
            "text": f"{status_badge(status)}&nbsp; {html.escape(r['reason'])}<br><br><b>Action:</b> {action}",
        },
    ]

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        story(steps)
    with right:
        with st.container(border=True):
            card_head(
                "Demand and forecast",
                "Actual demand (indigo) and the forecast (cyan).",
                tag=METHOD_SHORT[method],
            )
            st.plotly_chart(
                legend_below(
                    demand_forecast_chart(
                        fc, ctx.scenario, history_weeks=39, horizon_weeks=p.projection_weeks, height=330
                    )
                ),
                use_container_width=True,
                config=CONFIG,
                key="story_demand",
            )
        with st.container(border=True):
            card_head("Forecast method scores", "Walk-forward WAPE; the selected method in indigo.")
            st.plotly_chart(
                method_comparison_chart(fc), use_container_width=True, config=CONFIG, key="story_methods"
            )
        with st.container(border=True):
            card_head(
                "Forecast errors",
                f"Forecast − actual, last 52 weeks. Their spread (±{fc.error_sd:,.1f}) sizes the buffer.",
            )
            st.plotly_chart(
                forecast_error_chart(fc, ctx.scenario),
                use_container_width=True,
                config=CONFIG,
                key="story_errors",
            )
        with st.container(border=True):
            card_head(
                "Projected stock, next 12 weeks", "Existing orders and today's order included; nothing else."
            )
            st.plotly_chart(
                legend_below(
                    projection_chart(
                        proj,
                        safety_stock=float(r["safety_stock"]),
                        reorder_point=rop,
                        lead_time_weeks=lt,
                        scenario=ctx.scenario,
                        height=360,
                    )
                ),
                use_container_width=True,
                config=CONFIG,
                key="story_projection",
            )
        with st.container(border=True):
            card_head("Order size trade-off (EOQ)", "Total yearly cost is lowest at the EOQ.")
            st.plotly_chart(
                legend_below(
                    eoq_cost_chart(
                        float(r["annual_demand"]),
                        float(r["ordering_cost_eur"]),
                        float(r["holding_cost_per_unit"]),
                        float(r["eoq"]),
                        int(r["recommended_order"]),
                    ),
                    extra_bottom=90,
                    y=-0.3,
                ),
                use_container_width=True,
                config=CONFIG,
                key="story_eoq",
            )


# ============================================================================== demand & forecast
def render_demand(ctx: SkuContext) -> None:
    fc, p = ctx.fc, ctx.params
    kpi_row(
        [
            {
                "label": "Forecast / week",
                "value": fmt_units(fc.weekly_forecast, 1),
                "sub": METHOD_LABELS[fc.selected_method],
            },
            {
                "label": "Accuracy (1 − WAPE)",
                "value": fmt_pct(1 - fc.wape),
                "sub": f"WAPE {fmt_pct(fc.wape)}, last 52 weeks",
            },
            {"label": "Bias", "value": fmt_pct(fc.bias, signed=True), "sub": "positive = over-forecasting"},
            {"label": "Error SD", "value": f"±{fc.error_sd:,.1f}", "sub": "typical weekly miss, units"},
        ]
    )
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        with c1:
            card_head(
                "Demand history and forecast",
                "Each forecast point was made one week ahead, using only earlier weeks.",
            )
        with c2:
            span = st.segmented_control(
                "History",
                ["26 wks", "52 wks", "104 wks"],
                default="52 wks",
                key=f"span_{ctx.sku}",
                label_visibility="collapsed",
            )
        weeks = {"26 wks": 26, "52 wks": 52, "104 wks": 104}.get(span or "52 wks", 52)
        st.plotly_chart(
            demand_forecast_chart(
                fc, ctx.scenario, history_weeks=weeks, horizon_weeks=p.projection_weeks, height=360
            ),
            use_container_width=True,
            config=CONFIG,
            key="demand_main",
        )
    left, right = st.columns([1, 1.2], gap="medium")
    with left:
        with st.container(border=True):
            card_head(
                "Method comparison",
                f"Scored on weeks {fc.evaluation_window[0]}–{fc.evaluation_window[1]}. Simplest method within {p.wape_tolerance:.0%} of the best wins.",
            )
            st.plotly_chart(
                method_comparison_chart(fc), use_container_width=True, config=CONFIG, key="demand_methods"
            )
            scores = fc.method_scores.copy()
            table = pd.DataFrame(
                {
                    "Method": [
                        ("✓ " if s else "") + METHOD_SHORT[m]
                        for m, s in zip(scores.index, scores["selected"], strict=True)
                    ],
                    "WAPE": scores["wape"].to_numpy() * 100,
                    "Bias": scores["bias"].to_numpy() * 100,
                    "Error SD": scores["error_sd"].to_numpy(),
                    "Next week": scores["next_forecast"].to_numpy(),
                }
            )
            st.dataframe(
                table,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "WAPE": st.column_config.NumberColumn(format="%.1f%%"),
                    "Bias": st.column_config.NumberColumn(format="%+.1f%%"),
                    "Error SD": st.column_config.NumberColumn(format="%.1f"),
                    "Next week": st.column_config.NumberColumn(format="%.1f"),
                },
            )
    with right:
        with st.container(border=True):
            card_head(
                "Forecast errors, week by week",
                "Forecast − actual of the selected method. Their spread (SD) sizes the safety stock.",
            )
            st.plotly_chart(
                forecast_error_chart(fc, ctx.scenario),
                use_container_width=True,
                config=CONFIG,
                key="demand_errors",
            )
            st.caption(
                f"Cyan bars: over-forecast weeks · indigo bars: under-forecast weeks · shaded band: ±1 SD ({fc.error_sd:,.1f} units)."
            )


# ============================================================================== inventory & orders
def render_inventory(ctx: SkuContext) -> None:
    r, proj, p = ctx.row, ctx.proj, ctx.params
    ip, rop = float(r["inventory_position"]), float(r["reorder_point"])
    kpi_row(
        [
            {
                "label": "On hand",
                "value": fmt_units(r["on_hand"]),
                "sub": f"{r['weeks_of_cover_on_hand']:.1f} weeks of cover",
            },
            {
                "label": "On order",
                "value": fmt_units(r["on_order"]),
                "sub": f"{len(ctx.open_orders)} open PO" + ("s" if len(ctx.open_orders) != 1 else ""),
            },
            {"label": "Backorders", "value": fmt_units(r["backorders"]), "sub": "owed to customers"},
            {
                "label": "Inventory position",
                "value": fmt_units(ip),
                "sub": delta(f"{ip - rop:+,.0f} vs reorder point", ip > rop),
            },
            {
                "label": "Reorder point",
                "value": fmt_units(rop),
                "sub": f"{fmt_units(r['lead_time_demand'])} lead-time demand + {fmt_units(r['safety_stock'])} buffer",
            },
        ]
    )
    with st.container(border=True):
        card_head(
            f"Projected stock, next {p.projection_weeks} weeks",
            "Closing = opening + receipts − forecast demand. Only today's decision is included; future reviews are not simulated, "
            "so negative values are the shortfall if nothing else were done.",
        )
        st.plotly_chart(
            projection_chart(
                proj,
                safety_stock=float(r["safety_stock"]),
                reorder_point=rop,
                lead_time_weeks=ctx.lead_time,
                scenario=ctx.scenario,
                height=380,
            ),
            use_container_width=True,
            config=CONFIG,
            key="inv_projection",
        )
        with st.expander("Week-by-week projection table"):
            table = proj.table.copy()
            table["week_start"] = pd.to_datetime(table["week_start"])
            st.dataframe(
                table,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "week": st.column_config.NumberColumn("Week", format="%d"),
                    "week_start": st.column_config.DateColumn("Week starting", format="DD MMM YYYY"),
                    "opening_inventory": st.column_config.NumberColumn("Opening", format="%.0f"),
                    "existing_po_receipt": st.column_config.NumberColumn("Open PO receipt", format="%.0f"),
                    "new_order_receipt": st.column_config.NumberColumn("New order receipt", format="%.0f"),
                    "forecast_demand": st.column_config.NumberColumn("Forecast demand", format="%.1f"),
                    "closing_inventory": st.column_config.NumberColumn("Closing", format="%.0f"),
                    "projected_inventory_position": st.column_config.NumberColumn(
                        "Position incl. on order", format="%.0f"
                    ),
                },
            )
    left, right = st.columns([1.3, 1], gap="medium")
    with left:
        with st.container(border=True):
            card_head(
                "Why this order size: the EOQ trade-off",
                "Small orders cost more to place; large orders cost more to hold. EOQ sits at the lowest total cost.",
            )
            st.plotly_chart(
                eoq_cost_chart(
                    float(r["annual_demand"]),
                    float(r["ordering_cost_eur"]),
                    float(r["holding_cost_per_unit"]),
                    float(r["eoq"]),
                    int(r["recommended_order"]),
                ),
                use_container_width=True,
                config=CONFIG,
                key="inv_eoq",
            )
    with right:
        with st.container(border=True):
            card_head("Open purchase orders")
            if ctx.open_orders.empty:
                st.caption("No open purchase orders for this SKU.")
            else:
                pos = ctx.open_orders.assign(
                    arrives=[fmt_date(ctx.scenario.week_start(int(w))) for w in ctx.open_orders["due_week"]]
                )
                st.dataframe(
                    pos[["po_id", "quantity", "due_week", "arrives"]],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "po_id": "PO",
                        "quantity": st.column_config.NumberColumn("Units", format="%d"),
                        "due_week": st.column_config.NumberColumn("Due week", format="%d"),
                        "arrives": "Arrives",
                    },
                )
        with st.container(border=True):
            card_head("Recommended order")
            if r["recommended_order"] > 0:
                st.html(
                    f'<div class="dp-kpi-value" style="font-family:var(--dp-head);font-size:30px;font-weight:800;color:var(--dp-primary)">'
                    f"{int(r['recommended_order']):,} units</div>"
                    f'<div class="dp-reason" style="margin-top:6px">{fmt_eur(r["recommended_order_value"])} from {html.escape(r["supplier_name"])}, '
                    f"arriving week {int(r['new_order_receipt_week'])} ({fmt_date(ctx.scenario.week_start(int(r['new_order_receipt_week'])))}).</div>"
                )
            else:
                st.html(
                    f'<div class="dp-reason">No order this week. If triggered, the rounded EOQ would be <b>{int(r["eoq_rounded"]):,} units</b>.</div>'
                )


# ============================================================================== calculations (Excel-style)
def render_calculations(ctx: SkuContext) -> None:
    r, fc, p, proj = ctx.row, ctx.fc, ctx.params, ctx.proj
    z = p.z_value
    lt = ctx.lead_time
    errors = fc.errors
    wf = fc.walk_forward
    ev0, ev1 = fc.evaluation_window
    window = wf.loc[ev0:ev1]
    window_sum = window["actual"].sum()
    method = fc.selected_method
    last4 = ", ".join(f"{v:.0f}" for v in wf["actual"].tail(4))
    last8 = ", ".join(f"{v:.0f}" for v in wf["actual"].tail(8))
    numbers = {
        "MA4": f"average({last4})",
        "MA8": f"average({last8})",
        "SES": f"{p.ses_alpha} × {wf['actual'].iloc[-1]:.0f} + {1 - p.ses_alpha:.1f} × {wf['SES'].iloc[-1]:.1f}",
        "Naive": f"last actual = {wf['actual'].iloc[-1]:.0f}",
    }[method]
    excel_forecast = {
        "MA4": "=AVERAGE(C105:C108)  (last 4 actuals)",
        "MA8": "=AVERAGE(C101:C108)  (last 8 actuals)",
        "SES": "=SES_Alpha*C108+(1-SES_Alpha)*G108",
        "Naive": "=C108  (last actual)",
    }[method]
    decision = bool(r["reorder_triggered"])
    scores = fc.method_scores
    over_weeks = int((errors > 0).sum())
    ip = float(r["inventory_position"])
    rop = float(r["reorder_point"])

    head, button = st.columns([3, 1], vertical_alignment="center")
    with head:
        callout(
            "Every card recomputes one step with this SKU's own numbers, using the same formulas as the Excel validation model. "
            "The <b>Excel</b> line shows the exact formula in the downloadable workbook, where every step is a live formula "
            "you can change and watch recalculate. The Python engine matches the original workbook to 1e-9 for all 48 SKUs.",
            kind="info",
        )
    with button:
        from ui.state import sku_workbook

        st.download_button(
            "Download Excel workbook",
            data=sku_workbook(ctx.sku),
            file_name=f"{ctx.sku}_planning_workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/table_view:",
            use_container_width=True,
            key=f"xlsx_calc_{ctx.sku}",
        )

    subhead("1 · Forecast")
    step_cards(
        [
            {
                "number": 1,
                "title": "Weekly forecast",
                "formula": {
                    "Naive": "F = last week's actual",
                    "MA4": "F = average of the last 4 weeks",
                    "MA8": "F = average of the last 8 weeks",
                    "SES": "F = α·A(t) + (1−α)·F(t)",
                }[method],
                "numbers": numbers,
                "result": fmt_units(fc.weekly_forecast, 1),
                "unit": f"units / week · {METHOD_SHORT[method]}",
                "interpretation": f"Held flat for the next {p.projection_weeks} weeks: V1 has no trend or seasonality.",
                "source": f"<b>Method chosen</b> by walk-forward WAPE on weeks {ev0}–{ev1}: "
                + " · ".join(f"{METHOD_SHORT[m]} {scores.loc[m, 'wape']:.1%}" for m in METHODS),
                "excel": excel_forecast + " → Method_Selection!E",
                "why": "Every later number (lead-time demand, reorder point, EOQ, projection) scales with this forecast.",
            },
            {
                "number": 2,
                "title": "WAPE (accuracy)",
                "formula": "Σ|forecast − actual| ÷ Σ actual",
                "numbers": f"{errors.abs().sum():,.0f} ÷ {window_sum:,.0f}",
                "result": fmt_pct(fc.wape),
                "unit": "of volume",
                "interpretation": f"The forecast misses by {fc.wape:.1%} of actual volume on average, whatever the direction.",
                "source": f"<b>{len(errors)} weekly errors</b> from weeks {ev0}–{ev1}; each forecast used only earlier weeks.",
                "excel": f"=SUM(Forecast!{'LMNO'[METHODS.index(method)]}57:{'LMNO'[METHODS.index(method)]}108)/SUM(Forecast!C57:C108)",
                "why": "Selects the method. Volume-weighted, so zero-demand weeks do not explode it the way MAPE would.",
            },
            {
                "number": 3,
                "title": "Bias (direction)",
                "formula": "Σ(forecast − actual) ÷ Σ actual",
                "numbers": f"{errors.sum():+,.0f} ÷ {window_sum:,.0f}",
                "result": fmt_pct(fc.bias, signed=True),
                "unit": "over" if fc.bias > 0 else "under",
                "interpretation": f"Positive = over-forecasting. {over_weeks} of {len(errors)} weeks were over-forecast.",
                "source": "<b>Same errors as WAPE</b>, but signed, so over- and under-forecasts cancel.",
                "excel": f"=SUM(Forecast!{'HIJK'[METHODS.index(method)]}57:{'HIJK'[METHODS.index(method)]}108)/SUM(Forecast!C57:C108)",
                "why": "A persistent bias means systematic over-stock (positive) or stockouts (negative) that safety stock cannot fix.",
            },
            {
                "number": 4,
                "title": "Forecast error SD",
                "formula": "STDEV.S of weekly errors",
                "numbers": f"{len(errors)} errors, mean {errors.mean():+.1f}, range {errors.min():+.0f} to {errors.max():+.0f}",
                "result": fmt_units(fc.error_sd, 1),
                "unit": "units",
                "interpretation": f"A typical weekly miss is about ±{fc.error_sd:,.1f} units.",
                "source": "<b>Sample standard deviation</b> (n − 1), exactly like Excel's STDEV.S.",
                "excel": f"=STDEV.S(Forecast!{'HIJK'[METHODS.index(method)]}57:{'HIJK'[METHODS.index(method)]}108)",
                "why": "This is the uncertainty safety stock protects against: bigger historical misses mean a bigger buffer.",
            },
        ]
    )

    subhead("2 · When to order")
    step_cards(
        [
            {
                "number": 5,
                "title": "z-value",
                "formula": "z = NORM.S.INV(service level)",
                "numbers": f"NORM.S.INV({p.target_service_level:.3f})",
                "result": f"{z:.3f}",
                "unit": f"for {p.target_service_level:.1%}",
                "interpretation": "Standard deviations of protection for the target cycle service level.",
                "source": "<b>Service level</b> from the sidebar. 90% → 1.282 · 95% → 1.645 · 99% → 2.326.",
                "excel": "=NORM.S.INV(TSL)",
                "why": "Going from 95% to 99% adds 41% more safety stock: the last few points of service are the most expensive.",
            },
            {
                "number": 6,
                "title": "Safety stock",
                "formula": "z × error SD × √lead time",
                "numbers": f"{z:.3f} × {fc.error_sd:.1f} × √{lt} = {z:.3f} × {fc.error_sd:.1f} × {lt**0.5:.3f}",
                "result": fmt_units(r["safety_stock"]),
                "unit": "units",
                "interpretation": f"About {r['safety_stock'] / fc.weekly_forecast:.1f} weeks of demand held as a buffer.",
                "source": f"<b>Lead time</b> {lt} week{'s' if lt != 1 else ''} from supplier {html.escape(r['supplier_name'])} (fixed).",
                "excel": "=Z_Value*Error_SD*SQRT(Lead_Time)",
                "why": "Assumes a fixed lead time and roughly independent weekly errors (the square-root-of-time rule).",
            },
            {
                "number": 7,
                "title": "Lead-time demand",
                "formula": "weekly forecast × lead time",
                "numbers": f"{fc.weekly_forecast:.1f} × {lt}",
                "result": fmt_units(r["lead_time_demand"]),
                "unit": "units",
                "interpretation": "Expected customer demand while a new order is on its way.",
                "source": "<b>Forecast</b> from step 1 · <b>lead time</b> from the supplier.",
                "excel": "=Forecast*Lead_Time",
                "why": "Stock needed just to keep serving normal demand until the replenishment lands.",
            },
            {
                "number": 8,
                "title": "Reorder point",
                "formula": "lead-time demand + safety stock",
                "numbers": f"{r['lead_time_demand']:,.1f} + {r['safety_stock']:,.1f}",
                "result": fmt_units(rop),
                "unit": "units",
                "interpretation": "Order when the inventory position is at or below this level.",
                "source": "<b>Steps 6 + 7.</b> Compared with the inventory position, never with on-hand stock alone.",
                "excel": "=LT_Demand+Safety_Stock",
                "why": "Answers WHEN to order.",
            },
        ]
    )

    subhead("3 · Order decision")
    po_text = (
        "; ".join(
            f"{po['po_id']}: {int(po['quantity']):,} due week {int(po['due_week'])}"
            for _, po in ctx.open_orders.iterrows()
        )
        if not ctx.open_orders.empty
        else "no open purchase orders"
    )
    step_cards(
        [
            {
                "number": 9,
                "title": "Inventory position",
                "formula": "on hand + on order − backorders",
                "numbers": f"{int(r['on_hand']):,} + {int(r['on_order']):,} − {int(r['backorders']):,}",
                "result": fmt_units(ip),
                "unit": "units",
                "interpretation": "Stock available or already on its way, net of what is owed to customers."
                + (
                    f" <b>Negative: backorders exceed stock by {int(r['shortage_units'])} units.</b>"
                    if ip < 0
                    else ""
                ),
                "source": f"<b>Open POs:</b> {po_text}.",
                "excel": "=On_Hand+On_Order-Backorders",
                "why": "Counting stock already on order is what prevents a duplicate order every week.",
            },
            {
                "number": 10,
                "title": "Reorder decision",
                "formula": "inventory position ≤ reorder point?",
                "numbers": f"{ip:,.0f} ≤ {rop:,.1f} ?",
                "result": "YES – order" if decision else "NO – wait",
                "interpretation": (
                    f"{rop - ip:,.0f} units at or below the reorder point."
                    if decision
                    else f"{ip - rop:,.0f} units above the reorder point."
                ),
                "source": "<b>Steps 8 + 9.</b> Checked once a week (weekly review).",
                "excel": '=IF(Inv_Position<=ROP,"YES","NO")',
                "why": "The trigger. Without it, EOQ would say how much to buy but never when.",
            },
            {
                "number": 11,
                "title": "Weeks of cover",
                "formula": "max(inventory position, 0) ÷ weekly forecast",
                "numbers": f"{max(ip, 0):,.0f} ÷ {fc.weekly_forecast:.1f}",
                "result": f"{r['weeks_of_cover']:.1f}",
                "unit": "weeks",
                "interpretation": f"On-hand stock alone covers {r['weeks_of_cover_on_hand']:.1f} weeks.",
                "source": f"<b>Excess threshold</b> {p.excess_weeks_of_cover:g} weeks (sidebar).",
                "excel": "=IF(Forecast>0,MAX(Inv_Position,0)/Forecast,0)",
                "why": "The quickest health check: too low risks stockouts, too high ties up cash.",
            },
        ],
        cols=3,
    )

    subhead("4 · How much to order")
    step_cards(
        [
            {
                "number": 12,
                "title": "Annual demand",
                "formula": "weekly forecast × 52",
                "numbers": f"{fc.weekly_forecast:.2f} × {p.weeks_per_year}",
                "result": fmt_units(r["annual_demand"]),
                "unit": "units / year",
                "interpretation": "The weekly rate is assumed to hold all year.",
                "source": "<b>Forecast</b> from step 1.",
                "excel": "=Forecast*Weeks_Per_Year",
                "why": "EOQ is defined on annual quantities and annual holding cost.",
            },
            {
                "number": 13,
                "title": "Holding cost / unit",
                "formula": "unit cost × annual holding rate",
                "numbers": f"{fmt_eur(r['unit_cost_eur'], 2)} × {p.annual_holding_rate:.0%}",
                "result": fmt_eur(r["holding_cost_per_unit"], 2),
                "unit": "per year",
                "interpretation": f"Ordering cost is {fmt_eur(r['ordering_cost_eur'])} per order (supplier).",
                "source": "<b>Holding rate</b> from the sidebar: capital, storage, obsolescence.",
                "excel": "=Unit_Cost*Holding_Rate",
                "why": "The cost that pushes towards smaller, more frequent orders.",
            },
            {
                "number": 14,
                "title": "EOQ",
                "formula": "√(2 × D × ordering cost ÷ H)",
                "numbers": f"√(2 × {r['annual_demand']:,.0f} × {r['ordering_cost_eur']:.0f} ÷ {r['holding_cost_per_unit']:.2f})",
                "result": fmt_units(r["eoq"]),
                "unit": "units",
                "interpretation": f"≈ {r['eoq'] / fc.weekly_forecast:.1f} weeks of demand per order, ~{r['annual_demand'] / r['eoq']:.0f} orders a year.",
                "source": "<b>Steps 12 + 13</b> and the supplier's ordering cost.",
                "excel": "=SQRT(2*Annual_Demand*Ordering_Cost/Holding_Cost)",
                "why": "Answers HOW MUCH. Total cost is flat near the EOQ, so rounding to cases costs little.",
            },
            {
                "number": 15,
                "title": "Recommended order",
                "formula": "if triggered: ROUNDUP(EOQ ÷ pack) × pack",
                "numbers": f"ROUNDUP({r['eoq']:.1f} ÷ {int(r['case_pack'])}) × {int(r['case_pack'])} = {int(r['eoq_rounded']):,}",
                "result": fmt_units(r["recommended_order"]),
                "unit": "units",
                "interpretation": (
                    f"Worth {fmt_eur(r['recommended_order_value'])}, arriving week {int(r['new_order_receipt_week'])}."
                    if r["recommended_order"] > 0
                    else "Zero: the reorder point is not reached this week."
                ),
                "source": "<b>Step 10</b> decides whether; <b>step 14</b> decides how much.",
                "excel": '=IF(Trigger="YES",EOQ_Rounded,0) with EOQ_Rounded =ROUNDUP(EOQ/Case_Pack,0)*Case_Pack',
                "why": "One EOQ per weekly review; if the position is far below the ROP the next review orders again.",
            },
        ]
    )

    subhead("5 · Projection and status")
    zero_week = proj.first_zero_week
    step_cards(
        [
            {
                "number": 16,
                "title": "12-week projection",
                "formula": "closing = opening + receipts − forecast",
                "numbers": f"week 1: {int(r['on_hand']) - int(r['backorders']):,} + {proj.table['existing_po_receipt'].iloc[0]:,.0f} + {proj.table['new_order_receipt'].iloc[0]:,.0f} − {fc.weekly_forecast:.1f}",
                "result": fmt_units(proj.table["closing_inventory"].iloc[0]),
                "unit": "units at end of week 1",
                "interpretation": f"Lowest projected stock {proj.min_closing:,.0f}; week 12 closes at {proj.table['closing_inventory'].iloc[-1]:,.0f}.",
                "source": "<b>Only today's decision</b> is included; future weekly reviews are not simulated.",
                "excel": "=C5+D5+E5-F5  (Projection sheet, row per week)",
                "why": "Shows whether open POs and today's order arrive before stock runs out.",
            },
            {
                "number": 17,
                "title": "First zero week",
                "formula": "first week with closing ≤ 0",
                "numbers": f"lead time {lt} wk → a new order lands in week {lt + 1}",
                "result": str(zero_week) if zero_week else "none",
                "unit": "inside the lead time"
                if proj.zero_within_lead_time
                else ("after the lead time" if zero_week else ""),
                "interpretation": "Zero inside the lead time means no order placed today can prevent the stockout.",
                "source": "<b>Projection</b> from step 16.",
                "excel": '=IFERROR(MATCH(1,H5:H16,0),"None")',
                "why": "This is what separates STOCKOUT RISK from a normal reorder.",
            },
            {
                "number": 18,
                "title": "Planning status",
                "formula": "risk → reorder → excess → healthy",
                "numbers": f"zero in LT: {'YES' if proj.zero_within_lead_time else 'NO'} · trigger: {'YES' if decision else 'NO'} · cover {r['weeks_of_cover']:.1f}",
                "result": status_badge(r["status"], large=True),
                "interpretation": html.escape(r["reason"]),
                "source": "<b>Steps 10, 11 and 17</b>, checked in priority order.",
                "excel": '=IF(Zero_In_LT="YES","STOCKOUT RISK",IF(Trigger="YES","REORDER REQUIRED",IF(WoC>Excess_WoC,"EXCESS STOCK","HEALTHY")))',
                "why": "One status per SKU, with the reason built from its own numbers.",
            },
        ],
        cols=3,
    )


# ============================================================================== backtest for one SKU
def render_backtest(ctx: SkuContext) -> None:
    bt = ctx.result.backtest
    detail = bt.sku_detail(ctx.sku)
    m = bt.sku_summary[bt.sku_summary["sku"] == ctx.sku].set_index("policy")
    a, b = m.loc[BASELINE], m.loc[PROPOSED]
    kpi_row(
        [
            {
                "label": "Fill rate (proposed)",
                "value": fmt_pct(b["fill_rate"]),
                "sub": f"baseline {fmt_pct(a['fill_rate'])} · "
                + delta(
                    f"{(b['fill_rate'] - a['fill_rate']) * 100:+.1f} pp", b["fill_rate"] >= a["fill_rate"]
                ),
            },
            {
                "label": "Stockout weeks",
                "value": f"{b['stockout_weeks']:.0f}",
                "sub": f"baseline {a['stockout_weeks']:.0f} · "
                + delta(
                    f"{b['stockout_weeks'] - a['stockout_weeks']:+.0f}",
                    b["stockout_weeks"] <= a["stockout_weeks"],
                ),
            },
            {
                "label": "Orders placed",
                "value": f"{b['number_of_orders']:.0f}",
                "sub": f"baseline {a['number_of_orders']:.0f} · "
                + delta(
                    f"{b['number_of_orders'] - a['number_of_orders']:+.0f}",
                    b["number_of_orders"] <= a["number_of_orders"],
                ),
            },
            {
                "label": "Avg inventory value",
                "value": fmt_eur(b["average_inventory_value"]),
                "sub": f"baseline {fmt_eur(a['average_inventory_value'])} · "
                + delta(
                    f"{(b['average_inventory_value'] / a['average_inventory_value'] - 1) * 100:+.0f}%",
                    b["average_inventory_value"] <= a["average_inventory_value"],
                ),
            },
        ]
    )
    with st.container(border=True):
        card_head(
            f"Replay of weeks {bt.weeks[0]}–{bt.weeks[1]} for this SKU",
            "Both policies start from the same stock. Lost-sale weeks are marked ×. No future data is used at any decision.",
        )
        st.plotly_chart(
            legend_below(
                backtest_sku_chart(detail, POLICY_LABELS[BASELINE], POLICY_LABELS[PROPOSED]),
                extra_bottom=110,
                y=-0.2,
            ),
            use_container_width=True,
            config=CONFIG,
            key="sku_bt",
        )
