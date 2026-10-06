"""GRAPHITE-01 phase 3: the Constructor at Level 0, and its runner.

    python -m carbon.agent_campaign.graphite.phase3 run --root DIR --challenge TOKEN \
        --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json \
        --credential-file PATH \
        (--runpod-key-file PATH | --runpod-key-env RUNPOD_API_KEY) \
        --miner-profile PROFILE.json --miner-campaign ID --code-ref SHA \
        --literature-snapshot SNAPSHOT.json [--allow-unchecked-cards] [--session N] \
        [--level N] [--compute carrier --image-manifest C03_IMAGE.json] \
        [--score-variant VERSION]
    python -m carbon.agent_campaign.graphite.phase3 run --root DIR --challenge TOKEN --dry-run \
        [--literature-snapshot SNAPSHOT.json [--allow-unchecked-cards]] [--level N]
    python -m carbon.agent_campaign.graphite.phase3 cancel --root DIR --session N
    python -m carbon.agent_campaign.graphite.phase3 reconcile --root DIR --challenge TOKEN --grant G \
        (--runpod-key-file PATH | --runpod-key-env RUNPOD_API_KEY) --code-ref SHA
    python -m carbon.agent_campaign.graphite.phase3 status --root DIR
    python -m carbon.agent_campaign.graphite.phase3 rebuild --bundle DIR
    python -m carbon.agent_campaign.graphite.phase3 proposals --root DIR
    python -m carbon.agent_campaign.graphite.phase3 admission-controller init \
        --root DIR --challenge TOKEN --grant ZERO_SPEND_ADMISSION_GRANT

`reconcile` prints its report and exits 0 when every pod is settled, or 4
when one is not; then stderr carries one typed line
(`reconcile_pods_not_settled`) with each unsettled intent's age and, for an
uncertain create, the UTC minute at or after which a re-run can settle it.

`--compute carrier` runs proposals in the isolated C-03 carrier on this
operator host instead of RunPod (`carrier_pods`, VALIDATOR-06): no RunPod
key, no provider money, Levels 0-3 only, and the lane's declared program
deadline. A tokens-only grant (`TOKENS_ONLY_GRANTS`) runs only there.

One session is one run of the Constructor behind the #475 campaign controller,
under one owner grant that covers both its model calls and its pods
(OWNER-GRAPHITE-03: "$15 runpod included"):

1. the controller reserves the grant's `worst_case_run_cost` for the run and
   refuses a run past `permitted_runs` or the ceiling (tokens and pods
   together, as the provider reports both);
2. `Phase3Provider` drives the research loop with the Constructor's prompt and
   closed tools. Its miner tools go through the real miner path
   (`miner_path.attach`, the standard miner MCP door) to the named DEVELOPMENT
   campaign; its proposals go to Carbon's runner (`experiment`), which admits
   each one through the reconstruction gate, runs it on a pod, checks the
   pod's build against Carbon's own, and scores it by that Challenge's frozen
   rule;
3. inside the run, every model call is reserved before dispatch (the research
   ledger, capped at the run's token share) and every pod before launch (the
   pod ledger, against the run's combined cap); each settles from the
   provider's reported charge, and an unknown outcome keeps its reservation;
4. after the loop, Carbon bundles the session's best improvement, with
   ablations, as a PR-ready directory, and rebuilds it from the bundle alone;
5. findings (an unrebuildable proposal, a rebuild mismatch) are recorded on
   the controller, where they stop any later expansion.

**Construction level** (`--level`, GRAPHITE-DEV-VARIANTS-01). Level 0, the
default, constructs inside the recorded miner-facing contract exactly as
before. A level above 0 runs the development-only contract variant
`development_variants.DEV_VARIANTS` registers for the Challenge and level
(OWNER-GRAPHITE-TEST-WAVE-03 §1): the session's permission profile is the
variant itself, the controller records it as a development expansion, and
every proposal compiles through the variant's own path. An unregistered or
unrecorded level is refused before anything runs.

**Development score variant** (`--score-variant VERSION`, VALIDATOR-09; see
`score_variant`). A registered development score variant of the session's
Challenge, at Level 0, is resolved before any spend and pinned in the brief
and the permission profile. Every result carries its result beside the
frozen rule's, and every result, the summary and the delivery its label; a
resume under another variant is refused. Without the flag nothing changes.

**Literature** (GRAPHITE-D28, D29). A live run reads a frozen phase-2 snapshot
(`phase2 snapshot`), named by `--literature-snapshot`; it refuses to start
without one. The session record pins the snapshot file's digest, the offer
policy and every offered card, and a resume with a different snapshot or
policy is refused before anything runs. By default the session is offered
only cards a person checked CORRECT; `--allow-unchecked-cards` adds unchecked
cards, marked UNCHECKED in every tool result and in the session record. No
checked card means an empty index, stated in the record and in `status`;
nothing falls back to another index. The dry run without a snapshot serves the
phase-1 synthetic fixture and records that it did.

**Next-level proposals** (GRAPHITE-D30). `proposals` lists the typed records
a Planner or Constructor session wrote with `graphite_propose_next_level`; a
run's bundle carries its own. A proposal widens nothing and is never scored.

`DIR` is a private directory outside the repository. Nothing here opens a
pull request, writes under `docs/`, or touches chain state.

**Credentials.** Keys by file path, as phase 4 takes them: `--credential-file`
names an owner-only file holding the Engy key, checked by its metadata alone
with phase 4's rule (`phase4.owner_only_file`). `--credential-env ENGY_API_KEY`
is kept for older launchers: it copies the variable into a 0600 file in a fresh
0700 directory, removed on exit. The RunPod key as the pod tooling keeps it: an
owner-only file (`~/.runpod/api_key` for `pod_control`); `--runpod-key-env
RUNPOD_API_KEY` copies the variable the same way. Neither key is printed,
logged or given to the agent. `python -m carbon.agent_campaign.graphite
run-checked` (`run_checked`) takes key files only.

**Ends and next steps.** A session that ended (`succeeded`, `failed`,
`cancelled`) is terminal: running the same `run` again prints its recorded
end. `run` and `status` carry `next_step`; a `failed` session with code
`reconciliation_required` names `reconcile`, then a new `--session N`.
`run` and `status` also carry `pod_charges`: each pod's booked amount beside
its provider charge or estimate, with the basis (`experiment.CHARGE_BASES`).

`--dry-run` runs the whole session with a scripted model, a scripted pod
account and a recording miner tool, under a synthetic grant, writing only
under `DIR/dry-run`. Carbon's admission, frozen-rule scoring, comparison,
bundle and clean rebuild are real; the predictions are SYNTHETIC. Beside the
session it runs `pods.real_path_check`: the live pod backend (the operator
compute store, service and adapter) built on the main thread and driven
through `asyncio.to_thread`, concurrently, with RunPod in memory, and the dry
run fails unless that check is OK (POD-STORE-THREADS-01). Its first
turn returns three tool calls at once, as live session 1's model did, so the
parallel-call rule runs before any spend: under `PARALLEL_CALLS_V2`
(LP-PROD-A) all three run, and the dry run reports how many calls of
several-call turns ran and how many did not. It also reports the session's
limits: no model-call cap, the run's money cap and its elapsed limit; and the
Constructor's model selection (GRAPHITE-D34): adapter, model, input window,
admission ceiling, output cap, timeout and per-call reservation. It also runs
`experiment.failure_path_check` (GRAPHITE-POD-LOGS-RETRY-01), which must be OK:
a pod exiting non-zero keeps its logs, bounded, and a baseline failing as
infrastructure is retried once and scores; a pod whose GPU probe fails
(`environment`) is relaunched once and scores, and a second probe failure
stops the session `FAILED_INFRA` (GRAPHITE-POD-GPU-PROBE-01). The provider
ends a session the experiment stopped that way `failed`, code `failed_infra`,
with no agent charge.

**Model access** (GRAPHITE-D34, 2026-10-04). A new session opens on
`engy-chat` (`ADAPTER`): Engy's Chat Completions replies report each call's
charge (`x_engy.charged_micro`), which settles it; its Messages endpoint
reports none, so a call there keeps its full reservation. The Constructor's
input window is its model's whole published context, with a 600 s timeout
(`roles.MODEL_SETTINGS`). A session recorded before resumes with the
selection its record froze.

**Session limits** (OWNER-GRAPHITE-MINER-01 §6, 2026-10-03). A new session
runs under `provider.SESSION_LIMITS_V2`: no session-turn cap (the 150 of
GRAPHITE-D26 is historical) and no per-role call cap. The grant's
`worst_case_run_cost`, the controller's reservation for the run and the cap
every model call and pod is admitted against, is the hard bound, with the
grant's `max_runtime_s`: a model call is admitted only when its timeout fits
the remaining time, and a pod only when it can finish within it. The grant
arithmetic is unchanged. Stall detection and its one-rung escalation stay. A
session recorded under the old cap resumes under it, byte-identically.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.data import write_once
from carbon.development_session.model_provider import selection_from_record
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_loop import parallel_call_counts, run_epoch

from .. import boundaries
from ..grant import SpendingGrant
from ..provider import (
    Capabilities,
    IntegrationMode,
    ProviderUnavailable,
    RunStatus,
    TaskSpec,
)
from . import delivery as deliver_
from . import experiment as ex
from . import grant_binding, next_level
from . import literature as lit
from . import score_variant as sv
from . import tools as toolbox
from .cli_usage import ChallengeParser, challenge_help, next_step
from .ladder import Ladder, LadderError
from .provider import (
    EPOCH,
    NANO_PER_USD,
    OWNER,
    PROVIDER,
    SESSION_LIMITS_V1,
    SESSION_LIMITS_V2,
    GraphiteLedger,
    GraphiteProvider,
    RunCapReached,
    SessionBrief,
    SessionMismatch,
    SessionStopped,
    limit_dimension,
    tool_text_of,
)
from .roles import (
    CONSTRUCTOR_SESSION_TURNS,
    CONSTRUCTOR_STALL_ATTEMPTS,
    PARALLEL_RULES,
    PROPOSE,
    ROLES,
    TOOL_TEXT_V2,
    RoleName,
)

REPOSITORY = Path(__file__).resolve().parents[3]
CAMPAIGN = "graphite-phase3"
OPERATOR = "graphite-phase3-runner"
WORKSPACE = "graphite-phase3-workspace"
CREDENTIAL_REF = "graphite-phase3-engy"
PROFILE_SCHEMA = "carbon.graphite.phase3.permission-profile.v1"
_TERMINAL = ("succeeded", "failed", "cancelled")
#: The Engy adapter a new phase-3 session opens on (GRAPHITE-D34; owner,
#: 2026-10-04: "perfect. I approve what comes back"). Engy's Chat Completions
#: replies carry `x_engy.charged_micro`, which settles each call; its Messages
#: endpoint returns no `x_engy` block (measured 2026-09-27, the then-current
#: finding 7), so every call of live sessions 1 and 2 on `engy-anthropic` kept
#: its full reservation. A recorded session keeps the adapter it opened on.
ADAPTER = "engy-chat"


# -- the Constructor's tools ---------------------------------------------------------------
#: Under the v2 session-limits rule, a proposal whose pods cannot finish within
#: the run's remaining elapsed time is refused before anything starts.
PROPOSAL_NO_TIME = "proposal_cannot_fit_remaining_time"
#: Under v2, an ablation whose pod cannot finish within the run's remaining
#: elapsed time is not run (delivery's other such status is
#: `NOT_RUN_NO_PODS_LEFT`).
ABLATION_NO_TIME = "NOT_RUN_NO_TIME"


def pod_seconds(budget):
    """One pod's full lifetime, its deadline from launch (`Phase3Budget`)."""
    return budget.pod_minutes * 60


