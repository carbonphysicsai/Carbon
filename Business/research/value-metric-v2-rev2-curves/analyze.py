"""Public DEVELOPMENT replay; no model execution or Carbon runtime imports."""

from __future__ import annotations

import argparse
import ast
import collections
import copy
import gzip
import hashlib
import importlib.util
import itertools
import json
import pathlib
import sys

import numpy as np
from scipy.stats import kendalltau

DRAFT_SHA = "afdc4145e030ec8025d4450401c5baf50fe42a95ee73f7dc76fdc7774148ecd5"
OLD_RESULTS_SHA = "e8a8256365ebddb6d30705f38f2edeefffae811371b49780a3f1fa0bc17521ab"
HERE = pathlib.Path(__file__).resolve().parent
OLD = HERE.parent / "value-metric-v2-stress"
GRID = {
    "population": [
        "nominal",
        "shifted",
        "pooled",
        "edge",
        "robust_soc",
        "robust_temperature",
    ],
    "kappa": [0.05, 0.1, 0.25, 0.5],
    "k": [1, 2, 3, 4, 5],
    "delta": [0, 0.01, 0.05, 0.1, 0.25],
    "alpha": [0.001, 0.005, 0.01, 0.025, 0.05],
}
ANCHOR = {"population": "pooled", "kappa": 0.1, "k": 3, "delta": 0.05, "alpha": 0.01}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def inherited_modules():
    # aggregate imports analyze_public by name; these are committed research helpers.
    pin = HERE / "source-pin.json"
    if pin.exists():
        for rel, expected in json.loads(pin.read_text(encoding="utf-8"))[
            "inherited_source_sha256"
        ].items():
            raw = (HERE / rel).read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Inherited research source identity mismatch")
    analysis = load_module("analyze_public", OLD / "analyze_public.py")
    aggregate = load_module("res08_aggregate", OLD / "aggregate.py")
    return analysis, aggregate


def prepare_rev2(args, analysis):
    """Keep RES-08 preparation; replace precisely its obsolete draft assertion.

    The original draft and cache identities are retained as rev-1 provenance.
    Their cached orders are NOT reused as rev-2 proposals. All member orders
    are recomputed below from the same digest-checked public predictions.
    """
    analysis.require_hash(args.draft, DRAFT_SHA)
    analysis.require_hash(OLD / "results.json", OLD_RESULTS_SHA)
    tree = ast.parse((OLD / "analyze_public.py").read_text(encoding="utf-8"))
    fn = copy.deepcopy(
        next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "prepare"
        )
    )
    removed = []
    for node in fn.body:
        if (
            isinstance(node, ast.Expr)
            and ast.unparse(node) == "require_hash(args.draft, DRAFT_HASH)"
        ):
            removed.append(node)
    if len(removed) != 1:
        raise ValueError("Expected exactly one historical draft check")
    fn.body = [n for n in fn.body if n not in removed]
    namespace = dict(vars(analysis))
    exec(  # noqa: S102
        compile(
            ast.Module([fn], type_ignores=[]), str(OLD / "analyze_public.py"), "exec"
        ),
        namespace,
    )
    return namespace["prepare"](args)


def strict_bank(truth, fallback):
    return truth[fallback]["status"] == "FEASIBLE" and all(
        v["status"] in ("FEASIBLE", "INFEASIBLE") for v in truth.values()
    )


def shortlist(candidates, assessed, fallback, cap, known_fallback=None):
    base = (
        known_fallback
        if known_fallback is not None
        else assessed[fallback]["objective"]
    )
    if base is None:
        return []
    return [
        c["id"]
        for c in sorted(
            candidates,
            key=lambda c: (
                (
                    assessed[c["id"]]["objective"]
                    if assessed[c["id"]]["objective"] is not None
                    else float("inf")
                ),
                c["c1"],
                c["c2"],
                c["id"],
            ),
        )
        if assessed[c["id"]]["feasible"]
        and assessed[c["id"]]["objective"] is not None
        and assessed[c["id"]]["objective"] < base
    ][:cap]


