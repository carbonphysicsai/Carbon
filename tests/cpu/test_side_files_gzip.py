"""H3a (owner rule #13; Lead pick 20 Nov 2026): a grade's subset-repeat and menu row-check side files are kept as
deterministic gzip and read back as exactly their own bytes; a side file written before (plain ``.json``) is read as
before; every digest that names them stays over the uncompressed bytes."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention

ROOT = Path(__file__).resolve().parents[2]
RAW = json.dumps(
    {"schema": "carbon.menu-rowcheck.v1", "positions": list(range(200))}
).encode()


def test_a_side_file_is_written_gzipped_and_read_as_its_own_bytes(tmp_path):
    path = tmp_path / "menu-rowcheck-0123456789abcdef.json"
    assert not retention._side_exists(path)
    retention._write_side(path, RAW)
    assert not path.exists() and retention._side_gz(path).exists()
    assert retention._side_exists(path)
    assert retention._side_bytes(path, 10**6) == RAW
    packed = retention._side_gz(path).read_bytes()
    assert len(packed) < len(RAW)
    # deterministic: the same content gives the same bytes anywhere (no time, no name in the header)
    assert packed == gzip.compress(RAW, compresslevel=6, mtime=0)
    # write-once: the same bytes again are accepted, other bytes refused
    retention._write_side(path, RAW)
    with pytest.raises(ValueError):
        retention._write_side(path, RAW + b" ")


def test_a_side_file_written_before_is_read_as_before(tmp_path):
    path = tmp_path / "subset-repeat-0123456789abcdef.json"
    path.write_bytes(RAW)
    assert retention._side_exists(path)
    assert retention._side_bytes(path, 10**6) == RAW


def test_a_broken_or_oversized_side_file_is_carbons_unavailable(tmp_path):
    path = tmp_path / "subset-repeat-0123456789abcdef.json"
    retention._side_gz(path).write_bytes(b"not gzip")
    with pytest.raises(retention.RetentionUnavailable):
        retention._side_bytes(path, 10**6)
    other = tmp_path / "menu-rowcheck-fedcba9876543210.json"
    retention._write_side(other, RAW)
    with pytest.raises(retention.RetentionUnavailable):
        retention._side_bytes(
            other, len(RAW) - 1
        )  # the decompressed bytes are bounded too


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_breakdown_tools_read_a_gzipped_side_file_and_skip_the_basis_file(tmp_path):
    king = _module(
        "king_grade_breakdown", ROOT / "scripts" / "dev" / "king_grade_breakdown.py"
    )
    backfill = _module(
        "grade_breakdown_backfill",
        ROOT / "scripts" / "dev" / "grade_breakdown_backfill.py",
    )
    folder = tmp_path / "rtsk_x.evaluation"
    folder.mkdir()
    side = folder / "menu-rowcheck-0123456789abcdef.json"
    retention._write_side(side, RAW)
    (folder / "menu-rowcheck-basis-0123456789abcdef.json").write_text("{}")
    found = backfill._one(
        folder,
        "menu-rowcheck-*.json*",
        "rowcheck_missing",
        exclude="menu-rowcheck-basis-",
    )
    assert found == retention._side_gz(side)
    assert king._read_file(found) == RAW
    assert (
        hashlib.sha256(king._read_file(found)).digest() == hashlib.sha256(RAW).digest()
    )
