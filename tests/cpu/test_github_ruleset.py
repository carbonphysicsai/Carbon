from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "scripts" / "dev" / "apply_github_ruleset.py"
ARTIFACT = REPOSITORY_ROOT / ".github" / "rulesets" / "main.v1.json"
MAIN_SHA = "a" * 40
CANDIDATE_SHA = "b" * 40
PR_NUMBER = 72
RULESET_LIST_ENDPOINT = (
    "repos/carbonphysicsai/Carbon/rulesets?includes_parents=true&per_page=100&page=1"
)
CHECK_RUNS_ENDPOINT = (
    "repos/carbonphysicsai/Carbon/commits/"
    + CANDIDATE_SHA
    + "/check-runs?check_name=Merge%20gate&filter=latest&app_id=15368"
    "&per_page=100&page=1"
)
PR_ENDPOINT = f"repos/carbonphysicsai/Carbon/pulls/{PR_NUMBER}"
EFFECTIVE_RULES_ENDPOINT = (
    "repos/carbonphysicsai/Carbon/rules/branches/main?per_page=100&page=1"
)

spec = importlib.util.spec_from_file_location("apply_github_ruleset", SCRIPT)
assert spec is not None and spec.loader is not None
ruleset_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ruleset_module
spec.loader.exec_module(ruleset_module)


class FakeClient:
    def __init__(self, responses: Mapping[str, Any]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, endpoint, payload))
        key = f"{method} {endpoint}"
        if key in self.responses:
            response = self.responses[key]
            if isinstance(response, ResponseSequence):
                response = response.next(key)
            if isinstance(response, Exception):
                raise response
            return response
        if endpoint in self.responses:
            response = self.responses[endpoint]
            if isinstance(response, ResponseSequence):
                response = response.next(endpoint)
            if isinstance(response, Exception):
                raise response
            return response
        raise AssertionError(f"unexpected fake API request: {key}")


class ResponseSequence:
    def __init__(self, *values: Any) -> None:
        self.values = list(values)

    def next(self, key: str) -> Any:
        if not self.values:
            raise AssertionError(f"response sequence exhausted for {key}")
        return self.values.pop(0)


class FakeGit:
    def __init__(
        self,
        *,
        status: str = "",
        head: str = CANDIDATE_SHA,
        origin_main: str = MAIN_SHA,
        ancestor: bool = True,
    ) -> None:
        self.status = status
        self.head = head
        self.origin_main = origin_main
        self.ancestor = ancestor
        self.calls: list[tuple[str, ...]] = []

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(arguments)
        if arguments == ("status", "--porcelain=v1", "--untracked-files=all"):
            return subprocess.CompletedProcess(arguments, 0, self.status, "")
        if arguments == ("rev-parse", "--verify", "HEAD^{commit}"):
            return subprocess.CompletedProcess(arguments, 0, self.head + "\n", "")
        if arguments == (
            "rev-parse",
            "--verify",
            "refs/remotes/origin/main^{commit}",
        ):
            return subprocess.CompletedProcess(
                arguments, 0, self.origin_main + "\n", ""
            )
        if arguments == (
            "merge-base",
            "--is-ancestor",
            MAIN_SHA,
            CANDIDATE_SHA,
        ):
            return subprocess.CompletedProcess(
                arguments, 0 if self.ancestor else 1, "", ""
            )
        raise AssertionError(f"unexpected fake Git request: {arguments}")


def _artifact() -> dict[str, Any]:
    return ruleset_module.load_artifact(ARTIFACT)


def _raw_artifact() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _merge_gate_run(
    *,
    run_id: int = 10,
    status: str = "completed",
    conclusion: str | None = "success",
    started_at: str = "2026-09-01T00:00:00Z",
    completed_at: str | None = None,
) -> dict[str, Any]:
    if completed_at is None and status == "completed":
        completed_at = "2026-09-01T00:01:00Z"
    return {
        "id": run_id,
        "name": "Merge gate",
        "head_sha": CANDIDATE_SHA,
        "status": status,
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at,
        "app": {"id": 15368},
    }


def _live_pr() -> dict[str, Any]:
    return {
        "number": PR_NUMBER,
        "state": "open",
        "draft": False,
        "base": {
            "ref": "main",
            "sha": MAIN_SHA,
            "repo": {"full_name": "carbonphysicsai/Carbon"},
        },
        "head": {
            "ref": "agent/b-01f-development-throughput",
            "sha": CANDIDATE_SHA,
            "repo": {"full_name": "carbonphysicsai/Carbon"},
        },
    }


def _base_responses(
    *,
    admin: bool = True,
    rulesets: list[dict[str, Any]] | None = None,
    effective: list[dict[str, Any]] | None = None,
    pull: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "repos/carbonphysicsai/Carbon": {
            "permissions": {"admin": admin},
            "allow_merge_commit": True,
            "allow_squash_merge": True,
            "allow_rebase_merge": True,
            "allow_auto_merge": False,
        },
        "repos/carbonphysicsai/Carbon/branches/main": {"commit": {"sha": MAIN_SHA}},
        CHECK_RUNS_ENDPOINT: {
            "total_count": 1,
            "check_runs": [_merge_gate_run()],
        },
        RULESET_LIST_ENDPOINT: rulesets or [],
        EFFECTIVE_RULES_ENDPOINT: effective or [],
        PR_ENDPOINT: pull if pull is not None else _live_pr(),
    }


def _effective_rules(
    artifact: Mapping[str, Any], *, ruleset_id: int = 41
) -> list[dict[str, Any]]:
    return [
        {**json.loads(json.dumps(rule)), "ruleset_id": ruleset_id}
        for rule in artifact["ruleset"]["rules"]
    ]


