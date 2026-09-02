#!/usr/bin/env python3
"""Dry-run, apply, and verify Carbon's versioned GitHub main ruleset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT = REPOSITORY_ROOT / ".github" / "rulesets" / "main.v1.json"
EXPECTED_REPOSITORY = "carbonphysicsai/Carbon"
EXPECTED_RULESET_NAME = "Carbon main merge gate"
GITHUB_ACTIONS_APP_ID = 15368
PAGE_SIZE = 100
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

EXPECTED_PULL_REQUEST_PARAMETERS = {
    "allowed_merge_methods": ["merge"],
    "dismiss_stale_reviews_on_push": True,
    "require_code_owner_review": False,
    "require_last_push_approval": True,
    "required_approving_review_count": 1,
    "required_review_thread_resolution": True,
}
EXPECTED_REQUIRED_CHECKS = (
    {"context": "GPT review gate", "integration_id": GITHUB_ACTIONS_APP_ID},
    {"context": "Merge gate", "integration_id": GITHUB_ACTIONS_APP_ID},
)
EXPECTED_STATUS_CHECK_PARAMETERS = {
    "do_not_enforce_on_create": False,
    "strict_required_status_checks_policy": True,
    "required_status_checks": list(EXPECTED_REQUIRED_CHECKS),
}
EXPECTED_RULE_TYPES = {
    "deletion",
    "non_fast_forward",
    "pull_request",
    "required_status_checks",
}
EXPECTED_REPOSITORY_SETTINGS = {
    "allow_merge_commit": True,
    "allow_squash_merge": False,
    "allow_rebase_merge": False,
    "allow_auto_merge": False,
}


class RulesetError(RuntimeError):
    """The requested ruleset operation cannot be completed safely."""


class GhClient:
    """Small JSON-only wrapper around the authenticated GitHub CLI."""

    def request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        command = [
            "gh",
            "api",
            "--header",
            "Accept: application/vnd.github+json",
            "--header",
            "X-GitHub-Api-Version: 2022-11-28",
        ]
        if method != "GET":
            command.extend(("--method", method))
        if payload is not None:
            command.extend(("--input", "-"))
        command.append(endpoint)
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip() or "no output"
            raise RulesetError(f"GitHub API {method} {endpoint} failed: {detail}")
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise RulesetError(
                f"GitHub API {method} {endpoint} did not return JSON"
            ) from exc


class GitClient:
    """Small local Git wrapper used only by guarded apply mode."""

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )


@dataclass(frozen=True)
class RulesetPlan:
    repository: str
    ruleset_action: str
    ruleset_id: int | None
    ruleset_state_sha256: str
    settings_action: str
    settings_state_sha256: str
    expected_main: str | None
    merge_gate_sha: str | None
    pr_number: int | None = None


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RulesetError(f"{label} must be a JSON object")
    return value


def load_artifact(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RulesetError(f"Cannot read ruleset artifact {path}: {exc}") from exc
    artifact = _require_mapping(value, "ruleset artifact")
    if set(artifact) != {
        "artifact_version",
        "api_version",
        "repository",
        "ruleset",
        "repository_settings",
    }:
        raise RulesetError("ruleset artifact has an unexpected field inventory")
    if (
        type(artifact.get("artifact_version")) is not int
        or artifact.get("artifact_version") != 1
    ):
        raise RulesetError("ruleset artifact_version must be 1")
    if artifact.get("api_version") != "2022-11-28":
        raise RulesetError("ruleset api_version must be 2022-11-28")
    if artifact.get("repository") != EXPECTED_REPOSITORY:
        raise RulesetError(f"ruleset repository must be exactly {EXPECTED_REPOSITORY}")
    ruleset = _require_mapping(artifact.get("ruleset"), "ruleset")
    settings = _require_mapping(
        artifact.get("repository_settings"), "repository_settings"
    )
    if set(ruleset) != {
        "name",
        "target",
        "enforcement",
        "bypass_actors",
        "conditions",
        "rules",
    }:
        raise RulesetError("managed ruleset has an unexpected field inventory")
    if ruleset.get("name") != EXPECTED_RULESET_NAME:
        raise RulesetError(f"managed ruleset name must be {EXPECTED_RULESET_NAME!r}")
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        raise RulesetError("managed ruleset must be an active branch ruleset")
    if ruleset.get("bypass_actors") != []:
        raise RulesetError("managed ruleset must not grant bypass actors")
    conditions = _require_mapping(ruleset.get("conditions"), "ruleset.conditions")
    if conditions != {"ref_name": {"include": ["refs/heads/main"], "exclude": []}}:
        raise RulesetError("managed ruleset must target only refs/heads/main")
    rules = ruleset.get("rules")
    if not isinstance(rules, list) or not all(isinstance(item, dict) for item in rules):
        raise RulesetError("managed ruleset rules must be JSON objects")
    rule_types = [item.get("type") for item in rules]
    if (
        not all(isinstance(rule_type, str) for rule_type in rule_types)
        or set(rule_types) != EXPECTED_RULE_TYPES
        or len(rule_types) != len(EXPECTED_RULE_TYPES)
    ):
        raise RulesetError("managed ruleset has an unexpected rule inventory")
    rules_by_type = {str(item["type"]): item for item in rules}
    for rule_type in ("deletion", "non_fast_forward"):
        if rules_by_type[rule_type] != {"type": rule_type}:
            raise RulesetError(f"{rule_type} rule has unexpected fields")
    pull_request = next(item for item in rules if item["type"] == "pull_request")
    if set(pull_request) != {"type", "parameters"}:
        raise RulesetError("pull_request rule has unexpected fields")
    pull_parameters = _require_mapping(
        pull_request.get("parameters"), "pull_request.parameters"
    )
    if (
        pull_parameters != EXPECTED_PULL_REQUEST_PARAMETERS
        or type(pull_parameters.get("required_approving_review_count")) is not int
        or any(
            pull_parameters.get(field) is not expected
            for field, expected in (
                ("dismiss_stale_reviews_on_push", True),
                ("require_code_owner_review", False),
                ("require_last_push_approval", True),
                ("required_review_thread_resolution", True),
            )
        )
    ):
        raise RulesetError(
            "pull_request parameters do not match the managed merge contract"
        )
    checks_rule = next(
        item for item in rules if item["type"] == "required_status_checks"
    )
    if set(checks_rule) != {"type", "parameters"}:
        raise RulesetError("required_status_checks rule has unexpected fields")
    check_parameters = _require_mapping(
        checks_rule.get("parameters"), "required_status_checks.parameters"
    )
    if set(check_parameters) != set(EXPECTED_STATUS_CHECK_PARAMETERS):
        raise RulesetError("required_status_checks parameters have unexpected fields")
    if check_parameters.get("do_not_enforce_on_create") is not False:
        raise RulesetError("required checks must be enforced on branch creation")
    if check_parameters.get("strict_required_status_checks_policy") is not True:
        raise RulesetError("required checks must use the strict status policy")
    checks = check_parameters.get("required_status_checks")
    if not isinstance(checks, list) or len(checks) != len(EXPECTED_REQUIRED_CHECKS):
        raise RulesetError("required checks must be Merge gate and GPT review gate")
    normalized_checks: list[tuple[str, int]] = []
    for item in checks:
        if not isinstance(item, dict) or set(item) != {"context", "integration_id"}:
            raise RulesetError("required check entries have unexpected fields")
        context = item.get("context")
        integration_id = item.get("integration_id")
        if not isinstance(context, str) or type(integration_id) is not int:
            raise RulesetError("required check identities are malformed")
        normalized_checks.append((context, integration_id))
    expected_checks = sorted(
        (str(item["context"]), int(item["integration_id"]))
        for item in EXPECTED_REQUIRED_CHECKS
    )
    if sorted(normalized_checks) != expected_checks:
        raise RulesetError("required checks must be Merge gate and GPT review gate")
    if settings != EXPECTED_REPOSITORY_SETTINGS or any(
        type(setting) is not bool for setting in settings.values()
    ):
        raise RulesetError(
            "repository merge settings do not match the managed contract"
        )
    return artifact


def _selected_mapping(value: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys}


def _repository_settings_values(
    value: Mapping[str, Any], desired: Mapping[str, Any]
) -> dict[str, bool]:
    selected: dict[str, bool] = {}
    for field in desired:
        current = value.get(field)
        if type(current) is not bool:
            raise RulesetError(
                f"live repository setting {field} is missing or is not boolean"
            )
        selected[field] = current
    return selected


def _integration_sort_key(value: Any) -> tuple[int, int, str]:
    if value is None:
        return (0, 0, "")
    if type(value) is int:
        return (1, value, "")
    return (2, 0, str(value))


def normalize_ruleset(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize GitHub-added fields while retaining every managed value."""

    normalized_rules: list[dict[str, Any]] = []
    for raw_rule in value.get("rules", []):
        if not isinstance(raw_rule, dict):
            continue
        rule_type = raw_rule.get("type")
        rule: dict[str, Any] = {"type": rule_type}
        parameters = raw_rule.get("parameters")
        if rule_type == "pull_request" and isinstance(parameters, dict):
            rule["parameters"] = _selected_mapping(
                parameters,
                (
                    "allowed_merge_methods",
                    "dismiss_stale_reviews_on_push",
                    "require_code_owner_review",
                    "require_last_push_approval",
                    "required_approving_review_count",
                    "required_review_thread_resolution",
                ),
            )
        elif rule_type == "required_status_checks" and isinstance(parameters, dict):
            selected = _selected_mapping(
                parameters,
                (
                    "do_not_enforce_on_create",
                    "strict_required_status_checks_policy",
                ),
            )
            selected["required_status_checks"] = sorted(
                (
                    {
                        "context": item.get("context"),
                        "integration_id": item.get("integration_id"),
                    }
                    for item in parameters.get("required_status_checks", [])
                    if isinstance(item, dict)
                ),
                key=lambda item: (
                    str(item["context"]),
                    _integration_sort_key(item["integration_id"]),
                ),
            )
            rule["parameters"] = selected
        normalized_rules.append(rule)
    conditions = value.get("conditions", {})
    ref_name = conditions.get("ref_name", {}) if isinstance(conditions, dict) else {}
    return {
        "name": value.get("name"),
        "target": value.get("target"),
        "enforcement": value.get("enforcement"),
        "bypass_actors": value.get("bypass_actors", []),
        "conditions": {
            "ref_name": {
                "include": ref_name.get("include", []),
                "exclude": ref_name.get("exclude", []),
            }
        },
        "rules": sorted(normalized_rules, key=lambda item: str(item["type"])),
    }


