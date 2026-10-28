"""Motor grades a sealed exam grid (OWNER-MOTOR-EXAM-GRID-01; Validator rulings
VALIDATOR_RULING_MOTOR_SEALED_GRADING_20261022 and MOTOR_GRID_SPLIT): a placed
5 designs x 6 conditions grid, graded with Motor's registered decision measure
(A = the minimum of the registered benefits that exist on one grid, D the
verified-regret benefit), total 0.5 A + 0.5 D, the receipt sha256(solver_evidence),
the native gates unchanged, in a new adapter module that leaves Motor's
development producer untouched. The grid is a synthetic, non-production fixture."""

from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pytest
from test_motor_sealed_family import document, records_for

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_kit import physical_pack
from carbon.motor import customer_decision as decision
from carbon.motor.domain import ANGLE_STEPS
from carbon.scoring import dual_score, motor_physics
from carbon.scoring import motor_dual_measurement as mdm
from carbon.scoring import motor_dual_pack as dev
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

MOTOR = "electric-motor-magnetics"
#: Motor's development producer digest after composite 40's accepted move
#: (the sealed bank loader and copy modules, Validator 2026-10-22: was
#: sha256:5fe2c492...c75a2b9c) and graph route v2's one producer move (Motor
#: 1.4 joins `VERSIONS` under 1.3's evaluation version), then scoring v2's
#: modules beside it (rc3, graph route v2 on scoring v2), then the sealed-pack
#: fail-closed fix (Validator P0, 2026-10-23; was
#: sha256:2c7023be118193685c3fb4f71fa656e51865f7e15be3fc14b13a8da19919e5e9),
#: then the pool-graded versions' one shared-producer move (M2/M3: the pool path in `physical_dual_pack`,
#: `sealed_batch_source` and `copy_derivation`, pre-publish; was
#: sha256:6b72a0162a5b691b2f44613523e453a61ccf235a35ff8bc6fdec5ffdbf4537ab).
#: then the pool-graded versions' no-timed-query rule (GPU_REBUILD_RULINGS section 13: `physical_dual_pack`
#: and `bundle_benchmark_core`; pre-publish; was
#: sha256:d802eebd03590c158b3225eac7e30b0c404c476de6408eb1e0454d347097fd56).
DEV_PRODUCER_DIGEST = (
    "sha256:d31b710243539886d45806c982061f444f4a4d4bfcdaf15c748c377fc100dec1"
)
DESIGNS, CONDITIONS = 5, 6


def _curve(design, condition):
    """A synthetic torque curve: higher designs and conditions make more mean
    torque, so some designs are feasible at every condition and some are not."""
    mean = 3.0 + 0.8 * design + 0.15 * condition
    ripple = 0.05 + 0.01 * design
    return [
        mean * (1.0 + ripple * math.sin(2 * math.pi * k / ANGLE_STEPS))
        for k in range(ANGLE_STEPS)
    ]


def _grid_bank(wall_s=1.5, probes=True):
    """Data Collection's sealed bank in the grid layout of the split ruling:
    one cohort, design-major cells, ``design_id`` / ``condition_id`` fields in
    the reference records, design inputs shared within a design and condition
    inputs shared within a condition."""
    doc = document()
    records = [dict(r, wall_s=wall_s) for r in records_for(doc)]
    base = pack.sealed_bank(doc, records)
    interface = physical.input_names(sealed)
    column = {name: interface.index(name) for name in interface}
    inputs = np.asarray(base["inputs"])
    rows, ids, new_records, refs = [], [], [], []
    for d in range(DESIGNS):
        for c in range(CONDITIONS):
            row = np.array(inputs[d], dtype="<f8")
            for name in decision.CONDITION_VARIABLES:
                row[column[name]] = inputs[DESIGNS + c][column[name]]
            curve = _curve(d, c)
            case_id = f"m{d}{c}"
            rows.append(row)
            ids.append(case_id)
            refs.append(curve)
            new_records.append(
                {
                    "case_id": case_id,
                    "status": "OK",
                    "inputs": dict(zip(interface, map(float, row), strict=True)),
                    "image": records[0]["image"],
                    "outputs": {"torque_nm": curve},
                    "wall_s": wall_s,
                    "design_id": f"design-{d}",
                    "condition_id": f"condition-{c}",
                }
            )
    bank = dict(base)
    bank["case_ids"] = tuple(ids)
    bank["cohorts"] = (sealed.COHORT,) * len(ids)
    bank["inputs"] = np.asarray(rows, dtype="<f8")
    bank["references"] = np.asarray(refs, dtype="<f8")
    bank["reference_records"] = new_records
    cases = {c["case_id"]: c["inputs"] for c in doc["cases"]}
    return pack._with_probes(bank, cases, "<f8") if probes else bank


