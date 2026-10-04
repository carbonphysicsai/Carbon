"""Graphite phase 4: the Attacker session driver for the general attack engine.

    python -m carbon.agent_campaign.graphite.phase4 run --root DIR --dry-run
        [--challenge TOKEN]
    python -m carbon.agent_campaign.graphite.phase4 run --root DIR \
        --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json \
        --credential-file PATH \
        --miner-profile PROFILE.json --miner-campaign ID [--session N] \
        [--challenge TOKEN]
    python -m carbon.agent_campaign.graphite.phase4 log --root DIR [--dry-run]

**The engine.** The attack engine is challenge-neutral and lives in
`carbon.agent_campaign.attack` (the neutral core, its per-Challenge adapters,
analysis, verify, the knowledge store, report and benchmark). This module is
the *session driver* only: it runs one Attacker session on #504's phase-3
harness and then runs Carbon's own side through the engine. It owns no
science, no grade and no authority.

**The session.** `AttackerProvider` is #504's `Phase3Provider`, so an Attacker
session inherits the v2 session-limits rule (no session-turn cap, no per-role
call cap; the grant's per-run money cap and elapsed limit bind), the engine's
recorded context compaction, the parallel-call rule, and the experiment's
pods. It runs the Attacker role's prompt and closed tool manifest
(`roles.py`). Its miner tools go through the real miner path (the standard
miner MCP door to the Challenge's DEVELOPMENT campaign); `AttackerTools`
enforces one resource rule before dispatch: a sandbox code run must ask for a
wall allowance of at most the adapter's `code_run_seconds` (family
`resource_and_failure_accounting`). Nothing else caps the session; money and
time bind (OWNER-GRAPHITE-ATTACKER-01 §5).

**Carbon's side** reads the session's journal, never the model's prose
(`attack.analysis`), maps each attempt to a family through the Challenge's
adapter, re-verifies each with the adapter's oracle, and rebuilds every attack
construction it scores on the phase-3 pods (`attack.verify`). A verified
breach, or a wrongly refused control, is recorded on the #475 controller as a
`FAILING_TRIGGER` through `controller.record_finding`, where it stops any
later expansion. Attempts, verified findings and near-misses go into the
durable attack-knowledge store (`attack.knowledge`), whose snapshot digest the
run pins. The per-family report and benchmark B2 (Attacker vs battery's
deterministic `track_a` at an equal attempt budget) come from `attack.report`
and `attack.benchmark`.

**`--dry-run`** runs one session with a scripted model and `ScriptedPods`
under `DIR/attacker-dry-run`, with a synthetic copy of the grant and no miner
path, then Carbon's side with the same engine, producing the coverage report
and B2. It sends nothing and spends nothing.

**Grant.** A live run reads `GRAPHITE-GRANT-PHASE4`
(OWNER-GRAPHITE-ATTACKER-01 §5). One grant covers both the Attacker's model
calls and the pods on which Carbon rebuilds the constructions it scores.

Nothing here grades a finding, submits, opens a pull request, writes weights or
touches chain state. Not security acceptance. A live run is NOT executed in
this work.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_loop import run_epoch
from carbon.development_session.research_tools import PREFIX

from .. import boundaries
from ..grant import SpendingGrant
from ..provider import ProviderUnavailable, TaskSpec
from . import experiment as ex
from . import tools as toolbox
from .phase3 import Phase3Provider, RunnerRefused, _root, load_grant
from .provider import EPOCH, OWNER, GraphiteProvider, SessionBrief
from .roles import PARALLEL_RULES, ROLES, RoleName

REPOSITORY = Path(__file__).resolve().parents[3]
CAMPAIGN = "graphite-phase4"
OPERATOR = "graphite-phase4-runner"
WORKSPACE = "graphite-phase4-workspace"
CREDENTIAL_REF = "graphite-phase4-engy"
PROFILE_SCHEMA = "carbon.graphite.phase4.attacker-profile.v1"
#: The owner-approved grant the Attacker runs under (OWNER-GRAPHITE-ATTACKER-01
#: §5). The dry run copies it under a synthetic identity.
GRANT_ID = "GRAPHITE-GRANT-PHASE4"
GRANT_FILE = "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json"
#: The pipeline stage an Attacker campaign runs at.
STAGE = "test_iterate"
#: The construction level battery's first adapter runs at (Level 0).
BATTERY_CHALLENGE = "battery-fastcharge-ageing-development-v1"
BATTERY_LEVEL = 0
#: A run's worst case rebuilds up to this many attack constructions on their
#: own verify pods; the grant's `worst_case_run_cost` is derived from it
#: (grants/README.md). Money binds, not this count.
ATTACKER_VERIFY_PODS = 6
#: Code runs the session's model may start: the research sandbox applies the
#: wall allowance; no Carbon count caps a session (money and time bind).
#: The per-family attempt budget benchmark B2 holds the Attacker and battery's
#: deterministic harness to.
ATTACK_BUDGET = 8
ROWS_SCHEMA = "carbon.graphite.attack-rows.v2"
LOG_SCHEMA = "carbon.graphite.attacker-iteration-log.v1"
COVERAGE_SCHEMA = "carbon.graphite.attacker-coverage.v1"
_TERMINAL = ("succeeded", "failed", "cancelled")


# -- the attack engine seam ----------------------------------------------------------------
def attack_modules():
    """The neutral attack engine (`carbon.agent_campaign.attack`). Imported
    here, not at module load, so the driver imports before the engine slices
    merge; a test injects fakes by replacing this function."""
    from ..attack import adapter, analysis, benchmark, engine, knowledge, report, verify

    return {
        "adapter": adapter,
        "analysis": analysis,
        "benchmark": benchmark,
        "engine": engine,
        "knowledge": knowledge,
        "report": report,
        "verify": verify,
    }


def get_adapter(atk, challenge_id, level):
    """The adapter the engine registers for one Challenge and construction
    level (`attack.adapter.ADAPTERS`)."""
    try:
        return atk["adapter"].ADAPTERS[(challenge_id, level)]
    except KeyError:
        raise RunnerRefused("no_attack_adapter_for_challenge_level") from None


def adapter_code_run_seconds(adapter):
    """The wall allowance one sandbox code run may ask, from the adapter's
    resource family (battery Level 0: `battery.research.PRACTICE_SECONDS`).
    A positive integer, or the runner refuses."""
    value = getattr(adapter, "code_run_seconds", None)
    seconds = value() if callable(value) else value
    if type(seconds) is not int or seconds < 1:
        raise RunnerRefused("adapter_code_run_seconds_is_a_positive_integer")
    return seconds


# -- the Attacker's tools ------------------------------------------------------------------
#: A code run whose wall allowance is missing or over the adapter's ceiling is
#: refused before anything is dispatched (family resource_and_failure_accounting).
CODE_ACTIONS = ("run_python", "run_julia")


def is_code_run(name, arguments):
    """A task that trains or runs code: practice, `run_python`, `run_julia`."""
    return (
        name == PREFIX + "start_research_task"
        and type(arguments) is dict
        and (
            arguments.get("kind") == "practice"
            or arguments.get("action") in CODE_ACTIONS
        )
    )


class AttackerTools:
    """What the Attacker's toolbox delegates to: the real miner path, with the
    adapter's code-run wall allowance enforced before dispatch. No count caps a
    session; money and time bind (OWNER-GRAPHITE-ATTACKER-01 §5)."""

    def __init__(self, *, miner, emit, code_run_seconds):
        self.miner, self.emit = miner, emit
        self.code_run_seconds = code_run_seconds

    def _wall_refusal(self, arguments):
        """The typed refusal of a code run that asks for no wall allowance or
        one over the adapter's ceiling, or None. A timeout at the allowance is
        FAILED_INFRA in the sandbox, never a pass."""
        if arguments.get("action") in CODE_ACTIONS:
            try:
                inner = json.loads(arguments.get("arguments_json"))
            except (TypeError, ValueError):
                inner = None
            if type(inner) is not dict:
                return "code_run_arguments_unreadable"
            seconds = inner.get("seconds")
            most = self.code_run_seconds
            if type(seconds) is not int or not 1 <= seconds <= most:
                return "code_run_needs_seconds_up_to_" + str(most)
        return None

    async def call(self, name, arguments, identity):
        if is_code_run(name, arguments):
            refused = self._wall_refusal(arguments)
            if refused is not None:
                return toolbox.refusal(
                    "REJECTED_BEFORE_DISPATCH",
                    refused,
                    code_run_seconds_at_most=self.code_run_seconds,
                )
        if self.miner is None:
            return toolbox.refusal(
                toolbox.UNAVAILABLE,
                "miner_path_not_attached",
                reason="This session has no miner campaign attached; nothing ran.",
            )
        if is_code_run(name, arguments):
            self.emit(
                "code-run-" + identity,
                {"kind": "code_run_dispatched", "tool": name, "identity": identity},
            )
        return await self.miner.call(name, arguments, identity)


# -- the budget ----------------------------------------------------------------------------
def attacker_budget(grant, verify_pods=ATTACKER_VERIFY_PODS):
    """One Attacker run's share of the grant, split between the verify pods and
    the model-call tokens, like #504's budget but at the Attacker's worst-case
    pod count (`ATTACKER_VERIFY_PODS`). The grant's `worst_case_run_cost` is
    the combined cap."""
    base = ex.phase3_budget(grant)
    budget = ex.Phase3Budget(
        run_cap_usd=base.run_cap_usd,
        hourly_usd=base.hourly_usd,
        pod_minutes=base.pod_minutes,
        max_pods=verify_pods,
    )
    if budget.max_pods < 2 or budget.token_allowance_usd <= 0:
        raise ProviderUnavailable("grant_run_cost_cannot_cover_pods_and_tokens")
    return budget


# -- the provider --------------------------------------------------------------------------
class AttackerProvider(Phase3Provider):
    """#504's `Phase3Provider` for Attacker sessions: the v2 session-limits
    rule (no call cap), compaction, the parallel-call rule, and the
    experiment's pods, but driving the Attacker role with `AttackerTools`
    instead of the Constructor's proposal path. An Attacker session proposes no
    construction, so it bundles and scores nothing itself; Carbon rebuilds the
    constructions it scores on these pods on its own side (`attack.verify`)."""

    def __init__(
        self,
        *,
        root,
        grant,
        model,
        pods,
        code_run_seconds,
        miner_attach=None,
        miner_tools=None,
        **kwargs,
    ):
        if type(code_run_seconds) is not int or code_run_seconds < 1:
            raise ProviderUnavailable("code_run_seconds_required")
        self._code_run_seconds = code_run_seconds
        super().__init__(
            root=root,
            grant=grant,
            model=model,
            pods=pods,
            miner_attach=miner_attach,
            miner_tools=miner_tools,
            **kwargs,
        )
        # The Attacker's worst case is its verify pods, not the Constructor's
        # twelve; the token share follows (grants/README.md).
        self.budget = attacker_budget(grant)

    def start(self, spec, idempotency_key):
        # #504's `Phase3Provider.start` enforces the Constructor; the Attacker
        # uses the same harness with its own role, so go to the base provider's
        # start after the Attacker-only check.
        if type(spec) is TaskSpec and self.find(idempotency_key) is None:
            brief = self._brief(spec.instructions_digest)
            if brief is not None and brief["role"] != RoleName.ATTACKER.value:
                raise ProviderUnavailable("phase4_runs_the_attacker_only")
        return GraphiteProvider.start(self, spec, idempotency_key)

    def _manifest(self, opened):
        return {**super()._manifest(opened), "implementation": "graphite-phase4"}

    def code_runs(self, run_id):
        """Code runs dispatched so far in this session, from its events."""
        return sum(
            1
            for event in self.events(run_id, 0)
            if event["kind"] == "code_run_dispatched"
        )

    async def _epoch(self, run_id, ledger, role, brief, selection):
        """One Attacker epoch: the Attacker role's toolbox with `AttackerTools`
        between it and the real miner path, the v2 count-free loop limits and
        compaction, and the parallel-call rule. No delivery, no bundle and no
        stall escalation: an Attacker proposes no construction."""
        opened = self._opened(run_id)

        def emit(event_id, body):
            self._emit(run_id, event_id, body)

        async with self._attached(run_id) as miner:
            sdk = toolbox.GraphiteToolbox(
                role=role,
                literature_index=self.literature,
                emit=emit,
                miner_tools=AttackerTools(
                    miner=miner,
                    emit=emit,
                    code_run_seconds=self._code_run_seconds,
                ),
            )
            return await run_epoch(
                ledger,
                owner=OWNER,
                epoch=EPOCH,
                sdk=sdk,
                credential_file=None,
                initial_observation=brief["initial_observation"],
                transport=self.model.transport_for(selection),
                provider=selection,
                instructions=role.prompt,
                tools=role.tool_schemas(),
                parallel_calls=PARALLEL_RULES.get(role.name),
                **self._loop_limits(opened),
            )


# -- brief, controller and one session -------------------------------------------------------
def family_vectors(adapter):
    """The families the adapter names, worded for the Attacker's brief: the
    family id, its Track A check and its neutral goal. The adapter owns the
    neutral wording (lesson 2026-10-02-attacker-brief-protected-markers); the
    brief refuses if any string names protected material."""
    rows = []
    for family in adapter.families():
        rows.append(
            {
                "id": _attr(family, "name", "family_id"),
                "check": _attr(family, "check"),
                "goal": _attr(family, "goal", default=""),
            }
        )
    return rows


def _attr(obj, *names, default=None):
    """The first present attribute or mapping key among `names`."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    if default is not None or not names:
        return default
    raise KeyError(names[0])


