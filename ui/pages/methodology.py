"""Methodology: every concept, formula, assumption and limitation, written to be explained out loud."""

import streamlit as st

from ui.components import callout, chain, hero, step_cards, subhead
from ui.state import current_plan

result = current_plan()
params = result.params
scenario = result.data.scenario

hero(
    "Methodology & assumptions",
    "How the numbers are computed, and what they do not claim",
    "Every concept in this tool is deliberately simple enough to explain: what it is, why a planner uses it, "
    "how it is calculated, what it assumes and where it breaks. The same formulas were first built and hand-checked "
    "in an Excel model, then implemented in Python and validated against it.",
)

chain(
    [
        "Historical sales",
        "Forecast",
        "WAPE / bias",
        "Forecast error",
        "Safety stock",
        "Lead-time demand",
        "Reorder point",
        "Inventory position",
        "Reorder decision",
        "EOQ",
        "Recommended order",
        "12-week projection",
        "Exceptions",
        "Backtest",
    ]
)

section_choice = (
    st.segmented_control(
        "Section",
        ["Planning chain", "Assumptions & limitations", "Backtest design", "Out of scope", "Validation"],
        default="Planning chain",
        key="method_section",
        label_visibility="collapsed",
    )
    or "Planning chain"
)

if section_choice == "Planning chain":
    callout(
        "<strong>The chain in one paragraph.</strong> Four simple forecasts are replayed week by week and the most accurate "
        "(simplest on a tie) is kept. Its past misses (error SD) set the safety stock for the chosen service level. Lead-time "
        "demand plus safety stock is the reorder point, which answers <em>when</em> to order; it is compared with the inventory "
        "position (on hand + on order − backorders). When triggered, EOQ answers <em>how much</em>. A 12-week projection then "
        "checks whether supply lands before stock runs out. The 18 cards below are the same chain, one step at a time.",
        kind="info",
    )
    subhead("Forecasting")
    step_cards(
        [
            {
                "number": 1,
                "title": "Naive forecast",
                "formula": "F(t) = A(t−1)",
                "numbers": "last week sold 120 → forecast 120",
                "result": "120",
                "unit": "units",
                "interpretation": "The simplest benchmark; reacts instantly to level shifts but chases every random spike.",
            },
            {
                "number": 2,
                "title": "Moving average (4 / 8 weeks)",
                "formula": "F(t) = mean(A(t−N) … A(t−1))",
                "numbers": "100, 110, 90, 100 → 4-week MA",
                "result": "100",
                "unit": "units",
                "interpretation": "Smooths noise into a level estimate. Short windows react faster; long windows are smoother. Lags trends, ignores seasonality.",
            },
            {
                "number": 3,
                "title": "Simple exponential smoothing",
                "formula": "F(t) = α·A(t−1) + (1−α)·F(t−1);  F(2) = A(1)",
                "numbers": f"α {params.ses_alpha}: 0.3×120 + 0.7×100",
                "result": "106",
                "unit": "units",
                "interpretation": "All history with geometrically declining weights; one parameter controls responsiveness. α is fixed, not optimised. No trend or seasonality.",
            },
            {
                "number": 4,
                "title": "Walk-forward evaluation",
                "formula": "forecast for week t uses only weeks < t",
                "numbers": f"scored on the last {params.evaluation_weeks} weeks",
                "result": "no leakage",
                "interpretation": "Errors are out-of-sample by construction. In-sample errors would understate uncertainty, understate safety stock, and silently break the inventory layer.",
            },
            {
                "number": 5,
                "title": "WAPE",
                "formula": "Σ|F − A| ÷ Σ A",
                "numbers": "actual 100, 0, 50 · forecast 90, 10, 60 → 30 ÷ 150",
                "result": "20%",
                "interpretation": "Volume-weighted, stays defined with zero-demand weeks (MAPE does not). Direction-blind. The method-selection metric.",
            },
            {
                "number": 6,
                "title": "Forecast bias",
                "formula": "Σ(F − A) ÷ Σ A",
                "numbers": "errors −10, +10, +10 on volume 150",
                "result": "+6.7%",
                "interpretation": "Positive = systematic over-forecasting. WAPE and bias answer different questions: a method can be unbiased and still inaccurate.",
            },
            {
                "number": 7,
                "title": "Method selection",
                "formula": "lowest WAPE; simpler wins within tolerance",
                "numbers": f"tolerance {params.wape_tolerance:.0%} · order Naive < MA4 < MA8 < SES",
                "result": "one method per SKU",
                "interpretation": "When two methods are practically tied, prefer the one that is easier to explain and maintain.",
            },
            {
                "number": 8,
                "title": "Forecast error SD",
                "formula": "STDEV.S of weekly errors (F − A)",
                "numbers": "errors −8, 4, 10, −6",
                "result": "8.4",
                "unit": "units",
                "interpretation": "Measures how uncertain the selected forecast is. Feeds safety stock: larger historical misses → more protection.",
            },
        ]
    )
    subhead("Safety stock and reorder point · when to order")
    step_cards(
        [
            {
                "number": 9,
                "title": "Target service level → z",
                "formula": "z = NORM.S.INV(service level)",
                "numbers": "90% → 1.282 · 95% → 1.645 · 99% → 2.326",
                "result": f"{params.z_value:.3f}",
                "unit": f"at {params.target_service_level:.1%}",
                "interpretation": "Cycle service level: probability of no stockout during a lead time. Assumes roughly normal forecast errors; weak for very lumpy demand.",
            },
            {
                "number": 10,
                "title": "Safety stock",
                "formula": "z × error SD × √lead time",
                "numbers": "1.645 × 35 × √3",
                "result": "99.7",
                "unit": "units",
                "interpretation": "Buffer against forecast error over the lead time. Fixed lead time; weekly errors assumed independent (square-root-of-time); review period not added.",
            },
            {
                "number": 11,
                "title": "Lead-time demand",
                "formula": "weekly forecast × lead time",
                "numbers": "100 × 3",
                "result": "300",
                "unit": "units",
                "interpretation": "Expected demand while waiting for a new order. Flat forecast, so trends inside the lead time are ignored.",
            },
            {
                "number": 12,
                "title": "Reorder point",
                "formula": "lead-time demand + safety stock",
                "numbers": "300 + 90",
                "result": "390",
                "unit": "units",
                "interpretation": "Answers WHEN: when the inventory position (not on-hand stock) reaches this level or lower, order.",
            },
        ]
    )
    subhead("Inventory position, EOQ and the order · how much to order")
    step_cards(
        [
            {
                "number": 13,
                "title": "Inventory position",
                "formula": "on hand + on order − backorders",
                "numbers": "75 + 380 − 0",
                "result": "455",
                "unit": "units",
                "interpretation": "The right quantity to compare with the reorder point. Counting stock already on order prevents duplicate orders. Says nothing about when POs arrive (the projection does).",
            },
            {
                "number": 14,
                "title": "Weeks of cover",
                "formula": "inventory position ÷ weekly forecast",
                "numbers": "600 ÷ 50",
                "result": "12",
                "unit": "weeks",
                "interpretation": f"Health indicator and the excess-stock trigger (> {params.excess_weeks_of_cover:g} weeks). A negative position is shown as 0 weeks plus an explicit shortage, never as negative cover.",
            },
            {
                "number": 15,
                "title": "Annual demand & holding cost",
                "formula": "D = forecast × 52 · H = unit cost × holding rate",
                "numbers": f"100 × 52 = 5,200 · €20 × {params.annual_holding_rate:.0%}",
                "result": "5,200 / €4.00",
                "interpretation": "EOQ is defined on annual quantities. The holding rate (capital, storage, obsolescence) is one assumption for all SKUs.",
            },
            {
                "number": 16,
                "title": "Economic order quantity",
                "formula": "√(2 × D × ordering cost ÷ H)",
                "numbers": "√(2 × 5,200 × 40 ÷ 4)",
                "result": "322",
                "unit": "units",
                "interpretation": "Answers HOW MUCH: balances few large orders against many small ones. Assumes stable demand, known costs, no discounts, minimums or capacity limits. Total cost is flat near the optimum, so rounding is cheap.",
            },
            {
                "number": 17,
                "title": "Recommended order",
                "formula": "IF position ≤ ROP: ROUNDUP(EOQ ÷ case pack) × case pack ELSE 0",
                "numbers": "455 ≤ 479 · EOQ 755 · case pack 20",
                "result": "760",
                "unit": "units",
                "interpretation": "One EOQ per weekly review. If the position is far below the reorder point, one order may not restore it and the next review orders again.",
            },
            {
                "number": 18,
                "title": "Projection",
                "formula": "closing = opening + receipts − forecast demand",
                "numbers": f"{params.projection_weeks} weeks, receipts at start of week",
                "result": "first zero week",
                "interpretation": "Includes existing POs and today's recommended order only. Stock hitting zero inside the lead time = stockout risk, because no new order can arrive in time.",
            },
        ],
        cols=3,
    )

