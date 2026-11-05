#!/usr/bin/env python3
"""CUSTODY: how a neighbour-task variant rule (V_var) would move each contender's D on a sealed pool.

For a candidate ``variant_rule`` (`carbon.scoring.pool_grader.OptimizerPolicy.variant_rule`) this grades every
contender twice on the same pool, once as today (no rule) and once with the rule, and prints JSON:

- per contender: D without and with the variants, the change, and the grading wall time of each (the extra wall);
- per target: each variant slot's state (graded, or the refusal code: a reference failure), and whether the variant's
  reference best design differs from the base's (``best_design_changed``: the shifted question has a different answer);
- per contender and target: the base d, the aggregate d, and each variant's d.

It names targets and per-target values, so it runs on the custody host only and its output stays there. Nothing is
written. Inputs (JSON files):

- ``--pool``: a list of `pool_grader.dump_pool` documents (one set);
- ``--policies``: ``{"optimizer": {OptimizerPolicy fields, no variant_rule}, "honesty": {HonestyPolicy fields}}``;
- ``--rule``: the candidate variant rule; ``--starts``: ``{target_id: [{"start": [...], "seed": int}, ...]}``;
- ``--contender NAME=FILE`` (repeat): ``{target_id: [outputs dict per pool design, in the pool's design order]}``.

    python -B scripts/dev/pool_variant_report.py --pool pool.json --policies policies.json --rule rule.json \\
        --starts starts.json --contender a=a.json --contender b=b.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path


def _predictor(specs, answers):
    """``predict(conditions, designs)`` over one contender's answers, keyed by each target's conditions and design."""
    by_conditions = {_key(spec.conditions): spec for spec in specs}

    def predict(conditions, designs):
        spec = by_conditions[_key(conditions)]
        rows = answers[spec.target_id]
        index = {tuple(d): n for n, d in enumerate(spec.designs)}
        return [dict(rows[index[tuple(d)]]) for d in designs]

    return predict


def _key(conditions):
    return json.dumps(conditions, sort_keys=True, separators=(",", ":"))


def report(specs, rule, starts, contenders, optimizer, honesty):
    """The report as a JSON-ready dict (see the module docstring)."""
    from carbon.scoring import pool_grader

    attached = [
        pool_grader.attach_variants(spec, rule, starts[spec.target_id])
        for spec in specs
    ]
    with_rule = replace(optimizer, variant_rule=rule)
    targets = []
    for spec, full in zip(specs, attached, strict=True):
        base_best = spec.designs[spec.reference]
        slots = [
            {
                "variant": variant.target_id,
                "state": "graded",
                "best_design_changed": variant.designs[variant.reference] != base_best,
            }
            for variant in full.variants
        ]
        slots += [
            {"limit": name, "shift": shift, "state": code}
            for name, shift, code in full.variant_refusals
        ]
        targets.append({"target": spec.target_id, "slots": slots})
    rows = []
    for name, answers in contenders.items():
        predict = _predictor(specs, answers)
        started = time.perf_counter()
        base = pool_grader.grade_set(specs, predict, optimizer, honesty)
        between = time.perf_counter()
        varied = pool_grader.grade_set(attached, predict, with_rule, honesty)
        ended = time.perf_counter()
        rows.append(
            {
                "contender": name,
                "d_base": base.d,
                "d_with_variants": varied.d,
                "d_change": varied.d - base.d,
                "wall_seconds_base": between - started,
                "wall_seconds_with_variants": ended - between,
                "targets": [
                    {
                        "target": g.target_id,
                        "base_d": g.base_d,
                        "d": g.d,
                        "reason": g.reason,
                        "fallback": g.variant_fallback,
                        "variants": [
                            {"variant": v, "d": d, "reason": r}
                            for v, d, r in g.variants
                        ],
                    }
                    for g in varied.targets
                ],
            }
        )
    return {"custody_only": True, "targets": targets, "contenders": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pool", required=True, type=Path)
    parser.add_argument("--policies", required=True, type=Path)
    parser.add_argument("--rule", required=True, type=Path)
    parser.add_argument("--starts", required=True, type=Path)
    parser.add_argument("--contender", action="append", required=True)
    args = parser.parse_args(argv)
    from carbon.scoring import pool_grader

    def load(path):
        return json.loads(path.read_text(encoding="utf-8"))

    specs = [pool_grader.load_pool(document) for document in load(args.pool)]
    policies = load(args.policies)
    if "variant_rule" in policies["optimizer"]:
        parser.error("--policies must not carry variant_rule; pass it with --rule")
    contenders = {}
    for item in args.contender:
        name, sep, path = item.partition("=")
        if not sep or not name or name in contenders:
            parser.error(f"--contender wants a unique NAME=FILE, got {item!r}")
        contenders[name] = load(Path(path))
    out = report(
        specs,
        load(args.rule),
        load(args.starts),
        contenders,
        pool_grader.OptimizerPolicy(**policies["optimizer"]),
        pool_grader.HonestyPolicy(**policies["honesty"]),
    )
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
