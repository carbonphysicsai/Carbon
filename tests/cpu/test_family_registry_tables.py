"""A family registered by data extends the shared tables add-only, and moves no producer byte (owner G-LEAD-97).

Claims: with no row (the committed file) every table and every lookup is what main had, and no scoring module is imported
by the registry; a registered family is in each table and an unregistered one in none; nothing a table holds is replaced;
a refused row adds nothing; the producer files and the worker image inputs are not this head's. Synthetic values only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_kit import family_registry, version_overlay
from carbon.challenge_registry import pinned_module
from carbon.scoring import (
    copy_derivation,
    physical_dual_pack,
    pool_baseline,
    pool_version,
)

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "zz-synthetic"
KIT = "carbon.challenge_kit.f02_sealed_pack"
GRADER = "carbon.scoring.f02_sealed_dual_pack"
ALL = ("case_id", "design_id", "condition_id")
LIVE_KINDS = {
    "f08-ribbed-bracket": "f08",
    "f02": "f02",
    "electric-motor-magnetics": "motor",
    "chip-cold-plate": "cooling",
}
LIVE_OPACITY = {
    "electric-motor-magnetics": ALL,
    "chip-cold-plate": ALL,
    "f08-ribbed-bracket": ALL,
    "f02": (),
    "battery-fastcharge-ageing-development-v1": (),
}
LIVE_TARGETS = {
    "electric-motor-magnetics": "carbon.scoring.motor_sealed_dual_pack",
    "f02": "carbon.scoring.f02_sealed_dual_pack",
    "f08-ribbed-bracket": "carbon.scoring.f08_sealed_dual_pack",
    "chip-cold-plate": "carbon.scoring.cooling_encoded_dual_pack",
}
TABLES = (
    (pool_version, "KINDS", LIVE_KINDS),
    (copy_derivation, "OPAQUE_BY_CHALLENGE", LIVE_OPACITY),
    (version_overlay, "SEALED_TARGET", LIVE_TARGETS),
)


def _block(name):
    return {"module": name, "sha256": pinned_module.file_sha256(name)}


def _row(**changes):
    return {
        "kind": "zzsynthetic",
        "opacity": ["case_id"],
        "baseline": {
            "bounds": {"b": [0.0, 1.0], "a": [-2.0, 2.0]},
            "length_ridge": [3.0, 0.01],
        },
        "modules": {"sealed_kit": _block(KIT), "sealed_grader": _block(GRADER)},
        **changes,
    }


@pytest.fixture
def tables(monkeypatch):
    for module, name, _live in TABLES:
        monkeypatch.setattr(module, name, dict(getattr(module, name)))
    monkeypatch.setattr(family_registry, "_INSTALLED", {})
    monkeypatch.setattr(family_registry, "_REFUSED", {})


def _install(tmp_path, families):
    path = tmp_path / "families.json"
    path.write_text(
        json.dumps({"schema": family_registry.SCHEMA, "families": families})
    )
    return family_registry.install(path=path)


def test_the_committed_file_registers_no_family_and_every_table_is_the_code_s(tables):
    assert family_registry.load() == {} and family_registry.families() == ()
    for module, name, live in TABLES:
        assert getattr(module, name) == live, name


def test_every_live_kind_keeps_its_registered_fit():
    live = {"f08": (2.0, 1e-4), "motor": (4.0, 1e-4), "cooling": None, "f02": None}
    assert {k: pool_baseline._length_ridge(k) for k in live} == live
    assert frozenset(live) == pool_baseline.CODE_KINDS


def test_the_registry_alone_loads_neither_table_s_module():
    program = (
        "import sys; from carbon.challenge_kit import family_registry; "
        "names = ('carbon.scoring.copy_derivation', 'carbon.scoring.pool_version'); "
        "print([m for m in names if m in sys.modules])"
    )
    done = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    assert done.stdout.strip() == "[]"


def test_a_registered_family_is_in_each_table(tables, tmp_path):
    assert set(_install(tmp_path, {FAMILY: _row()})) == {FAMILY}
    assert pool_version.KINDS[FAMILY] == "zzsynthetic"
    assert copy_derivation.opaque_for(FAMILY) == ("case_id",)
    assert version_overlay.SEALED_TARGET[FAMILY] == GRADER
    for module, name, live in TABLES:
        kept = {k: v for k, v in getattr(module, name).items() if k != FAMILY}
        assert kept == live, name
    # its declared baseline is its row's, in the row's own order
    assert pool_baseline.declared_bounds("zzsynthetic", "0.1") == {
        "b": (0.0, 1.0),
        "a": (-2.0, 2.0),
    }
    assert pool_baseline._length_ridge("zzsynthetic") == (3.0, 0.01)
    # idempotent
    assert set(_install(tmp_path, {FAMILY: _row()})) == {FAMILY}


def test_a_family_with_no_sealed_grader_names_no_sealed_target(tables, tmp_path):
    _install(tmp_path, {FAMILY: _row(modules={"sealed_kit": _block(KIT)})})
    assert FAMILY in pool_version.KINDS and FAMILY not in version_overlay.SEALED_TARGET


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "motor"},
        {"opacity": ["nothing"]},
        {"modules": {"sealed_grader": {"module": GRADER, "sha256": "0" * 64}}},
        {"baseline": {"bounds": {}, "length_ridge": None}},
    ],
)
def test_a_refused_row_adds_nothing(tables, tmp_path, change):
    assert _install(tmp_path, {FAMILY: _row(**change)}) == {}
    assert FAMILY in family_registry.refused()
    for module, name, live in TABLES:
        assert getattr(module, name) == live, name


@pytest.mark.parametrize("challenge", sorted(LIVE_KINDS))
def test_a_family_the_code_serves_is_never_replaced(tables, tmp_path, challenge):
    assert _install(tmp_path, {challenge: _row()}) == {}
    for module, name, live in TABLES:
        assert getattr(module, name) == live, name


def test_a_name_a_table_holds_already_is_refused_whole(tables, tmp_path, monkeypatch):
    monkeypatch.setitem(copy_derivation.OPAQUE_BY_CHALLENGE, FAMILY, ("design_id",))
    assert _install(tmp_path, {FAMILY: _row()}) == {}
    assert FAMILY not in pool_version.KINDS
    assert copy_derivation.OPAQUE_BY_CHALLENGE[FAMILY] == ("design_id",)


def test_an_unregistered_family_is_refused_typed(tables):
    with pytest.raises(copy_derivation.CopyRefused) as refused:
        copy_derivation.opaque_for("no-such-family")
    assert refused.value.code == "copy_challenge_unregistered"
    assert "no-such-family" not in pool_version.KINDS
    with pytest.raises(pool_baseline.PoolBaselineRefused):
        pool_baseline.declared_bounds("nosuchkind", "0.1")


def test_no_producer_or_image_file_is_the_registry_s():
    """The files a pack's producer digest is made of never name the registry, so registering a family moves none."""
    for name in physical_dual_pack._SHARED_FILES:
        text = (ROOT / "carbon" / "scoring" / name).read_text(encoding="utf-8")
        assert "family_registry" not in text, name
    inputs = (ROOT / "carbon/reconstruction/worker/build_inputs.txt").read_text(
        encoding="utf-8"
    )
    assert "family_registry" not in inputs
