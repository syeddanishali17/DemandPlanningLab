# Input data

All files are synthetic and were exported from the Excel validation workbook with
`scripts/export_excel_data.py`. The application reads only these CSVs.

| File | One row per | Columns |
|---|---|---|
| `scenario.json` | scenario | company, warehouse, snapshot_date, currency, history_weeks |
| `sku_master.csv` | SKU | sku, product_name, category, supplier_id, unit_cost_eur, case_pack, demand_pattern (info only) |
| `suppliers.csv` | supplier | supplier_id, supplier_name, lead_time_weeks, ordering_cost_eur |
| `inventory_snapshot.csv` | SKU | sku, on_hand, backorders (at the snapshot date) |
| `purchase_orders.csv` | open PO | po_id, sku, quantity, due_week (1 = week starting on the snapshot date) |
| `demand_history.csv` | SKU-week | week (1..104), week_start, sku, demand |

To plan your own products, replace these files with the same columns. `planning/data.py` validates them on load and
reports every problem it finds (missing files or columns, unknown suppliers or SKUs, negative quantities, gaps in the
weekly history). At least 61 weeks of history per SKU are needed (8 warm-up weeks + a 52-week evaluation window + 1).
