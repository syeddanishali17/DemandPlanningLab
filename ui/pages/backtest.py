"""Backtest: replay of the final weeks comparing the four-week baseline with the proposed policy."""

import pandas as pd
import streamlit as st

from planning.backtest import BASELINE, METRIC_LABELS, POLICY_LABELS, PROPOSED
from ui.charts import backtest_sku_chart, backtest_tradeoff_chart, legend_below
from ui.components import callout, delta, hero, kpi_row, section, simple_table
from ui.state import current_plan
from ui.theme import SERIES, STATUS_COLOR, fmt_eur, fmt_pct, fmt_units

result = current_plan()
bt = result.backtest
params = result.params
plan = result.plan
start, end = bt.weeks
n_weeks = end - start + 1
n_skus = plan["sku"].nunique()

hero(
    "Historical backtest",
    "Does the proposed policy actually beat a simple rule?",
    f"The final {n_weeks} weeks of history (weeks {start}–{end}) are replayed for all {n_skus} SKUs, "
    "week by week, using only the information a planner would have had at the time. Two policies, same starting stock, "
    "same lead times and case packs; unmet demand is a lost sale.",
)

# ---------------------------------------------------------------- headline KPIs
fill_a, fill_b = bt.metric(BASELINE, "fill_rate"), bt.metric(PROPOSED, "fill_rate")
so_a, so_b = bt.metric(BASELINE, "stockout_weeks"), bt.metric(PROPOSED, "stockout_weeks")
ord_a, ord_b = bt.metric(BASELINE, "number_of_orders"), bt.metric(PROPOSED, "number_of_orders")
val_a, val_b = bt.metric(BASELINE, "average_inventory_value"), bt.metric(PROPOSED, "average_inventory_value")


def _delta(text: str, good: bool | None) -> str:
    return f"{delta(text, good)} vs baseline"


kpi_row(
    [
        {
            "label": "Fill rate (proposed)",
            "value": fmt_pct(fill_b),
            "sub": _delta(f"{(fill_b - fill_a) * 100:+.1f} pp", fill_b >= fill_a),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Stockout SKU-weeks",
            "value": f"{so_b:.0f}",
            "sub": _delta(f"{so_b - so_a:+.0f}", so_b <= so_a),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Orders placed",
            "value": f"{ord_b:.0f}",
            "sub": _delta(f"{ord_b - ord_a:+.0f}", ord_b <= ord_a),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Avg inventory value",
            "value": fmt_eur(val_b),
            "sub": _delta(f"{(val_b / val_a - 1) * 100:+.0f}%", val_b <= val_a),
            "accent": SERIES["proposed"],
        },
    ]
)

# ---------------------------------------------------------------- comparison table
HOW_TO_READ = {
    "fill_rate": "Units sold ÷ units demanded. Higher is better.",
    "stockout_weeks": f"SKU-weeks with any lost sale ({n_skus} SKUs × {n_weeks} weeks = {n_skus * n_weeks:,} possible). Lower is better.",
    "average_inventory_units": "Average end-of-week units across all SKUs. Units of different SKUs are not comparable: see value.",
    "number_of_orders": "Purchase orders placed. Fewer orders = less ordering workload and cost.",
    "average_inventory_value": "Average end-of-week stock at unit cost. The fair way to compare inventory across SKUs.",
}
rows = []
for metric, label in METRIC_LABELS.items():
    a, b = bt.metric(BASELINE, metric), bt.metric(PROPOSED, metric)
    if metric == "fill_rate":
        fmt_a, fmt_b, diff = fmt_pct(a), fmt_pct(b), f"{(b - a) * 100:+.1f} pp"
    elif metric == "average_inventory_value":
        fmt_a, fmt_b, diff = fmt_eur(a), fmt_eur(b), f"{fmt_eur(b - a)} ({(b / a - 1) * 100:+.0f}%)"
    else:
        fmt_a, fmt_b, diff = fmt_units(a), fmt_units(b), f"{b - a:+,.0f}"
    rows.append([label, fmt_a, fmt_b, diff, HOW_TO_READ[metric]])