def baseline_strategy(adapter):
    """The construction the Attacker probes around; the experiment machinery
    rebuilds it. From the adapter when it names one, else battery's public
    scaffold (battery Level 0)."""
    if hasattr(adapter, "baseline"):
        value = adapter.baseline
        return value() if callable(value) else value
    from carbon.battery.research import SCAFFOLD

    return SCAFFOLD


def public_identity(adapter):
    value = getattr(adapter, "public_identity", None)
    if value is not None:
        return value() if callable(value) else value
    from carbon.battery.challenge import CHALLENGE

    return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}


def brief_observation(adapter, *, code_run_seconds):
    """The Attacker's starting observation: the Challenge's public development
    identity, the construction level, the adapter's families and the one
    resource limit a code run is held to. Refused if it names protected
    material (SessionBrief does the same check)."""
    observation = {
        "challenge": public_identity(adapter),
        "stage": STAGE,
        "level": adapter.level,
        "baseline_strategy": baseline_strategy(adapter),
        "objective": (
            "Probe this Challenge's research path for each family below, through "
            "the tools you are given, at the construction level named. Try "
            "well-formed attempts a careful attacker would try; you may run code "
            "inside the research sandbox within its wall allowance. For each "
            "attempt, say what you tried and what the path did. A suspected breach "
            "is a report for Carbon to verify, never a verdict."
        ),
        "families": family_vectors(adapter),
        "limits": {
            "model_calls": None,
            "code_runs": None,
            "code_run_seconds_at_most": code_run_seconds,
        },
    }
    if toolbox.protected(observation):
        raise ValueError("refused: the attacker brief names protected material")
    return observation


