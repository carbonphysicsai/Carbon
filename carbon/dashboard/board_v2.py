"""The `board.v2` data contract (DASHBOARD-02 S1): one board per Challenge and
device class, for the redesigned pages.

`project(board, now)` takes the board model `feed.project` returned, so it sees
only the signed feed's allow-listed, verified fields, and never the raw
document. It adds no field the feed does not carry and invents no value:

- every `null` has a reason, at `reasons[<key>]` of the object that holds it
  (`REASONS` lists the codes). `not_in_feed` means the signed feed carries no
  such field yet, so the Validator decides whether to add it;
- rank, incumbent ("king") and challenger states are the validator's, copied as
  given. The only arithmetic is display arithmetic: the king's margin over the
  runner-up, block-to-time conversions at the nominal block time, and gate
  counts;
- the ranking section is the one the feed's standing ranks by (each `best`).
  It is labelled with its own name and sense, for example "accuracy (lower is
  better)", never "score": the registered score is not in the feed yet;
- an era is one rule digest. A board holds one feed document, so its history
  is never spliced across digests; a new digest is a new era;
- the Validator's signed rules card is the only source of a rule statement
  (Test Lead ruling, DASHBOARD-02 S1). `rules.status` is UNAVAILABLE with no
  card, DIGEST_MISMATCH when the card's `rule.digest` is not the feed's
  `challenge.rule_digest`, and OK when they match. Unless OK, the rule text,
  round period, release predicate, retirement count and release lag are null
  with the status's reason; numbers measured in the feed (scores, blocks)
  stay. The feed's own rotation (`rotation`, from
  `release.rotation_every_blocks`) and its section metadata (`sections`) are
  such numbers (DASHBOARD-02 S2): shown whatever the status, while
  `next_round.every` stays the rule's round period;
- VALIDATOR-33 A (#1143) feeds add chain time, the king from the winner
  ledger, its handovers and the target to beat (DASHBOARD-02 S1b). The king's
  UID, coldkey, crowning, share, next halving and defences fill the board's
  king only when the feed's king is its released incumbent; otherwise they
  stay null with `king_not_released`. The target's margins and noise guard
  are values the validator posts in its signed feed, not rule statements, so
  they show whatever the rules card's status; the rule's prose stays the
  card's. The next release block is the feed's next rotation block, and its
  time is an estimate from `as_of_block` at the nominal block time. With
  `as_of_block`, the feed's age is measured from its chain time.

Display software only: nothing here ranks, nominates or promotes.
"""

from __future__ import annotations

import datetime
import re

from carbon.dashboard import feed

SCHEMA = "carbon.dashboard.board.v2"
#: Nominal Bittensor block time, used only to show estimated durations.
BLOCK_SECONDS = 12
#: ENGINEERING UI DEFAULT, not a registered value: a board whose feed was
#: generated more than this long ago shows phase STALE.
STALE_AFTER_SECONDS = 2 * 60 * 60
PHASES = ("PRE_FIRST_RELEASE", "LIVE", "STALE")
#: The feed's standing holds only eligible entries (each `gates.eligible` PASS).
ELIGIBLE_LABEL = "Eligible for the championship"
REASONS = (
    "not_in_feed",
    "no_released_incumbent",
    "no_standing",
    "ranking_section_ambiguous",
    "no_ranking_section",
    "no_runner_up",
    "not_a_challenger",
    "generated_at_unparseable",
    "rules_unavailable",
    "rules_digest_mismatch",
    "sealed_until_grain",
    "grain_human_input",
    "not_a_numeric_section",
    # VALIDATOR-33 A: the feed's king is not (yet) the released incumbent.
    "king_not_released",
    # The king is not paid now (ineligible, or its share is 0): no halving.
    "king_not_paid",
    # The deployed rule names no registered score.
    "no_registered_score",
    # The latest king's reign has no end yet.
    "reigning",
)
#: The noise guard's parameters, as the feed's final comparison states them.
NOISE_GUARD_KEYS = feed.COMPARISON_KEYS
RULES_STATES = ("UNAVAILABLE", "DIGEST_MISMATCH", "OK")
# The championship's shape (Test Lead, VALIDATOR-32 rev 7 §5), for S2. None
# of it is in the feed yet, so `championship.rounds` and every `entry` field are
# null with `not_in_feed`; nothing here computes them.
CHAMPIONSHIP_ROUND_KEYS = (
    "epoch",
    "chunks_used",
    "stopped",
    "n_solved",
    "margin_pct",
    "entrants",
    "new_king",
    "paid_from_epoch",
)
CHAMPIONSHIP_STOPS = ("efficacy", "futility", "max")
CHAMPIONSHIP_ENTRANT_KEYS = (
    "est_improvement_pct",
    "lower_bound_pct",
    "guard_bar_pct",
    "gap_to_win_pct",
    "safety",
    "outcome",
)
EMPTY_EPOCH_OUTCOME = "no contenders: king paid"
CHAMPIONSHIP_ENTRY_COLDKEY_KEYS = ("screening_display", "gap_to_entry", "entered")
_CARD_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_UTC = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z")


