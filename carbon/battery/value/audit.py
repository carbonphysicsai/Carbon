"""Read-only diagnostic of retained EV1/EV2 evidence, without rescoring it.

Usage: python -m carbon.battery.value.audit --results results.json [--out audit.json]
No qualification threshold, independent-family claim, or acceptance is inferred.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median

from .decision import kendall_tau_b


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def audit(results):
    if results.get("schema") != "carbon.engineering-value-results.v1":
        raise ValueError("unsupported_ev_result")
    members = results["summary"]["members"]
    panel = sorted(
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is True
    )
    excluded = sorted(
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is not True
    )
    scheduled = sorted(
        s for s, row in results["references"].items() if row["split"] == "verification"
    )
    coverage = {}
    losses = {}
    for member in panel:
        resolved = {}
        unsafe = 0
        for scenario in scheduled:
            row = results["decisions"][member].get(scenario)
            if row is None:
                continue
            outcome = row["outcome"]
            loss = outcome["decision_loss"]
            if loss is not None and (not _finite(loss) or loss < 0):
                raise ValueError("invalid_decision_loss")
            if loss is not None:
                resolved[scenario] = loss
                unsafe += outcome["kind"] == "SELECTED_INFEASIBLE"
        coverage[member] = {
            "scheduled": len(scheduled),
            "resolved": len(resolved),
            "unresolved_or_missing": len(scheduled) - len(resolved),
            "unsafe_selections": unsafe,
            "unsafe_fraction_of_resolved": unsafe / len(resolved) if resolved else None,
        }
        losses[member] = resolved
    common = (
        sorted(set.intersection(*(set(v) for v in losses.values()))) if losses else []
    )
    complete = bool(panel and scheduled) and all(
        len(v) == len(scheduled) for v in losses.values()
    )
    rules = sorted(results["comparison"])
    comparisons = {}
    for rule in rules:
        scores = {m: results["rule_scores"][m][rule] for m in panel}
        measurable = bool(panel) and all(_finite(v) for v in scores.values())
        mean_losses = (
            {m: sum(losses[m][s] for s in common) / len(common) for m in panel}
            if common
            else {}
        )
        pairs = (
            [(scores[m], -mean_losses[m]) for m in panel]
            if measurable and common
            else []
        )
        concordant = discordant = tied = 0
        for i, (score, quality) in enumerate(pairs):
            for other_score, other_quality in pairs[i + 1 :]:
                product = (score - other_score) * (quality - other_quality)
                concordant += product > 0
                discordant += product < 0
                tied += product == 0
        groups = {}
        for member in panel:
            # Same recipe/seed grouping as the historical EV report, not a
            # scientific assertion that these are independent model families.
            groups.setdefault(member.rsplit("-s", 1)[0], []).append(member)
        recipe_pairs = (
            [
                (
                    median(scores[m] for m in group),
                    -median(mean_losses[m] for m in group),
                )
                for group in groups.values()
            ]
            if pairs
            else []
        )
        comparisons[rule] = {
            "eligible_member_tau_on_common_cases": (
                kendall_tau_b([p[0] for p in pairs], [p[1] for p in pairs])
                if len(pairs) >= 3
                else None
            ),
            "recipe_median_tau_on_common_cases": (
                kendall_tau_b(
                    [p[0] for p in recipe_pairs], [p[1] for p in recipe_pairs]
                )
                if len(recipe_pairs) >= 3
                else None
            ),
            "recipe_groups": len(groups),
            "concordant_pairs": concordant,
            "discordant_pairs": discordant,
            "tied_pairs": tied,
            "full_verification_coverage": complete,
        }
    limits = [
        "Retrospective diagnostic only; no untouched confirmation or acceptance.",
        "Controls are excluded from real-model correlation; they require a separate attack report.",
        "Recipe grouping is not independent-family evidence; seed replicas are not independent methods.",
        "No confidence interval or practical-effect threshold is established by this audit.",
        "Common-case statistics omit unresolved outcomes; omission can bias the ranking.",
        "Existing summary correlations may include gate-ineligible models; this audit excludes them.",
    ]
    if not complete:
        limits.append(
            "Incomplete verification coverage requires a preregistered sensitivity analysis."
        )
    if not any(
        r["status_counts"].get("FEASIBLE", 0)
        for r in results["references"].values()
        if r["split"] == "verification"
    ):
        limits.append(
            "No verification scenario has a feasible candidate; useful-design regret is untested."
        )
    return {
        "schema": "carbon.engineering-value-audit.v1",
        "contract_digest": results["contract_digest"],
        "evidence_class": "RETROSPECTIVE_DEVELOPMENT_DIAGNOSTIC",
        "admission_status": "NOT_ESTABLISHED",
        "eligible_reconstructed_members": panel,
        "excluded_ineligible_members": excluded,
        "verification_scenarios": len(scheduled),
        "common_resolved_scenarios": len(common),
        "coverage": coverage,
        "rules": comparisons,
        "limitations": limits,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = audit(json.loads(args.results.read_bytes()))
    body = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(body)
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
