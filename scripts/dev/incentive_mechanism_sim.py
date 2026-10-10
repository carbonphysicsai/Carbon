"""Offline, assumption-labelled score -> promotion -> weight-target sensitivity.

No validator, reward publisher, chain, hidden bank or reference solver is called.
The normal interval in this fast sweep is a documented surrogate for the
DEVELOPMENT_RULE's 4,000-draw percentile bootstrap, not a policy implementation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

SCHEMA = "carbon.development.incentive-simulation.v1"
STRATEGIES = (
    "honest",
    "copy",
    "sybil_one_key_control",
    "sybil",
    "snipe",
    "timing",
)
Q12 = 10**12  # carbon.rewards.core.Q12; tested against winner_decay golden arithmetic
PUBLIC_NOISE_SHA256 = "503b2cf04bffff3571ecc55f6a17413884e1b3739c8cee205ae36b84642c99ad"
PUBLIC_NOISE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/graphite-run5-q1/practice-summaries.json"
)


def _wilson(successes: int, trials: int) -> tuple[float, float]:
    z = 1.959963984540054
    observed = successes / trials
    denominator = 1 + z * z / trials
    centre = (observed + z * z / (2 * trials)) / denominator
    half = (
        z
        * math.sqrt(observed * (1 - observed) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0.0, centre - half), min(1.0, centre + half)


def _target_units(share_units: int, age_periods: int, decay: float) -> int:
    # The 0.5 branch reproduces winner_decay.winner_fraction's Q12 right shift.
    fraction_units = (
        Q12 >> age_periods if decay == 0.5 else math.floor(Q12 * decay**age_periods)
    )
    return share_units * fraction_units // Q12


def _promotion_age_origin(
    prior_origin: int, window: int, incumbent: Candidate, winner: Candidate
) -> int:
    # `actor` is the assumed common coldkey, so a sybil hotkey handoff cannot
    # renew the winner's 24-hour clock (winner_eligibility.decide).
    return prior_origin if winner.actor == incumbent.actor else window


def _finite(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def public_noise_proxy(path: Path, expected_sha256: str) -> dict:
    """Median within-recipe seed SD from the committed *public practice* panel.

    This measures rebuild/seed spread on the public practice set. Its use as a
    per-window score-error proxy is a simulation assumption, not empirical exam
    noise or a calibrated uncertainty model.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("public noise source digest mismatch")
    rows = json.loads(raw)
    if not isinstance(rows, dict):
        raise TypeError("public noise source must be an object")
    by_recipe: dict[str, list[float]] = defaultdict(list)
    for row in rows.values():
        recipe = row["recipe_digest"]
        score = _finite(row["summary"]["score"], "public score")
        by_recipe[recipe].append(score)
    sds = [
        statistics.stdev(scores) for scores in by_recipe.values() if len(scores) >= 2
    ]
    if len(sds) < 2:
        raise ValueError("at least two repeated public recipes required")
    return {
        "source_sha256": digest,
        "recipes": len(by_recipe),
        "repeated_recipes": len(sds),
        "scores": sum(map(len, by_recipe.values())),
        "median_within_recipe_sd": statistics.median(sds),
        "interpretation": "public-practice seed spread used as assumed window-noise proxy",
    }


@dataclass(frozen=True)
class Candidate:
    actor: str
    hotkey: str
    quality: float


def _score_pair(
    rng: random.Random,
    incumbent: float,
    challenger: float,
    *,
    score_sd: float,
    paired: bool,
    common_fraction: float,
    bank_shift: float,
) -> tuple[float, float]:
    # Gaussian mean-score surrogate. The spread is measured across public
    # practice seeds; treating it as a window SD is an explicit assumption.
    shared_sd = score_sd * math.sqrt(common_fraction) if paired else 0.0
    private_sd = score_sd * math.sqrt(1 - common_fraction) if paired else score_sd
    common = rng.gauss(0, shared_sd)
    inc = max(1e-9, incumbent + bank_shift + common + rng.gauss(0, private_sd))
    chal = max(1e-9, challenger + bank_shift + common + rng.gauss(0, private_sd))
    return inc, chal