def _fields(*items):
    """An object of `(key, value, reason)` items; each null value's reason
    goes to `reasons[key]`."""
    out, reasons = {}, {}
    for key, value, reason in items:
        out[key] = value
        if value is None:
            reasons[key] = reason
    out["reasons"] = reasons
    return out


def utc_seconds(text):
    """Seconds since the epoch for `YYYY-MM-DDTHH:MM:SSZ`, or None."""
    match = _UTC.fullmatch(text) if type(text) is str else None
    if match is None:
        return None
    y, mo, d, h, mi, s = (int(g) for g in match.groups())
    if y < 1970:
        return None
    try:
        moment = datetime.datetime(y, mo, d, h, mi, s, tzinfo=datetime.timezone.utc)
    except ValueError:
        return None
    return int(moment.timestamp())


#: The latest whole second `utc_text` writes (9999-12-31T23:59:59Z).
_MAX_UTC_SECONDS = feed.MAX_UTC_MS // 1000


def utc_text(seconds):
    """`YYYY-MM-DDTHH:MM:SSZ` for whole seconds since the epoch, or None when
    out of range."""
    if seconds is None or not 0 <= seconds <= _MAX_UTC_SECONDS:
        return None
    d = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    return (
        f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
        f"T{d.hour:02d}:{d.minute:02d}:{d.second:02d}Z"
    )


