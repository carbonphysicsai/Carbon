"""Battery grades a sealed 4 x 35 exam grid (VALIDATOR_BATTERY_SEALED_RULINGS_20261022
§11; OWNER-BATTERY-EXAM-GRID-01): the registered dual measurement with the
batch's own 4 scenarios x EV4's frozen 35 candidates, D = decision_value's q,
A and the gates as registered, total 0.5 A + 0.5 D, in a new adapter module that
leaves Battery's development producer untouched. The grid is built from EV4's
development references (real solves, not an exam batch)."""

from __future__ import annotations

import copy
import functools
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import domain
from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import gate_plating_v2 as gp
from carbon.challenge_kit import battery_pack, physical_pack
from carbon.scoring import battery_dual_measurement as bdm
from carbon.scoring import battery_dual_pack as dev
from carbon.scoring import battery_sealed_dual_pack as sealed
from carbon.scoring import dual_score
from carbon.scoring import physical_dual_pack as physical

REPOSITORY = Path(__file__).resolve().parents[2]
DECISION_REFERENCES = (
    REPOSITORY / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
)
#: Battery's development producer digest after the one accepted move that hashed
#: the sealed bank loader and copy modules (Validator, 2026-10-22).
DEV_PRODUCER_DIGEST = (
    "sha256:615a11005e080d439b26685cf4e4a43652f7e36d92f6d80f3ac6db045265e540"
)


@functools.cache
def _sealed_bank():
    """Four EV4 development scenarios whose 35 references all solved and that
    have a feasible candidate, as a sealed grid bank: the cells in the 2.0
    decision-row format with each record's own mesh-160 margin."""
    contract = dev._contract()
    lines = gzip.decompress(DECISION_REFERENCES.read_bytes()).decode().splitlines()
    ok = {r["case_id"]: r for r in map(json.loads, lines) if r["status"] == "OK"}
    m160 = gp.m160_by_case()
    candidates = ev.candidates(contract)
    chosen = []
    for entry in contract["scenarios"]["development"]:
        ids = [ev.case_id(contract, entry, c, 0) for c in candidates]
        if not all(i in ok for i in ids):
            continue
        scenario = {"id": entry["id"], "conditions": entry["conditions"]}
        refs = {(c["id"], 0): ok[i] for c, i in zip(candidates, ids, strict=True)}
        keys = {(c["id"], 0): i for c, i in zip(candidates, ids, strict=True)}
        reference = gp.assess_reference(contract, scenario, candidates, refs, keys)
        if d.best_in_set(candidates, reference) is not None:
            chosen.append((entry, ids))
        if len(chosen) == sealed.SCENARIOS:
            break
    assert len(chosen) == sealed.SCENARIOS
    case_ids, inputs, references, records = [], [], [], []
    for _entry, ids in chosen:
        for case_id in ids:
            record = copy.deepcopy(ok[case_id])
            margin = d.measure(contract, record["outputs"])["plating_margin_v"]
            entry_m160 = m160.get(case_id)
            record["plating_margin_m160_v"] = (
                entry_m160[1] if entry_m160 is not None else margin
            )
            # The family names each cell's grid position on its record.
            _prefix, scenario_id, candidate_id, _index = case_id.split(":")
            record["scenario_id"], record["candidate_id"] = scenario_id, candidate_id
            case_ids.append(case_id)
            inputs.append([float(record["inputs"][k]) for k in domain.INPUTS])
            references.append(battery_pack._flat(record["outputs"]))
            records.append(record)
    x = np.asarray(inputs, dtype=np.float64)
    y = np.asarray(references, dtype=np.float64)
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "cohorts": (sealed.COHORT,) * len(case_ids),
        "inputs": x,
        "references": y,
        "reference_present": (True,) * len(case_ids),
        "reference_records": records,
        "solver_evidence": b'{"synthetic":"sealed-grid-evidence"}',
    }


@functools.cache
def _bank():
    return sealed.prepared(_sealed_bank())


def _rows():
    return physical.bank_rows(_bank(), sealed.input_names())


