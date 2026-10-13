#!/usr/bin/env python3
"""Bind CI's head and merge acceptance to immutable Git identities (PLT-12)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "carbon.ci-merge-receipt.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
JOB = re.compile(r"(.+) \((head|merge)(?:, ([0-5]))?\) \[([0-9a-f]{40})\]\Z")
FAMILIES = {
    "Canonical environment": 6,
    "Clean dev-container image": 6,
    "C-03/C-04/C-05/C-07/C-08/C-10 isolated service acceptance": 1,
    "Authored-Julia isolated service acceptance": 1,
    "Workbench release and application acceptance": 1,
    "Contract and authority acceptance": 1,
    "Development Hub validation": 1,
    "Derived documentation acceptance": 1,
}


class MergeError(RuntimeError):
    """No validated integration result can be claimed."""


def exact_sha(value: Any) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise MergeError("expected an exact lowercase commit SHA")
    return value


def git(repository: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise MergeError(f"Git {args[0]} failed: {process.stderr.strip()}")
    return process.stdout.strip()


def prepare(repository: Path, head: str, base: str, merge: str) -> dict[str, Any]:
    """Validate GitHub's proposed merge; never construct or substitute a head."""
    head, base, merge = map(exact_sha, (head, base, merge))
    for commit in (head, base, merge):
        if git(repository, "rev-parse", "--verify", commit + "^{commit}") != commit:
            raise MergeError("commit identity mismatch")
    parents = git(repository, "show", "-s", "--format=%P", merge).split()
    if parents != [base, head]:
        raise MergeError("merge must have exact ordered base/head parents")
    # git merge-tree does not change this checkout or create a branch. A
    # conflict returns nonzero; matching parent names alone cannot bless a
    # manually resolved, unrelated, or head-only tree.
    expected_tree = git(repository, "merge-tree", "--write-tree", base, head)
    merge_tree = git(repository, "rev-parse", merge + "^{tree}")
    if expected_tree != merge_tree:
        raise MergeError("merge tree differs from the clean base/head merge")
    return {
        "schema": SCHEMA,
        "head": {"sha": head, "tree": git(repository, "rev-parse", head + "^{tree}")},
        "base": {"sha": base, "tree": git(repository, "rev-parse", base + "^{tree}")},
        "merge": {"sha": merge, "tree": merge_tree, "parents": parents},
        "head_result": "PENDING",
        "merge_result": "PENDING",
        "classification": "INCOMPLETE",
        "gate_result": "PENDING",
        "required_jobs": {},
        "jobs": [],
    }


def check_receipt(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "head",
            "base",
            "merge",
            "head_result",
            "merge_result",
            "classification",
            "gate_result",
            "required_jobs",
            "jobs",
        }
        or value.get("schema") != SCHEMA
    ):
        raise MergeError("invalid merge receipt schema")
    for name in ("head", "base", "merge"):
        section = value.get(name)
        keys = {"sha", "tree", "parents"} if name == "merge" else {"sha", "tree"}
        if not isinstance(section, dict) or set(section) != keys:
            raise MergeError("invalid merge receipt identity")
        exact_sha(section["sha"])
        exact_sha(section["tree"])
    if value["merge"]["parents"] != [value["base"]["sha"], value["head"]["sha"]]:
        raise MergeError("invalid merge receipt parents")
    required = value["required_jobs"]
    if (
        not isinstance(required, dict)
        or any(
            family not in FAMILIES
            or type(count) is not int
            or count != FAMILIES[family]
            for family, count in required.items()
        )
        or not isinstance(value["jobs"], list)
    ):
        raise MergeError("invalid receipt job inventory")
    for job in value["jobs"]:
        if (
            not isinstance(job, dict)
            or set(job)
            != {"family", "revision", "index", "id", "attempt", "status", "conclusion"}
            or job["family"] not in required
            or job["revision"] not in ("head", "merge")
            or (
                type(job["id"]) is not int
                or job["id"] <= 0
                or type(job["index"]) is not int
                or type(job["attempt"]) is not int
                or job["attempt"] <= 0
            )
        ):
            raise MergeError("invalid receipt job fact")
    return value


