"""Plotly chart builders. One function per chart; all share the same base layout and colour meanings."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from planning.data import Scenario
from planning.exceptions import STATUS_ORDER
from planning.forecasting import METHOD_SHORT, SkuForecast
from planning.projection import ProjectionResult
from ui.theme import BORDER, MUTED, PRIMARY, SERIES, STATUS_COLOR, STATUS_SHORT, SUBTLE, TEXT

FONT = "Inter, sans-serif"
GRID = "#EDEFF6"
CONFIG = {"displayModeBar": False}


def base_layout(height: int = 360, **overrides) -> dict:
    layout = dict(
        height=height,
        margin=dict(l=8, r=8, t=34, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=TEXT),
        hoverlabel=dict(font=dict(family=FONT, size=13, color=TEXT), bgcolor="white", bordercolor=BORDER),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12, color=MUTED),
            itemclick=False,
            itemdoubleclick=False,
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            linecolor=BORDER,
            tickfont=dict(size=12, color=MUTED),
            title_font=dict(size=12, color=MUTED),
        ),
        yaxis=dict(
            gridcolor=GRID,
            zeroline=False,
            tickfont=dict(size=12, color=MUTED),
            title_font=dict(size=12, color=MUTED),
        ),
    )
    layout.update(overrides)
    return layout


def _gradient(rgb: str, top: float = 0.28) -> dict:
    """Vertical fade from the line colour to transparent (the Circly-style area look)."""
    return dict(type="vertical", colorscale=[[0.0, f"rgba({rgb},0)"], [1.0, f"rgba({rgb},{top})"]])


INDIGO_RGB = "79,70,229"
CYAN_RGB = "6,182,212"


def _hline(
    fig: go.Figure, y: float, colour: str, label: str, dash: str = "dash", position: str = "top left"
) -> None:
    fig.add_hline(
        y=y,
        line=dict(color=colour, width=1.5, dash=dash),
        annotation_text=label,
        annotation_position=position,
        annotation_font=dict(size=11, color=colour, family=FONT),
    )


# --------------------------------------------------------------------------- dashboard
def portfolio_demand_chart(
    forecasts: dict[str, SkuForecast], scenario: Scenario, horizon_weeks: int = 12
) -> go.Figure:
    """Total weekly demand (last 52 weeks) vs the selected methods' walk-forward forecast, plus the forward forecast."""
    actual = sum(fc.walk_forward["actual"] for fc in forecasts.values())
    fitted = sum(fc.walk_forward[fc.selected_method] for fc in forecasts.values())
    last_week = int(actual.index.max())
    window = actual.index[actual.index > last_week - 52]
    dates = [scenario.snapshot_date - timedelta(weeks=last_week - int(w) + 1) for w in window]
    forward = sum(fc.weekly_forecast for fc in forecasts.values())
    fwd_dates = [dates[-1]] + [scenario.week_start(w) for w in range(1, horizon_weeks + 1)]

    fig = go.Figure()
    fig.add_scatter(
        x=dates,
        y=actual.loc[window],
        mode="lines",
        name="Actual demand",
        line=dict(color=SERIES["actual"], width=2.4, shape="spline", smoothing=0.6),
        fill="tozeroy",
        fillgradient=_gradient(INDIGO_RGB, 0.20),
        hovertemplate="Week of %{x|%d %b %Y}<br>Actual: <b>%{y:,.0f}</b> units<extra></extra>",
    )
    fig.add_scatter(
        x=dates,
        y=fitted.loc[window],
        mode="lines",
        name="Forecast (made a week earlier)",
        line=dict(color=SERIES["forecast"], width=2, shape="spline", smoothing=0.6),
        hovertemplate="Week of %{x|%d %b %Y}<br>Forecast: <b>%{y:,.0f}</b> units<extra></extra>",
    )
    fig.add_scatter(
        x=fwd_dates,
        y=[float(fitted.loc[window].iloc[-1])] + [forward] * horizon_weeks,
        mode="lines",
        name=f"Next {horizon_weeks} weeks: {forward:,.0f} units/week",
        line=dict(color=SERIES["forecast"], width=2.4, dash="dot"),
        fill="tozeroy",
        fillgradient=_gradient(CYAN_RGB, 0.14),
        hovertemplate="Week of %{x|%d %b %Y}<br>Forecast: <b>%{y:,.0f}</b> units<extra></extra>",
    )
    fig.add_vline(x=scenario.snapshot_date, line=dict(color=SUBTLE, width=1, dash="dot"))
    fig.add_annotation(
        x=scenario.snapshot_date,
        y=1,
        yref="paper",
        text="Today",
        showarrow=False,
        xanchor="left",
        yanchor="top",
        font=dict(size=11, color=MUTED),
        xshift=4,
        yshift=-4,
    )
    ymax = float(max(actual.loc[window].max(), fitted.loc[window].max(), forward))
    ymin = float(min(actual.loc[window].min(), fitted.loc[window].dropna().min(), forward))
    fig.update_layout(base_layout(height=330, yaxis_title="Units per week", hovermode="x unified"))
    fig.update_yaxes(range=[ymin * 0.85, ymax * 1.06])
    return fig