@functools.cache
def _definition():
    return sealed.definition(bank=_bank(), train_raw=b"")


def _truth():
    """A model that predicts every reference exactly; every probe row the same
    fixed curve, so each B15 pair agrees before the switch."""
    bank = _bank()
    rows = [list(map(float, row)) for row in bank["references"]]
    fixed = rows[0]
    return [
        fixed if cohort == sealed.PROBE else row
        for row, cohort in zip(rows, bank["cohorts"], strict=True)
    ]


def _measure(outputs, repeats=None, definition=None, rows=None):
    return sealed.measure(
        bank_rows=rows or _rows(),
        outputs=outputs,
        repeats=repeats or [outputs, outputs],
        definition=definition or _definition(),
        limits={},
        objective={},
        train_raw=b"",
        names=sealed.input_names(),
    )


def test_the_definition_binds_the_batchs_own_scenarios_and_receipt():
    definition = _definition()
    sealed.validate_definition(definition)
    assert definition["grid"] == {"scenarios": 4, "candidates": 35}
    assert len(definition["decision_scenarios"]) == 4
    ids = {s["id"] for s in definition["decision_scenarios"]}
    assert all(len(s["conditions"]) == 1 for s in definition["decision_scenarios"])
    assert len(ids) == 4
    assert definition["reference_receipt_sha256"] == (
        "sha256:" + hashlib.sha256(_bank()["solver_evidence"]).hexdigest()
    )
    assert definition["g_feas"] == bdm.registry_gate()
    assert definition["b15_probe_plan"] == bdm.pinned("b15_probe_plan")
    with pytest.raises(bdm.BatteryMeasurementRefused):
        sealed.definition(bank={"solver_evidence": b""}, train_raw=b"")
    for broken in (
        {**definition, "grid": {"scenarios": 12, "candidates": 35}},
        {**definition, "decision_scenarios": definition["decision_scenarios"][:3]},
        {**definition, "reference_receipt_sha256": "x"},
        {
            **definition,
            "g_feas": {
                "measure": "feasibility",
                "cutoff": 0.5,
                "comparison": "exceeds",
            },
        },
        {k: v for k, v in definition.items() if k != "unresolved_mask"},
    ):
        with pytest.raises(bdm.BatteryMeasurementRefused):
            sealed.validate_definition(broken)


def test_probe_rows_are_the_public_plan_appended_once():
    base = _sealed_bank()
    bank = sealed.with_probe_rows(base)
    assert len(base["case_ids"]) == 140
    assert len(bank["case_ids"]) == 140 + 2 * 200
    assert sealed.with_probe_rows(bank) is bank
    assert bank["cohorts"][:140] == (sealed.COHORT,) * 140
    assert set(bank["cohorts"][140:]) == {sealed.PROBE}
    assert not any(bank["reference_present"][140:])


def test_a_model_equal_to_the_references_scores_every_leg_and_gate():
    measured = _measure(_truth())
    # D prices every pick under the decision contract's costs, so even a model
    # equal to the references is below 1 where a conservative pick costs regret.
    assert measured["A"] == 1.0 and 0 < measured["D"] <= 1
    assert measured["gates"] == {
        "exam_gates": True,
        "g_feas": True,
        "physics_b15": True,
        "paired_repeat": True,
    }
    assert measured["decision"]["scenarios"] == 4
    assert measured["decision_outcome"] == "VERIFIED_FEASIBLE"
    assert measured["b15"]["n_pairs"] == 200 and measured["b15"]["n_violations"] == 0


