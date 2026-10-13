"""Public EV4 question-family research; no solver or model execution."""

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

HERE = pathlib.Path(__file__).resolve().parent
RESEARCH = HERE.parent
KAPPAS = (0.05, 0.1, 0.25, 0.5)
CAPS = (1, 2, 3, 4, 5)
BETAS = (0, 0.25, 1, 4)


def dependencies():
    pin = HERE / "source-pin.json"
    if pin.exists():
        for relative, expected in json.loads(pin.read_text(encoding="utf-8"))[
            "inherited_source_sha256"
        ].items():
            raw = (HERE / relative).read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Inherited public research source identity mismatch")
    path = RESEARCH / "value-metric-v2-rev2-curves/analyze.py"
    spec = importlib.util.spec_from_file_location("res09_public_research", path)
    rev2 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rev2
    spec.loader.exec_module(rev2)
    analysis, aggregate = rev2.inherited_modules()
    return rev2, analysis, aggregate


def objective(quantities, conditions, beta):
    if any(v is None or v["time_to_cv_onset_s"] is None for v in quantities):
        return None
    return max(
        v["time_to_cv_onset_s"] / 120 + beta * (v["peak_temperature_c"] - t)
        for v, (t, _) in zip(quantities, conditions, strict=True)
    )


def grammars(candidates):
    return {
        9: [
            c
            for c in candidates
            if c["c1"] in (0.75, 1.25, 2) and c["c2"] in (0.2, 0.6, 1)
        ],
        20: [c for c in candidates if c["c1"] in (0.75, 1, 1.5, 2)],
        35: list(candidates),
    }


def questions(namespace):
    out = []
    for size in (9, 20, 35):
        for split in ("development", "verification"):
            for q in namespace["Q"]:
                if q["family"] == "single" and q["split"] == split:
                    out.append(
                        q
                        | {"group": f"single-{split}-a{size}", "size": size, "beta": 0}
                    )
    warm = [(t, s) for t in (19.0, 29.0, 38.0) for s in (0.22, 0.40)]
    for n in (2, 3, 4):
        for i, conditions in enumerate(itertools.combinations(warm, n)):
            q = namespace["qdef"](
                f"warm-n{n}-{i}", list(conditions), "composed", "verification"
            )
            out.append(q | {"group": f"warm-robust-n{n}", "size": 35, "beta": 0})
    for q in namespace["Q"]:
        if q["family"] != "single":
            out.append(q | {"group": q["family"], "size": 35, "beta": 0})
        elif q["split"] == "verification":
            for beta in BETAS[1:]:
                out.append(
                    q | {"group": f"time-heat-beta{beta:g}", "size": 35, "beta": beta}
                )
    return out


def assess(namespace, question, candidates, quantities):
    # Missing map nodes remain omitted; never impute a physical answer.
    measured = {
        (c["id"], i): quantities.get((c["id"], float(t), float(s)))
        for c in candidates
        for i, (t, s) in enumerate(question["conditions"])
    }
    complete = [
        c
        for c in candidates
        if all(
            measured[c["id"], i] is not None for i in range(len(question["conditions"]))
        )
    ]
    predicted = namespace["decision"].assess_predicted(
        namespace["CON"], question, complete, measured
    )
    for c in candidates:
        per = [measured[c["id"], i] for i in range(len(question["conditions"]))]
        if c["id"] not in predicted:
            predicted[c["id"]] = {"feasible": False, "objective": None}
        else:
            predicted[c["id"]]["objective"] = objective(
                per, question["conditions"], question["beta"]
            )
    return predicted


def blend_outputs(records):
    """Interpolate public output traces, not physical reference truth."""
    return {
        key: (
            sum(np.asarray(v[key]) * weight for v, weight in records).tolist()
            if isinstance(records[0][0][key], list)
            else sum(v[key] * weight for v, weight in records)
        )
        for key in ("voltage_v", "temperature_c", "plating_margin_v")
    }


