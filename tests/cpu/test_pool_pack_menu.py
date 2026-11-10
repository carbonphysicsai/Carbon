"""The custody pack build of a menu-D version (Graphite-B G2/G3, 7 Nov): design-optimum's menus ride the pool
material in the door's naming, only under a registration naming exactly their record shas, and the in-pack baseline's
graded measure gets the menu keys + a FRESH baseline run for the keyed re-check (cleared after). Every task, record and
key is a SYNTHETIC fixture (test_menu_score's analytic toy)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_pool_menu import KEY, _do_pair_two_duties, _mk_rule

from carbon.scoring import pool_exam, pool_menu, pool_version

_SPEC = importlib.util.spec_from_file_location(
    "pool_pack_under_test", HERE.parents[1] / "scripts/dev/sealed_exam/pool_pack.py"
)
pool_pack = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pool_pack)

NAMES = {"input_names": ["cond", "x", "y"], "design_names": ["x", "y"]}


def _menu_dir(tmp_path):
    problem, record = _do_pair_two_duties()
    folder = tmp_path / "menus"
    folder.mkdir()
    (folder / "task-1.problem.json").write_text(json.dumps(problem), encoding="utf-8")
    (folder / "task-1.menu.json").write_text(json.dumps(record), encoding="utf-8")
    return folder


def test_a_menu_dir_pairs_every_record_with_its_problem(tmp_path):
    folder = _menu_dir(tmp_path)
    (pair,) = pool_pack._menu_pairs(folder)
    assert pair[0]["target_id"] == "task-1"
    (folder / "orphan.problem.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="problem files with no menu"):
        pool_pack._menu_pairs(folder)
    (folder / "orphan.problem.json").unlink()
    (folder / "task-1.problem.json").unlink()
    with pytest.raises(SystemExit, match="has no task-1.problem.json"):
        pool_pack._menu_pairs(folder)


def test_the_build_refuses_unless_the_registration_names_exactly_these_shas(
    tmp_path, monkeypatch
):
    folder = _menu_dir(tmp_path)
    material = {"input_dtype": "<f8", **NAMES}
    _m, shas = pool_menu.menu_material(pool_pack._menu_pairs(folder), **NAMES)
    monkeypatch.setattr(pool_version, "check_material", lambda m: m)
    monkeypatch.setattr(pool_version, "registered_menu", lambda c, v: None)
    with pytest.raises(SystemExit, match="register these menu record shas"):
        pool_pack._with_menu("toy", "1.8", material, folder)
    monkeypatch.setattr(
        pool_version, "registered_menu", lambda c, v: _mk_rule((("task-1", "a" * 64),))
    )
    with pytest.raises(SystemExit, match="register these menu record shas"):
        pool_pack._with_menu("toy", "1.8", material, folder)
    monkeypatch.setattr(
        pool_version,
        "registered_menu",
        lambda c, v: _mk_rule(tuple(sorted(shas.items()))),
    )
    with_menu, got = pool_pack._with_menu("toy", "1.8", material, folder)
    assert got == shas
    assert with_menu["menu"]["tasks"][0]["problem"]["objective"] == "over/f"


def test_the_in_pack_baseline_answers_the_recheck_with_a_fresh_run():
    calls = []

    def pool_baseline(*, bank_rows, names, sample_count):
        calls.append((len(bank_rows), names, sample_count))
        return [[float(r["inputs"]["i"])] for r in bank_rows], [0.1]

    recheck = pool_pack._baseline_recheck(SimpleNamespace(pool_baseline=pool_baseline))
    rows = [{"inputs": {"i": i}} for i in range(6)]
    assert recheck([4, 1], rows, ("n",)) == [[4.0], [1.0]]
    assert calls == [(2, ("n",), 1)]
    with pytest.raises(SystemExit, match="no pool_baseline"):
        pool_pack._baseline_recheck(SimpleNamespace())


@pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only key file modes are POSIX"
)
def test_the_keys_and_the_recheck_exist_only_inside_the_build(tmp_path):
    key = tmp_path / "k_crown"
    key.write_bytes(b"c" * 32)
    key.chmod(0o600)

    def pool_baseline(*, bank_rows, sample_count):
        return [[0.0] for _ in bank_rows], [0.1]

    module = SimpleNamespace(pool_baseline=pool_baseline)
    with pool_pack._menu_keys(module, {"task-1": "a" * 64}, key):
        assert len(pool_menu.active_key()) == 32
        staged = pool_menu.take_rowcheck(
            [{"inputs": {}}] * 10, _mk_rule((("task-1", "a" * 64),)), KEY
        )
        assert len(staged["positions"]) == 8 and staged["outputs"] == [[0.0]] * 8
    with pytest.raises(pool_exam.ExamRefused):
        pool_menu.active_key()
    assert pool_menu.take_rowcheck([{}] * 3, _mk_rule((("t", "a" * 64),)), KEY) is None


def test_a_non_menu_build_stages_nothing_and_a_menu_build_needs_the_key():
    with pool_pack._menu_keys(SimpleNamespace(), None, None):
        assert (
            pool_menu.take_rowcheck([{}] * 3, _mk_rule((("t", "a" * 64),)), KEY) is None
        )
    keys = pool_pack._menu_keys(SimpleNamespace(), {"task-1": "a" * 64}, None)
    with pytest.raises(SystemExit, match="needs --crown-key-file"):
        keys.__enter__()