def test_d_is_the_quiz_regret_over_the_batchs_own_scenarios():
    exact = _measure(_truth())
    outputs = [list(row) for row in _truth()]
    # Answer one scenario's cells with another scenario's: its picks change, so
    # D moves with the model (it is computed from the model's own answers).
    for k in range(35):
        outputs[k] = list(_truth()[35 + k])
    measured = _measure(outputs)
    assert measured["D"] != exact["D"] and 0 < measured["D"] <= 1
    assert measured["decision"]["regret"] == pytest.approx(1 / measured["D"] - 1)
    assert measured["decision"]["scenarios"] == 4
    # Missing a grid answer is the model's own missed opportunity: D is
    # computed on the same scenarios and never over fewer.
    contract = dev._contract()
    records = _bank()["reference_records"][:140]
    labels = sealed._labels(contract, records)
    refs = {r["case_id"]: r for r in records}
    predictions = {r["case_id"]: r["outputs"] for r in records}
    first = _definition()["decision_scenarios"][0]
    dropped = dict(predictions)
    dropped.pop(records[0]["case_id"])
    worse, _ = sealed.decision_value_sealed(contract, [first], dropped, refs, labels)
    assert worse == 1 / (1 + contract["mistake_costs"]["missed_opportunity"])


def test_the_sealed_truth_label_uses_the_cells_own_mesh_160_margin(monkeypatch):
    contract = dev._contract()
    records = _bank()["reference_records"][:140]
    seen = {}
    original = gp.plating_label

    def spy(reader, margin, m160=None):
        seen[round(margin, 12)] = m160
        return original(reader, margin, m160)

    monkeypatch.setattr(gp, "plating_label", spy)
    labels = sealed._labels(contract, records)
    assert set(labels) == {r["case_id"] for r in records}
    # Every cell's own recorded margin reached the v2 reader.
    for record in records:
        margin = d.measure(contract, record["outputs"])["plating_margin_v"]
        assert seen[round(margin, 12)] == record["plating_margin_m160_v"]
    # A label is the reader's (a claim or none), never a copied-in value.
    assert all(
        label is None or label["label"] in {"FEASIBLE", "INFEASIBLE", "UNRESOLVED"}
        for label in labels.values()
    )
    broken = copy.deepcopy(records[0])
    broken["plating_margin_m160_v"] = float("nan")
    with pytest.raises(bdm.BatteryMeasurementRefused):
        sealed._labels(contract, [broken])
    missing = {k: v for k, v in records[0].items() if k != "plating_margin_m160_v"}
    with pytest.raises(bdm.BatteryMeasurementRefused):
        sealed._labels(contract, [missing])


def test_a_grid_that_is_not_4_by_35_refuses():
    rows = _rows()
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        _measure(_truth(), rows=rows[:139] + rows[140:])
    assert refused.value.code == "battery_sealed_grid"
    duplicate = copy.deepcopy(rows)
    duplicate[1]["record"]["scenario_id"] = duplicate[0]["record"]["scenario_id"]
    duplicate[1]["record"]["candidate_id"] = duplicate[0]["record"]["candidate_id"]
    with pytest.raises(bdm.BatteryMeasurementRefused):
        _measure(_truth(), rows=duplicate)
    foreign = copy.deepcopy(rows)
    foreign[0]["record"]["candidate_id"] = "c1=9,c2=9"
    with pytest.raises(bdm.BatteryMeasurementRefused):
        _measure(_truth(), rows=foreign)
    moved = copy.deepcopy(rows)
    moved[0]["inputs"] = dict(
        moved[0]["inputs"], soc0=moved[0]["inputs"]["soc0"] + 0.01
    )
    with pytest.raises(bdm.BatteryMeasurementRefused):
        _measure(_truth(), rows=moved)
    absent = copy.deepcopy(rows)
    absent[0]["reference_present"] = False
    with pytest.raises(bdm.BatteryMeasurementRefused):
        _measure(_truth(), rows=absent)
    # A definition from another batch's scenarios is refused.
    other = dict(
        _definition(),
        decision_scenarios=[
            {**s, "id": s["id"] + "x"} for s in _definition()["decision_scenarios"]
        ],
    )
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        _measure(_truth(), definition=other)
    assert refused.value.code == "battery_sealed_scenarios"


