"""Read the validator's signed score feed and keep only what may be shown.

The feed is `carbon.validator.score-feed.v1`, as `carbon.challenge_validator.
score_feed.build` writes it (VALIDATOR-29, released windows only). The
validator applies the disclosure rules first; the dashboard applies them again
(DASHBOARD_PLAN.md §2) and refuses the whole document when one fails. A refusal
is never drawn in part and never replaced by fixture data.

The checks:

1. the pinned schema;
2. an Ed25519 signature, over `DOMAIN` + the canonical document without its
   `signature`, by a key pinned in the dashboard's trust, never the key the
   document names;
3. no live values: `values.live` is null and there is no top-level `live`
   (VALIDATOR-29 item 1 is reserved for an owner record);
4. labels: DEVELOPMENT always, TESTNET when given, FIXTURE exactly for fixtures;
5. one device class: the feed's own, or else every submission's, which must
   agree (CPU and GPU are never ranked together);
6. a registered precision, and every section value rounded to it (never a raw
   value);
7. every window a submission used, and every `detail` key, released;
8. allow-listed fields only: anything else is dropped.

Display software only: nothing here ranks, nominates or promotes. Rank,
incumbent and challenger states are the validator's and are copied as given.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

SCHEMA = "carbon.validator.score-feed.v1"
BOARD_SCHEMA = "carbon.dashboard.board.v1"
# VALIDATOR-29's signed bytes (score_feed.FeedKey.sign): this prefix, then
# json.dumps(sort_keys=True, separators=(",", ":"), allow_nan=False), ASCII.
DOMAIN = b"carbon.validator.score-feed.v1\x00"
NUMERIC_SECTIONS = ("accuracy", "design_q", "near_limit")
SENSES = ("lower_is_better", "higher_is_better")
GATE_VALUES = ("PASS", "FAIL")
LABELS = ("DEVELOPMENT", "TESTNET")
FIXTURE_LABEL = "FIXTURE"
# Per-case fields a released window's `detail` may carry. Others are dropped.
# VALIDATOR-29 v1 emits no detail; its fields are registered before it does.
CASE_TEXT_FIELDS = ("case_id",)
CASE_NUMBER_FIELDS = ("error",)
# The public half of the fixture key (carbon.dashboard.fixtures). It is public
# by design and can never be trusted for a production feed.
FIXTURE_PUBLIC_KEY = "d55fec2a82d5280786d8282263c8f324f43166eb036d38fb64bce7469d742cc8"

_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
_FIXTURE_HOTKEY = re.compile(r"fixture-[a-z0-9-]{1,32}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_HEX_KEY = re.compile(r"[0-9a-f]{64}")
_HEX_SIGNATURE = re.compile(r"[0-9a-f]{128}")
_DEVICE = re.compile(r"cpu|gpu:[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
_STATE = re.compile(r"[A-Z][A-Z0-9_]{0,39}")
_TEXT = re.compile(r"[^\x00-\x1f\x7f<>]{1,200}")


class FeedRefused(ValueError):
    """The whole document is refused; `code` says why, for the feed health line."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class Trust:
    """The feed keys a dashboard build accepts, pinned in its configuration.

    A production trust never holds the fixture key; a fixture trust holds only
    the fixture key. The two are built from different settings.
    """

    keys: frozenset
    fixture: bool = False

    def __post_init__(self):
        keys = frozenset(self.keys)
        if not keys or any(
            type(k) is not str or not _HEX_KEY.fullmatch(k) for k in keys
        ):
            raise ValueError("trust needs one or more 32-byte hex public keys")
        if self.fixture and keys != {FIXTURE_PUBLIC_KEY}:
            raise ValueError("a fixture trust holds only the fixture key")
        if not self.fixture and FIXTURE_PUBLIC_KEY in keys:
            raise ValueError("the fixture key is never a production key")
        object.__setattr__(self, "keys", keys)


def canonical_bytes(document):
    body = {k: v for k, v in document.items() if k != "signature"}
    return (
        DOMAIN
        + json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def key_id(public_hex):
    return "feed-" + hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:16]


