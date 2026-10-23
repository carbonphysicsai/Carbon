"""The "Current king" card: who holds each Challenge, and the score to beat.

Owner (via the Lead, 2026-10-23) asked whether miners can see the king. The
Validator ruled the sources and what is public:

- Per Challenge, from its grader's one public read-only route
  `GET /carbon/v1/koth/<challenge>` (OWNER-INTAKE-EXPOSURE-03K, testnet only):
  the holder's hotkey, its total and Carbon's baseline (each stepped to the
  Ladder grid, this exam version's totals), since when, the registered
  margin and the score to beat. A closed key set: any other key, or a value
  of the wrong kind, makes the answer unreadable, never partly shown. A null
  margin (none measured yet) says takeovers are paused; nothing stands in
  for it.
- The whole subnet's paid-keys line (Validator option (a)) is not built yet:
  its chain read is the network snapshot's, which no Launchpad module may
  reach (DASHBOARD-02 S3 condition 4).

Nothing here reads a recipe, a leg, a case or an exam fingerprint.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request

SCHEMA = "carbon.koth.public.v1"
PATH = "/carbon/v1/koth/"
FIELDS = frozenset(
    {
        "schema",
        "challenge_id",
        "challenge_version",
        "exam_version_label",
        "king",
        "margin",
        "to_beat",
        "baseline_total",
    }
)
KING_FIELDS = frozenset({"hotkey", "total", "since_epoch"})
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}")
#: Read bound: the answer is a handful of fields.
MAX_BYTES = 16384

PAUSED = "Takeovers paused: the margin isn't measured yet."
NO_ROUTE = "This grader doesn't publish its king yet."
UNREADABLE = "The grader's king answer couldn't be read; nothing of it is shown."
UNREACHABLE = "The grader couldn't be reached just now; try again later."
NO_GRADER = "No grader is set up for this Challenge on this machine."


class KingUnreadable(ValueError):
    """The route answered something outside its closed shape."""


def _total(value, *, nullable=True):
    if value is None and nullable:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise KingUnreadable("total")
    return float(value)


def parse(document, challenge_id):
    """The route's answer for `challenge_id`, checked field by field."""
    if (
        type(document) is not dict
        or set(document) != FIELDS
        or document["schema"] != SCHEMA
        or document["challenge_id"] != challenge_id
    ):
        raise KingUnreadable("shape")
    version, label = document["challenge_version"], document["exam_version_label"]
    if type(version) is not str or not _ID.fullmatch(version):
        raise KingUnreadable("challenge_version")
    if type(label) is not str or not _LABEL.fullmatch(label):
        raise KingUnreadable("exam_version_label")
    king = document["king"]
    if king is not None:
        if (
            type(king) is not dict
            or set(king) != KING_FIELDS
            or type(king["hotkey"]) is not str
            or not _SS58.fullmatch(king["hotkey"])
            or type(king["since_epoch"]) is not int
            or isinstance(king["since_epoch"], bool)
            or king["since_epoch"] < 0
        ):
            raise KingUnreadable("king")
        king = {
            "hotkey": king["hotkey"],
            "total": _total(king["total"], nullable=False),
            "since_epoch": king["since_epoch"],
        }
    margin, to_beat = _total(document["margin"]), _total(document["to_beat"])
    baseline = _total(document["baseline_total"])
    # A null margin has no score to beat (the Validator: never a default).
    if (margin is None) != (to_beat is None):
        raise KingUnreadable("to_beat")
    if king is not None and baseline is not None:
        raise KingUnreadable("baseline_total")
    # The score to beat is the king's total (or, with no king, the baseline)
    # plus the margin, within one Ladder grid step, eta (Validator, king-card
    # receipt: the margin itself is never part of the tolerance).
    held = king["total"] if king is not None else baseline
    if to_beat is not None:
        from carbon.scoring.grade_feedback import ETA

        if held is None or abs(to_beat - (held + margin)) > ETA + 1e-9:
            raise KingUnreadable("to_beat")
    return {
        "challenge_id": challenge_id,
        "challenge_version": version,
        "exam_version_label": label,
        "king": king,
        "margin": margin,
        "to_beat": to_beat,
        "baseline_total": baseline,
    }


def read(intake, challenge_id, *, timeout=10.0, opener=urllib.request.urlopen):
    """`(answer, None)` from the grader at `intake`, or `(None, words)`: why
    nothing is shown. A 404 is a grader that publishes no king yet."""
    from carbon.development_session.intake_targets import intake_url

    if not intake_url(intake) or not _ID.fullmatch(challenge_id or ""):
        return None, NO_GRADER
    url = intake.rstrip("/") + PATH + urllib.parse.quote(challenge_id, safe="")
    try:
        with opener(url, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as refused:
        return None, NO_ROUTE if refused.code == 404 else UNREACHABLE
    except (urllib.error.URLError, OSError, ValueError):
        return None, UNREACHABLE
    try:
        if len(raw) > MAX_BYTES:
            raise KingUnreadable("size")
        return parse(json.loads(raw), challenge_id), None
    except (KingUnreadable, ValueError):
        return None, UNREADABLE


def _score(value):
    return f"{value:.4f}"


def words(answer):
    """The card's lines for one Challenge's answer, in plain words."""
    lines = []
    king = answer["king"]
    label = answer["exam_version_label"]
    if king is not None:
        lines.append(
            f"Current king: {king['hotkey']}, score {_score(king['total'])} "
            f"(0 to 1, higher is better; exam {label}), since round "
            f"{king['since_epoch']}."
        )
        if answer["to_beat"] is not None:
            lines.append(
                f"Score to beat: {_score(answer['to_beat'])} (the king's score "
                f"plus the margin {_score(answer['margin'])})."
            )
    elif answer["baseline_total"] is not None:
        lines.append(
            f"No king yet: beat Carbon's baseline "
            f"({_score(answer['baseline_total'])}, exam {label})"
            + (
                f" by the margin {_score(answer['margin'])}, so score above "
                f"{_score(answer['to_beat'])}."
                if answer["to_beat"] is not None
                else "."
            )
        )
    else:
        lines.append(f"No king yet (exam {label}).")
    if answer["margin"] is None:
        lines.append(PAUSED)
    return lines


def card(intakes, *, read_one=read):
    """The whole card: each Challenge with a grader on this machine."""
    # The subnet's paid-keys line waits for a chain read of its own: the
    # metagraph read this would use is the network snapshot's, which no
    # Launchpad module may reach (the snapshot-unreachable invariant).
    challenges = []
    for challenge_id in sorted(intakes):
        answer, why = read_one(intakes[challenge_id], challenge_id)
        challenges.append(
            {
                "challenge_id": challenge_id,
                "answer": answer,
                "lines": words(answer) if answer is not None else [why],
            }
        )
    return {"subnet": None, "challenges": challenges}


def for_profile(configuration):
    """The card for this install's runner profile: its own graders
    (`intakes`) and, unless it practises without registering, its chain."""
    if configuration is None:
        return {
            "subnet": None,
            "challenges": [],
            "words": "Finish Setup to see each Challenge's king.",
        }
    from carbon.development_session.private_records import private_json
    from scripts.dev.miner_launchpad.runner import intakes

    return card(intakes(private_json(configuration)))
