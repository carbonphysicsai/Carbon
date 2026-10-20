#!/usr/bin/env python3
"""Battery B15: a public DEVELOPMENT probe plan for the exposed bank.

The adopted B15 gate (OWNER-PHYSICS-GATES-01, `carbon.battery.physics_gate`)
reads one registered probe plan. The only plan so far is operator-pinned and
uncommitted, so the gate cannot run on the exposed DEVELOPMENT bank. This
writes a public plan from the same generator the contract module provides
(`physics_contract.probe_pairs`: a uniform point in the probe region and its
partner moved up by B15's 0.05 step along c1 or c2), under a new public seed.
No references are needed: the gate reads only model predictions on the pairs.
The sealed exam keeps its private draw.

The plan file has exactly the three fields the gate accepts, so the seed and
count live in the sidecar provenance file, which also records the plan's
sha256.

    python3 scripts/dev/battery/b15_public_probes.py write --count N OUT_DIR
    python3 scripts/dev/battery/b15_public_probes.py host-check OPERATOR_PLAN

`host-check` runs on the operator host. It draws the public plan at the
operator plan's own pair count (the count is the only thing it takes from
that plan) and prints the count, the overlap and the public plan's sha256,
never a probe point, so the operator plan stays private. The committed plan
is then written locally with that count and must reproduce the same sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

from carbon.battery import physics_gate as gate
from carbon.challenge_validator import physics_contract as pc

PUBLIC_SEED = "carbon-battery-b15-public-development-20261020"
PROVENANCE_SCHEMA = "carbon.battery.physics-probes-public-provenance.v1"


def _contract():
    raw = (REPOSITORY / gate.CONTRACT).read_bytes()
    return raw, json.loads(raw)


def plan(count: int) -> tuple[bytes, dict]:
    """The public plan bytes and their provenance, deterministic in `count`."""
    raw, contract = _contract()
    law = next(law for law in contract["laws"] if law["id"] == "B15")
    pairs = [
        {"axis": axis, "base": base, "partner": partner}
        for axis, base, partner, _step in pc.probe_pairs(
            contract, law, seed=PUBLIC_SEED, count=count
        )
    ]
    if {p["axis"] for p in pairs} != set(law["inputs"]):
        raise SystemExit("refused: the draw does not cover both axes")
    body = {
        "schema": gate.PROBE_SCHEMA,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "pairs": pairs,
    }
    plan_raw = json.dumps(body, sort_keys=True, indent=1).encode() + b"\n"
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "law": "B15",
        "contract": gate.CONTRACT,
        "contract_sha256": body["contract_sha256"],
        "generator": "carbon.challenge_validator.physics_contract.probe_pairs",
        "seed": PUBLIC_SEED,
        "count": count,
        "axes": {a: sum(p["axis"] == a for p in pairs) for a in law["inputs"]},
        "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "references_needed": False,
        "sealed_exam": "keeps its private operator draw; this plan is not it",
    }
    return plan_raw, provenance


def _keys(body):
    region = sorted(_contract()[1]["probe_region"])
    pairs = {
        (p["axis"], *(p["base"][k] for k in region), *(p["partner"][k] for k in region))
        for p in body["pairs"]
    }
    points = {
        tuple(p[side][k] for k in region)
        for p in body["pairs"]
        for side in ("base", "partner")
    }
    return pairs, points


def disjoint(operator_raw: bytes, public_raw: bytes) -> dict:
    operator, public = json.loads(operator_raw), json.loads(public_raw)
    (op_pairs, op_points), (pub_pairs, pub_points) = _keys(operator), _keys(public)
    return {
        "operator_pairs": len(operator["pairs"]),
        "public_pairs": len(public["pairs"]),
        "shared_pairs": len(op_pairs & pub_pairs),
        "shared_points": len(op_points & pub_points),
        "operator_contract_matches": operator.get("contract_sha256")
        == public.get("contract_sha256"),
        "public_plan_sha256": hashlib.sha256(public_raw).hexdigest(),
        "disjoint": not (op_pairs & pub_pairs) and not (op_points & pub_points),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write")
    write.add_argument("--count", type=int, required=True)
    write.add_argument("out", type=Path)
    check = sub.add_parser("host-check")
    check.add_argument("operator_plan", type=Path)
    args = parser.parse_args(argv)
    if args.command == "write":
        plan_raw, provenance = plan(args.count)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "plan.json").write_bytes(plan_raw)
        (args.out / "provenance.json").write_bytes(
            json.dumps(provenance, sort_keys=True, indent=1).encode() + b"\n"
        )
        print(json.dumps({k: provenance[k] for k in ("count", "axes", "plan_sha256")}))
    else:
        operator_raw = args.operator_plan.read_bytes()
        count = len(json.loads(operator_raw)["pairs"])
        public_raw, _ = plan(count)
        print(json.dumps(disjoint(operator_raw, public_raw)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
