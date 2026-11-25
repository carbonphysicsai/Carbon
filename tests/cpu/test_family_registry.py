"""The host-side family registry: add-only, row-wise, sha checked before import, ships empty (v2 ruling row 4033)."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

import carbon
from carbon.challenge_kit import family_registry, version_overlay
from carbon.scoring import copy_derivation, pool_version

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "zz-synthetic"
MODULE = "carbon.zz_family_module"
SOURCE = "IMPORTED = True\n"
TABLES = (
    (pool_version, "KINDS"),
    (copy_derivation, "OPAQUE_BY_CHALLENGE"),
    (version_overlay, "SEALED_TARGET"),
)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(family_registry, "_INSTALLED", {})
    monkeypatch.setattr(family_registry, "_REFUSED", {})
    # a kept row extends the shared tables: each test starts from the code's own
    for module, name in TABLES:
        monkeypatch.setattr(module, name, dict(getattr(module, name)))
    monkeypatch.delitem(sys.modules, MODULE, raising=False)


@pytest.fixture
def module_dir(tmp_path, monkeypatch):
    """A directory searched for `carbon.*` modules beside the package's own."""
    folder = tmp_path / "carbon"
    folder.mkdir()
    (folder / "zz_family_module.py").write_bytes(SOURCE.encode())
    monkeypatch.setattr(carbon, "__path__", [*carbon.__path__, str(folder)])
    return folder


def _row(**changes):
    row = {
        "kind": "zz",
        "opacity": ["case_id"],
        "baseline": {"bounds": {"x": [0.0, 1.0]}, "length_ridge": [1.0, 0.5]},
        "modules": {},
    }
    row.update(changes)
    return row


def _block(source=SOURCE):
    return {"module": MODULE, "sha256": hashlib.sha256(source.encode()).hexdigest()}


def _write(tmp_path, families):
    path = tmp_path / "families.json"
    path.write_text(
        json.dumps({"schema": family_registry.SCHEMA, "families": families})
    )
    return path


def test_the_repository_file_is_empty_and_registers_nothing():
    assert family_registry.load() == {}
    assert family_registry.install() == {}
    assert family_registry.families() == ()
    assert family_registry.family("electric-motor-magnetics") is None


def test_the_opaque_ids_and_builtin_families_are_the_code_s_own():
    assert family_registry._OPAQUE == copy_derivation.OPAQUE
    assert frozenset(copy_derivation.OPAQUE_BY_CHALLENGE) == family_registry.BUILTIN


def test_a_row_registers_a_family_and_reads_back(tmp_path):
    digests = family_registry.install(_write(tmp_path, {FAMILY: _row()}))
    assert set(digests) == {FAMILY} == set(family_registry.families())
    found = family_registry.family(FAMILY)
    assert found == {
        "kind": "zz",
        "opacity": ("case_id",),
        "baseline": _row()["baseline"],
    }
    found["baseline"]["bounds"].clear()  # a caller's copy is its own
    assert family_registry.family(FAMILY)["baseline"] == _row()["baseline"]
    assert family_registry.refused() == {}


def test_install_is_idempotent_and_add_only(tmp_path):
    path = _write(tmp_path, {FAMILY: _row()})
    first = family_registry.install(path)
    assert family_registry.install(path) == first
    changed = _write(tmp_path, {FAMILY: _row(kind="other")})
    assert family_registry.install(changed) == first
    assert family_registry.family(FAMILY)["kind"] == "zz"
    assert FAMILY in family_registry.refused()


