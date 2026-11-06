"""A validator's signed launch board (OWNER-DASHBOARD-01): the public standing of
one launch Challenge, from the Ladder and the king, and nothing finer.

The launch Challenges (Motor, Cooling, F08, F02) are graded on sealed exams, so
there are no released windows and no score feed (`score_feed`). The dashboard
instead shows this closed document, one per Challenge, which the validator
operator builds on the validator host from what the receiver already stores
and serves:

- the **king**: exactly `koth_public.document` (the king's hotkey and
  Ladder-stepped total, the margin, the score to beat, Carbon's baseline while
  no one is king);
- the **ladder**: per graded hotkey, its Ladder *best* total (already floored to
  the Ladder step, "the total alone") and the status of its latest result in
  the Ladder's closed set (`grade_feedback.STATUSES`), with the closed gate
  names only when that result failed a gate;
- **counts**: how many hotkeys have a graded result, and how many are in each
  status. Counts only.

Nothing else can appear: no per-case or per-leg value, no section below the
total, no target, pool, seed, recipe or model, no raw or finer-than-the-step
number. The document is built field by field from allow-lists, never by
removing fields, and `check` refuses any other shape.

- **Schema:** `carbon.validator.launch-board.v1`, its own.
- **Signed bytes:** `BOARD_DOMAIN` followed by the document without its
  `signature` field, canonical as the feed's (`feed_file.canonical`). The
  domain is never the feed's or the network snapshot's: a launch-board
  signature verifies as neither of them, nor theirs as this.
- **Key:** the validator's feed key (`score_feed.FeedKey`), loaded on the
  validator host by the operator who runs this command. The dashboard pins its
  public half out of band. `LaunchBoardKey` signs under `BOARD_DOMAIN` only.
- **Never an input:** scoring and weights code never imports this module
  (`tests/invariants/test_launch_board_unreachable.py`).

    python -m carbon.challenge_validator.launch_board build --config BOARD.json --out board.json

The config (`CONFIG_SCHEMA`) names the receiver's attempt-ledger file, the
Challenge, the exam key, the king document (the receiver's own
`GET /carbon/v1/koth/<challenge_id>`, fetched by the operator) and the feed
key's file. The operator runs it on a timer and uploads `--out` next to the
network snapshot (`docs/development/DASHBOARD_CLOUDFLARE_SETUP.md`).

DEVELOPMENT / TESTNET only: no qualification, score, weight, reward or LIVE
authority.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

from carbon.scoring import grade_feedback as gf

from .feed_file import canonical as _canonical
from .feed_file import write_feed
from .koth_public import FIELDS as KOTH_FIELDS
from .koth_public import FIELDS_V2 as KOTH_FIELDS_V2
from .koth_public import KING_FIELDS, TO_BEAT_RULES
from .score_feed import FeedKey, FeedRefused

SCHEMA = "carbon.validator.launch-board.v1"
BOARD_DOMAIN = b"carbon.validator.launch-board.v1\x00"
#: The v2 board: v1's shape plus the king's ``to_beat_rule`` and ``crown_changes``, under its OWN signing domain. v1
#: stays byte-identical and is still built from a v1 king document; a v1 signature never verifies as v2 or the reverse.
SCHEMA_V2 = "carbon.validator.launch-board.v2"
BOARD_DOMAIN_V2 = b"carbon.validator.launch-board.v2\x00"
#: The v3 board (OWNER-CROWN-AVG-UNSTABLE-KING-01, Validator 3 Nov receipted wording): v2's shape plus ONE king field, ``stability``
#: ("STABLE" / "UNSTABLE", null with no king), under its OWN signing domain. v1 and v2 stay byte-identical; a v2 signature never
#: verifies as v3 or the reverse. "UNSTABLE" = the king's latest crown-average re-measure was seed-fragile, so his single
#: registered total stands; the board carries no seed, no mean and no number for it.
SCHEMA_V3 = "carbon.validator.launch-board.v3"
BOARD_DOMAIN_V3 = b"carbon.validator.launch-board.v3\x00"
STABILITY = ("STABLE", "UNSTABLE")
#: The v4 board (Lead 5 Nov 21:5x: each door's live crown state): v3's shape plus the king's re-measure progress
#: (``measure``: a state and two COUNTS, never a seed, mean or per-seed status) and the crown checks (``crown_checks``: the
#: latest decision per contender, hotkey + state + outcome and reason CODES), under its OWN signing domain. v1-v3 stay
#: byte-identical; a v3 signature never verifies as v4 or the reverse.
SCHEMA_V4 = "carbon.validator.launch-board.v4"
BOARD_DOMAIN_V4 = b"carbon.validator.launch-board.v4\x00"
#: MEASURED: a mean is filed on the king's current key; UNSTABLE: his re-measure was seed-fragile; IN_PROGRESS: some
#: rebuilds are kept, the mean is not filed yet; UNMEASURED: none kept.
MEASURE_STATES = ("MEASURED", "UNSTABLE", "IN_PROGRESS", "UNMEASURED")
MEASURE_FIELDS = frozenset({"state", "kept", "n"})
#: The crown outcomes that DECIDE a contender (bank_promotion's); anything else (UNAVAILABLE, FAILED_INFRA) is PENDING.
DECIDED_OUTCOMES = (
    "FIRST_INCUMBENT",
    "CHALLENGER",
    "INCUMBENT_KEEPS",
    "NO_WINNER",
    "INCUMBENT_DETHRONED",
)
CHECK_OUTCOMES = (*DECIDED_OUTCOMES, "UNAVAILABLE", "FAILED_INFRA")
CHECK_STATES = ("PENDING", "DECIDED")
CHECK_FIELDS = frozenset({"hotkey", "state", "outcome", "note"})
#: The PUBLIC phrase of a crown check (Validator-2 5 Nov 22:10): a closed map from the internal outcome and reason, never
#: the raw reason code. No near / far distinction (every INCUMBENT_KEEPS reads the same) and no gate or stability name.
#: Unknown reasons read "pending". Its content is the Carbon Validator's receipt.
NOTE_TOOK = "took the crown"
NOTE_FIRST = "took the first crown"
NOTE_REMOVED = "king removed"
NOTE_KEEPS = "the king keeps the crown"
NOTE_NO_CHANGE = "no crown change"
NOTE_WAIT_KING = "waiting for the king's re-measure"
NOTE_QUEUED = "queued"
NOTE_RETRY = "retrying after an infrastructure fault"
NOTE_PENDING = "pending"
NOTES = {
    "CHALLENGER": (NOTE_TOOK,),
    "FIRST_INCUMBENT": (NOTE_FIRST,),
    "INCUMBENT_DETHRONED": (NOTE_REMOVED,),
    "INCUMBENT_KEEPS": (NOTE_KEEPS,),
    "NO_WINNER": (NOTE_NO_CHANGE,),
    "FAILED_INFRA": (NOTE_RETRY,),
    "UNAVAILABLE": (NOTE_WAIT_KING, NOTE_QUEUED, NOTE_PENDING),
}
#: The internal UNAVAILABLE reasons that have their own phrase (crown_average.KING_UNMEASURED, bank_promotion.CROWNS_PAUSED /
#: CROWN_QUEUED, written out so this module imports neither); every other reason is "pending".
_WAIT_KING_REASONS = ("crown_average_king_unmeasured",)
_QUEUED_REASONS = ("crowns_paused", "queued_behind_undecided_crown")


def public_note(outcome, reason):
    """The public phrase of a crown check's ``outcome`` and internal ``reason`` (`NOTES`), or None for an outcome outside
    `CHECK_OUTCOMES`. The reason only picks between the UNAVAILABLE phrases; it is never published.
    """
    if outcome not in NOTES:
        return None
    if outcome != "UNAVAILABLE":
        return NOTES[outcome][0]
    if reason in _WAIT_KING_REASONS:
        return NOTE_WAIT_KING
    if reason in _QUEUED_REASONS:
        return NOTE_QUEUED
    return NOTE_PENDING


#: A board shows at most this many crown checks, newest first.
MAX_CROWN_CHECKS = 10
CONFIG_SCHEMA = "carbon.validator.launch-board.config.v1"
NETWORKS = ("testnet", "mainnet")
#: The labels a board may carry: never FIXTURE (a fixture is never served).
LABELS = {"testnet": ["DEVELOPMENT", "TESTNET"], "mainnet": ["DEVELOPMENT"]}
FIELDS = frozenset(
    {
        "schema",
        "version",
        "labels",
        "network",
        "generated_at",
        "challenge",
        "validator",
        "king",
        "ladder",
        "counts",
        "signature",
    }
)
FIELDS_V2 = FIELDS | {"crown_changes"}
FIELDS_V3 = FIELDS_V2
KING_SECTION = ("king", "margin", "to_beat", "baseline_total")
KING_SECTION_V2 = (*KING_SECTION, "to_beat_rule")
KING_SECTION_V3 = (*KING_SECTION_V2, "stability")
KING_SECTION_V4 = (*KING_SECTION_V3, "measure")
FIELDS_V4 = FIELDS_V2 | {"crown_checks"}
#: A board shows at most this many changes of king, newest first.
MAX_CROWN_CHANGES = 5
CROWN_CHANGE_FIELDS = frozenset({"from_hotkey", "to_hotkey", "since_epoch", "total"})
CHALLENGE_FIELDS = frozenset({"id", "version", "exam_version_label"})
LADDER_FIELDS = frozenset({"rank", "hotkey", "total", "status", "gate_names"})
COUNT_FIELDS = ("graded", "scored", "gate_failed", "not_scored")
#: A ladder this long is the whole table; the board shows no more rows than this.
MAX_LADDER = 512
MAX_GATES = 16
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
_HEX_KEY = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}")
_GATE = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


#: The most decimals a public number carries. The dashboard's reader refuses anything that does not fit
#: (`carbon.dashboard.launch._digits`), so the producer rounds to this, and rounds so the page is never kinder than the
#: truth: a total or the baseline DOWN (the Ladder's own floor rule continues to 9 places), the margin and the score to
#: beat UP (the bar is never understated).
DECIMALS = 9
_GRID = Decimal(1).scaleb(-DECIMALS)
#: The v2 ``rebuild_noise`` argument has no default: None is a value (no registered noise: the Ladder's eta step).
_REQUIRED = object()
#: ``build``'s ``stability`` is absent for a v1/v2 board; any value (None included) makes it a v3 board.
_ABSENT = object()


def floor9(value):
    """``value`` rounded DOWN to `DECIMALS` places, exactly (decimal arithmetic on the float's shortest form)."""
    return float(Decimal(repr(float(value))).quantize(_GRID, rounding=ROUND_FLOOR))


def ceil9(value):
    """``value`` rounded UP to `DECIMALS` places, exactly."""
    return float(Decimal(repr(float(value))).quantize(_GRID, rounding=ROUND_CEILING))


def on_nine(value):
    """Whether ``value`` already fits in `DECIMALS` places."""
    shown = Decimal(repr(float(value)))
    return shown == shown.quantize(_GRID)


class BoardRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _domain(document):
    """The signing domain of a board's schema: v2 and v3 each have their own, anything else is v1's."""
    schema = document.get("schema")
    if schema == SCHEMA_V4:
        return BOARD_DOMAIN_V4
    if schema == SCHEMA_V3:
        return BOARD_DOMAIN_V3
    return BOARD_DOMAIN_V2 if schema == SCHEMA_V2 else BOARD_DOMAIN


class LaunchBoardKey(FeedKey):
    """The validator's feed key, signing launch boards: under `BOARD_DOMAIN`
    only, never the feed's or the snapshot's domain."""

    def __repr__(self):
        return "LaunchBoardKey(<redacted>)"

    def sign(self, document):
        return self._key.sign(_domain(document) + _canonical(document).encode()).hex()


def _unit(value, code):
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not 0 <= value <= 1
        or not math.isfinite(value)
    ):
        raise BoardRefused(code)
    return float(value)


