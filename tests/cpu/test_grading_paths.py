"""M2's grading-path list cannot be escaped by a new import (Validator 4 Nov 15:46 H0 ruling 1, 16:38 must-fix).

Claims: the official grade's core (`lean_recipe_retention`) and both rebuild workers are grading paths; every module the
workers stage into their containers is a grading path; every program string they run imports only grading paths; and
every carbon module any of those imports (statically, lazy imports included) is either a grading path or named in
`GRADING_EXCLUDED` with a reason. A new import that is in neither list fails here, so it is classified before it lands.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.challenge_validator import direct_receiver as dr
from carbon.development_session import bundle_construction_worker as bundle_worker
from carbon.development_session import direct_graph_construction_worker as graph_worker

ROOT = Path(dr.__file__).resolve().parents[2]
CORE = (
    "carbon.challenge_validator.lean_recipe_retention",
    "carbon.development_session.bundle_construction_worker",
    "carbon.development_session.direct_graph_construction_worker",
)
EXCLUDED = dict(dr.GRADING_EXCLUDED)


def _path(module):
    """The repo-relative file of a carbon module or package, or None."""
    base = ROOT.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate.relative_to(ROOT).as_posix()
    return None


def _imports(tree, module, package):
    """The carbon modules ``tree`` imports, each resolved to the longest existing module name."""
    named = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.split(".") if package else module.split(".")[:-1]
                base = base[: len(base) - (node.level - 1)]
                source = ".".join(
                    [*base, *(node.module.split(".") if node.module else [])]
                )
            else:
                source = node.module or ""
            named.add(source)
            named.update(source + "." + alias.name for alias in node.names)
    found = set()
    for name in named:
        if name != "carbon" and not name.startswith("carbon."):
            continue
        while name and _path(name) is None:
            name = name.rpartition(".")[0]
        if name and name != "carbon":
            found.add(name)
    return found


def _module_imports(module):
    path = _path(module)
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return _imports(tree, module, path.endswith("__init__.py"))


def _staged():
    return sorted(
        {
            *bundle_worker.STAGED_MODULES,
            *graph_worker.STAGED_MODULES,
            *graph_worker.PHYSICAL_STAGED_MODULES,
            *graph_worker.PHYSICAL_V2_STAGED_MODULES,
        }
    )


def _programs():
    return {
        f"{worker.__name__}.{name}": value
        for worker in (bundle_worker, graph_worker)
        for name, value in vars(worker).items()
        if name.endswith("_PROGRAM") and type(value) is str
    }


def _classified(module):
    return dr.grading_path(_path(module)) or module in EXCLUDED


def test_the_core_and_everything_the_workers_stage_are_grading_paths():
    for module in (*CORE, *_staged()):
        assert _path(module) is not None, module
        assert dr.grading_path(_path(module)), module


@pytest.mark.parametrize("program", sorted(_programs()))
def test_every_worker_program_imports_only_grading_paths(program):
    tree = ast.parse(_programs()[program])
    for module in _imports(tree, "carbon.program", False):
        assert _classified(module), (program, module)


def test_every_import_of_the_grade_and_rebuild_is_classified():
    unclassified = sorted(
        (source, module)
        for source in (*CORE, *_staged())
        for module in _module_imports(source)
        if not _classified(module)
    )
    assert unclassified == []


def test_every_exclusion_is_real_reasoned_and_not_a_grading_path():
    assert len(EXCLUDED) == len(dr.GRADING_EXCLUDED)  # no repeats
    for module, reason in dr.GRADING_EXCLUDED:
        assert _path(module) is not None, module
        assert type(reason) is str and reason.strip(), module
        assert not dr.grading_path(_path(module)), module


def test_a_new_unclassified_import_fails_the_check(tmp_path):
    tree = ast.parse("from carbon.agent_campaign import graphite\n")
    found = _imports(tree, "carbon.challenge_validator.lean_recipe_retention", False)
    assert found and not all(_classified(module) for module in found)
