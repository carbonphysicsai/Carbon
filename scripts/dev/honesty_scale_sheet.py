#!/usr/bin/env python3
"""Honesty-scale candidates: per-target (q, e) for the proof-grid models, E2 included, and the sheet rendered from them.

Two steps, both aggregates only (no pool point, pick, truth or design leaves custody):

  record  (custody; reached through `pool_proof_grid.py --honesty-sheet-spec SPEC ...`, which builds the plugin)
          grades every model of the proof grid, plus the E2 controls, ONCE at s_h = 1 and writes
          ``honesty-dump-<kind>-<version>.json``: per model and target q, e, feasible, reason; the A and C legs, the gate
          names; and A_gen per set at every A_gen scale set. d = q * exp(-e / s_h) and e does not depend on s_h
          (`pool_grader.grade_target`), so one recording gives D at any s_h.
  render  (anywhere; reads dumps and regrade parts) ``python -m scripts.dev.honesty_scale_sheet render --spec RENDER.json``
          writes the candidate tables: D and total at candidate 0 (keep s_h = 1) and k x the baseline's median e.

E2 (the accuracy-matched gaming control, MOTOR_EXAM_FIX_SCOPE step 3) is an honest model's own predictions plus the same
bias the truth-built control adds to the truth: ``{"kind": "biased", "base": D, "bias": {...}}`` (`pool_proof_suite`,
`pool_plugin.model_outputs`). It is deterministic (seeded signs) and never a TRUTH model.

e is already in units of U: `pool_grader._error` is max over outputs of |prediction - truth| / U (or the rms). So s_h is a
multiple of U for every Challenge and the "unit-normalised" reading is the one the grader already uses; ``--u-dump``
(operator-only) lists each target's declared U per output so that can be checked against the pack.

RECORD SPEC (every value the owner's or the Validator's; nothing defaulted):
  {"budget", "sigma0", "population", "honesty_reduction", "agen_scale_sets": [{output: scale}, ...],  (no a_multiplier: it is
   the version's registered one)
   "a_rule", "c_rule": {"kind": "min"}, "optimism_k", "wrong_radius", "wrong_k", "seed", "bases": ["good", "default"]}
RENDER SPEC:
  {"out": PATH, "ks": [0.25, 0.5, 1.0], "challenges": [{"key", "name", "dump": PATH, "baseline_parts": PATH,
    "crown_parts": PATH, "baseline_agen_sweep": PATH|null, "crown_agen_sweep": PATH|null, "a_rule": {...}}]}
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

CONTROLS = ("optimistic_near_limits", "wrong_near_the_optimum")
STOCK = ("good", "default", "floor", "in_distribution_only")


class SheetError(ValueError):
    """An input this tool cannot use."""


def descriptors(spec):
    """Name -> descriptor: the proof grid's models and E2 on each honest base."""
    named = {
        "oracle": {"kind": "oracle"},
        "good": {"kind": "good"},
        "default": {"kind": "default"},
        "floor": {"kind": "floor"},
        "in_distribution_only": {"kind": "in_distribution"},
        "optimistic_near_limits": {
            "kind": "noisy",
            "k": spec["optimism_k"],
            "mode": "feasible_bias",
            "seed": spec["seed"],
        },
        "wrong_near_the_optimum": {
            "kind": "wrong_near_optimum",
            "radius": spec["wrong_radius"],
            "k": spec["wrong_k"],
            "seed": spec["seed"],
        },
    }
    for base in spec["bases"]:
        named[f"e2_optimistic[{base}]"] = {
            "kind": "biased",
            "base": {"kind": base},
            "bias": {
                "mode": "feasible_bias",
                "k": spec["optimism_k"],
                "seed": spec["seed"],
            },
        }
        named[f"e2_wrong_near[{base}]"] = {
            "kind": "biased",
            "base": {"kind": base},
            "bias": {
                "mode": "wrong_near",
                "radius": spec["wrong_radius"],
                "k": spec["wrong_k"],
                "seed": spec["seed"],
            },
        }
    return named


