"""Non-production carrier fixtures; no model execution or isolation claim."""

import base64
import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np
import pytest
from test_bundle_construction_worker import _binding, _recipe, _sha

from carbon.development_session import paired_inference as pair
from carbon.development_session.bundle_construction_worker import BundleInferenceResult
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.reconstruction.worker.model import WorkerImageIdentity


class FixtureLedger:
    def __init__(self, root):
        self.root = root
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            "CREATE TABLE operations (id TEXT, owner TEXT, state TEXT, "
            "reservation BLOB, actual BLOB, result BLOB)"
        )

    @contextmanager
    def db(self):
        yield self.connection

    def record(self, identity, state, actual, result=None):
        self.connection.execute(
            "INSERT INTO operations VALUES (?,?,?,?,?,?)",
            (
                identity,
                "fixture-owner",
                state,
                json.dumps({"numerical_milliseconds": 600000, "research_trials": 1}),
                json.dumps(actual) if actual is not None else None,
                json.dumps(result) if result is not None else None,
            ),
        )


@pytest.fixture
def fixture_pair(tmp_path, monkeypatch):
    ledger = FixtureLedger(tmp_path)
    recipe = _recipe(_sha("a"))
    calls = []
    state = b"fixture inert model; never executed"
    kwargs = {
        "owner": "fixture-owner",
        "identity": "fixture-pair",
        "inference_image": WorkerImageIdentity(*(_sha("b") for _ in range(8))),
        "recipe": recipe,
        "challenge_binding": _binding(recipe),
        "limits_document": {
            "reconstruction_resource_policy": {
                "inference_wall_seconds_max": 600,
                "total_reconstruction_wall_seconds_max": 1800,
            }
        },
        "state_bytes": state,
        "expected_state_digest": pair._digest(state),
        "inputs": np.array([[1.0], [2.0], [3.0]], dtype=np.float32),
        "expected_output_shape": (3, 1),
        "expected_output_dtype": "float32",
        "allowlist_bytes": b"fixture allowlist",
        "seconds": 600,
        "total_seconds": 1800,
        "runner": object(),
    }
    monkeypatch.setattr(pair, "verify_direct_resource_policy", lambda *args: None)
    monkeypatch.setattr(pair, "_trusted_allowlist", lambda raw: object())
    monkeypatch.setattr(pair, "load", lambda *args: None)

    def infer(current_ledger, **call):
        assert current_ledger is ledger
        calls.append(call)
        operation = "operation-" + str(len(calls)) * 64
        snapshot = ledger.root / operation / "snapshot"
        snapshot.mkdir(parents=True)
        predictions = b"[[4.0],[5.0],[6.0]]"
        receipt = {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": recipe.digest,
            "state_digest": pair._digest(state),
            "inputs_digest": pair._digest(pair._tensors(inputs=call["inputs"])),
            "predictions_digest": pair._digest(predictions),
            "measurement": {"scope": "FIXTURE_ONLY", "timing_s": {"inference": 0.01}},
        }
        raw_receipt = json.dumps(receipt).encode()
        (snapshot / "predictions.json").write_bytes(predictions)
        (snapshot / "receipt.json").write_bytes(raw_receipt)
        worker = {
            "operation": operation,
            "files": {
                "predictions.json": pair._digest(predictions),
                "receipt.json": pair._digest(raw_receipt),
            },
        }
        ledger.record(
            call["identity"],
            "SUCCEEDED",
            {"numerical_milliseconds": 101 + len(calls), "research_trials": 1},
            worker,
        )
        return BundleInferenceResult(
            recipe.digest,
            pair._digest(state),
            pair._digest(predictions),
            json.loads(predictions),
            operation,
            receipt,
        )

    monkeypatch.setattr(pair, "_infer_state", infer)
    yield SimpleNamespace(ledger=ledger, kwargs=kwargs, calls=calls, infer=infer)
    ledger.connection.close()


