"""Reusable presentation components (HTML fragments rendered with ``st.html``)."""

from __future__ import annotations

import html
from collections.abc import Iterable

import pandas as pd
import streamlit as st

from planning.exceptions import STATUS_ORDER
from ui.theme import CSS, STATUS_SHORT, STATUS_STYLE, fmt_units

SKU_PAGE = "ui/pages/sku_explorer.py"
AUTHOR = "Syed Danish Ali"
LINKEDIN = "https://www.linkedin.com/in/syeddanishali16/"
BYLINE = (
    f'<a class="dp-byline" href="{LINKEDIN}" target="_blank" rel="noopener"><i>SDA</i>'
    f"Portfolio project by <b>{AUTHOR}</b></a>"
)


def inject_css() -> None:
    st.html(CSS)


# ---------------------------------------------------------------------------------------- headers
def hero(
    kicker: str, title: str, lede: str | None = None, chips: Iterable[str] = (), byline: bool = True
) -> None:
    """Dark gradient banner used at the top of every page, with the author byline on the right."""
    lede_html = f'<div class="dp-lede">{lede}</div>' if lede else ""
    chips_html = "".join(f'<span class="dp-chip"><i></i>{c}</span>' for c in chips)
    chips_block = f'<div class="dp-chips">{chips_html}</div>' if chips_html else ""
    st.html(
        f'<div class="dp-hero"><div class="dp-hero-top"><div class="dp-kicker">{html.escape(kicker)}</div>'
        f"{BYLINE if byline else ''}</div><h1>{html.escape(title)}</h1>{lede_html}{chips_block}</div>"
    )


def page_header(kicker: str, title: str, lede: str | None = None) -> None:
    """Light header for reference pages."""
    lede_html = f'<div class="dp-lede">{lede}</div>' if lede else ""
    st.html(
        f'<div class="dp-header"><div class="dp-kicker">{html.escape(kicker)}</div>'
        f"<h1>{html.escape(title)}</h1>{lede_html}</div>"
    )


def section(
    title: str,
    sub: str | None = None,
    number: int | str | None = None,
    count: str | None = None,
    tight: bool = False,
) -> None:
    """Section heading with consistent spacing above it."""
    num = f'<span class="dp-section-num">{number}</span>' if number is not None else ""
    cnt = f'<span class="dp-count">{html.escape(count)}</span>' if count else ""
    sub_html = f'<div class="dp-section-sub">{sub}</div>' if sub else ""
    cls = "dp-section dp-section-tight" if tight else "dp-section"
    st.html(f'<div class="{cls}"><h2>{num}{html.escape(title)}{cnt}</h2>{sub_html}</div>')


def subhead(text: str) -> None:
    st.html(f'<div class="dp-subhead">{html.escape(text)}</div>')


def card_head(title: str, sub: str | None = None, tag: str | None = None) -> None:
    """Title + one-line takeaway (+ optional tag on the right) at the top of a bordered card."""
    sub_html = f'<div class="dp-card-sub">{sub}</div>' if sub else ""
    tag_html = f'<span class="dp-card-tag">{html.escape(tag)}</span>' if tag else ""
    st.html(
        f'<div class="dp-card-head"><div><div class="dp-card-title">{html.escape(title)}</div>{sub_html}</div>'
        f"{tag_html}</div>"
    )


# ---------------------------------------------------------------------------------------- small pieces
def empty_state(title: str, text: str) -> None:
    st.html(f'<div class="dp-empty"><strong>{html.escape(title)}</strong>{text}</div>')


def delta(text: str, good: bool | None) -> str:
    """Coloured delta text: good=True green, False red, None neutral."""
    cls = "dp-delta-flat" if good is None else ("dp-delta-up" if good else "dp-delta-down")
    return f'<span class="{cls}">{html.escape(text)}</span>'


def pill(text: str, good: bool | None) -> str:
    """Rounded delta pill (green / red / grey), like '+3.0 pp'."""
    cls = "dp-pill-flat" if good is None else ("dp-pill-up" if good else "dp-pill-down")
    return f'<span class="dp-pill {cls}">{html.escape(text)}</span>'


