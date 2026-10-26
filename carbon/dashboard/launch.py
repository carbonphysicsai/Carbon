"""Read a validator's signed launch board (OWNER-DASHBOARD-01) and keep only what
may be shown.

The launch Challenges are graded on sealed exams, so they have no released
windows and no score feed. Their standing reaches the dashboard as
`carbon.validator.launch-board.v1` (`carbon.challenge_validator.launch_board`):
the king, the Ladder's best totals per hotkey, and counts, and nothing finer.
This reader is independent of the validator's code, as `feed.py` is, and
applies the disclosure rules again; it refuses the whole document when one
fails and never draws a part of one.

The checks:

1. the pinned schema and an Ed25519 signature over `DOMAIN` plus the canonical
   document without its `signature`, by a key pinned in the dashboard's trust,
   never the key the document names (`DOMAIN` is neither the feed's nor the
   network snapshot's);
2. the closed field set at every level (`launch_board.check`'s shape): any other
   key, including any section below the total, refuses the board;
3. labels: DEVELOPMENT always, TESTNET on testnet, never FIXTURE here;
4. every total in 0..1, and none finer than the Ladder step the validator
   rounded it to (the board carries only what the Ladder itself shows);
5. the counts equal the ladder's own tally.

`project` returns the board model `board_v2.project` projects (board.v1),
with one ranking section, `total`, and no released windows: the board's phase
is PRE_FIRST_RELEASE until a hotkey has a graded result. Display software
only: it ranks, nominates and promotes nothing; rank, king and statuses are the
validator's, copied as given.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

SCHEMA = "carbon.validator.launch-board.v1"
DOMAIN = b"carbon.validator.launch-board.v1\x00"
TOTAL = "total"
SECTION_META = {
    TOTAL: {
        "display": "Total score",
        "unit": "0 to 1, rounded down to the Ladder step",
        "sense": "higher_is_better",
    }
}
STATUSES = ("IMPROVED", "NO_IMPROVEMENT", "GATE_FAILED", "NOT_SCORED")
NETWORK_LABELS = {"testnet": ["DEVELOPMENT", "TESTNET"], "mainnet": ["DEVELOPMENT"]}
MAX_LADDER = 512
MAX_GATES = 16
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
_HEX_KEY = re.compile(r"[0-9a-f]{64}")
_HEX_SIGNATURE = re.compile(r"[0-9a-f]{128}")
_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}")
_GATE = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
_ID = re.compile(r"[^\x00-\x1f\x7f<>]{1,200}")
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
KING_FIELDS = frozenset({"king", "margin", "to_beat", "baseline_total"})
KING_ROW = frozenset({"hotkey", "total", "since_epoch"})
LADDER_FIELDS = frozenset({"rank", "hotkey", "total", "status", "gate_names"})


class LaunchRefused(ValueError):
    """The whole document is refused; `code` says why, for the feed health line."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical_bytes(document):
    body = {k: v for k, v in document.items() if k != "signature"}
    return (
        DOMAIN
        + json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=True,
        ).encode()
    )


