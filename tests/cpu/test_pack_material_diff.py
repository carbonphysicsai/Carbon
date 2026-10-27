"""The read-only pack diff names which of the five registered-material fields differs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from test_challenge_pack_compatibility import _graph_case, _selected_pack

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dev"
    / "sealed_exam"
    / "pack_material_diff.py"
)
spec = importlib.util.spec_from_file_location("pack_material_diff_script", SCRIPT)
diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diff)


class Snapshot:
    """The prepared pack, with the source registration the pack would carry."""

    def __init__(self, selected, case):
        self._selected = selected
        self._source = {
            "trusted_job": case["job"],
            "benchmark_registration": case["registration"],
            "evaluation_version": "fixture",
        }
        self.manifest_digest = selected.manifest_digest
        self.private = selected.private

    def read_source_registration(self, private_root):
        return self._source

    def __getattr__(self, name):
        return getattr(self._selected, name)


def _rows(tmp_path, wrong_role):
    case = _graph_case(tmp_path)
    selected, public, private = _selected_pack(
        tmp_path / "pack", case, "1", wrong_role=wrong_role
    )
    rows, facts = diff.compare(
        Snapshot(selected, case), public, private, case["ordered_query_bytes"][0]
    )
    return {field: ok for field, ok, _ in rows}, rows, facts


def test_a_matching_pack_has_no_difference(tmp_path):
    verdicts, _, facts = _rows(tmp_path, None)
    assert verdicts == {
        "train": True,
        "interface": True,
        "physics_contract": True,
        "case_bank": True,
        "solver": True,
    }
    assert facts["pack_digest"].startswith("sha256:")


@pytest.mark.parametrize(
    ("wrong_role", "field"),
    [
        ("train", "train"),
        ("interface", "interface"),
        ("physics_contract", "physics_contract"),
        ("case_bank", "case_bank"),
        ("solver_evidence_kind", "solver"),
    ],
)
def test_exactly_the_differing_field_is_named(tmp_path, wrong_role, field):
    verdicts, rows, _facts = _rows(tmp_path, wrong_role)
    assert [name for name, ok in verdicts.items() if ok is False] == [field]
    detail = {name: text for name, _ok, text in rows}[field]
    # digests, sizes and key names only: never a value
    assert "sha256:" in detail or "bytes" in detail
    assert "different" not in detail


def test_without_the_ordered_query_the_case_bank_is_skipped_not_judged(tmp_path):
    case = _graph_case(tmp_path)
    selected, public, private = _selected_pack(tmp_path / "pack", case, "1")
    rows, _ = diff.compare(Snapshot(selected, case), public, private, None)
    assert {field: ok for field, ok, _ in rows}["case_bank"] is None