def _plan(
    *,
    repository: str,
    ruleset_action: str,
    ruleset_id: int | None,
    settings_action: str,
    expected_main: str | None,
    merge_gate_sha: str | None,
    pr_number: int | None,
    current_ruleset: Mapping[str, Any] | None = None,
    current_repository: Mapping[str, Any] | None = None,
) -> Any:
    artifact = _artifact()
    repository_data = (
        current_repository
        if current_repository is not None
        else _base_responses()["repos/carbonphysicsai/Carbon"]
    )
    current_settings = ruleset_module._repository_settings_values(
        repository_data, artifact["repository_settings"]
    )
    return ruleset_module.RulesetPlan(
        repository=repository,
        ruleset_action=ruleset_action,
        ruleset_id=ruleset_id,
        ruleset_state_sha256=ruleset_module._observation_digest(
            ruleset_module._ruleset_mutation_state(current_ruleset, artifact["ruleset"])
        ),
        settings_action=settings_action,
        settings_state_sha256=ruleset_module._observation_digest(current_settings),
        expected_main=expected_main,
        merge_gate_sha=merge_gate_sha,
        pr_number=pr_number,
    )


def test_versioned_artifact_encodes_fail_closed_main_contract() -> None:
    artifact = _artifact()
    assert artifact["repository"] == "carbonphysicsai/Carbon"
    ruleset = artifact["ruleset"]
    assert ruleset["bypass_actors"] == []
    assert ruleset["conditions"]["ref_name"] == {
        "include": ["refs/heads/main"],
        "exclude": [],
    }
    rules = {item["type"]: item for item in ruleset["rules"]}
    assert "required_linear_history" not in rules
    assert {
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_status_checks",
    } == set(rules)
    pull_request = rules["pull_request"]["parameters"]
    assert pull_request["allowed_merge_methods"] == ["merge"]
    assert pull_request["dismiss_stale_reviews_on_push"] is True
    assert pull_request["require_code_owner_review"] is False
    assert pull_request["require_last_push_approval"] is True
    assert pull_request["required_approving_review_count"] == 1
    assert pull_request["required_review_thread_resolution"] is True
    status_parameters = rules["required_status_checks"]["parameters"]
    assert status_parameters["do_not_enforce_on_create"] is False
    assert status_parameters["strict_required_status_checks_policy"] is True
    checks = {
        (item["context"], item["integration_id"])
        for item in status_parameters["required_status_checks"]
    }
    assert checks == {("Merge gate", 15368), ("GPT review gate", 15368)}
    assert artifact["repository_settings"] == {
        "allow_merge_commit": True,
        "allow_squash_merge": False,
        "allow_rebase_merge": False,
        "allow_auto_merge": False,
    }


def test_plan_creates_ruleset_and_patches_merge_methods() -> None:
    client = FakeClient(_base_responses())
    plan = ruleset_module.build_plan(
        client,
        _artifact(),
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert plan.ruleset_action == "CREATE"
    assert plan.ruleset_id is None
    assert plan.settings_action == "PATCH"
    assert client.calls[-1][:2] == (
        "GET",
        "repos/carbonphysicsai/Carbon/branches/main",
    )


def test_plan_is_noop_for_normalized_live_state() -> None:
    artifact = _artifact()
    desired = json.loads(json.dumps(artifact["ruleset"]))
    desired.update(
        {
            "id": 41,
            "source": "carbonphysicsai/Carbon",
            "source_type": "Repository",
        }
    )
    responses = _base_responses(
        rulesets=[
            {
                "id": 41,
                "name": "Carbon main merge gate",
                "source": "carbonphysicsai/Carbon",
                "source_type": "Repository",
            }
        ],
        effective=_effective_rules(artifact),
    )
    responses["repos/carbonphysicsai/Carbon"]["allow_squash_merge"] = False
    responses["repos/carbonphysicsai/Carbon"]["allow_rebase_merge"] = False
    responses["repos/carbonphysicsai/Carbon/rulesets/41"] = desired
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        artifact,
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert plan.ruleset_action == "NOOP"
    assert plan.ruleset_id == 41
    assert plan.settings_action == "NOOP"


def test_plan_refuses_non_admin_credentials() -> None:
    client = FakeClient(_base_responses(admin=False))
    with pytest.raises(ruleset_module.RulesetError, match="administration"):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_refuses_changed_main() -> None:
    responses = _base_responses()
    responses["repos/carbonphysicsai/Carbon/branches/main"] = {
        "commit": {"sha": "c" * 40}
    }
    client = FakeClient(responses)
    with pytest.raises(ruleset_module.RulesetError, match="main changed"):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("draft", "must be non-draft"),
        ("closed", "must be open on the exact candidate"),
        ("missing_base", "guarded pull request base must be a JSON object"),
        ("base_repository", "in-repository change targeting main"),
        ("base_ref", "in-repository change targeting main"),
        ("base_sha", "bind current main"),
        ("head_repository", "in-repository change targeting main"),
        ("head_sha", "bind current main"),
    ],
)
def test_plan_refuses_live_pr_identity_drift(case: str, message: str) -> None:
    pull = _live_pr()
    if case == "draft":
        pull["draft"] = True
    elif case == "closed":
        pull["state"] = "closed"
    elif case == "missing_base":
        pull.pop("base")
    elif case == "base_repository":
        pull["base"]["repo"]["full_name"] = "someone/Carbon"
    elif case == "base_ref":
        pull["base"]["ref"] = "release"
    elif case == "base_sha":
        pull["base"]["sha"] = "c" * 40
    elif case == "head_repository":
        pull["head"]["repo"]["full_name"] = "someone/Carbon"
    elif case == "head_sha":
        pull["head"]["sha"] = "c" * 40
    client = FakeClient(_base_responses(pull=pull))
    with pytest.raises(ruleset_module.RulesetError, match=message):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_accepts_exact_main_from_normally_merged_guard_pr() -> None:
    merged = _live_pr()
    merged.update(
        {
            "state": "closed",
            "merged_at": "2026-09-02T00:00:00Z",
            "merge_commit_sha": MAIN_SHA,
        }
    )
    merged["base"]["sha"] = "c" * 40
    responses = _base_responses(pull=merged)
    responses[f"repos/carbonphysicsai/Carbon/commits/{MAIN_SHA}"] = {
        "sha": MAIN_SHA,
        "parents": [{"sha": "c" * 40}, {"sha": CANDIDATE_SHA}],
    }
    main_check_endpoint = CHECK_RUNS_ENDPOINT.replace(CANDIDATE_SHA, MAIN_SHA)
    responses[main_check_endpoint] = responses.pop(CHECK_RUNS_ENDPOINT)
    responses[main_check_endpoint]["check_runs"][0]["head_sha"] = MAIN_SHA
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        _artifact(),
        expected_main=MAIN_SHA,
        merge_gate_sha=MAIN_SHA,
        pr_number=PR_NUMBER,
    )
    assert plan.expected_main == MAIN_SHA
    assert plan.merge_gate_sha == MAIN_SHA


