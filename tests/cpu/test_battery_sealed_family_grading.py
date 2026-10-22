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

import pytest

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
        # The runner records a measured solve time per case; the pack's
        # reference rows total it.
        "wall_s": 1.5,
    }
    record["plating"] = hidden.plating_label(m20, m160)
    return record


@pytest.fixture(scope="module")
def batch():
    # The family's own drawn 4 x 35 grid; each scenario's 35 cells take the
    # 35 EV4 development references of one fully solved scenario in order.
    cells = _sealed_bank()["reference_records"][:35]
    cases, _attempts = population.draw(random.Random(11), population.CELLS)
    document = _document(cases)
    records = [
        _record(case["case_id"], case["inputs"], cells[i % 35])
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
    # D is defined on the four scenarios. A depends on the exam's physics gates
    # against each cell's own initial state, which borrowed EV4 outputs do not
    # match for freshly drawn conditions, so only its range is asserted here
    # (A's value is pinned by test_battery_sealed_grading on consistent cells).
    assert 0 < measured["D"] <= 1
    assert measured["A"] is None or 0 < measured["A"] <= 1
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