def status_badge(status: str, large: bool = False) -> str:
    style = STATUS_STYLE[status]
    size = " dp-badge-lg" if large else ""
    return (
        f'<span class="dp-badge{size}" style="color:{style["color"]};background:{style["bg"]};'
        f'border-color:{style["border"]};--badge-dot:{style["dot"]}">{html.escape(STATUS_SHORT[status])}</span>'
    )


def loading_skeleton(message: str) -> str:
    """Shimmering placeholder that mirrors the dashboard layout while the plan is computed."""
    return (
        '<div class="dp-skel-wrap">'
        f'<div class="dp-skel-note">{html.escape(message)}</div>'
        '<div class="dp-skel" style="height:190px;border-radius:20px"></div>'
        '<div class="dp-skel-row" style="grid-template-columns:repeat(5,1fr)">'
        + '<div class="dp-skel" style="height:112px"></div>'
        * 5
        + "</div>"
        '<div class="dp-skel-row" style="grid-template-columns:2fr 1fr">'
        '<div class="dp-skel" style="height:340px"></div><div class="dp-skel" style="height:340px"></div></div>'
        "</div>"
    )


# ---------------------------------------------------------------------------------------- KPI tiles
def kpi_row(tiles: Iterable[dict], md_cols: int | None = None) -> None:
    """Tiles: label, value, sub (optional html), accent (optional colour), soft (optional bg), icon (optional glyph).

    All tiles share one row on wide screens; below ~860px they reflow to ``md_cols`` columns
    (default: an even split that avoids a lonely last tile), then 2, then 1.
    """
    tiles = list(tiles)
    n = len(tiles)
    md = md_cols or {5: 3, 6: 3, 4: 2}.get(n, min(n, 3))
    parts = []
    for tile in tiles:
        accent = tile.get("accent")
        soft = tile.get("soft")
        style_bits = []
        if accent:
            style_bits.append(f"--kpi-accent:{accent}")
        if soft:
            style_bits.append(f"--kpi-soft:{soft}")
        style = f' style="{";".join(style_bits)}"' if style_bits else ""
        icon = f'<span class="dp-kpi-icon">{tile["icon"]}</span>' if tile.get("icon") else ""
        sub = f'<div class="dp-kpi-sub">{tile["sub"]}</div>' if tile.get("sub") else ""
        parts.append(
            f'<div class="dp-kpi"{style}><div class="dp-kpi-top">{icon}<div class="dp-kpi-label">'
            f'{html.escape(tile["label"])}</div></div><div class="dp-kpi-value">{tile["value"]}</div>{sub}</div>'
        )
    st.html(
        f'<div class="dp-kpis-wrap"><div class="dp-kpis" style="--kpi-cols:{n};--kpi-cols-md:{md}">'
        + "".join(parts)
        + "</div></div>"
    )


def definitions(items: Iterable[tuple[str, str, str]]) -> None:
    """Glossary cards: (term, colour, explanation) — one term per card, heading on its own line."""
    parts = [
        f'<div class="dp-def"><div class="dp-def-term"><i style="background:{colour}"></i>{html.escape(term)}</div><p>{text}</p></div>'
        for term, colour, text in items
    ]
    st.html('<div class="dp-defs">' + "".join(parts) + "</div>")


def callout(text: str, kind: str = "note") -> None:
    st.html(f'<div class="dp-callout dp-callout-{kind}">{text}</div>')


def chain(steps: Iterable[str]) -> None:
    items = [f"<span>{html.escape(s)}</span>" for s in steps]
    st.html('<div class="dp-chain">' + "<i>→</i>".join(items) + "</div>")