@pytest.mark.parametrize(
    ("parents", "message"),
    [
        ([{"sha": "c" * 40}], "normal two-parent merge"),
        (
            [{"sha": "c" * 40}, {"sha": "d" * 40}],
            "second parent must equal",
        ),
    ],
)
def test_plan_refuses_non_normal_or_wrong_head_governance_merge(
    parents: list[dict[str, str]], message: str
) -> None:
    merged = _live_pr()
    merged.update(
        {
            "state": "closed",
            "merged_at": "2026-09-02T00:00:00Z",
            "merge_commit_sha": MAIN_SHA,
        }
    )
    responses = _base_responses(pull=merged)
    responses[f"repos/carbonphysicsai/Carbon/commits/{MAIN_SHA}"] = {
        "sha": MAIN_SHA,
        "parents": parents,
    }
    main_check_endpoint = CHECK_RUNS_ENDPOINT.replace(CANDIDATE_SHA, MAIN_SHA)
    responses[main_check_endpoint] = responses.pop(CHECK_RUNS_ENDPOINT)
    responses[main_check_endpoint]["check_runs"][0]["head_sha"] = MAIN_SHA
    client = FakeClient(responses)
    with pytest.raises(ruleset_module.RulesetError, match=message):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=MAIN_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_refuses_tied_latest_merge_gate_timestamps() -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 2,
        "check_runs": [
            _merge_gate_run(run_id=10, conclusion="success"),
            _merge_gate_run(run_id=11, conclusion="failure"),
        ],
    }
    client = FakeClient(responses)
    with pytest.raises(ruleset_module.RulesetError, match="timestamp is ambiguous"):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_accepts_newest_success_across_latest_check_suites() -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 2,
        "check_runs": [
            _merge_gate_run(
                run_id=99,
                started_at="2026-09-01T00:00:00Z",
                completed_at="2026-09-01T00:01:00Z",
            ),
            _merge_gate_run(
                run_id=1,
                started_at="2026-09-01T00:02:00Z",
                completed_at="2026-09-01T00:03:00Z",
            ),
        ],
    }
    plan = ruleset_module.build_plan(
        FakeClient(responses),
        _artifact(),
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert plan.ruleset_action == "CREATE"


def test_plan_refuses_newer_current_across_latest_check_suites() -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 2,
        "check_runs": [
            _merge_gate_run(
                run_id=99,
                started_at="2026-09-01T00:00:00Z",
                completed_at="2026-09-01T00:01:00Z",
            ),
            _merge_gate_run(
                run_id=1,
                status="in_progress",
                conclusion=None,
                started_at="2026-09-01T00:02:00Z",
            ),
        ],
    }
    with pytest.raises(ruleset_module.RulesetError, match="still current"):
        ruleset_module.build_plan(
            FakeClient(responses),
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


@pytest.mark.parametrize(
    ("started_at", "completed_at", "message"),
    [
        ("not-a-timestamp", "2026-09-01T00:01:00Z", "started_at"),
        ("2026-09-01T00:00:00Z", "not-a-timestamp", "completed_at"),
        (
            "2026-09-01T00:02:00Z",
            "2026-09-01T00:01:00Z",
            "precedes started_at",
        ),
    ],
)
def test_plan_refuses_invalid_merge_gate_timestamps(
    started_at: str, completed_at: str, message: str
) -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 1,
        "check_runs": [
            _merge_gate_run(started_at=started_at, completed_at=completed_at)
        ],
    }
    with pytest.raises(ruleset_module.RulesetError, match=message):
        ruleset_module.build_plan(
            FakeClient(responses),
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_refuses_current_queued_latest_merge_gate() -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 1,
        "check_runs": [
            _merge_gate_run(run_id=12, status="in_progress", conclusion=None)
        ],
    }
    with pytest.raises(ruleset_module.RulesetError, match="still current"):
        ruleset_module.build_plan(
            FakeClient(responses),
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_plan_refuses_failed_latest_merge_gate() -> None:
    responses = _base_responses()
    responses[CHECK_RUNS_ENDPOINT] = {
        "total_count": 1,
        "check_runs": [_merge_gate_run(run_id=9, conclusion="failure")],
    }
    with pytest.raises(ruleset_module.RulesetError, match="not successful"):
        ruleset_module.build_plan(
            FakeClient(responses),
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_latest_merge_gate_pagination_fails_if_set_changes_between_pages() -> None:
    page_two = CHECK_RUNS_ENDPOINT.removesuffix("page=1") + "page=2"
    first_page = [_merge_gate_run(run_id=index + 1) for index in range(100)]
    responses = {
        CHECK_RUNS_ENDPOINT: {"total_count": 101, "check_runs": first_page},
        page_two: {
            "total_count": 102,
            "check_runs": [_merge_gate_run(run_id=101)],
        },
    }
    client = FakeClient(responses)
    with pytest.raises(ruleset_module.RulesetError, match="changed during pagination"):
        ruleset_module._verify_merge_gate(
            client, "carbonphysicsai/Carbon", CANDIDATE_SHA
        )
    assert client.calls[-1][:2] == ("GET", page_two)


def test_latest_merge_gate_paginates_complete_stable_set_without_id_selection() -> None:
    page_two = CHECK_RUNS_ENDPOINT.removesuffix("page=1") + "page=2"
    first_page = [
        _merge_gate_run(
            run_id=index + 1000,
            conclusion="failure" if index == 99 else "success",
            started_at=f"2026-09-01T{index // 60:02d}:{index % 60:02d}:00Z",
            completed_at="2026-09-02T00:00:00Z",
        )
        for index in range(100)
    ]
    responses = {
        CHECK_RUNS_ENDPOINT: {"total_count": 101, "check_runs": first_page},
        page_two: {
            "total_count": 101,
            "check_runs": [
                _merge_gate_run(
                    run_id=1,
                    started_at="2026-09-01T02:00:00Z",
                    completed_at="2026-09-02T00:00:00Z",
                )
            ],
        },
    }
    client = FakeClient(responses)
    ruleset_module._verify_merge_gate(client, "carbonphysicsai/Carbon", CANDIDATE_SHA)
    assert client.calls[-1][:2] == ("GET", page_two)


def test_plan_refuses_inherited_ruleset_with_managed_name() -> None:
    responses = _base_responses(
        rulesets=[
            {
                "id": 99,
                "name": "Carbon main merge gate",
                "source": "carbonphysicsai",
                "source_type": "Organization",
            }
        ]
    )
    client = FakeClient(responses)
    with pytest.raises(ruleset_module.RulesetError, match="inherited"):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_apply_accepts_response_defaults_and_uses_only_managed_endpoints() -> None:
    artifact = _artifact()
    responses = _base_responses()
    summary = {
        "id": 7,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    pull_request = next(
        rule for rule in detail["rules"] if rule["type"] == "pull_request"
    )
    pull_request["parameters"].update(
        {
            "dismissal_restriction": {
                "allowed_actors": [],
                "enabled": False,
            },
            "ignore_approvals_from_contributors": False,
            "require_extra_approval_for_unattributed_changes": False,
            "required_reviewers": [],
        }
    )
    repository_before = _base_responses()["repos/carbonphysicsai/Carbon"]
    repository_after = dict(repository_before)
    repository_after.update(artifact["repository_settings"])
    responses.update(
        {
            "repos/carbonphysicsai/Carbon": ResponseSequence(
                repository_before, repository_before, repository_after
            ),
            RULESET_LIST_ENDPOINT: ResponseSequence([], [summary], [summary]),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                [],
                _effective_rules(artifact, ruleset_id=7),
                _effective_rules(artifact, ruleset_id=7),
                _effective_rules(artifact, ruleset_id=7),
            ),
            "repos/carbonphysicsai/Carbon/rulesets/7": ResponseSequence(detail, detail),
            "POST repos/carbonphysicsai/Carbon/rulesets": detail,
            "PATCH repos/carbonphysicsai/Carbon": {"id": 1},
        }
    )
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    mutations = [
        (method, endpoint, payload)
        for method, endpoint, payload in client.calls
        if method != "GET"
    ]
    assert [(method, endpoint) for method, endpoint, _ in mutations] == [
        ("POST", "repos/carbonphysicsai/Carbon/rulesets"),
        ("PATCH", "repos/carbonphysicsai/Carbon"),
    ]
    assert mutations[0][2] == artifact["ruleset"]
    assert mutations[1][2] == artifact["repository_settings"]
    assert client.calls[-1][:2] == ("GET", EFFECTIVE_RULES_ENDPOINT)


def test_failed_create_attempt_stops_after_one_forward_post() -> None:
    artifact = _artifact()
    responses = _base_responses()
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = (
        ruleset_module.RulesetError("injected ambiguous repository ruleset POST")
    )
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE") as caught:
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert "No automatic rollback or restorative mutation was attempted" in str(
        caught.value
    )
    mutations = [call for call in client.calls if call[0] != "GET"]
    assert mutations == [
        (
            "POST",
            "repos/carbonphysicsai/Carbon/rulesets",
            artifact["ruleset"],
        )
    ]
    assert client.calls[-1] == mutations[-1]


def test_failed_update_attempt_stops_after_one_forward_put() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    prior_ruleset = json.loads(json.dumps(artifact["ruleset"]))
    prior_ruleset["enforcement"] = "evaluate"
    prior_detail = json.loads(json.dumps(prior_ruleset))
    prior_detail.update(summary)
    responses = _base_responses(rulesets=[summary])
    responses.update(
        {
            "repos/carbonphysicsai/Carbon/rulesets/41": prior_detail,
            "PUT repos/carbonphysicsai/Carbon/rulesets/41": (
                ruleset_module.RulesetError("injected ambiguous repository ruleset PUT")
            ),
        }
    )
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="UPDATE",
        ruleset_id=41,
        current_ruleset=prior_detail,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    mutations = [call for call in client.calls if call[0] != "GET"]
    assert mutations == [
        (
            "PUT",
            "repos/carbonphysicsai/Carbon/rulesets/41",
            artifact["ruleset"],
        )
    ]
    assert client.calls[-1] == mutations[-1]


def test_create_refuses_malformed_mutation_response_id() -> None:
    artifact = _artifact()
    responses = _base_responses()
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": None}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE") as caught:
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert "created managed ruleset has no numeric id" in str(caught.value)
    expected_mutation = (
        "POST",
        "repos/carbonphysicsai/Carbon/rulesets",
        artifact["ruleset"],
    )
    assert [call for call in client.calls if call[0] != "GET"] == [expected_mutation]
    assert client.calls[-1] == expected_mutation


def test_update_refuses_boolean_mutation_response_id() -> None:
    artifact = _artifact()
    summary = {
        "id": 1,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    prior_detail = json.loads(json.dumps(artifact["ruleset"]))
    prior_detail["enforcement"] = "evaluate"
    prior_detail.update(summary)
    responses = _base_responses(rulesets=[summary])
    responses.update(
        {
            "repos/carbonphysicsai/Carbon/rulesets/1": prior_detail,
            "PUT repos/carbonphysicsai/Carbon/rulesets/1": {"id": True},
        }
    )
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="UPDATE",
        ruleset_id=1,
        current_ruleset=prior_detail,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE") as caught:
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert "updated managed ruleset id changed unexpectedly" in str(caught.value)
    expected_mutation = (
        "PUT",
        "repos/carbonphysicsai/Carbon/rulesets/1",
        artifact["ruleset"],
    )
    assert [call for call in client.calls if call[0] != "GET"] == [expected_mutation]
    assert client.calls[-1] == expected_mutation


@pytest.mark.parametrize(
    ("ruleset_action", "ruleset_id", "method"),
    [("CREATE", None, "POST"), ("UPDATE", 41, "PUT")],
)
def test_settings_failure_after_ruleset_success_sends_only_forward_writes(
    ruleset_action: str, ruleset_id: int | None, method: str
) -> None:
    artifact = _artifact()
    live_id = 7 if ruleset_id is None else ruleset_id
    summary = {
        "id": live_id,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    desired_detail = json.loads(json.dumps(artifact["ruleset"]))
    desired_detail.update(summary)
    repository_before = _base_responses()["repos/carbonphysicsai/Carbon"]
    responses = _base_responses(rulesets=[] if ruleset_id is None else [summary])
    responses.update(
        {
            "repos/carbonphysicsai/Carbon": ResponseSequence(
                repository_before, repository_before
            ),
            RULESET_LIST_ENDPOINT: ResponseSequence(
                [] if ruleset_id is None else [summary], [summary]
            ),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                [], _effective_rules(artifact, ruleset_id=live_id)
            ),
            "PATCH repos/carbonphysicsai/Carbon": ruleset_module.RulesetError(
                "injected ambiguous repository settings PATCH"
            ),
        }
    )
    if ruleset_id is None:
        ruleset_endpoint = "repos/carbonphysicsai/Carbon/rulesets"
        responses[f"POST {ruleset_endpoint}"] = desired_detail
        responses[f"repos/carbonphysicsai/Carbon/rulesets/{live_id}"] = desired_detail
    else:
        ruleset_endpoint = f"repos/carbonphysicsai/Carbon/rulesets/{live_id}"
        pull_request = next(
            rule for rule in desired_detail["rules"] if rule["type"] == "pull_request"
        )
        pull_request["parameters"].update(
            {
                "dismissal_restriction": {
                    "allowed_actors": [],
                    "enabled": False,
                },
                "ignore_approvals_from_contributors": False,
                "require_extra_approval_for_unattributed_changes": False,
                "required_reviewers": [],
            }
        )
        prior_detail = json.loads(json.dumps(desired_detail))
        prior_detail["enforcement"] = "evaluate"
        responses[ruleset_endpoint] = ResponseSequence(prior_detail, desired_detail)
        responses[f"PUT {ruleset_endpoint}"] = desired_detail
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action=ruleset_action,
        ruleset_id=ruleset_id,
        current_ruleset=None if ruleset_id is None else prior_detail,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    mutations = [call for call in client.calls if call[0] != "GET"]
    assert mutations == [
        (method, ruleset_endpoint, artifact["ruleset"]),
        (
            "PATCH",
            "repos/carbonphysicsai/Carbon",
            artifact["repository_settings"],
        ),
    ]
    assert client.calls[-1] == mutations[-1]


def test_forward_only_rerun_converges_ruleset_complete_settings_partial_state() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    repository_before = _base_responses()["repos/carbonphysicsai/Carbon"]
    repository_after = dict(repository_before)
    repository_after.update(artifact["repository_settings"])
    effective = _effective_rules(artifact, ruleset_id=41)
    responses = _base_responses(rulesets=[summary], effective=effective)
    responses.update(
        {
            "repos/carbonphysicsai/Carbon": ResponseSequence(
                repository_before, repository_before, repository_after
            ),
            RULESET_LIST_ENDPOINT: ResponseSequence([summary], [summary], [summary]),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                effective, effective, effective, effective
            ),
            "repos/carbonphysicsai/Carbon/rulesets/41": ResponseSequence(
                detail, detail, detail
            ),
            "PATCH repos/carbonphysicsai/Carbon": {"id": 1},
        }
    )
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        artifact,
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert (plan.ruleset_action, plan.settings_action) == ("NOOP", "PATCH")

    ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    mutations = [call for call in client.calls if call[0] != "GET"]
    assert mutations == [
        (
            "PATCH",
            "repos/carbonphysicsai/Carbon",
            artifact["repository_settings"],
        )
    ]
    assert client.calls[-1][:2] == ("GET", EFFECTIVE_RULES_ENDPOINT)


def test_apply_source_has_only_forward_desired_mutation_primitives() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    mutation_calls: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "request":
            continue
        method_keywords = [item for item in node.keywords if item.arg == "method"]
        if not method_keywords:
            continue
        assert len(method_keywords) == 1
        method_node = method_keywords[0].value
        assert isinstance(method_node, ast.Constant)
        assert isinstance(method_node.value, str)
        payload_keywords = [item for item in node.keywords if item.arg == "payload"]
        assert len(payload_keywords) == 1
        mutation_calls.append((method_node.value, payload_keywords[0].value))

    mutation_calls.sort(key=lambda item: item[1].lineno)
    assert [method for method, _ in mutation_calls] == ["POST", "PUT", "PATCH"]
    for method, payload in mutation_calls[:2]:
        assert method in {"POST", "PUT"}
        assert isinstance(payload, ast.Name)
        assert payload.id == "ruleset"
    settings_payload = mutation_calls[2][1]
    assert isinstance(settings_payload, ast.Call)
    assert isinstance(settings_payload.func, ast.Name)
    assert settings_payload.func.id == "_require_mapping"
    assert isinstance(settings_payload.args[0], ast.Subscript)
    assert isinstance(settings_payload.args[0].value, ast.Name)
    assert settings_payload.args[0].value.id == "artifact"
    assert isinstance(settings_payload.args[0].slice, ast.Constant)
    assert settings_payload.args[0].slice.value == "repository_settings"
    assert "def _restore_" not in source
    assert "_ApplySnapshot" not in source
    assert "_compensate_apply" not in source


def _write_artifact(tmp_path: Path, value: Mapping[str, Any]) -> Path:
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dismiss_stale_reviews_on_push", False),
        ("require_code_owner_review", True),
        ("require_last_push_approval", False),
        ("required_approving_review_count", False),
    ],
)
def test_artifact_refuses_changed_pull_request_contract(
    tmp_path: Path, field: str, value: Any
) -> None:
    artifact = _raw_artifact()
    rules = {item["type"]: item for item in artifact["ruleset"]["rules"]}
    rules["pull_request"]["parameters"][field] = value
    with pytest.raises(ruleset_module.RulesetError, match="pull_request parameters"):
        ruleset_module.load_artifact(_write_artifact(tmp_path, artifact))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("do_not_enforce_on_create", True, "branch creation"),
        ("strict_required_status_checks_policy", False, "strict status"),
    ],
)
def test_artifact_refuses_changed_status_policy(
    tmp_path: Path, field: str, value: bool, message: str
) -> None:
    artifact = _raw_artifact()
    rules = {item["type"]: item for item in artifact["ruleset"]["rules"]}
    rules["required_status_checks"]["parameters"][field] = value
    with pytest.raises(ruleset_module.RulesetError, match=message):
        ruleset_module.load_artifact(_write_artifact(tmp_path, artifact))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repository", "someone/Carbon", "repository must be exactly"),
        ("ruleset.name", "Another policy", "ruleset name"),
    ],
)
def test_artifact_refuses_changed_managed_identity(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    artifact = _raw_artifact()
    if field == "repository":
        artifact[field] = value
    else:
        artifact["ruleset"]["name"] = value
    with pytest.raises(ruleset_module.RulesetError, match=message):
        ruleset_module.load_artifact(_write_artifact(tmp_path, artifact))


def test_normalization_treats_missing_optional_integration_id_as_drift() -> None:
    artifact = _artifact()
    live = json.loads(json.dumps(artifact["ruleset"]))
    status_rule = next(
        item for item in live["rules"] if item["type"] == "required_status_checks"
    )
    status_rule["parameters"]["required_status_checks"][0].pop("integration_id")
    normalized = ruleset_module.normalize_ruleset(live)
    assert normalized != ruleset_module.normalize_ruleset(artifact["ruleset"])
    normalized_status = next(
        item for item in normalized["rules"] if item["type"] == "required_status_checks"
    )
    assert any(
        item["integration_id"] is None
        for item in normalized_status["parameters"]["required_status_checks"]
    )


def test_ruleset_discovery_paginates_before_deciding_to_create() -> None:
    first_page = [
        {
            "id": index,
            "name": f"unrelated-{index}",
            "source": "carbonphysicsai/Carbon",
            "source_type": "Repository",
        }
        for index in range(1, 101)
    ]
    managed_summary = {
        "id": 401,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(_artifact()["ruleset"]))
    client = FakeClient(
        {
            RULESET_LIST_ENDPOINT: first_page,
            (
                "repos/carbonphysicsai/Carbon/rulesets"
                "?includes_parents=true&per_page=100&page=2"
            ): [managed_summary],
            "repos/carbonphysicsai/Carbon/rulesets/401": detail,
        }
    )
    ruleset_id, current = ruleset_module._find_managed_ruleset(
        client, "carbonphysicsai/Carbon", "Carbon main merge gate"
    )
    assert ruleset_id == 401
    assert current == detail


def test_local_candidate_guard_accepts_clean_head_on_current_main_base() -> None:
    git = FakeGit()
    ruleset_module._verify_local_candidate(
        git, expected_main=MAIN_SHA, merge_gate_sha=CANDIDATE_SHA
    )
    assert git.calls[-1] == (
        "merge-base",
        "--is-ancestor",
        MAIN_SHA,
        CANDIDATE_SHA,
    )


def test_local_candidate_guard_refuses_dirty_checkout() -> None:
    with pytest.raises(ruleset_module.RulesetError, match="not clean"):
        ruleset_module._verify_local_candidate(
            FakeGit(status=" M tracked.py\n"),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
        )


def test_local_candidate_guard_refuses_stale_candidate_sha() -> None:
    with pytest.raises(ruleset_module.RulesetError, match="must equal local HEAD"):
        ruleset_module._verify_local_candidate(
            FakeGit(),
            expected_main=MAIN_SHA,
            merge_gate_sha="c" * 40,
        )


def test_local_candidate_guard_refuses_stale_origin_main() -> None:
    with pytest.raises(ruleset_module.RulesetError, match="equal local origin/main"):
        ruleset_module._verify_local_candidate(
            FakeGit(origin_main="c" * 40),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
        )


def test_local_candidate_guard_refuses_unrelated_candidate() -> None:
    with pytest.raises(ruleset_module.RulesetError, match="not an ancestor"):
        ruleset_module._verify_local_candidate(
            FakeGit(ancestor=False),
            expected_main=MAIN_SHA,
            merge_gate_sha=CANDIDATE_SHA,
        )


def test_plan_refuses_non_exact_sha_before_candidate_lookup() -> None:
    client = FakeClient(_base_responses())
    with pytest.raises(ruleset_module.RulesetError, match="40-character SHA"):
        ruleset_module.build_plan(
            client,
            _artifact(),
            expected_main=MAIN_SHA[:-1],
            merge_gate_sha=CANDIDATE_SHA,
            pr_number=PR_NUMBER,
        )


def test_apply_rechecks_main_guard_before_any_mutation() -> None:
    responses = _base_responses()
    responses["repos/carbonphysicsai/Carbon/branches/main"] = {
        "commit": {"sha": "c" * 40}
    }
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="NOOP",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="main changed"):
        ruleset_module.apply_plan(client, _artifact(), plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_changed_live_pr_head_before_any_mutation() -> None:
    pull = _live_pr()
    pull["head"]["sha"] = "c" * 40
    responses = _base_responses(pull=pull)
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="bind current main"):
        ruleset_module.apply_plan(client, _artifact(), plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_incompatible_preexisting_rule_before_any_mutation() -> None:
    artifact = _artifact()
    inherited = next(
        json.loads(json.dumps(item))
        for item in artifact["ruleset"]["rules"]
        if item["type"] == "pull_request"
    )
    inherited["ruleset_id"] = 99
    inherited["parameters"]["required_approving_review_count"] = 2
    responses = _base_responses(
        rulesets=[
            {
                "id": 99,
                "name": "Differently named inherited policy",
                "source": "carbonphysicsai",
                "source_type": "Organization",
            }
        ],
        effective=[inherited],
    )
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="human approval count"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_concurrent_settings_plan_drift_before_any_mutation() -> None:
    responses = _base_responses()
    responses["repos/carbonphysicsai/Carbon"].update(
        {"allow_squash_merge": False, "allow_rebase_merge": False}
    )
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="plan changed"):
        ruleset_module.apply_plan(client, _artifact(), plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)
    assert client.calls[-1][:2] == (
        "GET",
        "repos/carbonphysicsai/Carbon/branches/main",
    )


