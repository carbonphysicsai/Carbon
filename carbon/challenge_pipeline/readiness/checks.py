"""The registered checks. A check is `(item, ctx) -> Result` and never passes by
default: a check that cannot run, a component that is absent and a host that
lacks what the check needs are FAIL or NOT_BUILT, never PASS.

The runner names no challenge. What differs per challenge is data:
`challenges.json` (components and recorded tests), `<challenge>/` records
(onboarding, lanes, branch plan, reviews) and `conditions.json`.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .model import (
    FAIL,
    NOT_BUILT,
    PACKAGE,
    PASS,
    REPOSITORY,
    Result,
    file_digest,
)

TEST_TIMEOUT_SECONDS = 1800
PRELIVE_TIMEOUT_SECONDS = 1800

#: A lane's environment-probe / attribution policy registry (repository path).
LANE_PROBES = {
    "pod": "carbon/agent_campaign/graphite/attribution_policies/registry.json",
}


@dataclass
class Context:
    challenge: str
    level: int
    repository: Path = REPOSITORY
    data: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)


def load_challenge_data(challenge):
    document = json.loads((PACKAGE / "challenges.json").read_bytes())
    return document.get("challenges", {}).get(challenge, {})


def _is_file(ctx, relative):
    return (ctx.repository / relative).is_file()


# -- running recorded tests ---------------------------------------------------------------------
def run_tests(ctx, paths):
    """Run pytest on `paths` (repository-relative). PASS only on a clean run;
    a missing file, collection error or interpreter failure is FAIL."""
    missing = [p for p in paths if not _is_file(ctx, p.split("::")[0])]
    if missing:
        return Result(FAIL, "recorded test file is missing", tuple(missing))
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-x",
        "-p",
        "no:cacheprovider",
        *paths,
    ]
    try:
        done = subprocess.run(
            command,
            cwd=ctx.repository,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Result(
            FAIL, f"tests could not run: {type(error).__name__}", tuple(paths)
        )
    tail = (done.stdout or "").strip().splitlines()[-1:] or [""]
    evidence = tuple(paths) + (tail[0],)
    if done.returncode == 0:
        return Result(PASS, "recorded tests passed", evidence)
    return Result(
        FAIL, f"recorded tests failed (pytest exit {done.returncode})", evidence
    )


def recorded_tests(item, ctx):
    """Wire an item to tests: challenge-neutral tests the item names that exist
    in this tree, plus tests recorded for this challenge in challenges.json.
    Nothing to run is NOT_BUILT with the item's reason and owner."""
    pending = item.get("pending", {})
    paths = [p for p in pending.get("neutral_tests", []) if _is_file(ctx, p)]
    paths += list(ctx.data.get("tests", {}).get(item["id"], []))
    if paths:
        return run_tests(ctx, list(dict.fromkeys(paths)))
    reason = pending.get("reason", "no check is wired")
    return Result(NOT_BUILT, f"{reason}; owner: {pending.get('owner', 'unassigned')}")


def review_only(item, ctx):
    return None


# -- plumbing -----------------------------------------------------------------------------------
def registered_l0(item, ctx):
    from carbon.challenge_registry import registry

    found = [e for e in registry.entries() if e.challenge_id == ctx.challenge]
    if not found:
        return Result(FAIL, "the challenge is not in the registry")
    entry = found[0]
    if entry.status != registry.IMPLEMENTED:
        return Result(FAIL, f"registry status is {entry.status}, not IMPLEMENTED")
    from carbon.challenge_registry import campaigns

    try:
        campaigns.campaign_for_id(ctx.challenge)
    except Exception as error:  # noqa: BLE001 - any refusal is a failed check
        return Result(FAIL, f"no campaign composition: {type(error).__name__}")
    try:
        from carbon.reconstruction.capability_registry import contract

        digest = contract(ctx.challenge).digest
    except Exception as error:  # noqa: BLE001
        return Result(FAIL, f"no Level 0 construction contract: {type(error).__name__}")
    return Result(
        PASS,
        "registered, campaign composed, Level 0 contract resolves "
        "(Launchpad reachability itself is not separately exercised)",
        (f"registry:{entry.challenge_id}@{entry.version}", f"contract:{digest}"),
    )