@pytest.mark.parametrize("challenge_id", sorted(family_registry.BUILTIN))
def test_a_family_the_code_serves_is_refused(tmp_path, challenge_id):
    family_registry.install(_write(tmp_path, {challenge_id: _row()}))
    assert family_registry.family(challenge_id) is None
    assert challenge_id in family_registry.refused()


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "motor"},
        {"kind": "Zz"},
        {"kind": 1},
        {"opacity": ["row_id"]},
        {"opacity": ["case_id", "case_id"]},
        {"opacity": "case_id"},
        {"opacity": [["case_id"]]},
        {"baseline": {"bounds": {}, "length_ridge": None}},
        {"baseline": {"bounds": {"x": [1.0, 1.0]}, "length_ridge": None}},
        {"baseline": {"bounds": {"x": [0.0, True]}, "length_ridge": None}},
        {"baseline": {"bounds": {"x": [0.0, 10**400]}, "length_ridge": None}},
        {"baseline": {"bounds": {"x": [0.0, 1.0]}, "length_ridge": [10**400, 1]}},
        {"baseline": {"bounds": {"x": [0.0, float("inf")]}, "length_ridge": None}},
        {"baseline": {"bounds": {"x": [0.0, 1.0]}, "length_ridge": [1.0, 0.0]}},
        {"baseline": {"bounds": {"x": [0.0, 1.0]}}},
        {"modules": {"unknown_role": _block()}},
        {"modules": {"bank": {"module": MODULE}}},
        {"modules": {"bank": {"module": "os", "sha256": "0" * 64}}},
        {"modules": {"bank": {"module": "carbon.no_such_module", "sha256": "0" * 64}}},
        {"extra": 1},
    ],
)
def test_a_bad_row_refuses_itself_and_no_other(tmp_path, bad):
    path = _write(tmp_path, {"zz-bad": _row(**bad), FAMILY: _row()})
    family_registry.install(path)
    assert family_registry.families() == (FAMILY,)
    assert set(family_registry.refused()) == {"zz-bad"}


def test_two_families_never_share_a_kind(tmp_path):
    family_registry.install(_write(tmp_path, {"zz-a": _row(), "zz-b": _row()}))
    assert family_registry.families() == ("zz-a",)
    assert set(family_registry.refused()) == {"zz-b"}


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"[]",
        b"[" * 100_000,
        b'{"schema": "other", "families": {}}',
        b'{"schema": "carbon.challenge-kit.family-registry.v1"}',
        b'{"schema": "carbon.challenge-kit.family-registry.v1", "families": {"a": {}, "a": {}}}',
    ],
)
def test_an_unreadable_file_refuses_whole(tmp_path, raw):
    path = tmp_path / "families.json"
    path.write_bytes(raw)
    with pytest.raises(family_registry.FamilyRefused):
        family_registry.install(path)
    assert family_registry.families() == ()


def test_a_module_is_hashed_before_it_is_imported(tmp_path, module_dir):
    row = _row(modules={"sealed_kit": _block()})
    family_registry.install(_write(tmp_path, {FAMILY: row}))
    assert MODULE not in sys.modules  # install never imports
    (module_dir / "zz_family_module.py").write_bytes(b"raise SystemExit('ran')\n")
    with pytest.raises(family_registry.FamilyRefused, match="sha256 differs"):
        family_registry.module(FAMILY, "sealed_kit")
    assert MODULE not in sys.modules
    # CRLF reads as LF
    (module_dir / "zz_family_module.py").write_bytes(
        SOURCE.replace("\n", "\r\n").encode()
    )
    assert family_registry.module(FAMILY, "sealed_kit").IMPORTED is True


def test_a_row_whose_module_differs_is_refused_at_install(tmp_path, module_dir):
    row = _row(modules={"bank": _block("another file\n")})
    family_registry.install(_write(tmp_path, {FAMILY: row}))
    assert family_registry.family(FAMILY) is None
    assert MODULE not in sys.modules


def test_a_missing_role_or_family_refuses(tmp_path):
    family_registry.install(_write(tmp_path, {FAMILY: _row()}))
    for name, role in ((FAMILY, "bank"), (FAMILY, "other"), ("zz-none", "bank")):
        with pytest.raises(family_registry.FamilyRefused):
            family_registry.module(name, role)


def test_the_row_digest_moves_with_any_field(tmp_path):
    base = family_registry.canonical_digest(_row())
    moved = copy.deepcopy(_row())
    moved["opacity"] = []
    assert family_registry.canonical_digest(moved) != base


def test_the_registry_is_not_a_worker_build_input():
    inputs = (ROOT / "carbon/reconstruction/worker/build_inputs.txt").read_text()
    assert "family_registry" not in inputs
