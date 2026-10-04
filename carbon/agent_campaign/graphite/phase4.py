"""Graphite phase 4: the Attacker session driver for the general attack engine.

    python -m carbon.agent_campaign.graphite.phase4 run --root DIR --dry-run
        [--challenge TOKEN]
    python -m carbon.agent_campaign.graphite.phase4 run --root DIR \
        --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json \
        --credential-file PATH \
        --miner-profile PROFILE.json --miner-campaign ID [--session N] \
        [--challenge TOKEN]
    python -m carbon.agent_campaign.graphite.phase4 prelive --root DIR \
        [--challenge TOKEN] [--grant PATH]
    python -m carbon.agent_campaign.graphite.phase4 cancel --root DIR --session N
    python -m carbon.agent_campaign.graphite.phase4 status --root DIR [--dry-run]
    python -m carbon.agent_campaign.graphite.phase4 log --root DIR [--dry-run]

**The engine.** The attack engine is challenge-neutral and lives in
`carbon.agent_campaign.attack` (the neutral core, its per-Challenge adapters,
analysis, verify, the knowledge store, report and benchmark). This module is
the *session driver* only: it runs one Attacker session on #504's phase-3
harness and then runs Carbon's own side through the engine's published
interfaces. It owns no science, no grade and no authority.

**The session.** `AttackerProvider` is #504's `Phase3Provider`, so an Attacker
session inherits the v2 session-limits rule (no session-turn cap, no per-role
call cap; the grant's per-run money cap and elapsed limit bind), the engine's
recorded context compaction and the parallel-call rule. It runs the Attacker
role's prompt and closed tool manifest (`roles.py`) against the Challenge's
adapter: the brief names the adapter's public identity, construction level,
families (each with its check and its boundary as the goal), the families
declared NOT_RUN, the code-run wall allowance and the attack-knowledge
snapshot the session runs under. `AttackerTools` enforces one resource rule
before dispatch: a sandbox code run must ask for a wall allowance of at most
the adapter's `code_run_seconds` (family `resource_and_failure_accounting`),
by the adapter's own rule (`code_run_rule`), the function that family
attacks, never a copy.
Nothing else caps the session; money and time bind (OWNER-GRAPHITE-ATTACKER-01
§5). An Attacker proposes no construction, so its session has no baseline and
launches no pod; its frozen session record says so.

**Carbon's side** reads the session's journal, never the model's prose
(`attack.analysis.attempts`), maps each attempt to a family through the
adapter (`map_to_families`) and verifies every one (`attack.verify.verify`):
Carbon rebuilds each construction it scores with the adapter's `rebuild`
(an unrebuildable one is typed and never scored), re-checks it with the
adapter's oracle and bundles a breach's specimen for a clean rebuild. A
`BREACHED` verdict carries its conditions in the CONDITIONS vocabulary and is
recorded on the #475 controller through `verify.record` ->
`controller.record_finding`, where it stops any later expansion. So is every
other finding: a held-out control the boundary wrongly refused and a breach or
refused control in the adapter's deterministic baseline run, each bound to
digest evidence. Before any of it, the pinned store view is checked against
the session's independently recorded pin (`replay_guard`). Every verdict
is written to the durable attack-knowledge store with its own outcome
(near-misses only when the oracle says so; a timeout or crash is never a near
miss). The per-family report is built from the session's verdicts, and
benchmark B2 compares them with the adapter's deterministic engine runs at an
equal attempt budget, recorded under the store snapshot the session was pinned
to before it ran.

**Seam: Carbon's verify-pod rebuild.** Rebuilding attack constructions on
Carbon-launched phase-3 pods is declared NOT_RUN here (`POD_REBUILD_SEAM`): no
pod is launched and `verify` gets no pod build records, so an attempt the path
says ran on a pod is `UNDETERMINED`, never a pass. The grant keeps the pods'
share reserved; the token share is the session's money cap.

**`--dry-run`** runs one session with a scripted model and `ScriptedPods`
under `DIR/attacker-dry-run`, with a synthetic copy of the grant and no miner
path, then Carbon's side with the same engine, producing the coverage report
and B2. It sends nothing and spends nothing.

**Grant.** A live run reads `GRAPHITE-GRANT-PHASE4`
(OWNER-GRAPHITE-ATTACKER-01 §5), and only a copy whose canonical digest equals
the committed blob at a pushed HEAD, with the grants directory clean
(`check_committed_grant`); the working-tree file is never trusted.

**`prelive`** (`phase4_prelive`) runs every real code path of a live run up
to the network boundary, with fake transports at that boundary and nothing
synthetic behind it, under the threading the live run uses; it spends
nothing and must pass before the first live run. Nothing here grades a finding, submits, opens
a pull request, writes weights or touches chain state. Not security
acceptance. A live run is NOT executed in this work.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from carbon.challenge_readiness.admission import CHECKS, LEDGER_TRACK
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_loop import run_epoch
from carbon.development_session.research_tools import PREFIX

from .. import boundaries
from ..grant import SpendingGrant
from ..provider import ProviderUnavailable, TaskSpec
from . import experiment as ex
from . import tools as toolbox
from .phase3 import (
    Phase3Provider,
    RunnerRefused,
    _install_cancel,
    _root,
    check_code_ref,
    load_grant,
)
from .pods import PodFailure
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
#: The Challenge and construction level the CLI attacks by default (battery
#: Level 0, the first adapter); `--challenge` names another registered one.
BATTERY_CHALLENGE = "battery-fastcharge-ageing-development-v1"
BATTERY_LEVEL = 0
#: The grant's worst case budgets this many verify pods (grants/README.md);
#: the pods' share stays reserved while Carbon's verify-pod rebuild is a seam.
#: Money binds, not this count.
ATTACKER_VERIFY_PODS = 6
#: The per-family attempt budget benchmark B2 holds the Attacker and the
#: adapter's deterministic engine runs to. Not a session cap.
ATTACK_BUDGET = 8
#: The strategy label the knowledge store records for the Attacker's attempts:
#: `graphite-attacker:<operation>` ("which strategy found what").
STRATEGY = "graphite-attacker"
LOG_SCHEMA = "carbon.graphite.attacker-iteration-log.v2"
#: v3 adds the per-check view (`check_view`): every Track A check, the run
#: families and NOT_RUN seams the adapter declares for it, and any report row
#: that lost its check. v4 adds `findings_by_source` (every finding, from the
#: Attacker, held-out controls and the deterministic baseline, reaches the
#: controller), the held-out wrongful-rejection rate per family and the
#: store's suite pin.
COVERAGE_SCHEMA = "carbon.graphite.attacker-coverage.v4"
#: The eight Track A checks every coverage report accounts for.
TRACK_A_CHECKS = tuple(sorted(CHECKS[LEDGER_TRACK]))
PIN_SCHEMA = "carbon.graphite.attacker-store-pin.v1"
#: What a session needs from its adapter besides the core protocol (the
#: adapter's session surface, `attack.adapter.SessionSurface`).
SESSION_SURFACE = ("public_identity", "code_run_seconds")
#: The dry run's script also needs a recipe the contract refuses.
DRY_RUN_SURFACE = (*SESSION_SURFACE, "recipe_outside_contract")
POD_REBUILD_SEAM = {
    "name": "carbon_verify_pod_rebuild",
    "state": "NOT_RUN",
    "reason": (
        "rebuilding attack constructions on Carbon-launched phase-3 pods is not "
        "wired in phase 4; no pod is launched and verify receives no pod build "
        "records, so a pod-scored attempt is UNDETERMINED, never a pass"
    ),
}
_TERMINAL = ("succeeded", "failed", "cancelled")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


# -- the attack engine seam ----------------------------------------------------------------
def attack_modules():
    """The neutral attack engine (`carbon.agent_campaign.attack`). Imported
    here, not at module load, so the driver imports before the engine slices
    merge; a test injects fakes by replacing this function."""
    from ..attack import adapter, analysis, benchmark, knowledge, report, verify

    return {
        "adapter": adapter,
        "analysis": analysis,
        "benchmark": benchmark,
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


def surface_value(adapter, name):
    """One member of the adapter's session surface, called when callable.
    Refused typed when the adapter does not supply it: the driver never
    substitutes another Challenge's value."""
    value = getattr(adapter, name, None)
    if value is None:
        raise RunnerRefused("adapter_session_surface_missing: " + name)
    return value() if callable(value) else value