@pytest.fixture(scope="module")
def case():
    bank = _grid_bank()
    public = physical_pack.public_roles(MOTOR, "1.3")
    names = physical.input_names(sealed)
    return {
        "bank": bank,
        "public": public,
        "names": names,
        "rows": physical.bank_rows(bank, names),
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
        "definition": sealed.definition(bank=bank, train_raw=public["train"]),
        "model": motor_physics.registered_model(public["train"]),
    }


def _cells(rows):
    return [r for r in rows if r["cohort"] == "decision_sealed_grid"]


def _full(case, cells, model=None, rows=None):
    """Predictions for every row in the delivered order: the cell curves in the
    order the cells appear, the stand-in model (a flat curve at the
    registered-fit mean torque) at each probe row."""
    model = model or case["model"]
    cells = iter(cells)
    return [
        (
            [model([row["inputs"][n] for n in case["names"]])] * ANGLE_STEPS
            if row["cohort"] == "probe_response"
            else list(map(float, next(cells, [0.0] * ANGLE_STEPS)))
        )
        for row in (rows or case["rows"])
    ]


def _measure(case, outputs, repeats=None, definition=None, rows=None, model=None):
    if len(outputs) == 30:
        repeats = repeats or [outputs, outputs]
        outputs = _full(case, outputs, model, rows)
        repeats = [_full(case, r, model, rows) for r in repeats]
    return sealed.measure(
        bank_rows=rows or case["rows"],
        outputs=outputs,
        repeats=repeats or [outputs, outputs],
        definition=definition or case["definition"],
        limits=case["limits"],
        objective=case["objective"],
        train_raw=case["public"]["train"],
        names=case["names"],
    )


def _truth(case):
    return [
        list(map(float, row["reference"]))
        for row in case["rows"]
        if row["cohort"] == "decision_sealed_grid"
    ]


def test_the_definition_is_the_registered_decision_measure_on_a_grid(case):
    definition = case["definition"]
    sealed.validate_definition(definition)
    assert definition["grid"] == {"designs": 5, "conditions": 6}
    assert definition["cohort_counts"] == {"decision_sealed_grid": 30}
    assert definition["losses"] == list(sealed.LOSSES) and len(sealed.LOSSES) == 3
    assert definition["reference_receipt_sha256"] == (
        "sha256:" + hashlib.sha256(case["bank"]["solver_evidence"]).hexdigest()
    )
    # Every scale and the verification budget are Motor's registered ones.
    registered = dev.definition(bank=None, train_raw=b"")
    for key in (
        "f0_scale",
        "signed_margin_scale",
        "signed_margin_cell",
        "D_scale",
        "verification_budget",
    ):
        assert definition[key] == registered[key]
    with pytest.raises(mdm.MotorMeasurementRefused):
        sealed.definition(bank={"solver_evidence": b""}, train_raw=b"")
    for broken in (
        {**definition, "losses": definition["losses"][:2]},
        {**definition, "grid": {"designs": 6, "conditions": 5}},
        {**definition, "reference_receipt_sha256": "x"},
        {**definition, "cohort_counts": {"practice": 30}},
        {k: v for k, v in definition.items() if k != "D_scale"},
    ):
        with pytest.raises(mdm.MotorMeasurementRefused):
            sealed.validate_definition(broken)


