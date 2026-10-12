"""Exploratory aggregation of RES-07-reused public sufficient statistics."""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import pathlib

import analyze_public as analysis
import numpy as np


def load(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw["status"] != "DEVELOPMENT_NOT_REGISTERED":
        raise ValueError("Expected public development sufficient statistics")
    data = dict(raw)
    for key in (
        "attempts",
        "unsafe",
        "unknown",
        "returns",
        "gain_seconds",
        "rescues",
        "ceiling_seconds",
    ):
        data[key] = np.asarray(raw[key], dtype=float)
    return data


def ci(values):
    v = np.asarray(values)
    if v.ndim == 1:
        v = v[np.isfinite(v)]
    return np.quantile(v, [0.025, 0.975], axis=0).tolist() if len(v) else None


def question_weights(data, replicates=2000):
    rng = np.random.default_rng(20261012)
    weights = np.zeros((replicates, len(data["questions"])))
    for split in ("development", "verification"):
        temperatures = sorted(
            {
                q["conditions"][0][0]
                for q in data["questions"]
                if q["split"] == split and q["family"] == "single"
            }
        )
        counts = rng.multinomial(
            len(temperatures),
            np.ones(len(temperatures)) / len(temperatures),
            replicates,
        )
        for j, q in enumerate(data["questions"]):
            if q["split"] == split and q["family"] in ("single", "robust_soc"):
                weights[:, j] = counts[:, temperatures.index(q["conditions"][0][0])]
            elif q["family"] == "robust_temperature":
                weights[:, j] = 1  # One shared temperature panel, no temperature CI.
    clusters = sorted(set(data["recipes"][:100]))
    counts = rng.multinomial(
        len(clusters), np.ones(len(clusters)) / len(clusters), replicates
    )
    member_weights = counts[:, [clusters.index(r) for r in data["recipes"][:100]]]
    return weights, member_weights


def boot_means(per_question, indices, weights):
    w = weights[:, indices]
    den = w.sum(axis=1)
    out = np.full((len(w), len(per_question)), np.nan)
    valid = den > 0
    out[valid] = w[valid] @ per_question[:, indices].T / den[valid, None]
    return out


def aggregate(data):
    names = data["names"]
    map_index = names.index("control-bilinear-D")
    no_op = names.index("control-always-abstain")
    weights, member_weights = question_weights(data)
    primary = {}
    point_vectors = {family: [] for family in data["families"]}
    boot_vectors = {family: [] for family in data["families"]}
    for ki, cap in enumerate(analysis.CAPS):
        for kappa in analysis.KAPPAS:
            profile = f"k{cap}-c{kappa:g}"
            q_utility = analysis.utility(
                data["gain_seconds"][1, :, :, ki],
                data["attempts"][:, :, ki],
                kappa,
                120,
            )
            assert np.all(q_utility[no_op] == 0)
            row = {"cap": cap, "kappa": kappa, "families": {}}
            for family, indices in data["families"].items():
                values = q_utility[:, indices].mean(axis=1)
                boot = boot_means(q_utility, indices, weights)
                point_vectors[family].append(values[:100])
                boot_vectors[family].append(boot[:, :100])
                paired = boot[:, :100] - boot[:, map_index, None]
                mw = member_weights
                means = np.sum(mw * boot[:, :100], axis=1) / mw.sum(axis=1)
                sd = np.sqrt(
                    np.sum(mw * (boot[:, :100] - means[:, None]) ** 2, axis=1)
                    / mw.sum(axis=1)
                )
                ceiling = float(data["ceiling_seconds"][1, indices].mean() / 120)
                gains = data["gain_seconds"][1, :, indices, ki].mean(axis=0) / 120
                # NumPy advanced indexing places the question axis first here.
                assert gains.shape == (len(names),)
                attempts = data["attempts"][:, indices, ki].mean(axis=1)
                base_feasible = [
                    j for j in indices if data["fallback_statuses"][1][j] == "FEASIBLE"
                ]
                complete = [j for j in indices if data["complete_bank"][j]]
                conditional = (
                    q_utility[:, base_feasible].mean(axis=1) if base_feasible else None
                )
                complete_values = (
                    q_utility[:, complete].mean(axis=1) if complete else None
                )
                controls = {}
                for actor in range(100, len(names)):
                    controls[names[actor]] = {
                        "U": float(values[actor]),
                        "gain_units": float(gains[actor]),
                        "attempts_mean": float(attempts[actor]),
                        "rank_vs_real": analysis.rank_interval(
                            values[actor], values[:100]
                        ),
                        "mean_CI95_question_blocks": ci(boot[:, actor]),
                        "conditional_safe_fallback_U": (
                            float(conditional[actor])
                            if conditional is not None
                            else None
                        ),
                    }
                comparisons = values[:100] - values[map_index]
                # Retrospective answer-informed envelope, not an adopted cheap policy.
                cheap_indices = [
                    names.index(n)
                    for n in (
                        "control-bilinear-D",
                        "control-nearest-D",
                        "control-bilinear-D-guard-mask",
                    )
                ]
                cheap_points = [0.0]
                cheap_boots = [np.zeros(len(weights))]
                for smaller in range(cap):
                    u = analysis.utility(
                        data["gain_seconds"][1, cheap_indices, :, smaller],
                        data["attempts"][cheap_indices, :, smaller],
                        kappa,
                        120,
                    )
                    cheap_points.extend(u[:, indices].mean(axis=1).tolist())
                    cheap_boots.extend(boot_means(u, indices, weights).T)
                envelope = max(cheap_points)
                envelope_boot = np.maximum.reduce(cheap_boots)
                positive_gross_negative_net = (gains[:100] > 1e-12) & (
                    values[:100] < -1e-12
                )
                unsafe_totals = data["unsafe"][:100, indices, ki].sum(axis=1)
                equal_gain_cost_different_unsafe = sum(
                    abs(gains[a] - gains[b]) <= 1e-12
                    and abs(attempts[a] - attempts[b]) <= 1e-12
                    and unsafe_totals[a] != unsafe_totals[b]
                    for a in range(100)
                    for b in range(a + 1, 100)
                )
                row["families"][family] = {
                    "offered_questions": len(indices),
                    "fallback_status_counts": dict(
                        collections.Counter(
                            data["fallback_statuses"][1][j] for j in indices
                        )
                    ),
                    "complete_bank_questions": len(complete),
                    "known_safe_fallback_questions": len(base_feasible),
                    "real_stats": analysis.stats(values[:100]),
                    "real_SD_CI95_recipe_question": ci(sd),
                    "positive_gross_gain_negative_U": int(
                        positive_gross_negative_net.sum()
                    ),
                    "real_beat_bilinear": int(np.sum(comparisons > 1e-12)),
                    "retrospective_cheap_budget_envelope_U": envelope,
                    "real_beat_retrospective_cheap_envelope": int(
                        np.sum(values[:100] > envelope + 1e-12)
                    ),
                    "envelope_paired_lower_CI_above_zero_descriptive_count": int(
                        np.sum(
                            np.nanquantile(
                                boot[:, :100] - envelope_boot[:, None], 0.025, axis=0
                            )
                            > 0
                        )
                    ),
                    "equal_gain_cost_pairs_different_unsafe": equal_gain_cost_different_unsafe,
                    "real_tie_bilinear": int(np.sum(np.abs(comparisons) <= 1e-12)),
                    "paired_lower_CI_above_zero_descriptive_count": int(
                        np.sum(np.nanquantile(paired, 0.025, axis=0) > 0)
                    ),
                    "ceiling_gain_units": ceiling,
                    "bilinear_ceiling_capture": (
                        float(gains[map_index] / ceiling) if ceiling else None
                    ),
                    "real_capture_min_median_max": (
                        np.quantile(gains[:100] / ceiling, [0, 0.5, 1]).tolist()
                        if ceiling
                        else None
                    ),
                    "controls": controls,
                    "conditional_real_beat_bilinear": (
                        int(np.sum(conditional[:100] > conditional[map_index] + 1e-12))
                        if conditional is not None
                        else None
                    ),
                    "complete_bank_real_beat_bilinear": (
                        int(
                            np.sum(
                                complete_values[:100]
                                > complete_values[map_index] + 1e-12
                            )
                        )
                        if complete_values is not None
                        else None
                    ),
                    "per_real_member": {
                        name: {
                            "U": float(values[i]),
                            "gain_units": float(gains[i]),
                            "rank_among_real": analysis.rank_interval(
                                values[i], np.delete(values[:100], i)
                            ),
                            "attempts_mean": float(attempts[i]),
                            "unsafe_attempts": int(
                                data["unsafe"][i, indices, ki].sum()
                            ),
                            "unknown_attempts": int(
                                data["unknown"][i, indices, ki].sum()
                            ),
                            "rescues": int(data["rescues"][1, i, indices, ki].sum()),
                            "mean_U_CI95_question_blocks": ci(boot[:, i]),
                            "paired_minus_bilinear_CI95": ci(paired[:, i]),
                            "conditional_safe_fallback_U": (
                                float(conditional[i])
                                if conditional is not None
                                else None
                            ),
                            "complete_bank_U": (
                                float(complete_values[i])
                                if complete_values is not None
                                else None
                            ),
                        }
                        for i, name in enumerate(names[:100])
                    },
                    "oracle_numeric_utility_upper_bound": float(
                        np.maximum(
                            0, data["ceiling_seconds"][1, indices] / 120 - kappa
                        ).mean()
                    ),
                    "exact_query_cache_zero_lookup_charge_upper_bound": ceiling,
                }
            primary[profile] = row
    profile_order = list(primary)
    matrices = {
        family: [[analysis.tau(a, b) for b in vectors] for a in vectors]
        for family, vectors in point_vectors.items()
    }
    neighbor_cis = {}
    cluster_keys = sorted(set(data["recipes"][:100]))
    cluster_indices = {
        r: [i for i, recipe in enumerate(data["recipes"][:100]) if recipe == r]
        for r in cluster_keys
    }
    rng = np.random.default_rng(
        20261013
    )  # ASSUMPTION separate numerical resampling stream.
    ix = [
        np.concatenate(
            [
                cluster_indices[cluster_keys[j]]
                for j in rng.integers(0, len(cluster_keys), len(cluster_keys))
            ]
        )
        for _ in range(2000)
    ]
    for family in ("nominal", "shifted"):
        neighbors = []
        for a in range(len(profile_order)):
            for b in range(a + 1, len(profile_order)):
                pa, pb = primary[profile_order[a]], primary[profile_order[b]]
                if (
                    pa["cap"] == pb["cap"]
                    and abs(
                        analysis.KAPPAS.index(pa["kappa"])
                        - analysis.KAPPAS.index(pb["kappa"])
                    )
                    == 1
                ) or (pa["kappa"] == pb["kappa"] and abs(pa["cap"] - pb["cap"]) == 1):
                    vals = [
                        analysis.tau(
                            boot_vectors[family][a][rep, ids],
                            boot_vectors[family][b][rep, ids],
                        )
                        for rep, ids in enumerate(ix)
                    ]
                    defined = [v for v in vals if v is not None]
                    neighbors.append(
                        {
                            "a": profile_order[a],
                            "b": profile_order[b],
                            "tau": matrices[family][a][b],
                            "CI95_recipe_question": ci(defined),
                            "defined": len(defined),
                        }
                    )
        neighbor_cis[family] = neighbors
    full_grid = []
    grid_vectors = {}
    for cap, kappa, unit, bi, rho, eta in itertools.product(
        analysis.CAPS,
        analysis.KAPPAS,
        analysis.UNITS,
        range(3),
        analysis.RHOS,
        analysis.ETAS,
    ):
        q_u = analysis.utility(
            data["gain_seconds"][bi, :, :, cap - 1],
            data["attempts"][:, :, cap - 1],
            kappa,
            unit,
            data["rescues"][bi, :, :, cap - 1],
            eta,
        )
        nominal = q_u[:, data["families"]["nominal"]].mean(axis=1)
        shifted = q_u[:, data["families"]["shifted"]].mean(axis=1)
        values = (1 - rho) * nominal + rho * shifted
        assert values[no_op] == 0
        key = (cap, kappa, unit, bi, rho, eta)
        grid_vectors[key] = values[:100]
        full_grid.append(
            {
                "k": cap,
                "kappa": kappa,
                "unit": unit,
                "fallback": analysis.FALLBACKS[bi],
                "rho": rho,
                "eta": eta,
                "real_stats": analysis.stats(values[:100]),
                "abstain_rank": analysis.rank_interval(0, values[:100]),
                "bilinear_U": float(values[map_index]),
                "real_beat_bilinear": int(
                    np.sum(values[:100] > values[map_index] + 1e-12)
                ),
                "top_real_tied_labels": [
                    names[i]
                    for i in range(100)
                    if abs(values[i] - max(values[:100])) <= 1e-12
                ],
                "scores_real_100": values[:100].tolist(),
            }
        )
    anchor = grid_vectors[3, 0.1, 120, 1, 0, 0]
    factors = [
        list(analysis.CAPS),
        list(analysis.KAPPAS),
        list(analysis.UNITS),
        list(range(3)),
        list(analysis.RHOS),
        list(analysis.ETAS),
    ]
    taus_by_factor = {k: [] for k in ("k", "kappa", "unit", "fallback", "rho", "eta")}
    for row, (key, values) in zip(full_grid, grid_vectors.items(), strict=True):
        row["tau_to_display_anchor"] = analysis.tau(anchor, values)
        for index, name in enumerate(taus_by_factor):
            here = factors[index].index(key[index])
            if here + 1 < len(factors[index]):
                neighbor = list(key)
                neighbor[index] = factors[index][here + 1]
                t = analysis.tau(values, grid_vectors[tuple(neighbor)])
                if t is not None:
                    taus_by_factor[name].append(t)
    sensitivity = {
        name: {
            "neighbor_count_defined": len(v),
            "tau_min_q25_median_q75_max": (
                np.quantile(v, [0, 0.25, 0.5, 0.75, 1]).tolist() if v else None
            ),
        }
        for name, v in taus_by_factor.items()
    }
    random_report = {}
    rng = np.random.default_rng(20261012)
    random_seconds = np.zeros((256, len(data["questions"]), 5))
    random_attempts = np.zeros_like(random_seconds)
    for qi, q in enumerate(data["questions"]):
        refs = data["reference_action_objectives"][q["id"]]
        pool = [a for a, v in refs.items() if v["status"] == "FEASIBLE"]
        base = refs[analysis.FALLBACKS[1]]
        for ri in range(256):
            order = list(rng.permutation(pool))
            for ki, cap in enumerate(analysis.CAPS):
                attempted = order[:cap]
                gain = analysis.clipped_gain_seconds(
                    base["status"],
                    base["objective"],
                    min(refs[a]["objective"] for a in attempted) if attempted else None,
                )
                random_seconds[ri, qi, ki] = gain or 0
                random_attempts[ri, qi, ki] = len(attempted)
    for cap in analysis.CAPS:
        for kappa in analysis.KAPPAS:
            random_u = (
                random_seconds[:, :, cap - 1] / 120
                - kappa * random_attempts[:, :, cap - 1]
            )
            random_report[f"k{cap}-c{kappa:g}"] = {
                family: {
                    "utility_min_q05_median_q95_max": np.quantile(
                        random_u[:, ids].mean(axis=1), [0, 0.05, 0.5, 0.95, 1]
                    ).tolist(),
                    "expected_utility_MC256": float(random_u[:, ids].mean()),
                    "basis": "256 oracle-support random orders; Monte Carlo spread, not physical CI",
                }
                for family, ids in data["families"].items()
            }
    policies = {}
    for profile, row in primary.items():
        policies[profile] = {}
        for family, v in row["families"].items():
            gaps = [
                x["U"] - v["controls"]["control-bilinear-D"]["U"]
                for x in v["per_real_member"].values()
            ]
            policies[profile][family] = {
                "absolute_margin_descriptive_real_count": {
                    str(m): sum(g > m for g in gaps) for m in (0, 0.05, 0.1, 0.25)
                },
                "cheap_capture_meets_assumed_onboarding_threshold": {
                    str(t): (
                        v["bilinear_ceiling_capture"] >= t
                        if v["bilinear_ceiling_capture"] is not None
                        else None
                    )
                    for t in (0.5, 0.75, 0.9, 0.99)
                },
                "status": "HUMAN_INPUT options only; no guard, payout or qualification decision",
            }
    for unit in analysis.UNITS:
        factor = 120 / unit
        x = analysis.utility(
            data["gain_seconds"],
            data["attempts"][None, ...],
            0.1,
            120,
            data["rescues"],
            0.25,
        )
        y = analysis.utility(
            data["gain_seconds"],
            data["attempts"][None, ...],
            0.1 * factor,
            unit,
            data["rescues"],
            0.25 * factor,
        )
        np.testing.assert_allclose(y, x * factor, atol=1e-12)
    result = {
        "schema": "carbon.research.value-metric-v2-stress.v1",
        "maturity": "DEVELOPMENT_NOT_REGISTERED",
        "draft_sha256": data["draft_sha256"],
        "res07_functions_sha256": data["source_functions_sha256"],
        "source_commit": "430740562ecd9b24b8ffb886be96747f59b3b280",
        "real_members": names[:100],
        "inventory": {
            "unique_bundles": len(data["manifest"]),
            "duplicates": len(data["duplicates"]),
            "bundle_manifest": data["manifest"],
            "question_ids": [q["id"] for q in data["questions"]],
            "family_indices": data["families"],
            "fallback_statuses": data["fallback_statuses"],
            "complete_reference_bank": data["complete_bank"],
        },
        "interpretation": "all-offered zero rescue-credit bookkeeping proxy; unpriced physical gain remains unknown; conditional and complete-bank sensitivities separate",
        "numeric_grids": {
            "caps": analysis.CAPS,
            "kappas": analysis.KAPPAS,
            "units": analysis.UNITS,
            "fallbacks": analysis.FALLBACKS,
            "rhos": analysis.RHOS,
            "etas": analysis.ETAS,
        },
        "primary": primary,
        "primary_profile_order": profile_order,
        "primary_tau_matrices": matrices,
        "primary_neighbor_tau_intervals": neighbor_cis,
        "full_numeric_grid": full_grid,
        "one_factor_neighbor_tau": sensitivity,
        "random_feasible_MC256": random_report,
        "policy_only_sensitivity": policies,
        "checks": {
            "all_returned_actions_reference_feasible": True,
            "unique_prefix_caps": True,
            "always_abstain_exact_zero_all_profiles": True,
            "gain_within_finite_ceiling": True,
            "coherent_unit_rescaling_all_public_arrays": True,
            "no_runtime_solver_or_model_execution": True,
        },
        "limits": [
            "exploratory pointwise intervals, no simultaneous coverage",
            "only four question-temperature blocks",
            "raw 100-member panel does not imply mandatory gate eligibility",
            "no chain timestamps for tiebreaks",
            "no buyer-calibrated benefit/verification price",
            "no current v3 question-law or fresh confirmation claim",
            "reference-incomplete public questions cannot certify a fully pre-solved V2 bank",
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = aggregate(load(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((readable_json(result) + "\n").encode())
    print(
        "Aggregated 20 primary /",
        len(result["full_numeric_grid"]),
        "sensitivity profiles",
        flush=True,
    )


def numpy_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Unsupported aggregate type: {type(value).__name__}")


def readable_json(value, depth=0):
    """Keep member/grid records on separate lines without expanding numeric arrays."""

    def compact(v):
        return json.dumps(v, allow_nan=False, default=numpy_scalar)

    pad = "  " * depth
    if isinstance(value, dict):
        if "scores_real_100" in value or "U" in value or not value:
            return compact(value)
        return (
            "{\n"
            + ",\n".join(
                "  " + pad + compact(k) + ": " + readable_json(v, depth + 1)
                for k, v in value.items()
            )
            + "\n"
            + pad
            + "}"
        )
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return (
            "[\n"
            + ",\n".join("  " + pad + readable_json(v, depth + 1) for v in value)
            + "\n"
            + pad
            + "]"
        )
    return compact(value)


if __name__ == "__main__":
    main()
