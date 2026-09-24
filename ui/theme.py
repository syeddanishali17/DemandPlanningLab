"""Visual system: palette, status colours, type scale, spacing, motion and the global stylesheet.

Palette: deep indigo ink (sidebar, hero banners) · indigo brand · cyan forecast accent.
One colour per meaning, used identically in badges, tables and charts:

    actual demand      indigo area         forecast           cyan line
    projected stock    indigo line         reorder point      red, dashed
    safety stock       amber, dotted       open PO receipt    emerald triangle
    recommended order  cyan star           statuses           red / amber / sky / emerald

Type: Plus Jakarta Sans for headings and big numbers, Inter for text.
Scale (px): 12 label · 13 secondary · 14 UI/table · 15 body · 16 lede · 20 section · 26 figure · 34 hero title.
"""

from __future__ import annotations

from planning.exceptions import Status

# ----------------------------------------------------------------------------- palette
INK = "#111633"  # sidebar + hero background
INK_2 = "#1B2150"
PRIMARY = "#4F46E5"  # indigo-600: brand, actual demand, buttons
PRIMARY_HOVER = "#4338CA"
PRIMARY_SOFT = "#EEF0FF"
ACCENT = "#06B6D4"  # cyan-500: forecast
ACCENT_ON_DARK = "#67E8F9"
TEXT = "#151A30"
MUTED = "#5A6178"
SUBTLE = "#666C82"  # ≈5:1 on white: safe for small secondary text
BORDER = "#E4E7F0"
BORDER_STRONG = "#CDD2E1"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F6F7FC"
CANVAS = "#F5F6FB"

SERIES = {
    "actual": PRIMARY,
    "actual_fill": "rgba(79, 70, 229, 0.16)",
    "actual_bar": "#C7CBF3",
    "forecast": ACCENT,
    "forecast_fill": "rgba(6, 182, 212, 0.14)",
    "forecast_history": "#0891B2",
    "inventory": PRIMARY,
    "inventory_fill": "rgba(79, 70, 229, 0.10)",
    "shortfall_fill": "rgba(220, 38, 38, 0.12)",
    "reorder_point": "#DC2626",
    "safety_stock": "#D97706",
    "receipt": "#059669",
    "new_order": ACCENT,
    "baseline": "#A3A9BF",
    "proposed": PRIMARY,
    "lost": "#DC2626",
}

STATUS_STYLE = {
    Status.STOCKOUT_RISK.value: {
        "color": "#B91C1C",
        "dot": "#DC2626",
        "bg": "#FEF2F2",
        "border": "#FECACA",
        "icon": "▲",
    },
    Status.REORDER_REQUIRED.value: {
        "color": "#B45309",
        "dot": "#F59E0B",
        "bg": "#FFFBEB",
        "border": "#FDE68A",
        "icon": "●",
    },
    Status.EXCESS_STOCK.value: {
        "color": "#0369A1",
        "dot": "#0EA5E9",
        "bg": "#F0F9FF",
        "border": "#BAE6FD",
        "icon": "■",
    },
    Status.HEALTHY.value: {
        "color": "#047857",
        "dot": "#10B981",
        "bg": "#ECFDF5",
        "border": "#A7F3D0",
        "icon": "✓",
    },
}

STATUS_COLOR = {status: style["dot"] for status, style in STATUS_STYLE.items()}
STATUS_TEXT = {status: style["color"] for status, style in STATUS_STYLE.items()}
STATUS_SHORT = {
    Status.STOCKOUT_RISK.value: "Stockout risk",
    Status.REORDER_REQUIRED.value: "Reorder required",
    Status.EXCESS_STOCK.value: "Excess stock",
    Status.HEALTHY.value: "Healthy",
}


# ----------------------------------------------------------------------------- formatting
def fmt_units(value: float, decimals: int = 0) -> str:
    if value is None or value != value:
        return "–"
    return f"{value:,.{decimals}f}"


def fmt_eur(value: float, decimals: int = 0) -> str:
    if value is None or value != value:
        return "–"
    return f"€{value:,.{decimals}f}"


def fmt_eur_short(value: float) -> str:
    if value is None or value != value:
        return "–"
    return f"€{value / 1000:,.1f}k" if abs(value) >= 10_000 else fmt_eur(value)


def fmt_pct(value: float, decimals: int = 1, signed: bool = False) -> str:
    if value is None or value != value:
        return "–"
    return f"{value * 100:+.{decimals}f}%" if signed else f"{value * 100:.{decimals}f}%"


def fmt_weeks(value: float) -> str:
    if value is None or value != value:
        return "–"
    return f"{value:.1f} wks"


def fmt_date(value) -> str:
    return value.strftime("%d %b %Y") if value is not None else "–"