def test_apply_refuses_concurrent_ruleset_action_and_id_drift() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    responses = _base_responses(
        rulesets=[summary], effective=_effective_rules(artifact)
    )
    responses["repos/carbonphysicsai/Carbon/rulesets/41"] = detail
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="plan changed"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_changed_noncompliant_ruleset_with_same_update_action() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    prior = json.loads(json.dumps(artifact["ruleset"]))
    prior["enforcement"] = "evaluate"
    prior.update(summary)
    concurrent = json.loads(json.dumps(prior))
    concurrent["enforcement"] = "disabled"
    repository = _base_responses()["repos/carbonphysicsai/Carbon"]
    repository.update(artifact["repository_settings"])
    responses = _base_responses(rulesets=[summary])
    responses["repos/carbonphysicsai/Carbon"] = repository
    responses["repos/carbonphysicsai/Carbon/rulesets/41"] = ResponseSequence(
        prior, concurrent
    )
    responses["PUT repos/carbonphysicsai/Carbon/rulesets/41"] = {"id": 41}
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        artifact,
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert (plan.ruleset_action, plan.settings_action) == ("UPDATE", "NOOP")

    with pytest.raises(ruleset_module.RulesetError, match="plan changed"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_changed_noncompliant_settings_with_same_patch_action() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    prior = _base_responses()["repos/carbonphysicsai/Carbon"]
    concurrent = dict(prior)
    concurrent["allow_squash_merge"] = False
    effective = _effective_rules(artifact, ruleset_id=41)
    responses = _base_responses(rulesets=[summary], effective=effective)
    responses["repos/carbonphysicsai/Carbon"] = ResponseSequence(prior, concurrent)
    responses["repos/carbonphysicsai/Carbon/rulesets/41"] = detail
    responses["PATCH repos/carbonphysicsai/Carbon"] = {"id": 1}
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        artifact,
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert (plan.ruleset_action, plan.settings_action) == ("NOOP", "PATCH")

    with pytest.raises(ruleset_module.RulesetError, match="plan changed"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert all(method == "GET" for method, _, _ in client.calls)


def test_ruleset_state_digest_covers_writable_state_not_response_metadata() -> None:
    artifact = _artifact()
    first = json.loads(json.dumps(artifact["ruleset"]))
    first.update({"id": 41, "updated_at": "2026-09-01T00:00:00Z"})
    reordered = json.loads(json.dumps(first))
    reordered["id"] = 42
    reordered["updated_at"] = "2026-09-01T00:01:00Z"
    reordered["rules"].reverse()
    checks = next(
        rule for rule in reordered["rules"] if rule["type"] == "required_status_checks"
    )
    checks["parameters"]["required_status_checks"].reverse()
    first_state = ruleset_module._ruleset_mutation_state(first, artifact["ruleset"])
    reordered_state = ruleset_module._ruleset_mutation_state(
        reordered, artifact["ruleset"]
    )
    assert ruleset_module._observation_digest(
        first_state
    ) == ruleset_module._observation_digest(reordered_state)

    extra = json.loads(json.dumps(first))
    extra["rules"].append(
        {
            "type": "future_rule",
            "parameters": {"mode": "first", "ordered_steps": ["one", "two"]},
        }
    )
    changed_extra = json.loads(json.dumps(extra))
    changed_extra["rules"][-1]["parameters"]["mode"] = "second"
    assert ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(extra, artifact["ruleset"])
    ) != ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(changed_extra, artifact["ruleset"])
    )
    reordered_extra = json.loads(json.dumps(extra))
    reordered_extra["rules"][-1]["parameters"]["ordered_steps"].reverse()
    assert ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(extra, artifact["ruleset"])
    ) != ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(reordered_extra, artifact["ruleset"])
    )

    missing = json.loads(json.dumps(first))
    missing.pop("enforcement")
    explicit_null = json.loads(json.dumps(first))
    explicit_null["enforcement"] = None
    assert ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(missing, artifact["ruleset"])
    ) != ruleset_module._observation_digest(
        ruleset_module._ruleset_mutation_state(explicit_null, artifact["ruleset"])
    )


