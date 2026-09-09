"""Authenticated B-E4 DEVELOPMENT admission and controlled HTTP coverage."""

from __future__ import annotations

import json
import subprocess
import threading
from copy import deepcopy
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from carbon.gauntlet import (
    CARBON_OWNER_GITHUB_LOGIN,
    CARBON_OWNER_GITHUB_USER_ID,
    DEVELOPMENT_APPROVER_GITHUB_LOGIN,
    DEVELOPMENT_APPROVER_GITHUB_USER_ID,
    AgentProfile,
    ControlledDevelopmentAuthorizationStore,
    ControlledOpenAIResponsesTransport,
    DevelopmentApprovalUnavailable,
    DevelopmentAuthenticationError,
    DevelopmentAuthorizationError,
    DevelopmentAuthorizationStore,
    DevelopmentJournal,
    ExperimentalArm,
    GitHubCliCarbonOwnerAuthenticator,
    GitHubCliDevelopmentApproverAuthenticator,
    OpenAIResponsesTransport,
    ProviderAmbiguousTimeout,
    ProviderCall,
    ProviderCallKind,
    ProviderDispatcher,
    ProviderOutcomeKind,
    build_offline_provider_payload,
)
from carbon.gauntlet.agents import REGISTERED_EFFECTFUL_SURFACES
from scripts.dev import run_be4_development_pilot as pilot


def _current_request(tmp_path: Path) -> dict[str, object]:
    _tasks, _factory, _manifest, request = pilot._current_request_from_source(tmp_path)
    return request


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


def _provider_call() -> ProviderCall:
    return ProviderCall(
        "controlled-run:proposal:01:try-1",
        "controlled-run",
        0,
        ProviderCallKind.PROPOSAL,
        AgentProfile.PLANNER,
        ExperimentalArm.NO_PRIOR,
        _payload(),
        (),
        30.0,
        1_536,
    )


def _controlled_admission(
    tmp_path: Path,
    *,
    journal_binding: str = "sha256:" + "f" * 64,
    project_id: str = "fixture-project",
):
    request = _current_request(tmp_path / "request")
    bindings = pilot.authorization_bindings(
        request,
        journal_binding=journal_binding,
        project_id=project_id,
        organization_id=None,
    )
    store = ControlledDevelopmentAuthorizationStore(tmp_path / "authority.sqlite")
    authorization_id = store.issue_fixture(bindings)
    admission = store.claim_fixture(
        authorization_id,
        bindings=bindings,
        journal_binding=journal_binding,
    )
    return request, bindings, store, admission


def test_authenticated_github_viewer_requires_exact_development_approver_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def result(login: str, user_id: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["gh", "api", "/user"],
            0,
            json.dumps({"id": user_id, "login": login, "type": "User"}),
            "",
        )

    monkeypatch.setattr(
        "carbon.gauntlet.development_authority.subprocess.run",
        lambda *args, **kwargs: result(
            "arbitrary-login", DEVELOPMENT_APPROVER_GITHUB_USER_ID
        ),
    )
    with pytest.raises(DevelopmentAuthenticationError, match="not fitz-lang6"):
        GitHubCliDevelopmentApproverAuthenticator().authenticate()

    monkeypatch.setattr(
        "carbon.gauntlet.development_authority.subprocess.run",
        lambda *args, **kwargs: result(
            DEVELOPMENT_APPROVER_GITHUB_LOGIN, CARBON_OWNER_GITHUB_USER_ID
        ),
    )
    with pytest.raises(DevelopmentAuthenticationError, match="not fitz-lang6"):
        GitHubCliDevelopmentApproverAuthenticator().authenticate()

    monkeypatch.setattr(
        "carbon.gauntlet.development_authority.subprocess.run",
        lambda *args, **kwargs: result(
            CARBON_OWNER_GITHUB_LOGIN, CARBON_OWNER_GITHUB_USER_ID
        ),
    )
    with pytest.raises(DevelopmentAuthenticationError, match="not fitz-lang6"):
        GitHubCliDevelopmentApproverAuthenticator().authenticate()

    monkeypatch.setattr(
        "carbon.gauntlet.development_authority.subprocess.run",
        lambda *args, **kwargs: result(
            DEVELOPMENT_APPROVER_GITHUB_LOGIN, DEVELOPMENT_APPROVER_GITHUB_USER_ID
        ),
    )
    principal = GitHubCliDevelopmentApproverAuthenticator().authenticate()
    assert principal.login == DEVELOPMENT_APPROVER_GITHUB_LOGIN
    assert principal.user_id == DEVELOPMENT_APPROVER_GITHUB_USER_ID
    assert (
        GitHubCliCarbonOwnerAuthenticator is GitHubCliDevelopmentApproverAuthenticator
    )
    assert (CARBON_OWNER_GITHUB_LOGIN, CARBON_OWNER_GITHUB_USER_ID) == (
        "jbequ5",
        99_085_788,
    )