def _interval_classification(
    mean: float, base: float, margin: float, halfwidth: float
) -> str:
    low, high = mean - halfwidth, mean + halfwidth
    bound = margin * base
    if high < 0 and mean < -bound:
        return "better"
    if low > 0 and mean > bound:
        return "worse"
    if low >= -bound and high <= bound:
        return "equivalent"
    return "unresolved"


def _screen_and_final(
    rng: random.Random,
    current: float,
    candidates: list[Candidate],
    *,
    margin: float,
    score_sd: float,
    paired: bool,
    common_fraction: float,
    bank_shift: float,
    n: int,
    n_important: int,
    alpha: float,
    evidence_windows: int,
) -> Candidate | None:
    # One score per hotkey/window. A closed window nominates only its best
    # screen result; fresh final evidence decides whether it can promote.
    nominated: list[tuple[float, Candidate]] = []
    for candidate in candidates:
        inc_score, chal_score = _score_pair(
            rng,
            current,
            candidate.quality,
            score_sd=score_sd,
            paired=paired,
            common_fraction=common_fraction,
            bank_shift=bank_shift,
        )
        if chal_score < inc_score * (1 - margin):
            nominated.append((chal_score, candidate))
    if not nominated:
        return None
    _, finalist = min(nominated, key=lambda pair: (pair[0], pair[1].hotkey))
    inc_means, delta_means, imp_inc_means, imp_delta_means = [], [], [], []
    rest_count = n - n_important
    for _ in range(evidence_windows):
        imp_inc, imp_chal = _score_pair(
            rng,
            current,
            finalist.quality,
            score_sd=score_sd * math.sqrt(n / n_important),
            paired=paired,
            common_fraction=common_fraction,
            bank_shift=bank_shift,
        )
        if rest_count:
            rest_inc, rest_chal = _score_pair(
                rng,
                current,
                finalist.quality,
                score_sd=score_sd * math.sqrt(n / rest_count),
                paired=paired,
                common_fraction=common_fraction,
                bank_shift=bank_shift,
            )
        else:
            rest_inc, rest_chal = 0.0, 0.0
        inc_means.append((n_important * imp_inc + rest_count * rest_inc) / n)
        delta_means.append(
            (n_important * (imp_chal - imp_inc) + rest_count * (rest_chal - rest_inc))
            / n
        )
        imp_inc_means.append(imp_inc)
        imp_delta_means.append(imp_chal - imp_inc)
    z = statistics.NormalDist().inv_cdf(1 - alpha / 2)
    difference_sd = score_sd * math.sqrt(2 * (1 - common_fraction if paired else 1))
    overall = _interval_classification(
        statistics.fmean(delta_means),
        statistics.fmean(inc_means),
        margin,
        z * difference_sd / math.sqrt(evidence_windows),
    )
    important = _interval_classification(
        statistics.fmean(imp_delta_means),
        statistics.fmean(imp_inc_means),
        margin,
        z * difference_sd * math.sqrt(n / n_important) / math.sqrt(evidence_windows),
    )
    # Same promotable path as exam.final_compare: overall better and no
    # important-region regression. The interval itself is an approximation.
    if overall == "better" and important != "worse":
        return finalist
    return None


def _candidates(
    strategy: str, window: int, incumbent_quality: float, margin: float, cfg: dict
) -> list[Candidate]:
    best = _finite(cfg["best_quality"], "best_quality", positive=True)
    if strategy == "timing":
        if window < cfg["timing_arrival_window"]:
            return []
        return [Candidate("attacker", "timing", best)]
    candidates = [Candidate("honest", "honest", best)] if window >= 1 else []
    if window < 1 or strategy == "honest":
        return candidates
    if strategy == "copy":
        return candidates + [Candidate("attacker", "copy", incumbent_quality)]
    if strategy in {"sybil", "sybil_one_key_control"}:
        quality = _finite(cfg["sybil_quality"], "sybil_quality", positive=True)
        return candidates + [
            Candidate("attacker", f"sybil-{key}", quality)
            for key in range(cfg["sybil_hotkeys"] if strategy == "sybil" else 1)
        ]
    if strategy == "snipe":
        initial = _finite(cfg["initial_quality"], "initial_quality", positive=True)
        epsilon = _finite(cfg["snipe_epsilon"], "snipe_epsilon", positive=True)
        quality = initial * (1 - margin) - epsilon
        if quality <= best or quality <= 0:
            raise ValueError("sniper must be worse than the declared best model")
        return candidates + [Candidate("attacker", "snipe", quality)]
    raise ValueError("unknown strategy")