def result(jobs: list[dict[str, Any]], required: dict[str, int], revision: str) -> str:
    selected = [job for job in jobs if job["revision"] == revision]
    expected = {
        (family, index) for family, count in required.items() for index in range(count)
    }
    identities = [(job["family"], job["index"]) for job in selected]
    if (
        not expected
        or set(identities) != expected
        or len(identities) != len(expected)
        or (len({job["id"] for job in selected}) != len(selected))
    ):
        return "INCOMPLETE"
    if any(job["status"] != "completed" for job in selected):
        return "INCOMPLETE"
    return (
        "PASSED"
        if all(job["conclusion"] == "success" for job in selected)
        else "FAILED"
    )


def classify(head: str, merge: str) -> str:
    if "INCOMPLETE" in (head, merge) or "PENDING" in (head, merge):
        return "INCOMPLETE"
    return {
        ("PASSED", "PASSED"): "PASSED",
        ("FAILED", "PASSED"): "HEAD_ONLY_FAILURE",
        ("PASSED", "FAILED"): "MERGE_ONLY_FAILURE",
        ("FAILED", "FAILED"): "HEAD_AND_MERGE_FAILURE",
    }.get((head, merge), "INCOMPLETE")


def finish(
    receipt: dict[str, Any], pages: Any, required: dict[str, int]
) -> dict[str, Any]:
    check_receipt(receipt)
    if not isinstance(pages, list) or not pages:
        raise MergeError("no CI job pages were read")
    jobs = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("jobs"), list):
            raise MergeError("invalid CI jobs response")
        for job in page["jobs"]:
            if not isinstance(job, dict):
                raise MergeError("invalid CI job record")
            match = JOB.fullmatch(str(job.get("name", "")))
            if not match or match[1] not in required:
                continue
            family, revision, shard, merge_sha = match.groups()
            if merge_sha != receipt["merge"]["sha"]:
                continue
            if job.get("head_sha") != receipt["head"]["sha"]:
                raise MergeError("CI job belongs to another head")
            jobs.append(
                {
                    "family": family,
                    "revision": revision,
                    "index": int(shard or 0),
                    "id": job.get("id"),
                    "attempt": job.get("run_attempt"),
                    "status": job.get("status"),
                    "conclusion": job.get("conclusion"),
                }
            )
    # A failed-job retry keeps prior successes for this exact pair. Jobs
    # named for another merge cannot fill the quorum after base/preflight drift.
    latest = {}
    for job in jobs:
        attempt = job["attempt"]
        if type(attempt) is not int or attempt <= 0:
            raise MergeError("CI job has no execution attempt")
        key = (job["family"], job["revision"], job["index"])
        previous = latest.get(key, [])
        if not previous or attempt > previous[0]["attempt"]:
            latest[key] = [job]
        elif attempt == previous[0]["attempt"]:
            latest[key].append(job)
    jobs = [job for alternatives in latest.values() for job in alternatives]
    head = result(jobs, required, "head")
    merge = result(jobs, required, "merge")
    finished = {
        **receipt,
        "head_result": head,
        "merge_result": merge,
        "classification": classify(head, merge),
        "jobs": jobs,
        "required_jobs": required,
        "gate_result": "PENDING",
    }
    if len({job["id"] for job in jobs}) != len(jobs):
        finished["classification"] = "INCOMPLETE"
    return check_receipt(finished)


def passed(receipt: dict[str, Any]) -> bool:
    check_receipt(receipt)
    required = receipt["required_jobs"]
    return (
        bool(required)
        and receipt["gate_result"] == "PASSED"
        and len({job["id"] for job in receipt["jobs"]}) == len(receipt["jobs"])
        and (
            receipt["classification"] == "PASSED"
            and receipt["head_result"] == "PASSED"
            and receipt["merge_result"] == "PASSED"
            and result(receipt["jobs"], required, "head") == "PASSED"
            and result(receipt["jobs"], required, "merge") == "PASSED"
        )
    )


def required_jobs(scope: str, flags: dict[str, bool]) -> dict[str, int]:
    if scope == "RUNTIME_FULL":
        required = {"Canonical environment": 6}
        if flags["image"]:
            required["Clean dev-container image"] = 6
        if flags["service"]:
            required["C-03/C-04/C-05/C-07/C-08/C-10 isolated service acceptance"] = 1
            required["Authored-Julia isolated service acceptance"] = 1
    elif scope == "CONTRACT_AUTHORITY":
        required = {"Contract and authority acceptance": 1}
    elif scope == "DERIVED_DOCUMENTATION":
        required = {"Derived documentation acceptance": 1}
    else:
        raise MergeError("invalid acceptance scope")
    if flags["workbench"]:
        required["Workbench release and application acceptance"] = 1
    if flags["hub"] and scope != "DERIVED_DOCUMENTATION":
        required["Development Hub validation"] = 1
    return required