def trace_map(namespace, q):
    """Reuse RES-07 D-node weights; change only the interpolation representation.

    Scalar interpolation drops a stencil if a node never reaches CV. Trace
    interpolation does not fabricate that node's time: it interpolates the
    voltage traces, then applies the unchanged measurement helper.
    """
    tree = ast.parse(namespace["SOURCE_RAW"].decode("utf-8"))
    fn = copy.deepcopy(
        next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "cached_scalar_order"
        )
    )
    fn.name = "cached_trace_quantities"
    boundary = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "admissible" for t in n.targets)
    )
    fn.body = fn.body[:boundary] + [
        ast.Return(value=ast.Name(id="quantities", ctx=ast.Load()))
    ]
    changes = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "measured" for t in node.targets
        ):
            node.value = ast.parse(
                "[(r['outputs'], w) for r,w in records if r['status']=='OK']",
                mode="eval",
            ).body
            changes += 1
        if isinstance(node, ast.If) and ast.unparse(node.test).startswith(
            "len(measured) != len(records)"
        ):
            node.test = ast.parse("len(measured) != len(records)", mode="eval").body
            node.orelse[0].value = ast.parse(
                "decision.measure(CON, blend_outputs(measured))", mode="eval"
            ).body
            changes += 1
    if changes != 2:
        raise ValueError("Expected exact scalar-to-trace interpolation adapter")
    namespace["blend_outputs"] = blend_outputs
    ast.fix_missing_locations(fn)
    exec(  # noqa: S102
        compile(ast.Module([fn], type_ignores=[]), "RES07-D-trace-reuse", "exec"),
        namespace,
    )
    return namespace["cached_trace_quantities"](q, "bilinear_D_clamped")


def prepare(args, rev2, analysis):
    ns = rev2.prepare_rev2(args, analysis)
    ns["SOURCE_RAW"] = analysis.require_hash(args.res07_code, analysis.SOURCE_HASH)
    cases = sorted(
        {tuple(q["conditions"][0]) for q in ns["Q"] if q["family"] == "single"}
    )
    actors = []
    manifest = {r["sha256"]: r for r in ns["MANIFEST"]}
    for mi, member in enumerate(ns["REAL"]):
        entry = manifest[member["prediction_bundle_sha256"]]
        raw = analysis.require_hash(
            args.public_inputs / entry["folder"] / entry["file"], entry["sha256"]
        )
        doc = json.loads(gzip.decompress(raw))
        scalar = {}
        for c in ns["CAND"]:
            for t, s in cases:
                key = ns["REF_INDEX"][c["c1"], c["c2"], t, s]
                scalar[c["id"], t, s] = ns["decision"].measure(
                    ns["CON"], doc["predictions"][key]
                )
        actors.append(
            {"name": member["member"], "recipe": member["recipe"], "quantities": scalar}
        )
        if mi % 25 == 24:
            print("Public member quantities measured", mi + 1, flush=True)
    for method, name in (
        ("bilinear_D_clamped", "bilinear-D"),
        ("nearest_D", "nearest-D"),
    ):
        scalar = {}
        for q in ns["Q"]:
            if q["family"] != "single":
                continue
            rev2.map_assessments(ns, q, method)
            quantities = ns["cached_quantities"](q, method)
            t, s = q["conditions"][0]
            scalar.update(
                {
                    (c["id"], float(t), float(s)): quantities[c["id"], 0]
                    for c in ns["CAND"]
                }
            )
        actors.append({"name": name, "recipe": "cheap-control", "quantities": scalar})
    scalar = {}
    for q in ns["Q"]:
        if q["family"] == "single":
            quantities = trace_map(ns, q)
            t, s = q["conditions"][0]
            scalar.update(
                {
                    (c["id"], float(t), float(s)): quantities[c["id"], 0]
                    for c in ns["CAND"]
                }
            )
    actors.append(
        {"name": "bilinear-trace-D", "recipe": "cheap-control", "quantities": scalar}
    )
    for policy in ("low-current", "high-current", "fallback-c2-up", "fallback-c1-up"):
        actors.append(
            {
                "name": "solver-alone-" + policy,
                "recipe": "fixed-control",
                "policy": policy,
            }
        )
    return ns, actors