def _king(raw, *, v2=False):
    """The closed king document (`koth_public.document`'s shape, or `document_v2`'s) or a refusal."""
    if type(raw) is not dict or set(raw) != (KOTH_FIELDS_V2 if v2 else KOTH_FIELDS):
        raise BoardRefused("board_king")
    if v2 and raw["to_beat_rule"] not in TO_BEAT_RULES:
        raise BoardRefused("board_king")
    king = raw["king"]
    if king is not None:
        if (
            type(king) is not dict
            or set(king) != KING_FIELDS
            or type(king["hotkey"]) is not str
            or not _SS58.fullmatch(king["hotkey"])
            or type(king["since_epoch"]) is not int
            or king["since_epoch"] < 0
        ):
            raise BoardRefused("board_king")
        king = {
            "hotkey": king["hotkey"],
            "total": floor9(_unit(king["total"], "board_king")),
            "since_epoch": king["since_epoch"],
        }
    label = raw["exam_version_label"]
    if (
        type(raw["challenge_id"]) is not str
        or not raw["challenge_id"]
        or type(raw["challenge_version"]) is not str
        or not _NAME.fullmatch(raw["challenge_version"])
        or type(label) is not str
        or not _LABEL.fullmatch(label)
    ):
        raise BoardRefused("board_king")

    def optional(name, rounding):
        return None if raw[name] is None else rounding(_unit(raw[name], "board_king"))

    return {
        "schema": raw["schema"],
        "challenge_id": raw["challenge_id"],
        "challenge_version": raw["challenge_version"],
        "exam_version_label": label,
        "king": king,
        # the bar is never understated: margin and score to beat UP, the baseline DOWN
        "margin": optional("margin", ceil9),
        "to_beat": optional("to_beat", ceil9),
        "baseline_total": optional("baseline_total", floor9),
        **({"to_beat_rule": raw["to_beat_rule"]} if v2 else {}),
    }


