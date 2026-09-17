"""Synthetic boundary tests, never model inference or real improvement evidence."""

import json
import math
from dataclasses import replace

import pytest

from carbon.development_comparison.metrics import descriptive_metrics, report_document
from carbon.development_comparison.sources import read_json
from carbon.development_session.profile import canonical, digest


def cohorts():
    from test_cw1_burgers_session import _disclosure_cohorts

    return _disclosure_cohorts()


def changed(values, amount):
    return tuple(
        (
            role,
            tuple(
                (
                    request,
                    replace(
                        result,
                        measurements=tuple(
                            replace(
                                item,
                                normalization_scale=1.0,
                                raw_absolute_error=item.normalized_error + amount,
                                normalized_error=item.normalized_error + amount,
                            )
                            for item in result.measurements
                        ),
                    ),
                )
                for request, result in pairs
            ),
        )
        for role, pairs in values
    )


def test_metric_differences_are_descriptive_even_when_lower_or_equal():
    baseline, expected = cohorts()
    challenger = baseline
    baseline = changed(baseline, 1.0)
    result = descriptive_metrics(baseline, challenger, expected_cases=expected)
    for role in ("EVAL", "STRESS"):
        metric = result[role]["metrics"]["field_phase_rms"]
        assert metric["difference_challenger_minus_baseline"] == pytest.approx(-1.0)
        assert len(metric["baseline"]["replica_means"]) == 3
        assert metric["accepted_improvement"] is None
        assert metric["interval"] is None
        assert result[role]["cases"] == 12
    equal = descriptive_metrics(challenger, challenger, expected_cases=expected)
    report = report_document(
        contract_digest="fixture", baseline={}, challenger={}, metrics=equal
    )
    assert report["accepted_improvement"] is None and report["equivalence"] is None
    assert report["disposition"] == "INDETERMINATE_NO_ACCEPTANCE_RULE"
    assert not any(report["eligibility"].values())
    assert "tie" not in json.dumps(report).lower()


def test_variation_separates_replica_means_from_paired_cases():
    base, expected = cohorts()
    altered = []
    for role, pairs in base:
        cases = {case: index for index, case in enumerate(sorted(expected[role]))}
        rows = []
        for request, result in pairs:
            replica = int(request.candidate_replica_id[-1])
            offset = 10 * replica + cases[request.case_digest]
            rows.append(
                (
                    request,
                    replace(
                        result,
                        measurements=tuple(
                            replace(
                                item,
                                normalization_scale=1.0,
                                raw_absolute_error=float(offset),
                                normalized_error=float(offset),
                            )
                            for item in result.measurements
                        ),
                    ),
                )
            )
        altered.append((role, tuple(rows)))
    result = descriptive_metrics(base, tuple(altered), expected_cases=expected)
    value = result["EVAL"]["metrics"]["field_phase_rms"]
    assert value["challenger"]["replica_means"] == [5.5, 15.5, 25.5]
    assert value["challenger"]["mean"] == 15.5
    assert value["challenger"]["replica_mean_sample_sd"] == 10
    assert value["challenger"]["case_mean_sample_sd"] == pytest.approx(math.sqrt(13))


@pytest.mark.parametrize(
    "mode",
    ("missing", "duplicate", "role_swap", "wrong_case", "wrong_replica", "wrong_plan"),
)
def test_incomplete_or_incompatible_cohorts_withhold_comparison(mode):
    base, expected = cohorts()
    bad = list(base)
    pairs = list(bad[0][1])
    if mode == "missing":
        pairs.pop()
    elif mode == "duplicate":
        pairs[-1] = pairs[0]
    elif mode == "role_swap":
        pairs = list(base[1][1])
    else:
        request, result = pairs[0]
        field, value = {
            "wrong_case": ("case_digest", digest(b"unapproved")),
            "wrong_replica": ("candidate_replica_id", "reconstruction-replica-3"),
            "wrong_plan": ("candidate_plan_digest", digest(b"other-plan")),
        }[mode]
        request = replace(request, **{field: value})
        pairs[0] = request, replace(result, request_digest=request.request_digest)
    bad[0] = "EVAL", tuple(pairs)
    with pytest.raises(ValueError):
        descriptive_metrics(base, tuple(bad), expected_cases=expected)


