"""Public-input/synthetic statistical audit, never a solver or official evaluator.

The explicitly supplied input directory is read-only. Outputs are aggregate
diagnostics, not a production error guarantee. No original script is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from pathlib import Path
from statistics import NormalDist

import numpy as np

NORMAL = NormalDist()
INPUT_NAMES = (
    "MARGIN_SIZING_02.md",
    "MARGIN_SIZING_03.md",
    "MARGIN_SIZING_04.md",
    "PROPOSAL.md",
    "margin_02.json",
    "margin_03.json",
    "margin_04.json",
    "analysis.json",
    "paired.json",
    "m04.py",
    "margin_02.py",
    "margin_03.py",
    "margin_sizing.py",
    "paired.py",
)


def wilson(count: int, trials: int) -> list[float]:
    """Point/95% Wilson interval; Monte Carlo uncertainty only."""
    if trials <= 0 or not 0 <= count <= trials:
        raise ValueError("invalid binomial counts")
    z = NORMAL.inv_cdf(0.975)
    p = count / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials**2))
    half /= denominator
    return [max(0.0, center - half), p, min(1.0, center + half)]


def boundary(n: int, sigma: float, alpha: float, counts: np.ndarray) -> np.ndarray:
    """M04's positive crossing of a normal-mixture boundary."""
    if n <= 0 or sigma <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid boundary inputs")
    rho = n * sigma**2
    variance = counts * sigma**2
    return np.sqrt((variance + rho) * np.log((variance + rho) / (rho * alpha**2)))


def crossings(increments: np.ndarray, n: int, sigma: float, alpha: float) -> np.ndarray:
    if increments.ndim != 2:
        raise ValueError("expected trials by rounds")
    counts = n * np.arange(1, increments.shape[1] + 1)
    return np.any(
        np.cumsum(increments, axis=1) >= boundary(n, sigma, alpha, counts), axis=1
    )


def original_null_count() -> int:
    """Independent transcription preserving M04's RNG order and early stop."""
    rng = random.Random(3)
    n, sigma, alpha, rounds, trials = 2000, 0.46, 0.05, 14, 6000
    rho = n * sigma**2
    wins = 0
    for _ in range(trials):
        total = 0.0
        for round_index in range(1, rounds + 1):
            total += rng.gauss(0.0, sigma * math.sqrt(n))
            variance = round_index * n * sigma**2
            threshold = math.sqrt(
                (variance + rho) * math.log((variance + rho) / (rho * alpha**2))
            )
            if total >= threshold:
                wins += 1
                break
    return wins


def holm_rejections(z_scores: np.ndarray, alpha: float) -> np.ndarray:
    """Actual step-down Holm for one-sided known-normal z tests.

    These are ordinary fixed-round p-values, not carry-forward p-processes.
    Arbitrary within-round contender correlation is permitted if each is valid.
    """
    if z_scores.ndim != 2 or not 0 < alpha < 1:
        raise ValueError("invalid Holm input")
    contenders = z_scores.shape[1]
    if contenders == 0:
        raise ValueError("empty cohort")
    order = np.argsort(-z_scores, axis=1)
    ranked = np.take_along_axis(z_scores, order, axis=1)
    cutoffs = np.array(
        [NORMAL.inv_cdf(1 - alpha / (contenders - rank)) for rank in range(contenders)]
    )
    ranked_reject = np.logical_and.accumulate(ranked >= cutoffs, axis=1)
    rejected = np.zeros_like(ranked_reject)
    np.put_along_axis(rejected, order, ranked_reject, axis=1)
    return rejected


def rate_record(mask: np.ndarray) -> dict:
    count = int(mask.sum())
    trials = int(mask.size)
    return {
        "false_crossings": count,
        "trials": trials,
        "wilson95_low_point_high": wilson(count, trials),
    }


