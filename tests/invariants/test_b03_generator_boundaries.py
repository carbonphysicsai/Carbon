"""Constitutional package and authority boundaries for B-03 generators."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
import tomllib

pytestmark = pytest.mark.invariant

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CARBON_ROOT = _REPOSITORY_ROOT / "carbon"
_GENERATORS_ROOT = _CARBON_ROOT / "generators"

_EXPECTED_MODULE_PATHS = frozenset(
    {
        "__init__.py",
        "accounting.py",
        "authorities.py",
        "burgers.py",
        "canonical.py",
        "conformance.py",
        "disclosure.py",
        "errors.py",
        "model.py",
        "refs.py",
        "service.py",
    }
)

_ALLOWED_CARBON_DEPENDENCIES = (
    "carbon.authoring",
    "carbon.generators",
    "carbon.registry.digest",
    "carbon.registry.model",
    "carbon.seeding",
)

_ALLOWED_REGISTRY_SYMBOLS = {
    "carbon.registry.digest": frozenset({"is_sha256_digest"}),
    "carbon.registry.model": frozenset(
        {
            "ChallengeKey",
            "validate_canonical_identifier",
            "validate_version",
        }
    ),
}

_FORBIDDEN_SEEDING_SYMBOLS = frozenset(
    {
        "BeaconConflictError",
        "BeaconProvider",
        "MockContext",
        "MockEntropy",
        "OfficialContext",
        "OfficialEntropy",
        "OfficialEntropyUnavailable",
        "OfficialExamProjection",
        "QualificationContext",
        "QualificationEntropy",
        "acquire_official_context",
        "create_official_exam_projection",
        "derive_mock_seed",
        "derive_official_seed",
        "derive_qualification_seed",
    }
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
        "threading",
        "time",
        "urllib",
        "uuid",
        "xmlrpc",
        "zoneinfo",
    }
)

_FORBIDDEN_RUNTIME_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "input",
        "open",
    }
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

_RESERVED_FUTURE_OWNER_TYPES = frozenset(
    {
        "BindingExecutionQuote",
        "CalibratedResourceForecast",
        "ChallengeInteractionManifest",
        "ExperimentRecord",
        "GeneratorQualification",
        "LoadedScorePack",
        "MeasurementContract",
        "MeasurementResult",
        "PriorPack",
        "ProductionEnvironment",
        "ProductionGenerator",
        "QualificationManifest",
        "ReferencePolicy",
        "ReferenceResult",
        "ReferenceRunner",
        "ResearchReceipt",
        "ResearchService",
        "ResearchTask",
        "ScorePack",
        "StaticResourceInspection",
        "TruthAsset",
        "UncertaintyPolicy",
        "ValidationDossier",
    }
)


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_name(path: Path) -> str:
    relative = path.relative_to(_REPOSITORY_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _from_module(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    current = _module_name(path).split(".")
    package = current if path.name == "__init__.py" else current[:-1]
    trim = node.level - 1
    if trim > len(package):
        return ""
    base = package[: len(package) - trim]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _direct_import_modules(path: Path) -> tuple[tuple[str, int], ...]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((_from_module(path, node), node.lineno))
    return tuple(imports)


def _allowed_carbon_dependency(module_name: str) -> bool:
    return any(
        module_name == allowed or module_name.startswith(f"{allowed}.")
        for allowed in _ALLOWED_CARBON_DEPENDENCIES
    )


def _imports_generators(path: Path) -> tuple[int, ...]:
    lines: list[int] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "carbon.generators"
                or alias.name.startswith("carbon.generators.")
                for alias in node.names
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            base = _from_module(path, node)
            if (
                base == "carbon.generators"
                or base.startswith("carbon.generators.")
                or base == "carbon"
                and any(alias.name == "generators" for alias in node.names)
            ):
                lines.append(node.lineno)
    return tuple(lines)


def _matches_namespace(module_name: str, namespaces: tuple[str, ...]) -> bool:
    return any(
        module_name == namespace or module_name.startswith(f"{namespace}.")
        for namespace in namespaces
    )


def _relative(path: Path) -> str:
    return path.relative_to(_REPOSITORY_ROOT).as_posix()


def test_generators_has_the_required_package_module_seams() -> None:
    assert _GENERATORS_ROOT.is_dir()
    actual = {
        path.relative_to(_GENERATORS_ROOT).as_posix()
        for path in _python_files(_GENERATORS_ROOT)
    }
    assert actual == _EXPECTED_MODULE_PATHS


def test_generators_is_a_canonical_implementation_root() -> None:
    authority_path = _REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml"
    with authority_path.open("rb") as stream:
        authority = tomllib.load(stream)

    roots = authority["canonical"]["implementation_roots"]
    assert roots.count("carbon/generators") == 1


def test_generators_has_only_ratified_direct_carbon_dependencies() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
        for module_name, line in _direct_import_modules(path):
            if (
                module_name == "carbon" or module_name.startswith("carbon.")
            ) and not _allowed_carbon_dependency(module_name):
                violations.append(f"{_relative(path)}:{line}: {module_name}")

    assert violations == []


def test_generators_uses_only_registry_identity_and_digest_primitives() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "carbon.registry" or alias.name.startswith(
                        "carbon.registry."
                    ):
                        violations.append(
                            f"{_relative(path)}:{node.lineno}: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                base = _from_module(path, node)
                if base == "carbon.registry" or base.startswith("carbon.registry."):
                    allowed = _ALLOWED_REGISTRY_SYMBOLS.get(base, frozenset())
                    unexpected = sorted(
                        alias.name for alias in node.names if alias.name not in allowed
                    )
                    if unexpected:
                        violations.append(
                            f"{_relative(path)}:{node.lineno}: {base}:"
                            f"{','.join(unexpected)}"
                        )

    assert violations == []


def test_generators_uses_only_fixture_seeding_apis() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "carbon.seeding"
                    or alias.name.startswith("carbon.seeding.")
                    for alias in node.names
                ):
                    violations.append(f"{_relative(path)}:{node.lineno}: module alias")
            elif isinstance(node, ast.ImportFrom):
                base = _from_module(path, node)
                if base == "carbon.seeding" or base.startswith("carbon.seeding."):
                    forbidden = sorted(
                        alias.name
                        for alias in node.names
                        if alias.name in _FORBIDDEN_SEEDING_SYMBOLS
                    )
                    if forbidden:
                        violations.append(
                            f"{_relative(path)}:{node.lineno}:" f"{','.join(forbidden)}"
                        )

    assert violations == []


def test_existing_carbon_packages_do_not_reverse_import_generators() -> None:
    violations: list[str] = []
    for path in _python_files(_CARBON_ROOT):
        if _GENERATORS_ROOT in path.parents:
            continue
        violations.extend(
            f"{_relative(path)}:{line}" for line in _imports_generators(path)
        )

    assert violations == []


def test_generators_does_not_import_retired_namespaces() -> None:
    authority_path = _REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml"
    with authority_path.open("rb") as stream:
        authority = tomllib.load(stream)
    retired = tuple(authority["retired"]["runtime_namespaces"])

    violations = [
        f"{_relative(path)}:{line}: {module_name}"
        for path in _python_files(_GENERATORS_ROOT)
        for module_name, line in _direct_import_modules(path)
        if _matches_namespace(module_name, retired)
    ]

    assert violations == []


def test_generators_imports_no_dynamic_io_randomness_or_network_modules() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root in _FORBIDDEN_RUNTIME_MODULE_ROOTS:
                violations.append(f"{_relative(path)}:{line}: {module_name}")

    assert violations == []


def test_generators_external_dependencies_are_standard_library_only() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root != "carbon" and root not in sys.stdlib_module_names:
                violations.append(f"{_relative(path)}:{line}: {module_name}")

    assert violations == []


def test_generators_performs_no_dynamic_io_or_process_control_calls() -> None:
    violations: list[str] = []
    for path in _python_files(_GENERATORS_ROOT):
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


def test_generators_does_not_implement_future_owner_types() -> None:
    declared_names = {
        node.name
        for path in _python_files(_GENERATORS_ROOT)
        for node in _parse(path).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert declared_names.isdisjoint(_RESERVED_FUTURE_OWNER_TYPES)
