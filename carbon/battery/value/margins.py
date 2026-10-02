"""SR-2: the margin-aware scoring component, and its pre-registered study.

`docs/development/BATTERY_SCORING_RATIOS_SR2.md` fixes the definition, the
grid, the data, the selection and the outcome before anything here runs.

The leg `m` is the decision contract's cost-weighted margin error. On the two
constraints with a continuous margin (no plating onset, peak temperature),
the model's and the reference's margins are taken in the contract's own band
units. Optimism (the model's margin above the reference's) costs
`false_acceptance` per band, and pessimism costs `missed_opportunity` per
band. `m = 1 / (1 + mean cost)`. The constraints, limits, bands and costs are
the contract's; nothing new is chosen.

    python -m carbon.battery.value.margins --predictions DIR --out DIR
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from . import decision as d
from . import divergence, hypotheses, ratios
from . import panel as pn
from . import scoring as sc

PRIMARY_NAME = "ev2-2026-10-01"
SCHEMA = "carbon.battery.scoring-ratios.sr2.v1"
STEPS = 10
BOOTSTRAP = {"replicates": 10000, "seed": 20261003, "level": 0.95}
PRIMARY = "ev2-2026-10-01"
PRIMARY_CONTRACT = (
    "carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json"
)
CONSTRAINTS = ("no_plating_onset", "peak_temperature")


def _margins(contract, outputs):
    """Signed margins (positive is safe) in the contract's band units."""
    rules = {c["id"]: c for c in contract["constraints"]}
    bands = contract["reference"]["uncertainty"]["bands"]
    q = d.measure(contract, outputs)
    return {
        "no_plating_onset": (
            q["plating_margin_v"] - rules["no_plating_onset"]["threshold"]
        )
        / bands["plating_margin_v"],
        "peak_temperature": (
            rules["peak_temperature"]["threshold"] - q["peak_temperature_c"]
        )
        / bands["peak_temperature_c"],
    }


def margin_component(contract, predictions, case_ids, refs):
    """`m` for one member, or None when any case's prediction is missing."""
    costs = contract["mistake_costs"]
    total, terms = 0.0, 0
    optimism = pessimism = 0.0
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        said, truth = _margins(contract, outputs), _margins(contract, reference)
        for constraint in CONSTRAINTS:
            over = max(0.0, said[constraint] - truth[constraint])
            under = max(0.0, truth[constraint] - said[constraint])
            optimism += over
            pessimism += under
            total += costs["false_acceptance"] * over
            total += costs["missed_opportunity"] * under
            terms += 1
    if terms == 0:
        return None
    return {
        "score": 1.0 / (1.0 + total / terms),
        "terms": terms,
        "mean_optimism_bands": optimism / terms,
        "mean_pessimism_bands": pessimism / terms,
    }


def profiles():
    """The 286 pre-registered profiles: (id, (w_a, w_r, w_g, w_m))."""
    out = []
    for i in range(STEPS + 1):
        for j in range(STEPS + 1 - i):
            for k in range(STEPS + 1 - i - j):
                m = STEPS - i - j - k
                w = (i / STEPS, j / STEPS, k / STEPS, m / STEPS)
                name = "sr2-" + "-".join(
                    leg + ratios._fmt(x) for leg, x in zip("argm", w, strict=True)
                )
                out.append((name, w))
    return out


def score(component, weights):
    """The weighted geometric mean over (a, r, g, m); 0 when ineligible or a
    positive-weight leg is 0; None when a positive-weight leg is unmeasured."""
    if not component.get("eligible"):
        return 0.0
    margin = component.get("margin")
    legs = (*ratios.legs(component), None if margin is None else margin["score"])
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