def map_assessments(namespace, q, method):
    # Reuse the entire RES-07 map body through construction of its quantities.
    source = ast.parse(namespace["SOURCE_RAW"].decode("utf-8"))
    fn = copy.deepcopy(
        next(
            n
            for n in source.body
            if isinstance(n, ast.FunctionDef) and n.name == "cached_scalar_order"
        )
    )
    fn.name = "cached_quantities"
    boundary = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "admissible" for t in n.targets)
    )
    fn.body = fn.body[:boundary] + [
        ast.Return(value=ast.Name(id="quantities", ctx=ast.Load()))
    ]
    ast.fix_missing_locations(fn)
    exec(  # noqa: S102
        compile(ast.Module([fn], type_ignores=[]), "RES07-map-reuse", "exec"), namespace
    )
    quantities = namespace["cached_quantities"](q, method)
    out = {}
    for c in namespace["CAND"]:
        per = [quantities[c["id"], i] for i in range(len(q["conditions"]))]
        if any(v is None for v in per):
            out[c["id"]] = {"feasible": False, "objective": None}
        else:
            checks = [namespace["decision"].check(namespace["CON"], v) for v in per]
            out[c["id"]] = {
                "feasible": all(v == "PASS" for ck in checks for v in ck.values()),
                "objective": max(v["time_to_cv_onset_s"] for v in per),
            }
    return out


def collect(args, analysis):
    ns = prepare_rev2(args, analysis)
    ns["SOURCE_RAW"] = analysis.require_hash(args.res07_code, analysis.SOURCE_HASH)
    questions = ns["Q"]
    candidates, fallback = ns["CAND"], ns["BASE"]
    members = ns["REAL"] + [
        m for m in ns["MEMBERS"] if m["kind"] == "ADVERSARIAL_REBUILD"
    ]
    manifest = {r["sha256"]: r for r in ns["MANIFEST"]}
    actors = []

    def actor(name, recipe, assessments, kind):
        rows = []
        known_rows = []
        for q, assessed in zip(questions, assessments, strict=True):
            truth = ns["TRUTH"][q["id"]]
            caps = []
            known_caps = []
            for k in GRID["k"]:
                order = (
                    shortlist(candidates, assessed, fallback, k)
                    if assessed is not None
                    else []
                )
                result = ns["ORIGINAL_VERIFY"](order, q, truth, k)
                chosen = result["returned"]
                gain = analysis.clipped_gain_seconds(
                    truth[fallback]["status"],
                    truth[fallback]["objective"],
                    truth[chosen]["objective"] if chosen else None,
                )
                caps.append(
                    {
                        "gain_seconds": gain,
                        "tokens": result["complete_case_tokens"],
                        "unsafe": result["unsafe_rejections"],
                        "unknown": result["unresolved_or_unavailable_attempts"],
                        "attempts": result["attempts"],
                        "returned": chosen,
                    }
                )
                known_order = (
                    shortlist(
                        candidates, assessed, fallback, k, truth[fallback]["objective"]
                    )
                    if assessed is not None
                    else []
                )
                known_result = ns["ORIGINAL_VERIFY"](known_order, q, truth, k)
                known_chosen = known_result["returned"]
                known_gain = analysis.clipped_gain_seconds(
                    truth[fallback]["status"],
                    truth[fallback]["objective"],
                    truth[known_chosen]["objective"] if known_chosen else None,
                )
                known_caps.append(
                    {
                        "gain_seconds": known_gain,
                        "tokens": known_result["complete_case_tokens"],
                        "unsafe": known_result["unsafe_rejections"],
                        "unknown": known_result["unresolved_or_unavailable_attempts"],
                    }
                )
            rows.append(caps)
            known_rows.append(known_caps)
        actors.append(
            {
                "name": name,
                "recipe": recipe,
                "kind": kind,
                "rows": rows,
                "known_fallback_rows": known_rows,
            }
        )

    for mi, m in enumerate(members):
        entry = manifest[m["prediction_bundle_sha256"]]
        raw = analysis.require_hash(
            args.public_inputs / entry["folder"] / entry["file"], entry["sha256"]
        )
        doc = json.loads(gzip.decompress(raw))
        pred = {key: doc["predictions"][key] for key in ns["REFS"]}
        assessments = [
            ns["decision"].assess_predicted(
                ns["CON"], q, candidates, ns["prediction_quantities"](q, pred)
            )
            for q in questions
        ]
        actor(m["member"], m["recipe"], assessments, m["kind"])
        if mi % 25 == 24:
            print("Rev-2 validator selectors measured", mi + 1, flush=True)
    actor("control-always-abstain", "control", [None] * len(questions), "CONTROL")
    for method, label in (
        ("bilinear_D_clamped", "bilinear-D"),
        ("nearest_D", "nearest-D"),
    ):
        actor(
            "control-" + label,
            "control",
            [map_assessments(ns, q, method) for q in questions],
            "CONTROL",
        )
    actor(
        "control-fallback",
        "control",
        [
            {
                c["id"]: {"objective": 1.0, "feasible": c["id"] == fallback}
                for c in candidates
            }
            for _ in questions
        ],
        "CONTROL",
    )
    actor(
        "control-oracle",
        "control",
        [
            {
                c["id"]: {
                    "objective": ns["TRUTH"][q["id"]][c["id"]]["objective"],
                    "feasible": ns["TRUTH"][q["id"]][c["id"]]["status"] == "FEASIBLE",
                }
                for c in candidates
            }
            for q in questions
        ],
        "ANSWER_INFORMED_CONTROL",
    )
    return {
        "status": "DEVELOPMENT_NOT_REGISTERED",
        "draft_sha256": DRAFT_SHA,
        "questions": questions,
        "families": {
            f: [i for i, q in enumerate(questions) if q["id"] in ids]
            for f, ids in ns["question_sets"]().items()
        },
        "truth": {q["id"]: ns["TRUTH"][q["id"]] for q in questions},
        "fallback": fallback,
        "actors": actors,
        "manifest": ns["MANIFEST"],
        "duplicates": ns["DUPLICATES"],
    }