def adapter_code_run_seconds(adapter):
    """The wall allowance one sandbox code run may ask, from the adapter's
    session surface (battery Level 0: `battery.research.PRACTICE_SECONDS`).
    A positive integer, or the runner refuses."""
    seconds = surface_value(adapter, "code_run_seconds")
    if type(seconds) is not int or seconds < 1:
        raise RunnerRefused("adapter_code_run_seconds_is_a_positive_integer")
    return seconds


def public_identity(adapter):
    """The Challenge's public development identity, from the adapter."""
    identity = surface_value(adapter, "public_identity")
    if (
        type(identity) is not dict
        or type(identity.get("id")) is not str
        or type(identity.get("version")) is not str
    ):
        raise RunnerRefused("adapter_public_identity_is_an_id_and_a_version")
    return {"id": identity["id"], "version": identity["version"]}


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


def code_run_rule(adapter, code_run_seconds):
    """The one code-run rule an Attacker session's dispatcher applies: the
    adapter's own `code_run_refusal` when it has one (battery's), which is
    the rule its `resource_accounting` family attacks, else the core's rule
    (`attack.adapter.code_run_refusal`) at the adapter's allowance. Never a
    copy: the family and the dispatcher run the same function."""
    own = getattr(adapter, "code_run_refusal", None)
    if callable(own):
        return own
    from ..attack.adapter import code_run_refusal

    return functools.partial(code_run_refusal, seconds=code_run_seconds)


class AttackerTools:
    """What the Attacker's toolbox delegates to: the real miner path, with the
    adapter's code-run rule (`code_run_rule`) enforced before dispatch. No
    count caps a session; money and time bind (OWNER-GRAPHITE-ATTACKER-01
    §5)."""

    def __init__(self, *, miner, emit, code_run_seconds, refusal=None):
        self.miner, self.emit = miner, emit
        self.code_run_seconds = code_run_seconds
        self.refusal = refusal or code_run_rule(None, code_run_seconds)

    def _wall_refusal(self, arguments):
        """The typed refusal of a code run the rule refuses (no wall
        allowance, or one over the adapter's ceiling), or None. A run that
        reaches its own allowance ends `DEADLINE` (`OWN_ALLOWANCE_ELAPSED`:
        the allowance it chose elapsed, `research_carrier.
        _observed_miner_failure`), its own outcome, never a pass; only a
        failure Carbon cannot attribute to the run stays an infrastructure
        failure."""
        if arguments.get("action") in CODE_ACTIONS:
            try:
                inner = json.loads(arguments.get("arguments_json"))
            except (TypeError, ValueError):
                inner = None
            return self.refusal(inner)
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


# -- the budget and the pods -----------------------------------------------------------------
def attacker_budget(grant, verify_pods=ATTACKER_VERIFY_PODS):
    """One Attacker run's share of the grant, split between the verify pods and
    the model-call tokens, like #504's budget but at the Attacker's worst-case
    pod count (`ATTACKER_VERIFY_PODS`). The grant's `worst_case_run_cost` is
    the combined cap; the token share is the session's model-call money cap."""
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