def status_donut_chart(counts: dict[str, int]) -> go.Figure:
    labels = [STATUS_SHORT[s] for s in STATUS_ORDER]
    values = [counts.get(s, 0) for s in STATUS_ORDER]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker=dict(colors=[STATUS_COLOR[s] for s in STATUS_ORDER], line=dict(color="white", width=3)),
            textinfo="none",
            hovertemplate="%{label}: <b>%{value}</b> SKUs (%{percent})<extra></extra>",
        )
    )
    total = sum(values)
    fig.add_annotation(
        text=f"<b>{total}</b>",
        x=0.5,
        y=0.56,
        showarrow=False,
        font=dict(size=30, family="Plus Jakarta Sans", color=TEXT),
    )
    fig.add_annotation(text="SKUs", x=0.5, y=0.40, showarrow=False, font=dict(size=13, color=MUTED))
    fig.update_layout(base_layout(height=220, showlegend=False, margin=dict(l=0, r=0, t=4, b=4)))
    return fig


def orders_by_supplier_chart(plan: pd.DataFrame) -> go.Figure:
    orders = plan[plan["recommended_order"] > 0]
    grouped = (
        orders.groupby(["supplier_id", "supplier_name"])
        .agg(
            value=("recommended_order_value", "sum"),
            skus=("sku", "count"),
            units=("recommended_order", "sum"),
        )
        .reset_index()
        .sort_values("value")
    )
    fig = go.Figure(
        go.Bar(
            y=[f"{r.supplier_name}" for r in grouped.itertuples()],
            x=grouped["value"],
            orientation="h",
            marker=dict(color=grouped["value"], colorscale=[[0, "#A5B4FC"], [1, PRIMARY]], cornerradius=6),
            text=[f"€{v / 1000:,.1f}k" for v in grouped["value"]],
            textposition="outside",
            cliponaxis=False,
            customdata=np.stack([grouped["skus"], grouped["units"]], axis=1),
            hovertemplate="%{y}<br><b>€%{x:,.0f}</b> · %{customdata[0]} SKUs · %{customdata[1]:,.0f} units<extra></extra>",
        )
    )
    fig.update_layout(
        base_layout(
            height=max(170, 44 * len(grouped) + 30),
            showlegend=False,
            margin=dict(l=8, r=48, t=8, b=8),
            bargap=0.42,
        )
    )
    fig.update_xaxes(visible=False, range=[0, grouped["value"].max() * 1.18 if len(grouped) else 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12, color=TEXT))
    return fig


