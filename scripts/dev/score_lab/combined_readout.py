"""Reproduce descriptive results from the registered synthetic matrix.

No candidate import, score fitting, inference or reference solver. The optional
diagnostic repeats the fixed analytic buyer evaluation and existing reliability
calculation, after verifying the saved panel/mask/value identities.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

from .core import LabRefused, canonical_sha
from .finish_line import combined_diagnostics


def read_results(directory, plan):
    directory = Path(directory)
    identity = json.loads((directory / "IDENTITY.json").read_text(encoding="utf-8"))
    for name, digest in identity["artifacts_sha256"].items():
        if Path(name).name != name or "/" in name or "\\" in name:
            raise LabRefused("combined_receipt_path")
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise LabRefused("combined_receipt_digest")

    def read(name):
        if name not in identity["artifacts_sha256"]:
            raise LabRefused("combined_receipt_unbound_file")
        raw = (directory / name).read_bytes()
        return json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)

    if identity.get("schema") == "carbon.dev.score-lab-combined-identity.v1":
        start = read("START.json")
        if (
            start
            != {
                key: value
                for key, value in identity.items()
                if key != "artifacts_sha256"
            }
            or read("REGISTERED_PLAN.json") != plan
            or identity["plan_sha256"] != canonical_sha(plan)
            or identity["candidate_sha256"] != plan["candidates_sha256"]
        ):
            raise LabRefused("combined_readout_start_binding")
    run = read("RUN.json.gz")
    controls = read("CONTROLS.json")
    cells = [read(p.name) for p in sorted(directory.glob("CELL_*.json.gz"))]
    expected = set(itertools.product(range(len(plan["profiles"])), range(32)))
    pairs = [(c["profile_index"], c["component_index"]) for c in cells]
    if (
        len(pairs) != len(expected)
        or set(pairs) != expected
        or run["completed_cells"] != len(expected)
        or run["offered_cells"] != len(expected)
        or run["status"] != "COMPLETE"
        or controls["status"] != "CONTROL_PASS"
        or run["plan_sha256"] != canonical_sha(plan)
        or any(c["plan_sha256"] != canonical_sha(plan) for c in cells)
    ):
        raise LabRefused("combined_readout_complete_binding")
    return identity, run, controls, cells


def summarize(directory, plan):
    identity, run, _, cells = read_results(directory, plan)
    counts, rows = Counter(), []
    for cell in cells:
        for row in cell["rows"]:
            for scope, outcome in row["outcomes"].items():
                counts[outcome.get("reason", outcome["status"])] += 1
                if cell["component_index"] == row["physics_index"] == 0 and row[
                    "candidate"
                ].startswith("TOY-ABLATION/"):
                    rows.append(
                        {
                            "profile": plan["profiles"][cell["profile_index"]]["id"],
                            "candidate": row["candidate"],
                            "scope": scope,
                            **{
                                key: outcome.get(key)
                                for key in (
                                    "status",
                                    "tau",
                                    "tau_ci95",
                                    "top1_value",
                                    "top1_regret",
                                    "top1_member",
                                    "known_bad_in_top_half",
                                    "adversarial_in_top_half",
                                    "admissibility_failures",
                                )
                            },
                        }
                    )
    if dict(counts) != run["summary"]["status_counts"]:
        raise LabRefused("combined_readout_counts")
    effects = Counter(
        (
            "UNSCORED"
            if effect["delta_selected_value"] is None
            else (
                "HIGHER_VALUE"
                if effect["delta_selected_value"] > 0
                else (
                    "LOWER_VALUE"
                    if effect["delta_selected_value"] < 0
                    else "SAME_VALUE"
                )
            )
        )
        for effect in run["summary"]["paired_component_effects"]
    )
    return {
        "schema": "carbon.dev.score-lab-combined-summary.v1",
        "status": run["status"],
        "scope": "SYNTHETIC_DEVELOPMENT",
        "source_commit": identity["source_commit"],
        "plan_sha256": run["plan_sha256"],
        "run_sha256": hashlib.sha256(
            (Path(directory) / "RUN.json.gz").read_bytes()
        ).hexdigest(),
        "control_status": "CONTROL_PASS",
        "profiles": len(plan["profiles"]),
        "primary_members_per_profile": 6,
        "probe_members_per_profile": 2,
        "completed_cells": len(cells),
        "candidate_configuration_rows": sum(len(c["rows"]) for c in cells),
        "scoped_outcomes": sum(counts.values()),
        "status_counts": dict(counts),
        "scorer_evaluations": sum(c["scorer_evaluations"] for c in cells),
        "component_effect_counts": dict(effects),
        "baseline_ablation_outcomes": rows,
        "evaluation_cpu_seconds": run["evaluation_cpu_seconds"],
        "controls_cpu_seconds": run["controls_cpu_seconds"],
        "wall_seconds": run["total_wall_seconds"],
        "bootstrap_replicates": plan["profiles"][0]["config"]["bootstrap"],
        "weight_search_performed": False,
        "selection": None,
        "limitations": [
            "Three hand-selected illustrative profiles, no calibrated real population",
            "Six MODEL traits plus two probes, not independent rebuilt families",
            "Cached cheap anchors uncharged; own physics unavailable",
            "Per-row crossed exploratory intervals, not CIs on component differences or family-wide tests",
            "No real fit, policy selection, solver, model inference or hidden holdout",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registration", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--bootstrap-seed", type=int)
    args = parser.parse_args()
    if args.diagnostics is not None and args.bootstrap_seed is None:
        parser.error("diagnostics require an explicit bootstrap seed")
    plan = json.loads(args.registration.read_text(encoding="utf-8"))
    summary = summarize(args.results, plan)
    args.output.write_bytes(
        (json.dumps(summary, indent=2, allow_nan=False) + "\n").encode()
    )
    if args.diagnostics is not None:
        _, _, _, cells = read_results(args.results, plan)
        diagnostic = combined_diagnostics(
            plan,
            [c for c in cells if c["component_index"] == 0],
            seed=args.bootstrap_seed,
        )
        args.diagnostics.write_bytes(
            (json.dumps(diagnostic, indent=2, allow_nan=False) + "\n").encode()
        )


if __name__ == "__main__":
    main()