if section_choice == "Assumptions & limitations":
    st.markdown(
        f"""
**Scenario.** {scenario.company}, one warehouse ({scenario.warehouse}), {len(result.data.skus)} SKUs, {scenario.history_weeks} weeks of weekly demand,
fixed snapshot date {scenario.snapshot_date:%d %B %Y} (planning week 1 starts on that date). All data is synthetic and was generated to contain
stable, variable, growing, declining and low-volume items, plus deliberate stockout-risk and excess cases so the exception list is never empty.

| Simplification | What it means | Why it is acceptable in V1 |
|---|---|---|
| **Fixed supplier lead times** | Lead-time variability is not modelled in safety stock. | Keeps the safety-stock formula to one uncertainty source (forecast error) that is measured, not assumed. Stated, not hidden. |
| **Flat forecasts** | No trend or seasonality component. | Growing items tend to be under-forecast and declining items over-forecast; the bias metric makes this visible. |
| **Weekly errors assumed independent** | Safety stock scales with √lead time. | Standard textbook approximation. Real cumulative error over several weeks can be larger when misses are correlated. |
| **Error SD around the mean error** | `STDEV.S` measures spread, not total miss. | For a biased method the spread understates the total error. Bias is small for every SKU here (< 4%). |
| **Review period not added** | Protection covers the lead time only, not lead time + the one-week review period. | Simpler story, but a SKU can sit just above its reorder point at one review and run out before the next. In the backtest this is why the 1-week-lead-time SKUs have the lowest proposed fill rate. Protecting over lead time + 1 week is the first change for V1.1. |
| **One EOQ per review** | The order does not top up to a target level. | Preserves the clean "ROP = when, EOQ = how much" story. The next review orders again if needed. |
| **EOQ inputs** | Ordering cost and holding rate are assumptions; no discounts, minimums or capacity. | EOQ is a planning reference, not a purchasing contract. Total cost is flat near the optimum. |
| **Projection = today's decision only** | Future reviews are not simulated. | The stockout-risk flag only needs "does stock hit zero before a new order could land?". The chart says explicitly that it shows the no-further-action case. |
| **Lost sales** | Unmet demand in the backtest is lost, not backordered. | Realistic for retail / e-commerce and the harsher test. |
| **One service level for all SKUs** | No ABC / XYZ differentiation. | Segmentation is a natural next step; it would not change any formula here. |
"""
    )
    callout(
        "<strong>What the reorder point compares against.</strong> Always the inventory position, never on-hand stock alone. "
        "A SKU with 58 units on hand and 276 on order can be above its reorder point and still be at stockout risk if the PO lands "
        "after stock runs out. That is why the tool reports both a reorder decision and a projection-based risk flag, and why the reason "
        "text may say <em>expedite the open PO</em> rather than <em>order more</em>.",
        kind="info",
    )

