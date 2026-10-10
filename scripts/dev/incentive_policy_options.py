"""Offline, assumption-conditional duplicate-policy sensitivity; no runtime writes.

The comparison reuses #974's public-noise proxy, score draws and target
arithmetic. All artifact identities, similarity coordinates and actor qualities
in this script are synthetic. No validator or reward publisher is imported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from scripts.dev.incentive_mechanism_sim import (
    PUBLIC_NOISE_PATH,
    PUBLIC_NOISE_SHA256,
    Q12,
    _interval_classification,
    _score_pair,
    _target_units,
    _wilson,
    public_noise_proxy,
)
from scripts.dev.incentive_mechanism_sim import (
    validate as validate_base,
)

SCHEMA = "carbon.development.incentive-policy-options.v1"
SCENARIOS = (
    "honest_only",
    "exact_one",
    "exact_four",
    "near_one",
    "near_four",
    "copy_best_honest_first",
    "copy_best_attacker_first",
)
POLICIES = (
    "hotkey",
    "digest_split",
    "digest_first",
    "near_first_tight",
    "near_first_wide",
)


@dataclass(frozen=True)
class Submission:
    actor: str
    hotkey: str
    artifact: str
    quality: float
    coordinate: float
    order: int


def _seed(*parts: object) -> int:
    encoded = json.dumps(parts, separators=(",", ":"), sort_keys=True).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def _submissions(scenario: str, cfg: dict) -> list[Submission]:
    best = Submission("honest", "honest", "best", cfg["best_quality"], 0.0, 0)
    if scenario == "honest_only":
        return [best]
    if scenario.startswith("copy_best"):
        attacker_first = scenario.endswith("attacker_first")
        copy = Submission(
            "attacker", "copy", "best", best.quality, 0.0, 0 if attacker_first else 1
        )
        return sorted(
            [
                Submission(
                    "honest",
                    "honest",
                    "best",
                    best.quality,
                    0.0,
                    1 if attacker_first else 0,
                ),
                copy,
            ],
            key=lambda item: (item.order, item.hotkey),
        )
    if scenario not in {"exact_one", "exact_four", "near_one", "near_four"}:
        raise ValueError("unknown synthetic scenario")
    count = 4 if scenario.endswith("four") else 1
    near = scenario.startswith("near")
    if near:
        # Deliberate front-running stress: a weaker distinct artifact appears
        # first, so a too-wide similarity radius can suppress the true best.
        best = Submission("honest", "honest", "best", best.quality, 0.0, count + 1)
    attackers = [
        Submission(
            "attacker",
            f"attacker-{index}",
            f"near-{index}" if near else "weak",
            cfg["sybil_quality"],
            (
                cfg["weak_coordinate"] + index * cfg["near_step"]
                if near
                else cfg["weak_coordinate"]
            ),
            index if near else index + 1,
        )
        for index in range(count)
    ]
    return [best, *attackers]


def _distance(left: Submission, right: Submission) -> float:
    return abs(left.coordinate - right.coordinate)


def _eligible(
    submissions: list[Submission], incumbent: Submission, policy: str, cfg: dict
) -> tuple[list[Submission], int]:
    """Deduplicate before screening; return distinct candidates and false merges."""
    if policy == "hotkey":
        return submissions, 0
    threshold = (
        cfg["near_threshold_tight"]
        if policy == "near_first_tight"
        else cfg["near_threshold_wide"] if policy == "near_first_wide" else 0.0
    )
    chosen: list[Submission] = []
    false_merges = 0
    for item in sorted(submissions, key=lambda row: (row.order, row.hotkey)):
        prior = [incumbent, *chosen]
        same = next(
            (
                other
                for other in prior
                if item.artifact == other.artifact
                or (threshold > 0 and _distance(item, other) <= threshold)
            ),
            None,
        )
        if same is None:
            chosen.append(item)
        elif item.quality != same.quality:
            false_merges += 1
    return chosen, false_merges


def _screen_and_compare(
    cfg: dict,
    *,
    episode_seed: int,
    window: int,
    incumbent: Submission,
    candidates: list[Submission],
    margin: float,
    score_sd: float,
    bank_shift: float,
    evidence_windows: int,
) -> Submission | None:
    """Same Gaussian/normal-interval surrogate as #974, with keyed draws.

    Candidate screen draws are keyed independently of policy, so removing a
    duplicate does not change another candidate's random observation.
    """
    screened: list[tuple[float, Submission]] = []
    common_fraction = cfg["paired_common_fraction"]
    for item in candidates:
        rng = random.Random(_seed(episode_seed, window, "screen", item.hotkey))
        inc, chal = _score_pair(
            rng,
            incumbent.quality,
            item.quality,
            score_sd=score_sd,
            paired=True,
            common_fraction=common_fraction,
            bank_shift=bank_shift,
        )
        if chal < inc * (1 - margin):
            screened.append((chal, item))
    if not screened:
        return None
    _, finalist = min(screened, key=lambda pair: (pair[0], pair[1].hotkey))
    rng = random.Random(_seed(episode_seed, window, "final", finalist.hotkey))
    n = cfg["cases_per_comparison"]
    important = cfg["important_cases"]
    rest = n - important
    inc_means: list[float] = []
    delta_means: list[float] = []
    imp_inc_means: list[float] = []
    imp_delta_means: list[float] = []
    for _ in range(evidence_windows):
        imp_inc, imp_chal = _score_pair(
            rng,
            incumbent.quality,
            finalist.quality,
            score_sd=score_sd * math.sqrt(n / important),
            paired=True,
            common_fraction=common_fraction,
            bank_shift=bank_shift,
        )
        if rest:
            rest_inc, rest_chal = _score_pair(
                rng,
                incumbent.quality,
                finalist.quality,
                score_sd=score_sd * math.sqrt(n / rest),
                paired=True,
                common_fraction=common_fraction,
                bank_shift=bank_shift,
            )
        else:
            rest_inc = rest_chal = 0.0
        inc_means.append((important * imp_inc + rest * rest_inc) / n)
        delta_means.append(
            (important * (imp_chal - imp_inc) + rest * (rest_chal - rest_inc)) / n
        )
        imp_inc_means.append(imp_inc)
        imp_delta_means.append(imp_chal - imp_inc)
    z = statistics.NormalDist().inv_cdf(1 - cfg["alpha"] / 2)
    difference_sd = score_sd * math.sqrt(2 * (1 - common_fraction))
    overall = _interval_classification(
        statistics.fmean(delta_means),
        statistics.fmean(inc_means),
        margin,
        z * difference_sd / math.sqrt(evidence_windows),
    )
    important_result = _interval_classification(
        statistics.fmean(imp_delta_means),
        statistics.fmean(imp_inc_means),
        margin,
        z * difference_sd * math.sqrt(n / important) / math.sqrt(evidence_windows),
    )
    return finalist if overall == "better" and important_result != "worse" else None


def _credit_shares(
    policy: str, incumbent: Submission, registrants: dict[str, list[Submission]]
) -> dict[str, float]:
    if policy == "hotkey":
        return {incumbent.actor: 1.0}
    holders = registrants[incumbent.artifact]
    if policy == "digest_split":
        count = len(holders)
        return {
            actor: sum(row.actor == actor for row in holders) / count
            for actor in {row.actor for row in holders}
        }
    first = min(holders, key=lambda row: (row.order, row.hotkey))
    return {first.actor: 1.0}


def episode(
    cfg: dict,
    *,
    scenario: str,
    policy: str,
    margin: float,
    decay: float,
    score_sd: float,
    replicate: int,
) -> dict:
    initial = Submission(
        "initial", "initial", "initial", cfg["initial_quality"], -1.0, -1
    )
    incumbent = initial
    age_origin = 0
    horizon = cfg["horizon_windows"]
    family = scenario.split("_")[0]
    episode_seed = _seed(cfg["seed"], family, replicate)
    submissions = _submissions(scenario, cfg)
    registrants: dict[str, list[Submission]] = {"initial": [initial]}
    for item in submissions:
        registrants.setdefault(item.artifact, []).append(item)
    paid_best = paid_attacker = total_target = 0.0
    targets: list[float] = []
    wrong = promotions = false_merges = 0
    best_first: int | None = None
    first_dethrone: int | None = None
    pending: tuple[int, Submission] | None = None
    share_units = math.floor(cfg["challenge_share"] * Q12)
    for window in range(horizon):
        bank_rng = random.Random(
            _seed(episode_seed, "bank", window // cfg["exposure_limit"])
        )
        bank_shift = bank_rng.gauss(0, score_sd * cfg["bank_shift_fraction"])
        winner = None
        if pending is not None and pending[0] == window:
            winner = pending[1]
            pending = None
        elif pending is None and window >= 1:
            active = [
                item
                for item in submissions
                if not (
                    incumbent.artifact == item.artifact
                    and incumbent.actor == item.actor
                )
            ]
            eligible, merged = _eligible(active, incumbent, policy, cfg)
            false_merges += merged
            decided = _screen_and_compare(
                cfg,
                episode_seed=episode_seed,
                window=window,
                incumbent=incumbent,
                candidates=eligible,
                margin=margin,
                score_sd=score_sd,
                bank_shift=bank_shift,
                evidence_windows=cfg["comparison_windows"],
            )
            if decided is not None:
                due = window + cfg["comparison_windows"] - 1
                if due < horizon:
                    if due == window:
                        winner = decided
                    else:
                        pending = (due, decided)
        if winner is not None:
            promotions += 1
            if first_dethrone is None:
                first_dethrone = window
            if winner.quality >= incumbent.quality * (1 - margin):
                wrong += 1
            if winner.actor != incumbent.actor:
                age_origin = window
            incumbent = winner
            if winner.quality == cfg["best_quality"] and best_first is None:
                best_first = window
        age_periods = (window - age_origin) // cfg["windows_per_decay_period"]
        target = _target_units(share_units, age_periods, decay) / Q12
        targets.append(target)
        credit = _credit_shares(policy, incumbent, registrants)
        total_target += target
        paid_attacker += target * credit.get("attacker", 0.0)
        if incumbent.quality == cfg["best_quality"]:
            paid_best += target
    return {
        "best_paid_final": int(incumbent.quality == cfg["best_quality"]),
        "best_target_fraction": paid_best / total_target,
        "attacker_target_fraction": paid_attacker / total_target,
        "wrong_dethrones": wrong,
        "promotions": promotions,
        "best_promotion_window": best_first,
        "first_dethrone_window": first_dethrone,
        "false_merges": false_merges,
        "paid_budget_fraction": total_target / (horizon * share_units / Q12),
        "target_variation": sum(abs(right - left) for left, right in pairwise(targets))
        / ((horizon - 1) * cfg["challenge_share"]),
    }


def validate(cfg: dict) -> None:
    if cfg.get("schema") != SCHEMA:
        raise ValueError("wrong policy-options schema")
    base = cfg.get("base_simulation")
    if not isinstance(base, dict):
        raise TypeError("base_simulation is required")
    validate_base(base)
    for key in (
        "weak_coordinate",
        "near_step",
        "near_threshold_tight",
        "near_threshold_wide",
    ):
        value = cfg.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be nonnegative and finite")
    if not 0 < cfg["near_threshold_tight"] < cfg["near_threshold_wide"]:
        raise ValueError("near thresholds must be ordered positive assumptions")
    if cfg["near_step"] <= 0 or cfg["weak_coordinate"] <= 0:
        raise ValueError("synthetic coordinates require positive separation")
    if type(cfg.get("replicates")) is not int or cfg["replicates"] < 2:
        raise ValueError("at least two synthetic replicates required")
    if type(cfg.get("comparison_windows")) is not int or cfg["comparison_windows"] < 1:
        raise ValueError("comparison_windows must be positive")
    if cfg["comparison_windows"] > base["horizon_windows"]:
        raise ValueError("comparison extends beyond horizon")


def simulate(cfg: dict, noise: dict) -> list[dict]:
    validate(cfg)
    base = dict(cfg["base_simulation"])
    base.update(
        weak_coordinate=cfg["weak_coordinate"],
        near_step=cfg["near_step"],
        near_threshold_tight=cfg["near_threshold_tight"],
        near_threshold_wide=cfg["near_threshold_wide"],
        comparison_windows=cfg["comparison_windows"],
    )
    score_sd = noise["median_within_recipe_sd"] * base["noise_multiplier"]
    rows = []
    episode_cache: dict[tuple[float, float, str, str], list[dict]] = {}
    for margin in base["margins"]:
        for decay in base["decays"]:
            for policy in POLICIES:
                for scenario in SCENARIOS:
                    episodes = [
                        episode(
                            base,
                            scenario=scenario,
                            policy=policy,
                            margin=margin,
                            decay=decay,
                            score_sd=score_sd,
                            replicate=replicate,
                        )
                        for replicate in range(cfg["replicates"])
                    ]
                    episode_cache[(margin, decay, policy, scenario)] = episodes
                    best = sum(item["best_paid_final"] for item in episodes)
                    intervals = _wilson(best, len(episodes))
                    promoted = [
                        item["best_promotion_window"]
                        for item in episodes
                        if item["best_promotion_window"] is not None
                    ]
                    first = [
                        item["first_dethrone_window"]
                        for item in episodes
                        if item["first_dethrone_window"] is not None
                    ]
                    promotions = sum(item["promotions"] for item in episodes)
                    rows.append(
                        {
                            "scenario": scenario,
                            "policy": policy,
                            "margin_rel": margin,
                            "decay_factor_per_period": decay,
                            "comparison_windows": base["comparison_windows"],
                            "replicates": len(episodes),
                            "p_best_paid_final": best / len(episodes),
                            "p_best_paid_low95_mc": intervals[0],
                            "p_best_paid_high95_mc": intervals[1],
                            "attacker_target_fraction": statistics.fmean(
                                item["attacker_target_fraction"] for item in episodes
                            ),
                            "best_target_fraction": statistics.fmean(
                                item["best_target_fraction"] for item in episodes
                            ),
                            "wrong_dethrone_rate": (
                                sum(item["wrong_dethrones"] for item in episodes)
                                / promotions
                                if promotions
                                else ""
                            ),
                            "wrong_dethrones_per_run": statistics.fmean(
                                item["wrong_dethrones"] for item in episodes
                            ),
                            "time_to_best_mean_if_seen": (
                                statistics.fmean(promoted) if promoted else ""
                            ),
                            "time_to_best_censored_fraction": 1
                            - len(promoted) / len(episodes),
                            "time_to_first_dethrone_mean_if_seen": (
                                statistics.fmean(first) if first else ""
                            ),
                            "time_to_first_dethrone_censored_fraction": 1
                            - len(first) / len(episodes),
                            "false_merges_per_run": statistics.fmean(
                                item["false_merges"] for item in episodes
                            ),
                            "paid_fraction_of_challenge_budget": statistics.fmean(
                                item["paid_budget_fraction"] for item in episodes
                            ),
                            "target_variation_per_window": statistics.fmean(
                                item["target_variation"] for item in episodes
                            ),
                            "sybil_gain_vs_one_key": "",
                            "sybil_gain_low95_mc": "",
                            "sybil_gain_high95_mc": "",
                        }
                    )
    for row in rows:
        scenario = row["scenario"]
        if scenario not in {"exact_four", "near_four"}:
            continue
        key = (row["margin_rel"], row["decay_factor_per_period"], row["policy"])
        one = episode_cache[(*key, scenario.replace("four", "one"))]
        four = episode_cache[(*key, scenario)]
        differences = [
            a["attacker_target_fraction"] - b["attacker_target_fraction"]
            for a, b in zip(four, one, strict=True)
        ]
        row["sybil_gain_vs_one_key"] = statistics.fmean(differences)
        rng = random.Random(_seed(base["seed"], key, scenario, "gain-bootstrap"))
        boot = sorted(
            statistics.fmean(rng.choices(differences, k=len(differences)))
            for _ in range(1000)
        )
        row["sybil_gain_low95_mc"] = boot[24]
        row["sybil_gain_high95_mc"] = boot[974]
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    cfg = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate(cfg)
    base = cfg["base_simulation"]
    source = args.manifest.parent / base["public_noise_source"]
    if (
        source.resolve() != PUBLIC_NOISE_PATH.resolve()
        or base["public_noise_sha256"] != PUBLIC_NOISE_SHA256
    ):
        raise ValueError("only the pinned public-practice noise source is accepted")
    noise = public_noise_proxy(source, PUBLIC_NOISE_SHA256)
    rows = simulate(cfg, noise)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "rows": len(rows),
                "status": "ASSUMPTION_CONDITIONAL_DEVELOPMENT",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
