"""M3: a pool-graded version's sealed pack carries its design-search rows (Validator V8_RULINGS section 11).

The pool rides in the batch document (`document["pool"]`, private custody); the bank holds its rows beside the
sealed cells and the private probes (cohort `pool_design`, inputs only, one seeded interleaving, no target named),
and the copy/canonical machinery treats them as derived rows. Synthetic pools on Motor's real interface: nothing here
is a production value.
"""

from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

import numpy as np
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_motor_sealed_family import records_for

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_kit import physical_public_train
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.motor_grid_exam import population
from carbon.motor_grid_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
from carbon.scoring import copy_derivation as cd
from carbon.scoring import copy_package, pool_exam, pool_grader, pool_version
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import sealed_batch_source as source
from carbon.scoring.pool_grader import Limit

MOTOR = source.MOTOR
POOL_VERSION = "1.5"
NAMES = physical_public_train.numeric_interface_document(MOTOR)["input_names"]


def _target(target_id, seed, fixed):
    rng = random.Random(seed)
    n = len(DESIGN_INPUTS)
    unit = [[rng.random() for _ in range(n)] for _ in range(100)]
    designs = [list(point) for point in unit]
    truths = [{"f": sum(d), "g": sum(x * x for x in d)} for d in designs]
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
        truths=truths,
        agen=range(92, 100),
        start=tuple(0.5 for _ in range(n)),
        seed=seed,
    )


def _fixed(offset):
    return {name: 1.0 + offset + i / 10 for i, name in enumerate(CONDITION_INPUTS)}


def material(dtype="<f8", extra_target=False):
    groups = [
        [
            pool_grader.dump_pool(_target("A1", 1, _fixed(0.0))),
            pool_grader.dump_pool(_target("A2", 2, _fixed(1.0))),
        ]
    ]
    if extra_target:
        groups.append([pool_grader.dump_pool(_target("B1", 3, _fixed(2.0)))])
    return {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "motor",
        "version": POOL_VERSION,
        "input_names": list(NAMES),
        "design_names": list(DESIGN_INPUTS),
        "input_dtype": dtype,
        "set_digest": "sha256:" + "5" * 64,
        "sets": groups,
    }


@pytest.fixture(scope="module")
def batch():
    cases, _ = population.draw(random.Random(3), population.CELLS)
    document = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    return document, [dict(r, wall_s=1.5) for r in records_for(document)]


def _bank(batch, pool=None, version=POOL_VERSION):
    document, records = batch
    if pool is not None:
        document = {**document, "pool": pool}
    return source._build(MOTOR, pack, document, records, version)


# --- the rows -----------------------------------------------------------------------------------


def test_pool_rows_are_the_models_input_rows_quantised_deduplicated_and_target_blind():
    rows = pool_version.rows_from_material(material(), dtype="<f8", challenge=MOTOR)
    assert (
        len(rows) == 200
    )  # 100 designs of two targets; identical queries would be one row
    ids = [case_id for case_id, _, _ in rows]
    assert len(set(ids)) == 200 and all(i.startswith("pool-") for i in ids)
    assert all(record == {"kind": "pool_design"} for _, record, _ in rows)
    assert all(len(values) == len(NAMES) for _, _, values in rows)
    # quantised to the bank's dtype: float32 rows are exactly float32 values
    single = pool_version.rows_from_material(
        material("<f4"), dtype="<f4", challenge=MOTOR
    )
    assert all(float(np.float32(v)) == v for _, _, values in single for v in values)
    # the same query in two targets is one row
    twin = material()
    twin["sets"][0][1] = twin["sets"][0][0]
    assert (
        len(pool_version.rows_from_material(twin, dtype="<f8", challenge=MOTOR)) == 100
    )


def test_the_row_order_is_the_canonical_one_and_independent_of_the_material_order():
    forward = pool_version.rows_from_material(material(), dtype="<f8", challenge=MOTOR)
    flipped = material()
    flipped["sets"][0].reverse()
    assert forward == pool_version.rows_from_material(
        flipped, dtype="<f8", challenge=MOTOR
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(schema="other"),
        lambda m: m.update(sets=[]),
        lambda m: m.update(design_names=["not-an-input"]),
        lambda m: m.pop("set_digest"),
        lambda m: m["sets"][0][0].update(digest="sha256:" + "0" * 64),
    ],
)
def test_a_malformed_material_or_a_changed_pool_is_refused(mutate):
    bad = copy.deepcopy(material())
    mutate(bad)
    with pytest.raises(ValueError):
        pool_version.rows_from_material(bad, dtype="<f8", challenge=MOTOR)