def _stability_ok(stability, king, measure):
    """v3: a king has a stability, no king has none. v4 (``measure`` given): the stability follows the measure: STABLE
    exactly when MEASURED, UNSTABLE exactly when UNSTABLE, None while the king is not measured yet (IN_PROGRESS /
    UNMEASURED) or with no king."""
    if stability not in (None, *STABILITY):
        return False
    if measure is _ABSENT:
        return (stability is None) == (king is None)
    if king is None or type(measure) is not dict:
        return stability is None and king is None
    expected = {"MEASURED": "STABLE", "UNSTABLE": "UNSTABLE"}.get(measure.get("state"))
    return stability == expected


def measure_checked(measure, *, king):
    """The closed ``measure`` (None with no king) or `BoardRefused` ("board_measure")."""
    if king is None:
        if measure is not None:
            raise BoardRefused("board_measure")
        return None
    if (
        type(measure) is not dict
        or set(measure) != MEASURE_FIELDS
        or measure["state"] not in MEASURE_STATES
        or type(measure["kept"]) is not int
        or type(measure["n"]) is not int
        or not 2 <= measure["n"] <= 100
        or not 0 <= measure["kept"] <= measure["n"]
    ):
        raise BoardRefused("board_measure")
    return {"state": measure["state"], "kept": measure["kept"], "n": measure["n"]}


