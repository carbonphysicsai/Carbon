"""f02 menu-v2 solved-panel export (`carbon.design-search.solved-panel-export.v1`,
family `f02`) (EVIDENCE-PRODUCER-STAGES-01).

    python3 f02_export.py ROOT OUT.json

Test Lead 2026-10-11: the f02 reference stays on menu v2 (16 actions x 24
contexts), the contract the TRAIN plan and the f02 kit (#1036) already use.
Development panel, not hidden material.

- **Questions.** One plain question per registered context, as the kit
  states: its condition is the context id, its bank is the 16 menu actions
  in the registry's fixed order. The question law (`f02-round2.json`) is
  HUMAN_INPUT; only the registry's 95 C anchor is used and the context mass
  is uniform (registered UNREGISTERED). No requirement variant is drawn: the
  registry refines only within 1 C of 95 C, so a variant cap would leave
  unsolved rungs.
- **Objective and limit.** Most extra energy (J above the 20 W base), subject
  to the top-die maximum <= 95 C with the registry's 0.5 C band.
- **Rungs and settlement.** A primary within 1 C of 95 C has the registry's
  mesh-2 and dt/2 re-solves; their peaks ride as `mesh2.peak_top_c` and
  `dthalf.peak_top_c`. Per-candidate verdicts come from
  `scripts.dev.evidence_runs.settlement` in `all` mode: every rung on one
  side of 95 C and their spread below the band. A question keeps
  `refinement_demand` true while an in-band candidate stays unsettled.
- **Completeness.** Every primary must have solved; a missing or failed
  primary refuses the export (a reference failure, not a candidate result).
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for entry in (str(HERE), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import f02_menu as menu

from carbon.design_search import diversity, power_accumulation, producer_panels, tasks
from scripts.dev.evidence_runs import settlement

CHALLENGE = "f02"
SUPPORT = "f02-menu-v2-public-panel"
RULE = settlement.rule("f02-menu-v2.all-rungs-agree.v1")
RUNGS = (("mesh2", "mesh2"), ("dt0.5", "dthalf"))  # (case tag, value prefix)
EXPOSURE_LIMIT = 5  # f02-round2 bank recommendation e, development value
BATCH = 8  # f02-round2 k recommendation, development value
GRAMMAR = {
    "schema": tasks.GRAMMAR_SCHEMA,
    "version": "f02-menu-v2.actions.v1",
    "variables": [
        {"name": "peak_w", "type": "number", "min": 80.0, "max": 140.0, "step": 1.0},
        {"name": "on_time_s", "type": "number", "min": 5.0, "max": 20.0, "step": 0.1},
    ],
    "rules": [],
}


class Incomplete(Exception):
    """A registered primary has no solved observation."""


def _bank():
    cands, actions = [], {}
    for peak, d in itertools.product(menu.PEAKS_W, menu.ON_TIMES_S):
        cid = f"p{peak:g}-d{d:g}"
        cands.append(cid)
        actions[cid] = tasks.snap_action(GRAMMAR, {"peak_w": peak, "on_time_s": d})
    return cands, actions


def _task(ctx, cands, actions):
    return tasks.task(
        f"f02-{ctx}",
        identity={"challenge": CHALLENGE, "contract_version": "f02-menu-v2 (#846 registry; Test Lead 2026-10-11)",
                  "action_grammar": GRAMMAR, "optimizer": {"class": "exhaustive", "version": "v1"},
                  "query_budget": len(cands), "seed": 0,
                  "observer_version": "f02_deck.observe (top-die maximum over 120 s; energy above the 20 W base)",
                  "reference_bank": SUPPORT},
        conditions=[{"id": ctx, "stratum": ctx}],
        strata={ctx: {"p": 1, "q": 1, "w": 1}},
        candidates=cands,
        actions=actions,
        objective={"quantity": "extra_energy_j", "unit": "J", "sense": "max", "aggregate": "worst"},
        limits=[{"quantity": "peak_top_c", "unit": "C", "op": "<=", "value": menu.LIMIT, "band": menu.BAND}],
    )  # fmt: skip


def build(root):
    """The sealed export and a summary; refuses an incomplete primary panel."""
    observed = menu._observed(root)
    cands, actions = _bank()
    questions, missing, unsettled = [], [], 0
    for ctx, _ in menu.contexts():
        rows = []
        for peak, d in itertools.product(menu.PEAKS_W, menu.ON_TIMES_S):
            prim = observed.get(menu.case_name(ctx, peak, d))
            if not prim or prim["peak_top_c"] is None:
                missing.append(menu.case_name(ctx, peak, d))
                continue
            values = {
                "peak_top_c": float(prim["peak_top_c"]),
                "extra_energy_j": float(prim["extra_energy_j"]),
            }
            for tag, prefix in RUNGS:
                rung = observed.get(menu.case_name(ctx, peak, d, tag))
                if rung and rung["peak_top_c"] is not None:
                    values[f"{prefix}.peak_top_c"] = float(rung["peak_top_c"])
            rows.append({"candidate": f"p{peak:g}-d{d:g}", "condition": ctx, "values": values})  # fmt: skip
        if missing:
            continue
        task = _task(ctx, cands, actions)
        settled = settlement.verdicts(task, rows, [p for _, p in RUNGS], "all")
        truth = tasks.assess(
            task, {(r["candidate"], ctx): r["values"] for r in rows}, reference=True
        )
        open_ = sum(v["feasible"] is None for v in truth.values()) - len(settled)
        unsettled += open_
        questions.append({"case": f"f02-{ctx}", "support_case": SUPPORT, "task": task, "reference": rows,
                          "close_call": False, "refinement_demand": open_ > 0, "settled": settled})  # fmt: skip
    if missing:
        raise Incomplete(f"{len(missing)} primaries unsolved, first {missing[0]}")
    cases = [q["case"] for q in questions]
    law = diversity.register_law({
        "schema": diversity.LAW_SCHEMA_V2, "population_status": "UNREGISTERED", "kind": "grid",
        "draw_model": "iid_with_replacement", "batch_size": BATCH,
        "bins": [{"case": c, "q_mass": 1.0 / len(cases)} for c in cases], "mass_l1_error_bound": 0.0,
    })  # fmt: skip
    export = producer_panels.seal_export({
        "schema": producer_panels.EXPORT_SCHEMA, "sealed": True, "family": "f02", "challenge_id": CHALLENGE,
        "exposure_unit": power_accumulation.EXPOSURE_UNIT,
        "exposure": [{"case": c, "limit": EXPOSURE_LIMIT, "used": 0} for c in cases],
        "window_sampling": power_accumulation.register_window_sampling(
            case_strata=[{"case": c, "stratum": "all"} for c in cases],
            quotas_by_k=[{"questions_per_batch": k, "quotas": {"all": k}} for k in range(1, BATCH + 1)]),
        "questions": questions, "laws": [law], "refinement_rule": RULE,
    })  # fmt: skip
    bank, _grid, _, _ = producer_panels.adapt_export(export)  # main must accept it
    states = {}
    for row in bank["cases"]:
        states[row["state"]] = states.get(row["state"], 0) + 1
    return export, {
        "questions": len(questions),
        "states": states,
        "unsettled_in_band": unsettled,
    }


def main(argv=None):
    root, out = (argv or sys.argv[1:])[:2]
    export, summary = build(root)
    Path(out).write_text(
        json.dumps(export, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps({"export_digest": export["export_digest"], **summary}))


if __name__ == "__main__":
    main()