simple_table(
    [
        "Metric",
        "Baseline: four weeks of stock",
        "Proposed: forecast + SS + ROP + EOQ",
        "Difference (proposed − baseline)",
        "How to read it",
    ],
    rows,
    numeric=(1, 2, 3),
    widths=("18%", "15%", "17%", "17%", "33%"),
    strong_first=True,
)

if fill_b > fill_a and val_b > val_a:
    verdict = "Better service came with more inventory: a trade-off, not a free win."
elif fill_b >= fill_a and val_b <= val_a:
    verdict = "Service improved without extra inventory."
elif fill_b < fill_a and val_b < val_a:
    verdict = "Less inventory, but lower service."
else:
    verdict = "Lower service with more inventory: review the parameters."
callout(
    f"<strong>Reading.</strong> The proposed policy reached a fill rate of {fill_b:.1%} vs {fill_a:.1%} for the baseline, "
    f"with {so_b:.0f} vs {so_a:.0f} stockout SKU-weeks and {ord_b:.0f} vs {ord_a:.0f} orders, while average inventory value was "
    f"{abs(val_b / val_a - 1):.0%} {'higher' if val_b >= val_a else 'lower'}. {verdict} "
    "Results come from one synthetic scenario and a short window; they show trade-offs, not proof of general superiority.",
    kind="info",
)

callout(
    "<strong>Two different service measures.</strong> The sidebar's target "
    f"({params.target_service_level:.1%}) is a <em>cycle service level</em>: the probability of not running out during one "
    "replenishment cycle, which sets the z-value in safety stock. The backtest measures <em>fill rate</em>: the share of "
    "units demanded that were actually shipped. They are related but not the same number, so fill rates here are compared "
    "between policies, not against the cycle-service target. V1 sets no separate fill-rate goal.",
    kind="note",
)
callout(
    "<strong>How the replay works.</strong><br>"
    f"<strong>Baseline · four weeks of stock.</strong> If inventory position &lt; {params.baseline_weeks_of_stock} × trailing 4-week average demand, "
    "order up to that level (rounded up to the case pack).<br>"
    f"<strong>Proposed · forecast + safety stock + ROP + EOQ.</strong> Forecast method and error SD calibrated on weeks "
    f"{bt.calibration_window[0]}–{bt.calibration_window[1]} only; each week: ROP = forecast × LT + z × error SD × √LT; "
    "if inventory position ≤ ROP, order EOQ rounded up.<br>"
    "<strong>Weekly sequence.</strong> Receive orders placed a lead time ago → review inventory position → place order → serve demand from stock, shortfall lost. "
    f"Both policies open week {start} with {params.backtest_opening_cover_weeks} weeks of trailing 8-week average demand on hand and nothing on order.",
    kind="note",
)


# ---------------------------------------------------------------- by lead time
section(
    "The same result by supplier lead time", sub="Where the difference between the two policies comes from."
)
lt = (
    bt.sku_summary.merge(plan[["sku", "lead_time_weeks"]], on="sku")
    .groupby(["lead_time_weeks", "policy"])
    .agg(
        skus=("sku", "count"),
        lost=("lost_units", "sum"),
        demanded=("units_demanded", "sum"),
        value=("average_inventory_value", "sum"),
        orders=("number_of_orders", "sum"),
        stockouts=("stockout_weeks", "sum"),
    )
    .reset_index()
)
lt["fill_rate"] = 1 - lt["lost"] / lt["demanded"]
lt_rows = []
for lead_time, grp in lt.groupby("lead_time_weeks"):
    a = grp[grp["policy"] == BASELINE].iloc[0]
    b = grp[grp["policy"] == PROPOSED].iloc[0]
    better = b["fill_rate"] >= a["fill_rate"]
    colour = STATUS_COLOR["HEALTHY"] if better else STATUS_COLOR["STOCKOUT RISK"]
    lt_rows.append(
        [
            f"{int(lead_time)} week{'s' if lead_time > 1 else ''}",
            f"{int(a['skus'])}",
            fmt_pct(a["fill_rate"]),
            fmt_pct(b["fill_rate"]),
            f'<span style="color:{colour};font-weight:600">{(b["fill_rate"] - a["fill_rate"]) * 100:+.1f} pp</span>',
            f"{int(a['stockouts'])} → {int(b['stockouts'])}",
            f"{int(a['orders'])} → {int(b['orders'])}",
            f"{fmt_eur(a['value'])} → {fmt_eur(b['value'])} ({(b['value'] / a['value'] - 1) * 100:+.0f}%)",
        ]
    )