def crown_checks_checked(checks):
    """The closed ``crown_checks`` list (at most `MAX_CROWN_CHECKS`; hotkeys distinct; an outcome in `CHECK_OUTCOMES`
    whose state follows from it; a public note from that outcome's `NOTES`) or `BoardRefused` ("board_crown_checks").
    """
    if type(checks) is not list or len(checks) > MAX_CROWN_CHECKS:
        raise BoardRefused("board_crown_checks")
    out, seen = [], set()
    for check_ in checks:
        if (
            type(check_) is not dict
            or set(check_) != CHECK_FIELDS
            or type(check_["hotkey"]) is not str
            or not _SS58.fullmatch(check_["hotkey"])
            or check_["hotkey"] in seen
            or check_["outcome"] not in CHECK_OUTCOMES
            or check_["state"]
            != ("DECIDED" if check_["outcome"] in DECIDED_OUTCOMES else "PENDING")
            or check_["note"] not in NOTES[check_["outcome"]]
        ):
            raise BoardRefused("board_crown_checks")
        seen.add(check_["hotkey"])
        out.append({k: check_[k] for k in ("hotkey", "state", "outcome", "note")})
    return out


def crown_changes_checked(changes):
    """The closed ``crown_changes`` list (at most `MAX_CROWN_CHANGES`, each exactly the four keys, hotkeys as the king
    page shows them, the total rounded as every public total), or a refusal. Nothing else can pass through.
    """
    if type(changes) is not list or len(changes) > MAX_CROWN_CHANGES:
        raise BoardRefused("board_crown_changes")
    out = []
    for change in changes:
        if (
            type(change) is not dict
            or set(change) != CROWN_CHANGE_FIELDS
            or type(change["to_hotkey"]) is not str
            or not _SS58.fullmatch(change["to_hotkey"])
            or (
                change["from_hotkey"] is not None
                and (
                    type(change["from_hotkey"]) is not str
                    or not _SS58.fullmatch(change["from_hotkey"])
                )
            )
            or type(change["since_epoch"]) is not int
            or isinstance(change["since_epoch"], bool)
            or change["since_epoch"] < 0
        ):
            raise BoardRefused("board_crown_changes")
        out.append(
            {
                "from_hotkey": change["from_hotkey"],
                "to_hotkey": change["to_hotkey"],
                "since_epoch": change["since_epoch"],
                "total": floor9(_unit(change["total"], "board_crown_changes")),
            }
        )
    return out


