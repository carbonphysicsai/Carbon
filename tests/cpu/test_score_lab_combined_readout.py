"""Saved synthetic receipts must bind every cell used in the readout."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.dev.score_lab import combined_readout as cr
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "Business/research/score-lab-campaign-01/combined-matrix"


def plan():
    return json.loads((EVIDENCE / "REGISTRATION.json").read_text(encoding="utf-8"))


def test_committed_summary_is_reproduced_from_all_bound_synthetic_cells():
    actual = cr.summarize(EVIDENCE / "results", plan())
    expected = json.loads((EVIDENCE / "SUMMARY.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["completed_cells"] == 96
    assert actual["scoped_outcomes"] == 24576
    assert sum(actual["status_counts"].values()) == actual["scoped_outcomes"]
    assert actual["status_counts"]["missing_cheap_physics_measurements"] == 9216
    assert actual["selection"] is None


def test_modified_cell_is_rejected_before_readout(tmp_path):
    shutil.copytree(EVIDENCE / "results", tmp_path / "results")
    path = tmp_path / "results/CELL_0_0.json.gz"
    path.write_bytes(path.read_bytes() + b"altered")
    with pytest.raises(LabRefused, match="combined_receipt_digest"):
        cr.summarize(tmp_path / "results", plan())


def test_omitted_cell_cannot_become_complete_by_editing_identity(tmp_path):
    shutil.copytree(EVIDENCE / "results", tmp_path / "results")
    identity_path = tmp_path / "results/IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    del identity["artifacts_sha256"]["CELL_0_0.json.gz"]
    identity_path.write_bytes(json.dumps(identity).encode())
    (tmp_path / "results/CELL_0_0.json.gz").unlink()
    with pytest.raises(LabRefused, match="combined_readout_complete_binding"):
        cr.summarize(tmp_path / "results", plan())
