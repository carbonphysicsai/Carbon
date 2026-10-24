"""Proof suite for the pool grader (spec POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024, section 3).

Run per Challenge on each new evaluation version, before launch. Aggregates only: nothing here returns a
pool point, a pick or a truth beyond counts, curves and scores. Each test reports PASS, FAIL or
REPORT_ONLY (no pass rule is specified for coverage) with its numbers.

A Challenge supplies a `ProofPlugin`: its sealed sets (built with `pool_grader.build_target`), a fresh
draw factory, the TRAIN box for the in-distribution control, its real models (TRAIN-fit, default,
good), and `legs(descriptor, specs)` giving its A and C legs on the sealed cases for a model named by a
descriptor (a plain dict, below). Nothing in this module names a Challenge.

Models are named by descriptors so that the pool-side half (D and A_gen) is built here, generically,
from the pool truths, while the plugin builds the matching model on its own A and C cases:
  {"kind": "oracle"}
  {"kind": "noisy", "k": k, "mode": "random" | "feasible_bias", "seed": s}
        truth + k*U per output with a seeded sign; feasible_bias makes every limit margin k*U safer
  {"kind": "in_distribution"}        the plugin's TRAIN-fit model, designs clamped to the TRAIN box
  {"kind": "wrong_near_optimum", "radius": r, "k": k, "seed": s}
        exact except within normalised radius r of each target's reference optimum, where it is `noisy`
  {"kind": "default"}, {"kind": "good"}   the plugin's real models
  {"kind": "perturbed", "base": descriptor, "layers": [[seed, step], ...]}
        the base model plus seeded noise of step*U per output per layer (the leak attack's miner)

Every threshold, grid and count is a required argument (`SuiteParams`, `Policies`); the owner picks them
from the curves this suite reports. The rules taken from the spec as written: the separation rule's
max(0.10, 5 x KOTH margin) and the leak rule's margin + 2 standard errors.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from itertools import pairwise

from carbon.scoring import pool_grader

DESCRIPTOR_KINDS = (
    "oracle",
    "noisy",
    "in_distribution",
    "wrong_near_optimum",
    "default",
    "good",
    "perturbed",
)


@dataclass(frozen=True)
class Policies:
    """How a set is scored end to end: the grader's policies and the A / C combination (all OWNER)."""

    optimizer: pool_grader.OptimizerPolicy
    honesty: pool_grader.HonestyPolicy
    agen_scales: dict
    a_rule: dict
    c_rule: dict


@dataclass(frozen=True)
class SuiteParams:
    oracle_tolerance: float  # how close to 1.0 the oracle must score (a real grader's reference uncertainty keeps it just under)
    k_grid: tuple  # strictness curve: injected error in multiples of U
    monotone_tolerance: float
    optimism_k: float  # gaming control: every limit margin this many U safer than truth
    wrong_radius: (
        float  # gaming control: normalised radius around each reference optimum
    )
    wrong_k: float
    leak_rounds: int
    leak_step: float  # in multiples of U per perturbation layer
    ladder_decimals: int  # the Ladder total's rounding
    koth_margin: float
    near_optimum_radius: float  # coverage: normalised radius around the reference
    near_limit_u: (
        float  # coverage: "near a limit" means a true margin below this many U
    )
    bins: int  # coverage: bins per design variable
    separation_target: (
        float  # good must score at or below this (0.80, pending the owner)
    )
    seed: int
    resamples: int  # bootstrap resamples for a standard error


@dataclass(frozen=True)
class ProofPlugin:
    sets: tuple  # tuple of tuples of pool_grader.TargetSpec
    fresh_set: (
        object  # callable(draw_seed) -> tuple of TargetSpec, drawn from the same region
    )
    train_box: object  # callable(spec) -> ((lo, hi), ...) in design units
    train_model: object  # predict(conditions, designs), fit on TRAIN
    default_model: object
    good_model: object
    legs: object  # callable(descriptor, specs) -> {"A": a, "C": c} (optionally "A_se")


def _key(conditions):
    return json.dumps(conditions, sort_keys=True, separators=(",", ":"))


def _sign(*parts):
    raw = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).digest()
    return 1.0 if raw[0] & 1 else -1.0


class _Universe:
    """Every target the models may be asked about, found by their conditions and design vector."""

    def __init__(self, specs):
        self.specs = {}
        self.table = {}
        for spec in specs:
            key = _key(spec.conditions)
            if key in self.specs:
                raise pool_grader.PoolRefused(
                    "target_conditions_must_identify_one_target"
                )
            self.specs[key] = spec
            for index, design in enumerate(spec.designs):
                self.table[(key, design)] = index

    def lookup(self, conditions, design):
        key = _key(conditions)
        spec = self.specs[key]
        return spec, self.table[(key, tuple(float(x) for x in design))]


