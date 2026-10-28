"""The pool prediction-table checker names what makes a table fail a version's native gates (F08 1.6 grid, 2026-10-28)."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import pool_serving, practice_grid

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "pool_table_check.py"


def _checker():
    spec = importlib.util.spec_from_file_location("pool_table_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(kind="f08", version="1.6"):
    """A table of the version's own reference rows as 'predictions': native space, so every gate passes."""
    bank = practice_grid.practice_bank(kind, version)
    names = practice_grid.input_names(kind, version)
    rows = [
        {
            "inputs": [float(r["inputs"][n]) for n in names],
            "raw": list(map(float, r["reference"])),
        }
        for r in physical.bank_rows(bank, names)
        if r.get("reference") is not None
    ]
    return {
        "schema": pool_serving.SCHEMA,
        "kind": kind,
        "version": version,
        "input_names": list(names),
        "rows": rows,
    }


def test_a_native_space_table_passes_every_gate():
    checker = _checker()
    result = checker.check(_table(), "f08", "1.6")
    assert result["width"] == [result["expected_width"]] == [7]
    assert result["gate_failures"] == {}
    assert all(c["non_finite"] == 0 and c["negative"] == 0 for c in result["columns"])


@pytest.mark.parametrize(
    "mutate, column, counted",
    [
        # frequencies in kHz instead of Hz: every row leaves the 80-600 Hz band
        (
            lambda raw, j: raw.__setitem__(j, raw[j] / 1000.0),
            "peak_frequency_z005_hz",
            "finite_native_summary",
        ),
        # a negative compliance
        (
            lambda raw, j: raw.__setitem__(j, -abs(raw[j])),
            "static_tip_mm_per_n",
            "finite_native_summary",
        ),
    ],
)
def test_the_checker_names_the_column_and_gate_that_fail_on_every_row(
    mutate, column, counted
):
    checker = _checker()
    table = copy.deepcopy(_table())
    names = checker.output_names("f08", "1.6")
    j = names.index(column)
    for row in table["rows"]:
        mutate(row["raw"], j)
    result = checker.check(table, "f08", "1.6")
    assert result["gate_failures"][counted] == result["rows"]
    lines = []
    checker.report(result, lines.append)
    assert any(line.startswith(column) for line in lines)


def test_a_wrong_width_table_is_reported_with_the_interface_width():
    checker = _checker()
    table = copy.deepcopy(_table())
    for row in table["rows"]:
        row["raw"] = row["raw"][:-1]
    result = checker.check(table, "f08", "1.6")
    assert result["width"] == [6] and result["expected_width"] == 7
    assert result["gate_failures"]["finite_native_summary"] == result["rows"]
