"""Construction-neutral attacks on pod failure attribution (GRAPHITE-POD-GPU-PROBE-01).

The resource and failure-accounting family's question here: can a
construction make its own failure look like `environment`, the stage Carbon's
GPU probe claims when the pod's backend fails before any candidate code
(`graphite.pod_phase.probe_environment`)? Under `pod-attribution-v2` an
admitted environment failure is `FAILED_INFRA` with one free relaunch on a
fresh pod (`graphite.pod_outcome`), so a forged claim would turn the
construction's own crash into a retried infrastructure outcome (selective
crash and retry).

Nothing here is Challenge-specific: the boundary is Carbon's registered
attribution policy, classified on a synthetic pod export. An adapter adds
`attacks()` to its `resource_accounting` family and routes inputs of kind
`KIND` here (battery's does). Every input is a description of a pod's
export: file names, the supervisor report, the host's timing; no pod, no
code and no protected material.

- `boundary(value)`: the registered current policy's verdict;
- `specimen(value)`: a deliberately weakened classifier that trusts the pod's
  own `environment` claim, whoever wrote it and whatever the export shows;
- `breached(result)`: the claim bought an environment relaunch.

A held attack is evidence about this boundary only; it is no security
acceptance (AGENTS.md §13).
"""

from __future__ import annotations

KIND = "pod_outcome"
#: The attack inputs' declared worker seconds. Classification is relative to
#: it; any positive value serves.
WORK_SECONDS = 600
#: Host readings showing the phase running past the worker seconds.
RAN_FULL_ALLOWANCE = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 15.0 + WORK_SECONDS + 30,
    "ended": 15.0 + WORK_SECONDS + 45,
}
#: Host readings of a pod that ended about a minute after it started running.
ENDED_EARLY = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 60.0,
    "ended": 75.0,
}
#: An image with no separation record (`pod_outcome.SEPARATED_IMAGES`).
UNSEPARATED = "attack-unseparated-image"


def _report(*, stage="environment", probe_ok=False, program_started=False):
    from carbon.agent_campaign.graphite.pod_outcome import SUPERVISOR_SCHEMA

    return {
        "schema": SUPERVISOR_SCHEMA,
        "stage": stage,
        "probe": {"ok": probe_ok, "before_program": True},
        "program_started": program_started,
    }


def attempt(
    *,
    level,
    files,
    report,
    timing=ENDED_EARLY,
    claim="environment",
    earlier=(),
    attempt_index=0,
    image=UNSEPARATED,
):
    """One pod export to classify: what the pod claimed and exported, the
    host's readings and the session's recorded construction level."""
    return {
        "kind": KIND,
        "claim": claim,
        "level": level,
        "files": sorted(files),
        "report": report,
        "timing": timing,
        "earlier": list(earlier),
        "attempt": attempt_index,
        "image": image,
    }


def _result(status, reason_code, *, retry, relaunch, stop, policy):
    return {
        "kind": KIND,
        "status": status,
        "reason_code": reason_code,
        "retry": retry,
        "relaunch": relaunch,
        "stop": stop,
        "policy": policy,
    }


def boundary(value):
    """The registered current attribution policy's verdict on `value`."""
    from carbon.agent_campaign.graphite import pod_outcome

    policy = pod_outcome.load_policy()
    report = value["report"]
    timing = value["timing"]
    verdict = pod_outcome.classify(
        claim=value["claim"],
        admissible=pod_outcome.admissible_stage(report, value["image"]),
        timing=None if timing is None else pod_outcome.HostTiming(**timing),
        work_seconds=WORK_SECONDS,
        attempt=value["attempt"],
        level=value["level"],
        policy=policy,
        export=pod_outcome.environment_export(value["files"], report),
        earlier=tuple(value["earlier"]),
    )
    return _result(
        verdict.status,
        verdict.reason_code,
        retry=verdict.retry,
        relaunch=verdict.relaunch,
        stop=verdict.stop,
        policy=policy.version,
    )


