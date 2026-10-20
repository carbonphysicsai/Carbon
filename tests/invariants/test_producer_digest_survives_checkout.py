"""A dual producer's identity is the same on every checkout of a commit
(Validator, 2026-10-20). `producer_digest` hashes working-tree bytes, so
CRLF is read as LF there, and `.gitattributes` keeps git from converting
any file it hashes. No committed (path, sha256) pin names these files, so
test_pinned_files_survive_checkout cannot see them."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.scoring import battery_dual_pack as battery
from carbon.scoring import cooling_dual_pack as cooling
from carbon.scoring import f02_dual_pack as f02
from carbon.scoring import f08_dual_pack as f08
from carbon.scoring import motor_dual_pack as motor
from carbon.scoring import physical_dual_pack as physical

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
SCORING = Path(physical.__file__).parent
ADAPTERS = (battery, cooling, f02, f08, motor)


def _hashed():
    return sorted({*physical._SHARED_FILES, *(n for a in ADAPTERS for n in a.FILES)})


def test_a_crlf_copy_has_the_lf_trees_digest(tmp_path, monkeypatch):
    lf = {a.CHALLENGE: physical.producer_digest(a) for a in ADAPTERS}
    for name in _hashed():
        raw = (SCORING / name).read_bytes()
        assert b"\r\n" not in raw, name
        (tmp_path / name).write_bytes(raw.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(physical, "__file__", str(tmp_path / "physical_dual_pack.py"))
    assert {a.CHALLENGE: physical.producer_digest(a) for a in ADAPTERS} == lf


def test_an_autocrlf_checkout_never_converts_a_hashed_file():
    # Fail, never skip, when git or HEAD is missing.
    assert shutil.which("git"), "git is required for this invariant"
    converted = []
    for name in _hashed():
        path = f"carbon/scoring/{name}"
        committed = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "blob", f"HEAD:{path}"],
            capture_output=True,
            check=True,
        ).stdout
        checkout = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "-c",
                "core.autocrlf=true",
                "-c",
                "core.eol=crlf",
                "cat-file",
                "--filters",
                f"HEAD:{path}",
            ],
            capture_output=True,
            check=True,
        ).stdout
        if checkout != committed:
            converted.append(path)
    assert not converted, f"checkout converts producer files: {converted}"
    assert len(_hashed()) == 12
