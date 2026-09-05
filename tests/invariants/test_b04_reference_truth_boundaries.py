"""Constitutional package and authority boundaries for B-04 evaluation."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
import tomllib

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CARBON_ROOT = _REPOSITORY_ROOT / "carbon"
_EVALUATION_ROOT = _CARBON_ROOT / "evaluation"

_EXPECTED_MODULE_PATHS = frozenset(
    {
        "__init__.py",
        "admission.py",
        "assets.py",
        "canonical.py",
        "comparison.py",
        "disclosure.py",
        "enums.py",
        "errors.py",
        "execution.py",
        "fixtures.py",
        "model.py",
        "policy.py",
        "refs.py",
        "runners.py",
    }
)

_ALLOWED_CARBON_DEPENDENCIES = (
    "carbon.authoring.canonical",
    "carbon.authoring.cases",
    "carbon.authoring.errors",
    "carbon.authoring.evidence",
    "carbon.authoring.model",
    "carbon.authoring.primitives",
    "carbon.authoring.refs",
    "carbon.evaluation",
    "carbon.registry.model",
)

_FORBIDDEN_RUNTIME_MODULE_ROOTS = frozenset(
    {
        "asyncio",
        "builtins",
        "concurrent",
        "ctypes",
        "datetime",
        "dbm",
        "fcntl",
        "fileinput",
        "ftplib",
        "glob",
        "grp",
        "http",
        "imaplib",
        "importlib",
        "inspect",
        "io",
        "logging",
        "marshal",
        "mmap",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "pkg_resources",
        "pkgutil",
        "platform",
        "poplib",
        "pty",
        "pwd",
        "random",
        "requests",
        "resource",
        "runpy",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shutil",
        "signal",
        "smtplib",
        "socket",
        "sqlite3",
        "ssl",
        "subprocess",
        "sys",
        "telnetlib",
        "tempfile",
        "termios",
        "time",
        "urllib",
        "uuid",
        "xmlrpc",
        "zoneinfo",
    }
)

_FORBIDDEN_RUNTIME_CALLS = frozenset(
    {"__import__", "breakpoint", "compile", "eval", "exec", "input", "open"}
)

_FORBIDDEN_RUNTIME_METHOD_CALLS = frozenset(
    {
        "__import__",
        "connect",
        "getenv",
        "import_module",
        "kill",
        "load",
        "loads",
        "open",
        "popen",
        "read",
        "read_bytes",
        "read_text",
        "request",
        "run",
        "sleep",
        "spawn",
        "system",
        "terminate",
        "urlopen",
        "urandom",
        "write",
        "write_bytes",
        "write_text",
    }
)

_RESERVED_OWNER_NAMES = frozenset(
    {
        "CandidateMeasurement",
        "Dossier",
        "JuliaReferenceRunner",
        "MeasurementContract",
        "MeasurementResult",
        "ProductionReferenceService",
        "QualificationManifest",
        "ScorePack",
        "ScoringPolicy",
        "ValidationDossier",
    }
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _allowed_carbon_dependency(module_name: str) -> bool:
    return any(
        module_name == allowed or module_name.startswith(f"{allowed}.")
        for allowed in _ALLOWED_CARBON_DEPENDENCIES
    )


def _is_allowed_evaluation_consumer(path: Path, module_name: str) -> bool:
    """Permit only B-05's ratified public reference seam."""
    return (
        path.is_relative_to(_CARBON_ROOT / "measurement")
        and module_name == "carbon.evaluation.refs"
    )


def _matches_namespace(module_name: str, namespaces: tuple[str, ...]) -> bool:
    return any(
        module_name == namespace or module_name.startswith(f"{namespace}.")
        for namespace in namespaces
    )


def _relative(path: Path) -> str:
    return path.relative_to(_REPOSITORY_ROOT).as_posix()


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    (
        (
            "from carbon import evaluation",
            _CARBON_ROOT / "probe.py",
            "carbon.evaluation",
        ),
        ("from . import evaluation", _CARBON_ROOT / "probe.py", "carbon.evaluation"),
        (
            "import carbon.evaluation.refs",
            _CARBON_ROOT / "probe.py",
            "carbon.evaluation.refs",
        ),
    ),
)
def test_import_scanner_resolves_evaluation_namespaces(
    source: str, path: Path, expected: str
) -> None:
    imports = {
        module
        for module, _ in direct_import_modules(
            _REPOSITORY_ROOT, path, tree=ast.parse(source)
        )
    }
    assert expected in imports