def test_transition_drift_after_ruleset_success_stops_before_settings() -> None:
    artifact = _artifact()
    summary = {
        "id": 7,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    repository_before = _base_responses()["repos/carbonphysicsai/Carbon"]
    repository_after = dict(repository_before)
    repository_after.update({"allow_squash_merge": False, "allow_rebase_merge": False})
    responses = _base_responses()
    responses.update(
        {
            "repos/carbonphysicsai/Carbon": ResponseSequence(
                repository_before, repository_after
            ),
            RULESET_LIST_ENDPOINT: ResponseSequence([], [summary]),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                [], _effective_rules(artifact, ruleset_id=7)
            ),
            "repos/carbonphysicsai/Carbon/rulesets/7": detail,
            "POST repos/carbonphysicsai/Carbon/rulesets": detail,
        }
    )
    client = FakeClient(responses)
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE") as caught:
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    assert "between ruleset and repository-settings mutations" in str(caught.value)
    assert [call for call in client.calls if call[0] != "GET"] == [
        (
            "POST",
            "repos/carbonphysicsai/Carbon/rulesets",
            artifact["ruleset"],
        )
    ]


def test_transition_refuses_changed_settings_with_same_patch_action() -> None:
    artifact = _artifact()
    summary = {
        "id": 7,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    prior = _base_responses()["repos/carbonphysicsai/Carbon"]
    concurrent = dict(prior)
    concurrent["allow_squash_merge"] = False
    responses = _base_responses()
    responses.update(
        {
            "repos/carbonphysicsai/Carbon": ResponseSequence(prior, prior, concurrent),
            RULESET_LIST_ENDPOINT: ResponseSequence([], [], [summary]),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                [], [], _effective_rules(artifact, ruleset_id=7)
            ),
            "repos/carbonphysicsai/Carbon/rulesets/7": detail,
            "POST repos/carbonphysicsai/Carbon/rulesets": detail,
            "PATCH repos/carbonphysicsai/Carbon": {"id": 1},
        }
    )
    client = FakeClient(responses)
    plan = ruleset_module.build_plan(
        client,
        artifact,
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    assert (plan.ruleset_action, plan.settings_action) == ("CREATE", "PATCH")

    with pytest.raises(ruleset_module.RulesetError, match="APPLY INCOMPLETE") as caught:
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())

    assert "between ruleset and repository-settings mutations" in str(caught.value)
    assert [call for call in client.calls if call[0] != "GET"] == [
        (
            "POST",
            "repos/carbonphysicsai/Carbon/rulesets",
            artifact["ruleset"],
        )
    ]