def test_a_model_equal_to_the_references_earns_full_a_and_d(case):
    result = _measure(case, _truth(case))
    assert result["gates"] == {
        "native_motor_valid": True,
        "complete_fixed_coverage": True,
        "physics_laws": True,
    }
    assert result["gate_failed_cases"] == []
    # The stand-in model is not exactly linear in the current, so the law leg is
    # near one; the accuracy and response legs are exact.
    assert result["A_legs"]["A_acc"] == 1.0 and result["D"] == 1.0
    assert result["A"] == pytest.approx(1.0, abs=2e-3)
    assert result["decision_outcome"] == "VERIFIED_FEASIBLE"
    assert result["verified_regret"] == 0.0
    assert result["selected_design"] in {f"design-{d}" for d in range(DESIGNS)}
    assert result["losses"] == dict.fromkeys(sealed.LOSSES, 0.0)


def test_a_is_the_minimum_of_the_registered_benefits(case):
    shifted = [[v + 0.35 for v in row] for row in _truth(case)]
    result = _measure(case, shifted)
    definition = case["definition"]
    f0_all, f0_worst, margin = (result["losses"][n] for n in sealed.LOSSES)
    assert f0_all > 0 and f0_worst >= f0_all and margin > 0
    benefits = [
        1.0 / (1.0 + f0_all / definition["f0_scale"]),
        1.0 / (1.0 + f0_worst / definition["f0_scale"]),
        1.0 / (1.0 + margin / definition["signed_margin_scale"]),
    ]
    assert result["A_legs"]["A_acc"] == min(benefits) < 1.0


def test_d_is_the_registered_decision_workflow_not_a_carried_a(case):
    # A uniform torque shift worsens A, and moves the ripple ranking so the
    # designs the model verifies are not the reference's feasible ones: the
    # registered workflow reports a missed opportunity, whatever A is. D is not a copy of A.
    shifted = [[v + 0.35 for v in row] for row in _truth(case)]
    result = _measure(case, shifted)
    assert 0.0 < result["A"] < 1.0
    assert result["decision_outcome"] == "MISSED_OPPORTUNITY"
    # The mean V keeps the pair/accept measures of a missed pick; the pack's
    # MISSED_OPPORTUNITY policy (maximum_D 0) is what floors the grade.
    assert 0.0 <= result["D"] < 1.0 and result["D"] != result["A"]
    assert result["selected_design"] is None and result["verified_regret"] is None
    # The reference itself picks a design and earns the full benefit.
    exact = _measure(case, _truth(case))
    assert exact["decision_outcome"] == "VERIFIED_FEASIBLE" and exact["D"] == 1.0
    # A model that makes every design look infeasible has nothing to verify.
    starved = [[0.5 * min(row)] * len(row) for row in _truth(case)]
    outcome = _measure(case, starved)
    assert outcome["decision_outcome"] != "VERIFIED_FEASIBLE"
    assert outcome["D"] is None or outcome["D"] < 1.0


def test_the_total_is_the_registered_half_and_half(case):
    pack_body = sealed.applied_pack()
    assert pack_body["value_weight"] == 0.5
    assert pack_body["combination"] == "weighted_arithmetic_mean"
    assert pack_body["hard_gates"] == [
        "native_motor_valid",
        "complete_fixed_coverage",
        "physics_laws",
    ]
    assert set(pack_body["legs"]) == {"A", "D"}
    assert pack_body["decision_policy"] == dev._applied_pack()["decision_policy"]


def test_a_failed_gate_leaves_a_unmeasured_not_zero(case):
    broken = _truth(case)
    broken[0] = [float("nan")] * len(broken[0])
    result = _measure(case, broken)
    assert result["A"] is None
    assert result["gates"]["native_motor_valid"] is False
    assert _cells(case["rows"])[0]["case_id"] in result["gate_failed_cases"]


