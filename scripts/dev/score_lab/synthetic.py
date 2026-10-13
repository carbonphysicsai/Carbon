"""Analytic toy decision problems. Every truth evaluation is algebraic."""

from __future__ import annotations

import hashlib
import random
import statistics
from itertools import product

from .core import SCHEMA

MODEL_NAMES = (
    "unbiased-low-0",
    "unbiased-low-1",
    "unbiased-medium-0",
    "unbiased-medium-1",
    "unbiased-high-0",
    "unbiased-high-1",
    "boundary-bias",
    "rare-tail",
    "physics-violation",
    "overconfident",
)
PROBES = (
    "control-bilinear",
    "control-always-abstain",
    "known-bad-edge-optimist",
    "adversarial-gamer",
)


def profiles():
    """The full 2^5 diagnostic grid, not a selected scientific population."""
    for space, optima, constraint, shift, cost in product(
        ("small-grid", "continuous"),
        ("single", "multi"),
        ("loose", "tight"),
        ("nominal", "shifted"),
        (0.02, 0.2),
    ):
        yield {
            "space": space,
            "optima": optima,
            "constraint": constraint,
            "shift": shift,
            "verification_cost_ASSUMPTION": cost,
        }


def _rng(*parts):
    raw = ":".join(str(p) for p in parts).encode()
    return random.Random(int(hashlib.sha256(raw).hexdigest()[:16], 16))


def _centers(context, config):
    centers = [(0.73 - 0.10 * context, 0.0)]
    if config["optima"] == "multi":
        centers.append((0.32 + 0.05 * context, 0.045))
    return centers


def truth(x, context, config):
    """Objective is the lower envelope of explicit parabolas; hard margins."""
    objective = min((x - c) ** 2 + offset for c, offset in _centers(context, config))
    objective += 0.30 * context
    radius = 0.52 if config["constraint"] == "loose" else 0.28
    cap = 1.30 if config["constraint"] == "loose" else 0.90
    margins = (
        radius - abs(x - (0.45 + 0.08 * context)),
        cap - (x + 0.25 * context + 0.15 * x * context),
    )
    return {
        "objective": objective,
        "margins": margins,
        "status": ("FEASIBLE" if min(margins) >= 0 else "INFEASIBLE"),
        "solves": 1,
    }


def exact_best(context, config):
    """Analytic constrained minimum, including the continuous grammar."""
    radius = 0.52 if config["constraint"] == "loose" else 0.28
    center = 0.45 + 0.08 * context
    lower = max(0.0, center - radius)
    upper = min(
        1.0,
        center + radius,
        (1.30 if config["constraint"] == "loose" else 0.90) / (1 + 0.15 * context)
        - 0.25 * context / (1 + 0.15 * context),
    )
    if lower > upper:
        return None
    candidates = [min(max(c, lower), upper) for c, _ in _centers(context, config)]
    return min(truth(x, context, config)["objective"] for x in candidates)


def _interp(x, context, config):
    anchors = (0.0, 0.5, 1.0)
    lo, hi = (0, 1) if x <= 0.5 else (1, 2)
    a, b = truth(anchors[lo], context, config), truth(anchors[hi], context, config)
    t = (x - anchors[lo]) / (anchors[hi] - anchors[lo])
    return {
        "objective": a["objective"] * (1 - t) + b["objective"] * t,
        "margins": tuple(
            a["margins"][j] * (1 - t) + b["margins"][j] * t for j in (0, 1)
        ),
    }


def _predict(name, qid, x, context, config, *, score_side):
    if name == "control-bilinear":
        out = _interp(x, context, config)
    else:
        t = truth(x, context, config)
        levels = {
            "unbiased-low": 0.012,
            "unbiased-medium": 0.04,
            "unbiased-high": 0.09,
        }
        level = next((v for k, v in levels.items() if name.startswith(k)), 0.025)
        rng = _rng(name, qid, f"{x:.8f}")
        objective = t["objective"] + rng.gauss(0, level)
        margins = [v + rng.gauss(0, level) for v in t["margins"]]
        if (
            name in ("boundary-bias", "known-bad-edge-optimist")
            and -0.09 < min(t["margins"]) < 0.04
        ):
            margins = [v + (0.10 if name == "boundary-bias" else 0.18) for v in margins]
        if name == "rare-tail" and rng.random() < 0.035:
            objective -= 0.4
            margins = [v + 0.3 for v in margins]
        if name == "physics-violation" and x > 0.82:
            objective -= 0.3  # toy law violation: below the parabolic envelope
        if name == "adversarial-gamer" and not score_side and x > 0.68:
            objective -= 0.4  # deliberately accurate on score cases only
            margins = [v + 0.3 for v in margins]
        out = {"objective": objective, "margins": tuple(margins)}
    if name == "control-always-abstain":
        out = {"objective": 1e6, "margins": (-1e6, -1e6)}
    out["feasible"] = min(out["margins"]) >= 0
    out["sigma"] = 0.001 if name == "overconfident" else 0.05
    return out


