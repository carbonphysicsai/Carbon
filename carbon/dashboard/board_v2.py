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
  stay.

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
)
RULES_STATES = ("UNAVAILABLE", "DIGEST_MISMATCH", "OK")
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


def freshness(generated_at, released_count, now):
    """`(phase, freshness)` from the feed's `generated_at` and `now`."""
    if type(now) is not int:
        raise ValueError("now is whole seconds since the epoch")
    stamp = utc_seconds(generated_at)
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
    }


def restamp(board, now):
    """A stored v2 board with its phase recomputed at `now` (for the last
    accepted board kept when a newer feed is refused)."""
    phase, fresh = freshness(
        board["generated_at"], board["next_release"]["released_windows"], now
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
    return (
        _fields(
            ("hotkey", incumbent["hotkey"], None),
            ("uid", None, "not_in_feed"),
            ("submission_id", incumbent["submission_id"], "not_in_feed"),
            ("section", name, "no_ranking_section"),
            ("value", value, "no_ranking_section" if name is None else "not_in_feed"),
            ("registered_score", None, "not_in_feed"),
            ("since_block", incumbent["since_block"], "not_in_feed"),
            ("since_utc", None, "not_in_feed"),
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
        )
        | {"hotkeys": list(row["hotkeys"])}
        for row in ladder
    ]


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
            ("grain", *_ruled(None, gate)),
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
    return {
        **_fields(
            ("era", board["challenge"]["rule_digest"], None),
            ("section", name, "no_ranking_section"),
            ("kings", None, "not_in_feed"),
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
    phase, fresh = freshness(board["generated_at"], released, now)
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
            ("championship", None, "not_in_feed"),
        ),
        "rules": rules,
        # Both parts are the rule's: the posted margin and the comparison's
        # noise guard. Neither is in the feed yet, so no target is shown.
        "target_to_beat": _fields(
            ("value", None, "not_in_feed"),
            ("posted_margin", None, "not_in_feed"),
            ("noise_guard", None, "not_in_feed"),
        ),
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
                ("next_block", None, "not_in_feed"),
                ("next_utc", None, "not_in_feed"),
            ),
            "released_windows": released,
        },
        "gates": _gates(board, king),
        "excluded_canaries": board["excluded_canaries"],
    }