class Phase3Tools:
    """What the Constructor's toolbox delegates to: the proposal tool goes to
    Carbon's runner; every miner SDK tool goes to the real miner path.

    `seconds_left` reads the run's remaining elapsed time under the v2
    session-limits rule (None under v1, which has no such gate): a proposal
    starts only when its pod, and the baseline's when the baseline has not
    run, can finish within it."""

    def __init__(self, *, experiment, miner, seconds_left=None):
        self.experiment, self.miner = experiment, miner
        self.seconds_left = seconds_left

    async def call(self, name, arguments, identity):
        if name == PROPOSE:
            late = self._no_time()
            if late is not None:
                return late
            # A pod runs for minutes: off the event loop, so the miner path's
            # own tasks keep running. A process death still propagates.
            return await asyncio.to_thread(
                self.experiment.propose_tool, arguments, identity
            )
        if self.miner is None:
            return toolbox.refusal(
                toolbox.UNAVAILABLE,
                "miner_path_not_attached",
                reason="This session has no miner campaign attached; nothing ran.",
            )
        return await self.miner.call(name, arguments, identity)

    def _no_time(self):
        """The typed refusal of a proposal whose pods cannot finish within the
        run's remaining elapsed time, or None. The loop journals the answer, so
        a replay reads it and never re-decides."""
        if self.seconds_left is None:
            return None
        left = self.seconds_left()
        pods = 1 + self.experiment.pods_before_proposal()
        needed = pods * pod_seconds(self.experiment.budget)
        if left is None or needed <= left:
            return None
        return toolbox.refusal(
            "REJECTED_BEFORE_DISPATCH",
            PROPOSAL_NO_TIME,
            reason=(
                "The run's remaining time cannot hold this proposal's pod"
                + (" and the baseline's" if pods == 2 else "")
                + "; nothing ran. Select a practised recipe or stop."
            ),
            pods_needed=pods,
            seconds_needed=needed,
            seconds_left=max(0, int(left)),
        )


class TimeBoundExperiment:
    """The experiment as a v2 session's delivery sees it: an ablation that has
    not begun, and whose pod cannot finish within the run's remaining elapsed
    time, is not run and is answered `NOT_RUN_NO_TIME`; everything else is the
    experiment's own. One that began before a restart is the experiment's to
    close (it never reruns one), so it is passed through."""

    def __init__(self, experiment, seconds_left):
        self._experiment, self._seconds_left = experiment, seconds_left

    def __getattr__(self, name):
        return getattr(self._experiment, name)

    def run(self, pid, kind, strategy, *, why, parent=None):
        begun = (self._experiment.root / "proposals" / pid / "intent.json").exists()
        left = self._seconds_left()
        if (
            not begun
            and left is not None
            and pod_seconds(self._experiment.budget) > left
        ):
            return {
                "proposal_id": pid,
                "kind": kind,
                "status": ABLATION_NO_TIME,
                "strategy_digest": digest(canonical(strategy)),
                "scored": False,
            }
        return self._experiment.run(pid, kind, strategy, why=why, parent=parent)


# -- the provider --------------------------------------------------------------------------
class Phase3Ledger(GraphiteLedger):
    """The run's research ledger, held to the run's combined cap: a model call
    is reserved only while tokens committed, plus pods committed, plus the
    call's own reservation stay within the grant's worst-case run cost. A
    replayed call (already reserved) is never refused."""

    def __init__(self, root, *, clock, cancelled, crash, admits, stopped=None):
        super().__init__(root, clock=clock, cancelled=cancelled, crash=crash)
        self._admits = admits
        self._stopped = stopped

    def _reserve(self, identity, **kwargs):
        # A session Carbon stopped as infrastructure (a repeated pod
        # environment failure) reserves nothing new; a replay still reads.
        stop = None if self._stopped is None else self._stopped(identity)
        if stop is not None:
            raise SessionStopped(stop)
        nano = (kwargs.get("resources") or {}).get("provider_nanodollars") or 0
        if nano and not self._admits(identity, nano):
            raise RunCapReached("run_cap_tokens_plus_pods")
        return super()._reserve(identity, **kwargs)


#: The budget-status rule a new phase-3 session records (AGENT-DOOR-USABILITY-01
#: A5, approved by the Test Lead): its turn status drops the campaign
#: research-trial line when the run ledger meters no research trials (its
#: budget is 0: a phase-3 experiment runs on pods, metered by the run's money
#: cap and pod limit), instead of telling the agent "0 of 0 research trials
#: left" (`research_loop.budget_status`, `omit_unmetered_trials`). A session
#: whose record names no rule - every one opened before - keeps the v1 status
#: bytes on replay and resume.
BUDGET_STATUS_V2 = "carbon.graphite.budget-status.v2"
BUDGET_STATUSES = (BUDGET_STATUS_V2,)


def budget_status_of(opened):
    """The budget-status rule a session record carries: None (v1, the
    historical status) when it names none; an unknown rule resumes nothing."""
    rule = opened.get("budget_status")
    if rule is not None and rule not in BUDGET_STATUSES:
        raise SessionMismatch("budget_status_unknown")
    return rule


