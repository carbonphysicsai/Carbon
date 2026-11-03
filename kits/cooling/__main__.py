"""`python -m kits.cooling`: the Cooling data kit's commands.

    python -m kits.cooling build                   # pull the solver image by its pinned digest
    python -m kits.cooling licences                # every licence in the image
    python -m kits.cooling range                   # the internal range the kit samples
    python -m kits.cooling generate --n 50 --seed 7 --out DIR [--parallel 4] [--cpus 2]
    python -m kits.cooling generate --nominal --out DIR
    python -m kits.cooling generate --plan CASES.json --out DIR
    python -m kits.cooling parse DIR               # DIR/train.npz + DIR/train.provenance.json
    python -m kits.cooling check DIR/train.npz     # read it back: shapes and finiteness
    python -m kits.cooling cost DIR                # wall time, memory and cores per case
    python -m kits.cooling verify --out DIR        # the verify set, compared within U
    python -m kits.cooling score DIR --predictions PRED.json   # the practice score

Results may differ from Carbon's pinned reference, which alone grades.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from . import kit

#: Prints OpenFOAM's licence files and every package the image holds
#: (amendment A7).
_LICENCES = (
    "for f in $(find /usr/lib/openfoam /opt -maxdepth 4 -type f "
    "\\( -iname 'COPYING*' -o -iname 'LICENSE*' \\) 2>/dev/null); "
    'do echo "== $f"; cat "$f"; done; '
    'echo "== packages (licence in /usr/share/doc/<package>/copyright)"; '
    "dpkg-query -W -f '${Package} ${Version}\\n'"
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m kits.cooling", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="pull the solver image by its pinned digest")
    sub.add_parser("licences", help="every licence in the image")
    sub.add_parser("range", help="print the internal range the kit samples")
    gen = sub.add_parser("generate", help="draw and solve cases")
    pick = gen.add_mutually_exclusive_group(required=True)
    pick.add_argument("--n", type=int)
    pick.add_argument("--nominal", action="store_true")
    pick.add_argument("--plan", type=Path)
    gen.add_argument("--seed", type=int, default=0)
    _run_options(gen)
    gen.add_argument(
        "--keep", action="store_true", help="keep each case's solver files"
    )
    parse = sub.add_parser("parse", help="write the TRAIN-format files")
    parse.add_argument("dir", type=Path)
    check = sub.add_parser("check", help="read a TRAIN-format npz back")
    check.add_argument("npz", type=Path)
    cost = sub.add_parser("cost", help="each case's wall time, memory and cores")
    cost.add_argument("dir", type=Path)
    verify = sub.add_parser("verify", help="run the verify set; compare within U")
    _run_options(verify)
    verify.add_argument("--verify-set", type=Path, default=kit.VERIFY_SET)
    score = sub.add_parser("score", help="the practice score of your predictions")
    score.add_argument("dir", type=Path)
    score.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except kit.KitError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


def _run_options(sub):
    sub.add_argument("--out", type=Path, required=True)
    sub.add_argument("--parallel", type=int, default=1)
    sub.add_argument("--cpus", type=float, default=2.0)
    sub.add_argument("--timeout-s", type=float, default=14400.0)


def _records(directory):
    path = kit.refuse_protected(directory) / "records.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run(args):
    if args.command == "build":
        command = ["docker", "pull", kit.IMAGE]
        print(" ".join(command), flush=True)
        return subprocess.run(command, check=False).returncode
    if args.command == "licences":
        command = ["docker", "run", "--rm", "--network", "none", kit.IMAGE]
        return subprocess.run(
            [*command, "bash", "-c", _LICENCES], check=False
        ).returncode
    if args.command == "range":
        print(json.dumps(kit.internal_range(), indent=2))
        return 0
    run = {
        "parallel": getattr(args, "parallel", 1),
        "cpus": getattr(args, "cpus", 2.0),
        "timeout_s": getattr(args, "timeout_s", 14400.0),
    }
    if args.command == "generate":
        if args.nominal:
            cases = kit.nominal()
        elif args.plan is not None:
            plan = kit.refuse_protected(args.plan)
            cases = json.loads(plan.read_text(encoding="utf-8"))["cases"]
        else:
            cases = kit.sample(args.n, args.seed)
        records = kit.generate(cases, args.out, keep=args.keep, **run)
        ok = sum(1 for r in records if r["status"] == "OK")
        print(
            f"{ok} of {len(records)} cases OK; records in {args.out / 'records.jsonl'}"
        )
        return 0 if ok == len(records) else 1
    if args.command == "parse":
        raw, provenance = kit.parse(args.dir / "records.jsonl")
        kit.write_output(args.dir, "train.npz", raw)
        kit.write_output(
            args.dir,
            "train.provenance.json",
            json.dumps(provenance, indent=1, sort_keys=True) + "\n",
        )
        print(
            f"{len(provenance['case_ids'])} cases -> {args.dir / 'train.npz'}; "
            f"skipped {provenance['skipped']}"
        )
        return 0
    if args.command == "check":
        arrays = kit.read_npz(kit.refuse_protected(args.npz))
        for name, (shape, rows) in sorted(arrays.items()):
            finite = all(math.isfinite(v) for row in rows for v in row)
            print(f"{name}: shape {shape}, all finite: {finite}")
        return 0
    if args.command == "cost":
        for row in _records(args.dir):
            print(row["case_id"], row["status"], json.dumps(row.get("cost")))
        return 0
    if args.command == "verify":
        report = kit.verify(args.out, path=args.verify_set, **run)
        print(
            "VERIFY PASS"
            if report["pass"]
            else "VERIFY FAIL: do not train on this data until it passes"
        )
        return 0 if report["pass"] else 1
    if args.command == "score":
        predictions = json.loads(
            kit.refuse_protected(args.predictions).read_text(encoding="utf-8")
        )
        result = kit.score(_records(args.dir), predictions)
        kit.write_output(args.dir, "score.json", json.dumps(result, indent=1) + "\n")
        print(f"{result['label']} (never an exam score or grade)")
        print(json.dumps({k: result[k] for k in ("gates", "accuracy")}, indent=1))
        for part in ("design_value", "minimums", "information_budget"):
            print(f"{part}: {result[part]}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
