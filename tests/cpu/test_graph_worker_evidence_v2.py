"""H2 under owner LO-6 (V2 15:51:55Z: every producer digest unchanged): a graph's worker evidence is KEPT on disk
without the graded predictions again as base64 (schema v2, "packed"), and its task's sqlite row is v2 too; in memory
it is always the exact v1 bytes again (`bundle_benchmark_core.unpack_graph_worker`), so the producer
(`private_evaluation_source`, unchanged) and every in-memory digest see v1. The custody's kept worker-evidence role is
the packed bytes; the scoring core accepts the v1 in memory when it packs to exactly them. A v1 file kept before is read
as it is."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from test_public_bundle_model_custody import (
    _graph_fixture,
    _graph_retain_mutation,
    _json,
    _sha,
)

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session.graph_state_contract import GRAPH_SOURCE_STATE_SCHEMA
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.scoring import bundle_benchmark_core as bundle
from scripts.dev.score_lab import public_unbound_custody as custody

PREDICTIONS = b"[[[[0.5]]]]"
OTHER = b"[[[[0.6]]]]"


def _v1(predictions=PREDICTIONS, **more):
    return {
        "schema": bundle.GRAPH_WORKER_V1,
        "inference_operation": "operation-" + "a" * 64,
        "predictions_digest": bundle._sha(predictions),
        "predictions_raw_base64": base64.b64encode(predictions).decode("ascii"),
        **more,
    }


def _v2(predictions=PREDICTIONS):
    worker = _v1(predictions)
    worker.pop("predictions_raw_base64")
    worker["schema"] = bundle.GRAPH_WORKER_V2
    return worker


def test_pack_then_unpack_gives_the_exact_v1_bytes():
    raw = retention._json(_v1())
    packed = bundle.pack_graph_worker(raw, PREDICTIONS)
    assert packed == retention._json(_v2())
    assert len(packed) < len(raw)
    assert bundle.unpack_graph_worker(packed, PREDICTIONS) == raw
    # a v1 kept before (and anything that is not a v2 evidence) is read as it is
    assert bundle.unpack_graph_worker(raw, PREDICTIONS) == raw
    assert bundle.unpack_graph_worker(b"{}", None) == b"{}"


@pytest.mark.parametrize(
    "raw,predictions",
    [
        (retention._json(_v1()), OTHER),  # its base64 is not these predictions
        (json.dumps(_v1(), indent=1).encode(), PREDICTIONS),  # not its one byte form
        (retention._json({**_v1(), "predictions_digest": _sha(OTHER)}), PREDICTIONS),
        (retention._json({**_v1(), "schema": bundle.GRAPH_WORKER_V2}), PREDICTIONS),
        (retention._json({**_v1(), "predictions_raw_base64": "not!"}), PREDICTIONS),
        (b"not json", PREDICTIONS),
    ],
)
def test_only_a_canonical_v1_of_exactly_its_predictions_is_packed(raw, predictions):
    assert bundle.pack_graph_worker(raw, predictions) is None


@pytest.mark.parametrize(
    "raw,predictions",
    [
        (retention._json(_v2()), OTHER),  # other bytes than its digest
        (retention._json(_v2()), None),  # the predictions are missing
        (retention._json({**_v2(), "predictions_raw_base64": "W10="}), PREDICTIONS),
        (json.dumps(_v2(), indent=1).encode(), PREDICTIONS),
    ],
)
def test_a_v2_without_its_own_predictions_is_refused_as_carbons_gap(raw, predictions):
    with pytest.raises(bundle.BundleBenchmarkRefused, match="graph_worker_unpack"):
        bundle.unpack_graph_worker(raw, predictions)
    with pytest.raises(retention.RetentionUnavailable, match="worker_evidence_unpack"):
        retention._v1_worker(raw, predictions)


def test_retention_keeps_the_worker_evidence_packed_and_names_the_kept_bytes():
    raw = retention._json(_v1())
    artifacts = {
        "inference-receipt.json": b"{}",
        "predictions.json": PREDICTIONS,
        retention.WORKER_EVIDENCE: raw,
    }
    kept = retention._kept_files(artifacts)
    assert kept[retention.WORKER_EVIDENCE] == retention._json(_v2())
    assert {k: v for k, v in kept.items() if k != retention.WORKER_EVIDENCE} == {
        k: v for k, v in artifacts.items() if k != retention.WORKER_EVIDENCE
    }
    assert artifacts[retention.WORKER_EVIDENCE] == raw  # the in-memory files are v1
    # the producer's originals are v1 only (no predictions beside them: its key sets are unchanged)
    assert retention._graph_originals(artifacts) == {
        "inference_receipt_raw": b"{}",
        "worker_evidence_raw": raw,
    }
    # a worker evidence whose base64 is not the retained predictions is kept as it is
    other = {**artifacts, "predictions.json": OTHER}
    assert retention._kept_files(other)[retention.WORKER_EVIDENCE] == raw


def test_retention_writes_the_kept_bytes(tmp_path):
    raw = retention._json(_v1())
    task_root = tmp_path / "task"
    task_root.mkdir(mode=0o700)
    retention._write_retained(
        task_root,
        {"predictions.json": PREDICTIONS, retention.WORKER_EVIDENCE: raw},
    )
    kept = (task_root / retention.WORKER_EVIDENCE).read_bytes()
    assert kept == retention._json(_v2())
    assert retention._v1_worker(kept, PREDICTIONS) == raw


def _entry(worker_role_raw, receipt_raw):
    return {
        "source_schema": GRAPH_SOURCE_STATE_SCHEMA,
        "source_kind": "graph",
        "role_schema": "carbon.scorelab.public-model-artifact-roles.v5",
        "submission_digest": "sha256:" + "1" * 64,
        "state_digest": "sha256:" + "2" * 64,
        "prediction_digest": bundle._sha(PREDICTIONS),
        "roles": {
            "inference_receipt": {
                "file": "inference-receipt.json",
                "codec": "json",
                "sha256": bundle._sha(receipt_raw),
            },
            "worker_evidence": {
                "file": "worker-evidence.json",
                "codec": "json",
                "sha256": bundle._sha(worker_role_raw),
            },
        },
    }


def _inference(worker_raw, receipt_raw, receipt):
    return {
        "inference_receipt_raw": receipt_raw,
        "worker_evidence_raw": worker_raw,
        "receipt": receipt,
        "worker_operation": "operation-" + "a" * 64,
    }


def test_the_scoring_core_takes_the_v1_in_memory_against_a_kept_packed_role():
    receipt = {"predictions_digest": bundle._sha(PREDICTIONS)}
    receipt_raw = retention._json(receipt)
    worker = _v1(
        inference_receipt=receipt,
        submission_digest="sha256:" + "1" * 64,
        state_digest="sha256:" + "2" * 64,
    )
    raw = retention._json(worker)
    packed = bundle.pack_graph_worker(raw, PREDICTIONS)
    for kept in (raw, packed):  # a v1 kept before, and one kept packed
        retained, parsed = bundle._graph_saved_inference_binding(
            _entry(kept, receipt_raw), _inference(raw, receipt_raw, receipt)
        )
        assert parsed == worker and retained == receipt
    # a v1 carrying OTHER predictions never stands for the packed role (its base64 is outside the packed bytes, so it is
    # checked against the evidence's own predictions_digest)
    forged = retention._json({**worker, **_v1(OTHER)})
    forged_v1 = json.loads(forged)
    forged_v1["predictions_digest"] = worker["predictions_digest"]
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_saved_original_binding"
    ):
        bundle._graph_saved_inference_binding(
            _entry(packed, receipt_raw),
            _inference(retention._json(forged_v1), receipt_raw, receipt),
        )


def test_a_v2_rows_predictions_are_its_inference_ops_snapshot(tmp_path):
    operation = "operation-" + "a" * 64
    snapshot = tmp_path / operation / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "predictions.json").write_bytes(PREDICTIONS)
    tasks = SimpleNamespace(ledger=SimpleNamespace(root=tmp_path))
    read = DirectDevelopmentTasksV3._graded_snapshot_predictions
    assert read(tasks, {"inference_operation": operation}) == PREDICTIONS
    with pytest.raises(ValueError):
        read(tasks, {"inference_operation": "../" + operation})
    (snapshot / "predictions.json").unlink()
    with pytest.raises(ValueError):
        read(tasks, {"inference_operation": operation})


def _to_v2(root, manifest_path, originals, **changes):
    worker = json.loads(originals["stage/worker-evidence.json"])
    worker.pop("predictions_raw_base64")
    worker["schema"] = bundle.GRAPH_WORKER_V2
    worker.update(changes)
    _graph_retain_mutation(root, manifest_path, "worker_evidence", _json(worker))
    return worker


def test_custody_takes_a_kept_packed_graph_whose_predictions_role_is_its_digest(
    tmp_path,
):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    v1_receipt = custody.prepare_custody_v5(root, manifest_path)
    _to_v2(root, manifest_path, originals)
    receipt = custody.prepare_custody_v5(root, manifest_path)
    assert receipt["challenge"] == v1_receipt["challenge"]


def test_custody_refuses_a_packed_graph_with_base64_or_another_digest(tmp_path):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    _to_v2(root, manifest_path, originals, predictions_raw_base64="W10=")
    with pytest.raises(custody.CustodyRefused):
        custody.prepare_custody_v5(root, manifest_path)
    (tmp_path / "other").mkdir()
    root, manifest_path, originals = _graph_fixture(tmp_path / "other")
    _to_v2(root, manifest_path, originals, predictions_digest=_sha(b"other"))
    with pytest.raises(custody.CustodyRefused):
        custody.prepare_custody_v5(root, manifest_path)


def test_a_task_kept_before_h2_keeps_its_v1_worker_evidence_on_re_retention(tmp_path):
    """Live 116, 20 Nov 23:01Z: rtsk_fe9da399's owed regrade re-retained its graph artifacts and met its own pre-H2 v1
    worker-evidence.json (packed bytes now differ: ``immutable session artifact conflict``). A task folder that already
    keeps the v1 bytes keeps them (on disk and in its role manifest's digest); a new folder is packed as before.
    """
    raw = retention._json(_v1())
    artifacts = {"predictions.json": PREDICTIONS, retention.WORKER_EVIDENCE: raw}
    old = tmp_path / "old"
    old.mkdir(mode=0o700)
    (old / retention.WORKER_EVIDENCE).write_bytes(raw)  # kept before H2
    (old / "predictions.json").write_bytes(PREDICTIONS)
    assert retention._kept_files(artifacts, old)[retention.WORKER_EVIDENCE] == raw
    retention._write_retained(old, artifacts)  # the re-retention: no conflict
    assert (old / retention.WORKER_EVIDENCE).read_bytes() == raw
    assert retention._v1_worker(raw, PREDICTIONS) == raw  # readers take the v1 form
    # a fresh folder, or one holding other bytes, is packed (H2) exactly as before
    new = tmp_path / "new"
    assert retention._kept_files(artifacts, new)[retention.WORKER_EVIDENCE] == (
        retention._json(_v2())
    )
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    (other / retention.WORKER_EVIDENCE).write_bytes(b"{}")
    assert retention._kept_files(artifacts, other)[retention.WORKER_EVIDENCE] == (
        retention._json(_v2())
    )