class Phase3Provider(GraphiteProvider):
    """`GraphiteProvider` for the Constructor's Level-0 sessions.

    Adds, per run: the pod runner and its ledger, the real miner path, the
    combined token-and-pod spend, pod termination on cancellation and after a
    crash, delivery, and the stall rule's escalation.

    A session under the v2 limits rule has no call cap, so the run's money cap
    or its elapsed limit is what ends a session the agent does not end. Its
    pods stay inside both: a pod starts only when the run cap holds its
    reservation and it can finish within the run's remaining elapsed time (a
    proposal that cannot is refused `proposal_cannot_fit_remaining_time`; an
    ablation that cannot is recorded `NOT_RUN_NO_TIME`). A limit stop still
    closes the session's work: the best improvement is bundled, with the
    ablations that fit, and the stall rule's escalation applies. The session
    still ends `failed` with `run_cap_reached` and the dimension, as a capped
    run always has.
    """

    #: A v1 Constructor session's call cap (GRAPHITE-D26); see `roles`.
    HISTORICAL_SESSION_TURNS = CONSTRUCTOR_SESSION_TURNS
    #: The budget-status rule a new session records (`BUDGET_STATUS_V2`).
    NEW_SESSION_BUDGET_STATUS = BUDGET_STATUS_V2

    def __init__(
        self,
        *,
        root,
        grant,
        model,
        pods,
        miner_attach=None,
        miner_tools=None,
        scorer=None,
        repository=REPOSITORY,
        randomness=os.urandom,
        adapter_id=None,
        scoring=None,
        score_variant=None,
        hidden=None,
        **kwargs,
    ):
        if type(grant) is not SpendingGrant:
            raise ProviderUnavailable("spending_grant_required")
        if grant.zero_spend:
            # An admission controller's grant runs no session.
            raise ProviderUnavailable("grant_is_zero_spend")
        #: The session's development score variant (VALIDATOR-09), resolved
        #: before spend (`score_variant.resolve`), or None. It wraps the
        #: Challenge's own frozen rule, never an injected scorer.
        if score_variant is not None and scorer is not None:
            raise ProviderUnavailable("score_variant_wraps_the_frozen_rule_only")
        self.score_variant = score_variant
        try:
            # The session's Challenge (`ChallengeScoring`, VALIDATOR-01): the
            # only registered one unless named.
            self.scoring = challenge_scoring.resolve(scoring)
        except challenge_scoring.ScoringUnavailable as refused:
            raise ProviderUnavailable(refused.code) from None
        # The session reads its own Challenge's literature only.
        check_literature_challenge(
            kwargs.get("literature_index"),
            self.scoring.challenge_id,
            ProviderUnavailable,
        )
        try:
            # The backend's own rate when it declares one (the CPU carrier
            # lane costs no provider money); otherwise RunPod's.
            self.budget = ex.phase3_budget(
                grant, self.scoring, getattr(pods, "hourly_usd", None)
            )
        except ex.BudgetRefused as refused:
            raise ProviderUnavailable(refused.code) from None
        super().__init__(
            root=root,
            grant=grant,
            model=model,
            miner_tools=miner_tools,
            # New sessions open on engy-chat (GRAPHITE-D34).
            adapter_id=ADAPTER if adapter_id is None else adapter_id,
            **kwargs,
        )
        # A grant registering a start model (OWNER-GRAPHITE-PHASE3-R4-01)
        # raises its start roles' ladder to that rung; every other grant
        # keeps the base ladder, exactly as before.
        start_rungs = grant_binding.start_rungs(grant)
        if start_rungs:
            self.ladder = Ladder(Path(root) / "ladder", start_rungs=start_rungs)
        self.pods, self.miner_attach = pods, miner_attach
        #: `run_id -> HiddenPool`, or None: each run's hidden-pool scoring
        #: through the real validator (VALIDATOR-13, `hidden_score`).
        self.hidden = hidden
        self.scorer, self.repository, self.randomness = scorer, repository, randomness
        #: The campaign controller this provider's runs record findings on as
        #: they are found, and tag next-level proposals from (`bind_findings`).
        self.findings_controller = None

    # -- findings, recorded before the results they affect -----------------------------------
    def bind_findings(self, control):
        """Record each finding a run's experiment finds on `control` when it is
        found, and tag every next-level proposal with `control`'s tag as of
        when it is written (conditional-evidence.v2 "ordering")."""
        self.findings_controller = control

    def conditional_tag(self):
        control = self.findings_controller
        return None if control is None else control.conditional_tag()

    def _record_finding(self, finding):
        control = self.findings_controller
        if control is not None:
            control.record_finding(
                finding["id"], finding["condition"], canonical(finding["evidence"])
            )

    # -- configuration ---------------------------------------------------------------------
    def caps(self, rule=None):
        caps = super().caps(rule)
        caps["provider_nanodollars"] = ex.usd_to_nano(self.budget.token_allowance_usd)
        return caps

    def _grant_record(self):
        return {**super()._grant_record(), "phase3_budget": self.budget.record()}

    def session_limits_record(self, task):
        """The v2 record, with the run's whole cap (tokens and pods together,
        the controller's reservation), the pod limit, the pod admission rule
        that keeps every pod inside the elapsed limit, the stall rule that
        stays, and what a session a limit stopped still does."""
        return {
            **super().session_limits_record(task),
            "money_cap_covers": "model_calls_and_pods",
            "pods_per_session": self.budget.max_pods,
            "pod_seconds": pod_seconds(self.budget),
            # A pod starts only when it fits the run cap and can finish within
            # the run's remaining elapsed time (a proposal also counts the
            # baseline's pod when the baseline has not run).
            "pod_admission": "money_cap_and_remaining_elapsed_seconds",
            "stall_attempts": CONSTRUCTOR_STALL_ATTEMPTS,
            "stall_escalation": "one_rung",
            "on_limit_stop": "bundle_best_improvement_and_escalate_on_stall",
        }

    def _seconds_left(self, run_id):
        """The run's remaining elapsed time by its research ledger, the bound
        every model call is admitted against: from the ledger's first
        reservation, `max_runtime_s` long. None when the ledger has no limit."""
        status = CampaignLedger(self._dir(run_id) / "ledger", clock=self.clock).status(
            owner=OWNER
        )
        limit = status["elapsed_limit_seconds"]
        if limit is None:
            return None
        started = status["started_unix"]
        if started is None:
            return limit
        return started + limit - self.clock()

    def _time_gate(self, run_id, opened):
        """The remaining-time reader the pod gates use under the v2 rule; None
        under v1, which starts pods as it always did."""
        if self.rule_of(opened) != SESSION_LIMITS_V2:
            return None
        return lambda: self._seconds_left(run_id)

    def _delivery_view(self, run_id, experiment):
        """What delivery runs its ablations through: under v2, the experiment
        bounded by the run's remaining elapsed time; under v1, the experiment."""
        gate = self._time_gate(run_id, self._opened(run_id))
        return experiment if gate is None else TimeBoundExperiment(experiment, gate)

    def _manifest(self, opened):
        return {**super()._manifest(opened), "implementation": "graphite-phase3"}

    def opening_rules(self):
        """A new session records the budget-status rule it runs under
        (`BUDGET_STATUS_V2`); none when this provider records none."""
        rule = self.NEW_SESSION_BUDGET_STATUS
        rules = {} if rule is None else {"budget_status": rule}
        # The grant's run conditions (start model, lowest level, token share),
        # only for a grant that registers them: every other record unchanged.
        conditions = grant_binding.run_conditions(self.grant)
        if conditions is not None:
            rules["run_conditions"] = conditions
        return rules

    def _literature_record(self):
        """A phase-3 session records where its literature came from; the
        phase-1 fixture says it is one (GRAPHITE-D28)."""
        record = super()._literature_record()
        if type(self.literature) is lit.LiteratureIndex:
            record = {
                **record,
                "source": {"kind": FIXTURE_SOURCE},
                "note": FIXTURE_NOTE,
            }
        return record

    def start(self, spec, idempotency_key):
        if type(spec) is TaskSpec and self.find(idempotency_key) is None:
            brief = self._brief(spec.instructions_digest)
            if brief is not None:
                if brief["role"] != RoleName.CONSTRUCTOR.value:
                    raise ProviderUnavailable("phase3_runs_the_constructor_only")
                observation = brief["initial_observation"]
                check_observation(observation, self.scoring)
                if observation.get("literature") != literature_brief(self.literature):
                    raise ProviderUnavailable("brief_literature_is_not_the_sessions")
                if observation.get("score_variant") != sv.identity_of(
                    self.score_variant
                ):
                    raise ProviderUnavailable("brief_score_variant_is_not_the_sessions")
                # OWNER-GRAPHITE-PHASE3-R4-01: a grant's lowest construction
                # level and its start rung, checked before a session opens.
                refused = grant_binding.level_refusal(
                    self.grant, observation.get("level")
                ) or grant_binding.start_model_refusal(
                    self.grant,
                    RoleName.CONSTRUCTOR,
                    self.ladder.model(RoleName.CONSTRUCTOR),
                )
                if refused is not None:
                    raise ProviderUnavailable(refused)
        return super().start(spec, idempotency_key)

    # -- the run's experiment ----------------------------------------------------------------
    def experiment(self, run_id):
        opened = self._opened(run_id)
        brief = self._brief(opened["brief"]["digest"])
        # VALIDATOR-09: a run's results are labelled with the score variant its
        # brief pinned (None: none, exactly as before).
        scored = recorded_score_variant(brief)
        return ex.Experiment(
            root=self._dir(run_id) / "experiment",
            run_id=run_id,
            pods=self.pods,
            budget=self.budget,
            baseline=brief["initial_observation"]["baseline_strategy"],
            token_committed=lambda: self._tokens_usd(run_id),
            cancelled=lambda: self._state(run_id)["cancel_requested"],
            ladder=self.ladder,
            emit=lambda event_id, body: self._emit(run_id, event_id, body),
            scorer=self._session_scorer(scored),
            repository=self.repository,
            clock=self.clock,
            randomness=self.randomness,
            scoring=self.scoring,
            construction_level=recorded_level(opened, self.scoring, scored),
            seconds_left=self._time_gate(run_id, opened),
            development_variant=recorded_variant(opened, self.scoring),
            on_finding=self._record_finding,
            **({} if scored is None else {"score_variant": scored}),
            hidden=None if self.hidden is None else self.hidden(run_id),
        )

    def _session_scorer(self, scored):
        """The run's scorer: as before without a score variant. A run whose
        brief pinned another variant than this provider's never scores
        (`score_variant_is_not_the_sessions`, only when a score is needed, so
        cancellation and reconciliation still run)."""
        if scored == sv.identity_of(self.score_variant):
            return self.scorer or self._frozen_rule

        def refused():
            raise ProviderUnavailable("score_variant_is_not_the_sessions")

        return refused

    def _next_level(self, run_id, role):
        """The next-level writer bound to this session's exact Challenge. Each
        proposal carries `conditional_tag()` as of when it is written."""

        def write(arguments, identity):
            return next_level.propose_tool(
                arguments,
                literature=self.literature,
                run_dir=self._dir(run_id),
                run_id=run_id,
                identity=identity,
                role=role.name.value,
                scoring=self.scoring,
                conditional=self.conditional_tag(),
            )

        return write

    def _frozen_rule(self):
        """The frozen rule, loaded once per provider (its material is pinned).
        Under a development score variant, the variant's rule over it
        (`score_variant.VariantRule`, VALIDATOR-09)."""
        if getattr(self, "_rule", None) is None:
            self._rule = sv.rule_for(
                ex.frozen_rule(self.repository, self.scoring), self.score_variant
            )
        return self._rule

    def _ledger(self, run_id):
        return Phase3Ledger(
            self._dir(run_id) / "ledger",
            clock=self.clock,
            cancelled=lambda: self._state(run_id)["cancel_requested"],
            crash=self._checkpoint_crash,
            admits=lambda identity, nano: self._admits_call(run_id, identity, nano),
            stopped=lambda identity: self._stopped_for(run_id, identity),
        )

    def _stopped_for(self, run_id, identity):
        """The reason the run's experiment stopped the session, for a call not
        yet reserved; None for a replay or a running session."""
        if any(call["identity"] == identity for call in self._calls(run_id)):
            return None
        stop = self.experiment(run_id).stopped()
        return None if stop is None else stop["reason_code"]

    def _admits_call(self, run_id, identity, nano):
        if any(call["identity"] == identity for call in self._calls(run_id)):
            return True  # a replay reserves nothing new
        committed = self._tokens_usd(run_id) + self.experiment(run_id).pod_committed()
        return committed + Decimal(nano) / NANO_PER_USD <= self.budget.run_cap_usd

    def _tokens_usd(self, run_id):
        settled, pending = GraphiteProvider._spend(self, run_id)
        return Decimal(settled + pending) / NANO_PER_USD

    def _spend(self, run_id):
        settled, pending = GraphiteProvider._spend(self, run_id)
        pods = self.experiment(run_id).ledger.committed()
        return (
            settled + ex.usd_to_nano(pods[0]),
            pending + ex.usd_to_nano(pods[1]),
        )

    def _unresolved(self, run_id):
        experiment = self.experiment(run_id)
        return (
            super()._unresolved(run_id)
            or bool(experiment.ledger.live())
            or bool(experiment.interrupted())
        )

    def status(self, run_id):
        status = super().status(run_id)
        if status.workers_terminated and self.experiment(run_id).ledger.live():
            # A pod not verified gone is a worker that may still run.
            return RunStatus(status.state, status.worker_ids, False)
        return status

    def request_cancel(self, run_id):
        """Ask a running worker, in this process or another, to stop: it
        terminates its pod and finishes cancelled at its next checkpoint."""
        state = self._state(run_id)
        if state["state"] in _TERMINAL:
            return state["state"]
        self._set_state(run_id, cancel_requested=True)
        self._emit(run_id, "cancel-requested", {"kind": "cancel_requested"})
        return "cancel_requested"

    def cancel(self, run_id):
        state = self._state(run_id)
        if state["state"] not in _TERMINAL and run_id not in self._active:
            # No worker here: terminate whatever pods the run left first.
            self.experiment(run_id).reconcile()
        return super().cancel(run_id)

    def run(self, run_id):
        state = self._state(run_id)
        if state["state"] not in _TERMINAL:
            experiment = self.experiment(run_id)
            experiment.reconcile()
            if experiment.ledger.live():
                return self._finish(
                    run_id, "failed", {"code": "pod_termination_unverified"}, None
                )
        return super().run(run_id)

    @contextlib.asynccontextmanager
    async def _attached(self, run_id):
        if self.miner_attach is None:
            yield self.miner_tools
            return
        async with self.miner_attach(session=run_id.removeprefix("graphite-")) as tools:
            yield tools

    async def _epoch(self, run_id, ledger, role, brief, selection):
        experiment = self.experiment(run_id)
        opened = self._opened(run_id)
        try:
            async with self._attached(run_id) as miner:
                sdk = toolbox.GraphiteToolbox(
                    role=role,
                    literature_index=self.literature,
                    emit=lambda event_id, body: self._emit(run_id, event_id, body),
                    miner_tools=Phase3Tools(
                        experiment=experiment,
                        miner=miner,
                        seconds_left=self._time_gate(run_id, opened),
                    ),
                    next_level=self._next_level(run_id, role),
                )
                report = await run_epoch(
                    ledger,
                    owner=OWNER,
                    epoch=EPOCH,
                    sdk=sdk,
                    credential_file=None,
                    initial_observation=brief["initial_observation"],
                    transport=self.model.transport_for(selection),
                    provider=selection,
                    instructions=role.prompt,
                    tools=role.tool_schemas(tool_text_of(opened)),
                    # Every tool call of a turn runs, in the model's order
                    # (LP-PROD-A, superseding GRAPHITE-D33's first-call rule).
                    parallel_calls=PARALLEL_RULES.get(role.name),
                    # v2: no call cap, count-free limits and compaction; v1:
                    # the historical 150-call cap (`_loop_limits`).
                    **self._loop_limits(opened),
                    # The status rule the record names: v2 drops the unmetered
                    # "0 of 0 research trials" line; none keeps v1's bytes.
                    omit_unmetered_trials=(
                        budget_status_of(opened) == BUDGET_STATUS_V2
                    ),
                )
        except ValueError as error:
            if (
                limit_dimension(error) is not None
                and self.rule_of(opened) == SESSION_LIMITS_V2
            ):
                self._close_at_limit(run_id, experiment)
            raise
        if report["status"] != "RECONCILIATION_REQUIRED":
            self._deliver(run_id, experiment, report)
        self._escalate_on_stall(run_id, experiment)
        return report

    def _close_at_limit(self, run_id, experiment):
        """A v2 session stopped by a run limit (money, an operator's call cap
        or elapsed time), not by the agent: bundle its best improvement, its
        ablations bounded by the run cap and the remaining time like every v2
        delivery, and apply the stall rule's escalation. The limit stop itself
        is re-raised by the caller and recorded as `run_cap_reached`."""
        self._deliver(run_id, experiment, None)
        self._escalate_on_stall(run_id, experiment)

    def _deliver(self, run_id, experiment, report):
        path = self._dir(run_id) / "delivery.json"
        if path.exists():
            return json.loads(path.read_bytes())
        selection = None
        if report is not None and report.get("status") == "SELECTED":
            selection = {"strategy_digest": digest(canonical(report["strategy"]))}
        outcome = deliver_.deliver(
            self._delivery_view(run_id, experiment),
            self._dir(run_id) / "delivery",
            selection=selection,
            proposals=next_level.ProposalStore(self._dir(run_id)).proposals(),
        )
        if experiment.score_variant is not None:
            # The delivery report is labelled with the session's development
            # score variant (VALIDATOR-09); without one it is unchanged.
            outcome = {
                **outcome,
                "label": experiment.score_variant["label"],
                "score_variant": experiment.score_variant,
            }
        write_once(path, canonical(outcome))
        return outcome

    def _escalate_on_stall(self, run_id, experiment):
        """The stall rule's one-rung escalation, consuming the run's recorded
        observation; it applies to the Constructor's next session."""
        observation = experiment.stall_observation()
        path = self._dir(run_id) / "escalation.json"
        if observation is None or path.exists():
            return
        try:
            result = self.ladder.escalate(
                RoleName.CONSTRUCTOR, observation["failure_id"]
            )
        except LadderError as refused:
            result = {"escalated": False, "reason": refused.code}
        write_once(path, canonical(result))

    def session_record(self, run_id, *, final=None, failure=None):
        record = super().session_record(run_id, final=final, failure=failure)
        experiment = self.experiment(run_id)
        extra = {
            "phase3": experiment.summary(),
            "next_level_proposals": [
                p["proposal_id"]
                for p in next_level.ProposalStore(self._dir(run_id)).proposals()
            ],
        }
        for name in ("delivery", "escalation"):
            path = self._dir(run_id) / (name + ".json")
            extra[name] = json.loads(path.read_bytes()) if path.exists() else None
        return {**record, **extra}