def synthetic_audit(trials: int, seed: int) -> list[dict]:
    """Declared stresses, not estimates of a private bank's distributions."""
    rng = np.random.default_rng(seed)
    rounds, sigma, alpha = 14, 0.46, 0.05
    rows = []
    for n in (2000, 3000):
        z = rng.standard_normal((trials, rounds))
        scale = sigma * math.sqrt(n)
        for multiplier in (1.0, 1.25, 1.5, 2.0):
            rows.append(
                {
                    "scenario": "normal_variance_misspecification",
                    "N": n,
                    "actual_sd_multiplier": multiplier,
                    "assumption": "independent Gaussian rounds; declared proxy SD remains 0.46",
                    **rate_record(crossings(z * scale * multiplier, n, sigma, alpha)),
                }
            )
        for phi in (0.25, 0.5, 0.75, 0.9):
            correlated = z.copy()
            for r in range(1, rounds):
                correlated[:, r] = (
                    phi * correlated[:, r - 1] + math.sqrt(1 - phi**2) * z[:, r]
                )
            rows.append(
                {
                    "scenario": "stationary_AR1_round_shocks",
                    "N": n,
                    "phi": phi,
                    "assumption": "marginal round variance unchanged; carry variance ignores covariance",
                    **rate_record(crossings(correlated * scale, n, sigma, alpha)),
                }
            )
        for probability in (0.001, 0.01, 0.05):
            positive = math.sqrt((1 - probability) / probability)
            negative = -math.sqrt(probability / (1 - probability))
            shocks = np.where(
                rng.random((trials, rounds)) < probability, positive, negative
            )
            rows.append(
                {
                    "scenario": "rare_positive_round_shock",
                    "N": n,
                    "positive_probability": probability,
                    "assumption": "independent, zero-mean/unit-variance batch shocks, not IID case noise",
                    **rate_record(crossings(shocks * scale, n, sigma, alpha)),
                }
            )
        heavy = rng.standard_t(3, size=(trials, rounds)) / math.sqrt(3)
        rows.append(
            {
                "scenario": "student_t3_round_shocks",
                "N": n,
                "assumption": "independent, zero-mean/unit-variance batch shocks; no sub-Gaussian MGF",
                **rate_record(crossings(heavy * scale, n, sigma, alpha)),
            }
        )
    return rows


