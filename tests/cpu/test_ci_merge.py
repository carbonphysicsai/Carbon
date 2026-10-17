"""PLT-12: stale synthetic branches, exact merge identities and CI quorum."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))
from ci_merge import (
    MergeError,
    classify,
    current,
    finish,
    passed,
    prepare,
    required_jobs,
)


def git(repo, *args):
    run = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return run.stdout.strip()


@pytest.fixture
def stale(tmp_path):
    """Head changes a test; advancing base changes its imported implementation."""
    repo = tmp_path / "synthetic"
    repo.mkdir()
    git(repo, "init", "--initial-branch=fixture-base")
    git(repo, "config", "user.name", "Synthetic Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "value.py").write_text("VALUE = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture root")
    root = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "stale-head")
    (repo / "check.py").write_text("from value import VALUE\nassert VALUE == 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture head")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--detach", root)
    (repo / "value.py").write_text("VALUE = 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture advancing base")
    base = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "merge-tree", "--write-tree", base, head)
    merge = git(
        repo, "commit-tree", tree, "-p", base, "-p", head, "-m", "fixture merge"
    )
    return repo, root, head, base, merge


def pages(head_sha, merge_sha, head="success", merge="success", *, count=6):
    return [
        {
            "jobs": [
                {
                    "id": 100 + side * 10 + index,
                    "name": f"Canonical environment ({revision}, {index}) [{merge_sha}]",
                    "head_sha": head_sha,
                    "run_attempt": 1,
                    "status": "completed",
                    "conclusion": conclusion,
                }
                for side, (revision, conclusion) in enumerate(
                    (("head", head), ("merge", merge))
                )
                for index in range(count)
            ]
        }
    ]


def live(receipt):
    return {
        "state": "open",
        "draft": False,
        "mergeable": True,
        "head": {"sha": receipt["head"]["sha"]},
        "base": {"ref": "main", "sha": receipt["base"]["sha"]},
    }


def run_check(repo, revision):
    git(repo, "checkout", "--detach", revision)
    return subprocess.run(
        [sys.executable, "-B", "check.py"], cwd=repo, capture_output=True, check=False
    ).returncode


def test_deliberately_stale_head_passes_but_its_clean_merge_fails(stale):
    repo, _, head, base, merge = stale
    receipt = prepare(repo, head, base, merge)
    assert receipt["merge"]["parents"] == [base, head]
    assert receipt["head"]["tree"] != receipt["merge"]["tree"]
    assert run_check(repo, head) == 0
    assert run_check(repo, merge) != 0
    report = finish(
        receipt, pages(head, merge, merge="failure"), {"Canonical environment": 6}
    )
    assert report["head_result"] == "PASSED"
    assert report["merge_result"] == "FAILED"
    assert report["classification"] == "MERGE_ONLY_FAILURE"
    assert not passed(report)


def test_exact_receipt_is_kept_alongside_both_results(stale):
    repo, _, head, base, merge = stale
    receipt = prepare(repo, head, base, merge)
    report = finish(receipt, pages(head, merge), {"Canonical environment": 6})
    for key in ("head", "base", "merge"):
        assert report[key] == receipt[key]
    assert report["classification"] == "PASSED"
    assert len(report["jobs"]) == 12
    assert not passed(report), "passing jobs alone are not a current-base gate"
    report["gate_result"] = "PASSED"
    assert passed(report)


def test_head_only_failure_is_observed_separately_from_a_passing_merge(stale):
    repo, _, head, base, _ = stale
    git(repo, "checkout", "--detach", head)
    (repo / "check.py").write_text("from value import VALUE\nassert VALUE == 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture test that needs the newer base")
    head = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "merge-tree", "--write-tree", base, head)
    merge = git(
        repo, "commit-tree", tree, "-p", base, "-p", head, "-m", "fixture merge"
    )
    assert run_check(repo, head) != 0
    assert run_check(repo, merge) == 0
    report = finish(
        prepare(repo, head, base, merge),
        pages(head, merge, head="failure"),
        {"Canonical environment": 6},
    )
    assert report["classification"] == "HEAD_ONLY_FAILURE"
    assert not passed(report)


def test_wrong_ordered_parents_and_head_only_substitution_are_refused(stale):
    repo, _, head, base, merge = stale
    with pytest.raises(MergeError, match="ordered"):
        prepare(repo, head, base, head)
    with pytest.raises(MergeError, match="ordered"):
        prepare(repo, base, head, merge)
    fake = git(
        repo,
        "commit-tree",
        git(repo, "rev-parse", head + "^{tree}"),
        "-p",
        base,
        "-p",
        head,
        "-m",
        "wrong tree fixture",
    )
    with pytest.raises(MergeError, match="tree differs"):
        prepare(repo, head, base, fake)


def test_conflicting_head_never_falls_back_to_head_tree(stale):
    repo, root, _, base, _ = stale
    git(repo, "checkout", "--detach", root)
    (repo / "value.py").write_text("VALUE = 3\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture conflicting head")
    head = git(repo, "rev-parse", "HEAD")
    fake = git(
        repo,
        "commit-tree",
        git(repo, "rev-parse", head + "^{tree}"),
        "-p",
        base,
        "-p",
        head,
        "-m",
        "conflict fallback fixture",
    )
    with pytest.raises(MergeError, match="merge-tree failed"):
        prepare(repo, head, base, fake)


@pytest.mark.parametrize("mutation", ["base", "head", "conflict", "unreadable_merge"])
def test_base_and_head_drift_are_fail_closed(stale, mutation):
    repo, _, head, base, merge = stale
    receipt = prepare(repo, head, base, merge)
    pull = live(receipt)
    if mutation == "base":
        pull["base"]["sha"] = "a" * 40
    elif mutation == "head":
        pull["head"]["sha"] = "b" * 40
    else:
        pull["mergeable"] = False if mutation == "conflict" else None
    with pytest.raises(MergeError):
        current(receipt, pull, base)
    if mutation == "base":
        with pytest.raises(MergeError, match="BASE_CHANGED"):
            current(receipt, live(receipt), "c" * 40)


@pytest.mark.parametrize(
    "conclusion", ["failure", "cancelled", "skipped", "neutral", None]
)
def test_any_non_success_required_result_rejects_acceptance(stale, conclusion):
    repo, _, head, base, merge = stale
    report = finish(
        prepare(repo, head, base, merge),
        pages(head, merge, merge=conclusion),
        {"Canonical environment": 6},
    )
    assert report["classification"] == "MERGE_ONLY_FAILURE"
    assert not passed(report)


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "wrong_revision", "running", "reused_id"]
)
def test_missing_or_ambiguous_job_evidence_cannot_pass(stale, mutation):
    repo, _, head, base, merge = stale
    evidence = pages(head, merge)
    if mutation == "missing":
        evidence[0]["jobs"].pop()
    elif mutation == "duplicate":
        evidence[0]["jobs"].append(copy.deepcopy(evidence[0]["jobs"][-1]))
    elif mutation == "wrong_revision":
        evidence[0]["jobs"][-1]["name"] = "Canonical environment (unknown, 5)"
    elif mutation == "running":
        evidence[0]["jobs"][-1]["status"] = "in_progress"
    else:
        evidence[0]["jobs"][-1]["id"] = evidence[0]["jobs"][-2]["id"]
    report = finish(
        prepare(repo, head, base, merge), evidence, {"Canonical environment": 6}
    )
    assert report["classification"] == "INCOMPLETE"
    assert not passed(report)


@pytest.mark.parametrize(
    "head,merge,expected",
    [
        ("PASSED", "PASSED", "PASSED"),
        ("FAILED", "PASSED", "HEAD_ONLY_FAILURE"),
        ("PASSED", "FAILED", "MERGE_ONLY_FAILURE"),
        ("FAILED", "FAILED", "HEAD_AND_MERGE_FAILURE"),
        ("PENDING", "PASSED", "INCOMPLETE"),
    ],
)
def test_reports_distinguish_both_failures(head, merge, expected):
    assert classify(head, merge) == expected


def test_every_existing_lane_remains_required_for_each_revision():
    flags = dict.fromkeys(("image", "service", "workbench", "hub"), True)
    full = required_jobs("RUNTIME_FULL", flags)
    assert full["Canonical environment"] == 6
    assert full["Clean dev-container image"] == 6
    assert len(full) == 6
    assert (
        required_jobs("CONTRACT_AUTHORITY", flags)["Contract and authority acceptance"]
        == 1
    )
    assert (
        required_jobs("DERIVED_DOCUMENTATION", flags)[
            "Derived documentation acceptance"
        ]
        == 1
    )
    with pytest.raises(MergeError):
        required_jobs("UNKNOWN", flags)


def test_failed_job_retry_reuses_successes_only_for_the_same_pair(stale):
    repo, _, head, base, merge = stale
    receipt = prepare(repo, head, base, merge)
    evidence = pages(head, merge)
    failed = evidence[0]["jobs"][-1]
    failed["conclusion"] = "failure"
    retry = {**failed, "id": 777, "run_attempt": 2, "conclusion": "success"}
    evidence.append({"jobs": [retry]})
    report = finish(receipt, evidence, {"Canonical environment": 6})
    assert report["classification"] == "PASSED"
    assert len(report["jobs"]) == 12
    assert {job["attempt"] for job in report["jobs"]} == {1, 2}
    assert 777 in {job["id"] for job in report["jobs"]}
    assert failed["id"] not in {job["id"] for job in report["jobs"]}


def test_successes_for_an_older_merge_cannot_fill_a_new_pair_quorum(stale):
    repo, _, head, base, merge = stale
    evidence = pages(head, merge)
    git(repo, "checkout", "--detach", base)
    (repo / "new-base.txt").write_text("fixture base advancement\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture newer base")
    base = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "merge-tree", "--write-tree", base, head)
    new_merge = git(
        repo, "commit-tree", tree, "-p", base, "-p", head, "-m", "fixture newer merge"
    )
    current_job = pages(head, new_merge)[0]["jobs"][-1]
    current_job.update(id=888, run_attempt=2)
    evidence.append({"jobs": [current_job]})
    report = finish(
        prepare(repo, head, base, new_merge), evidence, {"Canonical environment": 6}
    )
    assert report["classification"] == "INCOMPLETE"
    assert len(report["jobs"]) == 1


def test_job_api_head_binding_cannot_be_substituted(stale):
    repo, _, head, base, merge = stale
    with pytest.raises(MergeError, match="another head"):
        finish(
            prepare(repo, head, base, merge),
            pages("a" * 40, merge),
            {"Canonical environment": 6},
        )


def test_finished_failure_and_base_drift_are_retained_in_cli_receipt(stale, tmp_path):
    repo, _, head, base, merge = stale
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(prepare(repo, head, base, merge)))
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(pages(head, merge)))
    pull_path = tmp_path / "pull.json"
    pull_path.write_text(json.dumps(live(json.loads(receipt_path.read_text()))))
    rules_path = tmp_path / "rules.json"
    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": "Merge gate", "integration_id": 15368}
                ],
            },
        }
    ]
    rules_path.write_text(json.dumps(rules))
    command = [
        sys.executable,
        str(ROOT / "scripts/dev/ci_merge.py"),
        "finish",
        "--repository",
        str(repo),
        "--receipt",
        str(receipt_path),
        "--jobs",
        str(jobs_path),
        "--pull",
        str(pull_path),
        "--scope",
        "RUNTIME_FULL",
        "--rules",
        str(rules_path),
        "--main",
    ]
    run = subprocess.run(
        [*command, "a" * 40], capture_output=True, text=True, check=False
    )
    assert run.returncode != 0 and "BASE_CHANGED" in run.stderr
    report = json.loads(receipt_path.read_text())
    assert report["gate_result"] == "BASE_CHANGED"
    assert report["head_result"] == report["merge_result"] == "PASSED"
    jobs_path.write_text(json.dumps(pages(head, merge, merge="failure")))
    run = subprocess.run([*command, base], capture_output=True, text=True, check=False)
    assert run.returncode != 0 and "MERGE_ONLY_FAILURE" in run.stderr
    report = json.loads(receipt_path.read_text())
    assert report["gate_result"] == "ACCEPTANCE_FAILED"
    assert report["head"]["sha"] == head and report["base"]["sha"] == base
    jobs_path.write_text(json.dumps(pages(head, merge)))
    rules[0]["parameters"]["strict_required_status_checks_policy"] = False
    rules_path.write_text(json.dumps(rules))
    run = subprocess.run([*command, base], capture_output=True, text=True, check=False)
    assert run.returncode != 0 and "BASE_RULE_NOT_ACTIVE" in run.stderr
    report = json.loads(receipt_path.read_text())
    assert report["gate_result"] == "BASE_RULE_NOT_ACTIVE"
    assert report["head_result"] == report["merge_result"] == "PASSED"
    rules[0]["parameters"]["strict_required_status_checks_policy"] = True
    rules_path.write_text(json.dumps(rules))
    run = subprocess.run([*command, base], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert passed(json.loads(receipt_path.read_text()))


def test_workflow_runs_both_revisions_without_changing_toolchain_pins():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    jobs = {}
    for match in re.finditer(
        r"^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    ):
        jobs[match[1]] = match[2]
    for name in (
        "canonical",
        "dev-image",
        "c03-worker",
        "julia-service",
        "workbench",
        "contract-authority",
        "hub-validation",
        "derived-documentation",
    ):
        job = jobs[name]
        assert "revision: [head, merge]" in job
        assert "fail-fast: false" in job
        assert (
            "ref: ${{ matrix.revision == 'head' && needs.preflight.outputs.candidate_sha || needs.preflight.outputs.merge_sha }}"
            in job
        )
        assert "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in job
    assert "shard: [0, 1, 2, 3, 4, 5]" in jobs["canonical"]
    assert "shard: [0, 1, 2, 3, 4, 5]" in jobs["dev-image"]
    needs = re.search(r"needs: \[([^\]]+)\]", jobs["merge-gate"])
    assert needs is not None
    assert set(needs[1].split(", ")) == {
        "preflight",
        "canonical",
        "dev-image",
        "c03-worker",
        "julia-service",
        "workbench",
        "contract-authority",
        "hub-validation",
        "derived-documentation",
    }
    assert jobs["merge-gate"].startswith("    name: Merge gate\n")
    for job in jobs.values():
        if "uses: astral-sh/setup-uv@" in job:
            assert 'version: "0.12.7"' in job
        if "uses: actions/setup-node@" in job:
            assert 'node-version: "24.19.0"' in job


def test_initial_helper_migration_is_exact_byte_bound_and_prefers_protected_base(
    tmp_path,
):
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    block = workflow.split("helper=.carbon-gate-base/scripts/dev/ci_merge.py", 1)[
        1
    ].split("          gh api --paginate", 1)[0]
    source = (ROOT / "scripts/dev/ci_merge.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() in block
    candidate = tmp_path / ".carbon-gate-candidate/scripts/dev/ci_merge.py"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(source)
    command = (
        "set -euo pipefail\nhelper=.carbon-gate-base/scripts/dev/ci_merge.py"
        + block
        + '\nprintf "%s" "$helper"'
    )

    def invoke():
        return subprocess.run(
            ["bash", "-c", command],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    assert invoke().returncode == 0
    candidate.write_bytes(source + b"\n# unreviewed substitution fixture\n")
    assert invoke().returncode != 0
    protected = tmp_path / ".carbon-gate-base/scripts/dev/ci_merge.py"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(source)
    run = invoke()
    assert run.returncode == 0
    assert run.stdout == ".carbon-gate-base/scripts/dev/ci_merge.py"
