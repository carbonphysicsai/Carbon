"""v2 RE-RULING #5: which changed grading paths a door's served version never reads (`grading_scope.not_served`).

The receiver's M2 migration and the release precheck (`exam_identity.py`) share the one verdict. The changes are built
as commits on this checkout's HEAD in a shared, checkout-free clone, so the real grading rule, the real import closure
and the real dynamic-site table judge them.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_validator import direct_receiver as dr
from carbon.challenge_validator import grading_scope as gs
from tests.cpu.test_owner_manifest_migration import Ledger, _manifest

ROOT = Path(dr.__file__).resolve().parents[2]
CROWN = "scripts/validator_host_classes/crown_official_score.json"
SERVED = "electric-motor-magnetics 1.8"
CHALLENGE = {"id": "electric-motor-magnetics", "version": "1.8"}
PACK = "a" * 64


def _git(root, *args, data=None, env=None):
    # release 22 Nov 01:25:43Z: in the canonical container the files' owner is not the container user, and a --shared
    # clone opens ROOT/.git, which the container's safe.directory entry (the worktree) does not cover: trust it for this
    # test's own read-only clones only (the fixture's repos are throw-away tmp clones; nothing is written to ROOT)
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(root), *args],
        input=data,
        capture_output=True,
        check=True,
        env={**os.environ, **(env or {})},
    ).stdout


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "exam_identity_scope_tool", ROOT / "scripts/dev/release/exam_identity.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """``(clone, base, commit)``: ``commit({path: bytes | None})`` makes a child of ``base`` (None deletes)."""
    clone = tmp_path_factory.mktemp("scope") / "clone"
    _git(ROOT, "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(clone))
    base = _git(ROOT, "rev-parse", "HEAD").decode().strip()
    index = str(clone.parent / "index")
    env = {
        "GIT_INDEX_FILE": index,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def commit(files):
        _git(clone, "read-tree", base, env=env)
        for path, body in files.items():
            if body is None:
                _git(clone, "update-index", "--force-remove", "--", path, env=env)
                continue
            oid = (
                _git(clone, "hash-object", "-w", "--stdin", data=body).decode().strip()
            )
            _git(
                clone,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{oid},{path}",
                env=env,
            )
        tree = _git(clone, "write-tree", env=env).decode().strip()
        return (
            _git(clone, "commit-tree", tree, "-p", base, "-m", "probe", env=env)
            .decode()
            .strip()
        )

    return clone, base, commit


def _crown(**changes):
    doc = json.loads((ROOT / CROWN).read_bytes())
    doc["versions"].update(changes.pop("versions", {}))
    doc.update(changes)
    return (json.dumps(doc, indent=2) + "\n").encode()


def _scope(repo, files, served=(SERVED,)):
    clone, base, commit = repo
    new = commit(files)
    return gs.scope(clone, base, new, sorted(files), frozenset(served), dr.grading_path)


# -- (1) keyed registries ----------------------------------------------------------------------------------------------


def test_the_keyed_allow_list_is_the_crown_registry_and_it_is_keyed_by_pair():
    assert gs.KEYED_JSON == {CROWN: ("versions",)}
    assert dr.grading_path(CROWN)
    versions = json.loads((ROOT / CROWN).read_bytes())["versions"]
    assert versions and all(gs.PAIR.fullmatch(key) for key in versions)
    assert SERVED in versions


def test_another_pairs_entry_is_not_served(repo):
    verdict = _scope(
        repo,
        {CROWN: _crown(versions={"electric-motor-magnetics 1.9": {"margin": 0.01}})},
    )
    assert verdict == {CROWN: gs.KEYED_OTHER}


@pytest.mark.parametrize(
    "body, served, reason",
    [
        # the served pair's own entry
        (
            _crown(versions={SERVED: {"margin": 0.02}}),
            (SERVED,),
            "global:served_entry_changed",
        ),
        # a served pair with no entry: its entry is not 'present'
        (
            _crown(versions={"f02 2.6": {"margin": 0.01}}),
            ("f02 2.5",),
            "global:served_entry_absent",
        ),
        # another top-level field moved with the other pair's entry
        (
            _crown(source="x", versions={"f02 2.6": {"margin": 0.01}}),
            (SERVED,),
            "global:other_field_changed",
        ),
        # an entry keyed otherwise (a GPU class, a family): GLOBAL
        (
            _crown(versions={"A100": {"margin": 0.01}}),
            (SERVED,),
            "global:entry_keyed_otherwise",
        ),
        # layout only: no entry changed, so not a change confined to other pairs' entries
        (
            json.dumps(json.loads((ROOT / CROWN).read_bytes())).encode(),
            (SERVED,),
            "global:no_entry_changed",
        ),
        (b"{not json", (SERVED,), "global:json_unreadable"),
        (
            b'{"schema": 1, "schema": 2, "versions": {}}',
            (SERVED,),
            "global:duplicate_key",
        ),
        (b'{"schema": NaN, "versions": {}}', (SERVED,), "global:non_finite"),
    ],
)
def test_every_other_keyed_change_is_global(repo, body, served, reason):
    assert _scope(repo, {CROWN: body}, served) == {CROWN: reason}


def test_an_unknown_or_otherwise_keyed_json_is_global(repo):
    path = "carbon/reconstruction/construction_promotions.json"
    body = (ROOT / path).read_bytes().rstrip() + b"\n\n"
    assert _scope(repo, {path: body}) == {path: "global:not_a_keyed_registry"}
    assert _scope(repo, {CROWN: None}) == {
        CROWN: "global:added_deleted_or_not_a_regular_file"
    }


# -- (2) pure .py additions --------------------------------------------------------------------------------------------


def test_each_addition_rule(repo):
    exam_cap = "carbon/challenge_validator/exam_cap.py"
    files = {
        "carbon/scoring/zz_scope_alone.py": b"VALUE = 1\n",
        # imported statically by an existing (here: a non-grading) file
        "carbon/scoring/zz_scope_imported.py": b"VALUE = 1\n",
        exam_cap: (ROOT / exam_cap).read_bytes()
        + b"\nfrom carbon.scoring import zz_scope_imported  # noqa\n",
        # named by an existing registry file
        "carbon/scoring/zz_scope_named.py": b"VALUE = 1\n",
        "scripts/validator_host_classes/zz_scope_names.json": b'{"module": "carbon.scoring.zz_scope_named"}\n',
        # each computed-name site's pattern
        "carbon/scoring/zz_scope_probe/population.py": b"VALUE = 1\n",
        "carbon/challenge_kit/zz_scope_public.py": b"VALUE = 1\n",
        "carbon/backbones/zz_scope_backbone.py": b"VALUE = 1\n",
        # an overlay dispatch module, a package init, a module shadowing a package
        "carbon/scoring/zz_scope_dispatch.py": b"def dispatch(config):\n    return config\n",
        "carbon/scoring/zz_scope_pkg/__init__.py": b"",
        "carbon/scoring/zz_scope_pkg.py": b"VALUE = 1\n",
    }
    clone, base, commit = repo
    new = commit(files)
    paths = sorted(p for p in files if p.endswith(".py") and p != exam_cap)
    verdict = gs.scope(clone, base, new, paths, frozenset({SERVED}), dr.grading_path)
    assert verdict == {
        "carbon/backbones/zz_scope_backbone.py": "global:dynamic_site:carbon/backbones/__init__.py:import_module",
        "carbon/challenge_kit/zz_scope_public.py": "global:dynamic_site:carbon/direct_campaign/spec.py:import_module",
        "carbon/scoring/zz_scope_alone.py": gs.PURE_ADDITION,
        "carbon/scoring/zz_scope_dispatch.py": "global:dispatch_module",
        "carbon/scoring/zz_scope_imported.py": f"global:imported_by:{exam_cap}",
        "carbon/scoring/zz_scope_named.py": "global:named_in_text",
        "carbon/scoring/zz_scope_pkg.py": "global:shadows_a_package",
        "carbon/scoring/zz_scope_pkg/__init__.py": "global:package_init",
        "carbon/scoring/zz_scope_probe/population.py": (
            "global:dynamic_site:carbon/challenge_validator/confirmation_sources.py:import_module"
        ),
    }


def test_a_star_import_of_the_package_reaches_an_addition(repo):
    exam_cap = "carbon/challenge_validator/exam_cap.py"
    verdict = _scope(
        repo,
        {
            "carbon/scoring/zz_scope_starred.py": b"VALUE = 1\n",
            exam_cap: (ROOT / exam_cap).read_bytes()
            + b"\nfrom carbon.scoring import *  # noqa\n",
        },
    )
    assert (
        verdict["carbon/scoring/zz_scope_starred.py"]
        == f"global:imported_by:{exam_cap}"
    )


def test_a_modified_or_deleted_py_keeps_todays_check(repo):
    path = "carbon/scoring/dev_grid.py"
    assert _scope(repo, {path: (ROOT / path).read_bytes() + b"\n"}) == {
        path: "global:modified_deleted_or_renamed_py"
    }
    assert _scope(repo, {path: None}) == {path: "global:modified_deleted_or_renamed_py"}


def test_a_new_dynamic_site_makes_every_addition_global(repo):
    verdict = _scope(
        repo,
        {
            "carbon/scoring/zz_scope_alone.py": b"VALUE = 1\n",
            "carbon/scoring/zz_scope_loader.py": b"import importlib\n\ndef load(n):\n    return importlib.import_module(n)\n",
        },
    )
    assert set(verdict.values()) == {"global:dynamic_site_unlisted"}


# -- the dynamic-site table --------------------------------------------------------------------------------------------


def test_the_dynamic_site_table_is_pinned_against_an_ast_scan():
    head = _git(ROOT, "rev-parse", "HEAD").decode().strip()
    found = gs.dynamic_sites(gs.Tree(ROOT, head), dr.grading_path)
    assert found == gs._table()
    for path, call, _argument, count, kind, pattern in gs.DYNAMIC_SITES:
        assert (ROOT / path).is_file(), path
        assert call in gs.IMPORT_CALLS | gs.CODE_CALLS | {"python -m"}
        assert count >= 1 and kind in gs.KINDS
        assert pattern is None or re.compile(pattern)
    # the sites the ruling names are all in it
    named = {(path, call) for path, call, *_ in gs.DYNAMIC_SITES}
    for site in (
        ("carbon/challenge_validator/confirmation_sources.py", "import_module"),
        ("carbon/direct_campaign/spec.py", "import_module"),
        ("carbon/training_budget/adapter.py", "import_module"),
        (
            "carbon/challenge_pipeline/structures_readiness.py",
            "spec_from_file_location",
        ),
        ("carbon/scoring/f02_sealed_dual_pack.py", "__import__"),
        ("carbon/challenge_kit/version_overlay.py", "import_module"),
    ):
        assert site in named, site


def test_the_scan_sees_computed_names_program_texts_and_python_m():
    source = (
        "import importlib, sys\n"
        "importlib.import_module(f'carbon.{x}')\n"
        "__import__(name)\n"
        "model.eval()\n"
        "exec(code)\n"
        "argv = [sys.executable, '-m', target]\n"
        "PROGRAM = '''import importlib\\nimportlib.util.find_spec(n)\\n'''\n"
    )
    assert sorted(gs._sites_in(source, ast.parse(source))) == [
        ("__import__", "name"),
        ("exec", "code"),
        ("find_spec", "n"),
        ("import_module", 'f"carbon.{x}"'),
        ("python -m", "target"),
    ]


# -- (3) one verdict for the receiver and the release precheck ---------------------------------------------------------

DIFFS = {
    "keyed_other_and_pure_addition": {
        CROWN: _crown(versions={"electric-motor-magnetics 1.9": {"margin": 0.01}}),
        "carbon/scoring/zz_scope_alone.py": b"VALUE = 1\n",
    },
    "served_entry": {CROWN: _crown(versions={SERVED: {"margin": 0.02}})},
    "addition_and_modified": {
        "carbon/scoring/zz_scope_alone.py": b"VALUE = 1\n",
        "carbon/scoring/dev_grid.py": (ROOT / "carbon/scoring/dev_grid.py").read_bytes()
        + b"\n",
    },
    "dynamic_pattern": {"carbon/scoring/zz_scope_probe/domain.py": b"VALUE = 1\n"},
}


@pytest.mark.parametrize("name", sorted(DIFFS))
def test_the_receiver_and_the_release_precheck_give_one_verdict(repo, tool, name):
    clone, base, commit = repo
    new = commit(DIFFS[name])
    dr._GRADING_CHANGES.clear()
    touched = dr._grading_change(base, new, clone)
    receiver = dr._grading_change_not_served(base, new, touched, CHALLENGE, root=clone)
    release = tool.check(
        clone, base, new, old_pack=PACK, new_pack=PACK, served=[SERVED]
    )
    assert release["grading_paths_changed"] == list(touched)
    if name == "keyed_other_and_pure_addition":
        assert receiver == {
            CROWN: gs.KEYED_OTHER,
            "carbon/scoring/zz_scope_alone.py": gs.PURE_ADDITION,
        }
        assert release["state"] == tool.NOT_SERVED and tool.EXIT[release["state"]] == 0
        assert release["grading_paths_not_served"] == receiver
    else:
        assert receiver is None
        assert release["state"] == tool.CHANGE
    # without the served pair the release precheck is exactly as before
    assert (
        tool.check(clone, base, new, old_pack=PACK, new_pack=PACK)["state"]
        == tool.CHANGE
    )


def test_a_build_input_move_or_a_pack_change_is_never_scoped(repo, tool):
    clone, base, commit = repo
    new = commit(DIFFS["keyed_other_and_pure_addition"])
    assert (
        dr._grading_change_not_served(
            base, new, ("build_inputs", CROWN), CHALLENGE, root=clone
        )
        is None
    )
    moved = tool.check(
        clone, base, new, old_pack=PACK, new_pack="b" * 64, served=[SERVED]
    )
    assert moved["state"] == tool.CHANGE


# -- the receiver still declares every SERVED change -------------------------------------------------------------------


@pytest.fixture
def door(repo, monkeypatch):
    from carbon.reconstruction import served_recipe_contract

    clone, base, commit = repo
    contract = "sha256:" + "c" * 64
    monkeypatch.setattr(
        served_recipe_contract,
        "registered",
        lambda cid, version: type("C", (), {"digest": contract})(),
    )
    monkeypatch.setattr(dr, "_is_ancestor", lambda old, new, root=None: True)
    monkeypatch.setattr(
        dr, "_grading_change", functools.partial(dr._grading_change, root=clone)
    )
    monkeypatch.setattr(
        dr,
        "_grading_change_not_served",
        functools.partial(dr._grading_change_not_served, root=clone),
    )
    dr._GRADING_CHANGES.clear()

    def migrate(tmp_path, name):
        tmp_path.mkdir(parents=True, exist_ok=True)
        new = commit(DIFFS[name])
        frozen, candidate = _manifest(base), _manifest(new)
        for manifest in (frozen, candidate):
            manifest["challenge"] = dict(CHALLENGE)
        ledger = Ledger(tmp_path, frozen, [contract])
        return (
            dr._migrate_owner_manifest(ledger, "5Owner", ledger.raw, frozen, candidate),
            ledger,
            frozen,
        )

    return migrate


def _events(capsys):
    return [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("{")
    ]


def test_a_change_the_served_version_never_reads_migrates_and_is_journaled(
    door, tmp_path, capsys
):
    ok, ledger, frozen = door(tmp_path, "keyed_other_and_pure_addition")
    assert ok is True and ledger.manifest() != frozen
    lines = _events(capsys)
    said = next(line for line in lines if line["event"] == "grading_change_not_served")
    assert said["files"] == {
        CROWN: gs.KEYED_OTHER,
        "carbon/scoring/zz_scope_alone.py": gs.PURE_ADDITION,
    }
    record = json.loads(
        (tmp_path / "manifest-migrations.jsonl").read_text().splitlines()[-1]
    )
    assert record["basis"] == "grading_change_not_served"
    assert record["files_not_served"] == said["files"]


@pytest.mark.parametrize(
    "name", ["served_entry", "addition_and_modified", "dynamic_pattern"]
)
def test_the_receiver_with_scoping_still_declares_every_served_change(
    door, tmp_path, capsys, monkeypatch, name
):
    ok, ledger, frozen = door(tmp_path, name)
    assert ok is False and ledger.manifest() == frozen
    said = _events(capsys)[-1]
    assert said["event"] == "owner_manifest_migration_refused"
    assert said["reason"] == "grading_path_changed"
    # the declared record still carries it, under the GLOBAL path list
    seen = []

    def declared(old, new, touched):
        seen.append(list(touched))
        return {"reason": "r", "evidence_sha256": "e" * 64}

    monkeypatch.setattr(dr, "_declared_change", declared)
    ok, ledger, _frozen = door(tmp_path / "declared", name)
    assert ok is True
    record = json.loads(
        (tmp_path / "declared" / "manifest-migrations.jsonl")
        .read_text()
        .splitlines()[-1]
    )
    assert record["basis"] == "declared" and "files_not_served" not in record
    assert seen == [sorted(path for path in DIFFS[name] if dr.grading_path(path))]


def test_any_doubt_clears_nothing(repo):
    clone, base, commit = repo
    new = commit(DIFFS["keyed_other_and_pure_addition"])
    paths = sorted(DIFFS["keyed_other_and_pure_addition"])
    assert gs.not_served(clone, base, new, paths, {SERVED}, dr.grading_path) is not None
    assert (
        gs.not_served(clone, "f" * 40, new, paths, {SERVED}, dr.grading_path) is None
    )  # git cannot tell
    assert (
        gs.not_served(clone, base, new, paths, set(), dr.grading_path) is None
    )  # no served pair
    assert (
        gs.not_served(clone, base, new, paths, {"motor"}, dr.grading_path) is None
    )  # not a pair
    assert (
        gs.not_served(
            clone, base, new, [*paths, "docs/x.md"], {SERVED}, dr.grading_path
        )
        is None
    )
    assert (
        gs.not_served(clone, base, base, paths, {SERVED}, dr.grading_path) is None
    )  # nothing added at NEW
    broken = "carbon/scoring/zz_scope_broken.py"
    assert (
        gs.not_served(
            clone,
            base,
            commit({broken: b"def (\n"}),
            [broken],
            {SERVED},
            dr.grading_path,
        )
        is None
    )