# --- the bank -----------------------------------------------------------------------------------


def test_a_pool_version_bank_holds_the_pool_rows_among_the_cells_and_probes(batch):
    plain = source._build(MOTOR, pack, *batch, "1.4")
    bank = _bank(batch, material())
    cohorts = list(bank["cohorts"])
    assert cohorts.count(pool_exam.POOL_COHORT) == 200
    assert len(cohorts) == len(plain["cohorts"]) + 200
    assert bank["pool"] == material()
    assert bank["inputs"].dtype == plain["inputs"].dtype
    present = np.asarray(bank["reference_present"])
    assert (
        present.sum() == 30 and not present[np.asarray(cohorts) == "pool_design"].any()
    )
    assert np.isnan(bank["references"][~present]).all()
    # pool rows are interleaved, not a suffix, and not grouped by target
    positions = [i for i, c in enumerate(cohorts) if c == pool_exam.POOL_COHORT]
    assert positions[-1] - positions[0] > 200 and positions != list(
        range(positions[0], positions[0] + 200)
    )
    # nothing but the sealed grid remains once they are set aside
    assert sealed.is_sealed_bank(pool_version.strip_pool(bank))
    assert sealed.is_pool_bank(bank) and not sealed.is_sealed_bank(bank)
    assert not sealed.is_pool_bank(plain)


def test_the_bank_is_deterministic_and_every_copy_of_one_exam_is_the_same_exam(batch):
    first, second = _bank(batch, material()), _bank(batch, material())
    assert first["case_ids"] == second["case_ids"]
    assert (first["inputs"] == second["inputs"]).all()
    assert cd.content_digest(first) == cd.content_digest(second)


def test_a_version_without_a_pool_refuses_one_and_a_pool_version_refuses_none(batch):
    with pytest.raises(source.SealedBankRefused, match="pool_material_mismatch"):
        _bank(batch, material(), version="1.4")
    with pytest.raises(source.SealedBankRefused, match="pool_material_mismatch"):
        _bank(batch, None, version=POOL_VERSION)


def test_the_pool_version_dispatches_to_its_adapter_only_for_a_pool_bank(batch):
    bank = _bank(batch, material())
    chosen = sealed.adapter_for_bank(bank, POOL_VERSION)
    assert chosen.POOL_GRADED and chosen.VERSION == POOL_VERSION
    with pytest.raises(sealed.Refused):
        sealed.adapter_for_bank(source._build(MOTOR, pack, *batch, "1.4"), POOL_VERSION)


# --- the copies and the canonical form -----------------------------------------------------------


def test_the_canonical_bank_is_the_canonical_batch_rebuilt_pool_rows_included(batch):
    document = {**batch[0], "pool": material()}
    records = batch[1]
    bank = source._build(MOTOR, pack, document, records, POOL_VERSION)
    canonical = cd.canonicalize(bank)
    raw, _source_fp, canonical_fp = copy_package.canonical_batch(
        MOTOR, POOL_VERSION, document, records
    )
    carried = __import__("json").loads(raw)
    rebuilt = source._build(
        MOTOR, pack, carried["document"], carried["records"], POOL_VERSION
    )
    assert cd.content_digest(canonical) == cd.content_digest(rebuilt) == canonical_fp
    assert list(canonical["cohorts"]) == list(rebuilt["cohorts"])
    assert (canonical["inputs"] == rebuilt["inputs"]).all()
    assert rebuilt["pool"] == material()