def test_a_roster_cohort_or_grid_that_is_not_the_sealed_grid_refuses(case):
    truth = _truth(case)
    with pytest.raises(mdm.MotorMeasurementRefused):
        _measure(case, truth[:-1], repeats=[truth[:-1], truth[:-1]])
    wrong_cohort = [dict(row, cohort="practice") for row in case["rows"]]
    with pytest.raises(mdm.MotorMeasurementRefused) as refused:
        _measure(case, truth, rows=wrong_cohort)
    assert refused.value.code == "motor_bank_cohort"
    # Two cells claiming one (design, condition): not a complete grid.
    first, second = [
        i for i, r in enumerate(case["rows"]) if r["cohort"] == "decision_sealed_grid"
    ][:2]
    duplicate = copy.deepcopy(case["rows"])
    duplicate[second]["condition_id"] = duplicate[first]["condition_id"]
    with pytest.raises(mdm.MotorMeasurementRefused) as refused:
        _measure(case, truth, rows=duplicate)
    assert refused.value.code == "motor_sealed_grid"
    # A sixth design id is not 5 x 6.
    extra = copy.deepcopy(case["rows"])
    extra[first]["design_id"] = "design-9"
    with pytest.raises(mdm.MotorMeasurementRefused):
        _measure(case, truth, rows=extra)


def test_the_development_producer_is_untouched_and_a_sealed_bank_refuses_under_it(
    case,
):
    assert dev.producer_digest() == DEV_PRODUCER_DIGEST
    assert dev.FILES == ("motor_dual_pack.py", "motor_dual_measurement.py")
    assert sealed.producer_digest() != dev.producer_digest()
    assert sealed.FILES == (
        *dev.FILES,
        "sealed_grid_common.py",
        "critical_fidelity.py",
        "design_fidelity.py",
        "physics_half.py",
        "probe_design.py",
        "motor_physics.py",
        "motor_sealed_dual_pack.py",
    )
    with pytest.raises(mdm.MotorMeasurementRefused) as refused:
        dev.measure(
            bank_rows=_cells(case["rows"]),
            outputs=_truth(case),
            repeats=[_truth(case), _truth(case)],
            definition=dev.definition(bank=None, train_raw=b""),
            limits=case["limits"],
            objective=case["objective"],
            train_raw=case["public"]["train"],
            names=case["names"],
        )
    assert refused.value.code == "motor_bank_cohort"


def test_dispatch_is_by_the_banks_declared_population(case):
    for version in ("1.1", "1.2", "1.3", "1.4"):
        chosen = sealed.adapter_for_bank(case["bank"], version)
        assert chosen.EVALUATION_VERSION == "motor-dual-sealed-batch-30-v2"
        assert chosen.VERSION == version and chosen.CASE_ID == sealed.CASE_ID
    assert sealed.adapter("1.0") is None and sealed.adapter("1.6") is None
    # Motor 1.5 is the pool-graded version: a pool adapter, never the plain grid grader
    assert sealed.adapter("1.5").POOL_GRADED
    development = physical_pack.development_bank(MOTOR, "1.3")
    chosen = sealed.adapter_for_bank(development, "1.3")
    assert chosen.EVALUATION_VERSION == dev.VERSIONS["1.3"][0]
    assert not sealed.is_sealed_bank(development)
    assert sealed.is_sealed_bank(case["bank"])
    mixed = dict(case["bank"], cohorts=("decision_sealed_grid",) * 29 + ("practice",))
    with pytest.raises(mdm.MotorMeasurementRefused):
        sealed.adapter_for_bank(mixed, "1.3")
    # The pre-grid placed-30 bank (cohort screening) is not a sealed grid.
    placed = dict(case["bank"], cohorts=("screening",) * 30)
    assert not sealed.is_sealed_bank(placed)
    with pytest.raises(mdm.MotorMeasurementRefused):
        sealed.adapter_for_bank(placed, "1.3")


