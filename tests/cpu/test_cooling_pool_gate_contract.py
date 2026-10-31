"""A probed or pool-graded Cooling pack registers the law gate its measurement returns (Test Engineer, 2026-10-30).

Cooling's measurement adds `physics_laws` whenever the definition carries a `physics` block; its pack's `hard_gates`
once did not, so every gate-contract check (`gates == list(measured["gates"])`, in the calibration grade and in
`physical_dual_pack`'s dual-native path) refused a Cooling 1.5/1.6 pool pack. Real-shaped Cooling pool packs from
test_pool_pack_cooling (synthetic pools and grid, nothing production); no worker, no solver.
"""

from __future__ import annotations

import json
import random

import pytest
from test_cooling_hidden_family import document as grid_document
from test_cooling_hidden_family import ok_record
from test_pool_pack_cooling import COOLING, _bank, material

from carbon.challenge_validator import calibration_grade as cg
from carbon.challenge_validator import calibration_grade_run as run_module
from carbon.challenge_validator.evaluation_pack import prepare_pack
from carbon.cold_plate_exam import population
from carbon.scoring import cooling_encoded_dual_pack as encoded
from carbon.scoring import cooling_hotspot_dual_pack as hotspot
from carbon.scoring import cooling_physics, pool_exam
from carbon.scoring import sealed_batch_source as source

POOL_GATES = [pool_exam.PHYSICS_GATE, pool_exam.SPEED_GATE]


@pytest.fixture(scope="module")
def batch():
    doc = grid_document(population.draw(random.Random(2), 16)[0])
    records = []
    for i, case in enumerate(doc["cases"]):
        record = ok_record(case["case_id"], case["inputs"], peak=60.0)
        record["outputs"]["pressure_drop_pa"] = 40.0 + 3.0 * i
        record["wall_s"] = 1.5
        records.append(record)
    return doc, records


def _writer(version):
    return hotspot.write_sealed_pack if version == "1.6" else encoded.write_sealed_pack


def _pack(batch, version, tmp_path, *, calibration):
    document, records = batch
    bank = _bank(batch, material(version), version)
    root = tmp_path / "pack"
    manifest = _writer(version)(
        root,
        bank,
        version=version,
        inference_image_id="sha256:" + "1" * 64,
        calibration=calibration,
    )
    return (
        root,
        json.loads(manifest.read_bytes()),
        {**document, "pool": material(version)},
        records,
    )


@pytest.mark.parametrize("version", ["1.5", "1.6"])
@pytest.mark.parametrize("calibration", [False, True])
def test_the_pool_pack_registers_the_physics_law_gate_before_the_pool_gates(
    batch, version, calibration, tmp_path
):
    root, manifest, _carried, _records = _pack(
        batch, version, tmp_path, calibration=calibration
    )
    pack = json.loads((root / manifest["private"]["score_pack"]["path"]).read_bytes())
    gates = pack["hard_gates"]
    assert gates[-3:] == [cooling_physics.GATE, *POOL_GATES]
    assert len(gates) == len(set(gates))
    # the producer's registration names the same list: `physical_dual_pack` asserts
    # gates == registration["mandatory_gates"] == list(measured["gates"]) when it produces a measurement
    registration = json.loads(
        (root / manifest["private"]["source_registration"]["path"]).read_bytes()
    )
    assert registration["benchmark_registration"]["mandatory_gates"] == gates


def test_the_calibration_grade_of_a_cooling_1_6_pool_pack_passes_the_gate_contract(
    batch, tmp_path
):
    """Before the fix this raised CalibrationRefused('dual_native_gate_contract') (the same lists the official
    dual-native path asserts equal)."""
    root, _manifest, carried, records = _pack(batch, "1.6", tmp_path, calibration=True)
    prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=COOLING,
        challenge_version="1.6",
    )
    (root / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(carried, records))
    snapshot = run_module.prepare(root, COOLING, "1.6")
    bank, adapter, names = run_module.resolve_bank(snapshot, root, COOLING, "1.6")
    assert getattr(adapter, "POOL_GRADED", False)
    roles = run_module._roles(snapshot, root)
    rows = run_module._stand_in_rows(bank)
    result = cg.grade(
        adapter=adapter,
        bank=bank,
        pack=roles["score_pack"],
        definition=run_module.graded_definition(adapter, bank, roles["definition"]),
        limits=roles["limits"],
        objective=roles["objective"],
        train_raw=roles["train"],
        interface_names=names,
        infer=lambda _inputs: rows,
        entry_id="sha256:" + "2" * 64,
        challenge=adapter.CHALLENGE,
    )
    # the speed gate is the tool's labelled placeholder; every other registered gate is a result
    assert result["speed_gate"] == cg.SPEED_NOT_MEASURED
    assert set(result["gates"]) == set(roles["score_pack"]["hard_gates"]) - {
        pool_exam.SPEED_GATE
    }
    assert cooling_physics.GATE in result["gates"]
