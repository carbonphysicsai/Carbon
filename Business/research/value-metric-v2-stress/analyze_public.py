"""Offline DEVELOPMENT adapter around unchanged, digest-bound RES-07 functions."""

from __future__ import annotations

import argparse
import ast
import collections
import copy
import gzip
import hashlib
import importlib.util
import json
import math
import pathlib
import re

import numpy as np
from scipy.stats import kendalltau, rankdata

SOURCE_HASH = "e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff"
DRAFT_HASH = "973594923121ad177bbbd764ee94bae1d5b59b50aebe6ed0d67667250b0ffa4c"
REFERENCE_HASH = "72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf"
PRIOR_HASH = "a1473c98baaf2352c02db38b1aeef3938c41b2a958fd1f568cff0c5e29e975b0"
COHORT_HASH = "a320b9c7005b8c6ad21ee22958bc78baf4a20435677826a74ab9795f7c3f3b0e"
HELPER_BLOB = "b1d899d116317bd190ad6812f0aae5d3e8a16c0c"
CONTRACT_BLOB = "3961b89a98c8877190bc010579852497057d3518"
KAPPAS = (0.05, 0.1, 0.25, 0.5)
CAPS = (1, 2, 3, 4, 5)
UNITS = (60, 120, 240)
FALLBACKS = ("c1=0.5,c2=0.6", "c1=0.75,c2=0.6", "c1=1,c2=0.6")
RHOS = (0, 0.1, 0.25)
ETAS = (0, 0.25, 1)
TIE_DIGITS = 12  # ASSUMPTION numerical diagnostic, not production epsilon.
FUNCTIONS = {
    "sha",
    "gitblob",
    "finite",
    "tau",
    "numeric_mean",
    "quantiles",
    "recipe",
    "architecture",
    "rank_interval",
    "rank_changes",
    "candidates",
    "read_refs",
    "qdef",
    "ref_assessment",
    "qinfo",
    "prediction_quantities",
    "order_and_outcome",
    "verify",
    "fit_guard",
    "fresh_members",
    "cached_scalar_order",
    "question_sets",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def require_hash(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"Public/reused source identity mismatch: {path.name}")
    return raw


def clipped_gain_seconds(fallback_status, fallback_objective, returned_objective):
    """None is unpriced physical gain; a bookkeeping proxy may credit zero."""
    if fallback_status != "FEASIBLE":
        return None
    if returned_objective is None:
        return 0.0
    return max(0.0, fallback_objective - returned_objective)


def utility(credited_gain_seconds, attempts, kappa, unit, rescues=0, eta=0):
    if unit <= 0 or kappa <= 0 or np.any(np.asarray(attempts) < 0):
        raise ValueError("Positive research unit/cost and valid attempts required")
    return credited_gain_seconds / unit - kappa * attempts + eta * rescues


def rank_interval(value, real):
    rounded = np.round(np.asarray(real), TIE_DIGITS)
    v = round(float(value), TIE_DIGITS)
    return {
        "best": 1 + int(np.sum(rounded > v)),
        "worst": 1 + int(np.sum(rounded >= v)),
        "of": len(real) + 1,
    }


def tau(x, y):
    value = float(
        kendalltau(np.round(x, TIE_DIGITS), np.round(y, TIE_DIGITS)).statistic
    )
    return value if math.isfinite(value) else None


def stats(values):
    v = np.asarray(values, dtype=float)
    quantiles = np.quantile(v, [0, 0.25, 0.5, 0.75, 1])
    rounded = np.round(v, TIE_DIGITS)
    n = len(v)
    tie_pairs = sum(c * (c - 1) // 2 for c in collections.Counter(rounded).values())
    return {
        "min_q25_median_q75_max": quantiles.tolist(),
        "mean": float(v.mean()),
        "sd": float(v.std()),
        "iqr": float(quantiles[3] - quantiles[1]),
        "positive": int(np.sum(v > 1e-12)),
        "negative": int(np.sum(v < -1e-12)),
        "zero_numeric": int(np.sum(np.abs(v) <= 1e-12)),
        "exact_distinct_values": len(set(v.tolist())),
        "numeric_distinct_values": len(set(rounded.tolist())),
        "numeric_tie_pairs": tie_pairs,
        "all_pairs": n * (n - 1) // 2,
        "numeric_tie_fraction": tie_pairs / (n * (n - 1) / 2),
    }


def prepare(args):
    """Reuse source function bodies; skip original top-level analysis/writes."""
    source_raw = require_hash(args.res07_code, SOURCE_HASH)
    require_hash(args.draft, DRAFT_HASH)
    prior = json.loads(require_hash(args.res07_results, PRIOR_HASH))
    require_hash(args.public_inputs / "ev4-decision-references.jsonl", REFERENCE_HASH)
    original_dir = args.res07_code.parent
    helper = original_dir / "decision.py"
    contract = original_dir / "ev4-contract.json"
    if blob(helper.read_bytes().replace(b"\r\n", b"\n")) != HELPER_BLOB:
        raise ValueError("Pinned isolated measurement helper changed")
    if blob(contract.read_bytes().replace(b"\r\n", b"\n")) != CONTRACT_BLOB:
        raise ValueError("Pinned historical contract changed")
    spec = importlib.util.spec_from_file_location("isolated_public_decision", helper)
    decision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decision)
    tree = ast.parse(source_raw.decode("utf-8"))
    definitions = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS
    ]
    if {n.name for n in definitions} != FUNCTIONS:
        raise ValueError("Required RES-07 functions missing")
    namespace = {
        "np": np,
        "kendalltau": kendalltau,
        "rankdata": rankdata,
        "math": math,
        "pathlib": pathlib,
        "re": re,
        "json": json,
        "collections": collections,
        "gzip": gzip,
        "hashlib": hashlib,
        "copy": copy,
        "decision": decision,
        "HERE": original_dir,
        "PUBLIC": args.public_inputs,
        "BUDGETS": list(CAPS),
        "CON": json.loads(contract.read_text(encoding="utf-8")),
    }
    namespace["UNIT"] = namespace["CON"]["minimum_useful_improvement_s"]
    # Hash-bound, reviewed local research source; never accepts miner code.
    exec(  # noqa: S102
        compile(ast.Module(definitions, type_ignores=[]), str(args.res07_code), "exec"),
        namespace,
    )
    refs, reference_hash = namespace["read_refs"]()
    namespace.update(REFS=refs, REF_SHA=reference_hash)
    selected = []
    targets = {
        "CAND",
        "BYID",
        "BASE",
        "REF_INDEX",
        "Q",
        "QBYID",
        "TRUTH",
        "QINFO",
        "GUARD",
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                v.id
                for target in node.targets
                for v in ast.walk(target)
                if isinstance(v, ast.Name)
            }
            if names & targets:
                selected.append(node)
        elif isinstance(node, ast.For) and any(
            isinstance(v, ast.Call)
            and isinstance(v.func, ast.Attribute)
            and isinstance(v.func.value, ast.Name)
            and v.func.value.id == "Q"
            and v.func.attr == "append"
            for v in ast.walk(node)
        ):
            selected.append(node)
    exec(  # noqa: S102
        compile(ast.Module(selected, type_ignores=[]), str(args.res07_code), "exec"),
        namespace,
    )
    physics = json.loads(require_hash(args.res06_json, COHORT_HASH))
    if physics["reference_sha256"] != REFERENCE_HASH:
        raise ValueError("Prior public cohort/reference mismatch")
    namespace["PHYSICS"] = {m["member"]: m for m in physics["members"]}
    namespace["SETTLED_TRUTH"] = namespace["TRUTH"]  # No refined overlay in V2 primary.
    original_verify = namespace["verify"]

    def capture(order, question, truth, cap):
        result = original_verify(order, question, truth, cap)
        result["attempted_actions"] = order[:cap]
        return result

    namespace["verify"] = capture
    cache_ids = {
        "source": SOURCE_HASH,
        "draft": DRAFT_HASH,
        "references": REFERENCE_HASH,
        "prior_results": PRIOR_HASH,
        "caps": list(CAPS),
    }
    if args.cache.exists():
        cached = json.loads(gzip.decompress(args.cache.read_bytes()))
        if cached["ids"] != cache_ids:
            raise ValueError("Derived public cache identity mismatch")
        members, manifest, duplicates = (
            cached["members"],
            cached["manifest"],
            cached["duplicates"],
        )
        for row in manifest:
            require_hash(
                args.public_inputs / row["folder"] / row["file"], row["sha256"]
            )
    else:
        members, manifest, duplicates = namespace["fresh_members"]()
        args.cache.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(
            {
                "ids": cache_ids,
                "members": members,
                "manifest": manifest,
                "duplicates": duplicates,
            },
            allow_nan=False,
        ).encode()
        args.cache.write_bytes(gzip.compress(raw, mtime=0))
    if (
        manifest != prior["inventory"]["bundle_manifest"]
        or duplicates != prior["inventory"]["duplicates"]
    ):
        raise ValueError("RES-07 public artifact inventory drift")
    real = [m for m in members if m["kind"] == "EV4_REAL_CPU_REBUILD"]
    if len(real) != 100 or len({m["recipe"] for m in real}) != 80:
        raise ValueError("Expected real-member cohort absent")
    namespace.update(
        MEMBERS=members,
        REAL=real,
        MANIFEST=manifest,
        DUPLICATES=duplicates,
        ORIGINAL_VERIFY=original_verify,
    )
    print("Source reuse verified; real cohort", len(real), flush=True)
    return namespace