def _episode(
    rng: random.Random,
    cfg: dict,
    *,
    strategy: str,
    margin: float,
    decay: float,
    evidence_windows: int,
    paired: bool,
    score_sd: float,
) -> dict:
    initial = _finite(cfg["initial_quality"], "initial_quality", positive=True)
    best = _finite(cfg["best_quality"], "best_quality", positive=True)
    incumbent = Candidate("initial", "initial", initial)
    age_origin = 0
    paid_best = paid_attacker = paid_total = 0.0
    paid_windows_best = wrong = promotions = 0
    best_first = None
    first_dethrone = None
    best_by_first_exposure = False
    targets: list[float] = []
    recipients: list[tuple[str, float]] = []
    share_units = math.floor(cfg["challenge_share"] * Q12)
    bank_shift = 0.0
    pending: tuple[int, Candidate] | None = None
    horizon = cfg["horizon_windows"]
    for window in range(horizon):
        if window % cfg["exposure_limit"] == 0:
            bank_shift = rng.gauss(0, score_sd * cfg["bank_shift_fraction"])
        winner = None
        if pending is not None and pending[0] == window:
            winner = pending[1]
            pending = None
        elif pending is None:
            candidates = _candidates(strategy, window, incumbent.quality, margin, cfg)
            # An honest miner stops resubmitting its exact model once it is
            # incumbent. The timing actor likewise stops after its first win.
            if incumbent.actor == "honest":
                candidates = [c for c in candidates if c.actor != "honest"]
            if strategy == "timing" and incumbent.actor == "attacker":
                candidates = []
            # The current v2 admission cap is one attempt per hotkey per window.
            if len({c.hotkey for c in candidates}) != len(candidates):
                raise ValueError("duplicate hotkey attempt in one window")
            decided = _screen_and_final(
                rng,
                incumbent.quality,
                candidates,
                margin=margin,
                score_sd=score_sd,
                paired=paired,
                common_fraction=cfg["paired_common_fraction"],
                bank_shift=bank_shift,
                n=cfg["cases_per_comparison"],
                n_important=cfg["important_cases"],
                alpha=cfg["alpha"],
                evidence_windows=evidence_windows,
            )
            if decided is not None:
                due = window + evidence_windows - 1
                if due < horizon:
                    if due == window:
                        winner = decided
                    else:
                        pending = (due, decided)
        if winner is not None:
            promotions += 1
            if first_dethrone is None:
                first_dethrone = window
            # The synthetic truth declares a promotion wrong when its true
            # gain does not clear the scenario's practical margin.
            if winner.quality >= incumbent.quality * (1 - margin):
                wrong += 1
            age_origin = _promotion_age_origin(age_origin, window, incumbent, winner)
            incumbent = winner
            if winner.quality == best and best_first is None:
                best_first = window
        # The target is a fraction of a *declared* Challenge share. Remainder
        # burns. It is not a chain observation or a payment to a miner.
        age_periods = (window - age_origin) // cfg["windows_per_decay_period"]
        target_units = _target_units(share_units, age_periods, decay)
        target = target_units / Q12
        targets.append(target)
        recipients.append((incumbent.hotkey, target))
        paid_total += target
        if incumbent.quality == best:
            paid_best += target
            paid_windows_best += 1
            if window < cfg["exposure_limit"]:
                best_by_first_exposure = True
        if incumbent.actor == "attacker":
            paid_attacker += target
    return {
        "best_paid_final": float(incumbent.quality == best),
        "best_paid_any": float(paid_windows_best > 0),
        "best_paid_by_first_exposure": float(best_by_first_exposure),
        "best_paid_weight_fraction": paid_best / paid_total if paid_total else 0.0,
        "best_paid_windows_fraction": paid_windows_best / horizon,
        "time_to_best_uncensored": best_first,
        "time_to_first_dethrone_uncensored": first_dethrone,
        "wrong_dethrones": wrong,
        "promotions": promotions,
        "wrong_dethrone_rate": wrong / promotions if promotions else 0.0,
        "target_variation": sum(abs(b - a) for a, b in pairwise(targets))
        / (horizon - 1)
        / cfg["challenge_share"],
        "recipient_variation": sum(
            abs(b - a) if left == right else max(a, b)
            for (left, a), (right, b) in pairwise(recipients)
        )
        / (horizon - 1)
        / cfg["challenge_share"],
        "attacker_weight_fraction": paid_attacker / paid_total if paid_total else 0.0,
        "paid_fraction_of_challenge_budget": paid_total / (horizon * share_units / Q12),
        "burn_fraction_of_challenge_budget": 1
        - paid_total / (horizon * share_units / Q12),
    }


