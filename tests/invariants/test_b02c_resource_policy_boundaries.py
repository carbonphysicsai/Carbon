"""Constitutional package and authority boundaries for B-02C resource policy."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
import tomllib

pytestmark = pytest.mark.invariant

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CARBON_ROOT = _REPOSITORY_ROOT / "carbon"
_RESOURCE_POLICY_ROOT = _CARBON_ROOT / "resource_policy"
_REVERSE_DEPENDENCY_ROOTS = (
    _CARBON_ROOT / "authoring",
    _CARBON_ROOT / "construction",
    _CARBON_ROOT / "fees",
    _CARBON_ROOT / "mcp",
    _CARBON_ROOT / "registry",
    _CARBON_ROOT / "scoring",
    _CARBON_ROOT / "traineval",
)

_ALLOWED_CARBON_DEPENDENCIES = (
    "carbon.resource_policy",
    "carbon.authoring",
    "carbon.construction",
    "carbon.registry",
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

_FORBIDDEN_MODEL_FIELDS = frozenset(
    {
        "allocation",
        "allocation_id",
        "callable",
        "case_id",
        "case_ref",
        "command",
        "concurrency",
        "credential",
        "credentials",
        "currency",
        "derived_seed",
        "draw_id",
        "endpoint",
        "entitlement",
        "fee",
        "frontier",
        "gate",
        "hidden_case_count",
        "import_path",
        "invoice",
        "margin",
        "participant_code",
        "path",
        "payment",
        "price",
        "qualification",
        "queue_position",
        "quota",
        "rank",
        "reference_identity",
        "refund",
        "score",
        "seed",
        "settlement",
        "sponsor_priority",
        "stake",
        "stratum",
        "topology",
        "uri",
        "url",
        "weight",
        "winner_probability",
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
        "connect",
        "kill",
        "open",
        "popen",
        "read",
        "read_bytes",
        "read_text",
        "request",
        "run",
        "spawn",
        "system",
        "terminate",
        "urlopen",
        "write",
        "write_bytes",
        "write_text",
    }
)

_RESERVED_OWNER_TYPES = frozenset(
    {
        "BindingExecutionAdmission",
        "BindingExecutionQuote",
        "CalibratedResourceForecast",
        "ProductionResourceClass",
        "ProductionResourceContext",
        "ReconstructionEvidencePolicy",
        "ResourcePrice",
        "ResourceQuota",
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


def _imports_resource_policy(path: Path) -> tuple[int, ...]:
    lines: list[int] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "carbon.resource_policy"
                or alias.name.startswith("carbon.resource_policy.")
                for alias in node.names
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            base = _from_module(path, node)
            if (
                base == "carbon.resource_policy"
                or base.startswith("carbon.resource_policy.")
                or base == "carbon"
                and any(alias.name == "resource_policy" for alias in node.names)
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


def test_resource_policy_is_a_canonical_implementation_root() -> None:
    authority_path = _REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml"
    with authority_path.open("rb") as stream:
        authority = tomllib.load(stream)

    roots = authority["canonical"]["implementation_roots"]
    assert roots.count("carbon/resource_policy") == 1


def test_resource_policy_has_only_ratified_direct_carbon_dependencies() -> None:
    violations: list[str] = []
    for path in _python_files(_RESOURCE_POLICY_ROOT):
        for module_name, line in _direct_import_modules(path):
            if (
                module_name == "carbon" or module_name.startswith("carbon.")
            ) and not any(
                module_name == allowed or module_name.startswith(f"{allowed}.")
                for allowed in _ALLOWED_CARBON_DEPENDENCIES
            ):
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_upstream_and_reserved_consumers_do_not_import_resource_policy() -> None:
    violations: list[str] = []
    for root in _REVERSE_DEPENDENCY_ROOTS:
        for path in _python_files(root):
            violations.extend(
                f"{path.relative_to(_REPOSITORY_ROOT)}:{line}"
                for line in _imports_resource_policy(path)
            )

    assert violations == []


def test_resource_policy_imports_no_dynamic_io_randomness_or_network_modules() -> None:
    violations: list[str] = []
    for path in _python_files(_RESOURCE_POLICY_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root in _FORBIDDEN_RUNTIME_MODULE_ROOTS:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_resource_policy_external_dependencies_are_standard_library_only() -> None:
    violations: list[str] = []
    for path in _python_files(_RESOURCE_POLICY_ROOT):
        for module_name, line in _direct_import_modules(path):
            root = module_name.partition(".")[0]
            if root != "carbon" and root not in sys.stdlib_module_names:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{line}: {module_name}"
                )

    assert violations == []


def test_resource_policy_performs_no_dynamic_io_or_process_control_calls() -> None:
    violations: list[str] = []
    for path in _python_files(_RESOURCE_POLICY_ROOT):
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in _FORBIDDEN_RUNTIME_CALLS
            ):
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}:"
                    f"{node.func.id}"
                )
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _FORBIDDEN_RUNTIME_METHOD_CALLS
            ):
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}:"
                    f"{node.func.attr}"
                )

    assert violations == []


def test_public_models_expose_no_hidden_evaluation_or_economic_fields() -> None:
    violations: list[str] = []
    for path in _python_files(_RESOURCE_POLICY_ROOT):
        for node in _parse(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            decorators = {_decorator_name(item) for item in node.decorator_list}
            if "dataclass" not in decorators:
                continue
            field_names = {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
            forbidden = field_names & _FORBIDDEN_MODEL_FIELDS
            if node.name == "ResourcePolicyIssue":
                forbidden.discard("path")
            if forbidden:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.name}:"
                    f"{','.join(sorted(forbidden))}"
                )

    assert violations == []


def test_resource_policy_does_not_implement_future_owner_types() -> None:
    declared_names = {
        node.name
        for path in _python_files(_RESOURCE_POLICY_ROOT)
        for node in _parse(path).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert declared_names.isdisjoint(_RESERVED_OWNER_TYPES)


def test_resource_policy_ships_no_default_policy_or_class() -> None:
    from carbon import resource_policy

    assert type(resource_policy.__all__) is list
    assert resource_policy.__all__ == sorted(resource_policy.__all__)
    assert len(resource_policy.__all__) == len(set(resource_policy.__all__))
    assert all(name in vars(resource_policy) for name in resource_policy.__all__)

    resource_class_type = resource_policy.ResourceClass
    policy_type = resource_policy.ResearchResourcePolicy
    assert not any(
        type(value) in {resource_class_type, policy_type}
        for value in vars(resource_policy).values()
    )
