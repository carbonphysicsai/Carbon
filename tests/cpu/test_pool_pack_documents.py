"""pool_pack.py's sealed documents (blocker B2, Wed 11 Nov 2026): a version whose raw registration asks for the coverage
plan (+ sums), the scoring cells, the in-range cases or the variant starts builds only WITH them, carried in the sealed
material under pool_version's keys; a document the registration does not ask for refuses. The grader's own rules
(pool_exam.attach_coverage_plan / attach_physics / attach_variant_starts), checked before a pack is written.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from carbon.scoring import pool_version

ROOT = Path(__file__).resolve().parents[2]


def _pool_pack():
    spec = importlib.util.spec_from_file_location(
        "pool_pack_documents_under_test", ROOT / "scripts/dev/sealed_exam/pool_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _material():
    return {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "motor",
        "version": "9.9",
        "input_names": ["a", "b"],
        "design_names": ["a"],
        "input_dtype": "<f8",
        "set_digest": "sha256:" + "0" * 64,
        "sets": [[{"digest": "x"}]],
    }


def _documents():
    return {
        pool_version.COVERAGE_PLAN: {
            "schema": "carbon.pool.coverage-plan.v1",
            "classes": ["k"],
            "targets": {"t": "k"},
        },
        pool_version.COVERAGE_PLAN_SUMS: "0" * 64 + "  plan.json\n",
        pool_version.SCORING_CELLS: {"schema": "x"},
        pool_version.IN_RANGE_CASES: {"schema": "y"},
        pool_version.VARIANT_STARTS: {"t": []},
    }


def _constants(tmp_path, entry):
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps(
            {
                "schema": pool_version.SCHEMA,
                "versions": {"electric-motor-magnetics 9.9": entry},
            }
        )
    )
    return path


FULL = {
    "optimizer": {
        "coverage_plan_sha256": "HUMAN_INPUT",
        "coverage_plan_sums_sha256": "HUMAN_INPUT",
        "variant_rule": {"x": 1},
    },
    "physics": {"in_range_cases_sha256": "HUMAN_INPUT"},
}


def test_the_table_is_pool_versions_optional_material_keys():
    pack = _pool_pack()
    keys = {row[0] for row in pack.SEALED_DOCUMENTS}
    assert keys == {
        pool_version.COVERAGE_PLAN,
        pool_version.COVERAGE_PLAN_SUMS,
        pool_version.SCORING_CELLS,
        pool_version.IN_RANGE_CASES,
        pool_version.VARIANT_STARTS,
    }


def test_a_registered_version_carries_every_document(tmp_path):
    pack = _pool_pack()
    out = pack._with_documents(
        "electric-motor-magnetics",
        "9.9",
        _material(),
        _documents(),
        constants=_constants(tmp_path, FULL),
    )
    for key, value in _documents().items():
        assert out[key] == value


@pytest.mark.parametrize("missing", sorted(_documents()))
def test_a_registered_version_refuses_each_missing_document(tmp_path, missing):
    pack = _pool_pack()
    docs = {k: v for k, v in _documents().items() if k != missing}
    flag = next(row[1] for row in pack.SEALED_DOCUMENTS if row[0] == missing)
    with pytest.raises(SystemExit, match="give --" + flag):
        pack._with_documents(
            "electric-motor-magnetics",
            "9.9",
            _material(),
            docs,
            constants=_constants(tmp_path, FULL),
        )


@pytest.mark.parametrize("extra", sorted(_documents()))
def test_an_unregistered_document_refuses(tmp_path, extra):
    pack = _pool_pack()
    flag = next(row[1] for row in pack.SEALED_DOCUMENTS if row[0] == extra)
    entry = {"optimizer": {"coverage_plan_sha256": None, "variant_rule": None}}
    with pytest.raises(SystemExit, match="--" + flag + " refused"):
        pack._with_documents(
            "electric-motor-magnetics",
            "9.9",
            _material(),
            {extra: _documents()[extra]},
            constants=_constants(tmp_path, entry),
        )


def test_a_version_registering_none_is_unchanged(tmp_path):
    pack = _pool_pack()
    out = pack._with_documents(
        "electric-motor-magnetics",
        "9.9",
        _material(),
        {},
        constants=_constants(tmp_path, {"optimizer": {}}),
    )
    assert out == _material()


def test_both_1_8_registrations_require_all_five():
    """The real Motor 1.8 and Cooling 1.8 rows (Line D) register a coverage plan, a physics block with in-range cases and
    a variant rule: a pack without the five documents refuses."""
    pack = _pool_pack()
    raw = json.loads(Path(pool_version.CONSTANTS).read_bytes())["versions"]
    for name in ("electric-motor-magnetics 1.8", "chip-cold-plate 1.8"):
        entry = raw[name]
        assert all(
            pack._registered_leaf(entry, row[2]) for row in pack.SEALED_DOCUMENTS
        ), name