def test_import_scanner_preserves_approved_measurement_refs_seam() -> None:
    path = _CARBON_ROOT / "measurement" / "probe.py"
    imports = direct_import_modules(
        _REPOSITORY_ROOT,
        path,
        tree=ast.parse("from carbon.evaluation.refs import ReferencePolicyRef"),
    )
    assert imports == (("carbon.evaluation.refs", 1),)
    assert _is_allowed_evaluation_consumer(path, imports[0][0])


def test_evaluation_has_the_exact_ratified_module_seams() -> None:
    assert _EVALUATION_ROOT.is_dir()
    actual = {
        path.relative_to(_EVALUATION_ROOT).as_posix()
        for path in _python_files(_EVALUATION_ROOT)
    }
    assert actual == _EXPECTED_MODULE_PATHS


def test_evaluation_is_one_exact_canonical_implementation_root() -> None:
    with (_REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml").open("rb") as stream:
        authority = tomllib.load(stream)
    assert (
        authority["canonical"]["implementation_roots"].count("carbon/evaluation") == 1
    )


def test_evaluation_has_only_ratified_direct_carbon_dependencies() -> None:
    violations = [
        f"{_relative(path)}:{line}: {module_name}"
        for path in _python_files(_EVALUATION_ROOT)
        for module_name, line in direct_import_modules(_REPOSITORY_ROOT, path)
        if (module_name == "carbon" or module_name.startswith("carbon."))
        and not _allowed_carbon_dependency(module_name)
    ]
    assert violations == []


def test_only_measurement_may_import_exact_public_evaluation_refs() -> None:
    violations = [
        f"{_relative(path)}:{line}: {module_name}"
        for path in _python_files(_CARBON_ROOT)
        if _EVALUATION_ROOT not in path.parents
        for module_name, line in direct_import_modules(_REPOSITORY_ROOT, path)
        if _matches_namespace(module_name, ("carbon.evaluation",))
        and not _is_allowed_evaluation_consumer(path, module_name)
    ]
    assert violations == []


def test_evaluation_does_not_import_retired_namespaces() -> None:
    with (_REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml").open("rb") as stream:
        authority = tomllib.load(stream)
    retired = tuple(authority["retired"]["runtime_namespaces"])
    violations = [
        f"{_relative(path)}:{line}: {module_name}"
        for path in _python_files(_EVALUATION_ROOT)
        for module_name, line in direct_import_modules(_REPOSITORY_ROOT, path)
        if _matches_namespace(module_name, retired)
    ]
    assert violations == []


def test_evaluation_imports_no_dynamic_io_randomness_or_network_modules() -> None:
    violations: list[str] = []
    for path in _python_files(_EVALUATION_ROOT):
        for module_name, line in direct_import_modules(_REPOSITORY_ROOT, path):
            if module_name.partition(".")[0] in _FORBIDDEN_RUNTIME_MODULE_ROOTS:
                violations.append(f"{_relative(path)}:{line}: {module_name}")
    assert violations == []


def test_evaluation_external_dependencies_are_standard_library_only() -> None:
    violations: list[str] = []
    for path in _python_files(_EVALUATION_ROOT):
        for module_name, line in direct_import_modules(_REPOSITORY_ROOT, path):
            root = module_name.partition(".")[0]
            if root != "carbon" and root not in sys.stdlib_module_names:
                violations.append(f"{_relative(path)}:{line}: {module_name}")
    assert violations == []


def test_evaluation_performs_no_dynamic_io_or_process_control_calls() -> None:
    violations: list[str] = []
    for path in _python_files(_EVALUATION_ROOT):
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "*" for alias in node.names
            ):
                violations.append(f"{_relative(path)}:{node.lineno}: star import")
                continue
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in _FORBIDDEN_RUNTIME_CALLS
            ):
                violations.append(f"{_relative(path)}:{node.lineno}:{node.func.id}")
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _FORBIDDEN_RUNTIME_METHOD_CALLS
            ):
                violations.append(f"{_relative(path)}:{node.lineno}:{node.func.attr}")
    assert violations == []


def test_evaluation_does_not_implement_later_ticket_owners() -> None:
    declared_names = {
        node.name
        for path in _python_files(_EVALUATION_ROOT)
        for node in _parse(path).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert declared_names.isdisjoint(_RESERVED_OWNER_NAMES)


def test_fixture_module_contains_no_scientific_or_live_authority_literals() -> None:
    source = (_EVALUATION_ROOT / "fixtures.py").read_text(encoding="utf-8")
    forbidden = (
        "Cole-Hopf",
        "ColeHopf",
        "julia",
        "qualified_primary",
        "scientifically_qualified=True",
        "live_eligible=True",
    )
    assert [literal for literal in forbidden if literal in source] == []
