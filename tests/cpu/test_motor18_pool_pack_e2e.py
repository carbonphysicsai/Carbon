"""END TO END: a FULL `pool_pack.build` of a SYNTHETIC Motor 1.8 pack on the path the custody P3 runs (Lead, 12 Nov: every
seam the scratch P3 found one run at a time must surface here first). Plain A batch -> the predecessor's plain bank ->
sealed documents -> the menu dir under its registration -> canonical batch -> the 1.8 bank through the kit's own probe
path (menu rows included) -> Motor 1.8's own writer -> record. Only the registration FILE is redirected (a copy of the
real pool_constants.json whose Motor 1.8 row has its last open leaves set to labelled SYNTHETIC values and its menu
shas set to this fixture's); nothing on the build path is stubbed. Every target, design, truth, menu, key and document
here is a synthetic fixture, never a production value.
"""

from __future__ import annotations

import copy
import functools
import importlib.util
import json
import math
import os
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from test_pool_menu import _do_pair_two_duties

from carbon.motor_grid_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
from carbon.scoring import pool_exam, pool_grader, pool_version
from carbon.scoring import sealed_batch_source as source

importlib.import_module("carbon.challenge_kit.version_registry")  # arms the 1.8 overlay


@pytest.fixture(scope="module")
def batch():
    """The plain Motor A batch: the same synthetic grid batch test_pool_pack builds (its recipe, seed 3)."""
    import random as _random

    from test_motor_sealed_family import records_for

    from carbon.challenge_validator import motor_sealed_grid as grid
    from carbon.motor_grid_exam import population

    cases, _ = population.draw(_random.Random(3), population.CELLS)
    document = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    return document, [dict(r, wall_s=1.5) for r in records_for(document)]


MOTOR = "electric-motor-magnetics"
VERSION = "1.8"
NAMES = [*DESIGN_INPUTS, *CONDITION_INPUTS]
_SPEC = importlib.util.spec_from_file_location(
    "pool_pack_motor18_e2e", ROOT / "scripts/dev/sealed_exam/pool_pack.py"
)
pool_pack = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pool_pack)


def _six(design2):
    """The toy's 2-D design placed in Motor's six design dimensions (the other four held at 0.5)."""
    return [design2[0], design2[1], 0.5, 0.5, 0.5, 0.5]


def _menu_dir(tmp_path):
    problem, record = _do_pair_two_duties()
    problem = copy.deepcopy(problem)
    problem["box"] = [[0.0, 1.0]] * len(DESIGN_INPUTS)
    problem["duties"] = {
        "over": {CONDITION_INPUTS[0]: 10.0, CONDITION_INPUTS[1]: 30.0},
        "rated": {CONDITION_INPUTS[0]: 5.0, CONDITION_INPUTS[1]: 0.0},
    }
    record = copy.deepcopy(record)
    for row in record["pool"]:
        row["design"] = _six(row["design"])
    folder = tmp_path / "menus"
    folder.mkdir()
    # three tasks: the registration's minimum (pool_menu MIN_TASKS); the real Motor 1.8 menu has four
    for n in (1, 2, 3):
        task = f"task-{n}"
        (folder / f"{task}.problem.json").write_text(
            json.dumps({**problem, "target_id": task}), encoding="utf-8"
        )
        (folder / f"{task}.menu.json").write_text(
            json.dumps({**record, "task_id": task}), encoding="utf-8"
        )
    return folder


def _target(target_id, seed, fixed):
    rng = random.Random(seed)
    designs = [[rng.random() for _ in DESIGN_INPUTS] for _ in range(16)]
    return pool_grader.build_accuracy_target(
        target_id=target_id,
        conditions={"target_id": target_id, "fixed": fixed},
        outputs=("f", "g"),
        u={"f": 0.01, "g": 0.01},
        box=tuple((0.0, 1.0) for _ in DESIGN_INPUTS),
        designs=designs,
        truths=[{"f": sum(d), "g": sum(x * x for x in d)} for d in designs],
    )