class NoVerifyPods:
    """The pod backend of a live Attacker run while Carbon's verify-pod rebuild
    is a seam (`POD_REBUILD_SEAM`): it launches nothing, so it needs no key and
    can spend nothing. A launch is refused before any provider write."""

    name = "none"

    def describe(self):
        return {"backend": self.name, "seam": POD_REBUILD_SEAM["name"]}

    def launch(self, job, private):
        raise PodFailure("launch", "phase4_launches_no_pod", executed=False)

    def wait(self, handle, *, deadline, cancelled):
        raise PodFailure("wait", "phase4_launches_no_pod", executed=False)

    def fetch(self, handle):
        raise PodFailure("fetch", "phase4_launches_no_pod", executed=False)

    def terminate(self, handle):
        return True

    def charge(self, handle):
        return Decimal(0)

    def recover(self, intent_id, private):
        return None


# -- the provider --------------------------------------------------------------------------
class AttackerProvider(Phase3Provider):
    """#504's `Phase3Provider` for Attacker sessions: the v2 session-limits
    rule (no call cap), compaction and the parallel-call rule, driving the
    Attacker role with `AttackerTools` against one Challenge's adapter. An
    Attacker proposes no construction: its experiment has no baseline and runs
    no pod, and its session bundles and scores nothing itself."""

    def __init__(
        self,
        *,
        root,
        grant,
        model,
        pods,
        adapter,
        miner_attach=None,
        miner_tools=None,
        **kwargs,
    ):
        self.adapter = adapter
        self._code_run_seconds = adapter_code_run_seconds(adapter)
        self._code_run_rule = code_run_rule(adapter, self._code_run_seconds)
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

    def session_limits_record(self, task):
        """The v2 record an Attacker session freezes: the base v2 rule (no
        call cap, money and elapsed time bind) and what an Attacker does,
        without the Constructor's pod, delivery and stall fields."""
        return {
            **GraphiteProvider.session_limits_record(self, task),
            "money_cap_covers": "model_calls",
            "pods_per_session": 0,
            "verify_pod_rebuild": POD_REBUILD_SEAM["state"],
            "code_run_seconds_at_most": self._code_run_seconds,
            "on_limit_stop": "record_attempts_only",
        }

    def start(self, spec, idempotency_key):
        # #504's `Phase3Provider.start` enforces the Constructor and battery's
        # baseline; the Attacker uses the same harness with its own role and
        # brief check, then the base provider's start.
        if type(spec) is TaskSpec and self.find(idempotency_key) is None:
            brief = self._brief(spec.instructions_digest)
            if brief is not None:
                if brief["role"] != RoleName.ATTACKER.value:
                    raise ProviderUnavailable("phase4_runs_the_attacker_only")
                check_attacker_observation(
                    brief["initial_observation"],
                    self.adapter,
                    code_run_seconds=self._code_run_seconds,
                )
        return GraphiteProvider.start(self, spec, idempotency_key)

    def experiment(self, run_id):
        """The run's pod accounting, with no baseline: an Attacker proposes no
        construction, so no pod runs one for it."""
        return ex.Experiment(
            root=self._dir(run_id) / "experiment",
            run_id=run_id,
            pods=self.pods,
            budget=self.budget,
            baseline=None,
            token_committed=lambda: self._tokens_usd(run_id),
            cancelled=lambda: self._state(run_id)["cancel_requested"],
            ladder=self.ladder,
            emit=lambda event_id, body: self._emit(run_id, event_id, body),
            scorer=self.scorer or self._frozen_rule,
            repository=self.repository,
            clock=self.clock,
            randomness=self.randomness,
        )

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
                    refusal=self._code_run_rule,
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
    family's name, its Track A check and its boundary as the goal. The adapter
    owns the neutral wording (lesson 2026-10-02-attacker-brief-protected-
    markers); the brief refuses if any string names protected material."""
    return [
        {"id": family.name, "check": family.check, "goal": family.boundary}
        for family in adapter.families()
    ]


def seam_vectors(adapter):
    """The families the adapter declares NOT_RUN at this level: named so the
    Attacker spends nothing on them; never a pass. Their check is left out: one
    Track A check's name (`fresh_attack_confirmation`) trips the protected
    filter, and a seam asks nothing of the Attacker."""
    return [{"id": seam.name, "state": "NOT_RUN"} for seam in adapter.level_families()]


def knowledge_brief(view, adapter):
    """What the pinned attack-knowledge snapshot says about this Challenge's
    families: the snapshot digest and per-family counts (no boundary text, no
    content). The session runs under this snapshot; B2 is recorded under it."""
    priors = view.priors(adapter.challenge_id)
    names = {family.name for family in adapter.families()}
    by_family = {
        name: {key: value for key, value in entry.items() if key != "boundaries"}
        for name, entry in priors.get("by_family", {}).items()
        if name in names
    }
    return {"snapshot": view.digest, "by_family": by_family}


def brief_observation(adapter, *, knowledge=None):
    """The Attacker's starting observation: the Challenge's public development
    identity and contract token, the construction level, the adapter's
    families and seams, the attack-knowledge snapshot it runs under, and the
    one resource limit a code run is held to. Refused if it names protected
    material (SessionBrief does the same check)."""
    observation = {
        "challenge": public_identity(adapter),
        "challenge_id": adapter.challenge_id,
        "stage": STAGE,
        "level": adapter.level,
        "contract_digest": adapter.contract_digest,
        "objective": (
            "Probe this Challenge's research path for each family below, through "
            "the tools you are given, at the construction level named. Try "
            "well-formed attempts a careful attacker would try; you may run code "
            "inside the research sandbox within its wall allowance. For each "
            "attempt, say what you tried and what the path did. A suspected breach "
            "is a report for Carbon to verify, never a verdict."
        ),
        "families": family_vectors(adapter),
        "not_run": seam_vectors(adapter),
        "attack_knowledge": knowledge,
        "limits": {
            "model_calls": None,
            "code_runs": None,
            "code_run_seconds_at_most": adapter_code_run_seconds(adapter),
        },
    }
    if toolbox.protected(observation):
        raise ValueError("refused: the attacker brief names protected material")
    return observation


def check_attacker_observation(observation, adapter, *, code_run_seconds):
    """An Attacker brief serves exactly its adapter's Challenge and level, at
    its families and wall allowance, with no baseline (an Attacker proposes no
    construction). Refused typed otherwise; the driver substitutes nothing."""
    expected = {
        "challenge": public_identity(adapter),
        "challenge_id": adapter.challenge_id,
        "level": adapter.level,
        "contract_digest": adapter.contract_digest,
    }
    for key, value in expected.items():
        if observation.get(key) != value:
            raise ProviderUnavailable("attacker_brief_" + key + "_is_not_the_adapters")
    named = [row.get("id") for row in observation.get("families") or ()]
    if named != [family.name for family in adapter.families()]:
        raise ProviderUnavailable("attacker_brief_families_are_not_the_adapters")
    limits = observation.get("limits") or {}
    if limits.get("code_run_seconds_at_most") != code_run_seconds:
        raise ProviderUnavailable("attacker_brief_code_run_seconds_mismatch")
    if "baseline_strategy" in observation:
        raise ProviderUnavailable("attacker_brief_carries_no_baseline")


def session_brief(adapter, *, checkout_commit, knowledge=None, repository=REPOSITORY):
    role = ROLES[RoleName.ATTACKER]
    manifest = boundaries.checkout_manifest(repository, role.boundary)
    return SessionBrief(
        role=RoleName.ATTACKER,
        initial_observation=brief_observation(adapter, knowledge=knowledge),
        checkout_commit=checkout_commit,
        checkout_manifest_digest=boundaries.manifest_digest(manifest),
    )


def attacker_profile(adapter):
    document = {
        "schema": PROFILE_SCHEMA,
        "challenge": adapter.challenge_id,
        "level": adapter.level,
        "contract_digest": adapter.contract_digest,
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


def ensure_campaign(control, *, checkout_digest, profile_digest):
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


# -- the attack-knowledge store ---------------------------------------------------------------
def open_store(store, atk):
    """The durable attack-knowledge store under the runner's store."""
    knowledge = atk["knowledge"]
    name = getattr(knowledge, "STORE_DIRNAME", "graphite-attack-knowledge")
    return knowledge.AttackStore(Path(store).resolve() / name)


