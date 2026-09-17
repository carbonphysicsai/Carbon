"""One durable non-paying simulation lineage; no per-epoch baseline reset."""

from __future__ import annotations

import json
from dataclasses import asdict

from carbon.development_comparison.acceptance import (
    resolve_acceptance,
)
from carbon.development_comparison.simulation import simulate

from .data import write_once
from .profile import canonical


def update_simulation(root, ref, *, epoch):
    report = resolve_acceptance(ref)
    directory = root / "reward-simulation"
    directory.mkdir(exist_ok=True, mode=0o700)
    existing = directory / "first-accepted-comparison.json"
    output = directory / ("epoch-" + str(epoch) + ".json")
    if output.exists():
        return json.loads(output.read_bytes())
    if report["decision"]["accepted_improvement"] is not True:
        value = {
            "status": "NO_ACCEPTED_COMPARISON",
            "reason": report["decision"]["disposition"],
            "opening_admission": "candidate admissibility alone grants zero earned improvement credit",
            "comparison_digest": ref.report_digest,
            "paying": False,
            "network_eligible": False,
        }
    else:
        pin = {
            "root": str(ref.root),
            "registration_digest": ref.registration_digest,
            "report_digest": ref.report_digest,
        }
        if existing.exists() and json.loads(existing.read_bytes()) != pin:
            # Epochs use fresh cohorts and compare to the fixed control, not to
            # an incumbent receipt. Existing C-REWARD correctly rejects that as
            # a continuation. Keep the first clock/headroom and do not mint a
            # second opening lineage to make another reward appear.
            value = {
                "status": "WITHHELD_INCOMPATIBLE_INCUMBENT_LINEAGE",
                "comparison_digest": ref.report_digest,
                "reason": "fresh-cohort fixed-control comparison does not reference the simulation incumbent; a matched incumbent comparison is needed",
                "opening_reset": False,
                "paying": False,
                "network_eligible": False,
            }
        else:
            write_once(existing, canonical(pin))
            result = simulate((ref,), clock_ms=1000, activation_ms=(1000,))
            value = {
                "status": "SIMULATED_ACCEPTED_DEVELOPMENT",
                "comparison_digest": ref.report_digest,
                "result": asdict(result),
                "clock_basis": "explicit offline milliseconds, not block or wall time",
                "opening_credit": 0,
                "paying": False,
                "network_eligible": False,
            }
    write_once(output, canonical(value))
    return value
