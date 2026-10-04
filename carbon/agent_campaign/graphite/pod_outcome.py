"""How a pod run that did not finish is typed (OWNER-GRAPHITE-TEST-WAVE-02 §3).

A pod runs Carbon's supervisor (`pod_phase`) and a program under one user and
one filesystem. The pinned study image gives the supervisor no separate uid.
What runs as that program depends on the construction level, which comes from
the session's recorded permission profile and never from the submission:
- **Levels 0-3:** the program is Carbon's own trainer, rebuilt from a
  declarative recipe. No participant code runs in the pod.
- **Levels 4-5:** participant code runs in the pod. That code could write
  `failure.json`, serve a forged `/status` or kill the supervisor.

The outcome is typed by an order of authority:

1. **Authority: what Carbon's host observes.** The pod lifecycle (launch,
   the pod's own deadline, loss, cancellation) and the host's own clock
   readings of the pod's phase (`HostTiming`).
2. **Admissible evidence.** Two sources qualify:
   - the pod's stage claim at Levels 0-3, which only Carbon's own code
     writes;
   - at any level, a supervisor report from an image that a host-side record
     (`SEPARATED_IMAGES`) says runs the supervisor apart from the program.
     The pod's own claim never makes it so, and no image has such a record
     yet.
3. **Evidence only.** At Levels 4-5 without a separation record, or at an
   unknown level, anything in the shared uid or filesystem (`failure.json`,
   `/status` stages, exit codes) is recorded but never blames the candidate.

The rules:
- **Timeouts, at every level** (host contention can cause one whoever wrote
  the claim):
  - A worker timeout is never a scientific failure. A first one is
    `FAILED_INFRA` and the proposal is retried once, on a fresh pod, under
    the same declared budget.
  - Only a second timeout that the host's timing confirms counts as the
    candidate exceeding its declared budget: `CANDIDATE_RESOURCE_EXCEEDED`,
    never scored and never a physics failure. The host confirms a timeout
    when its own readings show the phase ran at least the declared worker
    seconds. That span includes Carbon's own compile and pin check, which run
    before the program starts.
  - When the host's timing makes a claimed timeout impossible, the result is
    `FAILED_INFRA` plus an `OTHER_SIGNAL` finding, because it could be
    tampering. Any other unconfirmed second timeout is `FAILED_INFRA`.
- **Program failures:**
  - On admissible evidence, a program failure is the candidate's:
    `CANDIDATE_FAILED`, `program`. That is the typing before this rule, kept
    so a recipe that crashes Carbon's trainer cannot buy infrastructure
    semantics (Track A, selective crash and retry).
  - Otherwise it is `FAILED_INFRA`, `candidate_failure_unattributed`, with
    the claim kept as evidence.
- **Compile failures** stay `FAILED_INFRA` (`compile`), as before. The pod's
  compile ran after Carbon's host compiled the same recipe, so a failure there
  points at the pod's environment.
- The pod's own lifetime deadline, a launch failure and a lost pod stay
  `FAILED_INFRA`, as before.

At Levels 4-5 this mirrors `research_carrier._observed_miner_failure`: a
failure is the candidate's only on observed evidence, and never on an
ambiguous one.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Pinned images whose supervisor runs apart from the candidate (separate uid
#: or unwritable report path), each by a verification record. None yet: the
#: EV4 study image runs the supervisor and the program as one non-root user.
SEPARATED_IMAGES = {}
#: The first construction level at which participant code runs in the pod
#: (Challenge_Admission's construction ladder: Levels 4-5 are code).
PARTICIPANT_CODE_LEVEL = 4

FAILED_INFRA = "FAILED_INFRA"
CANDIDATE_FAILED = "CANDIDATE_FAILED"
CANDIDATE_RESOURCE_EXCEEDED = "CANDIDATE_RESOURCE_EXCEEDED"


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
    #: Whether this attempt asks for the one retry.
    retry: bool = False
    #: Whether the host timing contradicts the pod's claim (an OTHER_SIGNAL).
    signal: bool = False


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


def trusted_writer(level):
    """Whether only Carbon's own code writes the pod's claims at `level`:
    Levels 0-3. An unknown level is not trusted."""
    return type(level) is int and 0 <= level < PARTICIPANT_CODE_LEVEL


def classify(*, claim, admissible, timing, work_seconds, attempt, level):
    """Type one ended-but-not-done pod run.

    `claim` is the failure stage the pod reported; `admissible` is a stage
    from a separated supervisor report, or None; `attempt` is 0 for the first
    pod and 1 for the retry; `level` is the session's recorded construction
    level, or None when it is unknown.
    """
    if admissible is None and trusted_writer(level):
        admissible = claim if claim in ("timeout", "program", "compile") else None
    stage = admissible if admissible is not None else claim
    if stage == "timeout":
        check = timeout_check(timing, work_seconds)
        if check == "contradicted":
            return Verdict(
                FAILED_INFRA, "timeout_claim_contradicts_host_timing", signal=True
            )
        if attempt == 0:
            return Verdict(FAILED_INFRA, "worker_timeout_retried", retry=True)
        if check == "confirmed":
            return Verdict(CANDIDATE_RESOURCE_EXCEEDED, "worker_timeout_repeated")
        return Verdict(FAILED_INFRA, "worker_timeout_unconfirmed")
    if stage == "program" and admissible == "program":
        return Verdict(CANDIDATE_FAILED, "program")
    if stage == "compile" and admissible == "compile":
        return Verdict(FAILED_INFRA, "compile")
    if stage in ("program", "compile"):
        return Verdict(FAILED_INFRA, "candidate_failure_unattributed")
    return Verdict(FAILED_INFRA, "pod")


def admissible_stage(report, image):
    """The stage of a supervisor report, only for an image with a separation
    record; otherwise None (the report stays evidence)."""
    if image not in SEPARATED_IMAGES or type(report) is not dict:
        return None
    stage = report.get("stage")
    return stage if stage in ("timeout", "program", "compile") else None


__all__ = [
    "CANDIDATE_FAILED",
    "CANDIDATE_RESOURCE_EXCEEDED",
    "FAILED_INFRA",
    "PARTICIPANT_CODE_LEVEL",
    "SEPARATED_IMAGES",
    "HostTiming",
    "Verdict",
    "admissible_stage",
    "classify",
    "timeout_check",
    "trusted_writer",
]