def check_observation(observation, scoring=None):
    """A phase-3 brief serves the session's Challenge only (its
    `ChallengeScoring`), with a baseline Carbon can rebuild."""
    try:
        scoring = challenge_scoring.resolve(scoring)
    except challenge_scoring.ScoringUnavailable as refused:
        raise ProviderUnavailable(refused.code) from None
    if not scoring.check_challenge(observation.get("challenge") or {}):
        raise ProviderUnavailable("phase3_challenge_not_served")
    variant = None
    if observation.get("level") != 0:
        # A development level's brief names its registered variant.
        from carbon.reconstruction import development_variants

        named = (observation.get("construction_contract") or {}).get(
            "development_variant"
        )
        try:
            variant = development_variants.registered(named, scoring.challenge_id)
        except development_variants.VariantRefused as refused:
            raise ProviderUnavailable(refused.code) from None
        if variant.level != observation.get("level"):
            raise ProviderUnavailable("development_variant_is_another_level")
    # Level 0 calls admission exactly as before; only a development level
    # names its variant.
    level = {} if variant is None else {"variant": variant}
    try:
        ex.admit(observation.get("baseline_strategy"), 0, scoring=scoring, **level)
    except (ex.Unrebuildable, ex.NotServed):
        raise ProviderUnavailable("baseline_not_rebuildable") from None


# -- literature ------------------------------------------------------------------------------
FIXTURE_SOURCE = "PHASE1_SYNTHETIC_FIXTURE"
FIXTURE_NOTE = (
    "The phase-1 synthetic fixture index was used: three synthetic cards, no "
    "real paper. Only a dry run or a test serves it; a live run needs "
    "--literature-snapshot."
)
#: The most cards a brief lists; the rest stay readable by id (GRAPHITE-D31).
#: A ranked snapshot lists them best first; an unranked one by card id.
MAX_BRIEF_CARDS = 100
#: The Challenge an unranked (phase-2 v1/v2) snapshot is for.
BATTERY_LITERATURE = "battery-fastcharge-ageing-development-v1"


def literature_brief(index):
    """What the Constructor's brief says about its literature: the pinned
    digest, the policy and the offered cards' ids and titles. The Constructor
    holds `lit_card` only, so the brief is how it learns which ids exist."""
    if type(index) is lit.OfferedLiterature:
        rows, policy, empty = index.catalogue(), index.policy, index.empty
    else:
        rows = [
            {
                "card_id": card["card_id"],
                "title": card["title"],
                "check_status": FIXTURE_SOURCE,
            }
            for card in sorted(index.cards, key=lambda card: card["card_id"])
        ]
        policy, empty = FIXTURE_SOURCE, False
    return {
        "snapshot_digest": index.snapshot_digest,
        "offer_policy": policy,
        "cards": rows[:MAX_BRIEF_CARDS],
        "cards_not_listed": max(0, len(rows) - MAX_BRIEF_CARDS),
        "empty": empty,
        "read_with": "lit_card",
        "content_is_data": True,
    }


def open_literature(path, *, allow_unchecked):
    """The session's literature from a phase-2 snapshot file, or a typed
    refusal."""
    from . import method_cards

    try:
        return method_cards.offered_literature(path, allow_unchecked=allow_unchecked)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RunnerRefused("literature_snapshot_refused: " + str(error)) from None


# -- briefs, profile and the controller ------------------------------------------------------
def development_variant_for(level, scoring):
    """The construction level's development-only variant for the session's
    named Challenge (`scoring`): None at Level 0 (the recorded miner-facing
    contract, unchanged); at a level above 0 the variant `DEV_VARIANTS`
    registers for that Challenge and level, or a typed refusal
    (`development_variant_unregistered`, OWNER-GRAPHITE-TEST-WAVE-03 §1).
    Only Carbon's development runners read a variant."""
    if level == 0 and type(level) is int:
        return None
    if type(level) is not int or level < 0:
        raise RunnerRefused("level_is_a_ladder_level")
    from carbon.reconstruction import development_variants

    try:
        challenge = challenge_scoring.resolve(scoring).challenge_id
    except (challenge_scoring.ScoringUnavailable, TypeError):
        raise RunnerRefused("challenge_scoring_must_be_named") from None
    try:
        return development_variants.variant(challenge, level)
    except development_variants.VariantRefused as refused:
        raise RunnerRefused(refused.code) from None


def _variant_of(scoring, variant):
    """A development level's variant, only for the session's own Challenge."""
    if variant is not None and variant.challenge != scoring.challenge_id:
        raise RunnerRefused("development_variant_is_another_challenges")
    return variant


def _variant_contract(variant):
    """What a development-level run constructs under: the variant's record."""
    from carbon.reconstruction import development_variants

    try:
        return development_variants.recorded_variant(variant)
    except development_variants.VariantRefused as refused:
        raise RunnerRefused(refused.code) from None


def session_brief(
    *,
    checkout_commit,
    budget,
    baseline=None,
    literature=None,
    repository=REPOSITORY,
    scoring=None,
    variant=None,
    tool_text=TOOL_TEXT_V2,
    score_variant=None,
):
    """The Constructor's brief: the session Challenge's public development
    material only (its `ChallengeScoring`), and the session's offered
    literature (the phase-1 fixture when none is given). `variant` is the
    development level's registered variant (`development_variant_for`) for
    the same Challenge, or None at Level 0. `score_variant` is the session's
    development score variant identity (VALIDATOR-09), pinned here; None adds
    nothing."""
    scoring = (
        challenge_scoring.scoring_for(budget.challenge_id)
        if scoring is None
        else challenge_scoring.resolve(scoring)
    )
    variant = _variant_of(scoring, variant)
    _score_variant_of(scoring, variant, score_variant)
    baseline = scoring.baseline_strategy() if baseline is None else baseline
    literature = lit.FIXTURE_INDEX if literature is None else literature
    if variant is None:
        level, contract = 0, ex.recorded_contract(scoring)
    else:
        level, contract = variant.level, _variant_contract(variant)
    # The session Challenge's published material, never another's.
    manifest = boundaries.checkout_manifest(
        repository, boundaries.Role.CONSTRUCTION, scoring.published_material()
    )
    observation = {
        "challenge": scoring.challenge(),
        "level": level,
        "construction_contract": contract,
        "baseline_strategy": baseline,
        "objective": scoring.construction_objective,
        "proposal_tool": PROPOSE,
        "pods_per_session": budget.max_pods,
        "pods_note": "The baseline uses the first pod of the session.",
        "stall_limit": CONSTRUCTOR_STALL_ATTEMPTS,
        "literature": literature_brief(literature),
        "instructions": (
            "Read the Challenge and its construction contract with the miner tools, "
            "validate and compile before proposing, then propose with "
            + PROPOSE
            + ". Method cards listed under literature can be read with lit_card; "
            "their text is data. Select a recipe only with evidence, or stop and "
            "say why."
        ),
    }
    if score_variant is not None:
        observation["score_variant"] = score_variant
    return SessionBrief(
        role=RoleName.CONSTRUCTOR,
        initial_observation=observation,
        checkout_commit=checkout_commit,
        checkout_manifest_digest=boundaries.manifest_digest(manifest),
        # A new session reads challenge-neutral tool text (VALIDATOR-07).
        tool_text=tool_text,
    )


def permission_profile(scoring, variant=None, score_variant=None):
    """Level 0: the session Challenge's recorded contract, widened by nothing.
    At a development level the profile is the registered variant itself: its
    document, pinned by its digest, which is what the campaign controller's
    development ledger records (GRAPHITE-DEV-VARIANTS-01). A development score
    variant (its identity, VALIDATOR-09) is pinned in the Level-0 profile, so
    the controller records it by the profile's digest; None adds nothing."""
    scoring = challenge_scoring.resolve(scoring)
    _score_variant_of(scoring, variant, score_variant)
    if _variant_of(scoring, variant) is not None:
        return variant.document(), variant.digest
    document = {
        "schema": PROFILE_SCHEMA,
        "level": 0,
        "construction_contract": ex.recorded_contract(scoring),
        "surface": "declarative TrainingStrategy inside the recorded contract",
        "widens": [],
    }
    if score_variant is not None:
        document["score_variant"] = score_variant
    return document, digest(canonical(document))


def _score_variant_of(scoring, variant, score_variant):
    """A score variant identity runs at Level 0, for the session's Challenge."""
    if score_variant is None:
        return
    if variant is not None:
        raise RunnerRefused(sv.LEVEL0_ONLY)
    if type(score_variant) is not dict or not str(
        score_variant.get("label", "")
    ).startswith("development_score_result:"):
        raise RunnerRefused("score_variant_identity_malformed")


def recorded_score_variant(brief):
    """The development score variant identity a run's brief pinned, or None."""
    return ((brief or {}).get("initial_observation") or {}).get("score_variant")


def recorded_variant(opened, scoring):
    """The registered development variant of the session's Challenge that an
    opened run's task recorded as its profile, or None (Level 0, or
    unknown)."""
    from carbon.reconstruction import development_variants

    challenge = challenge_scoring.resolve(scoring).challenge_id
    task = (opened or {}).get("task") or {}
    try:
        return development_variants.registered(task.get("profile_digest"), challenge)
    except development_variants.VariantRefused:
        return None


def recorded_level(opened, scoring, score_variant=None):
    """The construction level of an opened run, from the permission profile
    its task recorded: the profile's level only when the run's recorded
    profile digest is this profile's (Level 0's, Level 0's under the score
    variant identity its brief pinned, or a registered development variant's
    of the same Challenge), else None (unknown). Never read from a submission
    (`pod_outcome`)."""
    document, profile = permission_profile(scoring)
    task = (opened or {}).get("task") or {}
    if task.get("profile_digest") == profile:
        return document["level"]
    if score_variant is not None:
        scored, profile = permission_profile(scoring, score_variant=score_variant)
        if task.get("profile_digest") == profile:
            return scored["level"]
    found = recorded_variant(opened, scoring)
    return None if found is None else found.level


def controller_for(root, provider, grant, clock=None):
    from ..controller import CampaignController

    kwargs = {} if clock is None else {"clock": clock}
    return CampaignController(
        root=Path(root) / "controller",
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
        role=ROLES[RoleName.CONSTRUCTOR].boundary,
        workspace_id=WORKSPACE,
        credential_ref=CREDENTIAL_REF,
        checkout_digest=checkout_digest,
        profile_digest=profile_digest,
        ceiling=str(grant.monetary_ceiling - grant.cleanup_allowance),
    )


def session_key(number):
    return f"graphite-phase3-session-{number}"


def sync_findings(control, provider, run_id):
    ids = []
    for finding in provider.experiment(run_id).findings():
        control.record_finding(
            finding["id"], finding["condition"], canonical(finding["evidence"])
        )
        ids.append(finding["id"])
    return ids


