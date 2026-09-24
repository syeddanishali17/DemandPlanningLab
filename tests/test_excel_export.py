"""The per-SKU Excel export: its live formulas must recalculate to the same numbers as the Python engine.

pycel evaluates the workbook's formulas without Excel. It does not implement STDEV.S / NORM.S.INV,
so ``tests/xl_functions.py`` supplies them as a plugin.
"""

import pytest
from openpyxl.workbook.defined_name import DefinedNameDict

from planning.config import PlanningParameters
from planning.excel_export import build_sku_workbook, sku_workbook_bytes
from planning.pipeline import run_plan

pycel = pytest.importorskip("pycel")
# pycel reads defined names through the pre-3.1 openpyxl API.
if not hasattr(DefinedNameDict, "definedName"):
    DefinedNameDict.definedName = property(lambda self: list(self.values()))

# one SKU per status, plus one with two decimals of SES/MA8 selection
SKUS = ["CLN-003", "ELE-003", "BTH-002", "KIT-005", "KIT-006"]


def _compile(result, sku, tmp_path):
    path = tmp_path / f"{sku}.xlsx"
    build_sku_workbook(result, sku).save(path)
    return pycel.ExcelCompiler(filename=str(path), plugins=["tests.xl_functions"])


@pytest.mark.parametrize("sku", SKUS)
def test_every_check_passes(result, sku, tmp_path):
    xl = _compile(result, sku, tmp_path)
    labels = []
    row = 5
    while xl.evaluate(f"Check!A{row}"):
        labels.append(xl.evaluate(f"Check!A{row}"))
        assert xl.evaluate(f"Check!E{row}") == "PASS", (
            sku,
            xl.evaluate(f"Check!A{row}"),
            xl.evaluate(f"Check!B{row}"),
            xl.evaluate(f"Check!C{row}"),
        )
        row += 1
    assert len(labels) == 20


def test_workbook_is_live_changing_the_service_level_recalculates(data, tmp_path):
    base = run_plan(data, PlanningParameters(), include_backtest=False)
    xl = _compile(base, "BTH-002", tmp_path)
    xl.evaluate("Replenishment!D7")  # build the dependency graph before changing an input
    xl.set_value("Inputs!B5", 0.99)  # TSL input cell
    high = run_plan(data, PlanningParameters(target_service_level=0.99), include_backtest=False).sku_plan(
        "BTH-002"
    )
    assert xl.evaluate("Replenishment!D5") == pytest.approx(high["safety_stock"], abs=1e-6)  # safety stock
    assert xl.evaluate("Replenishment!D7") == pytest.approx(high["reorder_point"], abs=1e-6)  # reorder point


def test_bytes_are_a_valid_xlsx(result):
    blob = sku_workbook_bytes(result, "BTH-002")
    assert blob[:2] == b"PK"  # xlsx is a zip archive
    assert len(blob) > 10_000