def verify(document, trust):
    """The pinned hex key that signed the document, or a refusal."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    signature = document.get("signature")
    if type(signature) is not str or not _HEX_SIGNATURE.fullmatch(signature):
        raise LaunchRefused("signature_missing")
    try:
        message = canonical_bytes(document)
    except (TypeError, ValueError) as exc:
        raise LaunchRefused("not_canonical") from exc
    for public in sorted(trust.keys):
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(
                bytes.fromhex(signature), message
            )
        except InvalidSignature:
            continue
        return public
    raise LaunchRefused("signature_invalid")


def _unit(value, code, *, nullable=False):
    if value is None and nullable:
        return None
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise LaunchRefused(code)
    return float(value)


def _digits(values):
    """The fewest decimal places (at least 3) that hold every value exactly: a
    display parameter, never a finer number than the validator sent."""
    for digits in range(3, 10):
        if all(round(v, digits) == v for v in values):
            return digits
    raise LaunchRefused("total_unrounded")


def _check(document):
    if set(document) != FIELDS:
        raise LaunchRefused("board_fields")
    network = document["network"]
    if network not in NETWORK_LABELS or document["labels"] != NETWORK_LABELS[network]:
        raise LaunchRefused("labels_invalid")
    if type(document["version"]) is not int or document["version"] < 1:
        raise LaunchRefused("version_invalid")
    if type(document["generated_at"]) is not str or not _UTC.fullmatch(
        document["generated_at"]
    ):
        raise LaunchRefused("generated_at_invalid")
    challenge = document["challenge"]
    if (
        type(challenge) is not dict
        or set(challenge) != {"id", "version", "exam_version_label"}
        or any(
            type(challenge[k]) is not str or not _ID.fullmatch(challenge[k])
            for k in challenge
        )
        or not _NAME.fullmatch(challenge["version"])
        or not _LABEL.fullmatch(challenge["exam_version_label"])
    ):
        raise LaunchRefused("challenge_invalid")
    validator = document["validator"]
    if (
        type(validator) is not dict
        or set(validator) != {"feed_key"}
        or type(validator["feed_key"]) is not str
        or not _HEX_KEY.fullmatch(validator["feed_key"])
    ):
        raise LaunchRefused("validator_invalid")
    king = document["king"]
    if type(king) is not dict or set(king) != KING_FIELDS:
        raise LaunchRefused("king_invalid")
    row = king["king"]
    if row is not None:
        if (
            type(row) is not dict
            or set(row) != KING_ROW
            or type(row["hotkey"]) is not str
            or not _SS58.fullmatch(row["hotkey"])
            or type(row["since_epoch"]) is not int
            or row["since_epoch"] < 0
        ):
            raise LaunchRefused("king_invalid")
        _unit(row["total"], "king_invalid")
    for name in ("margin", "to_beat", "baseline_total"):
        _unit(king[name], "king_invalid", nullable=True)
    ladder = document["ladder"]
    if type(ladder) is not list or len(ladder) > MAX_LADDER:
        raise LaunchRefused("ladder_invalid")
    seen = set()
    tally = dict.fromkeys(STATUSES, 0)
    for entry in ladder:
        if (
            type(entry) is not dict
            or set(entry) != LADDER_FIELDS
            or type(entry["rank"]) is not int
            or entry["rank"] < 1
            or type(entry["hotkey"]) is not str
            or not _SS58.fullmatch(entry["hotkey"])
            or entry["hotkey"] in seen
            or entry["status"] not in STATUSES
        ):
            raise LaunchRefused("ladder_invalid")
        seen.add(entry["hotkey"])
        _unit(entry["total"], "ladder_invalid", nullable=True)
        gates = entry["gate_names"]
        if gates is not None and (
            entry["status"] != "GATE_FAILED"
            or type(gates) is not list
            or len(gates) > MAX_GATES
            or any(type(g) is not str or not _GATE.fullmatch(g) for g in gates)
        ):
            raise LaunchRefused("ladder_invalid")
        tally[entry["status"]] += 1
    counts = {
        "graded": len(ladder),
        "scored": tally["IMPROVED"] + tally["NO_IMPROVEMENT"],
        "gate_failed": tally["GATE_FAILED"],
        "not_scored": tally["NOT_SCORED"],
    }
    if document["counts"] != counts:
        raise LaunchRefused("counts_invalid")
    return counts


def project(document, trust):
    """Verify a launch board and return the dashboard's board model (board.v1).

    Raises LaunchRefused with a reason code; never returns a partial board.
    """
    from carbon.dashboard import feed

    if trust.fixture:
        raise LaunchRefused("fixture_launch_board")
    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise LaunchRefused("schema_unsupported")
    signer = verify(document, trust)
    counts = _check(document)
    ladder = document["ladder"]
    king = document["king"]
    totals = [e["total"] for e in ladder if e["total"] is not None]
    if king["king"] is not None:
        totals.append(king["king"]["total"])
    totals += [
        king[k] for k in ("margin", "to_beat", "baseline_total") if king[k] is not None
    ]
    digits = _digits(totals)
    challenge = document["challenge"]
    standing = [
        {
            "rank": e["rank"],
            "hotkey": e["hotkey"],
            "best": {TOTAL: e["total"]},
            "best_at_block": None,
        }
        for e in ladder
        if e["total"] is not None
    ]
    standing.sort(key=lambda r: (r["rank"], r["hotkey"]))
    incumbent = None
    if king["king"] is not None:
        incumbent = {
            "hotkey": king["king"]["hotkey"],
            "submission_id": None,
            "since_block": None,
            "sections": {TOTAL: king["king"]["total"]},
        }
    digest = "sha256:" + hashlib.sha256(canonical_bytes(document)).hexdigest()
    return {
        "schema": feed.BOARD_SCHEMA,
        "source_schema": SCHEMA,
        "fixture": False,
        "labels": list(document["labels"]),
        "challenge": {
            "id": challenge["id"],
            "version": challenge["version"],
            "rule_digest": "exam:" + challenge["exam_version_label"],
            "rule": None,
        },
        "device_class": None,
        "slug": feed.board_slug(challenge["id"], "no-class"),
        "version": document["version"],
        "released_through_block": None,
        "generated_at": document["generated_at"],
        "values": {
            "precision": 10.0**-digits,
            "digits": digits,
            "display_threshold": None,
            "registered": "launch board: the Ladder's own rounding",
        },
        "section_meta": {TOTAL: dict(SECTION_META[TOTAL])},
        "release": None,
        "as_of_block": None,
        "king": None,
        "handovers": None,
        "target_to_beat": None,
        "released_windows": [],
        # Graded hotkeys stand in for released windows: the phase is
        # PRE_FIRST_RELEASE until one hotkey has a graded result.
        "released_count": counts["graded"],
        "incumbent": incumbent,
        "challengers": [{"hotkey": e["hotkey"], "state": e["status"]} for e in ladder],
        "standing": standing,
        "ladder": None,
        "history": {},
        "miners": {},
        "excluded_canaries": 0,
        "showcase_panel": None,
        "launch": {
            "counts": counts,
            "margin": king["margin"],
            "to_beat": king["to_beat"],
            "baseline_total": king["baseline_total"],
            "king_since_epoch": (
                None if king["king"] is None else king["king"]["since_epoch"]
            ),
            "exam_version_label": challenge["exam_version_label"],
            "network": document["network"],
            "gate_names": {
                e["hotkey"]: list(e["gate_names"]) for e in ladder if e["gate_names"]
            },
        },
        "feed": {
            "key_id": feed.key_id(signer),
            "public_key": signer,
            "digest": digest,
        },
    }
