"""Public synthetic economics; no validator, solver, network or protected inputs.

NumPy is already part of Carbon's science-jax environment. The grader samples
joint Gaussian sufficient statistics for fresh shared cases, not physics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

NORMAL = NormalDist()


def t_critical(alpha: float, k: int, blocks: int) -> float:
    """Third-order large-df expansion; caller only permits df >= 1999."""
    if not 0 < alpha < 1 or k < 1 or blocks < 2000:
        raise ValueError("invalid alpha, cohort or information count")
    z = NORMAL.inv_cdf(1 - alpha / k)
    v = blocks - 1
    return (
        z
        + (z**3 + z) / (4 * v)
        + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * v**2)
        + (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / (384 * v**3)
    )


def normal_cdf(x):
    """Vector normal CDF approximation for behavioral beliefs, not grading."""
    x = np.asarray(x, dtype=float)
    u = 1 / (1 + 0.2316419 * np.abs(x))
    density = np.exp(-(x * x) / 2) / math.sqrt(2 * math.pi)
    tail = (
        density
        * u
        * (
            0.319381530
            + u
            * (-0.356563782 + u * (1.781477937 + u * (-1.821255978 + u * 1.330274429)))
        )
    )
    return np.where(x >= 0, 1 - tail, tail)


def rent(pool, share, decay, hazard, discount, age=0, horizon=90):
    """Expected finite gross target rent under ASSUMED constant survival hazard."""
    ratio = decay * discount * (1 - hazard)
    ratio = np.asarray(ratio, dtype=float)
    total = np.divide(
        1 - ratio**horizon,
        1 - ratio,
        out=np.full_like(ratio, horizon),
        where=ratio != 1,
    )
    return pool * share * decay**age * total


def select_winner(observed, paired_se, incumbent, margin, critical):
    """Strict AND bars, per-episode incumbent; fixed alpha/K, not extra coins."""
    rows = np.arange(len(incumbent))
    king_error = observed[rows, incumbent]
    improvement = king_error[:, None] - observed
    eligible = (
        (king_error[:, None] > 0)
        & (improvement > margin * king_error[:, None])
        & (improvement > critical * paired_se)
        & np.isfinite(observed)
    )
    eligible[rows, incumbent] = False
    candidates = np.where(eligible, observed, np.inf)
    best = np.argmin(candidates, axis=1)
    found = np.isfinite(candidates[rows, best])
    tied = np.sum(candidates == candidates[rows, best, None], axis=1) > 1
    return np.where(found & ~tied, best, incumbent)


def shared_batch(rng, quality, incumbent, identity, anchor, cfg):
    """Exact Gaussian marginal/joint mean and paired-variance statistics.

    Centered Gaussian case components U0/common, U1/king and Ui/independent
    have df=blocks-1. Projecting Ui onto U0,U1 gives independent normal
    coordinates and a chi-square residual norm. This preserves shared-case
    covariance in both means and SEs without allocating 4,000 case rows.
    Exact artifact copies share all components; their difference is zero.
    """
    r, m = quality.shape
    rows = np.arange(r)
    blocks = cfg["blocks"]
    df = blocks - 1
    king = quality[rows, incumbent]
    sigma = cfg["case_sd"] * quality
    king_sigma = sigma[rows, incumbent]
    rho = cfg["shared_correlation"]
    identical = identity == identity[rows, incumbent, None]
    related = anchor == identity[rows, incumbent, None]
    affinity = np.where(identical, 1.0, np.where(related, cfg["copy_affinity"], 0.0))
    a0 = (king_sigma[:, None] - sigma) * math.sqrt(rho)
    a1 = (king_sigma[:, None] - sigma * affinity) * math.sqrt(1 - rho)
    ai = -sigma * np.sqrt(1 - affinity**2) * math.sqrt(1 - rho)

    # Map identical artifacts to the same independent component.
    first = np.argmax(identity[:, :, None] == identity[:, None, :], axis=2)
    z0 = rng.normal(size=(r, 1))
    z1 = rng.normal(size=(r, 1))
    zi = np.take_along_axis(rng.normal(size=(r, m)), first, axis=1)
    difference = (
        king[:, None] - quality + (a0 * z0 + a1 * z1 + ai * zi) / math.sqrt(blocks)
    )
    king_observed = king + king_sigma * (
        math.sqrt(rho) * z0[:, 0] + math.sqrt(1 - rho) * z1[:, 0]
    ) / math.sqrt(blocks)
    observed = king_observed[:, None] - difference

    l00 = np.sqrt(rng.chisquare(df, size=(r, 1)))
    l10 = rng.normal(size=(r, 1))
    l11 = np.sqrt(rng.chisquare(df - 1, size=(r, 1)))
    z_i0 = np.take_along_axis(rng.normal(size=(r, m)), first, axis=1)
    z_i1 = np.take_along_axis(rng.normal(size=(r, m)), first, axis=1)
    residual = np.take_along_axis(rng.chisquare(df - 2, size=(r, m)), first, axis=1)
    variance = (
        (a0 * l00 + a1 * l10 + ai * z_i0) ** 2
        + (a1 * l11 + ai * z_i1) ** 2
        + ai**2 * residual
    ) / df
    se = np.sqrt(np.maximum(variance, 0) / blocks)
    return observed, se


def summarize(values, bounded=False):
    """Episode-cluster MC mean CI, separate from scenario uncertainty."""
    a = np.asarray(values, dtype=float)
    mean = float(np.mean(a))
    half = 1.96 * float(np.std(a, ddof=1)) / math.sqrt(len(a)) if len(a) > 1 else 0
    lo, hi = mean - half, mean + half
    if bounded:
        lo, hi = max(0.0, lo), min(1.0, hi)
        if np.all(a == 0):
            # E[bounded rate] <= P(any episode event): exact zero-event
            # binomial bound, with episodes rather than dependent rounds.
            hi = 1 - 0.025 ** (1 / len(a))
        elif np.all(a == 1):
            lo = 0.025 ** (1 / len(a))
    return {
        "low": lo,
        "base": mean,
        "high": hi,
    }


def episode_population(cfg, reps):
    roles = (
        ["expert"] * cfg["experts"]
        + ["steady"] * cfg["steady"]
        + ["imitator"] * cfg["imitators"]
        + ["holder"] * cfg["holders"]
        + ["newcomer"] * cfg["newcomers"]
    )
    m = len(roles)
    rng = np.random.default_rng(cfg["public_seed"])
    role = np.array(roles)
    quality = rng.uniform(
        1 + cfg["initial_gap_low"], 1 + cfg["initial_gap_high"], size=(reps, m)
    )
    quality[:, 0] = 1.0
    growth = np.array([cfg["growth_by_role"][v] for v in roles])[None, :]
    growth = (
        growth
        * rng.uniform(cfg["skill_factor_low"], cfg["skill_factor_high"], size=(reps, m))
        * cfg["growth_scale"]
    )
    hours = np.array([cfg["hours_by_role"][v] for v in roles])[None, :]
    rates = np.array([cfg["gpu_rate_by_role"][v] for v in roles])[None, :]
    daily_cost = (hours * rates + cfg["effort_overhead"]) * cfg["cost_scale"]
    arrival = np.where(role == "newcomer", cfg["arrival_day"], 0)
    return role, quality, growth, daily_cost, arrival


def run_population(cfg, reps):
    """Vectorized episode clusters; all randomness public synthetic."""
    if reps < 2 or cfg["days"] <= cfg["arrival_day"] + 30:
        raise ValueError("need episode replication and full newcomer follow-up")
    if not 0 < cfg["decay"] <= 1 or cfg["challenges"] < 1:
        raise ValueError("invalid decay or Challenge count")
    if cfg["quality_floor"] <= 0 or cfg["case_sd"] < 0 or cfg["newcomers"] < 1:
        raise ValueError("invalid quality/noise/population")
    if not 0 <= cfg["shared_correlation"] < 1 or not 0 <= cfg["copy_affinity"] <= 1:
        raise ValueError("invalid correlations")
    if not 0 < cfg.get("share_override", 1 / cfg["challenges"]) <= 1:
        raise ValueError("invalid allocation")
    role, quality, growth, daily_cost, arrival = episode_population(cfg, reps)
    r, m = quality.shape
    rows = np.arange(r)
    # Separate streams keep unchanged kinds of randomness matched across options.
    seed = cfg["public_seed"]
    skill_rng = np.random.default_rng(seed + 11)
    screen_rng = np.random.default_rng(seed + 23)
    exam_rng = np.random.default_rng(seed + 37)
    belief_rng = np.random.default_rng(seed + 41)
    gate_rng = np.random.default_rng(seed + 53)
    identity = np.broadcast_to(np.arange(m), (r, m)).copy()
    anchor = np.full((r, m), -1, dtype=int)
    displayed = np.full((r, m), -np.inf)
    nominee_quality = quality.copy()
    nominee_identity = identity.copy()
    nominee_anchor = anchor.copy()
    incumbent = np.zeros(r, dtype=int)
    stored_quality = np.ones(r)
    stored_identity = np.zeros(r, dtype=int)
    stored_anchor = np.full(r, -1, dtype=int)
    clock_age = np.zeros(r, dtype=int)
    research_days = np.zeros((r, m))
    paid = np.zeros((r, m))
    cost = np.zeros((r, m))
    nominee_days = np.zeros((r, m))
    effort_days = np.zeros((r, m))
    action_counts = np.zeros((r, 4))
    first_crown = np.full((r, m), cfg["days"] + 1)
    first_crown[:, 0] = 0
    changes = np.zeros(r)
    self_advances = np.zeros(r)
    false_crowns = np.zeros(r)
    submargin_promotions = np.zeros(r)
    improvements = np.zeros(r)
    missed = np.zeros(r)
    real_opportunities = np.zeros(r)
    spell_start = np.zeros(r, dtype=int)
    spells = [[] for _ in range(r)]
    promotions = np.zeros(r)
    resets = np.zeros(r)
    copy_wins = np.zeros(r)
    critical = t_critical(cfg["alpha"], cfg["k"], cfg["blocks"])
    share = cfg.get("share_override", 1 / cfg["challenges"])
    imitation = role == "imitator"
    research_role = np.isin(role, ["expert", "steady", "newcomer"])
    newcomers = role == "newcomer"

    for day in range(cfg["days"]):
        active = day >= arrival
        king = stored_quality.copy()
        king_identity = stored_identity.copy()
        arriving = (day == arrival) & newcomers
        quality = np.where(arriving, king[:, None] * (1 + cfg["newcomer_gap"]), quality)
        is_king = np.arange(m)[None, :] == incumbent[:, None]
        marginal_growth = growth / (1 + research_days / cfg["diminishing_days"])
        # 0=hold, 1=independent research, 2=pure imitation, 3=imitate+research.
        actions = np.where(research_role, 1, 0)[None, :].repeat(r, axis=0)
        copy_action = 3 if cfg["copy_mode"] == "improve" else 2
        actions[:, imitation] = copy_action
        if cfg["behavior"] == "adaptive":
            belief = quality * np.exp(
                belief_rng.normal(0, cfg["belief_sd"], size=(r, m))
            )
            # Public opponent is the stored king, not its unpublished upgrade.
            king_belief = stored_quality[:, None] * np.exp(
                belief_rng.normal(0, cfg["belief_sd"], size=(r, 1))
            )
            plan = cfg["planning_days"]
            floor = cfg["quality_floor"]
            expected_gain = (
                marginal_growth
                + cfg["breakthrough_probability"] * cfg["breakthrough_mean"]
            )
            independent = floor + (belief - floor) * np.exp(-plan * expected_gain)
            penalty = 0 if cfg["copy_mode"] == "exact" else cfg["copy_penalty"]
            copied = king_belief * (1 + penalty)
            imitated = floor + (np.minimum(belief, copied) - floor) * np.exp(
                -plan * expected_gain
            )
            candidates = [independent, copied, imitated]
            utilities = []
            base_rent = rent(
                cfg["daily_pool"],
                share,
                cfg["decay"],
                cfg["forecast_hazard"],
                cfg["discount"],
            )
            for action, q_next in enumerate(candidates, 1):
                se = cfg["case_sd"] * np.sqrt(
                    np.maximum(
                        king_belief**2
                        + q_next**2
                        - 2 * cfg["shared_correlation"] * king_belief * q_next,
                        1e-12,
                    )
                    / cfg["blocks"]
                )
                threshold = np.maximum(cfg["margin"] * king_belief, critical * se)
                p_win = normal_cdf((king_belief - q_next - threshold) / se)
                # Approximate forecast top-k probability, not an equilibrium.
                forecast_rank = np.sum(belief[:, None, :] < q_next[:, :, None], axis=2)
                nomination = 1 / (
                    1
                    + np.exp((forecast_rank - cfg["k"] + 0.5) / cfg["rank_temperature"])
                )
                action_cost = (
                    daily_cost
                    if action != 2
                    else cfg["copy_hours"]
                    * np.array([cfg["gpu_rate_by_role"][v] for v in role])[None, :]
                    * cfg["cost_scale"]
                )
                if action == 3:
                    action_cost = (
                        action_cost
                        + cfg["copy_hours"]
                        * np.array([cfg["gpu_rate_by_role"][v] for v in role])[None, :]
                        * cfg["cost_scale"]
                    )
                u = p_win * nomination * base_rent - plan * action_cost
                rel_gain = np.maximum((king_belief - q_next) / king_belief, 0)
                new_hazard = cfg["forecast_hazard"] * np.exp(
                    -cfg["defense_sensitivity"] * rel_gain
                )
                old_rent = rent(
                    cfg["daily_pool"],
                    share,
                    cfg["decay"],
                    cfg["forecast_hazard"],
                    cfg["discount"],
                    clock_age[:, None],
                )
                new_rent = rent(
                    cfg["daily_pool"],
                    share,
                    cfg["decay"],
                    new_hazard,
                    cfg["discount"],
                    0 if cfg["self_reset"] else clock_age[:, None],
                )
                defense = (
                    p_win * np.maximum(new_rent - old_rent, 0) - plan * action_cost
                )
                utilities.append(np.where(is_king, defense, u))
            # Imitation-capable actors choose reuse; others independent research.
            score = np.stack(utilities, axis=2)
            score[:, ~imitation, 1:] = -np.inf
            if cfg["copy_mode"] != "improve":
                score[:, imitation, 2] = -np.inf
                score[:, imitation, 0] = -np.inf
            else:
                score[:, imitation, 0] = -np.inf
            score[:, role == "holder", :] = -np.inf
            best = np.argmax(score, axis=2)
            utility = np.max(score, axis=2)
            actions = np.where(utility > 0, best + 1, 0)

        actions = np.where(active, actions, 0)
        for a in range(4):
            action_counts[:, a] += np.sum((actions == a) & active, axis=1)
        work = (actions == 1) | (actions == 3)
        imitation_action = (actions == 2) | (actions == 3)
        copy_rate = np.array([cfg["gpu_rate_by_role"][v] for v in role])[None, :]
        daily_spend = np.where(work, daily_cost, 0)
        daily_spend += (
            imitation_action * cfg["copy_hours"] * copy_rate * cfg["cost_scale"]
        )
        cost += daily_spend
        effort_days += work
        penalty = 0 if cfg["copy_mode"] == "exact" else cfg["copy_penalty"]
        source_quality = king[:, None] * (1 + penalty)
        use_anchor = imitation_action & (source_quality < quality)
        proposed = np.where(use_anchor, source_quality, quality)
        new_anchor = np.where(use_anchor, king_identity[:, None], anchor)
        if cfg["copy_mode"] == "exact":
            proposed_identity = np.where(use_anchor, king_identity[:, None], identity)
        else:
            proposed_identity = identity.copy()

        jitter = skill_rng.lognormal(
            -0.5 * cfg["growth_jitter"] ** 2, cfg["growth_jitter"], size=(r, m)
        )
        breakthroughs = skill_rng.random((r, m)) < cfg["breakthrough_probability"]
        step = marginal_growth * jitter + breakthroughs * skill_rng.uniform(
            0, 2 * cfg["breakthrough_mean"], size=(r, m)
        )
        proposal = cfg["quality_floor"] + (proposed - cfg["quality_floor"]) * np.exp(
            -step * work
        )
        accepted = active & (gate_rng.random((r, m)) >= cfg["gate_reject"])
        improved = accepted & (proposal < quality)
        quality = np.where(improved, proposal, quality)
        anchor = np.where(improved, new_anchor, anchor)
        if cfg["copy_mode"] == "exact":
            identity = np.where(improved & (actions == 2), proposed_identity, identity)
        unique = improved & (actions != 2)
        if cfg["copy_mode"] != "exact":
            unique |= improved & (actions == 2)
        identity = np.where(unique, m * (day + 1) + np.arange(m)[None, :], identity)
        research_days += work  # Failed attempts still consume cost/learning effort.

        first = np.argmax(identity[:, :, None] == identity[:, None, :], axis=2)
        noise = np.take_along_axis(screen_rng.normal(size=(r, m)), first, axis=1)
        screening = quality * np.exp(cfg["screen_sd"] * noise)
        screening *= np.where(imitation[None, :], math.exp(-cfg["copy_screen_bias"]), 1)
        # D6 identity refusal and one candidate per known synthetic coldkey.
        original_owner = identity % m == np.arange(m)[None, :]
        if cfg["use_ladder"]:
            admitted = (improved | arriving | ((day == 0) & active)) & original_owner
            log_score = -np.log(screening)
            grain = math.log1p(cfg["ladder_grain"])
            update = admitted & (log_score > displayed + grain)
            displayed = np.where(update, np.round(log_score / grain) * grain, displayed)
            nominee_quality = np.where(update, quality, nominee_quality)
            nominee_identity = np.where(update, identity, nominee_identity)
            nominee_anchor = np.where(update, anchor, nominee_anchor)
        else:
            displayed = -np.log(screening)
            nominee_quality = quality.copy()
            nominee_identity = identity.copy()
            nominee_anchor = anchor.copy()
        same_stored_king = is_king & (nominee_identity == stored_identity[:, None])
        if not cfg["incumbent_may_contend"]:
            same_stored_king |= is_king
        rank_key = np.where(
            active & original_owner & ~same_stored_king, -displayed, np.inf
        )
        order = np.lexsort((nominee_identity, rank_key), axis=1)[:, : cfg["k"]]
        selected = np.zeros((r, m), dtype=bool)
        selected[rows[:, None], order] = True
        selected &= active & original_owner & ~same_stored_king & np.isfinite(rank_key)
        nominee_days += selected
        king = stored_quality.copy()
        genuine = active & ~is_king & (quality < (1 - cfg["margin"]) * king[:, None])
        real_opportunities += np.sum(genuine, axis=1)
        nominated_gain = nominee_quality < (1 - cfg["margin"]) * king[:, None]
        missed += np.sum(genuine & ~(selected & nominated_gain), axis=1)
        board_quality = np.column_stack([nominee_quality, stored_quality])
        board_identity = np.column_stack([nominee_identity, stored_identity])
        board_anchor = np.column_stack([nominee_anchor, stored_anchor])
        board_king = np.full(r, m, dtype=int)
        observed, se = shared_batch(
            exam_rng, board_quality, board_king, board_identity, board_anchor, cfg
        )
        final_errors = np.where(
            np.column_stack([selected, np.ones(r, dtype=bool)]), observed, np.inf
        )
        winner = select_winner(final_errors, se, board_king, cfg["margin"], critical)
        promoted = winner != m
        new_owner = np.where(promoted, winner, incumbent)
        changed = new_owner != incumbent
        self_advance = promoted & ~changed
        previous_true = stored_quality.copy()
        new_true = board_quality[rows, winner]
        false = promoted & (new_true >= previous_true)
        false_crowns += false
        true_gain = (previous_true - new_true) / previous_true
        submargin_promotions += (
            promoted & (true_gain > 0) & (true_gain <= cfg["margin"])
        )
        copy_wins += changed & imitation[new_owner]
        improvements += np.where(
            promoted, np.maximum(np.log(previous_true / new_true), 0), 0
        )
        for ep in np.flatnonzero(changed):
            spells[ep].append((int(spell_start[ep]), day - int(spell_start[ep]), True))
        spell_start = np.where(changed, day, spell_start)
        changes += changed
        promotions += promoted
        self_advances += self_advance
        reset = changed | (self_advance & cfg["self_reset"])
        resets += reset
        stored_quality = new_true
        stored_identity = board_identity[rows, winner]
        stored_anchor = board_anchor[rows, winner]
        incumbent = new_owner
        first_crown[rows, incumbent] = np.minimum(first_crown[rows, incumbent], day)
        clock_age = np.where(reset, 0, clock_age)
        amount = cfg["daily_pool"] * share * cfg["decay"] ** clock_age
        paid[rows, incumbent] += amount
        clock_age += 1
    for ep in range(r):
        spells[ep].append(
            (int(spell_start[ep]), cfg["days"] - int(spell_start[ep]), False)
        )
    totals = np.sum(paid, axis=1)
    fraction = np.divide(
        paid, totals[:, None], out=np.zeros_like(paid), where=totals[:, None] > 0
    )
    concentration = np.sort(fraction, axis=1)
    restricted = []
    for histories in spells:
        complete_followup = [
            min(duration, 30)
            for start, duration, _ in histories
            if start <= cfg["days"] - 30
        ]
        restricted.append(float(np.mean(complete_followup)))
    metrics = {
        "crown_changes_per_30_days": changes * 30 / cfg["days"],
        "tenure_restricted_30_days": restricted,
        "terminal_spell_censored_fraction": [
            sum(not e for _, _, e in h) / len(h) for h in spells
        ],
        "paid_fraction_of_challenge_allocation": totals
        / (cfg["days"] * cfg["daily_pool"] * share),
        "paid_fraction_of_subnet_miner_pool": totals
        / (cfg["days"] * cfg["daily_pool"]),
        "top1_paid_share": concentration[:, -1],
        "top3_paid_share": np.sum(concentration[:, -3:], axis=1),
        "payout_hhi": np.sum(fraction**2, axis=1),
        "newcomer_crowned_within_30_days": np.mean(
            first_crown[:, newcomers] < cfg["arrival_day"] + 30, axis=1
        ),
        "newcomer_ever_crowned": np.mean(
            first_crown[:, newcomers] < cfg["days"], axis=1
        ),
        "newcomer_nominated_day_fraction": np.mean(
            nominee_days[:, newcomers] / (cfg["days"] - cfg["arrival_day"]), axis=1
        ),
        "false_accuracy_crowns_per_round": false_crowns / cfg["days"],
        "submargin_accuracy_promotions_per_round": submargin_promotions / cfg["days"],
        "imitation_owner_paid_share": np.sum(fraction[:, imitation], axis=1),
        "imitation_owner_crown_changes": copy_wins,
        "screening_missed_real_opportunity_fraction": np.divide(
            missed, real_opportunities, out=np.zeros(r), where=real_opportunities > 0
        ),
        "research_action_fraction": (action_counts[:, 1] + action_counts[:, 3])
        / np.sum(action_counts, axis=1),
        "pure_imitation_action_fraction": action_counts[:, 2]
        / np.sum(action_counts, axis=1),
        "hold_action_fraction": action_counts[:, 0] / np.sum(action_counts, axis=1),
        "compute_plus_assumed_overhead": np.sum(cost, axis=1),
        "gross_target_usd_equivalent": totals,
        "net_target_less_modeled_cost": totals - np.sum(cost, axis=1),
        "log_accuracy_improvement": improvements,
        "net_log_accuracy_improvement": np.log(1 / stored_quality),
        "self_advances": self_advances,
        "payout_clock_resets": resets,
        "promotions": promotions,
    }
    result = {
        "parameters": cfg,
        "metrics": {
            key: summarize(
                value,
                "fraction" in key
                or "share" in key
                or "hhi" in key
                or "crowned" in key
                or key.endswith("_per_round"),
            )
            for key, value in metrics.items()
        },
        "roles": {},
    }
    for name in sorted(set(role)):
        ix = role == name
        result["roles"][name] = {
            "gross_per_actor": summarize(np.mean(paid[:, ix], axis=1)),
            "cost_per_actor": summarize(np.mean(cost[:, ix], axis=1)),
            "net_per_actor": summarize(np.mean((paid - cost)[:, ix], axis=1)),
            "research_days_per_actor": summarize(np.mean(effort_days[:, ix], axis=1)),
            "ever_crowned_actor_fraction": summarize(
                np.mean(first_crown[:, ix] < cfg["days"], axis=1), True
            ),
        }
    return result


def base_config(manifest):
    return {key: record["base"] for key, record in manifest["parameters"].items()}


def wilson(successes, count):
    z = 1.959963984540054
    p = successes / count
    divisor = 1 + z * z / count
    center = (p + z * z / (2 * count)) / divisor
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / divisor
    return {
        "low": max(0, center - half),
        "base": p,
        "high": min(1, center + half),
        "successes": int(successes),
        "rounds": count,
    }


def grading_controls(manifest):
    base = base_config(manifest)
    result = []
    for sd in [0.2, 0.4, 0.9]:
        cfg = {**base, "case_sd": sd}
        for gain in [0, 0.01, 0.0225, 0.03, 0.05]:
            n = manifest["controls"]["null_rounds" if gain == 0 else "power_rounds"]
            rng = np.random.default_rng(99821)
            quality = np.ones((n, 11))
            if gain:
                quality[:, 1] = 1 - gain
            identity = np.broadcast_to(np.arange(11), quality.shape)
            anchor = np.full_like(identity, -1)
            incumbent = np.zeros(n, dtype=int)
            observed, se = shared_batch(rng, quality, incumbent, identity, anchor, cfg)
            winner = select_winner(
                observed,
                se,
                incumbent,
                cfg["margin"],
                t_critical(cfg["alpha"], 10, cfg["blocks"]),
            )
            event = winner != 0 if gain == 0 else winner == 1
            result.append(
                {
                    "case_sd": sd,
                    "true_gain": gain,
                    "outcome": "all_null_false_crown" if gain == 0 else "contender_win",
                    **wilson(np.sum(event), n),
                }
            )
    n = manifest["controls"]["null_rounds"]
    q = np.ones((n, 11))
    identity = np.zeros_like(q, dtype=int)
    observed, se = shared_batch(
        np.random.default_rng(99821),
        q,
        np.zeros(n, dtype=int),
        identity,
        identity,
        base,
    )
    winner = select_winner(
        observed,
        se,
        np.zeros(n, dtype=int),
        base["margin"],
        t_critical(base["alpha"], 10, base["blocks"]),
    )
    result.append({"outcome": "ten_exact_copies", **wilson(np.sum(winner != 0), n)})
    return result


def scenarios(manifest):
    base = base_config(manifest)
    configs = []
    for behavior in ["fixed", "adaptive"]:
        for decay in manifest["sweep"]["decay"]:
            for challenges in manifest["sweep"]["challenges"]:
                cfg = {
                    **base,
                    "behavior": behavior,
                    "decay": decay,
                    "challenges": challenges,
                }
                configs.append((f"grid_{behavior}_d{decay}_N{challenges}", cfg))
    for label, overrides in manifest["sensitivity"].items():
        for decay in [0.5, 0.9]:
            cfg = {**base, "behavior": "adaptive", "decay": decay, **overrides}
            configs.append((f"{label}_d{decay}", cfg))
    return configs


def write_results(manifest_path, result_path, reps_override=None):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["status"] != "PUBLIC_ASSUMPTIONS_ONLY":
        raise ValueError("requires public synthetic assumptions manifest")
    reps = reps_override or manifest["replicates"]["base"]
    records = []
    for label, cfg in scenarios(manifest):
        record = run_population(cfg, reps)
        record["scenario"] = label
        records.append(record)
        print(label, flush=True)
    output = {
        "status": "CONDITIONAL_RESEARCH_TARGETS_NOT_SETTLED_PAYOUTS",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "numpy_version": np.__version__,
        "replicates": reps,
        "interval_policy": "low/base/high = approximate 95% episode-cluster Monte Carlo mean CI; all-zero/all-one bounded outputs use conservative episode-indicator Clopper-Pearson limits; grading controls use Wilson. These do not cover behavioral/model uncertainty.",
        "base_parameters": base_config(manifest),
        "scenarios": records,
        "grading_controls": grading_controls(manifest),
    }
    for record in records:
        record["parameters"] = {
            key: value
            for key, value in record["parameters"].items()
            if value != output["base_parameters"].get(key)
        }
    result_path.write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    with result_path.with_suffix(".csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario",
                "behavior",
                "decay",
                "challenges",
                "metric",
                "low",
                "base",
                "high",
            ]
        )
        for record in records:
            c = {**output["base_parameters"], **record["parameters"]}
            for metric, values in record["metrics"].items():
                writer.writerow(
                    [
                        record["scenario"],
                        c["behavior"],
                        c["decay"],
                        c["challenges"],
                        metric,
                        values["low"],
                        values["base"],
                        values["high"],
                    ]
                )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, default=Path(__file__).with_name("assumptions.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("results.json")
    )
    parser.add_argument("--replicates", type=int)
    args = parser.parse_args()
    if args.output.resolve().parent != Path(__file__).resolve().parent:
        raise ValueError("research output must stay in this ticket directory")
    write_results(args.manifest, args.output, args.replicates)


if __name__ == "__main__":
    main()
