"""Demand & Inventory Planner: Streamlit entry point.

Run from the repository root::

    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from ui.components import inject_css
from ui.state import load_or_stop, sidebar_parameters
from ui.theme import fmt_date

AUTHOR = "Syed Danish Ali"
LINKEDIN = "https://www.linkedin.com/in/syeddanishali16/"

st.set_page_config(
    page_title="Demand & Inventory Planner",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "About": f"Demand & Inventory Planner, a portfolio project built by {AUTHOR}. LinkedIn: {LINKEDIN}",
    },
)
inject_css()

PAGES = {
    "Workflow": [
        st.Page("ui/pages/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
        st.Page("ui/pages/sku_explorer.py", title="SKU Explorer", icon=":material/inventory_2:"),
        st.Page("ui/pages/replenishment.py", title="Replenishment Plan", icon=":material/local_shipping:"),
        st.Page("ui/pages/suppliers.py", title="Supplier View", icon=":material/factory:"),
    ],
    "Analysis": [
        st.Page("ui/pages/backtest.py", title="Policy Backtest", icon=":material/history:"),
        st.Page("ui/pages/methodology.py", title="Methodology", icon=":material/menu_book:"),
    ],
    "Project": [
        st.Page("ui/pages/about.py", title="About", icon=":material/person:"),
    ],
}

BRAND_MARK = '<img class="dp-brand-mark" alt="" src="data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgNDYgNDYiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CiAgPGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJkcGciIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAiIHN0b3AtY29sb3I9IiM2MzY2RjEiLz48c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiMwNkI2RDQiLz48L2xpbmVhckdyYWRpZW50PjwvZGVmcz4KICA8cmVjdCB3aWR0aD0iNDYiIGhlaWdodD0iNDYiIHJ4PSIxMyIgZmlsbD0idXJsKCNkcGcpIi8+CiAgPHBhdGggZD0iTTEyIDMwIEwxMiAyNCBNMTggMzAgTDE4IDE5IE0yNCAzMCBMMjQgMjIgTTMwIDMwIEwzMCAxNSIgc3Ryb2tlPSIjZmZmIiBzdHJva2Utd2lkdGg9IjMuMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+CiAgPHBhdGggZD0iTTExIDE3IEwxOCAxMiBMMjUgMTYgTDM1IDkiIHN0cm9rZT0iI0NGRkFGRSIgc3Ryb2tlLXdpZHRoPSIyLjIiIGZpbGw9Im5vbmUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLWRhc2hhcnJheT0iMyAzIi8+CiAgPGNpcmNsZSBjeD0iMzUiIGN5PSI5IiByPSIyLjYiIGZpbGw9IiNmZmYiLz4KPC9zdmc+">'


data = load_or_stop()
navigation = st.navigation(PAGES, position="hidden")

with st.sidebar:
    st.html(
        f'<div class="dp-brand">{BRAND_MARK}<div><div class="dp-brand-name">Demand &amp; Inventory<br>Planner</div>'
        '<div class="dp-brand-sub">Forecast · Safety stock · Reorder · EOQ</div></div></div>'
    )
    for group, pages in PAGES.items():
        st.html(f'<div class="dp-nav-group">{group}</div>')
        for page in pages:
            st.page_link(page, label=page.title, icon=page.icon)

    st.html('<div class="dp-side-label">Planning parameters</div>')
    sidebar_parameters()

    st.html(
        f'<div class="dp-side-card" style="margin-top:14px"><b>{data.scenario.company}</b> (fictitious)<br>'
        f"{data.scenario.warehouse}<br>Snapshot {fmt_date(data.scenario.snapshot_date)} · "
        f"{len(data.skus)} SKUs · synthetic data</div>"
        f'<div class="dp-side-foot">A portfolio project built by <b>{AUTHOR}</b>. Planning logic prototyped in '
        f"Excel, then implemented and validated in Python.<br>"
        f'<a class="dp-linkedin" href="{LINKEDIN}" target="_blank" rel="noopener">'
        '<img width="15" height="15" alt="" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNSIgaGVpZ2h0PSIxNSIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSIjZmZmIj48cGF0aCBkPSJNMjAuNDUgMjAuNDVoLTMuNTZ2LTUuNTdjMC0xLjMzLS4wMi0zLjA0LTEuODUtMy4wNC0xLjg1IDAtMi4xNCAxLjQ1LTIuMTQgMi45NHY1LjY3SDkuMzRWOWgzLjQxdjEuNTZoLjA1Yy40OC0uOSAxLjY0LTEuODUgMy4zNy0xLjg1IDMuNiAwIDQuMjcgMi4zNyA0LjI3IDUuNDZ2Ni4yOHpNNS4zNCA3LjQzYTIuMDYgMi4wNiAwIDEgMSAwLTQuMTMgMi4wNiAyLjA2IDAgMCAxIDAgNC4xM3pNNy4xMiAyMC40NUgzLjU2VjloMy41NnYxMS40NXpNMjIuMjIgMEgxLjc3Qy43OSAwIDAgLjc3IDAgMS43M3YyMC41NEMwIDIzLjIzLjc5IDI0IDEuNzcgMjRoMjAuNDVjLjk4IDAgMS43OC0uNzcgMS43OC0xLjczVjEuNzNDMjQgLjc3IDIzLjIgMCAyMi4yMiAweiIvPjwvc3ZnPg==">'
        "Connect on LinkedIn</a></div>"
    )

navigation.run()