def specimen(value):
    """Vulnerable specimen: a classifier that trusts a candidate-written
    `environment` claim. Any such claim is an infrastructure failure with a
    relaunch, at any level, whatever the export and the host's timing show."""
    if value["claim"] == "environment":
        return _result(
            "FAILED_INFRA",
            "pod_environment",
            retry=True,
            relaunch=True,
            stop=False,
            policy="specimen-trusts-the-pods-environment-claim",
        )
    return boundary(value)


def breached(result):
    """A claim bought an environment relaunch."""
    return result.get("kind") == KIND and bool(result.get("relaunch"))


#: The files a pod exports once its program ran.
_PROGRAM_RAN = ("built.json", "failure.json", "phase.log", "program.log")


def attacks():
    """`((name, input), ...)`: a construction's own failure dressed as an
    environment failure. Each must come back without a relaunch."""
    clean = _report()
    return (
        # Levels 4-5: the program shares the pod's uid, crashes, and
        # overwrites failure.json and the supervisor report after the probe
        # passed, claiming `environment` (the Carbon Validator's case).
        (
            "level4_crash_rewritten_as_environment",
            attempt(level=4, files=_PROGRAM_RAN + ("supervisor.json",), report=clean),
        ),
        # ...and deletes every trace of its own run first.
        (
            "level4_crash_rewritten_with_traces_removed",
            attempt(
                level=4,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=clean,
            ),
        ),
        (
            "unknown_level_environment_claim",
            attempt(
                level=None,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=clean,
            ),
        ),
        # Level 0: a claim of `environment` from a pod whose program ran.
        (
            "level0_environment_claim_after_the_program_ran",
            attempt(level=0, files=_PROGRAM_RAN + ("supervisor.json",), report=clean),
        ),
        (
            "level0_environment_claim_with_predictions",
            attempt(
                level=0,
                files=("failure.json", "predictions.json", "supervisor.json"),
                report=clean,
            ),
        ),
        # Level 0: the probe record says the probe passed.
        (
            "level0_environment_claim_over_a_passing_probe",
            attempt(
                level=0,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=_report(probe_ok=True),
            ),
        ),
        # Level 0: no probe record at all.
        (
            "level0_environment_claim_without_a_probe_record",
            attempt(level=0, files=("failure.json", "phase.log"), report=None),
        ),
        # Level 0: the host saw the phase run its whole worker allowance.
        (
            "level0_environment_claim_after_the_full_allowance",
            attempt(
                level=0,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=clean,
                timing=RAN_FULL_ALLOWANCE,
            ),
        ),
        # A second environment failure asks for another relaunch.
        (
            "level0_second_environment_failure_asks_again",
            attempt(
                level=0,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=clean,
                earlier=("pod_environment",),
                attempt_index=1,
            ),
        ),
        # An environment failure after a worker-deadline retry asks for a
        # second infrastructure retry (the counter never resets). Named
        # without "timeout": pod timeout typing is battery's NOT_RUN seam.
        (
            "level0_environment_after_a_worker_deadline_retry",
            attempt(
                level=0,
                files=("failure.json", "phase.log", "supervisor.json"),
                report=clean,
                earlier=("worker_timeout_retried",),
                attempt_index=1,
            ),
        ),
    )


def control():
    """An honest environment failure at Level 0: the probe failed before the
    program, nothing past it was exported. The real boundary relaunches it."""
    return attempt(
        level=0,
        files=("failure.json", "phase.log", "supervisor.json"),
        report=_report(),
    )


def control_passes(value):
    """The real boundary relaunches an honest environment failure once."""
    result = boundary(value)
    return result["relaunch"] and result["status"] == "FAILED_INFRA"


__all__ = [
    "KIND",
    "attacks",
    "attempt",
    "boundary",
    "breached",
    "control",
    "control_passes",
    "specimen",
]
