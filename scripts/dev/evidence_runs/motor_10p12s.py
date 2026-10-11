"""Registered evidence entrypoint: motor 10p/12s (EVIDENCE-ENTRYPOINTS-01).

    python -m scripts.dev.evidence_runs.motor_10p12s check --kind train-stage1
    python -m scripts.dev.evidence_runs.motor_10p12s solve --kind train-stage1 --out DIR [--parallel N]
    python -m scripts.dev.evidence_runs.motor_10p12s export-train --runs DIR --out FILE.jsonl

- **Plan** (committed, sha256-bound): `train-stage1`, the public TRAIN stage 1
  of OWNER-MOTOR-TRAIN-GRANT-01, i.e. 128 geometries (12 axis anchors + LHS,
  each >= 0.10 from the 43 panel/study designs) x the panel's 11-solve bundle
  = 1,408 cases. #1035's support check covers 44/44 panel rows.
- **Solver:** the pinned motor reference image (GetDP 3.5.0, Gmsh 4.15.2,
  `carbon-motor-reference@sha256:599521e7...`) through
  `scripts.dev.motor.feasibility02.run`, 2 CPUs per case, flux observers on.
- **Output:** `<out>/records.jsonl`, one `carbon.motor.feasibility02-record.v1`
  per case: the signed torque curve over 12 deg (48 samples at 0.25 deg),
  co-energy, RMS |B| per region, phase current, deck sha256, checks.
- **export-train:** `carbon.motor-10p12s.train-record.v1` JSONL for the
  10p/12s kit (#1035): inputs = the six grammar coordinates + `j_a_mm2` +
  `gamma_deg`, outputs `t00`..`t47` (the signed curve), `source` naming this
  TRAIN set. Non-OK cases are excluded and counted. Prints the sha256.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.dev.evidence_runs import common

IMAGE_REF = "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
IMAGE_DIGEST = "sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
PLANS = {
    "train-stage1": ("docs/development/evidence/motor-feasibility-02/plans/train-stage1-plan.json",
                     "4a067614ee921d20069504937e3913cebb30226cafe35c489d3a9356a2f4f2cd"),
}  # fmt: skip
TRAIN_SCHEMA = "carbon.motor-10p12s.train-record.v1"
GRAMMAR = (
    "magnet_mm",
    "coverage",
    "airgap_mm",
    "tooth_frac",
    "opening_frac",
    "slot_bottom_mm",
)
SAMPLES = 48
SOURCE = "motor 10p/12s public TRAIN stage 1 (OWNER-MOTOR-TRAIN-GRANT-01; registry motor-feasibility-02 train_stage1)"


def check(kind, inspect=None):
    path, sha = PLANS[kind]
    plan = common.require_plan(path, sha)
    common.require_image(IMAGE_REF, IMAGE_DIGEST, inspect)
    return plan


def solve(kind, out, parallel):
    plan = check(kind)
    env = {**os.environ, "CARBON_MOTOR_IMAGE": IMAGE_REF}
    cmd = [sys.executable, "-m", "scripts.dev.motor.feasibility02.run", str(plan), "--out", str(out),
           "--parallel", str(parallel), "--timeout-s", "43200"]  # fmt: skip
    return subprocess.run(cmd, cwd=common.ROOT, env=env, check=False).returncode


def train_record(record):
    """One kit TRAIN record (None when the case is not OK or off the grid)."""
    out = record.get("outputs") or {}
    curve = out.get("torque_nm")
    if record.get("status") != "OK" or not curve:
        return None
    if (
        len(curve) == 2 * SAMPLES
    ):  # a rung-2 curve: every other sample is the 0.25-deg grid
        curve = curve[::2]
    if len(curve) != SAMPLES:
        return None
    return {
        "schema": TRAIN_SCHEMA,
        "case_id": record["case_id"],
        "inputs": {**{k: record["design"][k] for k in GRAMMAR}, "j_a_mm2": record["j_a_mm2"],
                   "gamma_deg": record["gamma_deg"]},
        "outputs": {f"t{i:02d}": float(v) for i, v in enumerate(curve)},
        "source": SOURCE,
    }  # fmt: skip


def export_train(runs, out):
    records = common.read_jsonl(Path(runs) / "records.jsonl")
    latest = {}
    for r in records:  # an OK record is never displaced by a later failed one
        if latest.get(r["case_id"], {}).get("status") != "OK":
            latest[r["case_id"]] = r
    rows = [
        t
        for t in map(train_record, (latest[k] for k in sorted(latest)))
        if t is not None
    ]
    sha = common.write_jsonl(out, rows)
    return {
        "cases": len(latest),
        "exported": len(rows),
        "excluded": len(latest) - len(rows),
        "sha256": sha,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="evidence_runs.motor_10p12s", description=__doc__.split("\n")[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--kind", choices=sorted(PLANS), required=True)
    s = sub.add_parser("solve")
    s.add_argument("--kind", choices=sorted(PLANS), required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--parallel", type=int, default=2)
    e = sub.add_parser("export-train")
    e.add_argument("--runs", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "check":
            print(
                json.dumps(
                    {
                        "plan": str(check(args.kind)),
                        "image": IMAGE_DIGEST,
                        "status": "OK",
                    }
                )
            )
            return 0
        if args.cmd == "solve":
            return solve(args.kind, args.out, args.parallel)
        print(json.dumps(export_train(args.runs, args.out)))
        return 0
    except common.Refused as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
