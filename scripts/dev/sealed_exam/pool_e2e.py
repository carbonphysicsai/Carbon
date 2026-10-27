#!/usr/bin/env python3
"""Evidence of the sealed pool-grade path for ONE graded submission, read from the receiver's private evaluation
directory (run by a lane with access to the grading host; reads only, writes nothing, prints digests and verdicts).

    python scripts/dev/sealed_exam/pool_e2e.py verify --eval-dir <receiver private evaluation dir of the task> \
        --pack-root <evaluation pack root> --challenge-id electric-motor-magnetics --version 1.5

The chain it checks, from what the receiver wrote (nothing is re-graded):

    receiver -> rebuild -> graded inference -> pool rows -> grader + physics gates + speed -> dual measurement
    (dual-measurement.json, inference-pair.json, single-call.json, evaluation-pack-binding.json)

- the measurement is bound to this pack (its evaluation_pack_digest equals the pack manifest's digest);
- the pack's score pack lists both pool gates (physics_pool, speed) among its hard gates, and the measurement
  carries a verdict for every one of them;
- the single-call side file is well formed (20 positive finite seconds), its median is compared with the version's
  registered ceiling (the same arithmetic as the gate), and the timed outputs matched the graded run;
- A, D and the total (0.5 A + 0.5 D, D capped by C inside the grade) as the measurement holds them.

The KOTH comparison and the weights preview are separate, existing commands (printed under "next"); the burn is
expected until the recalibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FILES = (
    "dual-measurement.json",
    "dual-measurement-registration.json",
    "inference-pair.json",
    "single-call.json",
    "evaluation-pack-binding.json",
)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _json(path):
    return json.loads(Path(path).read_bytes())


def verify(eval_dir, pack_root, challenge_id, version):
    """The evidence record (digests and verdicts only) of one graded submission."""
    from carbon.challenge_registry import speed_gate
    from carbon.development_session import single_call_timing
    from carbon.scoring import pool_exam

    eval_dir, pack_root = Path(eval_dir), Path(pack_root)
    problems, record = [], {"challenge": challenge_id, "version": version}
    present = {n: (eval_dir / n) for n in FILES if (eval_dir / n).is_file()}
    record["files"] = {n: _sha(p.read_bytes()) for n, p in present.items()}
    for needed in ("dual-measurement.json", "single-call.json", "inference-pair.json"):
        if needed not in present:
            problems.append(f"missing:{needed}")

    manifest_path = pack_root / "evaluation-pack.json"
    manifest = _json(manifest_path) if manifest_path.is_file() else None
    pack_digest = _sha(manifest_path.read_bytes()) if manifest else None
    record["pack_manifest_digest"] = pack_digest

    score_pack = None
    if manifest:
        try:
            score_pack = _json(pack_root / manifest["private"]["score_pack"]["path"])
        except (KeyError, OSError, ValueError):
            problems.append("score_pack_unreadable")
    gates = list(score_pack["hard_gates"]) if score_pack else []
    record["pool_gates_in_the_pack"] = [
        g for g in (pool_exam.PHYSICS_GATE, pool_exam.SPEED_GATE) if g in gates
    ]
    if set(record["pool_gates_in_the_pack"]) != {
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
    }:
        problems.append("pack_is_not_pool_graded")

    if "dual-measurement.json" in present:
        measurement = _json(present["dual-measurement.json"])
        record["bound_to_this_pack"] = (
            pack_digest is not None
            and measurement.get("evaluation_pack_digest") == pack_digest
        )
        if not record["bound_to_this_pack"]:
            problems.append("measurement_not_bound_to_this_pack")
        record["producer_digest"] = measurement.get("producer_digest")
        model = (measurement.get("benchmark") or {}).get("models", [{}])[0]
        verdicts = model.get("gates") or {}
        record["gate_verdicts"] = dict(sorted(verdicts.items()))
        missing = [g for g in gates if g not in verdicts]
        if missing:
            problems.append("no_verdict_for:" + ",".join(missing))
        measurements = {
            k: v["value"]
            for k, v in (model.get("measurements") or {}).items()
            if isinstance(v, dict) and "value" in v
        }
        record["measurements"] = dict(sorted(measurements.items()))
        a = measurements.get("robust_fidelity_benefit")
        d = measurements.get("verified_value_benefit")
        record["A"], record["D"] = a, d
        record["total"] = (
            0.5 * a + 0.5 * d
            if isinstance(a, (int, float)) and isinstance(d, (int, float))
            else None
        )
        record["decision_outcome"] = model.get("decision_outcome")

    if "single-call.json" in present:
        try:
            seconds, match = single_call_timing.read_side_file(
                present["single-call.json"].read_bytes()
            )
            ceiling = speed_gate.ceiling_seconds(challenge_id)
            record["speed"] = {
                "calls": len(seconds),
                "median_seconds": statistics.median(seconds),
                "max_seconds": max(seconds),
                "ceiling_seconds_per_design": ceiling,
                "median_within_ceiling": statistics.median(seconds) <= ceiling,
                "timed_outputs_equal_the_graded_run": match,
            }
        except single_call_timing.SingleCallRefused as refused:
            problems.append("single_call:" + refused.code)
        verdict = record.get("gate_verdicts", {}).get(pool_exam.SPEED_GATE)
        speed = record.get("speed")
        if speed and verdict is not None:
            expected = (
                "PASS"
                if speed["median_within_ceiling"]
                and speed["timed_outputs_equal_the_graded_run"]
                else "FAIL"
            )
            record["speed_gate_matches_the_side_file"] = verdict == expected
            if verdict != expected:
                problems.append("speed_verdict_differs_from_the_side_file")

    record["problems"] = problems
    record["verdict"] = "CONSISTENT" if not problems else "INCONSISTENT"
    record["next"] = (
        "KOTH + weights: python -m carbon.validator_setup <weights action> preview --lean-pool <pool store> ... "
        "(carbon/rewards/weight_policies/testnet-winner-v4-launch.json; all burn until the recalibration)"
    )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("verify")
    for flag in ("eval-dir", "pack-root", "challenge-id", "version"):
        one.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    record = verify(args.eval_dir, args.pack_root, args.challenge_id, args.version)
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0 if record["verdict"] == "CONSISTENT" else 3


if __name__ == "__main__":
    raise SystemExit(main())