def pool_predictor(plugin, descriptor, specs):
    """The predict(conditions, designs) callable for a descriptor, over the pool's designs."""
    kind = descriptor.get("kind")
    if kind not in DESCRIPTOR_KINDS:
        raise pool_grader.PoolRefused("unknown_model_descriptor")
    universe = _Universe(specs)
    if kind == "default":
        return plugin.default_model
    if kind == "good":
        return plugin.good_model
    if kind == "perturbed":
        base = pool_predictor(plugin, descriptor["base"], specs)
        layers = descriptor["layers"]

        def perturbed(conditions, designs):
            out = []
            for design, prediction in zip(designs, base(conditions, designs)):
                spec, _ = universe.lookup(conditions, design)
                out.append(
                    {
                        name: value
                        + sum(
                            step
                            * spec.u[name]
                            * _sign(seed, "layer", _key(conditions), list(design), name)
                            for seed, step in layers
                        )
                        for name, value in prediction.items()
                    }
                )
            return out

        return perturbed
    if kind == "in_distribution":

        def clamped(conditions, designs):
            spec = universe.specs[_key(conditions)]
            box = plugin.train_box(spec)
            return plugin.train_model(
                conditions,
                [
                    [min(hi, max(lo, x)) for x, (lo, hi) in zip(design, box)]
                    for design in designs
                ],
            )

        return clamped
    k = descriptor.get("k", 0.0)
    seed = descriptor.get("seed", 0)

    def truth_based(conditions, designs):
        out = []
        for design in designs:
            spec, index = universe.lookup(conditions, design)
            truth = dict(spec.truths[index])
            if kind == "oracle":
                out.append(truth)
            elif kind == "noisy" and descriptor["mode"] == "feasible_bias":
                for limit in spec.limits:
                    shift = k * spec.u[limit.output]
                    truth[limit.output] += shift if limit.kind == ">=" else -shift
                out.append(truth)
            elif kind == "noisy" and descriptor["mode"] == "random":
                out.append(_random_error(spec, conditions, design, truth, k, seed))
            elif kind == "wrong_near_optimum":
                reference = spec.norm[spec.reference]
                distance = math.dist(reference, spec.norm[index])
                out.append(
                    _random_error(spec, conditions, design, truth, k, seed)
                    if distance <= descriptor["radius"]
                    else truth
                )
            else:
                raise pool_grader.PoolRefused("unknown_noisy_mode")
        return out

    return truth_based


def _random_error(spec, conditions, design, truth, k, seed):
    return {
        name: value
        + k * spec.u[name] * _sign(seed, "noise", _key(conditions), list(design), name)
        for name, value in truth.items()
    }


def _mean_over_sets(sets, fn):
    return statistics.fmean(fn(specs) for specs in sets)


def score_specs(plugin, specs, descriptor, policies, all_specs):
    """TOP for one set of targets: 0.5 A + 0.5 D with the C rule, A_gen entering A by the owner's rule."""
    predict = pool_predictor(plugin, descriptor, all_specs)
    grade = pool_grader.grade_set(specs, predict, policies.optimizer, policies.honesty)
    legs = plugin.legs(descriptor, specs)
    a_gen = pool_grader.agen_accuracy(specs, predict, policies.agen_scales)
    a = pool_grader.combine_a(legs["A"], a_gen, policies.a_rule)
    # A failed mandatory gate gives no score (the plugin reports `gates_ok`; absent means no gate to fail).
    if legs.get("gates_ok") is False:
        return 0.0, grade, a_gen, legs
    return pool_grader.total(a, grade.d, legs["C"], policies.c_rule), grade, a_gen, legs


def version_total(plugin, descriptor, policies):
    """A model's total over all of the version's sets (the mean over sets), unrounded."""
    all_specs = [spec for specs in plugin.sets for spec in specs]
    return _mean_over_sets(
        plugin.sets,
        lambda specs: score_specs(plugin, specs, descriptor, policies, all_specs)[0],
    )


def _verdict(passed, numbers):
    return {"verdict": "PASS" if passed else "FAIL", "numbers": numbers}


