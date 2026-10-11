"""Build the readiness Q1 panel for battery from the committed graphite-run5 evidence.

    python scripts/dev/battery/readiness_q1_panel.py --out PANEL.json
    python -m carbon.challenge_pipeline.readiness.q1 build \\
        --challenge battery-fastcharge-ageing-development-v1 --level 0 \\
        --panel PANEL.json \\
        --out carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/q1_report.json

The mapping is `carbon/challenge_pipeline/readiness/Q1_PANELS.md` (battery section,
corrected by Data Collection and matching `graphite_run5_analysis.py`). It reads only
committed files under `docs/development/evidence/graphite-run5-q1/`; it invents no value,
runs nothing, and touches no hidden material.

- members: the analysis's one-seed-per-recipe panel (`first_seed`);
- `score` = minus `cpu_practice_score` (the practice score is lower-is-better);
- `value` = `development_decision_loss`; `eligible` = the results' eligibility and a score;
- `kind` = GRAPHITE_RECONSTRUCTED (q1-report members carry none);
- `decision_outcome` = per development scenario on the common resolved mask:
  `selected` when set; ABSTAIN for CORRECT_ABSTENTION, MISSED_OPPORTUNITY or
  ABSTENTION_UNRESOLVED; MISSING_OUTPUT for MODEL_OUTPUT_MISSING (not an abstention);
- `aliases` from `aliasing.json`;
- reference: EV4_REFERENCE, the committed EV4 decision references.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
EVIDENCE = REPOSITORY / "docs/development/evidence/graphite-run5-q1"
REFERENCE = "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
ABSTAIN_KINDS = ("CORRECT_ABSTENTION", "MISSED_OPPORTUNITY", "ABSTENTION_UNRESOLVED")


def outcome(entry):
    selected = entry["outcome"]["selected"]
    if selected is not None:
        return selected
    kind = entry["outcome"]["kind"]
    if kind in ABSTAIN_KINDS:
        return "ABSTAIN"
    if kind == "MODEL_OUTPUT_MISSING":
        return "MISSING_OUTPUT"
    raise ValueError(f"unmapped decision kind {kind}")


def build(evidence=EVIDENCE):
    report = json.loads((evidence / "q1-report.json").read_text(encoding="utf-8"))
    results = json.loads((evidence / "results.json").read_text(encoding="utf-8"))
    aliasing = json.loads((evidence / "aliasing.json").read_text(encoding="utf-8"))
    excluded = set(report["mask"]["excluded"])
    members = {}
    for name, row in sorted(report["members"].items()):
        if not row.get("first_seed"):
            continue
        scenarios = {
            scenario: outcome(entry)
            for scenario, entry in sorted(results["decisions"][name].items())
            if entry["split"] == "development" and scenario not in excluded
        }
        score = row["cpu_practice_score"]
        members[name] = {
            "score": None if score is None else -float(score),
            "value": float(row["development_decision_loss"]),
            "eligible": bool(row["eligible"]) and score is not None,
            "recipe": row["recipe"],
            "kind": "GRAPHITE_RECONSTRUCTED",
            "decision_outcome": scenarios,
        }
    panel_members = set(members)
    aliases = [
        {"alias": a["alias"], "target": a["target"]}
        for a in aliasing
        if a["alias"] in panel_members and a["target"] in panel_members
    ]
    return {
        "reference": {"provenance": "EV4_REFERENCE", "ref": REFERENCE},
        "decision_study": "graphite-run5-q1 (results.json, q1-report.json); common resolved mask "
        f"{report['mask']['common_resolved']} of {report['mask']['development_scenarios']} development scenarios",
        "aliases": aliases,
        "members": members,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    Path(args.out).write_text(
        json.dumps(build(), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