def step_cards(cards: Iterable[dict], cols: int | None = None) -> None:
    """Formula cards: number, title, formula, numbers, result, unit, interpretation.

    ``cols`` defaults to the number of cards (max 4) so a row never leaves an orphan card.
    """
    cards = list(cards)
    cols = cols or min(len(cards), 4)
    parts = []
    for c in cards:
        unit = f"<small>{html.escape(c['unit'])}</small>" if c.get("unit") else ""
        numbers = (
            f'<div class="dp-step-numbers">{html.escape(c["numbers"])}</div>' if c.get("numbers") else ""
        )
        formula = (
            f'<div class="dp-step-formula">{html.escape(c["formula"])}</div>' if c.get("formula") else ""
        )
        excel = (
            f'<div class="dp-step-excel"><span>Excel</span><code>{html.escape(c["excel"])}</code></div>'
            if c.get("excel")
            else ""
        )
        source = f'<div class="dp-step-source">{c["source"]}</div>' if c.get("source") else ""
        why = f'<div class="dp-step-why"><b>Why it matters</b>{c["why"]}</div>' if c.get("why") else ""
        parts.append(
            f'<div class="dp-step"><div class="dp-step-head"><span class="dp-step-num">{c["number"]}</span>'
            f'<span class="dp-step-title">{html.escape(c["title"])}</span></div>{formula}{numbers}'
            f'<div class="dp-step-result">{c["result"]}{unit}</div>'
            f'<div class="dp-step-interp">{c["interpretation"]}</div>{source}{excel}{why}</div>'
        )
    st.html(f'<div class="dp-steps" style="--cols:{cols}">' + "".join(parts) + "</div>")


def key_values(pairs: Iterable[tuple[str, str]]) -> None:
    parts = [f"<dt>{html.escape(k)}</dt><dd>{v}</dd>" for k, v in pairs]
    st.html('<dl class="dp-kv">' + "".join(parts) + "</dl>")


def status_legend(counts: dict[str, int], colours: dict[str, str]) -> None:
    items = [
        f'<div class="dp-legend-item"><i style="background:{colours[s]}"></i>{html.escape(STATUS_SHORT[s])}'
        f"<b>{counts.get(s, 0)}</b></div>"
        for s in STATUS_ORDER
    ]
    st.html('<div class="dp-legend-list">' + "".join(items) + "</div>")


# ---------------------------------------------------------------------------------------- story timeline
def story(steps: Iterable[dict]) -> None:
    """Vertical storyline. Each step: eyebrow, title, text (html), facts [(label, value, strong)],
    optional extra (html), dot (glyph), dot_bg, dot_fg."""
    parts = []
    for s in steps:
        facts = "".join(
            f'<div class="dp-fact{" dp-fact-strong" if strong else ""}"><span>{html.escape(label)}</span><b>{value}</b></div>'
            for label, value, strong in s.get("facts", [])
        )
        facts_html = f'<div class="dp-story-facts">{facts}</div>' if facts else ""
        dot_style = f"--dot-bg:{s.get('dot_bg', '#EEF0FF')};--dot-fg:{s.get('dot_fg', '#4F46E5')}"
        parts.append(
            f'<div class="dp-story-step"><div><span class="dp-story-dot" style="{dot_style}">{s["dot"]}</span></div>'
            f'<div class="dp-story-body"><div class="dp-story-eyebrow">{html.escape(s["eyebrow"])}</div>'
            f'<div class="dp-story-title">{html.escape(s["title"])}</div>'
            f'<div class="dp-story-text">{s["text"]}</div>{facts_html}{s.get("extra", "")}</div></div>'
        )
    st.html('<div class="dp-story">' + "".join(parts) + "</div>")


def gauge_html(position: float, reorder_point: float, upper: float) -> str:
    """Horizontal gauge: where the inventory position sits relative to the reorder point."""
    upper = max(upper, reorder_point * 1.6, position * 1.1, 1.0)
    lower = min(0.0, position)
    span = upper - lower

    def pct(v: float) -> float:
        return max(0.0, min(100.0, (v - lower) / span * 100))

    return (
        f'<div class="dp-gauge"><div class="dp-gauge-track">'
        f'<div class="dp-gauge-mark" style="left:{pct(reorder_point):.1f}%"></div>'
        f'<div class="dp-gauge-pin" style="left:{pct(position):.1f}%"></div></div>'
        f'<div class="dp-gauge-labels"><span>{fmt_units(lower)}</span>'
        f'<span style="color:#DC2626;font-weight:600">Reorder point {fmt_units(reorder_point)}</span>'
        f"<span>{fmt_units(upper)}</span></div></div>"
    )