def cover_strip_chart(plan: pd.DataFrame, excess_threshold: float) -> go.Figure:
    """Every SKU as a dot on a weeks-of-cover axis, one row per status (jittered)."""
    rng = np.random.default_rng(7)
    positions = {status: i for i, status in enumerate(STATUS_ORDER[::-1])}
    fig = go.Figure()
    for status in STATUS_ORDER:
        rows = plan[plan["status"] == status]
        if rows.empty:
            continue
        y = positions[status] + rng.uniform(-0.22, 0.22, size=len(rows))
        fig.add_scatter(
            x=rows["weeks_of_cover"],
            y=y,
            mode="markers",
            name=STATUS_SHORT[status],
            marker=dict(
                color=STATUS_COLOR[status], size=12, opacity=0.9, line=dict(color="white", width=1.5)
            ),
            customdata=np.stack(
                [rows["sku"], rows["product_name"], rows["inventory_position"], rows["reorder_point"]], axis=1
            ),
            hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}<br>Cover: %{x:.1f} weeks<br>"
            "Inventory position: %{customdata[2]:,.0f} · ROP: %{customdata[3]:,.0f}<extra></extra>",
        )
    fig.add_vrect(
        x0=excess_threshold,
        x1=max(plan["weeks_of_cover"].max() * 1.05, excess_threshold + 2),
        fillcolor="rgba(14,165,233,0.06)",
        line_width=0,
    )
    fig.add_vline(
        x=excess_threshold,
        line=dict(color=STATUS_COLOR["EXCESS STOCK"], width=1.5, dash="dash"),
        annotation_text=f"Excess above {excess_threshold:g} wks",
        annotation_position="top right",
        annotation_font=dict(size=11, color="#0369A1", family=FONT),
    )
    fig.update_layout(
        base_layout(
            height=290, xaxis_title="Weeks of cover (inventory position ÷ weekly forecast)", showlegend=False
        )
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(positions.values()),
        ticktext=[STATUS_SHORT[s] for s in positions],
        range=[-0.6, len(positions) - 0.4],
        showgrid=True,
        gridcolor=GRID,
        tickfont=dict(size=12, color=TEXT),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, rangemode="tozero")
    return fig


def value_by_status_chart(plan: pd.DataFrame) -> go.Figure:
    grouped = (
        plan.groupby("status")
        .agg(
            on_hand_value=("on_hand_value", "sum"),
            skus=("sku", "count"),
            order_value=("recommended_order_value", "sum"),
        )
        .reindex(STATUS_ORDER)
        .fillna(0)
    )
    fig = go.Figure()
    fig.add_bar(
        x=[STATUS_SHORT[s].replace(" ", "<br>") for s in grouped.index],
        y=grouped["on_hand_value"],
        marker=dict(color=[STATUS_COLOR[s] for s in grouped.index], cornerradius=8),
        text=[f"€{v / 1000:,.0f}k" for v in grouped["on_hand_value"]],
        textposition="outside",
        customdata=np.stack([grouped["skus"], grouped["order_value"]], axis=1),
        hovertemplate="%{x}<br>%{customdata[0]} SKUs<br>On-hand value: €%{y:,.0f}<br>Recommended orders: €%{customdata[1]:,.0f}<extra></extra>",
    )
    fig.update_layout(base_layout(height=290, yaxis_title="On-hand value (€)", showlegend=False, bargap=0.45))
    fig.update_yaxes(range=[0, grouped["on_hand_value"].max() * 1.22])
    fig.update_xaxes(tickangle=0, tickfont=dict(size=12, color=TEXT))
    return fig


