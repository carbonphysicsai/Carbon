"""Battery's A, D and gates for the shared physical dual producer.

DEVELOPMENT only, exposed development bank: never a hidden-exam or paying
claim. The values are the Carbon Validator's registered Battery A/D packet
(BATTERY_DUAL_PACKET_20261020), every one from an existing owner record:

- the score is registry v5's ``G-FEAS/A-Q>`` (OWNER-BATTERY-SCORE-CANDIDATE-01),
  combined as the other dual packs combine theirs (0.5 A + 0.5 D,
  OWNER-EVALUATION-FOCUS; the registry's own geometric mean is not used);
- A is the registry's leg ``a``: ``ratios.legs`` over ``scoring.components``;
- D is the registry's leg ``q``: 1 / (1 + mean Q3 decision regret) over EV4's
  development scenarios, under the quiz's registered UNRESOLVED rule;
- gates: G-FEAS (``false_feasible_rate`` above the registry's cutoff fails)
  with battery-plating-ref-v2 plating truth (OWNER-BATTERY-GATE-PLATING-V2-01),
  the existing exam gates (physics laws B1-B3), B15 and the exact paired
  repeat.

Every measure calls the pinned battery value functions; nothing is
reimplemented except the two compositions the pinned modules lack (the v2
truth in ``false_feasible_rate`` and in ``q3_judge``), which swap only the
reference assessment for ``gate_plating_v2``'s. A PRACTICE case whose v2
plating label is UNRESOLVED is removed from A and G-FEAS as a whole case and
recorded in the mask; a reference failure is never a candidate failure.

D and B15 read Battery 2.0's decision and probe rows (the EV4 development
grid and the approved public B15 plan, both pinned in the definition); a row
without a reference is never truth, and no feasible scenario refuses.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

DEFINITION_SCHEMA = "carbon.scoring.battery-dual-definition.v1"
METHOD = "registry-v5-g-feas-a-q-plating-v2"
GATES = ("exam_gates", "g_feas", "physics_b15", "paired_repeat")
_REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRY = (
    "docs/development/evidence/battery-score-tuning/registry-v5.json",
    "sha256:70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277",
)
CANDIDATE = "G-FEAS/A-Q>"
UNRESOLVED_REASON = "plating_reference_unresolved"


class BatteryMeasurementRefused(ValueError):
    """The bank, definition or predictions cannot support the measurement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise BatteryMeasurementRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def registry_gate():
    """The registered candidate's G-FEAS gate, read from the pinned registry:
    ``{"measure", "cutoff", "comparison"}``."""
    raw = (_REPOSITORY / REGISTRY[0]).read_bytes()
    _require("sha256:" + hashlib.sha256(raw).hexdigest() == REGISTRY[1], "registry")
    entries = [c for c in json.loads(raw)["candidates"] if c.get("id") == CANDIDATE]
    _require(
        len(entries) == 1
        and entries[0].get("measure") == "feasibility"
        and entries[0].get("comparison") == "exceeds"
        and entries[0].get("base") == "A-Q"
        and type(entries[0].get("grid")) is list
        and len(entries[0]["grid"]) == 1
        and _number(entries[0]["grid"][0]),
        "registry_candidate",
    )
    return {
        "measure": "feasibility",
        "cutoff": entries[0]["grid"][0],
        "comparison": "exceeds",
    }


def validate_definition(definition):
    """The registered A/D definition document, checked for every field used."""
    _require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("registry")
        == {"path": REGISTRY[0], "sha256": REGISTRY[1], "candidate": CANDIDATE}
        and definition.get("g_feas") == registry_gate()
        and definition.get("paired_repeat") == {"procedure": "per_case", "floor": 0}
        and type(definition.get("unresolved_mask")) is dict
        and definition["unresolved_mask"].get("reason") == UNRESOLVED_REASON
        and type(definition["unresolved_mask"].get("case_ids")) is list
        and all(type(c) is str for c in definition["unresolved_mask"]["case_ids"])
        and definition.get("decision_scenarios") == decision_scenarios()
        and definition.get("ev4_references") == pinned("ev4_references")
        and definition.get("b15_probe_plan") == pinned("b15_probe_plan"),
        "battery_definition",
    )


def pinned(name):
    """A pinned Battery 2.0 source, as the pack carries it (battery_pack)."""
    from carbon.challenge_kit import battery_pack

    path, sha = {
        "ev4_references": battery_pack._EV4_REFERENCES,
        "b15_probe_plan": battery_pack._B15_PLAN,
    }[name]
    return {"path": path, "sha256": "sha256:" + sha}


def decision_scenarios():
    """D's scenarios: EV4's development scenarios, in its order."""
    from carbon.battery import quiz_stratum
    from carbon.battery.value import contract as ev

    contract = quiz_stratum.contract(_REPOSITORY)
    return [
        {"id": s["id"], "conditions": s["conditions"]}
        for s in ev.scenarios(contract, "development")
    ]


