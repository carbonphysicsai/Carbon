"""The A40 harness's Level 4 B' leg (plan PR 9; PHASE1_PLAN.md section 3).

CPU only, no pod and no spend. Claims tested:

1. Documents are prepared before spend: `level4_lower` writes one staging
   directory per recipe (the picks, then the coverage recipe), and
   `level4_section` pins each one's submission digest, files and review ops
   in the run record; a missing directory is a refusal.
2. The pod configuration carries the leg on JAX only: one B' rebuild per
   recipe; the trained coverage recipe joins the native recipes, the
   forward-only kNN does not (it carries its own native). The deadline
   counts the leg's rebuilds at the smoke's own leg measurement. The ship
   list carries the pinned files.
3. On the CPU, one recipe's B' rebuild (pod child, fresh interpreter) gives
   the native child's `params_sha256` (same host), refuses documents that
   are not the record's, and records an `outputs_sha256`.
4. The forward-only kNN child (gather, sort) gives, bit for bit, the outputs
   of the JAX function it was lowered from, on the CPU, in the same record;
   the NumPy predictor's difference is recorded, not compared.
5. The comparison is digest equality only. Same host: B' against native.
   Across hosts: B' against B', refused on a driver mismatch or one unit.
   A disagreement is a recorded outcome, never a harness failure.
"""

from __future__ import annotations

import copy
import hashlib
import os

import pytest
from test_a40_acceptance import RECORD, SMOKE, host

from scripts.dev.exam_design.runpod import a40_acceptance as a40
from scripts.dev.exam_design.runpod import a40_pod_phase as phase

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

#: A small JAX recipe for the CPU checks; not a pick.
TINY = {"steps": 16, "width": 16, "depth": 1}


def _record(**parameters):
    record = copy.deepcopy(RECORD)
    strategy = a40._strategy("mlp", {**TINY, **parameters})
    record["picks"] = [{"role": "largest", "id": "r2", "strategy": strategy}]
    record["recipes_by_backend"] = a40.recipes_by_backend(
        {**record, "fno": {"id": "fno_defaults", "strategy": {}}}
    )
    return record


@pytest.fixture(scope="module")
def lowered(tmp_path_factory, monkeypatch_module):
    root = tmp_path_factory.mktemp("repository")
    coverage = (
        {"id": "level4_relu_layer_norm_mlp", "backbone": "mlp",
         "parameters": {**TINY, "activation": "relu", "normalization": "layer_norm"}},
    )  # fmt: skip
    monkeypatch_module.setattr(a40, "LEVEL4_COVERAGE", coverage)
    record = _record()
    record["level4"] = a40.level4_lower(record, root)
    return root, record


@pytest.fixture(scope="module")
def monkeypatch_module():
    patch = pytest.MonkeyPatch()
    yield patch
    patch.undo()


def test_documents_are_pinned_before_spend(lowered, tmp_path):
    root, record = lowered
    section = record["level4"]
    assert [(p["id"], p["kind"]) for p in section["picks"]] == [
        ("r2", "train"),
        ("level4_relu_layer_norm_mlp", "train"),
        ("level4_knn_forward", "forward"),
    ]
    assert section["covers"] == {"gather": True, "named_function": True}
    for pick in section["picks"]:
        assert pick["submission"].startswith("sha256:")
        assert all((root / f).is_file() for f in pick["files"])
    assert a40.level4_section(record, root) == section
    with pytest.raises(a40.Refused):
        a40.level4_section(record, tmp_path)  # nothing committed there


def test_the_leg_is_configured_on_jax_only(lowered):
    _, record = lowered
    jax = a40.phase_config("jax", record)
    torch = a40.phase_config("pytorch", record)
    assert [e["id"] for e in jax["level4"]] == [
        "r2",
        "level4_relu_layer_norm_mlp",
        "level4_knn_forward",
    ]
    assert "level4" not in torch
    assert [r["id"] for r in jax["recipes"]] == ["r2", "level4_relu_layer_norm_mlp"]
    assert [r["id"] for r in torch["recipes"]] == ["r2", "fno_defaults"]
    files = a40.level4_files(record)
    assert files and all(f.startswith(a40.LEVEL4_DIR + "/") for f in files)


def test_the_deadline_counts_the_legs_own_measurement():
    base = a40.pod_deadline_seconds(SMOKE, 4)
    assert base == a40.pod_deadline_seconds(SMOKE, 4, 0)
    leg = dict(SMOKE, level4_wall_seconds=50.0)
    assert a40.pod_deadline_seconds(leg, 4, 2) == int((120 + 4 * 30 + 2 * 50) * 1.5)
    assert a40.pod_deadline_seconds(SMOKE, 4, 2) == int((120 + 6 * 30) * 1.5)


