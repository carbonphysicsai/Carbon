"""Carbon's experiment runner for Graphite phase 3 (Constructor, Level 0).

The Constructor proposes; Carbon runs, scores and rebuilds (plan §5; invariants
7.9 and 7.10). One proposal goes through these steps, each journalled
write-once under the run's private root:

1. **Reconstruction gate** (OWNER-GRAPHITE-02's reconstruction rule). The
   proposal must be a declarative strategy that compiles under the selected
   Challenge's construction contract, and the live contract must be the one
   its newest expansion record pins (`carbon/reconstruction/expansions`).
   Level 0 widens nothing. A proposal Carbon cannot rebuild is refused
   fail-closed, typed `REFUSED_UNREBUILDABLE`, recorded as a finding and
   never run or scored. Carbon computes, before any pod, exactly what it
   would build: the recipe, the staged files and the program, by digest
   (`pod_phase.built_record`).
2. **Run.** One pod (`pods`), reserved first against the run's combined token
   and pod budget under the phase-3 grant. The pod reproduces Carbon's pinned
   digests or refuses to run. It is terminated and verified gone whatever
   happens, except when the process itself dies; a restart then terminates it
   and never launches it again.
3. **Independent rebuild.** What the pod reports it built is compared with
   what Carbon computed by itself. Any difference is a typed
   `REBUILD_MISMATCH` finding, and the proposal is not scored.
4. **Frozen-rule score.** Carbon scores fetched predictions on its own host
   against the selected Challenge's public PRACTICE references, gates,
   calibration and comparison rule through its named `ChallengeScoring`.
   This is development feedback on adaptively seen public cases, never an exam
   result.
5. **Stall rule.** After `roles.CONSTRUCTOR_STALL_ATTEMPTS` (5, OWNER-GRAPHITE-02)
   scored proposals in a row that are not an IMPROVEMENT over the baseline,
   Carbon records one `BUILD_STALLED_AGAINST_BASELINE` observation on the
   ladder for the run.

**Environment failures** (GRAPHITE-POD-GPU-PROBE-01, `pod-attribution-v2`).
A pod whose GPU probe failed before any candidate code is relaunched once on
a fresh pod, reserved and admitted like every pod (the session's pod limit,
the run's money cap, the remaining elapsed time and the pod launch gate),
with both attempts ledgered and typed. A proposal's infrastructure retries
share one cap (`AttributionPolicy.infra_retry_cap`). A second environment
failure stops the session: the stop is recorded write-once
(`session-stop.json`), no further pod is launched, and the provider ends the
session `FAILED_INFRA`, with no agent charge. The session's baseline gets at
most one extra pod from the relaunch and the baseline retry together.

Everything returned to the agent is data: a closed feedback document with no
authority, scanned like every other tool result by the role's toolbox.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

from carbon.challenge_validator import scoring as challenge_scoring
from carbon.challenge_validator.scoring import (
    NotServed,
    Unrebuildable,
    rebuild_differences,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from . import baseline_retry, pod_logs, pod_outcome
from . import pods as podlib
from .roles import (
    CONSTRUCTOR_STALL_ATTEMPTS,
    FailureKind,
    RoleName,
)

REPOSITORY = Path(__file__).resolve().parents[3]
PROPOSAL_SCHEMA = "carbon.graphite.phase3.proposal-result.v1"
FEEDBACK_SCHEMA = "carbon.graphite.phase3.feedback.v1"
STOP_SCHEMA = "carbon.graphite.phase3.session-stop.v1"
#: A proposal refused because Carbon stopped the session as infrastructure.
SESSION_STOPPED = "REFUSED_SESSION_STOPPED"
#: Reason prefixes when an environment relaunch cannot run.
RELAUNCH_REFUSED = "pod_environment_relaunch_refused:"
#: The session baseline's retry never gets a relaunch too: the baseline gets
#: at most one extra pod from the two rules together.
BASELINE_RETRY_USED = "baseline_retry_used"
RELAUNCH_NO_TIME = "relaunch_cannot_fit_remaining_time"
NANO = Decimal(10) ** 9
MAX_STRATEGY_BYTES = 16384


class BudgetRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


# -- the phase-3 budget --------------------------------------------------------------------
@dataclass(frozen=True)
class Phase3Budget:
    """One run's share of the grant, split between pods and tokens.

    The grant's `worst_case_run_cost` is the run's combined cap. Pods take
    `max_pods` proposals at `pod_minutes` each, at the EV4 rate ceiling plus
    disk (`pods.prices`); tokens take the rest. Both draw on the one cap: a
    pod is admitted only while tokens committed plus pods committed plus the
    new pod's reservation stay within it, and the run's model calls are capped
    at the token remainder by the research ledger.
    """

    run_cap_usd: Decimal
    hourly_usd: Decimal
    pod_minutes: int
    max_pods: int
    challenge_id: str

    @property
    def pod_reservation_usd(self):
        return podlib.pod_reservation(self.pod_minutes, self.hourly_usd)

    @property
    def pod_allowance_usd(self):
        return podlib.cents_up(self.max_pods * self.pod_reservation_usd)

    @property
    def token_allowance_usd(self):
        return self.run_cap_usd - self.pod_allowance_usd

    def record(self):
        return {
            "run_cap_usd": str(self.run_cap_usd),
            "pod_minutes": self.pod_minutes,
            "max_pods": self.max_pods,
            "hourly_usd": str(
                self.hourly_usd.quantize(podlib.NANODOLLAR, rounding=ROUND_CEILING)
            ),
            "pod_reservation_usd": str(self.pod_reservation_usd),
            "pod_allowance_usd": str(self.pod_allowance_usd),
            "token_allowance_usd": str(self.token_allowance_usd),
        }


#: The registered phase-3 session shape (GRAPHITE-D20, derived in
#: docs/development/graphite/grants/README.md): pod hours per session at the
#: plan's upper estimate (USD 1-3 of pod time, plan §7), in whole proposals.
SESSION_POD_MINUTES = 360


def phase3_budget(grant, scoring=None, hourly_usd=None):
    """One run's budget. `hourly_usd` is the compute backend's own rate when
    it declares one (the CPU carrier lane: 0, so the whole run cap goes to
    tokens); otherwise the RunPod rate ceiling (`pods.prices`)."""
    scoring = challenge_scoring.resolve(scoring)
    if hourly_usd is None:
        hourly_usd = podlib.prices()["hourly_usd"]
    minutes = podlib.proposal_minutes(scoring)
    budget = Phase3Budget(
        run_cap_usd=grant.worst_case_run_cost,
        hourly_usd=hourly_usd,
        pod_minutes=minutes,
        max_pods=SESSION_POD_MINUTES // minutes,
        challenge_id=scoring.challenge_id,
    )
    if budget.max_pods < 2 or budget.token_allowance_usd <= 0:
        # A baseline and one proposal, and some tokens, must fit one run.
        raise BudgetRefused("grant_run_cost_cannot_cover_pods_and_tokens")
    return budget


# -- the reconstruction gate ---------------------------------------------------------------
# The Challenge's own parts come through its `ChallengeScoring`
# (`carbon.challenge_validator.scoring`, VALIDATOR-01). With no scoring named,
# the only registered one serves; once several are registered, a caller must
# name its Challenge.
def recorded_contract(scoring=None):
    """The construction contract in force, only if its newest expansion record
    pins it (Level 0 constructs inside the recorded contract, nothing wider)."""
    return challenge_scoring.resolve(scoring).recorded_contract()


def admit(strategy, seed, root=REPOSITORY, scoring=None, variant=None):
    """Compile `strategy` exactly as Carbon would rebuild it; return what
    Carbon would build (`ChallengeScoring.built_record`). Raises `Unrebuildable`
    (never scored) or `NotServed` (Carbon rebuilds it, these pods do not).

    `variant` is the registered development-only variant of a development
    level (OWNER-GRAPHITE-TEST-WAVE-03 §1), or None at Level 0. With one, the
    strategy compiles through the variant's own path
    (`development_variants.compile_development`) for the same explicit
    Challenge; Level 0 is unchanged."""
    if type(strategy) is not dict:
        raise Unrebuildable("strategy_not_an_object")
    resolved = (
        challenge_scoring.scoring_for(strategy.get("challenge_id"))
        if scoring is None
        else challenge_scoring.resolve(scoring)
    )
    if strategy.get("challenge_id") != resolved.challenge_id:
        raise Unrebuildable(resolved.wrong_challenge_code)
    if variant is not None:
        from carbon.reconstruction import development_variants

        return development_variants.admit(resolved, strategy, seed, root, variant)
    contract = recorded_contract(resolved)
    return challenge_scoring.admit(resolved, strategy, seed, root, contract=contract)


def development_differences(expected, built):
    """At a development level, the variant binding must match too."""
    if "development" not in expected:
        return []
    if type(built) is not dict or built.get("development") != expected["development"]:
        return ["development"]
    return []


# -- the frozen rule -----------------------------------------------------------------------
def frozen_rule(root=REPOSITORY, scoring=None):
    """The Challenge's frozen rule on its public PRACTICE references
    (development feedback only)."""
    return challenge_scoring.resolve(scoring).frozen_rule(root)


#: The name earlier callers construct the frozen rule by.
FrozenRule = frozen_rule
#: What Carbon compares between what it computed and what the pod built
#: (`rebuild_differences`); the Attacker's tamper fields are pinned to it.
REBUILT_FIELDS = challenge_scoring.REBUILT_FIELDS
_clean = challenge_scoring.clean


# -- the pod ledger ------------------------------------------------------------------------
class PodLedger:
    """EV4's campaign-ledger pattern, per run: an append-only JSONL file of
    every pod event. Spend is read back from it: a pod's committed amount is
    its provider-reported charge once settled, and otherwise its full
    reservation (an unknown outcome keeps its reservation)."""

    def __init__(self, path, clock):
        self.path = Path(path)
        self.clock = clock

    def append(self, event, **body):
        row = {"event": event, "at": self.clock(), **body}
        with self.path.open("ab") as stream:
            stream.write(canonical(row) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.path.chmod(0o600)
        return row

    def rows(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_bytes().splitlines()]

    def pods(self):
        state = {}
        for row in self.rows():
            intent = row.get("intent_id")
            if intent is None:
                continue
            pod = state.setdefault(
                intent,
                {
                    "intent_id": intent,
                    "proposal": row.get("proposal"),
                    "reserved_usd": None,
                    "settled_usd": None,
                    "launch": None,
                    "pod_id": None,
                    "rate_usd_per_hr": None,
                    "terminated": False,
                },
            )
            event = row["event"]
            if event == "pod_reserved":
                pod["reserved_usd"] = row["reserved_usd"]
            elif event == "pod_launch_requested":
                pod["launch"] = pod["launch"] or "requested"
            elif event == "pod_launch_refused":
                pod["launch"] = "refused"
                pod["terminated"] = True  # nothing was created
            elif event == "pod_launch_ambiguous":
                pod["launch"] = "ambiguous"
            elif event == "pod_created":
                pod["launch"] = "created"
                pod["pod_id"] = row["pod_id"]
                pod["rate_usd_per_hr"] = row.get("rate_usd_per_hr")
            elif event == "pod_terminated_verified":
                pod["terminated"] = True
            elif event == "pod_settled":
                pod["settled_usd"] = row["charge_usd"]
        return state

    def committed(self):
        """(settled, pending) USD across the run's pods."""
        settled = pending = Decimal(0)
        for pod in self.pods().values():
            if pod["settled_usd"] is not None:
                settled += Decimal(pod["settled_usd"])
            elif pod["reserved_usd"] is not None:
                pending += Decimal(pod["reserved_usd"])
        return settled, pending

    def live(self):
        """Pods that were (or may have been) created and are not verified gone."""
        return [
            pod
            for pod in self.pods().values()
            if pod["launch"] in ("requested", "created", "ambiguous")
            and not pod["terminated"]
        ]

    def never_dispatched(self):
        """Pods reserved whose create was never requested: nothing to pay."""
        return [
            pod
            for pod in self.pods().values()
            if pod["launch"] is None and pod["settled_usd"] is None
        ]


