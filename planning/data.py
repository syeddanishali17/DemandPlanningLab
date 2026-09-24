"""Load and validate the planning inputs from the CSV files in ``data/``.

Everything the engine needs is bundled into one immutable :class:`PlanningData` object so
the calculation modules never touch the file system themselves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cached_property
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

REQUIRED_COLUMNS = {
    "sku_master.csv": ["sku", "product_name", "category", "supplier_id", "unit_cost_eur", "case_pack"],
    "suppliers.csv": ["supplier_id", "supplier_name", "lead_time_weeks", "ordering_cost_eur"],
    "inventory_snapshot.csv": ["sku", "on_hand", "backorders"],
    "purchase_orders.csv": ["po_id", "sku", "quantity", "due_week"],
    "demand_history.csv": ["week", "week_start", "sku", "demand"],
}

# 8 warm-up weeks for MA8 + the evaluation window + at least one scored week.
MIN_HISTORY_WEEKS = 61


class DataValidationError(ValueError):
    """Raised when the input files are structurally unusable. Carries every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Input data failed validation:\n- " + "\n- ".join(problems))


@dataclass(frozen=True)
class Scenario:
    company: str
    warehouse: str
    snapshot_date: date
    currency: str
    history_weeks: int

    def week_start(self, planning_week: int) -> date:
        """Calendar date of the start of a planning week (week 1 starts on the snapshot date)."""
        return self.snapshot_date + timedelta(weeks=planning_week - 1)


@dataclass(frozen=True)
class PlanningData:
    scenario: Scenario
    sku_master: pd.DataFrame
    """One row per SKU with supplier attributes and the inventory snapshot joined in."""
    suppliers: pd.DataFrame
    demand_history: pd.DataFrame
    """Tidy weekly demand: week, week_start, sku, demand."""
    purchase_orders: pd.DataFrame
    """Open POs: po_id, sku, quantity, due_week (1 = week starting on the snapshot date)."""

    @property
    def skus(self) -> list[str]:
        return self.sku_master["sku"].tolist()

    def sku_row(self, sku: str) -> pd.Series:
        rows = self.sku_master.loc[self.sku_master["sku"] == sku]
        if rows.empty:
            raise KeyError(f"unknown SKU {sku!r}")
        return rows.iloc[0]

    @cached_property
    def _demand_by_sku(self) -> dict[str, pd.Series]:
        matrix = self.demand_matrix()
        return {sku: matrix[sku].rename("demand") for sku in matrix.columns}

    def demand_series(self, sku: str) -> pd.Series:
        """Weekly actual demand for one SKU, indexed by week number (1..N)."""
        try:
            return self._demand_by_sku[sku]
        except KeyError as exc:
            raise KeyError(f"unknown SKU {sku!r}") from exc

    def demand_matrix(self) -> pd.DataFrame:
        """Weeks as rows, SKUs as columns."""
        return self.demand_history.pivot(index="week", columns="sku", values="demand").sort_index()

    def open_orders(self, sku: str) -> pd.DataFrame:
        return self.purchase_orders.loc[self.purchase_orders["sku"] == sku]


def _read_csv(data_dir: Path, name: str, problems: list[str]) -> pd.DataFrame | None:
    path = data_dir / name
    if not path.exists():
        problems.append(f"missing file: {path.name}")
        return None
    frame = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in frame.columns]
    if missing:
        problems.append(f"{name}: missing columns {missing}")
        return None
    return frame


def load_planning_data(data_dir: Path | str = DEFAULT_DATA_DIR) -> PlanningData:
    """Read the CSV inputs, validate them and join supplier + inventory attributes onto the SKU master."""
    data_dir = Path(data_dir)
    problems: list[str] = []

    scenario_path = data_dir / "scenario.json"
    scenario_raw: dict = {}
    if scenario_path.exists():
        scenario_raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    else:
        problems.append("missing file: scenario.json")

    frames = {name: _read_csv(data_dir, name, problems) for name in REQUIRED_COLUMNS}
    if problems:
        raise DataValidationError(problems)

    master = frames["sku_master.csv"]
    suppliers = frames["suppliers.csv"]
    inventory = frames["inventory_snapshot.csv"]
    pos = frames["purchase_orders.csv"]
    history = frames["demand_history.csv"]

    problems.extend(_validate(master, suppliers, inventory, pos, history))
    if problems:
        raise DataValidationError(problems)

    history = history.copy()
    history["week_start"] = pd.to_datetime(history["week_start"]).dt.date
    history = history.sort_values(["sku", "week"]).reset_index(drop=True)

    on_order = pos.groupby("sku")["quantity"].sum().rename("on_order")
    joined = (
        master.merge(suppliers, on="supplier_id", how="left")
        .merge(inventory, on="sku", how="left")
        .merge(on_order, on="sku", how="left")
    )
    joined["on_order"] = joined["on_order"].fillna(0).astype(int)
    joined["on_hand"] = joined["on_hand"].astype(int)
    joined["backorders"] = joined["backorders"].astype(int)
    if "demand_pattern" not in joined.columns:
        joined["demand_pattern"] = ""

    scenario = Scenario(
        company=scenario_raw.get("company", "Demo company"),
        warehouse=scenario_raw.get("warehouse", "Central warehouse"),
        snapshot_date=date.fromisoformat(scenario_raw["snapshot_date"]),
        currency=scenario_raw.get("currency", "EUR"),
        history_weeks=int(history["week"].max()),
    )
    return PlanningData(
        scenario=scenario,
        sku_master=joined.reset_index(drop=True),
        suppliers=suppliers.reset_index(drop=True),
        demand_history=history,
        purchase_orders=pos.sort_values(["sku", "due_week"]).reset_index(drop=True),
    )