def test_a_validator_copy_carries_the_pool_and_canonicalises_to_the_same_exam(batch):
    document = {**batch[0], "pool": material()}
    records = batch[1]
    raw, _header = copy_package.make_copy(
        MOTOR, POOL_VERSION, document, records, key=b"k" * 32, hotkey="valV3-hotkey"
    )
    carried = __import__("json").loads(raw)
    assert carried["document"]["pool"] == material()
    copied = source._build(
        MOTOR, pack, carried["document"], carried["records"], POOL_VERSION
    )
    original = source._build(MOTOR, pack, document, records, POOL_VERSION)
    assert cd.content_digest(copied) == cd.content_digest(original)
    # a copy's pool rows are renamed and reordered, never changed in value
    assert sorted(map(tuple, copied["inputs"].tolist())) == sorted(
        map(tuple, original["inputs"].tolist())
    )
    assert list(copied["case_ids"]) != list(original["case_ids"])


# --- the adapter's native definition sees the sealed rows only ----------------------------------------


def test_the_pool_adapter_builds_its_native_definition_from_the_sealed_bank(batch):
    bank = _bank(batch, material())
    chosen = sealed.adapter(POOL_VERSION)
    stripped = pool_version.strip_pool(bank)
    train_raw = __import__(
        "carbon.challenge_kit.physical_pack", fromlist=["x"]
    ).public_roles(MOTOR, POOL_VERSION)["train"]
    assert chosen.definition(
        bank=bank, train_raw=train_raw
    ) == sealed._ADAPTER.definition(bank=stripped, train_raw=train_raw)
    assert "pool" not in pool_version.strip_pool(bank)


# --- the whole pack: written, sealed by the receiver's loader, resolved back to the pool bank ------------


def test_the_pool_pack_is_written_sealed_and_resolves_back_to_the_same_pool_bank(
    batch, tmp_path
):
    import json

    from carbon.challenge_validator.evaluation_pack import prepare_pack

    document, records = batch
    carried = {**document, "pool": material()}
    bank = source._build(MOTOR, pack, carried, records, POOL_VERSION)
    root = tmp_path / "pack"
    manifest_path = sealed.write_sealed_pack(
        root, bank, version=POOL_VERSION, inference_image_id="sha256:" + "1" * 64
    )
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["pack_version"].endswith(sealed.PACK_SUFFIX)
    # the score pack registers the two pool gates beside the native ones
    score_pack = json.loads(
        (root / manifest["private"]["score_pack"]["path"]).read_bytes()
    )
    assert score_pack["hard_gates"][-2:] == [
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
    ]
    # the case bank holds every row (cells, probes, pool), one inference's worth
    case_bank_role = (root / manifest["private"]["case_bank"]["path"]).read_bytes()
    assert case_bank_role == pack.private_roles(bank)["case_bank"]
    # a public file never holds the pool's truths
    public_text = (root / manifest["public"]["accuracy_definition"]["path"]).read_text()
    assert "truths" not in public_text and "pool-" not in public_text
    # the receiver's loader seals it, and the sealed batch the pack carries resolves to the same bank
    prepared = prepare_pack(
        root,
        "evaluation-pack.json",
        public_root=root,
        private_root=root,
        challenge_id=MOTOR,
        challenge_version=POOL_VERSION,
    )
    (root / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(carried, records))
    resolved_bank, adapter = source.resolve(
        challenge=MOTOR,
        version=POOL_VERSION,
        selected_pack=prepared.snapshot,
        private_root=root,
        development_adapter=None,
    )
    assert adapter.POOL_GRADED and adapter.VERSION == POOL_VERSION
    assert list(resolved_bank["case_ids"]) == list(bank["case_ids"])
    assert resolved_bank["pool"] == material()


# --- the custody builder script ---------------------------------------------------------------------


def _builder():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts/dev/sealed_exam/pool_pack.py"
    spec = importlib.util.spec_from_file_location("pool_pack_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_custody_builder_writes_the_pool_pack_and_a_digest_only_record(
    batch, tmp_path
):
    import json

    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    out = tmp_path / "out"
    record = _builder().build(
        challenge=MOTOR,
        version=POOL_VERSION,
        batch_dir=plain,
        out_dir=out,
        inference_image_id="sha256:" + "1" * 64,
        material=material(),
    )
    assert record["rows"]["pool"] > 0 and record["rows"]["probes"] > 0
    assert (
        record["rows"]["total"]
        == record["rows"]["pool"] + record["rows"]["probes"] + record["rows"]["cells"]
    )
    assert record["rows"]["cells"] == len(document["cases"])
    assert json.loads((out / "record.json").read_text()) == record
    # the record names digests and counts only: no truths, designs or inputs
    text = json.dumps(record)
    # no truth or design list: the key "designs" (a list), unlike the count "designs_total"
    assert '"truths"' not in text and '"designs"' not in text
    # the carried batch beside the roles is the canonical one and resolves to the pool bank
    carried = source.read_batch(out / "pack")
    assert carried is not None and carried[0]["pool"] == material()


