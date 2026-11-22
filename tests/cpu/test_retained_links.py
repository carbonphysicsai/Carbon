"""Retained grade files stored ONCE on disk (owner rule #13; live 116, 19 Nov 2026: GPUYard grew ~2.7 GB/h, the door's own
grade evidence). A counted grade's task root copied its origin's files and its 12.6 MB graded predictions, which were
already on disk byte for byte (the origin's retained files; the inference operation's output). Now such a file is a
HARD LINK to the file it equals (`data.link_once`): the same name, the same bytes, the same digests for every reader and
custody check (no format change, no reader change), stored once. Old task roots (plain copies) and new ones (links) are
read the same way. Fixture doubles only.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_graph_pool_counted_e2e import TASK, _grade, _setup
from test_pool_dual_e2e import (
    case,  # noqa: F401  (the imported case fixture is received by tests)
)

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session.data import link_once

pytestmark = pytest.mark.skipif(os.name != "posix", reason="hard links and modes")


def _same_file(a, b):
    first, second = os.stat(a), os.stat(b)
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def test_identical_bytes_are_linked_and_everything_else_is_written(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(b'{"a": 1}')
    source.chmod(0o644)
    linked = tmp_path / "linked.json"
    assert link_once(source, linked, b'{"a": 1}') is True
    assert _same_file(source, linked) and linked.read_bytes() == b'{"a": 1}'
    assert stat.S_IMODE(linked.stat().st_mode) == 0o600  # owner-only (was 0644)
    # the same call again is a no-op; other bytes at an existing path refuse, as write_once
    assert link_once(source, linked, b'{"a": 1}') is False
    with pytest.raises(ValueError, match="immutable"):
        link_once(source, linked, b'{"a": 2}')
    # other bytes of the same size, no source, a missing source, a link as source: written, never linked
    for name, src in (
        ("other.json", source),
        ("none.json", None),
        ("missing.json", tmp_path / "nope"),
    ):
        target = tmp_path / name
        assert link_once(src, target, b'{"b": 9}') is False
        assert target.read_bytes() == b'{"b": 9}' and not _same_file(source, target)
    pointer = tmp_path / "pointer"
    pointer.symlink_to(source)
    target = tmp_path / "via-link.json"
    assert link_once(pointer, target, b'{"a": 1}') is False
    assert not _same_file(source, target) and not target.is_symlink()
    # candidates are tried in order: the first holding exactly the bytes is linked (a missing file, other bytes of the
    # same size and a link are passed over)
    decoy = tmp_path / "decoy.json"
    decoy.write_bytes(b'{"c": 3}')
    chosen = tmp_path / "chosen.json"
    candidates = (tmp_path / "nope", None, decoy, pointer, source)
    assert link_once(candidates, chosen, b'{"a": 1}') is True
    assert _same_file(source, chosen) and not _same_file(decoy, chosen)
    # no candidate holds the bytes: written
    alone = tmp_path / "alone.json"
    assert link_once((decoy, source), alone, b'{"d": 4}') is False
    assert alone.read_bytes() == b'{"d": 4}' and not _same_file(source, alone)


def test_the_operation_sources_name_only_well_formed_operations(tmp_path):
    provider = type("P", (), {"ledger": type("L", (), {"root": tmp_path})()})()
    op = "operation-" + "a" * 64
    sources = retention._operation_sources(
        provider,
        {
            "build_operation": op,
            "inference_operation": op,
            "timed_operation": "../escape",
        },
    )
    assert sources == {
        "state.npz": tmp_path / op / "snapshot" / "state.npz",
        "predictions.json": tmp_path / op / "snapshot" / "predictions.json",
        "sigma.json": tmp_path
        / op
        / "snapshot"
        / "sigma.json",  # H3g R2: used only when the task kept one
    }
    assert retention._operation_sources(object(), {}) == {}


def test_a_counted_grade_stores_its_origins_files_once_and_every_reader_reads_old_and_new(
    case, tmp_path, monkeypatch  # noqa: F811
):
    """The real retention + counted regrade + custody (`prepare_custody_v5`, `create_entry_v5`) + retry: the origin task
    root (written as before) and the counted grade's task root (its unchanged files linked to the origin's) are read by
    the same code, with the same digests."""
    fixture = _setup(case, tmp_path, monkeypatch)
    result = _grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    origin = fixture.base / TASK
    (root,) = [
        p
        for p in fixture.base.iterdir()
        if p.is_dir() and p.name != TASK and not p.name.endswith(".evaluation")
    ]
    shared = [
        p.name
        for p in root.iterdir()
        if (origin / p.name).exists() and _same_file(p, origin / p.name)
    ]
    # every file the counted grade keeps unchanged from its origin is on disk once
    unchanged = {
        p.name
        for p in root.iterdir()
        if (origin / p.name).exists()
        and p.read_bytes() == (origin / p.name).read_bytes()
    }
    # (this fixture's counted bank and inference re-make the origin's inputs, predictions and receipt byte for byte:
    # those too are the origin's files, not copies)
    assert set(shared) == unchanged
    assert "recipe.json" in shared and "state.npz" in shared
    # the graded predictions are on disk once either way: the origin's file of the same bytes, else the inference
    # operation's own output
    assert (root / "predictions.json").stat().st_nlink >= 2
    # every reader reads the new root as the old: a regrade of the counted grade's own entry reads its retained files by
    # name with their digests (`_regrade_origin`), and the retry re-reads them create-only
    again = _grade(fixture, counted=True)
    assert again["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", again
    for name in shared:
        assert (root / name).read_bytes() == (origin / name).read_bytes()
