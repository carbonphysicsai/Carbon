"""Constitutional package and authority boundaries for B-02B construction."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
import tomllib

pytestmark = pytest.mark.invariant

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CARBON_ROOT = _REPOSITORY_ROOT / "carbon"
_CONSTRUCTION_ROOT = _CARBON_ROOT / "construction"
_REVERSE_DEPENDENCY_ROOTS = (
    _CARBON_ROOT / "schema",
    _CARBON_ROOT / "authoring",
    _CARBON_ROOT / "registry",
    _CARBON_ROOT / "fees",
)

_ALLOWED_CARBON_DEPENDENCIES = (
    "carbon.construction",
    "carbon.schema.strategy",
    "carbon.authoring",
    "carbon.registry",
    "carbon.fees.strategy_identity",
)

_FORBIDDEN_RUNTIME_MODULE_ROOTS = frozenset(
    {
        "asyncio",
        "ctypes",
        "datetime",
        "http",
        "importlib",
        "inspect",
        "marshal",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "pkg_resources",
        "pkgutil",
        "platform",
        "random",
        "requests",
        "resource",
        "secrets",
        "shelve",
        "shutil",
        "socket",
        "sqlite3",
        "subprocess",
        "sys",
        "tempfile",
        "time",
        "urllib",
        "uuid",
    }
)

_FORBIDDEN_COMPILER_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "callable",
        "compile",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "hasattr",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)

_FORBIDDEN_COMPILER_METHOD_CALLS = frozenset(
    {
        "__getattribute__",
        "__import__",
        "connect",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "hasattr",
        "import_module",
        "load",
        "loads",
        "locals",
        "open",
        "read",
        "read_bytes",
        "read_text",
        "request",
        "setattr",
        "urlopen",
        "vars",
        "write",
        "write_bytes",
        "write_text",
    }
)

_FORBIDDEN_COMPILE_ARGUMENTS = frozenset(
    {
        "admission_policy",
        "authority",
        "capability",
        "case",
        "consumer",
        "consumer_mode",
        "draw",
        "entropy",
        "entropy_domain",
        "evaluation",
        "gate",
        "mode",
        "resource_policy",
        "scorer",
        "seed",
    }
)

_FORBIDDEN_DECLARATIVE_FIELDS = frozenset(
    {
        "_capability",
        "admission_verdict",
        "authority",
        "callback",
        "callbacks",
        "callable",
        "callables",
        "capability",
        "checkpoint",
        "consumer_mode",
        "custom_dataset",
        "dataset",
        "dataset_path",
        "draw",
        "draw_id",
        "entropy_context",
        "entropy_domain",
        "executable",
        "gate",
        "gate_result",
        "import_string",
        "is_live",
        "loader",
        "model_artifact",
        "module_path",
        "network_endpoint",
        "nonce",
        "official_mode",
        "participant_graph",
        "participant_seed",
        "pickle",
        "practice_mode",
        "qualification",
        "qualified",
        "repository",
        "resource_policy",
        "resource_policy_verdict",
        "rng",
        "rng_state",
        "score",
        "scorer",
        "script",
        "seed",
        "serialized_blob",
        "source_code",
    }
)

_FORBIDDEN_PIN_FIELDS = frozenset(
    {
        "command",
        "endpoint",
        "import_path",
        "package",
        "package_resolver",
        "path",
        "uri",
        "url",
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


def _imports_construction(path: Path) -> tuple[int, ...]:
    lines: list[int] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "carbon.construction"
                or alias.name.startswith("carbon.construction.")
                for alias in node.names
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            base = _from_module(path, node)
            if (
                base == "carbon.construction"
                or base.startswith("carbon.construction.")
                or base == "carbon"
                and any(alias.name == "construction" for alias in node.names)
            ):
                lines.append(node.lineno)
    return tuple(lines)


def _decorator_name(decorator: ast.expr) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def test_construction_is_a_canonical_implementation_root() -> None:
    authority_path = _REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml"
    with authority_path.open("rb") as stream:
        authority = tomllib.load(stream)

    roots = authority["canonical"]["implementation_roots"]
    assert roots.count("carbon/construction") == 1


def test_construction_has_only_the_ratified_direct_carbon_dependencies() -> None:
    violations: list[str] = []
    for path in _python_files(_CONSTRUCTION_ROOT):
        for module_name, line in _direct_import_modules(path):
            if (
                module_name == "carbon" or module_name.startswith("carbon.")
            ) and not _allowed_carbon_dependency(module_name):
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_schema_authoring_registry_and_fees_do_not_import_construction() -> None:
    violations: list[str] = []
    for root in _REVERSE_DEPENDENCY_ROOTS:
        for path in _python_files(root):
            for line in _imports_construction(path):
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{line}")

    assert violations == []


def test_construction_imports_no_dynamic_io_randomness_or_network_modules() -> None:
    violations: list[str] = []
    for path in _python_files(_CONSTRUCTION_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root in _FORBIDDEN_RUNTIME_MODULE_ROOTS:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_construction_external_dependencies_are_standard_library_only() -> None:
    violations: list[str] = []
    for path in _python_files(_CONSTRUCTION_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root != "carbon" and root not in sys.stdlib_module_names:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_compiler_performs_no_dynamic_io_import_or_reflection_calls() -> None:
    compiler_path = _CONSTRUCTION_ROOT / "compiler.py"
    violations: list[str] = []
    for node in ast.walk(_parse(compiler_path)):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_COMPILER_CALLS
        ):
            violations.append(f"{node.func.id}:{node.lineno}")
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _FORBIDDEN_COMPILER_METHOD_CALLS
        ):
            violations.append(f"{node.func.attr}:{node.lineno}")

    assert violations == []


def test_compile_entrypoint_has_no_consumer_randomness_policy_or_authority_input() -> (
    None
):
    compiler_path = _CONSTRUCTION_ROOT / "compiler.py"
    compile_functions = [
        node
        for node in _parse(compiler_path).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "compile_strategy"
    ]
    assert len(compile_functions) == 1
    function = compile_functions[0]
    argument_names = {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    assert not argument_names & _FORBIDDEN_COMPILE_ARGUMENTS


def test_declarative_models_expose_no_runtime_capability_or_authority_fields() -> None:
    violations: list[str] = []
    for path in _python_files(_CONSTRUCTION_ROOT):
        for node in _parse(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            decorators = {_decorator_name(item) for item in node.decorator_list}
            if "dataclass" not in decorators:
                continue
            fields = {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
            forbidden = fields & _FORBIDDEN_DECLARATIVE_FIELDS
            if node.name in {
                "CompilerIdentity",
                "DependencyPin",
                "EnvironmentPin",
                "ImplementationPin",
                "InterfacePin",
            }:
                forbidden |= fields & _FORBIDDEN_PIN_FIELDS
            if forbidden:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.name}:"
                    f"{','.join(sorted(forbidden))}"
                )

    assert violations == []