def session_brief(adapter, *, checkout_commit, code_run_seconds, repository=REPOSITORY):
    role = ROLES[RoleName.ATTACKER]
    manifest = boundaries.checkout_manifest(repository, role.boundary)
    return SessionBrief(
        role=RoleName.ATTACKER,
        initial_observation=brief_observation(
            adapter, code_run_seconds=code_run_seconds
        ),
        checkout_commit=checkout_commit,
        checkout_manifest_digest=boundaries.manifest_digest(manifest),
    )


def attacker_profile(adapter):
    document = {
        "schema": PROFILE_SCHEMA,
        "challenge": _attr(adapter, "challenge_id"),
        "level": adapter.level,
        "contract_digest": _attr(adapter, "contract_digest", default=""),
        "surface": "red-team the Challenge's research path through the miner tools",
        "widens": [],
    }
    return document, digest(canonical(document))


def controller_for(store, provider, grant, clock=None):
    from ..controller import CampaignController

    kwargs = {} if clock is None else {"clock": clock}
    return CampaignController(
        root=Path(store) / "controller",
        provider=provider,
        grant=grant,
        operator=OPERATOR,
        **kwargs,
    )


def ensure_campaign(control, adapter, *, checkout_digest, profile_digest):
    if CAMPAIGN in control.budget()["campaigns"]:
        return
    grant = control.grant
    control.register_campaign(
        CAMPAIGN,
        role=ROLES[RoleName.ATTACKER].boundary,
        workspace_id=WORKSPACE,
        credential_ref=CREDENTIAL_REF,
        checkout_digest=checkout_digest,
        profile_digest=profile_digest,
        ceiling=str(grant.monetary_ceiling - grant.cleanup_allowance),
    )


