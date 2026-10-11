"""Public-input/synthetic statistical audit, never a solver or official evaluator.

The explicitly supplied input directory is read-only. Outputs are aggregate
diagnostics, not a production error guarantee. No original script is executed.
"""

from __future__ import annotations

import argparse
import hashlib
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
    args = parser.parse_args()
    inputs, output = args.inputs.resolve(), args.output.resolve()
    if output == inputs or inputs in output.parents:
        parser.error("input directory is read-only; output must be elsewhere")
    result = run(inputs, args.trials, args.seed)
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
