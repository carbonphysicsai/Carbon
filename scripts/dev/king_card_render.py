"""Render the PUBLIC king card from the crowning grade's private grade breakdown (`carbon.challenge_validator.crown_card`,
Validator-2's standing ruling KING_STATS_DISCLOSURE_20261119). Operator tool: read-only on the breakdown.

    python scripts/dev/king_card_render.py --breakdown <dir>/<task>.grade-breakdown.json --crowned-task <task>
        --source official|recomputed [--self-check-matched --graded-at 2026-11-18T10:00:00Z]
        --epoch E1 --pack-id <public pack id> --code-sha <sha>
        --lane-class <lane>=<host-class record.json> [--lane-class ...] --out <dir>

The public output and class names are read from the PUBLIC registration of this checkout (`pool_version.CONSTANTS`,
the served pool constants; V2 19 Nov), never typed. Each ``--lane-class`` names one speed lane (``local`` or the
lane's docker host, as its grade_lane line says) and the host-class record of that lane's machine; the card shows the
record's device class name, never the host, and a lane with no record refuses. ``--out`` is an existing owner-only
directory; it receives ``king-card.json`` and ``king-card.txt`` (public, for the owner's sign-off) and
``king-card-receipt.json`` (operator-only: which breakdown file, the registration and record files, all sha256).
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
    parser.add_argument("--lane-class", action="append", default=[])
    # a lane no host-class record was measured for: its label is the closed "class not recorded" (V2 19 Nov)
    parser.add_argument("--lane-unrecorded", action="append", default=[])
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
    from carbon.challenge_validator import crown_card as king_card
    from carbon.scoring import pool_version

    try:
        out = _out_dir(args.out)
        raw = _read(args.breakdown, "breakdown_unreadable")
        document = json.loads(raw)
        if type(document) is not dict:
            raise Refused("breakdown_unreadable")
        registration_path = Path(pool_version.CONSTANTS).resolve()
        registration = _read(registration_path, "registration_unreadable")
        outputs, classes = king_card.public_names(
            registration,
            document.get("challenge_id"),
            document.get("challenge_version"),
        )
        lane_classes, lanes = {}, {}
        for item in args.lane_class:
            lane, sep, path = item.partition("=")
            if not sep or not lane or lane in lane_classes:
                raise Refused("lane_class_argument_invalid")
            record = _read(path, "lane_class_record_unreadable")
            lane_classes[lane] = king_card.lane_class(record)
            lanes[lane] = {
                "file": str(Path(path).resolve()),
                "sha256": king_card._sha256(record),
            }
        for lane in args.lane_unrecorded:
            if not lane or lane in lane_classes:
                raise Refused("lane_class_argument_invalid")
            lane_classes[lane] = king_card.UNRECORDED_CLASS
            lanes[lane] = {"file": None, "sha256": None}
        card = king_card.render(
            document,
            crowned_task=args.crowned_task,
            source=args.source,
            self_check_matched=args.self_check_matched,
            graded_at=args.graded_at,
            epoch=args.epoch,
            pack_id=args.pack_id,
            code_sha=args.code_sha,
            public_outputs=outputs,
            public_classes=classes,
            lane_classes=lane_classes,
        )
        receipt = king_card.receipt(
            card,
            Path(args.breakdown).resolve(),
            raw,
            args.crowned_task,
            registration={
                "file": str(registration_path),
                "sha256": king_card._sha256(registration),
                "outputs": outputs,
                "classes": classes,
            },
            lanes=lanes,
        )
        names = ("king-card.json", "king-card.txt", "king-card-receipt.json")
        if any((out / name).exists() for name in names):
            raise Refused("out_files_exist")
        _write_new(out / names[0], king_card.dumps(card))
        _write_new(out / names[1], king_card.text(card).encode())
        _write_new(
            out / names[2],
            json.dumps(receipt, sort_keys=True, indent=1).encode() + b"\n",
        )
    except Exception as exc:  # noqa: BLE001 - a typed code only, never a message
        code = getattr(exc, "code", None)
        print("refused:" + (code if type(code) is str else type(exc).__name__))
        return 3
    print(receipt["card_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
