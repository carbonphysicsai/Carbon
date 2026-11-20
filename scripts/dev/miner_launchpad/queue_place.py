"""The "Your place in line" card: where this miner's submission waits, the validator's state and the typical wait.

Owner goal (20 Nov 2026): miners send fewer "why is mine not moving" messages. Everything here is read from the door's
EXISTING public queue route, `GET <intake>/carbon/v1/queue/<challenge>[/v4]` (`carbon.challenge_validator.queue_public`),
which any visitor, and the public dashboard, already read. Nothing new is disclosed and nothing is signed or sent:

- the door's state in plain words (up, paused, updating, or not answering);
- the typical wait: the median submit-to-verdict time over the last 24 h and the slowest 10 %, once the door has enough
  verdicts (it says so itself when it has not);
- THIS miner's own row or rows: position, state and time in the queue, found by the first 4 and last 4 characters of the
  miner's own public hotkey (the only form the feed shows). A row the feed names no hotkey for is never claimed.

The feed's rows are unsigned, in 5-minute steps, and name no recipe, score or task id. This module reads the feed only
and copies out the fields it names; it imports no validator code (the client/validator import boundary), and a test holds
its constants to the feed's own. Like the king card it is read at most once a minute by the page.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request

PATH = "/carbon/v1/queue/"
SCHEMA_V4 = "carbon.queue.public.v4"
SCHEMA_V3 = "carbon.queue.public.v3"
SCHEMA_V1 = "carbon.queue.public.v1"
V4_SUFFIX = "/v4"
V3_SUFFIX = "/v3"
#: The feed's own bound for the rows document (`queue_public.MAX_BYTES_V3`); v1 is 4096.
MAX_BYTES = 131072
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
#: The feed's short key: 4 characters, an ellipsis, 4 characters.
_SHORT_KEY = re.compile(r"[1-9A-HJ-NP-Za-km-z]{4}…[1-9A-HJ-NP-Za-km-z]{4}")
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
ROWS_QUANTUM_S = 300

#: The feed's door states (`queue_public.DOOR_STATES`) -> the card's state and its plain words. Never an operator reason.
DOOR_STATES = {
    "grading": ("up", "The validator is up and grading."),
    "re-measuring the king": (
        "up",
        "The validator is up; it is re-measuring the king before it continues.",
    ),
    "paused": ("paused", "The validator is paused: it grades nothing while it is paused."),
    "draining for an update": (
        "updating",
        "Carbon is upgrading the validator; please retry shortly.",
    ),
}
UPDATING = "updating"
WORDS_UPDATING_ANSWER = DOOR_STATES["draining for an update"][1]
WORDS_DOWN = (
    "The validator did not answer from this machine just now. It may be down, or your connection may be: try again in "
    "a few minutes."
)
NO_GRADER = "No validator is set up for this Challenge on this machine."
NO_ROUTE = "This validator does not publish its queue yet."
UNREADABLE = "The validator's queue answer could not be read; nothing of it is shown."
NO_HOTKEY = "Finish registration to see your own place in line; the door's state and wait are shown below."


class QueueUnreadable(ValueError):
    """The route answered something outside the shape this card reads."""


def _count(value, *, maximum=10**7):
    if (
        type(value) is not int
        or isinstance(value, bool)
        or not 0 <= value <= maximum
    ):
        raise QueueUnreadable("count")
    return value


def _seconds(value):
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0 <= value <= 10**8
    ):
        raise QueueUnreadable("seconds")
    return float(value)


def parse(document, challenge_id):
    """The route's answer for ``challenge_id``, checked field by field: only the fields this card shows, copied out.
    ``rows`` is None for a door that serves no row list (the v1 document)."""
    if (
        type(document) is not dict
        or document.get("schema") not in (SCHEMA_V4, SCHEMA_V3, SCHEMA_V1)
        or document.get("challenge_id") != challenge_id
        or document.get("door_state") not in DOOR_STATES
    ):
        raise QueueUnreadable("document")
    wait = document.get("wait_24h")
    if type(wait) is not dict:
        raise QueueUnreadable("wait")
    parsed = {
        "door_state": document["door_state"],
        "waiting_to_build": _count(document.get("waiting_to_build")),
        "building_now": _count(document.get("building_now")),
        "waiting_to_grade": _count(document.get("waiting_to_grade")),
        "grading_now": _count(document.get("grading_now")),
        "verdicts": _count(wait.get("verdicts")),
        "median_s": _seconds(wait.get("median_s")),
        "p90_s": _seconds(wait.get("p90_s")),
        "as_of": document.get("as_of") if type(document.get("as_of")) is str else None,
        "rows": None,
        "more_rows": 0,
    }
    if parsed["as_of"] is not None and not re.fullmatch(
        r"[0-9TZ:-]{20}", parsed["as_of"]
    ):
        raise QueueUnreadable("as_of")
    if document["schema"] != SCHEMA_V1:
        listed = document.get("rows")
        if type(listed) is not list:
            raise QueueUnreadable("rows")
        rows = []
        for position, row in enumerate(listed, 1):
            if (
                type(row) is not dict
                or row.get("position") != position
                or type(row.get("state")) is not str
                or len(row["state"]) > 32
                or not (
                    row.get("hotkey") is None
                    or _SHORT_KEY.fullmatch(str(row["hotkey"]))
                )
            ):
                raise QueueUnreadable("row")
            rows.append(
                {
                    "position": position,
                    "hotkey": row.get("hotkey"),
                    "state": row["state"],
                    "in_queue_s": _count(row.get("in_queue_s"), maximum=10**8),
                }
            )
        parsed["rows"] = rows
        parsed["more_rows"] = _count(document.get("more_rows"))
    return parsed


def short_hotkey(hotkey):
    """The feed's short form of an ss58 hotkey, or None for anything else."""
    if type(hotkey) is not str or not _SS58.fullmatch(hotkey):
        return None
    return hotkey[:4] + "…" + hotkey[-4:]