def test_censoring_must_be_explicit_and_no_nonfinite_metrics():
    base, expected = cohorts()
    request, result = base[0][1][0]
    with pytest.raises(ValueError):
        replace(result.measurements[0], normalized_error=float("nan"))
    changed_result = replace(
        result,
        diagnostics=tuple(
            (key, value)
            for key, value in result.diagnostics
            if key != "candidate_half_time_censored"
        ),
    )
    bad = (("EVAL", ((request, changed_result),) + base[0][1][1:]), base[1])
    with pytest.raises(ValueError, match="censor"):
        descriptive_metrics(base, bad, expected_cases=expected)


def test_comparison_artifacts_are_bounded_and_replay_is_immutable(tmp_path):
    from carbon.development_session.data import write_once

    path = tmp_path / "report.json"
    write_once(path, canonical({"fixture": True}))
    write_once(path, canonical({"fixture": True}))
    with pytest.raises(ValueError, match="conflict"):
        write_once(path, canonical({"fixture": False}))
    assert read_json(path) == {"fixture": True}
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="duplicate"):
        read_json(path)
    with pytest.raises(ValueError, match="bounded"):
        read_json(path, maximum=1)


@pytest.mark.parametrize("changed_bytes", (False, True))
def test_quarantine_query_covers_primary_and_reexecution_sources(
    tmp_path, changed_bytes
):
    from c10_fixtures import make_fixture
    from test_c10_independent_reexecution import _complete_pair, _service

    from carbon.reexecution.store import ReexecutionJournal

    fixture = make_fixture(tmp_path, output_suffix="different" if changed_bytes else "")
    journal, service = _service(fixture)
    reexecution, _ = _complete_pair(fixture, service)
    for result in (fixture.primary_result, reexecution):
        states = ReexecutionJournal.source_states(
            journal.path,
            account_digest=result.account.account_digest,
            receipt_digest=result.account.receipt_digest,
        )
        assert states == ("QUARANTINED" if changed_bytes else "COMPARED",)


def test_quarantine_read_does_not_restart_worker_and_detects_tampering(tmp_path):
    from c10_fixtures import make_fixture
    from test_c10_independent_reexecution import _service

    from carbon.reexecution.model import JournalState, ReexecutionFailure
    from carbon.reexecution.store import ReexecutionJournal

    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.launch(fixture.launch_intent)
    args = {
        "account_digest": fixture.primary_result.account.account_digest,
        "receipt_digest": fixture.primary_result.account.receipt_digest,
    }
    assert ReexecutionJournal.source_states(journal.path, **args) == ("RUNNING",)
    assert journal.status(fixture.launch_intent).state is JournalState.RUNNING
    with journal._transaction() as db:
        db.execute("UPDATE c10_event_v1 SET body='{}' WHERE sequence=1")
    with pytest.raises(ReexecutionFailure):
        ReexecutionJournal.source_states(journal.path, **args)
    with pytest.raises(ReexecutionFailure):
        ReexecutionJournal.source_states(tmp_path / "absent.sqlite3", **args)


def test_new_authority_cannot_reuse_legacy_budget_or_other_contract(tmp_path):
    from carbon.development_session.agent import check_authority, proposal

    old = proposal()
    plan = proposal(comparison_contract_digest=digest(b"fixture contract"))
    assert (plan["max_calls"], plan["max_proposals"], plan["max_total_usd"]) == (
        24,
        2,
        1.0,
    )
    assert old["max_calls"] == 12 and old["max_total_usd"] == 0.25
    path = tmp_path / "authority.json"
    authority = {
        "schema": "carbon.burgers-session.model-run-authority.v1",
        "proposal_digest": digest(canonical(plan)),
        "approved": True,
        "valid_from_unix": 0,
        "valid_until_unix": 200,
        "max_total_usd": 1.0,
    }
    path.write_bytes(canonical(authority))
    check_authority(path, now=100, run_proposal=plan)
    with pytest.raises(ValueError, match="bind"):
        check_authority(path, now=100)
    with pytest.raises(ValueError, match="expired"):
        check_authority(path, now=201, run_proposal=plan)


