"""SR-1: battery scoring ratios on retained EV results (pre-registered).

`docs/development/BATTERY_SCORING_RATIOS_SR1.md` fixes the grid, the
admissibility condition, the selection and the outcome before anything here
runs. It is offline: it re-weights the three components every EV2 and EV4
member already has, with no reference solve, fit or spend.

- `a`, accuracy: `1/(1+E)`;
- `r`, important-region robustness: `1/(1+E_important)`;
- `g`, decision agreement: the decision contract's own component.

Gates stay mandatory, so an ineligible member scores 0 under every profile.
The deciding rule, `control-exam-v1`, is the comparator. A selected profile is
a proposal and changes no testnet rule (OWNER-TRACK-A-L0-02 item 7).

    python -m carbon.battery.value.ratios --out DIR
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from . import divergence, hypotheses
from .decision import kendall_tau_b

SCHEMA = "carbon.battery.scoring-ratios.sr1.v1"
DECIDING = "control-exam-v1"
OPTIMIST = "control-boundary_optimist"
STEPS = 10  # weights in steps of 0.1
BOOTSTRAP = {"replicates": 10000, "seed": 20261002, "level": 0.95}
PRIMARY = "ev4-2026-10-01"
REPLICATION = "ev2-2026-10-01"
EV4_CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"


def profiles():
    """The 66 pre-registered profiles: (id, (w_a, w_r, w_g))."""
    out = []
    for i in range(STEPS + 1):
        for j in range(STEPS + 1 - i):
            k = STEPS - i - j
            w = (i / STEPS, j / STEPS, k / STEPS)
            out.append((f"sr-a{_fmt(w[0])}-r{_fmt(w[1])}-g{_fmt(w[2])}", w))
    return out


def _fmt(value):
    return "0" if value == 0 else ("1" if value == 1 else f"{value:.1f}")


def legs(component):
    """`(a, r, g)` for one member, or None where a leg is not measured."""
    e, ei = component.get("E"), component.get("E_important")
    decision = component.get("decision")
    return (
        None if e is None else 1.0 / (1.0 + e),
        None if ei is None else 1.0 / (1.0 + ei),
        None if decision is None else decision["score"],
    )


def score(component, weights):
    """A profile's score: Carbon's weight-profile combination
    (`carbon.scoring.weight_profile.combine`), a weighted geometric mean
    `exp(sum(w * log(leg)))` over positive-weight legs, 0 when any of them is
    0. Extended to three legs because the registered profile type has one
    robustness slot. 0 when ineligible (gates are never rescued); None when a
    leg with positive weight is not measured."""
    if not component.get("eligible"):
        return 0.0
    terms = []
    for weight, leg in zip(weights, legs(component), strict=True):
        if weight == 0:
            continue
        if leg is None:
            return None
        if leg == 0.0:
            return 0.0
        terms.append(weight * math.log(leg))
    return math.exp(math.fsum(terms))


def rescored(results):
    """A copy of `results` with every SR-1 profile added to `rule_scores`."""
    out = copy.deepcopy(results)
    for member, component in results["components"].items():
        for profile_id, weights in profiles():
            out["rule_scores"][member][profile_id] = score(component, weights)
    return out


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def tau(results, rule, split):
    """Kendall τ-b between the rule's score and negative decision loss over
    eligible reconstructed members; None when not computable."""
    members = results["summary"]["members"]
    pairs = []
    for member in hypotheses.eligible_real(results):
        s, loss = (
            results["rule_scores"][member].get(rule),
            members[member]["loss_" + split],
        )
        if not _numeric(s) or loss is None:
            continue
        pairs.append((s, -loss))
    if len(pairs) < 3:
        return None
    return kendall_tau_b([p[0] for p in pairs], [p[1] for p in pairs])


def optimist_check(results, rule):
    """Is the boundary optimist scored below every eligible real member?"""
    mine = results["rule_scores"].get(OPTIMIST, {}).get(rule)
    others = [
        results["rule_scores"][m].get(rule) for m in hypotheses.eligible_real(results)
    ]
    if not _numeric(mine) or not others or not all(_numeric(v) for v in others):
        return None
    return {
        "below_every_eligible_member": all(mine < v for v in others),
        "members_at_or_below_it": sum(1 for v in others if v <= mine),
        "eligible_members": len(others),
    }


def divergence_counts(results, rule):
    counts = {split: 0 for split in divergence.SPLITS}
    for condition in divergence.conditions(results, rule=rule):
        if condition["condition"] == "SCORE_VALUE_DIVERGENCE":
            counts[condition["split"]] += 1
    return counts


def table(results):
    """Every profile (and the deciding rule) on one result."""
    rules = [DECIDING] + [p for p, _ in profiles()]
    return {
        rule: {
            "tau_development": tau(results, rule, "development"),
            "tau_verification": tau(results, rule, "verification"),
            "optimist": optimist_check(results, rule),
            "divergence": divergence_counts(results, rule),
        }
        for rule in rules
    }


def choose(rows):
    """The pre-registered selection on EV4 development (SR-1 §4)."""
    weights = dict(profiles())
    admissible = [
        p
        for p in weights
        if rows[p]["optimist"]
        and rows[p]["optimist"]["below_every_eligible_member"]
        and rows[p]["tau_development"] is not None
    ]
    if not admissible:
        return None, admissible
    chosen = max(
        admissible,
        key=lambda p: (
            rows[p]["tau_development"],
            -rows[p]["divergence"]["development"],
            weights[p][0],
        ),
    )
    return chosen, admissible


def paired(results, contract, rule):
    """Δτ (rule − deciding) on verification with its bootstrap interval."""
    members = [
        m
        for m in hypotheses.eligible_real(results)
        if _numeric(results["rule_scores"][m].get(rule))
        and _numeric(results["rule_scores"][m].get(DECIDING))
    ]
    return hypotheses.paired_bootstrap(
        [results["rule_scores"][m][rule] for m in members],
        [results["rule_scores"][m][DECIDING] for m in members],
        hypotheses.loss_matrix(
            results, members, hypotheses.verification_scenarios(contract)
        ),
        replicates=BOOTSTRAP["replicates"],
        seed=BOOTSTRAP["seed"],
        level=BOOTSTRAP["level"],
    )


def outcome(primary_rows, replication_rows, chosen, h1, band):
    """PROMOTE_TO_CONFIRMATION only if all four pre-registered conditions hold."""
    if chosen is None:
        return "NO_PROMOTION", {"admissible_profiles": 0}
    rep = replication_rows[chosen]["optimist"]
    checks = {
        "catches_optimist_on_ev4_and_ev2": bool(
            primary_rows[chosen]["optimist"]["below_every_eligible_member"]
            and rep
            and rep["below_every_eligible_member"]
        ),
        "fewer_divergence_on_ev4_verification": (
            primary_rows[chosen]["divergence"]["verification"]
            < primary_rows[DECIDING]["divergence"]["verification"]
        ),
        "delta_tau_point_at_least_zero": (
            h1["delta_tau"] is not None and h1["delta_tau"] >= 0
        ),
        "interval_low_above_minus_band": (
            h1["interval"][0] is not None
            and band is not None
            and h1["interval"][0] > -band
        ),
    }
    return (
        "PROMOTE_TO_CONFIRMATION" if all(checks.values()) else "NO_PROMOTION"
    ), checks


def run(root="."):
    root = Path(root)
    loaded, digests = {}, {}
    for name in (PRIMARY, REPLICATION):
        path = root / "docs/development/evidence" / name / "results.json"
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        loaded[name] = rescored(json.loads(path.read_text()))
    contract = json.loads((root / EV4_CONTRACT).read_text())
    primary, replication = table(loaded[PRIMARY]), table(loaded[REPLICATION])
    chosen, admissible = choose(primary)
    h1 = None if chosen is None else paired(loaded[PRIMARY], contract, chosen)
    band = divergence.tau_noise_band(loaded[PRIMARY])
    decision, checks = outcome(
        primary, replication, chosen, h1 or {}, None if band is None else band["band"]
    )
    return {
        "schema": SCHEMA,
        "preregistration": "docs/development/BATTERY_SCORING_RATIOS_SR1.md",
        "results_sha256": digests,
        "profiles_tried": len(profiles()),
        "admissible_on_ev4": admissible,
        "chosen": chosen,
        "chosen_weights": None if chosen is None else dict(profiles())[chosen],
        "h1_ev4_verification": h1,
        "tau_noise_band_ev4_verification": band,
        "outcome": decision,
        "outcome_checks": checks,
        "ev4": primary,
        "ev2": replication,
        "claims": {
            "testnet_rule_changed": False,
            "confirmation": False,
            "optimal_weight_ratio_claimed": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.ratios")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(".")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(report, sort_keys=True, indent=1))
    print(
        json.dumps(
            {k: report[k] for k in ("chosen", "outcome", "outcome_checks")},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