class ResumeRefused(ValueError):
    """A session would resume under inputs its record does not pin."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_resume(provider, number):
    """Before a resume touches anything: the literature must be the one the
    session record pins (GRAPHITE-D28)."""
    run_id = provider.run_id_for(session_key(number))
    path = provider._dir(run_id) / "session-open.json"
    if not path.is_file():
        return
    opened = json.loads(path.read_bytes())
    if opened["literature"] != provider._literature_record():
        raise ResumeRefused("literature_snapshot_changed_since_the_session_opened")
    # VALIDATOR-09: the score variant identity the session's brief pinned (its
    # rule identity, digest included) must be the provider's.
    brief = provider._brief(opened["brief"]["digest"])
    mine = sv.identity_of(getattr(provider, "score_variant", None))
    if recorded_score_variant(brief) != mine:
        raise ResumeRefused("score_variant_changed_since_the_session_opened")


def ensure_development_expansion(control, variant, operator=OPERATOR):
    """At a development level, the controller's newest development expansion
    is the variant (recorded once, tagged with any open finding); the
    controller refuses any digest `DEV_VARIANTS` does not register."""
    if control.development_profile() == variant.digest:
        return
    control.record_development_expansion(
        challenge=variant.challenge,
        profile=f"level-{variant.level}",
        widened=", ".join(variant.permissions()),
        permissions=variant.digest,
        operator=operator,
    )


def run_session(control, provider, brief, number, variant=None):
    """Launch (or resume) session `number` under the controller and run it.
    `variant` is the development level's registered variant, or None at
    Level 0; it must be the one the brief names."""
    if type(number) is not int or not 1 <= number <= control.grant.permitted_runs:
        raise ValueError("session is 1 .. the grant's permitted runs")
    observation = getattr(brief, "initial_observation", None) or {}
    named = (observation.get("construction_contract") or {}).get("development_variant")
    if named != (None if variant is None else variant.digest):
        raise ValueError("the brief names another construction level")
    scored = sv.identity_of(getattr(provider, "score_variant", None))
    if observation.get("score_variant") != scored:
        raise ValueError("the brief names another score variant")
    check_resume(provider, number)
    _document, profile = permission_profile(provider.scoring, variant, scored)
    ensure_campaign(
        control, checkout_digest=brief.checkout_manifest_digest, profile_digest=profile
    )
    if variant is not None:
        ensure_development_expansion(control, variant)
    spec = TaskSpec(
        campaign_id=CAMPAIGN,
        role=ROLES[RoleName.CONSTRUCTOR].boundary.value,
        workspace_id=WORKSPACE,
        credential_ref=CREDENTIAL_REF,
        profile_digest=profile,
        instructions_digest=provider.register_brief(brief),
        max_runtime_s=control.grant.max_runtime_s,
    )
    key = session_key(number)
    # Each finding is recorded on the controller when the experiment finds it,
    # so a next-level proposal written after it carries it.
    provider.bind_findings(control)
    control.recover()
    phase = control.launch(spec, key)
    run_id = provider.run_id_for(key)
    final = provider.run(run_id) if provider.find(key) is not None else None
    # The session's findings are recorded before its events and artifacts are
    # ingested, so those entries carry them (conditional-evidence.v2
    # "ordering"); `sync_findings` also covers a run another process ran.
    findings = sync_findings(control, provider, run_id) if final else []
    phase = control.poll(key)
    # Tagged with every finding open after this session's are recorded, its
    # own included, and any attested repair (conditional-evidence.v2).
    conditional = control.conditional_tag()
    return {
        "session": number,
        "run_id": run_id,
        "provider_state": final,
        "controller_phase": phase,
        "findings": findings,
        "budget": control.budget(),
        "summary": provider.experiment(run_id).summary() if final else None,
        "delivery": _read(provider._dir(run_id) / "delivery.json"),
        "literature": _literature_of(provider._dir(run_id)),
        "session_limits": session_limits_of(provider._dir(run_id)),
        "next_level_proposals": [
            p["proposal_id"]
            for p in next_level.ProposalStore(provider._dir(run_id)).proposals()
        ],
        **conditional,
    }


def _literature_of(run_dir):
    opened = _read(Path(run_dir) / "session-open.json")
    return None if opened is None else opened["literature"]


def session_limits_of(run_dir):
    """What bounds a session, read from its record: the v2 block as frozen,
    or, for a record without one, the historical rule it runs under."""
    opened = _read(Path(run_dir) / "session-open.json")
    if opened is None:
        return None
    if opened.get("session_limits") is not None:
        return opened["session_limits"]
    return {
        "schema": SESSION_LIMITS_V1,
        "session_turns": Phase3Provider.HISTORICAL_SESSION_TURNS,
        "provider_attempts": opened["caps"]["provider_attempts"],
        "note": "opened under the historical rule; it resumes under its own cap",
    }


def model_call_cap(limits):
    """The model-call cap in force for a session's limits (`session_limits_of`),
    or None when only money and time bind: under v1 the run ledger's
    `provider_attempts`; under v2 an operator's own cap, else the loop's
    per-epoch count."""
    if limits["schema"] == SESSION_LIMITS_V1:
        return limits["provider_attempts"]
    if limits["operator_call_cap"] is not None:
        return limits["operator_call_cap"]
    return limits["loop_limits"]["calls_per_epoch"]


def model_window(provider, run_id):
    """What a session's recorded model selection admits (GRAPHITE-D34): its
    adapter and model, the input window and the admission ceiling the loop
    holds every request under, the output cap, the provider timeout and the
    most one call reserves."""
    selection = selection_from_record(
        provider._opened(run_id)["model"],
        credential_file=provider.model.credential_reference,
    )
    settings, reservation = selection.settings, selection.reservation_nano
    return {
        "provider_id": selection.provider_id,
        "model": selection.model_id,
        "max_input_tokens": settings.max_input_tokens,
        "admission_ceiling_tokens": settings.max_input_tokens - CONTEXT_RESERVE_TOKENS,
        "max_output_tokens": settings.max_output_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "reservation_usd": (
            None if reservation is None else str(Decimal(reservation) / NANO_PER_USD)
        ),
    }


def _read(path):
    return json.loads(path.read_bytes()) if path.exists() else None


# -- the runner ----------------------------------------------------------------------------
class RunnerRefused(SystemExit):
    def __init__(self, code):
        print(json.dumps({"status": "REFUSED", "reason_code": code}))
        super().__init__(2)


def _root(value):
    root = Path(value).expanduser().resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise RunnerRefused("root_must_be_outside_the_repository")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def load_grant(path):
    from ..grant import GrantError

    try:
        return SpendingGrant.from_document(json.loads(Path(path).read_bytes()))
    except (OSError, ValueError) as error:
        code = (
            "grant_refused: " + str(error)
            if type(error) is GrantError
            else ("grant_unreadable")
        )
        raise RunnerRefused(code) from None


@contextlib.contextmanager
def secret_file(*, path=None, env=None, environ=os.environ, names=()):
    """A key file reference: `path` as given (it must exist), or a 0600 copy
    of the environment variable `env` in a fresh 0700 directory, removed on
    exit (GRAPHITE-D16). The value is never printed."""
    if (path is None) == (env is None):
        raise RunnerRefused("one_of_key_file_or_key_env_required")
    if path is not None:
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            raise RunnerRefused("key_file_missing")
        yield str(candidate)
        return
    if env not in names:
        raise RunnerRefused("key_env_not_recognised")
    value = environ.get(env)
    if not value or not value.strip():
        raise RunnerRefused("key_env_empty")
    directory = tempfile.mkdtemp(prefix="graphite-key-")
    try:
        os.chmod(directory, 0o700)
        target = Path(directory) / "key"
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(value.strip())
        yield str(target)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def runpod_key_status(path):
    """The RunPod key file must be owner-only (the compute layer's rule)."""
    from scripts.dev.exam_design.runpod.operator_compute import (
        CredentialStatus,
        FileCredentialProvider,
    )

    return FileCredentialProvider(Path(path)).status() is CredentialStatus.CONFIGURED


def check_code_ref(ref, repository=REPOSITORY):
    """The pod fetches code at `ref`, and Carbon pins staged files from this
    checkout: the ref must be this checkout's HEAD, pushed, and clean."""
    from scripts.dev.exam_design.runpod import pod_control

    if type(ref) is not str or len(ref) != 40:
        raise RunnerRefused("code_ref_must_be_a_40_hex_commit")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    if git("rev-parse", "HEAD").stdout.strip() != ref:
        raise RunnerRefused("code_ref_is_not_this_checkout_head")
    if git("status", "--porcelain", "--", "carbon", "scripts/dev/exam_design").stdout:
        raise RunnerRefused("shipped_code_has_uncommitted_changes")
    if not pod_control.ref_is_pushed(ref):
        raise RunnerRefused("code_ref_not_pushed")


def _install_cancel(provider, run_id):
    """SIGINT/SIGTERM ask the worker to stop: it terminates its pod first."""

    def handler(_signum, _frame):
        provider.request_cancel(run_id)

    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), handler)


def _literature_from(args, *, check_challenge=True):
    """The session's literature, or None for the dry run's fixture. A live run
    checks its Challenge later (`check_challenge=False`), after the spend and
    code checks: authority first, then input content."""
    if args.literature_snapshot is None:
        if args.allow_unchecked_cards:
            raise RunnerRefused("allow_unchecked_cards_needs_a_literature_snapshot")
        return None
    offered = open_literature(
        args.literature_snapshot, allow_unchecked=args.allow_unchecked_cards
    )
    if check_challenge:
        check_literature_challenge(offered, args.challenge, RunnerRefused)
    return offered


def check_literature_challenge(offered, challenge_id, refusal):
    """A session reads its own Challenge's literature only: a ranked snapshot
    names its Challenge; an unranked (v1/v2) one is battery's phase 2."""
    if type(offered) is not lit.OfferedLiterature:
        return
    for_challenge = offered.challenge_id or BATTERY_LITERATURE
    if for_challenge != challenge_id:
        raise refusal("literature_snapshot_is_for_another_challenge")


#: The compute lanes a live phase-3 run may use (`--compute`).
COMPUTE_LANES = ("runpod", "carrier")
#: Grants that pay for tokens only: their runs use the CPU carrier lane, and
#: a RunPod launch under one is refused. The cooling CPU grant's id is the
#: Test Lead's (2026-10-05); its file is
#: docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3-COOLING-CPU.json, and
#: a tokens-only run's pod money budget is 0 (`experiment.Phase3Budget`).
TOKENS_ONLY_GRANTS = frozenset({"GRAPHITE-GRANT-PHASE3-COOLING-CPU"})


def compute_lane(args, grant):
    """The run's compute lane, checked before anything is read or spent."""
    compute = getattr(args, "compute", "runpod")
    if compute not in COMPUTE_LANES:
        raise RunnerRefused("compute_lane_unknown")
    if compute == "runpod":
        if grant.grant_id in TOKENS_ONLY_GRANTS:
            raise RunnerRefused("grant_is_tokens_only_use_the_carrier_lane")
        return compute
    if getattr(args, "level", 0) not in (0, 1, 2, 3):
        # Levels 4-5 run participant code: never in the operator's carrier.
        raise RunnerRefused("carrier_lane_refuses_levels_4_5")
    if not getattr(args, "image_manifest", None):
        raise RunnerRefused("required: --image-manifest")
    return compute


def carrier_pods(root, manifest):
    """The CPU carrier backend on this (operator) host: the pinned C-03 worker
    image, refused unless the host doctor finds this host eligible."""
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    from .carrier_pods import CarrierPods

    try:
        image = load_image_identity(manifest)
    except (OSError, ValueError, TypeError):
        raise RunnerRefused("carrier_image_manifest_unreadable") from None
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise RunnerRefused("carrier_host_not_eligible")
    return CarrierPods(root, image=image)


def finalized_block_clock(context):
    """`() -> int | None`: the chain's finalized block, read-only; None when
    the chain cannot be read (the hidden result is then `UNAVAILABLE`)."""
    import asyncio

    from carbon.chain.models import ChainFailure
    from carbon.chain.sdk import BittensorReader

    def clock():
        try:
            return asyncio.run(BittensorReader().capture(context)).finalized_block
        except (ChainFailure, OSError):
            return None

    return clock


def hidden_pool_factory(
    config_path, scoring, variant, *, clock=None, repository=REPOSITORY
):
    """`run_id -> HiddenPool` over the battery deployment at `config_path`
    (VALIDATOR-13). Checked before anything is spent: the deployment loads
    writable, its rule seals hidden results, and a development level (the
    run's registered variant) needs a deployment that opted in with
    `development_only` (owner, 2026-10-06)."""
    from pathlib import Path

    from carbon.battery import deployment

    from .hidden_score import HiddenPool, HiddenPoolRefused

    if clock is None:
        from carbon.chain.models import ChainContext
        from carbon.development_testnet.operator import (
            DEFAULT_ENDPOINT,
            TESTNET_GENESIS,
        )

        clock = finalized_block_clock(
            ChainContext(
                "testnet",
                DEFAULT_ENDPOINT,
                "bittensor-official-test",
                TESTNET_GENESIS,
                567,
            )
        )
    try:
        target = deployment.validator(Path(config_path), repository=repository)
    except deployment.EvaluationUnavailable as refused:
        raise RunnerRefused("hidden_" + refused.code) from None
    try:
        probe = HiddenPool(target, run_id="probe", clock=clock, variant=variant)
    except HiddenPoolRefused as refused:
        raise RunnerRefused(refused.code) from None
    if probe.challenge_id != scoring.challenge_id:
        raise RunnerRefused("hidden_pool_is_another_challenges")
    return lambda run_id: HiddenPool(
        target, run_id=run_id, clock=clock, variant=variant
    )


