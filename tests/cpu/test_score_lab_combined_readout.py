"""Saved synthetic receipts must bind every cell used in the readout."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_combined as cc
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


def _fresh_producer(tmp_path, monkeypatch, *, fail_cell=False):
    """Exercise the real orchestration/receipts with declared fixture workers.

    Workers write empty synthetic cell payloads: this tests the transport and
    identity boundary, not candidate arithmetic (covered by the cell tests).
    """
    registration = plan()
    registration["profiles"] = registration["profiles"][:1]
    for source in registration["sources"]:
        source["sha256"] = cc.source_sha(ROOT / source["path"])
    candidate = tmp_path / "toy.py"
    candidate.write_bytes(b"# Not executed: identity-only fixture worker.\n")
    registration["candidates_sha256"] = cc.file_sha(candidate)
    source_plan = tmp_path / "plan.json"
    source_plan.write_bytes(json.dumps(registration).encode())
    output = tmp_path / "fresh"
    original_popen = subprocess.Popen
    starts = []

    def launch(command, **kwargs):
        if command[0] == "git":
            return original_popen(command, **kwargs)
        # The start identity and immutable plan must exist before first dispatch.
        start = json.loads((output / "START.json").read_bytes())
        starts.append(start)
        assert start["plan_sha256"] == cc.canonical_sha(registration)
        assert start["candidate_sha256"] == cc.file_sha(candidate)
        assert start["producer_sha256"] == cc.source_sha(cc.__file__)
        assert start["source_commit"]
        assert command[4] == str((output / "REGISTERED_PLAN.json").resolve())
        assert json.loads(Path(command[4]).read_bytes()) == registration
        # Altering the caller's plan after dispatch cannot change later workers.
        source_plan.write_bytes(b'{"changed_after_start":true}')
        controls = command[3] == "_controls"
        value = (
            {"status": "CONTROL_PASS"}
            if controls
            else {
                "plan_sha256": start["plan_sha256"],
                "profile_index": int(command[7]),
                "component_index": int(command[8]),
                "rows": [],
                "scorer_evaluations": 0,
            }
        )
        cc._dump(command[6], value)

        class Completed:
            returncode = 1 if fail_cell and not controls else 0

            def communicate(self, timeout):
                assert timeout > 0
                return b"", b"fixture worker"

        return Completed()

    monkeypatch.setattr(subprocess, "Popen", launch)
    result = cc.run(source_plan, candidate, output, ROOT)
    assert all(start == starts[0] for start in starts)
    return registration, result, output


def test_fresh_producer_feeds_readout_without_any_private_export_wrapper(
    tmp_path, monkeypatch
):
    registration, run, output = _fresh_producer(tmp_path, monkeypatch)
    identity, reread, controls, cells = cr.read_results(output, registration)
    assert reread == run and run["status"] == "COMPLETE"
    assert controls["status"] == "CONTROL_PASS" and len(cells) == 32
    assert identity["schema"] == "carbon.dev.score-lab-combined-identity.v1"
    assert cr.summarize(output, registration)["completed_cells"] == 32
    # Even updating the file hash cannot hide a mismatch with the pinned start.
    start = json.loads((output / "START.json").read_bytes())
    start["source_commit"] = "0" * 40
    cc._dump(output / "START.json", start)
    identity["artifacts_sha256"]["START.json"] = cc.file_sha(output / "START.json")
    cc._dump(output / "IDENTITY.json", identity)
    with pytest.raises(LabRefused, match="combined_readout_start_binding"):
        cr.read_results(output, registration)


def test_failed_fresh_producer_emits_identity_but_never_complete_readout(
    tmp_path, monkeypatch
):
    registration, run, output = _fresh_producer(tmp_path, monkeypatch, fail_cell=True)
    assert run["status"] == "STOPPED_WORKER_FAILURE_OR_CAP"
    assert (output / "IDENTITY.json").is_file()
    with pytest.raises(LabRefused, match="combined_readout_complete_binding"):
        cr.read_results(output, registration)