def physics_b15(probe_predictions):
    """B15 over the public probe pairs, by the pinned checker
    (``physics_gate.BatteryPhysics``, OWNER-PHYSICS-GATES-01): it validates the
    contract adoption and every pair of the approved plan, then measures the
    model's own pair residuals. Returns the checker's B15 verdict."""
    from carbon.battery import construction_bundle_material as material
    from carbon.battery import physics_gate

    plan = pinned("b15_probe_plan")
    term = {
        "contract_sha256": material.PHYSICS_SHA256,
        "probes_path": plan["path"],
        "probes_sha256": plan["sha256"].removeprefix("sha256:"),
        "reference_image": physics_gate.REFERENCE_IMAGE,
    }
    try:
        checker = physics_gate.BatteryPhysics(
            term, _REPOSITORY, reference_image=physics_gate.REFERENCE_IMAGE
        )
    except physics_gate.PhysicsRefused as exc:
        raise BatteryMeasurementRefused("battery_b15_" + exc.code) from exc
    return checker.measure(probe_predictions, [])["B15"]


def store(records):
    """An exam case store over bank PRACTICE records, built exactly as
    ``value.scoring.scoring_set`` builds its own."""
    import numpy as np

    from carbon.battery import exam
    from carbon.battery.calibration import SHAPES, frozen_calibration
    from carbon.battery.challenge import PublicMaterial

    refs = {r["case_id"]: r for r in records}
    material = PublicMaterial.load(_REPOSITORY)
    ocv = {
        c: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for c, r in refs.items()
        if r.get("inputs")
    }
    tol, scales = frozen_calibration(_REPOSITORY)
    return exam.CaseStore(refs, ocv, tol, scales, SHAPES, {})


def rated_cases(records):
    """``(rated case ids, mask)``: a case whose v2 plating label is UNRESOLVED
    is counted, never rated."""
    unresolved = [
        r["case_id"]
        for r in records
        if type(r.get("plating_label_v2")) is dict
        and r["plating_label_v2"].get("label") == "UNRESOLVED"
    ]
    rated = [r["case_id"] for r in records if r["case_id"] not in set(unresolved)]
    return rated, {"case_ids": unresolved, "reason": UNRESOLVED_REASON}


def accuracy_and_exam_gates(contract, predictions, case_ids, case_store):
    """Registry leg ``a`` and the exam gates' verdict, from the pinned
    ``scoring.components`` and ``ratios.legs``."""
    from carbon.battery.value import ratios
    from carbon.battery.value import scoring as sc

    component = sc.components(predictions, case_ids, case_store, contract)
    a, _r, _g = ratios.legs(component)
    return a, bool(component["eligible"]), component


def false_feasible_rate_v2(contract, predictions, case_ids, refs, labels):
    """``score_tuning.false_feasible_rate`` with the reference's plating verdict
    from battery-plating-ref-v2 (``gate_plating_v2.check``); temperature and
    CV truth keep EV4's bands. ``labels[case_id]`` is the case's v2 label (None
    is v2's no claim). None when a case is missing or no case fails."""
    from carbon.battery.value import decision as d
    from carbon.battery.value import gate_plating_v2 as gp

    bands = contract["reference"]["uncertainty"]["bands"]
    fails = accepted = 0
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        truth = gp.check(
            contract, d.measure(contract, reference), bands, labels[case_id]
        )
        if any(v == d.FAIL for v in truth.values()):
            said = d.check(contract, d.measure(contract, outputs))
            fails += 1
            accepted += all(v == d.PASS for v in said.values())
    return None if fails == 0 else accepted / fails


def q3_judge_v2(contract, scenario, grid_predictions, grid_refs):
    """``quiz.q3_judge`` with the reference grid assessed under the plating-v2
    gate (``gate_plating_v2.assess_reference``), or None for a scenario whose
    reference grid holds no feasible design (``quiz.q3_feasible``'s rule).

    The candidates are EV4's own frozen grid (``contract.candidates``, 35), the
    grid the decision references cover; ``quiz.q3_candidates`` is the quiz's
    finer 117-member grid, whose EV4 subset has the same order."""
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d
    from carbon.battery.value import gate_plating_v2 as gp

    candidates = ev.candidates(contract)
    keys = {(c["id"], 0): ev.case_id(contract, scenario, c, 0) for c in candidates}
    refs = {key: grid_refs[cid] for key, cid in keys.items() if cid in grid_refs}
    reference = gp.assess_reference(contract, scenario, candidates, refs, keys)
    best = d.best_in_set(candidates, reference)
    if best is None:
        return None
    quantities = {}
    for candidate in candidates:
        outputs = grid_predictions.get(keys[(candidate["id"], 0)])
        if outputs is None:
            return {
                "kind": "MODEL_OUTPUT_MISSING",
                "selected": None,
                "decision_loss": contract["mistake_costs"]["missed_opportunity"],
            }
        quantities[(candidate["id"], 0)] = d.measure(contract, outputs)
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    selection = d.select(candidates, predicted)
    baseline_id = ev.candidate_id(contract["baseline"]["protocol"])
    result = d.outcome(contract, candidates, selection, reference, baseline_id)
    return {
        "kind": result["kind"],
        "selected": result.get("selected"),
        "decision_loss": result["decision_loss"],
    }


