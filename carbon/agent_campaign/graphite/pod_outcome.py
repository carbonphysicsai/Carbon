"""How a pod run that did not finish is typed (OWNER-GRAPHITE-TEST-WAVE-02 §3).

Attribution is a **versioned, registered policy**, not fixed logic. Each
policy is a data document in `attribution_policies/`. The registry
(`attribution_policies/registry.json`) pins every version's digest and names
the current one. Swapping the policy is a registered change: a new document
and a registry entry, never an edit to this module or to scoring code. Every
typed outcome records the policy version and digest, the raw pod claim and
the host's timing, so a policy can be judged from evidence, for example by the
Attacker's resource and accounting families (selective crash and retry, forged
classification).

What a policy may not change (checked when it loads; it fails closed):
- an unfinished run is never `SCORED`;
- evidence-only claims, unconfirmed timeouts, a timeout claim the host's timing
  contradicts, a first (retried) timeout and a missing claim are all
  `FAILED_INFRA`. The candidate is never blamed on ambiguous evidence.

The order of authority the policy works within:
1. **Authority: what Carbon's host observes.** The pod lifecycle (launch, the
   pod's own deadline, loss, cancellation) and the host's own clock readings
   of the pod's phase (`HostTiming`).
2. **Admissible evidence.** Two sources qualify:
   - a supervisor report, from an image that a host-side record
     (`SEPARATED_IMAGES`) says runs the supervisor apart from the program
     (the pod's own claim never makes it so, and no image has such a record
     yet);
   - the pod's own stage claim at a level where the policy says only Carbon's
     code writes it (`trusted_writer_levels`; v1: Levels 0-3, where Carbon's
     trainer runs a declarative recipe).
3. **Evidence only.** Anything else in the pod's shared uid or filesystem
   (`failure.json`, `/status` stages, exit codes), including at an unknown
   level. It is recorded and never blames the candidate.

Timeouts confirm on the host's own readings: the phase's lower bound is at
least the declared worker seconds, and a contradiction is an upper bound below
them. That span includes Carbon's own compile and pin check, which run before
the program.

The construction level comes from the session's recorded permission profile,
never from a submission.

**The environment stage (`pod-attribution-v2`, GRAPHITE-POD-GPU-PROBE-01).**
Before any candidate code, Carbon's pod phase runs a GPU probe in the
program's own interpreter and environment (`pod_phase.probe_environment`)
and writes its result into the supervisor report (`SUPERVISOR_SCHEMA`). A
failed probe claims stage `environment` and the program never runs. Under a
v2 policy, in this order:
1. host timing first: a pod the host saw run its whole worker allowance did
   not fail before the program, so its `environment` claim is contradicted
   (OTHER_SIGNAL, `FAILED_INFRA`, no retry);
2. admissible only where Carbon writes the claim (trusted levels, or a
   separated image's supervisor report); otherwise evidence only;
3. consistent only when the export shows the program never started and the
   probe record says it failed before the program (`environment_export`);
   otherwise OTHER_SIGNAL, `FAILED_INFRA`, never a free retry;
4. one relaunch on a fresh pod, within one cap on every infrastructure retry
   of a proposal (timeouts and relaunches together; the counter never resets
   across them); a second environment failure stops the session
   (`Verdict.stop`), `FAILED_INFRA`, no agent charge.
A v1 policy reads `environment` as no claim, exactly as it always did.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: Pinned images whose supervisor runs apart from the candidate (separate uid
#: or unwritable report path), each by a verification record. None yet: the
#: EV4 study image runs the supervisor and the program as one non-root user.
SEPARATED_IMAGES = {}

FAILED_INFRA = "FAILED_INFRA"
CANDIDATE_FAILED = "CANDIDATE_FAILED"
CANDIDATE_RESOURCE_EXCEEDED = "CANDIDATE_RESOURCE_EXCEEDED"
#: Statuses a policy may assign to an unfinished pod run. Never `SCORED`.
STATUSES = frozenset({FAILED_INFRA, CANDIDATE_FAILED, CANDIDATE_RESOURCE_EXCEEDED})
ENVIRONMENT = "environment"
#: The stages a v1 policy names.
V1_STAGES = ("timeout", "program", "compile")
#: Every stage any registered policy may name (a supervisor report's stage is
#: read against it; each policy then reads only its own `stages`).
STAGES = (*V1_STAGES, ENVIRONMENT)

POLICY_DIR = Path(__file__).with_name("attribution_policies")
POLICY_SCHEMA = "carbon.graphite.pod-attribution-policy.v1"
POLICY_SCHEMA_V2 = "carbon.graphite.pod-attribution-policy.v2"
REGISTRY_SCHEMA = "carbon.graphite.pod-attribution-registry.v1"
#: The report Carbon's pod phase (supervisor code) writes: the probe's result
#: and the stage it failed at, if any (`pod_phase._report`). Admissible only
#: from an image with a SEPARATED_IMAGES record; otherwise evidence.
SUPERVISOR_SCHEMA = "carbon.graphite.pod-supervisor-report.v1"
_KEYS = {
    "schema",
    "version",
    "authority",
    "status",
    "trusted_writer_levels",
    "timeout",
    "admissible",
    "evidence_only",
    "no_claim",
    "notes",
}
_TIMEOUT_KEYS = {
    "retries",
    "confirm",
    "contradict",
    "repeated_confirmed",
    "retried",
    "unconfirmed",
    "contradicted",
}
#: The only host-timing tests this module implements; a policy naming another
#: is refused rather than reinterpreted.
CONFIRM = "host_phase_min_at_least_work_seconds"
CONTRADICT = "host_phase_max_below_work_seconds"
#: A v2 document's further fields, closed sets like v1's.
_KEYS_V2 = _KEYS | {"infra_retries", "environment"}
_INFRA_KEYS = {"max", "cap_reached"}
_ENVIRONMENT_KEYS = {
    "relaunches",
    "confirm",
    "contradict",
    "inconsistent",
    "contradicted",
    "repeated",
    "on_repeated",
}
#: The environment tests this module implements (`environment_consistent`;
#: `host_ran_full_allowance`), and what a repeated environment failure does.
ENV_CONFIRM = "program_never_started_and_probe_failed_before_program"
ENV_CONTRADICT = CONFIRM
STOP_SESSION = "stop_session"
#: The most infrastructure retries (timeout retries and environment relaunches
#: together) any policy may give one proposal: a relaunch never loops.
MAX_INFRA_RETRIES = 1
#: Exported files that show the pod went past the probe (the program started
#: or Carbon built the recipe). An honest environment failure exports none.
PAST_PROBE_FILES = ("program.log", "predictions.json", "built.json", "DONE.json")


class PolicyRefused(ValueError):
    """An attribution policy that is unregistered, altered or unsafe."""


@dataclass(frozen=True)
class HostTiming:
    """Host clock readings of one pod's phase, taken by Carbon's own polls.

    - `before_running`: the last poll before the phase was seen running;
    - `first_running`, `last_running`: the first and last polls that saw it
      running;
    - `ended`: the first poll that saw it end.

    Any of them may be None when the host did not observe it.
    """

    before_running: float | None = None
    first_running: float | None = None
    last_running: float | None = None
    ended: float | None = None

    def phase_min(self):
        """A lower bound on how long the phase ran: it started no later than
        the first running poll and ended after the last one."""
        if self.first_running is None or self.last_running is None:
            return None
        return max(0.0, self.last_running - self.first_running)

    def phase_max(self):
        """An upper bound: it started after the last poll before running and
        ended no later than the first poll that saw it end."""
        if self.before_running is None or self.ended is None:
            return None
        return max(0.0, self.ended - self.before_running)

    def record(self):
        return {
            "before_running": self.before_running,
            "first_running": self.first_running,
            "last_running": self.last_running,
            "ended": self.ended,
            "phase_min_s": self.phase_min(),
            "phase_max_s": self.phase_max(),
        }


@dataclass(frozen=True)
class Verdict:
    status: str
    reason_code: str
    #: Whether this attempt asks for a retry.
    retry: bool = False
    #: Whether the host timing contradicts the pod's claim (an OTHER_SIGNAL).
    signal: bool = False
    #: Whether the retry is an environment relaunch (else a timeout retry).
    relaunch: bool = False
    #: Whether this outcome stops the session (a repeated environment
    #: failure): FAILED_INFRA, no agent charge.
    stop: bool = False


def _digest(document):
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _outcome(value, where):
    if (
        type(value) is not list
        or len(value) != 2
        or value[0] not in STATUSES
        or type(value[1]) is not str
        or not value[1]
    ):
        raise PolicyRefused(where + " is [status, reason_code]")
    return value[0], value[1]


@dataclass(frozen=True)
class AttributionPolicy:
    """One registered attribution policy, as loaded and checked."""

    version: str
    digest: str
    trusted_writer_levels: frozenset
    retries: int
    timeout: dict
    admissible: dict
    evidence_only: dict
    no_claim: tuple
    #: The stages this policy reads; any other claim is no claim.
    stages: tuple = V1_STAGES
    #: Infrastructure retries one proposal may get, all kinds together (v1:
    #: its timeout retries, the only kind it has).
    infra_retry_cap: int = 0
    #: A v2 policy's environment rules, None under v1.
    environment: dict | None = None
    #: A v2 policy's outcome when the cap leaves no retry.
    cap_reached: tuple | None = None

    @staticmethod
    def from_document(document, digest):
        if type(document) is not dict:
            raise PolicyRefused("policy fields")
        schema = document.get("schema")
        if schema not in (POLICY_SCHEMA, POLICY_SCHEMA_V2):
            raise PolicyRefused("policy schema")
        v2 = schema == POLICY_SCHEMA_V2
        if set(document) != (_KEYS_V2 if v2 else _KEYS):
            raise PolicyRefused("policy fields")
        stages = STAGES if v2 else V1_STAGES
        levels = document["trusted_writer_levels"]
        if type(levels) is not list or not all(
            type(level) is int and level >= 0 for level in levels
        ):
            raise PolicyRefused("trusted_writer_levels are non-negative integers")
        timeout = document["timeout"]
        if type(timeout) is not dict or set(timeout) != _TIMEOUT_KEYS:
            raise PolicyRefused("timeout fields")
        if (timeout["confirm"], timeout["contradict"]) != (CONFIRM, CONTRADICT):
            raise PolicyRefused("timeout tests this module does not implement")
        retries = timeout["retries"]
        if type(retries) is not int or retries < 0:
            raise PolicyRefused("timeout retries is a non-negative integer")
        outcomes = {
            name: _outcome(timeout[name], "timeout." + name)
            for name in ("repeated_confirmed", "retried", "unconfirmed", "contradicted")
        }
        admissible, evidence_only = {}, {}
        claimed = set(stages) - {"timeout"}
        for table, target, name in (
            (document["admissible"], admissible, "admissible"),
            (document["evidence_only"], evidence_only, "evidence_only"),
        ):
            if type(table) is not dict or set(table) != claimed:
                raise PolicyRefused(name + " covers " + ", ".join(sorted(claimed)))
            for stage, value in table.items():
                target[stage] = _outcome(value, f"{name}.{stage}")
        no_claim = _outcome(document["no_claim"], "no_claim")
        # What no policy may change: ambiguity is never the candidate's.
        never_blamed = [
            outcomes["retried"],
            outcomes["unconfirmed"],
            outcomes["contradicted"],
            no_claim,
            *evidence_only.values(),
        ]
        environment, cap_reached, cap = None, None, retries
        if v2:
            environment, cap_reached, cap = _v2_rules(document, retries)
            # An environment failure is never the candidate's, whoever wrote
            # the claim and whatever the export shows.
            never_blamed += [
                admissible[ENVIRONMENT],
                cap_reached,
                environment["inconsistent"],
                environment["contradicted"],
                environment["repeated"],
            ]
        if not never_the_candidates(never_blamed):
            raise PolicyRefused("ambiguous or evidence-only outcomes are FAILED_INFRA")
        return AttributionPolicy(
            version=document["version"],
            digest=digest,
            trusted_writer_levels=frozenset(levels),
            retries=retries,
            timeout=outcomes,
            admissible=admissible,
            evidence_only=evidence_only,
            no_claim=no_claim,
            stages=stages,
            infra_retry_cap=cap,
            environment=environment,
            cap_reached=cap_reached,
        )

    def record(self):
        return {"version": self.version, "digest": self.digest}


def never_the_candidates(outcomes):
    """Every `(status, reason_code)` in `outcomes` is FAILED_INFRA: what no
    policy may type as the candidate's (ambiguity, evidence-only claims and,
    under v2, every environment outcome)."""
    return all(status == FAILED_INFRA for status, _ in outcomes)


def _small(value, where, most):
    if type(value) is not int or not 0 <= value <= most:
        raise PolicyRefused(f"{where} is an integer from 0 to {most}")
    return value


def _v2_rules(document, timeout_retries):
    """A v2 document's retry cap and environment rules, checked: one cap on
    every infrastructure retry of a proposal (never more than
    MAX_INFRA_RETRIES), the tests this module implements and a repeated
    environment failure that stops the session."""
    infra = document["infra_retries"]
    if type(infra) is not dict or set(infra) != _INFRA_KEYS:
        raise PolicyRefused("infra_retries fields")
    cap = _small(infra["max"], "infra_retries.max", MAX_INFRA_RETRIES)
    if timeout_retries > cap:
        raise PolicyRefused("timeout retries exceed the infrastructure retry cap")
    cap_reached = _outcome(infra["cap_reached"], "infra_retries.cap_reached")
    environment = document["environment"]
    if type(environment) is not dict or set(environment) != _ENVIRONMENT_KEYS:
        raise PolicyRefused("environment fields")
    relaunches = _small(environment["relaunches"], "environment.relaunches", cap)
    if (environment["confirm"], environment["contradict"]) != (
        ENV_CONFIRM,
        ENV_CONTRADICT,
    ):
        raise PolicyRefused("environment tests this module does not implement")
    if environment["on_repeated"] != STOP_SESSION:
        raise PolicyRefused("a repeated environment failure stops the session")
    rules = {
        name: _outcome(environment[name], "environment." + name)
        for name in ("inconsistent", "contradicted", "repeated")
    }
    rules["relaunches"] = relaunches
    return rules, cap_reached, cap


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise PolicyRefused("attribution policy registry unreadable") from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("versions")) is not dict
        or registry.get("current") not in registry["versions"]
    ):
        raise PolicyRefused("attribution policy registry malformed")
    return registry


def registered_policies(directory=None):
    """Every registered policy version, in registry order."""
    return list(_registry(POLICY_DIR if directory is None else directory)["versions"])


def load_policy(version=None, directory=None):
    """The registered policy `version` (the registry's current one when None).
    Refused unless its document's digest is the one the registry pins."""
    directory = POLICY_DIR if directory is None else directory
    registry = _registry(directory)
    version = registry["current"] if version is None else version
    pinned = registry["versions"].get(version)
    if pinned is None:
        raise PolicyRefused("attribution policy not registered: " + str(version))
    try:
        document = json.loads((Path(directory) / f"{version}.json").read_text())
    except (OSError, ValueError):
        raise PolicyRefused("attribution policy unreadable: " + version) from None
    digest = _digest(document)
    if digest != pinned:
        raise PolicyRefused("attribution policy altered: " + version)
    if document.get("version") != version:
        raise PolicyRefused("attribution policy names another version")
    return AttributionPolicy.from_document(document, digest)


def timeout_check(timing, work_seconds):
    """`"confirmed"`, `"contradicted"` or `"unconfirmed"` for a claimed timeout."""
    if timing is None:
        return "unconfirmed"
    upper, lower = timing.phase_max(), timing.phase_min()
    if upper is not None and upper < work_seconds:
        return "contradicted"
    if lower is not None and lower >= work_seconds:
        return "confirmed"
    return "unconfirmed"


def trusted_writer(level, policy):
    """Whether, under `policy`, only Carbon's own code writes the pod's claims
    at `level`. An unknown or malformed level is never trusted."""
    return type(level) is int and level in policy.trusted_writer_levels


def classify(
    *,
    claim,
    admissible,
    timing,
    work_seconds,
    attempt,
    level,
    policy,
    export=None,
    earlier=(),
):
    """Type one ended-but-not-done pod run under `policy`. Pure.

    `claim` is the failure stage the pod reported; `admissible` is a stage
    from a separated supervisor report, or None; `attempt` counts this
    proposal's pod attempts from 0, so it is also the number of
    infrastructure retries already used; `level` is the session's recorded
    construction level, or None. A v2 policy also reads `export`, what the
    pod's export shows (`environment_export`), and `earlier`, the reason codes
    of this proposal's earlier attempts in order.
    """
    if type(policy) is not AttributionPolicy:
        raise TypeError("a registered AttributionPolicy is required")
    if admissible not in policy.stages:
        admissible = None
    if admissible is None and trusted_writer(level, policy):
        admissible = claim if claim in policy.stages else None
    stage = admissible if admissible is not None else claim
    if stage == "timeout":
        check = timeout_check(timing, work_seconds)
        if check == "contradicted":
            return Verdict(*policy.timeout["contradicted"], signal=True)
        if policy.environment is None:
            # v1, unchanged: its only retries are timeout retries.
            if attempt < policy.retries:
                return Verdict(*policy.timeout["retried"], retry=True)
        else:
            prior = tuple(earlier).count(policy.timeout["retried"][1])
            if prior < policy.retries:
                # A first timeout is never the candidate's: retried while the
                # proposal's one infrastructure retry is left, else typed
                # infrastructure with no retry.
                if retry_left(attempt, policy):
                    return Verdict(*policy.timeout["retried"], retry=True)
                return Verdict(*policy.cap_reached)
        if check == "confirmed":
            return Verdict(*policy.timeout["repeated_confirmed"])
        return Verdict(*policy.timeout["unconfirmed"])
    if stage == ENVIRONMENT and policy.environment is not None:
        return _environment(
            admissible, timing, work_seconds, attempt, policy, export, earlier
        )
    if stage in ("program", "compile"):
        table = policy.admissible if admissible == stage else policy.evidence_only
        return Verdict(*table[stage])
    return Verdict(*policy.no_claim)


def _environment(admissible, timing, work_seconds, attempt, policy, export, earlier):
    """An `environment` claim under a v2 policy, in its order of authority."""
    rules = policy.environment
    if host_ran_full_allowance(timing, work_seconds):
        # The host saw the phase run the whole worker allowance: the program
        # ran, so it did not fail before the program.
        return Verdict(*rules["contradicted"], signal=True)
    if admissible != ENVIRONMENT:
        # Written where participant code runs: evidence only.
        return Verdict(*policy.evidence_only[ENVIRONMENT])
    if not environment_consistent(export):
        return Verdict(*rules["inconsistent"], signal=True)
    relaunch = policy.admissible[ENVIRONMENT]
    if relaunch[1] in tuple(earlier):
        return Verdict(*rules["repeated"], stop=True)
    if retry_left(attempt, policy) and relaunch_left(earlier, policy):
        return Verdict(*relaunch, retry=True, relaunch=True)
    return Verdict(*policy.cap_reached)


def retry_left(attempt, policy):
    """Whether the proposal has an infrastructure retry left: one counter for
    timeout retries and environment relaunches together."""
    return attempt < policy.infra_retry_cap


def relaunch_left(earlier, policy):
    """Whether the policy's environment relaunches are not yet used."""
    used = tuple(earlier).count(policy.admissible[ENVIRONMENT][1])
    return used < policy.environment["relaunches"]


def host_ran_full_allowance(timing, work_seconds):
    """The host's own readings show the phase running at least the worker
    allowance (`timeout_check`'s confirmation)."""
    return timeout_check(timing, work_seconds) == "confirmed"


def environment_export(names, report):
    """What a pod's export shows about an `environment` claim, from the names
    of the files it exported and its supervisor report (parsed, or None):

    - `program_started`: a file only a run past the probe writes
      (`PAST_PROBE_FILES`), or a report that does not say the program never
      started;
    - `probe_failed_before_program`: the report is the supervisor schema,
      names stage `environment`, and its probe record failed before the
      program.
    """
    names = frozenset(names)
    report = report if type(report) is dict else None
    probe = None if report is None else report.get("probe")
    return {
        "program_started": bool(names & set(PAST_PROBE_FILES))
        or report is None
        or report.get("program_started") is not False,
        "probe_failed_before_program": report is not None
        and report.get("schema") == SUPERVISOR_SCHEMA
        and report.get("stage") == ENVIRONMENT
        and type(probe) is dict
        and probe.get("ok") is False
        and probe.get("before_program") is True,
    }


def environment_consistent(export):
    """An `environment` claim is accepted only when the export shows the
    program never started and the probe failed before it."""
    return (
        type(export) is dict
        and export.get("program_started") is False
        and export.get("probe_failed_before_program") is True
    )


def admissible_stage(report, image):
    """The stage of a supervisor report, only for an image with a separation
    record; otherwise None (the report stays evidence)."""
    if image not in SEPARATED_IMAGES or type(report) is not dict:
        return None
    stage = report.get("stage")
    return stage if stage in STAGES else None


__all__ = [
    "CANDIDATE_FAILED",
    "CANDIDATE_RESOURCE_EXCEEDED",
    "ENVIRONMENT",
    "FAILED_INFRA",
    "MAX_INFRA_RETRIES",
    "POLICY_DIR",
    "SEPARATED_IMAGES",
    "SUPERVISOR_SCHEMA",
    "AttributionPolicy",
    "HostTiming",
    "PolicyRefused",
    "Verdict",
    "admissible_stage",
    "classify",
    "environment_consistent",
    "environment_export",
    "host_ran_full_allowance",
    "load_policy",
    "registered_policies",
    "relaunch_left",
    "retry_left",
    "timeout_check",
    "trusted_writer",
]