def ladder_rows(
    rows, *, exact=None, king_hotkey=None, king_total=None, rebuild_noise=None
):
    """The board's ladder from `ladder_store.board_rows`: ``[(hotkey, best,
    latest)]`` with each document as the Ladder serves it. One row per hotkey:
    its best total (null before any improvement) and its latest status, ranked
    by total, highest first, equal totals sharing a rank.

    With ``exact`` (a v2 board; OWNER-BOARD-TRUE-ORDER-01) the order is the TRUE one: the current king (``king_hotkey``)
    is always listed first at rank 1, every other row follows by descending EXACT best total, and equal ranks only when
    the exact totals are bit-equal (a challenger bit-equal to the king co-ranks 1, listed after the king). A row for
    which ``exact`` holds no total (only the crown path keeps one) is ordered by its own floored total, as on v1; none
    is invented. An exact total orders its row only when it IS that row's total: floored the Ladder's way (its step,
    from ``rebuild_noise``, the Challenge's registration as the Ladder reads it, or None) it gives the row's published
    total; otherwise the row keeps the floored rule (Validator, 1 Nov 19:05 CST). The published ``total`` stays
    step-floored, and the exact totals never leave this function: only the order is revealed. On such a
    board the KING row's shown total is ``king_total`` (the crown standing's floored total, as the king page shows it)
    rather than its single best grade, so the board and the king page always agree.
    """
    kept = []
    for hotkey, best, latest in rows:
        if type(hotkey) is not str or not _SS58.fullmatch(hotkey):
            raise BoardRefused("board_hotkey")
        if latest is None or latest.get("status") not in gf.STATUSES:
            raise BoardRefused("board_latest")
        total = None if best is None else floor9(_unit(best["total"], "board_total"))
        gates = (
            [g for g in latest["gate_names"] if type(g) is str and _GATE.fullmatch(g)]
            if latest["status"] == "GATE_FAILED"
            else None
        )
        if gates is not None and len(gates) > MAX_GATES:
            raise BoardRefused("board_gates")
        kept.append((hotkey, total, latest["status"], gates))
    if exact is None:
        kept.sort(key=lambda row: (row[1] is None, -(row[1] or 0.0), row[0]))
        keys = [row[1] for row in kept]
    else:
        if king_hotkey is not None and king_total is not None:
            kept = [
                (h, king_total if h == king_hotkey else t, st, g)
                for h, t, st, g in kept
            ]
        keys = _true_order(kept, exact, king_hotkey, _noise_value(rebuild_noise))
        kept = [row for row, _ in keys]
        keys = [key for _, key in keys]
    out, rank, previous = [], 0, object()
    for position, ((hotkey, total, status, gates), key) in enumerate(
        zip(kept, keys, strict=True), 1
    ):
        if key != previous:
            rank, previous = position, key
        row = {
            "rank": rank,
            "hotkey": hotkey,
            "total": total,
            "status": status,
            "gate_names": gates,
        }
        out.append(row)
    if len(out) > MAX_LADDER:
        raise BoardRefused("board_ladder_size")
    return out


def _noise_value(rebuild_noise):
    """The registered rebuild noise's value (None when none is registered), checked as the Ladder checks it."""
    from .ladder_store import LadderStoreRefused
    from .ladder_store import _noise_value as ladder_noise

    try:
        noise = ladder_noise(rebuild_noise)
        gf.step(noise)
    except (LadderStoreRefused, gf.LadderFeedbackRefused):
        raise BoardRefused("board_rebuild_noise") from None
    return noise


