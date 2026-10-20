"""With a pool store, a bound private evaluation is filed and meets the incumbent.

The retained graded submission contends for the DEVELOPMENT crown through the
registered comparator (KOTH-TAKEOVER-RULE-01); the comparison is recorded in the
retention result and never unbinds the evaluation.
"""

# ruff: noqa: F811  (the imported `case` fixture is received as a test argument)
import json
from types import SimpleNamespace

import pytest
from test_normal_dual_pack_retention import _fixture, _producer
from test_physical_dual_pack_end_to_end import _produce, case  # noqa: F401

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import bank_promotion
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.bank_promotion import BankPromotion
from carbon.scoring import physical_dual_pack
from carbon.scoring import private_evaluation_evidence as evidence
from carbon.scoring import private_evaluation_source as source
from carbon.scoring.engine import ScoreEngine


def _intent(adapter, submission_id):
    adapter.ledger.record_recipe_task_intent(
        adapter.contract_digest,
        submission_id,
        "fixture-owner",
        "sha256:" + "9" * 64,
    )


def _setup(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    # The inert graph fixture binds a v3 dual evaluation (no repeat pair, hence no v4). The
    # comparison itself is the real one; only its paired-binding schema gate is pointed at
    # the fixture's schema so the wiring around it can be exercised.
    monkeypatch.setattr(
        bank_promotion, "PAIRED_BINDING", "carbon.scoring.private-evaluation-binding.v3"
    )
    monkeypatch.setattr(source, "produce_dual_benchmark_input", _producer(fixture))
    _intent(fixture.adapter, fixture.task_id)
    return fixture, PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0)


def _run(fixture, tmp_path, store, submission_id=None):
    return retention.retain_served_result(
        fixture.adapter,
        submission_id or fixture.task_id,
        artifact_directory=fixture.artifact_root,
        entry_directory=tmp_path / "bank-entries",
        pool_store=store,
    )


def _second_submission(fixture):
    """A second graded submission of the same owner, in a later epoch."""
    second = "rtsk_" + "b" * 64
    adapter = fixture.adapter
    adapter.ledger.record(
        SimpleNamespace(
            hotkey="fixture-owner",
            receipt={"sequence": 2, "digest": "e", "block": 720},
            contract_digest=adapter.contract_digest,
        ),
        kind="OUTCOME",
        submission_id=second,
    )
    _intent(adapter, second)
    provider = adapter._provider("fixture-owner")
    provider._requests[second] = provider._requests[fixture.task_id]
    return second


