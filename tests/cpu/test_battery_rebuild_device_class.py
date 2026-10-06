"""Scores are compared only within one rebuild device class (TORCH-GPU-01).

The Test Lead's condition on battery implementation 2.0: CPU and GPU rebuilds
of one recipe differ, so every score record carries the worker image and the
device class that rebuilt its model, and scores of different device classes
are never ranked or compared together. This keeps OWNER-SHARED-ANSWER-KEY-01's
"a CPU rebuild is not a scored result" enforceable. These tests hold:
- the validator's score records carry the rebuild identity, from what the
  rebuild recorded;
- a record made before the field existed keeps its meaning: the legacy CPU
  class, its image unrecorded;
- nomination refuses an incumbent of another device class;
- a final whose two rebuilds differ in device class decides nothing;
- the hidden-pool report ranks within one pool version and device class;
- dropping the device class (mutation) reads as CPU and so is refused against
  a GPU incumbent, never silently compared.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import hidden_score
from carbon.battery import exam
from carbon.battery import rebuild_identity as ri

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
    run,
    submission,
)

IMAGE = "sha256:" + "1" * 64
TORCH = "sha256:" + "2" * 64
A40 = "gpu:NVIDIA A40"


def identity(device_class, image=IMAGE):
    return {"schema": ri.SCHEMA, "worker_image": image, "device_class": device_class}


def score(value, device_class=None, *, version=1):
    record = {
        "eligible": True,
        "score": value,
        "important_score": None,
        "pool_version": version,
    }
    if device_class is not None:
        record["rebuild"] = identity(device_class)
    return record


# --- the identity ----------------------------------------------------------------


def test_the_identity_is_what_the_rebuild_recorded():
    carrier = {"backend": "ISOLATED_CARRIER", "image": IMAGE, "pytorch_image": TORCH}
    assert ri.from_reconstruction({**carrier, "fit": {"params_sha256": "x"}}) == (
        identity("cpu", IMAGE)
    )
    # A GPU carrier names the device in its identity, as JAX's GPU backend
    # records do; the same field, the same class, whichever backend rebuilt.
    gpu_carrier = {**carrier, "device_kind": "NVIDIA A40"}
    jax_gpu = {**gpu_carrier, "fit": {}}
    assert ri.from_reconstruction(jax_gpu) == identity(A40, IMAGE)
    torch_gpu = {"backend": "pytorch", "device": "cuda", "device_kind": "NVIDIA A40"}
    assert ri.from_reconstruction({**gpu_carrier, "fit": torch_gpu}) == identity(
        A40, TORCH
    )
    with pytest.raises(ValueError, match="different devices"):
        ri.from_reconstruction(
            {**jax_gpu, "fit": {"backend": "pytorch", "device_kind": "NVIDIA H100"}}
        )


def test_nothing_the_rebuild_returns_can_set_the_device_class():
    """The class is the validator backend's identity alone. A fit (what the
    worker returns, the only output a candidate's construction shapes) that
    names a device the backend did not is refused, never read as a class."""
    carrier = {"backend": "ISOLATED_CARRIER", "image": IMAGE}
    for fit in (
        {"device_kind": "NVIDIA A40"},
        {"backend": "pytorch", "device": "cuda", "device_kind": "NVIDIA A40"},
    ):
        with pytest.raises(ValueError, match="different devices"):
            ri.from_reconstruction({**carrier, "fit": fit})
    # Other fit keys never move it.
    assert ri.from_reconstruction(
        {**carrier, "fit": {"device_class": A40, "device": "cuda"}}
    ) == identity("cpu", IMAGE)
    # A direct (in-process, development) rebuild has no worker image.
    assert (
        ri.from_reconstruction({"backend": "DIRECT", "fit": {}})["worker_image"] is None
    )
    with pytest.raises(ValueError):
        ri.from_reconstruction({"device_kind": "", "fit": {}})


def test_a_record_without_the_field_keeps_its_meaning():
    legacy = ri.of(score(0.1))
    assert legacy == {
        "schema": ri.LEGACY_SCHEMA,
        "worker_image": None,
        "device_class": "cpu",
    }
    with pytest.raises(ValueError):
        ri.of({"rebuild": {"schema": "other", "device_class": "cpu"}})


# --- comparisons never mix classes -------------------------------------------------


def test_mixing_device_classes_in_a_ranking_is_refused():
    assert ri.require_one_class([score(0.1, A40), score(0.2, A40)]) == A40
    assert ri.require_one_class([score(0.1), score(0.2, "cpu")]) == "cpu"
    with pytest.raises(ri.DeviceClassMixed) as mixed:
        ri.require_one_class([score(0.1, A40), score(0.2, "cpu")])
    assert mixed.value.classes == ("cpu", A40)


def test_nomination_refuses_an_incumbent_of_another_device_class():
    assert exam.nominate(score(0.1, A40), score(0.5, A40), 0.05) == (True, "nominated")
    assert exam.nominate(score(0.1, "cpu"), score(0.5), 0.05) == (True, "nominated")
    assert exam.nominate(score(0.1, A40), score(0.5, "cpu"), 0.05) == (
        False,
        "incumbent rebuilt on another device class",
    )
    assert exam.nominate(score(0.1, "cpu"), score(0.5, A40), 0.05)[0] is False


def test_dropping_the_device_class_is_never_a_silent_comparison():
    """Mutation: a GPU record that loses its `rebuild` reads as CPU, so it is
    refused against a GPU incumbent rather than compared with it."""
    gpu = score(0.1, A40)
    dropped = {k: v for k, v in gpu.items() if k != "rebuild"}
    assert ri.device_class(dropped) == "cpu"
    assert exam.nominate(dropped, score(0.5, A40), 0.05)[0] is False
    with pytest.raises(ri.DeviceClassMixed):
        ri.require_one_class([dropped, score(0.5, A40)])


def operator(pid, value, device_class=None, version=1):
    found = {
        "proposal_id": pid,
        "kind": "proposal",
        "submission_id": "bsub-" + pid,
        "pool_version": version,
        "aggregate": {"eligible": True, "score": value, "important_score": None},
        "rotation_overdue": False,
        "overdue_margin_blocks": None,
        "replay": "REPRODUCED",
    }
    if device_class is not None:
        found["rebuild"] = identity(device_class)
    return found


def test_the_hidden_pool_report_ranks_within_one_device_class():
    found = hidden_score.report(
        [
            operator("gpu-a", 0.30, A40),
            operator("cpu-a", 0.10, "cpu"),
            operator("gpu-b", 0.20, A40),
            operator("legacy", 0.05),
        ]
    )
    assert found["schema"] == "carbon.graphite.hidden-pool-report.v2"
    by_class = found["primary"]["by_pool_version"]["1"]
    assert set(by_class) == {"cpu", A40}
    assert [r["proposal_id"] for r in by_class[A40]] == ["gpu-b", "gpu-a"]
    assert [r["proposal_id"] for r in by_class["cpu"]] == ["legacy", "cpu-a"]


# --- the validator records it, end to end -----------------------------------------


def test_the_validators_score_record_carries_the_rebuild_identity(
    tmp_path, refs, backend  # noqa: F811 - the daemon tests' fixtures
):
    from carbon.challenge_validator.battery import SCORE_RECORD_SCHEMA

    validator = make(tmp_path, refs, backend)
    outcome = run(validator, submission("hk1"))
    assert outcome["state"] == "SCORED"
    record = validator.store.score(outcome["submission_id"])["record"]
    # The direct (development) backend rebuilds in process, on the CPU.
    assert record["rebuild"] == {
        "schema": ri.SCHEMA,
        "worker_image": None,
        "device_class": "cpu",
    }
    assert SCORE_RECORD_SCHEMA == "carbon.battery.operator-score-record.v2"


def leveled(pid, value, device_class=None, level=0, version=1):
    found = operator(pid, value, device_class, version)
    if level:
        found["level"] = level
    return found


def placements(report):
    """(table, level, pool version, device class) of every ranked row."""
    out = {}
    for version, classes in report["primary"]["by_pool_version"].items():
        for cls, rows in classes.items():
            for r in rows:
                out[r["proposal_id"]] = ("primary", 0, version, cls)
    for level, table in report["development_levels"].items():
        for version, classes in table["by_pool_version"].items():
            for cls, rows in classes.items():
                for r in rows:
                    out[r["proposal_id"]] = ("development", int(level), version, cls)
    return out


def test_nothing_is_ranked_across_levels_or_device_classes():
    """Main's development table and this branch's device classes, merged:
    Level 0 by (pool version, device class); a development level by (level,
    pool version, device class)."""
    records = [
        leveled("l0-cpu", 0.3, "cpu"),
        leveled("l0-gpu", 0.2, A40),
        leveled("l1-cpu", 0.1, "cpu", level=1),
        leveled("l1-gpu", 0.05, A40, level=1),
        leveled("l1-gpu-v2", 0.04, A40, level=1, version=2),
    ]
    found = placements(hidden_score.report(records))
    assert found == {
        "l0-cpu": ("primary", 0, "1", "cpu"),
        "l0-gpu": ("primary", 0, "1", A40),
        "l1-cpu": ("development", 1, "1", "cpu"),
        "l1-gpu": ("development", 1, "1", A40),
        "l1-gpu-v2": ("development", 1, "2", A40),
    }
    # Every ranked list holds one level, one pool version and one class.
    assert len(set(found.values())) == len(found)


@pytest.mark.parametrize("dropped", ["rebuild", "level"])
def test_dropping_either_key_moves_the_record_never_mixes_it(dropped):
    """Mutation: a record that loses its device class (or its level) is
    placed by what it then says - the legacy CPU class (or Level 0) - so it
    leaves its former list rather than being ranked inside it."""
    gpu_l1 = leveled("x", 0.05, A40, level=1)
    before = placements(hidden_score.report([gpu_l1]))["x"]
    mutated = {k: v for k, v in gpu_l1.items() if k != dropped}
    after = placements(hidden_score.report([mutated]))["x"]
    assert before == ("development", 1, "1", A40)
    if dropped == "rebuild":
        assert after == ("development", 1, "1", "cpu")
    else:
        assert after == ("primary", 0, "1", A40)