# --------------------------------------------------------------------------- SKU explorer
def demand_forecast_chart(
    fc: SkuForecast, scenario: Scenario, history_weeks: int = 52, horizon_weeks: int = 12, height: int = 330
) -> go.Figure:
    """Historical demand (area), the selected method's walk-forward forecast and the flat forward forecast with its error band."""
    table = fc.walk_forward
    last_week = int(table.index.max())
    hist = table.loc[max(1, last_week - history_weeks + 1) :]
    hist_dates = [scenario.snapshot_date - timedelta(weeks=last_week - w + 1) for w in hist.index]
    fwd_dates = [scenario.week_start(w) for w in range(1, horizon_weeks + 1)]
    method = fc.selected_method

    fig = go.Figure()
    fig.add_scatter(
        x=hist_dates,
        y=hist["actual"],
        mode="lines",
        name="Actual demand",
        line=dict(color=SERIES["actual"], width=2.2, shape="spline", smoothing=0.5),
        fill="tozeroy",
        fillgradient=_gradient(INDIGO_RGB, 0.28),
        hovertemplate="Week of %{x|%d %b %Y}<br>Actual: <b>%{y:,.0f}</b> units<extra></extra>",
    )
    fig.add_scatter(
        x=hist_dates,
        y=hist[method],
        mode="lines",
        name=f"Forecast ({METHOD_SHORT[method]}, made a week earlier)",
        line=dict(color=SERIES["forecast"], width=1.8),
        hovertemplate="Week of %{x|%d %b %Y}<br>Forecast: <b>%{y:,.1f}</b><extra></extra>",
    )
    band = fc.error_sd
    fig.add_scatter(
        x=fwd_dates + fwd_dates[::-1],
        y=[fc.weekly_forecast + band] * horizon_weeks + [max(fc.weekly_forecast - band, 0)] * horizon_weeks,
        fill="toself",
        fillcolor=SERIES["forecast_fill"],
        line=dict(width=0),
        name="±1 SD of past forecast error",
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=fwd_dates,
        y=[fc.weekly_forecast] * horizon_weeks,
        mode="lines",
        name=f"Next {horizon_weeks} weeks: {fc.weekly_forecast:,.1f}/week",
        line=dict(color=SERIES["forecast"], width=2.8, dash="dot"),
        hovertemplate="Week of %{x|%d %b %Y}<br>Forecast: <b>%{y:,.1f}</b> units<extra></extra>",
    )
    fig.add_vline(x=scenario.snapshot_date, line=dict(color=SUBTLE, width=1, dash="dot"))
    fig.add_annotation(
        x=scenario.snapshot_date,
        y=1,
        yref="paper",
        text="Today",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font=dict(size=11, color=MUTED),
        xshift=4,
        yshift=-4,
    )
    fig.update_layout(base_layout(height=height, yaxis_title="Units per week", hovermode="x unified"))
    fig.update_yaxes(rangemode="tozero")
    return fig