def test_the_receiver_pack_directory_scores_half_a_plus_half_d(case, tmp_path):
    """The pack the writer makes registers with the shared scorer, and a model
    equal to the references scores 1.0 (0.5 A + 0.5 D)."""
    root = tmp_path / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, case["bank"], version="1.3", inference_image_id="sha256:" + "1" * 64
    )
    assert manifest_path == root / "evaluation-pack.json"
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["pack_version"].endswith(sealed.PACK_SUFFIX)
    assert "exposed-bank" not in manifest["pack_version"]
    for role in (
        "case_bank",
        "reference_rows",
        "solver_evidence",
        "score_pack",
        "source_registration",
    ):
        assert (root / manifest["private"][role]["path"]).is_file(), role
    assert (root / manifest["public"]["accuracy_definition"]["path"]).is_file()
    score_pack = json.loads(
        (root / manifest["private"]["score_pack"]["path"]).read_bytes()
    )
    assert all(leg["minimum"] is None for leg in score_pack["legs"].values())
    accuracy = json.loads(
        (root / manifest["public"]["accuracy_definition"]["path"]).read_bytes()
    )
    assert accuracy["method"] == sealed.METHOD
    assert accuracy["producer_digest"] == sealed.producer_digest()
    dev_bank = physical_pack.development_bank(MOTOR, "1.3")
    assert accuracy["bank_digest"] == physical.bank_digest(case["bank"])
    assert accuracy["bank_digest"] != physical.bank_digest(dev_bank)

    result = _measure(case, _truth(case))
    benchmark = {
        "schema": dual_score.INPUT_SCHEMA,
        "scope": score_pack["scope"],
        "challenge": score_pack["challenge"],
        "physics_contract_digest": score_pack["physics_contract_digest"],
        "measurement_contract_digest": score_pack["measurement_contract_digest"],
        "population_role": "P",
        "common_mask_digest": "sha256:" + "2" * 64,
        "models": [
            {
                "artifact_digest": "sha256:" + "3" * 64,
                "gates": dict.fromkeys(score_pack["hard_gates"], "PASS"),
                "measurements": {
                    physical.METRICS[leg]: {
                        "status": "RESOLVED",
                        "value": result[leg],
                        "unit": "1",
                    }
                    for leg in ("A", "D")
                },
                "decision_outcome": result["decision_outcome"],
            }
        ],
    }
    scored = dual_score.score(benchmark, score_pack)["models"][0]
    assert scored["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert scored["legs"]["D"] == 1.0 and scored["legs"]["A"] == pytest.approx(
        1.0, abs=2e-3
    )
    assert scored["score"] == pytest.approx(1.0, abs=2e-3)

    # The receiver seals the draft exactly as it seals a development pack.
    from carbon.challenge_validator.evaluation_pack import prepare_pack

    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=MOTOR,
        challenge_version="1.3",
    )
    assert not prepared.snapshot.missing_roles()["private"]
    assert prepared.snapshot.pack_version.endswith(sealed.PACK_SUFFIX)
    # A second write into a non-empty root, and a development bank, refuse.
    with pytest.raises(ValueError):
        sealed.write_sealed_pack(root, case["bank"], version="1.3")
    with pytest.raises(mdm.MotorMeasurementRefused):
        sealed.write_sealed_pack(tmp_path / "other", dev_bank, version="1.3")


def test_the_definition_registers_the_critical_block(case):
    block = case["definition"]["critical"]
    assert block["rule"] == "D=min(V,C)"
    assert {c["quantity"]: c["scale"] for c in block["components"]} == {
        "mean_torque_margin_nm": 0.10,
        "ripple_fraction_margin": 0.01,
    }
    assert block["objective"]["scale"] == case["definition"]["D_scale"]
    assert block["components_not_applied"] == ["response", "gap"]


def test_a_right_pick_with_wrong_margins_scores_d_below_one(case):
    """The owner control: the reference own pick, margins off. The value-only
    grader gave D = 1; a correct action alone no longer earns full Design."""
    truth = _truth(case)
    exact = _measure(case, truth)
    assert exact["D"] == 1.0 and exact["design_fidelity"]["C"] == 1.0
    skewed = _measure(case, [[v * 1.03 for v in row] for row in truth])
    assert skewed["selected_design"] == exact["selected_design"]
    assert skewed["verified_regret"] == 0.0
    c = skewed["design_fidelity"]["C"]
    assert c < 1.0 and skewed["D"] == c < 1.0


def test_an_unselected_designs_wrong_margins_cap_d(case):
    truth = _truth(case)
    exact = _measure(case, truth)
    outputs = copy.deepcopy(truth)
    # design-0 (cells 0..5) is never the pick; one cell predicted 20% high.
    assert exact["selected_design"] != "design-0"
    outputs[0] = [v * 1.2 for v in outputs[0]]
    measured = _measure(case, outputs)
    assert measured["selected_design"] == exact["selected_design"]
    assert measured["D"] < 1.0