def test_two_invalid_proposals_and_ambiguous_provider_calls_consume_caps(tmp_path):
    from carbon.development_session.agent import MAX_CALL_USD
    from carbon.development_session.budget import SessionBudget

    budget = SessionBudget(tmp_path / "budget.sqlite3")
    for index in range(2):
        budget.reserve(f"invalid-{index}", "proposal", 1, 2, 2)
        budget.finish(f"invalid-{index}", 1, "FAILED")
    with pytest.raises(ValueError, match="exhausted"):
        budget.reserve("third", "proposal", 1, 2, 2)
    for index in range(24):
        budget.reserve(f"call-{index}", "provider_usd", MAX_CALL_USD, 1.0, 24)
    with pytest.raises(ValueError, match="exhausted"):
        budget.reserve("call-25", "provider_usd", MAX_CALL_USD, 1.0, 24)
    with pytest.raises(ValueError, match="reconcile"):
        budget.reserve("call-0", "provider_usd", MAX_CALL_USD, 1.0, 24)


def test_synthetic_reward_interface_reuses_takeover_self_improvement_and_decay():
    from carbon.development_comparison.report import ComparisonRef
    from carbon.development_comparison.reward import (
        SyntheticAcceptedComparison,
        simulate_synthetic,
    )
    from carbon.rewards.core import (
        DAY_MS,
        Q12,
        DevelopmentTerms,
        Holder,
        Record,
        fraction,
    )

    terms = DevelopmentTerms(
        "a" * 64, "b" * 64, (0.2).hex(), "1", 0, 10 * DAY_MS, 20 * DAY_MS, ((0, Q12),)
    )
    a, b = (
        Holder("fixture-a", "fixture-owner-a", 0),
        Holder("fixture-b", "fixture-owner-b", 0),
    )
    items = tuple(
        SyntheticAcceptedComparison(
            Record(str(index) * 64, str(index + 3) * 64, score.hex(), holder, index),
            index * DAY_MS,
        )
        for index, score, holder in ((1, 0.4, a), (2, 0.5, a), (3, 0.6, b))
    )
    states = simulate_synthetic(terms, items)
    assert states[0].holder is None and fraction(states[0], 0) == 0
    assert states[1].holder == states[2].holder == a and states[3].holder == b
    assert fraction(states[3], 4 * DAY_MS) == fraction(states[3], 3 * DAY_MS) // 2
    with pytest.raises(ValueError, match="synthetic"):
        simulate_synthetic(terms, (ComparisonRef(None, "real-report"),))


@pytest.mark.parametrize("state_name", ("SUPERSEDED", "REVOKED"))
def test_lifecycle_withholds_source_even_when_measurements_exist(tmp_path, state_name):
    from types import SimpleNamespace

    from c10_fixtures import make_fixture

    from carbon.audit import ReceiptLifecycleState
    from carbon.development_comparison.sources import validate_active_association

    result = make_fixture(tmp_path).primary_result
    receipt = result.signed_receipt.receipt
    auth = SimpleNamespace(
        challenge_id=receipt.binding.challenge_id,
        challenge_version=receipt.binding.challenge_version,
    )
    validate_active_association(
        receipt, result.account, auth, ReceiptLifecycleState.ACTIVE
    )
    with pytest.raises(ValueError, match="active complete"):
        validate_active_association(
            receipt, result.account, auth, ReceiptLifecycleState(state_name)
        )
    auth.challenge_version = "another-version"
    with pytest.raises(ValueError, match="active complete"):
        validate_active_association(
            receipt, result.account, auth, ReceiptLifecycleState.ACTIVE
        )


def test_changed_receipt_association_cannot_enter_comparison(tmp_path):
    from types import SimpleNamespace

    from c10_fixtures import make_fixture

    from carbon.audit import ReceiptLifecycleState
    from carbon.development_comparison.sources import validate_active_association

    result = make_fixture(tmp_path).primary_result
    receipt = result.signed_receipt.receipt
    auth = SimpleNamespace(
        challenge_id=receipt.binding.challenge_id,
        challenge_version=receipt.binding.challenge_version,
    )
    other_account = replace(result.account, receipt_digest=digest(b"other receipt"))
    with pytest.raises(ValueError, match="active complete"):
        validate_active_association(
            receipt, other_account, auth, ReceiptLifecycleState.ACTIVE
        )


