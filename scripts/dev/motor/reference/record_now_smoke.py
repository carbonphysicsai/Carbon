"""Motor record-now SMOKE (TE, 5 Nov). Run from a checkout of te/motor-record-now (scripts/dev/motor/reference/record_now_smoke.py) on a host with Docker and the motor
reference image (the one payload 9e4df7f6 pins), e.g.:

    CARBON_MOTOR_IMAGE=<the payload's carbon-motor-reference image> python -B scripts/dev/motor/reference/record_now_smoke.py --work /tmp/mrn

It solves the PUBLIC nominal design only (tests/cpu/test_motor.NOMINAL: no TRAIN, hidden or custody case) once with
the pinned `run_batch.py` and once with `run_batch_record_now.py`, then checks:
  1. both records are OK;
  2. torque_nm is BIT-IDENTICAL between them (the added print changes no solve);
  3. record_now is present, its arrays have one row per torque position, every value finite;
  4. the phase flux linkages swing (pk-pk > 0) and the magnets' least |b| is positive;
  5. coil-flux sanity: the three phase linkages sum to ~0 at every position (balanced 3-phase), reported as a ratio.
Prints ONE JSON line of booleans, counts and that ratio. Exit 0 = all of 1-4 hold.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.repo / "tests" / "cpu"))
    from test_motor import NOMINAL

    args.work.mkdir(parents=True, exist_ok=False)
    plan = args.work / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "batch": "smoke",
                "cases": [{"case_id": "smoke-nominal", "inputs": NOMINAL}],
            }
        )
    )
    records = {}
    for name, script in (
        ("pinned", "run_batch.py"),
        ("record_now", "run_batch_record_now.py"),
    ):
        out = args.work / name
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(args.repo / "scripts/dev/motor/reference" / script),
                str(plan),
                "--out",
                str(out),
                "--parallel",
                "1",
                "--keep",
                "all",
            ],
            check=True,
            cwd=args.repo,
        )
        (records[name],) = [
            json.loads(line)
            for line in (out / "records.jsonl").read_text().splitlines()
            if line.strip()
        ]
    pinned, new = records["pinned"], records["record_now"]
    kept = new.get("record_now") or {}
    positions = len(new.get("outputs", {}).get("torque_nm", []))
    values = [
        v
        for key in ("coil_flux_linkage_wb", "coil_a_integral_wbm")
        for row in kept.get(key, [])
        for v in row
    ] + list(kept.get("magnet_min_b_t", []))
    phases = kept.get("phase_flux_linkage_wb", {})
    swing = {p: (max(v) - min(v)) if v else 0.0 for p, v in phases.items()}
    peak = max(swing.values() or [0.0])
    balance = (
        max(abs(sum(phases[p][i] for p in "ABC")) for i in range(positions)) / peak
        if peak > 0 and positions
        else None
    )
    report = {
        "both_ok": pinned.get("status") == "OK" and new.get("status") == "OK",
        "torque_bit_identical": pinned.get("outputs", {}).get("torque_nm")
        == new.get("outputs", {}).get("torque_nm"),
        "outputs_keys_unchanged": set(new.get("outputs", {}))
        == set(pinned.get("outputs", {})),
        "record_now_rows_match": positions > 0
        and all(
            len(kept.get(key, [])) == positions
            for key in ("coil_flux_linkage_wb", "coil_a_integral_wbm", "magnet_min_b_t")
        ),
        "all_finite": bool(values) and all(math.isfinite(v) for v in values),
        "phase_linkage_swings": all(s > 0 for s in swing.values()) and len(swing) == 3,
        "magnet_min_b_positive": bool(kept.get("magnet_min_b_t"))
        and min(kept["magnet_min_b_t"]) > 0,
        "phase_sum_over_peak_max": balance,
        "wrapper_record_names_its_runner": (new.get("runner") or {}).get("name")
        == "record-now"
        and "runner" not in pinned
        and new.get("wall_s_basis") == "record-now runner",
        "positions": positions,
    }
    print(json.dumps({"motor_record_now_smoke": report}), flush=True)
    passed = all(
        report[k]
        for k in (
            "both_ok",
            "wrapper_record_names_its_runner",
            "torque_bit_identical",
            "outputs_keys_unchanged",
            "record_now_rows_match",
            "all_finite",
            "phase_linkage_swings",
            "magnet_min_b_positive",
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