def test_the_first_scored_submission_becomes_the_first_incumbent(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    result = _run(fixture, tmp_path, store)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    koth = result["koth_comparison"]
    assert koth.get("outcome") == "FIRST_INCUMBENT", koth
    assert koth["reason"] == "first_scored_contender"
    held = store.incumbent()
    assert held == {
        "model_id": fixture.task_id,
        "reason": "bank_comparison_development",
    }
    # Filed once under the submission's own id on the evaluation key it was graded on.
    pair = BankPromotion(
        store,
        registered_source_receipt_sha256=_pin(result),
    ).private_pair(fixture.task_id, koth["evaluation_key"])
    assert pair["candidate"]["submission_id"] == fixture.task_id


def _pin(result):
    import json

    return json.loads(result["private_evaluation_path"].read_bytes())[
        "source_receipt_sha256"
    ]


def test_without_a_pool_store_nothing_changes(tmp_path, monkeypatch):
    fixture, _ = _setup(tmp_path, monkeypatch)
    result = _run(fixture, tmp_path, None)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    assert "koth_comparison" not in result


def test_with_no_registered_noise_a_challenger_is_unavailable(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    _run(fixture, tmp_path, store)
    second = _second_submission(fixture)
    result = _run(fixture, tmp_path, store, second)
    koth = result["koth_comparison"]
    assert koth["outcome"] == "UNAVAILABLE"
    assert koth["reason"] == "rebuild_noise_unregistered"
    # The incumbent and its clock are untouched; the evaluation is still bound.
    assert store.incumbent()["model_id"] == fixture.task_id
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"


def test_the_leg_minimum_baseline_never_contends(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    entry_id = _run(fixture, tmp_path, None)["entry_id"]
    monkeypatch.setattr(
        physical_dual_pack, "minimum_source_entry_ids", lambda _definition: [entry_id]
    )
    result = _run(fixture, tmp_path, store)
    koth = result["koth_comparison"]
    assert koth["outcome"] == "NO_WINNER"
    assert koth["reason"] == "leg_minimum_source_not_a_contender"
    assert store.incumbent() is None


def test_a_pool_refusal_never_unbinds_the_evaluation(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)

    def refuse(self, submission_id, key, comparator):
        raise StateError("incumbent_moved")

    monkeypatch.setattr(BankPromotion, "consider_private", refuse)
    result = _run(fixture, tmp_path, store)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    assert result["private_evaluation_path"].is_file()
    assert result["koth_comparison"] == {"error": "incumbent_moved"}
    assert store.incumbent() is None


def test_the_dev_incumbent_is_not_a_payable_reason(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    _run(fixture, tmp_path, store)
    assert store.incumbent()["reason"] == "bank_comparison_development"


def test_a_regrade_never_contends_or_feeds_the_ladder(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    first = _run(fixture, tmp_path, None)
    regrade = retention._Regrade(
        "fixture-owner", object(), "origin", first["entry_id"], None
    )
    bare = {
        key: value
        for key, value in first.items()
        if key
        not in (
            "private_evaluation_state",
            "private_evaluation_path",
            "ladder_feedback_state",
        )
    }
    again = retention._retain_selected_pack_evaluation(
        fixture.adapter,
        fixture.task_id,
        bare,
        fixture.artifacts,
        None,
        regrade,
        pool_store=store,
    )
    assert again["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    assert "koth_comparison" not in again and "ladder_feedback_state" not in again
    assert store.incumbent() is None


def test_without_the_intakes_request_digest_nothing_is_admitted(tmp_path, monkeypatch):
    fixture, store = _setup(tmp_path, monkeypatch)
    second = "rtsk_" + "c" * 64
    fixture.adapter.ledger.record(
        SimpleNamespace(
            hotkey="fixture-owner",
            receipt={"sequence": 3, "digest": "f", "block": 1080},
            contract_digest=fixture.adapter.contract_digest,
        ),
        kind="OUTCOME",
        submission_id=second,
    )
    provider = fixture.adapter._provider("fixture-owner")
    provider._requests[second] = provider._requests[fixture.task_id]
    result = _run(fixture, tmp_path, store, second)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    assert result["koth_comparison"] == {
        "error": "pool_admit_request_digest_unavailable"
    }
    with pytest.raises(StateError, match="unknown_submission"):
        store.submission(second)
    assert store.incumbent() is None


# --- the real paired (v4) binding of each physical Challenge ------------------------


def _v4(case):
    """The bind inputs, registered pin and retained bytes of a real v4 evaluation."""
    prepared, measured = _produce(case)
    scoring = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    inputs = {
        "entry": case["entry"],
        "custody_receipt_raw": case["custody_raw"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "measured_model": measured.measured_model,
        "score_pack": case["score_pack"],
        "graph_originals": case["originals"],
        "expected_result_digest": evidence._sha(evidence._canonical(scoring)),
        "ordered_query_bytes": [case["case_bank"]],
        "evaluation_source_receipt_raw": prepared.raw,
        "expected_evaluation_pack_digest": case["snapshot"].manifest_digest,
        "dual_measurement_receipt_raw": measured.raw,
        "registered_dual_measurement_sha256": measured.sha256,
        "selected_evaluation_pack": case["snapshot"],
    }
    assert (
        evidence.bind_private_evaluation_evidence(
            registered_source_receipt_sha256=prepared.sha256, **inputs
        )["schema"]
        == evidence.PAIRED_SIDECAR_SCHEMA
    )
    task = case["root"].parent / "task"
    artifacts = {
        "recipe.json": (task / "recipe.json").read_bytes(),
        "state.npz": (task / "state.npz").read_bytes(),
    }
    return inputs, prepared.sha256, artifacts


def _adapter_for(case, tmp_path):
    from carbon.challenge_validator.ledger import AttemptLedger

    directory = tmp_path / "attempts"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    discovery = SimpleNamespace(
        evaluation_pack_snapshot=case["snapshot"],
        evaluation_pack_public_root=case["root"],
    )
    adapter = SimpleNamespace(
        ledger=ledger,
        contract_digest="sha256:" + "c" * 64,
        challenge_id=case["adapter"].CHALLENGE,
        discovery=discovery,
        owner=lambda _submission: "owner-hotkey",
    )
    return adapter


def test_the_real_v4_binding_of_each_physical_challenge_contends(case, tmp_path):
    inputs, pin, artifacts = _v4(case)
    adapter = _adapter_for(case, tmp_path)
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0)
    first, second = "rtsk_" + "1" * 64, "rtsk_" + "2" * 64
    for submission_id in (first, second):
        adapter.ledger.record_recipe_task_intent(
            adapter.contract_digest, submission_id, "owner-hotkey", "sha256:" + "8" * 64
        )
    one = retention._contend(adapter, store, first, artifacts, inputs, pin)
    assert one["outcome"] == "FIRST_INCUMBENT", one
    assert store.incumbent()["model_id"] == first
    # The same graded model again: with no registered noise it is unavailable, never a win.
    two = retention._contend(adapter, store, second, artifacts, inputs, pin)
    assert two["outcome"] == "UNAVAILABLE", two
    assert two["reason"] == "rebuild_noise_unregistered"
    assert store.incumbent()["model_id"] == first
