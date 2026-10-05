"""Carbon's experiment runner for Graphite phase 3 (Constructor, Level 0).

The Constructor proposes; Carbon runs, scores and rebuilds (plan §5; invariants
7.9 and 7.10). One proposal goes through these steps, each journalled
write-once under the run's private root:

1. **Reconstruction gate** (OWNER-GRAPHITE-02's reconstruction rule). The
   proposal must be a declarative battery `TrainingStrategy` that compiles
   under the battery construction contract, and the live contract must be the
   one its newest expansion record pins (`carbon/reconstruction/expansions`).
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
4. **Frozen-rule score.** Carbon scores the fetched predictions on its own
   host against the public PRACTICE references with the battery exam's gates,
   frozen calibration and score (`carbon.battery.practice.score_practice`), and
   compares each proposal with the session's baseline by the frozen paired
   comparison (`carbon.battery.exam.final_compare`, rule v2's comparison and
   equivalence margin). This is development feedback on adaptively seen
   public cases, never an exam result.
5. **Stall rule.** After `roles.CONSTRUCTOR_STALL_ATTEMPTS` (5, OWNER-GRAPHITE-02)
   scored proposals in a row that are not an IMPROVEMENT over the baseline,
   Carbon records one `BUILD_STALLED_AGAINST_BASELINE` observation on the
   ladder for the run.

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

from . import pod_outcome
from . import pods as podlib
from .roles import (
    CONSTRUCTOR_STALL_ATTEMPTS,
    FailureKind,
    RoleName,
)

REPOSITORY = Path(__file__).resolve().parents[3]
PROPOSAL_SCHEMA = "carbon.graphite.phase3.proposal-result.v1"
FEEDBACK_SCHEMA = "carbon.graphite.phase3.feedback.v1"
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


def phase3_budget(grant, scoring=None):
    economics = podlib.prices()
    minutes = podlib.proposal_minutes(scoring)
    budget = Phase3Budget(
        run_cap_usd=grant.worst_case_run_cost,
        hourly_usd=economics["hourly_usd"],
        pod_minutes=minutes,
        max_pods=SESSION_POD_MINUTES // minutes,
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
    (`development_variants.compile_development`); Level 0 is unchanged."""
    resolved = challenge_scoring.resolve(scoring)
    if type(strategy) is not dict:
        raise Unrebuildable("strategy_not_an_object")
    if strategy.get("challenge_id") != resolved.challenge_id:
        raise Unrebuildable(resolved.wrong_challenge_code)
    if variant is not None:
        from carbon.reconstruction import development_variants

        return development_variants.admit(resolved, strategy, seed, root, variant)
    contract = recorded_contract() if scoring is None else recorded_contract(scoring)
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
        development_variant=None,
        on_finding=None,
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
        # The registered attribution policy (`pod_outcome`): the registry's
        # current version unless one is named.
        self.attribution = (
            pod_outcome.load_policy()
            if attribution_policy is None
            else pod_outcome.load_policy(attribution_policy)
        )

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
        attempts = []
        for attempt in range(self.attribution.retries + 1):
            if attempt:
                # A retry after a worker timeout, on a fresh pod under the
                # same declared budget, as many as the registered attribution
                # policy allows (OWNER-GRAPHITE-TEST-WAVE-02 §3: one). It is
                # charged to the run like any pod.
                try:
                    reservation = self._admit_pod()
                except BudgetRefused as refused:
                    return self._close(
                        pid,
                        {
                            **common,
                            "status": "FAILED_INFRA",
                            "reason_code": "worker_timeout_retry_refused:"
                            + refused.code,
                            **_attempts(attempts),
                            "scored": False,
                            "pods_left": self.pods_left(),
                        },
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
            failure = _json(files.get("failure.json"))
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
                pid, job_intent, attempt, files, failure, timing
            )
            attempts.append(evidence)
            if verdict.retry:
                continue
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
        fit = _json(files.get("fit.json")) or {}
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
            baseline_rows = self.rows("baseline")
            baseline = self.record("baseline")
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
                record["baseline"] = {
                    "eligible": baseline["frozen_rule"]["eligible"],
                    "score": baseline["frozen_rule"]["score"],
                }
        if kind == "proposal":
            record["stall"] = self._stall(record)
        return self._close(pid, record)

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

    def _type_unfinished(self, pid, intent_id, attempt, files, failure, timing):
        """Type a pod run that ended without finishing under the registered
        attribution policy (`pod_outcome.classify`): host timing and lifecycle
        decide, and the construction level decides whose claims the pod's
        files carry. The evidence keeps the raw claim, the host's timing and
        the policy, so the policy can be judged from it."""
        image = (self.pods.describe() or {}).get("image")
        report = _json(files.get("supervisor.json"))
        verdict = pod_outcome.classify(
            claim=(failure or {}).get("stage"),
            admissible=pod_outcome.admissible_stage(report, image),
            timing=timing,
            work_seconds=podlib.contract_work_seconds(self.scoring),
            attempt=attempt,
            level=self.construction_level,
            policy=self.attribution,
        )
        evidence = {
            "intent_id": intent_id,
            "attempt": attempt,
            "construction_level": self.construction_level,
            "attribution_policy": self.attribution.record(),
            "status": verdict.status,
            "reason_code": verdict.reason_code,
            "claimed_stage": (failure or {}).get("stage"),
            "claim": _raw_claim(files.get("failure.json")),
            "failure_digest": (
                digest(files["failure.json"]) if "failure.json" in files else None
            ),
            "host_timing": None if timing is None else timing.record(),
        }
        self.ledger.append(
            "pod_attempt_typed",
            intent_id=intent_id,
            proposal=pid,
            status=verdict.status,
            reason_code=verdict.reason_code,
        )
        if verdict.signal:
            evidence["finding"] = self._finding(
                "POD_TIMING_DISAGREEMENT",
                pid,
                {
                    "intent_id": intent_id,
                    "claimed_stage": evidence["claimed_stage"],
                    "failure_digest": evidence["failure_digest"],
                    "host_timing": evidence["host_timing"],
                    "work_seconds": podlib.contract_work_seconds(self.scoring),
                },
            )
        return verdict, evidence

    def _timing(self, handle):
        read = getattr(self.pods, "timing", None)
        if read is None:
            return None
        try:
            return read(handle)
        except (podlib.PodFailure, OSError, ValueError):
            return None

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
        """Deterministic: digests and outcomes, no wall-clock time."""
        return {
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


def retry_intent(intent_id, attempt=1):
    """A retry's own pod intent: distinct, never a resend of an earlier one."""
    suffix = "-r" + str(attempt)
    return intent_id[: 120 - len(suffix)] + suffix


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