def method_comparison_chart(fc: SkuForecast) -> go.Figure:
    scores = fc.method_scores
    colours = [SERIES["actual"] if sel else "#D5D8F0" for sel in scores["selected"]]
    fig = go.Figure(
        go.Bar(
            x=[METHOD_SHORT[m] for m in scores.index],
            y=scores["wape"] * 100,
            marker=dict(color=colours, cornerradius=8),
            text=[f"{w * 100:.1f}%" for w in scores["wape"]],
            textposition="outside",
            hovertemplate="%{x}<br>WAPE %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_hline(y=scores["wape"].min() * 100, line=dict(color=SUBTLE, width=1, dash="dot"))
    fig.update_layout(
        base_layout(
            height=250, yaxis_title="WAPE (%)", showlegend=False, bargap=0.4, margin=dict(l=8, r=8, t=16, b=8)
        )
    )
    fig.update_yaxes(range=[0, max(scores["wape"].max() * 100 * 1.25, 1)])
    fig.update_xaxes(tickangle=0, tickfont=dict(size=12, color=TEXT))
    return fig


def forecast_error_chart(fc: SkuForecast, scenario: Scenario) -> go.Figure:
    """Weekly walk-forward errors of the selected method with a ±1 SD band: the raw material of safety stock."""
    errors = fc.errors
    last_week = int(fc.walk_forward.index.max())
    dates = [scenario.snapshot_date - timedelta(weeks=last_week - int(w) + 1) for w in errors.index]
    colours = [SERIES["forecast"] if e >= 0 else SERIES["actual"] for e in errors]
    fig = go.Figure(
        go.Bar(
            x=dates,
            y=errors,
            marker=dict(color=colours, cornerradius=3),
            name="Forecast − actual",
            hovertemplate="Week of %{x|%d %b %Y}<br>Error: <b>%{y:+,.1f}</b> units<extra></extra>",
        )
    )
    sd = fc.error_sd
    fig.add_hrect(y0=-sd, y1=sd, fillcolor="rgba(79,70,229,0.06)", line_width=0)
    _hline(fig, sd, "#D97706", f"+1 SD = {sd:,.1f}", dash="dot")
    _hline(fig, -sd, "#D97706", "−1 SD", dash="dot")
    fig.add_hline(y=0, line=dict(color=BORDER, width=1))
    fig.update_layout(
        base_layout(height=260, yaxis_title="Units (+ over / − under)", showlegend=False, bargap=0.25)
    )
    return fig


def projection_chart(
    proj: ProjectionResult,
    *,
    safety_stock: float,
    reorder_point: float,
    lead_time_weeks: int,
    scenario: Scenario,
    height: int = 380,
) -> go.Figure:
    """12-week closing inventory with receipts, reorder point, safety stock and the lead-time window."""
    t = proj.table
    dates = [scenario.week_start(int(w)) for w in t["week"]]
    closing = t["closing_inventory"].to_numpy()

    fig = go.Figure()
    lt_end = scenario.week_start(lead_time_weeks + 1)
    fig.add_vrect(x0=scenario.snapshot_date, x1=lt_end, fillcolor="rgba(139,145,167,0.10)", line_width=0)
    fig.add_scatter(
        x=[None],
        y=[None],
        mode="markers",
        name=f"Lead time ({lead_time_weeks} wk): today's order cannot arrive",
        marker=dict(symbol="square", size=12, color="rgba(139,145,167,0.35)"),
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=dates,
        y=np.maximum(closing, 0),
        mode="lines",
        line=dict(width=0, shape="hv"),
        fill="tozeroy",
        fillcolor=SERIES["inventory_fill"],
        hoverinfo="skip",
        showlegend=False,
    )
    fig.add_scatter(
        x=dates,
        y=np.minimum(closing, 0),
        mode="lines",
        line=dict(width=0, shape="hv"),
        fill="tozeroy",
        fillcolor=SERIES["shortfall_fill"],
        hoverinfo="skip",
        showlegend=False,
    )
    fig.add_scatter(
        x=dates,
        y=closing,
        mode="lines+markers",
        name="Projected stock",
        line=dict(color=SERIES["inventory"], width=2.6, shape="hv"),
        marker=dict(size=6, color=SERIES["inventory"]),
        customdata=np.stack([t["opening_inventory"], t["forecast_demand"], t["week"]], axis=1),
        hovertemplate="Week %{customdata[2]} · %{x|%d %b}<br>Opening: %{customdata[0]:,.0f}<br>Forecast demand: %{customdata[1]:,.1f}<br><b>Closing: %{y:,.0f}</b><extra></extra>",
    )
    receipts = t[t["existing_po_receipt"] > 0]
    if not receipts.empty:
        fig.add_scatter(
            x=[scenario.week_start(int(w)) for w in receipts["week"]],
            y=receipts["closing_inventory"],
            mode="markers",
            name="Open PO arrives",
            marker=dict(
                symbol="triangle-up", size=15, color=SERIES["receipt"], line=dict(color="white", width=1.5)
            ),
            customdata=receipts["existing_po_receipt"],
            hovertemplate="Open PO receipt: <b>%{customdata:,.0f}</b> units<extra></extra>",
        )
    new = t[t["new_order_receipt"] > 0]
    if not new.empty:
        fig.add_scatter(
            x=[scenario.week_start(int(w)) for w in new["week"]],
            y=new["closing_inventory"],
            mode="markers",
            name="Recommended order arrives",
            marker=dict(
                symbol="star", size=18, color=SERIES["new_order"], line=dict(color="white", width=1.5)
            ),
            customdata=new["new_order_receipt"],
            hovertemplate="Recommended order arrives: <b>%{customdata:,.0f}</b> units<extra></extra>",
        )
    _hline(
        fig,
        reorder_point,
        SERIES["reorder_point"],
        f"Reorder point {reorder_point:,.0f}",
        position="top right",
    )
    _hline(
        fig,
        safety_stock,
        SERIES["safety_stock"],
        f"Safety stock {safety_stock:,.0f}",
        dash="dot",
        position="bottom right",
    )
    fig.add_hline(y=0, line=dict(color=TEXT, width=1))
    if proj.next_review_trigger_week and proj.next_review_trigger_week > 1 and proj.first_zero_week != 1:
        x = scenario.week_start(proj.next_review_trigger_week)
        fig.add_vline(x=x, line=dict(color=SERIES["reorder_point"], width=1, dash="dot"))
        fig.add_scatter(
            x=[None],
            y=[None],
            mode="lines",
            name=f"Next review would reorder (week {proj.next_review_trigger_week})",
            line=dict(color=SERIES["reorder_point"], width=1, dash="dot"),
            hoverinfo="skip",
        )
    fig.update_layout(base_layout(height=height, yaxis_title="Units (end of week)", hovermode="x unified"))
    return fig


def eoq_cost_chart(
    annual_demand: float, ordering_cost: float, holding_cost: float, eoq: float, order_qty: int
) -> go.Figure:
    """Annual ordering, holding and total cost against order size: EOQ sits at the bottom of the total-cost curve."""
    if annual_demand <= 0 or eoq <= 0:
        return go.Figure().update_layout(base_layout(height=280))
    q = np.linspace(max(eoq * 0.2, 1), eoq * 2.6, 160)
    ordering = annual_demand / q * ordering_cost
    holding = q / 2 * holding_cost
    total = ordering + holding
    fig = go.Figure()
    fig.add_scatter(
        x=q,
        y=ordering,
        mode="lines",
        name="Ordering cost",
        line=dict(color=SERIES["forecast"], width=2),
        hovertemplate="Q %{x:,.0f}<br>Ordering €%{y:,.0f}/yr<extra></extra>",
    )
    fig.add_scatter(
        x=q,
        y=holding,
        mode="lines",
        name="Holding cost",
        line=dict(color="#D97706", width=2),
        hovertemplate="Q %{x:,.0f}<br>Holding €%{y:,.0f}/yr<extra></extra>",
    )
    fig.add_scatter(
        x=q,
        y=total,
        mode="lines",
        name="Total cost",
        line=dict(color=SERIES["actual"], width=3),
        fill="tozeroy",
        fillgradient=_gradient(INDIGO_RGB, 0.14),
        hovertemplate="Q %{x:,.0f}<br><b>Total €%{y:,.0f}/yr</b><extra></extra>",
    )
    eoq_cost = annual_demand / eoq * ordering_cost + eoq / 2 * holding_cost
    fig.add_scatter(
        x=[eoq],
        y=[eoq_cost],
        mode="markers+text",
        marker=dict(size=12, color=SERIES["actual"], line=dict(color="white", width=2)),
        text=[f"EOQ {eoq:,.0f}"],
        textposition="top center",
        textfont=dict(size=12, color=TEXT),
        showlegend=False,
        hovertemplate="EOQ %{x:,.0f}<br>Total €%{y:,.0f}/yr<extra></extra>",
    )
    if order_qty > 0:
        fig.add_vline(x=order_qty, line=dict(color=SUBTLE, width=1, dash="dot"))
    fig.update_layout(
        base_layout(
            height=290, xaxis_title="Order quantity (units)", yaxis_title="€ per year", hovermode="x unified"
        )
    )
    fig.update_yaxes(range=[0, float(total.min()) * 2.2])
    return fig


# --------------------------------------------------------------------------- backtest
def legend_below(fig: go.Figure, extra_bottom: int = 70, y: float = -0.16) -> go.Figure:
    """For narrow cards: move the legend under the plot so it never covers the data."""
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=y, xanchor="left", x=0), margin=dict(b=extra_bottom)
    )
    return fig


