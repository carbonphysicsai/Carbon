"""Render the PUBLIC king card from the crowning grade's private grade breakdown (`carbon.challenge_validator.king_card`,
Validator-2's standing ruling KING_STATS_DISCLOSURE_20261119). Operator tool: read-only on the breakdown.

    python scripts/dev/king_card_render.py --breakdown <dir>/<task>.grade-breakdown.json --crowned-task <task>
        --source official|recomputed [--self-check-matched --graded-at 2026-11-18T10:00:00Z]
        --epoch E1 --pack-id <public pack id> --code-sha <sha> --public <public.json> --out <dir>

``--public`` is a JSON file ``{"outputs": [...], "classes": [...], "lane_classes": {lane: label}}``: the public
registration's output and class names, and the public class label of each speed lane (V2 names them; a lane it does
not name refuses). ``--out`` is an existing owner-only directory; it receives ``king-card.json`` and ``king-card.txt``
(public, for the owner's sign-off) and ``king-card-receipt.json`` (operator-only: which breakdown file, its sha256).
Exit 0 with the card's sha256 printed; 3 refused with a typed code (nothing written).
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 262144


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--crowned-task", required=True)
    parser.add_argument("--source", required=True, choices=("official", "recomputed"))
    parser.add_argument("--self-check-matched", action="store_true")
    parser.add_argument("--graded-at", default=None)
    parser.add_argument("--epoch", required=True)
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--public", required=True)
    parser.add_argument("--out", required=True)
    return parser


class Refused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _read(path, code):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_BYTES:
        raise Refused(code)
    return target.read_bytes()


def _out_dir(path):
    selected = Path(path)
    if (
        not selected.is_absolute()
        or selected.is_symlink()
        or not selected.is_dir()
        or (os.name == "posix" and stat.S_IMODE(selected.stat().st_mode) & 0o077)
    ):
        raise Refused("out_dir_not_owner_only")
    return selected


def _write_new(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def main(argv=None):
    args = _parser().parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from carbon.challenge_validator import king_card

    try:
        out = _out_dir(args.out)
        raw = _read(args.breakdown, "breakdown_unreadable")
        public = json.loads(_read(args.public, "public_unreadable"))
        if type(public) is not dict or set(public) != {"outputs", "classes", "lane_classes"}:
            raise Refused("public_invalid")
        card = king_card.render(
            json.loads(raw),
            crowned_task=args.crowned_task,
            source=args.source,
            self_check_matched=args.self_check_matched,
            graded_at=args.graded_at,
            epoch=args.epoch,
            pack_id=args.pack_id,
            code_sha=args.code_sha,
            public_outputs=public["outputs"],
            public_classes=public["classes"],
            lane_classes=public["lane_classes"],
        )
        receipt = king_card.receipt(card, Path(args.breakdown).resolve(), raw, args.crowned_task)
        names = ("king-card.json", "king-card.txt", "king-card-receipt.json")
        if any((out / name).exists() for name in names):
            raise Refused("out_files_exist")
        _write_new(out / names[0], king_card.dumps(card))
        _write_new(out / names[1], king_card.text(card).encode())
        _write_new(out / names[2], json.dumps(receipt, sort_keys=True, indent=1).encode() + b"\n")
    except Exception as exc:  # noqa: BLE001 - a typed code only, never a message
        code = getattr(exc, "code", None)
        print("refused:" + (code if type(code) is str else type(exc).__name__))
        return 3
    print(receipt["card_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
