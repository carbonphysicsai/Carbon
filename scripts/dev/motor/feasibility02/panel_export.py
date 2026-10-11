"""Motor solved-panel export (`carbon.design-search.solved-panel-export.v1`,
family `motor`) from MOTOR-FEASIBILITY-02 stages 1-3.

    PYTHONPATH=<main checkout> python -m scripts.dev.motor.feasibility02.panel_export --runs S1 S2 S3 --plan S1PLAN --out OUT.json

Test Lead 2026-10-08: export motor's solved panel like battery v3; no new
compute. Development panel, not hidden material.

- **Candidates.** Every public 10p12s design at every skew span its slice
  variants were solved for (0 deg always; 2 and 4 deg where S2 ran), in a
  fixed order. One condition: the frozen precision command J 10, gamma 0
  (cogging from J 0 at the same span).
- **Objective.** The packet's ranking: lowest holding ripple fraction (the
  holding current density is the same frozen command for all, so the next
  key is the bank order).
- **Limits.** Mean >= floor (band 0.10 N m), pk-pk <= allowance (band
  0.02), ripple fraction <= 5 %, cogging <= allowance (band 0.02), with
  `settlement_rule` = the two-rung rule. Rung-2 (S3) values ride as
  `refined.<quantity>`.
- **Questions.** The nominal question (6.0 N m, 0.30, 0.05) and requirement
  variants over holding floor {6.0, 6.25, 6.5, 6.75, 7.0} x pk-pk allowance
  {0.25, 0.30} x cogging {0.03, 0.05}. The packet only illustrates 6 vs 7 N m;
  these values are HUMAN_INPUT and registered UNREGISTERED.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.design_search import diversity, power_accumulation, producer_panels, tasks
from scripts.dev.motor.feasibility02 import stages

CHALLENGE = "motor-precision-joint-development (#758 MOTOR-FEASIBILITY-02 public study)"
RULE = "carbon.reference.two-rung-settlement.v1"
SUPPORT = "motor-feasibility-02-public-panel"
FLOORS, PK, COG = (6.0, 6.25, 6.5, 6.75, 7.0), (0.25, 0.30), (0.03, 0.05)
EXPOSURE_LIMIT, BATCH = 5, 8
GRAMMAR = {
    "schema": tasks.GRAMMAR_SCHEMA,
    "version": "motor-feas02-10p12s-public-designs.v1",
    "variables": [
        {"name": "design", "type": "integer", "min": 0, "max": 23, "step": 1},
        {"name": "skew_deg", "type": "integer", "min": 0, "max": 4, "step": 2},
    ],
    "rules": [],
}


def bank(runs, plan):
    records = stages._records(runs)
    designs = json.loads(Path(plan).read_text())["designs"]
    rows, cands, actions = [], [], {}
    for i in range(len(designs)):
        loaded = stages.skewed_loaded(records, i, 10.0, 0.0)
        cog = stages.skewed_cogging(records, i) or {}
        for span in ("0", "2", "4"):
            if span not in loaded or span not in cog:
                continue
            m = loaded[span]
            cid = f"d{i:02d}-skew{span}"
            values = {"ripple_fraction": m["pk_pk_nm"] / abs(m["mean_nm"]), "mean_nm": m["mean_nm"],
                      "pk_pk_nm": m["pk_pk_nm"], "cogging_nm": cog[span]}  # fmt: skip
            r2 = stages._stack(
                records, i, 10.0, 0.0, float(span), "s3r2", stages.STEP_DEG / 2
            )
            c2 = stages._cog(records, i, float(span), "s3r2", stages.STEP_DEG / 2)
            if r2 is not None and c2 is not None:
                values.update({"refined.mean_nm": r2["mean_nm"], "refined.pk_pk_nm": r2["pk_pk_nm"],
                               "refined.cogging_nm": c2})  # fmt: skip
            cands.append(cid)
            actions[cid] = tasks.snap_action(
                GRAMMAR, {"design": i, "skew_deg": int(span)}
            )
            rows.append({"candidate": cid, "condition": "J10-g0", "values": values})
    return cands, actions, rows


def question(case, cands, actions, floor, pk, cog):
    return tasks.task(
        case,
        identity={"challenge": CHALLENGE, "contract_version": "motor-precision-joint-v2",
                  "action_grammar": GRAMMAR, "optimizer": {"class": "exhaustive", "version": "v1"},
                  "query_budget": len(cands), "seed": 0,
                  "observer_version": "motor-feas02 three-slice stack, 0.25/0.125 deg", "reference_bank": SUPPORT},
        conditions=[{"id": "J10-g0", "stratum": "holding"}],
        strata={"holding": {"p": 1, "q": 1, "w": 1}},
        candidates=cands, actions=actions,
        objective={"quantity": "ripple_fraction", "unit": "1", "sense": "min", "aggregate": "worst"},
        limits=[
            {"quantity": "mean_nm", "unit": "N m", "op": ">=", "value": floor, "band": 0.10, "settlement_rule": RULE},
            {"quantity": "pk_pk_nm", "unit": "N m", "op": "<=", "value": pk, "band": 0.02, "settlement_rule": RULE},
            {"quantity": "ripple_fraction", "unit": "1", "op": "<=", "value": 0.05},
            {"quantity": "cogging_nm", "unit": "N m", "op": "<=", "value": cog, "band": 0.02, "settlement_rule": RULE},
        ],
    )  # fmt: skip


def build(runs, plan):
    cands, actions, rows = bank(runs, plan)
    variants = [(6.0, 0.30, 0.05)] + [
        v for v in itertools.product(FLOORS, PK, COG) if v != (6.0, 0.30, 0.05)
    ]
    questions = []
    for i, (floor, pk, cog) in enumerate(variants):
        case = f"motor-q{i:02d}"
        questions.append({"case": case, "support_case": SUPPORT, "task": question(case, cands, actions, floor, pk, cog),
                          "reference": rows, "close_call": False, "refinement_demand": False})  # fmt: skip
    cases = [q["case"] for q in questions]
    law = diversity.register_law({
        "schema": diversity.LAW_SCHEMA_V2, "population_status": "UNREGISTERED", "kind": "grid",
        "draw_model": "iid_with_replacement", "batch_size": BATCH,
        "bins": [{"case": c, "q_mass": 1.0 / len(cases)} for c in cases], "mass_l1_error_bound": 0.0,
    })  # fmt: skip
    return producer_panels.seal_export({
        "schema": producer_panels.EXPORT_SCHEMA, "sealed": True, "family": "motor", "challenge_id": CHALLENGE,
        "exposure_unit": power_accumulation.EXPOSURE_UNIT,
        "exposure": [{"case": c, "limit": EXPOSURE_LIMIT, "used": 0} for c in cases],
        "window_sampling": power_accumulation.register_window_sampling(
            case_strata=[{"case": c, "stratum": "all"} for c in cases],
            quotas_by_k=[{"questions_per_batch": k, "quotas": {"all": k}} for k in range(1, BATCH + 1)]),
        "questions": questions, "laws": [law],
    })  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(prog="motor panel_export")
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    export = build(args.runs, args.plan)
    bank_, _grid, _, _ = producer_panels.adapt_export(export)
    states = {}
    for row in bank_["cases"]:
        states[row["state"]] = states.get(row["state"], 0) + 1
    args.out.write_text(
        json.dumps(export, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps({"export_digest": export["export_digest"], "questions": len(export["questions"]),
                      "candidates": len(export["questions"][0]["task"]["candidates"]),
                      "states_under_current_main": states}, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