def pin_path(store, number):
    return Path(store) / "pins" / f"session-{number}.json"


def read_pin(store, number):
    """Session `number`'s recorded store pin, checked: exactly its schema,
    its session number and a sha256 store digest. Refused typed when the
    file is missing (`session_pin_missing`) or anything else is wrong
    (`session_pin_malformed`); never re-snapshotted silently."""
    path = pin_path(store, number)
    if not path.is_file() or path.is_symlink():
        raise RunnerRefused("session_pin_missing")
    try:
        record = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise RunnerRefused("session_pin_malformed") from None
    if (
        type(record) is not dict
        or set(record) != {"schema", "session", "attack_knowledge_digest"}
        or record["schema"] != PIN_SCHEMA
        or type(record["session"]) is not int
        or record["session"] != number
        or type(record["attack_knowledge_digest"]) is not str
        or not _DIGEST.fullmatch(record["attack_knowledge_digest"])
    ):
        raise RunnerRefused("session_pin_malformed")
    return record


def pin_session(store, number, kstore, *, resume=False):
    """The store snapshot session `number` runs under, frozen once before the
    session opens, as a read-only view. B2 is recorded under its digest;
    specimens added later belong to the next snapshot.

    A new session snapshots the store and writes the pin. A resume (the
    session was already launched) reuses its recorded pin and refuses when
    the pin is missing or malformed: it never re-snapshots, which would run
    the rest of the session under a store it was not briefed on. A pin left
    by a session that never launched is checked and reused."""
    path = pin_path(store, number)
    if resume or path.exists():
        value = read_pin(store, number)["attack_knowledge_digest"]
    else:
        value = kstore.snapshot()
        path.parent.mkdir(mode=0o700, exist_ok=True)
        write_once(
            path,
            canonical(
                {
                    "schema": PIN_SCHEMA,
                    "session": number,
                    "attack_knowledge_digest": value,
                }
            ),
        )
    return kstore.pin(value)


def replay_guard(store, number, view, atk):
    """The pinned view, checked against the session's independently recorded
    pin (`read_pin`), never against itself: a view under any other store
    digest is refused (invariant 10)."""
    knowledge = atk["knowledge"]
    recorded = read_pin(store, number)
    try:
        return view.replay_recorded(recorded)
    except knowledge.KnowledgeError as refused:
        raise RunnerRefused("attack_knowledge_" + refused.code) from None


def is_finding(verdict, verify):
    """A verdict is a finding exactly when it is BREACHED, and then it carries
    its conditions (the published `verify.Verdict` contract). A verdict where
    the two disagree is refused: never read as a pass."""
    breached = verdict.outcome == verify.BREACHED
    if breached != bool(tuple(verdict.conditions)):
        raise RunnerRefused("verdict_breach_and_conditions_disagree")
    return breached


#: Verdict reasons of an infrastructure failure that are not a crash or a
#: timeout: FAILED_INFRA itself and a dispatch whose outcome is unresolved.
INFRA_FAILURE_REASONS = ("FAILED_INFRA", "DISPATCH_UNRESOLVED")


