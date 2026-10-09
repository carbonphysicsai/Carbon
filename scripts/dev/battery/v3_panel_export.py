"""Battery v3 solved-panel export (`carbon.design-search.solved-panel-export.v1`,
family `battery-v3`) from the public feasibility study (tiers 1-4).

    PYTHONPATH=<main checkout> python scripts/dev/battery/v3_panel_export.py RUNS OUT.json [--questions N]

Test Lead 2026-10-08: seal the boundary-coverage panel indexed by ambient
band, packet cooling set (x1/x2/x4) only, no new compute. Development panel,
not hidden material.

- **Bands and banks.** One indexed question over the five v3 bands (5, 15,
  25, 35, 40 C). Each band's bank is every solved action at that band with
  cooling x1/x2/x4 and SOC0 0.10, in a fixed sorted order. Nothing is
  dropped after its verdict is known.
- **Questions.** Question 0 is the nominal map: zero margins and the mean of
  the packet's suggested mix. Questions 1..N are requirement variants drawn
  with a fixed seed from the v3 packet's *suggested* law: mix Dirichlet(2, 3,
  8, 5, 2), thermal margin U[0, 2.5] K, plating margin U[0, 2] mV. That law
  is HUMAN_INPUT and is registered here as UNREGISTERED. SOC is fixed at 10 %
  (the only solved support). Every question reuses the same solved panel, so
  all of them are one bank cluster.
- **Settlement (Test Lead ruling (a)).** Each banded limit names
  `settlement_rule` = REFINEMENT_RULE (in the task digest, hence the export
  digest). A refined candidate's rows carry `refined.<quantity>` beside the
  standard value. Under that rule a within-band verdict is settled when both
  rungs lie on one side of the limit and differ by less than the band. Code
  that does not know the rule ignores both and behaves as before.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feasibility02_tier4 as t4

from carbon.design_search import (
    diversity,
    indexed,
    power_accumulation,
    producer_panels,
    tasks,
)

CHALLENGE = "battery-fastcharge-ageing-development-v1"
BANDS = (5.0, 15.0, 25.0, 35.0, 40.0)
COOLING = (1.0, 2.0, 4.0)
MIX_ALPHA = (2.0, 3.0, 8.0, 5.0, 2.0)
REFINEMENT_RULE = "carbon.reference.multi-rung-settlement.v1"
#: rung 3 (mesh 80, rtol 1e-7) for the candidates whose rungs 1-2 straddle a
#: question's limit; settled when the two finest rungs lie on one side and
#: differ by less than the band
RUNG3_DIR = "bfeas-t6r3"
SUPPORT = "battery-feasibility-02-public-panel"
EXPOSURE_LIMIT = 5  # v2-bank E (OWNER-BANK-ARCHITECTURE-01), development value
BATCH = 8
#: the CV hold sits at 4.2 V to solver precision; feasibility02_v2 registers 4.2 V + 1e-6
V_TOLERANCE = 1e-6
QUANTITIES = ("minutes", "charging_t_max_c", "plating_min_v", "v_max_v", "q30_over_q1")
GRAMMAR = {
    "schema": tasks.GRAMMAR_SCHEMA,
    "version": "battery-ambient-map-v3.study-actions.v1",
    "variables": [
        {"name": "c1", "type": "number", "min": 0.25, "max": 2.0, "step": 0.005},
        {"name": "c2", "type": "number", "min": 0.25, "max": 2.0, "step": 0.005},
        {"name": "switch_v", "type": "number", "min": 4.0, "max": 4.15, "step": 0.05},
        {"name": "cooling", "type": "integer", "min": 1, "max": 4, "step": 1},
    ],
    "rules": [
        {"kind": "linear", "coefficients": {"c2": 1, "c1": -1}, "op": "<=", "value": 0}
    ],
}


def solved_with_switch(runs):
    """{(c1, c2, sv, h, T): (standard, refined or None)} at SOC0 0.10."""
    rows = []
    for name in t4.DIRS:
        path = Path(runs) / name / "records.jsonl"
        if path.exists():
            rows += [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    base, refined = {}, {}
    for r in rows:
        if (
            r["status"] != "OK"
            or r["case_id"].startswith("control-")
            or r.get("soc0", t4.SOC0) != t4.SOC0
        ):
            continue
        k = (round(r["c1"], 4), round(r["c2"], 4), round(r.get("switch_voltage_v", 4.0), 4),
             round(r["h_multiplier"], 4), float(r["t_amb_c"]))  # fmt: skip
        (refined if r["case_id"].startswith("refined:") else base)[k] = t4.v2.measures(
            r
        )
    rung3 = {}
    path = Path(runs) / RUNG3_DIR / "records.jsonl"
    if path.exists():
        for x in path.read_text().splitlines():
            r = json.loads(x) if x.strip() else None
            if r and r["status"] == "OK":
                k = (round(r["c1"], 4), round(r["c2"], 4), round(r.get("switch_voltage_v", 4.0), 4),
                     round(r["h_multiplier"], 4), float(r["t_amb_c"]))  # fmt: skip
                rung3[k] = t4.v2.measures(r)
    return {k: (m, refined.get(k), rung3.get(k)) for k, m in base.items()}


def band_bank(have, t):
    keys = sorted(
        k
        for k in have
        if k[4] == t and k[3] in COOLING and have[k][0]["minutes"] is not None
    )
    cands, actions, rows = [], {}, []
    for c1, c2, sv, h, _ in keys:
        cid = f"c1={c1:g},c2={c2:g},sv={sv:g},h{h:g}"
        action = tasks.snap_action(
            GRAMMAR, {"c1": c1, "c2": c2, "switch_v": sv, "cooling": int(h)}
        )
        cands.append(cid)
        actions[cid] = action
        m, ref, r3 = have[(c1, c2, sv, h, t)]
        values = {q: float(m[q]) for q in QUANTITIES}
        if ref is not None:
            values.update(
                {
                    f"refined.{q}": float(ref[q])
                    for q in ("charging_t_max_c", "plating_min_v")
                }
            )
        if r3 is not None:
            values.update(
                {
                    f"rung3.{q}": float(r3[q])
                    for q in ("charging_t_max_c", "plating_min_v")
                }
            )
        rows.append({"candidate": cid, "condition": f"T{t:g}", "values": values})
    return cands, actions, rows


def subtask(case, t, cands, actions, margin_t, margin_p):
    band = f"T{t:g}"
    return tasks.task(
        f"{case}-{band}",
        identity={"challenge": CHALLENGE, "contract_version": "battery-ambient-map-v3 (#846, proposed)",
                  "action_grammar": GRAMMAR, "optimizer": {"class": "exhaustive", "version": "v1"},
                  "query_budget": len(cands), "seed": 0,
                  "observer_version": "battery-feasibility-02 observers (all 30 cycles, per-phase extrema, SOC clock)",
                  "reference_bank": SUPPORT},
        conditions=[{"id": band, "stratum": band}],
        strata={band: {"p": 1, "q": 1, "w": 1}},
        candidates=cands,
        actions=actions,
        objective={"quantity": "minutes", "unit": "min", "sense": "min", "aggregate": "worst"},
        limits=[
            {"quantity": "charging_t_max_c", "unit": "C", "op": "<=", "value": 45.0 - margin_t, "band": t4.T_BAND,
             "settlement_rule": REFINEMENT_RULE},
            {"quantity": "plating_min_v", "unit": "V", "op": ">=", "value": margin_p, "band": t4.P_BAND,
             "settlement_rule": REFINEMENT_RULE},
            {"quantity": "v_max_v", "unit": "V", "op": "<=", "value": 4.2 + V_TOLERANCE},
            {"quantity": "q30_over_q1", "unit": "1", "op": ">=", "value": 0.99},
        ],
    )  # fmt: skip


def build(runs, n_questions=24, seed=846):
    have = solved_with_switch(runs)
    banks = {t: band_bank(have, t) for t in BANDS}
    rng = np.random.default_rng(seed)
    draws = [(np.array(MIX_ALPHA) / sum(MIX_ALPHA), 0.0, 0.0)]
    for _ in range(n_questions):
        draws.append(
            (
                rng.dirichlet(MIX_ALPHA),
                float(rng.uniform(0, 2.5)),
                float(rng.uniform(0, 2.0)) * 1e-3,
            )
        )
    questions = []
    for i, (mix, m_t, m_p) in enumerate(draws):
        case = f"battery-v3-q{i:02d}"
        indices, reference = [], []
        micro = [round(float(w) * 1_000_000) for w in mix]
        micro[-1] = 1_000_000 - sum(micro[:-1])  # exact unit sum after rounding
        for t, w in zip(BANDS, (m / 1_000_000 for m in micro)):
            cands, actions, rows = banks[t]
            indices.append({"index_value": t, "buyer_weight": w,
                            "task": subtask(case, t, cands, actions, round(m_t, 4), round(m_p, 6))})  # fmt: skip
            reference.append({"index_value": t, "panel": rows})
        registered = indexed.indexed_task(
            case, index_axis="ambient_c", indices=indices,
            query_budget=sum(len(banks[t][0]) for t in BANDS),
            value_equivalence={"quantity": "minutes", "unit": "min", "tolerance": 0.5, "rule": indexed.EQUIVALENCE_RULE},
        )  # fmt: skip
        questions.append({"case": case, "support_case": SUPPORT, "task": registered, "reference": reference,
                          "close_call": False, "refinement_demand": False})  # fmt: skip
    cases = [q["case"] for q in questions]
    law = diversity.register_law({
        "schema": diversity.LAW_SCHEMA_V2, "population_status": "UNREGISTERED", "kind": "grid",
        "draw_model": "iid_with_replacement", "batch_size": BATCH,
        "bins": [{"case": c, "q_mass": 1.0 / len(cases)} for c in cases], "mass_l1_error_bound": 0.0,
    })  # fmt: skip
    return producer_panels.seal_export({
        "schema": producer_panels.EXPORT_SCHEMA, "sealed": True, "family": "battery-v3", "challenge_id": CHALLENGE,
        "exposure_unit": power_accumulation.EXPOSURE_UNIT,
        "exposure": [{"case": c, "limit": EXPOSURE_LIMIT, "used": 0} for c in cases],
        "window_sampling": power_accumulation.register_window_sampling(
            case_strata=[{"case": c, "stratum": "all"} for c in cases],
            quotas_by_k=[{"questions_per_batch": k, "quotas": {"all": k}} for k in range(1, BATCH + 1)]),
        "questions": questions, "laws": [law],
    })  # fmt: skip


def main(runs, out, n=24):
    export = build(runs, int(n))
    bank, _grid, _, _ = producer_panels.adapt_export(
        export
    )  # current main must accept it
    states = {}
    for row in bank["cases"]:
        states[row["state"]] = states.get(row["state"], 0) + 1
    text = json.dumps(export, sort_keys=True, separators=(",", ":"))
    Path(out).write_text(text + "\n")
    print(json.dumps({"export_digest": export["export_digest"], "questions": len(export["questions"]),
                      "states_under_current_main": states, "bytes": len(text),
                      "candidates_per_band": {f"T{t:g}": len(export["questions"][0]["task"]["indices"][i]["task"]["candidates"])
                                              for i, t in enumerate(BANDS)}}, indent=1))  # fmt: skip


if __name__ == "__main__":
    main(*sys.argv[1:4])
