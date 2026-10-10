"""Aggregate, assumption-labelled power planning for design questions.

This is a development sensitivity model, not a power estimate from settled
reference outcomes. It never reads producer exports or individual case data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

SCHEMA = "carbon.design-search.power-planning-assumptions.v1"
CONTROLS = ("edge_optimist", "over_cautious", "localized_sign_error", "path_aware")


def _positive_int(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _probability(value, label, *, lower=0.0, upper=1.0):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not lower < value < upper
    ):
        raise ValueError(f"{label} must be finite and between {lower} and {upper}")
    return float(value)


def validate_manifest(manifest):
    """Refuse missing assumptions and non-aggregate or inconsistent shapes."""
    if (
        type(manifest) is not dict
        or set(manifest)
        != {
            "schema",
            "alpha",
            "target_power",
            "replicates",
            "seed",
            "windows",
            "challenges",
        }
        or manifest["schema"] != SCHEMA
    ):
        raise ValueError("complete power-planning assumption manifest required")
    _probability(manifest["alpha"], "alpha", upper=0.5)
    _probability(manifest["target_power"], "target_power")
    _positive_int(manifest["replicates"], "replicates")
    if type(manifest["seed"]) is not int or manifest["seed"] < 0:
        raise ValueError("nonnegative deterministic seed required")
    windows = manifest["windows"]
    if type(windows) is not list or not windows or windows != sorted(set(windows)):
        raise ValueError("windows must be a sorted unique list")
    for value in windows:
        _positive_int(value, "window count")
    challenges = manifest["challenges"]
    if type(challenges) is not list or len(challenges) != 3:
        raise ValueError("battery, motor and f02 assumption rows required")
    if {row.get("name") for row in challenges if type(row) is dict} != {
        "battery_v3",
        "motor",
        "f02",
    }:
        raise ValueError("exact Challenge planning set required")
    for row in challenges:
        if type(row) is not dict or set(row) != {
            "name",
            "law_source",
            "panel_shape",
            "bank_questions",
            "bank_status",
            "independent_banks",
            "questions_per_batch",
            "exposure_limits",
            "buyer_units",
            "severity_levels",
            "effect_assumptions",
            "startup_eur_per_independent_panel",
        }:
            raise ValueError("complete Challenge planning row required")
        bank_questions = _positive_int(row["bank_questions"], "bank_questions")
        for key in ("independent_banks", "questions_per_batch", "exposure_limits"):
            values = row[key]
            if type(values) is not list or not values or values != sorted(set(values)):
                raise ValueError(f"{key} must be sorted and unique")
            for value in values:
                _positive_int(value, key)
        if row["independent_banks"][-1] > bank_questions:
            raise ValueError("independent banks exceed question count")
        if row["questions_per_batch"][-1] > bank_questions:
            raise ValueError("k exceeds question count")
        if type(row["law_source"]) is not str or not row["law_source"]:
            raise ValueError("law source required")
        if type(row["panel_shape"]) is not dict or not row["panel_shape"]:
            raise ValueError("aggregate panel shape required")
        if type(row["bank_status"]) is not str or not row["bank_status"]:
            raise ValueError("bank status required")
        units = row["buyer_units"]
        if (
            type(units) is not dict
            or not units
            or any(
                type(key) is not str or type(value) is not str or not value
                for key, value in units.items()
            )
        ):
            raise ValueError("buyer units required for every limit quantity")
        levels = row["severity_levels"]
        if type(levels) is not list or len(levels) not in (3, 4):
            raise ValueError("three or four severity levels required")
        names = set()
        for level in levels:
            if type(level) is not dict or set(level) != {"name", "by_quantity"}:
                raise ValueError("typed per-quantity severity required")
            name = level["name"]
            if type(name) is not str or not name or name in names:
                raise ValueError("unique severity level names required")
            names.add(name)
            if type(level["by_quantity"]) is not dict or set(
                level["by_quantity"]
            ) != set(units):
                raise ValueError("severity must cover every controlled quantity")
            for value in level["by_quantity"].values():
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or value <= 0
                ):
                    raise ValueError("positive finite severity in buyer units required")
        effects = row["effect_assumptions"]
        if type(effects) is not dict or set(effects) != set(CONTROLS):
            raise ValueError("all four behaviour controls required")
        for control, probabilities in effects.items():
            if type(probabilities) is not list or len(probabilities) != len(levels):
                raise ValueError(f"four level probabilities required for {control}")
            for probability in probabilities:
                _probability(
                    probability, "assumed positive-bank probability", lower=0.5
                )
        cost = row["startup_eur_per_independent_panel"]
        if type(cost) is not dict or set(cost) != {"low", "high", "basis"}:
            raise ValueError("explicit startup cost basis required")
        if (cost["low"] is None) != (cost["high"] is None):
            raise ValueError("cost bounds must both be available or absent")
        if cost["low"] is not None and (
            type(cost["low"]) not in (int, float)
            or type(cost["high"]) not in (int, float)
            or not math.isfinite(cost["low"])
            or not math.isfinite(cost["high"])
            or not 0 <= cost["low"] <= cost["high"]
        ):
            raise ValueError("invalid startup cost bounds")
        if type(cost["basis"]) is not str or not cost["basis"]:
            raise ValueError("startup cost basis required")


def exact_sign_power(independent_clusters, positive_probability, alpha):
    """Exact one-sided sign-test detection under an assumed Bernoulli effect."""
    if independent_clusters == 0:
        return 0.0
    n = independent_clusters
    threshold = next(
        (
            wins
            for wins in range(n + 1)
            if sum(math.comb(n, i) for i in range(wins, n + 1)) / 2**n <= alpha
        ),
        n + 1,
    )
    return sum(
        math.comb(n, wins)
        * positive_probability**wins
        * (1 - positive_probability) ** (n - wins)
        for wins in range(threshold, n + 1)
    )


def _path_cluster_counts(
    *, bank_questions, independent_banks, exposure, k, windows, seed
):
    """Sample distinct question IDs; charge every draw to shared-bank exposure."""
    rng = random.Random(seed)
    remaining = [exposure] * independent_banks
    seen = set()
    counts = []
    for _ in range(windows):
        available = list(range(bank_questions))
        for _ in range(k):
            eligible = [
                case for case in available if remaining[case % independent_banks] > 0
            ]
            if not eligible:
                return counts + [None] * (windows - len(counts))
            selected = rng.choice(eligible)
            available.remove(selected)
            cluster = selected % independent_banks
            remaining[cluster] -= 1
            seen.add(cluster)
        counts.append(len(seen))
    return counts


def _mean_and_error(values):
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, 0.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


def simulate(manifest):
    """Return only aggregate scenario rows; no case identity leaves this model."""
    validate_manifest(manifest)
    rows = []
    windows = manifest["windows"]
    maximum = windows[-1]
    for challenge in manifest["challenges"]:
        for banks in challenge["independent_banks"]:
            for exposure in challenge["exposure_limits"]:
                for k in challenge["questions_per_batch"]:
                    paths = [
                        _path_cluster_counts(
                            bank_questions=challenge["bank_questions"],
                            independent_banks=banks,
                            exposure=exposure,
                            k=k,
                            windows=maximum,
                            seed=f"{manifest['seed']}:{challenge['name']}:{banks}:{exposure}:{k}:{replicate}",
                        )
                        for replicate in range(manifest["replicates"])
                    ]
                    for window in windows:
                        counts = [path[window - 1] for path in paths]
                        feasible = [count for count in counts if count is not None]
                        feasibility = len(feasible) / len(counts)
                        for control in CONTROLS:
                            for index, level in enumerate(challenge["severity_levels"]):
                                positive = challenge["effect_assumptions"][control][
                                    index
                                ]
                                estimates = [
                                    exact_sign_power(count, positive, manifest["alpha"])
                                    for count in feasible
                                ]
                                if feasibility == 1:
                                    detection, error = _mean_and_error(estimates)
                                    mean_clusters = sum(feasible) / len(feasible)
                                else:
                                    detection = error = mean_clusters = None
                                rows.append(
                                    {
                                        "challenge": challenge["name"],
                                        "bank_questions_B": challenge["bank_questions"],
                                        "independent_bank_clusters_ASSUMPTION": banks,
                                        "exposure_E_ASSUMPTION": exposure,
                                        "questions_per_batch_k": k,
                                        "windows": window,
                                        "control": control,
                                        "severity_level": level["name"],
                                        "positive_bank_probability_ASSUMPTION": positive,
                                        "exposure_feasible_probability": feasibility,
                                        "detection_probability_ASSUMPTION": detection,
                                        "monte_carlo_standard_error": error,
                                        "mean_distinct_bank_clusters": mean_clusters,
                                    }
                                )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    rows = simulate(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "schema": "carbon.design-search.power-planning-result.v1",
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                "aggregate_rows": len(rows),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