def test_descriptive_report_cannot_be_all_burn_source_or_scalar_score():
    from carbon.development_testnet.model import DevelopmentTestnetFailure
    from carbon.development_testnet.service import DevelopmentTestnetIntentIssuer

    value = report_document(
        contract_digest="fixture", baseline={}, challenger={}, metrics={}
    )
    with pytest.raises(
        DevelopmentTestnetFailure, match="DEVELOPMENT_EVIDENCE_REQUIRED"
    ):
        DevelopmentTestnetIntentIssuer._validate_source(None, value)
    assert value["score"] is None and value["accepted_improvement"] is None


def test_owner_report_ignores_contract_and_replays_without_new_accounting(
    tmp_path, monkeypatch
):
    from carbon.development_comparison import owner
    from carbon.development_session.data import write_once

    contract = {"baseline_strategy": {"fixture": True}}
    monkeypatch.setattr(owner, "load_contract", lambda _: contract)
    write_once(tmp_path / "comparison-contract.json", canonical(contract))
    with pytest.raises(ValueError, match="outcome required"):
        owner.write_owner_report(tmp_path)
    write_once(
        tmp_path / "agent-stopped-report.json", canonical({"status": "synthetic-stop"})
    )
    first = owner.write_owner_report(tmp_path)
    assert first["status"] == "STOPPED_OR_INCOMPLETE"
    assert first["totals"]["provider_calls_including_failures"] == 0
    assert owner.write_owner_report(tmp_path) == first


def test_c04_and_c05_reference_domains_bind_same_bytes_without_relabeling():
    from test_c05_burgers_measurement import _inputs

    from carbon.development_comparison.sources import validate_reference_association
    from carbon.reference_runtime.model import BurgersReferenceArtifact

    _, request, _, reference = _inputs()
    c04 = BurgersReferenceArtifact(
        request.reference_request_digest, request.shape, reference.payload
    )
    assert c04.artifact_digest != request.reference_artifact_digest
    validate_reference_association(request, c04.artifact_digest, reference.payload)
    with pytest.raises(ValueError, match="reference artifact"):
        validate_reference_association(
            request, request.reference_artifact_digest, reference.payload
        )
    with pytest.raises(ValueError):
        validate_reference_association(
            request, c04.artifact_digest, b"\0" * len(reference.payload)
        )


def test_report_readback_compares_canonical_bytes_not_tuple_list_representation(
    tmp_path, monkeypatch
):
    from carbon.development_comparison import report

    value = {
        "challenger_source": str(tmp_path / "source.json"),
        "binding": {"replicas": ("one", "two", "three")},
        "accepted_improvement": None,
    }
    path = tmp_path / "comparison-fixture.json"
    path.write_bytes(canonical(value))
    monkeypatch.setattr(report, "compute", lambda *_: value)
    ref = report.ComparisonRef(path, digest(path.read_bytes()))
    assert report.resolve_report(tmp_path, ref)["binding"]["replicas"] == [
        "one",
        "two",
        "three",
    ]
    tampered = json.loads(path.read_bytes())
    tampered["accepted_improvement"] = True
    path.write_bytes(canonical(tampered))
    with pytest.raises(ValueError, match="altered"):
        report.resolve_report(
            tmp_path, report.ComparisonRef(path, digest(path.read_bytes()))
        )


def test_adaptation_requires_received_feedback_before_new_strategy(tmp_path):
    from carbon.development_comparison.owner import accounting

    def response(number, tool, fields):
        (tmp_path / f"provider-{number}-response.json").write_bytes(
            canonical(
                {
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                    "output": [
                        {
                            "type": "function_call",
                            "name": tool,
                            "arguments": json.dumps(fields),
                        }
                    ],
                }
            )
        )

    response(2, "dry_validate", {"strategy": {"fixture": 1}})
    response(9, "get_submission_result", {"submission_id": "fixture"})
    response(10, "dry_validate", {"strategy": {"fixture": 2}})
    assert not accounting(tmp_path)["revised_after_new_feedback"]
    (tmp_path / "provider-9-tool-result.json").write_bytes(
        canonical(
            {"feedback": {"schema": "carbon.c07.development-aggregate-feedback.v1"}}
        )
    )
    result = accounting(tmp_path)
    assert result["tool_sequence"] == [
        "dry_validate",
        "get_submission_result",
        "dry_validate",
    ]
    assert result["read_completed_feedback"] and result["revised_after_new_feedback"]
