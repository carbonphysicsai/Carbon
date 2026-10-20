"""A Motor mesher stopped from outside is FAILED_INFRA, never a reference
failure (invariant 7); the frozen runner itself is not edited."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "motor_infra_relabel", ROOT / "scripts/dev/motor/reference/infra_relabel.py"
)
relabel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(relabel)

CUT = "Traceback (most recent call last):\n"
COMPLETE = (
    "Traceback (most recent call last):\n"
    '  File "mesh.py", line 9, in <module>\n'
    "ValueError: magnet arc does not close\n"
)


def _run(tmp_path, cases):
    lines = []
    for case_id, (status, run, log, mesh) in cases.items():
        case = tmp_path / "cases" / case_id
        case.mkdir(parents=True)
        if log is not None:
            (case / "log.mesh").write_text(log)
        if mesh:
            (case / "mesh.json").write_text("{}")
        reasons = ["no torque at step 0"] if status != "OK" else []
        lines.append(
            json.dumps(
                {"case_id": case_id, "status": status, "run": run, "reasons": reasons}
            )
        )
    (tmp_path / "records.jsonl").write_text("\n".join(lines) + "\n")
    return (tmp_path / "records.jsonl").read_bytes()


def _records(tmp_path):
    return {
        r["case_id"]: r
        for r in map(json.loads, (tmp_path / "records.jsonl").read_text().splitlines())
    }


def test_a_planted_truncated_log_becomes_failed_infra(tmp_path):
    original = _run(
        tmp_path,
        {
            "killed-120": ("REFERENCE_SOLVER_FAILED", "exit 120", CUT, False),
            "cut-only": ("REFERENCE_SOLVER_FAILED", "exit 1", CUT, False),
            "signal": ("REFERENCE_SOLVER_FAILED", "exit 137", None, False),
            "real-error": ("REFERENCE_SOLVER_FAILED", "exit 1", COMPLETE, False),
            "meshed": ("REFERENCE_SOLVER_FAILED", "exit 137", CUT, True),
            "ok": ("OK", "exit 0", "", True),
        },
    )
    result = relabel.relabel(tmp_path)
    assert result["relabelled_failed_infra"] == ["cut-only", "killed-120", "signal"]
    records = _records(tmp_path)
    assert records["killed-120"]["status"] == "FAILED_INFRA"
    assert (
        records["killed-120"]["relabelled_from"]["status"] == "REFERENCE_SOLVER_FAILED"
    )
    assert "cut off" in records["cut-only"]["reasons"][0]
    # A mesher's own complete error and a written mesh keep their labels.
    assert records["real-error"]["status"] == "REFERENCE_SOLVER_FAILED"
    assert records["meshed"]["status"] == "REFERENCE_SOLVER_FAILED"
    assert records["ok"]["status"] == "OK"
    # The runner's own file is kept byte for byte, and a rerun is idempotent.
    assert (tmp_path / relabel.RAW).read_bytes() == original
    once = (tmp_path / "records.jsonl").read_bytes()
    relabel.relabel(tmp_path)
    assert (tmp_path / "records.jsonl").read_bytes() == once


def test_the_frozen_runner_is_untouched():
    """The decision study's construction freeze binds run_batch.py; this fix
    lives beside it and the runner never imports it."""
    runner = (ROOT / "scripts/dev/motor/reference/run_batch.py").read_text()
    assert "infra_relabel" not in runner
