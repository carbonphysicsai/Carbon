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
    # Carbon's own file and function names, not data: keep them readable
    # (a long snake_case name must not be masked as base64-looking).
    place = f"{os.path.basename(last.filename)}:{last.lineno}:{last.name}"
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in place)[:160]


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


# --- failure classes (owner P0, 20 Nov 2026: "better failure labels and explanations") ---------------------------------
# A FAILED_INFRA task's closed CLASS, read from its retained diagnosis (stage, reason, where raised, sanitized tail), so
# every record classifies, old ones included, and nothing stored changes. Live 116, 20 Nov: 270 of 343 FAILED_INFRA were
# one catch-all ("build / reconstruction.worker.runtime.failed"): 255 build walls reached on a box shared by other
# builds, 14 lost box links, 1 killed command; none was the recipe's. A wall reached on a QUIET box is the candidate's
# and never FAILED_INFRA (`research_carrier._candidate_resource_stop`), so a FAILED_INFRA wall is Carbon's.

#: Carbon's side: re-run automatically within owner D16's caps (`lean_recipe.BUILD_CODE_RETRIES`), owed as V2 rules.
CARBON_CLASSES = frozenset(
    {
        "carbon_build_wall_busy_host",
        "carbon_inference_wall_busy_host",
        "carbon_box_link_lost",
        "carbon_worker_killed",
        "carbon_docker_command_timeout",
        "carbon_box_unavailable",
        "carbon_dependency_unavailable",
        "carbon_construction_deadline",
        "carbon_restart_lost",
        "carbon_state_conflict",
        "carbon_cleanup_uncertain",
    }
)
#: The recipe's own side: never re-run automatically (the owed list is told, for review).
RECIPE_CLASSES = frozenset({"recipe_program_exited"})
#: Anything else: Carbon's (invariant 7) but re-run ONCE only, never the full cap.
UNCLASSIFIED = "carbon_unclassified"
CLASSES = CARBON_CLASSES | RECIPE_CLASSES | {UNCLASSIFIED}
#: Automatic re-runs a class allows within one task's chain: None = owner D16's per-code cap as before.
RETRIES = {**{name: None for name in CARBON_CLASSES}, UNCLASSIFIED: 1}
RETRIES.update({name: 0 for name in RECIPE_CLASSES})
#: The one plain-English line a miner reads for each class (fixed text: never the diagnosis tail).
EXPLANATIONS = {
    "carbon_build_wall_busy_host": (
        "Your build reached its time limit while Carbon's build machine was busy with other builds, so it counts as "
        "Carbon's failure, not yours. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_inference_wall_busy_host": (
        "Your model's inference reached its time limit while Carbon's machine was busy, so it counts as Carbon's "
        "failure, not yours. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_box_link_lost": (
        "Carbon lost its connection to the build machine during your build. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_worker_killed": (
        "Carbon stopped the worker running your build (a restart or maintenance). Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_docker_command_timeout": (
        "A Carbon container command did not answer in time during your build. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_box_unavailable": (
        "No Carbon build machine was available to run your build. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_dependency_unavailable": (
        "A Carbon image or file your build needs was not available. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_construction_deadline": (
        "Your build and inference ran out of their combined time on a busy Carbon machine. Carbon re-runs it "
        "automatically, up to its retry limit."
    ),
    "carbon_restart_lost": (
        "Carbon restarted while your build was running and could not recover it. Carbon re-runs it automatically, up to its retry limit."
    ),
    "carbon_state_conflict": (
        "Carbon's own records for this build did not agree, so it was stopped on Carbon's side. Carbon re-runs it "
        "automatically, up to its retry limit."
    ),
    "carbon_cleanup_uncertain": (
        "Carbon could not confirm the cleanup after your build. Carbon re-runs it automatically, up to its retry limit."
    ),
    "recipe_program_exited": (
        "Your build program stopped with an error before it finished. Check your recipe and resubmit it; Carbon does "
        "not re-run this automatically."
    ),
    UNCLASSIFIED: (
        "Your build failed on Carbon's side for a reason Carbon has not classified yet. Carbon re-runs it once "
        "automatically."
    ),
}
_LINK_LOST = (
    "dial-stdio",
    "Broken pipe",
    "BrokenPipeError",
    "Connection reset",
    "remote_gpu_build_unhealthy",
)
_BOX_UNAVAILABLE = (
    "remote_gpu_build_no_box",
    "remote_gpu_build_no_proven_box",
    "remote_gpu_build_slots_busy",
)
_EXIT = re.compile(r"(?:^|\n)exit=([0-9]{1,3})\n")


def classify(record) -> str:
    """The closed class (`CLASSES`) of a retained diagnosis record, `UNCLASSIFIED` for anything not recognised (or not a
    record). Deterministic from the record alone."""
    if type(record) is not dict:
        return UNCLASSIFIED
    stage = record.get("failed_stage")
    reason = record.get("reason_code")
    tail = record.get("tail") if type(record.get("tail")) is str else ""
    place = record.get("raised_at") if type(record.get("raised_at")) is str else ""
    if any(marker in tail for marker in _LINK_LOST):
        return "carbon_box_link_lost"
    if "stream command timed out" in tail:
        if stage == "build":
            return "carbon_build_wall_busy_host"
        if stage == "inference":
            return "carbon_inference_wall_busy_host"
    if "bounded command timed out" in tail:
        return "carbon_docker_command_timeout"
    if any(marker in tail for marker in _BOX_UNAVAILABLE):
        return "carbon_box_unavailable"
    if "construction_total_deadline_reached" in tail:
        return "carbon_construction_deadline"
    exited = _EXIT.search(tail)
    if exited is not None:
        code = int(exited.group(1))
        if code in (137, 143):
            return "carbon_worker_killed"
        if (
            stage == "build"
            and 1 <= code <= 125
            and place.endswith(":stream_to_file")
            and "ssh" not in tail
        ):
            # the build PROGRAM's own non-zero exit, the box and its link up
            return "recipe_program_exited"
    if stage == "dependency_check" or reason == "dependency_unavailable":
        return "carbon_dependency_unavailable"
    if stage == "restart_reconcile":
        return "carbon_restart_lost"
    if reason == "reconstruction.worker.cleanup.uncertain":
        return "carbon_cleanup_uncertain"
    if reason == "reconstruction.worker.infrastructure.unavailable":
        return "carbon_box_unavailable"
    if reason == "custody_or_state_invalid":
        return "carbon_state_conflict"
    return UNCLASSIFIED
