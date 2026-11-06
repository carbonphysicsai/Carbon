"""Write or check a version's sealed headroom admission document (HEADROOM_SCORING_PLAN rev 2; EQ 6 Nov: the TL writes
it at freeze, in custody, from the Validator's verdicts; the Validator signs its sha; the sha is registered in the pack).

    python scripts/dev/headroom_admission.py write --draft DRAFT.json --out ADMISSION.json \\
        --h-min 4 --h-lo 2.5 --n-min 12
    python scripts/dev/headroom_admission.py check ADMISSION.json --h-min 4 --h-lo 2.5 --n-min 12

DRAFT.json has the document's own shape (`pool_physics_score.HEADROOM_SCHEMA`): ``families`` {family: [class, ...]}
and ``cells`` [{family, class, output, anchor_u, anchor_lo_u, n, tests: {H, C, O, R, V: PASS | FAIL}}]. ``write``
validates it exactly as the grader will (`pool_physics_score.headroom_admission`, under the thresholds given, which must
be the version's registered ones), writes the canonical bytes owner-only, and prints the sha256 and COUNTS only (cells,
admitted, not admitted). It never prints an anchor or a class name: the document is custody material.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carbon.scoring import pool_physics_score as pps


def _rule(args):
    return SimpleNamespace(h_min=args.h_min, h_lo=args.h_lo, n_min=args.n_min)


def _summary(admission, raw):
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "cells": len(admission.scored) + len(admission.not_admitted),
        "admitted": len(admission.scored),
        "not_admitted": len(admission.not_admitted),
        "families": len(admission.families),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="headroom_admission")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("write", "check"):
        command = commands.add_parser(name)
        if name == "write":
            command.add_argument("--draft", required=True, type=Path)
            command.add_argument("--out", required=True, type=Path)
        else:
            command.add_argument("document", type=Path)
        command.add_argument("--h-min", required=True, type=float)
        command.add_argument("--h-lo", required=True, type=float)
        command.add_argument("--n-min", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        source = args.draft if args.command == "write" else args.document
        document = json.loads(source.read_text(encoding="utf-8"))
        admission = pps.headroom_admission(
            (
                {**document, "schema": pps.HEADROOM_SCHEMA}
                if args.command == "write"
                else document
            ),
            _rule(args),
        )
    except (OSError, ValueError) as error:
        print("refused:", getattr(error, "args", [type(error).__name__])[0])
        return 1
    if args.command == "check":
        raw = source.read_bytes()
        if raw != pps.cell_map_bytes(document):
            print("refused: not_canonical_bytes")
            return 1
        print(json.dumps(_summary(admission, raw)))
        return 0
    raw = pps.cell_map_bytes({**document, "schema": pps.HEADROOM_SCHEMA})
    if args.out.exists():
        print(
            "refused: out_exists"
        )  # write-once: a sealed admission is never overwritten
        return 1
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
    print(json.dumps(_summary(admission, raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
