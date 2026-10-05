"""SR-M1: motor score candidates, computed exactly as registered.

The definitions live in `.agent/tickets/SR-M1_motor_score_candidates.md`,
which was committed and pushed before this module computed anything. This is
DEVELOPMENT evidence only. The frozen rule (`exam.py`) is unchanged and
nothing is adopted.
"""

from __future__ import annotations

import math
import random
from statistics import fmean, pstdev

from carbon.design_search import score_value, track_b

from . import decision_study as ds
from . import exam, q1_panel
from . import track_b as motor

L_RF = 0.30
L_MT = 4.0
COMPONENT_SETS = {
    "F0": ("mean", "shape"),
    "A1": ("mean", "amp"),
    "A2": ("mean", "shiftmin"),
    "B": ("mean", "shape"),
    "C": ("dec",),
    "A1B": ("mean", "amp"),
    "A1C": ("mean", "amp", "dec"),
    "A1BC": ("mean", "amp", "dec"),
    "A2B": ("mean", "shiftmin"),
}
WITH_B = {"B", "A1B", "A1BC", "A2B"}
ALPHAS = (0.5, 1.5, 2.0)
DELTAS = (-0.10, -0.05, 0.05, 0.10)
KRR_SETTINGS = ((2.0, 1e-4), (8.0, 1e-4), (4.0, 1e-2), (4.0, 1e-6))
BOOTSTRAPS = 2000
SCHEMA = "carbon.motor.score-candidates.v1"


def scales(train):
    ok = [r for r in train if r.get("status") == "OK"]
    base = exam.scales_from_train(ok)
    pp = [max(r["outputs"]["torque_nm"]) - min(r["outputs"]["torque_nm"]) for r in ok]
    return {**base, "s_pp": pstdev(pp)}


def _rf(curve):
    mean = fmean(curve)
    if mean <= 0:
        return 1.0
    return min((max(curve) - min(curve)) / mean, 1.0)


def components(prediction, reference, s):
    p = [float(t) for t in prediction["torque_nm"]]
    r = [float(t) for t in reference["outputs"]["torque_nm"]]
    pm, rm = fmean(p), fmean(r)
    pr = [t - pm for t in p]
    rr = [t - rm for t in r]
    n = len(r)

    def rms(a):
        return math.sqrt(fmean((x - y) ** 2 for x, y in zip(a, rr)))

    shift = min(rms(pr[k:] + pr[:k]) for k in range(n))
    return {
        "mean": abs(pm - rm) / s["s_mean"],
        "shape": rms(pr) / s["s_ripple"],
        "amp": abs((max(p) - min(p)) - (max(r) - min(r))) / s["s_pp"],
        "shiftmin": shift / s["s_ripple"],
        "dec": (abs(_rf(p) - _rf(r)) / L_RF + abs(pm - rm) / L_MT) / 2,
        "signed_mean": pm - rm,
        "important": reference["inputs"]["current_density_a_mm2"] >= exam.J_IMPORTANT,
    }


def candidate_scores(rows, s, cases=None):
    """Every candidate's score from per-case component rows (optionally a
    bootstrap draw of case indices)."""

    picked = rows if cases is None else [rows[i] for i in cases]
    out = {}
    important = [r["signed_mean"] for r in picked if r["important"]]
    bias = fmean(important) if important else 0.0
    b_term = max(0.0, bias) / s["s_mean"]
    for name, parts in COMPONENT_SETS.items():
        score = fmean(fmean(r[c] for c in parts) for r in picked)
        out[name] = score + (b_term if name in WITH_B else 0.0)
    return out


def widened_members(config, repository):
    """The fixture 5 plus the 11 registered development members."""

    batches, notes = q1_panel.members(config, repository)
    krr = batches["learned-krr-v1"]

    def scaled(alpha):
        def batch(inputs):
            out = {}
            for key, curve in krr(inputs).items():
                values = curve["torque_nm"]
                mean = fmean(values)
                out[key] = {"torque_nm": [mean + alpha * (v - mean) for v in values]}
            return out

        return batch

    def biased(delta):
        def batch(inputs):
            out = {}
            for key, curve in krr(inputs).items():
                values = curve["torque_nm"]
                shift = delta * fmean(values)
                out[key] = {"torque_nm": [v + shift for v in values]}
            return out

        return batch

    widened = dict(batches)
    for alpha in ALPHAS:
        widened[f"ripple-x{alpha:g}"] = scaled(alpha)
    for delta in DELTAS:
        widened[f"mean-bias{delta:+.2f}"] = biased(delta)
    for length, ridge in KRR_SETTINGS:
        settings = {
            **config["models"]["learned-krr-v1"],
            "length": length,
            "ridge": ridge,
        }
        variant = {**config, "models": {**config["models"], "learned-krr-v1": settings}}
        predict, _ = ds._learned_model(variant, repository)
        widened[f"krr-l{length:g}-r{ridge:g}"] = q1_panel._batch(predict)
    return widened, notes


