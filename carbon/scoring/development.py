"""Owner-delegated, non-paying DEVELOPMENT scalar and comparison rule.

This is a new result family in the existing scoring owner, not an A5 fixture
relabel or an official ScoreInput. Provenance is admitted by the comparison owner.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from carbon.development_session.profile import canonical, digest
from carbon.measurement_runtime.development import VERSION, METRICS
from .engine import _combined_score
from .model import LegScore

RULE = {
    "schema": "carbon.development-score-rule.v1",
    "id": "burgers-development-balanced-v1",
    "authority": "OWNER-C-W1-D3-DELEGATION-01",
    "challenge": ["burgers-dynamics-v1", "1.0"],
    "profile": "carbon.burgers-supervised-development.v2",
    "measurement_version": VERSION,
    "roles": ["EVAL", "STRESS"],
    "cases_per_role": 12,
    "replicas": 3,
    "weights": {"physics": 0.25, "robustness": 0.25, "accuracy": 0.5},
    "transform": "1/(1+error); A5 weighted-geometric scalar arithmetic",
    "physics": "equal-case energy_path_rms",
    "accuracy": "equal-case field_time_rms",
    "robustness": "worst-case field_time_rms",
    "role_aggregation": "minimum of EVAL and STRESS",
    "hard_limits": {
        "initial_condition": 32 * 2**-23,
        "conserved_mean": 0.01,
        "maximum_principle": 0.01,
        "integrated_energy_balance": 0.05,
    },
    "reference_balance_indicator_limit": 0.025,
    "practical_score_margin": 0.005,
    "per_case_noninferiority": 0.01,
    "equivalence_score_margin": 0.005,
    "reference_field_indicator_limit": 0.0025,
    "reference_energy_indicator_limit": 0.0025,
    "arithmetic_floor": 128 * 2**-52,
    "uncertainty": "all cross-replica pairs plus empirical reference sensitivity; no probability or population CI",
    "training_budget": "same v2 ceiling, 32..64 steps; unused ceiling earns no bonus",
    "historical_use": "ranking/calibration only; acceptance requires prospective freeze before both starts",
    "scope": "DEVELOPMENT_NONPAYING_NOT_QUALIFIED",
}


def rule_digest():
    return digest(canonical(RULE))


@dataclass(frozen=True)
class DevelopmentDecision:
    rule: str
    disposition: str
    baseline: dict
    challenger: dict
    difference_interval: tuple[float, float]
    reasons: tuple[str, ...]
    accepted_improvement: bool
    official_eligible: bool = False
    protected_eligible: bool = False
    settlement_eligible: bool = False
    network_eligible: bool = False


def summarize(rows):
    if type(rows) is not tuple or len(rows) != 72:
        raise ValueError("complete 2 x 12 x 3 evidence required")
    cells = {}
    for row in rows:
        if set(row) != {"role", "case", "replica", "measurement"}:
            raise ValueError("closed development measurement row required")
        key = (row["role"], row["case"], row["replica"])
        if (
            key in cells
            or key[0] not in RULE["roles"]
            or type(key[1]) is not str
            or type(key[2]) is not int
            or key[2] not in range(3)
        ):
            raise ValueError("conflicting/invalid case-replica identity")
        m = row["measurement"]
        if (
            m["version"] != VERSION
            or set(m["metrics"]) != set(METRICS)
            or any(
                type(v) is not float or not math.isfinite(v) or v < 0
                for v in m["metrics"].values()
            )
            or type(m["reference_balance_discretization_indicator"]) is not float
            or not math.isfinite(m["reference_balance_discretization_indicator"])
            or m["reference_balance_discretization_indicator"] < 0
        ):
            raise ValueError("incompatible/nonfinite measurement")
        cells[key] = m
    byrole = {
        role: sorted({k[1] for k in cells if k[0] == role}) for role in RULE["roles"]
    }
    if (
        any(len(c) != 12 for c in byrole.values())
        or set(byrole["EVAL"]) & set(byrole["STRESS"])
        or set(cells)
        != {(role, c, k) for role, cs in byrole.items() for c in cs for k in range(3)}
    ):
        raise ValueError("complete disjoint cohort required")
    failed = set()
    reference_unresolved = False
    roles = {}
    for role, cases in byrole.items():
        scores = []
        legs = []
        for replica in range(3):
            ms = [cells[(role, c, replica)] for c in cases]
            for m in ms:
                floor = m["reference_balance_discretization_indicator"]
                reference_unresolved |= (
                    floor > RULE["reference_balance_indicator_limit"]
                )
                for name, limit in RULE["hard_limits"].items():
                    allowance = floor if name == "integrated_energy_balance" else 0.0
                    if (
                        m["metrics"][name] + RULE["arithmetic_floor"]
                        >= limit + allowance
                    ):
                        failed.add(role + ":" + name)
            means = {
                name: math.fsum(m["metrics"][name] for m in ms) / 12 for name in METRICS
            }
            errors = (
                means["energy_path_rms"],
                max(m["metrics"]["field_time_rms"] for m in ms),
                means["field_time_rms"],
            )
            values = tuple(1 / (1 + v) for v in errors)
            leg = tuple(
                LegScore(name, (), v)
                for name, v in zip(
                    ("physics", "robustness", "accuracy"), values, strict=True
                )
            )
            scores.append(_combined_score(leg, (0.25, 0.25, 0.5)))
            legs.append(
                dict(zip(("physics", "robustness", "accuracy"), values, strict=True))
            )
        roles[role] = {
            "replica_scores": scores,
            "legs": legs,
            "metrics": {
                name: math.fsum(
                    cells[(role, c, k)]["metrics"][name]
                    for c in cases
                    for k in range(3)
                )
                / 36
                for name in METRICS
            },
        }
    replica_scores = [
        min(roles[r]["replica_scores"][k] for r in RULE["roles"]) for k in range(3)
    ]
    return {
        "roles": roles,
        "replica_scores": replica_scores,
        "score": math.fsum(replica_scores) / 3,
        "failed_mandatory": sorted(failed),
        "reference_unresolved": reference_unresolved,
    }


def compare(
    baseline,
    challenger,
    *,
    prospective,
    reference_field_indicator,
    reference_energy_indicator,
):
    b, c = summarize(baseline), summarize(challenger)
    for x in (reference_field_indicator, reference_energy_indicator):
        if type(x) is not float or not math.isfinite(x) or x < 0:
            raise ValueError("explicit finite numerical/reference indicators required")
    bkeys = {(r["role"], r["case"], r["replica"]) for r in baseline}
    if bkeys != {(r["role"], r["case"], r["replica"]) for r in challenger}:
        raise ValueError("incompatible cohorts")
    # Empirical sensitivity envelope: reciprocal errors are 1-Lipschitz, and
    # log(score) is 0.75-Lipschitz in field and 0.25 in energy error.
    # Twice the single-source sensitivity conservatively covers a difference.
    delta = (
        2 * (0.75 * reference_field_indicator + 0.25 * reference_energy_indicator)
        + RULE["arithmetic_floor"]
    )
    lo = min(c["replica_scores"]) - max(b["replica_scores"]) - delta
    hi = max(c["replica_scores"]) - min(b["replica_scores"]) + delta

    def dominance(left, right):
        return all(
            max(
                r["measurement"]["metrics"][metric]
                for r in left
                if r["role"] == role and r["case"] == case
            )
            - min(
                r["measurement"]["metrics"][metric]
                for r in right
                if r["role"] == role and r["case"] == case
            )
            + 2
            * (
                reference_field_indicator
                if metric == "field_time_rms"
                else reference_energy_indicator
            )
            <= RULE["per_case_noninferiority"]
            for role, case, _ in bkeys
            for metric in ("field_time_rms", "energy_path_rms")
        )

    reasons = []
    if prospective is not True:
        disposition = "RETROSPECTIVE_DEVELOPMENT_RANKING"
        reasons.append(
            "both sources predate the frozen rule or prospective admission is absent"
        )
    elif (
        b["reference_unresolved"]
        or c["reference_unresolved"]
        or reference_field_indicator > RULE["reference_field_indicator_limit"]
        or reference_energy_indicator > RULE["reference_energy_indicator_limit"]
    ):
        disposition = "INDETERMINATE_REFERENCE_RESOLUTION"
        reasons.append(
            "empirical reference/discretization indicators exceed the frozen development resolution budget"
        )
    elif c["failed_mandatory"]:
        disposition = "REJECTED_MANDATORY"
        reasons.extend(c["failed_mandatory"])
    elif b["failed_mandatory"]:
        disposition = "INDETERMINATE_INELIGIBLE_BASELINE"
        reasons.extend(b["failed_mandatory"])
    elif lo > RULE["practical_score_margin"] and dominance(challenger, baseline):
        disposition = "ACCEPTED_DEVELOPMENT_IMPROVEMENT"
    elif hi < -RULE["practical_score_margin"] and dominance(baseline, challenger):
        disposition = "DEVELOPMENT_REGRESSION"
    elif (
        lo >= -RULE["equivalence_score_margin"]
        and hi <= RULE["equivalence_score_margin"]
        and dominance(challenger, baseline)
        and dominance(baseline, challenger)
    ):
        disposition = "DEVELOPMENT_EQUIVALENT"
    elif lo > RULE["practical_score_margin"] or hi < -RULE["practical_score_margin"]:
        disposition = "DEVELOPMENT_TRADEOFF"
        reasons.append("aggregate change conflicts with at least one case or metric")
    else:
        disposition = "INDETERMINATE_REPLICA_OR_EFFECT_RESOLUTION"
        reasons.append(
            "observed replica/reference envelope does not resolve the practical margin; not a tie"
        )
    return DevelopmentDecision(
        rule_digest(),
        disposition,
        b,
        c,
        (lo, hi),
        tuple(reasons),
        disposition == "ACCEPTED_DEVELOPMENT_IMPROVEMENT",
    )
