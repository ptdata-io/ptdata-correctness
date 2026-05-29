"""Golden-file correctness tests: filing_lineage.

Loads every YAML case in cases/filing_lineage/ and asserts the live service matches. RED until the
service implements the behavior — that is correct; the golden files are the specification.
Configure the target with PTDATA_BASE_URL (and PTDATA_API_KEY if required).
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from conftest import load_cases, run_case


@pytest.mark.parametrize("case", load_cases("filing_lineage"), ids=lambda c: c.get("_file", "?"))
def test_filing_lineage(case, client):
    run_case(client, case)