def _true_order(kept, exact, king_hotkey, noise):
    """``[(row, tie_key)]`` in the true order: the king first (alone at rank 1), then descending exact best total; the
    tie key is the exact total itself (so only bit-equal totals share a rank), the row's own floored total when no exact
    total is held for it (v1's order and ties for that row), or None for a row with no best total.
    """
    if type(exact) is not dict:
        raise BoardRefused("board_exact")
    values = {}
    for hotkey, total, _status, _gates in kept:
        value = exact.get(hotkey)
        if value is not None and (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise BoardRefused("board_exact")
        # Validator 1 Nov 19:05 CST: an exact total is used only when it is this row's own total: floored to the
        # Ladder's step and then to 9 places (as the Ladder floors a best, and the king page its crown standing) it
        # gives the row's published total. Otherwise (a grade of another exam, a read that raced a new grade, a row
        # with no best) the row keeps the floored rule, as a row the pool store holds no exact total for.
        if value is not None and (
            total is None or floor9(gf.floor_to_step(value, noise)) != total
        ):
            value = None
        values[hotkey] = value
    # Validator 17:25 CST: an exact total orders only rows that both hold one; a row with one against a row without is
    # compared on both floored totals. So the floored total sorts first, and a floored group (equal shown totals) that
    # holds a row with no exact total is ONE tie: that row is equal to every row in it.
    mixed = {t for h, t, _s, _g in kept if t is not None and values[h] is None}

    def tie_key(row):
        hotkey, total = row[0], row[1]
        if total is None:
            return None
        if total in mixed or values[hotkey] is None:
            return ("floored", total)
        return ("exact", values[hotkey])

    king = [row for row in kept if row[0] == king_hotkey]
    rest = [row for row in kept if row[0] != king_hotkey]
    rest.sort(
        key=lambda row: (
            row[1] is None,
            -(row[1] or 0.0),
            values[row[0]] is None,
            -(values[row[0]] or 0.0),
            row[0],
        )
    )
    ordered = [
        (row, tie_key(row)) for row in king
    ]  # first, alone unless a challenger compares equal
    ordered += [(row, tie_key(row)) for row in rest]
    if king and len(ordered) > len(king):
        # the group right after the king co-ranks 1 when any of its rows compares equal to the king: bit-equal exact
        # totals when both hold one, else equal floored totals
        (krow, kkey), group_key = ordered[0], ordered[len(king)][1]
        group = [
            i for i in range(len(king), len(ordered)) if ordered[i][1] == group_key
        ]

        def equal_to_king(row):
            if values[krow[0]] is not None and values[row[0]] is not None:
                return values[row[0]] == values[krow[0]]
            return row[1] is not None and row[1] == krow[1]

        if group_key is not None and any(equal_to_king(ordered[i][0]) for i in group):
            for i in group:
                ordered[i] = (ordered[i][0], kkey)
    return ordered


def exact_best_totals(store, *, challenge_id, exam_key, king_model_id=None):
    """The OPERATOR-SIDE source of the exact best totals for a v2 board (never published, never persisted): per hotkey,
    the maximum ``total_score`` over the pool store's private evaluations of this Challenge that the Ladder counts as
    scored (its own scored statuses) on the board rows' exam. That exam is ``exam_key``, the sealed evaluation pack
    digest the Ladder keys its rows by, matched against the evidence's own ``evaluation_pack_digest`` (Validator, 1 Nov
    19:05 CST: the evidence names a judge-suffixed evaluation version, never the Ladder's label). The king's own entry
    is the incumbent standing's total (after crown-average, its N-rebuild mean). ``store`` needs
    `private_evaluation_bodies()` and `incumbent_standing`. A host-owned derived row (not a hotkey) is skipped. Pass
    the result to `build(..., exact_totals=)`, which uses an entry only where it floors to its row's published total.
    """
    from .koth_public import KothPublicRefused, _owner_hotkey

    best = {}
    for body in store.private_evaluation_bodies():
        evidence = body.get("evidence")
        model = evidence.get("model_p") if type(evidence) is dict else None
        if (
            type(model) is not dict
            or evidence.get("challenge") != challenge_id
            or exam_key is None
            or evidence.get("evaluation_pack_digest") != exam_key
            or model.get("score_status") not in gf._SCORED
            or type(model.get("total_score")) is not float
            or not math.isfinite(model["total_score"])
        ):
            continue
        try:
            hotkey = _owner_hotkey(body.get("owner"))
        except KothPublicRefused:
            continue
        if _SS58.fullmatch(hotkey):
            best[hotkey] = max(best.get(hotkey, 0.0), model["total_score"])
    if king_model_id is not None:
        standing = store.incumbent_standing(king_model_id)
        if standing is not None:
            try:
                hotkey = _owner_hotkey(standing["owner"])
            except KothPublicRefused:
                hotkey = ""
            if _SS58.fullmatch(hotkey):
                best[hotkey] = float(standing["total"])
    return best


def counts(ladder):
    """How many hotkeys have a graded result, and how many sit in each status."""
    by = {"IMPROVED": 0, "NO_IMPROVEMENT": 0, "GATE_FAILED": 0, "NOT_SCORED": 0}
    for row in ladder:
        by[row["status"]] += 1
    return {
        "graded": len(ladder),
        "scored": by["IMPROVED"] + by["NO_IMPROVEMENT"],
        "gate_failed": by["GATE_FAILED"],
        "not_scored": by["NOT_SCORED"],
    }


def build(
    *,
    king_document,
    rows,
    network,
    key,
    version,
    now=None,
    crown_changes=None,
    exact_totals=None,
    rebuild_noise=_REQUIRED,
    stability=_ABSENT,
    measure=_ABSENT,
    crown_checks=None,
):
    """The signed launch board for one Challenge.

    ``king_document`` is the receiver's `koth_public.document` (its public
    ``GET /carbon/v1/koth/<id>`` answer); ``rows`` are
    `ladder_store.board_rows`; ``key`` a `LaunchBoardKey`; ``version`` a whole
    number that grows with every build (the Worker keeps the last-good board
    when it does not). A v2 board also takes ``exact_totals`` and ``rebuild_noise`` (the Challenge's registration, or
    None when none is registered: the Ladder's step), with no default, so neither can be left out.
    """
    if network not in NETWORKS:
        raise BoardRefused("board_network")
    if type(version) is not int or version < 1:
        raise BoardRefused("board_version")
    v4 = measure is not _ABSENT
    v3 = v4 or stability is not _ABSENT
    v2 = crown_changes is not None
    if v3 and not v2:
        raise BoardRefused("board_v3_needs_crown_changes")  # v3 is v2 plus one field
    if v4 and (stability is _ABSENT or crown_checks is None):
        raise BoardRefused(
            "board_v4_needs_stability_and_checks"
        )  # v4 is v3 plus two fields
    king = _king(king_document, v2=v2)
    if v3 and not _stability_ok(stability, king["king"], measure if v4 else _ABSENT):
        raise BoardRefused("board_stability")
    if v2 and exact_totals is None:
        raise BoardRefused(
            "board_exact_totals_required"
        )  # the v2 board's order is the true one
    if v2 and rebuild_noise is _REQUIRED:
        raise BoardRefused("board_rebuild_noise_required")
    ladder = ladder_rows(
        rows,
        exact=exact_totals if v2 else None,
        king_hotkey=None if king["king"] is None else king["king"]["hotkey"],
        king_total=None if king["king"] is None else king["king"]["total"],
        rebuild_noise=rebuild_noise if v2 else None,
    )
    moment = datetime.datetime.now(datetime.UTC) if now is None else now
    document = {
        "schema": SCHEMA_V4 if v4 else SCHEMA_V3 if v3 else SCHEMA_V2 if v2 else SCHEMA,
        "version": version,
        "labels": list(LABELS[network]),
        "network": network,
        "generated_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "challenge": {
            "id": king["challenge_id"],
            "version": king["challenge_version"],
            "exam_version_label": king["exam_version_label"],
        },
        "validator": {"feed_key": key.public_key},
        "king": {name: king[name] for name in (KING_SECTION_V2 if v2 else KING_SECTION)}
        | ({"stability": stability} if v3 else {})
        | ({"measure": measure_checked(measure, king=king["king"])} if v4 else {}),
        "ladder": ladder,
        "counts": counts(ladder),
        **({"crown_changes": crown_changes_checked(crown_changes)} if v2 else {}),
        **({"crown_checks": crown_checks_checked(crown_checks)} if v4 else {}),
    }
    check(document, unsigned=True)
    return {**document, "signature": key.sign(document)}