def verified_predictions(directory, manifest):
    """Every member's predictions, each file checked against the manifest."""
    directory = Path(directory)
    expected = {}
    for line in Path(manifest).read_text().splitlines():
        if line.strip():
            digest, name = line.split()
            expected[name] = digest
    out = {}
    for name, digest in sorted(expected.items()):
        body = (directory / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("prediction file does not match its digest: " + name)
        document = sc.load_predictions(directory / name)
        out[document["member"]] = document["predictions"]
    return out


def content_verified_predictions(directory, results, contract, repository="."):
    """Every member's predictions, each checked by content: its recomputed
    exam components (E, E_important, decision score, eligibility) must equal
    the components the result recorded, exactly. For regenerated files whose
    bytes differ only in wall-clock fields, so their byte digests cannot
    match (OWNER-EV4-REGEN-01)."""
    store, case_ids, _ = sc.scoring_set(repository)
    out = {}
    for path in sorted(Path(directory).glob("*.json.gz")):
        document = sc.load_predictions(path)
        member = document["member"]
        got = sc.components(document["predictions"], case_ids, store, contract)
        want = results["components"][member]
        same = (
            got["eligible"] == want["eligible"]
            and got["E"] == want["E"]
            and got["E_important"] == want["E_important"]
            and (got.get("decision") or {}).get("score")
            == (want.get("decision") or {}).get("score")
        )
        if not same:
            raise ValueError("regenerated predictions differ in content: " + member)
        out[member] = document["predictions"]
    expected = {
        m
        for m, row in results["summary"]["members"].items()
        if row["kind"] != "SYNTHETIC_CONTROL"
    }
    if set(out) != expected:
        raise ValueError("regenerated predictions do not cover the panel")
    return out


def with_margins(results, contract, predictions, repository="."):
    """A copy of `results` whose components carry `m`, and every SR-2
    profile in `rule_scores`."""
    store, case_ids, _ = sc.scoring_set(repository)
    out = copy.deepcopy(results)
    for member, row in results["summary"]["members"].items():
        if row["kind"] == "SYNTHETIC_CONTROL":
            kind = member.removeprefix("control-")
            member_predictions = pn.control_predictions(kind, store.refs)
        else:
            member_predictions = predictions[member]
        out["components"][member]["margin"] = margin_component(
            contract, member_predictions, case_ids, store.refs
        )
        for profile_id, weights in profiles():
            out["rule_scores"][member][profile_id] = score(
                out["components"][member], weights
            )
    return out


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


def paired(results, contract, proposed, deciding=ratios.DECIDING, *, seed=None):
    members = [
        m
        for m in hypotheses.eligible_real(results)
        if ratios._numeric(results["rule_scores"][m].get(proposed))
        and ratios._numeric(results["rule_scores"][m].get(deciding))
    ]
    return hypotheses.paired_bootstrap(
        [results["rule_scores"][m][proposed] for m in members],
        [results["rule_scores"][m][deciding] for m in members],
        hypotheses.loss_matrix(
            results, members, hypotheses.verification_scenarios(contract)
        ),
        replicates=BOOTSTRAP["replicates"],
        seed=BOOTSTRAP["seed"] if seed is None else seed,
        level=BOOTSTRAP["level"],
    )


def outcome(rows, chosen, h1, band):
    if chosen is None:
        return "NO_PROMOTION", {"admissible_profiles": 0}
    checks = {
        "catches_optimist": bool(
            rows[chosen]["optimist"]["below_every_eligible_member"]
        ),
        "fewer_divergence_on_verification": (
            rows[chosen]["divergence"]["verification"]
            < rows[ratios.DECIDING]["divergence"]["verification"]
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


def run(predictions_dir, root=".", *, dataset=None, contract_path=None, verify="bytes"):
    root = Path(root)
    dataset = dataset or PRIMARY
    evidence = root / "docs/development/evidence" / dataset
    results_path = evidence / "results.json"
    contract = json.loads((root / (contract_path or PRIMARY_CONTRACT)).read_text())
    predictions = (
        verified_predictions(predictions_dir, evidence / "predictions.sha256")
        if verify == "bytes"
        else content_verified_predictions(
            predictions_dir, json.loads(results_path.read_text()), contract, root
        )
    )
    results = with_margins(
        json.loads(results_path.read_text()), contract, predictions, root
    )
    rows = table(results)
    chosen, admissible = choose(rows)
    h1 = None if chosen is None else paired(results, contract, chosen)
    band = divergence.tau_noise_band(results)
    decision, checks = outcome(
        rows, chosen, h1 or {}, None if band is None else band["band"]
    )
    leg = paired(results, contract, "sr2-a0-r0-g0-m1", "sr2-a0-r0-g1-m0")
    return {
        "schema": SCHEMA,
        "preregistration": "docs/development/BATTERY_SCORING_RATIOS_SR2.md",
        "results_sha256": {
            dataset: hashlib.sha256(results_path.read_bytes()).hexdigest()
        },
        "profiles_tried": len(profiles()),
        "margin_component": {
            m: results["components"][m]["margin"] for m in sorted(results["components"])
        },
        "admissible": admissible,
        "chosen": chosen,
        "chosen_weights": None if chosen is None else dict(profiles())[chosen],
        "h1_verification": h1,
        "m_against_g_verification": leg,
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
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.margins")
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