# ---------------------------------------------------------------------------------------- tables & filters
def status_filter(
    key: str, default: list[str] | None = None, options: list[str] | None = None, show_label: bool = False
) -> list[str]:
    """Pill selector for statuses; returns the selected status values (all options when nothing is selected)."""
    options = options or STATUS_ORDER
    labels = {s: STATUS_SHORT[s] for s in options}
    chosen = st.pills(
        "Status",
        options=options,
        format_func=lambda s: labels[s],
        selection_mode="multi",
        default=default,
        key=key,
        label_visibility="visible" if show_label else "collapsed",
    )
    return list(chosen) if chosen else list(options)


def status_cell_style(label_to_status: dict[str, str]):
    """Styler function colouring a status-label column like the badges."""

    def _style(value: str) -> str:
        style = STATUS_STYLE.get(label_to_status.get(value, ""))
        return f"background-color:{style['bg']};color:{style['color']};font-weight:600" if style else ""

    return _style


def simple_table(
    headers: list[str],
    rows: Iterable[Iterable[str]],
    numeric: Iterable[int] = (),
    widths: Iterable[str] | None = None,
    strong_first: bool = False,
) -> None:
    """Small HTML table with wrapping text. ``numeric`` lists the right-aligned column indexes."""
    numeric = set(numeric)
    colgroup = "".join(f'<col style="width:{w}">' for w in widths) if widths else ""
    head = "".join(
        f'<th class="{"num" if i in numeric else ""}">{html.escape(h)}</th>' for i, h in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = []
        for i, value in enumerate(row):
            cls = "num" if i in numeric else ""
            if strong_first and i == 0:
                cls += " strong"
            cells.append(f'<td class="{cls.strip()}">{value}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.html(
        f'<table class="dp-table dp-table-compact"><colgroup>{colgroup}</colgroup><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def attention_row_html(row: pd.Series, excess_threshold: float) -> str:
    """One compact row of the dashboard's 'needs attention' list: the action and the timing that makes it urgent."""
    style = STATUS_STYLE[row["status"]]
    status = row["status"]
    zero = row.get("first_zero_week")
    po = row.get("next_po_week")
    if status == "STOCKOUT RISK":
        timing = f"Stock out week {int(zero)}"
        timing += f" · open PO lands week {int(po)}" if pd.notna(po) else " · no open PO"
        right = f"<b>Week {int(zero)}</b><span>stock-out</span>"
    elif status == "REORDER REQUIRED":
        timing = f"Position {fmt_units(row['inventory_position'])} vs reorder point {fmt_units(row['reorder_point'])}"
        right = f"<b>{fmt_units(row['recommended_order'])}</b><span>units to order</span>"
    else:
        timing = f"{row['weeks_of_cover']:.1f} weeks of cover, limit {excess_threshold:g}"
        right = f"<b>{row['weeks_of_cover']:.1f} wks</b><span>cover</span>"
    action = (
        f'<span class="dp-action" style="color:{style["color"]};background:{style["bg"]};border-color:{style["border"]}">'
        f"{html.escape(row['action'])}</span>"
    )
    return (
        f'<div class="dp-att-row"><span class="dp-att-dot" style="background:{style["dot"]}"></span>'
        f'<div style="min-width:0"><div class="dp-att-name"><small>{html.escape(row["sku"])}</small>'
        f'{html.escape(row["product_name"])}</div><div class="dp-att-why">{action}{html.escape(timing)}</div></div>'
        f'<div class="dp-att-right">{right}</div></div>'
    )