if section_choice == "Backtest design":
    st.markdown(
        f"""
**Window.** The final {params.backtest_weeks} weeks of history are replayed for every SKU.
**Calibration.** Forecast-method choice and error SD for the proposed policy are estimated on the {params.evaluation_weeks} weeks *before* the replay
and then frozen. Each weekly forecast inside the replay uses only earlier actuals. Actual demand of a week is revealed only after the order decision.

**Weekly sequence (both policies).**
1. Receive orders placed one lead time ago.
2. Review inventory position = stock + on order.
3. Place an order if the policy says so (it arrives one lead time later).
4. Serve demand from stock; the shortfall is a lost sale.

**Opening condition.** Both policies start with {params.backtest_opening_cover_weeks} weeks of trailing 8-week average demand on hand and nothing on order.

| Policy | Rule | What it represents |
|---|---|---|
| **Baseline: four weeks of stock** | If inventory position < {params.baseline_weeks_of_stock} × trailing 4-week average, order up to that level (case-pack rounded). | What a simple spreadsheet rule does today. |
| **Proposed: forecast + SS + ROP + EOQ** | ROP = forecast × LT + z × error SD × √LT; if position ≤ ROP, order EOQ (case-pack rounded). | The methodology of this tool. |

**Metrics.** Fill rate (units sold ÷ demanded), stockout SKU-weeks, average end-of-week inventory in units and at cost, number of orders.
Results are reported as found, including SKUs where the proposed policy is worse. A single synthetic scenario and a 16-week window are evidence of
trade-offs, not proof of general superiority.

**No look-ahead test.** The test suite changes demand after a cut-off week and asserts that every order decision before the cut-off is unchanged.
"""
    )