def session_key(number):
    return f"graphite-phase4-session-{number}"


def _is_finding(verdict):
    """A verified breach, or a wrongly refused control: the engine records it
    as a finding and stops expansion. Read from the verdict whether it names a
    breach and carries a condition in the CONDITIONS vocabulary."""
    breached = _attr(verdict, "breached", "is_finding", default=False)
    condition = _attr(verdict, "condition", default=None)
    return bool(breached) and condition is not None


def carbon_side(store, control, provider, run_id, adapter, atk, *, budget):
    """Carbon's own side of a finished session, through the engine: the
    session's attempts read from its journal, mapped to families, verified with
    the adapter's oracle and rebuilt on the pods; a verified breach recorded on
    the controller as a finding; attempts and findings written to the durable
    knowledge store. Returns (coverage report, B2, finding ids, store digest)."""
    analysis, verify = atk["analysis"], atk["verify"]
    engine, report, benchmark = atk["engine"], atk["report"], atk["benchmark"]
    knowledge = atk["knowledge"]

    session_dir = provider._dir(run_id)
    attempts = analysis.attempts(session_dir)
    mapped = analysis.map_to_families(attempts, adapter)

    kstore = knowledge.AttackStore(Path(store) / "knowledge")
    cid, level = _attr(adapter, "challenge_id"), adapter.level
    findings = []
    for family, family_attempts in mapped.items():
        for attempt in family_attempts:
            verdict = verify.verify(attempt, adapter, pods=provider.pods)
            kstore.add_attempt(
                cid, level, family=family, attempt=attempt, verdict=verdict
            )
            if _is_finding(verdict):
                finding_id = verify.record(verdict, control)
                kstore.add_finding(cid, level, family=family, verdict=verdict)
                findings.append(finding_id)
            else:
                kstore.add_near_miss(cid, level, family=family, verdict=verdict)

    runs = [engine.run_family(family, budget=budget) for family in adapter.families()]
    held_out = adapter.controls("held_out")
    family_report = report.family_report(runs, controls_held_out=held_out)
    b2 = benchmark.b2(runs, baseline_runs=None, budget=budget)
    store_digest = kstore.snapshot()

    coverage = {
        "schema": COVERAGE_SCHEMA,
        "challenge": cid,
        "construction_level": level,
        "store_digest": store_digest,
        "families": family_report,
        "findings": findings,
        "benchmark_b2": b2,
        "claims": {"security_acceptance": False, "graded": False},
    }
    return coverage, b2, findings, store_digest


