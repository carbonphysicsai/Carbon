"""EV5's admission conditions, from its committed evidence.

    python -m scripts.dev.battery.ev5_conditions

Writes `docs/development/evidence/ev5-2026-10-03/conditions.json`, a
`carbon.admission-conditions.v1` report that the battery Level 0 campaign
controller's operator records with `CampaignController.consume_conditions`.
Every condition is bound by SHA-256 to the evidence files it reads. This
script never writes to a campaign store.

- SCORE_VALUE_DIVERGENCE `ADVERSARIAL_TOP_HALF`: each Track A construction
  that selects a reference-infeasible protocol yet ranks in the top half
  under the deciding rule plus the gate (the EV5 adversarial-score verdict).
- SCORE_VALUE_DIVERGENCE `MODE_X_VERIFIED_VIOLATION`: each Mode X member with
  a reference-verified violation that ranks in the top half (one condition
  per member, its findings counted by band).
- GATE_ANOMALY `GATE_DOES_NOT_SEPARATE_DECISION_VALUE`: H2 does not hold.
- OTHER_SIGNAL `KNOWN_BLIND_SPOT_UNCAUGHT`: H3's sign-error control
  is caught by no rule (only the descriptive measurement separates it).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = "docs/development/evidence/ev5-2026-10-03"
REVIEW = (
    "the newest battery expansion record "
    "(carbon/reconstruction/expansions/battery-fastcharge-ageing-development-v1/)"
)
FILES = ("analysis.json", "results.json", "optimizer/findings.json", "run-record.json")


def _sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _condition(condition, member, kind, detail, basis):
    return {
        "schema": "carbon.admission-condition.v1",
        "condition": condition,
        "member": member,
        "kind": kind,
        "detail": detail,
        "basis": basis,
        "review_state": REVIEW,
    }


def report(root=ROOT):
    evidence = Path(root) / EVIDENCE
    analysis = json.loads((evidence / "analysis.json").read_text())
    adversarial = analysis["adversarial_score"]
    conditions = []
    mode_x = {}
    for row in adversarial["constructions"]:
        if not row["verdict"]["top_half"]:
            continue
        if row["source"] == "track_a":
            conditions.append(
                _condition(
                    "SCORE_VALUE_DIVERGENCE",
                    row["member"],
                    "ADVERSARIAL_TOP_HALF",
                    {
                        "infeasible_scenarios": row["scenarios"],
                        "rank": row["verdict"]["rank"],
                        "of": row["verdict"]["of"],
                        "gate": row["gate"],
                    },
                    "analysis.json adversarial_score (deciding rule plus the gate, "
                    "failures last; 2 x rank <= n)",
                )
            )
        else:
            entry = mode_x.setdefault(
                row["member"],
                {
                    "rank": row["verdict"]["rank"],
                    "of": row["verdict"]["of"],
                    "gate": row["gate"],
                    "in_band": 0,
                    "out_of_band": 0,
                    "violated": set(),
                },
            )
            entry[
                "in_band" if row["source"].endswith("/in_band") else "out_of_band"
            ] += 1
            entry["violated"].update(row.get("violated") or [])
    for member, entry in sorted(mode_x.items()):
        entry["violated"] = sorted(entry["violated"])
        conditions.append(
            _condition(
                "SCORE_VALUE_DIVERGENCE",
                member,
                "MODE_X_VERIFIED_VIOLATION",
                entry,
                "analysis.json adversarial_score; optimizer/findings.json",
            )
        )
    h2 = analysis["value"]["H2"]
    if h2["outcome"] != "HOLDS":
        conditions.append(
            _condition(
                "GATE_ANOMALY",
                "near-limit optimism gate (2.0 bands)",
                "GATE_DOES_NOT_SEPARATE_DECISION_VALUE",
                {
                    "outcome": h2["outcome"],
                    "controls_hold": h2["controls_hold"],
                    "real_members_failed": h2["real_members_failed"],
                    "real_members": h2["real_members"],
                    "difference": h2["group_difference"]["difference"],
                    "interval": h2["group_difference"]["interval"],
                },
                "analysis.json value.H2",
            )
        )
    h3 = analysis["value"]["H3"]
    if not h3["caught"]["by_rule"] and not h3["caught"]["by_gate"]:
        conditions.append(
            _condition(
                "OTHER_SIGNAL",
                "control-localized_sign_error",
                "KNOWN_BLIND_SPOT_UNCAUGHT",
                {
                    "near_limit_false_acceptance": h3["sign_error_control_rate"],
                    "separation_by_measurement": h3["separation"],
                    "ranks": h3["sign_error_rank"],
                },
                "analysis.json value.H3",
            )
        )
    return {
        "schema": "carbon.admission-conditions.v1",
        "results": f"{EVIDENCE}/analysis.json",
        "deciding_rule": "control-exam-v1 (testnet rule), plus the near-limit gate",
        "evidence_sha256": {name: _sha(evidence / name) for name in FILES},
        "conditions": conditions,
        "effect": "findings block LOCK, not exploration",
        "recording": "by the campaign controller's operator via CampaignController.consume_conditions",
        "scope": (
            "public synthetic DEVELOPMENT evidence (EV5, run at c9c27a63); no "
            "qualification claim; not mainnet; the sealed confirmation report "
            "is not an input"
        ),
    }


def main():
    from carbon.challenge_readiness.admission import CONDITIONS

    out = ROOT / EVIDENCE / "conditions.json"
    document = report()
    # Only the admission vocabulary; the specific label is the `kind` subtype.
    unknown = sorted({c["condition"] for c in document["conditions"]} - CONDITIONS)
    if unknown:
        raise SystemExit(f"refusing: conditions outside the vocabulary: {unknown}")
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "written": str(out.relative_to(ROOT)),
                "conditions": len(document["conditions"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
