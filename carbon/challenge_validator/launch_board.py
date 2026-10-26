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
from pathlib import Path

from carbon.scoring import grade_feedback as gf

from .feed_file import canonical as _canonical
from .feed_file import write_feed
from .koth_public import FIELDS as KOTH_FIELDS
from .koth_public import KING_FIELDS
from .score_feed import FeedKey, FeedRefused

SCHEMA = "carbon.validator.launch-board.v1"
BOARD_DOMAIN = b"carbon.validator.launch-board.v1\x00"
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


class BoardRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class LaunchBoardKey(FeedKey):
    """The validator's feed key, signing launch boards: under `BOARD_DOMAIN`
    only, never the feed's or the snapshot's domain."""

    def __repr__(self):
        return "LaunchBoardKey(<redacted>)"

    def sign(self, document):
        return self._key.sign(BOARD_DOMAIN + _canonical(document).encode()).hex()


def _unit(value, code):
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not 0 <= value <= 1
        or not math.isfinite(value)
    ):
        raise BoardRefused(code)
    return float(value)


def _king(raw):
    """The closed king document (`koth_public.document`'s shape) or a refusal."""
    if type(raw) is not dict or set(raw) != KOTH_FIELDS:
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
            "total": _unit(king["total"], "board_king"),
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

    def optional(name):
        return None if raw[name] is None else _unit(raw[name], "board_king")

    return {
        "schema": raw["schema"],
        "challenge_id": raw["challenge_id"],
        "challenge_version": raw["challenge_version"],
        "exam_version_label": label,
        "king": king,
        "margin": optional("margin"),
        "to_beat": optional("to_beat"),
        "baseline_total": optional("baseline_total"),
    }


def ladder_rows(rows):
    """The board's ladder from `ladder_store.board_rows`: ``[(hotkey, best,
    latest)]`` with each document as the Ladder serves it. One row per hotkey:
    its best total (null before any improvement) and its latest status, ranked
    by total, highest first, equal totals sharing a rank."""
    kept = []
    for hotkey, best, latest in rows:
        if type(hotkey) is not str or not _SS58.fullmatch(hotkey):
            raise BoardRefused("board_hotkey")
        if latest is None or latest.get("status") not in gf.STATUSES:
            raise BoardRefused("board_latest")
        total = None if best is None else _unit(best["total"], "board_total")
        gates = (
            [g for g in latest["gate_names"] if type(g) is str and _GATE.fullmatch(g)]
            if latest["status"] == "GATE_FAILED"
            else None
        )
        if gates is not None and len(gates) > MAX_GATES:
            raise BoardRefused("board_gates")
        kept.append((hotkey, total, latest["status"], gates))
    kept.sort(key=lambda row: (row[1] is None, -(row[1] or 0.0), row[0]))
    out, rank, previous = [], 0, object()
    for position, (hotkey, total, status, gates) in enumerate(kept, 1):
        if total != previous:
            rank, previous = position, total
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


def build(*, king_document, rows, network, key, version, now=None):
    """The signed launch board for one Challenge.

    ``king_document`` is the receiver's `koth_public.document` (its public
    ``GET /carbon/v1/koth/<id>`` answer); ``rows`` are
    `ladder_store.board_rows`; ``key`` a `LaunchBoardKey`; ``version`` a whole
    number that grows with every build (the Worker keeps the last-good board
    when it does not)."""
    if network not in NETWORKS:
        raise BoardRefused("board_network")
    if type(version) is not int or version < 1:
        raise BoardRefused("board_version")
    king = _king(king_document)
    ladder = ladder_rows(rows)
    moment = datetime.datetime.now(datetime.UTC) if now is None else now
    document = {
        "schema": SCHEMA,
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
        "king": {
            name: king[name] for name in ("king", "margin", "to_beat", "baseline_total")
        },
        "ladder": ladder,
        "counts": counts(ladder),
    }
    check(document, unsigned=True)
    return {**document, "signature": key.sign(document)}


def check(document, *, unsigned=False):
    """The document when it has exactly the board's closed shape, else a
    `BoardRefused`: the writer's last step and the reader's first."""
    want = FIELDS - ({"signature"} if unsigned else set())
    if type(document) is not dict or set(document) != want:
        raise BoardRefused("board_fields")
    if document["schema"] != SCHEMA or document["network"] not in NETWORKS:
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
    if type(king) is not dict or set(king) != {
        "king",
        "margin",
        "to_beat",
        "baseline_total",
    }:
        raise BoardRefused("board_king")
    _king(
        {
            "schema": "carbon.koth.public.v1",
            "challenge_id": challenge["id"],
            "challenge_version": challenge["version"],
            "exam_version_label": challenge["exam_version_label"],
            **king,
        }
    )
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
            BOARD_DOMAIN + _canonical(body).encode(),
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="launch_board")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--config", required=True, type=Path)
    make.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = _config(args.config)
        from .ladder_store import board_rows

        challenge = type(
            "Challenge",
            (),
            {
                "challenge_id": config["challenge"]["id"],
                "version": config["challenge"]["version"],
            },
        )()
        king = json.loads(Path(config["koth"]).read_text(encoding="utf-8"))
        rows = board_rows(config["ledger"], challenge, config["exam_key"])
        key = LaunchBoardKey.load(config["key"])
        version = config.get("version")
        if version is None:
            version = int(datetime.datetime.now(datetime.UTC).timestamp())
        write_feed(
            args.out,
            build(
                king_document=king,
                rows=rows,
                network=config["network"],
                key=key,
                version=version,
            ),
        )
    except (BoardRefused, FeedRefused, OSError, ValueError, KeyError) as error:
        print("launch board refused:", getattr(error, "code", type(error).__name__))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