def test_apply_cli_requires_live_pr_number() -> None:
    with pytest.raises(SystemExit):
        ruleset_module._parse_args(
            [
                "--apply",
                "--expected-main",
                MAIN_SHA,
                "--merge-gate-sha",
                CANDIDATE_SHA,
            ]
        )
    parsed = ruleset_module._parse_args(
        [
            "--apply",
            "--expected-main",
            MAIN_SHA,
            "--merge-gate-sha",
            CANDIDATE_SHA,
            "--pr-number",
            str(PR_NUMBER),
        ]
    )
    assert parsed.pr_number == PR_NUMBER


def test_dry_run_is_get_only_and_does_not_require_clean_local_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(_base_responses())
    git = FakeGit(status=" M local.py\n")
    monkeypatch.setattr(ruleset_module, "GhClient", lambda: client)
    monkeypatch.setattr(ruleset_module, "GitClient", lambda: git)
    assert (
        ruleset_module.main(
            [
                "--dry-run",
                "--expected-main",
                MAIN_SHA,
                "--merge-gate-sha",
                CANDIDATE_SHA,
                "--pr-number",
                str(PR_NUMBER),
            ]
        )
        == 0
    )
    assert git.calls == []
    assert all(method == "GET" for method, _, _ in client.calls)


def test_effective_rules_accept_exact_managed_contract() -> None:
    artifact = _artifact()
    ruleset_module._verify_effective_rules(
        _effective_rules(artifact),
        artifact["ruleset"],
        41,
        require_managed=True,
    )