def _open(url, *, timeout):
    from carbon.miner_agent import MINER_HEADERS

    return urllib.request.urlopen(
        urllib.request.Request(url, headers=MINER_HEADERS, method="GET"),
        timeout=timeout,
    )


def read(intake, challenge_id, *, timeout=10.0, opener=_open):
    """``(answer, None)`` from the door at ``intake``, or ``(None, (state, words))``: why nothing is shown. ``state`` is
    "updating" for a door that answers 503 ``updating``, "down" for one that does not answer, else "unknown"."""
    from carbon.development_session.intake_targets import intake_url

    if not intake_url(intake) or not _ID.fullmatch(challenge_id or ""):
        return None, ("unknown", NO_GRADER)
    url = intake.rstrip("/") + PATH + urllib.parse.quote(challenge_id, safe="")
    raw = None
    # v4 (rows told apart per state), then v3, when the door serves them (404: an older door), then v1 (no rows).
    for candidate in (url + V4_SUFFIX, url + V3_SUFFIX, url):
        try:
            with opener(candidate, timeout=timeout) as response:
                raw = response.read(MAX_BYTES + 1)
            break
        except urllib.error.HTTPError as refused:
            if refused.code == 404 and candidate != url:
                continue
            if refused.code == 404:
                return None, ("unknown", NO_ROUTE)
            if refused.code == 503 and _is_updating(refused):
                return None, (UPDATING, WORDS_UPDATING_ANSWER)
            return None, ("down", WORDS_DOWN)
        except (urllib.error.URLError, OSError, ValueError):
            return None, ("down", WORDS_DOWN)
    try:
        if len(raw) > MAX_BYTES:
            raise QueueUnreadable("size")
        return parse(json.loads(raw), challenge_id), None
    except (QueueUnreadable, ValueError):
        return None, ("unknown", UNREADABLE)


def _is_updating(refused):
    """Whether a 503 is the door's own ``status: updating`` answer (`battery.intake.updating_answer`)."""
    try:
        answer = json.loads(refused.read(4096) or b"{}")
    except (OSError, ValueError):
        return False
    return type(answer) is dict and answer.get("status") == UPDATING