def store_outcome(verdict, verify):
    """A verdict as the knowledge store's outcome vocabulary. A timeout,
    an infrastructure failure (stored FAILED_INFRA, never folded into CRASH:
    invariant 7) or a crash, an unrebuildable construction, Graphite's own
    refusal (nothing reached the path) and anything not judged are never a
    hold."""
    if verdict.outcome == verify.BREACHED:
        return "BREACHED"
    if verdict.rebuild == verify.UNREBUILDABLE:
        return "UNREBUILDABLE"
    if verdict.outcome == verify.HELD:
        return "NOT_RUN" if verdict.refused_by == "graphite" else "HELD"
    if verdict.outcome == verify.INFRA:
        reason = (verdict.reason or "").upper()
        if "TIME" in reason:
            return "TIMEOUT"
        if any(code in reason for code in INFRA_FAILURE_REASONS):
            return "FAILED_INFRA"
        return "CRASH"
    return "NOT_RUN"  # UNDETERMINED or NOT_APPLICABLE: nothing judged


def _specimen_value(attempt, analysis):
    """The input a finding's regression specimen re-runs: the construction
    the attempt carried, else its arguments; only its identity when its
    content was withheld."""
    if attempt.withheld is not None:
        return {"attempt": attempt.identity}
    construction = analysis.construction(attempt)
    if type(construction) is dict:
        return construction
    return dict(attempt.arguments)


def _evidence(verdict, attempt):
    found = sorted(
        {
            value
            for value in verdict.evidence.values()
            if type(value) is str and _DIGEST.fullmatch(value)
        }
    )
    return found or [attempt.intent_digest]


def remember(kstore, atk, adapter, definition, attempt, verdict, rows):
    """Write one verdict to the knowledge store with its own outcome: the
    attempt always, a near miss only when the oracle reports one, and each
    finding with its regression specimen. A record the store refuses is listed
    with its typed code, never dropped silently."""
    knowledge, verify = atk["knowledge"], atk["verify"]
    if definition is None:
        rows["not_stored"].append(
            {"attempt": attempt.identity, "reason": "no_family_takes_this_attempt"}
        )
        return
    boundary = definition.boundary
    if knowledge.sealed(boundary) or knowledge.held_out(boundary):
        boundary = definition.name  # the store refuses such words; never stored
    common = {
        "challenge_id": adapter.challenge_id,
        "level": adapter.level,
        "contract_digest": adapter.contract_digest,
        "check": definition.check,
        "family": definition.name,
        "boundary": boundary,
        "strategy": STRATEGY + ":" + (attempt.operation or "unknown"),
        "attempt_id": attempt.identity,
    }

    def write(kind, call, **fields):
        try:
            call(**common, **fields)
        except knowledge.KnowledgeError as refused:
            rows["refused"].append(
                {"attempt": attempt.identity, "kind": kind, "code": refused.code}
            )
            return False
        rows["written"] += 1
        return True

    outcome = store_outcome(verdict, verify)
    payload = {**attempt.record(), "arguments": dict(attempt.arguments)}
    if not write("attempt", kstore.add_attempt, attempt=payload, outcome=outcome):
        # Its arguments named material the store refuses: keep the attempt's
        # identity and digests alone.
        payload = attempt.record()
        write("attempt", kstore.add_attempt, attempt=payload, outcome=outcome)
    if verdict.near_miss and outcome != "BREACHED":
        write(
            "near_miss",
            kstore.add_near_miss,
            attempt=payload,
            note=verdict.reason or "the oracle reported a near miss",
        )
    if outcome == "BREACHED":
        for condition in verdict.conditions:
            write(
                "finding",
                kstore.add_finding,
                condition=condition,
                specimen=_specimen_value(attempt, atk["analysis"]),
                evidence=_evidence(verdict, attempt),
                # Carbon scores only what it rebuilt; an attempt that carried no
                # construction was re-run by Carbon's own oracle as given.
                rebuilt=verdict.rebuild != verify.UNREBUILDABLE,
            )


def held_out_rows(adapter, atk, outcomes=None):
    """Each held-out control against its family's real boundary, as the
    report's `{family, control, outcome, identity, input_digest}` rows: the
    wrongful-rejection measurement only, never fed to a run or the store."""
    if outcomes is None:
        outcomes = atk["adapter"].held_out_outcomes(adapter)
    return [
        {
            "family": family,
            "control": row["control"],
            "outcome": row["outcome"],
            "identity": row.get("identity"),
            "input_digest": row.get("input_digest"),
        }
        for family, rows in outcomes.items()
        for row in rows
    ]


def check_view(adapter, family_report, b2):
    """Every Track A check, with the families the adapter declares for it.

    The check a family belongs to comes from the adapter's own declarations
    (`FamilyDef.check` for a run family, `SeamFamily.check` for a NOT_RUN
    seam), never from a report row, so a report that drops a seam's check
    cannot hide that check. A check no family or seam names is listed as
    `undeclared` (never a pass). A report or B2 row whose check is missing
    is listed under `report_rows_without_check`; one whose check disagrees
    with the adapter's declaration is refused."""
    declared = {}
    for kind, entries in (
        ("run", adapter.families()),
        ("seam", adapter.level_families()),
    ):
        for entry in entries:
            if entry.name in declared:
                raise RunnerRefused("adapter_family_declared_twice: " + entry.name)
            if entry.check not in TRACK_A_CHECKS:
                raise RunnerRefused("adapter_family_check_unknown: " + entry.name)
            declared[entry.name] = (kind, entry.check)
    unnamed = []
    for source, rows in (
        ("families", family_report["families"]),
        ("benchmark_b2", b2["families"]),
    ):
        for name, line in rows.items():
            want = declared.get(name, (None, None))[1]
            got = line.get("check")
            if got is None:
                unnamed.append({"report": source, "family": name, "declared": want})
            elif want is not None and got != want:
                raise RunnerRefused(
                    "report_check_disagrees_with_adapter: " + source + ":" + name
                )
    rows = family_report["families"]
    checks = {}
    for check in TRACK_A_CHECKS:
        checks[check] = {
            name: {
                "kind": kind,
                "status": rows[name]["status"] if name in rows else "NOT_REPORTED",
            }
            for name, (kind, named) in sorted(declared.items())
            if named == check
        }
    return {
        "checks": checks,
        "undeclared": [check for check, names in checks.items() if not names],
        "report_rows_without_check": unnamed,
    }