# -- the runner ----------------------------------------------------------------------------
def _feedback_view(record):
    """What the agent sees of one proposal: closed fields, no authority."""
    view = {
        "schema": FEEDBACK_SCHEMA,
        "status": record["status"],
        "proposal_id": record["proposal_id"],
        "kind": record["kind"],
        "development_feedback_only": True,
        "official_eligible": False,
        "authority_granted": False,
    }
    for key in (
        "reason_code",
        "issues",
        "recipe_digest",
        "frozen_rule",
        "against_baseline",
        "baseline",
        "fit",
        "differences",
        "stall",
        "pods_left",
        # The hidden-pool view (`hidden_score`): only what a mainnet miner sees.
        "hidden",
    ):
        if key in record:
            view[key] = record[key]
    return view


class Experiment:
    """One run's proposals: admission, pods, rebuild check, frozen-rule score.

    `pods` is a `pods.PodBackend`; `token_committed()` returns the run's model
    spend in USD (settled plus still reserved); `cancelled()` is the run's
    cancellation; `ladder` is the provider's escalation ladder; `emit` journals
    an event for the controller. `construction_level` is the session's
    recorded construction level (its permission profile), never the
    submission's; it decides whose claims a pod's files carry
    (`pod_outcome`). None means unknown, and then no pod claim blames the
    candidate. `attribution_policy` names a registered attribution policy
    version; None is the registry's current one. `development_variant` is the
    registered development-only variant (`DevContractVariant`) of a
    development level, or None at Level 0; with one, every proposal compiles
    through the variant's own path and its pod job names the variant.

    The session's baseline (Carbon's own recipe and seed), when it closes
    `FAILED_INFRA` or with its program crashed, is run once more under the
    registered baseline-retry policy (`baseline_retry`; `retry_policy` names a
    version, None is the current one). `seconds_left` reads the run's
    remaining elapsed time (None: no elapsed limit); the retry starts only
    when it and the waiting proposal's pod can finish within it. The logs of
    a pod run that does not score are kept, bounded, in its proposal's record
    directory (`pod_logs`), as operator evidence only.

    `hidden` is a `hidden_score.HiddenPool` (VALIDATOR-13) or None. With one,
    every scored proposal is also submitted to the battery validator's hidden
    pool. Its record and feedback carry only the miner-visible `hidden` view;
    the operator record is written beside them (`hidden-operator.json`) and
    nowhere else. With None, nothing changes. Level 0 only: the validator
    never serves a development variant.
    """

    def __init__(
        self,
        *,
        root,
        run_id,
        pods,
        budget,
        baseline,
        token_committed,
        cancelled,
        ladder,
        emit,
        scorer=None,
        repository=REPOSITORY,
        clock,
        randomness=os.urandom,
        scoring=None,
        construction_level=None,
        attribution_policy=None,
        retry_policy=None,
        seconds_left=None,
        development_variant=None,
        on_finding=None,
        hidden=None,
    ):
        from .provider import RunCancelled

        self.root = podlib.private_dir(root)
        podlib.private_dir(self.root / "proposals")
        self.run_id, self.pods, self.budget = run_id, pods, budget
        self.baseline = baseline
        self.token_committed, self.cancelled = token_committed, cancelled
        self.ladder, self.emit = ladder, emit
        self.scorer = scorer
        self.repository, self.clock, self.randomness = repository, clock, randomness
        self.ledger = PodLedger(self.root / "pod-ledger.jsonl", clock)
        self._cancel = RunCancelled
        self.scoring = challenge_scoring.resolve(scoring)
        self.construction_level = construction_level
        self.development_variant = development_variant
        #: Called with each new finding once it is durable, so the caller can
        #: record it on the campaign controller before any later result
        #: (conditional-evidence.v2 "ordering"); None records nothing more.
        self.on_finding = on_finding
        if development_variant is not None and (
            construction_level != development_variant.level
        ):
            raise ValueError("a development variant runs at its own level")
        if hidden is not None and (
            development_variant is not None
            or hidden.challenge_id != self.scoring.challenge_id
        ):
            raise ValueError("hidden scoring serves its own Challenge at Level 0")
        self.hidden = hidden
        # The registered attribution policy (`pod_outcome`): the registry's
        # current version unless one is named.
        self.attribution = (
            pod_outcome.load_policy()
            if attribution_policy is None
            else pod_outcome.load_policy(attribution_policy)
        )
        self.retry_policy = (
            baseline_retry.load_policy()
            if retry_policy is None
            else baseline_retry.load_policy(retry_policy)
        )
        self.seconds_left = seconds_left
        # The log bodies fetched from each proposal's pods, held until the
        # proposal closes: written only when it does not score.
        self._logs = {}

    # -- records ---------------------------------------------------------------------------
    def _dir(self, pid):
        return podlib.private_dir(self.root / "proposals" / pid)

    def _scorer(self):
        if self.scorer is None:
            self.scorer = frozen_rule(self.repository, self.scoring)
        elif not hasattr(self.scorer, "score"):
            self.scorer = self.scorer()  # a factory, called once when needed
        return self.scorer

    def records(self, kind=None):
        found = []
        for path in sorted((self.root / "proposals").glob("*/result.json")):
            record = json.loads(path.read_bytes())
            if kind is None or record["kind"] == kind:
                found.append(record)
        return sorted(found, key=lambda r: r["ordinal"])

    def record(self, pid):
        path = self.root / "proposals" / pid / "result.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def rows(self, pid):
        path = self.root / "proposals" / pid / "rows.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def hidden_records(self):
        """The run's hidden-pool operator records, by proposal (operator
        evidence; `DEVELOPMENT_HIDDEN_POOL`). Scores are comparable only within
        one pool version; the validator's own leader is `hidden.standing()`."""
        found = []
        for record in self.records():
            path = self.root / "proposals" / record["proposal_id"]
            path = path / "hidden-operator.json"
            if path.exists():
                found.append(
                    {
                        "proposal_id": record["proposal_id"],
                        "kind": record["kind"],
                        **json.loads(path.read_bytes()),
                    }
                )
        return found

    def findings(self):
        path = self.root / "findings.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def _finding(self, kind, pid, detail):
        evidence = {
            "schema": "carbon.graphite.phase3.finding.v1",
            "kind": kind,
            "run_id": self.run_id,
            "proposal_id": pid,
            "detail": detail,
        }
        body = canonical(evidence)
        finding_id = "graphite-{}-{}".format(
            kind.lower().replace("_", "-"), digest(body)[7:23]
        )
        if any(f["id"] == finding_id for f in self.findings()):
            return finding_id
        finding = {"id": finding_id, "condition": "OTHER_SIGNAL", "evidence": evidence}
        line = canonical(finding)
        with (self.root / "findings.jsonl").open("ab") as stream:
            stream.write(line + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.emit(
            "finding-" + finding_id,
            {"kind": "finding", "finding_id": finding_id, "finding": kind},
        )
        if self.on_finding is not None:
            self.on_finding(finding)
        return finding_id

    def _seed(self, pid):
        path = self._dir(pid) / "seed.bin"
        if not path.exists():
            write_once(path, self.randomness(4))
        return int.from_bytes(path.read_bytes()[:4], "big")

    def _close(self, pid, record):
        held = self._logs.pop(pid, None)
        if held and pod_logs.kept_for(record["status"]):
            # Operator evidence only: never in the record, the feedback, an
            # event or a bundle (`pod_logs`).
            kept = pod_logs.keep(self._dir(pid) / "pod-logs", held)
            self.ledger.append("pod_logs_kept", proposal=pid, attempts=kept)
        write_once(self._dir(pid) / "result.json", canonical(record))
        self.emit(
            "proposal-" + pid,
            {
                "kind": "proposal_result",
                "proposal_id": pid,
                "status": record["status"],
                "result_digest": digest(canonical(record)),
            },
        )
        return record

    # -- spend -----------------------------------------------------------------------------
    def pod_committed(self):
        settled, pending = self.ledger.committed()
        return settled + pending

    def pods_left(self):
        return self.budget.max_pods - sum(
            1 for p in self.ledger.pods().values() if p["reserved_usd"] is not None
        )

    def _admit_pod(self):
        if self.pods_left() <= 0:
            raise BudgetRefused("session_pod_limit_reached")
        reservation = self.budget.pod_reservation_usd
        committed = self.token_committed() + self.pod_committed()
        if committed + reservation > self.budget.run_cap_usd:
            raise BudgetRefused("run_cap_reached_tokens_plus_pods")
        return reservation

    # -- reconciliation ----------------------------------------------------------------------
    def reconcile(self):
        """After a restart, or on cancellation with no worker: terminate every
        pod this run may have created and that is not verified gone, then
        settle what the provider reports. Never launches anything."""
        report = []
        for pod in self.ledger.never_dispatched():
            self.ledger.append(
                "pod_settled",
                intent_id=pod["intent_id"],
                proposal=pod["proposal"],
                charge_usd="0",
                basis="reserved_never_dispatched",
            )
        for pod in self.ledger.live():
            handle = None
            if pod["launch"] == "created":
                handle = podlib.PodHandle(
                    pod["intent_id"], pod["pod_id"], pod["rate_usd_per_hr"]
                )
            else:
                handle = self._recover(pod["proposal"], pod["intent_id"])
                if handle is None:
                    report.append({"intent_id": pod["intent_id"], "terminated": True})
                    continue
                if handle == "unknown":
                    report.append({"intent_id": pod["intent_id"], "terminated": None})
                    continue
                self.ledger.append(
                    "pod_created",
                    intent_id=pod["intent_id"],
                    proposal=pod["proposal"],
                    pod_id=handle.pod_id,
                    rate_usd_per_hr=handle.rate_usd_per_hr,
                    via="recover",
                )
            verified = self._terminate(pod["proposal"], handle)
            report.append({"intent_id": pod["intent_id"], "terminated": verified})
        return report

    def _recover(self, pid, intent_id):
        """A pod an uncertain create may have made. None when none exists (its
        reservation is then released), "unknown" when the provider cannot say
        yet (the reservation stays), else its handle."""
        try:
            handle = self.pods.recover(intent_id, self._dir(pid) / "private")
        except podlib.PodFailure:
            return "unknown"
        if handle is None:
            self.ledger.append(
                "pod_launch_refused",
                intent_id=intent_id,
                proposal=pid,
                stage="recover_found_no_pod",
            )
            self.ledger.append(
                "pod_settled",
                intent_id=intent_id,
                proposal=pid,
                charge_usd="0",
                basis="no_pod_was_created",
            )
        return handle

    def _terminate(self, pid, handle):
        self.ledger.append(
            "pod_terminate_requested",
            intent_id=handle.intent_id,
            proposal=pid,
            pod_id=handle.pod_id,
        )
        for _ in range(3):
            if self.pods.terminate(handle):
                self.ledger.append(
                    "pod_terminated_verified",
                    intent_id=handle.intent_id,
                    proposal=pid,
                    pod_id=handle.pod_id,
                )
                self._settle(pid, handle)
                return True
        self.ledger.append(
            "pod_terminate_unverified",
            intent_id=handle.intent_id,
            proposal=pid,
            pod_id=handle.pod_id,
        )
        return False

    def _settle(self, pid, handle):
        charge = self.pods.charge(handle)
        if charge is None:
            self.ledger.append(
                "pod_charge_unresolved",
                intent_id=handle.intent_id,
                proposal=pid,
                note="no provider-reported charge; the full reservation is kept",
            )
            return
        self.ledger.append(
            "pod_settled",
            intent_id=handle.intent_id,
            proposal=pid,
            charge_usd=str(charge),
            basis="provider_reported",
        )

    # -- one proposal --------------------------------------------------------------------------
    def propose_tool(self, arguments, identity):
        """The agent's `graphite_run_proposal` tool."""
        if (
            type(arguments) is not dict
            or set(arguments) != {"strategy_json", "hypothesis", "expected_effect"}
            or type(arguments["strategy_json"]) is not str
            or len(arguments["strategy_json"].encode()) > MAX_STRATEGY_BYTES
            or any(
                type(arguments[k]) is not str or not 1 <= len(arguments[k]) <= 2048
                for k in ("hypothesis", "expected_effect")
            )
        ):
            return {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason_code": "proposal_arguments_malformed",
                "dispatched": False,
                "authority_granted": False,
            }
        try:
            strategy = json.loads(arguments["strategy_json"])
        except ValueError:
            return {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason_code": "strategy_json_not_json",
                "dispatched": False,
                "authority_granted": False,
            }
        pid = "p-" + digest(identity.encode())[7:19]
        stop = self.stopped()
        if stop is not None and self.record(pid) is None:
            # Carbon stopped the session as infrastructure: nothing new runs.
            return {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason_code": "session_stopped:" + stop["reason_code"],
                "dispatched": False,
                "authority_granted": False,
            }
        record = self.run(
            pid,
            "proposal",
            strategy,
            why={
                "hypothesis": arguments["hypothesis"],
                "expected_effect": arguments["expected_effect"],
            },
        )
        return _feedback_view(record)

    def _baseline_needed(self):
        record = self.record("baseline")
        return record is None

    def baseline_record(self):
        return self.record("baseline")

    # -- the baseline retry (`baseline_retry`) -----------------------------------------------
    def baseline_id(self):
        """The proposal id of the session's baseline: its retry when the first
        did not score and the retry did, else `baseline`."""
        first = self.record("baseline")
        if first is not None and first["status"] != "SCORED":
            retried = self.record(baseline_retry.RETRY_ID)
            if retried is not None and retried["status"] == "SCORED":
                return baseline_retry.RETRY_ID
        return "baseline"

    def baseline_retry(self):
        """The recorded retry decision, or None when none was needed yet."""
        path = self.root / "baseline-retry.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def pods_before_proposal(self):
        """Pods Carbon runs before the next proposal's own: the baseline's
        when it has not run, or a decided retry a process death interrupted.
        (A retry decided later is held to the time gate when it is decided.)"""
        if self.record("baseline") is None:
            return 1
        decision = self.baseline_retry()
        pending = (
            decision is not None
            and decision["retry"]
            and self.record(baseline_retry.RETRY_ID) is None
        )
        return 1 if pending else 0

    def _retry_budget(self, pods):
        """None when the session's pod limit and the run's money cap (tokens
        and pods together) hold `pods` more pods, else the refusal code."""
        if self.pods_left() < pods:
            return "session_pod_limit_reached"
        committed = self.token_committed() + self.pod_committed()
        if committed + pods * self.budget.pod_reservation_usd > self.budget.run_cap_usd:
            return "run_cap_reached_tokens_plus_pods"
        return None

    def _fits_time(self, pods):
        left = None if self.seconds_left is None else self.seconds_left()
        return left is None or pods * self.budget.pod_minutes * 60 <= left

    # -- environment relaunches and the session stop (`pod-attribution-v2`) -----------------
    def _relaunch_refusal(self, pid):
        """Why an environment relaunch cannot run, or None. Its pod is then
        admitted like any pod (`_admit_pod`: the session's pod limit and the
        run's money cap) and launched through the pod launch gate."""
        if pid == baseline_retry.RETRY_ID:
            return BASELINE_RETRY_USED
        if not self._fits_time(1):
            return RELAUNCH_NO_TIME
        return None

    def relaunched(self, pid):
        """Whether proposal `pid` used an environment relaunch: an extra pod
        admitted for it, as the pod ledger records."""
        return any(
            row["event"] == "pod_environment_relaunch" and row.get("proposal") == pid
            for row in self.ledger.rows()
        )

    def stopped(self):
        """The recorded session stop, or None."""
        path = self.root / "session-stop.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def _stop_session(self, pid, verdict):
        """Record, once, that Carbon stops the session as infrastructure: no
        agent charge, no further pod. The provider ends the session."""
        if self.stopped() is not None:
            return
        stop = {
            "schema": STOP_SCHEMA,
            "status": "FAILED_INFRA",
            "reason_code": verdict.reason_code,
            "proposal_id": pid,
            "policy": self.attribution.record(),
            "candidate_charged": False,
        }
        write_once(self.root / "session-stop.json", canonical(stop))
        self.ledger.append(
            "session_stopped",
            proposal=pid,
            status="FAILED_INFRA",
            reason_code=verdict.reason_code,
            policy=self.attribution.record(),
        )
        self.emit(
            "session-stopped",
            {
                "kind": "session_stopped",
                "status": "FAILED_INFRA",
                "reason_code": verdict.reason_code,
                "proposal_id": pid,
                "policy": self.attribution.record(),
            },
        )

    def _retry_baseline(self):
        """Decide once, under the registered policy, whether the session's
        failed baseline runs once more, record the decision and run the retry.
        Called before a proposal's own pod; a decision is never re-made."""
        path = self.root / "baseline-retry.json"
        decision = self.baseline_retry()
        if decision is not None:
            if decision["retry"] and self.record(baseline_retry.RETRY_ID) is None:
                self._run_retry(decision)  # a process died after the decision
            return
        first = self.record("baseline")
        if first is None or first["status"] == "SCORED" or self.stopped():
            return
        policy = self.retry_policy
        retry, reason = baseline_retry.decide(
            policy=policy,
            first=first,
            retries_used=int(
                (self.root / "proposals" / baseline_retry.RETRY_ID).exists()
            ),
            budget_refusal=self._retry_budget(policy.pods_required),
            time_fits=self._fits_time(policy.pods_required),
            environment_relaunched=self.relaunched("baseline"),
        )
        earlier = [
            r["proposal_id"]
            for r in self.records()
            if r["kind"] != "baseline" and r["status"] == "SCORED"
        ]
        decision = {
            "schema": baseline_retry.DECISION_SCHEMA,
            "policy": policy.record(),
            "baseline": {
                "proposal_id": "baseline",
                "status": first["status"],
                "reason_code": first.get("reason_code"),
            },
            "retry": retry,
            "reason_code": reason,
            "retry_proposal_id": baseline_retry.RETRY_ID if retry else None,
            "seed": "same_as_failed_baseline",
            "pods_required": policy.pods_required,
            "pods_left": self.pods_left(),
            # Result records are write-once: these stay NO_BASELINE.
            "earlier_scored_not_recompared": earlier,
            "earlier_scored_note": (
                "scored before the retry against no baseline; result records "
                "are write-once and are not re-compared"
                if earlier
                else None
            ),
        }
        write_once(path, canonical(decision))
        self.ledger.append(
            "baseline_retry_decided",
            proposal="baseline",
            retry=retry,
            reason_code=reason,
            retry_proposal_id=decision["retry_proposal_id"],
            policy=policy.record(),
        )
        self.emit(
            "baseline-retry",
            {
                "kind": "baseline_retry",
                "retry": retry,
                "reason_code": reason,
                "baseline_status": first["status"],
                "baseline_reason_code": first.get("reason_code"),
                "policy": policy.record(),
                "decision_digest": digest(canonical(decision)),
            },
        )
        if retry:
            self._run_retry(decision)

    def _run_retry(self, decision):
        """The retry: the same strategy, with the failed baseline's seed."""
        seed = self.root / "proposals" / "baseline" / "seed.bin"
        target = self._dir(baseline_retry.RETRY_ID) / "seed.bin"
        if seed.is_file() and not target.exists():
            write_once(target, seed.read_bytes())
        self.run(
            baseline_retry.RETRY_ID,
            "baseline",
            self.baseline,
            why={
                "baseline_retry_of": "baseline",
                "reason_code": decision["baseline"]["reason_code"],
                "policy": decision["policy"],
            },
        )

    def run(self, pid, kind, strategy, *, why, parent=None):
        """Admit, run, rebuild-check and score one strategy. Idempotent: a
        closed proposal returns its record; one interrupted by a process death
        has its pod terminated and is closed `FAILED_INFRA`, never rerun."""
        closed = self.record(pid)
        if closed is not None:
            return closed
        folder = self._dir(pid)
        intent_path = folder / "intent.json"
        if not intent_path.exists():
            ordinal = len(list((self.root / "proposals").glob("*/intent.json")))
            write_once(
                intent_path,
                canonical(
                    {
                        "proposal_id": pid,
                        "kind": kind,
                        "ordinal": ordinal,
                        "strategy": strategy,
                        "why": why,
                        "parent": parent,
                    }
                ),
            )
        intent = json.loads(intent_path.read_bytes())
        base = {
            "schema": PROPOSAL_SCHEMA,
            "proposal_id": pid,
            "kind": kind,
            "ordinal": intent["ordinal"],
            "strategy_digest": digest(canonical(strategy)),
            "parent": parent,
        }
        seed = self._seed(pid)
        try:
            # Level 0 calls admission exactly as before; only a development
            # level names its variant.
            level = (
                {}
                if self.development_variant is None
                else {"variant": self.development_variant}
            )
            expected = admit(strategy, seed, self.repository, self.scoring, **level)
        except Unrebuildable as refused:
            finding = self._finding(
                "UNREBUILDABLE",
                pid,
                {"code": refused.code, "issues": [list(i) for i in refused.issues]},
            )
            return self._close(
                pid,
                {
                    **base,
                    "status": "REFUSED_UNREBUILDABLE",
                    "reason_code": refused.code,
                    "issues": [list(i) for i in refused.issues],
                    "finding": finding,
                    "scored": False,
                },
            )
        except NotServed as refused:
            return self._close(
                pid,
                {
                    **base,
                    "status": "REFUSED_BACKEND_NOT_SERVED",
                    "reason_code": str(refused),
                    "scored": False,
                },
            )
        write_once(folder / "expected.json", canonical(expected))
        intent_id = (self.run_id + "-" + pid)[:120]
        if any(p["intent_id"] == intent_id for p in self.ledger.pods().values()):
            # A process died after this proposal reserved its pod: terminate
            # whatever it may have created, and never launch it again.
            self.reconcile()
            return self._close(
                pid,
                {
                    **base,
                    "status": "FAILED_INFRA",
                    "reason_code": "interrupted_not_rerun",
                    "recipe_digest": expected["recipe_digest"],
                    "scored": False,
                },
            )
        if kind != "baseline" and self._baseline_needed():
            # The session's baseline runs once, before the first admitted
            # proposal, on the same path and the same frozen rule.
            self.run("baseline", "baseline", self.baseline, why=None)
        if kind != "baseline":
            self._retry_baseline()
        stop = self.stopped()
        if stop is not None:
            # The session was stopped as infrastructure (here, by the
            # baseline's repeated environment failure): no pod is launched.
            return self._close(
                pid,
                {
                    **base,
                    "status": SESSION_STOPPED,
                    "reason_code": stop["reason_code"],
                    "recipe_digest": expected["recipe_digest"],
                    "scored": False,
                    "pods_left": self.pods_left(),
                },
            )
        try:
            reservation = self._admit_pod()
        except BudgetRefused as refused:
            return self._close(
                pid,
                {
                    **base,
                    "status": "REFUSED_BUDGET",
                    "reason_code": refused.code,
                    "recipe_digest": expected["recipe_digest"],
                    "scored": False,
                    "pods_left": self.pods_left(),
                },
            )
        common = {**base, "recipe_digest": expected["recipe_digest"]}
        attempts, verdict = [], None
        for attempt in range(pod_attempts(self.attribution)):
            if attempt:
                # A retry on a fresh pod under the same declared budget: after
                # a worker timeout, or a relaunch after an environment
                # failure, within the proposal's one cap on infrastructure
                # retries (`pod_attempts`). It is charged to the run like any
                # pod and admitted by the same limits.
                prefix = (
                    RELAUNCH_REFUSED
                    if verdict.relaunch
                    else "worker_timeout_retry_refused:"
                )
                refusal = self._relaunch_refusal(pid) if verdict.relaunch else None
                if refusal is None:
                    try:
                        reservation = self._admit_pod()
                    except BudgetRefused as refused:
                        refusal = refused.code
                if refusal is not None:
                    return self._close(
                        pid,
                        {
                            **common,
                            "status": "FAILED_INFRA",
                            "reason_code": prefix + refusal,
                            **_attempts(attempts),
                            "scored": False,
                            "pods_left": self.pods_left(),
                        },
                    )
                if verdict.relaunch:
                    self.ledger.append(
                        "pod_environment_relaunch",
                        proposal=pid,
                        attempt=attempt,
                        policy=self.attribution.record(),
                    )
            job_intent = intent_id if not attempt else retry_intent(intent_id, attempt)
            outcome, files, timing = self._attempt(
                pid, job_intent, reservation, strategy, expected, seed
            )
            if outcome in ("launch_refused", "launch_unresolved", "infra"):
                return self._close(
                    pid,
                    {
                        **common,
                        "status": "FAILED_INFRA",
                        "reason_code": outcome,
                        **_attempts(attempts),
                        "scored": False,
                        "pods_left": self.pods_left(),
                    },
                )
            built = _json(files.get("built.json"))
            failure = _object(files.get("failure.json"))
            if _stage(failure) == pod_outcome.ENVIRONMENT and "built.json" not in files:
                # The pod stopped at the probe, before anything was built:
                # there is no build to compare. The claim is typed below.
                differences = []
            else:
                differences = rebuild_differences(expected, built)
                if not differences:
                    differences = development_differences(expected, built)
            if (failure or {}).get("stage") == "verification" and not differences:
                differences = ["pod_refused_pinned_digests"]
            if differences:
                finding = self._finding(
                    "REBUILD_MISMATCH", pid, {"differences": differences}
                )
                return self._close(
                    pid,
                    {
                        **common,
                        "status": "REBUILD_MISMATCH",
                        "differences": differences,
                        "finding": finding,
                        **_attempts(attempts),
                        "scored": False,
                        "pods_left": self.pods_left(),
                    },
                )
            if outcome == "done":
                break
            verdict, evidence = self._type_unfinished(
                pid,
                job_intent,
                attempt,
                files,
                failure,
                timing,
                earlier=tuple(a["reason_code"] for a in attempts),
            )
            attempts.append(evidence)
            if verdict.retry:
                continue
            if verdict.stop:
                self._stop_session(pid, verdict)
            return self._close(
                pid,
                {
                    **common,
                    "status": verdict.status,
                    "reason_code": verdict.reason_code,
                    **_attempts(attempts),
                    "scored": False,
                    "pods_left": self.pods_left(),
                },
            )
        else:
            # Every allowed attempt asked for a retry: the cap stops it here,
            # whatever the policy said (never a loop).
            return self._close(
                pid,
                {
                    **common,
                    "status": "FAILED_INFRA",
                    "reason_code": "infra_retry_cap_reached",
                    **_attempts(attempts),
                    "scored": False,
                    "pods_left": self.pods_left(),
                },
            )
        predictions = _json(files.get("predictions.json"))
        if type(predictions) is not dict:
            return self._close(
                pid,
                {
                    **common,
                    "status": "FAILED_INFRA",
                    "reason_code": "predictions_missing",
                    **_attempts(attempts),
                    "scored": False,
                    "pods_left": self.pods_left(),
                },
            )
        scorer = self._scorer()
        rows, summary = scorer.score(predictions)
        write_once(folder / "rows.json", canonical(rows))
        fit = _object(files.get("fit.json")) or {}
        record = {
            **common,
            "status": "SCORED",
            "scored": True,
            "rule": scorer.identity,
            "built_digest": digest(canonical(built)),
            "frozen_rule": {
                key: summary.get(key)
                for key in (
                    "eligible",
                    "score",
                    "important_score",
                    "n_scored",
                    "n_gate_failed",
                    "gate_failures",
                    "components",
                )
            },
            "fit": {
                key: _clean(fit[key])
                for key in ("final_loss", "train_s", "compile_s", "n_params")
                if key in fit
            },
            "pods_left": self.pods_left(),
            **_attempts(attempts),
        }
        if kind != "baseline":
            baseline_id = self.baseline_id()
            baseline_rows = self.rows(baseline_id)
            baseline = self.record(baseline_id)
            if baseline_rows is None or baseline["status"] != "SCORED":
                record["against_baseline"] = {
                    "outcome": "NO_BASELINE",
                    "reason": "the session's baseline was not scored",
                    "promotable": False,
                }
            else:
                comparison = scorer.compare(
                    baseline_rows, rows, bool(summary.get("eligible"))
                )
                record["against_baseline"] = {
                    key: comparison.get(key)
                    for key in (
                        "outcome",
                        "reason",
                        "promotable",
                        "n",
                        "mean_delta",
                        "ci",
                        "overall",
                        "important",
                    )
                }
                if comparison.get("interpretation") is not None:
                    record["against_baseline"]["interpretation"] = comparison[
                        "interpretation"
                    ]
                record["baseline"] = {
                    "eligible": baseline["frozen_rule"]["eligible"],
                    "score": baseline["frozen_rule"]["score"],
                }
                if baseline_id != "baseline":
                    # The session's baseline is its retry (`baseline_retry`).
                    record["baseline"]["proposal_id"] = baseline_id
        if kind == "proposal":
            record["stall"] = self._stall(record)
        if self.hidden is not None:
            record["hidden"] = self._hidden_score(pid, kind, strategy)
        return self._close(pid, record)

    def _hidden_score(self, pid, kind, strategy):
        """Submit a scored proposal to the hidden pool (`hidden_score`). The
        record keeps only the miner-visible view; the operator record is
        written once beside it and is never in a record, feedback, event or
        bundle."""
        view, operator = self.hidden.submit(kind, strategy)
        if operator is not None:
            write_once(self._dir(pid) / "hidden-operator.json", canonical(operator))
        return view

    def _attempt(self, pid, intent_id, reservation, strategy, expected, seed):
        """Reserve and run one pod for a proposal; `(outcome, files, timing)`."""
        self.ledger.append(
            "pod_reserved",
            intent_id=intent_id,
            proposal=pid,
            reserved_usd=str(reservation),
            minutes=self.budget.pod_minutes,
        )
        job = podlib.PodJob(
            intent_id=intent_id,
            strategy=strategy,
            contract_digest=expected["contract_digest"],
            seed=seed,
            expected={"files": expected["staged"], "program": expected["program"]},
            minutes=self.budget.pod_minutes,
            seconds=podlib.contract_work_seconds(self.scoring),
            development_variant=(
                None
                if self.development_variant is None
                else self.development_variant.digest
            ),
        )
        return self._pod(pid, job)

    def _type_unfinished(
        self, pid, intent_id, attempt, files, failure, timing, earlier=()
    ):
        """Type a pod run that ended without finishing under the registered
        attribution policy (`pod_outcome.classify`): host timing and lifecycle
        decide, and the construction level decides whose claims the pod's
        files carry. The evidence keeps the raw claim, the host's timing and
        the policy, so the policy can be judged from it. `earlier` is the
        reason codes of this proposal's earlier attempts."""
        image = (self.pods.describe() or {}).get("image")
        report = _object(files.get("supervisor.json"))
        claim = _stage(failure)
        # The deadline host timing is compared with (the backend's declared
        # program deadline, VALIDATOR-06) and the export v2 reads (#604).
        deadline = self._program_deadline()
        export = pod_outcome.environment_export(files, report)
        verdict = pod_outcome.classify(
            claim=claim,
            admissible=pod_outcome.admissible_stage(report, image),
            timing=timing,
            work_seconds=deadline,
            attempt=attempt,
            level=self.construction_level,
            policy=self.attribution,
            export=export,
            earlier=earlier,
        )
        evidence = {
            "intent_id": intent_id,
            "attempt": attempt,
            "construction_level": self.construction_level,
            "attribution_policy": self.attribution.record(),
            "status": verdict.status,
            "reason_code": verdict.reason_code,
            "claimed_stage": claim,
            "claim": _raw_claim(files.get("failure.json")),
            "failure_digest": (
                digest(files["failure.json"]) if "failure.json" in files else None
            ),
            "host_timing": None if timing is None else timing.record(),
            # What host timing is compared with: the contract's deadline, or
            # the backend's declared effective program deadline.
            "program_deadline_seconds": deadline,
        }
        if claim == pod_outcome.ENVIRONMENT:
            # What the export showed against the claim (v2's consistency
            # check). Recorded only for this claim, so every other typed
            # outcome keeps the shape it had.
            evidence["environment_export"] = export
        self.ledger.append(
            "pod_attempt_typed",
            intent_id=intent_id,
            proposal=pid,
            status=verdict.status,
            reason_code=verdict.reason_code,
        )
        if verdict.signal and claim == pod_outcome.ENVIRONMENT:
            evidence["finding"] = self._finding(
                "POD_ENVIRONMENT_CLAIM_DISAGREEMENT",
                pid,
                {
                    "intent_id": intent_id,
                    "claimed_stage": claim,
                    "reason_code": verdict.reason_code,
                    "failure_digest": evidence["failure_digest"],
                    "environment_export": export,
                    "host_timing": evidence["host_timing"],
                    "work_seconds": deadline,
                },
            )
        elif verdict.signal:
            evidence["finding"] = self._finding(
                "POD_TIMING_DISAGREEMENT",
                pid,
                {
                    "intent_id": intent_id,
                    "claimed_stage": evidence["claimed_stage"],
                    "failure_digest": evidence["failure_digest"],
                    "host_timing": evidence["host_timing"],
                    "work_seconds": deadline,
                },
            )
        return verdict, evidence

    def _program_deadline(self):
        """The deadline a program actually had: the contract's work seconds,
        or the backend's declared effective deadline when it stops a program
        earlier (the CPU carrier lane's setup margin). Host-observed timing is
        compared with this, so a backend's own stop is never read as a
        forged claim, and every lane attributes timeouts by the same rule."""
        work = podlib.contract_work_seconds(self.scoring)
        declared = getattr(self.pods, "effective_work_seconds", None)
        return work if declared is None else declared(work)

    def _timing(self, handle):
        read = getattr(self.pods, "timing", None)
        if read is None:
            return None
        try:
            return read(handle)
        except (podlib.PodFailure, OSError, ValueError):
            return None

    def _listing(self, handle):
        """The sha256 the pod listed for each file it exported, or None when
        the backend keeps no listing (then no log matches, `pod_logs`)."""
        read = getattr(self.pods, "listing", None)
        if read is None:
            return None
        try:
            listed = read(handle)
        except (podlib.PodFailure, OSError, ValueError):
            return None
        return listed if type(listed) is dict else None

    def _hold_logs(self, pid, intent_id, files, handle):
        logs = {name: files[name] for name in pod_logs.LOG_NAMES if name in files}
        if logs:
            self._logs.setdefault(pid, []).append(
                (intent_id, logs, self._listing(handle))
            )

    def _pod(self, pid, job):
        """Launch, wait, fetch, terminate and settle one pod. Returns the
        outcome and the fetched files. A process death propagates without
        terminating (a restart reconciles); every other failure terminates."""
        private = podlib.private_dir(self._dir(pid) / "private")
        self.ledger.append(
            "pod_launch_requested", intent_id=job.intent_id, proposal=pid
        )
        try:
            handle = self.pods.launch(job, private)
        except podlib.PodFailure as failure:
            if not failure.executed:
                self.ledger.append(
                    "pod_launch_refused",
                    intent_id=job.intent_id,
                    proposal=pid,
                    stage=failure.stage,
                )
                self.ledger.append(
                    "pod_settled",
                    intent_id=job.intent_id,
                    proposal=pid,
                    charge_usd="0",
                    basis="refused_before_any_create",
                )
                return "launch_refused", {}, None
            self.ledger.append(
                "pod_launch_ambiguous", intent_id=job.intent_id, proposal=pid
            )
            handle = self._recover(pid, job.intent_id)
            if handle is None:
                return "launch_refused", {}, None
            if handle == "unknown":
                return "launch_unresolved", {}, None
        self.ledger.append(
            "pod_created",
            intent_id=job.intent_id,
            proposal=pid,
            pod_id=handle.pod_id,
            rate_usd_per_hr=handle.rate_usd_per_hr,
            ship=self.pods.describe(),
        )
        files, outcome, cancelled, timing = {}, "infra", False, None
        try:
            outcome = self.pods.wait(
                handle,
                deadline=self.clock() + job.minutes * 60,
                cancelled=self.cancelled,
            )
            if outcome == "cancelled":
                cancelled = True
            elif outcome in ("done", "failed"):
                files = self.pods.fetch(handle)
                self.ledger.append(
                    "pod_exported",
                    intent_id=job.intent_id,
                    proposal=pid,
                    files={name: digest(body) for name, body in sorted(files.items())},
                )
                self._hold_logs(pid, job.intent_id, files, handle)
            else:
                outcome = "infra"
        except (podlib.PodFailure, OSError, ValueError):
            outcome = "infra"
        timing = self._timing(handle)
        self.ledger.append(
            "pod_finished", intent_id=job.intent_id, proposal=pid, outcome=outcome
        )
        self._terminate(pid, handle)
        if cancelled:
            raise self._cancel()
        return outcome, files, timing

    def _stall(self, record):
        """Consecutive scored proposals, ending with this one, that are not an
        IMPROVEMENT over the baseline; the ladder observation at the limit."""
        outcomes = [
            r.get("against_baseline", {}).get("outcome")
            for r in self.records("proposal")
            if r["status"] == "SCORED"
        ] + [record.get("against_baseline", {}).get("outcome")]
        count = 0
        for outcome in reversed(outcomes):
            if outcome == "IMPROVEMENT":
                break
            count += 1
        stalled = count >= CONSTRUCTOR_STALL_ATTEMPTS
        observation = self.root / "stall-observation.json"
        if stalled and not observation.exists():
            evidence = digest(
                canonical(
                    [r["proposal_id"] for r in self.records("proposal")]
                    + [record["proposal_id"]]
                )
            )
            failure_id = self.ladder.record_failure(
                RoleName.CONSTRUCTOR,
                FailureKind.BUILD_STALLED_AGAINST_BASELINE,
                evidence,
                attempts=count,
            )
            write_once(
                observation,
                canonical(
                    {"failure_id": failure_id, "attempts": count, "evidence": evidence}
                ),
            )
        return {
            "non_improving_attempts": count,
            "limit": CONSTRUCTOR_STALL_ATTEMPTS,
            "stalled": stalled,
        }

    def interrupted(self):
        """Proposals whose run began and never closed: a process died inside
        them. Their reservations stand until reconciled; none is rerun."""
        return sorted(
            path.parent.name
            for path in (self.root / "proposals").glob("*/intent.json")
            if not (path.parent / "result.json").exists()
        )

    def stall_observation(self):
        path = self.root / "stall-observation.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    # -- the session's summary -----------------------------------------------------------------
    def spend(self):
        settled, pending = self.ledger.committed()
        return {"pods_settled_usd": str(settled), "pods_pending_usd": str(pending)}

    def summary(self):
        """Deterministic: digests and outcomes, no wall-clock time. A run with
        a baseline-retry decision also carries it; one without has exactly
        the summary it had before that rule (a recorded session replays
        byte-identically)."""
        summary = {
            "budget": self.budget.record(),
            "proposals": [
                {
                    "proposal_id": r["proposal_id"],
                    "kind": r["kind"],
                    "status": r["status"],
                    "recipe_digest": r.get("recipe_digest"),
                    "outcome": (r.get("against_baseline") or {}).get("outcome"),
                    "result_digest": digest(canonical(r)),
                }
                for r in self.records()
            ],
            "findings": [f["id"] for f in self.findings()],
            "stall_observation": self.stall_observation(),
            "pods": [
                {
                    k: p[k]
                    for k in (
                        "intent_id",
                        "proposal",
                        "launch",
                        "terminated",
                        "settled_usd",
                        "reserved_usd",
                    )
                }
                for p in sorted(
                    self.ledger.pods().values(), key=lambda p: p["intent_id"]
                )
            ],
        }
        decision = self.baseline_retry()
        if decision is not None:
            summary["baseline_retry"] = decision
        stop = self.stopped()
        if stop is not None:
            summary["session_stop"] = stop
        return summary


def pod_attempts(policy):
    """The most pods one proposal may use: its first, plus the policy's one
    cap on infrastructure retries of every kind (`pod_outcome`). The loop is
    bounded by it, whatever a verdict asks for."""
    return 1 + min(policy.infra_retry_cap, pod_outcome.MAX_INFRA_RETRIES)


def retry_intent(intent_id, attempt=1):
    """A retry's own pod intent: distinct, never a resend of an earlier one."""
    suffix = "-r" + str(attempt)
    return intent_id[: 120 - len(suffix)] + suffix


#: The longest pod-claimed stage name recorded as such; anything else is kept
#: only through the raw claim's digest (a pod's own text, hostile at Levels
#: 4-5; VALIDATOR-01 security review, finding 6).
MAX_STAGE = 32


def _object(body):
    """A pod file parsed as a JSON object, or None for anything else."""
    value = _json(body)
    return value if type(value) is dict else None


def _stage(failure):
    """The stage a pod's failure.json names, if it is a short string."""
    stage = (failure or {}).get("stage")
    return stage if type(stage) is str and 0 < len(stage) <= MAX_STAGE else None


def _attempts(attempts):
    if not attempts:
        return {}
    return {
        "attempts": attempts,
        "attribution_policy": attempts[-1]["attribution_policy"],
    }


#: The most of a pod's raw failure claim kept verbatim; a larger one is kept
#: by digest only (it is the pod's own text, and at Levels 4-5 hostile).
MAX_RAW_CLAIM = 1024


def _raw_claim(body):
    """The pod's raw failure claim as recorded evidence: the parsed object
    when it is small JSON, else only its size and digest."""
    if body is None:
        return None
    parsed = _json(body)
    if parsed is not None and len(body) <= MAX_RAW_CLAIM:
        return {"parsed": parsed}
    return {"bytes": len(body), "digest": digest(body)}


def _json(body):
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def usd_to_nano(amount):
    return int((Decimal(amount) * NANO).to_integral_value(rounding=ROUND_FLOOR))


# -- the failure-path check ----------------------------------------------------------------
FAILURE_CHECK_SCHEMA = "carbon.graphite.pod-failure-path-check.v1"
#: A SYNTHETIC program log larger than the per-file cap, so the check sees a
#: log kept bounded (head and tail) with its traceback at the end.
_CHECK_LOG = (
    b"SYNTHETIC training step\n" * 9000
    + podlib.SYNTHETIC_LOGS["program.log"].split(b"\n", 1)[1]
)


class _NoLadder:
    def record_failure(self, *args, **kwargs):
        raise AssertionError("the failure-path check never stalls")


def failure_path_check(
    root,
    *,
    baseline,
    budget,
    scoring,
    scorer=None,
    repository=REPOSITORY,
    level=0,
):
    """Drive the R2 run-4 fixes with scripted pods: no pod, no network, no
    spend; Carbon's admission, rebuild check and frozen-rule scoring are real.

    1. The session's baseline pod ends with no claim (`FAILED_INFRA`, `pod`):
       its logs are kept, and it is retried once on a later pod under the
       registered baseline-retry policy; the retry scores and becomes the
       session's baseline.
    2. A proposal scores against the retried baseline.
    3. A proposal's pod exits non-zero (the run-4 shape: `failure.json` stage
       `program`, `exit 1`) with a log larger than the per-file cap: the log is
       kept bounded, and its traceback's exception class is noted. An agent
       proposal's crash is never retried.
    4. In a second run, the session's baseline exits 1 at stage `program`
       (`CANDIDATE_FAILED` at Level 0): it is retried once (the owner's
       direction, 2026-10-04), the retry scores, and a proposal is compared
       with it.
    5. In a third run (GRAPHITE-POD-GPU-PROBE-01), the baseline's pod and a
       proposal's pod each fail at the GPU probe (`environment`): each is
       relaunched once on a fresh pod and scores; the baseline retry is not
       used; both relaunches and typed attempts are ledgered.
    6. In a fourth run, the baseline's pod fails at the probe twice: the
       session stops `FAILED_INFRA` with no agent charge, the waiting
       proposal is refused without a pod, a later proposal is rejected before
       dispatch, and only two pods were launched.
    Nothing of any log reaches a result record, an event or the ledger.

    `root` must be new or empty. Returns a report with `status` OK or FAILED;
    it never raises for a failed check. The phase-3 dry run runs it."""
    scoring = challenge_scoring.resolve(scoring)
    report = {
        "schema": FAILURE_CHECK_SCHEMA,
        "synthetic": True,
        "network": False,
        "spend_usd": "0",
        "construction_level": level,
    }
    try:
        root = Path(root)
        if root.exists() and any(root.iterdir()):
            raise ValueError("the check's root must be new or empty")
        account = podlib.ScriptedPods(
            steps=[
                podlib.Step(outcome="failed", outputs=podlib.failed_outputs(None)),
                podlib.Step(outputs=podlib.synthetic_outputs(1.0)),
                podlib.Step(outputs=podlib.synthetic_outputs(0.4)),
                podlib.Step(
                    outcome="failed",
                    outputs=podlib.failed_outputs(
                        "program",
                        logs={
                            "program.log": _CHECK_LOG,
                            "phase.log": podlib.SYNTHETIC_LOGS["phase.log"],
                        },
                    ),
                ),
            ]
        )
        events = []

        def experiment(where, pods):
            return Experiment(
                root=root / where,
                run_id="failure-path-check-" + where,
                pods=pods,
                budget=budget,
                baseline=baseline,
                token_committed=lambda: Decimal(0),
                cancelled=lambda: False,
                ladder=_NoLadder(),
                emit=lambda event_id, body: events.append((event_id, body)),
                scorer=scorer,
                scoring=scoring,
                repository=repository,
                clock=lambda: 0.0,
                randomness=lambda n: b"\x03" * n,
                construction_level=level,
            )

        run = experiment("baseline-infra", account)
        why = {"hypothesis": "failure-path check", "expected_effect": "typed"}
        scored = run.run("p-check-scored", "proposal", baseline, why=why)
        failed = run.run("p-check-failed", "proposal", baseline, why=why)
        first, decision = run.record("baseline"), run.baseline_retry() or {}
        retried = run.record(baseline_retry.RETRY_ID) or {}
        logs = {
            pid: pod_logs.read_index(run.root / "proposals" / pid / "pod-logs")
            for pid in ("baseline", "p-check-failed")
        }
        program = [
            entry
            for index in logs["p-check-failed"]
            for entry in index["logs"]
            if entry["name"] == "program.log"
        ]
        failures = []
        if first["status"] != "FAILED_INFRA" or not decision.get("retry"):
            failures.append("the_failed_baseline_was_not_retried")
        if retried.get("status") != "SCORED" or run.baseline_id() != retried.get(
            "proposal_id"
        ):
            failures.append("the_retried_baseline_is_not_the_sessions")
        against = scored.get("against_baseline") or {}
        if scored["status"] != "SCORED" or against.get("outcome") in (
            None,
            "NO_BASELINE",
        ):
            failures.append("a_proposal_was_not_compared_with_the_retry")
        if failed["status"] == "SCORED" or len(program) != 1:
            failures.append("a_failed_pods_program_log_was_not_indexed")
        elif not (
            program[0]["status"] == pod_logs.KEPT
            and program[0]["truncated_bytes"] > 0
            and program[0]["kept_bytes"]
            <= pod_logs.LOG_HEAD_BYTES + pod_logs.LOG_TAIL_BYTES
        ):
            failures.append("a_failed_pods_log_was_not_kept_bounded")
        if not logs["baseline"]:
            failures.append("the_failed_baselines_logs_were_not_kept")
        if len(account.launched) != 4 or any(
            intent.startswith(run.run_id + "-p-check-failed-")
            for intent, _job in account.launched
        ):
            failures.append("an_agent_proposals_crash_was_retried")
        # 4. The baseline's own program crash, in a second run.
        crashing = podlib.ScriptedPods(
            steps=[
                podlib.Step(outcome="failed", outputs=podlib.failed_outputs("program")),
                podlib.Step(outputs=podlib.synthetic_outputs(1.0)),
                podlib.Step(outputs=podlib.synthetic_outputs(0.4)),
            ]
        )
        crash_run = experiment("baseline-crash", crashing)
        crash_scored = crash_run.run("p-check-scored", "proposal", baseline, why=why)
        crash_first = crash_run.record("baseline")
        crash_decision = crash_run.baseline_retry() or {}
        crash_retried = crash_run.record(baseline_retry.RETRY_ID) or {}
        crash_against = crash_scored.get("against_baseline") or {}
        if not crash_decision.get("retry") or crash_retried.get("status") != "SCORED":
            failures.append("the_crashed_baseline_was_not_retried_to_a_score")
        if crash_run.baseline_id() != baseline_retry.RETRY_ID or crash_against.get(
            "outcome"
        ) in (None, "NO_BASELINE"):
            failures.append("a_proposal_was_not_compared_with_the_crash_retry")
        if crashing.alive or len(crashing.launched) != 3:
            failures.append("the_crash_retry_used_other_than_one_pod")
        for pid in ("p-check-scored", baseline_retry.RETRY_ID):
            if (run.root / "proposals" / pid / "pod-logs").exists():
                failures.append("a_scored_pods_logs_were_kept")
        # 5. GPU probe failures (GRAPHITE-POD-GPU-PROBE-01): the baseline's
        # and a proposal's pods fail at the probe, before any candidate code;
        # each is relaunched once and scores. The baseline retry is not used.
        environment = podlib.environment_outputs()
        relaunching = podlib.ScriptedPods(
            steps=[
                podlib.Step(outcome="failed", outputs=environment),
                podlib.Step(outputs=podlib.synthetic_outputs(1.0)),
                podlib.Step(outcome="failed", outputs=environment),
                podlib.Step(outputs=podlib.synthetic_outputs(0.4)),
            ]
        )
        env_run = experiment("environment-relaunch", relaunching)
        env_scored = env_run.run("p-check-environment", "proposal", baseline, why=why)
        env_base = env_run.record("baseline")
        env_against = env_scored.get("against_baseline") or {}
        if (
            env_base["status"] != "SCORED"
            or [a["reason_code"] for a in env_base.get("attempts", [])]
            != ["pod_environment"]
            or env_scored["status"] != "SCORED"
            or [a["reason_code"] for a in env_scored.get("attempts", [])]
            != ["pod_environment"]
        ):
            failures.append("an_environment_failure_was_not_relaunched_to_a_score")
        if env_against.get("outcome") in (None, "NO_BASELINE"):
            failures.append("a_relaunched_proposal_was_not_compared")
        if env_run.baseline_retry() is not None or env_run.stopped() is not None:
            failures.append("a_relaunch_also_used_the_baseline_retry_or_stopped")
        if len(relaunching.launched) != 4 or relaunching.alive:
            failures.append("the_relaunches_used_other_than_one_pod_each")
        relaunch_rows = [
            r
            for r in env_run.ledger.rows()
            if r["event"] in ("pod_environment_relaunch", "pod_attempt_typed")
        ]
        if len(relaunch_rows) != 4:
            failures.append("a_relaunch_or_its_typed_attempt_was_not_ledgered")
        # 6. The baseline's pod fails at the probe twice: the session stops as
        # FAILED_INFRA, with no agent charge, and nothing else is launched.
        twice = podlib.ScriptedPods(
            steps=[
                podlib.Step(outcome="failed", outputs=environment),
                podlib.Step(outcome="failed", outputs=environment),
                podlib.Step(outputs=podlib.synthetic_outputs(0.4)),
            ]
        )
        stop_run = experiment("environment-twice", twice)
        stop_refused = stop_run.run("p-check-stopped", "proposal", baseline, why=why)
        stop_base = stop_run.record("baseline")
        stop = stop_run.stopped() or {}
        late = stop_run.propose_tool(
            {
                "strategy_json": json.dumps(baseline),
                "hypothesis": "after the stop",
                "expected_effect": "refused",
            },
            "failure-path-check-after-stop",
        )
        if (stop_base["status"], stop_base["reason_code"]) != (
            "FAILED_INFRA",
            "pod_environment_repeated",
        ):
            failures.append("a_repeated_environment_failure_was_not_failed_infra")
        if (stop.get("status"), stop.get("candidate_charged")) != (
            "FAILED_INFRA",
            False,
        ):
            failures.append("a_repeated_environment_failure_did_not_stop_the_session")
        if (
            stop_refused["status"] != SESSION_STOPPED
            or late.get("status") != "REJECTED_BEFORE_DISPATCH"
            or late.get("dispatched") is not False
        ):
            failures.append("a_proposal_ran_after_the_session_stopped")
        if stop_run.baseline_retry() is not None:
            failures.append("the_stopped_baseline_was_retried")
        if len(twice.launched) != 2 or twice.alive:
            failures.append("the_stop_launched_other_than_two_pods")
        for marker in (b"SYNTHETIC scripted failure", b"SYNTHETIC Unable"):
            leaked = [
                path.name
                for path in root.glob("*/proposals/*/result.json")
                if marker in path.read_bytes()
            ]
            if (
                leaked
                or any(
                    marker in path.read_bytes()
                    for path in root.glob("*/pod-ledger.jsonl")
                )
                or any(marker in canonical(body) for _event, body in events)
            ):
                failures.append("log_text_left_the_pod_logs")
        if account.alive:
            failures.append("a_pod_left_alive")
        report.update(
            {
                "status": "FAILED" if failures else "OK",
                "failures": sorted(set(failures)),
                "pods_launched": len(account.launched),
                "baseline": {
                    "status": first["status"],
                    "reason_code": first.get("reason_code"),
                },
                "baseline_retry": {
                    "retry": decision.get("retry"),
                    "reason_code": decision.get("reason_code"),
                    "policy": decision.get("policy"),
                    "retry_status": retried.get("status"),
                },
                "compared": {
                    "outcome": against.get("outcome"),
                    "promotable": against.get("promotable"),
                    "baseline": (scored.get("baseline") or {}).get("proposal_id"),
                },
                "baseline_crash_retry": {
                    "baseline": {
                        "status": crash_first["status"],
                        "reason_code": crash_first.get("reason_code"),
                    },
                    "retry": crash_decision.get("retry"),
                    "reason_code": crash_decision.get("reason_code"),
                    "retry_status": crash_retried.get("status"),
                    "compared": {
                        "outcome": crash_against.get("outcome"),
                        "promotable": crash_against.get("promotable"),
                        "baseline": (crash_scored.get("baseline") or {}).get(
                            "proposal_id"
                        ),
                    },
                    "pods_launched": len(crashing.launched),
                },
                "environment_relaunch": {
                    "baseline": {
                        "status": env_base["status"],
                        "attempts": [
                            a["reason_code"] for a in env_base.get("attempts", [])
                        ],
                    },
                    "proposal": {
                        "status": env_scored["status"],
                        "attempts": [
                            a["reason_code"] for a in env_scored.get("attempts", [])
                        ],
                        "compared": env_against.get("outcome"),
                    },
                    "baseline_retry": env_run.baseline_retry(),
                    "pods_launched": len(relaunching.launched),
                    "policy": env_base.get("attribution_policy"),
                },
                "environment_twice": {
                    "baseline": {
                        "status": stop_base["status"],
                        "reason_code": stop_base["reason_code"],
                    },
                    "session_stop": stop,
                    "next_proposal": {
                        "status": stop_refused["status"],
                        "reason_code": stop_refused.get("reason_code"),
                    },
                    "proposal_after_stop": {
                        "status": late.get("status"),
                        "reason_code": late.get("reason_code"),
                    },
                    "pods_launched": len(twice.launched),
                },
                "failed_pod": {
                    "status": failed["status"],
                    "reason_code": failed.get("reason_code"),
                    "logs": [
                        {
                            k: entry.get(k)
                            for k in (
                                "name",
                                "status",
                                "bytes",
                                "kept_bytes",
                                "truncated_bytes",
                                "exception_class",
                            )
                        }
                        for index in logs["p-check-failed"]
                        for entry in index["logs"]
                    ],
                },
                "caps": pod_logs.caps(),
            }
        )
    except Exception as error:  # noqa: BLE001 -- the check reports, typed
        report.update(
            {
                "status": "FAILED",
                "failures": ["exception"],
                "error_type": f"{type(error).__module__}.{type(error).__name__}",
                "error": str(error)[:500],
            }
        )
    return report