simple_table(
    [
        "Lead time",
        "SKUs",
        "Fill rate · baseline",
        "Fill rate · proposed",
        "Change",
        "Stockout SKU-weeks",
        "Orders",
        "Avg inventory value (baseline → proposed)",
    ],
    lt_rows,
    numeric=(1, 2, 3, 4, 5, 6, 7),
    widths=("10%", "6%", "12%", "12%", "9%", "14%", "11%", "26%"),
    strong_first=True,
)
prop = lt[lt["policy"] == PROPOSED].set_index("lead_time_weeks")["fill_rate"]
base = lt[lt["policy"] == BASELINE].set_index("lead_time_weeks")["fill_rate"]
shortest, longest = int(prop.index.min()), int(prop.index.max())
weakest_lt = int(prop.idxmin())
limitation = (
    f"That is consistent with the {shortest}-week lead time having the lowest proposed fill rate "
    f"({prop.loc[shortest]:.1%}); protecting over lead time + 1 week is the first change for V1.1."
    if weakest_lt == shortest
    else f"The lowest proposed fill rate is at the {weakest_lt}-week lead time ({prop.loc[weakest_lt]:.1%})."
)
callout(
    "<strong>Why the picture differs by lead time.</strong> “Four weeks of stock” is blind to the lead time: its fill rate "
    f"runs from {base.loc[shortest]:.1%} at a {shortest}-week lead time down to {base.loc[longest]:.1%} at {longest} weeks. "
    "The proposed policy sizes protection to each lead time and forecast error, so its fill rate stays in a narrower band, "
    f"{prop.min():.1%} to {prop.max():.1%}, across all suppliers. "
    "<strong>Known V1 limitation:</strong> safety stock covers the lead time only, not lead time + the one-week review period, "
    "so a SKU can sit just above its reorder point at one review and run out before the next. " + limitation,
    kind="info",
)

# ---------------------------------------------------------------- per-SKU trade-off
section("Where the proposed policy helps, and where it does not")
t1, t2 = st.columns([3, 2], gap="medium")
with t1:
    st.caption(
        "Each dot is one SKU: change in fill rate (up = better service) against change in average inventory value "
        "(right = more stock), proposed minus baseline."
    )
    st.plotly_chart(
        backtest_tradeoff_chart(bt.sku_summary, plan),
        use_container_width=True,
        config={"displayModeBar": False},
    )
with t2:
    wide = bt.sku_summary.pivot(
        index="sku",
        columns="policy",
        values=["fill_rate", "average_inventory_value", "number_of_orders", "stockout_weeks"],
    )
    worse = wide[wide[("fill_rate", PROPOSED)] < wide[("fill_rate", BASELINE)]]
    st.markdown(f"**SKUs with a lower fill rate under the proposed policy: {len(worse)} of {len(wide)}**")
    if worse.empty:
        st.caption("None in this replay.")
    else:
        lead_times = plan.set_index("sku")["lead_time_weeks"]
        table = pd.DataFrame(
            {
                "SKU": worse.index,
                "LT (wks)": lead_times.reindex(worse.index).to_numpy(),
                "Fill · baseline": worse[("fill_rate", BASELINE)].to_numpy() * 100,
                "Fill · proposed": worse[("fill_rate", PROPOSED)].to_numpy() * 100,
            }
        ).sort_values("Fill · proposed")
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            height=min(400, 42 + 35 * len(table)),
            column_config={
                "SKU": st.column_config.TextColumn(width=90),
                "LT (wks)": st.column_config.NumberColumn(format="%d", width=70),
                "Fill · baseline": st.column_config.NumberColumn(format="%.1f%%", width=95),
                "Fill · proposed": st.column_config.NumberColumn(format="%.1f%%", width=95),
            },
        )
        st.caption(
            "Almost all are short-lead-time SKUs: the baseline reorders nearly every week, while the proposed policy "
            "accepts a small service risk between reviews in exchange for far fewer orders. Reported as found."
        )