def scoring_registered(item, ctx):
    from carbon.challenge_validator import scoring

    evidence, problems = [], []
    try:
        scoring.scoring_for(ctx.challenge)
        evidence.append("scoring_for(named) resolves")
    except scoring.ScoringUnavailable as refused:
        problems.append(f"no ChallengeScoring registered ({refused.code})")
    if len(scoring.registered()) >= 2:
        try:
            scoring.scoring_for(None)
            problems.append("an unnamed scoring call did not refuse")
        except scoring.ScoringUnavailable as refused:
            evidence.append(f"unnamed call refuses ({refused.code})")
    else:
        problems.append(
            "fewer than two scorings registered: unnamed refusal untestable"
        )
    spec = ctx.data.get("validator_adapter")
    if not spec:
        problems.append(
            "no Interface v1 validator adapter is recorded for the challenge"
        )
    else:
        try:
            module, _, name = spec.partition(":")
            cls = getattr(importlib.import_module(module), name)
            from carbon.challenge_validator.interface import ChallengeAdapter

            if not (isinstance(cls, type) and issubclass(cls, ChallengeAdapter)):
                problems.append(f"{spec} is not a ChallengeAdapter")
            elif inspect.isabstract(cls):
                problems.append(f"{spec} is abstract")
            else:
                evidence.append(f"adapter:{spec}")
        except Exception as error:  # noqa: BLE001
            problems.append(
                f"validator adapter {spec} unusable: {type(error).__name__}"
            )
    if problems:
        return Result(FAIL, "; ".join(problems), tuple(evidence))
    return Result(
        PASS,
        "scoring registered, unnamed call refuses, adapter class defined",
        tuple(evidence),
    )


# -- onboarding records -------------------------------------------------------------------------
def _record(ctx, name):
    path = PACKAGE / ctx.challenge / name
    if not path.is_file():
        return None, path
    try:
        return json.loads(path.read_bytes()), path
    except ValueError:
        return False, path


def branch_plan(item, ctx):
    plan, path = _record(ctx, "branches.json")
    if plan is None:
        return recorded_tests(item, ctx)
    names = plan.get("planned_branches") if plan else None
    if not (
        isinstance(names, list) and names and all(isinstance(n, str) for n in names)
    ):
        return Result(FAIL, "branches.json is malformed", (path.name,))
    try:
        done = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=ctx.repository,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return Result(FAIL, "origin could not be listed")
    if done.returncode != 0:
        return Result(FAIL, "origin could not be listed")
    heads = {
        line.split("refs/heads/", 1)[1]
        for line in done.stdout.splitlines()
        if "refs/heads/" in line
    }
    taken = sorted(set(names) & heads)
    if taken:
        return Result(
            FAIL, "planned branch names already exist on origin", tuple(taken)
        )
    return Result(PASS, "no planned branch name exists on origin", (file_digest(path),))


def onboarding_decisions(item, ctx):
    record, path = _record(ctx, "onboarding.json")
    if record is None:
        return recorded_tests(item, ctx)
    ids = record.get("decision_ids") if record else None
    if not (
        isinstance(ids, list) and ids and all(isinstance(i, str) and i for i in ids)
    ):
        return Result(FAIL, "onboarding.json is malformed", (path.name,))
    names = [p.name for p in (REPOSITORY / ".agent" / "decisions").glob("*.md")]
    unresolved = [i for i in ids if not any(i in n for n in names)]
    if unresolved:
        return Result(FAIL, "decision ids with no decision file", tuple(unresolved))
    return Result(
        PASS, "every cited decision id resolves to a decision file", tuple(ids)
    )


def compute_lanes(item, ctx):
    record, path = _record(ctx, "lanes.json")
    if record is None:
        return recorded_tests(item, ctx)
    lanes = record.get("lanes") if record else None
    if not (isinstance(lanes, list) and lanes):
        return Result(FAIL, "lanes.json is malformed", (path.name,))
    unknown = [lane for lane in lanes if lane not in LANE_PROBES]
    if unknown:
        return Result(
            FAIL,
            "compute lanes with no registered environment probe policy",
            tuple(unknown),
        )
    evidence = []
    for lane in lanes:
        try:
            registry = json.loads((REPOSITORY / LANE_PROBES[lane]).read_bytes())
            current = registry["current"]
            evidence.append(f"{lane}:{current}:{registry['versions'][current]}")
        except (OSError, ValueError, KeyError):
            return Result(FAIL, f"the {lane} lane's policy registry is unreadable")
    return Result(
        PASS,
        "each declared lane has a current registered attribution policy",
        tuple(evidence),
    )


