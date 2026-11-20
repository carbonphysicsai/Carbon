"""The recomputed grade-breakdown backfill (data harvest plan G1 / S6; Validator-2 design receipt 20 Nov 11:26:59Z):
historical values never change, a miss writes nothing, the actual diffs are kept, every refusal is typed, and the run
stops resumably on disk or load."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.scoring.physical_dual_pack import METRICS

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "grade_breakdown_backfill", ROOT / "scripts" / "dev" / "grade_breakdown_backfill.py"
)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)

PACK = "sha256:" + "a" * 64
PRODUCER = "sha256:" + "b" * 64
IDENTITY = {
    "challenge": "electric-motor-magnetics",
    "version": "1.8",
    "pack_digest": PACK,
    "producer_digest": PRODUCER,
}
HISTORICAL = {"A": 0.9, "D": 0.8, "total": 0.85}


def _grade(state, n, *, pack=PACK, producer=PRODUCER, version="1.8", revision=True):
    task = "rtsk_" + format(n, "064x")
    artifacts = state / "auto-grade" / "artifacts"
    folder = artifacts / (task + ".evaluation")
    root = artifacts / task
    folder.mkdir(parents=True)
    root.mkdir()
    (root / "predictions.json").write_text("[[1.0]]")
    legs = {
        METRICS["A"]: {"value": HISTORICAL["A"]},
        METRICS["D"]: {"value": HISTORICAL["D"]},
    }
    (folder / "dual-measurement.json").write_text(
        json.dumps(
            {
                "producer_digest": producer,
                "benchmark": {"models": [{"measurements": legs}]},
            }
        )
    )
    (folder / "private-evaluation-binding.json").write_text(
        json.dumps(
            {
                "challenge": "electric-motor-magnetics",
                "challenge_version": version,
                "evaluation_pack_digest": pack,
                "model_p": {"total_score": HISTORICAL["total"]},
            }
        )
    )
    if revision:
        (folder / "grade-installed-commit.json").write_text(
            json.dumps({"commit": "c" * 40, "tree": "d" * 40, "dirty": False})
        )
    (folder / "menu-rowcheck-0123456789abcdef.json").write_text("{}")
    (folder / "single-call.json").write_text("{}")
    os.utime(folder, (1_000_000 + n, 1_000_000 + n))
    return task, folder


def _args(state, apply):
    return SimpleNamespace(
        state=str(state),
        private_root="/unused",
        menu_key_file="/unused",
        copy_hotkey=None,
        tool_commit="e" * 40,
        apply=apply,
        min_free_gb=10.0,
        max_load=16.0,
    )


def _recompute(values):
    calls = []

    def recompute(args, task, inputs):
        calls.append(task)
        return dict(values), {"schema": "carbon.exam.grade-breakdown.v1", "task": task}

    recompute.calls = calls
    return recompute


def _run(state, apply, recompute, **kwargs):
    kwargs.setdefault("free", lambda: 100 * 1024**3)
    kwargs.setdefault("load", lambda: 1.0)
    return backfill.run(
        _args(state, apply), identity=IDENTITY, recompute=recompute, **kwargs
    )


def test_the_dry_run_counts_and_writes_nothing(tmp_path):
    for n in range(3):
        _grade(tmp_path, n)
    recompute = _recompute(HISTORICAL)
    report = _run(tmp_path, False, recompute)
    (group,) = report["groups"]
    assert (group["version"], group["kept"], group["to_compute"]) == ("1.8", 3, 3)
    assert recompute.calls == []
    assert not list(tmp_path.rglob("*" + backfill.SUFFIX))


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_a_matching_grade_gets_one_new_owner_only_recomputed_file_with_its_diffs(
    tmp_path,
):
    task, folder = _grade(tmp_path, 1)
    values = {**HISTORICAL, "A": HISTORICAL["A"] + 1e-6}
    report = _run(tmp_path, True, _recompute(values))
    (group,) = report["groups"]
    assert (group["recomputed"], group["nonzero_diff"], group["self_check_failed"]) == (
        1,
        1,
        0,
    )
    path = folder / (task + backfill.SUFFIX)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    document = json.loads(path.read_bytes())
    assert document["provenance"] == "recomputed"
    assert document["label"] == backfill.LABEL
    assert document["self_check"]["A"]["historical"] == HISTORICAL["A"]
    assert document["self_check"]["A"]["abs_diff"] == pytest.approx(1e-6)
    assert document["self_check"]["total"]["abs_diff"] == 0
    assert document["grade_revision"] == {
        "commit": "c" * 40,
        "tree": "d" * 40,
        "dirty": False,
    }
    assert document["tool_commit"] == "e" * 40
    assert set(document["inputs"]) == {"predictions", "rowcheck", "single_call", "pair"}
    assert not (folder / (task + backfill.LIVE_SUFFIX)).exists()
    assert report["bytes_written"] == path.stat().st_size
    # resumable: a second run skips it
    again = _run(tmp_path, True, _recompute(values))
    assert again["groups"][0]["refused"] == {"recomputed_present": 1}


def test_a_miss_writes_nothing_and_is_counted(tmp_path):
    task, folder = _grade(tmp_path, 1)
    report = _run(tmp_path, True, _recompute({**HISTORICAL, "total": 0.86}))
    (group,) = report["groups"]
    assert (group["recomputed"], group["self_check_failed"]) == (0, 1)
    assert not (folder / (task + backfill.SUFFIX)).exists()


def test_every_refusal_is_typed_and_nothing_is_recomputed_under_other_semantics(
    tmp_path,
):
    _grade(tmp_path, 1, producer="sha256:" + "f" * 64)
    _grade(tmp_path, 2, pack="sha256:" + "9" * 64)
    _grade(tmp_path, 3, revision=False)
    task, folder = _grade(tmp_path, 4)
    (folder / (task + backfill.LIVE_SUFFIX)).write_text("{}")
    task, folder = _grade(tmp_path, 5)
    (folder / "ARCHIVED.json").write_text("{}")
    task, folder = _grade(tmp_path, 6)
    (folder / "single-call.json").unlink()
    recompute = _recompute(HISTORICAL)
    report = _run(tmp_path, True, recompute)
    refused = {}
    for group in report["groups"]:
        for code, n in group["refused"].items():
            refused[code] = refused.get(code, 0) + n
    assert refused == {
        "version_not_supported": 1,
        "pack_differs": 1,
        "grade_revision_unrecorded": 1,
        "live_breakdown_present": 1,
        "archived": 1,
        "single_call_missing": 1,
    }
    assert recompute.calls == []


def test_the_run_stops_resumably_on_low_disk_or_high_load(tmp_path):
    for n in range(2):
        _grade(tmp_path, n)
    recompute = _recompute(HISTORICAL)
    report = _run(tmp_path, True, recompute, free=lambda: 9 * 1024**3)
    assert report["stopped"] == "disk_below_min_free"
    assert recompute.calls == []
    report = _run(tmp_path, True, recompute, load=lambda: 17.0)
    assert report["stopped"] == "load_above_max"
    assert report["groups"][0]["to_compute"] == 2


def test_a_tool_refusal_is_counted_by_its_code(tmp_path):
    _grade(tmp_path, 1)

    def recompute(args, task, inputs):
        error = ValueError("x")
        error.code = "pack_is_not_sealed"
        raise error

    report = _run(tmp_path, True, recompute)
    assert report["groups"][0]["refused"] == {"pack_is_not_sealed": 1}
