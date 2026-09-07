from __future__ import annotations

import ast
import pickle
import sys
from pathlib import Path

import pytest
import tomllib

from carbon import reproducibility
from carbon.registry import ChallengeKey
from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CARBON_ROOT = REPOSITORY_ROOT / "carbon"
REPRODUCIBILITY_ROOT = CARBON_ROOT / "reproducibility"

EXPECTED_MODULES = {
    "__init__.py",
    "canonical.py",
    "enums.py",
    "errors.py",
    "harness.py",
    "model.py",
    "refs.py",
}

ALLOWED_CARBON_DEPENDENCIES = {
    "carbon.authoring.primitives",
    "carbon.authoring.refs",
    "carbon.construction",
    "carbon.evaluation",
    "carbon.evaluation.refs",
    "carbon.measurement",
    "carbon.registry",
    "carbon.reproducibility",
}

FORBIDDEN_MODULE_ROOTS = {
    "asyncio",
    "concurrent",
    "ctypes",
    "http",
    "importlib",
    "logging",
    "multiprocessing",
    "os",
    "pathlib",
    "random",
    "requests",
    "secrets",
    "shutil",
    "socket",
    "subprocess",
    "tempfile",
    "time",
    "urllib",
    "uuid",
}

FORBIDDEN_OWNER_TOKENS = {
    "commercial",
    "frontier",
    "leaderboard",
    "marketplace",
    "network",
    "production",
    "ranking",
    "settlement",
    "treasury",
}


def python_files(root: Path):
    return tuple(sorted(root.rglob("*.py")))


def imported_modules(path: Path):
    return direct_import_modules(REPOSITORY_ROOT, path)


def allowed_carbon_dependency(module: str) -> bool:
    return module in ALLOWED_CARBON_DEPENDENCIES or module.startswith(
        "carbon.reproducibility."
    )


def test_reproducibility_is_one_exact_canonical_implementation_root() -> None:
    with (REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml").open("rb") as stream:
        authority = tomllib.load(stream)
    assert (
        authority["canonical"]["implementation_roots"].count("carbon/reproducibility")
        == 1
    )
    assert {
        path.relative_to(REPRODUCIBILITY_ROOT).as_posix()
        for path in python_files(REPRODUCIBILITY_ROOT)
    } == EXPECTED_MODULES


def test_reproducibility_has_only_ratified_direct_carbon_dependencies() -> None:
    violations = [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), line, module)
        for path in python_files(REPRODUCIBILITY_ROOT)
        for module, line in imported_modules(path)
        if (module == "carbon" or module.startswith("carbon."))
        and not allowed_carbon_dependency(module)
    ]
    assert violations == []


def test_completed_and_later_packages_do_not_import_reproducibility() -> None:
    violations = [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), line, module)
        for path in python_files(CARBON_ROOT)
        if REPRODUCIBILITY_ROOT not in path.parents
        for module, line in imported_modules(path)
        if module == "carbon.reproducibility"
        or module.startswith("carbon.reproducibility.")
    ]
    assert violations == []


def test_reproducibility_is_standard_library_only_outside_carbon() -> None:
    violations = [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), line, module)
        for path in python_files(REPRODUCIBILITY_ROOT)
        for module, line in imported_modules(path)
        if module.partition(".")[0] != "carbon"
        and module.partition(".")[0] not in sys.stdlib_module_names
    ]
    assert violations == []
    assert [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), line, module)
        for path in python_files(REPRODUCIBILITY_ROOT)
        for module, line in imported_modules(path)
        if module.partition(".")[0] in FORBIDDEN_MODULE_ROOTS
    ] == []


def test_reproducibility_exposes_fixture_authority_only() -> None:
    public_names = {name.casefold() for name in reproducibility.__all__}
    assert all(
        token not in name for name in public_names for token in FORBIDDEN_OWNER_TOKENS
    )
    assert tuple(reproducibility.ProducerRole) == (
        reproducibility.ProducerRole.PRODUCER_INDEPENDENT,
    )
    assert not hasattr(reproducibility, "ScoreEngine")
    assert not hasattr(reproducibility, "FrontierPromotionEvent")


def test_reproducibility_defines_no_embedded_numeric_decision_default() -> None:
    violations = []
    for path in python_files(REPRODUCIBILITY_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            defaults = ()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = (*node.args.defaults, *node.args.kw_defaults)
            elif isinstance(node, ast.AnnAssign):
                defaults = (node.value,)
            for default in defaults:
                if isinstance(default, ast.Constant) and type(default.value) is float:
                    violations.append((path.name, getattr(node, "lineno", 0)))
    assert violations == []


def test_reproducibility_refs_are_protected_and_nonpickleable() -> None:
    value = reproducibility.ReproducibilityRef(
        ChallengeKey("fixture-burgers", "1.0"),
        reproducibility.ReproducibilityRefKind.EVIDENCE,
        "fixture-evidence",
        "1.0",
        "sha256:" + "a" * 64,
    )
    assert "fixture-burgers" not in repr(value)
    assert "fixture-burgers" not in str(value)
    with pytest.raises(TypeError):
        pickle.dumps(value)


def test_reproducibility_sources_do_not_use_retired_namespaces() -> None:
    with (REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml").open("rb") as stream:
        authority = tomllib.load(stream)
    retired = tuple(authority["retired"]["runtime_namespaces"])
    violations = [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), line, module)
        for path in python_files(REPRODUCIBILITY_ROOT)
        for module, line in imported_modules(path)
        if any(module == item or module.startswith(f"{item}.") for item in retired)
    ]
    assert violations == []