def test_effective_rules_refuse_inherited_linear_history() -> None:
    artifact = _artifact()
    effective = _effective_rules(artifact)
    effective.append({"type": "required_linear_history", "ruleset_id": 99})
    with pytest.raises(ruleset_module.RulesetError, match="incompatible .* type"):
        ruleset_module._verify_effective_rules(
            effective, artifact["ruleset"], 41, require_managed=True
        )


def test_effective_rules_refuse_inherited_human_approval() -> None:
    artifact = _artifact()
    effective = _effective_rules(artifact)
    inherited = next(
        json.loads(json.dumps(item))
        for item in artifact["ruleset"]["rules"]
        if item["type"] == "pull_request"
    )
    inherited["ruleset_id"] = 99
    inherited["parameters"]["required_approving_review_count"] = 2
    effective.append(inherited)
    with pytest.raises(ruleset_module.RulesetError, match="human approval count"):
        ruleset_module._verify_effective_rules(
            effective, artifact["ruleset"], 41, require_managed=True
        )


def test_effective_rules_refuse_extra_inherited_required_check() -> None:
    artifact = _artifact()
    effective = _effective_rules(artifact)
    inherited = next(
        json.loads(json.dumps(item))
        for item in artifact["ruleset"]["rules"]
        if item["type"] == "required_status_checks"
    )
    inherited["ruleset_id"] = 99
    inherited["parameters"]["required_status_checks"].append(
        {"context": "Unexpected", "integration_id": 15368}
    )
    effective.append(inherited)
    with pytest.raises(ruleset_module.RulesetError, match="outside exact"):
        ruleset_module._verify_effective_rules(
            effective, artifact["ruleset"], 41, require_managed=True
        )


def test_post_apply_verification_refuses_incompatible_inherited_rule() -> None:
    artifact = _artifact()
    summary = {
        "id": 41,
        "name": "Carbon main merge gate",
        "source": "carbonphysicsai/Carbon",
        "source_type": "Repository",
    }
    detail = json.loads(json.dumps(artifact["ruleset"]))
    detail.update(summary)
    responses = _base_responses(rulesets=[summary])
    responses["repos/carbonphysicsai/Carbon"].update(
        {"allow_squash_merge": False, "allow_rebase_merge": False}
    )
    responses["repos/carbonphysicsai/Carbon/rulesets/41"] = detail
    responses[EFFECTIVE_RULES_ENDPOINT] = [
        *_effective_rules(artifact),
        {"type": "required_linear_history", "ruleset_id": 99},
    ]
    plan = _plan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="NOOP",
        ruleset_id=41,
        settings_action="NOOP",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="incompatible .* type"):
        ruleset_module.verify_applied(FakeClient(responses), artifact, plan)