def sign_test_p(differences, blocks, delta):
    """Exact block sign-flip diagnostic; symmetry is an explicit assumption."""
    x = np.asarray(differences, dtype=float) - delta
    labels = sorted(set(blocks))
    sums = np.array([x[np.array(blocks) == b].sum() for b in labels])
    signs = np.array(list(itertools.product((-1, 1), repeat=len(labels))))
    observed = sums.sum()
    tolerance = 100 * np.finfo(float).eps * max(1, abs(observed))
    return float(np.mean(signs @ sums >= observed - tolerance))


def lex_ranks(values, unsafe, unknown):
    keys = [
        (float(u), -int(s), -int(z))
        for u, s, z in zip(values, unsafe, unknown, strict=True)
    ]
    distinct = sorted(set(keys), reverse=True)
    # Earliest chain commitment absent; retain intervals for exact residual ties.
    return np.array([distinct.index(key) for key in keys])


def profiles(data):
    configs = []
    for parameter, choices in GRID.items():
        for value in choices:
            configs.append(dict(ANCHOR, **{parameter: value}, curve=parameter))
    for population in ("nominal", "shifted", "pooled"):
        for k, kappa in itertools.product(GRID["k"], GRID["kappa"]):
            configs.append(
                dict(ANCHOR, population=population, k=k, kappa=kappa, curve="joint")
            )
    return configs