def test_pair_executes_two_full_tensor_queries_and_preserves_identical_outputs(
    fixture_pair,
):
    f = fixture_pair
    result = pair.infer_frozen_pair(f.ledger, **f.kwargs).evidence
    assert result["schema"] == pair.SCHEMA
    assert result["execution_boundary"] == "TEST_ONLY_LOCAL_RUNNER"
    assert result["inference_operation_attempts"] == 2
    assert result["logical_prediction_rows_per_operation"] == 3
    assert result["logical_prediction_row_attempts"] == 6
    assert result["forward_calls"] is None
    assert result["scientific_qualification"] is False
    assert result["official_eligible"] is False
    assert len(f.calls) == 2
    assert f.calls[0]["identity"] != f.calls[1]["identity"]
    for call in f.calls:
        assert call["state"] == f.kwargs["state_bytes"]
        assert call["measure_query"] is True
        assert "train" not in call and "source" not in call
        assert not call["inputs"].flags.writeable
    assert pair._tensors(inputs=f.calls[0]["inputs"]) == pair._tensors(
        inputs=f.calls[1]["inputs"]
    )
    primary, repeat = result["primary"], result["repeat"]
    assert primary["worker_operation"] != repeat["worker_operation"]
    assert primary["originals"] == repeat["originals"]  # equality is legitimate
    assert (
        base64.b64decode(primary["originals"]["predictions.json"]["raw_base64"])
        == b"[[4.0],[5.0],[6.0]]"
    )
    assert [
        x["accounting"]["actual"]["numerical_milliseconds"] for x in (primary, repeat)
    ] == [102, 103]


def test_used_pair_identity_refuses_replay_before_another_query(fixture_pair):
    f = fixture_pair
    pair.infer_frozen_pair(f.ledger, **f.kwargs)
    with pytest.raises(RecipeRefused, match="already_used"):
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert len(f.calls) == 2


@pytest.mark.parametrize("actual", [None, {"numerical_milliseconds": 713}])
def test_failed_repeat_preserves_primary_original_and_unknown_or_actual_charge(
    fixture_pair, monkeypatch, actual
):
    f = fixture_pair
    failure = RecipeRefused("fixture_reference_or_infra_failure")

    def fail_repeat(ledger, **call):
        if call["identity"].endswith("-repeat"):
            ledger.record(call["identity"], "FAILED_INFRA", actual)
            raise failure
        return f.infer(ledger, **call)

    monkeypatch.setattr(pair, "_infer_state", fail_repeat)
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    failed = caught.value
    assert failed.phase == "repeat"
    assert failed.cause is failure
    assert set(failed.originals) == {"primary"}
    assert failed.attempts["repeat"]["state"] == "FAILED_INFRA"
    assert failed.attempts["repeat"]["actual"] == actual
    assert failed.attempts["repeat"]["reservation"]["numerical_milliseconds"] == 600000


def test_first_failure_records_repeat_as_not_started(fixture_pair, monkeypatch):
    f = fixture_pair

    def fail(ledger, **call):
        ledger.record(call["identity"], "FAILED_INFRA", None)
        raise ValueError("fixture incomplete inference")

    monkeypatch.setattr(pair, "_infer_state", fail)
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert caught.value.phase == "primary"
    assert caught.value.originals == {}
    assert caught.value.attempts["repeat"] is None


@pytest.mark.parametrize(
    "field,value",
    [("state_bytes", b"changed"), ("expected_output_shape", (2, 1)), ("seconds", True)],
)
def test_bad_bindings_refuse_before_dispatch(fixture_pair, field, value):
    f = fixture_pair
    with pytest.raises(RecipeRefused, match="binding_invalid"):
        pair.infer_frozen_pair(f.ledger, **{**f.kwargs, field: value})
    assert f.calls == []


def test_changed_original_bytes_cannot_become_pair_evidence(fixture_pair, monkeypatch):
    f = fixture_pair

    def corrupt(ledger, **call):
        result = f.infer(ledger, **call)
        (
            ledger.root / result.worker_operation / "snapshot" / "predictions.json"
        ).write_bytes(b"[]")
        return result

    monkeypatch.setattr(pair, "_infer_state", corrupt)
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert caught.value.cause.code == "inference_pair_original_changed"
    assert caught.value.originals == {}
    assert len(f.calls) == 1


def test_original_requires_settled_accounting_not_zero_cost_fallback(
    fixture_pair, monkeypatch
):
    f = fixture_pair

    def missing(ledger, **call):
        result = f.infer(ledger, **call)
        ledger.connection.execute("UPDATE operations SET actual=NULL")
        return result

    monkeypatch.setattr(pair, "_infer_state", missing)
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert caught.value.cause.code == "inference_pair_accounting_unavailable"


