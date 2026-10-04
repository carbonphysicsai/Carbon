"""The common test suite (Challenge Roadmap §03), version 1, DRAFT.

`suite_v1.json` is Challenge-neutral: it names no challenge. It registers
Track A's eight attack vectors and Track B's studies, the draft severity rules,
the metrics, the exam registration and each vector's place on the
construction ladder. Each Track A vector cites the shared checks that exercise
it, as pytest node ids grouped as `generic` and `sandbox` (those that need a
real container), and lists its known shared gaps.

Each challenge supplies a suite map, `suite_maps/<challenge>.json`:
- its own checks per vector, including its own sandbox checks;
- its own gaps;
- the dependency groups its checks need;
- its Track B and exam specifics.

A second challenge adds a map. It never edits the suite.

`run` executes one challenge's cited checks and reports each vector's
coverage, bound to the suite's digest, the map's digest, the challenge's
construction level and the commit it ran on:
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
unrestricted agents. A vector's participant-code part, which needs a level the
challenge has not reached (Level 4 and above), is reported NOT_RUN at that
level, never a pass.
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

from carbon.challenge_readiness.admission import CHECKS, LEDGER_TRACK

SUITE = Path(__file__).with_name("suite_v1.json")
MAPS = Path(__file__).with_name("suite_maps")
RECORDS = Path(__file__).with_name("records")
REPOSITORY = Path(__file__).resolve().parents[2]
GROUPS = ("generic", "sandbox")
VECTORS = tuple(f"A{i}" for i in range(1, 9))
MAP_KEYS = {
    "schema",
    "suite_version",
    "challenge",
    "family",
    "environment_groups",
    "track_a",
    "track_b",
    "exam",
}


def load_suite(path=SUITE):
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    if [v["id"] for v in suite["track_a"]] != list(VECTORS):
        raise ValueError("Track A has vectors A1 to A8, in order")
    for vector in suite["track_a"]:
        if set(vector["checks"]) - set(GROUPS):
            raise ValueError(
                f"{vector['id']}: shared check groups are {GROUPS}; a challenge's "
                "own checks belong in its suite map"
            )
        ladder = vector.get("ladder")
        if not (
            isinstance(ladder, dict)
            and ladder.get("applies_from_level") == 0
            and ladder.get("participant_code_from_level") in (None, 4, 5)
        ):
            raise ValueError(f"{vector['id']}: states its place on the ladder")
    if set(suite["severity"]["levels"]) != {"critical", "high", "medium", "low"}:
        raise ValueError("severity levels are critical, high, medium and low")
    mapped = {c for v in suite["track_a"] for c in v.get("admission_checks", ())}
    if mapped != CHECKS[LEDGER_TRACK]:
        raise ValueError("Track A's vectors map exactly the eight admission checks")
    return suite


def vectors_by_check(suite=None):
    """{admission check: [vector ids]}: the vectors that exercise each of the
    eight shared Track A checks, in vector order. The attack engine's families
    name a check; this is where a check meets the suite's vectors."""
    suite = suite or load_suite()
    out = {}
    for vector in suite["track_a"]:
        for check in vector["admission_checks"]:
            out.setdefault(check, []).append(vector["id"])
    return out


def _pin(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def digest(path=SUITE):
    """The suite's pin: SHA-256 of its canonical JSON."""
    return _pin(load_suite(path))


def load_map(challenge, maps=MAPS, suite=None):
    """One challenge's suite map, checked against the suite it maps onto."""
    path = Path(maps) / f"{challenge}.json"
    if not path.is_file():
        raise ValueError(f"no suite map for {challenge}: add {path.name}")
    suite_map = json.loads(path.read_text(encoding="utf-8"))
    if set(suite_map) != MAP_KEYS or suite_map["schema"] != (
        "carbon.challenge-pipeline.suite-map.v1"
    ):
        raise ValueError(f"{path.name}: keys are {sorted(MAP_KEYS)}")
    if suite_map["challenge"] != challenge:
        raise ValueError(f"{path.name}: maps {suite_map['challenge']}, not {challenge}")
    suite = suite or load_suite()
    if suite_map["suite_version"] != suite["suite_version"]:
        raise ValueError(f"{path.name}: maps onto another suite version")
    if set(suite_map["track_a"]) != set(VECTORS):
        raise ValueError(f"{path.name}: maps every Track A vector, A1 to A8")
    for vid, entry in suite_map["track_a"].items():
        if set(entry) != {"checks", "sandbox", "gaps"}:
            raise ValueError(f"{path.name} {vid}: {{checks, sandbox, gaps}}")
    if set(suite_map["track_b"]) != {b["id"] for b in suite["track_b"]}:
        raise ValueError(f"{path.name}: maps every Track B study")
    return suite_map


def map_digest(challenge, maps=MAPS):
    return _pin(load_map(challenge, maps))


def construction_level(challenge, records=RECORDS):
    """The challenge's recorded construction level, from its pipeline record."""
    for path in sorted(Path(records).glob("*.json")):
        construction = json.loads(path.read_text(encoding="utf-8")).get("construction")
        if construction and construction.get("challenge") == challenge:
            return construction.get("level")
    return None


def checks_for(suite, suite_map, *, sandbox=False):
    """{vector id: [node ids]} for one challenge: the shared generic checks,
    the challenge's own, and both sets of sandbox checks only when asked for."""
    out = {}
    for v in suite["track_a"]:
        own = suite_map["track_a"][v["id"]]
        nodes = list(v["checks"].get("generic", [])) + list(own["checks"])
        if sandbox:
            nodes += list(v["checks"].get("sandbox", [])) + list(own["sandbox"])
        out[v["id"]] = nodes
    return out


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
    challenge,
    *,
    sandbox=False,
    suite_path=SUITE,
    maps=MAPS,
    records=RECORDS,
    repository=REPOSITORY,
    python=None,
):
    """Run one challenge's Track A checks; return the coverage report."""
    suite = load_suite(suite_path)
    suite_map = load_map(challenge, maps, suite)
    level = construction_level(challenge, records)
    plan = checks_for(suite, suite_map, sandbox=sandbox)
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
        ladder = vector["ladder"]
        code_level = ladder["participant_code_from_level"]
        participant_code = None
        if code_level is not None:
            reached = level is not None and level >= code_level
            participant_code = {
                "what": ladder["participant_code"],
                "from_level": code_level,
                # Not reached means NOT_RUN at this level, never a pass. Once
                # reached it is IN_SCOPE: the vector's checks must then cover
                # it, which the technical owner confirms; reaching it is not
                # evidence that they do.
                "status": "IN_SCOPE" if reached else "NOT_RUN",
            }
        vectors.append(
            {
                "id": vector["id"],
                "name": vector["name"],
                "status": status,
                "checks": checks,
                "participant_code": participant_code,
                "gaps": vector["gaps"] + suite_map["track_a"][vector["id"]]["gaps"],
                "open_parameters": vector["open_parameters"],
            }
        )
    needed = suite_map["environment_groups"]
    installed = os.environ.get("CARBON_UV_GROUPS", "").split()
    return {
        "schema": "carbon.challenge-pipeline.suite-run.v1",
        "suite_version": suite["suite_version"],
        "suite_digest": digest(suite_path),
        "challenge": challenge,
        "map_digest": _pin(suite_map),
        "construction_level": level,
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