def fixed_order(candidates, policy, fallback):
    others = [c for c in candidates if c["id"] != fallback]
    base = next(c for c in candidates if c["id"] == fallback)
    if policy == "low-current":
        key = lambda c: (c["c1"], c["c2"])
    elif policy == "high-current":
        key = lambda c: (-c["c1"], -c["c2"])
    elif policy == "fallback-c2-up":
        key = lambda c: (
            c["c1"] != base["c1"],
            c["c2"] <= base["c2"],
            abs(c["c2"] - base["c2"]),
            c["c1"],
            c["c2"],
        )
    elif policy == "fallback-c1-up":
        key = lambda c: (
            c["c2"] != base["c2"],
            c["c1"] <= base["c1"],
            abs(c["c1"] - base["c1"]),
            c["c1"],
            c["c2"],
        )
    else:
        raise ValueError("Unknown fixed solver-alone order")
    return [c["id"] for c in sorted(others, key=key)]


def arrays(namespace, actors, rev2):
    qs = questions(namespace)
    grammar = grammars(namespace["CAND"])
    shape = (len(actors), len(qs), len(CAPS))
    gain, tokens, unsafe = (np.zeros(shape) for _ in range(3))
    coverage = []
    ceiling = []
    for qi, q in enumerate(qs):
        candidates = grammar[q["size"]]
        full = namespace["ref_assessment"](q, namespace["REFS"])
        for row in full.values():
            row["objective"] = objective(
                row.get("quantities", [None]), q["conditions"], q["beta"]
            )
        namespace["QINFO"][q["id"]] = namespace["qinfo"](q, full)
        truth = {c["id"]: full[c["id"]] for c in candidates}
        fallback = truth[namespace["BASE"]]
        priced = fallback["status"] == "FEASIBLE"
        strict = rev2.strict_bank(truth, namespace["BASE"])
        parent_strict = rev2.strict_bank(full, namespace["BASE"])
        best = namespace["decision"].best_in_set(candidates, truth)
        max_gain = (
            max(0, fallback["objective"] - truth[best]["objective"])
            if priced and best
            else None
        )
        ceiling.append(max_gain)
        coverage.append(
            {
                "id": q["id"],
                "group": q["group"],
                "actions": len(candidates),
                "conditions": q["conditions"],
                "beta_assumption": q["beta"],
                "priced": priced,
                "strict": strict,
                "full35_strict": parent_strict,
                "statuses": dict(
                    collections.Counter(v["status"] for v in truth.values())
                ),
                "uncertain_actions": [
                    a
                    for a, v in truth.items()
                    if v["status"] in ("UNRESOLVED", "REFERENCE_UNAVAILABLE")
                ],
            }
        )
        for ai, actor in enumerate(actors):
            predicted = (
                assess(namespace, q, candidates, actor["quantities"])
                if "policy" not in actor
                else None
            )
            for ki, cap in enumerate(CAPS):
                order = (
                    fixed_order(candidates, actor["policy"], namespace["BASE"])[:cap]
                    if "policy" in actor
                    else rev2.shortlist(candidates, predicted, namespace["BASE"], cap)
                )
                row = namespace["ORIGINAL_VERIFY"](order, q, truth, cap)
                chosen = row["returned"]
                if chosen:
                    assert truth[chosen]["status"] == "FEASIBLE"
                gain[ai, qi, ki] = (
                    max(0, fallback["objective"] - truth[chosen]["objective"])
                    if priced and chosen
                    else 0
                )
                tokens[ai, qi, ki] = row["complete_case_tokens"]
                unsafe[ai, qi, ki] = row["unsafe_rejections"]
        if qi % 50 == 49:
            print("Question variants measured", qi + 1, flush=True)
    return qs, coverage, ceiling, gain, tokens, unsafe


def block_ci(values, ids, questions):
    # Composed questions share inputs; one composed public panel has no fresh
    # independent blocks. Do not resample its combinations as independent data.
    if any(len(questions[i]["conditions"]) != 1 for i in ids):
        return None
    blocks = sorted({str(tuple(questions[i]["conditions"][0])) for i in ids})
    # Preserve within-temperature dependence, as RES-08/09 did.
    temps = sorted({questions[i]["conditions"][0][0] for i in ids})
    if len(temps) < 2:
        return None
    rng = np.random.default_rng(20261013)
    counts = rng.multinomial(len(temps), np.ones(len(temps)) / len(temps), 2000)
    weights = counts[:, [temps.index(questions[i]["conditions"][0][0]) for i in ids]]
    boot = weights @ values[:, ids].T / weights.sum(axis=1, keepdims=True)
    assert blocks
    return np.quantile(boot, [0.025, 0.975], axis=0)


