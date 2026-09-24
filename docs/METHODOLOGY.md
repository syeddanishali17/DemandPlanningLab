# Methodology

Every concept in this tool is deliberately simple enough to explain end to end: what it is, why a planner uses it, how it is
calculated, what it assumes and where it breaks. The same formulas were first built and hand-checked in an Excel model
(`docs/validation/Demand_Inventory_Planning_Model_V1.xlsx`), then implemented in Python and validated against it.

**Sign convention used everywhere:** error = forecast − actual, so a positive bias means over-forecasting.
**Timing convention:** week 104 is the last completed history week; planning week 1 starts on the snapshot date
(29 June 2026). Receipts arrive at the start of a week, before that week's demand. An order placed now with lead time L
arrives at the start of planning week L + 1.

---

## 1. Scenario

Hearthline Home Online GmbH (fictitious), one central warehouse, 48 SKUs in 5 categories, 5 suppliers with fixed lead times of
1–6 weeks and ordering costs of €35–90 per order, 104 weeks of weekly demand, a fixed snapshot date. All data is synthetic
and was generated to contain stable, variable, growing, declining and low-volume items plus deliberate stockout-risk and
excess cases, so the exception list is never empty.

Inputs per SKU: product, category, supplier, unit cost, case pack, on-hand stock, backorders and open purchase orders
(any number per SKU, each with a quantity and a due week).

## 2. Forecasting

| Method | Formula | Notes |
|---|---|---|
| Naive | F(t) = A(t−1) | Simplest benchmark; chases noise |
| Moving average, 4 and 8 weeks | F(t) = mean(A(t−N) … A(t−1)) | Smooths noise; lags trends; flat forecast |
| Simple exponential smoothing | F(t) = α·A(t−1) + (1−α)·F(t−1), F(2) = A(1), α = 0.3 fixed | All history with declining weights; no trend or seasonality |

**Walk-forward evaluation.** The forecast for week t uses only weeks before t. Methods are scored on the most recent
52 weeks (weeks 53–104). This makes every error out-of-sample by construction: in-sample errors would understate
uncertainty, understate safety stock and silently break the inventory layer.

**Metrics** (on the evaluation window):

- WAPE = Σ|F − A| ÷ Σ A. Volume-weighted, defined with zero-demand weeks (MAPE is not), direction-blind.
- Bias = Σ(F − A) ÷ Σ A. Positive = systematic over-forecasting. WAPE and bias answer different questions.
- Forecast error SD = sample standard deviation (Excel `STDEV.S`) of the weekly errors of the selected method.

**Selection.** Lowest WAPE wins, unless a simpler method (order: Naive < MA4 < MA8 < SES) is within 1.0 WAPE point of the best,
in which case the simpler one is chosen. Practically tied methods should be the one that is easiest to explain and maintain.

**Weekly forecast.** The selected method's next-week forecast, assumed flat for every future week.

**Portfolio WAPE** = Σ|errors| ÷ Σ actuals across all SKUs (volume-weighted).

## 3. Safety stock and reorder point (when to order)

| Step | Formula | Example |
|---|---|---|
| Safety factor | z = NORM.S.INV(target service level) | 95% → 1.645 |
| Safety stock | SS = z × error SD × √lead time | 1.645 × 35 × √3 = 99.7 |
| Lead-time demand | LTD = weekly forecast × lead time | 100 × 3 = 300 |
| Reorder point | ROP = LTD + SS | 300 + 90 = 390 |

The target is a *cycle* service level: the probability of not stocking out during a lead time. It is not the same as the
fill rate (share of units served), which is what the backtest measures.

Assumptions: fixed lead time; weekly errors roughly normal and independent (hence √lead time); the review period is not
added to the protection interval; error SD measures spread around the mean error, so a biased method's SD understates the
total miss (bias is below 4% for every SKU in this data).

## 4. Inventory position and the reorder decision

- Inventory position = on hand + on order − backorders. This is what the reorder point is compared with, never on-hand stock
  alone: counting stock already on order prevents duplicate orders, the most common bug in replenishment logic.
- Weeks of cover = inventory position ÷ weekly forecast. When backorders exceed stock the position is negative; the app shows
  0 weeks of cover and states the shortage explicitly rather than reporting a negative cover (the workbook shows the
  negative value).
- Decision: if inventory position ≤ reorder point, replenishment is triggered; otherwise no order.

## 5. Economic order quantity (how much to order)

| Step | Formula | Example |
|---|---|---|
| Annual demand | D = weekly forecast × 52 | 100 × 52 = 5,200 |
| Holding cost per unit | H = unit cost × annual holding rate | €20 × 20% = €4.00 |
| EOQ | √(2 × D × ordering cost ÷ H) | √(2 × 5,200 × 40 ÷ 4) = 322 |
| Recommended order | if triggered: ROUNDUP(EOQ ÷ case pack) × case pack, else 0 | EOQ 755, case pack 20 → 760 |

EOQ balances the cost of placing many small orders against the cost of holding large amounts of stock. Assumptions: stable
demand, known ordering and holding costs, no quantity discounts, supplier minimums or capacity limits. Total cost is flat
near the optimum, so case-pack rounding costs little. One EOQ is ordered per weekly review: if the position is far below the
reorder point, the next review orders again.

## 6. Twelve-week projection

closing(w) = opening(w) + existing PO receipts(w) + new order receipt(w) − weekly forecast, with opening(1) = on hand −
backorders and opening(w) = closing(w−1). Existing POs land in their due week, today's recommended order in week
lead time + 1. Closing inventory is not floored at zero: a negative value is the cumulative projected shortfall.