def validate(cfg: dict) -> None:
    if cfg.get("schema") != SCHEMA:
        raise ValueError("wrong simulation schema")
    for key in (
        "initial_quality",
        "best_quality",
        "sybil_quality",
        "snipe_epsilon",
        "challenge_share",
    ):
        _finite(cfg[key], key, positive=True)
    if not cfg["best_quality"] < cfg["sybil_quality"] < cfg["initial_quality"]:
        raise ValueError("quality order must be best < sybil < incumbent")
    for key in ("alpha", "paired_common_fraction", "bank_shift_fraction"):
        v = _finite(cfg[key], key)
        if not 0 <= v < 1 or (key == "alpha" and v == 0):
            raise ValueError(f"{key} outside range")
    if cfg["challenge_share"] > 1:
        raise ValueError("Challenge share exceeds one")
    if math.floor(cfg["challenge_share"] * Q12) == 0:
        raise ValueError("Challenge share rounds to zero Q12 units")
    for key in (
        "cases_per_comparison",
        "important_cases",
        "exposure_limit",
        "windows_per_decay_period",
        "timing_arrival_window",
        "sybil_hotkeys",
        "replicates",
        "horizon_windows",
    ):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if not 2 <= cfg["important_cases"] <= cfg["cases_per_comparison"]:
        raise ValueError("invalid important case count")
    comparison = cfg["registered_comparison"]
    if cfg["alpha"] != comparison["alpha"]:
        raise ValueError("alpha differs from named development comparison")
    if cfg["cases_per_comparison"] < comparison["n_min"]:
        raise ValueError("fewer cases than registered comparison minimum")
    if cfg["important_cases"] < comparison["important_min"]:
        raise ValueError("fewer important cases than registered minimum")
    if comparison["n_boot"] != 4000:
        raise ValueError("manifest does not name the registered bootstrap setting")
    for key in ("margins", "decays", "comparison_windows"):
        if not isinstance(cfg[key], list) or not cfg[key]:
            raise ValueError(f"{key} must be nonempty")
    if any(not 0 <= _finite(v, "margin") < 1 for v in cfg["margins"]):
        raise ValueError("margin outside [0,1)")
    if cfg["registered_equivalence_margin_rel"] not in cfg["margins"]:
        raise ValueError("margin sweep must include the registered rule")
    if any(not 0 < _finite(v, "decay") <= 1 for v in cfg["decays"]):
        raise ValueError("decay outside (0,1]")
    if any(
        type(v) is not int or v < 1 or v > cfg["horizon_windows"]
        for v in cfg["comparison_windows"]
    ):
        raise ValueError("comparison windows outside horizon")
    if (
        cfg["timing_arrival_window"] + max(cfg["comparison_windows"])
        > cfg["horizon_windows"]
    ):
        raise ValueError("horizon too short for timing comparison")
    if type(cfg["seed"]) is not int or cfg["seed"] < 0:
        raise ValueError("seed must be a nonnegative synthetic integer")