def _log(store, entry):
    path = Path(store) / "iteration-log.jsonl"
    if path.exists() and any(
        json.loads(line)["run_id"] == entry["run_id"]
        for line in path.read_bytes().splitlines()
    ):
        return
    with path.open("ab") as stream:
        stream.write(canonical(entry) + b"\n")
    path.chmod(0o600)


def run_session(store, control, provider, adapter, brief, number, atk, *, budget):
    """Launch (or resume) Attacker session `number`, run it, and do Carbon's
    side through the engine. Returns the iteration-log entry and the coverage
    report."""
    if type(number) is not int or not 1 <= number <= control.grant.permitted_runs:
        raise ValueError("session is 1 .. the grant's permitted runs")
    _document, profile = attacker_profile(adapter)
    ensure_campaign(
        control,
        adapter,
        checkout_digest=brief.checkout_manifest_digest,
        profile_digest=profile,
    )
    spec = TaskSpec(
        campaign_id=CAMPAIGN,
        role=ROLES[RoleName.ATTACKER].boundary.value,
        workspace_id=WORKSPACE,
        credential_ref=CREDENTIAL_REF,
        profile_digest=profile,
        instructions_digest=provider.register_brief(brief),
        max_runtime_s=control.grant.max_runtime_s,
    )
    key = session_key(number)
    control.recover()
    control.launch(spec, key)
    run_id = provider.run_id_for(key)
    final = provider.run(run_id) if provider.find(key) is not None else None
    phase = control.poll(key)
    coverage = None
    findings = []
    if final:
        coverage, _b2, findings, _digest = carbon_side(
            store, control, provider, run_id, adapter, atk, budget=budget
        )
    entry = {
        "schema": LOG_SCHEMA,
        "session": number,
        "run_id": run_id,
        "challenge": _attr(adapter, "challenge_id"),
        "construction_level": adapter.level,
        "role": RoleName.ATTACKER.value,
        "stage": STAGE,
        "provider_state": final,
        "controller_phase": str(phase),
        "failure": provider._state(run_id)["failure"] if final else None,
        "settled_usd": str(provider.usage(run_id).settled) if final else None,
        "code_runs": provider.code_runs(run_id) if final else 0,
        "findings": findings,
        "store_digest": coverage["store_digest"] if coverage else None,
    }
    if final in _TERMINAL:
        _log(store, entry)
    return entry, coverage