def backtest_sku_chart(
    detail: pd.DataFrame, baseline_label: str, proposed_label: str, height: int = 360
) -> go.Figure:
    a = detail[detail["policy"] == "baseline"].sort_values("week")
    b = detail[detail["policy"] == "proposed"].sort_values("week")
    fig = go.Figure()
    fig.add_bar(
        x=a["week"],
        y=a["actual_demand"],
        name="Actual demand",
        marker=dict(color="#E3E5F4", cornerradius=4),
        hovertemplate="Week %{x}<br>Demand: %{y:,.0f}<extra></extra>",
    )
    for rows, label, colour in (
        (a, baseline_label, SERIES["baseline"]),
        (b, proposed_label, SERIES["proposed"]),
    ):
        fig.add_scatter(
            x=rows["week"],
            y=rows["closing_stock"],
            mode="lines+markers",
            name=label,
            line=dict(color=colour, width=2.6),
            marker=dict(size=6),
            customdata=np.stack([rows["order"], rows["lost_sales"]], axis=1),
            hovertemplate="Week %{x}<br>Closing stock: %{y:,.0f}<br>Order placed: %{customdata[0]:,.0f}<br>Lost sales: %{customdata[1]:,.0f}<extra></extra>",
        )
        lost = rows[rows["lost_sales"] > 0]
        if not lost.empty:
            fig.add_scatter(
                x=lost["week"],
                y=[0] * len(lost),
                mode="markers",
                name=f"Lost sales · {label.split(':')[0]}",
                marker=dict(symbol="x", size=11, color=colour, line=dict(width=2)),
                customdata=lost["lost_sales"],
                hovertemplate="Week %{x}<br>Lost sales: %{customdata:,.0f} units<extra></extra>",
            )
    fig.add_scatter(
        x=b["week"],
        y=b["reorder_point"],
        mode="lines",
        name="Reorder point (proposed)",
        line=dict(color=SERIES["reorder_point"], width=1.3, dash="dash"),
        hovertemplate="Week %{x}<br>ROP: %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        base_layout(
            height=height, yaxis_title="Units", xaxis_title="History week", hovermode="x unified", bargap=0.4
        )
    )
    return fig


