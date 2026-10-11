"""Analytical stand-ins; no random draws, bank reads or Carbon imports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def effective_n(multiplicities, rho):
    if not multiplicities or not 0 <= rho <= 1:
        raise ValueError("Valid case clusters and correlation required")
    if any(type(m) is not int or m < 1 for m in multiplicities):
        raise ValueError("Positive integer appearances required")
    total = sum(multiplicities)
    return total**2 / (rho * sum(m * m for m in multiplicities) + (1 - rho) * total)


def cost_per_window(n, exposures, offer_cpu_h, yield_rate=1.0):
    if n <= 0 or type(exposures) is not int or exposures < 1:
        raise ValueError("Positive draw and exposure budget required")
    if offer_cpu_h < 0 or not 0 < yield_rate <= 1:
        raise ValueError("Measured cost and positive admission yield required")
    return n * offer_cpu_h / (exposures * yield_rate)


def publication_lag(exposures, spacing, active_duration):
    if min(exposures, spacing, active_duration) < 1:
        raise ValueError("Positive window units required")
    if exposures > 1 and spacing < active_duration:
        raise ValueError("Reuse would overlap active windows")
    return (exposures - 1) * spacing + active_duration


def random_repeat_max_quantile(n, p, quantile):
    """E=2 iid-target Bernoulli approximation; not actual schedule telemetry."""
    if n <= 0 or not 0 < p < 1 or not 0 < quantile < 1:
        raise ValueError("Invalid approximation inputs")
    return math.ceil(math.log1p(-(quantile ** (1 / n))) / math.log1p(-p))


def report():
    classes = {"battery": (20, 5), "motor_like": (10, 10), "CFD_class": (5, 20)}
    rows = {}
    for name, (multiple, e) in classes.items():
        rows[name] = {
            "owner_historical_testing_B_over_n": multiple,
            "owner_historical_testing_E": e,
            "ESS_for_1000_appearances_at_rho_low_base_high": [
                effective_n([e] * (1000 // e), r) for r in (0.25, 0.75, 1.0)
            ],
            "variance_multiplier_low_base_high": [
                1 + (e - 1) * r for r in (0.25, 0.75, 1.0)
            ],
            "CI_width_multiplier_low_base_high": [
                math.sqrt(1 + (e - 1) * r) for r in (0.25, 0.75, 1.0)
            ],
            "fresh_cases_per_100_appearances": 100 / e,
            "single_case_expected_draw_lifetime_random_windows": multiple * e,
            "scheduled_lag_windows_at_spacing_3_duration_3": publication_lag(e, 3, 3),
        }
    costs = {
        "battery_pool": {
            "multiple": 20,
            "E": 5,
            "n": 100,
            "costs": [75 / 3600, 91 / 3600, 120 / 3600],
        },
        "motor_like": {"multiple": 10, "E": 10, "n": 100, "costs": [0.6, 0.8, 1.0]},
        "CFD_class": {"multiple": 5, "E": 20, "n": 100, "costs": [2, 6, 20]},
    }
    for row in costs.values():
        row["startup_CPU_h_low_base_high"] = [
            row["multiple"] * row["n"] * c for c in row["costs"]
        ]
        row["refill_CPU_h_per_window_low_base_high"] = [
            cost_per_window(row["n"], row["E"], c) for c in row["costs"]
        ]
    return {
        "schema": "carbon.research.bank-rotation-stats.v1",
        "status": "ANALYTICAL_ASSUMPTION_SENSITIVITY_NOT_MEASURED_BANK",
        "rho_low_base_high_ASSUMPTION": [0.25, 0.75, 1.0],
        "appearance_count_ASSUMPTION": 1000,
        "classes": rows,
        "cost_examples": costs,
        "cost_basis": {
            "battery_pool": "91 CPU-s from VALIDATOR-23 planning; 75/120 ASSUMPTION, not current latency measurements",
            "motor_like": "0.6-1 core-h from owner architecture; .8 midpoint ASSUMPTION",
            "CFD_class": "2/6/20 core-h ASSUMPTION illustration; actual Challenge cost HUMAN_INPUT",
            "n": "100 ASSUMPTION common comparison; historical battery n=100 with 98 distinct draws",
        },
        "battery_Q3_offer_cost_assumption_low_base_high_CPU_h": [0.66, 0.73, 0.80],
        "battery_Q3_admission_surrogate_ASSUMPTION_low_base_high": [0.5, 0.5625, 0.7],
        "battery_Q3_startup_160_live_CPU_h_low_base_high": [
            160 * 0.66 / 0.7,
            160 * 0.73 / 0.5625,
            160 * 0.8 / 0.5,
        ],
        "battery_Q3_refill_8_appearances_E5_CPU_h_low_base_high": [
            cost_per_window(8, 5, 0.66, 0.7),
            cost_per_window(8, 5, 0.73, 0.5625),
            cost_per_window(8, 5, 0.8, 0.5),
        ],
        "battery_Q3_legacy_route_125_solves_times_91_CPU_s_per_offer_CPU_h": 125
        * 91
        / 3600,
        "current_testnet_E1_3920_draws_day_at_91_CPU_s_CPU_h": 3920 * 91 / 3600,
        "random_E2_release_approx_98_targets_B2000_next_draw_probability": 98 / 2000,
        "random_E2_max_repeat_windows_q50_q95_q99": [
            random_repeat_max_quantile(98, 98 / 2000, q) for q in (0.5, 0.95, 0.99)
        ],
        "random_release_approximation_basis": "ASSUMPTION independent Bernoulli targets, no active exclusion/turnover; illustrates tail only",
        "time_basis": "Window/block wall time is owner/chain parameter, not CPU-h",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "results.json"
    )
    args = p.parse_args()
    args.output.write_text(
        json.dumps(report(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