# ---------------------------------------------------------------- representative SKU
section(
    "Week by week for one SKU",
    sub="Pick any SKU to replay both policies side by side. Defaults to the SKU you last opened in the SKU Explorer.",
)
skus = plan["sku"].tolist()
labels = {r["sku"]: f"{r['sku']} · {r['product_name']}" for _, r in plan.iterrows()}
default = st.session_state.get("selected_sku", "KIT-006")
c1, _ = st.columns([2, 3])
with c1:
    sku = st.selectbox(
        "SKU",
        skus,
        index=skus.index(default) if default in skus else 0,
        format_func=lambda s: labels[s],
        label_visibility="collapsed",
        key=f"bt_sku_{default}",
    )
detail = bt.sku_detail(sku)
row = result.sku_plan(sku)
method = detail.loc[detail["policy"] == PROPOSED, "forecast_method"].iloc[0]
sku_metrics = bt.sku_summary[bt.sku_summary["sku"] == sku].set_index("policy")
m_a, m_b = sku_metrics.loc[BASELINE], sku_metrics.loc[PROPOSED]
kpi_row(
    [
        {
            "label": "Lead time",
            "value": f"{int(row['lead_time_weeks'])} weeks",
            "sub": f"proposed forecast: {method}",
        },
        {
            "label": "Fill rate",
            "value": fmt_pct(m_b["fill_rate"]),
            "sub": f"baseline {fmt_pct(m_a['fill_rate'])} · "
            + delta(
                f"{(m_b['fill_rate'] - m_a['fill_rate']) * 100:+.1f} pp", m_b["fill_rate"] >= m_a["fill_rate"]
            ),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Stockout weeks",
            "value": f"{m_b['stockout_weeks']:.0f}",
            "sub": f"baseline {m_a['stockout_weeks']:.0f} · "
            + delta(
                f"{m_b['stockout_weeks'] - m_a['stockout_weeks']:+.0f}",
                m_b["stockout_weeks"] <= m_a["stockout_weeks"],
            ),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Orders placed",
            "value": f"{m_b['number_of_orders']:.0f}",
            "sub": f"baseline {m_a['number_of_orders']:.0f} · "
            + delta(
                f"{m_b['number_of_orders'] - m_a['number_of_orders']:+.0f}",
                m_b["number_of_orders"] <= m_a["number_of_orders"],
            ),
            "accent": SERIES["proposed"],
        },
        {
            "label": "Avg inventory value",
            "value": fmt_eur(m_b["average_inventory_value"]),
            "sub": f"baseline {fmt_eur(m_a['average_inventory_value'])} · "
            + delta(
                f"{(m_b['average_inventory_value'] / m_a['average_inventory_value'] - 1) * 100:+.0f}%",
                m_b["average_inventory_value"] <= m_a["average_inventory_value"],
            ),
            "accent": SERIES["proposed"],
        },
    ]
)
st.plotly_chart(
    legend_below(
        backtest_sku_chart(detail, POLICY_LABELS[BASELINE], POLICY_LABELS[PROPOSED]), extra_bottom=110, y=-0.2
    ),
    use_container_width=True,
    config={"displayModeBar": False},
)
st.caption(
    "Closing stock per week for both policies, actual demand as bars, lost-sale weeks marked with ×, and the proposed policy's reorder point."
)
with st.expander("Weekly detail table"):
    cols = [
        "policy",
        "week",
        "actual_demand",
        "forecast",
        "receipts",
        "stock_start",
        "on_order",
        "inventory_position",
        "reorder_point",
        "order",
        "sales",
        "lost_sales",
        "closing_stock",
    ]
    st.dataframe(
        detail[cols].sort_values(["policy", "week"]),
        hide_index=True,
        use_container_width=True,
        column_config={
            c: st.column_config.NumberColumn(format="%.0f")
            for c in cols
            if c not in ("policy", "week", "forecast", "reorder_point")
        }
        | {
            "forecast": st.column_config.NumberColumn(format="%.1f"),
            "reorder_point": st.column_config.NumberColumn(format="%.1f"),
        },
    )