def daily_holm_audit(trials: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rounds, alpha = 14, 0.05
    rows = []
    for contenders in (1, 5, 20):
        for correlation in (0.0, 0.5, 0.9):
            shared = rng.standard_normal((trials, rounds, 1))
            independent = rng.standard_normal((trials, rounds, contenders))
            z = (
                math.sqrt(correlation) * shared
                + math.sqrt(1 - correlation) * independent
            )
            rejected = holm_rejections(z.reshape(-1, contenders), alpha)
            events = rejected.reshape(trials, rounds, contenders).any(axis=2)
            rows.append(
                {
                    "scenario": "daily_fixed_round_Holm_all_null",
                    "contenders": contenders,
                    "within_round_correlation": correlation,
                    "assumption": "fresh independent rounds; no carry-forward branch or incumbent changes",
                    "day1": rate_record(events[:, 0]),
                    "any_of_14_days": rate_record(events.any(axis=1)),
                }
            )
    return rows


def fingerprint_inputs(root: Path) -> list[dict]:
    records = []
    for name in INPUT_NAMES:
        content = (root / name).read_bytes()
        records.append(
            {
                "name": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return records


def empirical_audit(rows_path: Path, trials: int, seed: int) -> dict:
    """Conditional public-case bootstrap, not new physical/reference cases.

    The same multinomial counts resample whole contender vectors. Centering
    imposes an all-null counterfactual; batch reuse is an explicit stress.
    """
    content = rows_path.read_bytes()
    records = [
        json.loads(line)
        for line in content.decode("utf-8").splitlines()
        if line.strip()
    ]
    if trials <= 0 or not records:
        raise ValueError("empty empirical audit")
    errors, important = {}, {}
    for record in records:
        if record["exit"] != 0:
            raise ValueError("failed source run")
        key = (record["member"], record["seed"])
        if key in errors:
            raise ValueError("duplicate source artifact/seed")
        errors[key] = {}
        for row in record["rows"]:
            case_id = row["case_id"]
            if not case_id.startswith("practice-"):
                raise ValueError("only explicitly public PRACTICE rows permitted")
            if case_id in errors[key] or not math.isfinite(row["error"]):
                raise ValueError("duplicate case or invalid error")
            errors[key][case_id] = row["error"]
            if case_id in important and important[case_id] != row["important"]:
                raise ValueError("inconsistent case metadata")
            important[case_id] = row["important"]
    case_sets = [set(value) for value in errors.values()]
    if any(value != case_sets[0] for value in case_sets):
        raise ValueError("public runs do not share identical cases")
    ids = sorted(case_sets[0])
    members = sorted({member for member, _ in errors if member.startswith("stage-a")})
    if len(members) < 2 or any((member, 1) not in errors for member in members):
        raise ValueError("missing public MLP seed-one panel")
    matrix = np.array(
        [[errors[(member, 1)][case_id] for member in members] for case_id in ids]
    )
    pairs = list(itertools.combinations(range(len(members)), 2))
    differences = np.column_stack([matrix[:, a] - matrix[:, b] for a, b in pairs])
    bases = np.array(
        [(matrix[:, a].mean() + matrix[:, b].mean()) / 2 for a, b in pairs]
    )
    centered = differences - differences.mean(axis=0)
    sigma = centered.std(axis=0, ddof=0)
    if np.any(sigma <= 0) or np.any(bases <= 0):
        raise ValueError("degenerate empirical contrast")
    standardized = centered / sigma
    diagnostics = []
    for index, (a, b) in enumerate(pairs):
        squares = np.sort(centered[:, index] ** 2)
        top_count = max(1, math.ceil(len(ids) * 0.05))
        diagnostics.append(
            {
                "pair": f"M{a + 1}-M{b + 1}",
                "correlation": float(np.corrcoef(matrix[:, a], matrix[:, b])[0, 1]),
                "sample_sd_relative_pair_average": float(
                    differences[:, index].std(ddof=1) / bases[index]
                ),
                "empirical_population_sd_relative_pair_average": float(
                    sigma[index] / bases[index]
                ),
                "skewness_centered": float(np.mean(standardized[:, index] ** 3)),
                "excess_kurtosis_centered": float(
                    np.mean(standardized[:, index] ** 4) - 3
                ),
                "largest_abs_centered_in_sd": float(
                    np.max(np.abs(standardized[:, index]))
                ),
                "top_5_percent_cases_variance_share": float(
                    squares[-top_count:].sum() / squares.sum()
                ),
            }
        )
    rng = np.random.default_rng(seed)
    n, rounds, alpha = 3000, 14, 0.05
    increments = np.empty((trials, rounds, len(pairs)))
    probabilities = np.full(len(ids), 1 / len(ids))
    for round_index in range(rounds):
        counts = rng.multinomial(n, probabilities, size=trials)
        increments[:, round_index, :] = counts @ centered
    scenarios = []
    for label, reuse, proxy in (
        ("IID_correct_empirical_population_sd", 1, sigma),
        ("IID_fixed_median_relative_proxy", 1, 0.46 * bases),
        ("reused_batch_twice_counted_as_fresh", 2, sigma),
        ("reused_batch_three_times_counted_as_fresh", 3, sigma),
    ):
        selected = increments[:, np.arange(rounds) // reuse, :]
        results = []
        for index, diag in enumerate(diagnostics):
            for sign in (1, -1):
                results.append(
                    {
                        "pair": diag["pair"],
                        "direction": sign,
                        **rate_record(
                            crossings(
                                sign * selected[:, :, index],
                                n,
                                float(proxy[index]),
                                alpha,
                            )
                        ),
                    }
                )
        scenarios.append(
            {
                "scenario": label,
                "assumption": "empirical centered case vectors IID with replacement; reuse is deliberately not fresh evidence",
                "distinct_batches": math.ceil(rounds / reuse),
                "pairs": results,
            }
        )
    power = []
    for index, diag in enumerate(diagnostics):
        for alpha_art in (0.05, 0.01):
            for delta in (0.01, 0.02, 0.03):
                for sign in (1, -1):
                    shifted = sign * increments[:, :, index] + delta * bases[index] * n
                    thresholds = boundary(
                        n, float(sigma[index]), alpha_art, n * np.arange(1, rounds + 1)
                    )
                    events = np.maximum.accumulate(
                        np.cumsum(shifted, axis=1) >= thresholds, axis=1
                    )
                    rates = events.mean(axis=0)
                    reached = np.flatnonzero(rates >= 0.8)
                    power.append(
                        {
                            "pair": diag["pair"],
                            "direction": sign,
                            "alpha_art": alpha_art,
                            "assumed_relative_pair_average_gain": delta,
                            "rounds_to_80_percent_point_estimate": (
                                int(reached[0] + 1) if reached.size else None
                            ),
                            "win_by_14_rounds": {
                                "wins": int(events[:, -1].sum()),
                                "trials": trials,
                                "wilson95_low_point_high": wilson(
                                    int(events[:, -1].sum()), trials
                                ),
                            },
                        }
                    )
    # The first len(members)-1 combinations share M1 as incumbent.
    cohort_size = len(members) - 1
    z = increments[:, :, :cohort_size] / (sigma[:cohort_size] * math.sqrt(n))
    events = (
        holm_rejections(z.reshape(-1, cohort_size), alpha)
        .reshape(trials, rounds, cohort_size)
        .any(axis=2)
    )
    return {
        "status": "EMPIRICAL_PUBLIC_CONDITIONAL_DIAGNOSTIC_NOT_PRODUCTION_VALIDATION",
        "source": {
            "name": "seed-variance-01/rows.jsonl",
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
        "source_run_count": len(records),
        "distinct_cases": len(ids),
        "distinct_recipes": len({member for member, _ in errors}),
        "source_eligible_runs": sum(
            bool(record["frozen_rule"]["eligible"]) for record in records
        ),
        "important_cases": sum(bool(important[case_id]) for case_id in ids),
        "seed_one_MLP_count": len(members),
        "alias_policy": "M1... in lexicographic public recipe-id order; no raw case/run identifiers published",
        "bootstrap_assumptions": "N=3000, 14 rounds, empirical vectors centered to zero mean; uniform IID sampling with replacement from public cases; not 3000 distinct physical cases",
        "bootstrap_trials": trials,
        "public_synthetic_seed": seed,
        "unidentified_dependence": "no source/time blocks supplied; case-id ordering is not chronological; round dependence is not estimated",
        "pair_diagnostics": diagnostics,
        "carry_null_scenarios": scenarios,
        "assumption_power_sensitivity": power,
        "normal_approximation_daily_Holm_shared_M1": {
            "cohort_size": cohort_size,
            "day1": rate_record(events[:, 0]),
            "any_of_14_days": rate_record(events.any(axis=1)),
            "limit": "normal-approximate p-values, fixed all-null centered cohort; not full adaptive championship",
        },
    }


def run(root: Path, trials: int, seed: int) -> dict:
    if trials <= 0:
        raise ValueError("trials must be positive")
    supplied = json.loads((root / "margin_04.json").read_text(encoding="utf-8"))
    reproduced = original_null_count()
    return {
        "ticket": "CHAMPIONSHIP-STATS-REVIEW-01",
        "maturity": "PUBLIC_DIAGNOSTIC_NOT_PRODUCTION_VALIDATION",
        "source_inputs": fingerprint_inputs(root),
        "synthetic_seed": seed,
        "synthetic_trials_per_scenario": trials,
        "numeric_policy": "scenarios are ASSUMPTION; intervals are Monte Carlo uncertainty only",
        "original_null_reproduction": {
            "N": 2000,
            "rounds": 14,
            "alpha_art": 0.05,
            "trials": 6000,
            "false_crossings": reproduced,
            "wilson95_low_point_high": wilson(reproduced, 6000),
            "supplied_rate": supplied["carry_forward_false_rate_14_rounds"],
            "matches": reproduced / 6000
            == supplied["carry_forward_false_rate_14_rounds"],
        },
        "synthetic_carry_stress": synthetic_audit(trials, seed),
        "daily_Holm_stress": daily_holm_audit(trials, seed + 1),
        "empirical_distribution_status": "GAP_PENDING_PUBLIC_PER_CASE_ROWS",
        "implemented_in_original": [
            "known-normal power formula",
            "single-artifact mixture crossing",
        ],
        "not_implemented_in_original": [
            "full Holm winner selection",
            "alpha-investing ledger",
            "incumbent changes",
            "combined fast-lane/carry error budget",
            "mandatory/important gates",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=40000)
    parser.add_argument("--seed", type=int, default=731)
    parser.add_argument("--empirical-rows", type=Path)
    parser.add_argument("--empirical-trials", type=int, default=10000)
    args = parser.parse_args()
    inputs, output = args.inputs.resolve(), args.output.resolve()
    if output == inputs or inputs in output.parents:
        parser.error("input directory is read-only; output must be elsewhere")
    if args.empirical_rows and (
        output == args.empirical_rows.resolve()
        or args.empirical_rows.resolve().parent in output.parents
    ):
        parser.error("empirical input directory is read-only; output must be elsewhere")
    result = run(inputs, args.trials, args.seed)
    if args.empirical_rows:
        result["empirical_public_audit"] = empirical_audit(
            args.empirical_rows, args.empirical_trials, args.seed + 2
        )
        result["empirical_distribution_status"] = (
            "PUBLIC_CASE_RESAMPLING_COMPLETE_REALISTIC_BANK_DEPENDENCE_UNVALIDATED"
        )
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "original": result["original_null_reproduction"],
                "stress_scenarios": len(result["synthetic_carry_stress"]),
            }
        )
    )


if __name__ == "__main__":
    main()