Only today's decision is included. Future weekly reviews, which would place further orders once the inventory position
crosses the reorder point, are not simulated, so the projection answers "what happens if we take no further action". The
app states this next to the chart and marks the week in which the next review would normally reorder. A healthy SKU's
projection therefore eventually reaches zero; that is expected and is not a risk flag.

## 7. Statuses and reasons

Evaluated in priority order, one status per SKU:

| Status | Rule |
|---|---|
| STOCKOUT RISK | projected closing inventory ≤ 0 in any week ≤ lead time, i.e. before a new order placed today could arrive |
| REORDER REQUIRED | inventory position ≤ reorder point |
| EXCESS STOCK | weeks of cover > threshold (default 12) |
| HEALTHY | none of the above |

A SKU can be at stockout risk with no order triggered: on-hand stock runs out before an open PO lands even though the
inventory position (which counts the PO) is above the reorder point. The reason text then says "expedite the open PO".
Every non-healthy SKU gets a reason built from its own numbers, e.g. *"Inventory position of 455 units is 24 units below the
reorder point of 479 units. Replenishment is required. EOQ recommends approximately 755 units, rounded to 760 (case pack 20)."*

Attention ranking: stockout risk first (lowest cover first), then reorder required, then excess stock (highest cover first).

## 8. Backtest

The final 16 weeks of history (weeks 89–104) are replayed for every SKU. Forecast-method choice and error SD for the proposed
policy are calibrated on weeks 37–88 only and then frozen; each weekly forecast inside the replay uses only earlier actuals;
actual demand of a week is revealed only after the order decision.

Weekly sequence for both policies:

1. receive orders placed one lead time ago;
2. review inventory position = stock + on order;
3. place an order if the policy says so (arrives one lead time later);
4. serve demand from stock; the shortfall is a lost sale.

Both policies open with 6 weeks of trailing 8-week average demand on hand and nothing on order.

| Policy | Rule |
|---|---|
| Baseline: four weeks of stock | if inventory position < 4 × trailing 4-week average, order up to that level (case-pack rounded) |
| Proposed: forecast + SS + ROP + EOQ | ROP = forecast × LT + z × error SD × √LT; if inventory position ≤ ROP, order EOQ (case-pack rounded) |

Metrics: fill rate (units sold ÷ demanded), stockout SKU-weeks, average end-of-week inventory in units and at unit cost,
number of orders. A test changes demand after a cut-off week and asserts that every order decision before the cut-off is
unchanged (no look-ahead); another asserts demanded = sold + lost every week (unit conservation).

**Result at default parameters.** Fill rate 92.8% → 95.8%, stockout SKU-weeks 145 → 71, orders 592 → 129, average inventory
value €63k → €111k (+76%). By lead time, baseline vs proposed fill rate: 1 week 100% → 94%, 2 weeks 99.5% → 96.8%,
3 weeks 95% → 96%, 4 weeks 84.5% → 97%, 6 weeks 64% → 98%. A "four weeks of stock" rule is blind to lead time; the proposed
policy sizes protection to it. The short-lead-time shortfall against the 95% target is the documented review-period
simplification: a SKU can sit just above its reorder point at one review and run out before the next.

## 9. Out of scope (future extensions)

ABC-XYZ segmentation with service levels per segment · intermittent-demand methods (Croston, TSB) and ADI/CV² classification ·
tracking signal and Forecast Value Added · lead-time variability · review period in the protection interval (LT + 1) ·
trend / seasonal forecasting · multi-echelon or multi-warehouse inventory · supplier minimums, discounts, capacity ·
solver- or simulation-based optimisation · additional backtest policies and service-level sweeps · machine learning,
promotions, price elasticity, supplier scorecards · databases, APIs, authentication.

## 10. Validation against the Excel model

`scripts/extract_excel_reference.py` pulls the workbook's calculated results into `tests/fixtures/excel_reference/`, and
`tests/test_excel_parity.py` compares the Python engine against them for all 48 SKUs at a tolerance of 1e-9:

| Area | Checked values |
|---|---|
| Forecasting | WAPE, bias, error SD and next-week forecast of all four methods; selected method; portfolio WAPE; calibration-window selection |
| Inventory policy | safety stock, lead-time demand, reorder point, inventory position, weeks of cover, EOQ, case-pack rounding, trigger, recommended order, on-hand value, attention rank |
| Projection | all 12 weekly closing values, receipts and the first zero week |
| Exceptions | every status (6 stockout risk · 11 reorder required · 8 excess · 23 healthy) |
| Backtest | all five portfolio metrics for both policies and every weekly state for all 768 SKU-weeks per policy |

One intentional difference: negative weeks of cover in the workbook are shown as 0 plus an explicit shortage in the app.

## 11. Interview questions this project prepares you for

- Why WAPE rather than MAPE? *Volume-weighted, defined with zero-demand weeks, reflects the units that matter.*
- What is the difference between accuracy and bias, and which is worse? *Bias compounds into systematic over- or under-stocking.*
- Why does safety stock depend on forecast error rather than demand variability? *A good forecast removes predictable variation; only the unpredictable remainder needs a buffer.*
- Why compare the reorder point with the inventory position and not on-hand stock? *Otherwise every open PO triggers a duplicate order.*
- What is the difference between cycle service level and fill rate? *Probability of no stockout per cycle vs share of units served; the backtest measures the second.*
- Where did the proposed policy not help, and why? *Short-lead-time SKUs, because the review week is not protected.*
- What would you change first with real data? *Add the review period, measure lead-time variability, segment service levels.*
