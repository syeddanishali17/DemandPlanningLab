"""Export the planning INPUTS from the Excel validation workbook into tidy CSV files.

The Streamlit application never opens the workbook. This one-off script pulls the
inputs (SKU master, suppliers, demand history, inventory snapshot, open purchase
orders and the scenario constants) into ``data/`` so the Python engine is
self-contained and reproducible.

Usage (from the repository root)::

    python scripts/export_excel_data.py --workbook docs/validation/Demand_Inventory_Planning_Model_V1.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _sheet_rows(ws, first_row: int, last_row: int, first_col: int, last_col: int):
    for r in range(first_row, last_row + 1):
        yield [ws.cell(r, c).value for c in range(first_col, last_col + 1)]


def export(workbook: Path) -> None:
    wb = openpyxl.load_workbook(workbook, data_only=True)
    inputs = wb["Inputs"]

    # --- Scenario constants ---------------------------------------------------
    scenario = {
        "company": inputs["B8"].value,
        "warehouse": inputs["B9"].value,
        "snapshot_date": inputs["B10"].value.strftime("%Y-%m-%d"),
        "currency": "EUR",
        "history_weeks": int(inputs["B19"].value),
        "source_workbook": workbook.name,
    }

    # --- Suppliers --------------------------------------------------------------
    suppliers = pd.DataFrame(
        list(_sheet_rows(inputs, 31, 35, 1, 4)),
        columns=["supplier_id", "supplier_name", "lead_time_weeks", "ordering_cost_eur"],
    )

    # --- SKU master + inventory snapshot + open POs -------------------------------
    master_cols = [
        "sku_no",
        "sku",
        "product_name",
        "category",
        "supplier_id",
        "lead_time_weeks",
        "ordering_cost_eur",
        "unit_cost_eur",
        "case_pack",
        "on_hand",
        "on_order",
        "po_due_week",
        "backorders",
        "demand_pattern",
    ]
    master = pd.DataFrame(list(_sheet_rows(inputs, 40, 87, 1, 14)), columns=master_cols)

    sku_master = master[
        ["sku", "product_name", "category", "supplier_id", "unit_cost_eur", "case_pack", "demand_pattern"]
    ]
    inventory = master[["sku", "on_hand", "backorders"]].astype({"on_hand": int, "backorders": int})

    open_pos = master.loc[master["on_order"].fillna(0) > 0, ["sku", "on_order", "po_due_week"]].copy()
    open_pos.insert(0, "po_id", [f"PO-{i + 1:04d}" for i in range(len(open_pos))])
    open_pos = open_pos.rename(columns={"on_order": "quantity", "po_due_week": "due_week"}).astype(
        {"quantity": int, "due_week": int}
    )

    # --- Demand history -------------------------------------------------------------
    history = pd.read_excel(workbook, sheet_name="Demand_History")
    history.columns = ["week", "week_start", "sku", "demand"]
    history["week_start"] = pd.to_datetime(history["week_start"]).dt.strftime("%Y-%m-%d")
    history["demand"] = history["demand"].astype(int)

    # --- Write --------------------------------------------------------------------
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    suppliers.to_csv(DATA_DIR / "suppliers.csv", index=False)
    sku_master.to_csv(DATA_DIR / "sku_master.csv", index=False)
    inventory.to_csv(DATA_DIR / "inventory_snapshot.csv", index=False)
    open_pos.to_csv(DATA_DIR / "purchase_orders.csv", index=False)
    history.to_csv(DATA_DIR / "demand_history.csv", index=False)

    print(f"scenario           : {scenario}")
    print(f"suppliers          : {len(suppliers)} rows")
    print(f"sku_master         : {len(sku_master)} rows")
    print(f"inventory_snapshot : {len(inventory)} rows")
    print(f"purchase_orders    : {len(open_pos)} rows")
    print(
        f"demand_history     : {len(history)} rows ({history['sku'].nunique()} SKUs x {history['week'].max()} weeks)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True, help="Path to the Excel validation workbook")
    args = parser.parse_args()
    export(args.workbook.resolve())
