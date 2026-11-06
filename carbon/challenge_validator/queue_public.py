"""The public, read-only queue document: ``GET /carbon/v1/queue/<challenge_id>`` (owner 6 Nov: "We need to show miners
the Queue if our system is going to back one up and make them wait"; spec Miner X QUEUE_VISIBILITY_SPEC_20261106).

What a miner may know about this door's queue, and nothing else: COUNTS and the door's state in plain words. Closed
field set ``schema, challenge_id, challenge_version, door_state, waiting_to_build, building_now, waiting_to_grade,
grading_now, wait_24h, as_of``; ``wait_24h`` is ``verdicts, median_s, p90_s, reason``.

- ``door_state`` is one of `DOOR_STATES`, never an operator reason or detail;
- every count is a non-negative int, ``grading_now`` 0 or 1;
- ``wait_24h``: submit-to-verdict seconds over the last 24 h, median and the slowest 10 % (nearest-rank p90), only once
  there are `MIN_VERDICTS` verdicts; before that both are null with ``reason`` ``fewer_than_5_verdicts_in_24h``;
- ``as_of``: the UTC time the counts were read (ISO 8601, seconds).

It names no hotkey, task id, recipe, score, timing of any one submission, pack, seed or host. A door that serves no
queue answers 404; a reader that fails answers 503, never a partial document. Pure: the receiver supplies a ``view``
whose ``snapshot()`` returns the raw counts (`queue_view.QueueView`).
"""

from __future__ import annotations

import datetime
import json
import math

SCHEMA = "carbon.queue.public.v1"
PATH = "/carbon/v1/queue/"
MAX_BYTES = 4096
#: The door states a miner sees, in plain words (Miner X's spec): nothing else, never an operator reason.
GRADING = "grading"
PAUSED = "paused"
DRAINING = "draining for an update"
KING = "re-measuring the king"
DOOR_STATES = (GRADING, PAUSED, DRAINING, KING)
MIN_VERDICTS = 5
TOO_FEW = "fewer_than_5_verdicts_in_24h"
FIELDS = frozenset(
    {
        "schema",
        "challenge_id",
        "challenge_version",
        "door_state",
        "waiting_to_build",
        "building_now",
        "waiting_to_grade",
        "grading_now",
        "wait_24h",
        "as_of",
    }
)
WAIT_FIELDS = frozenset({"verdicts", "median_s", "p90_s", "reason"})
#: The raw snapshot a view returns (and nothing else is read from it).
SNAPSHOT_FIELDS = frozenset(
    {
        "door_state",
        "waiting_to_build",
        "building_now",
        "waiting_to_grade",
        "grading_now",
        "waits_s",
        "as_of_unix",
    }
)


class QueuePublicRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _count(value, code, maximum=10**7):
    if type(value) is not int or not 0 <= value <= maximum:
        raise QueuePublicRefused(code)
    return value


def wait_summary(waits_s):
    """``{verdicts, median_s, p90_s, reason}`` from the last 24 h's submit-to-verdict waits (seconds)."""
    if type(waits_s) not in (list, tuple):
        raise QueuePublicRefused("queue_waits_invalid")
    waits = []
    for value in waits_s:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise QueuePublicRefused("queue_waits_invalid")
        waits.append(float(value))
    if len(waits) < MIN_VERDICTS:
        return {
            "verdicts": len(waits),
            "median_s": None,
            "p90_s": None,
            "reason": TOO_FEW,
        }
    ordered = sorted(waits)
    n = len(ordered)
    middle = n // 2
    median = ordered[middle] if n % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    p90 = ordered[max(0, math.ceil(0.9 * n) - 1)]  # nearest rank
    return {
        "verdicts": n,
        "median_s": round(median),
        "p90_s": round(p90),
        "reason": None,
    }


def document(snapshot, challenge):
    """The public document from a view's raw snapshot, checked field by field (closed set)."""
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_FIELDS:
        raise QueuePublicRefused("queue_snapshot_invalid")
    if snapshot["door_state"] not in DOOR_STATES:
        raise QueuePublicRefused("queue_door_state_invalid")
    grading = _count(snapshot["grading_now"], "queue_grading_now_invalid", 1)
    as_of = snapshot["as_of_unix"]
    if type(as_of) not in (int, float) or not math.isfinite(as_of) or as_of <= 0:
        raise QueuePublicRefused("queue_as_of_invalid")
    body = {
        "schema": SCHEMA,
        "challenge_id": challenge.challenge_id,
        "challenge_version": challenge.version,
        "door_state": snapshot["door_state"],
        "waiting_to_build": _count(snapshot["waiting_to_build"], "queue_count_invalid"),
        "building_now": _count(snapshot["building_now"], "queue_count_invalid"),
        "waiting_to_grade": _count(snapshot["waiting_to_grade"], "queue_count_invalid"),
        "grading_now": grading,
        "wait_24h": wait_summary(snapshot["waits_s"]),
        "as_of": datetime.datetime.fromtimestamp(as_of, datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    if set(body) != FIELDS or set(body["wait_24h"]) != WAIT_FIELDS:
        raise QueuePublicRefused("queue_fields_differ")
    return body


def serve(view, challenge):
    """``(status, document-or-refusal)`` as `koth_public.serve`: 200 with the document, 404 with no view, 503 when the
    view fails or the document would exceed `MAX_BYTES` (never partial)."""
    if view is None:
        return 404, {"refused": "queue_not_served"}
    try:
        body = document(view.snapshot(), challenge)
    except QueuePublicRefused as refused:
        return 503, {"refused": refused.code}
    except (AttributeError, OSError, ValueError, KeyError, TypeError):
        return 503, {"refused": "queue_unavailable"}
    if len(json.dumps(body, sort_keys=True, separators=(",", ":"))) > MAX_BYTES:
        return 503, {"refused": "queue_unavailable"}
    return 200, body