def verify(document, trust):
    """Return the pinned hex key that signed the document, or refuse it."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise FeedRefused("schema_unsupported")
    signature = document.get("signature")
    if type(signature) is not str or not _HEX_SIGNATURE.fullmatch(signature):
        raise FeedRefused("signature_missing")
    try:
        message = canonical_bytes(document)
    except (TypeError, ValueError) as exc:
        raise FeedRefused("not_canonical") from exc
    for public in sorted(trust.keys):
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(
                bytes.fromhex(signature), message
            )
        except InvalidSignature:
            continue
        return public
    raise FeedRefused("signature_invalid")


def _int(value, code, *, minimum=0, optional=False):
    if value is None and optional:
        return None
    if type(value) is not int or value < minimum:
        raise FeedRefused(code)
    return value


def _text(value, code):
    if type(value) is not str or not _TEXT.fullmatch(value):
        raise FeedRefused(code)
    return value


def _number(value, code):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise FeedRefused(code)
    return value


def digits_of(precision):
    """Decimal places for a registered precision that is a power of ten."""
    digits = -math.log10(precision)
    if abs(digits - round(digits)) > 1e-9 or round(digits) < 0:
        raise FeedRefused("feed_values_unregistered", "precision")
    return round(digits)


def _rounded(value, digits, where):
    if value is None:
        return None
    _number(value, "section_not_a_number")
    if round(value, digits) != value:
        raise FeedRefused("unrounded_value", where)
    return value


def _hotkey(value, trust):
    pattern = _FIXTURE_HOTKEY if trust.fixture else _SS58
    if type(value) is not str or not pattern.fullmatch(value):
        raise FeedRefused("hotkey_invalid")
    return value


def _sections(raw, digits, where):
    """Numeric sections (nullable, rounded) and gates; unknown keys dropped."""
    if raw is None:
        return {}
    if type(raw) is not dict:
        raise FeedRefused("sections_invalid", where)
    out = {}
    for name in NUMERIC_SECTIONS:
        if name in raw:
            out[name] = _rounded(raw[name], digits, f"{where}.{name}")
    if "gates" in raw:
        gates = raw["gates"]
        if type(gates) is not dict:
            raise FeedRefused("gates_invalid", where)
        out["gates"] = {}
        for gate, value in sorted(gates.items()):
            if value not in GATE_VALUES:
                raise FeedRefused("gates_invalid", where)
            out["gates"][_text(gate, "gates_invalid")] = value
    return out


def _values(raw):
    if type(raw) is not dict:
        raise FeedRefused("feed_values_unregistered")
    if raw.get("live") is not None:
        raise FeedRefused("live_not_authorized")
    released = raw.get("released")
    if type(released) is not dict:
        raise FeedRefused("feed_values_unregistered")
    precision = released.get("precision")
    if type(precision) not in (int, float) or not math.isfinite(precision):
        raise FeedRefused("feed_values_unregistered")
    if precision <= 0:
        raise FeedRefused("feed_values_unregistered")
    threshold = released.get("display_threshold")
    if threshold is not None:
        _number(threshold, "feed_values_unregistered")
    return {
        "precision": precision,
        "digits": digits_of(precision),
        "display_threshold": threshold,
        "registered": _text(raw.get("registered"), "feed_values_unregistered"),
    }


def _section_meta(raw):
    """Display name, unit and sense per section, from the feed's top-level
    `sections`. Numeric sections state a sense; gates have none. The dashboard
    assumes no sense of its own."""
    if raw is None:
        return {}
    if type(raw) is not dict:
        raise FeedRefused("section_meta_invalid")
    out = {}
    for name in (*NUMERIC_SECTIONS, "gates"):
        meta = raw.get(name)
        if meta is None:
            continue
        sense = meta.get("sense") if type(meta) is dict else "invalid"
        if (name == "gates" and sense is not None) or (
            name != "gates" and sense not in SENSES
        ):
            raise FeedRefused("section_meta_invalid", name)
        out[name] = {
            "display": _text(meta.get("display", name), "section_meta_invalid"),
            "unit": (
                None
                if meta.get("unit") in (None, "")
                else _text(meta["unit"], "section_meta_invalid")
            ),
            "sense": sense,
        }
    return out


def _detail(raw, released, used, where):
    if raw is None:
        return {}
    if type(raw) is not dict:
        raise FeedRefused("detail_invalid", where)
    out = {}
    for fingerprint, body in sorted(raw.items()):
        if fingerprint not in released or fingerprint not in used:
            raise FeedRefused("detail_not_released", where)
        cases = body.get("cases") if type(body) is dict else None
        if type(cases) is not list:
            raise FeedRefused("detail_invalid", where)
        kept = []
        for case in cases:
            if type(case) is not dict:
                raise FeedRefused("detail_invalid", where)
            row = {f: _text(case.get(f), "detail_invalid") for f in CASE_TEXT_FIELDS}
            for field in CASE_NUMBER_FIELDS:
                if field in case:
                    row[field] = _number(case[field], "detail_invalid")
            kept.append(row)
        out[fingerprint] = {"cases": kept}
    return out


def _device(value):
    if type(value) is not str or not _DEVICE.fullmatch(value):
        raise FeedRefused("device_class_invalid")
    return value


def _release(raw):
    if raw is None:
        return None
    if type(raw) is not dict:
        raise FeedRefused("release_invalid")
    return {
        "predicate": (
            None
            if raw.get("predicate") is None
            else _text(raw["predicate"], "release_invalid")
        ),
        **{
            k: _int(raw.get(k), "release_invalid", optional=True)
            for k in ("retire_at", "rotation_every_blocks", "expected_lag_blocks")
        },
    }


def project(document, trust):
    """Verify a feed document and return the dashboard's board model.

    Raises FeedRefused with a reason code; never returns a partial board.
    """
    signer = verify(document, trust)
    if "live" in document:
        raise FeedRefused("live_not_authorized")
    values = _values(document.get("values"))
    digits = values["digits"]
    labels = document.get("labels")
    allowed = set(LABELS) | ({FIXTURE_LABEL} if trust.fixture else set())
    if (
        type(labels) is not list
        or "DEVELOPMENT" not in labels
        or len(set(labels)) != len(labels)
        or not set(labels) <= allowed
        or (FIXTURE_LABEL in labels) != trust.fixture
    ):
        raise FeedRefused("labels_invalid")
    challenge = document.get("challenge")
    if type(challenge) is not dict:
        raise FeedRefused("challenge_invalid")
    challenge = {
        **{
            k: _text(challenge.get(k), "challenge_invalid")
            for k in ("id", "version", "rule_digest")
        },
        "rule": (
            None
            if challenge.get("rule") is None
            else _text(challenge["rule"], "challenge_invalid")
        ),
    }

    windows = document.get("released_windows")
    if type(windows) is not list:
        raise FeedRefused("released_windows_invalid")
    released = []
    for fingerprint in windows:
        if type(fingerprint) is not str or not _FINGERPRINT.fullmatch(fingerprint):
            raise FeedRefused("released_windows_invalid")
        released.append(fingerprint)
    released_set = set(released)

    submissions = document.get("submissions")
    if type(submissions) is not list:
        raise FeedRefused("submissions_invalid")
    classes = set()
    if document.get("device_class") is not None:
        classes.add(_device(document["device_class"]))
    miners = {}
    for index, raw in enumerate(submissions):
        where = f"submissions[{index}]"
        if type(raw) is not dict:
            raise FeedRefused("submissions_invalid", where)
        hotkey = _hotkey(raw.get("hotkey"), trust)
        used = raw.get("windows")
        if type(used) is not list or not used:
            raise FeedRefused("submissions_invalid", where)
        if any(w not in released_set for w in used):
            raise FeedRefused("unreleased_window", where)
        state = raw.get("state")
        if type(state) is not str or not _STATE.fullmatch(state):
            raise FeedRefused("submissions_invalid", where)
        if "device_class" in raw:
            classes.add(_device(raw["device_class"]))
        row = {
            "submission_id": _text(raw.get("submission_id"), "submissions_invalid"),
            "receipt_block": _int(
                raw.get("receipt_block"), "submissions_invalid", optional=True
            ),
            "windows": sorted(used),
            "state": state,
            "sections": _sections(raw.get("sections"), digits, where),
            "detail": _detail(raw.get("detail"), released_set, set(used), where),
        }
        miners.setdefault(hotkey, {"hotkey": hotkey, "submissions": []})
        miners[hotkey]["submissions"].append(row)
    if len(classes) > 1:
        raise FeedRefused("device_class_mixed")
    device_class = next(iter(classes)) if classes else None
    for miner in miners.values():
        miner["submissions"].sort(
            key=lambda r: (r["receipt_block"] or 0, r["submission_id"])
        )

    board = document.get("leaderboard")
    if type(board) is not dict:
        raise FeedRefused("leaderboard_invalid")
    incumbent = board.get("incumbent")
    if incumbent is not None:
        if type(incumbent) is not dict:
            raise FeedRefused("leaderboard_invalid")
        incumbent = {
            "hotkey": _hotkey(incumbent.get("hotkey"), trust),
            "submission_id": (
                None
                if incumbent.get("submission_id") is None
                else _text(incumbent["submission_id"], "leaderboard_invalid")
            ),
            "since_block": _int(
                incumbent.get("since_block"), "leaderboard_invalid", optional=True
            ),
            "sections": _sections(incumbent.get("sections"), digits, "incumbent"),
        }
    challengers = []
    for raw in board.get("challengers") or []:
        if type(raw) is not dict:
            raise FeedRefused("leaderboard_invalid", "challengers")
        state = raw.get("state")
        if type(state) is not str or not _STATE.fullmatch(state):
            raise FeedRefused("leaderboard_invalid", "challengers")
        challengers.append(
            {"hotkey": _hotkey(raw.get("hotkey"), trust), "state": state}
        )
    standing = []
    for raw in board.get("standing") or []:
        if type(raw) is not dict:
            raise FeedRefused("leaderboard_invalid", "standing")
        standing.append(
            {
                "rank": _int(raw.get("rank"), "leaderboard_invalid", minimum=1),
                "hotkey": _hotkey(raw.get("hotkey"), trust),
                "best": _sections(raw.get("best"), digits, "standing"),
                "best_at_block": _int(
                    raw.get("best_at_block"), "leaderboard_invalid", optional=True
                ),
            }
        )
    standing.sort(key=lambda r: (r["rank"], r["hotkey"]))
    history = {}
    raw_history = board.get("history") or {}
    if type(raw_history) is not dict:
        raise FeedRefused("leaderboard_invalid", "history")
    for hotkey, points in sorted(raw_history.items()):
        _hotkey(hotkey, trust)
        if type(points) is not list:
            raise FeedRefused("leaderboard_invalid", "history")
        kept = []
        for point in points:
            if type(point) is not dict:
                raise FeedRefused("leaderboard_invalid", "history")
            kept.append(
                {
                    "receipt_block": _int(
                        point.get("receipt_block"), "leaderboard_invalid", optional=True
                    ),
                    "sections": _sections(point.get("sections"), digits, "history"),
                }
            )
        history[hotkey] = sorted(kept, key=lambda p: p["receipt_block"] or 0)
    excluded = document.get("excluded", {})
    canaries = _int(
        excluded.get("canary_hotkeys", 0) if type(excluded) is dict else None,
        "excluded_invalid",
    )
    generated_at = document.get("generated_at")
    return {
        "schema": BOARD_SCHEMA,
        "source_schema": SCHEMA,
        "fixture": trust.fixture,
        "labels": list(labels),
        "challenge": challenge,
        "device_class": device_class,
        "slug": board_slug(challenge["id"], device_class or "no-class"),
        "version": _int(document.get("version"), "version_invalid", minimum=1),
        "released_through_block": _int(
            document.get("released_through_block"), "block_invalid", optional=True
        ),
        "generated_at": (
            None
            if generated_at is None
            else _text(generated_at, "generated_at_invalid")
        ),
        "values": values,
        "section_meta": _section_meta(document.get("sections")),
        "release": _release(document.get("release")),
        "released_windows": released,
        "incumbent": incumbent,
        "challengers": challengers,
        "standing": standing,
        "history": history,
        "miners": dict(sorted(miners.items())),
        "excluded_canaries": canaries,
        "feed": {
            "key_id": key_id(signer),
            "digest": "sha256:" + hashlib.sha256(canonical_bytes(document)).hexdigest(),
        },
    }


def board_slug(challenge_id, device_class):
    raw = f"{challenge_id}--{device_class}".lower()
    return re.sub(r"[^a-z0-9.-]+", "-", raw).strip("-")