def test_the_development_producer_is_untouched_and_a_dev_bank_refuses_here():
    assert dev.producer_digest() == DEV_PRODUCER_DIGEST
    assert dev.FILES == ("battery_dual_pack.py", "battery_dual_measurement.py")
    assert sealed.producer_digest() != dev.producer_digest()
    assert sealed.FILES == (
        *dev.FILES,
        "sealed_grid_common.py",
        "battery_sealed_dual_pack.py",
    )
    development = physical_pack.development_bank(dev.CHALLENGE, "2.0")
    rows = physical.bank_rows(development, sealed.input_names())
    with pytest.raises(bdm.BatteryMeasurementRefused) as refused:
        sealed.measure(
            bank_rows=rows,
            outputs=[list(r) for r in development["references"]],
            repeats=[[], []],
            definition=_definition(),
            limits={},
            objective={},
            train_raw=b"",
            names=sealed.input_names(),
        )
    assert refused.value.code in {"battery_sealed_grid", "battery_prediction_tensor"}


def test_dispatch_is_by_the_banks_declared_population():
    for version in ("2.0", "2.1"):
        chosen = sealed.adapter_for_bank(_bank(), version)
        assert chosen.EVALUATION_VERSION == "battery-dual-sealed-grid-4x35-v1"
        assert chosen.VERSION == version and chosen.CASE_ID == sealed.CASE_ID
    assert sealed.adapter("1.0") is None and sealed.adapter("2.2") is None
    development = physical_pack.development_bank(dev.CHALLENGE, "2.0")
    chosen = sealed.adapter_for_bank(development, "2.0")
    assert chosen.EVALUATION_VERSION == dev.VERSIONS["2.0"][0]
    assert sealed.is_sealed_bank(_bank()) and not sealed.is_sealed_bank(development)
    mixed = dict(
        _bank(), cohorts=(sealed.COHORT,) * 139 + ("practice",) + (sealed.PROBE,) * 0
    )
    mixed["cohorts"] = tuple(mixed["cohorts"]) + (sealed.PROBE,) * (
        len(_bank()["cohorts"]) - 140
    )
    with pytest.raises(bdm.BatteryMeasurementRefused):
        sealed.adapter_for_bank(mixed, "2.1")


def test_the_receiver_pack_directory_scores_half_a_plus_half_d(tmp_path):
    root = tmp_path / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, _sealed_bank(), version="2.1", inference_image_id="sha256:" + "1" * 64
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
    score_pack = json.loads(
        (root / manifest["private"]["score_pack"]["path"]).read_bytes()
    )
    assert all(leg["minimum"] is None for leg in score_pack["legs"].values())
    assert score_pack["value_weight"] == 0.5
    accuracy = json.loads(
        (root / manifest["public"]["accuracy_definition"]["path"]).read_bytes()
    )
    assert accuracy["method"] == sealed.METHOD
    assert accuracy["producer_digest"] == sealed.producer_digest()
    assert accuracy["bank_digest"] == physical.bank_digest(_bank())
    assert accuracy["bank_digest"] != physical.bank_digest(
        physical_pack.development_bank(dev.CHALLENGE, "2.0")
    )
    measured = _measure(_truth())
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
                "gates": {k: "PASS" for k in score_pack["hard_gates"]},
                "measurements": {
                    physical.METRICS[leg]: {
                        "status": "RESOLVED",
                        "value": measured[leg],
                        "unit": "1",
                    }
                    for leg in ("A", "D")
                },
                "decision_outcome": measured["decision_outcome"],
            }
        ],
    }
    scored = dual_score.score(benchmark, score_pack)["models"][0]
    assert scored["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert scored["legs"] == {"A": 1.0, "D": measured["D"]}
    assert scored["score"] == pytest.approx(0.5 * 1.0 + 0.5 * measured["D"])

    from carbon.challenge_validator.evaluation_pack import prepare_pack

    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=dev.CHALLENGE,
        challenge_version="2.1",
    )
    assert not prepared.snapshot.missing_roles()["private"]
    with pytest.raises(ValueError):
        sealed.write_sealed_pack(root, _sealed_bank(), version="2.1")
    with pytest.raises(bdm.BatteryMeasurementRefused):
        sealed.write_sealed_pack(
            tmp_path / "other",
            physical_pack.development_bank(dev.CHALLENGE, "2.0"),
            version="2.1",
        )