def backtest_tradeoff_chart(sku_summary: pd.DataFrame, plan: pd.DataFrame) -> go.Figure:
    """Per SKU: change in fill rate vs change in average inventory value, proposed minus baseline."""
    wide = sku_summary.pivot(index="sku", columns="policy", values=["fill_rate", "average_inventory_value"])
    d_fill = (wide[("fill_rate", "proposed")] - wide[("fill_rate", "baseline")]) * 100
    base_val = wide[("average_inventory_value", "baseline")].replace(0, np.nan)
    d_value = (wide[("average_inventory_value", "proposed")] / base_val - 1) * 100
    names = plan.set_index("sku")["product_name"].reindex(wide.index)
    outcome = np.select(
        [(d_fill >= 0) & (d_value <= 0), (d_fill >= 0) & (d_value > 0), (d_fill < 0) & (d_value <= 0)],
        ["Better service, less stock", "Better service, more stock", "Less stock, lower service"],
        default="More stock, lower service",
    )
    colours = {
        "Better service, less stock": STATUS_COLOR["HEALTHY"],
        "Better service, more stock": PRIMARY,
        "Less stock, lower service": STATUS_COLOR["EXCESS STOCK"],
        "More stock, lower service": STATUS_COLOR["STOCKOUT RISK"],
    }
    fig = go.Figure()
    for label, colour in colours.items():
        mask = outcome == label
        if not mask.any():
            continue
        fig.add_scatter(
            x=d_value[mask],
            y=d_fill[mask],
            mode="markers",
            name=f"{label} ({int(mask.sum())})",
            marker=dict(color=colour, size=12, opacity=0.88, line=dict(color="white", width=1.5)),
            customdata=np.stack([wide.index[mask], names[mask]], axis=1),
            hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}<br>Fill rate: %{y:+.1f} pp<br>Avg inventory value: %{x:+.0f}%<extra></extra>",
        )
    fig.add_hline(y=0, line=dict(color=BORDER_LINE, width=1))
    fig.add_vline(x=0, line=dict(color=BORDER_LINE, width=1))
    fig.update_layout(
        base_layout(
            height=400,
            xaxis_title="Change in average inventory value (proposed vs baseline, %)",
            yaxis_title="Change in fill rate (pp)",
        )
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, ticksuffix="%")
    return fig


BORDER_LINE = "#CDD2E1"