def _canonical_observation(value: Any) -> Any:
    """Canonicalize JSON mappings while preserving potentially meaningful arrays."""

    if isinstance(value, Mapping):
        return {str(key): _canonical_observation(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_observation(item) for item in value]
    return value


def _sorted_observation_list(value: Sequence[Any]) -> list[Any]:
    items = [_canonical_observation(item) for item in value]
    return sorted(
        items,
        key=lambda item: json.dumps(
            item,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def _observation_digest(value: Any) -> str:
    """Return one stable token for an exact mutable live-state observation."""

    encoded = json.dumps(
        _canonical_observation(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ruleset_mutation_state(
    value: Mapping[str, Any] | None, desired: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Select every field the desired ruleset PUT would overwrite."""

    if value is None:
        return None
    state = _canonical_observation({key: value.get(key) for key in desired})
    if not isinstance(state, dict):
        raise RulesetError("managed ruleset mutation state is not an object")
    state["__present_fields__"] = sorted(key for key in desired if key in value)
    bypass_actors = state.get("bypass_actors")
    if isinstance(bypass_actors, list):
        state["bypass_actors"] = _sorted_observation_list(bypass_actors)
    conditions = state.get("conditions")
    if isinstance(conditions, dict):
        ref_name = conditions.get("ref_name")
        if isinstance(ref_name, dict):
            for field in ("include", "exclude"):
                values = ref_name.get(field)
                if isinstance(values, list):
                    ref_name[field] = _sorted_observation_list(values)
    rules = state.get("rules")
    if isinstance(rules, list):
        normalized_rules: list[Any] = []
        for raw_rule in rules:
            if not isinstance(raw_rule, dict):
                normalized_rules.append(raw_rule)
                continue
            rule = dict(raw_rule)
            parameters = rule.get("parameters")
            if isinstance(parameters, dict):
                parameters = dict(parameters)
                if rule.get("type") == "pull_request":
                    methods = parameters.get("allowed_merge_methods")
                    if isinstance(methods, list):
                        parameters["allowed_merge_methods"] = _sorted_observation_list(
                            methods
                        )
                elif rule.get("type") == "required_status_checks":
                    checks = parameters.get("required_status_checks")
                    if isinstance(checks, list):
                        parameters["required_status_checks"] = _sorted_observation_list(
                            checks
                        )
                rule["parameters"] = parameters
            normalized_rules.append(rule)
        state["rules"] = _sorted_observation_list(normalized_rules)
    return state


def _repo_endpoint(repository: str, suffix: str = "") -> str:
    return f"repos/{repository}{suffix}"


def _repository_owned(summary: Mapping[str, Any], repository: str) -> bool:
    source_type = str(summary.get("source_type", "")).lower()
    source = str(summary.get("source", ""))
    return source_type == "repository" and source.lower() in {
        repository.lower(),
        repository.split("/", 1)[1].lower(),
    }


def _paginated_list(client: GhClient, endpoint: str, label: str) -> list[Any]:
    values: list[Any] = []
    page = 1
    separator = "&" if "?" in endpoint else "?"
    while True:
        current = client.request(
            f"{endpoint}{separator}per_page={PAGE_SIZE}&page={page}"
        )
        if not isinstance(current, list):
            raise RulesetError(f"{label} was not an array")
        values.extend(current)
        if len(current) < PAGE_SIZE:
            return values
        page += 1


def _find_managed_ruleset(
    client: GhClient, repository: str, name: str
) -> tuple[int | None, dict[str, Any] | None]:
    summaries = _paginated_list(
        client,
        _repo_endpoint(repository, "/rulesets?includes_parents=true"),
        "GitHub ruleset listing",
    )
    named = [
        item
        for item in summaries
        if isinstance(item, dict) and item.get("name") == name
    ]
    owned = [item for item in named if _repository_owned(item, repository)]
    inherited = [item for item in named if item not in owned]
    if inherited:
        raise RulesetError(
            "an inherited ruleset uses the managed name; refusing mutation"
        )
    if len(owned) > 1:
        raise RulesetError("multiple repository rulesets use the managed name")
    if not owned:
        return None, None
    ruleset_id = owned[0].get("id")
    if type(ruleset_id) is not int:
        raise RulesetError("managed ruleset summary has no numeric id")
    detail = client.request(_repo_endpoint(repository, f"/rulesets/{ruleset_id}"))
    return ruleset_id, _require_mapping(detail, "managed ruleset detail")


def _verify_admin(repository_data: Mapping[str, Any]) -> None:
    permissions = repository_data.get("permissions")
    if not isinstance(permissions, dict) or permissions.get("admin") is not True:
        raise RulesetError(
            "authenticated credentials do not have repository administration"
        )


def _require_sha(value: str, label: str) -> str:
    if SHA_PATTERN.fullmatch(value) is None:
        raise RulesetError(f"{label} must be an exact lowercase 40-character SHA")
    return value


def _verify_main_guard(
    client: GhClient, repository: str, expected_main: str | None
) -> None:
    if expected_main is None:
        return
    _require_sha(expected_main, "expected main")
    branch = _require_mapping(
        client.request(_repo_endpoint(repository, "/branches/main")), "main branch"
    )
    commit = _require_mapping(branch.get("commit"), "main branch commit")
    if commit.get("sha") != expected_main:
        raise RulesetError(
            f"main changed: expected {expected_main}, found {commit.get('sha')}"
        )


def _github_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise RulesetError(f"Merge gate check run has no valid {label} timestamp")
    encoded = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(encoded)
    except ValueError as exc:
        raise RulesetError(
            f"Merge gate check run has no valid {label} timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RulesetError(f"Merge gate check run has no valid {label} timestamp")
    return parsed.astimezone(UTC)


def _merge_gate_started_at(item: Mapping[str, Any]) -> datetime:
    started_at = _github_timestamp(item.get("started_at"), "started_at")
    completed_at = item.get("completed_at")
    if item.get("status") == "completed":
        completed = _github_timestamp(completed_at, "completed_at")
        if completed < started_at:
            raise RulesetError("Merge gate check run completed_at precedes started_at")
    elif completed_at is not None:
        raise RulesetError("current Merge gate check run unexpectedly has completed_at")
    return started_at


def _verify_merge_gate(
    client: GhClient, repository: str, merge_gate_sha: str | None
) -> None:
    if merge_gate_sha is None:
        return
    _require_sha(merge_gate_sha, "merge-gate SHA")
    endpoint = _repo_endpoint(
        repository,
        (
            f"/commits/{merge_gate_sha}/check-runs"
            f"?check_name=Merge%20gate&filter=latest&app_id={GITHUB_ACTIONS_APP_ID}"
        ),
    )
    matches: list[dict[str, Any]] = []
    total_count: int | None = None
    page = 1
    while True:
        response = _require_mapping(
            client.request(f"{endpoint}&per_page={PAGE_SIZE}&page={page}"),
            "candidate check-runs",
        )
        current_total = response.get("total_count")
        if type(current_total) is not int or current_total < 0:
            raise RulesetError("candidate check-runs had no valid total_count")
        if total_count is None:
            total_count = current_total
        elif current_total != total_count:
            raise RulesetError("latest Merge gate set changed during pagination")
        check_runs = response.get("check_runs")
        if not isinstance(check_runs, list):
            raise RulesetError("candidate check-runs did not contain an array")
        for item in check_runs:
            if not isinstance(item, dict) or item.get("name") != "Merge gate":
                raise RulesetError("latest Merge gate query returned a foreign check")
            app = item.get("app")
            if not isinstance(app, dict) or app.get("id") != GITHUB_ACTIONS_APP_ID:
                raise RulesetError("latest Merge gate query returned a foreign app")
            if item.get("head_sha") != merge_gate_sha:
                raise RulesetError(
                    "GitHub returned a Merge gate check for the wrong candidate SHA"
                )
            run_id = item.get("id")
            if type(run_id) is not int or run_id <= 0:
                raise RulesetError("Merge gate check run has no valid numeric id")
            matches.append(item)
        if len(matches) > total_count:
            raise RulesetError("latest Merge gate pagination exceeded total_count")
        if len(matches) == total_count:
            break
        if len(check_runs) != PAGE_SIZE:
            raise RulesetError("latest Merge gate pagination ended before total_count")
        page += 1
    if not matches:
        raise RulesetError(f"no GitHub Actions Merge gate exists on {merge_gate_sha}")
    timestamped = [(_merge_gate_started_at(item), item) for item in matches]
    timestamped.sort(key=lambda pair: pair[0])
    if len(timestamped) > 1 and timestamped[-1][0] == timestamped[-2][0]:
        raise RulesetError("latest GitHub Actions Merge gate timestamp is ambiguous")
    latest = timestamped[-1][1]
    if latest.get("status") != "completed":
        raise RulesetError(
            "latest GitHub Actions Merge gate is still current "
            f"(id={latest['id']}, status={latest.get('status')})"
        )
    if latest.get("conclusion") != "success":
        raise RulesetError(
            "latest GitHub Actions Merge gate on "
            f"{merge_gate_sha} is not successful "
            f"(id={latest['id']}, status={latest.get('status')}, "
            f"conclusion={latest.get('conclusion')})"
        )


def _git_output(git: GitClient, *arguments: str, label: str) -> str:
    result = git.run(*arguments)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise RulesetError(f"local Git {label} failed: {detail}")
    return result.stdout.strip()


def _verify_local_candidate(
    git: GitClient, *, expected_main: str, merge_gate_sha: str
) -> None:
    """Bind an apply request to this clean checkout and its current main base."""

    _require_sha(expected_main, "expected main")
    _require_sha(merge_gate_sha, "merge-gate SHA")
    status = _git_output(
        git,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        label="status",
    )
    if status:
        raise RulesetError("local checkout is not clean; refusing ruleset mutation")
    head = _git_output(
        git, "rev-parse", "--verify", "HEAD^{commit}", label="HEAD resolution"
    )
    _require_sha(head, "local HEAD")
    if head != merge_gate_sha:
        raise RulesetError(
            f"merge-gate SHA must equal local HEAD: expected {head}, got {merge_gate_sha}"
        )
    origin_main = _git_output(
        git,
        "rev-parse",
        "--verify",
        "refs/remotes/origin/main^{commit}",
        label="origin/main resolution",
    )
    _require_sha(origin_main, "local origin/main")
    if origin_main != expected_main:
        raise RulesetError(
            f"expected main must equal local origin/main: expected {origin_main}, "
            f"got {expected_main}"
        )
    ancestry = git.run("merge-base", "--is-ancestor", expected_main, merge_gate_sha)
    if ancestry.returncode == 1:
        raise RulesetError("current origin/main is not an ancestor of local HEAD")
    if ancestry.returncode != 0:
        detail = ancestry.stderr.strip() or ancestry.stdout.strip() or "no output"
        raise RulesetError(f"local Git ancestry check failed: {detail}")


def _verify_live_pr(
    client: GhClient,
    repository: str,
    *,
    pr_number: int,
    expected_main: str,
    merge_gate_sha: str,
) -> None:
    if type(pr_number) is not int or pr_number <= 0:
        raise RulesetError("PR number must be a positive integer")
    pull = _require_mapping(
        client.request(_repo_endpoint(repository, f"/pulls/{pr_number}")),
        "guarded pull request",
    )
    if pull.get("number") != pr_number:
        raise RulesetError("live pull request number does not match --pr-number")
    base = _require_mapping(pull.get("base"), "guarded pull request base")
    base_repo = _require_mapping(base.get("repo"), "guarded base repository")
    head = _require_mapping(pull.get("head"), "guarded pull request head")
    head_repo = _require_mapping(head.get("repo"), "guarded head repository")
    if (
        base_repo.get("full_name") != EXPECTED_REPOSITORY
        or base.get("ref") != "main"
        or head_repo.get("full_name") != EXPECTED_REPOSITORY
    ):
        raise RulesetError(
            "guarded pull request must be an in-repository change targeting main"
        )
    if pull.get("state") == "open":
        if pull.get("draft") is not False:
            raise RulesetError("open guarded pull request must be non-draft")
        if base.get("sha") != expected_main or head.get("sha") != merge_gate_sha:
            raise RulesetError(
                "open guarded pull request must bind current main and the exact candidate"
            )
        return
    if (
        pull.get("state") == "closed"
        and isinstance(pull.get("merged_at"), str)
        and bool(pull.get("merged_at"))
        and pull.get("merge_commit_sha") == expected_main
        and merge_gate_sha == expected_main
    ):
        merged_head = _require_sha(head.get("sha"), "merged pull request head")
        merge_commit = _require_mapping(
            client.request(_repo_endpoint(repository, f"/commits/{expected_main}")),
            "guarded merge commit",
        )
        if (
            _require_sha(merge_commit.get("sha"), "guarded merge commit SHA")
            != expected_main
        ):
            raise RulesetError("guarded merge commit does not match exact checked main")
        parents = merge_commit.get("parents")
        if not isinstance(parents, list) or len(parents) != 2:
            raise RulesetError(
                "guarded governance PR must use a normal two-parent merge"
            )
        second_parent = _require_mapping(parents[1], "guarded merge second parent")
        if (
            _require_sha(second_parent.get("sha"), "guarded merge second parent SHA")
            != merged_head
        ):
            raise RulesetError(
                "guarded merge second parent must equal the reviewed PR head"
            )
        return
    raise RulesetError(
        "guarded pull request must be open on the exact candidate or normally "
        "merged as the exact checked main"
    )


def build_plan(
    client: GhClient,
    artifact: Mapping[str, Any],
    *,
    expected_main: str | None,
    merge_gate_sha: str | None,
    pr_number: int | None = None,
) -> RulesetPlan:
    guard_values = (expected_main, merge_gate_sha, pr_number)
    if any(value is not None for value in guard_values) and not all(
        value is not None for value in guard_values
    ):
        raise RulesetError(
            "expected main, merge-gate SHA, and PR number must be supplied together"
        )
    if (
        expected_main is not None
        and merge_gate_sha is not None
        and pr_number is not None
    ):
        _require_sha(expected_main, "expected main")
        _require_sha(merge_gate_sha, "merge-gate SHA")
        if type(pr_number) is not int or pr_number <= 0:
            raise RulesetError("PR number must be a positive integer")
    repository = str(artifact["repository"])
    repository_data = _require_mapping(
        client.request(_repo_endpoint(repository)), "repository"
    )
    _verify_admin(repository_data)
    desired_ruleset = _require_mapping(artifact["ruleset"], "ruleset")
    ruleset_id, current_ruleset = _find_managed_ruleset(
        client, repository, str(desired_ruleset["name"])
    )
    if current_ruleset is None:
        ruleset_action = "CREATE"
    elif normalize_ruleset(current_ruleset) == normalize_ruleset(desired_ruleset):
        ruleset_action = "NOOP"
    else:
        ruleset_action = "UPDATE"
    settings = _require_mapping(artifact["repository_settings"], "repository_settings")
    current_settings = _repository_settings_values(repository_data, settings)
    settings_action = "NOOP" if current_settings == settings else "PATCH"
    effective = _paginated_list(
        client,
        _repo_endpoint(repository, "/rules/branches/main"),
        "effective main rules",
    )
    _verify_effective_rules(
        effective,
        desired_ruleset,
        ruleset_id,
        require_managed=ruleset_action == "NOOP",
    )
    if merge_gate_sha is not None:
        _verify_merge_gate(client, repository, merge_gate_sha)
    if pr_number is not None:
        assert expected_main is not None and merge_gate_sha is not None
        _verify_live_pr(
            client,
            repository,
            pr_number=pr_number,
            expected_main=expected_main,
            merge_gate_sha=merge_gate_sha,
        )
    _verify_main_guard(client, repository, expected_main)
    plan = RulesetPlan(
        repository=repository,
        ruleset_action=ruleset_action,
        ruleset_id=ruleset_id,
        ruleset_state_sha256=_observation_digest(
            _ruleset_mutation_state(current_ruleset, desired_ruleset)
        ),
        settings_action=settings_action,
        settings_state_sha256=_observation_digest(current_settings),
        expected_main=expected_main,
        merge_gate_sha=merge_gate_sha,
        pr_number=pr_number,
    )
    return plan


def _require_unchanged_plan(
    expected: RulesetPlan, current: RulesetPlan, *, phase: str
) -> None:
    if current != expected:
        raise RulesetError(
            f"live ruleset plan changed {phase}; expected {expected}, found {current}"
        )


def apply_plan(
    client: GhClient,
    artifact: Mapping[str, Any],
    plan: RulesetPlan,
    *,
    git: GitClient,
) -> None:
    """Converge only toward the artifact and never issue a restorative write.

    Each pre-write replan compares canonical fingerprints of every mutable
    field, so distinct noncompliant states cannot collapse to the same action.
    GitHub does not provide a cross-endpoint transaction or conditional unsafe
    requests for these endpoints. Repository administrators must serialize with
    this operation. Once any forward mutation is attempted, failure stops the
    operation and a fresh guarded invocation must reconcile the live state.
    """

    if (
        plan.expected_main is None
        or plan.merge_gate_sha is None
        or plan.pr_number is None
    ):
        raise RulesetError("apply plan is missing exact main, candidate, or PR guards")
    if artifact.get("repository") != plan.repository:
        raise RulesetError("apply plan repository does not match the artifact")
    if plan.ruleset_action not in {"CREATE", "UPDATE", "NOOP"}:
        raise RulesetError(f"unexpected ruleset action {plan.ruleset_action!r}")
    if plan.settings_action not in {"PATCH", "NOOP"}:
        raise RulesetError(f"unexpected settings action {plan.settings_action!r}")
    for label, observation in (
        ("ruleset", plan.ruleset_state_sha256),
        ("repository-settings", plan.settings_state_sha256),
    ):
        if (
            not isinstance(observation, str)
            or DIGEST_PATTERN.fullmatch(observation) is None
        ):
            raise RulesetError(f"apply plan has no valid {label} observation")
    _verify_local_candidate(
        git,
        expected_main=plan.expected_main,
        merge_gate_sha=plan.merge_gate_sha,
    )
    current = build_plan(
        client,
        artifact,
        expected_main=plan.expected_main,
        merge_gate_sha=plan.merge_gate_sha,
        pr_number=plan.pr_number,
    )
    _require_unchanged_plan(plan, current, phase="before the first mutation")
    _verify_local_candidate(
        git,
        expected_main=plan.expected_main,
        merge_gate_sha=plan.merge_gate_sha,
    )
    ruleset = _require_mapping(artifact["ruleset"], "ruleset")
    live_ruleset_id = plan.ruleset_id
    written_ruleset: dict[str, Any] | None = None
    mutation_phase: str | None = None
    try:
        if plan.ruleset_action == "CREATE":
            mutation_phase = "managed-ruleset CREATE request"
            created = _require_mapping(
                client.request(
                    _repo_endpoint(plan.repository, "/rulesets"),
                    method="POST",
                    payload=ruleset,
                ),
                "created managed ruleset",
            )
            live_ruleset_id = created.get("id")
            if type(live_ruleset_id) is not int:
                raise RulesetError("created managed ruleset has no numeric id")
            written_ruleset = created
        elif plan.ruleset_action == "UPDATE":
            if plan.ruleset_id is None:
                raise RulesetError("UPDATE plan is missing the managed ruleset id")
            mutation_phase = "managed-ruleset UPDATE request"
            updated = _require_mapping(
                client.request(
                    _repo_endpoint(plan.repository, f"/rulesets/{plan.ruleset_id}"),
                    method="PUT",
                    payload=ruleset,
                ),
                "updated managed ruleset",
            )
            updated_ruleset_id = updated.get("id")
            if (
                type(updated_ruleset_id) is not int
                or updated_ruleset_id != plan.ruleset_id
            ):
                raise RulesetError("updated managed ruleset id changed unexpectedly")
            written_ruleset = updated
        if plan.settings_action == "PATCH":
            if plan.ruleset_action in {"CREATE", "UPDATE"}:
                if written_ruleset is None:
                    raise RulesetError(
                        "ruleset mutation returned no exact state observation"
                    )
                _verify_local_candidate(
                    git,
                    expected_main=plan.expected_main,
                    merge_gate_sha=plan.merge_gate_sha,
                )
                expected_transition = RulesetPlan(
                    repository=plan.repository,
                    ruleset_action="NOOP",
                    ruleset_id=live_ruleset_id,
                    ruleset_state_sha256=_observation_digest(
                        _ruleset_mutation_state(written_ruleset, ruleset)
                    ),
                    settings_action="PATCH",
                    settings_state_sha256=plan.settings_state_sha256,
                    expected_main=plan.expected_main,
                    merge_gate_sha=plan.merge_gate_sha,
                    pr_number=plan.pr_number,
                )
                current = build_plan(
                    client,
                    artifact,
                    expected_main=plan.expected_main,
                    merge_gate_sha=plan.merge_gate_sha,
                    pr_number=plan.pr_number,
                )
                _require_unchanged_plan(
                    expected_transition,
                    current,
                    phase="between ruleset and repository-settings mutations",
                )
                _verify_local_candidate(
                    git,
                    expected_main=plan.expected_main,
                    merge_gate_sha=plan.merge_gate_sha,
                )
            mutation_phase = "repository-settings PATCH request"
            client.request(
                _repo_endpoint(plan.repository),
                method="PATCH",
                payload=_require_mapping(
                    artifact["repository_settings"], "repository_settings"
                ),
            )
        verify_applied(client, artifact, plan)
    except RulesetError as exc:
        if mutation_phase is None:
            raise
        raise RulesetError(
            f"GitHub forward-only apply stopped after {mutation_phase}. APPLY "
            "INCOMPLETE; MANUAL RECOVERY MAY BE REQUIRED. No automatic rollback "
            "or restorative mutation was attempted because GitHub does not support "
            "atomic conditional writes for these endpoints. Live state may be "
            "unchanged or partially converged. Run a fresh guarded --dry-run, "
            "serialize repository administration, and rerun --apply with fresh "
            f"exact guards. Original failure: {exc}"
        ) from exc


def _normalized_single_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_ruleset({"rules": [dict(rule)]})["rules"]
    if len(normalized) != 1:
        raise RulesetError("could not normalize an effective main rule")
    return normalized[0]


def _check_identity(item: Any) -> tuple[str, int | None]:
    if not isinstance(item, dict) or "context" not in item:
        raise RulesetError("effective required check identity is malformed")
    context = item.get("context")
    integration_id = item.get("integration_id")
    if not isinstance(context, str):
        raise RulesetError("effective required check context is malformed")
    if integration_id is not None and type(integration_id) is not int:
        raise RulesetError("effective required check integration id is malformed")
    return context, integration_id


def _verify_effective_rules(
    effective: Sequence[Any],
    desired_ruleset: Mapping[str, Any],
    managed_ruleset_id: int | None,
    *,
    require_managed: bool,
) -> None:
    if require_managed and managed_ruleset_id is None:
        raise RulesetError("verified managed ruleset has no numeric id")
    rules: list[dict[str, Any]] = []
    for raw_rule in effective:
        if not isinstance(raw_rule, dict):
            raise RulesetError("effective main rule was not a JSON object")
        ruleset_id = raw_rule.get("ruleset_id")
        if type(ruleset_id) is not int:
            raise RulesetError("effective main rule has no numeric ruleset id")
        rule_type = raw_rule.get("type")
        if rule_type not in EXPECTED_RULE_TYPES:
            raise RulesetError(
                f"incompatible effective main rule type {rule_type!r} is active"
            )
        rules.append(raw_rule)

    desired_rules = desired_ruleset.get("rules")
    if not isinstance(desired_rules, list):
        raise RulesetError("desired ruleset rules were not an array")
    desired_by_type = {
        str(item.get("type")): item for item in desired_rules if isinstance(item, dict)
    }
    if managed_ruleset_id is not None:
        managed = [
            item for item in rules if item.get("ruleset_id") == managed_ruleset_id
        ]
        if require_managed:
            managed_types = [item.get("type") for item in managed]
            if set(managed_types) != EXPECTED_RULE_TYPES or len(managed_types) != len(
                EXPECTED_RULE_TYPES
            ):
                raise RulesetError("managed ruleset is not fully effective on main")
            for item in managed:
                rule_type = str(item["type"])
                if _normalized_single_rule(item) != _normalized_single_rule(
                    desired_by_type[rule_type]
                ):
                    raise RulesetError(
                        f"managed {rule_type} rule is not effective with exact parameters"
                    )

    effective_checks: set[tuple[str, int | None]] = set()
    for item in rules:
        rule_type = item["type"]
        if rule_type == "pull_request":
            parameters = _require_mapping(
                item.get("parameters"), "effective pull_request parameters"
            )
            methods = parameters.get("allowed_merge_methods")
            approval_count = parameters.get("required_approving_review_count")
            if not isinstance(methods, list) or "merge" not in methods:
                raise RulesetError(
                    "an effective pull_request rule blocks normal merge commits"
                )
            if type(approval_count) is not int or approval_count not in {0, 1}:
                raise RulesetError(
                    "an effective pull_request rule has an incompatible human approval count"
                )
            if parameters.get("require_code_owner_review") is not False:
                raise RulesetError(
                    "an effective pull_request rule enables incompatible "
                    "require_code_owner_review"
                )
            for field in (
                "dismiss_stale_reviews_on_push",
                "require_last_push_approval",
            ):
                if type(parameters.get(field)) is not bool:
                    raise RulesetError(
                        f"an effective pull_request rule has malformed {field}"
                    )
        elif rule_type == "required_status_checks":
            parameters = _require_mapping(
                item.get("parameters"),
                "effective required_status_checks parameters",
            )
            checks = parameters.get("required_status_checks")
            if not isinstance(checks, list):
                raise RulesetError("effective required checks were not an array")
            effective_checks.update(_check_identity(check) for check in checks)

    expected_checks = {
        (str(item["context"]), int(item["integration_id"]))
        for item in EXPECTED_REQUIRED_CHECKS
    }
    if not effective_checks.issubset(expected_checks):
        raise RulesetError(
            "effective required checks include checks outside exact Merge gate and GPT review policy"
        )
    if require_managed and effective_checks != expected_checks:
        raise RulesetError(
            "effective required checks differ from exact Merge gate and GPT review policy"
        )


def verify_applied(
    client: GhClient, artifact: Mapping[str, Any], plan: RulesetPlan
) -> None:
    repeated = build_plan(
        client,
        artifact,
        expected_main=plan.expected_main,
        merge_gate_sha=plan.merge_gate_sha,
        pr_number=plan.pr_number,
    )
    if repeated.ruleset_action != "NOOP" or repeated.settings_action != "NOOP":
        raise RulesetError(
            "live verification still reports ruleset or repository-settings drift"
        )
    effective = _paginated_list(
        client,
        _repo_endpoint(plan.repository, "/rules/branches/main"),
        "effective main rules",
    )
    _verify_effective_rules(
        effective,
        _require_mapping(artifact["ruleset"], "ruleset"),
        repeated.ruleset_id,
        require_managed=True,
    )


def _positive_pr_number(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("PR number must be an integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("PR number must be positive")
    return number


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Apply mode is restricted to an exact checked in-repository PR head or "
            "the exact checked main produced by that normally merged PR."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print the exact plan")
    mode.add_argument("--apply", action="store_true", help="apply and verify the plan")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument(
        "--expected-main",
        help="exact live and local origin/main SHA guard (required with --apply)",
    )
    parser.add_argument(
        "--merge-gate-sha",
        help=(
            "exact clean local HEAD with a successful latest Merge gate "
            "(required with --apply)"
        ),
    )
    parser.add_argument(
        "--pr-number",
        type=_positive_pr_number,
        help=(
            "guarded in-repository PR number; it must either be open at the clean "
            "local candidate or normally merged as the exact checked local main"
        ),
    )
    args = parser.parse_args(argv)
    guards = (args.expected_main, args.merge_gate_sha, args.pr_number)
    if args.apply and not all(value is not None for value in guards):
        parser.error(
            "--apply requires --expected-main, --merge-gate-sha, and --pr-number"
        )
    if (
        args.dry_run
        and any(value is not None for value in guards)
        and not all(value is not None for value in guards)
    ):
        parser.error(
            "guarded --dry-run requires --expected-main, --merge-gate-sha, and "
            "--pr-number together"
        )
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        artifact = load_artifact(args.artifact.resolve())
        client = GhClient()
        git = GitClient()
        if args.apply:
            _verify_local_candidate(
                git,
                expected_main=str(args.expected_main),
                merge_gate_sha=str(args.merge_gate_sha),
            )
        plan = build_plan(
            client,
            artifact,
            expected_main=args.expected_main,
            merge_gate_sha=args.merge_gate_sha,
            pr_number=args.pr_number,
        )
        print(json.dumps(plan.__dict__, indent=2, sort_keys=True))
        if args.dry_run:
            print("Dry run only; no GitHub setting was changed.")
            return 0
        apply_plan(client, artifact, plan, git=git)
        print("Carbon main ruleset and merge settings applied and verified.")
        return 0
    except RulesetError as exc:
        print(f"GitHub ruleset error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
