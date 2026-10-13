"""Offline score-lab CLI: python -m scripts.dev.score_lab."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import statistics
from pathlib import Path

from . import (
    bank,
    bank_builder,
    candidates,
    physics,
    public_ev4,
    public_physics,
    synthetic,
)
from .core import LabRefused, analyze, registry_rule, v2_rule


def _load_rule(args):
    if args.candidates:
        return None  # loaded as a set after the panels are built
    if args.registry:
        return registry_rule(args.registry, args.candidate)
    if args.v2_definition:
        return v2_rule(
            definition=json.loads(args.v2_definition.read_text(encoding="utf-8")),
            kappa=args.kappa,
            cap=args.cap,
            unit=args.unit,
        )
    path, sep, name = args.function.partition(":")
    if not sep or not name:
        raise LabRefused("function_syntax")
    spec = importlib.util.spec_from_file_location("score_lab_local_rule", path)
    if spec is None or spec.loader is None:
        raise LabRefused("function_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, name, None)
    if not callable(fn):
        raise LabRefused("function_not_callable")
    return fn


def _rule_args(parser):
    rules = parser.add_mutually_exclusive_group(required=True)
    rules.add_argument("--registry", type=Path)
    rules.add_argument("--v2-definition", type=Path)
    rules.add_argument(
        "--candidates", type=Path, help="trusted local Validator candidate file"
    )
    rules.add_argument("--function", help="trusted local file.py:function")
    parser.add_argument("--candidate", help="id from --registry")
    parser.add_argument("--kappa", type=float, help="V2 ASSUMPTION, no default")
    parser.add_argument("--cap", type=int, help="V2 k ASSUMPTION, no default")
    parser.add_argument("--unit", type=float, help="V2 u ASSUMPTION, no default")
    parser.add_argument("--gate-json", help="explicit G-FEAS gate for toy V2")
    parser.add_argument("--bootstrap", type=int, default=200)
    parser.add_argument("--out", type=Path, help="optional aggregate JSON output")


def _report(rows):
    measured = [r for r in rows if r.get("status") == "MEASURED_DEVELOPMENT"]
    concerns = [
        r
        for r in rows
        if r.get("status") != "MEASURED_DEVELOPMENT"
        or r["tau"] is None
        or r["tau_ci95"] is None
        or r["tau_ci95"][0] <= 0
    ]
    headline = (
        "tracks value on every tested knob (exploratory)"
        if measured and not concerns
        else f"fails or remains unresolved on {len(concerns)}/{len(rows)} tested knobs"
    )
    taus = [r["tau"] for r in measured if r["tau"] is not None]
    regrets = [r["top1_regret"] for r in measured if r["top1_regret"] is not None]
    knobs = ("space", "optima", "constraint", "shift", "verification_cost_ASSUMPTION")

    def median_at(knob, value):
        xs = [
            r["tau"]
            for r in measured
            if r["tau"] is not None and (r.get("assumption") or {}).get(knob) == value
        ]
        return statistics.median(xs) if xs else None

    stability = {
        knob: {
            str(value): median_at(knob, value)
            for value in sorted(
                {
                    r["assumption"][knob]
                    for r in measured
                    if r.get("assumption") and knob in r["assumption"]
                }
            )
        }
        for knob in knobs
        if any(r.get("assumption") and knob in r["assumption"] for r in measured)
    }

    def median_rank(key):
        ranks = [r[key] for r in measured if r.get(key) is not None]
        return statistics.median(ranks) if ranks else None

    summary = {
        "status": "DEVELOPMENT_DIAGNOSTIC",
        "verdict": headline,
        "profiles": len(rows),
        "measured": len(measured),
        "tau_range": [min(taus), max(taus)] if taus else None,
        "tau_median": statistics.median(taus) if taus else None,
        "point_tau_negative_profiles": sum(x < 0 for x in taus),
        "positive_ci_profiles": sum(
            r["tau_ci95"] is not None and r["tau_ci95"][0] > 0 for r in measured
        ),
        "knob_median_tau": stability,
        "top1_regret_range": [min(regrets), max(regrets)] if regrets else None,
        "cheap_baseline_median_rank": median_rank("cheap_baseline_rank"),
        "always_abstain_median_rank": median_rank("always_abstain_rank"),
        "known_bad_top_half_profiles": sum(
            bool(r.get("known_bad_in_top_half")) for r in measured
        ),
        "adversarial_top_half_profiles": sum(
            bool(r.get("adversarial_in_top_half")) for r in measured
        ),
        "concerns": [
            {
                "assumption": r.get("assumption"),
                "tau": r.get("tau"),
                "ci95": r.get("tau_ci95"),
                "status": r["status"],
            }
            for r in concerns
        ],
        "rows": rows,
    }
    print("SCORE LAB — DEVELOPMENT ONLY")
    print(headline)
    print(
        f"profiles {len(rows)} | measured {len(measured)} | tau range {summary['tau_range']}"
    )
    print(
        f"median tau {summary['tau_median']} | point-negative "
        f"{summary['point_tau_negative_profiles']} | CI-positive "
        f"{summary['positive_ci_profiles']}"
    )
    print(f"top-1 regret range {summary['top1_regret_range']}")
    print(
        f"median rank: cheap {summary['cheap_baseline_median_rank']}, "
        f"always-abstain {summary['always_abstain_median_rank']}; "
        f"known-bad top-half {summary['known_bad_top_half_profiles']}/{len(measured)}, "
        f"adversarial top-half {summary['adversarial_top_half_profiles']}/{len(measured)}"
    )
    if stability:
        weakest = min(
            (
                (value, knob, setting)
                for knob, settings in stability.items()
                for setting, value in settings.items()
                if value is not None
            ),
            default=None,
        )
        if weakest is not None:
            print(
                f"weakest median knob: {weakest[1]}={weakest[2]} (tau {weakest[0]:.3f})"
            )
    if concerns:
        print("first concern:", json.dumps(summary["concerns"][0], sort_keys=True))
    return summary


def _write(out, report):
    if out is not None:
        out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    synth = commands.add_parser("synthetic", help="32 analytic knob profiles")
    _rule_args(synth)
    synth.add_argument("--quick", action="store_true", help="first four profiles")
    synth.add_argument("--questions-per-side", type=int, default=8)
    synth.add_argument(
        "--value-workflow", choices=("one-pick", "v2-shortlist"), default="one-pick"
    )
    synth.add_argument("--buyer-cap", type=int, help="V2 buyer k ASSUMPTION")
    synth.add_argument("--buyer-unit", type=float, help="V2 buyer u ASSUMPTION")
    synth.add_argument(
        "--verification-costs", help="comma-separated toy cost assumptions"
    )
    prepare = commands.add_parser(
        "prepare-ev4", help="digest-check public EV4, cache quantities"
    )
    prepare.add_argument("--public-dir", type=Path, required=True)
    prepare.add_argument("--repository", type=Path, default=Path("."))
    prepare.add_argument("--out", type=Path, required=True)
    replay = commands.add_parser(
        "replay", help="run a rule on a public or fixture cache"
    )
    _rule_args(replay)
    replay.add_argument("--cache", type=Path, required=True)
    check = commands.add_parser("bank-check", help="V2 development-half bank check")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--records", type=Path, required=True)
    check.add_argument("--definition", type=Path, required=True)
    check.add_argument("--cheap", type=Path)
    check.add_argument("--reference-model", type=Path)
    check.add_argument("--learnability", type=Path)
    check.add_argument("--cap", type=int)
    check.add_argument("--kappa", type=float)
    check.add_argument("--unit", type=float)
    check.add_argument("--ceiling-threshold", type=float)
    check.add_argument("--out", type=Path)
    bank_plan = commands.add_parser(
        "bank-plan", help="producer-only V2 reference-job plan; writes protected output"
    )
    bank_plan.add_argument("--registration", type=Path, required=True)
    bank_plan.add_argument("--draws", type=Path, required=True)
    bank_plan.add_argument("--definition", type=Path, required=True)
    bank_plan.add_argument("--split-seed-file", type=Path, required=True)
    bank_plan.add_argument("--out", type=Path, required=True)
    bank_solved = commands.add_parser(
        "bank-solved-check", help="aggregate-only V2 solved-bank reconciliation"
    )
    bank_solved.add_argument("--plan", type=Path, required=True)
    bank_solved.add_argument("--registration", type=Path, required=True)
    bank_solved.add_argument("--draws", type=Path, required=True)
    bank_solved.add_argument("--split-seed-file", type=Path, required=True)
    bank_solved.add_argument("--records", type=Path, required=True)
    bank_solved.add_argument("--definition", type=Path, required=True)
    bank_solved.add_argument("--cheap", type=Path)
    bank_solved.add_argument("--reference-model", type=Path)
    bank_solved.add_argument("--learnability", type=Path)
    bank_solved.add_argument("--cap", type=int)
    bank_solved.add_argument("--kappa", type=float)
    bank_solved.add_argument("--unit", type=float)
    bank_solved.add_argument("--ceiling-threshold", type=float)
    bank_solved.add_argument("--out", type=Path)
    bank_cost = commands.add_parser(
        "bank-cost", help="producer-only V2 cost and refinement jobs"
    )
    bank_cost.add_argument("--plan", type=Path, required=True)
    bank_cost.add_argument("--registration", type=Path, required=True)
    bank_cost.add_argument("--draws", type=Path, required=True)
    bank_cost.add_argument("--definition", type=Path, required=True)
    bank_cost.add_argument("--split-seed-file", type=Path, required=True)
    bank_cost.add_argument("--policy", type=Path, required=True)
    bank_cost.add_argument("--coarse", type=Path)
    bank_cost.add_argument("--jobs-out", type=Path)
    bank_cost.add_argument("--out", type=Path)
    phys = commands.add_parser(
        "physics", help="OPT-15b analytic physics and neighbour sweep"
    )
    phys.add_argument("--config", type=Path, required=True)
    phys.add_argument("--candidates", type=Path, required=True)
    phys.add_argument("--candidate", help="one candidate id; default is all ten")
    phys.add_argument(
        "--public-cache", type=Path, help="optional public EV4 Score Lab cache"
    )
    phys.add_argument("--plt-readings", type=Path, help="PLT-01 public paired readings")
    phys.add_argument("--b9-measurements", type=Path, help="public B9 measurement file")
    phys.add_argument(
        "--tier2-registry", type=Path, help="exact public registry anchor"
    )
    phys.add_argument("--tier2-candidate", help="id in --tier2-registry")
    phys.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "bank-plan":
        planned = bank_builder.plan(
            json.loads(args.registration.read_text(encoding="utf-8")),
            json.loads(args.draws.read_text(encoding="utf-8")),
            definition_bytes=args.definition.read_bytes(),
            split_seed=args.split_seed_file.read_text(encoding="utf-8").strip(),
        )
        args.out.write_text(
            json.dumps(planned, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            "PRODUCER ONLY: wrote protected V2 plan; "
            f"{len(planned['questions'])} questions, {len(planned['jobs'])} reference jobs"
        )
        return 0
    if args.command == "bank-solved-check":
        optional = lambda path: (
            None if path is None else json.loads(path.read_text(encoding="utf-8"))
        )
        result = bank_builder.check_solved(
            json.loads(args.plan.read_text(encoding="utf-8")),
            bank.read_records(args.records),
            registration=json.loads(args.registration.read_text(encoding="utf-8")),
            draws=json.loads(args.draws.read_text(encoding="utf-8")),
            definition_bytes=args.definition.read_bytes(),
            split_seed=args.split_seed_file.read_text(encoding="utf-8").strip(),
            cheap=optional(args.cheap),
            reference_model=optional(args.reference_model),
            learnability=optional(args.learnability),
            cap=args.cap,
            kappa=args.kappa,
            unit=args.unit,
            ceiling_threshold=args.ceiling_threshold,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        _write(args.out, result)
        return 0
    if args.command == "bank-cost":
        coarse = (
            None
            if args.coarse is None
            else json.loads(args.coarse.read_text(encoding="utf-8"))
        )
        cost = bank_builder.reference_cost(
            json.loads(args.plan.read_text(encoding="utf-8")),
            json.loads(args.policy.read_text(encoding="utf-8")),
            coarse,
            registration=json.loads(args.registration.read_text(encoding="utf-8")),
            draws=json.loads(args.draws.read_text(encoding="utf-8")),
            definition_bytes=args.definition.read_bytes(),
            split_seed=args.split_seed_file.read_text(encoding="utf-8").strip(),
        )
        jobs = cost.pop("refinement_jobs")
        if args.jobs_out is not None:
            args.jobs_out.write_text(
                json.dumps(jobs, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print(json.dumps(cost, indent=2, sort_keys=True))
        _write(args.out, cost)
        return 0
    if args.command == "physics":
        config = json.loads(args.config.read_text(encoding="utf-8"))
        specs, digest = candidates.load(args.candidates)
        if args.candidate:
            if args.candidate not in specs:
                raise LabRefused("candidate_not_registered")
            specs = {args.candidate: specs[args.candidate]}
        report = physics.sensitivity(config, specs, digest)
        supplied = [args.public_cache, args.plt_readings, args.b9_measurements]
        if (args.tier2_registry is None) != (args.tier2_candidate is None):
            raise LabRefused("physics_tier2_anchor_incomplete")
        if args.tier2_registry is not None and args.public_cache is None:
            raise LabRefused("physics_tier2_public_cache_required")
        if any(x is not None for x in supplied):
            if any(x is None for x in supplied):
                raise LabRefused("physics_public_inputs_incomplete")
            with (
                gzip.open(args.public_cache, "rt", encoding="utf-8")
                if args.public_cache.suffix == ".gz"
                else args.public_cache.open("r", encoding="utf-8")
            ) as handle:
                public_panel = json.load(handle)
            traits = public_physics.load_traits(args.plt_readings, args.b9_measurements)
            wrapper = candidates.load_physics_wrapper(args.candidates)
            report["tier2_public"] = {}
            for name, spec in specs.items():
                rule = candidates.rule_from_spec(
                    name,
                    spec,
                    path_digest=digest,
                    panel=public_panel,
                    registry_v5=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v5.json"
                    ),
                    registry_v9=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v9.json"
                    ),
                    registry_v10=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v10.json"
                    ),
                )
                report["tier2_public"][name] = (
                    public_physics.replay(
                        public_panel,
                        traits,
                        rule,
                        config["physics_sweep"],
                        bootstrap=config["bootstrap"],
                        with_physics=wrapper,
                    )
                    if rule is not None
                    else {
                        "status": "INSUFFICIENT_EVIDENCE",
                        "reason": "exact_public_registry_or_decision_contract_missing",
                    }
                )
            if args.tier2_registry is not None:
                exact = registry_rule(args.tier2_registry, args.tier2_candidate)
                report["tier2_public"]["exact_registry_anchor"] = public_physics.replay(
                    public_panel,
                    traits,
                    exact,
                    config["physics_sweep"],
                    bootstrap=config["bootstrap"],
                    with_physics=wrapper,
                )
        print("SCORE LAB PHYSICS — SYNTHETIC DEVELOPMENT ONLY")
        print(
            f"{len(report['rows'])} rule × switch rows; "
            f"{len(report['sensitivity']['table'])} sensitivity settings"
        )
        for entry in report["sensitivity"]["table"]:
            changed = {
                switch: len(moved)
                for switch, moved in entry["changed_positions"].items()
                if moved
            }
            print(
                f"{entry['lever']}={json.dumps(entry['setting'], sort_keys=True)} "
                f"changed rule positions by switch: {changed}"
            )
        print(
            f"physics switch effects: {len(report['physics_verdict']['effects'])}; "
            "descriptive only, no owner value selected"
        )
        _write(args.out, report)
        return 0
    if args.command == "prepare-ev4":
        panel = public_ev4.build(args.public_dir, args.repository)
        with gzip.open(args.out, "wt", encoding="utf-8") as handle:
            json.dump(panel, handle, sort_keys=True)
        print(f"public EV4 cache: {len(panel['members'])} members; {args.out}")
        return 0
    if args.command == "bank-check":
        optional = lambda path: (
            None if path is None else json.loads(path.read_text(encoding="utf-8"))
        )
        result = bank.check(
            optional(args.manifest),
            bank.read_records(args.records),
            definition_bytes=args.definition.read_bytes(),
            cheap=optional(args.cheap),
            reference_model=optional(args.reference_model),
            learnability=optional(args.learnability),
            cap=args.cap,
            kappa=args.kappa,
            unit=args.unit,
            ceiling_threshold=args.ceiling_threshold,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        _write(args.out, result)
        return 0
    rule = _load_rule(args)
    if args.command == "synthetic":
        configs = list(synthetic.profiles())
        if args.verification_costs:
            costs = [float(x) for x in args.verification_costs.split(",")]
            if not costs or any(not math.isfinite(x) or x <= 0 for x in costs):
                raise LabRefused("verification_costs_invalid")
            noncost = list(
                dict.fromkeys(
                    tuple(
                        (k, v)
                        for k, v in c.items()
                        if k != "verification_cost_ASSUMPTION"
                    )
                    for c in configs
                )
            )
            configs = [
                dict(items, verification_cost_ASSUMPTION=cost)
                for items in noncost
                for cost in costs
            ]
        if args.quick:
            configs = configs[:4]
        buyer = None
        if args.value_workflow == "v2-shortlist":
            cap = args.buyer_cap if args.buyer_cap is not None else args.cap
            unit = args.buyer_unit if args.buyer_unit is not None else args.unit
            if (
                not isinstance(cap, int)
                or cap < 1
                or not isinstance(unit, (int, float))
                or not math.isfinite(unit)
                or unit <= 0
            ):
                raise LabRefused("buyer_workflow_human_input_required")
            buyer = {"cap": cap, "unit": unit}
        panels = [
            synthetic.build(c, questions_per_side=args.questions_per_side, buyer=buyer)
            for c in configs
        ]
    else:
        with (
            gzip.open(args.cache, "rt", encoding="utf-8")
            if args.cache.suffix == ".gz"
            else args.cache.open("r", encoding="utf-8")
        ) as handle:
            panels = [json.load(handle)]
    if args.gate_json:
        gate = json.loads(args.gate_json)
        if not score_gate_valid(gate):
            raise LabRefused("v2_gate_malformed")
        for panel in panels:
            panel.setdefault("score_metadata", {})["v2_gate"] = gate
    if args.candidates:
        specs, digest = candidates.load(args.candidates)
        selected = [args.candidate] if args.candidate else list(specs)
        if any(name not in specs for name in selected):
            raise LabRefused("candidate_not_registered")
        results = {}
        for name in selected:
            rows = []
            for panel in panels:
                rule = candidates.rule_from_spec(
                    name,
                    specs[name],
                    path_digest=digest,
                    panel=panel,
                    registry_v5=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v5.json"
                    ),
                    registry_v9=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v9.json"
                    ),
                    registry_v10=Path(
                        "docs/development/evidence/battery-score-tuning/registry-v10.json"
                    ),
                )
                rows.append(
                    analyze(panel, rule, bootstrap=args.bootstrap)
                    if rule
                    else {
                        "status": "INSUFFICIENT_EVIDENCE",
                        "reason": "exact_public_registry_or_decision_contract_missing",
                    }
                )
            print(f"CANDIDATE {name} (proxy on toys; exact registry on public EV4)")
            results[name] = _report(rows)
        result = {
            "status": "DEVELOPMENT_DIAGNOSTIC",
            "candidates_sha256": digest,
            "candidates": results,
        }
        _write(args.out, result)
        return 0
    rows = [analyze(panel, rule, bootstrap=args.bootstrap) for panel in panels]
    result = _report(rows)
    _write(args.out, result)
    return 0


def score_gate_valid(gate):
    from carbon.battery.value import score_tuning

    return score_tuning._valid_gate(gate) and gate["measure"] == "feasibility"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabRefused as exc:
        raise SystemExit(f"SCORE_LAB_REFUSED: {exc.code}") from None
