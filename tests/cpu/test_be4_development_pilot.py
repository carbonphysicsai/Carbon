"""Runnable B-E4 development-pilot integration and fail-closed boundaries."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

import pytest

from carbon.gauntlet import (
    AgentProfile,
    DeterministicOfflineTransport,
    DevelopmentApprovalUnavailable,
    DevelopmentJournal,
    DevelopmentPilotError,
    DevelopmentPilotRunner,
    ExperimentalArm,
    OpenAIResponsesTransport,
    PilotContractError,
    ProviderAmbiguousTimeout,
    ProviderCall,
    ProviderCallKind,
    ProviderConversationTurn,
    ProviderDispatcher,
    ProviderOutcomeKind,
    ProviderResult,
    ProviderUsage,
    UnresolvedOperationError,
    build_offline_provider_payload,
)
from scripts.dev import run_be4_development_pilot as pilot


def _payload() -> dict[str, object]:
    return build_offline_provider_payload(
        {
            "frozen_system_and_profile_policy": {
                "policy_id": "fixture-policy",
                "profile": "PLANNER",
                "system_policy": "return typed fixture data only",
            },
            "agent_visible_synthetic_task_description": {"target_family": "Y_EQUALS_X"},
            "current_arm_permitted_prior_material": {
                "arm": "NO_PRIOR",
                "material": None,
            },
            "current_run_permitted_practice_feedback": [],
            "public_resource_facts": {
                "scaffold_strategy": {
                    "schema_version": "1.0",
                    "challenge_id": "fixture_authoring",
                    "backbone": "fno",
                    "parameters": {
                        "fixture_sampling_level": 1,
                        "fixture_curriculum_emphasis": 1,
                        "fixture_feature_degree": 1,
                    },
                }
            },
            "current_run_existing_candidate_ids": [],
        }
    )


def _call(
    *,
    operation_id: str = "run:proposal:01:try-1",
    history: tuple[ProviderConversationTurn, ...] = (),
) -> ProviderCall:
    return ProviderCall(
        operation_id,
        "run",
        0,
        ProviderCallKind.PROPOSAL,
        AgentProfile.PLANNER,
        ExperimentalArm.NO_PRIOR,
        _payload(),
        history,
        30.0,
        1_536,
    )


def _single_slot_runner(
    tmp_path: Path,
    *,
    faults: dict[str, str] | None = None,
) -> tuple[DevelopmentPilotRunner, object, object, DevelopmentJournal, object]:
    tasks, factory, manifest = pilot._build(tmp_path / "fixture")
    journal = DevelopmentJournal(
        tmp_path / "journal.sqlite", manifest_digest=manifest.content_digest
    )
    transport = DeterministicOfflineTransport(faults)
    runner = DevelopmentPilotRunner(
        manifest=manifest,
        tasks={item.task_id: item for item in tasks},
        journal=journal,
        transport=transport,
        service_factory=factory,
    )
    slot = manifest.schedule[0]
    task = next(item for item in tasks if item.task_id == slot.task_id)
    return runner, slot, task, journal, transport


def test_responses_request_is_strict_history_accounted_and_tool_free() -> None:
    transport = DeterministicOfflineTransport()
    first = _call()
    result = transport.dispatch(first)
    turn = ProviderConversationTurn(
        first.run_id,
        first.profile,
        first.arm,
        first.kind,
        first.payload,
        result,
    )
    second = _call(operation_id="run:proposal:02:try-1", history=(turn,))
    body = second.responses_body()

    assert body["model"] == "gpt-5.6-terra"
    assert body["store"] is False
    assert body["background"] is False
    assert body["tools"] == []
    assert body["tool_choice"] == "none"
    assert body["parallel_tool_calls"] is False
    assert body["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert body["reasoning"] == {"effort": "medium"}
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["type"] == "json_schema"
    assert [item["role"] for item in body["input"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second.input_token_upper_bound > first.input_token_upper_bound
    assert "credential" not in json.dumps(body).lower()

    crossed_payload = json.loads(json.dumps(first.payload))
    crossed_payload["current_arm_permitted_prior_material"]["arm"] = "GENERIC_PRIOR"
    crossed = ProviderConversationTurn(
        first.run_id,
        first.profile,
        ExperimentalArm.GENERIC_PRIOR,
        first.kind,
        crossed_payload,
        result,
    )
    with pytest.raises(ValueError, match="run or arm"):
        _call(history=(crossed,))


def test_real_transport_fails_before_network_or_credentials_are_needed() -> None:
    called = False

    def opener(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        raise AssertionError("network must remain unreachable")

    transport = OpenAIResponsesTransport(
        api_key="fixture-key-that-must-stay-redacted",
        project_id="fixture-project-that-must-stay-redacted",
        organization_id="fixture-organization-that-must-stay-redacted",
        opener=opener,
    )
    assert "credential-redacted" in repr(transport)
    assert "fixture" not in repr(transport)
    with pytest.raises(DevelopmentApprovalUnavailable, match="BLOCKED"):
        transport.dispatch(_call())
    assert called is False


@pytest.mark.parametrize("bad_value", [True, "7", 7.0, -1])
def test_provider_usage_requires_exact_nonnegative_integers(
    bad_value: object,
) -> None:
    payload = {
        "id": "resp_fixture",
        "model": "gpt-5.6-terra",
        "service_tier": "default",
        "usage": {
            "input_tokens": bad_value,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 1},
        },
    }
    with pytest.raises(ProviderAmbiguousTimeout, match="usage"):
        OpenAIResponsesTransport._parse(_call(), payload, "{}", "2026-09-09T00:00:00Z")


def test_provider_call_rejects_registered_context_overrun() -> None:
    payload = _payload()
    facts = payload["public_resource_facts"]
    assert isinstance(facts, dict)
    facts["oversized_public_text"] = "x" * 32_768
    with pytest.raises(ValueError, match="context ceiling"):
        ProviderCall(
            "run:proposal:oversized",
            "run",
            0,
            ProviderCallKind.PROPOSAL,
            AgentProfile.PLANNER,
            ExperimentalArm.NO_PRIOR,
            payload,
            (),
            30.0,
            1_536,
        )


def test_execution_request_is_content_bound_and_cannot_claim_execution(
    tmp_path: Path,
) -> None:
    _tasks, factory, manifest = pilot._build(tmp_path / "fixture")
    request = pilot.validate_execution_request(
        pilot.execution_request(manifest, factory.artifact_manifest)
    )
    assert request["manifest"]["content_digest"] == manifest.content_digest
    assert request["paid_execution_occurred"] is False

    request["paid_execution_occurred"] = True
    digest_source = dict(request)
    digest_source.pop("content_digest")
    request["content_digest"] = pilot._domain_digest(
        pilot._EXECUTION_REQUEST_DOMAIN, digest_source
    )
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_execution_request(request)


def test_journal_replays_completion_and_retains_ambiguous_reservation(
    tmp_path: Path,
) -> None:
    digest = "sha256:" + "a" * 64
    call = _call()
    transport = DeterministicOfflineTransport()
    with DevelopmentJournal(
        tmp_path / "complete.sqlite", manifest_digest=digest
    ) as journal:
        dispatcher = ProviderDispatcher(journal=journal, transport=transport)
        first = dispatcher.dispatch(call)
        replay = dispatcher.dispatch(call)
        assert replay == first
        assert transport.dispatched_operation_ids == (call.operation_id,)
        retained = journal._connection.execute(
            "SELECT call_json, result_json FROM operation WHERE operation_id = ?",
            (call.operation_id,),
        ).fetchone()
        assert retained is not None
        assert json.loads(retained[0])["body"] == call.responses_body()
        assert json.loads(retained[1])["raw_response_text"] == first.raw_response_text

    ambiguous = DeterministicOfflineTransport({call.operation_id: "AMBIGUOUS_TIMEOUT"})
    journal = DevelopmentJournal(tmp_path / "unknown.sqlite", manifest_digest=digest)
    dispatcher = ProviderDispatcher(journal=journal, transport=ambiguous)
    with pytest.raises(ProviderAmbiguousTimeout):
        dispatcher.dispatch(call)
    snapshot = journal.cost_snapshot()
    assert snapshot.reserved_input_tokens == call.input_token_upper_bound
    assert snapshot.reserved_output_tokens == call.max_output_tokens
    assert snapshot.reserved_cost_usd > 0
    journal.close()

    with DevelopmentJournal(
        tmp_path / "unknown.sqlite", manifest_digest=digest
    ) as reopened:
        assert reopened.has_unresolved_operations() is True
        with pytest.raises(UnresolvedOperationError):
            ProviderDispatcher(journal=reopened, transport=ambiguous).dispatch(call)
    assert ambiguous.dispatched_operation_ids == (call.operation_id,)


def test_post_dispatch_provider_overrun_is_retained_and_stops(tmp_path: Path) -> None:
    call = _call()

    class OverrunTransport:
        calls = 0

        def dispatch(self, dispatched: ProviderCall) -> ProviderResult:
            self.calls += 1
            raw = "{}"
            return ProviderResult(
                ProviderOutcomeKind.MALFORMED,
                "resp-overrun",
                "gpt-5.6-terra",
                "gpt-5.6-terra",
                "default",
                "default",
                "2026-09-09T00:00:00Z",
                "2026-09-09T00:00:01Z",
                ProviderUsage(
                    65_537,
                    0,
                    0,
                    1,
                    0,
                ),
                None,
                "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                raw,
                {},
            )

    with DevelopmentJournal(
        tmp_path / "overrun.sqlite", manifest_digest="sha256:" + "c" * 64
    ) as journal:
        transport = OverrunTransport()
        dispatcher = ProviderDispatcher(journal=journal, transport=transport)
        with pytest.raises(DevelopmentPilotError, match="per-operation reservation"):
            dispatcher.dispatch(call)
        snapshot = journal.cost_snapshot(run_id=call.run_id)
        assert snapshot.confirmed_input_tokens == 65_537
        assert snapshot.reserved_input_tokens == 0
        next_call = _call(operation_id="run:proposal:02:try-1")
        with pytest.raises(DevelopmentPilotError, match="cannot fit"):
            dispatcher.dispatch(next_call)
        assert transport.calls == 1


def test_incomplete_local_run_is_not_blindly_replayed(tmp_path: Path) -> None:
    path = tmp_path / "run.sqlite"
    digest = "sha256:" + "b" * 64
    with DevelopmentJournal(path, manifest_digest=digest) as journal:
        journal.begin_run("run-1")
    with (
        DevelopmentJournal(path, manifest_digest=digest) as journal,
        pytest.raises(UnresolvedOperationError, match="incomplete durable state"),
    ):
        journal.begin_run("run-1")


def test_restart_preserves_stage_and_run_deadline_origins(tmp_path: Path) -> None:
    tasks, factory, manifest = pilot._build(tmp_path / "fixture")
    path = tmp_path / "deadline.sqlite"
    with DevelopmentJournal(path, manifest_digest=manifest.content_digest) as journal:
        journal.begin_run(manifest.schedule[0].run_id)

    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE campaign SET started_at_unix = ? WHERE singleton = 1",
        (time.time() - 57_601.0,),
    )
    connection.execute(
        "UPDATE run_state SET started_at_unix = ? WHERE run_id = ?",
        (time.time() - 901.0, manifest.schedule[0].run_id),
    )
    connection.commit()
    connection.close()

    with DevelopmentJournal(path, manifest_digest=manifest.content_digest) as journal:
        runner = DevelopmentPilotRunner(
            manifest=manifest,
            tasks={item.task_id: item for item in tasks},
            journal=journal,
            transport=DeterministicOfflineTransport(),
            service_factory=factory,
        )
        assert runner._stage_elapsed() >= 57_600.0
        with pytest.raises(PilotContractError, match="remaining deadlines"):
            runner._deadline(manifest.schedule[0].run_id, time.monotonic_ns())


def test_verified_failure_gets_one_retry_and_explicit_stop_is_terminal(
    tmp_path: Path,
) -> None:
    first_operation = (
        "be4-development-planner-be4-pilot-v2-04-no_prior:" "proposal:01:try-1"
    )
    runner, slot, task, journal, transport = _single_slot_runner(
        tmp_path / "retry", faults={first_operation: "VERIFIED_FAILURE"}
    )
    value = runner._run_slot(slot, task)
    assert value["status"] == "COMPLETED"
    assert value["interaction"]["provider_requests"] == 6
    assert transport.dispatched_operation_ids[:2] == (
        first_operation,
        first_operation.removesuffix("try-1") + "try-2",
    )
    journal.close()

    runner, slot, task, journal, _transport = _single_slot_runner(
        tmp_path / "stop", faults={first_operation: "EXPLICIT_STOP"}
    )
    value = runner._run_slot(slot, task)
    assert value["status"] == "STOPPED"
    assert value["interaction"]["termination_reason"] == "EXPLICIT_AGENT_STOP"
    assert value["interaction"]["proposal_attempts"] == 0
    assert value["interaction"]["provider_requests"] == 1
    assert value["practice_evidence"] == []
    journal.close()


def test_ambiguous_timeout_stops_without_resend(tmp_path: Path) -> None:
    operation = "be4-development-planner-be4-pilot-v2-04-no_prior:" "proposal:01:try-1"
    runner, slot, task, journal, transport = _single_slot_runner(
        tmp_path, faults={operation: "AMBIGUOUS_TIMEOUT"}
    )
    with pytest.raises(ProviderAmbiguousTimeout):
        runner._run_slot(slot, task)
    assert transport.dispatched_operation_ids == (operation,)
    assert journal.has_unresolved_operations() is True
    assert journal.cost_snapshot(run_id=slot.run_id).reserved_cost_usd > 0
    journal.close()


def test_invalid_refusal_truncation_and_malformed_calls_are_not_free(
    tmp_path: Path,
) -> None:
    prefix = "be4-development-planner-be4-pilot-v2-04-no_prior:proposal:"
    runner, slot, task, journal, _transport = _single_slot_runner(
        tmp_path,
        faults={
            prefix + "01:try-1": "REFUSAL",
            prefix + "02:try-1": "MALFORMED",
            prefix + "03:try-1": "TRUNCATED",
            prefix + "04:try-1": "INVALID_STRATEGY",
        },
    )
    value = runner._run_slot(slot, task)
    assert value["status"] == "STOPPED"
    assert value["interaction"]["proposal_attempts"] == 4
    assert value["interaction"]["provider_requests"] == 5
    assert value["interaction"]["termination_reason"] == "FINAL_STOP"
    assert [item["outcome"] for item in value["provider_results"]] == [
        ProviderOutcomeKind.REFUSAL.value,
        ProviderOutcomeKind.MALFORMED.value,
        ProviderOutcomeKind.TRUNCATED.value,
        ProviderOutcomeKind.STRUCTURED.value,
        ProviderOutcomeKind.STRUCTURED.value,
    ]
    assert value["practice_evidence"] == []
    assert len(value["candidate_records"]) == 1
    assert value["candidate_records"][0]["attempt"] == 4
    assert value["candidate_records"][0]["executable"] is False
    journal.close()


def test_full_40_slot_offline_matrix_uses_actual_carbon_fixture_services(
    tmp_path: Path,
) -> None:
    report = pilot.run_offline(
        journal_path=tmp_path / "development.sqlite",
        report_path=tmp_path / "report.json",
    )
    resumed = pilot.run_offline(
        journal_path=tmp_path / "development.sqlite",
        report_path=None,
    )
    assert resumed == report
    rows = report["run_results"]
    assert report["completed_run_count"] == 40
    assert report["remaining_run_count"] == 0
    assert report["model_inference_executed"] is False
    assert report["paid_execution_occurred"] is False
    assert report["qualifying_execution_ready"] is False
    assert {item["profile"] for item in rows} == {item.value for item in AgentProfile}
    assert {item["arm"] for item in rows} == {item.value for item in ExperimentalArm}
    assert {item["task_id"] for item in rows} == {
        "be4-pilot-v2-04",
        "be4-pilot-v2-07",
    }
    assert [item["run_ordinal"] for item in rows] == list(range(40))

    adaptive = [item for item in rows if item["profile"] != "MINIMALIST"]
    minimalist = [item for item in rows if item["profile"] == "MINIMALIST"]
    assert len(adaptive) == 32 and len(minimalist) == 8
    assert all(len(item["provider_results"]) == 5 for item in adaptive)
    assert all(len(item["practice_evidence"]) == 3 for item in adaptive)
    assert all(
        item["interaction"]["termination_reason"] == "FINAL_SELECTION"
        for item in adaptive
    )
    assert all(
        item["resource_observation"]["confirmed_fixture_units"] == 119.0
        for item in adaptive
    )
    assert all(len(item["provider_results"]) == 1 for item in minimalist)
    assert all(len(item["practice_evidence"]) == 1 for item in minimalist)
    assert all(
        item["interaction"]["termination_reason"] == "MINIMALIST_ONE_ATTEMPT_COMPLETE"
        for item in minimalist
    )
    assert all(
        item["resource_observation"]["confirmed_fixture_units"] == 51.0
        for item in minimalist
    )
    assert all(item["official_endpoint"] is not None for item in rows)
    assert all(item["public_result"]["fixture_origin"] is True for item in rows)

    connection = sqlite3.connect(tmp_path / "development.sqlite")
    selection = connection.execute(
        "SELECT call_json FROM operation WHERE operation_id LIKE '%selection%' "
        "ORDER BY operation_id LIMIT 1"
    ).fetchone()
    assert selection is not None
    body = json.loads(selection[0])["body"]
    assert len(body["input"]) == 10
    assert body["tools"] == [] and body["store"] is False
    all_calls = "".join(
        item[0] for item in connection.execute("SELECT call_json FROM operation")
    )
    connection.close()
    for forbidden in (
        "evaluator_seed",
        "hidden_case",
        "private_reference",
        "shadow_data",
        "scorer_internal",
        "credential",
        "other_arm_transcript",
        "other_run_transcript",
    ):
        assert forbidden not in all_calls.lower()


def test_execution_request_is_content_bound_but_not_authority(tmp_path: Path) -> None:
    _tasks, factory, manifest = pilot._build(tmp_path / "request")
    request = pilot.validate_execution_request(
        pilot.execution_request(manifest, factory.artifact_manifest)
    )
    assert request["paid_execution_occurred"] is False
    assert request["qualifying_execution_ready"] is False
    assert request["manifest"]["approval_boundary"] == {
        "actual_execution_evidence": False,
        "authenticated_five_owner_approval": False,
        "one_use_execution_authorization": False,
        "paid_provider_execution": False,
    }

    mutated = json.loads(json.dumps(request))
    mutated["paid_execution_occurred"] = True
    digest_source = dict(mutated)
    digest_source.pop("content_digest")
    mutated["content_digest"] = pilot._domain_digest(
        pilot._EXECUTION_REQUEST_DOMAIN, digest_source
    )
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_execution_request(mutated)

    artifact_mutation = json.loads(json.dumps(request))
    artifact_mutation["artifact_identities"]["tasks"][0]["evaluator_seed_egress"] = True
    artifact_mutation["manifest"]["artifact_manifest_digest"] = pilot._domain_digest(
        pilot._ARTIFACT_MANIFEST_DOMAIN, artifact_mutation["artifact_identities"]
    )
    manifest_source = dict(artifact_mutation["manifest"])
    manifest_source.pop("content_digest")
    artifact_mutation["manifest"]["content_digest"] = pilot._domain_digest(
        b"carbon.be4.development-manifest.v1\x00", manifest_source
    )
    outer = dict(artifact_mutation)
    outer.pop("content_digest")
    artifact_mutation["content_digest"] = pilot._domain_digest(
        pilot._EXECUTION_REQUEST_DOMAIN, outer
    )
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_execution_request(artifact_mutation)
