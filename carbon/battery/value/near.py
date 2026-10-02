"""SR-3: margin error near the decision boundary (pre-registered).

`docs/development/BATTERY_SCORING_RATIOS_SR3.md` fixes everything before this
runs. The leg `n` is SR-2's cost-weighted margin error
(`margins.margin_component`), averaged only over the cases whose reference is
in the published important region (`domain.is_important`, OWNER-SR3-NEAR-01).
Nothing else differs from SR-2.

    python -m carbon.battery.value.near --predictions DIR --out DIR
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from ..domain import is_important
from . import divergence, margins, ratios
from . import panel as pn
from . import scoring as sc

PRIMARY_NAME = "ev2-2026-10-01"
SCHEMA = "carbon.battery.scoring-ratios.sr3.v1"
STEPS = 10
SEED = 20261004


def near_cases(store, case_ids):
    """The scoring cases whose reference is in the published important region."""
    return [
        c
        for c in case_ids
        if store.refs[c].get("outputs") is not None and is_important(store.refs[c])
    ]


def profiles():
    """The 286 pre-registered profiles: (id, (w_a, w_r, w_g, w_n))."""
    return [
        ("sr3-" + name.removeprefix("sr2-").replace("-m", "-n"), w)
        for name, w in margins.profiles()
    ]


def score(component, weights):
    """The weighted geometric mean over (a, r, g, n)."""
    if not component.get("eligible"):
        return 0.0
    near = component.get("near")
    legs = (*ratios.legs(component), None if near is None else near["score"])
    terms = []
    for weight, leg in zip(weights, legs, strict=True):
        if weight == 0:
            continue
        if leg is None:
            return None
        if leg == 0.0:
            return 0.0
        terms.append(weight * math.log(leg))
    return math.exp(math.fsum(terms))


def with_near(results, contract, predictions, repository="."):
    store, case_ids, _ = sc.scoring_set(repository)
    near = near_cases(store, case_ids)
    out = copy.deepcopy(results)
    for member, row in results["summary"]["members"].items():
        if row["kind"] == "SYNTHETIC_CONTROL":
            member_predictions = pn.control_predictions(
                member.removeprefix("control-"), store.refs
            )
        else:
            member_predictions = predictions[member]
        component = out["components"][member]
        component["near"] = margins.margin_component(
            contract, member_predictions, near, store.refs
        )
        component["margin"] = margins.margin_component(
            contract, member_predictions, case_ids, store.refs
        )
        for profile_id, weights in profiles():
            out["rule_scores"][member][profile_id] = score(component, weights)
        out["rule_scores"][member]["sr2-a0-r0-g0-m1"] = margins.score(
            component, (0.0, 0.0, 0.0, 1.0)
        )
    return out, len(near), len(case_ids)


def table(results):
    rules = [ratios.DECIDING] + [p for p, _ in profiles()]
    return {
        rule: {
            "tau_development": ratios.tau(results, rule, "development"),
            "tau_verification": ratios.tau(results, rule, "verification"),
            "optimist": ratios.optimist_check(results, rule),
            "divergence": ratios.divergence_counts(results, rule),
        }
        for rule in rules
    }


def choose(rows):
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


def run(predictions_dir, root=".", *, dataset=None, contract_path=None, verify="bytes"):
    root = Path(root)
    dataset = dataset or margins.PRIMARY
    evidence = root / "docs/development/evidence" / dataset
    results_path = evidence / "results.json"
    contract = json.loads(
        (root / (contract_path or margins.PRIMARY_CONTRACT)).read_text()
    )
    predictions = (
        margins.verified_predictions(predictions_dir, evidence / "predictions.sha256")
        if verify == "bytes"
        else margins.content_verified_predictions(
            predictions_dir, json.loads(results_path.read_text()), contract, root
        )
    )
    results, n_near, n_all = with_near(
        json.loads(results_path.read_text()), contract, predictions, root
    )
    rows = table(results)
    chosen, admissible = choose(rows)
    h1 = (
        None if chosen is None else margins.paired(results, contract, chosen, seed=SEED)
    )
    band = divergence.tau_noise_band(results)
    decision, checks = margins.outcome(
        rows, chosen, h1 or {}, None if band is None else band["band"]
    )
    n_only, g_only = "sr3-a0-r0-g0-n1", "sr3-a0-r0-g1-n0"
    return {
        "schema": SCHEMA,
        "preregistration": "docs/development/BATTERY_SCORING_RATIOS_SR3.md",
        "results_sha256": {
            dataset: hashlib.sha256(results_path.read_bytes()).hexdigest()
        },
        "near_cases": n_near,
        "scoring_cases": n_all,
        "profiles_tried": len(profiles()),
        "near_component": {
            m: results["components"][m]["near"] for m in sorted(results["components"])
        },
        "admissible": admissible,
        "chosen": chosen,
        "chosen_weights": None if chosen is None else dict(profiles())[chosen],
        "h1_verification": h1,
        "n_against_g_verification": margins.paired(
            results, contract, n_only, g_only, seed=SEED
        ),
        "n_against_m_verification": margins.paired(
            results, contract, n_only, "sr2-a0-r0-g0-m1", seed=SEED
        ),
        "tau_noise_band_verification": band,
        "outcome": decision,
        "outcome_checks": checks,
        "dataset": dataset,
        "prediction_verification": verify,
        "ev2" if dataset == "ev2-2026-10-01" else "rows": rows,
        "ev4_replication": (
            "NOT_RUN: predictions not retained; regenerate and verify first"
            if dataset == PRIMARY_NAME
            else "THIS_RUN"
        ),
        "claims": {
            "testnet_rule_changed": False,
            "confirmation": False,
            "optimal_weight_ratio_claimed": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.near")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dataset", help="evidence directory name (default EV2)")
    parser.add_argument("--contract", help="decision contract path (default EV2's)")
    parser.add_argument("--verify", choices=("bytes", "content"), default="bytes")
    args = parser.parse_args(argv)
    report = run(
        args.predictions,
        ".",
        dataset=args.dataset,
        contract_path=args.contract,
        verify=args.verify,
    )
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