def hidden_remote_factory(url, key_path, scoring, variant, *, ca=None, post=None):
    """`run_id -> RemoteHiddenPool`: the hidden pool on its own host, reached
    through the signed door (VALIDATOR-19 slice 0). Graphite holds only the
    submitter key and receives only sealed views."""
    from pathlib import Path

    from carbon.battery.dev_submit import (
        DevSubmitRefused,
        RemoteHiddenPool,
        SubmitterKey,
    )

    try:
        key = SubmitterKey.load(Path(key_path))
    except (DevSubmitRefused, OSError):
        raise RunnerRefused("hidden_submitter_key_unreadable") from None
    base = scoring.contract().digest

    def factory(run_id):
        return RemoteHiddenPool(
            url,
            key,
            run_id=run_id,
            challenge_id=scoring.challenge_id,
            contract_digest=base,
            variant=variant,
            ca=ca,
            post=post,
        )

    try:
        factory("probe")
    except DevSubmitRefused as refused:
        raise RunnerRefused(refused.code) from None
    return factory


def command_run(args):
    try:
        scoring = challenge_scoring.scoring_for(args.challenge)
    except challenge_scoring.ScoringUnavailable as refused:
        raise RunnerRefused(refused.code) from None
    # A development level resolves the named Challenge's registered variant
    # before anything is read or spent; an unregistered one is refused here.
    variant = development_variant_for(getattr(args, "level", 0), scoring)
    level = {} if variant is None else {"development_variant": variant}
    # VALIDATOR-09: a development score variant is resolved here too, before
    # any grant, pod or model call; refused, typed, otherwise.
    scored = score_variant_for(getattr(args, "score_variant", None), scoring, variant)
    if scored is not None:
        level["score_variant"] = scored
    if args.dry_run:
        return dry_run(
            _root(args.root),
            scoring,
            literature=_literature_from(args),
            analysis_image_manifest=getattr(args, "analysis_image_manifest", None),
            **level,
        )
    root = _root(args.root)
    grant = load_grant(args.grant)
    if grant.provider != "graphite":
        raise RunnerRefused("grant_provider_must_be_graphite")
    # The grant bound to the named Challenge, and to main's committed blob
    # where its registration says so, and to the construction level where it
    # registers a lowest one (`grant_binding`).
    from .grant_binding import check_phase3_grant

    check_phase3_grant(
        args.grant, grant, challenge=args.challenge, level=getattr(args, "level", 0)
    )
    if args.miner_profile is None or args.miner_campaign is None:
        raise RunnerRefused("the_real_miner_path_needs_a_miner_profile_and_campaign")
    if args.literature_snapshot is None:
        # GRAPHITE-D28: a paid session never runs on the synthetic fixture.
        raise RunnerRefused("live_run_needs_a_literature_snapshot")
    # Refusal precedence: the grant and compute lane (spend authority), then
    # the code ref (code integrity), then the literature's Challenge (input
    # content). Every one refuses before a model call or a pod.
    literature = _literature_from(args, check_challenge=False)
    compute = compute_lane(args, grant)
    from . import miner_path
    from .model import LiveModel, ModelAccessRefused
    from .phase2 import credential_file
    from .pods import RunPodPods

    with contextlib.ExitStack() as stack:
        if args.credential_file is not None:
            # The same owner-only rule as phase 4's --credential-file.
            from .phase4 import owner_only_file

            owner_only_file(args.credential_file)
        engy = stack.enter_context(
            credential_file(path=args.credential_file, env=args.credential_env)
        )
        if compute == "runpod":
            runpod = stack.enter_context(
                secret_file(
                    path=args.runpod_key_file,
                    env=args.runpod_key_env,
                    names=("RUNPOD_API_KEY",),
                )
            )
            if not runpod_key_status(runpod):
                raise RunnerRefused("runpod_key_file_must_be_owner_only")
        check_code_ref(args.code_ref)
        check_literature_challenge(literature, args.challenge, RunnerRefused)
        if getattr(args, "hidden_deployment", None) and getattr(
            args, "hidden_endpoint", None
        ):
            raise RunnerRefused("hidden_pool_named_twice")
        if getattr(args, "hidden_endpoint", None):
            hidden = hidden_remote_factory(
                args.hidden_endpoint,
                args.hidden_submitter_key,
                scoring,
                variant,
                ca=getattr(args, "hidden_ca", None),
            )
        elif getattr(args, "hidden_deployment", None):
            hidden = hidden_pool_factory(args.hidden_deployment, scoring, variant)
        else:
            hidden = None
        try:
            model = LiveModel(grant=grant, credential_file=engy, provider="graphite")
        except ModelAccessRefused as refused:
            raise RunnerRefused(refused.code) from None
        if compute == "runpod":
            pods = RunPodPods(
                root=root / "pods",
                key_file=runpod,
                code_ref=args.code_ref,
                scoring=scoring,
            )
        else:
            pods = carrier_pods(root / "carrier", args.image_manifest)

        def attach(*, session):
            return miner_path.attach(
                args.miner_profile,
                args.miner_campaign,
                session=session,
                scoring=scoring,
            )

        provider = Phase3Provider(
            root=root / "graphite",
            grant=grant,
            model=model,
            pods=pods,
            miner_attach=attach,
            literature_index=literature,
            scoring=scoring,
            score_variant=scored,
            hidden=hidden,
        )
        try:
            check_resume(provider, args.session)
        except ResumeRefused as refused:
            raise RunnerRefused(refused.code) from None
        control = controller_for(root, provider, grant)
        try:
            budget = provider.budget
            brief = session_brief(
                checkout_commit=args.code_ref,
                budget=budget,
                literature=literature,
                scoring=scoring,
                variant=variant,
                score_variant=sv.identity_of(scored),
            )
            _install_cancel(provider, provider.run_id_for(session_key(args.session)))
            result = run_session(control, provider, brief, args.session, variant)
        finally:
            control.close()
    run_dir = provider._dir(result["run_id"])
    result["pod_charges"] = ex.pod_charge_report(
        ex.PodLedger(run_dir / "experiment" / "pod-ledger.jsonl", time.time)
    )
    result["next_step"] = _next_step(_read(run_dir / "state.json"))
    print(json.dumps(result, indent=1, default=str))
    return 0 if result["provider_state"] == "succeeded" else 4


def _next_step(state):
    """The typed next step for a run's recorded state (`cli_usage.next_step`):
    a terminal `reconciliation_required` session names `reconcile`, never a
    rerun."""
    if not isinstance(state, dict):
        return None
    return next_step(state.get("state"), state.get("failure"))


def command_cancel(args):
    root = _root(args.root)
    run_id = GraphiteProvider.run_id_for(session_key(args.session))
    state_path = root / "graphite" / "runs" / run_id / "state.json"
    if not state_path.exists():
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


def command_reconcile(args):
    root = _root(args.root)
    grant = load_grant(args.grant)
    from .model import ScriptedModel
    from .pods import RunPodPods

    try:
        scoring = challenge_scoring.scoring_for(args.challenge)
    except challenge_scoring.ScoringUnavailable as refused:
        raise RunnerRefused(refused.code) from None

    with secret_file(
        path=args.runpod_key_file, env=args.runpod_key_env, names=("RUNPOD_API_KEY",)
    ) as runpod:
        pods = RunPodPods(
            root=root / "pods",
            key_file=runpod,
            code_ref=args.code_ref,
            scoring=scoring,
        )
        # Reconciliation makes no model call: a scripted model with no script.
        provider = Phase3Provider(
            root=root / "graphite",
            grant=grant,
            model=ScriptedModel([]),
            pods=pods,
            scoring=scoring,
        )
        report = {}
        for run in sorted((root / "graphite" / "runs").glob("graphite-*")):
            if (run / "session-open.json").is_file():
                report[run.name] = provider.experiment(run.name).reconcile()
    print(json.dumps(report, indent=1))
    live = any(
        r.get("terminated") is not True for rows in report.values() for r in rows
    )
    if live:
        # Exit 4 stays; stdout stays the report. What to do next goes to
        # stderr as one typed line (OPERATOR-USABILITY-01 D3).
        print(json.dumps(reconcile_pending(report)), file=sys.stderr)
    return 4 if live else 0


def _minute_utc(unix):
    """`unix` rounded up to the whole minute, as (ISO time, "HH:MM UTC")."""
    import datetime
    import math

    moment = datetime.datetime.fromtimestamp(math.ceil(unix / 60) * 60, datetime.UTC)
    return moment.strftime("%Y-%m-%dT%H:%MZ"), moment.strftime("%H:%M UTC")


def reconcile_pending(report):
    """Why a reconcile exited 4, and when to run it again.

    An uncertain pod create that the provider cannot yet confirm or deny
    settles only once the compute layer's grace has passed since the intent
    was made (`ComputeService.recover`, `not_found_grace_s`): each such pod
    gets its intent's age and the first whole UTC minute at or after which a
    re-run can settle it. A termination that was not verified can be re-run
    at once."""
    unsettled, rerun = [], None
    for rows in report.values():
        for row in rows:
            if row.get("terminated") is True:
                continue
            entry = {"intent_id": row.get("intent_id")}
            if row.get("terminated") is None and "settles_at_unix" in row:
                at, hhmm = _minute_utc(row["settles_at_unix"])
                entry.update(
                    intent_age_s=round(row["intent_age_s"]),
                    not_found_grace_s=row["not_found_grace_s"],
                    rerun_at_utc=at,
                    next_step=(
                        f"settles after {row['not_found_grace_s']:g} s; "
                        f"re-run at or after {hhmm}"
                    ),
                )
                rerun = max(rerun or at, at)
            elif row.get("terminated") is None:
                entry["next_step"] = (
                    "the provider cannot say yet whether the pod exists; re-run reconcile"
                )
            else:
                entry["next_step"] = "termination not verified; re-run reconcile now"
            unsettled.append(entry)
    return {
        "status": "REFUSED",
        "reason_code": "reconcile_pods_not_settled",
        "unsettled": unsettled,
        "rerun_at_utc": rerun,
    }


def command_status(args):
    root = Path(args.root).expanduser().resolve()
    out = {}
    for run in sorted((root / "graphite" / "runs").glob("graphite-*")):
        state = _read(run / "state.json")
        ledger = ex.PodLedger(run / "experiment" / "pod-ledger.jsonl", time.time)
        settled, pending = ledger.committed()
        out[run.name] = {
            "state": state,
            "pods_settled_usd": str(settled),
            "pods_pending_usd": str(pending),
            "pods_live": [p["intent_id"] for p in ledger.live()],
            "pod_charges": ex.pod_charge_report(ledger),
            "next_step": _next_step(state),
            "delivery": _read(run / "delivery.json"),
            "escalation": _read(run / "escalation.json"),
            "literature": _literature_of(run),
            "session_limits": session_limits_of(run),
            "next_level_proposals": [
                p["proposal_id"] for p in next_level.ProposalStore(run).proposals()
            ],
        }
    print(json.dumps(out, indent=1))
    return 0


def command_proposals(args):
    """List the next-level proposals under a root. They widen nothing."""
    root = Path(args.root).expanduser().resolve()
    if args.dry_run:
        root = root / "dry-run"
    rows = next_level.listing(root)
    print(
        json.dumps(
            {
                "proposals": rows,
                "count": len(rows),
                "note": (
                    "PROPOSED records for the owner. None widens the construction "
                    "contract, changes a permission or affects a score; widening "
                    "a level is an owner decision under the reconstruction rule."
                ),
            },
            indent=1,
        )
    )
    return 0


def command_rebuild(args):
    result = deliver_.clean_rebuild(Path(args.bundle))
    print(json.dumps(result, indent=1))
    return 0 if result["status"] == "REBUILT" else 4


