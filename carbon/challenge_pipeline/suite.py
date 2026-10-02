"""The common test suite (Challenge Roadmap §03), version 1, DRAFT.

`suite_v1.json` registers Track A's eight attack vectors and Track B's
studies, the draft severity rules, the metrics and the exam registration.
Each Track A vector cites the existing checks that exercise it, as pytest node
ids grouped as `generic`, per challenge (`battery`), and `sandbox` for those
that need a real container. It also lists its known gaps.

`run` executes one challenge's cited checks and reports each vector's
coverage, bound to the suite's digest and the commit it ran on:
- PASS: every cited check ran and passed;
- FINDING_CANDIDATE: a cited check failed. A failing defense test is a
  candidate finding for the technical owner to grade, not a grade;
- NOT_RUN: a cited check was skipped, deselected or could not be collected.

The report records the environment it ran in. A challenge's checks need the
dependency groups the suite lists for it (`environments`); with a group
missing, checks that need it do not run.

Statuses come from each test's own outcome, never from pytest's exit code.
The invariant lane's conftest fails any session that deselects tests, so a
run that selects by name exits 1 even when every selected test passed;
`pytest_summary` shows the counts.

A NOT_RUN check is neither a pass nor a finding. The listed gaps stay open
whatever the checks say, because a clean run does not prove resistance to
unrestricted agents.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SUITE = Path(__file__).with_name("suite_v1.json")
REPOSITORY = Path(__file__).resolve().parents[2]
GROUPS = ("generic", "battery", "sandbox")


def load_suite(path=SUITE):
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    if [v["id"] for v in suite["track_a"]] != [f"A{i}" for i in range(1, 9)]:
        raise ValueError("Track A has vectors A1 to A8, in order")
    for vector in suite["track_a"]:
        if set(vector["checks"]) - set(GROUPS):
            raise ValueError(f"{vector['id']}: check groups are {GROUPS}")
    if set(suite["severity"]["levels"]) != {"critical", "high", "medium", "low"}:
        raise ValueError("severity levels are critical, high, medium and low")
    return suite


def digest(path=SUITE):
    """The suite's pin: SHA-256 of its canonical JSON."""
    body = json.dumps(load_suite(path), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def checks_for(suite, challenge, *, sandbox=False):
    """{vector id: [node ids]} for one challenge: the generic checks, the
    challenge's own, and the sandbox checks only when asked for."""
    groups = ["generic", challenge] + (["sandbox"] if sandbox else [])
    return {
        v["id"]: [n for g in groups for n in v["checks"].get(g, [])]
        for v in suite["track_a"]
    }


def _outcomes(junit):
    """{node id without parameters: [outcome, ...]} from a JUnit XML file."""
    out = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        path = case.get("classname", "").replace(".", "/") + ".py"
        name = case.get("name", "").split("[", 1)[0]
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        out.setdefault(f"{path}::{name}", []).append(outcome)
    return out


def _status(outcomes):
    if not outcomes or "skipped" in outcomes:
        return "NOT_RUN"
    return "FINDING_CANDIDATE" if "failed" in outcomes else "PASS"


def run(
    challenge, *, sandbox=False, suite_path=SUITE, repository=REPOSITORY, python=None
):
    """Run one challenge's Track A checks; return the coverage report."""
    suite = load_suite(suite_path)
    plan = checks_for(suite, challenge, sandbox=sandbox)
    nodes = sorted({n for ids in plan.values() for n in ids})
    # Select by name across the cited files, so a check that is missing or a
    # file that cannot be collected here leaves its own checks NOT_RUN and
    # never stops the rest. Outcomes are matched back to exact node ids.
    files = sorted(
        {
            n.split("::")[0]
            for n in nodes
            if (Path(repository) / n.split("::")[0]).is_file()
        }
    )
    names = " or ".join(sorted({n.split("::")[1] for n in nodes}))
    outcomes, exit_code, summary = {}, None, None
    if files:
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            command = [python or sys.executable, "-m", "pytest", "-q"]
            command += ["-p", "no:cacheprovider", "--continue-on-collection-errors"]
            command += [f"--junitxml={junit}", "-k", names, *files]
            completed = subprocess.run(
                command,
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )
            exit_code = completed.returncode
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            summary = lines[-1].strip("= ") if lines else None
            outcomes = _outcomes(junit) if junit.exists() else {}
    commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    vectors = []
    for vector in suite["track_a"]:
        checks = [
            {"node": n, "status": _status(outcomes.get(n, []))}
            for n in plan[vector["id"]]
        ]
        statuses = {c["status"] for c in checks}
        if not checks:
            status = "NOT_RUN"
        elif "FINDING_CANDIDATE" in statuses:
            status = "FINDING_CANDIDATE"
        elif "NOT_RUN" in statuses:
            status = "NOT_RUN"
        else:
            status = "PASS"
        vectors.append(
            {
                "id": vector["id"],
                "name": vector["name"],
                "status": status,
                "checks": checks,
                "gaps": vector["gaps"],
                "open_parameters": vector["open_parameters"],
            }
        )
    needed = suite.get("environments", {}).get(challenge, [])
    installed = os.environ.get("CARBON_UV_GROUPS", "").split()
    return {
        "schema": "carbon.challenge-pipeline.suite-run.v1",
        "suite_version": suite["suite_version"],
        "suite_digest": digest(suite_path),
        "challenge": challenge,
        "sandbox": sandbox,
        "commit": commit or None,
        "pytest_exit": exit_code,
        "pytest_summary": summary,
        # Selecting by name can also run tests the suite does not cite. Their
        # failures do not change a vector's status, but they are shown.
        "uncited_failures": sorted(
            node
            for node, results in outcomes.items()
            if node not in nodes and "failed" in results
        ),
        "environment": {
            "canonical": os.environ.get("CARBON_CANONICAL_DEV_ENV"),
            "groups": installed,
            "missing_groups": [g for g in needed if g not in installed],
        },
        "vectors": vectors,
        "claims": {"security_acceptance": False, "graded": False},
    }
