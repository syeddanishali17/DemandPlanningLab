from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from planning.config import PlanningParameters
from planning.data import PlanningData, load_planning_data
from planning.pipeline import PlanResult, run_plan

FIXTURES = Path(__file__).parent / "fixtures" / "excel_reference"


@pytest.fixture(scope="session")
def params() -> PlanningParameters:
    return PlanningParameters()


@pytest.fixture(scope="session")
def data() -> PlanningData:
    return load_planning_data()


@pytest.fixture(scope="session")
def result(data: PlanningData, params: PlanningParameters) -> PlanResult:
    return run_plan(data, params)


def excel_reference(name: str) -> pd.DataFrame:
    return pd.read_csv(FIXTURES / f"{name}.csv")