def simulate(cfg: dict, noise: dict) -> list[dict]:
    validate(cfg)
    score_sd = noise["median_within_recipe_sd"] * cfg["noise_multiplier"]
    _finite(cfg["noise_multiplier"], "noise_multiplier", positive=True)
    rows = []
    for paired in (True, False):
        for margin in cfg["margins"]:
            for decay in cfg["decays"]:
                for evidence_windows in cfg["comparison_windows"]:
                    for strategy in STRATEGIES:
                        episodes = []
                        for replicate in range(cfg["replicates"]):
                            identity = json.dumps(
                                [
                                    cfg["seed"],
                                    paired,
                                    margin,
                                    decay,
                                    evidence_windows,
                                    strategy,
                                    replicate,
                                ],
                                separators=(",", ":"),
                            )
                            rng = random.Random(
                                int.from_bytes(
                                    hashlib.sha256(identity.encode()).digest()[:8],
                                    "big",
                                )
                            )
                            episodes.append(
                                _episode(
                                    rng,
                                    cfg,
                                    strategy=strategy,
                                    margin=margin,
                                    decay=decay,
                                    evidence_windows=evidence_windows,
                                    paired=paired,
                                    score_sd=score_sd,
                                )
                            )
                        uncensored = [
                            e["time_to_best_uncensored"]
                            for e in episodes
                            if e["time_to_best_uncensored"] is not None
                        ]
                        dethrones = [
                            e["time_to_first_dethrone_uncensored"]
                            for e in episodes
                            if e["time_to_first_dethrone_uncensored"] is not None
                        ]
                        total_promotions = sum(e["promotions"] for e in episodes)
                        row = {
                            "comparison": (
                                "paired_same_case"
                                if paired
                                else "unpaired_counterfactual"
                            ),
                            "margin_rel": margin,
                            "decay_factor_per_period": decay,
                            "comparison_windows": evidence_windows,
                            "horizon_windows": cfg["horizon_windows"],
                            "strategy": strategy,
                            "replicates": len(episodes),
                            "p_best_paid_final": statistics.fmean(
                                e["best_paid_final"] for e in episodes
                            ),
                            "p_best_paid_final_low95_mc": _wilson(
                                sum(int(e["best_paid_final"]) for e in episodes),
                                len(episodes),
                            )[0],
                            "p_best_paid_final_high95_mc": _wilson(
                                sum(int(e["best_paid_final"]) for e in episodes),
                                len(episodes),
                            )[1],
                            "p_best_paid_any": statistics.fmean(
                                e["best_paid_any"] for e in episodes
                            ),
                            "p_best_paid_by_first_exposure": statistics.fmean(
                                e["best_paid_by_first_exposure"] for e in episodes
                            ),
                            "p_best_paid_by_first_exposure_low95_mc": _wilson(
                                sum(
                                    int(e["best_paid_by_first_exposure"])
                                    for e in episodes
                                ),
                                len(episodes),
                            )[0],
                            "p_best_paid_by_first_exposure_high95_mc": _wilson(
                                sum(
                                    int(e["best_paid_by_first_exposure"])
                                    for e in episodes
                                ),
                                len(episodes),
                            )[1],
                            "best_paid_weight_fraction": statistics.fmean(
                                e["best_paid_weight_fraction"] for e in episodes
                            ),
                            "best_paid_windows_fraction": statistics.fmean(
                                e["best_paid_windows_fraction"] for e in episodes
                            ),
                            "time_to_best_mean_if_seen": (
                                statistics.fmean(uncensored) if uncensored else ""
                            ),
                            "time_to_best_censored_fraction": 1
                            - len(uncensored) / len(episodes),
                            "time_to_first_dethrone_mean_if_seen": (
                                statistics.fmean(dethrones) if dethrones else ""
                            ),
                            "time_to_first_dethrone_censored_fraction": 1
                            - len(dethrones) / len(episodes),
                            "wrong_dethrones_per_run": statistics.fmean(
                                e["wrong_dethrones"] for e in episodes
                            ),
                            "promotions_per_run": statistics.fmean(
                                e["promotions"] for e in episodes
                            ),
                            "wrong_dethrone_rate": (
                                sum(e["wrong_dethrones"] for e in episodes)
                                / total_promotions
                                if total_promotions
                                else ""
                            ),
                            "target_variation_per_window": statistics.fmean(
                                e["target_variation"] for e in episodes
                            ),
                            "recipient_variation_per_window": statistics.fmean(
                                e["recipient_variation"] for e in episodes
                            ),
                            "attacker_weight_fraction": statistics.fmean(
                                e["attacker_weight_fraction"] for e in episodes
                            ),
                            "paid_fraction_of_challenge_budget": statistics.fmean(
                                e["paid_fraction_of_challenge_budget"] for e in episodes
                            ),
                            "burn_fraction_of_challenge_budget": statistics.fmean(
                                e["burn_fraction_of_challenge_budget"] for e in episodes
                            ),
                        }
                        rows.append(row)
    return rows