def test_on_cpu_bprime_equals_native_on_the_same_host(lowered):
    root, record = lowered
    entry = a40.level4_entries(record)[0]
    env = phase.pinned_environment("jax", device=None)
    native = phase.run_repeat(entry["strategy"], 0, a40.REPOSITORY, env, timeout=600)
    bprime = phase.run_level4(entry, 0, root, env, timeout=600)
    assert "error" not in native, native
    assert "error" not in bprime, bprime
    assert bprime["params_sha256"] == native["params_sha256"]
    assert phase.hexdigest_ok(bprime["outputs_sha256"])
    assert bprime["submission"] == entry["submission"]
    wrong = dict(entry, submission="sha256:" + "0" * 64)
    assert "error" in phase.run_level4(wrong, 0, root, env, timeout=600)


def _leg(rows_host, rid, params, outputs="o", *, error=False):
    row = {
        "recipe_id": rid,
        "leg": a40.LEVEL4_LEG,
        "repeat": 0,
        "params_sha256": hashlib.sha256(params.encode()).hexdigest(),
        "outputs_sha256": hashlib.sha256(outputs.encode()).hexdigest(),
    }
    if error:
        row = {"recipe_id": rid, "leg": a40.LEVEL4_LEG, "error": "exit 1"}
    rows_host["rows"].append(row)
    return rows_host


def test_comparison_same_host_and_across_hosts():
    # Native repeats hash f"{salt}{r}" with salt "s" and r "s": "ss".
    agree = [
        _leg(host("A", "u1", "1"), "r", "ss"),
        _leg(host("B", "u2", "1"), "r", "ss"),
    ]
    (cell,) = a40.compare(agree)["level4"]
    assert {c["outcome"] for c in cell["same_host"].values()} == {"AGREE"}
    assert cell["across_hosts"]["outcome"] == "AGREE"
    differ = [
        _leg(host("A", "u1", "1"), "r", "x"),
        _leg(host("B", "u2", "1"), "r", "ss", "p"),
    ]
    (cell,) = a40.compare(differ)["level4"]
    assert cell["same_host"]["A"]["outcome"] == "DISAGREE"
    assert cell["across_hosts"]["outcome"] == "DISAGREE"
    drivers = [
        _leg(host("A", "u1", "1"), "r", "ss"),
        _leg(host("B", "u2", "2"), "r", "ss"),
    ]
    (cell,) = a40.compare(drivers)["level4"]
    assert cell["across_hosts"]["outcome"] == "REFUSED_DRIVER_MISMATCH"
    (cell,) = a40.compare([_leg(host("A", "u1", "1"), "r", "ss")])["level4"]
    assert cell["across_hosts"]["outcome"] == "REFUSED_ONE_UNIT"
    failed = [
        _leg(host("A", "u1", "1"), "r", "", error=True),
        _leg(host("B", "u2", "1"), "r", "ss"),
    ]
    (cell,) = a40.compare(failed)["level4"]
    assert cell["same_host"]["A"]["outcome"] == "INCOMPLETE"
    assert cell["across_hosts"]["outcome"] == "INCOMPLETE"
    # Native cells never count a leg row.
    native = a40.compare(agree)["cells"][0]
    assert all(c["repeats"] == 2 for c in native["within_host"].values())


def test_the_forward_only_knn_equals_native_on_cpu(lowered):
    root, record = lowered
    (entry,) = [e for e in a40.level4_entries(record) if e["kind"] == "forward"]
    env = phase.pinned_environment("jax", device=None)
    row = phase.run_level4(entry, 0, root, env, timeout=600)
    assert "error" not in row, row
    assert row["path"] == "forward_only"
    assert row["outputs_sha256"] == row["native_outputs_sha256"]
    assert isinstance(row["numpy_max_abs_difference"], float)
    leg = {"recipe_id": entry["id"], "leg": a40.LEVEL4_LEG, "repeat": 0, **row}
    hosts = [
        {
            "backend": "jax",
            "label": label,
            "identity": {"uuid": label, "driver_version": "1"},
            "rows": [leg],
        }
        for label in ("A", "B")
    ]
    (cell,) = a40.compare(hosts)["level4"]
    assert {c["outcome"] for c in cell["same_host"].values()} == {"AGREE"}
    assert cell["across_hosts"]["outcome"] == "AGREE"


def test_a_jax_only_run_books_two_pods(lowered):
    """The Level 4 leg's grant (OWNER-L4-GPU-LEG-GRANT-01) runs JAX pods only:
    the plan covers that backend alone and books 2 pods + 2 replacements;
    both backends keep the 4 + 2 arithmetic."""
    _, record = lowered
    jax_only = a40.plan(record, {"jax": SMOKE}, backends=("jax",))
    assert set(jax_only) == {"jax"} and jax_only["jax"]["pods"] == 2
    assert jax_only["jax"]["level4_rebuilds_per_pod"] == 3
    both = a40.plan(record, {"jax": SMOKE, "pytorch": SMOKE})
    assert set(both) == {"jax", "pytorch"}
    assert {b["pods"] for b in both.values()} == {4}
