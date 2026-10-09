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
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import q1
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

#: The one explicit value that records "no strata, on purpose" (Test Lead,
#: citing OWNER-GRAPHITE-TEST-WAVE-05 section 4). An empty list stays a gap.
NO_STRATA_BY_DESIGN = "NONE_UNIFORM_LAW"
ATTRIBUTION_REGISTRY = (
    "carbon/agent_campaign/graphite/attribution_policies/registry.json"
)
#: The components an ownership map names (gate item O1).
OWNERSHIP_COMPONENTS = (
    "contract",
    "scorer",
    "validator_adapter",
    "attack_adapter",
    "decision_study",
    "references",
    "gates",
    "literature",
    "grants",
)


@dataclass
class Context:
    challenge: str
    level: int
    repository: Path = REPOSITORY
    data: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)

    def data_policy(self, item_id):
        """A registered test-side value (policies.json), never invented here."""
        document = json.loads((PACKAGE / "policies.json").read_bytes())
        return document["policies"][item_id]


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
    paths = [
        p.replace("{challenge}", ctx.challenge)
        for p in pending.get("neutral_tests", [])
        if _is_file(ctx, p.split("::")[0])
    ]
    paths += list(ctx.data.get("tests", {}).get(item.get("id", "P4"), []))
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
    """O2: no planned branch name exists on origin under a different owner.
    Each planned entry is `{name, expected_owner, state}`. A name that exists
    on origin passes only when its entry is STARTED, which records that its
    expected owner opened it (PR Head tracks new branches and updates the file);
    otherwise it exists under an owner this record does not vouch for."""
    plan, path = _record(ctx, "branches.json")
    if plan is None:
        return recorded_tests(item, ctx)
    entries = plan.get("planned_branches") if plan else None
    valid = isinstance(entries, list) and bool(entries)
    if valid:
        for entry in entries:
            valid = valid and (
                isinstance(entry, dict)
                and isinstance(entry.get("name"), str)
                and bool(entry["name"])
                and isinstance(entry.get("expected_owner"), str)
                and bool(entry["expected_owner"].strip())
                and entry.get("state") in ("PROPOSED", "STARTED")
            )
    if not valid:
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
    foreign = sorted(
        e["name"] for e in entries if e["name"] in heads and e["state"] != "STARTED"
    )
    if foreign:
        return Result(
            FAIL,
            "planned branch names exist on origin and are not recorded as started "
            "by their expected owner",
            tuple(foreign),
        )
    return Result(
        PASS,
        "no planned branch name exists on origin under another owner",
        (file_digest(path),),
    )


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