def canary_predictions(cfg: dict, noise: dict, rows: list[dict]) -> dict:
    """A joinable prediction, with observation slots deliberately empty."""
    selected = [
        row
        for row in rows
        if row["comparison"] == "paired_same_case"
        and row["margin_rel"] == cfg["registered_equivalence_margin_rel"]
        and row["decay_factor_per_period"] == 0.5
    ]
    return {
        "schema": "carbon.development.incentive-canary-predictions.v1",
        "status": "SYNTHETIC_PREDICTION_NOT_LIVE_EVIDENCE",
        "source_sha256": noise["source_sha256"],
        "basis": "paired same-case, registered development margin, current 24-hour halving target",
        "prediction_method": (
            "Gaussian mean-score and normal-interval surrogate; "
            f"{cfg['replicates']} Monte Carlo runs per row"
        ),
        "assumed_parameters": {
            "score_noise_sd": noise["median_within_recipe_sd"]
            * cfg["noise_multiplier"],
            "paired_common_fraction": cfg["paired_common_fraction"],
            "cases_per_comparison": cfg["cases_per_comparison"],
            "important_cases": cfg["important_cases"],
            "horizon_windows": cfg["horizon_windows"],
            "exposure_limit": cfg["exposure_limit"],
            "challenge_share": cfg["challenge_share"],
            "windows_per_decay_period": cfg["windows_per_decay_period"],
            "initial_quality": cfg["initial_quality"],
            "best_quality": cfg["best_quality"],
            "sybil_quality": cfg["sybil_quality"],
            "sybil_hotkeys": cfg["sybil_hotkeys"],
            "snipe_epsilon": cfg["snipe_epsilon"],
            "timing_arrival_window": cfg["timing_arrival_window"],
        },
        "observation_requirements": {
            "comparison_windows": "actual fresh evidence windows per comparison",
            "true_quality": "independently known testnet model quality to identify best/wrong dethrones; otherwise NOT_IDENTIFIABLE",
            "winner_weight": "observed normalized weight target, distinct from chain settlement or miner receipts",
            "chain_emission": "observed emitted fraction/readback; compare with ideal direct-winner-plus-burn target separately",
            "coldkey_linkage": "required to test sybil no-clock-reset prediction",
        },
        "rows": [
            {
                "comparison_windows": row["comparison_windows"],
                "strategy": row["strategy"],
                "predicted": {
                    key: row[key]
                    for key in (
                        "p_best_paid_final",
                        "p_best_paid_final_low95_mc",
                        "p_best_paid_final_high95_mc",
                        "p_best_paid_by_first_exposure",
                        "time_to_best_mean_if_seen",
                        "time_to_best_censored_fraction",
                        "time_to_first_dethrone_mean_if_seen",
                        "time_to_first_dethrone_censored_fraction",
                        "wrong_dethrone_rate",
                        "target_variation_per_window",
                        "recipient_variation_per_window",
                        "attacker_weight_fraction",
                        "burn_fraction_of_challenge_budget",
                    )
                },
                "observed": None,
            }
            for row in selected
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--canary-predictions", type=Path)
    args = parser.parse_args(argv)
    manifest_bytes = args.manifest.read_bytes()
    cfg = json.loads(manifest_bytes)
    source = args.manifest.parent / cfg["public_noise_source"]
    if source.resolve() != PUBLIC_NOISE_PATH.resolve():
        raise ValueError("only the committed public practice noise source is accepted")
    if cfg["public_noise_sha256"] != PUBLIC_NOISE_SHA256:
        raise ValueError("only the pinned public practice digest is accepted")
    noise = public_noise_proxy(source, cfg["public_noise_sha256"])
    rows = simulate(cfg, noise)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    if args.canary_predictions is not None:
        canary = canary_predictions(cfg, noise, rows)
        canary["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        args.canary_predictions.write_text(
            json.dumps(canary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "rows": len(rows),
                "noise": noise,
                "output": str(args.output),
                "status": "ASSUMPTION_CONDITIONAL_DEVELOPMENT",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
