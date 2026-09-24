"""About: the project, the author and how the tool was built and validated."""

import streamlit as st

from ui.components import hero
from ui.state import current_plan

AUTHOR = "Syed Danish Ali"
LINKEDIN = "https://www.linkedin.com/in/syeddanishali16/"

result = current_plan()
scenario = result.data.scenario

hero(
    "About this project",
    "A demand & inventory planning tool, built to be explained",
    f"A portfolio project built by <b style='color:#fff'>{AUTHOR}</b>. It answers one planning question for "
    f"{scenario.company}, a fictitious home & living e-tailer: which products need attention this week, when should they "
    "be reordered, and roughly how much should be ordered?",
    chips=[
        "Python · pandas",
        "Streamlit · Plotly",
        "Validated against Excel",
        "Automated tests vs the Excel model",
    ],
)

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    st.html(
        '<div class="dp-about-card"><h3>What it does</h3><ul>'
        "<li>Forecasts 48 SKUs with four explainable methods, scored walk-forward.</li>"
        "<li>Turns forecast error into safety stock and a reorder point.</li>"
        "<li>Compares the inventory position with the reorder point and sizes orders with EOQ.</li>"
        "<li>Projects stock 12 weeks ahead and flags stockout risk, reorders and excess.</li>"
        "<li>Backtests the policy against a simple four-weeks-of-stock rule.</li></ul></div>"
    )
with c2:
    st.html(
        '<div class="dp-about-card"><h3>How it was built</h3>'
        "<p>The planning logic was first prototyped and hand-checked in an Excel model. It was then implemented as a small, "
        "tested Python engine (no UI code inside), and this Streamlit app sits on top of it.</p>"
        "<p>The test suite checks the Python results against the workbook for every SKU (forecasts, safety stock, reorder "
        "points, orders, the 12-week projection, statuses and every week of the backtest) at a tolerance of 1e-9.</p></div>"
    )
with c3:
    st.html(
        f'<div class="dp-about-card"><h3>About the author</h3>'
        f"<p><b>{AUTHOR}</b> builds practical planning and supply-chain analytics tools. This project focuses on the "
        "fundamentals a demand or inventory planner uses every week, kept simple enough to explain end to end.</p>"
        f'<p style="margin-top:14px"><a class="dp-linkedin-light" href="{LINKEDIN}" target="_blank" rel="noopener" '
        'style="display:inline-flex;align-items:center;gap:8px;padding:9px 14px;border-radius:10px;background:#0A66C2;'
        'color:#fff;font-weight:600;text-decoration:none">Connect on LinkedIn →</a></p></div>'
    )

st.html(
    '<div class="dp-callout dp-callout-note" style="margin-top:6px"><strong>Deliberately out of scope for V1:</strong> '
    "ABC-XYZ segmentation, intermittent-demand methods, lead-time variability, multi-echelon inventory, machine-learning "
    "forecasts and solver-based optimisation. All data is synthetic; no real company data is used.</div>"
)