def _decisions(problem, contract, reference, batches, directory):
    predictors = [motor._model(n, contract, b) for n, b in batches.items()]
    q1 = track_b.alignment(
        problem,
        predictors,
        method="fixed_grid",
        parameters={},
        query_allowance=len(problem.designs) * len(problem.conditions),
        reference=reference,
        directory=directory,
        unit=motor.UNIT,
    )
    scope = track_b.CONTRACT_SCOPE
    return {
        n: {
            "value": track_b.decision_value(q1["arms"][n]["scopes"][scope]),
            "selection": q1["arms"][n]["design_id"],
            "outcome": q1["arms"][n]["scopes"][scope]["proposal_outcome"],
            "tie_determined": q1["arms"][n]["scopes"][scope]["tie_determined"],
        }
        for n in batches
    }


def _tau(scores, values, names):
    usable = [n for n in names if values[n] is not None]
    return score_value.kendall_tau_b(
        [-scores[n] for n in usable],
        [(-values[n][0], -values[n][1]) for n in usable],
    )


def _interval(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    lo = xs[int(0.025 * (len(xs) - 1))]
    hi = xs[math.ceil(0.975 * (len(xs) - 1))]
    return [lo, hi]


def study(names, rows_by_member, s, values, bootstraps=BOOTSTRAPS):
    """Per candidate: tau, rho, divergence, top-k and the case-bootstrap band."""

    n_cases = len(next(iter(rows_by_member.values())))
    full = {m: candidate_scores(rows_by_member[m], s) for m in names}
    results = {}
    for cand in COMPONENT_SETS:
        panel = {
            m: {
                "score": -full[m][cand],
                "value": values[m]["value"],
                "eligible": True,
                "recipe": m,
                "kind": "MEMBER",
            }
            for m in names
        }
        aligned = score_value.alignment(panel, top_k=3)
        results[cand] = {
            "scores": {m: full[m][cand] for m in names},
            "kendall_tau_b": aligned["kendall_tau_b"],
            "spearman_rho": aligned["spearman_rho"],
            "divergence_count": sum(
                c["condition"] == "SCORE_VALUE_DIVERGENCE"
                for c in aligned["conditions"]
            ),
            "divergent_members": sorted(
                c["member"]
                for c in aligned["conditions"]
                if c["condition"] == "SCORE_VALUE_DIVERGENCE"
            ),
            "top_k": aligned["top_k"],
        }
    rng = random.Random(0)
    taus = {cand: [] for cand in COMPONENT_SETS}
    for _ in range(bootstraps):
        cases = [rng.randrange(n_cases) for _ in range(n_cases)]
        draw = {m: candidate_scores(rows_by_member[m], s, cases) for m in names}
        for cand in COMPONENT_SETS:
            taus[cand].append(
                _tau(
                    {m: draw[m][cand] for m in names},
                    {m: values[m]["value"] for m in names},
                    names,
                )
            )
    for cand in COMPONENT_SETS:
        diffs = [
            None if a is None or b is None else a - b
            for a, b in zip(taus[cand], taus["F0"])
        ]
        interval = _interval(diffs)
        results[cand]["tau_interval"] = _interval(taus[cand])
        results[cand]["tau_minus_F0_interval"] = interval
        results[cand]["progress_over_F0"] = (
            cand != "F0" and interval is not None and interval[0] > 0
        )
    return results


def run(repository, directory, bootstraps=BOOTSTRAPS):
    from pathlib import Path

    from .challenge import PublicMaterial
    from .practice import PracticeSet

    repository = Path(repository)
    config = motor.load_config(repository)
    table = __import__("json").loads((repository / motor.REPLAY).read_text("utf-8"))
    reference = motor.replay_reference(config, table)
    problem, contract = motor.problem(config)
    material = PublicMaterial.load(repository)
    s = scales(material.train)
    practice = PracticeSet.load(repository)
    inputs = {r["case_id"]: r["inputs"] for r in practice.records}
    batches, notes = widened_members(config, repository)
    rows = {}
    for name, batch in batches.items():
        predictions = batch(inputs)
        rows[name] = [
            components(predictions[r["case_id"]], r, s)
            for r in practice.records
            if r.get("status") == "OK"
        ]
    values = _decisions(problem, contract, reference, batches, Path(directory))
    fixture = list(q1_panel.members(config, repository)[0])
    widened = list(batches)
    frozen = {
        m: fmean(fmean((r["mean"], r["shape"])) for r in rows[m]) for m in fixture
    }
    return {
        "schema": SCHEMA,
        "registration": ".agent/tickets/SR-M1_motor_score_candidates.md (commit 00962445)",
        "scales": s,
        "frozen_rule_check": frozen,
        "decisions": values,
        "fixture_panel": study(fixture, rows, s, values, bootstraps),
        "widened_panel": study(widened, rows, s, values, bootstraps),
        "notes": {
            **notes,
            "n_fixture": len(fixture),
            "n_widened": len(widened),
            "bootstraps": bootstraps,
            "claims": "descriptive DEVELOPMENT evidence; nothing adopted",
        },
    }
