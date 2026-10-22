"""Integration: a fake 140-cell batch built by Data Collection's
``battery_sealed_pack`` is graded by ``battery_sealed_dual_pack`` (Validator,
VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §13).

The family (``dc/battery-sealed``) and the grader are separate heads; this test
runs once both are in the tree and skips until then. The batch is the family's
own fake: a drawn 4 x 35 grid with synthetic, non-production records."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import numpy as np
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]

pytest.importorskip("carbon.battery_sealed.population")
pytest.importorskip("carbon.challenge_kit.battery_sealed_pack")

from carbon.battery_sealed import population  # noqa: E402
from carbon.challenge_kit import battery_sealed_pack as family_pack  # noqa: E402
from carbon.challenge_validator import battery_sealed_hidden as hidden  # noqa: E402
from carbon.scoring import battery_dual_measurement as bdm  # noqa: E402
from carbon.scoring import battery_sealed_dual_pack as sealed  # noqa: E402
from carbon.scoring import physical_dual_pack as physical  # noqa: E402
from test_battery_sealed_grading import _sealed_bank  # noqa: E402


def _document(cases):
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": hidden.CHALLENGE_ID, "version": hidden.CHALLENGE_VERSION},
        "role": "battery-sealed-exam-1",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"c{i:03d}", "inputs": c} for i, c in enumerate(cases)],
    }


def _record(case_id, inputs, source):
    """A terminal record for ``inputs`` whose solve outputs are an EV4
    development reference's (a real solve with a feasible and an infeasible
    side), so the batch can define a decision."""
    outputs = copy.deepcopy(source["outputs"])
    # Move the borrowed curves to this cell's own start (synthetic; the peak
    # voltage and the shape are kept): the exam's initial-state gates compare the first voltage with
    # the cell's open-circuit voltage and the first temperature with its ambient.
    from carbon.battery.challenge import PublicMaterial

    material = PublicMaterial.load(REPOSITORY)
    ocv = float(np.interp(inputs["soc0"], material.ocv_soc, material.ocv_v))
    v0, vmax = outputs["voltage_v"][0], max(outputs["voltage_v"])
    outputs["voltage_v"] = [
        ocv + (v - v0) * (vmax - ocv) / (vmax - v0) for v in outputs["voltage_v"]
    ]
    outputs["temperature_c"] = [
        v + (inputs["t_amb_c"] - outputs["temperature_c"][0])
        for v in outputs["temperature_c"]
    ]
    m20 = outputs["plating_margin_v"]
    m160 = source["plating_margin_m160_v"]
    record = {
        "case_id": case_id,
        "inputs": inputs,
        "status": "OK",
        "image": hidden.SOLVER_IMAGE,
        "overlay_lock_sha256": hidden.overlay_lock_sha256(),
        "outputs": outputs,
        "plating_margin_m160_v": m160,
        # The family's per-solve walls (the standard and the mesh-160 solve),
        # exactly as it writes them.
        "solves": {"standard": {"wall_s": 50.0}, "m160": {"wall_s": 250.0}},
    }
    record["plating"] = hidden.plating_label(m20, m160)
    return record


def _ev4_sources():
    """Every fully solved EV4 development scenario's 35 references (real
    solves) with its (ambient, soc0): the cells' synthetic outputs start from the
    scenario nearest each drawn one."""
    import gzip

    from carbon.battery import quiz_stratum
    from carbon.battery.value import contract as ev
    from carbon.battery.value import gate_plating_v2 as gp

    contract = quiz_stratum.contract(REPOSITORY)
    lines = gzip.decompress(
        (
            REPOSITORY
            / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
        ).read_bytes()
    ).decode().splitlines()
    ok = {r["case_id"]: r for r in map(json.loads, lines) if r["status"] == "OK"}
    m160 = gp.m160_by_case()
    sources = []
    for scenario in contract["scenarios"]["development"]:
        ids = [ev.case_id(contract, scenario, c, 0) for c in ev.candidates(contract)]
        if not all(i in ok for i in ids):
            continue
        cells = []
        for case_id in ids:
            record = copy.deepcopy(ok[case_id])
            entry = m160.get(case_id)
            record["plating_margin_m160_v"] = (
                entry[1] if entry is not None else record["outputs"]["plating_margin_v"]
            )
            cells.append(record)
        sources.append((tuple(scenario["conditions"][0]), cells))
    return sources


@pytest.fixture(scope="module")
def batch():
    # The family's own drawn 4 x 35 grid; each drawn scenario's 35 cells take
    # the 35 EV4 development references of the nearest fully solved EV4
    # scenario, moved to the drawn start (synthetic, non-production).
    sources = _ev4_sources()
    cases, _attempts = population.draw(random.Random(11), population.CELLS)
    document = _document(cases)

    def nearest(inputs):
        t, soc = inputs["t_amb_c"], inputs["soc0"]
        return min(
            sources,
            key=lambda s: ((s[0][0] - t) / 29.0) ** 2 + ((s[0][1] - soc) / 0.36) ** 2,
        )[1]

    records = [
        _record(case["case_id"], case["inputs"], nearest(case["inputs"])[i % 35])
        for i, case in enumerate(document["cases"])
    ]
    return family_pack.sealed_bank(document, records)


def _outputs(bank):
    rows = [list(map(float, row)) for row in bank["references"]]
    fixed = rows[0]
    return [
        fixed if cohort == sealed.PROBE else row
        for row, cohort in zip(rows, bank["cohorts"], strict=True)
    ]


def test_every_scenario_has_a_feasible_and_an_infeasible_reference(batch):
    """The family's decision check (§11 rule 4), on the references' v2 labels:
    each scenario has a candidate FEASIBLE and one INFEASIBLE, so D is defined
    and the choice is not trivial."""
    from carbon.battery.value import decision as d
    from carbon.battery.value import gate_plating_v2 as gp

    contract = sealed._contract()
    bank = sealed.prepared(batch)
    rows = physical.bank_rows(bank, sealed.input_names())
    _scenarios, grid, _cells = sealed._grid(rows, contract)
    labels = sealed._labels(contract, [rows[i]["record"] for i in grid])
    bands = contract["reference"]["uncertainty"]["bands"]
    status = {}
    for i in grid:
        record = rows[i]["record"]
        checks = gp.check(
            contract,
            d.measure(contract, record["outputs"]),
            bands,
            labels[record["case_id"]],
        )
        values = set(checks.values())
        side = (
            "INFEASIBLE"
            if d.FAIL in values
            else "UNRESOLVED" if d.UNRESOLVED in values else "FEASIBLE"
        )
        status.setdefault(record["scenario_id"], set()).add(side)
    assert len(status) == 4
    assert all({"FEASIBLE", "INFEASIBLE"} <= sides for sides in status.values())


def test_the_familys_bank_is_the_graders_population(batch):
    assert batch["cohorts"] == (sealed.COHORT,) * 140
    assert sealed.COHORT == "decision_sealed_grid"
    assert sealed.is_sealed_bank(batch)
    chosen = sealed.adapter_for_bank(batch, "2.1")
    assert chosen.EVALUATION_VERSION == "battery-dual-sealed-grid-4x35-v1"


def test_a_model_equal_to_the_references_is_graded_on_the_batchs_four_scenarios(
    batch,
):
    bank = sealed.prepared(batch)
    names = sealed.input_names()
    rows = physical.bank_rows(bank, names)
    definition = sealed.definition(bank=batch, train_raw=b"")
    sealed.validate_definition(definition)
    assert sorted(s["id"] for s in definition["decision_scenarios"]) == [
        f"scenario-{i}" for i in range(4)
    ]
    outputs = _outputs(bank)
    measured = sealed.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits={},
        objective={},
        train_raw=b"",
        names=names,
    )
    assert measured["decision"]["scenarios"] == 4
    # A, D and the total are defined and in 0..1 with no refusal. The cells'
    # synthetic outputs are the nearest EV4 scenario's, moved to each cell's own
    # start, so the exam's initial-state gates pass.
    assert 0 < measured["A"] <= 1 and 0 < measured["D"] <= 1
    assert 0 < 0.5 * measured["A"] + 0.5 * measured["D"] <= 1
    assert measured["gates"]["exam_gates"] is True
    assert set(measured["gates"]) == set(bdm.GATES)
    assert measured["decision_outcome"] == "VERIFIED_FEASIBLE"


def test_the_receiver_pack_directory_is_written_from_the_familys_bank(batch, tmp_path):
    from carbon.challenge_validator.evaluation_pack import prepare_pack

    root = tmp_path / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, batch, version="2.1", inference_image_id="sha256:" + "1" * 64
    )
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["pack_version"].endswith(sealed.PACK_SUFFIX)
    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=sealed.CHALLENGE,
        challenge_version="2.1",
    )
    assert not prepared.snapshot.missing_roles()["private"]
    accuracy = json.loads(
        (root / manifest["public"]["accuracy_definition"]["path"]).read_bytes()
    )
    assert accuracy["producer_digest"] == sealed.producer_digest()
    assert len(accuracy["decision_scenarios"]) == 4