def collect(namespace, actors, rev2):
    qs, coverage, ceiling, gain, tokens, unsafe = arrays(namespace, actors, rev2)
    times = [
        r["wall_s"]
        for r in namespace["REFS"].values()
        if r["status"] == "OK" and isinstance(r.get("wall_s"), (int, float))
    ]
    return {
        "status": "DEVELOPMENT_NOT_REGISTERED",
        "questions": qs,
        "coverage": coverage,
        "ceiling": ceiling,
        "gain": gain.tolist(),
        "tokens": tokens.tolist(),
        "unsafe": unsafe.tolist(),
        "actors": [{"name": a["name"], "recipe": a["recipe"]} for a in actors],
        "public_case_wall_s_p10_p50_p90": np.quantile(times, [0.1, 0.5, 0.9]).tolist(),
        "public_OK_reference_cases": len(times),
        "public_reference_wall_s_sum": float(sum(times)),
        "unpriced_gain_array_meaning": "Bookkeeping zeros only; no buyer gain is asserted, and unpriced questions never enter a mean.",
    }


def aggregate(data):
    qs, coverage, ceiling, actors = (
        data[k] for k in ("questions", "coverage", "ceiling", "actors")
    )
    gain, tokens, unsafe = (np.asarray(data[k]) for k in ("gain", "tokens", "unsafe"))
    groups = sorted({q["group"] for q in qs})
    profiles = []
    for group in groups:
        offered = [i for i, q in enumerate(qs) if q["group"] == group]
        for scope in (
            "strict",
            "priced_incomplete_diagnostic",
            "matched_full35_strict",
        ):
            if scope == "priced_incomplete_diagnostic":
                ids = [i for i in offered if coverage[i]["priced"]]
            elif scope == "strict":
                ids = [i for i in offered if coverage[i]["strict"]]
            else:
                ids = [i for i in offered if coverage[i]["full35_strict"]]
            for ki, cap in enumerate(CAPS):
                for kappa in KAPPAS:
                    record = {
                        "group": group,
                        "scope": scope,
                        "cap": cap,
                        "kappa_assumption": kappa,
                        "offered": len(offered),
                        "questions": len(ids),
                        "question_ids": [coverage[i]["id"] for i in ids],
                    }
                    if not ids:
                        profiles.append(record | {"status": "EMPTY_BANK_GAP"})
                        continue
                    u = gain[:, :, ki] - kappa * tokens[:, :, ki]
                    means = u[:, ids].mean(axis=1)
                    bilinear, nearest = means[100:102]
                    strongest = max(bilinear, nearest)
                    ci = block_ci(u[:100] - u[100], ids, qs)
                    trace_ci = block_ci(u[:100] - u[102], ids, qs)
                    max_gain = float(np.mean([ceiling[i] for i in ids]))
                    map_gains = gain[100:102, ids, ki].mean(axis=1)
                    budget_options = [(0.0, "known-fallback", 0)]
                    for smaller in range(ki + 1):
                        alternative = (
                            gain[100:, :, smaller] - kappa * tokens[100:, :, smaller]
                        )
                        budget_options.extend(
                            (float(value), actors[100 + j]["name"], smaller + 1)
                            for j, value in enumerate(alternative[:, ids].mean(axis=1))
                        )
                    budget_value, budget_policy, budget_prefix = max(budget_options)
                    best_real = int(np.argmax(means[:100]))
                    budget_actor = next(
                        (i for i, a in enumerate(actors) if a["name"] == budget_policy),
                        None,
                    )
                    profiles.append(
                        record
                        | {
                            "status": "PUBLIC_RETROSPECTIVE_DIAGNOSTIC",
                            "bilinear_U": float(bilinear),
                            "nearest_U": float(nearest),
                            "real_beat_bilinear": int(
                                np.sum(means[:100] > bilinear + 1e-12)
                            ),
                            "real_beat_stronger_two_maps": int(
                                np.sum(means[:100] > strongest + 1e-12)
                            ),
                            "trace_map_U": float(means[102]),
                            "trace_map_ceiling_capture": (
                                float(gain[102, ids, ki].mean() / max_gain)
                                if max_gain
                                else None
                            ),
                            "real_beat_trace_map": int(
                                np.sum(means[:100] > means[102] + 1e-12)
                            ),
                            "paired_CI_lower_positive_vs_trace": (
                                int(np.sum(trace_ci[0] > 0))
                                if trace_ci is not None
                                else None
                            ),
                            "paired_CI_lower_positive_vs_bilinear": (
                                int(np.sum(ci[0] > 0)) if ci is not None else None
                            ),
                            "best_real_margin_vs_stronger_maps": float(
                                max(means[:100]) - strongest
                            ),
                            "retrospective_cheap_budget_envelope_U": budget_value,
                            "retrospective_envelope_policy": budget_policy,
                            "retrospective_envelope_prefix": budget_prefix,
                            "real_beat_retrospective_budget_envelope": int(
                                np.sum(means[:100] > budget_value + 1e-12)
                            ),
                            "best_real_margin_vs_budget_envelope": float(
                                max(means[:100]) - budget_value
                            ),
                            "point_best_real_gain": float(
                                gain[best_real, ids, ki].mean()
                            ),
                            "point_best_real_tokens": float(
                                tokens[best_real, ids, ki].mean()
                            ),
                            "budget_envelope_gain": (
                                float(gain[budget_actor, ids, budget_prefix - 1].mean())
                                if budget_actor is not None
                                else 0.0
                            ),
                            "budget_envelope_tokens": (
                                float(
                                    tokens[budget_actor, ids, budget_prefix - 1].mean()
                                )
                                if budget_actor is not None
                                else 0.0
                            ),
                            "real_U_low_median_high": np.quantile(
                                means[:100], [0, 0.5, 1]
                            ).tolist(),
                            "map_ceiling_capture": (
                                (map_gains / max_gain).tolist() if max_gain else None
                            ),
                            "ceiling_gain_units": max_gain,
                            "unsafe_proposals_real": int(unsafe[:100, ids, ki].sum()),
                            "per_member": [
                                {
                                    "name": a["name"],
                                    "U": float(means[i]),
                                    "margin_vs_stronger_maps": float(
                                        means[i] - strongest
                                    ),
                                    "paired_CI95_vs_bilinear": (
                                        ci[:, i].tolist() if ci is not None else None
                                    ),
                                }
                                for i, a in enumerate(actors[:100])
                            ],
                        }
                    )
    for record in profiles:
        if record["cap"] != 3 or record["kappa_assumption"] != 0.1:
            record.pop("per_member", None)
    return {
        "status": "DEVELOPMENT_NOT_REGISTERED",
        "coverage": coverage,
        "profiles": profiles,
        "source_question_count": len(qs),
        "member_count": 100,
        "recipe_count": 80,
        **{
            k: data[k]
            for k in (
                "public_case_wall_s_p10_p50_p90",
                "public_OK_reference_cases",
                "public_reference_wall_s_sum",
            )
        },
    }


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
    rev2, analysis, writer = dependencies()
    if args.measurements:
        pin = json.loads((HERE / "source-pin.json").read_text(encoding="utf-8"))
        if (
            hashlib.sha256(args.measurements.read_bytes()).hexdigest()
            != pin["measurements_sha256"]
        ):
            raise ValueError("Public scalar measurement identity mismatch")
        data = json.loads(args.measurements.read_text(encoding="utf-8"))
        if data["status"] != "DEVELOPMENT_NOT_REGISTERED":
            raise ValueError("Expected public DEVELOPMENT measurements")
    else:
        ns, actors = prepare(args, rev2, analysis)
        data = collect(ns, actors, rev2)
        (args.output.parent / "measurements.json").write_bytes(
            (writer.readable_json(data) + "\n").encode()
        )
    result = aggregate(data)
    args.output.write_bytes((writer.readable_json(result) + "\n").encode())
    print("Family diagnostics written; no bank or parameters adopted", flush=True)


if __name__ == "__main__":
    main()