def test_a_definition_without_the_critical_block_grades_value_only(case):
    """An earlier-version definition still grades exactly as it did."""
    legacy = {k: v for k, v in case["definition"].items() if k != "critical"}
    truth = _truth(case)
    skewed = _measure(
        case, [[v * 1.03 for v in row] for row in truth], definition=legacy
    )
    assert skewed["D"] == 1.0 and skewed["design_fidelity"] is None


# --- the physics half ---------------------------------------------------------


def test_the_definition_registers_the_physics_and_probe_blocks(case):
    definition = case["definition"]
    assert definition["probes"] == {"cohort": "probe_response", "rows": 4 * 19}
    block = definition["physics"]
    assert block["rule"] == "A=mean(A_acc,A_robust,A_law,A_response)"
    assert {law["name"] for law in block["laws"]} == {
        "linear_in_current",
        "zero_current_torque",
        "mean_torque_positive",
    }
    response = block["response"]
    j = response["inputs"].index("current_density_a_mm2")
    assert 0.5 < response["exponent"][0][j] < 1.5  # TRAIN fit, ~1.01
    angle = response["inputs"].index("current_angle_deg")
    assert response["exponent"][0][angle] is None  # sign gate only


def test_the_probes_are_private_unreferenced_rows_among_the_cells(case):
    rows = case["rows"]
    cohorts = [r["cohort"] for r in rows]
    assert cohorts.count("decision_sealed_grid") == 30 and len(rows) == 106
    # interleaved with the cells, never a suffix
    assert cohorts[:30] != ["decision_sealed_grid"] * 30
    assert cohorts[-30:] != ["decision_sealed_grid"] * 30
    probes = [r for r in rows if r["cohort"] == "probe_response"]
    assert len(probes) == 76 and all(r["reference"] is None for r in probes)
    zero = [r for r in probes if r["record"]["probe"].get("kind") == "law:j_zero"]
    assert zero and all(r["inputs"]["current_density_a_mm2"] == 0.0 for r in zero)


def test_a_model_with_the_registered_sensitivities_earns_full_response(case):
    result = _measure(case, _truth(case))
    assert result["A_legs"]["A_response"] == pytest.approx(1.0, abs=1e-3)
    assert result["physics_half"]["sign_gate_failed"] == []


def test_a_model_nonlinear_in_the_current_loses_on_the_law_leg(case):
    good = _measure(case, _truth(case))
    registered = case["model"]

    def saturating(point):
        # Same slope at small current, strongly saturating above it.
        j = point[6]
        return registered(point) * (1.0 / (1.0 + 0.08 * j))

    bad = _measure(case, _truth(case), model=saturating)
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"] - 0.02
    assert bad["A_legs"]["A_acc"] == good["A_legs"]["A_acc"]


def test_a_nonzero_torque_at_zero_current_loses_on_the_law_leg(case):
    good = _measure(case, _truth(case))
    registered = case["model"]

    def offset(point):
        return registered(point) if point[6] > 0 else 5.0

    bad = _measure(case, _truth(case), model=offset)
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"] - 0.02


def test_a_wrong_angle_trend_fails_the_sign_gate(case):
    registered = case["model"]

    def rising(point):
        flipped = list(point)
        flipped[7] = 60.0 - point[7]
        return registered(flipped)

    result = _measure(case, _truth(case), model=rising)
    assert result["gates"]["physics_laws"] is False
    assert any(
        "current_angle_deg" in item
        for item in result["physics_half"]["gate_failed_laws"]
    )


def test_a_negative_mean_torque_at_positive_current_fails_the_gate(case):
    result = _measure(case, _truth(case), model=lambda point: -1.0)
    assert result["gates"]["physics_laws"] is False
    assert "mean_torque_positive" in result["physics_half"]["gate_failed_laws"]


def test_a_sealed_motor_bank_is_graded_under_the_v2_version(case):
    for version in ("1.1", "1.2", "1.3"):
        chosen = sealed.adapter_for_bank(case["bank"], version)
        assert chosen.EVALUATION_VERSION == "motor-dual-sealed-batch-30-v2"