if section_choice == "Out of scope":
    st.markdown(
        """
These are deliberately **not** in V1. Each would be a sensible next step; none is needed to make the core chain correct.

- ABC-XYZ segmentation with service levels per segment
- Intermittent-demand methods (Croston, TSB) and ADI / CV² classification
- Tracking signal and Forecast Value Added
- Supplier lead-time variability in safety stock
- Review period added to the protection interval (lead time + 1 week)
- Trend / seasonal forecasting methods
- Multi-echelon or multi-warehouse inventory
- Supplier minimums, quantity discounts, capacity constraints
- Solver- or simulation-based optimisation of service vs inventory
- Additional backtest policies and service-level sweeps
- Machine-learning forecasts, promotions, price elasticity, supplier scorecards
- Databases, APIs, authentication, enterprise integrations

The guiding rule: every concept in the tool should be one its author can explain end to end: what it is, why a planner uses it,
how it is calculated, what it assumes and what its limits are.
"""
    )

if section_choice == "Validation":
    st.markdown(
        """
**Excel first, then Python.** The planning logic was first built as an independent Excel model
(`docs/validation/Demand_Inventory_Planning_Model_V1.xlsx`) with hand-checked textbook examples, then implemented in Python.

**What the Python test suite checks against the workbook, for all 48 SKUs:**

| Area | Checked values |
|---|---|
| Forecasting | WAPE, bias, error SD and next-week forecast of all four methods; the selected method; portfolio WAPE |
| Inventory policy | Safety stock, lead-time demand, reorder point, inventory position, weeks of cover, EOQ, case-pack rounding, reorder trigger, recommended order, on-hand value, attention rank |
| Projection | All 12 weekly closing-inventory values, receipts and the first zero week |
| Exceptions | Status of every SKU (6 stockout risk · 11 reorder required · 8 excess · 23 healthy at default parameters) |
| Backtest | All five portfolio metrics for both policies, and every weekly state (stock, on order, orders, sales, lost sales) for all 768 SKU-weeks |

Tolerance is 1e-9 on every numeric comparison. Textbook examples from the brief (EOQ ≈ 322, safety stock = 99.72, ROP = 390, WAPE = 20%)
are unit-tested separately, as are the no-look-ahead and unit-conservation properties of the backtest.

**One intentional difference.** The workbook shows a negative weeks-of-cover when backorders exceed stock; the app shows 0 weeks and states the shortage explicitly.
"""
    )