def _question(qid, context, config):
    xs = (
        (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        if config["space"] == "small-grid"
        else tuple(i / 50 for i in range(51))
    )
    actions = {f"x={x:.2f}": truth(x, context, config) for x in xs}
    return {
        "id": qid,
        "block": qid,
        "context": context,
        "fallback": "x=0.20",
        "weight": 1.0,  # assumed uniform toy P/w, never a Challenge registration
        "actions": actions,
        "exact_best_objective": exact_best(context, config),
    }


def _decision_loss(question, prediction, cost, buyer=None):
    actions = question["actions"]
    fallback = actions[question["fallback"]]
    if buyer is not None:
        if fallback["status"] != "FEASIBLE":
            return None
        shortlist = sorted(
            (
                (p["objective"], aid)
                for aid, p in prediction.items()
                if p["feasible"] and p["objective"] < fallback["objective"]
            ),
            key=lambda x: (x[0], x[1]),
        )[: buyer["cap"]]
        feasible = [
            actions[aid]["objective"]
            for _, aid in shortlist
            if actions[aid]["status"] == "FEASIBLE"
            and actions[aid]["objective"] < fallback["objective"]
        ]
        gain = (
            max(0.0, (fallback["objective"] - min(feasible)) / buyer["unit"])
            if feasible
            else 0.0
        )
        return -(gain - cost * len(shortlist))
    ranked = sorted(
        ((p["objective"], aid) for aid, p in prediction.items() if p["feasible"]),
        key=lambda x: (x[0], x[1]),
    )
    if not ranked:
        return 0.0
    chosen = actions[ranked[0][1]]
    if chosen["status"] != "FEASIBLE":
        return 1.0 + cost  # ASSUMPTION toy false-feasible loss
    if fallback["status"] != "FEASIBLE":
        return None  # rescue is outside this scored value population
    benefit = max(0.0, fallback["objective"] - chosen["objective"])
    return cost - benefit


def _row(questions, predictions, config):
    errors, boundary, optimism, calls, correct = [], [], [], 0, 0
    losses = []
    for qid, question in questions.items():
        for aid, ref in question["actions"].items():
            pred = predictions[qid][aid]
            err = abs(pred["objective"] - ref["objective"]) + sum(
                abs(p - r) for p, r in zip(pred["margins"], ref["margins"], strict=True)
            )
            errors.append(err)
            if abs(min(ref["margins"])) < 0.12:
                boundary.append(err)
                optimism.append(
                    float(pred["feasible"] and ref["status"] == "INFEASIBLE")
                )
            calls += 1
            correct += pred["feasible"] == (ref["status"] == "FEASIBLE")
        losses.append(
            _decision_loss(
                question, predictions[qid], config["verification_cost_ASSUMPTION"]
            )
        )
    e = statistics.fmean(errors)
    be = statistics.fmean(boundary) if boundary else e
    opt = statistics.fmean(optimism) if optimism else 0.0
    regret = statistics.fmean(v for v in losses if v is not None)
    return {
        "eligible": True,
        "E": e,
        "legs": {
            "a": 1 / (1 + e),
            "r": 1 / (1 + be),
            "g": correct / calls,
            "m": 1 / (1 + 2 * e),
            "n": 1 / (1 + 2 * be),
            "p": 1 / (1 + opt),
            "q": 1 / (1 + max(0.0, regret)),
        },
        "gates": {
            "near": opt,
            "envelope": opt,
            "feasibility": sum(optimism) / max(1, len(errors)),
            "plating_fa": opt,
            "error": e,
        },
    }


def build(config, *, questions_per_side=8, buyer=None):
    if questions_per_side < 3:
        raise ValueError("need at least three analytic questions per side")
    shift = 0.19 if config["shift"] == "shifted" else 0.0
    score = {
        f"S-{i}": _question(f"S-{i}", 0.06 + i * 0.075, config)
        for i in range(questions_per_side)
    }
    value = {
        f"V-{i}": _question(f"V-{i}", 0.085 + i * 0.075 + shift, config)
        for i in range(questions_per_side)
    }
    oracle_losses = {}
    for qid, question in value.items():
        fallback = question["actions"][question["fallback"]]
        best = question["exact_best_objective"]
        oracle_losses[qid] = (
            None
            if fallback["status"] != "FEASIBLE" or best is None
            else min(
                0.0,
                config["verification_cost_ASSUMPTION"]
                - max(0.0, fallback["objective"] - best)
                / (buyer["unit"] if buyer is not None else 1.0),
            )
        )
    members = []
    for name in (*MODEL_NAMES, *PROBES):
        sp = {
            qid: {
                aid: _predict(
                    name, qid, float(aid[2:]), q["context"], config, score_side=True
                )
                for aid in q["actions"]
            }
            for qid, q in score.items()
        }
        vp = {
            qid: {
                aid: _predict(
                    name, qid, float(aid[2:]), q["context"], config, score_side=False
                )
                for aid in q["actions"]
            }
            for qid, q in value.items()
        }
        members.append(
            {
                "id": name,
                "recipe": (
                    name.rsplit("-", 1)[0] if name.startswith("unbiased") else name
                ),
                "kind": "MODEL" if name in MODEL_NAMES else "PROBE",
                "score_predictions": sp,
                "score_row": _row(score, sp, config),
                "value_losses": {
                    qid: _decision_loss(
                        q, vp[qid], config["verification_cost_ASSUMPTION"], buyer
                    )
                    for qid, q in value.items()
                },
            }
        )
    return {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "assumption": config
        | {
            "buyer_workflow_ASSUMPTION": (
                {"kind": "v2_shortlist", **buyer}
                if buyer is not None
                else {"kind": "one_pick", "false_feasible_loss": 1.0}
            )
        },
        "score_questions": score,
        "value_questions": value,
        "exact_oracle_losses": oracle_losses,
        "members": members,
    }