def collect(namespace):
    qs = namespace["Q"]
    truth = namespace["TRUTH"]
    decision = namespace["decision"]
    candidates = namespace["CAND"]
    rng = np.random.default_rng(20261012)
    controls = {
        "control-always-abstain": lambda q: [],
        "control-bilinear-D": lambda q: namespace["cached_scalar_order"](
            q, "bilinear_D_clamped"
        ),
        "control-nearest-D": lambda q: namespace["cached_scalar_order"](q, "nearest_D"),
        "control-random-feasible-frozen": lambda q: list(
            rng.permutation(
                [
                    c["id"]
                    for c in candidates
                    if truth[q["id"]][c["id"]]["status"] == decision.FEASIBLE
                ]
            )
        ),
        "control-oracle-physical": lambda q: (
            [namespace["QINFO"][q["id"]]["best"]]
            if namespace["QINFO"][q["id"]]["best"]
            else []
        ),
    }
    for fallback in FALLBACKS:
        controls["control-propose-fallback-" + fallback] = lambda q, b=fallback: [b]
    controls["control-bilinear-oracle-priced-mask"] = lambda q: (
        namespace["cached_scalar_order"](q, "bilinear_D_clamped")
        if truth[q["id"]][namespace["BASE"]]["status"] == decision.FEASIBLE
        else []
    )
    guard = namespace["GUARD"]
    controls["control-bilinear-D-guard-mask"] = lambda q: (
        namespace["cached_scalar_order"](q, "bilinear_D_clamped")
        if all(
            t >= guard["t_min"] and s >= guard["soc_min"] for t, s in q["conditions"]
        )
        else []
    )
    controls["control-oracle-unique-padding"] = lambda q: (
        [namespace["QINFO"][q["id"]]["best"]]
        + [
            c["id"]
            for c in sorted(
                candidates,
                key=lambda c: (
                    -(truth[q["id"]][c["id"]]["objective"] or 0),
                    c["c1"],
                    c["c2"],
                ),
            )
            if truth[q["id"]][c["id"]]["status"] == decision.FEASIBLE
            and c["id"] != namespace["QINFO"][q["id"]]["best"]
        ]
        if namespace["QINFO"][q["id"]]["best"]
        else []
    )
    actors = list(namespace["REAL"])
    for name, order_fn in controls.items():
        rows = {}
        for question in qs:
            order = order_fn(question)
            rows[question["id"]] = {
                "verify": {
                    str(k): namespace["verify"](
                        order, question, truth[question["id"]], k
                    )
                    for k in CAPS
                }
            }
        actors.append({"member": name, "recipe": name, "questions": rows})
    shape = (len(actors), len(qs), len(CAPS))
    attempts = np.zeros(shape)
    unsafe = np.zeros(shape)
    unknown = np.zeros(shape)
    returns = np.zeros(shape)
    gain_seconds = np.zeros((len(FALLBACKS),) + shape)
    rescues = np.zeros_like(gain_seconds)
    fallback_statuses = [
        [truth[q["id"]][fallback]["status"] for q in qs] for fallback in FALLBACKS
    ]
    ceiling_seconds = np.zeros((len(FALLBACKS), len(qs)))
    for bi, fallback in enumerate(FALLBACKS):
        for qi, q in enumerate(qs):
            base = truth[q["id"]][fallback]
            best = namespace["QINFO"][q["id"]]["best"]
            if base["status"] == decision.FEASIBLE:
                ceiling_seconds[bi, qi] = clipped_gain_seconds(
                    base["status"], base["objective"], truth[q["id"]][best]["objective"]
                )
    for ai, actor in enumerate(actors):
        for qi, q in enumerate(qs):
            for ki, cap in enumerate(CAPS):
                row = actor["questions"][q["id"]]["verify"][str(cap)]
                attempted = row["attempted_actions"]
                assert len(attempted) == len(set(attempted)) == row["attempts"] <= cap
                chosen = row["returned"]
                if chosen:
                    assert truth[q["id"]][chosen]["status"] == decision.FEASIBLE
                attempts[ai, qi, ki] = row["attempts"]
                unsafe[ai, qi, ki] = row["unsafe_rejections"]
                unknown[ai, qi, ki] = row["unresolved_or_unavailable_attempts"]
                returns[ai, qi, ki] = chosen is not None
                for bi, fallback in enumerate(FALLBACKS):
                    base = truth[q["id"]][fallback]
                    gain = clipped_gain_seconds(
                        base["status"],
                        base.get("objective"),
                        truth[q["id"]][chosen]["objective"] if chosen else None,
                    )
                    gain_seconds[bi, ai, qi, ki] = gain or 0.0
                    rescues[bi, ai, qi, ki] = (
                        chosen is not None and base["status"] == decision.INFEASIBLE
                    )
    assert np.all(gain_seconds >= 0)
    assert np.all(gain_seconds <= ceiling_seconds[:, None, :, None] + 1e-8)
    ids = {
        name: [i for i, q in enumerate(qs) if q["id"] in values]
        for name, values in namespace["question_sets"]().items()
    }
    complete = [
        all(v["status"] != decision.UNAVAILABLE for v in truth[q["id"]].values())
        for q in qs
    ]
    return {
        "actors": actors,
        "names": [a["member"] for a in actors],
        "questions": qs,
        "attempts": attempts,
        "unsafe": unsafe,
        "unknown": unknown,
        "returns": returns,
        "gain_seconds": gain_seconds,
        "rescues": rescues,
        "fallback_statuses": fallback_statuses,
        "ceiling_seconds": ceiling_seconds,
        "families": ids,
        "complete_bank": complete,
    }