def decision_value(contract, scenarios, grid_predictions, grid_refs):
    """Registry leg ``q`` over ``scenarios`` (``[{id, conditions}]``): the
    quiz's measures over the feasible scenarios' outcomes, and q = 1/(1+regret)."""
    from carbon.battery.value import quiz

    outcomes = []
    for entry in scenarios:
        scenario = quiz.q3_scenario(entry["id"], entry["conditions"][0])
        judged = q3_judge_v2(contract, scenario, grid_predictions, grid_refs)
        if judged is not None:
            outcomes.append(judged)
    measures = quiz.q3_measures(outcomes, contract)
    regret = measures["regret"]
    return (None if regret is None else 1.0 / (1.0 + regret)), {
        **measures,
        "scenarios": len(outcomes),
    }


def g_feas_passes(measured, cutoff):
    """``score_tuning.exceeds_verdict``'s registered comparison (registry v5,
    ``comparison: exceeds``): PASS at or below the cutoff; above it, or
    unmeasured, fails. Not imported: ``score_tuning`` reaches the battery
    panel's attack harness, which no miner-reachable module may import
    (OWNER-GRAPHITE-ATTACKER-01); a test pins it equal to the pinned function."""
    return measured is not None and not measured > cutoff


def paired_repeat_exact(outputs, repeats):
    """The graded run and both fresh repeats agree exactly (registered floor 0)."""
    return len(repeats) == 2 and all(r == outputs for r in repeats)


def practice_measures(*, bank, outputs, repeats, definition, contract):
    """A, the exam gates, G-FEAS and the exact paired repeat on the bank's
    PRACTICE rows; ``bank`` is the shared producer's bank rows, ``outputs`` and
    ``repeats`` the graded run's and the two fresh repeats' flat rows."""
    from carbon.battery import construction_material as cm

    practice = [i for i, row in enumerate(bank) if row["cohort"] == "practice"]
    _require(practice, "battery_practice_rows")
    records = [bank[i]["record"] for i in practice]
    case_ids = [bank[i]["case_id"] for i in practice]
    try:
        predictions = cm.output_predictions([outputs[i] for i in practice], case_ids)
    except ValueError as exc:
        raise BatteryMeasurementRefused("battery_prediction_tensor") from exc
    rated, mask = rated_cases(records)
    _require(mask == definition["unresolved_mask"], "battery_unresolved_mask")
    case_store = store(records)
    a, exam_ok, _component = accuracy_and_exam_gates(
        contract, predictions, rated, case_store
    )
    labels = {r["case_id"]: r.get("plating_label_v2") for r in records}
    rate = false_feasible_rate_v2(contract, predictions, rated, case_store.refs, labels)
    gate = definition["g_feas"]
    return {
        "A": a,
        "gates": {
            "exam_gates": exam_ok,
            "g_feas": g_feas_passes(rate, gate["cutoff"]),
            "paired_repeat": paired_repeat_exact(outputs, repeats),
        },
        "false_feasible_rate": rate,
        "unresolved_mask": mask,
    }


def measure(*, bank, outputs, repeats, definition, contract):
    """Battery's A, D and gate verdicts on the 2.0 bank, or a refusal.

    PRACTICE rows give A, the exam gates and G-FEAS; the decision rows give D
    (EV4 development, plating-v2 truth, the quiz's rules); the probe rows give
    B15; the paired repeat covers every row. A row without a reference is never
    truth (the shared core's mask); a reference limitation refuses, never a
    candidate verdict.
    """
    from carbon.battery import construction_material as cm

    validate_definition(definition)
    practice = practice_measures(
        bank=bank,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        contract=contract,
    )

    def predictions(cohort):
        rows = [i for i, row in enumerate(bank) if row["cohort"] == cohort]
        _require(rows, "battery_" + cohort + "_rows")
        try:
            return rows, cm.output_predictions(
                [outputs[i] for i in rows], [bank[i]["case_id"] for i in rows]
            )
        except ValueError as exc:
            raise BatteryMeasurementRefused("battery_prediction_tensor") from exc

    decision_rows, grid_predictions = predictions("decision")
    grid_refs = {
        bank[i]["case_id"]: bank[i]["record"]
        for i in decision_rows
        if bank[i]["reference_present"]
    }
    d, decision = decision_value(
        contract, definition["decision_scenarios"], grid_predictions, grid_refs
    )
    # No feasible scenario is a reference limitation common to every model.
    _require(d is not None, "battery_d_reference_unresolved")
    _probe_rows, probe_predictions = predictions("probe")
    b15 = physics_b15(probe_predictions)
    return {
        "A": practice["A"],
        "D": d,
        "gates": {
            "exam_gates": practice["gates"]["exam_gates"],
            "g_feas": practice["gates"]["g_feas"],
            "physics_b15": b15["eligible"] is True,
            "paired_repeat": practice["gates"]["paired_repeat"],
        },
        # D is the quiz's q, which already prices every pick (packet section 2).
        "decision_outcome": "VERIFIED_FEASIBLE",
        "false_feasible_rate": practice["false_feasible_rate"],
        "unresolved_mask": practice["unresolved_mask"],
        "decision": decision,
        "b15": b15,
    }