def test_live_issuer_rejects_nonmatching_explicit_approval_before_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _current_request(tmp_path / "request")
    bindings = pilot.authorization_bindings(
        request,
        journal_binding="sha256:" + "e" * 64,
        project_id="fixture-project",
        organization_id=None,
    )
    called = False

    def authenticate(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        raise AssertionError("authentication must follow exact-digest validation")

    monkeypatch.setattr(
        GitHubCliDevelopmentApproverAuthenticator, "authenticate", authenticate
    )
    with (
        DevelopmentAuthorizationStore(tmp_path / "live.sqlite") as store,
        pytest.raises(DevelopmentAuthorizationError, match="does not match"),
    ):
        store.issue(
            bindings,
            approve_exact_request_digest="sha256:" + "0" * 64,
        )
    assert called is False


def test_live_runtime_must_match_the_frozen_canonical_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pilot.platform, "python_version", lambda: "3.11.15")
    with pytest.raises(pilot.DevelopmentFixtureError, match="canonical Python"):
        pilot._verify_canonical_runtime()


def test_responses_cli_fails_before_dispatch_without_external_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_PROJECT_ID", raising=False)
    called = False

    def dispatch(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        raise AssertionError("provider dispatch must remain unavailable")

    monkeypatch.setattr(OpenAIResponsesTransport, "dispatch", dispatch)
    assert pilot.main(["--responses"]) == 2
    assert "PAID_EXECUTION_BLOCKED" in capsys.readouterr().out
    assert called is False


def test_controlled_authorization_is_one_claim_across_restart_and_fails_closed(
    tmp_path: Path,
) -> None:
    request = _current_request(tmp_path / "request")
    journal_binding = "sha256:" + "d" * 64
    bindings = pilot.authorization_bindings(
        request,
        journal_binding=journal_binding,
        project_id="fixture-project",
        organization_id=None,
    )
    path = tmp_path / "authority.sqlite"
    with ControlledDevelopmentAuthorizationStore(path) as store:
        authorization_id = store.issue_fixture(bindings)
        assert store.issue_fixture(bindings) == authorization_id
        admission = store.claim_fixture(
            authorization_id,
            bindings=bindings,
            journal_binding=journal_binding,
        )
        admission.assert_current(
            project_id_digest=bindings.project_id_digest,
            organization_id_digest=None,
        )
        public = store.public_record(authorization_id)
        assert public["project_id_digest"] == bindings.project_id_digest
        assert public["monetary_ceiling_usd"] == "14.42"
        assert public["stage"] == "DEVELOPMENT"
        with pytest.raises(DevelopmentApprovalUnavailable, match="not current"):
            admission.assert_current(
                project_id_digest="sha256:" + "1" * 64,
                organization_id_digest=None,
            )
        with pytest.raises(DevelopmentApprovalUnavailable, match="invalid"):
            store.claim_fixture(
                authorization_id,
                bindings=bindings,
                journal_binding="sha256:" + "2" * 64,
            )
        changed_manifest = replace(
            bindings, campaign_manifest_digest="sha256:" + "3" * 64
        )
        with pytest.raises(DevelopmentAuthorizationError, match="different"):
            store.issue_fixture(changed_manifest)

    with ControlledDevelopmentAuthorizationStore(path) as reopened:
        resumed = reopened.claim_fixture(
            authorization_id,
            bindings=bindings,
            journal_binding=journal_binding,
        )
        resumed.assert_current(
            project_id_digest=bindings.project_id_digest,
            organization_id_digest=None,
        )
        reopened.finalize_fixture(resumed, report_digest="sha256:" + "4" * 64)
        with pytest.raises(DevelopmentAuthorizationError, match="terminal"):
            reopened.issue_fixture(bindings)

    revoked_path = tmp_path / "revoked.sqlite"
    with ControlledDevelopmentAuthorizationStore(revoked_path) as store:
        authorization_id = store.issue_fixture(bindings)
        admission = store.claim_fixture(
            authorization_id,
            bindings=bindings,
            journal_binding=journal_binding,
        )
        store.revoke_fixture(authorization_id)
        with pytest.raises(DevelopmentApprovalUnavailable, match="not current"):
            admission.assert_current(
                project_id_digest=bindings.project_id_digest,
                organization_id_digest=None,
            )

    expired_path = tmp_path / "expired.sqlite"
    with ControlledDevelopmentAuthorizationStore(expired_path) as store:
        authorization_id = store.issue_fixture(bindings)
        store.expire_fixture(authorization_id)
        with pytest.raises(DevelopmentApprovalUnavailable, match="expired"):
            store.claim_fixture(
                authorization_id,
                bindings=bindings,
                journal_binding=journal_binding,
            )


def test_authorization_cannot_move_to_a_recreated_or_second_journal(
    tmp_path: Path,
) -> None:
    request = _current_request(tmp_path / "request")
    manifest = pilot._validated_manifest(request["manifest"])
    with DevelopmentJournal(
        tmp_path / "first.sqlite", manifest_digest=manifest.content_digest
    ) as first:
        first_binding = first.authorization_binding(request["content_digest"])
    with DevelopmentJournal(
        tmp_path / "first.sqlite", manifest_digest=manifest.content_digest
    ) as reopened:
        assert reopened.authorization_binding(request["content_digest"]) == (
            first_binding
        )
    bindings = pilot.authorization_bindings(
        request,
        journal_binding=first_binding,
        project_id="fixture-project",
        organization_id=None,
    )
    with ControlledDevelopmentAuthorizationStore(
        tmp_path / "authority.sqlite"
    ) as store:
        authorization_id = store.issue_fixture(bindings)
        store.claim_fixture(
            authorization_id,
            bindings=bindings,
            journal_binding=first_binding,
        )
        with DevelopmentJournal(
            tmp_path / "second.sqlite", manifest_digest=manifest.content_digest
        ) as second:
            second_binding = second.authorization_binding(request["content_digest"])
        assert second_binding != first_binding
        rebound = replace(bindings, journal_binding=second_binding)
        with pytest.raises(DevelopmentAuthorizationError, match="different"):
            store.issue_fixture(rebound)
        with pytest.raises(DevelopmentApprovalUnavailable, match="invalid"):
            store.claim_fixture(
                authorization_id,
                bindings=bindings,
                journal_binding=second_binding,
            )


class _ResponsesFixtureHandler(BaseHTTPRequestHandler):
    calls: ClassVar[list[dict[str, object]]] = []
    expected_project = "fixture-project"
    response_status = 200

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        type(self).calls.append(body)
        if type(self.response_status) is not int or self.response_status != 200:
            self.send_response(self.response_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"controlled"}}')
            return
        assert self.path == "/v1/responses"
        assert self.headers["OpenAI-Project"] == self.expected_project
        assert (
            self.headers["Authorization"]
            == "Bearer fixture-key-never-valid-for-live-provider"
        )
        assert body["store"] is False and body["tools"] == []
        payload = json.loads(body["input"][-1]["content"])
        system = json.loads(body["input"][0]["content"])
        assert set(payload) | {"frozen_system_and_profile_policy"} == {
            "frozen_system_and_profile_policy",
            "agent_visible_synthetic_task_description",
            "current_arm_permitted_prior_material",
            "current_run_permitted_practice_feedback",
            "public_resource_facts",
            "current_run_existing_candidate_ids",
        }
        assert system["profile"] in {item.value for item in AgentProfile}
        if body["text"]["format"]["name"] == "be4_final_selection":
            feedback = payload["current_run_permitted_practice_feedback"]
            selected = min(
                feedback,
                key=lambda item: (item["comparison_value"], item["candidate_id"]),
            )
            structured = {
                "action": "SELECT",
                "candidate_id": selected["candidate_id"],
                "reason": "controlled minimum permitted feedback",
            }
        else:
            existing = payload["current_run_existing_candidate_ids"]
            strategy = deepcopy(payload["public_resource_facts"]["scaffold_strategy"])
            patterns = ((2, 1, 1), (1, 2, 1), (1, 1, 2), (2, 1, 1))
            pattern = patterns[len(existing) % len(patterns)]
            for index, surface in enumerate(REGISTERED_EFFECTFUL_SURFACES):
                strategy["parameters"][surface] = pattern[index]
            structured = {
                "action": "PROPOSE",
                "reason": "controlled structured response",
                "strategy": strategy,
                "surface_id": REGISTERED_EFFECTFUL_SURFACES[
                    len(existing) % len(REGISTERED_EFFECTFUL_SURFACES)
                ],
            }
        encoded = json.dumps(structured, separators=(",", ":"))
        ordinal = len(type(self).calls)
        envelope = {
            "id": f"resp_controlled_{ordinal:04d}",
            "model": "gpt-5.6-terra",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": encoded}],
                }
            ],
            "service_tier": "default",
            "status": "completed",
            "usage": {
                "input_tokens": max(1, len(json.dumps(body)) // 4),
                "input_tokens_details": {
                    "cache_write_tokens": 0,
                    "cached_tokens": 0,
                },
                "output_tokens": max(6, len(encoded) // 4),
                "output_tokens_details": {"reasoning_tokens": 5},
            },
        }
        raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _start_server(handler: type[BaseHTTPRequestHandler]):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_full_controlled_http_cli_path_traverses_40_carbon_slots(
    tmp_path: Path,
) -> None:
    _ResponsesFixtureHandler.calls = []
    _ResponsesFixtureHandler.expected_project = (
        "fixture-project-never-valid-for-live-provider"
    )
    _ResponsesFixtureHandler.response_status = 200
    server, thread = _start_server(_ResponsesFixtureHandler)
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/responses"
    try:
        exit_code = pilot.main(
            [
                "--controlled-responses-fixture",
                "--controlled-endpoint",
                endpoint,
                "--journal",
                str(tmp_path / "journal.sqlite"),
                "--controlled-authorization-store",
                str(tmp_path / "authority.sqlite"),
                "--report",
                str(tmp_path / "report.json"),
            ]
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert exit_code == 0
    report = pilot.validate_report(
        json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    )
    assert report["completed_run_count"] == 40
    assert report["provider_execution_status"] == "SIMULATED_OFFLINE_ONLY"
    assert report["paid_execution_occurred"] is False
    assert len(_ResponsesFixtureHandler.calls) == 168
    all_payloads = json.dumps(_ResponsesFixtureHandler.calls).lower()
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
        assert forbidden not in all_payloads


def test_controlled_http_error_is_unreconciled_and_not_retried(
    tmp_path: Path,
) -> None:
    _ResponsesFixtureHandler.calls = []
    _ResponsesFixtureHandler.expected_project = "fixture-project"
    _ResponsesFixtureHandler.response_status = 500
    server, thread = _start_server(_ResponsesFixtureHandler)
    store = None
    try:
        preview = _current_request(tmp_path / "preview")
        manifest = pilot._validated_manifest(preview["manifest"])
        with DevelopmentJournal(
            tmp_path / "journal.sqlite",
            manifest_digest=manifest.content_digest,
        ) as journal:
            journal_binding = journal.authorization_binding(preview["content_digest"])
            _request, bindings, store, admission = _controlled_admission(
                tmp_path,
                journal_binding=journal_binding,
            )
            transport = ControlledOpenAIResponsesTransport(
                endpoint=f"http://127.0.0.1:{server.server_port}/v1/responses",
                api_key="fixture-key-never-valid-for-live-provider",
                project_id="fixture-project",
                organization_id=None,
                admission=admission,
            )
            journal.bind_execution_authorization(
                authorization_id=admission.authorization_id,
                execution_request_digest=bindings.request_digest,
                provider_project_digest=bindings.project_id_digest,
                journal_binding=journal_binding,
            )
            dispatcher = ProviderDispatcher(journal=journal, transport=transport)
            with pytest.raises(ProviderAmbiguousTimeout, match="unreconciled"):
                dispatcher.dispatch(_provider_call())
            summary = journal.provider_operation_summary()
            assert summary["operation_states"]["UNKNOWN"] == 1
            assert summary["reserved_cost_usd"] != "0"
    finally:
        if store is not None:
            store.close()
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert len(_ResponsesFixtureHandler.calls) == 1


@pytest.mark.parametrize(
    ("status", "content", "expected"),
    [
        (
            "completed",
            [{"type": "refusal", "refusal": "controlled refusal"}],
            ProviderOutcomeKind.REFUSAL,
        ),
        ("incomplete", [], ProviderOutcomeKind.TRUNCATED),
    ],
)
def test_responses_refusal_and_truncation_are_typed_consumed_results(
    status: str, content: list[dict[str, object]], expected: ProviderOutcomeKind
) -> None:
    payload = {
        "id": "resp_controlled",
        "model": "gpt-5.6-terra",
        "output": [{"type": "message", "content": content}],
        "service_tier": "default",
        "status": status,
        "usage": {
            "input_tokens": 10,
            "input_tokens_details": {
                "cache_write_tokens": 0,
                "cached_tokens": 0,
            },
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 2},
        },
    }
    raw = json.dumps(payload)
    parsed = OpenAIResponsesTransport._parse(
        _provider_call(), payload, raw, "2026-09-09T00:00:00Z"
    )
    assert parsed.outcome is expected
    assert parsed.usage.output_tokens == 5


def test_real_report_accepts_unknown_billing_and_partial_stage_without_false_unpaid(
    tmp_path: Path,
) -> None:
    request = _current_request(tmp_path / "request")
    manifest = pilot._validated_manifest(request["manifest"])
    slot = manifest.schedule[0]
    project_digest = pilot.provider_identity_digest(
        "fixture-project", kind="OPENAI_PROJECT_ID"
    )
    summary = {
        "confirmed_cost_usd": "0",
        "confirmed_input_tokens": 0,
        "confirmed_output_tokens": 0,
        "conservative_cost_usd": "0.05",
        "dispatched_operation_count": 1,
        "operation_states": {
            "COMPLETED": 0,
            "INTENT": 0,
            "UNKNOWN": 1,
            "VERIFIED_NOT_EXECUTED": 0,
        },
        "reserved_cost_usd": "0.05",
        "reserved_input_tokens": 100,
        "reserved_output_tokens": 10,
    }
    base = {
        "authority_ceiling": pilot.DEVELOPMENT_AUTHORITY_CEILING,
        "campaign_manifest_digest": request["manifest"]["content_digest"],
        "completed_run_count": 0,
        "model_inference_executed": None,
        "offline_integration_only": False,
        "paid_execution_occurred": None,
        "provider_execution_status": "POSSIBLE_UNRECONCILED",
        "provider_operation_summary": summary,
        "qualifying_execution_ready": False,
        "recorded_run_count": 1,
        "remaining_run_count": 39,
        "run_results": [
            {
                "arm": slot.arm.value,
                "authority_ceiling": pilot.DEVELOPMENT_AUTHORITY_CEILING,
                "block_id": slot.block_id,
                "campaign_manifest_digest": manifest.content_digest,
                "diagnostic": "unreconciled controlled dispatch",
                "failure_kind": "UNRESOLVED_PROVIDER_DISPATCH",
                "profile": slot.profile.value,
                "qualifying_evidence": False,
                "run_id": slot.run_id,
                "run_ordinal": slot.ordinal,
                "schema_version": "carbon.be4.development-pilot.v2",
                "status": "FAILED",
                "task_id": slot.task_id,
            }
        ],
        "schema_version": "carbon.be4.development-pilot.v2",
        "stage": "DEVELOPMENT",
        "stop_reason": "UNRESOLVED_PROVIDER_DISPATCH",
    }
    journal_binding = "sha256:" + "3" * 64
    bound = pilot.authorization_bindings(
        request,
        journal_binding=journal_binding,
        project_id="fixture-project",
        organization_id=None,
    )
    authorization = {
        "approval_act_digest": "sha256:" + "1" * 64,
        "authorization_id": "be4-development-fixture",
        "bindings": bound.to_json(),
        "bindings_digest": bound.content_digest,
        "environment": "LIVE_OPENAI_RESPONSES",
        "expires_at_utc": "2026-09-14T00:00:00Z",
        "independent_multidisciplinary_ratification_claimed": False,
        "issued_at_utc": "2026-09-09T00:00:00Z",
        "issuer_github_login": DEVELOPMENT_APPROVER_GITHUB_LOGIN,
        "issuer_github_user_id": DEVELOPMENT_APPROVER_GITHUB_USER_ID,
        "journal_binding": journal_binding,
        "monetary_ceiling_usd": "14.42",
        "organization_id_digest": None,
        "principal_count": 1,
        "project_id_digest": project_digest,
        "request_digest": request["content_digest"],
        "stage": "DEVELOPMENT",
        "state": "CLAIMED",
        "terminal_report_digest": None,
    }
    report = pilot._real_report(
        base,
        request=request,
        authorization_record=authorization,
        project_id_digest=project_digest,
    )
    checked = pilot.validate_real_report(report, request=request)
    assert checked["paid_execution_occurred"] is None
    assert checked["provider_project"]["access_status"] == (
        "UNRECONCILED_AFTER_DISPATCH"
    )

    mutated = deepcopy(checked)
    mutated["paid_execution_occurred"] = False
    source = dict(mutated)
    source.pop("content_digest")
    mutated["content_digest"] = pilot._domain_digest(pilot._REAL_REPORT_DOMAIN, source)
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_real_report(mutated, request=request)

    rebound = deepcopy(checked)
    rebound["run_results"][0]["arm"] = "GENERIC_PRIOR"
    source = dict(rebound)
    source.pop("content_digest")
    rebound["content_digest"] = pilot._domain_digest(pilot._REAL_REPORT_DOMAIN, source)
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_real_report(rebound, request=request)

    malformed = deepcopy(checked)
    malformed["run_results"] = [True]
    source = dict(malformed)
    source.pop("content_digest")
    malformed["content_digest"] = pilot._domain_digest(
        pilot._REAL_REPORT_DOMAIN, source
    )
    with pytest.raises(pilot.DevelopmentFixtureError, match="boundary"):
        pilot.validate_real_report(malformed, request=request)
