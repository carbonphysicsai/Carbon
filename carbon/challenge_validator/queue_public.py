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
#: v2 (Miner X-B / TE-B 7 Nov) = v1's closed fields plus ``held_for_review``, served at ``PATH + <id> + V2_SUFFIX``
#: (the koth /v2 pattern); v1 stays byte-identical for current clients.
SCHEMA_V2 = "carbon.queue.public.v2"
V2_SUFFIX = "/v2"
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
FIELDS_V2 = FIELDS | {"held_for_review"}
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
#: The v2 count a view may add (`queue_view.QueueView.held`): an int on a crown-hold door, None on every other.
HELD = "held_for_review"


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
    if type(snapshot) is not dict or set(snapshot) - {HELD} != SNAPSHOT_FIELDS:
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


def document_v2(snapshot, challenge):
    """The v2 document: v1's, plus ``held_for_review``, the number of crown changes held for review on this door (a
    menu-D version's coded crown hold, `crown_hold`): a count, or None on a door that holds no crown, never 0 for it.
    """
    body = document(snapshot, challenge)
    held = snapshot.get(HELD) if type(snapshot) is dict else None
    if HELD not in snapshot or not (
        held is None or type(held) is int and 0 <= held <= 10**7
    ):
        raise QueuePublicRefused("queue_held_invalid")
    body = {**body, "schema": SCHEMA_V2, HELD: held}
    if set(body) != FIELDS_V2:
        raise QueuePublicRefused("queue_fields_differ")
    return body


def serve_v2(view, challenge):
    """`serve` for the v2 document."""
    return serve(view, challenge, render=document_v2)


def serve(view, challenge, *, render=document):
    """``(status, document-or-refusal)`` as `koth_public.serve`: 200 with the document, 404 with no view, 503 when the
    view fails or the document would exceed `MAX_BYTES` (never partial)."""
    if view is None:
        return 404, {"refused": "queue_not_served"}
    try:
        body = render(view.snapshot(), challenge)
    except QueuePublicRefused as refused:
        return 503, {"refused": refused.code}
    except (AttributeError, OSError, ValueError, KeyError, TypeError):
        return 503, {"refused": "queue_unavailable"}
    if len(json.dumps(body, sort_keys=True, separators=(",", ":"))) > MAX_BYTES:
        return 503, {"refused": "queue_unavailable"}
    return 200, body