def _validate(master, suppliers, inventory, pos, history) -> list[str]:
    """Structural checks that would otherwise surface as confusing calculation errors."""
    problems: list[str] = []
    skus = set(master["sku"])

    if master["sku"].duplicated().any():
        problems.append("sku_master.csv: duplicate SKU codes")
    if suppliers["supplier_id"].duplicated().any():
        problems.append("suppliers.csv: duplicate supplier ids")
    unknown_suppliers = set(master["supplier_id"]) - set(suppliers["supplier_id"])
    if unknown_suppliers:
        problems.append(f"sku_master.csv: unknown supplier ids {sorted(unknown_suppliers)}")
    if (master["unit_cost_eur"] <= 0).any():
        problems.append("sku_master.csv: unit_cost_eur must be positive")
    if (master["case_pack"] <= 0).any():
        problems.append("sku_master.csv: case_pack must be positive")
    if (suppliers["lead_time_weeks"] <= 0).any():
        problems.append("suppliers.csv: lead_time_weeks must be positive")
    if (suppliers["ordering_cost_eur"] <= 0).any():
        problems.append("suppliers.csv: ordering_cost_eur must be positive")

    missing_inventory = skus - set(inventory["sku"])
    if missing_inventory:
        problems.append(f"inventory_snapshot.csv: no row for {sorted(missing_inventory)}")
    if inventory["sku"].duplicated().any():
        problems.append("inventory_snapshot.csv: duplicate SKU rows")
    if (inventory[["on_hand", "backorders"]] < 0).any().any():
        problems.append("inventory_snapshot.csv: on_hand and backorders must be non-negative")

    unknown_po_skus = set(pos["sku"]) - skus
    if unknown_po_skus:
        problems.append(f"purchase_orders.csv: unknown SKUs {sorted(unknown_po_skus)}")
    if (pos["quantity"] <= 0).any():
        problems.append("purchase_orders.csv: quantity must be positive")
    if (pos["due_week"] < 1).any():
        problems.append("purchase_orders.csv: due_week must be >= 1 (1 = week starting on the snapshot date)")

    unknown_hist_skus = set(history["sku"]) - skus
    if unknown_hist_skus:
        problems.append(f"demand_history.csv: unknown SKUs {sorted(unknown_hist_skus)}")
    missing_hist = skus - set(history["sku"])
    if missing_hist:
        problems.append(f"demand_history.csv: no history for {sorted(missing_hist)}")
    if (history["demand"] < 0).any():
        problems.append("demand_history.csv: demand must be non-negative")
    if history.duplicated(["sku", "week"]).any():
        problems.append("demand_history.csv: duplicate (sku, week) rows")
    weeks_per_sku = history.groupby("sku")["week"].agg(["min", "max", "count"])
    gaps = weeks_per_sku[(weeks_per_sku["min"] != 1) | (weeks_per_sku["max"] != weeks_per_sku["count"])]
    if not gaps.empty:
        problems.append(f"demand_history.csv: weeks must run 1..N without gaps for {gaps.index.tolist()[:5]}")
    if weeks_per_sku["max"].nunique() > 1:
        problems.append("demand_history.csv: every SKU must have the same number of history weeks")
    short = weeks_per_sku[weeks_per_sku["count"] < MIN_HISTORY_WEEKS]
    if not short.empty:
        problems.append(
            f"demand_history.csv: at least {MIN_HISTORY_WEEKS} weeks of history needed for {short.index.tolist()[:5]}"
        )
    return problems
