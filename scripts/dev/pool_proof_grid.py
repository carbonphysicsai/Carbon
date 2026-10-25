#!/usr/bin/env python3
"""Run the proof suite over a grid of every OWNER constant and write the owner's scoring sheet for one Challenge.

    python scripts/dev/pool_proof_grid.py --kind KIND --version V \
        --binding carbon.scoring.pool_adapters:binding_for \
        --pools-dir CUSTODY/pools --sets SETS.json --grid GRID.json --out-dir OUT \
        --truth-probe-rule perfect --response-leg A_response --ignored-gates physics_laws \
        --truth-tolerance 1e-5

`--binding` names a `module:function` returning a `pool_plugin.ChallengeBinding` for (kind, version): the
Challenge's adapter and model servers, supplied by its lane. `--sets` maps set names to target ids
({"A": ["t1", ...], "B": [...]}); `--pools-dir` holds Data Collection's `pool-source-<tid>.json` documents (custody).
`--grid` is a JSON file with every `pool_proof_grid.GridSpec` field (none has a default). The sheet is
aggregates only; run it in custody, it reads sealed pool material.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _binding(path, kind, version):
    module, _, name = path.partition(":")
    if not module or not name:
        raise SystemExit("--binding must be module:function")
    return getattr(importlib.import_module(module), name)(kind, version)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag in ("kind", "version", "binding", "pools-dir", "sets", "grid", "out-dir"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument(
        "--truth-probe-rule", required=True, choices=("perfect", "measured")
    )
    parser.add_argument("--response-leg", required=True)
    parser.add_argument("--truth-tolerance", required=True, type=float)
    parser.add_argument(
        "--in-distribution",
        required=True,
        choices=("reported", "pass"),
        help="the in-distribution control: reported only (Phase 1, pools inside the TRAIN box) or a pass criterion",
    )
    parser.add_argument(
        "--ignored-gates", required=True, help="comma separated; may be empty"
    )
    parser.add_argument("--title", default=None)
    parser.add_argument(
        "--probe-truth-file",
        default=None,
        help="JSON {case_id: [true raw output row]} for the practice bank's probe rows (Data Collection's solves); "
        "used when the binding supplies no probe_truth",
    )
    args = parser.parse_args(argv)

    from carbon.scoring import pool_plugin, pool_proof_grid

    binding = _binding(args.binding, args.kind, args.version)
    pools = Path(args.pools_dir)
    sets = json.loads(Path(args.sets).read_text(encoding="utf-8"))
    specs = {}
    for names in sets.values():
        for tid in names:
            document = json.loads(
                (pools / f"pool-source-{tid}.json").read_text(encoding="utf-8")
            )
            specs[tid] = pool_plugin.spec_from_source(document, binding)
    grid_doc = json.loads(Path(args.grid).read_text(encoding="utf-8"))
    grid_doc = {k: v for k, v in grid_doc.items() if not k.startswith("_")}
    grid_doc["in_distribution_is_pass_criterion"] = args.in_distribution == "pass"
    out = Path(args.out_dir)
    fractions = grid_doc.pop("agen_scale_sets_train_spread_fractions", None)
    if fractions is not None:
        if "agen_scale_sets" in grid_doc:
            raise SystemExit(
                "give agen_scale_sets or its TRAIN-spread fractions, not both"
            )
        if binding.train_spread is None:
            raise SystemExit(
                "the binding supplies no train_spread to expand the A_gen fractions"
            )
        spread = binding.train_spread()
        grid_doc["agen_scale_sets"] = [
            {name: fraction * value for name, value in spread.items()}
            for fraction in fractions
        ]
        out.mkdir(parents=True, exist_ok=True)
        (out / f"agen-expansion-{args.kind}-{args.version}.json").write_text(
            json.dumps(
                {
                    "train_spread": spread,
                    "fractions": fractions,
                    "scale_sets": grid_doc["agen_scale_sets"],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    for key in (
        "budgets",
        "honesty_scales",
        "a_multipliers",
        "agen_scale_sets",
        "a_rules",
    ):
        grid_doc[key] = tuple(grid_doc[key])
    grid = pool_proof_grid.GridSpec(**grid_doc)
    bank_legs = pool_plugin.practice_bank_legs(
        binding,
        truth_probe_rule=args.truth_probe_rule,
        response_leg=args.response_leg,
        ignored_gates=tuple(g for g in args.ignored_gates.split(",") if g),
        truth_tolerance=args.truth_tolerance,
    )
    if args.probe_truth_file and binding.probe_truth is None:
        by_case = json.loads(Path(args.probe_truth_file).read_text(encoding="utf-8"))
        by_inputs = {
            tuple(sorted(r["inputs"].items())): r["case_id"] for r in bank_legs.rows
        }

        def from_file(rows):
            return [by_case[by_inputs[tuple(sorted(r.items()))]] for r in rows]

        bank_legs = replace(bank_legs, binding=replace(binding, probe_truth=from_file))
        binding = bank_legs.binding
    if args.truth_probe_rule == "perfect":
        try:
            record = bank_legs.verify_truth_rows()
        except pool_plugin.TruthCheckStop as stop:
            print(f"STOP, back to the Validator: {stop}", file=sys.stderr)
            return 3
        print(f"truth-row check passed: {record}")

    def no_fresh_set(draw):
        raise SystemExit("the grid run needs no fresh set")

    plugin = pool_plugin.make_plugin(
        binding,
        bank_legs,
        [[specs[t] for t in names] for names in sets.values()],
        no_fresh_set,
    )
    result = pool_proof_grid.run_grid(plugin, grid)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"owner-sheet-{args.kind}-{args.version}"
    (out / f"{stem}.json").write_text(pool_proof_grid.dump(result), encoding="utf-8")
    title = args.title or f"{args.kind} {args.version}"
    (out / f"{stem}.md").write_text(
        pool_proof_grid.sheet_markdown(title, result), encoding="utf-8"
    )
    print(
        f"{result['meta']['rows_meeting_all']} of {result['meta']['rows']} grid points meet every condition: {out / stem}.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
