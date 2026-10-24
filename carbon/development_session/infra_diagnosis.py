"""Why a direct task ended FAILED_INFRA: a closed stage and reason code, plus a
bounded, sanitized diagnostic tail (Lead, 2026-10-24: "a FAILED_INFRA with no
evidence is itself a bug").

OPERATOR-ONLY. The record is retained beside the task and read through
`private_infra_diagnosis`; no miner or public surface returns it, and the public
receipt keeps its closed `InfrastructureFailureClass`. The tail carries only
what Carbon's own code or the worker's private diagnostic wrote about the
failed step: printable ASCII, long hex or base64-looking runs masked, the last
`TAIL_CHARS` kept. It is never exam data, but treat it as private anyway.
"""

from __future__ import annotations

import os
import re
import traceback

from carbon.reconstruction.worker.model import WorkerFailure

SCHEMA = "carbon.direct-infra-diagnosis.v1"
TAIL_CHARS = 2048
#: Where in the task the failure arose.
STAGES = frozenset(
    {
        "dependency_check",  # the admitted image or source no longer matches
        "provision",  # staging the library overlay or source
        "prep",
        "build",
        "inference",
        "orchestration",  # the task runner itself, no child blamed
        "restart_reconcile",  # a restart found a running task with dead children
    }
)
#: Why: a worker code (the closed `WorkerCode` values) or one of these.
REASONS = frozenset(
    {
        "dependency_unavailable",
        "host_io_error",
        "custody_or_state_invalid",
        "timeout",
        "child_infrastructure_failed",
        "worker_lost",
        "unclassified_internal",
        "graph_decision",  # a Carbon graph decision, not an exception
    }
)
_MASKS = (
    (re.compile(r"[0-9A-Fa-f]{32,}"), "<hex>"),
    (re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}"), "<b64>"),
)


def sanitize_tail(raw) -> str:
    """The last `TAIL_CHARS` of ``raw`` (bytes or str) as printable ASCII with
    long hex and base64-looking runs masked."""
    if isinstance(raw, bytes):
        text = raw.decode("ascii", errors="replace")
    else:
        text = str(raw)
    text = "".join(c if 32 <= ord(c) < 127 or c == "\n" else "?" for c in text)
    for pattern, mask in _MASKS:
        text = pattern.sub(mask, text)
    return text[-TAIL_CHARS:]


def reason_for(error) -> str:
    """A closed reason code for ``error`` (never a message)."""
    if isinstance(error, WorkerFailure):
        return error.code.value
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, OSError):
        return "host_io_error"
    if isinstance(error, ValueError):
        return "custody_or_state_invalid"
    return "unclassified_internal"


def tail_for(error) -> str:
    """The sanitized tail for ``error``: the worker's private diagnostic, else
    the exception's type and message."""
    if isinstance(error, WorkerFailure) and error.private_diagnostic:
        return sanitize_tail(error.private_diagnostic)
    if error is None:
        return ""
    return sanitize_tail(f"{type(error).__name__}: {error}")


def traceback_for(error) -> str:
    """The sanitized tail of ``error``'s formatted traceback (frames, source
    lines and the final message): the step it was raised in."""
    if error is None or getattr(error, "__traceback__", None) is None:
        return ""
    return sanitize_tail(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )


def raised_at(error) -> str:
    """``file:line:function`` of the innermost frame, or an empty string."""
    frames = traceback.extract_tb(getattr(error, "__traceback__", None))
    if not frames:
        return ""
    last = frames[-1]
    return sanitize_tail(
        f"{os.path.basename(last.filename)}:{last.lineno}:{last.name}"
    )[:160]


def diagnosis(
    stage,
    reason,
    tail="",
    child_states=(),
    error=None,
) -> dict:
    """A validated diagnosis, or ValueError: stage and reason are closed.
    ``error`` adds where it was raised and the sanitized traceback tail."""
    states = [s for s in child_states]
    if (
        stage not in STAGES
        or not (reason in REASONS or reason.startswith("reconstruction.worker."))
        or type(tail) is not str
        or len(tail) > TAIL_CHARS
        or any(s is not None and type(s) is not str for s in states)
    ):
        raise ValueError("infrastructure diagnosis malformed")
    return {
        "failed_stage": stage,
        "reason_code": reason,
        "child_states": states,
        "tail": tail,
        "raised_at": raised_at(error),
        "traceback": traceback_for(error),
    }


def stage_of(child_states, provisioning=False) -> str:
    """The stage a failure arose in from the children's ledger states
    (build, inference, then prep) and whether provisioning was under way."""
    if provisioning:
        return "provision"
    for index, name in enumerate(("build", "inference", "prep")):
        if index < len(child_states) and child_states[index] == "FAILED_INFRA":
            return name
    return "orchestration"