def _lane_probe(lane):
    """Run a lane's own read-only environment probe, when it names one
    (`probe_cli` with `{input}` filled from the env var `probe_input_env`).
    Returns `(problem, evidence)`; a probe that cannot run fails closed."""
    cli = lane.get("probe_cli")
    if not cli:
        return None, []
    variable = lane.get("probe_input_env")
    value = os.environ.get(variable) if variable else None
    if not value:
        return (
            (
                f"{lane['lane']}: probe input not supplied (set {variable} to the "
                "host's pinned image manifest); cannot verify the environment"
            ),
            [],
        )
    command = [
        sys.executable if c == "{python}" else c.replace("{input}", value) for c in cli
    ]
    try:
        done = subprocess.run(
            command,
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"{lane['lane']}: probe could not run ({type(error).__name__})", []
    try:
        report = json.loads(done.stdout)
    except ValueError:
        report = {}
    if done.returncode == 2:
        return (
            f"{lane['lane']}: the lane policy was refused ({report.get('refused')})",
            [],
        )
    if done.returncode != 0 or report.get("eligible") is not True:
        return (
            (
                f"{lane['lane']}: environment not eligible here "
                f"(doctor {report.get('doctor_code')}, image_present "
                f"{report.get('image_present')}, exit {done.returncode}); run on the "
                "host with Docker and the pinned image"
            ),
            [],
        )
    return (
        None,
        [
            f"{lane['lane']}:probe:eligible",
            f"{lane['lane']}:probe_policy:{report.get('lane_policy')}:{report.get('lane_policy_digest')}",
        ],
        report,
    )


def compute_lanes(item, ctx):
    """Every compute lane the challenge uses names its own environment check
    (`probe`) and a registered, current policy in the registry the lane names;
    a lane that names a runnable probe (`probe_cli`) must also pass it on this
    host. A lane marked TBD, with no policy, or with a policy its registry does
    not hold or no longer calls current, fails: the gate never assumes a lane is
    covered. A lane's policy is never borrowed from another lane (a GPU probe's
    rules do not apply to a CPU carrier)."""
    record, path = _record(ctx, "lanes.json")
    if record is None:
        return recorded_tests(item, ctx)
    lanes = record.get("lanes") if record else None
    if not (isinstance(lanes, list) and lanes):
        return Result(FAIL, "lanes.json is malformed", (path.name,))
    evidence, problems = [], []
    for lane in lanes:
        name = lane.get("lane") if isinstance(lane, dict) else None
        if not (isinstance(name, str) and name):
            problems.append("a lane entry has no name")
            continue
        if lane.get("state") != "DECLARED":
            problems.append(f"{name}: lane is {lane.get('state')!r}, not DECLARED")
            continue
        if not lane.get("probe"):
            problems.append(f"{name}: no environment check named")
            continue
        policy = lane.get("policy")
        if not policy:
            problems.append(
                f"{name}: no attribution policy is registered for this lane"
            )
            continue
        try:
            registry = json.loads(
                (REPOSITORY / lane.get("registry", ATTRIBUTION_REGISTRY)).read_bytes()
            )
            digest = registry["versions"][policy]
        except (OSError, ValueError, KeyError):
            problems.append(f"{name}: policy {policy} is not in its registry")
            continue
        current = registry.get("current")
        if isinstance(current, dict):
            current = current.get(lane.get("registry_key", name))
        if current != policy:
            problems.append(f"{name}: policy {policy} is not the current version")
            continue
        outcome = _lane_probe(lane)
        if outcome[0]:
            problems.append(outcome[0])
            continue
        if len(outcome) == 3 and (
            outcome[2].get("lane_policy") != policy
            or outcome[2].get("lane_policy_digest") != digest
        ):
            problems.append(
                f"{name}: the probe reports a different policy than the registry"
            )
            continue
        evidence.append(f"{name}:{lane['probe']}:{policy}:{digest}")
        evidence.extend(outcome[1])
    if problems:
        return Result(FAIL, "; ".join(problems), tuple(evidence))
    return Result(
        PASS,
        "each lane names its own environment check and a current registered policy",
        tuple(evidence),
    )


def _challenge_tokens():
    """Literals that name a registered challenge: each registered id, and the
    id's first word when it is long enough to be a name (not a stop word)."""
    from carbon.challenge_registry import registry

    tokens = set()
    for entry in registry.entries():
        tokens.add(entry.challenge_id)
        first = entry.challenge_id.split("-")[0]
        if len(first) >= 6:
            tokens.add(first)
    return sorted(tokens)


def neutral_path(item, ctx):
    """P4: the tool text v2 an agent reads names no challenge (VALIDATOR-07,
    #610). The check proves its detector can fire by finding a challenge name in
    v1 first; a detector that cannot fire is a FAIL, never a pass. The literature
    snapshot and writeup parts of P4 are separate and are reported as NOT_BUILT
    until their PRs (#614 and #606) are on main, so the item is NOT_BUILT, not
    PASS, even when v2 is clean."""
    try:
        from carbon.agent_campaign.graphite import roles
    except Exception as error:  # noqa: BLE001
        return Result(FAIL, f"graphite roles could not load: {type(error).__name__}")
    v2 = getattr(roles, "TOOL_TEXT_V2", None)
    if v2 is None:
        return Result(
            NOT_BUILT,
            "versioned tool text (VALIDATOR-07, #610) is not in this tree; owner: Carbon Validator",
        )
    tokens = _challenge_tokens()

    def named(version):
        found = set()
        for role in roles.ROLES.values():
            text = json.dumps(role.tool_schemas(version), sort_keys=True).lower()
            found |= {t for t in tokens if t.lower() in text}
        return sorted(found)

    v1_names = named(roles.TOOL_TEXT_V1)
    if not v1_names:
        return Result(
            FAIL,
            "the neutrality detector found no challenge name in tool text v1, "
            "which is known to name one: the detector is blind",
        )
    v2_names = named(v2)
    if v2_names:
        return Result(
            FAIL,
            "tool text v2 names a challenge",
            tuple(f"names:{t}" for t in v2_names),
        )
    evidence = (f"v1_names:{','.join(v1_names)}", "v2_names:none")
    paths = list(ctx.data.get("tests", {}).get(item.get("id", "P4"), []))
    if not paths:
        return Result(
            NOT_BUILT,
            "tool text v2 names no challenge (detector proven on v1); the named-challenge "
            "plumbing and literature tests are not recorded for this challenge "
            "(owner: Carbon Validator)",
            evidence,
        )
    plumbing = run_tests(ctx, paths)
    if plumbing.status != PASS:
        return Result(
            FAIL,
            "named-challenge plumbing: " + plumbing.detail,
            evidence + plumbing.evidence,
        )
    return Result(
        PASS,
        "tool text v2 names no challenge and the named-challenge plumbing and "
        "literature tests pass",
        evidence + plumbing.evidence,
    )


def admission_controller(item, ctx):
    """A4: a designated admission controller is recorded for (challenge, level)
    (#615). A missing entry, a PENDING identity, or a malformed file all FAIL:
    a LOCK is refused until the operator's identity is recorded."""
    from carbon.challenge_pipeline import admission_controllers as ac

    try:
        entry = ac.designation(ctx.challenge, ctx.level)
    except ac.DesignationRefused as refused:
        return Result(FAIL, f"the designation file is refused ({refused})")
    if entry is None:
        return Result(
            FAIL,
            f"no admission controller is designated for ({ctx.challenge}, level "
            f"{ctx.level}); owner: Test Engineer",
        )
    if ac.pending(entry):
        return Result(
            FAIL,
            f"the controller {entry['name']} is designated but its identity is still "
            "pending: an operator must record it (a LOCK is refused until then)",
            (f"controller:{entry['name']}", "status:PENDING_OPERATOR_IDENTITY"),
        )
    return Result(
        PASS,
        "a designated admission controller with a recorded identity",
        (f"controller:{entry['name']}", f"identity:{entry['identity']}"),
    )


def grant_binding(item, ctx):
    """R5: the challenge's phase-4 grant is bound by the runner's registry, is
    a committed file, and the grant-binding tests pass. Pricing with lost-run
    headroom is a review of the owner's amounts, not a check this gate can make
    without inventing a rule, so the item stays NOT_BUILT even when the binding
    holds (evidence says what was verified)."""
    grant, refused = _phase4_grant(ctx)
    if refused:
        return Result(FAIL, refused)
    tested = run_tests(ctx, ["tests/cpu/test_graphite_phase4_grant.py"])
    if tested.status != PASS:
        return Result(FAIL, "grant-binding tests: " + tested.detail, tested.evidence)
    return Result(
        NOT_BUILT,
        f"the bound grant {grant} is committed and the binding tests pass; pricing with "
        "lost-run headroom and tokens-only where no pods run are not machine-checked "
        "(needs a recorded review of the owner's amounts; owner: Test Lead)",
        (f"grant:{grant}", *tested.evidence),
    )


def ownership_map(item, ctx):
    """O1's committed map: every component names an engineering `owner` and an
    `acceptance` authority, and an artifact
    that exists when its state is EXISTS. The Test Lead's review decides
    whether the map is right; this check only refuses a malformed one."""
    record, path = _record(ctx, "ownership.json")
    if record is None:
        return Result(FAIL, "no ownership.json is committed for the challenge")
    components = record.get("components") if record else None
    if not isinstance(components, dict):
        return Result(FAIL, "ownership.json is malformed", (path.name,))
    problems = []
    for name in OWNERSHIP_COMPONENTS:
        entry = components.get(name)
        if not isinstance(entry, dict):
            problems.append(f"{name}: no entry")
            continue
        for field_name in ("owner", "acceptance"):
            who = entry.get(field_name)
            if not (isinstance(who, str) and who.strip()) or who == "UNASSIGNED":
                problems.append(f"{name}: no {field_name} named")
        state = entry.get("state")
        if state not in ("EXISTS", "NOT_BUILT"):
            problems.append(f"{name}: state is not EXISTS or NOT_BUILT")
        elif state == "EXISTS":
            artifact = entry.get("artifact")
            if not (isinstance(artifact, str) and (REPOSITORY / artifact).exists()):
                problems.append(f"{name}: artifact {artifact!r} does not exist")
        if not (isinstance(entry.get("basis"), str) and entry["basis"].strip()):
            problems.append(f"{name}: no basis cited")
    if problems:
        return Result(FAIL, "; ".join(problems), (path.name,))
    return Result(
        PASS,
        "every component names an engineering owner and an acceptance owner (the review decides the map is right)",
        (file_digest(path),),
    )


def disk_free(item, ctx):
    """R6's automated half: free space on the WSL host's C: drive against the
    registered Test Lead threshold. A host where that drive cannot be measured
    fails closed."""
    policy = ctx.data_policy("R6")
    threshold = policy["min_free_gb"] * 10**9
    where = policy["path_windows"] if os.name == "nt" else policy["path_wsl"]
    try:
        free = shutil.disk_usage(where).free
    except OSError:
        return Result(
            FAIL,
            f"cannot measure the WSL host's C: drive from here ({where}); run on the host",
        )
    evidence = (
        f"{where}: {free / 10**9:.1f} GB free",
        f"threshold {policy['min_free_gb']} GB ({policy['authority']})",
    )
    if free >= threshold:
        return Result(PASS, "free disk meets the registered threshold", evidence)
    return Result(FAIL, "free disk is below the registered threshold", evidence)


# -- runtime ------------------------------------------------------------------------------------
def _phase4_grant(ctx):
    """`(grant file, refusal)` for the challenge's OWN phase-4 grant. The
    authority is the runner's per-challenge binding (`phase4.PHASE4_GRANTS`,
    #612): the grant format has no challenge field, so the binding lives there.
    A challenge with no entry has no grant. A grant recorded in challenges.json
    is only a cross-check: if it names a different file than the binding, R1
    fails, so it can never pass on another challenge's grant."""
    try:
        from carbon.agent_campaign.graphite import phase4

        entry = phase4.PHASE4_GRANTS.get(ctx.challenge)
    except Exception as error:  # noqa: BLE001
        return None, f"the phase-4 grant binding could not load: {type(error).__name__}"
    if entry is None:
        return None, (
            f"no grant for {ctx.challenge}: the runner's per-challenge binding "
            "registers none (it never falls back to another challenge's grant)"
        )
    recorded = (ctx.data.get("grants") or {}).get("phase4")
    if recorded and recorded != entry.grant_file:
        return None, (
            f"challenges.json records {recorded} for {ctx.challenge} but the runner "
            f"binds {entry.grant_file}: refusing another grant"
        )
    if not _is_file(ctx, entry.grant_file):
        return None, f"the bound grant {entry.grant_file} is not a committed file"
    return entry.grant_file, None


ANALYSIS_IMAGE_ENV = "CARBON_READINESS_ANALYSIS_IMAGE_MANIFEST"


def _analysis_image_manifest():
    """`(path, refusal)`: the host's analysis image manifest named by the
    environment variable, read with the consumer itself
    (`research_image.load_analysis_image`: the closed four-key document, bounded,
    no symlink). No manifest is invented or defaulted: unset, missing, or not that
    document is a refusal the R1 result states."""
    value = os.environ.get(ANALYSIS_IMAGE_ENV)
    if not value:
        return None, (
            f"no analysis image manifest: set {ANALYSIS_IMAGE_ENV} to the host's manifest "
            "file (the release produces it: schema, image_id, parent_image, runtime_digest); "
            "prelive's carrier containment check cannot run without it"
        )
    path = Path(value)
    if not path.is_file():
        return None, f"the analysis image manifest {value} is not a file"
    try:
        from carbon.development_session import research_image

        image = research_image.load_analysis_image(path)
    except (OSError, ValueError, TypeError, KeyError) as error:
        return None, (
            f"the analysis image manifest {value} is not the closed four-key format "
            f"({type(error).__name__})"
        )
    if not all(
        isinstance(v, str) and v
        for v in (image.image_id, image.parent_image, image.runtime_digest)
    ):
        return (
            None,
            f"the analysis image manifest {value} has an empty or non-text value",
        )
    return str(path), None


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
    grant, refused = _phase4_grant(ctx)
    if refused:
        return Result(FAIL, refused)
    manifest, refused = _analysis_image_manifest()
    if refused:
        return Result(FAIL, refused)
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
            "--grant",
            str(ctx.repository / grant),
            "--analysis-image-manifest",
            manifest,
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
        strata = doc.get("strata")
        if not ((isinstance(strata, list) and strata) or strata == NO_STRATA_BY_DESIGN):
            missing.append(
                "strata empty (an intentional none must be the explicit "
                f"{NO_STRATA_BY_DESIGN!r})"
            )
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
    "neutral_path": neutral_path,
    "admission_controller": admission_controller,
    "grant_binding": grant_binding,
    "q1_alignment": q1.v1_alignment_report,
    "q1_discrimination": q1.v2_panel_discrimination,
    "ownership_map": ownership_map,
    "disk_free": disk_free,
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