# -- admission conditions into the root's controller (GRAPHITE-ADMISSION-CONTROLLER-01) -----
CONDITIONS_SCHEMA = "carbon.admission-conditions.v1"
CONDITIONS_MESSAGES = {
    "controller_already_active": (
        "Another process holds this root's controller lock (a running session, "
        "reconcile or conditions command). Nothing was recorded; retry when it "
        "has finished."
    ),
    "grant_provider_mismatch": (
        "The grant's provider is not the phase-3 provider's; nothing was opened."
    ),
    "grant_changed_under_existing_store": (
        "The grant is not the one this root's controller is bound to; nothing "
        "was recorded."
    ),
    "controller_store_id_invalid": (
        "The controller's store-id file is damaged; nothing was recorded."
    ),
    "controller_store_missing": (
        "This root has no campaign controller store (ROOT/controller/"
        "campaign.sqlite3). Nothing was created; check the root."
    ),
    "controller_store_exists": (
        "ROOT/controller already exists; an admission controller is created "
        "once. Nothing was changed; use conditions --identity to read it."
    ),
    "admission_grant_must_be_zero_spend": (
        "An admission controller is bound only to a zero-spend grant (every "
        "amount 0, 0 runs, 0 submissions); nothing was created."
    ),
    "admission_grant_not_registered_for_challenge": (
        "No admission-controller grant is registered for this Challenge "
        "(grant_binding.ADMISSION_CONTROLLER_GRANTS); nothing was created."
    ),
    "admission_grant_file_unreadable": (
        "The Challenge's committed admission-controller grant could not be "
        "read; nothing was created."
    ),
    "admission_grant_differs_from_the_committed_grant": (
        "The grant is not the Challenge's committed admission-controller grant, "
        "field for field; nothing was created."
    ),
    "conditions_report_unreadable": "The report could not be read.",
    "conditions_report_malformed": (
        "The report is not a well-formed carbon.admission-conditions.v1 "
        "document; nothing was recorded."
    ),
    "conditions_report_schema_unsupported": (
        "The report's schema is not carbon.admission-conditions.v1; nothing was "
        "recorded."
    ),
    "conditions_report_challenge_mismatch": (
        "The report names a Challenge other than --challenge; nothing was recorded."
    ),
    "admission_controller_not_designated": (
        "No controller is designated for this (Challenge, level) in "
        "carbon/challenge_pipeline/admission_controllers.json. Nothing was "
        "recorded; pass --record-also to record here anyway (not the LOCK "
        "authority)."
    ),
    "admission_controller_mismatch": (
        "This root's controller is not the one designated for this (Challenge, "
        "level). Nothing was recorded; pass --record-also to record here anyway "
        "(not the LOCK authority)."
    ),
}


class ConditionsRefused(RunnerRefused):
    """A typed refusal with a plain message; nothing was recorded."""

    def __init__(self, code, detail=None):
        message = CONDITIONS_MESSAGES.get(code, code)
        out = {"status": "REFUSED", "reason_code": code, "message": message}
        if detail:
            out["detail"] = detail
        print(json.dumps(out))
        SystemExit.__init__(self, 2)
        self.reason_code = code


class NoPods:
    """The pod backend of a command that never runs a pod: every call is
    refused before anything is created. It holds no key and reads none."""

    name = "no-pods"

    def describe(self):
        return {"backend": self.name, "synthetic": True, "pods": "refused"}

    def _refuse(self, *_args, **_kwargs):
        from .pods import PodFailure

        raise PodFailure("launch", "no pod runs under this command", executed=False)

    launch = wait = fetch = terminate = charge = recover = _refuse


def conditions_report(path, challenge):
    """The report's bytes, document and level, checked before anything is
    opened: schema `carbon.admission-conditions.v1`, a list of conditions
    each naming one admission condition, an optional `challenge` that must be
    `challenge` and an optional `level` (default 0)."""
    from carbon.challenge_readiness import admission

    try:
        body = Path(path).read_bytes()
    except OSError as error:
        raise ConditionsRefused(
            "conditions_report_unreadable", type(error).__name__
        ) from None
    try:
        report = json.loads(body)
    except ValueError:
        raise ConditionsRefused("conditions_report_malformed", "not JSON") from None
    if type(report) is not dict:
        raise ConditionsRefused("conditions_report_malformed", "not an object")
    if report.get("schema") != CONDITIONS_SCHEMA:
        raise ConditionsRefused("conditions_report_schema_unsupported")
    entries = report.get("conditions")
    if type(entries) is not list or any(
        type(entry) is not dict or entry.get("condition") not in admission.CONDITIONS
        for entry in entries
    ):
        raise ConditionsRefused(
            "conditions_report_malformed", "conditions name admission conditions"
        )
    if "challenge" in report and report["challenge"] != challenge:
        raise ConditionsRefused("conditions_report_challenge_mismatch")
    level = report.get("level", 0)
    if type(level) is not int or level < 0:
        raise ConditionsRefused("conditions_report_malformed", "level")
    return body, report, level


def conditions_controller(root, grant, scoring):
    """The root's own controller (`controller_for`), opened offline: a
    scripted model with no script and `NoPods`, so no model call, pod or key
    is reachable. The provider's capabilities must match the grant's
    provider; another process's lock is refused."""
    from ..controller import ControllerError
    from .model import ScriptedModel

    if not (root / "controller" / "campaign.sqlite3").is_file():
        raise ConditionsRefused("controller_store_missing")
    if grant.zero_spend:
        # A dedicated admission controller (`admission-controller init`).
        return admission_controller(root, grant, scoring.challenge_id)
    try:
        provider = Phase3Provider(
            root=root / "graphite",
            grant=grant,
            model=ScriptedModel([]),
            pods=NoPods(),
            scoring=scoring,
        )
        return controller_for(root, provider, grant)
    except ProviderUnavailable as refused:
        raise ConditionsRefused(str(refused)) from None
    except ControllerError as refused:
        raise ConditionsRefused(refused.code) from None


# -- dedicated admission controllers (A4-DEDICATED-ADMISSION-CONTROLLERS-01) ---------------
class NoDispatch:
    """The provider of a dedicated admission controller: never dispatchable,
    and every run call refused. It holds no model, pod or key."""

    def capabilities(self):
        return Capabilities(
            provider=PROVIDER,
            mode=IntegrationMode.UNAVAILABLE,
            verified=False,
            supports_idempotent_start=False,
            supports_cancel=False,
            reports_worker_termination=False,
            reports_usage=False,
            basis="dedicated admission controller: zero-spend grant, no dispatch",
        )

    def _refuse(self, *_args, **_kwargs):
        raise ProviderUnavailable("admission_controller_never_dispatches")

    start = find = status = usage = events = artifacts = cancel = _refuse


def admission_controller(root, grant, challenge):
    """`challenge`'s dedicated admission controller at `root`, opened with
    `NoDispatch` under its committed zero-spend grant
    (`grant_binding.admission_grant_refusal`)."""
    from ..controller import ControllerError

    refused = grant_binding.admission_grant_refusal(grant, challenge)
    if refused is not None:
        raise ConditionsRefused(refused)
    try:
        return controller_for(root, NoDispatch(), grant)
    except ControllerError as refused:
        raise ConditionsRefused(refused.code) from None


def admission_store_exists(root):
    """Whether ROOT/controller exists in any form (an admission controller is
    created once; a link counts)."""
    store = root / "controller"
    return store.exists() or store.is_symlink()


def command_admission_controller(args):
    """Create `challenge`'s dedicated admission controller, offline:

        admission-controller init --root ROOT --challenge TOKEN --grant GRANT

    The grant must be the Challenge's committed zero-spend admission grant.
    The store is created empty under ROOT/controller (an existing one is
    refused), nothing is spent or dispatched, and the controller's identity
    is printed for the designation (`admission_controllers.json`).
    `conditions --identity` on the same root prints the same identity."""
    from carbon.challenge_pipeline import admission_controllers as designations

    root = Path(args.root).expanduser().resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise ConditionsRefused("root_must_be_outside_the_repository")
    grant = load_grant(args.grant)
    try:
        challenge_scoring.scoring_for(args.challenge)
    except challenge_scoring.ScoringUnavailable as refused:
        raise ConditionsRefused(refused.code) from None
    refused = grant_binding.admission_grant_refusal(grant, args.challenge)
    if refused is not None:
        raise ConditionsRefused(refused)
    if admission_store_exists(root):
        raise ConditionsRefused("controller_store_exists")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    control = admission_controller(root, grant, args.challenge)
    try:
        identity = control.identity()
    finally:
        control.close()
    try:
        entry = designations.designation(args.challenge, 0)
    except designations.DesignationRefused as refused:
        raise ConditionsRefused(refused.code, str(refused)) from None
    print(
        json.dumps(
            {
                "status": "CREATED",
                "challenge": args.challenge,
                "level": 0,
                "controller": identity,
                "designation": entry,
            },
            indent=1,
        )
    )
    return 0


def _designation(challenge, level, identity, record_also):
    """Whether this controller may take the report for (challenge, level),
    and what to say. Pending: allowed with a warning (the designated root is
    the one whose identity is pending, and a finding only ever closes LOCK).
    Not designated or another controller: refused unless `record_also`."""
    from carbon.challenge_pipeline import admission_controllers as designations

    try:
        entry = designations.designation(challenge, level)
    except designations.DesignationRefused as refused:
        raise ConditionsRefused(refused.code, str(refused)) from None
    view = {"challenge": challenge, "level": level, "entry": entry}
    if entry is not None and designations.pending(entry):
        view["status"] = designations.IDENTITY_PENDING
        view["lock_authority"] = None
        warning = (
            f"The designation for {challenge} level {level} is pending its "
            f"operator-reported identity ({entry['name']}). Recorded here as the "
            "intended authority; report this controller's identity in the "
            "follow-up that fills the designation. No LOCK passes until it does."
        )
        return view, [warning]
    if entry is not None and entry["identity"] == identity:
        view["status"], view["lock_authority"] = designations.DESIGNATED, True
        return view, []
    code = designations.NOT_DESIGNATED if entry is None else designations.MISMATCH
    if not record_also:
        raise ConditionsRefused(code, f"{challenge} level {level}")
    view["status"], view["lock_authority"] = code, False
    warning = (
        f"--record-also: this root is not the LOCK authority for {challenge} "
        f"level {level} ({code}). The findings are recorded here, and must also "
        "be recorded on the designated controller to block its LOCK."
    )
    return view, [warning]


def command_conditions(args):
    """Record an admission-conditions report's conditions as findings on the
    root's controller (`consume_conditions`), or print its identity only.

        conditions --root ROOT --grant GRANT --challenge TOKEN --report PATH
            [--record-also]
        conditions --root ROOT --grant GRANT --challenge TOKEN --identity

    Idempotent: the same report bytes give the same finding ids, and a repeat
    records nothing new (a finding repaired since is reopened, as the
    controller reopens any repaired finding recorded again)."""
    import hashlib

    from ..controller import ControllerError

    root = Path(args.root).expanduser().resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise ConditionsRefused("root_must_be_outside_the_repository")
    grant = load_grant(args.grant)
    try:
        scoring = challenge_scoring.scoring_for(args.challenge)
    except challenge_scoring.ScoringUnavailable as refused:
        raise ConditionsRefused(refused.code) from None
    report = None
    if not args.identity:
        if args.report is None:
            raise ConditionsRefused("required: --report or --identity")
        body, report, level = conditions_report(args.report, args.challenge)
    control = conditions_controller(root, grant, scoring)
    try:
        identity = control.identity()
        if args.identity:
            view, _ = _designation(args.challenge, 0, identity["identity"], True)
            print(json.dumps({"controller": identity, "designation": view}, indent=1))
            return 0
        view, warnings = _designation(
            args.challenge, level, identity["identity"], args.record_also
        )
        recorded = {
            e["observed_result"]["id"]
            for e in control.ledger()
            if e["kind"] == "finding"
        }
        open_before = {f["id"] for f in control.open_findings()}
        # The bytes checked above are the bytes consumed: a private copy.
        with tempfile.TemporaryDirectory(prefix="graphite-conditions-") as private:
            copy = Path(private) / "report.json"
            copy.write_bytes(body)
            try:
                ids = control.consume_conditions(copy)
            except ControllerError as refused:
                raise ConditionsRefused(refused.code) from None
    finally:
        control.close()
    for warning in warnings:
        print("WARNING: " + warning, file=sys.stderr)
    print(
        json.dumps(
            {
                "status": "CONSUMED",
                "challenge": args.challenge,
                "level": level,
                "report_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                "conditions": len(report["conditions"]),
                "finding_ids": ids,
                "findings": [
                    {
                        "id": fid,
                        "result": (
                            "RECORDED"
                            if fid not in recorded
                            else (
                                "ALREADY_RECORDED"
                                if fid in open_before
                                else "REOPENED_AFTER_REPAIR"
                            )
                        ),
                    }
                    for fid in ids
                ],
                "controller": identity,
                "designation": view,
                "warnings": warnings,
            },
            indent=1,
        )
    )
    return 0