def measure(data, analysis, inherited):
    questions = data["questions"]
    families = data["families"] | {
        "pooled": data["families"]["nominal"] + data["families"]["shifted"]
    }
    bank = [strict_bank(data["truth"][q["id"]], data["fallback"]) for q in questions]
    actors = data["actors"]
    names = [a["name"] for a in actors]
    real = 100
    cheap = names.index("control-bilinear-D")
    noop = names.index("control-always-abstain")
    gain = (
        np.array(
            [[[r["gain_seconds"] or 0 for r in q] for q in a["rows"]] for a in actors]
        )
        / 120
    )
    tokens = np.array([[[r["tokens"] for r in q] for q in a["rows"]] for a in actors])
    unsafe = np.array([[[r["unsafe"] for r in q] for q in a["rows"]] for a in actors])
    unknown = np.array([[[r["unknown"] for r in q] for q in a["rows"]] for a in actors])
    weights, _ = inherited.question_weights(
        {"questions": questions, "recipes": [a["recipe"] for a in actors]},
        replicates=2000,
    )
    anchor_ids = [i for i in families[ANCHOR["population"]] if bank[i]]
    anchor_u = (gain[:, :, 2] - 0.1 * tokens[:, :, 2])[:, anchor_ids].mean(axis=1)
    anchor_lex = lex_ranks(
        anchor_u[:real],
        unsafe[:real, anchor_ids, 2].sum(axis=1),
        unknown[:real, anchor_ids, 2].sum(axis=1),
    )
    rows = []
    for config in profiles(data):
        ids = [i for i in families[config["population"]] if bank[i]]
        row = config | {
            "question_ids": [questions[i]["id"] for i in ids],
            "n": len(ids),
        }
        if not ids:
            rows.append(row | {"status": "EMPTY_BANK_NOT_ZERO_VALUE"})
            continue
        ki = config["k"] - 1
        per = gain[:, :, ki] - config["kappa"] * tokens[:, :, ki]
        values = per[:, ids].mean(axis=1)
        assert np.all(per[noop] == 0)
        uunsafe = unsafe[:, ids, ki].sum(axis=1)
        uunknown = unknown[:, ids, ki].sum(axis=1)
        blocks = [
            str((questions[i]["split"], questions[i]["conditions"][0][0])) for i in ids
        ]
        boot = inherited.boot_means(per, ids, weights)
        paired = boot[:, :real] - boot[:, cheap, None]
        lower, upper = np.nanquantile(paired, [0.025, 0.975], axis=0)
        if len(set(blocks)) < 2:
            lower[:] = np.nan
            upper[:] = np.nan
        margin = values[:real] - values[cheap]
        pvalues = [
            sign_test_p(per[i, ids] - per[cheap, ids], blocks, config["delta"])
            for i in range(real)
        ]
        # Conservative round family diagnostic; production multiplicity is unregistered.
        passed = (
            (values[:real] > 0)
            & (margin > config["delta"])
            & (np.array(pvalues) <= config["alpha"])
        )
        keys = lex_ranks(values[:real], uunsafe[:real], uunknown[:real])
        exact_pairs = [
            (a, b)
            for a in range(real)
            for b in range(a + 1, real)
            if values[a] == values[b]
        ]
        num_pairs = sum(
            round(values[a], 12) == round(values[b], 12)
            for a in range(real)
            for b in range(a + 1, real)
        )
        row |= {
            "status": "MEASURED_PUBLIC_PROXY",
            "blocks": len(set(blocks)),
            "min_exact_p": 2 ** (-len(set(blocks))),
            "always_abstain_U": float(values[noop]),
            "always_abstain_rank": analysis.rank_interval(values[noop], values[:real]),
            "cheap_U": float(values[cheap]),
            "real_point_beats_cheap": int(np.sum(margin > 0)),
            "real_positive_U_and_margin": int(
                np.sum((margin > 0) & (values[:real] > 0))
            ),
            "no_member_beats_cheap_point": bool(np.all(margin <= 0)),
            "paired_CI95_lower_positive": int(np.sum(lower > 0)),
            "paired_CI_available": len(set(blocks)) >= 2,
            "paired_test_pass": int(passed.sum()),
            "bonferroni_round_test_pass": int(
                np.sum(passed & (np.array(pvalues) <= config["alpha"] / real))
            ),
            "exact_U_tie_pairs": len(exact_pairs),
            "numeric_U_tie_pairs_12digits": int(num_pairs),
            "unsafe_separated_exact_tie_pairs": int(
                sum(uunsafe[a] != uunsafe[b] for a, b in exact_pairs)
            ),
            "residual_lex_tie_pairs": int(
                sum(keys[a] == keys[b] for a, b in exact_pairs)
            ),
            "tau_U_to_anchor": analysis.tau(values[:real], anchor_u[:real]),
            "tau_lex_to_anchor": float(kendalltau(keys, anchor_lex).statistic),
            "unsafe_total_real": int(uunsafe[:real].sum()),
            "per_member": [
                {
                    "name": names[i],
                    "U": float(values[i]),
                    "margin_over_cheap": float(margin[i]),
                    "paired_CI95": (
                        [float(lower[i]), float(upper[i])]
                        if np.isfinite(lower[i])
                        else None
                    ),
                    "p_one_sided_delta": pvalues[i],
                    "unsafe": int(uunsafe[i]),
                    "unknown": int(uunknown[i]),
                }
                for i in range(real)
            ],
            "controls_and_adversaries": [
                {
                    "name": names[i],
                    "kind": actors[i]["kind"],
                    "U": float(values[i]),
                    "unsafe": int(uunsafe[i]),
                    "unknown": int(uunknown[i]),
                    "rank_vs_raw_real": analysis.rank_interval(
                        values[i], values[:real]
                    ),
                }
                for i in range(real, len(names))
            ],
        }
        known = np.array(
            [
                [
                    a["known_fallback_rows"][j][ki]["gain_seconds"] / 120
                    - config["kappa"] * a["known_fallback_rows"][j][ki]["tokens"]
                    for j in ids
                ]
                for a in actors
            ]
        )
        known_values = known.mean(axis=1)
        row["known_reference_fallback_objective_sensitivity"] = {
            "changed_member_U": int(np.sum(known_values[:real] != values[:real])),
            "tau_to_model_fallback_selector": analysis.tau(
                known_values[:real], values[:real]
            ),
            "real_point_beats_cheap": int(
                np.sum(known_values[:real] > known_values[cheap])
            ),
        }
        rows.append(row)
    coverage = []
    for i, q in enumerate(questions):
        truth = data["truth"][q["id"]]
        coverage.append(
            {
                "question": q["id"],
                "scored_strict": bank[i],
                "fallback": truth[data["fallback"]]["status"],
                "reference_statuses": dict(
                    collections.Counter(v["status"] for v in truth.values())
                ),
            }
        )
    excluded_returns = []
    for family, indices in families.items():
        for ki, k in enumerate(GRID["k"]):
            excluded_returns.append(
                {
                    "family": family,
                    "k": k,
                    "unscored_questions": sum(not bank[j] for j in indices),
                    "real_verified_rescue_returns": sum(
                        a["rows"][j][ki]["returned"] is not None
                        and data["truth"][questions[j]["id"]][data["fallback"]][
                            "status"
                        ]
                        == "INFEASIBLE"
                        for a in actors[:real]
                        for j in indices
                        if not bank[j]
                    ),
                }
            )
    return {
        "status": "DEVELOPMENT_NOT_REGISTERED",
        "draft_sha256": DRAFT_SHA,
        "grid_assumption": GRID,
        "anchor_not_recommendation": ANCHOR,
        "coverage": coverage,
        "excluded_question_returns": excluded_returns,
        "profiles": rows,
    }


