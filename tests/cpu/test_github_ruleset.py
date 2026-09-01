from __future__ import annotations

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
                return response.next(key)
            return response
        if endpoint in self.responses:
            response = self.responses[endpoint]
            if isinstance(response, ResponseSequence):
                return response.next(endpoint)
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
    assert pull_request["dismiss_stale_reviews_on_push"] is False
    assert pull_request["require_code_owner_review"] is False
    assert pull_request["require_last_push_approval"] is False
    assert pull_request["required_approving_review_count"] == 0
    assert pull_request["required_review_thread_resolution"] is True
    status_parameters = rules["required_status_checks"]["parameters"]
    assert status_parameters["do_not_enforce_on_create"] is False
    assert status_parameters["strict_required_status_checks_policy"] is True
    checks = {
        (item["context"], item["integration_id"])
        for item in status_parameters["required_status_checks"]
    }
    assert checks == {("Merge gate", 15368), ("Greptile Review", 867647)}
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
        ("draft", "open and non-draft"),
        ("closed", "open and non-draft"),
        ("missing_base", "pull request base must be a JSON object"),
        ("base_repository", "base must be current"),
        ("base_ref", "base must be current"),
        ("base_sha", "base must be current"),
        ("head_repository", "head must be the exact"),
        ("head_ref", "head must be the exact"),
        ("head_sha", "head must be the exact"),
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
    elif case == "head_ref":
        pull["head"]["ref"] = "agent/another-ticket"
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


def test_apply_uses_only_managed_endpoints() -> None:
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
    responses.update(
        {
            RULESET_LIST_ENDPOINT: ResponseSequence([], [summary]),
            EFFECTIVE_RULES_ENDPOINT: ResponseSequence(
                [], _effective_rules(artifact, ruleset_id=7)
            ),
            "repos/carbonphysicsai/Carbon/rulesets/7": detail,
            "POST repos/carbonphysicsai/Carbon/rulesets": summary,
            "PATCH repos/carbonphysicsai/Carbon": {"id": 1},
        }
    )
    client = FakeClient(responses)
    plan = ruleset_module.RulesetPlan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    assert [(method, endpoint) for method, endpoint, _ in client.calls] == [
        ("GET", "repos/carbonphysicsai/Carbon"),
        ("GET", RULESET_LIST_ENDPOINT),
        ("GET", EFFECTIVE_RULES_ENDPOINT),
        ("GET", CHECK_RUNS_ENDPOINT),
        ("GET", PR_ENDPOINT),
        ("GET", "repos/carbonphysicsai/Carbon/branches/main"),
        ("POST", "repos/carbonphysicsai/Carbon/rulesets"),
        ("GET", "repos/carbonphysicsai/Carbon"),
        ("GET", RULESET_LIST_ENDPOINT),
        ("GET", "repos/carbonphysicsai/Carbon/rulesets/7"),
        ("GET", EFFECTIVE_RULES_ENDPOINT),
        ("GET", CHECK_RUNS_ENDPOINT),
        ("GET", PR_ENDPOINT),
        ("GET", "repos/carbonphysicsai/Carbon/branches/main"),
        ("PATCH", "repos/carbonphysicsai/Carbon"),
    ]


def _write_artifact(tmp_path: Path, value: Mapping[str, Any]) -> Path:
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dismiss_stale_reviews_on_push", True),
        ("require_code_owner_review", True),
        ("require_last_push_approval", True),
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
    plan = ruleset_module.RulesetPlan(
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
    plan = ruleset_module.RulesetPlan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="exact in-repository"):
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
    inherited["parameters"]["required_approving_review_count"] = 1
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
    plan = ruleset_module.RulesetPlan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="human approvals"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    assert all(method == "GET" for method, _, _ in client.calls)


def test_apply_refuses_concurrent_settings_plan_drift_before_any_mutation() -> None:
    responses = _base_responses()
    responses["repos/carbonphysicsai/Carbon"].update(
        {"allow_squash_merge": False, "allow_rebase_merge": False}
    )
    responses["POST repos/carbonphysicsai/Carbon/rulesets"] = {"id": 7}
    client = FakeClient(responses)
    plan = ruleset_module.RulesetPlan(
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
    plan = ruleset_module.RulesetPlan(
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


def test_apply_rechecks_full_plan_between_separate_mutations() -> None:
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
            "POST repos/carbonphysicsai/Carbon/rulesets": summary,
            "PATCH repos/carbonphysicsai/Carbon": {"id": 1},
        }
    )
    client = FakeClient(responses)
    plan = ruleset_module.RulesetPlan(
        repository="carbonphysicsai/Carbon",
        ruleset_action="CREATE",
        ruleset_id=None,
        settings_action="PATCH",
        expected_main=MAIN_SHA,
        merge_gate_sha=CANDIDATE_SHA,
        pr_number=PR_NUMBER,
    )
    with pytest.raises(ruleset_module.RulesetError, match="between ruleset"):
        ruleset_module.apply_plan(client, artifact, plan, git=FakeGit())
    methods = [method for method, _, _ in client.calls]
    assert methods.count("POST") == 1
    assert "PATCH" not in methods
    assert client.calls[-1][:2] == (
        "GET",
        "repos/carbonphysicsai/Carbon/branches/main",
    )


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
    inherited["parameters"]["required_approving_review_count"] = 1
    effective.append(inherited)
    with pytest.raises(ruleset_module.RulesetError, match="human approvals"):
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
    plan = ruleset_module.RulesetPlan(
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