def family_values(data, bi, ki, kappa, unit=120, eta=0, mask="all"):
    per_question = utility(
        data["gain_seconds"][bi, :, :, ki],
        data["attempts"][:, :, ki],
        kappa,
        unit,
        data["rescues"][bi, :, :, ki],
        eta,
    )
    # utility() permits scalar validation; the arrays are initialized above.
    values = {}
    for family, indices in data["families"].items():
        selected = [
            j
            for j in indices
            if mask == "all"
            or (
                mask == "fallback_feasible"
                and data["fallback_statuses"][bi][j] == "FEASIBLE"
            )
            or (mask == "complete_bank" and data["complete_bank"][j])
        ]
        values[family] = per_question[:, selected].mean(axis=1) if selected else None
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--res07-code", type=pathlib.Path, required=True)
    parser.add_argument("--res07-results", type=pathlib.Path, required=True)
    parser.add_argument("--res06-json", type=pathlib.Path, required=True)
    parser.add_argument("--public-inputs", type=pathlib.Path, required=True)
    parser.add_argument("--draft", type=pathlib.Path, required=True)
    parser.add_argument("--cache", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    namespace = prepare(args)
    data = collect(namespace)
    # Remaining aggregation is supplied by the report driver, not by Carbon runtime.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "status": "DEVELOPMENT_NOT_REGISTERED",
        "names": data["names"],
        "questions": data["questions"],
        "families": data["families"],
        "fallback_statuses": data["fallback_statuses"],
        "complete_bank": data["complete_bank"],
        "recipes": [a["recipe"] for a in data["actors"]],
        "manifest": namespace["MANIFEST"],
        "duplicates": namespace["DUPLICATES"],
        "source_functions_sha256": SOURCE_HASH,
        "draft_sha256": DRAFT_HASH,
    }
    out["reference_action_objectives"] = {
        q["id"]: {
            a: {"status": v["status"], "objective": v["objective"]}
            for a, v in namespace["TRUTH"][q["id"]].items()
        }
        for q in data["questions"]
    }
    for key in [
        "attempts",
        "unsafe",
        "unknown",
        "returns",
        "gain_seconds",
        "rescues",
        "ceiling_seconds",
    ]:
        out[key] = data[key].tolist()
    args.output.write_bytes((json.dumps(out, allow_nan=False) + "\n").encode())
    print(
        "Public sufficient statistics written outside the committed artifacts",
        flush=True,
    )


if __name__ == "__main__":
    main()