def check_oracle_is_perfect(plugin, policies, params):
    """1. A model returning the pool truths exactly scores 1.0 on every leg and reaches every target's reference."""
    all_specs = [spec for specs in plugin.sets for spec in specs]
    oracle = {"kind": "oracle"}
    reached = targets = 0
    legs_ok = True
    totals, ds, a_gens, queries = [], [], [], {}
    for specs in plugin.sets:
        total, grade, a_gen, legs = score_specs(
            plugin, specs, oracle, policies, all_specs
        )
        totals.append(total)
        ds.append(grade.d)
        a_gens.append(a_gen)
        queries.update({t.target_id: t.queries for t in grade.targets})
        reached += sum(t.reached_reference for t in grade.targets)
        targets += len(grade.targets)
        tol = params.oracle_tolerance
        legs_ok &= (
            math.isclose(legs["A"], 1.0, abs_tol=tol)
            and math.isclose(legs["C"], 1.0, abs_tol=tol)
            and (a_gen is None or math.isclose(a_gen, 1.0, abs_tol=tol))
            and legs.get("gates_ok") is not False
        )
    passed = (
        legs_ok
        and reached == targets
        and all(math.isclose(t, 1.0, abs_tol=params.oracle_tolerance) for t in totals)
    )
    note = (
        None
        if reached == targets
        else "the oracle missed a reference optimum within B: B or the pool is too small (back to the owner)"
    )
    return _verdict(
        passed,
        {
            "totals": totals,
            "d": ds,
            "reached": reached,
            "targets": targets,
            "queries": queries,
            "note": note,
        },
    )


def check_strictness_curve(plugin, policies, params):
    """2. Oracle plus injected error at k x U: the total falls monotonically with k, both random and feasible-biased."""
    curves, passed = {}, True
    for mode in ("random", "feasible_bias"):
        points = [
            (
                k,
                version_total(
                    plugin,
                    {"kind": "noisy", "k": k, "mode": mode, "seed": params.seed},
                    policies,
                ),
            )
            for k in params.k_grid
        ]
        curves[mode] = points
        passed &= all(
            later <= earlier + params.monotone_tolerance
            for (_, earlier), (_, later) in pairwise(points)
        )
    return _verdict(passed, {"curves": curves})


def check_gaming_controls_lose(plugin, policies, params):
    """3. Each gaming control scores below the good model."""
    controls = {
        "optimistic_near_limits": {
            "kind": "noisy",
            "k": params.optimism_k,
            "mode": "feasible_bias",
            "seed": params.seed,
        },
        "in_distribution_only": {"kind": "in_distribution"},
        "wrong_near_the_optimum": {
            "kind": "wrong_near_optimum",
            "radius": params.wrong_radius,
            "k": params.wrong_k,
            "seed": params.seed,
        },
        "default_model": {"kind": "default"},
    }
    good = version_total(plugin, {"kind": "good"}, policies)
    scores = {name: version_total(plugin, d, policies) for name, d in controls.items()}
    return _verdict(
        all(s < good for s in scores.values()), {"good": good, "controls": scores}
    )


def _bin_share(spec, indices, bins):
    """The mean over design variables of the share of `bins` equal bins of that variable's range holding a point."""
    if not indices:
        return None
    return statistics.fmean(
        len({min(bins - 1, int(spec.norm[i][d] * bins)) for i in indices}) / bins
        for d in range(len(spec.box))
    )


def check_coverage(plugin, params, queries_per_target=None):
    """4. Where the pool sits: near each optimum and limit, the share of each variable's range covered, the A_gen
    slice's spread. REPORT_ONLY: the spec gives no pass rule."""
    rows = []
    for specs in plugin.sets:
        for spec in specs:
            reference = spec.norm[spec.reference]
            near_optimum = sum(
                1
                for i in spec.queryable
                if math.dist(reference, spec.norm[i]) <= params.near_optimum_radius
            )
            near_limit = {}
            for limit in spec.limits:
                near_limit[f"{limit.output}{limit.kind}"] = sum(
                    1
                    for t in spec.truths
                    if 0.0
                    <= limit.margin(t[limit.output])
                    <= params.near_limit_u * spec.u[limit.output]
                )
            rows.append(
                {
                    "target": spec.target_id,
                    "pool": len(spec.designs),
                    "excluded_for_u": spec.excluded,
                    "near_optimum": near_optimum,
                    "near_limit": near_limit,
                    "box_share": _bin_share(
                        spec, range(len(spec.designs)), params.bins
                    ),
                    "agen_points": len(spec.agen),
                    "agen_box_share": _bin_share(spec, spec.agen, params.bins),
                    "queries": (
                        None
                        if queries_per_target is None
                        else queries_per_target.get(spec.target_id)
                    ),
                }
            )
    return {"verdict": "REPORT_ONLY", "numbers": {"targets": rows}}


def bootstrap_se(values, seed, resamples):
    """Standard error of the mean by case bootstrap, seeded: the same rule the weekly overfit check uses."""
    if len(values) < 2:
        return 0.0
    rng = random.Random(seed)
    means = [
        statistics.fmean(rng.choice(values) for _ in values) for _ in range(resamples)
    ]
    return statistics.stdev(means)