def strict_base_rule(rules: Any) -> bool:
    """Require GitHub's server-side base guard, from the effective main rules."""
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        if (
            not isinstance(parameters, dict)
            or parameters.get("strict_required_status_checks_policy") is not True
        ):
            continue
        checks = parameters.get("required_status_checks")
        if isinstance(checks, list) and any(
            isinstance(check, dict)
            and check.get("context") == "Merge gate"
            and type(check.get("integration_id")) is int
            and check["integration_id"] == 15368
            for check in checks
        ):
            return True
    return False


def current(receipt: dict[str, Any], pull: Any, main: str) -> None:
    check_receipt(receipt)
    if (
        not isinstance(pull, dict)
        or pull.get("state") != "open"
        or pull.get("draft") is not False
    ):
        raise MergeError("pull request is not open and ready")
    head = pull.get("head")
    base = pull.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise MergeError("pull request identities could not be read")
    if head.get("sha") != receipt["head"]["sha"]:
        raise MergeError("HEAD_CHANGED: re-validation is required")
    if base.get("ref") != "main" or (
        base.get("sha") != receipt["base"]["sha"]
        or exact_sha(main) != receipt["base"]["sha"]
    ):
        raise MergeError("BASE_CHANGED: re-validation is required")
    if pull.get("mergeable") is not True:
        raise MergeError("merge is not confirmed clean; no head-only fallback")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "finish"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--head")
    parser.add_argument("--base")
    parser.add_argument("--merge")
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--pull", type=Path)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--main")
    parser.add_argument("--scope")
    for flag in ("image", "service", "workbench", "hub"):
        parser.add_argument("--" + flag, choices=("true", "false"), default="false")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            receipt = prepare(args.repository, args.head, args.base, args.merge)
        else:
            receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
            identities = prepare(
                args.repository,
                receipt["head"]["sha"],
                receipt["base"]["sha"],
                receipt["merge"]["sha"],
            )
            if any(
                receipt[key] != identities[key] for key in ("head", "base", "merge")
            ):
                raise MergeError("receipt identities do not match Git")
            receipt = finish(
                receipt,
                json.loads(args.jobs.read_text(encoding="utf-8")),
                required_jobs(
                    args.scope,
                    {
                        flag: getattr(args, flag) == "true"
                        for flag in ("image", "service", "workbench", "hub")
                    },
                ),
            )
            refusal = None
            try:
                current(
                    receipt,
                    json.loads(args.pull.read_text(encoding="utf-8")),
                    args.main,
                )
                rules = json.loads(args.rules.read_text(encoding="utf-8"))
                if not isinstance(rules, list):
                    raise MergeError("invalid effective main rules response")
                if not strict_base_rule(rules):
                    raise MergeError(
                        "BASE_RULE_NOT_ACTIVE: strict Actions Merge gate rule is required before merging"
                    )
            except MergeError as error:
                refusal = error
                receipt["gate_result"] = (
                    str(error).split(":", 1)[0]
                    if str(error).startswith(
                        ("HEAD_CHANGED:", "BASE_CHANGED:", "BASE_RULE_NOT_ACTIVE:")
                    )
                    else "IDENTITY_REFUSED"
                )
            else:
                receipt["gate_result"] = (
                    "PASSED"
                    if receipt["classification"] == "PASSED"
                    else "ACCEPTANCE_FAILED"
                )
            args.receipt.write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
            )
            if args.summary:
                with args.summary.open("a", encoding="utf-8") as stream:
                    stream.write(
                        "\n### Exact head and merge acceptance\n\n```json\n"
                        + json.dumps(receipt, indent=2)
                        + "\n```\n"
                    )
            if refusal:
                raise refusal
            if receipt["classification"] != "PASSED":
                raise MergeError(
                    receipt["classification"] + ": acceptance did not pass"
                )
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt))
        return 0
    except (
        MergeError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as error:
        print(f"CI merge validation refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