# -- runtime ------------------------------------------------------------------------------------
def prelive(item, ctx):
    """`phase4 prelive` for the challenge under a scratch root. It needs the
    committed grant on a pushed HEAD and a main to compare, so a host without
    them FAILS CLOSED here, saying why."""
    if os.name != "posix":
        return Result(
            FAIL,
            "prelive needs a POSIX host (it uses fcntl); run the gate on the "
            "canonical Linux host. Failing closed.",
        )
    with tempfile.TemporaryDirectory(prefix="readiness-prelive-") as root:
        command = [
            sys.executable,
            "-m",
            "carbon.agent_campaign.graphite.phase4",
            "prelive",
            "--root",
            root,
            "--challenge",
            ctx.challenge,
        ]
        try:
            done = subprocess.run(
                command,
                cwd=ctx.repository,
                capture_output=True,
                text=True,
                timeout=PRELIVE_TIMEOUT_SECONDS,
                check=False,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return Result(FAIL, f"prelive could not run: {type(error).__name__}")
    text = done.stdout or ""
    report = None
    start = text.find("{")
    if start >= 0:
        try:
            report = json.loads(text[start:])
        except ValueError:
            report = None
    if (
        done.returncode == 0
        and isinstance(report, dict)
        and report.get("verdict") == "PASS"
    ):
        ctx.cache["prelive"] = report
        return Result(
            PASS, "pre-live real-path gate passed", ("phase4 prelive verdict PASS",)
        )
    if isinstance(report, dict):
        blocking = [
            f"{b.get('path')}: {b.get('detail')}"
            for b in report.get("blocking_findings", [])
        ]
        return Result(
            FAIL,
            f"prelive verdict {report.get('verdict')} (exit {done.returncode})",
            tuple(blocking[:20]),
        )
    last = (done.stderr or "").strip().splitlines()[-1:] or ["no output"]
    return Result(
        FAIL, f"prelive did not complete (exit {done.returncode}): {last[0][:300]}"
    )


# -- attack instrument --------------------------------------------------------------------------
def attack_families(item, ctx):
    try:
        from carbon.agent_campaign.attack import adapter as core

        adapter = core.ADAPTERS[(ctx.challenge, ctx.level)]
    except KeyError:
        return Result(
            FAIL,
            f"no attack adapter is registered for ({ctx.challenge}, level {ctx.level})",
        )
    except Exception as error:  # noqa: BLE001
        return Result(FAIL, f"attack adapters could not load: {type(error).__name__}")
    try:
        families = adapter.families()
        problems = []
        for split in core.SPLITS:
            have = {c.family for c in adapter.controls(split)}
            problems += [
                f"{f.name}: no {split} control" for f in families if f.name not in have
            ]
    except Exception as error:  # noqa: BLE001
        return Result(FAIL, f"adapter could not be read: {type(error).__name__}")
    if problems:
        return Result(FAIL, "families without both control splits", tuple(problems))
    return Result(
        NOT_BUILT,
        "every family has an attack example, a control and trained and held-out "
        "controls; the Attacker's route to each family is not machine-checked "
        "(lesson A2 OPEN); owner: Test Engineer",
        tuple(f"family:{f.name}" for f in families),
    )


def confirmation_role(item, ctx):
    directory = REPOSITORY / "carbon/challenge_validator/confirmation_sets"
    try:
        registry = json.loads((directory / "registry.json").read_bytes())["sets"]
    except (OSError, ValueError, KeyError):
        return Result(FAIL, "the confirmation-set registry is unreadable")
    good, problems = [], []
    for path in sorted(directory.glob("*.json")):
        if path.name == "registry.json":
            continue
        try:
            doc = json.loads(path.read_bytes())
        except ValueError:
            problems.append(f"{path.name}: unreadable")
            continue
        if doc.get("challenge_id") != ctx.challenge or doc.get("sealable") is not True:
            continue
        role = doc.get("role")
        missing = []
        if role not in registry:
            missing.append("unregistered")
        if not (type(doc.get("cases")) is int and doc["cases"] > 0):
            missing.append("size unset")
        if not (isinstance(doc.get("sampling_law"), dict) and doc["sampling_law"]):
            missing.append("sampling law unset")
        if not (isinstance(doc.get("strata"), list) and doc["strata"]):
            missing.append("strata empty")
        if missing:
            problems.append(f"{role}: " + ", ".join(missing))
        else:
            good.append(role)
    if good:
        return Result(
            PASS,
            "a registered sealable confirmation-set role has size, law and strata",
            tuple(good),
        )
    return Result(
        FAIL,
        "no registered sealable confirmation-set role with size, law and strata",
        tuple(problems),
    )


CHECKS = {
    "review_only": review_only,
    "recorded_tests": recorded_tests,
    "branch_plan": branch_plan,
    "onboarding_decisions": onboarding_decisions,
    "registered_l0": registered_l0,
    "scoring_registered": scoring_registered,
    "compute_lanes": compute_lanes,
    "prelive": prelive,
    "attack_families": attack_families,
    "confirmation_role": confirmation_role,
}