def write_json(path, obj):
    _, inherited = inherited_modules()
    path.write_bytes((inherited.readable_json(obj) + "\n").encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", type=pathlib.Path)
    parser.add_argument("--res07-code", type=pathlib.Path)
    parser.add_argument("--reference-helper", type=pathlib.Path)
    parser.add_argument("--ev4-contract", type=pathlib.Path)
    parser.add_argument("--res07-results", type=pathlib.Path)
    parser.add_argument("--res06-json", type=pathlib.Path)
    parser.add_argument("--public-inputs", type=pathlib.Path)
    parser.add_argument("--draft", type=pathlib.Path)
    parser.add_argument("--cache", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    analysis, inherited = inherited_modules()
    if args.measurements:
        pins = json.loads((HERE / "source-pin.json").read_text(encoding="utf-8"))
        if (
            hashlib.sha256(args.measurements.read_bytes()).hexdigest()
            != pins["public_measurements_sha256"]
        ):
            raise ValueError("Public measurement asset identity mismatch")
        data = json.loads(args.measurements.read_text(encoding="utf-8"))
        if (
            data["draft_sha256"] != DRAFT_SHA
            or data["status"] != "DEVELOPMENT_NOT_REGISTERED"
        ):
            raise ValueError("Wrong measurement revision or maturity")
    else:
        data = collect(args, analysis)
        write_json(args.output.parent / "public-measurements.json", data)
    write_json(args.output, measure(data, analysis, inherited))
    print("Rev-2 curves written; no values adopted", flush=True)


if __name__ == "__main__":
    main()