def check(document, *, unsigned=False):
    """The document when it has exactly the board's closed shape, else a
    `BoardRefused`: the writer's last step and the reader's first."""
    v4 = type(document) is dict and document.get("schema") == SCHEMA_V4
    v3 = v4 or (type(document) is dict and document.get("schema") == SCHEMA_V3)
    v2 = v3 or (type(document) is dict and document.get("schema") == SCHEMA_V2)
    want = (FIELDS_V4 if v4 else FIELDS_V2 if v2 else FIELDS) - (
        {"signature"} if unsigned else set()
    )
    if type(document) is not dict or set(document) != want:
        raise BoardRefused("board_fields")
    if (
        document["schema"] not in (SCHEMA, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4)
        or document["network"] not in NETWORKS
    ):
        raise BoardRefused("board_schema")
    if document["labels"] != LABELS[document["network"]]:
        raise BoardRefused("board_labels")
    if type(document["version"]) is not int or document["version"] < 1:
        raise BoardRefused("board_version")
    if type(document["generated_at"]) is not str or not _UTC.fullmatch(
        document["generated_at"]
    ):
        raise BoardRefused("board_time")
    challenge = document["challenge"]
    if (
        type(challenge) is not dict
        or set(challenge) != CHALLENGE_FIELDS
        or any(type(challenge[k]) is not str or not challenge[k] for k in challenge)
    ):
        raise BoardRefused("board_challenge")
    validator = document["validator"]
    if (
        type(validator) is not dict
        or set(validator) != {"feed_key"}
        or type(validator["feed_key"]) is not str
        or not _HEX_KEY.fullmatch(validator["feed_key"])
    ):
        raise BoardRefused("board_validator")
    king = document["king"]
    if type(king) is not dict or set(king) != set(
        KING_SECTION_V4
        if v4
        else KING_SECTION_V3 if v3 else KING_SECTION_V2 if v2 else KING_SECTION
    ):
        raise BoardRefused("board_king")
    if v3 and not _stability_ok(
        king["stability"], king["king"], king["measure"] if v4 else _ABSENT
    ):
        raise BoardRefused("board_stability")
    _king(
        {
            "schema": "carbon.koth.public.v1",
            "challenge_id": challenge["id"],
            "challenge_version": challenge["version"],
            "exam_version_label": challenge["exam_version_label"],
            **{
                name: value
                for name, value in king.items()
                if name not in ("stability", "measure")
            },
        },
        v2=v2,
    )
    shown = [king[name] for name in ("margin", "to_beat", "baseline_total")]
    if king["king"] is not None:
        shown.append(king["king"]["total"])
    if any(value is not None and not on_nine(value) for value in shown):
        raise BoardRefused("board_unrounded")
    ladder = document["ladder"]
    if type(ladder) is not list or len(ladder) > MAX_LADDER:
        raise BoardRefused("board_ladder")
    seen = set()
    for row in ladder:
        if (
            type(row) is not dict
            or set(row) != LADDER_FIELDS
            or type(row["rank"]) is not int
            or row["rank"] < 1
            or type(row["hotkey"]) is not str
            or not _SS58.fullmatch(row["hotkey"])
            or row["hotkey"] in seen
            or row["status"] not in gf.STATUSES
        ):
            raise BoardRefused("board_ladder")
        seen.add(row["hotkey"])
        if row["total"] is not None:
            _unit(row["total"], "board_ladder")
            if not on_nine(row["total"]):
                raise BoardRefused("board_unrounded")
        if row["gate_names"] is not None and (
            row["status"] != "GATE_FAILED"
            or type(row["gate_names"]) is not list
            or len(row["gate_names"]) > MAX_GATES
            or any(
                type(g) is not str or not _GATE.fullmatch(g) for g in row["gate_names"]
            )
        ):
            raise BoardRefused("board_ladder")
    if document["counts"] != counts(ladder):
        raise BoardRefused("board_counts")
    if (
        v2
        and crown_changes_checked(document["crown_changes"])
        != document["crown_changes"]
    ):
        raise BoardRefused("board_crown_changes")
    if v4 and (
        measure_checked(king["measure"], king=king["king"]) != king["measure"]
        or crown_checks_checked(document["crown_checks"]) != document["crown_checks"]
    ):
        raise BoardRefused("board_measure_or_checks")
    return document