def leak_threshold(margin, se_sealed, se_fresh):
    """The weekly overfit check's rule (carbon.challenge_validator.exam_rotation.threshold): the sealed total may
    exceed the fresh total by no more than margin + 2 sqrt(se_sealed^2 + se_fresh^2)."""
    return margin + 2.0 * math.sqrt(se_sealed**2 + se_fresh**2)


def _total_and_se(plugin, descriptor, policies, sets, all_specs, params):
    per_set, d_values, a_ses = [], [], []
    for specs in sets:
        total, grade, _, legs = score_specs(
            plugin, specs, descriptor, policies, all_specs
        )
        per_set.append(total)
        d_values += [t.d for t in grade.targets]
        a_ses.append(legs.get("A_se", 0.0))
    se_d = 0.5 * bootstrap_se(d_values, params.seed, params.resamples)
    se_a = 0.5 * (statistics.fmean(a_ses) if a_ses else 0.0)
    return statistics.fmean(per_set), math.hypot(se_d, se_a)


def check_leak_attack(plugin, policies, params):
    """5. A simulated miner hill-climbs on the ROUNDED Ladder total by submitting perturbations of the good model over
    many rounds. Pass: its sealed-set gain over a fresh set from the same region stays within the KOTH margin plus
    2 standard errors (the weekly overfit rule)."""
    fresh = tuple(plugin.fresh_set(params.seed))
    all_specs = [spec for specs in plugin.sets for spec in specs] + list(fresh)
    base = {"kind": "good"}
    layers = []

    def sealed_rounded(current_layers):
        descriptor = {"kind": "perturbed", "base": base, "layers": current_layers}
        total = _mean_over_sets(
            plugin.sets,
            lambda specs: score_specs(plugin, specs, descriptor, policies, all_specs)[
                0
            ],
        )
        return round(total, params.ladder_decimals)

    best = sealed_rounded(layers)
    accepted = 0
    for round_index in range(params.leak_rounds):
        trial = layers + [[params.seed * 1_000_003 + round_index, params.leak_step]]
        score = sealed_rounded(trial)
        if score > best:
            best, layers, accepted = score, trial, accepted + 1
    descriptor = {"kind": "perturbed", "base": base, "layers": layers}
    sealed_total, se_sealed = _total_and_se(
        plugin, descriptor, policies, plugin.sets, all_specs, params
    )
    fresh_total, se_fresh = _total_and_se(
        plugin, descriptor, policies, (fresh,), all_specs, params
    )
    gain = sealed_total - fresh_total
    threshold = leak_threshold(params.koth_margin, se_sealed, se_fresh)
    return _verdict(
        gain <= threshold,
        {
            "rounds": params.leak_rounds,
            "accepted": accepted,
            "ladder_score_after": best,
            "sealed_total": sealed_total,
            "fresh_total": fresh_total,
            "gain": gain,
            "threshold": threshold,
            "se_sealed": se_sealed,
            "se_fresh": se_fresh,
        },
    )


def separation(good_total, default_total, *, target, koth_margin):
    """6. Good at or below the owner's target, and default at least max(0.10, 5 x KOTH margin) below good."""
    needed_gap = max(0.10, 5.0 * koth_margin)
    return _verdict(
        good_total <= target and default_total <= good_total - needed_gap,
        {
            "good": good_total,
            "default": default_total,
            "target": target,
            "needed_gap": needed_gap,
            "gap": good_total - default_total,
        },
    )


def run_suite(plugin, policies, params):
    """All six tests. Returns {name: {"verdict", "numbers"}}; nothing in it is a pool point, a pick or a truth."""
    pool_grader._check_policies(policies.optimizer, policies.honesty)
    oracle = check_oracle_is_perfect(plugin, policies, params)
    queries = oracle["numbers"]["queries"]
    report = {
        "1_oracle": oracle,
        "2_strictness": check_strictness_curve(plugin, policies, params),
        "3_gaming_controls": check_gaming_controls_lose(plugin, policies, params),
        "4_coverage": check_coverage(plugin, params, queries),
        "5_leak_attack": check_leak_attack(plugin, policies, params),
    }
    report["6_separation"] = separation(
        version_total(plugin, {"kind": "good"}, policies),
        version_total(plugin, {"kind": "default"}, policies),
        target=params.separation_target,
        koth_margin=params.koth_margin,
    )
    report["all_pass"] = all(
        v["verdict"] != "FAIL"
        for k, v in report.items()
        if isinstance(v, dict) and "verdict" in v
    )
    return report
