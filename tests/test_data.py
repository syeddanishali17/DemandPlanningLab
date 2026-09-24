"""Input loading and validation."""

import shutil
from pathlib import Path

import pandas as pd
import pytest

from planning.data import DEFAULT_DATA_DIR, DataValidationError, load_planning_data


def test_demo_data_loads_and_is_joined(data):
    assert len(data.skus) == 48
    assert data.scenario.history_weeks == 104
    assert str(data.scenario.snapshot_date) == "2026-06-29"
    row = data.sku_row("BTH-002")
    assert row["lead_time_weeks"] == 3 and row["ordering_cost_eur"] == 45  # joined from suppliers
    assert row["on_hand"] == 75 and row["on_order"] == 380  # joined from snapshot + open POs
    assert data.demand_series("KIT-001").index.tolist() == list(range(1, 105))
    assert data.scenario.week_start(1) == data.scenario.snapshot_date


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(DEFAULT_DATA_DIR, target)
    return target


def test_missing_file_is_reported(tmp_path):
    target = _copy_data(tmp_path)
    (target / "suppliers.csv").unlink()
    with pytest.raises(DataValidationError) as exc:
        load_planning_data(target)
    assert any("suppliers.csv" in p for p in exc.value.problems)


def test_all_validation_problems_are_collected(tmp_path):
    target = _copy_data(tmp_path)
    master = pd.read_csv(target / "sku_master.csv")
    master.loc[0, "supplier_id"] = "SUP-99"
    master.loc[1, "unit_cost_eur"] = 0
    master.to_csv(target / "sku_master.csv", index=False)
    pos = pd.read_csv(target / "purchase_orders.csv")
    pos.loc[0, "due_week"] = 0
    pos.to_csv(target / "purchase_orders.csv", index=False)
    with pytest.raises(DataValidationError) as exc:
        load_planning_data(target)
    problems = "\n".join(exc.value.problems)
    assert "SUP-99" in problems
    assert "unit_cost_eur" in problems
    assert "due_week" in problems


def test_history_gaps_are_detected(tmp_path):
    target = _copy_data(tmp_path)
    history = pd.read_csv(target / "demand_history.csv")
    history = history[~((history["sku"] == "KIT-001") & (history["week"] == 50))]
    history.to_csv(target / "demand_history.csv", index=False)
    with pytest.raises(DataValidationError) as exc:
        load_planning_data(target)
    assert any("without gaps" in p for p in exc.value.problems)