def test_repeat_deadline_exhaustion_retains_primary_and_does_not_dispatch(
    fixture_pair, monkeypatch
):
    f = fixture_pair
    ticks = iter([100.0, 100.0, 100.0, 1890.0])
    monkeypatch.setattr(pair.time, "monotonic", lambda: next(ticks))
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert caught.value.phase == "repeat"
    assert caught.value.cause.code == "inference_pair_deadline_reached"
    assert caught.value.attempts["repeat"] is None
    assert set(caught.value.originals) == {"primary"}
    assert len(f.calls) == 1


def test_candidate_failure_type_is_preserved_without_scientific_reclassification(
    fixture_pair, monkeypatch
):
    from carbon.development_session.research_carrier import (
        MINER_FAILURE_SCHEMA,
        MinerProgramFailure,
    )
    from carbon.reconstruction.worker.model import WorkerCode

    f = fixture_pair
    failure = MinerProgramFailure(
        {
            "schema": MINER_FAILURE_SCHEMA,
            "failure_code": WorkerCode.OUTPUT.value,
            "observation": "fixture candidate failure",
        }
    )

    def fail(ledger, **call):
        ledger.record(call["identity"], "FAILED_MINER", {"numerical_milliseconds": 12})
        raise failure

    monkeypatch.setattr(pair, "_infer_state", fail)
    with pytest.raises(pair.InferencePairFailure) as caught:
        pair.infer_frozen_pair(f.ledger, **f.kwargs)
    assert caught.value.cause is failure
    assert caught.value.attempts["primary"]["state"] == "FAILED_MINER"


def test_unreadable_failure_accounting_stays_unknown(monkeypatch):
    def unreadable(*args):
        raise sqlite3.OperationalError("fixture store temporarily unavailable")

    monkeypatch.setattr(pair, "_accounting", unreadable)
    result = pair._failure_accounting(object(), "fixture-owner", "fixture-id")
    assert result["state"] == "UNKNOWN"
    assert result["actual"] is None
    assert result["reservation"] is None


def test_maintained_infer_state_stages_only_frozen_query_and_validates_both_receipts(
    fixture_pair, monkeypatch
):
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.level4 import allowlist

    f = fixture_pair
    observed = []
    monkeypatch.setattr(pair, "_infer_state", worker._infer_state)
    # Module bytes are not executed in this carrier fixture. The real helper
    # still constructs control/input files and validates every output receipt.
    monkeypatch.setattr(worker, "_stage_bundle_modules", lambda *a, **k: ({}, []))

    def carrier(ledger, **call):
        files = call["files"]
        assert "train.npz" not in files and "source.tar.gz" not in files
        assert files["state.npz"] == f.kwargs["state_bytes"]
        assert call["source"] == worker.INFER_PROGRAM
        observed.append(files["inputs.npz"])
        control = json.loads(files["control.json"])
        operation = "operation-" + str(len(observed)) * 64
        snapshot = ledger.root / operation / "snapshot"
        snapshot.mkdir(parents=True)
        predictions = b"[[4.0],[5.0],[6.0]]"
        receipt = {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": control["recipe_digest"],
            "state_digest": control["state_digest"],
            "inputs_digest": control["inputs_digest"],
            "predictions_digest": pair._digest(predictions),
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": {
                    "preprocess": 0.1,
                    "inference": 0.2,
                    "postprocess": 0.1,
                    "export": 0.1,
                },
                "input_shape": [3, 1],
                "input_dtype": "float32",
                "output_shape": [3, 1],
                "output_dtype": "float32",
            },
        }
        (snapshot / "predictions.json").write_bytes(predictions)
        (snapshot / "receipt.json").write_text(json.dumps(receipt))
        result = {
            "operation": operation,
            "files": {
                name: pair._digest((snapshot / name).read_bytes())
                for name in ("predictions.json", "receipt.json")
            },
        }
        ledger.record(
            call["identity"], "SUCCEEDED", {"numerical_milliseconds": 111}, result
        )
        call["output_validator"](snapshot)
        return result

    evidence = pair.infer_frozen_pair(
        f.ledger,
        **{
            **f.kwargs,
            "runner": carrier,
            "allowlist_bytes": allowlist.load().raw,
        },
    ).evidence
    assert len(observed) == 2 and observed[0] == observed[1]
    assert (
        evidence["primary"]["worker_operation"]
        != evidence["repeat"]["worker_operation"]
    )
