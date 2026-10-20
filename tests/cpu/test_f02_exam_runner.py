"""F02's reference runner under the family contract: decks built as the
development exam's (RR-PACKS-04) references were, and typed outcomes that
keep infrastructure apart from reference failures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ELMER = ROOT / "scripts/dev/reference_packages/elmer"
sys.path.insert(0, str(ELMER))
_SPEC = importlib.util.spec_from_file_location(
    "f02_exam_runner", ELMER / "f02_exam_runner.py"
)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)
PINS = ROOT / "docs/development/evidence/reference-solvers-2026-10-15/pins"


def _sha(path):
    # Normalised so the check also holds on a Windows checkout's CRLF writes.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_decks_reproduce_the_exam_references_byte_for_byte(tmp_path):
    registered = {
        e["case"]: e
        for e in json.loads(
            (PINS / "f02-cold-pilot-convergence-manifest.json").read_text()
        )["cases"]
    }
    cases = [
        {"case_id": f"near-{p}", "inputs": {"peak_w": float(p), "on_time_s": 5.0}}
        for p in (84, 85, 86, 87)
    ]
    entries = runner.build(cases, tmp_path / "decks")
    assert len(entries) == 12
    for p in (84, 85, 86, 87):
        for tag, _, _ in runner.RUNGS:
            theirs = registered[f"cool-rect-near-{p}w-{tag}"]["files"]
            d = tmp_path / "decks" / "f02" / f"near-{p}-{tag}"
            assert {f: _sha(d / f) for f in theirs} == theirs
    manifest = json.loads((tmp_path / "decks" / "manifest.json").read_text())
    assert manifest["image"] == runner.readiness.IMAGE
    assert {e["reservation"] for e in manifest["cases"]} == {"primary", "mesh_and_time"}


def test_plans_are_checked():
    good = {
        "batch": "b",
        "cases": [{"case_id": "c0", "inputs": {"peak_w": 80.0, "on_time_s": 5.0}}],
    }
    assert runner.check_plan(good) == good["cases"]
    for bad in (
        {"batch": "b", "cases": []},
        {
            "batch": "b",
            "cases": [{"case_id": "a/b", "inputs": {"peak_w": 1, "on_time_s": 1}}],
        },
        {"batch": "b", "cases": [{"case_id": "c", "inputs": {"peak_w": 1}}]},
        {"batch": "b", "cases": [good["cases"][0], good["cases"][0]]},
    ):
        with pytest.raises(SystemExit):
            runner.check_plan(bad)


SOLVED = ("EXITED", 0, True)


@pytest.mark.parametrize(
    ("runs", "row", "status"),
    [
        ({"primary": SOLVED, "mesh2": SOLVED, "dt0.5": SOLVED}, {"pass": True}, "OK"),
        (
            {"primary": SOLVED, "mesh2": SOLVED, "dt0.5": SOLVED},
            {"pass": False},
            "REFERENCE_INVALID",
        ),
        (
            {"primary": SOLVED, "mesh2": ("TIMEOUT", None, False), "dt0.5": SOLVED},
            None,
            "REFERENCE_TIMEOUT",
        ),
        (
            {"primary": SOLVED, "mesh2": ("EXITED", 1, False), "dt0.5": SOLVED},
            None,
            "REFERENCE_SOLVER_FAILED",
        ),
        (
            {"primary": SOLVED, "mesh2": ("EXITED", 0, False), "dt0.5": SOLVED},
            None,
            "REFERENCE_SOLVER_FAILED",
        ),
        (
            {"primary": SOLVED, "mesh2": ("EXITED", 137, False), "dt0.5": SOLVED},
            None,
            "FAILED_INFRA",
        ),
        (
            {"primary": SOLVED, "mesh2": ("EXITED", 120, False), "dt0.5": SOLVED},
            None,
            "FAILED_INFRA",
        ),
        (
            {"primary": ("EXITED", 125, False), "mesh2": SOLVED, "dt0.5": SOLVED},
            None,
            "FAILED_INFRA",
        ),
        (
            {"primary": ("INFRA", None, False), "mesh2": SOLVED, "dt0.5": SOLVED},
            None,
            "FAILED_INFRA",
        ),
    ],
)
def test_outcomes_keep_infrastructure_apart_from_the_reference(runs, row, status):
    assert runner.classify(runs, row)[0] == status
    assert (status in runner.TERMINAL) is (status != "FAILED_INFRA")


def test_the_pinned_image_is_required(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "batch": "b",
                "cases": [
                    {"case_id": "c", "inputs": {"peak_w": 80.0, "on_time_s": 5.0}}
                ],
            }
        )
    )
    monkeypatch.setenv("CARBON_F02_IMAGE", "sha256:" + "0" * 64)
    with pytest.raises(SystemExit, match="pinned F02 image"):
        runner.main([str(plan), "--out", str(tmp_path / "out")])