# ----------------------------------------------------------------------------- stylesheet
CSS = f"""
<style>
:root {{
  --dp-ink: {INK}; --dp-ink-2: {INK_2};
  --dp-primary: {PRIMARY}; --dp-primary-hover: {PRIMARY_HOVER}; --dp-primary-soft: {PRIMARY_SOFT};
  --dp-accent: {ACCENT}; --dp-accent-dark: {ACCENT_ON_DARK};
  --dp-text: {TEXT}; --dp-muted: {MUTED}; --dp-subtle: {SUBTLE};
  --dp-border: {BORDER}; --dp-border-strong: {BORDER_STRONG};
  --dp-surface: {SURFACE}; --dp-surface-alt: {SURFACE_ALT};
  --dp-radius: 16px; --dp-radius-sm: 10px;
  --dp-shadow: 0 1px 2px rgba(17, 22, 51, 0.04), 0 2px 8px rgba(17, 22, 51, 0.04);
  --dp-shadow-hover: 0 10px 28px rgba(17, 22, 51, 0.09);
  --dp-ease: cubic-bezier(0.2, 0.7, 0.2, 1);
  --dp-head: "Plus Jakarta Sans", Inter, system-ui, sans-serif;
  --dp-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}}

/* ======================================================================= chrome */
[data-testid="stMainMenu"], [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent !important; pointer-events: none; height: 0 !important; min-height: 0 !important; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] {{ pointer-events: auto; visibility: visible !important; }}
button[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button {{
  width: 34px; height: 34px; border-radius: 10px !important; transition: background-color 0.15s, transform 0.15s; }}
button[data-testid="stExpandSidebarButton"] {{ position: fixed !important; top: 14px; left: 14px; z-index: 1000; background: {INK} !important;
  box-shadow: 0 6px 18px rgba(17, 22, 51, 0.25); }}
button[data-testid="stExpandSidebarButton"] span {{ color: #fff !important; }}
button[data-testid="stExpandSidebarButton"]:hover {{ transform: translateX(2px); background: #1E2466 !important; }}
[data-testid="stSidebarCollapseButton"] button {{ color: #9EA6CF !important; }}
[data-testid="stSidebarCollapseButton"] button:hover {{ background: rgba(158, 166, 207, 0.14) !important; color: #fff !important; }}
[data-testid="stSidebarHeader"] {{ padding: 12px 14px 0 14px !important; height: auto !important; min-height: 0 !important; }}
[data-testid="stLogoSpacer"] {{ display: none; }}

/* A thin progress bar while the app is working replaces Streamlit's dimming of stale content. */
[data-stale="true"] {{ opacity: 1 !important; transition: none !important; }}
@keyframes dp-progress {{ 0% {{ transform: translateX(-100%); }} 100% {{ transform: translateX(260%); }} }}
.stApp::before {{ content: ""; position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 999999; pointer-events: none;
  background: rgba(79, 70, 229, 0.12); opacity: 0; transition: opacity 0.2s ease; }}
.stApp::after {{ content: ""; position: fixed; top: 0; left: 0; width: 40%; height: 3px; z-index: 1000000; pointer-events: none;
  background: linear-gradient(90deg, rgba(6, 182, 212, 0), #06B6D4 30%, #6366F1 70%, rgba(99, 102, 241, 0));
  opacity: 0; transform: translateX(-100%); }}
.stApp:has([data-testid="stStatusWidget"])::before {{ opacity: 1; transition-delay: 0.12s; }}
.stApp:has([data-testid="stStatusWidget"])::after {{ opacity: 1; animation: dp-progress 1.1s cubic-bezier(0.4, 0, 0.2, 1) infinite; transition: opacity 0.2s ease 0.12s; }}

/* ======================================================================= layout */
.block-container, [data-testid="stMainBlockContainer"] {{ padding: 28px 40px 72px 40px !important; max-width: 1400px; }}
@media (max-width: 991px) {{ .block-container, [data-testid="stMainBlockContainer"] {{ padding: 64px 18px 56px 18px !important; }} }}
@media (min-width: 992px) and (max-width: 1280px) {{ .block-container, [data-testid="stMainBlockContainer"] {{ padding: 24px 26px 64px 26px !important; }} }}
[data-testid="stMarkdownContainer"] p {{ line-height: 1.6; }}
[data-testid="stMarkdownContainer"] > :last-child, [data-testid="stMarkdownContainer"] p:last-child {{ margin-bottom: 0; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ font-size: 13px !important; line-height: 1.5; color: var(--dp-muted) !important; }}
[data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stVerticalBlock"][style*="border"] {{
  border-radius: var(--dp-radius) !important; background: var(--dp-surface); box-shadow: var(--dp-shadow); border-color: var(--dp-border) !important;
}}

/* ======================================================================= motion */
/* Short and quiet (Linear / Vercel style): only page headers enter; cards and charts update in place. */
@keyframes dp-enter {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes dp-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes dp-shimmer {{ 0% {{ background-position: 100% 0; }} 100% {{ background-position: 0 0; }} }}
@keyframes dp-pulse {{ 0%, 100% {{ opacity: 0.35; }} 50% {{ opacity: 1; }} }}
.dp-hero, .dp-sku-hero, .dp-header {{ animation: dp-enter 0.24s cubic-bezier(0.2, 0, 0, 1) both; }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; transition: none !important; }} }}

/* Placeholders: charts and tables shimmer until they have actually drawn, so a page never flashes blank. */
[data-testid="stPlotlyChart"]:not(:has(.main-svg)), [data-testid="stDataFrame"]:not(:has(canvas)) {{
  min-height: 220px; border-radius: 12px; background: linear-gradient(90deg, #EEF0F7 25%, #F6F7FC 37%, #EEF0F7 63%);
  background-size: 400% 100%; animation: dp-shimmer 1.4s ease infinite; }}

/* ======================================================================= hero banner */
.dp-hero {{ position: relative; overflow: hidden; border-radius: 20px; padding: clamp(20px, 2.2vw, 30px) clamp(20px, 2.4vw, 34px); color: #fff;
  background: radial-gradient(120% 140% at 100% 0%, rgba(6, 182, 212, 0.28) 0%, rgba(6, 182, 212, 0) 45%),
              linear-gradient(135deg, {INK} 0%, #1E2466 55%, #2F2A8A 100%);
  box-shadow: 0 14px 40px rgba(17, 22, 51, 0.18); }}
.dp-hero::after {{ content: ""; position: absolute; right: -60px; bottom: -80px; width: 320px; height: 320px; border-radius: 50%;
  background: radial-gradient(circle, rgba(103, 232, 249, 0.18) 0%, rgba(103, 232, 249, 0) 70%); }}
.dp-hero-top {{ display: flex; justify-content: space-between; align-items: center; gap: 12px 16px; flex-wrap: wrap; position: relative; z-index: 1; margin-bottom: 10px; }}
.dp-hero-top .dp-kicker {{ margin-bottom: 0 !important; }}
.dp-byline {{ display: inline-flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 500; color: #E3E6F5 !important; background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16); border-radius: 999px; padding: 4px 12px 4px 5px; text-decoration: none !important; transition: background-color 0.15s; white-space: nowrap; }}
.dp-byline:hover {{ background: rgba(255, 255, 255, 0.16); }}
.dp-byline b {{ color: #fff; font-weight: 700; }}
.dp-byline i {{ width: 20px; height: 20px; border-radius: 50%; background: linear-gradient(135deg, #6366F1, #06B6D4); display: inline-flex; align-items: center;
  justify-content: center; font-style: normal; font-size: 9px; font-weight: 800; color: #fff; letter-spacing: 0.02em; }}
.dp-hero .dp-kicker {{ font-size: 12px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--dp-accent-dark); margin-bottom: 10px; }}
.dp-hero h1 {{ font-family: var(--dp-head) !important; font-size: clamp(22px, 2.15vw, 31px) !important; line-height: 1.2 !important; font-weight: 800 !important;
  letter-spacing: -0.025em; margin: 0 0 10px 0 !important; padding: 0 !important; color: #fff !important; max-width: 52rem; }}
.dp-hero .dp-lede {{ font-size: clamp(14px, 1.05vw, 15.5px); line-height: 1.6; color: rgba(227, 230, 245, 0.86); max-width: 58rem; }}
.dp-hero .dp-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; position: relative; z-index: 1; }}
.dp-hero .dp-chip {{ display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 500; color: #E3E6F5;
  background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 999px; padding: 5px 12px; }}
.dp-hero .dp-chip b {{ color: #fff; font-weight: 700; }}
.dp-hero .dp-chip i {{ width: 7px; height: 7px; border-radius: 50%; background: var(--dp-accent-dark); display: inline-block; }}

/* light page header (secondary pages) */
.dp-header .dp-kicker {{ font-size: 12px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--dp-primary); margin-bottom: 8px; }}
.dp-header h1 {{ font-family: var(--dp-head) !important; font-size: clamp(22px, 2vw, 28px) !important; line-height: 1.2 !important; font-weight: 800 !important;
  letter-spacing: -0.025em; margin: 0 0 8px 0 !important; padding: 0 !important; color: var(--dp-text); }}
.dp-header .dp-lede {{ color: var(--dp-muted); font-size: 16px; max-width: 62rem; line-height: 1.6; }}

/* ======================================================================= sections */
.dp-section {{ margin-top: 26px; }}
.dp-section.dp-section-tight {{ margin-top: 6px; }}
.dp-section h2 {{ font-family: var(--dp-head) !important; font-size: 20px !important; font-weight: 700 !important; line-height: 1.3 !important;
  letter-spacing: -0.015em; margin: 0 !important; padding: 0 !important; color: var(--dp-text); display: flex; align-items: center; gap: 10px; }}
.dp-section h2 .dp-section-num {{ display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 9px;
  background: var(--dp-primary-soft); color: var(--dp-primary); font-size: 13px; font-weight: 800; flex: 0 0 auto; }}
.dp-section h2 .dp-count {{ font-family: Inter, sans-serif; font-size: 12px; font-weight: 600; color: var(--dp-primary); background: var(--dp-primary-soft);
  border-radius: 999px; padding: 3px 10px; }}
.dp-section .dp-section-sub {{ font-size: 14px; color: var(--dp-muted); line-height: 1.55; margin-top: 6px; max-width: 72rem; }}
.dp-subhead {{ font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--dp-subtle); margin: 10px 0 0 0; }}
.dp-card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }}
.dp-card-head .dp-card-title {{ font-family: var(--dp-head); font-size: 16px; font-weight: 700; color: var(--dp-text); line-height: 1.35; letter-spacing: -0.01em; }}
.dp-card-head .dp-card-sub {{ font-size: 13px; color: var(--dp-muted); line-height: 1.5; margin-top: 3px; }}
.dp-card-head .dp-card-tag {{ font-size: 12px; font-weight: 600; color: var(--dp-muted); background: var(--dp-surface-alt);
  border: 1px solid var(--dp-border); border-radius: 999px; padding: 3px 10px; white-space: nowrap; }}

/* ======================================================================= KPI tiles */
.dp-kpis-wrap {{ container-type: inline-size; }}
.dp-kpis {{ display: grid; grid-template-columns: repeat(var(--kpi-cols, 4), minmax(0, 1fr)); gap: 12px; }}
@container (max-width: 860px) {{ .dp-kpis {{ grid-template-columns: repeat(var(--kpi-cols-md, 3), minmax(0, 1fr)); }} }}
@container (max-width: 560px) {{ .dp-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@container (max-width: 360px) {{ .dp-kpis {{ grid-template-columns: 1fr; }} }}
.dp-kpi {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: var(--dp-radius); padding: clamp(12px, 1.1vw, 16px) clamp(12px, 1.2vw, 18px);
  box-shadow: var(--dp-shadow); display: flex; flex-direction: column; gap: 6px; min-width: 0;
  transition: transform 0.2s var(--dp-ease), box-shadow 0.2s var(--dp-ease), border-color 0.2s; }}
.dp-kpi:hover {{ transform: translateY(-1px); box-shadow: var(--dp-shadow-hover); border-color: var(--dp-border-strong); }}
.dp-kpi-top {{ display: flex; align-items: center; gap: 9px; }}
.dp-kpi-icon {{ width: 30px; height: 30px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; font-size: 15px;
  background: var(--kpi-soft, var(--dp-primary-soft)); color: var(--kpi-accent, var(--dp-primary)); flex: 0 0 auto; }}
.dp-kpi .dp-kpi-label {{ font-size: 13px; font-weight: 600; color: var(--dp-muted); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.dp-kpi .dp-kpi-value {{ font-family: var(--dp-head); font-size: clamp(20px, 1.75vw, 26px); font-weight: 800; color: var(--dp-text); line-height: 1.15;
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }}
.dp-kpi .dp-kpi-sub {{ font-size: 13px; color: var(--dp-muted); line-height: 1.45; }}
.dp-pill {{ display: inline-flex; align-items: center; gap: 3px; font-size: 12px; font-weight: 700; border-radius: 999px; padding: 2px 8px;
  line-height: 1.5; white-space: nowrap; }}
.dp-pill-up {{ background: #DCFCE7; color: #047857; }}
.dp-pill-down {{ background: #FEE2E2; color: #B91C1C; }}
.dp-pill-flat {{ background: var(--dp-surface-alt); color: var(--dp-muted); }}
.dp-delta-up {{ color: #047857; font-weight: 700; }}
.dp-delta-down {{ color: #B91C1C; font-weight: 700; }}
.dp-delta-flat {{ color: var(--dp-muted); font-weight: 700; }}

/* ======================================================================= badges */
.dp-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
  white-space: nowrap; border: 1px solid; line-height: 1.45; }}
.dp-badge::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--badge-dot); }}
.dp-badge-lg {{ font-size: 13px; padding: 5px 13px; }}

/* ======================================================================= callouts */
.dp-callout {{ border-radius: 12px; padding: 13px 16px; font-size: 14px; line-height: 1.6; border: 1px solid; border-left-width: 4px; }}
.dp-callout strong {{ font-weight: 700; }}
.dp-callout-info {{ background: #F1F5FF; border-color: #D8DEFB; border-left-color: var(--dp-primary); color: #26306B; }}
.dp-callout-note {{ background: var(--dp-surface); border-color: var(--dp-border); border-left-color: var(--dp-accent); color: var(--dp-text); }}
.dp-callout-warn {{ background: #FFFBEB; border-color: #FDE68A; border-left-color: #D97706; color: #78350F; }}

/* ======================================================================= formula cards */
.dp-steps {{ display: grid; grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr)); gap: 14px; }}
@media (max-width: 1200px) {{ .dp-steps {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 720px) {{ .dp-steps {{ grid-template-columns: 1fr; }} }}
.dp-step {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: var(--dp-radius); padding: 16px 18px;
  display: flex; flex-direction: column; gap: 8px; box-shadow: var(--dp-shadow); transition: border-color 0.2s, box-shadow 0.2s var(--dp-ease); }}
.dp-step:hover {{ border-color: var(--dp-border-strong); box-shadow: var(--dp-shadow-hover); }}
.dp-step-head {{ display: flex; align-items: center; gap: 10px; }}
.dp-step-num {{ width: 26px; height: 26px; border-radius: 8px; background: var(--dp-primary); color: #fff; font-size: 12px; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; }}
.dp-step-title {{ font-family: var(--dp-head); font-weight: 700; font-size: 15px; color: var(--dp-text); line-height: 1.3; }}
.dp-step-formula {{ font-family: var(--dp-mono); font-size: 12px; line-height: 1.5; color: var(--dp-muted); background: var(--dp-surface-alt);
  border-radius: 8px; padding: 6px 10px; }}
.dp-step-numbers {{ font-family: var(--dp-mono); font-size: 12px; line-height: 1.5; color: var(--dp-text); }}
.dp-step-result {{ font-family: var(--dp-head); font-size: 26px; font-weight: 800; color: var(--dp-primary); line-height: 1.15; letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; }}
.dp-step-result small {{ font-family: Inter, sans-serif; font-size: 13px; font-weight: 500; color: var(--dp-muted); margin-left: 6px; letter-spacing: 0; }}
.dp-step-interp {{ font-size: 13px; color: var(--dp-muted); line-height: 1.55; }}
.dp-step-source {{ font-size: 12.5px; color: var(--dp-muted); line-height: 1.5; border-top: 1px dashed var(--dp-border); padding-top: 8px; }}
.dp-step-source b {{ color: var(--dp-text); font-weight: 600; }}
.dp-step-excel {{ display: flex; align-items: flex-start; gap: 8px; font-size: 12px; }}
.dp-step-excel span {{ flex: 0 0 auto; font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #047857;
  background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 1px 6px; margin-top: 1px; }}
.dp-step-excel code {{ font-family: var(--dp-mono); font-size: 11.5px; color: #1F2A44; background: transparent; padding: 0; word-break: break-word; }}
.dp-step-why {{ margin-top: auto; font-size: 12.5px; line-height: 1.5; color: #3B3F8F; background: #F3F4FF; border-radius: 10px; padding: 8px 10px; }}
.dp-step-why b {{ display: block; font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dp-primary); margin-bottom: 2px; }}

/* ======================================================================= story timeline (SKU explorer) */
.dp-story {{ position: relative; display: flex; flex-direction: column; gap: 0; }}
.dp-story-step {{ position: relative; display: grid; grid-template-columns: 44px 1fr; gap: 16px; padding-bottom: 22px; }}
.dp-story-step::before {{ content: ""; position: absolute; left: 21px; top: 44px; bottom: 0; width: 2px;
  background: linear-gradient(var(--dp-border-strong), var(--dp-border)); }}
.dp-story-step:last-child::before {{ display: none; }}
.dp-story-dot {{ width: 44px; height: 44px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center;
  font-size: 20px; background: var(--dot-bg, var(--dp-primary-soft)); color: var(--dot-fg, var(--dp-primary)); box-shadow: 0 0 0 4px #F5F6FB; }}
.dp-story-body {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: var(--dp-radius); padding: 16px 20px;
  box-shadow: var(--dp-shadow); transition: box-shadow 0.2s var(--dp-ease), border-color 0.2s; }}
.dp-story-body:hover {{ box-shadow: var(--dp-shadow-hover); border-color: var(--dp-border-strong); }}
.dp-story-eyebrow {{ font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--dp-subtle); }}
.dp-story-title {{ font-family: var(--dp-head); font-size: 17px; font-weight: 700; color: var(--dp-text); margin-top: 2px; letter-spacing: -0.01em; }}
.dp-story-text {{ font-size: 15px; line-height: 1.65; color: #343B55; margin-top: 6px; }}
.dp-story-text b {{ color: var(--dp-text); }}
.dp-story-facts {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }}
.dp-fact {{ background: var(--dp-surface-alt); border: 1px solid var(--dp-border); border-radius: 12px; padding: 8px 12px; min-width: 120px; }}
.dp-fact span {{ display: block; font-size: 12px; color: var(--dp-muted); font-weight: 600; }}
.dp-fact b {{ display: block; font-family: var(--dp-head); font-size: 18px; font-weight: 800; color: var(--dp-text); letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums; margin-top: 1px; }}
.dp-fact.dp-fact-strong {{ background: var(--dp-primary-soft); border-color: #D6D9FB; }}
.dp-fact.dp-fact-strong b {{ color: var(--dp-primary); }}
.dp-story-formula {{ font-family: var(--dp-mono); font-size: 12px; color: var(--dp-muted); margin-top: 10px; }}

/* gauge: inventory position vs reorder point */
.dp-gauge {{ margin-top: 14px; }}
.dp-gauge-track {{ position: relative; height: 12px; border-radius: 999px; background: linear-gradient(90deg, #FEE2E2 0%, #FEF3C7 35%, #DCFCE7 60%, #E0F2FE 100%); }}
.dp-gauge-mark {{ position: absolute; top: -6px; width: 2px; height: 24px; background: #DC2626; }}
.dp-gauge-pin {{ position: absolute; top: -5px; width: 22px; height: 22px; margin-left: -11px; border-radius: 50%; background: var(--dp-primary);
  border: 3px solid #fff; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.45); }}
.dp-gauge-labels {{ display: flex; justify-content: space-between; font-size: 12px; color: var(--dp-muted); margin-top: 10px; }}

/* ======================================================================= SKU hero */
.dp-sku-hero {{ border-radius: 20px; padding: 24px 28px; color: #fff; position: relative; overflow: hidden;
  background: radial-gradient(120% 160% at 100% 0%, rgba(6, 182, 212, 0.25) 0%, rgba(6, 182, 212, 0) 45%), linear-gradient(135deg, {INK} 0%, #1E2466 60%, #2F2A8A 100%);
  box-shadow: 0 14px 40px rgba(17, 22, 51, 0.16); display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 28px; align-items: center; }}
@media (max-width: 1000px) {{ .dp-sku-hero {{ grid-template-columns: 1fr; }} }}
.dp-sku-hero .dp-sku-code {{ font-size: 13px; font-weight: 700; letter-spacing: 0.1em; color: var(--dp-accent-dark); }}
.dp-sku-hero .dp-sku-name {{ font-family: var(--dp-head); font-size: clamp(21px, 1.9vw, 28px); font-weight: 800; letter-spacing: -0.02em; line-height: 1.2; margin: 4px 0 10px 0; }}
.dp-sku-hero .dp-sku-reason {{ font-size: 15px; line-height: 1.6; color: rgba(227, 230, 245, 0.9); margin-top: 12px; }}
.dp-sku-hero .dp-sku-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
.dp-sku-hero .dp-sku-stat {{ background: rgba(255, 255, 255, 0.07); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 10px 12px; }}
.dp-sku-hero .dp-sku-stat span {{ display: block; font-size: 12px; color: rgba(227, 230, 245, 0.72); font-weight: 600; }}
.dp-sku-hero .dp-sku-stat b {{ display: block; font-family: var(--dp-head); font-size: 20px; font-weight: 800; margin-top: 2px; font-variant-numeric: tabular-nums; }}
.dp-sku-hero .dp-sku-meta {{ font-size: 13px; color: rgba(227, 230, 245, 0.75); display: flex; flex-wrap: wrap; gap: 4px 16px; }}
.dp-sku-hero .dp-sku-meta span {{ white-space: nowrap; }}

/* ======================================================================= attention list (dashboard) */
.dp-att {{ display: flex; flex-direction: column; }}
.dp-att-row {{ display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 11px 6px;
  border-bottom: 1px solid var(--dp-border); text-decoration: none !important; color: inherit !important; border-radius: 10px;
  transition: background-color 0.15s, transform 0.15s var(--dp-ease); }}
.dp-att-row:last-child {{ border-bottom: none; }}
.dp-att-row:hover {{ background: var(--dp-surface-alt); transform: translateX(2px); }}
.dp-att-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.dp-att-name {{ font-size: 14px; font-weight: 600; color: var(--dp-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.dp-att-name small {{ font-weight: 500; color: var(--dp-subtle); margin-right: 6px; font-size: 13px; }}
.dp-att-why {{ font-size: 13px; color: var(--dp-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; }}
.dp-att-right {{ text-align: right; }}
.dp-action {{ display: inline-block; font-size: 11.5px; font-weight: 700; border: 1px solid; border-radius: 6px; padding: 0 6px; margin-right: 8px; line-height: 1.6; }}
.dp-att-right b {{ display: block; font-family: var(--dp-head); font-size: 15px; font-weight: 800; color: var(--dp-text); font-variant-numeric: tabular-nums; }}
.dp-att-right span {{ font-size: 12px; color: var(--dp-muted); }}

/* donut legend */
[data-testid="stPageLink"] a {{ white-space: nowrap; }}
[data-testid="stPageLink"] p {{ white-space: nowrap; overflow: visible !important; text-overflow: clip !important; }}
.dp-defs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
.dp-def {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: 14px; padding: 14px 16px; box-shadow: var(--dp-shadow); }}
.dp-def-term {{ display: flex; align-items: center; gap: 8px; font-family: var(--dp-head); font-weight: 700; font-size: 15px; color: var(--dp-text); margin-bottom: 6px; }}
.dp-def-term i {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.dp-def p {{ font-size: 13.5px; line-height: 1.55; color: var(--dp-muted); margin: 0; }}
.dp-legend-list {{ display: flex; flex-direction: column; gap: 10px; }}
.dp-legend-item {{ display: grid; grid-template-columns: 10px 1fr auto; gap: 10px; align-items: center; font-size: 14px; color: var(--dp-text); }}
.dp-legend-item i {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.dp-legend-item b {{ font-family: var(--dp-head); font-weight: 800; font-variant-numeric: tabular-nums; }}

/* ======================================================================= chain pills */
.dp-chain {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.dp-chain span {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: 999px; padding: 4px 12px; font-size: 12px; font-weight: 500; color: var(--dp-text); }}
.dp-chain i {{ color: var(--dp-subtle); font-style: normal; font-size: 12px; }}

/* ======================================================================= HTML tables */
.dp-table {{ width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 0; font-size: 14px; background: var(--dp-surface);
  border: 1px solid var(--dp-border); border-radius: var(--dp-radius); overflow: hidden; box-shadow: var(--dp-shadow); }}
.dp-table th {{ text-align: left; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: var(--dp-subtle);
  background: var(--dp-surface-alt); padding: 11px 12px; border-bottom: 1px solid var(--dp-border); line-height: 1.3; vertical-align: bottom; }}
.dp-table td {{ padding: 12px; border-bottom: 1px solid var(--dp-border); vertical-align: top; color: var(--dp-text); line-height: 1.45; transition: background-color 0.15s; }}
.dp-table tr:last-child td {{ border-bottom: none; }}
.dp-table td.num, .dp-table th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.dp-table td.num {{ white-space: nowrap; }}
.dp-table td.strong {{ font-weight: 600; }}
.dp-table.dp-table-compact td {{ padding: 10px 12px; }}
.dp-table td.reason {{ color: var(--dp-muted); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }}
.dp-table td.sku {{ font-weight: 600; overflow-wrap: anywhere; }}
.dp-table td.sku small {{ display: block; font-size: 13px; font-weight: 400; color: var(--dp-muted); margin-top: 2px; }}
.dp-table tbody tr:hover td {{ background: #FAFAFE; }}

/* ======================================================================= buttons, pills, inputs */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {{
  min-height: 40px; padding: 0 16px !important; border-radius: var(--dp-radius-sm) !important;
  transition: background-color 0.16s, border-color 0.16s, color 0.16s, box-shadow 0.16s, transform 0.08s; }}
[data-testid="stBaseButton-secondary"] {{ background: var(--dp-surface) !important; border: 1px solid var(--dp-border-strong) !important;
  color: var(--dp-text) !important; box-shadow: var(--dp-shadow); }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: var(--dp-primary) !important; color: var(--dp-primary) !important; background: var(--dp-primary-soft) !important; }}
[data-testid="stBaseButton-primary"] {{ background: linear-gradient(180deg, #5A52EA 0%, var(--dp-primary) 100%) !important; border: 1px solid var(--dp-primary) !important;
  color: #fff !important; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.30); }}
[data-testid="stBaseButton-primary"]:hover {{ background: var(--dp-primary-hover) !important; border-color: var(--dp-primary-hover) !important; box-shadow: 0 4px 14px rgba(79, 70, 229, 0.38); }}
[data-testid="stBaseButton-secondary"]:active, [data-testid="stBaseButton-primary"]:active {{ transform: translateY(1px); }}
[data-testid="stBaseButton-secondary"]:focus-visible, [data-testid="stBaseButton-primary"]:focus-visible {{ outline: 2px solid rgba(79, 70, 229, 0.4) !important; outline-offset: 2px; }}
[data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-primary"] p {{ font-size: 14px !important; font-weight: 600 !important; }}
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"], [data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"] {{
  min-height: 34px; padding: 0 14px !important; transition: background-color 0.15s, border-color 0.15s, color 0.15s; }}
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {{ border-radius: 999px !important; }}
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-segmented_control"] {{ background: var(--dp-surface) !important; border-color: var(--dp-border-strong) !important; }}
[data-testid="stBaseButton-pills"]:hover, [data-testid="stBaseButton-segmented_control"]:hover {{ border-color: var(--dp-primary) !important; color: var(--dp-primary) !important; }}
[data-testid="stBaseButton-pillsActive"], [data-testid="stBaseButton-segmented_controlActive"] {{ background: var(--dp-primary-soft) !important; border-color: var(--dp-primary) !important; color: var(--dp-primary) !important; }}
[data-testid="stBaseButton-pills"] p, [data-testid="stBaseButton-pillsActive"] p, [data-testid="stBaseButton-segmented_control"] p, [data-testid="stBaseButton-segmented_controlActive"] p {{ font-size: 13px !important; font-weight: 600 !important; }}
[data-testid="stWidgetLabel"] p {{ font-size: 13px !important; font-weight: 600 !important; color: var(--dp-text); }}
[data-baseweb="select"] > div, [data-baseweb="input"] {{ border-radius: var(--dp-radius-sm) !important; transition: border-color 0.15s, box-shadow 0.15s; }}
[data-baseweb="select"] > div:hover, [data-baseweb="input"]:hover {{ border-color: var(--dp-border-strong) !important; }}
[data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--dp-border); }}
[data-baseweb="tab"] {{ padding: 10px 14px !important; transition: color 0.15s; }}
[data-baseweb="tab"] p {{ font-size: 14px !important; font-weight: 600 !important; }}
[data-baseweb="tab"]:hover p {{ color: var(--dp-primary); }}
[data-baseweb="tab-highlight"] {{ background-color: var(--dp-primary) !important; height: 3px !important; border-radius: 3px; }}
[data-testid="stExpander"] details {{ border-radius: var(--dp-radius) !important; border-color: var(--dp-border) !important; background: var(--dp-surface); }}
[data-testid="stExpander"] summary p {{ font-size: 14px !important; font-weight: 600 !important; }}
[data-testid="stExpander"] summary:hover p {{ color: var(--dp-primary); }}

/* ======================================================================= sidebar */
[data-testid="stSidebar"] {{ border-right: 1px solid #232A5C; }}
[data-testid="stSidebar"] > div:first-child {{ background: radial-gradient(120% 50% at 0% 0%, rgba(79, 70, 229, 0.30) 0%, rgba(79, 70, 229, 0) 60%), {INK}; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 2px !important; }}
.dp-brand {{ display: flex; align-items: center; gap: 11px; padding: 0 2px 16px 2px; border-bottom: 1px solid #232A5C; margin-bottom: 6px; }}
.dp-brand-mark {{ width: 42px; height: 42px; flex: 0 0 auto; }}
.dp-brand-name {{ font-family: var(--dp-head); font-size: 16px; font-weight: 800; color: #fff; line-height: 1.15; letter-spacing: -0.015em; }}
.dp-brand-sub {{ font-size: 11.5px; color: #9EA6CF; margin-top: 3px; line-height: 1.35; }}
.dp-nav-group {{ font-size: 11px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #7D86B8; margin: 16px 0 4px 6px; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ border-radius: 10px !important; padding: 7px 10px !important; margin: 1px 0;
  transition: background-color 0.15s, color 0.15s; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{ background: rgba(158, 166, 207, 0.12) !important; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a p, [data-testid="stSidebar"] [data-testid="stPageLink"] a span {{ font-size: 14px !important; font-weight: 500 !important; color: #D5D9EE !important; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"], [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
  background: linear-gradient(90deg, rgba(103, 232, 249, 0.16), rgba(103, 232, 249, 0.04)) !important; box-shadow: inset 3px 0 0 {ACCENT_ON_DARK}; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p, [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span {{ color: #fff !important; font-weight: 700 !important; }}
.dp-side-card {{ background: rgba(255, 255, 255, 0.04); border: 1px solid #232A5C; border-radius: 14px; padding: 12px 14px; font-size: 13px; color: #B7BEE0; line-height: 1.5; }}
.dp-side-card b {{ color: #fff; font-weight: 700; }}
.dp-side-label {{ font-size: 11px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #7D86B8; margin: 20px 0 4px 6px; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color: #E3E6F5 !important; }}
[data-testid="stSidebar"] [data-testid="stSlider"] {{ padding: 0 6px 6px 6px; }}
.dp-side-foot {{ margin-top: 18px; border-top: 1px solid #232A5C; padding-top: 16px; font-size: 12px; color: #9EA6CF; line-height: 1.6; }}
.dp-side-foot b {{ color: #fff; font-weight: 700; }}
.dp-side-foot a.dp-linkedin {{ display: inline-flex; align-items: center; gap: 8px; margin-top: 10px; padding: 7px 12px; border-radius: 10px;
  background: #0A66C2; color: #fff !important; font-weight: 600; font-size: 13px; text-decoration: none !important; transition: background-color 0.15s, transform 0.15s; }}
.dp-side-foot a.dp-linkedin:hover {{ background: #0B5CAD; transform: translateY(-1px); }}

/* ======================================================================= loading skeleton */
.dp-skel {{ background: linear-gradient(90deg, #E8EAF4 25%, #F3F4FA 37%, #E8EAF4 63%); background-size: 400% 100%; animation: dp-shimmer 1.4s ease infinite; border-radius: var(--dp-radius); }}
.dp-skel-wrap {{ display: flex; flex-direction: column; gap: 14px; animation: dp-fade 0.3s ease both; }}
.dp-skel-row {{ display: grid; gap: 14px; }}
.dp-skel-note {{ font-size: 13px; color: var(--dp-muted); display: flex; align-items: center; gap: 8px; }}
.dp-skel-note::before {{ content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--dp-primary); animation: dp-pulse 1s ease-in-out infinite; }}

/* ======================================================================= misc */
.dp-kv {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 18px; font-size: 14px; line-height: 1.45; }}
.dp-kv dt {{ color: var(--dp-muted); }}
.dp-kv dd {{ margin: 0; font-weight: 500; font-variant-numeric: tabular-nums; color: var(--dp-text); }}
.dp-product {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
.dp-product-name {{ font-family: var(--dp-head); font-size: 20px; font-weight: 800; letter-spacing: -0.015em; color: var(--dp-text); line-height: 1.25; }}
.dp-reason {{ font-size: 15px; line-height: 1.6; color: var(--dp-text); }}
.dp-empty {{ text-align: center; padding: 36px 16px; border: 1px dashed var(--dp-border-strong); border-radius: var(--dp-radius); color: var(--dp-muted); font-size: 14px; background: var(--dp-surface); }}
.dp-empty strong {{ display: block; color: var(--dp-text); font-size: 15px; margin-bottom: 4px; }}
.dp-about-card {{ background: var(--dp-surface); border: 1px solid var(--dp-border); border-radius: var(--dp-radius); padding: 22px 24px; box-shadow: var(--dp-shadow); height: 100%; }}
.dp-about-card h3 {{ font-family: var(--dp-head) !important; font-size: 17px !important; font-weight: 700 !important; margin: 0 0 8px 0 !important; padding: 0 !important; }}
.dp-about-card p, .dp-about-card li {{ font-size: 14px; line-height: 1.65; color: #343B55; }}
.dp-about-card ul {{ padding-left: 18px; margin: 0; }}
</style>
"""
