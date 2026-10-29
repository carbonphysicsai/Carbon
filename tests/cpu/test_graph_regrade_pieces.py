"""The graph regrade's building blocks (OWNER-FULL-EXAM-BANK-01, graph source).

`regrade_retained_entry` runs a retained graph's frozen state on another pack's
bank through the same source-free inference the build used. Two helpers carry
that: the inference query arguments (which must stay identical to the graph
worker's own, for each registered adapter) and the regrade's own worker evidence
(the origin's, with the inference this regrade ran). An end-to-end graph regrade
needs a retained graph fixture with a runner and is not run here."""

import base64
import json
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import physical_material, synthetic_linear_field_2d
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import physical_graph_adapter as physical


def _adapter_ids():
    return [worker.SYNTHETIC_ADAPTER_ID, min(physical.ADAPTER_IDS)]


def _discovery(adapter_id):
    return SimpleNamespace(
        info=SimpleNamespace(challenge_key="key"),
        graph_adapter_for=lambda key: adapter_id if key == "key" else None,
    )


def _material(adapter_id):
    if adapter_id == worker.SYNTHETIC_ADAPTER_ID:
        return synthetic_linear_field_2d.bundle_material_v5()
    key = next(
        key for key, spec in physical.SPECS.items() if spec.adapter_id == adapter_id
    )
    return physical_material.bundle_material(*key)


def _workers_query(monkeypatch, tmp_path, adapter_id):
    """The query arguments `reconstruct_and_infer_graph_public` hands to the
    inference call, captured with the heavy parts stubbed."""
    captured = []
    material = _material(adapter_id)
    kit = material["construction_kit"]
    state = b"state-bytes"
    digest = worker._digest(state)
    operation = "operation-" + "1" * 64
    (tmp_path / operation / "snapshot").mkdir(parents=True)
    (tmp_path / operation / "snapshot" / "state.npz").write_bytes(state)
    build = SimpleNamespace(
        worker_operation=operation,
        state_digest=digest,
        state_path=tmp_path / operation / "snapshot" / "state.npz",
    )
    result = SimpleNamespace(state_digest=digest)
    monkeypatch.setattr(worker, "_checked_binding", lambda recipe, binding: binding)
    monkeypatch.setattr(worker, "verify_direct_resource_policy", lambda *_a: "policy")
    monkeypatch.setattr(worker, "reconstruct_public_graph", lambda *_a, **_k: build)
    monkeypatch.setattr(
        worker, "_infer_state", lambda **kwargs: captured.append(kwargs) or result
    )
    ledger = SimpleNamespace(root=tmp_path)
    policy = {
        "total_reconstruction_wall_seconds_max": 1000,
        "build_wall_seconds_max": 200,
        "inference_wall_seconds_max": 200,
    }
    worker.reconstruct_and_infer_graph_public(
        ledger,
        owner="o",
        identity="i",
        image="image",
        recipe=SimpleNamespace(digest="d"),
        challenge_binding={
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
        },
        limits_document={
            **material["construction_limits_document"],
            "reconstruction_resource_policy": policy,
        },
        source_envelope=b"",
        train=b"",
        inputs=np.zeros((1, 1), dtype=np.float32),
        expected_output_shape=(1, 1),
        allowlist_bytes=b"",
        seed=0,
        runner=object(),
        adapter_id=adapter_id,
    )
    (query,) = captured
    return query


@pytest.mark.parametrize("adapter_id", _adapter_ids())
def test_the_regrade_query_is_the_workers_own_for_each_graph_adapter(
    monkeypatch, tmp_path, adapter_id
):
    expected = _workers_query(monkeypatch, tmp_path, adapter_id)
    got = retention._graph_regrade_query(_discovery(adapter_id), _material(adapter_id))
    for name in ("input_name", "provenance", "program", "staged_files"):
        assert got.get(name) == expected.get(name), name
    # No other argument: the caller supplies the rest, as for a bundle.
    assert set(got) <= {"input_name", "provenance", "program", "staged_files"}


def test_an_unregistered_graph_adapter_is_typed_unavailable():
    with pytest.raises(retention.RetentionUnavailable, match="graph_adapter"):
        retention._graph_regrade_query(_discovery(None), {})


@pytest.mark.parametrize(
    "declared,accepted",
    [
        ("<f4", True),
        ("float32", True),
        ("<f8", False),
        ("float64", False),
        ("invalid", False),
        (None, False),
    ],
)
def test_regrade_dtype_uses_the_existing_exact_numeric_contract(declared, accepted):
    adapter_id = min(physical.ADAPTER_IDS)
    material = _material(adapter_id)
    # Synthetic interface metadata around an actual registered v1 adapter.
    # Equivalent spelling is accepted; a different precision still refuses.
    material["interface_document"] = {"outputs": {"dtype": declared}}
    if accepted:
        query = retention._graph_regrade_query(_discovery(adapter_id), material)
        assert query["program"] == worker.PHYSICAL_INFER_PROGRAM
    else:
        with pytest.raises(retention.RetentionUnavailable, match="graph_adapter"):
            retention._graph_regrade_query(_discovery(adapter_id), material)


def test_the_regrade_worker_evidence_is_the_origins_with_the_regrades_inference():
    origin = {
        "schema": "carbon.direct-private-attempt.graph.v1",
        "build_operation": "operation-" + "1" * 64,
        "inference_operation": "operation-" + "2" * 64,
        "state_digest": "sha256:" + "5" * 64,
        "submission_digest": "sha256:" + "6" * 64,
        "predictions_digest": "sha256:" + "7" * 64,
        "predictions_raw_base64": "b3JpZ2lu",
        "inference_receipt": {"old": True},
        "inference_controls_digest": "sha256:" + "8" * 64,
        "timed_operation": "operation-" + "3" * 64,
        "timed_receipt": {"old": True},
    }
    predictions = b"[[1.0]]"
    graded = SimpleNamespace(
        worker_operation="operation-" + "9" * 64,
        predictions_digest="sha256:" + "a" * 64,
    )
    timed = SimpleNamespace(worker_operation="operation-" + "b" * 64)
    raw = retention._graph_regrade_worker_evidence(
        retention._json(origin),
        provider=None,
        owner="o",
        identity="i",
        runner=object(),
        graded=graded,
        receipt_raw=b'{"new":1}',
        predictions=predictions,
        timed_result=timed,
        timed_raw=b'{"timed":1}',
        timed_identity="t",
    )
    evidence = json.loads(raw)
    assert evidence["inference_operation"] == graded.worker_operation
    assert evidence["inference_receipt"] == {"new": 1}
    assert evidence["predictions_digest"] == graded.predictions_digest
    assert base64.b64decode(evidence["predictions_raw_base64"]) == predictions
    assert evidence["timed_operation"] == timed.worker_operation
    assert evidence["timed_receipt"] == {"timed": 1}
    # The build, state and submission are the origin's, untouched.
    for name in ("build_operation", "state_digest", "submission_digest", "schema"):
        assert evidence[name] == origin[name]
    # With a test runner there are no real controls: the origin's value stays.
    assert evidence["inference_controls_digest"] == origin["inference_controls_digest"]
