"""M3 for Cooling 1.5: the pool-graded sealed pack is written, sealed by the receiver's loader and resolved back to
the same pool bank (the same route as Motor's, tests/cpu/test_pool_pack.py). Synthetic pools on Cooling's real
interface and a synthetic sealed grid: nothing here is a production value."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_cooling_hidden_family import document as grid_document
from test_cooling_hidden_family import ok_record

from carbon.challenge_kit import cooling_sealed_pack as pack
from carbon.challenge_kit import physical_public_train
from carbon.cold_plate_exam import population
from carbon.cold_plate_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
from carbon.scoring import cooling_encoded_dual_pack as sealed
from carbon.scoring import copy_package, pool_exam, pool_grader, pool_version
from carbon.scoring import sealed_batch_source as source
from carbon.scoring.pool_grader import Limit

COOLING = source.COOLING
VERSION = "1.5"
NAMES = physical_public_train.numeric_interface_document(COOLING)["input_names"]


def _target(target_id, seed, fixed):
    rng = random.Random(seed)
    n = len(DESIGN_INPUTS)
    designs = [[rng.random() for _ in range(n)] for _ in range(100)]
    return pool_grader.build_target(
        target_id=target_id,
        conditions={"target_id": target_id, "fixed": fixed},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", n * 0.45),),
        u={"f": 0.001, "g": 0.001},
        box=tuple((0.0, 1.0) for _ in range(n)),
        designs=designs,
        truths=[{"f": sum(d), "g": sum(x * x for x in d)} for d in designs],
        agen=range(92, 100),
        start=tuple(0.5 for _ in range(n)),
        seed=seed,
    )


def _fixed(offset):
    return {name: 1.0 + offset + i / 10 for i, name in enumerate(CONDITION_INPUTS)}


def material():
    return {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "cooling",
        "version": VERSION,
        "input_names": list(NAMES),
        "design_names": list(DESIGN_INPUTS),
        "input_dtype": "<f8",
        "set_digest": "sha256:" + "5" * 64,
        "sets": [
            [
                pool_grader.dump_pool(_target("A1", 1, _fixed(0.0))),
                pool_grader.dump_pool(_target("A2", 2, _fixed(1.0))),
            ]
        ],
    }


@pytest.fixture(scope="module")
def batch():
    doc = grid_document(population.draw(random.Random(2), 16)[0])
    records = []
    for i, case in enumerate(doc["cases"]):
        record = ok_record(case["case_id"], case["inputs"], peak=60.0)
        record["outputs"]["pressure_drop_pa"] = 40.0 + 3.0 * i
        record["wall_s"] = 1.5  # the real records carry their solver wall
        records.append(record)
    return doc, records


def _bank(batch, pool=None, version=VERSION):
    document, records = batch
    if pool is not None:
        document = {**document, "pool": pool}
    return source._build(COOLING, pack, document, records, version)


def test_the_cooling_pool_bank_holds_the_pool_rows_among_the_cells_and_probes(batch):
    bank = _bank(batch, material())
    cohorts = list(bank["cohorts"])
    pool_rows = cohorts.count(pool_exam.POOL_COHORT)
    assert pool_rows > 0 and cohorts.count("probe_response") > 0
    assert cohorts.count("decision_sealed_grid") == 16
    assert sealed.is_pool_bank(bank) and not sealed.is_sealed_bank(bank)
    # the plain grid is a sealed bank but not a pool bank
    plain = _bank(batch, None, "1.4")
    assert sealed.is_sealed_bank(plain) and not sealed.is_pool_bank(plain)
    assert bank["pool"] == material()


def test_the_sealed_bank_test_refuses_other_populations(batch):
    plain = _bank(batch, None, "1.4")
    assert not sealed.is_sealed_bank(
        {**plain, "cohorts": ("screening",) * len(plain["cohorts"])}
    )
    assert not sealed.is_sealed_bank({})
    assert not sealed.is_pool_bank(plain)


def test_the_cooling_pool_pack_is_written_sealed_and_resolves_back_to_the_same_bank(
    batch, tmp_path
):
    from carbon.challenge_validator.evaluation_pack import prepare_pack

    document, records = batch
    carried = {**document, "pool": material()}
    bank = _bank(batch, material())
    root = tmp_path / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, bank, version=VERSION, inference_image_id="sha256:" + "1" * 64
    )
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["pack_version"].endswith(sealed.PACK_SUFFIX)
    score_pack = json.loads(
        (root / manifest["private"]["score_pack"]["path"]).read_bytes()
    )
    assert score_pack["hard_gates"][-2:] == [
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
    ]
    case_bank = (root / manifest["private"]["case_bank"]["path"]).read_bytes()
    assert case_bank == pack.private_roles(bank)["case_bank"]
    public_text = (root / manifest["public"]["accuracy_definition"]["path"]).read_text()
    assert "truths" not in public_text and "pool-" not in public_text
    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=COOLING,
        challenge_version=VERSION,
    )
    (root / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(carried, records))
    resolved_bank, adapter = source.resolve(
        challenge=COOLING,
        version=VERSION,
        selected_pack=prepared.snapshot,
        private_root=root,
        development_adapter=None,
    )
    assert adapter.POOL_GRADED and adapter.VERSION == VERSION
    assert list(resolved_bank["case_ids"]) == list(bank["case_ids"])
    assert resolved_bank["pool"] == material()


def test_a_plain_grid_bank_cannot_be_written_as_a_pool_pack_and_a_pool_bank_not_as_plain(
    batch, tmp_path
):
    plain = _bank(batch, None, "1.4")
    with pytest.raises(Exception, match="cooling_bank_population"):
        sealed.write_sealed_pack(tmp_path / "a", plain, version=VERSION)
    with_pool = _bank(batch, material())
    with pytest.raises(Exception, match="cooling_bank_population"):
        sealed.write_sealed_pack(tmp_path / "b", with_pool, version="1.3")
    with pytest.raises(ValueError):
        sealed.write_sealed_pack(tmp_path / "c", plain, version="9.9")


def test_a_validator_copy_of_the_cooling_pool_exam_canonicalises_to_the_same_exam(
    batch,
):
    document = {**batch[0], "pool": material()}
    raw, _header = copy_package.make_copy(
        COOLING, VERSION, document, batch[1], key=b"k" * 32, hotkey="valV3-hotkey"
    )
    carried = json.loads(raw)
    assert carried["document"]["pool"] == material()
    canonical_raw, _source_fp, canonical_fp = copy_package.canonical_batch(
        COOLING, VERSION, document, batch[1]
    )
    copied = source._build(
        COOLING, pack, carried["document"], carried["records"], VERSION
    )
    original = source._build(COOLING, pack, document, batch[1], VERSION)
    assert len(copied["case_ids"]) == len(original["case_ids"])
    assert json.loads(canonical_raw)["document"]["pool"] == material()
    assert canonical_fp.startswith("sha256:")


def test_the_custody_builder_writes_the_cooling_pool_pack_and_a_digest_only_record(
    batch, tmp_path
):
    import importlib.util

    path = REPOSITORY / "scripts/dev/sealed_exam/pool_pack.py"
    spec = importlib.util.spec_from_file_location("pool_pack_script_cooling", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    record = builder.build(
        challenge=COOLING,
        version=VERSION,
        batch_dir=plain,
        out_dir=tmp_path / "out",
        inference_image_id="sha256:" + "1" * 64,
        material=material(),
    )
    assert record["rows"]["cells"] == 16 and record["rows"]["pool"] > 0
    assert record["rows"]["probes"] > 0
    assert (tmp_path / "out/pack/evaluation-pack.json").is_file()
    assert "truths" not in json.dumps(record) and "designs" not in json.dumps(record)
    carried = source.read_batch(tmp_path / "out/pack")
    assert carried is not None and carried[0]["pool"] == material()