def record_report_findings(family_report, control, verify):
    """Every control finding the report raises (a held-out control the real
    boundary wrongly refused), through `verify.record_control`, the same
    controller path an Attacker finding takes; returns the finding ids.
    Attack findings in the report are the Attacker's verdicts, already
    recorded through `verify.record`."""
    ids = []
    for finding in family_report["findings"]:
        if finding["role"] == "attack":
            continue
        ids.append(
            verify.record_control(
                control,
                family=finding["family"],
                control=finding["attempt"],
                split=finding["role"].removesuffix("_control"),
                identity=finding["control_identity"],
                input_digest=finding.get("input_digest"),
                outcome=finding["outcome"],
                source="family_report",
            )
        )
    return ids


def carbon_side(
    store,
    control,
    provider,
    run_id,
    adapter,
    atk,
    *,
    budget,
    kstore,
    view,
    session=1,
):
    """Carbon's own side of a finished session, through the engine (module
    docstring). Returns (coverage report, B2, finding ids, store digest).

    Every finding reaches the controller through one record path, whatever
    raised it: the Attacker's verdicts (`verify.record`), held-out controls
    the boundary wrongly refused (`record_report_findings`) and the
    deterministic baseline run's breaches and refused trained controls
    (`verify.record_engine_findings`). Any of them stops expansion."""
    analysis, verify = atk["analysis"], atk["verify"]
    report, benchmark = atk["report"], atk["benchmark"]
    # The snapshot the brief named, checked against the recorded pin.
    replay_guard(store, session, view, atk)

    found = analysis.attempts(provider._dir(run_id))
    mapped = analysis.map_to_families(found, adapter)
    families = tuple(adapter.families())
    seams = tuple(adapter.level_families())
    definitions = {family.name: family for family in families}
    specimen_dir = Path(store).resolve() / "specimens"
    verdicts, findings = [], []
    rows = {"written": 0, "refused": [], "not_stored": []}
    for family, attempts in mapped.items():
        for attempt in attempts:
            verdict = verify.verify(
                attempt, adapter, pods=None, family=family, specimen_dir=specimen_dir
            )
            if is_finding(verdict, verify):
                findings.extend(verify.record(verdict, control))
            verdicts.append(verdict)
            remember(
                kstore, atk, adapter, definitions.get(family), attempt, verdict, rows
            )

    outcomes = atk["adapter"].held_out_outcomes(adapter)
    held_out = held_out_rows(adapter, atk, outcomes)
    attacker = report.attacker_runs(verdicts, families=families)
    baseline = atk["adapter"].run_adapter(adapter, budget=budget)
    family_report = report.family_report(
        attacker, controls_held_out=held_out, seams=seams
    )
    by_source = {
        "attacker": list(findings),
        "held_out_controls": record_report_findings(family_report, control, verify),
        "deterministic_baseline": verify.record_engine_findings(baseline, control),
    }
    findings = [*by_source["attacker"]]
    for source in ("held_out_controls", "deterministic_baseline"):
        findings.extend(i for i in by_source[source] if i not in findings)
    b2 = benchmark.b2(
        attacker,
        baseline,
        budget=budget,
        store_snapshot=view.digest,
        controls_held_out=held_out,
        seams=seams,
    )
    after = kstore.snapshot()
    coverage = {
        "schema": COVERAGE_SCHEMA,
        "challenge": adapter.challenge_id,
        "construction_level": adapter.level,
        "contract_digest": adapter.contract_digest,
        "attempts": len(found),
        "verdicts": [verdict.record() for verdict in verdicts],
        "families": family_report,
        "checks": check_view(adapter, family_report, b2),
        "findings": findings,
        "findings_by_source": by_source,
        "wrongful_rejection_held_out": atk["adapter"].wrongful_rejection(
            outcomes, families
        ),
        "benchmark_b2": b2,
        "attack_knowledge": {
            "pinned": view.digest,
            "suite_pin": view.suite_pin(),
            "after": after,
            **rows,
        },
        "seams": [dict(POD_REBUILD_SEAM)],
        "claims": {"security_acceptance": False, "graded": False},
    }
    return coverage, b2, findings, after


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