# -- the dry run ---------------------------------------------------------------------------
DRY_RUN_GRANT = {
    "schema": "carbon.agent-campaign.spending-grant.v1",
    "grant_id": "graphite-phase3-dry-run-synthetic",
    "provider": "graphite",
    "account": "dry-run-no-account",
    "granted_by": "nobody-dry-run",
    "expires_at": "2099-01-01T00:00:00Z",
    "currency": "USD",
    "monetary_ceiling": "15.00",
    "cleanup_allowance": "0.25",
    "worst_case_run_cost": "4.91",
    "permitted_runs": 3,
    "max_concurrency": 1,
    "max_runtime_s": 39600,
    "max_submissions": 3,
}


class DryRunMiner:
    """Answers every miner tool with a fixed DRY RUN record; runs nothing."""

    async def call(self, name, arguments, identity):
        return {"status": "OK", "dry_run": True, "operation": name, "ran": False}


def dry_run_script(baseline, variant, refused):
    from .model import text, tool, tools

    prefix = "carbon_research_v2__"
    return [
        # Live session 1's first turn: three tool calls at once. All three
        # run, in order, each journalled (LP-PROD-A).
        tools(
            tool(prefix + "get_challenge_info", {}),
            tool(prefix + "get_interaction_manifest", {}),
            tool(prefix + "get_mock_scaffold", {}),
        ),
        tool(
            PROPOSE,
            {
                "strategy_json": json.dumps(refused),
                "hypothesis": "an operator family outside the contract",
                "expected_effect": "Carbon refuses it, typed",
            },
        ),
        tool(
            PROPOSE,
            {
                "strategy_json": json.dumps(variant),
                "hypothesis": "a second registered construction choice",
                "expected_effect": "a lower frozen-rule score than the baseline",
            },
        ),
        text("DRY RUN: the scripted Constructor stops here."),
    ]


def score_variant_for(version, scoring, variant=None):
    """The development score variant `--score-variant` names for the session's
    Challenge (`score_variant.resolve`), or None without the flag. Refused,
    typed, before anything is read or spent (VALIDATOR-09)."""
    try:
        return sv.resolve(
            version, scoring, level=0 if variant is None else variant.level
        )
    except sv.ScoreVariantRefused as refused:
        raise RunnerRefused(refused.code) from None


def dry_run(
    root,
    scoring,
    literature=None,
    development_variant=None,
    analysis_image_manifest=None,
    score_variant=None,
):
    """`development_variant`: a development level's registered variant for the
    same Challenge (`development_variant_for`), or None at Level 0.
    `analysis_image_manifest`: the campaign's pinned analysis image, for the
    REAL miner lane's containment check; without it that check fails closed
    and the dry run exits nonzero.
    `score_variant`: a resolved development score variant (`score_variant_for`),
    or None."""
    from carbon.development_session.containment_check import containment_check

    from .model import ScriptedModel
    from .pods import ScriptedPods, Step, real_path_check, synthetic_outputs

    root = root / "dry-run"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(mode=0o700)
    scoring = challenge_scoring.resolve(scoring)
    baseline = scoring.baseline_strategy()
    variant = scoring.fixture_variant_strategy()
    refused = scoring.fixture_refused_strategy()
    grant = SpendingGrant.from_document(DRY_RUN_GRANT)
    pods = ScriptedPods(
        steps=[
            Step(outputs=synthetic_outputs(1.0, scoring=scoring), charge="0.20"),
            Step(outputs=synthetic_outputs(0.4, scoring=scoring), charge="0.20"),
            Step(outputs=synthetic_outputs(1.0, scoring=scoring), charge="0.20"),
        ]
    )
    provider = Phase3Provider(
        root=root / "graphite",
        grant=grant,
        model=ScriptedModel(dry_run_script(baseline, variant, refused)),
        pods=pods,
        miner_tools=DryRunMiner(),
        randomness=lambda n: b"\x00" * n,
        scoring=scoring,
        **({} if literature is None else {"literature_index": literature}),
        **({} if score_variant is None else {"score_variant": score_variant}),
    )
    control = controller_for(root, provider, grant)
    try:
        brief = session_brief(
            checkout_commit="0" * 40,
            budget=provider.budget,
            literature=literature,
            scoring=scoring,
            variant=development_variant,
            **(
                {}
                if score_variant is None
                else {"score_variant": sv.identity_of(score_variant)}
            ),
        )
        result = run_session(control, provider, brief, 1, development_variant)
    finally:
        control.close()
    limits = result["session_limits"]
    result["dry_run"] = {
        "synthetic": True,
        "note": "scripted model, scripted pods and SYNTHETIC predictions; "
        "admission, scoring, comparison, bundle and clean rebuild are Carbon's own",
        "pods_launched": len(pods.launched),
        "pods_alive": sorted(pods.alive),
        **parallel_call_counts(
            provider._dir(result["run_id"]) / "ledger" / f"epoch-{EPOCH}"
        ),
        # The session's bounds (OWNER-GRAPHITE-MINER-01 §6): no call cap; the
        # run's money cap and its elapsed limit.
        "session_limits_rule": limits["schema"],
        "model_call_cap": model_call_cap(limits),
        "money_cap_usd": str(Decimal(limits["money_cap_nanodollars"]) / NANO_PER_USD),
        "elapsed_limit_s": limits["elapsed_seconds"],
        # The Constructor's selection, as the session record froze it
        # (GRAPHITE-D34): window, admission ceiling, timeout and reservation.
        "constructor_model": model_window(provider, result["run_id"]),
        # The scripted pods above never reach the operator layer; this drives
        # the live backend's own path, threads included, with RunPod in memory
        # (POD-STORE-THREADS-01).
        "real_pod_path": real_path_check(root / "real-pod-path", scoring=scoring),
        # A pod that exits non-zero keeps its logs, bounded; a baseline that
        # fails as infrastructure is retried once and scores (R2 run 4).
        "pod_failure_path": ex.failure_path_check(
            root / "pod-failure-path",
            baseline=baseline,
            budget=provider.budget,
            scoring=scoring,
            scorer=provider._frozen_rule(),
        ),
        # The miner door above is a fake; this runs one fixed cell through the
        # REAL miner lane and checks its containment from the host
        # (GRAPHITE-CARRIER-CONTAINMENT-01). Fails closed.
        "carrier_containment": containment_check(
            root=root / "carrier-containment", manifest=analysis_image_manifest
        ),
    }
    print(json.dumps(result, indent=1, default=str))
    ok = (
        result["provider_state"] == "succeeded"
        and result["dry_run"]["real_pod_path"]["status"] == "OK"
        and result["dry_run"]["pod_failure_path"]["status"] == "OK"
        and result["dry_run"]["carrier_containment"]["status"] == "PASS"
    )
    return 0 if ok else 4


def main(argv=None):
    parser = ChallengeParser(prog="graphite.phase3")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--root", required=True)
    run.add_argument("--challenge", required=True, help=challenge_help())
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--grant")
    run.add_argument(
        "--level",
        type=int,
        default=0,
        help=(
            "construction level (default 0, the recorded contract); a level "
            "above 0 runs its registered development-only variant, or is refused"
        ),
    )
    credential = run.add_mutually_exclusive_group()
    credential.add_argument(
        "--credential-file",
        help="path of an owner-only file holding the Engy key, as phase 4 takes "
        "it; checked by its metadata, never printed",
    )
    credential.add_argument(
        "--credential-env",
        help="kept for older launchers: ENGY_API_KEY, copied to a 0600 file "
        "removed on exit; prefer --credential-file",
    )
    runpod = run.add_mutually_exclusive_group()
    runpod.add_argument("--runpod-key-file")
    runpod.add_argument("--runpod-key-env")
    run.add_argument(
        "--compute",
        choices=COMPUTE_LANES,
        default="runpod",
        help="where proposals run: RunPod GPU pods, or the CPU carrier "
        "(C-03, this operator host, Levels 0-3 only)",
    )
    run.add_argument(
        "--image-manifest", help="the pinned C-03 worker image (--compute carrier)"
    )
    run.add_argument(
        "--analysis-image-manifest",
        help="the campaign's pinned analysis image, for the dry run's carrier "
        "containment check (without it the check fails closed)",
    )
    run.add_argument("--miner-profile")
    run.add_argument("--miner-campaign")
    run.add_argument("--code-ref")
    run.add_argument(
        "--hidden-deployment",
        help="also score each construction on this battery deployment's hidden "
        "pool through the real validator, in this process (synthetic fixtures "
        "only; a sealed pool lives on its own host: use --hidden-endpoint)",
    )
    run.add_argument(
        "--hidden-endpoint",
        help="the hidden pool's host door (VALIDATOR-19 slice 0), reached with "
        "--hidden-submitter-key",
    )
    run.add_argument("--hidden-submitter-key")
    run.add_argument(
        "--hidden-ca",
        help="the hidden host's own TLS certificate, pinned (HIDDEN_HOST_SETUP.md)",
    )
    run.add_argument("--session", type=int, default=1)
    run.add_argument("--literature-snapshot")
    run.add_argument("--allow-unchecked-cards", action="store_true")
    run.add_argument(
        "--score-variant",
        metavar="VERSION",
        help=(
            "a registered development score variant (VALIDATOR-09), Level 0 "
            "only: its result is recorded beside the frozen rule's on every "
            "result; resolved before any spend, or refused"
        ),
    )
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--root", required=True)
    cancel.add_argument("--session", type=int, required=True)
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--root", required=True)
    reconcile.add_argument("--challenge", required=True, help=challenge_help())
    reconcile.add_argument("--grant", required=True)
    key = reconcile.add_mutually_exclusive_group(required=True)
    key.add_argument("--runpod-key-file")
    key.add_argument("--runpod-key-env")
    reconcile.add_argument("--code-ref", required=True)
    status = sub.add_parser("status")
    status.add_argument("--root", required=True)
    rebuild = sub.add_parser("rebuild")
    rebuild.add_argument("--bundle", required=True)
    proposals = sub.add_parser("proposals")
    proposals.add_argument("--root", required=True)
    proposals.add_argument("--dry-run", action="store_true")
    conditions = sub.add_parser("conditions")
    conditions.add_argument("--root", required=True)
    conditions.add_argument("--grant", required=True)
    conditions.add_argument("--challenge", required=True)
    mode = conditions.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", help="a carbon.admission-conditions.v1 report")
    mode.add_argument(
        "--identity",
        action="store_true",
        help="print the controller's identity only; nothing is consumed",
    )
    conditions.add_argument(
        "--record-also",
        action="store_true",
        help="record into a controller that is not the designated LOCK authority",
    )
    admission = sub.add_parser("admission-controller")
    actions = admission.add_subparsers(dest="action", required=True)
    init = actions.add_parser(
        "init", help="create a dedicated zero-spend admission controller"
    )
    init.add_argument("--root", required=True)
    init.add_argument("--challenge", required=True)
    init.add_argument("--grant", required=True)
    args = parser.parse_args(argv)
    if args.command == "run" and not args.dry_run:
        missing = [
            name
            for name, value in (
                ("--grant", args.grant),
                (
                    "--credential-file or --credential-env",
                    args.credential_file or args.credential_env,
                ),
                (
                    "--runpod-key-file or --runpod-key-env",
                    args.compute != "runpod"
                    or args.runpod_key_file
                    or args.runpod_key_env,
                ),
                (
                    "--image-manifest",
                    args.compute != "carrier" or args.image_manifest,
                ),
                ("--code-ref", args.code_ref),
            )
            if not value
        ]
        if missing:
            raise RunnerRefused("required: " + ", ".join(missing))
    return {
        "run": command_run,
        "cancel": command_cancel,
        "reconcile": command_reconcile,
        "status": command_status,
        "rebuild": command_rebuild,
        "proposals": command_proposals,
        "conditions": command_conditions,
        "admission-controller": command_admission_controller,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
