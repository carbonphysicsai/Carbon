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
    torch_gpu = {"backend": "pytorch", "device": "cuda", "device_kind": "NVIDIA A40"}
    assert ri.from_reconstruction({**carrier, "fit": torch_gpu}) == identity(A40, TORCH)
    # A GPU carrier names the device in its identity, as JAX's GPU backend
    # records do; the same field, the same class, whichever backend rebuilt.
    jax_gpu = {**carrier, "device_kind": "NVIDIA A40", "fit": {}}
    assert ri.from_reconstruction(jax_gpu) == identity(A40, IMAGE)
    with pytest.raises(ValueError, match="different devices"):
        ri.from_reconstruction(
            {**jax_gpu, "fit": {"backend": "pytorch", "device_kind": "NVIDIA H100"}}
        )
    # A direct (in-process, development) rebuild has no worker image.
    assert (
        ri.from_reconstruction({"backend": "DIRECT", "fit": {}})["worker_image"] is None
    )
    with pytest.raises(ValueError):
        ri.from_reconstruction({"fit": {"device_kind": ""}})


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