def run_session(
    store, control, provider, adapter, brief, number, atk, *, budget, kstore, view
):
    """Launch (or resume) Attacker session `number`, run it, and do Carbon's
    side through the engine. Returns the iteration-log entry and the coverage
    report."""
    if type(number) is not int or not 1 <= number <= control.grant.permitted_runs:
        raise ValueError("session is 1 .. the grant's permitted runs")
    _document, profile = attacker_profile(adapter)
    ensure_campaign(
        control,
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
    if final in _TERMINAL:
        coverage, _b2, findings, _after = carbon_side(
            store,
            control,
            provider,
            run_id,
            adapter,
            atk,
            budget=budget,
            kstore=kstore,
            view=view,
            session=number,
        )
    entry = {
        "schema": LOG_SCHEMA,
        "session": number,
        "run_id": run_id,
        "challenge": adapter.challenge_id,
        "construction_level": adapter.level,
        "role": RoleName.ATTACKER.value,
        "stage": STAGE,
        "provider_state": final,
        "controller_phase": str(phase),
        "failure": provider._state(run_id)["failure"] if final else None,
        "settled_usd": str(provider.usage(run_id).settled) if final else None,
        "code_runs": provider.code_runs(run_id) if final else 0,
        "findings": findings,
        "store_pinned": view.digest,
        "store_after": coverage["attack_knowledge"]["after"] if coverage else None,
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


def grant_digest(document):
    """The canonical digest of a grant document (every field)."""
    return digest(canonical(document))


#: The directory the owner's grants are committed under; a live run refuses
#: when anything in it differs from HEAD.
GRANTS_DIR = str(Path(GRANT_FILE).parent)


def _git(repository, *args):
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        check=False,
    )


def check_committed_grant(path, repository=REPOSITORY):
    """A live run's grant must be the committed GRAPHITE-GRANT-PHASE4, field
    for field, as HEAD holds it: never the working tree, which an operator
    could edit together with the copy passed in.

    - The committed blob is read from git (`git show HEAD:<GRANT_FILE>`);
      none is `phase4_grant_not_committed`.
    - The given copy's canonical digest must equal the committed blob's: any
      amount, run count, runtime or identity changed, in the copy or in the
      working tree it was taken from, is
      `grant_differs_from_the_committed_phase4_grant`.
    - HEAD must already be on a remote branch (`git branch -r --contains
      HEAD`), so the grant a run spends under is the pushed, owner-approved
      one: `grant_commit_not_pushed`.
    - The grants directory must match HEAD (no change, staged or not, and no
      untracked file): `grants_directory_has_uncommitted_changes`.

    Returns the committed grant's canonical digest."""
    try:
        given = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise RunnerRefused("phase4_grant_file_unreadable") from None
    shown = _git(repository, "show", "HEAD:" + GRANT_FILE)
    if shown.returncode != 0:
        raise RunnerRefused("phase4_grant_not_committed")
    try:
        committed = json.loads(shown.stdout)
    except ValueError:
        raise RunnerRefused("phase4_grant_file_unreadable") from None
    if grant_digest(given) != grant_digest(committed):
        raise RunnerRefused("grant_differs_from_the_committed_phase4_grant")
    pushed = _git(repository, "branch", "-r", "--contains", "HEAD")
    if pushed.returncode != 0 or not pushed.stdout.strip():
        raise RunnerRefused("grant_commit_not_pushed")
    status = _git(
        repository, "status", "--porcelain", "--untracked-files=all", "--", GRANTS_DIR
    )
    if status.returncode != 0 or status.stdout.strip():
        raise RunnerRefused("grants_directory_has_uncommitted_changes")
    return grant_digest(committed)


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
    grant, head = live_checks(args.grant)
    engy = owner_only_file(args.credential_file)
    store = _store(root, False)
    from . import miner_path

    model = live_model(grant, engy)

    def attach(*, session):
        return miner_path.attach(
            args.miner_profile, args.miner_campaign, session=session
        )

    provider = live_provider(
        store, grant=grant, model=model, adapter=adapter, miner_attach=attach
    )
    entry, coverage = run_live(
        store, grant, provider, adapter, atk, session=args.session, head=head
    )
    print(
        json.dumps({"session": entry, "coverage": coverage}, indent=1, sort_keys=True)
    )
    return 0 if entry["provider_state"] == "succeeded" else 4


# -- the live run's parts, shared with the pre-live gate (`phase4_prelive`) -------------------
def live_checks(grant_path, repository=REPOSITORY):
    """What a live run checks before anything opens: the grant file is the
    phase-4 grant for Graphite and equals the committed blob at a pushed HEAD
    with the grants directory clean (`check_committed_grant`), and HEAD, the
    checkout the brief records and Carbon's side runs from, is pushed and
    its shipped code clean (#504's `check_code_ref`). Returns (grant, head)."""
    grant = load_grant(grant_path)
    if grant.grant_id != GRANT_ID:
        raise RunnerRefused("grant_is_not_the_phase4_grant")
    if grant.provider != "graphite":
        raise RunnerRefused("grant_provider_must_be_graphite")
    check_committed_grant(grant_path, repository)
    head = _head(repository)
    check_code_ref(head, repository)
    return grant, head


def live_model(grant, credential_file, *, opener=None):
    """The live run's model access (`model.LiveModel`). `opener` replaces
    urllib's opener at the network boundary for the pre-live gate only."""
    from .model import LiveModel, ModelAccessRefused

    try:
        return LiveModel(
            grant=grant,
            credential_file=credential_file,
            provider="graphite",
            opener=opener,
        )
    except ModelAccessRefused as refused:
        raise RunnerRefused(refused.code) from None


def live_provider(store, *, grant, model, adapter, miner_attach):
    """The provider a live Attacker run drives: `AttackerProvider` on the
    store's `graphite/` root with `NoVerifyPods` (Carbon's verify-pod rebuild
    is the declared seam `POD_REBUILD_SEAM`: no pod and no compute store)."""
    return AttackerProvider(
        root=Path(store) / "graphite",
        grant=grant,
        model=model,
        pods=NoVerifyPods(),
        adapter=adapter,
        miner_attach=miner_attach,
    )


def run_live(store, grant, provider, adapter, atk, *, session, head, signals=True):
    """One live session from its controller to Carbon's side: the
    controller, the attack-knowledge store, the session's pin (reused on a
    resume, never re-snapshotted), the brief under that pin, the SIGINT and
    SIGTERM cancel handlers (`signals`), and `run_session`. Returns (log
    entry, coverage report)."""
    control = controller_for(store, provider, grant)
    try:
        kstore = open_store(store, atk)
        resume = provider.find(session_key(session)) is not None
        view = pin_session(store, session, kstore, resume=resume)
        brief = session_brief(
            adapter, checkout_commit=head, knowledge=knowledge_brief(view, adapter)
        )
        if signals:
            _install_cancel(provider, provider.run_id_for(session_key(session)))
        return run_session(
            store,
            control,
            provider,
            adapter,
            brief,
            session,
            atk,
            budget=ATTACK_BUDGET,
            kstore=kstore,
            view=view,
        )
    finally:
        control.close()


def _runs_dir(args):
    root = Path(args.root).expanduser().resolve()
    store = root / (
        "attacker-dry-run" if getattr(args, "dry_run", False) else "attacker"
    )
    return store, store / "graphite" / "runs"


def command_cancel(args):
    """Ask a running Attacker session to stop at its next checkpoint (SIGINT
    or SIGTERM in the runner does the same). It launches no pod, so there is
    nothing to reconcile after it."""
    _store_dir, runs = _runs_dir(args)
    run_id = GraphiteProvider.run_id_for(session_key(args.session))
    state_path = runs / run_id / "state.json"
    if not state_path.is_file():
        raise RunnerRefused("unknown_session")
    state = json.loads(state_path.read_bytes())
    if state["state"] in _TERMINAL:
        print(json.dumps({"session": args.session, "state": state["state"]}))
        return 0
    state["cancel_requested"] = True
    temporary = state_path.with_name("state.json.tmp")
    temporary.write_bytes(canonical(state))
    temporary.chmod(0o600)
    os.replace(temporary, state_path)
    print(json.dumps({"session": args.session, "state": "cancel_requested"}))
    return 0


def command_status(args):
    store, runs = _runs_dir(args)
    out = {}
    for run in sorted(runs.glob("graphite-*")) if runs.is_dir() else ():
        path = run / "state.json"
        out[run.name] = json.loads(path.read_bytes()) if path.is_file() else None
    pins = store / "pins"
    print(
        json.dumps(
            {
                "runs": out,
                "pins": (
                    sorted(p.name for p in pins.glob("*.json")) if pins.is_dir() else []
                ),
            },
            indent=1,
        )
    )
    return 0


def command_log(args):
    store, _runs = _runs_dir(args)
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
    """The scripted Attacker: read the Challenge, validate a recipe the
    adapter's contract refuses, ask for a code run with no wall allowance
    (refused before dispatch), and stop."""
    from .model import text, tool

    for name in DRY_RUN_SURFACE:
        surface_value(adapter, name)
    outside = surface_value(adapter, "recipe_outside_contract")
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


def dry_run(root, adapter, atk, *, miner_tools=None):
    """One scripted session and Carbon's side, sending nothing and spending
    nothing: the scripted model reports a zero charge, the whole run is under
    the network guard (`phase4_prelive.network_guard`: any socket connect or
    name lookup raises), and a run that settles anything other than zero
    fails (exit 4)."""
    from .model import ScriptedModel
    from .phase4_prelive import network_guard
    from .pods import ScriptedPods

    store = root / "attacker-dry-run"
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(mode=0o700)
    grant = dry_run_grant()
    with network_guard() as attempts:
        provider = AttackerProvider(
            root=store / "graphite",
            grant=grant,
            model=ScriptedModel(dry_run_script(adapter), charged_micro=0),
            pods=ScriptedPods(),
            adapter=adapter,
            miner_tools=miner_tools,
            randomness=lambda n: b"\x00" * n,
        )
        control = controller_for(store, provider, grant)
        try:
            kstore = open_store(store, atk)
            view = pin_session(store, 1, kstore)
            brief = session_brief(
                adapter,
                checkout_commit="0" * 40,
                knowledge=knowledge_brief(view, adapter),
            )
            entry, coverage = run_session(
                store,
                control,
                provider,
                adapter,
                brief,
                1,
                atk,
                budget=ATTACK_BUDGET,
                kstore=kstore,
                view=view,
            )
        finally:
            control.close()
    settled_zero = entry["settled_usd"] is not None and Decimal(
        entry["settled_usd"]
    ) == Decimal(0)
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
            "settled_is_zero": settled_zero,
            "network_attempts": list(attempts),
        },
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    ok = entry["provider_state"] == "succeeded" and settled_zero and not attempts
    return 0 if ok else 4


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
    run.add_argument("--miner-profile")
    run.add_argument("--miner-campaign")
    run.add_argument("--session", type=int, default=1)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--root", required=True)
    cancel.add_argument("--session", type=int, required=True)
    for name in ("status", "log"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--dry-run", action="store_true")
    prelive = sub.add_parser("prelive")
    prelive.add_argument("--root", required=True)
    prelive.add_argument("--challenge", help=challenge_help)
    prelive.add_argument(
        "--grant",
        default=str(REPOSITORY / GRANT_FILE),
        help="the grant file a live run would pass (default: the committed one)",
    )
    args = parser.parse_args(argv)
    return {
        "run": command_run,
        "cancel": command_cancel,
        "status": command_status,
        "log": command_log,
        "prelive": command_prelive,
    }[args.command](args)


def command_prelive(args):
    """The pre-live gate (`phase4_prelive.prelive`)."""
    from .phase4_prelive import prelive

    atk = attack_modules()
    adapter = get_adapter(atk, args.challenge or BATTERY_CHALLENGE, BATTERY_LEVEL)
    return prelive(_root(args.root), adapter, atk, grant_path=args.grant)


if __name__ == "__main__":
    sys.exit(main())
