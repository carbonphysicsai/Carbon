"""Audit the score measures recoverable from committed public EV4 results.

This never opens a tuning work directory or the historical private-role
scoring references. Missing member-level measures stay unmeasured.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.battery.value import ratios
from carbon.battery.value import score_proof as proof
from carbon.battery.value import score_tuning as tuning
from scripts.dev.battery.score_proof import level_of, load_members

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "docs/development/evidence/ev4-2026-10-01/results.json"
OUTPUT = (
    ROOT
    / "docs/development/evidence/battery-score-tuning/score-leg-audit-public-v1.json"
)
LEGS = ("a", "r", "p", "m", "n", "g", "q")
GATES = ("feasibility", "plating_fa", "envelope", "near", "error")
OUTCOMES = ("SELECTED_INFEASIBLE", "MISSED_OPPORTUNITY")
MISSING_REASON = (
    "The committed EV4 result has aggregate E, E_important and decision "
    "agreement, but not public member-level predictions, Q3 regret or the "
    "other gate measures. Historical private-role scoring references are "
    "outside this public-only audit."
)


def audit(results: dict, members: dict, *, bootstrap: int = 500) -> dict:
    """Calculate descriptive alignment on one common resolved development mask."""
    if (
        results.get("claims", {}).get("evidence_class")
        != "PUBLIC_SYNTHETIC_DEVELOPMENT"
    ):
        raise ValueError("public_ev4_evidence_required")
    names = sorted(set(results["components"]) & set(results["decisions"]))
    values, mask, outcomes = tuning.decision_values(results, names)
    if not mask:
        raise ValueError("no_common_resolved_development_mask")
    levels = {m: level_of(m, members["levels"]) for m in names}
    roles = members["roles"]
    purposive = set(roles["known_bad"] + roles["adversarial"])
    anchors = {m for m in names if levels[m] is None}
    purposive.update(anchors)
    recipe_of = {m: m.rsplit("-s", 1)[0] if "-s" in m else m for m in names}
    by_member = {}
    for m in names:
        component = results["components"][m]
        a, r, g = ratios.legs(component)
        e = component.get("E") if component.get("eligible") else None
        by_member[m] = {
            "a": a,
            "r": r,
            "g": g,
            "error": e,
            **{
                kind: sum(outcomes[m][s] == kind for s in mask) / len(mask)
                for kind in OUTCOMES
            },
        }

    def pool_report(pool: list[str]) -> dict:
        primary = [m for m in pool if m not in purposive]
        if len(primary) < 3:
            return {"status": "NOT_MEASURABLE", "primary_members": len(primary)}
        _, pool_mask, _ = tuning.decision_values(results, pool)
        # The global mask is deliberately retained so a Level comparison never
        # acquires extra questions merely because its pool is smaller.
        if not set(mask).issubset(pool_mask):
            raise ValueError("inconsistent_common_mask")
        losses = {
            m: [results["decisions"][m][s]["outcome"]["decision_loss"] for s in mask]
            for m in primary
        }
        primary_values = {m: values[m] for m in primary}
        ceiling = proof.value_ceiling(list(losses.values()), n_boot=bootstrap)
        measures = {}
        for key in (*LEGS, *GATES, *OUTCOMES):
            if key not in by_member[primary[0]]:
                measures[key] = {"status": "UNMEASURED", "reason": MISSING_REASON}
                continue
            raw = {m: by_member[m][key] for m in pool}
            if any(raw[m] is None for m in primary):
                measures[key] = {
                    "status": "UNMEASURED",
                    "reason": "At least one primary member lacks this recorded measure.",
                }
                continue
            # All gate and bad-outcome measures are rates/errors: smaller is
            # better. The raw soft legs are scores: larger is better.
            scores = {
                m: (
                    None
                    if value is None
                    else -value if key in (*GATES, *OUTCOMES) else value
                )
                for m, value in raw.items()
            }
            boot = proof.bootstrap(
                scores,
                {},
                losses,
                recipe_of,
                primary,
                n=bootstrap,
            )
            ranked = proof._ranked(scores, pool)
            top_half = set(ranked[: len(ranked) // 2])
            measures[key] = {
                "status": "MEASURED",
                "tau": proof._tau(scores, primary_values, primary),
                "tau_ci95": None if boot is None else boot["joint"],
                "bootstrap": (
                    None
                    if boot is None
                    else {
                        "replicates": boot["replicates"],
                        "undefined_fraction": boot["undefined_fraction"],
                        "recipe_only": boot["recipe_only"],
                        "question_only": boot["question_only"],
                    }
                ),
                "known_bad_top_half": sorted(set(roles["known_bad"]) & top_half),
                "adversarial_top_half": sorted(set(roles["adversarial"]) & top_half),
            }
        return {
            "status": "PARTIAL_PUBLIC_EVIDENCE",
            "members": len(pool),
            "primary_members": len(primary),
            "resolved_questions": len(mask),
            "value_ceiling": ceiling,
            "outcome_shares": {
                kind: sum(by_member[m][kind] for m in primary) / len(primary)
                for kind in OUTCOMES
            },
            "measures": measures,
        }

    pools = {"pooled": names}
    pools.update(
        {
            f"L{level}": sorted(anchors | {m for m in names if levels[m] == level})
            for level in range(5)
        }
    )
    return {
        "schema": "carbon.battery.score-leg-audit-public.v1",
        "source": "committed EV4 public synthetic development results only",
        "scope": "descriptive; no score rule, cutoff or qualification is adopted",
        "common_resolved_development_questions": len(mask),
        "pools": {name: pool_report(pool) for name, pool in pools.items()},
        "missing": {
            "score_proof_postmortem": "not present on main; score_proof methods reused",
            "later_levels": "no public EV4 decision results and score legs for Levels 1-4",
            "member_level_legs": MISSING_REASON,
        },
    }


def main() -> None:
    body = RESULTS.read_bytes()
    report = audit(json.loads(body), load_members())
    report["source_sha256"] = hashlib.sha256(body).hexdigest()
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
