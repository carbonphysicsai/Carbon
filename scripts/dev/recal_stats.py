#!/usr/bin/env python3
"""Rebuild-noise statistics for the launch recalibration (GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030, item 4).

Reads the measured totals and state digests, writes one measurement document, and prints its sha256, which becomes the
registered `measurement_digest`. It registers nothing: writing koth_rebuild_noise.json is a reviewed change of its own.

Input (JSON), schema "carbon.recal-stats.input.v1":
  {"schema": ..., "challenges": {<name>: {
      "pack_digest": <64 hex>, "class_record_digest": <64 hex>,
      "control_basis_bit_identical": "<text>", "control_basis_within_noise": "<text>",
      "panel": [<entry_id>, ...],                       # panel order; the control search runs in this order
      "members": {<entry_id>: {
          "reference_fingerprint": <64 hex>,
          "seed0_totals": [10 numbers],                  # 10 rebuilds at the official seed 0
          "state_digests": [10 x 64 hex],                # one per rebuild
          "within_noise": true|false}},                  # only read when no member is bit-identical
      "control_seed_totals": {<entry_id>: [10 numbers]}  # the control rebuilt with seed=0..9
  }}}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys

SCHEMA_IN = "carbon.recal-stats.input.v1"
SCHEMA_OUT = "carbon.recal-stats.measurement.v1"
N = 10
_HEX = re.compile(r"[0-9a-f]{64}")


class StatsError(ValueError):
    pass


def _digest(value, where):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise StatsError(f"{where}: not a full 64-hex digest")
    return value


def _totals(value, where):
    if not isinstance(value, list) or len(value) != N:
        raise StatsError(f"{where}: need exactly {N} totals")
    out = []
    for x in value:
        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not math.isfinite(x)
        ):
            raise StatsError(f"{where}: totals must be finite numbers")
        out.append(float(x))
    return out


def canonical(doc):
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _challenge(name, spec):
    pack = _digest(spec.get("pack_digest"), f"{name}.pack_digest")
    klass = _digest(spec.get("class_record_digest"), f"{name}.class_record_digest")
    panel, members = spec.get("panel"), spec.get("members")
    if (
        not panel
        or not isinstance(members, dict)
        or set(panel) != set(members)
        or len(set(panel)) != len(panel)
    ):
        raise StatsError(f"{name}: panel must list each member exactly once")
    stats = {}
    for eid in panel:
        m = members[eid]
        totals = _totals(m.get("seed0_totals"), f"{name}.{eid}.seed0_totals")
        digests = m.get("state_digests")
        if not isinstance(digests, list) or len(digests) != N:
            raise StatsError(f"{name}.{eid}: need exactly {N} state digests")
        digests = [_digest(d, f"{name}.{eid}.state_digests") for d in digests]
        stats[eid] = {
            "sigma": statistics.stdev(totals),
            "bit_identical": len(set(digests)) == 1,
            "fingerprint": _digest(
                m.get("reference_fingerprint"), f"{name}.{eid}.reference_fingerprint"
            ),
            "within_noise": m.get("within_noise") is True,
            "seed0_total": totals[0],
        }
    sigma = max(s["sigma"] for s in stats.values())
    control = next((e for e in panel if stats[e]["bit_identical"]), None)
    basis = spec.get("control_basis_bit_identical")
    if control is None:
        pool = [e for e in panel if stats[e]["within_noise"]]
        if not pool:
            raise StatsError(
                f"{name}: no bit-identical member and none marked within_noise; no control can be chosen"
            )
        control = min(pool, key=lambda e: (stats[e]["sigma"], panel.index(e)))
        basis = spec.get("control_basis_within_noise")
    if not isinstance(basis, str) or not basis:
        raise StatsError(
            f"{name}: the control_basis text for the chosen case is missing"
        )
    seeds = _totals(
        (spec.get("control_seed_totals") or {}).get(control),
        f"{name}.control_seed_totals[{control}]",
    )
    spread = max(seeds) - min(seeds)
    value = max(5 * sigma, spread)
    if value == 0:
        raise StatsError(
            f"{name}: sigma and seed spread are both 0; stop and report (no resolution floor is registered)"
        )
    return {
        "bit_identical": {e: stats[e]["bit_identical"] for e in panel},
        "control": {
            "entry_id": control,
            "reference_fingerprint": stats[control]["fingerprint"],
            "reference_total": stats[control]["seed0_total"],
            "control_basis": basis,
            "pack_digest": pack,
            "class_record_digest": klass,
        },
        "seed_spread": spread,
        "sigma": sigma,
        "sigma_by_member": {e: stats[e]["sigma"] for e in panel},
        "value": value,
    }


def measure(doc):
    if (
        not isinstance(doc, dict)
        or doc.get("schema") != SCHEMA_IN
        or not isinstance(doc.get("challenges"), dict)
    ):
        raise StatsError(f"input must carry schema {SCHEMA_IN} and a challenges object")
    body = {
        "challenges": {
            n: _challenge(n, s) for n, s in sorted(doc["challenges"].items())
        },
        "schema": SCHEMA_OUT,
    }
    return {**body, "measurement_digest": hashlib.sha256(canonical(body)).hexdigest()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument(
        "--out", help="write the measurement document here (default: stdout)"
    )
    args = ap.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as f:
            result = measure(json.load(f))
    except (StatsError, OSError, json.JSONDecodeError) as exc:
        print(f"recal_stats: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(result["measurement_digest"])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