def test_the_custody_builder_refuses_a_batch_that_already_carries_a_pool(
    batch, tmp_path
):
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes({**document, "pool": material()}, records)
    )
    with pytest.raises(SystemExit):
        _builder().build(
            challenge=MOTOR,
            version=POOL_VERSION,
            batch_dir=plain,
            out_dir=tmp_path / "out",
            inference_image_id="sha256:" + "1" * 64,
            material=material(),
        )


# --- how the pool designs become the exam pool rows (counts only) --------------------------------------


def _dup_target(target_id, seed, fixed, designs):
    n = len(DESIGN_INPUTS)
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
        agen=range(len(designs) - 8, len(designs)),
        start=tuple(0.5 for _ in range(n)),
        seed=seed,
    )


def _pool_material(targets, dtype="<f8"):
    return {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "motor",
        "version": POOL_VERSION,
        "input_names": list(NAMES),
        "design_names": list(DESIGN_INPUTS),
        "input_dtype": dtype,
        "set_digest": "sha256:" + "5" * 64,
        "sets": [[pool_grader.dump_pool(t) for t in targets]],
    }


def test_the_row_accounting_matches_the_rows_and_names_each_kind_of_duplicate():
    n = len(DESIGN_INPUTS)
    rng = random.Random(8)
    base = [[rng.random() for _ in range(n)] for _ in range(20)]
    fixed = _fixed(0.0)
    # A2 repeats A1's first 3 designs (same fixed conditions: cross-target duplicates); A3 holds one design twice,
    # 1e-12 apart (distinct as float64, equal as float32: made equal by the quantisation)
    a1 = _dup_target("A1", 1, fixed, base)
    fresh = [[rng.random() for _ in range(n)] for _ in range(17)]
    a2 = _dup_target("A2", 2, fixed, base[:3] + fresh)
    near = [[v + 1e-12 for v in base[5]]]
    more = [[rng.random() for _ in range(n)] for _ in range(18)]
    a3 = _dup_target("A3", 3, _fixed(1.0), [base[5]] + near + more)
    material = _pool_material([a1, a2, a3], dtype="<f4")
    counts = pool_version.row_accounting(material, dtype="<f4")
    rows = pool_version.rows_from_material(material, dtype="<f4", challenge=MOTOR)
    assert counts["targets"] == 3 and counts["designs_total"] == 60
    assert counts["unique_rows"] == len(rows)
    assert counts["designs_total"] - counts["unique_rows"] == (
        counts["dup_within_target"] + counts["dup_across_targets"]
    )
    assert counts["dup_across_targets"] == 3
    assert counts["dup_within_target"] == 1
    assert counts["dup_created_by_quantisation"] == 1
    # in float64 the near pair stays two rows
    exact = pool_version.row_accounting(material, dtype="<f8")
    assert exact["dup_within_target"] == 0 and exact["unique_rows"] == len(rows) + 1
    # counts only
    assert all(type(v) is int for v in counts.values())


def test_the_builder_record_carries_the_accounting(batch, tmp_path):
    import importlib.util

    path = REPOSITORY / "scripts/dev/sealed_exam/pool_pack.py"
    spec = importlib.util.spec_from_file_location("pool_pack_accounting", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    record = builder.build(
        challenge=MOTOR,
        version=POOL_VERSION,
        batch_dir=plain,
        out_dir=tmp_path / "out",
        inference_image_id="sha256:" + "1" * 64,
        material=material(),
    )
    accounting = record["pool_accounting"]
    assert accounting["unique_rows"] == record["rows"]["pool"]
    assert accounting["designs_total"] - accounting["unique_rows"] == (
        accounting["dup_within_target"] + accounting["dup_across_targets"]
    )