def _finite(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def record(plugin, spec, kind, version, *, a_multiplier):
    """Grade every model once at s_h = 1 and return the dump (aggregates only).

    ``a_multiplier`` is the version's REGISTERED A-leg tightening (`pool_version.registered_a_multiplier`), required and
    never read from the spec: each A leg 1 / (1 + x) becomes 1 / (1 + m x) before the legs are averaged, exactly as the
    exam (`pool_exam.measure_pool`) and the proof grid score it, so the recorded A and totals match the live exam.
    """
    from carbon.scoring import pool_grader
    from carbon.scoring.pool_proof_grid import tighten

    if (
        type(a_multiplier) not in (int, float)
        or isinstance(a_multiplier, bool)
        or not math.isfinite(a_multiplier)
        or a_multiplier <= 0
    ):
        raise SheetError("a_multiplier_must_be_the_registered_positive_number")
    if "a_multiplier" in spec:
        raise SheetError("a_multiplier_comes_from_the_registered_version_not_the_spec")
    from carbon.scoring import pool_proof_suite as suite

    all_specs = [s for specs in plugin.sets for s in specs]
    optimizer = pool_grader.OptimizerPolicy(
        budget=spec["budget"],
        sigma0=spec["sigma0"],
        population=spec["population"],
        # a NEW version's engineer's-shortcut D zero (absent = the median), as its pools carry it
        d_zero=spec.get("d_zero"),
        # the version's neighbour-task rule rides with its plugin (its sets carry the variants)
        variant_rule=getattr(plugin, "variant_rule", None),
    )
    honesty = pool_grader.HonestyPolicy(scale=1.0, reduction=spec["honesty_reduction"])
    models = {}
    for name, descriptor in descriptors(spec).items():
        predict = suite.pool_predictor(plugin, descriptor, all_specs)
        grades = [
            pool_grader.grade_set(specs, predict, optimizer, honesty)
            for specs in plugin.sets
        ]
        legs = plugin.legs(descriptor, plugin.sets[0])
        gates = (
            list(plugin.pool_gates(descriptor, all_specs)) if plugin.pool_gates else []
        )
        speed = bool(
            plugin.speed_gate
            and (r := plugin.speed_gate(descriptor)) is not None
            and not r["passed"]
        )
        a_legs = legs.get("A_legs")
        a_bank = (
            statistics.fmean(tighten(v, a_multiplier) for v in a_legs.values())
            if a_legs
            else tighten(legs["A"], a_multiplier)
        )
        models[name] = {
            "descriptor_kind": descriptor["kind"],
            "sets": [
                [
                    {
                        "target": t.digest.removeprefix("sha256:")[:16],
                        "feasible": t.feasible,
                        "reason": t.reason,
                        "q": t.q,
                        "e": _finite(t.e),
                    }
                    for t in grade.targets
                ]
                for grade in grades
            ],
            "A": a_bank,
            "A_untightened": legs["A"],
            "C": legs["C"],
            "gates_ok": legs.get("gates_ok"),
            "pool_gate_failures": gates,
            "speed_failed": speed,
            "agen": [
                [
                    pool_grader.agen_accuracy(specs, predict, scales)
                    for specs in plugin.sets
                ]
                for scales in spec["agen_scale_sets"]
            ],
        }
    return {
        "schema": "carbon.honesty-scale-dump.v1",
        "kind": kind,
        "version": version,
        "a_multiplier": a_multiplier,
        "spec": {k: v for k, v in spec.items()},
        "models": models,
    }


def registered_inputs(kind, version, spec, *, path=None):
    """The version's REGISTERED a_multiplier, after checking the spec's optimizer, honesty reduction and rules equal the
    registered entry (a spec that differs would record a different exam than the live one): raises `SheetError`.
    """
    from carbon.scoring import pool_version

    challenge_id = next((c for c, k in pool_version.KINDS.items() if k == kind), None)
    if challenge_id is None:
        raise SheetError("kind_is_not_a_registered_pool_kind")
    kwargs = {} if path is None else {"path": path}
    try:
        multiplier = pool_version.registered_a_multiplier(
            challenge_id, version, **kwargs
        )
        policies = pool_version.registered_policies(challenge_id, version, **kwargs)
    except Exception as refused:  # noqa: BLE001 - closed code, no guess
        raise SheetError(f"version_not_registered: {refused}") from None
    registered = {
        "budget": policies.optimizer.budget,
        "sigma0": policies.optimizer.sigma0,
        "population": policies.optimizer.population,
        "honesty_reduction": policies.honesty.reduction,
        "a_rule": policies.a_rule,
        "c_rule": policies.c_rule,
    }
    differs = sorted(k for k, v in registered.items() if spec.get(k) != v)
    if differs:
        raise SheetError(
            "spec_differs_from_the_registered_version: " + ", ".join(differs)
        )
    return multiplier


def u_dump(plugin):
    """OPERATOR ONLY: the declared U of every target and output (the number, or r in r x |true value|)."""
    return [
        {"target": s.digest.removeprefix("sha256:")[:16], "u": dict(s.u)}
        for specs in plugin.sets
        for s in specs
    ]


# ---------------------------------------------------------------------------------------------------------------- render


def d_set(targets, s_h):
    """Mean over the set's targets of q * exp(-e / s_h); an infinite e (None) earns 0."""
    return statistics.fmean(
        0.0 if t["e"] is None else t["q"] * math.exp(-t["e"] / s_h) for t in targets
    )


def model_d(model, s_h):
    """D as the exam composes it: the mean over sets of min(set mean d, C)."""
    return statistics.fmean(min(d_set(t, s_h), model["C"]) for t in model["sets"])


def model_a(model, j, a_rule):
    """A at A_gen scale set j: the mean over sets of combine_a(A, A_gen of the set, rule)."""
    from carbon.scoring import pool_grader

    return statistics.fmean(
        pool_grader.combine_a(model["A"], gen, a_rule) for gen in model["agen"][j]
    )


def model_total(model, s_h, j, a_rule):
    """0.5 A + 0.5 D, 0 when a mandatory gate or the speed gate failed (the grader's own rule)."""
    if (
        model["gates_ok"] is False
        or model["pool_gate_failures"]
        or model["speed_failed"]
    ):
        return 0.0
    return 0.5 * model_a(model, j, a_rule) + 0.5 * model_d(model, s_h)


def parts_targets(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    (one,) = document["sets"]
    return (
        [(t["q"], t["e"]) for t in one["targets"]],
        one["C"],
        document["regraded_a"],
    )


def _d_parts(targets, c, s_h):
    return min(statistics.fmean(q * math.exp(-e / s_h) for q, e in targets), c)


def _fmt(value):
    return "n/m" if value is None else f"{value:.3g}"


def render(spec):
    """The markdown for every Challenge in the render spec."""
    ks = spec["ks"]
    out = [
        "# Honesty-scale candidates, measured (Test Engineer)",
        "",
        (
            "Candidates, not choices; the owner picks. D and total per candidate s_h, from one recording at s_h = 1 "
            "(`d = q * exp(-e / s_h)`; e is in units of U). Total = 0.5 A + 0.5 D with the exam's own A rule, "
            "0 when a gate failed. A cell the dump does not hold says `n/m`."
        ),
        "",
    ]
    for ch in spec["challenges"]:
        dump = json.loads(Path(ch["dump"]).read_text(encoding="utf-8"))
        models = dump["models"]
        a_rule = ch.get("a_rule") or dump["spec"]["a_rule"]
        base_t, base_c, base_a = parts_targets(ch["baseline_parts"])
        crown_t, crown_c, crown_a = parts_targets(ch["crown_parts"])
        median_e = statistics.median(e for _, e in base_t)
        candidates = [("0 (keep s_h = 1)", 1.0)] + [
            (f"k={k:g}", k * median_e) for k in ks
        ]
        names = [
            n
            for n in ("oracle", "good", "default", "floor", "in_distribution_only")
            if n in models
        ]
        gaming = [n for n in models if n in CONTROLS or n.startswith("e2_")]
        out += [
            f"## {ch['name']}",
            "",
            f"Baseline median e = {median_e:.4g} (the k=1 scale). Columns: D (total). Honest = good/default/crown.",
            "",
            "| candidate | s_h | baseline | UID 35 crown | "
            + " | ".join(names + gaming)
            + " | who earns D: e=3 / e=30 | (b) gaming <= honest (D and total) | (c) oracle |",
            "|---|---|---|---|" + "---|" * (len(names) + len(gaming)) + "---|---|---|",
        ]
        for label, s_h in candidates:
            cells = [
                f"{_d_parts(base_t, base_c, s_h):.3g} ({0.5 * base_a + 0.5 * _d_parts(base_t, base_c, s_h):.3f})",
                f"{_d_parts(crown_t, crown_c, s_h):.3g} ({0.5 * crown_a + 0.5 * _d_parts(crown_t, crown_c, s_h):.3f})",
            ]
            value = {}
            for name in names + gaming:
                m = models[name]
                d = model_d(m, s_h)
                t = model_total(m, s_h, 0, a_rule)
                value[name] = (d, t)
                cells.append(f"{d:.3g} ({t:.3f})")
            honest = [value[n] for n in ("good", "default") if n in value]
            failures = []
            for name in gaming:
                if name.startswith("e2_"):
                    base = name[name.index("[") + 1 : -1]
                    limit = value.get(base)
                    limit = [limit] if limit else honest
                else:
                    limit = honest
                if not limit:
                    continue
                bd = max(x[0] for x in limit)
                bt = max(x[1] for x in limit)
                if value[name][0] > bd + 1e-12 or value[name][1] > bt + 1e-12:
                    failures.append(name)
            oracle = value.get("oracle")
            cells.append(f"{math.exp(-3 / s_h):.3g} / {math.exp(-30 / s_h):.3g}")
            cells.append("PASS" if not failures else "FAIL: " + ", ".join(failures))
            cells.append("n/m" if oracle is None else f"{oracle[0]:.3g}")
            out.append(f"| {label} | {s_h:.4g} | " + " | ".join(cells) + " |")
        out.append("")
        # A-scale sweep
        scale_sets = dump["spec"]["agen_scale_sets"]
        out += [
            f"### {ch['name']}: A at stricter A_gen scales (s_h = 1)",
            "",
            "| A_gen scale set | "
            + " | ".join(names + gaming)
            + " | baseline A | UID 35 crown A |",
            "|---|" + "---|" * (len(names) + len(gaming) + 2),
        ]
        sweeps = {}
        for who, key in (
            ("baseline", "baseline_agen_sweep"),
            ("crown", "crown_agen_sweep"),
        ):
            if ch.get(key):
                sweeps[who] = json.loads(Path(ch[key]).read_text(encoding="utf-8"))
        for j, scales in enumerate(scale_sets):
            row = [f"{model_a(models[n], j, a_rule):.4f}" for n in names + gaming]
            for who, fallback in (("baseline", base_a), ("crown", crown_a)):
                sweep = sweeps.get(who)
                row.append(
                    f"{sweep[j]['A']:.4f}"
                    if sweep and j < len(sweep)
                    else ("n/m" if j else f"{fallback:.4f}")
                )
            out.append(f"| set-{j} | " + " | ".join(row) + " |")
        out.append("")
    return "\n".join(out)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render")
    r.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    text = render(spec)
    Path(spec["out"]).write_text(text, encoding="utf-8")
    print(f"wrote {spec['out']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
