#!/usr/bin/env python3
"""F02 2.5 response references from the solver's own truth at the SEALED probes (custody).

OWNER-MOTOR-SHEET-AND-F02-EXPONENT-01 (owner "1 and a"): F02's registered on-time exponent is a global-fit defect, so
F02 2.5's response leg anchors the on-time reference on the solver's local slope per probe group (same band). The
probes are the sealed batch's own, so their truths exist only after a solver run in custody:

    python scripts/dev/sealed_exam/f02_response_reference.py plan  --batch-dir A --out probes.json
        the sealed bank's probe points (case id + inputs, custody only) for the solver job;
    python scripts/dev/sealed_exam/f02_response_reference.py build --batch-dir A --truth truth.json --out ref.json
        truth.json = {probe case id: [peak]} from the solver; ref.json = the pool material's `response_reference`
        ({"input": "on_time_s", "by_base": {probe base: local slope}}), which pool_pack.py takes as
        --response-reference.

A.batch-dir is the plain F02 A batch (the predecessor's registered sealed batch, `sealed-batch.json`). Nothing is
graded and nothing is signed; a truth file that does not cover every probe exactly is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHALLENGE = "f02"
VERSION = "2.5"


def probe_rows(batch_dir):
    """The sealed bank's probe rows (bank row dicts) of the plain A batch."""
    from carbon.challenge_kit.version_registry import find
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import practice_grid, probe_design
    from carbon.scoring import sealed_batch_source as source

    carried = source.read_batch(batch_dir)
    if carried is None:
        raise SystemExit("--batch-dir has no sealed-batch.json")
    document, records = carried
    if "pool" in document:
        raise SystemExit("give the plain A batch (no pool material)")
    kit = source._kit(CHALLENGE)
    predecessor = find(CHALLENGE, VERSION).predecessor
    bank = source._build(CHALLENGE, kit, document, records, predecessor)
    names = practice_grid.input_names(CHALLENGE, VERSION)
    rows = physical.bank_rows(bank, names)
    return [r for r in rows if r["cohort"] == probe_design.PROBE_COHORT]


def build_reference(rows, truth):
    """The `response_reference` of the pool material from the solver's ``truth`` ({case id: [peak]})."""
    from carbon.scoring import f02_physics

    if type(truth) is not dict or set(truth) != {r["case_id"] for r in rows}:
        raise SystemExit("the truth file must cover exactly the sealed probes")
    peaks = []
    for row in rows:
        value = truth[row["case_id"]]
        if type(value) is not list or len(value) != 1:
            raise SystemExit("each truth is the width-1 peak row")
        peaks.append(float(value[0]))
    return {
        "input": "on_time_s",
        "by_base": f02_physics.local_slopes(rows, peaks, "on_time_s"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--batch-dir", required=True)
    plan.add_argument("--out", required=True)
    build = sub.add_parser("build")
    build.add_argument("--batch-dir", required=True)
    build.add_argument("--truth", required=True)
    build.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    rows = probe_rows(args.batch_dir)
    if args.command == "plan":
        document = {
            "schema": "carbon.f02.sealed-probe-plan.v1",
            "version": VERSION,
            "probes": {r["case_id"]: r["inputs"] for r in rows},
        }
        Path(args.out).write_text(
            json.dumps(document, sort_keys=True, indent=1) + "\n", encoding="utf-8"
        )
        print(json.dumps({"probes": len(rows), "out": args.out}))
        return 0
    truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    reference = build_reference(rows, truth)
    Path(args.out).write_text(
        json.dumps(reference, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    slopes = list(reference["by_base"].values())
    print(
        json.dumps(
            {
                "groups": len(slopes),
                "slope_min": min(slopes),
                "slope_max": max(slopes),
                "out": args.out,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