def _material():
    fixed = lambda a, b: {CONDITION_INPUTS[0]: a, CONDITION_INPUTS[1]: b}
    return {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "motor",
        "version": VERSION,
        "input_names": list(NAMES),
        "design_names": list(DESIGN_INPUTS),
        "input_dtype": "<f8",
        "set_digest": "sha256:" + "5" * 64,
        "sets": [
            [pool_grader.dump_pool(_target("A1", 1, fixed(8.0, 10.0)))],
            [pool_grader.dump_pool(_target("B1", 2, fixed(12.0, 20.0)))],
        ],
    }


def _documents():
    plan = {
        "schema": "carbon.pool.coverage-plan.v1",
        "classes": ["H-1", "H-3a"],
        "targets": {"A1": "H-1", "B1": "H-3a"},
    }
    return {
        pool_version.COVERAGE_PLAN: plan,
        pool_version.COVERAGE_PLAN_SUMS: "0" * 64 + "  coverage-plan.json\n",
        pool_version.SCORING_CELLS: {"schema": "fixture.scoring-cells"},
        pool_version.IN_RANGE_CASES: {"schema": "fixture.in-range-cases"},
    }


def _registration(tmp_path, menu_shas):
    """A copy of the REAL pool_constants.json with Motor 1.8's open leaves set to labelled SYNTHETIC values."""
    document = json.loads(
        (ROOT / "scripts/validator_host_classes/pool_constants.json").read_bytes()
    )
    row = document["versions"][f"{MOTOR} {VERSION}"]
    row["menu"]["records_sha256"] = dict(menu_shas)
    row["menu"]["rowcheck"] = {"rel_tol": 0.0, "abs_tol": 1e-12, "subset": 2}
    row["honesty"]["scale"] = 1.0
    row["fit_breaker"]["d_zero"]["dv_proof_sha256"] = "d" * 64
    assert "HUMAN_INPUT" not in json.dumps(
        row
    ), "the fixture must close every open leaf"
    path = tmp_path / "pool_constants.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def registered(tmp_path, monkeypatch):
    menus = _menu_dir(tmp_path)
    shas = pool_pack.menu_shas(MOTOR, VERSION, menus)
    path = _registration(tmp_path, shas)
    monkeypatch.setattr(pool_version, "CONSTANTS", path)
    for name in ("registered_policies", "registered_menu", "registered_a_multiplier"):
        original = getattr(pool_version, name)
        monkeypatch.setattr(pool_version, name, functools.partial(original, path=path))
    key = tmp_path / "k_crown"
    key.write_bytes(bytes(range(32)))
    os.chmod(key, 0o600)
    return menus, key, shas


def test_a_full_motor_1_8_pool_pack_builds_end_to_end(batch, tmp_path, registered):
    menus, key, shas = registered
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    out = tmp_path / "out"
    record = pool_pack.build(
        challenge=MOTOR,
        version=VERSION,
        batch_dir=plain,
        out_dir=out,
        inference_image_id="sha256:" + "1" * 64,
        material=_material(),
        menu_dir=menus,
        crown_key_file=key,
        documents=_documents(),
    )
    rows = record["rows"]
    assert rows["cells"] == len(document["cases"]) and rows["probes"] > 0
    # 2 targets x 16 designs + the menu's (design x duty) rows, all as pool rows
    assert rows["pool"] > 32
    assert rows["total"] == rows["pool"] + rows["probes"] + rows["cells"]
    assert record["menu"] == {"tasks": 3, "records_sha256": shas}
    # the pack resolves back to a Motor 1.8 pool bank with its grader
    carried = source.read_batch(out / "pack")
    assert carried is not None and carried[0]["pool"]["version"] == VERSION
    assert pool_version.MENU in carried[0]["pool"]
    # the door's side: the written pack's bank rebuilds (menu rows and all) and finds Motor 1.8's own grader
    bank = source._build(MOTOR, source._kit(MOTOR), carried[0], carried[1], VERSION)
    assert len(bank["case_ids"]) == rows["total"]
    adapter = source._adapter(MOTOR, bank, VERSION, None)
    assert adapter is not None and adapter.VERSION == VERSION
    assert math.isfinite(len(json.dumps(record)))
    text = json.dumps(record)
    assert '"truths"' not in text and '"design"' not in text
    with pytest.raises(pool_exam.ExamRefused):
        pool_version.rows_from_material(
            carried[0]["pool"], dtype="<f8", challenge="cooling"
        )