def verify(document, pinned_key):
    """The board when its signature is the pinned key's over `BOARD_DOMAIN`
    and the document is the closed shape; else a `BoardRefused`. The key the
    document names is informational: `pinned_key` is what a reader configured
    out of band."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        body = {k: v for k, v in document.items() if k != "signature"}
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pinned_key)).verify(
            bytes.fromhex(document["signature"]),
            _domain(body) + _canonical(body).encode(),
        )
    except (InvalidSignature, KeyError, TypeError, ValueError, AttributeError):
        raise BoardRefused("board_signature") from None
    return check(document)


# --- the command ---------------------------------------------------------------------


def _config(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {"schema", "network", "ledger", "challenge", "exam_key", "koth", "key"}
    if (
        type(raw) is not dict
        or raw.get("schema") != CONFIG_SCHEMA
        or not names <= set(raw)
        or set(raw) - names - {"version"}
        or raw["network"] not in NETWORKS
    ):
        raise BoardRefused("board_config")
    return raw


def build_from_ledger(
    *,
    ledger,
    challenge,
    exam_key,
    king_document,
    network,
    key,
    version,
    crown_changes=None,
    exact_totals=None,
    rebuild_noise=_REQUIRED,
    stability=_ABSENT,
    measure=_ABSENT,
    crown_checks=None,
):
    """The signed board for ``challenge`` (an object with `challenge_id` and `version`)
    from the receiver's ledger file (read-only) and its king document. ``exam_key``
    is the sealed pack digest, or "latest" for the exam of the most recent graded
    result (an empty ladder when nothing is graded yet)."""
    from .ladder_store import board_rows, latest_exam_key

    if exam_key == "latest":
        exam_key = latest_exam_key(ledger, challenge)
    rows = [] if exam_key is None else board_rows(ledger, challenge, exam_key)
    return build(
        king_document=king_document,
        rows=rows,
        network=network,
        key=key,
        version=version,
        crown_changes=crown_changes,
        exact_totals=exact_totals,
        rebuild_noise=rebuild_noise,
        stability=stability,
        measure=measure,
        crown_checks=crown_checks,
    )


def now_version():
    """A whole number that grows with every build: seconds since the epoch."""
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def main(argv=None):
    parser = argparse.ArgumentParser(prog="launch_board")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--config", required=True, type=Path)
    make.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = _config(args.config)
        challenge = type(
            "Challenge",
            (),
            {
                "challenge_id": config["challenge"]["id"],
                "version": config["challenge"]["version"],
            },
        )()
        king = json.loads(Path(config["koth"]).read_text(encoding="utf-8"))
        key = LaunchBoardKey.load(config["key"])
        version = config.get("version")
        write_feed(
            args.out,
            build_from_ledger(
                ledger=config["ledger"],
                challenge=challenge,
                exam_key=config["exam_key"],
                king_document=king,
                network=config["network"],
                key=key,
                version=now_version() if version is None else version,
            ),
        )
    except (BoardRefused, FeedRefused, OSError, ValueError, KeyError) as error:
        print("launch board refused:", getattr(error, "code", type(error).__name__))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