# -- the runner ----------------------------------------------------------------------------
def owner_only_file(path):
    """The Engy key's file, checked by its metadata alone: a regular file, not
    a link, owned by this user, with no group or other permission. Never read,
    printed or logged here."""
    candidate = Path(path).expanduser()
    try:
        info = os.lstat(candidate)
    except OSError:
        raise RunnerRefused("credential_file_missing") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RunnerRefused("credential_file_not_a_regular_file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RunnerRefused("credential_file_must_be_owner_only")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RunnerRefused("credential_file_not_owned_by_this_user")
    if info.st_size == 0:
        raise RunnerRefused("credential_file_empty")
    return str(candidate)


def _head(repository=REPOSITORY):
    out = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if len(out) != 40:
        raise RunnerRefused("checkout_commit_unavailable")
    return out


def _store(root, dry_run):
    store = root / ("attacker-dry-run" if dry_run else "attacker")
    store.mkdir(mode=0o700, exist_ok=True)
    return store


def command_run(args):
    atk = attack_modules()
    challenge = args.challenge or BATTERY_CHALLENGE
    adapter = get_adapter(atk, challenge, BATTERY_LEVEL)
    if args.dry_run:
        if any(
            (args.grant, args.credential_file, args.miner_profile, args.miner_campaign)
        ):
            raise RunnerRefused("dry_run_takes_no_grant_credential_or_miner_campaign")
        return dry_run(_root(args.root), adapter, atk)
    missing = [
        name
        for name, value in (
            ("--grant", args.grant),
            ("--credential-file", args.credential_file),
            ("--miner-profile", args.miner_profile),
            ("--miner-campaign", args.miner_campaign),
        )
        if not value
    ]
    if missing:
        raise RunnerRefused("required: " + ", ".join(missing))
    root = _root(args.root)
    grant = load_grant(args.grant)
    if grant.grant_id != GRANT_ID:
        raise RunnerRefused("grant_is_not_the_phase4_grant")
    if grant.provider != "graphite":
        raise RunnerRefused("grant_provider_must_be_graphite")
    if not args.runpod_key_file:
        raise RunnerRefused("required: --runpod-key-file")
    engy = owner_only_file(args.credential_file)
    runpod = owner_only_file(args.runpod_key_file)
    store = _store(root, False)
    code_run_seconds = adapter_code_run_seconds(adapter)
    from . import miner_path
    from .model import LiveModel, ModelAccessRefused
    from .pods import RunPodPods

    try:
        model = LiveModel(grant=grant, credential_file=engy, provider="graphite")
    except ModelAccessRefused as refused:
        raise RunnerRefused(refused.code) from None

    def attach(*, session):
        return miner_path.attach(
            args.miner_profile, args.miner_campaign, session=session
        )

    pods = RunPodPods(root=store / "pods", key_file=runpod, code_ref=_head())
    provider = AttackerProvider(
        root=store / "graphite",
        grant=grant,
        model=model,
        pods=pods,
        code_run_seconds=code_run_seconds,
        miner_attach=attach,
    )
    control = controller_for(store, provider, grant)
    try:
        brief = session_brief(
            adapter, checkout_commit=_head(), code_run_seconds=code_run_seconds
        )
        entry, coverage = run_session(
            store,
            control,
            provider,
            adapter,
            brief,
            args.session,
            atk,
            budget=ATTACK_BUDGET,
        )
    finally:
        control.close()
    print(
        json.dumps({"session": entry, "coverage": coverage}, indent=1, sort_keys=True)
    )
    return 0 if entry["provider_state"] == "succeeded" else 4


def command_log(args):
    root = Path(args.root).expanduser().resolve()
    store = root / ("attacker-dry-run" if args.dry_run else "attacker")
    with contextlib.suppress(FileNotFoundError):
        sys.stdout.write((store / "iteration-log.jsonl").read_text())
    return 0


# -- the dry run ---------------------------------------------------------------------------
#: What a dry-run grant changes in the real grant: who and what it names. Its
#: amounts, runs and runtime are the real grant's.
DRY_RUN_IDENTITY = {
    "grant_id": "graphite-phase4-attacker-dry-run-synthetic",
    "account": "dry-run-no-account",
    "granted_by": "nobody-dry-run",
    "expires_at": "2099-01-01T00:00:00Z",
}


def dry_run_grant(repository=REPOSITORY):
    """A synthetic copy of GRAPHITE-GRANT-PHASE4: the same amounts, runs and
    runtime, under a synthetic identity."""
    try:
        document = json.loads((Path(repository) / GRANT_FILE).read_bytes())
    except (OSError, ValueError):
        raise RunnerRefused("phase4_grant_file_unreadable") from None
    if document.get("grant_id") != GRANT_ID:
        raise RunnerRefused("phase4_grant_file_names_another_grant")
    return SpendingGrant.from_document({**document, **DRY_RUN_IDENTITY})


def dry_run_script(adapter):
    from .model import text, tool

    outside = None
    recipe = getattr(adapter, "recipe_outside_contract", None)
    if recipe is not None:
        outside = recipe() if callable(recipe) else recipe
    if outside is None:
        from carbon.battery.research import SCAFFOLD

        outside = {**SCAFFOLD, "backbone": "transolver"}
    return [
        tool(PREFIX + "get_challenge_info", {}),
        tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(outside)}),
        tool(
            PREFIX + "start_research_task",
            {
                "kind": "workspace",
                "strategy_json": None,
                "action": "run_python",
                "arguments_json": json.dumps({"source": "print(1)", "files": []}),
                "hypothesis": "a code run without a wall allowance",
                "expected_effect": "refused before dispatch",
            },
        ),
        text("DRY RUN: the scripted Attacker stops here."),
    ]


