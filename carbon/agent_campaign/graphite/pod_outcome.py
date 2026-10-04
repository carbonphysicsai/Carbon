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
STAGES = ("timeout", "program", "compile")

POLICY_DIR = Path(__file__).with_name("attribution_policies")
POLICY_SCHEMA = "carbon.graphite.pod-attribution-policy.v1"
REGISTRY_SCHEMA = "carbon.graphite.pod-attribution-registry.v1"
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

    @staticmethod
    def from_document(document, digest):
        if type(document) is not dict or set(document) != _KEYS:
            raise PolicyRefused("policy fields")
        if document["schema"] != POLICY_SCHEMA:
            raise PolicyRefused("policy schema")
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
        for table, target, name in (
            (document["admissible"], admissible, "admissible"),
            (document["evidence_only"], evidence_only, "evidence_only"),
        ):
            if type(table) is not dict or set(table) != {"program", "compile"}:
                raise PolicyRefused(name + " covers program and compile")
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
        if any(status != FAILED_INFRA for status, _ in never_blamed):
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
        )

    def record(self):
        return {"version": self.version, "digest": self.digest}


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


def classify(*, claim, admissible, timing, work_seconds, attempt, level, policy):
    """Type one ended-but-not-done pod run under `policy`.

    `claim` is the failure stage the pod reported; `admissible` is a stage
    from a separated supervisor report, or None; `attempt` counts from 0;
    `level` is the session's recorded construction level, or None.
    """
    if type(policy) is not AttributionPolicy:
        raise TypeError("a registered AttributionPolicy is required")
    if admissible is None and trusted_writer(level, policy):
        admissible = claim if claim in STAGES else None
    stage = admissible if admissible is not None else claim
    if stage == "timeout":
        check = timeout_check(timing, work_seconds)
        if check == "contradicted":
            return Verdict(*policy.timeout["contradicted"], signal=True)
        if attempt < policy.retries:
            return Verdict(*policy.timeout["retried"], retry=True)
        if check == "confirmed":
            return Verdict(*policy.timeout["repeated_confirmed"])
        return Verdict(*policy.timeout["unconfirmed"])
    if stage in ("program", "compile"):
        table = policy.admissible if admissible == stage else policy.evidence_only
        return Verdict(*table[stage])
    return Verdict(*policy.no_claim)


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
    "FAILED_INFRA",
    "POLICY_DIR",
    "SEPARATED_IMAGES",
    "AttributionPolicy",
    "HostTiming",
    "PolicyRefused",
    "Verdict",
    "admissible_stage",
    "classify",
    "load_policy",
    "registered_policies",
    "timeout_check",
    "trusted_writer",
]