def _utc_of_ms(ms):
    """A feed time in UTC ms as text, to the whole second (rounded down)."""
    return None if ms is None else utc_text(ms // 1000)


def _span(blocks):
    """A block count with its nominal duration; None when the feed states none."""
    if blocks is None:
        return None
    return {
        "blocks": blocks,
        "seconds": blocks * BLOCK_SECONDS,
        # blocks * 12 / 3600 h, to 2 places (blocks / 3 is never a half).
        "hours": round(blocks / 3) / 100,
    }


def _units(value, digits):
    return round(value * 10**digits)


def freshness(generated_at, released_count, now, as_of=None):
    """`(phase, freshness)` from the feed's age at `now`: measured from its
    chain time `as_of` (whole seconds, from `as_of_block`) when it carries one,
    else from `generated_at`. `basis` says which."""
    if type(now) is not int:
        raise ValueError("now is whole seconds since the epoch")
    if as_of is not None:
        stamp, basis = as_of, "as_of_block"
    else:
        stamp, basis = utc_seconds(generated_at), "generated_at"
    age = None if stamp is None else now - stamp
    if age is None or age > STALE_AFTER_SECONDS:
        phase = "STALE"
    elif released_count == 0:
        phase = "PRE_FIRST_RELEASE"
    else:
        phase = "LIVE"
    reason = "not_in_feed" if generated_at is None else "generated_at_unparseable"
    return phase, {
        **_fields(("age_seconds", age, reason)),
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "basis": basis,
    }


def restamp(board, now):
    """A stored v2 board with its phase recomputed at `now` (for the last
    accepted board kept when a newer feed is refused)."""
    as_of = board.get("as_of_block")
    phase, fresh = freshness(
        board["generated_at"],
        board["next_release"]["released_windows"],
        now,
        None if as_of is None else utc_seconds(as_of["timestamp_utc"]),
    )
    return {**board, "phase": phase, "freshness": fresh}


def _ranking_section(board):
    names = set()
    for row in board["standing"]:
        names.update(k for k in row["best"] if k in feed.NUMERIC_SECTIONS)
    if not board["standing"]:
        return None, "no_standing"
    if len(names) != 1:
        return None, "ranking_section_ambiguous"
    (name,) = names
    meta = board["section_meta"].get(name)
    sense = None if meta is None else meta["sense"]
    return (
        _fields(
            ("name", name, None),
            ("display", None if meta is None else meta["display"], "not_in_feed"),
            ("unit", None if meta is None else meta["unit"], "not_in_feed"),
            ("sense", sense, "not_in_feed"),
            (
                "label",
                None if sense is None else f"{name} ({sense.replace('_', ' ')})",
                "not_in_feed",
            ),
        ),
        None,
    )


def _king(board, section, challengers):
    incumbent = board["incumbent"]
    if incumbent is None:
        return None, "no_released_incumbent"
    name = None if section is None else section["name"]
    value = None if name is None else incumbent["sections"].get(name)
    runner = None
    if name is not None:
        runner = next(
            (
                row
                for row in board["standing"]
                if row["hotkey"] != incumbent["hotkey"]
                and row["best"].get(name) is not None
            ),
            None,
        )
    margin, margin_reason = None, None
    if name is None:
        margin_reason = "no_ranking_section"
    elif value is None:
        margin_reason = "not_in_feed"
    elif runner is None:
        margin_reason = "no_runner_up"
    elif section["sense"] is None:
        margin_reason = "not_in_feed"
    else:
        digits = board["values"]["digits"]
        king, other = _units(value, digits), _units(runner["best"][name], digits)
        ahead = other - king if section["sense"] == "lower_is_better" else king - other
        margin = ahead / 10**digits
    gates = incumbent["sections"].get("gates")
    ledger, why = _ledger_king(board, incumbent)

    def of(key):
        return None if ledger is None else ledger[key]

    crowned_ms = of("crowned_utc_ms")
    crowned = _utc_of_ms(crowned_ms)
    as_of = board.get("as_of_block")
    held = None
    if (
        crowned_ms is not None
        and as_of is not None
        and as_of["timestamp_ms"] >= crowned_ms
    ):
        held = (as_of["timestamp_ms"] - crowned_ms) // 1000
    unpaid = ledger is not None and (
        ledger["eligible"] is False or ledger["share_now"] == 0
    )
    submission = incumbent["submission_id"]
    return (
        _fields(
            ("hotkey", incumbent["hotkey"], None),
            ("uid", of("uid"), why),
            ("coldkey", of("coldkey"), why),
            (
                "submission_id",
                of("submission_id") if submission is None else submission,
                "not_in_feed",
            ),
            ("section", name, "no_ranking_section"),
            ("value", value, "no_ranking_section" if name is None else "not_in_feed"),
            ("registered_score", None, "not_in_feed"),
            ("since_block", incumbent["since_block"], "not_in_feed"),
            # Held since the crowning: a defence never resets the king's clock.
            ("since_utc", crowned, why),
            ("crowned_utc", crowned, why),
            # Seconds held at the feed's chain time (`as_of_block`).
            ("held_for", held, why),
            ("crowned_epoch", None, "not_in_feed"),
            ("eligible", of("eligible"), why),
            ("eligibility_reason", of("reason"), why),
            ("share_now", of("share_now"), why),
            (
                "next_halving_utc",
                _utc_of_ms(of("next_halving_utc_ms")),
                "king_not_paid" if unpaid else why,
            ),
            ("next_halving_epoch", None, "not_in_feed"),
            # The finals the king survived, as the feed counts them.
            ("defences", of("challenges_survived"), why),
            # Positive: the king is ahead of the runner-up in the section's sense.
            ("margin", margin, margin_reason),
            (
                "runner_up",
                None if runner is None else runner["hotkey"],
                "no_ranking_section" if name is None else "no_runner_up",
            ),
            (
                "challenger_state",
                challengers.get(incumbent["hotkey"]),
                "not_a_challenger",
            ),
            ("gates", None if gates is None else dict(gates), "not_in_feed"),
        ),
        None,
    )


def _ledger_king(board, incumbent):
    """`(king, reason)`: the feed's king (VALIDATOR-33 A) when it is the
    released incumbent; else None and why its fields are null."""
    king = board.get("king")
    if king is None:
        return None, "not_in_feed"
    if king["hotkey"] != incumbent["hotkey"]:
        return None, "king_not_released"
    return king, "not_in_feed"


def _target(board):
    """The target to beat as the validator posts it in its signed feed: the
    rule's kind, the posted (final) and screening margins, the noise guard
    (the final comparison's parameters), the registered score and the gates.
    `value` has no feed field yet."""
    target = board.get("target_to_beat")

    def of(key):
        return None if target is None else target[key]

    comparison = of("final_comparison")
    score = of("score")
    return _fields(
        ("value", None, "not_in_feed"),
        ("kind", of("kind"), "not_in_feed"),
        ("posted_margin", of("final_margin_rel"), "not_in_feed"),
        ("screening_margin", of("screening_margin_rel"), "not_in_feed"),
        (
            "noise_guard",
            None
            if comparison is None
            else _fields(
                *((k, comparison[k], "not_in_feed") for k in NOISE_GUARD_KEYS)
            ),
            "not_in_feed",
        ),
        (
            "registered_score",
            None
            if score is None
            else _fields(
                ("candidate", score["candidate"], "not_in_feed"),
                ("registry_sha256", score["registry_sha256"], "not_in_feed"),
                ("decision", score["decision"], "not_in_feed"),
            ),
            "not_in_feed" if target is None else "no_registered_score",
        ),
        ("gates", None if of("gates") is None else list(of("gates")), "not_in_feed"),
    )


def _next_release_time(board, release):
    """`(next_block, next_utc)`: the feed's next rotation block, and its time
    estimated from `as_of_block` at the nominal block time."""
    block = release.get("next_rotation_block")
    as_of = board.get("as_of_block")
    if block is None or as_of is None:
        return block, None
    seconds = as_of["timestamp_ms"] // 1000 + (block - as_of["number"]) * BLOCK_SECONDS
    return block, utc_text(seconds)


def _rules(board, card):
    """`(rules, gate)`: the rules status, and the reason rule statements are
    withheld (None when OK). `card` is a verified rules card's summary,
    `{"digest": "sha256:…", "rule": {"digest": …}}`, or None. No card is
    configured until the Validator publishes one."""
    if card is None:
        return (
            _fields(
                ("status", "UNAVAILABLE", None),
                ("card_digest", None, "rules_unavailable"),
            ),
            "rules_unavailable",
        )
    digest = card.get("digest") if type(card) is dict else None
    rule = card.get("rule") if type(card) is dict else None
    if type(digest) is not str or not _CARD_DIGEST.fullmatch(digest):
        raise ValueError("a rules card summary names its sha256 digest")
    if type(rule) is not dict or type(rule.get("digest")) is not str:
        raise ValueError("a rules card summary names its rule digest")
    ok = rule["digest"] == board["challenge"]["rule_digest"]
    status = "OK" if ok else "DIGEST_MISMATCH"
    return (
        _fields(("status", status, None), ("card_digest", digest, None)),
        None if ok else "rules_digest_mismatch",
    )


def _ruled(value, gate):
    """A rule statement: withheld with `gate`'s reason unless the rules are OK."""
    return (None, gate) if gate is not None else (value, "not_in_feed")


def _coldkeys(board):
    """The feed's coldkey ladder (OWNER-BATTERY-CHAMPIONSHIP-03), as given: one
    pooled displayed score and status per coldkey, its hotkeys informational."""
    ladder = board.get("ladder")
    if ladder is None:
        return None
    return [
        _fields(
            ("coldkey", row["coldkey"], None),
            ("rank", row["rank"], "not_in_feed"),
            ("displayed_score", row["displayed_score"], "sealed_until_grain"),
            ("status", row["status"], None),
            ("best_submission_id", row["best_submission_id"], "not_in_feed"),
            ("displayed_at_block", row["displayed_at_block"], "not_in_feed"),
        )
        | {"hotkeys": list(row["hotkeys"])}
        for row in ladder["coldkeys"]
    ]


def _grain_pct(board, gate):
    """The ladder's grain: a rule value, so shown only when the rules are OK;
    null while the grain is HUMAN_INPUT."""
    ladder = board.get("ladder")
    if gate is not None:
        return None, gate
    if ladder is None:
        return None, "not_in_feed"
    return ladder["grain_pct"], "grain_human_input"


def _leaderboard(board, section, challengers, lag, gate):
    name = None if section is None else section["name"]
    king = None if board["incumbent"] is None else board["incumbent"]["hotkey"]
    entries = [
        _fields(
            ("rank", row["rank"], None),
            ("hotkey", row["hotkey"], None),
            ("uid", None, "not_in_feed"),
            (
                "screening_value",
                None if name is None else row["best"].get(name),
                "no_ranking_section" if name is None else "not_in_feed",
            ),
            ("registered_score", None, "not_in_feed"),
            ("best_at_block", row["best_at_block"], "not_in_feed"),
            ("challenger_state", challengers.get(row["hotkey"]), "not_a_challenger"),
        )
        | {"is_king": row["hotkey"] == king}
        for row in board["standing"]
    ]
    return {
        **_fields(
            ("section", name, "no_ranking_section"),
            ("release_lag", *lag),
            ("coldkeys", _coldkeys(board), "not_in_feed"),
            ("grain_pct", *_grain_pct(board, gate)),
        ),
        "label": ELIGIBLE_LABEL,
        "entries": entries,
    }


def _history(board, section):
    name = None if section is None else section["name"]
    points = {}
    if name is not None:
        for hotkey, series in board["history"].items():
            kept = [
                {"receipt_block": p["receipt_block"], "value": p["sections"][name]}
                for p in series
                if p["receipt_block"] is not None
                and p["sections"].get(name) is not None
            ]
            if kept:
                points[hotkey] = kept
    handovers = board.get("handovers")
    rows = kings = None
    if handovers is not None:
        rows = [
            _fields(
                ("utc", _utc_of_ms(h["utc_ms"]), "not_in_feed"),
                ("to_hotkey", h["to_hotkey"], "not_in_feed"),
                ("from_hotkey", h["from_hotkey"], "not_in_feed"),
                ("kind", h["kind"], "not_in_feed"),
                ("eligible", h["eligible"], "not_in_feed"),
                ("eligibility_reason", h["reason"], "not_in_feed"),
            )
            for h in handovers
        ]
        # Each reign runs from one handover to the next, in the feed's order.
        kings = [
            _fields(
                ("hotkey", row["to_hotkey"], "not_in_feed"),
                ("crowned_utc", row["utc"], "not_in_feed"),
                (
                    "until_utc",
                    rows[i + 1]["utc"] if i + 1 < len(rows) else None,
                    "not_in_feed" if i + 1 < len(rows) else "reigning",
                ),
                ("eligible", row["eligible"], "not_in_feed"),
            )
            for i, row in enumerate(rows)
        ]
    return {
        **_fields(
            ("era", board["challenge"]["rule_digest"], None),
            ("section", name, "no_ranking_section"),
            ("kings", kings, "not_in_feed"),
            ("handovers", rows, "not_in_feed"),
        ),
        "points": points,
    }


def _gates(board, king):
    meta = board["section_meta"].get("gates")
    names, failing, count = set(), {}, 0
    for miner in board["miners"].values():
        for row in miner["submissions"]:
            gates = row["sections"].get("gates")
            if gates is None:
                continue
            count += 1
            for gate, value in gates.items():
                names.add(gate)
                if value == "FAIL":
                    failing[gate] = failing.get(gate, 0) + 1
    return {
        **_fields(
            ("display", None if meta is None else meta["display"], "not_in_feed"),
            ("unit", None if meta is None else meta["unit"], "not_in_feed"),
            (
                "king",
                None if king is None else king["gates"],
                "no_released_incumbent" if king is None else "not_in_feed",
            ),
        ),
        "names": sorted(names),
        "submissions_with_gates": count,
        "failing": dict(sorted(failing.items())),
    }


def project(board, now, rules_card=None):
    """The v2 board for a `feed.project` board model, at `now` (whole seconds
    since the epoch, for the phase only), with a verified rules card summary
    when one is configured (`_rules`)."""
    if board.get("schema") != feed.BOARD_SCHEMA:
        raise ValueError("board.v2 is projected from a verified board.v1 model")
    release = board["release"] or {}
    released = len(board["released_windows"])
    as_of = board.get("as_of_block")
    phase, fresh = freshness(
        board["generated_at"],
        released,
        now,
        None if as_of is None else as_of["timestamp_ms"] // 1000,
    )
    next_block, next_utc = _next_release_time(board, release)
    section, section_reason = _ranking_section(board)
    challengers = {}
    for row in board["challengers"]:
        challengers.setdefault(row["hotkey"], row["state"])
    lag = _span(release.get("expected_lag_blocks"))
    king, king_reason = _king(board, section, challengers)
    every = release.get("rotation_every_blocks")
    rules, gate = _rules(board, rules_card)
    challenge = {k: v for k, v in board["challenge"].items() if k != "rule"}
    return {
        **_fields(
            ("generated_at", board["generated_at"], "not_in_feed"),
            ("ranking_section", section, section_reason),
            ("king", king, king_reason),
            # The feed's own rotation period (`release.rotation_every_blocks`),
            # a block count measured in the feed (DASHBOARD-02 S2), shown
            # whatever the rules card's status.
            ("rotation", _span(every), "not_in_feed"),
            # The finalized block the feed's chain-time fields were read at.
            (
                "as_of_block",
                None
                if as_of is None
                else {
                    "number": as_of["number"],
                    "hash": as_of["hash"],
                    "timestamp_utc": _utc_of_ms(as_of["timestamp_ms"]),
                },
                "not_in_feed",
            ),
        ),
        # What is scored: each section's display name, unit and sense, as
        # the feed states them.
        "sections": [
            _fields(
                ("name", name, None),
                ("display", meta["display"], "not_in_feed"),
                ("unit", meta["unit"], "not_in_feed"),
                # Gates are pass/fail: they have no better direction.
                (
                    "sense",
                    meta["sense"],
                    "not_a_numeric_section" if name == "gates" else "not_in_feed",
                ),
            )
            for name, meta in board["section_meta"].items()
        ],
        "championship": _fields(
            ("rounds", None, "not_in_feed"),
            (
                "entry",
                _fields(
                    ("trigger_bar", None, "not_in_feed"),
                    ("king_screening_display", None, "not_in_feed"),
                    ("coldkeys", None, "not_in_feed"),
                ),
                None,
            ),
        ),
        "rules": rules,
        # The two bars, the posted margin and the final comparison's noise
        # guard, as the validator posts them in its signed feed (VALIDATOR-33
        # A); their prose stays the rules card's.
        "target_to_beat": _target(board),
        "schema": SCHEMA,
        "source_schema": board["source_schema"],
        "fixture": board["fixture"],
        "labels": list(board["labels"]),
        "challenge": {
            **challenge,
            **_fields(("rule", *_ruled(board["challenge"]["rule"], gate))),
        },
        "era": board["challenge"]["rule_digest"],
        "device_class": board["device_class"],
        "slug": board["slug"],
        "version": board["version"],
        "feed": dict(board["feed"]),
        "phase": phase,
        "freshness": fresh,
        "block_seconds": BLOCK_SECONDS,
        "eligible_leaderboard": _leaderboard(
            board, section, challengers, _ruled(lag, gate), gate
        ),
        "history": _history(board, section),
        "next_round": _fields(
            ("every", *_ruled(_span(every), gate)),
            ("next_block", None, "not_in_feed"),
            ("next_utc", None, "not_in_feed"),
        ),
        "next_release": {
            **_fields(
                ("predicate", *_ruled(release.get("predicate"), gate)),
                ("retire_at", *_ruled(release.get("retire_at"), gate)),
                ("lag", *_ruled(lag, gate)),
                # The feed's next rotation block; its time an estimate.
                ("next_block", next_block, "not_in_feed"),
                ("next_utc", next_utc, "not_in_feed"),
            ),
            "released_windows": released,
        },
        "gates": _gates(board, king),
        "excluded_canaries": board["excluded_canaries"],
    }