def dry_run(root, adapter, atk):
    from .model import ScriptedModel
    from .pods import ScriptedPods

    store = root / "attacker-dry-run"
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(mode=0o700)
    grant = dry_run_grant()
    code_run_seconds = adapter_code_run_seconds(adapter)
    provider = AttackerProvider(
        root=store / "graphite",
        grant=grant,
        model=ScriptedModel(dry_run_script(adapter)),
        pods=ScriptedPods(),
        code_run_seconds=code_run_seconds,
        randomness=lambda n: b"\x00" * n,
    )
    control = controller_for(store, provider, grant)
    try:
        brief = session_brief(
            adapter, checkout_commit="0" * 40, code_run_seconds=code_run_seconds
        )
        entry, coverage = run_session(
            store, control, provider, adapter, brief, 1, atk, budget=ATTACK_BUDGET
        )
    finally:
        control.close()
    out = {
        "session": entry,
        "coverage": coverage,
        "dry_run": {
            "synthetic": True,
            "note": "scripted model, scripted pods, synthetic grant and no miner "
            "path; Carbon's analysis, verification and the report are the engine's "
            "own. It sends nothing and spends nothing.",
            "money_cap_usd": str(provider.budget.token_allowance_usd),
            "settled_usd": entry["settled_usd"],
        },
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0 if entry["provider_state"] == "succeeded" else 4


def main(argv=None):
    parser = argparse.ArgumentParser(prog="graphite.phase4")
    sub = parser.add_subparsers(dest="command", required=True)
    challenge_help = "the Challenge's contract token (default: battery Level 0)"
    run = sub.add_parser("run")
    run.add_argument("--root", required=True)
    run.add_argument("--challenge", help=challenge_help)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--grant")
    run.add_argument(
        "--credential-file",
        help="path of an owner-only file holding the Engy key; never read here",
    )
    run.add_argument("--runpod-key-file")
    run.add_argument("--miner-profile")
    run.add_argument("--miner-campaign")
    run.add_argument("--session", type=int, default=1)
    log = sub.add_parser("log")
    log.add_argument("--root", required=True)
    log.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return {"run": command_run, "log": command_log}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