def duration_words(seconds):
    """``seconds`` in the unit a person reads: seconds, minutes, or hours with one decimal (the dashboard's own steps)."""
    if seconds is None:
        return None
    if seconds < 90:
        return f"{round(seconds)} s"
    if seconds < 5400:
        return f"{round(seconds / 60)} min"
    return f"{seconds / 3600:.1f} h"


def _in_queue_words(seconds):
    if seconds < ROWS_QUANTUM_S:
        return "under 5 min"
    if seconds < 3600:
        return f"{seconds // 60} min"
    return f"{seconds // 3600} h {(seconds // 60) % 60} min"


def own_rows(answer, hotkey):
    """This miner's rows of the feed: ``[{position, state, in_queue_s}]``, found by the short form of its own hotkey."""
    short = short_hotkey(hotkey)
    if short is None or answer.get("rows") is None:
        return []
    return [
        {k: row[k] for k in ("position", "state", "in_queue_s")}
        for row in answer["rows"]
        if row["hotkey"] == short
    ]


def lines(answer, hotkey):
    """The card's lines for one Challenge's answer, in plain words."""
    state, door_words = DOOR_STATES[answer["door_state"]]
    out = [door_words]
    rows = answer["rows"]
    total = None if rows is None else len(rows) + answer["more_rows"]
    if hotkey is None:
        out.append(NO_HOTKEY)
    elif rows is None:
        out.append("This validator does not list individual submissions, so your own place is not shown.")
    else:
        mine = own_rows(answer, hotkey)
        for row in mine:
            out.append(
                f"Your place: {row['position']} of {total} ({row['state']}; in the line "
                f"{_in_queue_words(row['in_queue_s'])} so far)."
            )
        if mine:
            if len(mine) > 1:
                out.append(
                    "Each of your submissions that is waiting has its own line above. The list finds you by the "
                    "first and last 4 characters of your hotkey."
                )
        elif answer["more_rows"] > 0:
            out.append(
                f"Your hotkey is not among the oldest {len(rows)} of {total} waiting submissions listed, so a later "
                "one is not shown here yet."
            )
        else:
            out.append(
                "Your hotkey is not in the line right now: nothing of yours is waiting here. A graded submission "
                "leaves the line when its verdict is in."
            )
    out.append(
        f"In the line: {answer['waiting_to_build']} waiting to build, {answer['building_now']} building, "
        f"{answer['waiting_to_grade']} waiting to grade, {answer['grading_now']} grading."
    )
    median = duration_words(answer["median_s"])
    if median is None:
        out.append("Typical wait, last 24 h: not enough verdicts yet to say.")
    else:
        out.append(
            f"Typical wait, last 24 h: {median} from submit to verdict (the slowest 10 % waited "
            f"{duration_words(answer['p90_s'])}; {answer['verdicts']} verdicts, all submissions on this validator)."
        )
    return out, state


def card(intakes, hotkey, *, read_one=read):
    """The whole card: each Challenge with a validator on this machine."""
    challenges = []
    for challenge_id in sorted(intakes):
        answer, why = read_one(intakes[challenge_id], challenge_id)
        if answer is not None:
            text, state = lines(answer, hotkey)
            own = own_rows(answer, hotkey)
        else:
            state, words = why
            text, own = [words], []
        challenges.append(
            {
                "challenge_id": challenge_id,
                "door": state,
                "your_rows": own,
                "lines": text,
            }
        )
    return {"challenges": challenges}


def for_profile(configuration):
    """The card for this install's runner profile: its own validators (`intakes`) and, once registered, its own hotkey."""
    if configuration is None:
        return {
            "challenges": [],
            "words": "Finish Setup to see your place in line.",
        }
    from carbon.development_session.private_records import private_json
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import intakes, miner_hotkey

    profile = private_json(configuration)
    try:
        hotkey = miner_hotkey(profile)
    except (Rejected, OSError, ValueError, KeyError):
        hotkey = None
    return card(intakes(profile), hotkey)
