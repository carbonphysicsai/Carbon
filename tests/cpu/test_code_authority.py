"""Machine-enforced current/archived code-authority boundary."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import tomllib

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = REPOSITORY_ROOT / ".agent" / "CODE_AUTHORITY.toml"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
PREFLIGHT_PATH = REPOSITORY_ROOT / "scripts" / "dev" / "preflight.sh"
CI_PATH = REPOSITORY_ROOT / "scripts" / "dev" / "ci.sh"
DOCKERFILE_PATH = REPOSITORY_ROOT / ".devcontainer" / "Dockerfile"
DEVCONTAINER_PATH = REPOSITORY_ROOT / ".devcontainer" / "devcontainer.json"
DOCTOR_PATH = REPOSITORY_ROOT / "scripts" / "dev" / "doctor.sh"
VERIFY_IMAGE_PATH = REPOSITORY_ROOT / "scripts" / "dev" / "verify_image.sh"
DIFF_HYGIENE_PATH = REPOSITORY_ROOT / "scripts" / "dev" / "check_diff_hygiene.py"


def _workflow_job_blocks(workflow: str) -> dict[str, str]:
    """Return top-level job blocks without depending on line numbers."""

    lines = workflow.splitlines()
    jobs_line = next(
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"(?P<indent>\s*)jobs:\s*", line)
    )
    parent_indent = len(lines[jobs_line]) - len(lines[jobs_line].lstrip())
    job_indent: int | None = None
    starts: list[tuple[str, int]] = []
    for index in range(jobs_line + 1, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= parent_indent:
            break
        match = re.fullmatch(r"\s*([A-Za-z0-9_-]+):\s*", line)
        if match is None:
            continue
        if job_indent is None:
            job_indent = indent
        if indent == job_indent:
            starts.append((match.group(1), index))

    assert starts, "workflow has no jobs"
    blocks: dict[str, str] = {}
    for position, (job_id, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        blocks[job_id] = "\n".join(lines[start:end])
    return blocks


def _yaml_scalar(block: str, key: str) -> str:
    match = re.search(
        rf"^\s*{re.escape(key)}:\s*([^#\n]+?)\s*(?:#.*)?$",
        block,
        flags=re.MULTILINE,
    )
    assert match is not None, f"missing {key!r} in YAML block"
    return match.group(1)


def _inline_run_commands(block: str) -> tuple[str, ...]:
    commands = (
        match.group(1).strip()
        for match in re.finditer(r"^\s+run:\s+(\S.*)$", block, re.MULTILINE)
    )
    return tuple(command for command in commands if not command.startswith(("|", ">")))


def _authority() -> dict[str, Any]:
    with AUTHORITY_PATH.open("rb") as stream:
        return tomllib.load(stream)


def _run_git(*arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


def _git_at(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def _initialize_git_repository(repository: Path) -> str:
    repository.mkdir()
    commands = (
        ("init", "--quiet"),
        ("config", "user.name", "Carbon Test"),
        ("config", "user.email", "carbon-test@example.invalid"),
        ("config", "commit.gpgsign", "false"),
        ("config", "core.autocrlf", "false"),
    )
    for arguments in commands:
        process = _git_at(repository, *arguments)
        assert process.returncode == 0, process.stderr
    tracked = repository / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    assert _git_at(repository, "add", "--all").returncode == 0
    process = _git_at(repository, "commit", "--quiet", "--message", "base")
    assert process.returncode == 0, process.stderr
    return _git_at(repository, "rev-parse", "HEAD").stdout.strip()


def _create_package(root: Path, *parts: str) -> Path:
    package = root
    for part in parts:
        package /= part
        package.mkdir(exist_ok=True)
        init_path = package / "__init__.py"
        if not init_path.exists():
            init_path.write_text("", encoding="utf-8")
    return package


def _python_files(paths: Iterable[str]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for relative in paths:
        path = REPOSITORY_ROOT / relative
        assert path.exists(), f"canonical authority root is missing: {relative}"
        if path.is_file():
            if path.suffix == ".py":
                files.add(path)
            continue
        files.update(path.rglob("*.py"))
    return tuple(sorted(files))


def _matches_namespace(module: str, retired: tuple[str, ...]) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in retired)


def _source_package(path: Path) -> str | None:
    current = path.parent
    parts: list[str] = []
    while (current / "__init__.py").is_file():
        parts.append(current.name)
        current = current.parent
    if not parts:
        return None
    return ".".join(reversed(parts))


def _resolve_relative_name(
    path: Path,
    node: ast.AST,
    relative_name: str,
    package: str | None,
) -> str:
    assert (
        package is not None
    ), f"relative import has no package context: {path}:{node.lineno}"
    try:
        return importlib.util.resolve_name(relative_name, package)
    except ImportError as error:
        raise AssertionError(
            f"invalid relative import {relative_name!r} from package "
            f"{package!r}: {path}:{node.lineno}"
        ) from error


def _literal_string(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_strings(node: ast.expr | None) -> tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return ()
    return tuple(
        value
        for element in node.elts
        if (value := _literal_string(element)) is not None
    )


def _call_argument(
    node: ast.Call,
    position: int,
    keyword: str,
) -> ast.expr | None:
    if len(node.args) > position:
        return node.args[position]
    return next(
        (candidate.value for candidate in node.keywords if candidate.arg == keyword),
        None,
    )


def _import_bindings(
    tree: ast.AST,
) -> tuple[set[str], set[str], set[str], set[str]]:
    importlib_modules: set[str] = set()
    import_module_functions: set[str] = set()
    builtins_modules: set[str] = set()
    builtin_import_functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or (
                    alias.asname is None and alias.name.startswith("importlib.")
                ):
                    importlib_modules.add(alias.asname or "importlib")
                elif alias.name == "builtins":
                    builtins_modules.add(alias.asname or "builtins")
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == "importlib":
                import_module_functions.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "import_module"
                )
            elif node.module == "builtins":
                builtin_import_functions.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "__import__"
                )
    return (
        importlib_modules,
        import_module_functions,
        builtins_modules,
        builtin_import_functions,
    )


def _enclosing_scope(tree: ast.AST, node: ast.AST) -> str:
    scopes = (
        candidate
        for candidate in ast.walk(tree)
        if isinstance(candidate, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
        and candidate.lineno
        <= node.lineno
        <= (candidate.end_lineno or candidate.lineno)
    )
    enclosing = sorted(scopes, key=lambda candidate: candidate.lineno)
    return enclosing[-1].name if enclosing else "<module>"


def _import_analysis(
    path: Path,
) -> tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]]:
    """Resolve imports and inventory recognized nonliteral dynamic targets."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _source_package(path)
    (
        importlib_modules,
        import_module_functions,
        builtins_modules,
        builtin_import_functions,
    ) = _import_bindings(tree)
    modules: list[str] = []
    unresolved_dynamic: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module is None:
                    continue
                resolved_base = node.module
            else:
                relative_name = "." * node.level + (node.module or "")
                resolved_base = _resolve_relative_name(
                    path,
                    node,
                    relative_name,
                    package,
                )
            modules.append(resolved_base)
            modules.extend(
                f"{resolved_base}.{alias.name}"
                for alias in node.names
                if alias.name != "*"
            )
            continue
        if not isinstance(node, ast.Call):
            continue
        is_import_module = (
            isinstance(node.func, ast.Name) and node.func.id in import_module_functions
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in importlib_modules
        )
        is_builtin_import = (
            isinstance(node.func, ast.Name)
            and (
                node.func.id == "__import__" or node.func.id in builtin_import_functions
            )
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "__import__"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in builtins_modules
        )
        if not (is_import_module or is_builtin_import):
            continue
        target_node = _call_argument(node, 0, "name")
        target = _literal_string(target_node)
        if target is None:
            unresolved_dynamic.append(
                (
                    _enclosing_scope(tree, node),
                    ast.unparse(node.func),
                    (
                        ast.unparse(target_node)
                        if target_node is not None
                        else "<missing>"
                    ),
                )
            )
            continue
        if is_import_module and target.startswith("."):
            package_node = _call_argument(node, 1, "package")
            dynamic_package = _literal_string(package_node)
            if isinstance(package_node, ast.Name) and package_node.id == "__package__":
                dynamic_package = package
            target = _resolve_relative_name(
                path,
                node,
                target,
                dynamic_package,
            )
        elif is_builtin_import:
            level_node = _call_argument(node, 4, "level")
            level = level_node.value if isinstance(level_node, ast.Constant) else 0
            if isinstance(level, int) and level > 0:
                target = _resolve_relative_name(
                    path,
                    node,
                    "." * level + target,
                    package,
                )
        modules.append(target)
        if is_builtin_import:
            fromlist = _call_argument(node, 3, "fromlist")
            modules.extend(
                f"{target}.{member}" for member in _literal_strings(fromlist)
            )
    return tuple(modules), tuple(unresolved_dynamic)


def _resolved_import_targets(path: Path) -> tuple[str, ...]:
    return _import_analysis(path)[0]


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"literal assignment {name!r} is missing from {path}")


def _wheel_contains_namespace(name: str, namespace: str) -> bool:
    module_path = namespace.replace(".", "/")
    return (
        name == f"{module_path}.py"
        or name == f"{module_path}/__init__.py"
        or name.startswith(f"{module_path}/")
    )


def _contains_executable_material(path: Path) -> bool:
    if path.is_file() or path.is_symlink():
        return True
    return path.is_dir() and any(
        candidate.is_file() or candidate.is_symlink() for candidate in path.rglob("*")
    )


def test_authority_record_is_closed_and_archive_tag_is_exact() -> None:
    authority = _authority()
    assert set(authority) == {
        "schema_version",
        "decision",
        "archive",
        "canonical",
        "retired",
        "exceptions",
    }
    assert authority["schema_version"] == 1
    assert authority["decision"] == "B-01E-D1"
    assert authority["exceptions"] == {
        "runtime_imports": [],
        "executable_paths": [],
    }

    archive = authority["archive"]
    assert archive == {
        "tag": "archive/pre-wave-b-legacy-2026-08-30",
        "branch": "archive/legacy-prototypes",
        "commit": "4ee58d56862d0441d5d151d79db1fe3036f1025d",
        "tree": "9f767ea16ffb7185ab64acff2542c7a8dcc2e339",
        "index": "docs/history/LEGACY_CODE_INDEX.md",
        "authority": "Archive presence grants no current implementation authority.",
    }
    tag_ref = f"refs/tags/{archive['tag']}"
    assert _run_git("cat-file", "-t", tag_ref) == "tag"
    assert _run_git("rev-parse", f"{tag_ref}^{{}}") == archive["commit"]
    assert _run_git("rev-parse", f"{tag_ref}^{{tree}}") == archive["tree"]


def test_authority_lists_are_sorted_unique_and_disjoint() -> None:
    authority = _authority()
    canonical = authority["canonical"]
    retired = authority["retired"]
    for key in (
        "implementation_roots",
        "test_roots",
        "fixture_roots",
        "script_roots",
        "package_include",
    ):
        values = canonical[key]
        assert values == sorted(set(values)), key
    for key in ("runtime_namespaces", "executable_paths"):
        values = retired[key]
        assert values == sorted(set(values)), key

    canonical_paths = {
        path
        for key in ("implementation_roots", "test_roots", "script_roots")
        for path in canonical[key]
    }
    assert canonical_paths.isdisjoint(retired["executable_paths"])
    assert "carbon.backbones" not in retired["runtime_namespaces"]


def test_retired_executable_paths_are_absent_from_active_main() -> None:
    retired_paths = _authority()["retired"]["executable_paths"]
    unexpected = [
        path
        for path in retired_paths
        if _contains_executable_material(REPOSITORY_ROOT / path)
    ]
    assert unexpected == []


def test_retired_relative_imports_fail_namespace_boundary(tmp_path: Path) -> None:
    cards = _create_package(tmp_path, "carbon", "cards")
    internal = _create_package(tmp_path, "carbon", "cards", "internal")
    direct_source = cards / "relative_imports.py"
    direct_source.write_text(
        "from ..base import X\nfrom .. import protocol\n",
        encoding="utf-8",
    )
    deep_source = internal / "relative_imports.py"
    deep_source.write_text(
        "from ...common import Y\n",
        encoding="utf-8",
    )

    resolved = {
        *_resolved_import_targets(direct_source),
        *_resolved_import_targets(deep_source),
    }
    assert {"carbon.base", "carbon.common", "carbon.protocol"} <= resolved
    retired = ("carbon.base", "carbon.common", "carbon.protocol")
    violations = {module for module in resolved if _matches_namespace(module, retired)}
    assert {"carbon.base", "carbon.common", "carbon.protocol"} <= violations


def test_valid_canonical_relative_import_resolves_without_retired_match(
    tmp_path: Path,
) -> None:
    cards = _create_package(tmp_path, "carbon", "cards")
    source = cards / "valid_relative.py"
    source.write_text(
        "from .model import EvaluationCard\n",
        encoding="utf-8",
    )

    resolved = _resolved_import_targets(source)
    assert "carbon.cards.model" in resolved
    assert not any(
        _matches_namespace(module, ("carbon.base", "carbon.common", "poc"))
        for module in resolved
    )


def test_absolute_and_literal_dynamic_import_aliases_remain_enforced(
    tmp_path: Path,
) -> None:
    cards = _create_package(tmp_path, "carbon", "cards")
    source = cards / "dynamic_imports.py"
    source.write_text(
        """import builtins as builtin_loader
import importlib as loader
import importlib.util
from builtins import __import__ as load_builtin
from importlib import import_module as load_module

import carbon.base
from carbon import protocol

loader.import_module("carbon.common")
loader.import_module("..common", package="carbon.cards")
load_module("poc")
importlib.import_module(name="carbon.sciml")
builtin_loader.__import__("carbon.validator")
load_builtin("carbon.emission")
__import__(name="neurons")
computed_member = "not-statically-resolved"
__import__("carbon", fromlist=("miner", computed_member))
""",
        encoding="utf-8",
    )

    resolved = set(_resolved_import_targets(source))
    assert {
        "carbon.base",
        "carbon.common",
        "carbon.emission",
        "carbon.miner",
        "carbon.protocol",
        "carbon.sciml",
        "carbon.validator",
        "neurons",
        "poc",
    } <= resolved


def test_canonical_python_cannot_import_retired_namespaces() -> None:
    authority = _authority()
    canonical = authority["canonical"]
    retired = tuple(authority["retired"]["runtime_namespaces"])
    roots = (
        *canonical["implementation_roots"],
        *canonical["test_roots"],
        *canonical["script_roots"],
    )
    violations: list[tuple[str, str]] = []
    unresolved_dynamic: list[tuple[str, str, str, str]] = []
    for path in _python_files(roots):
        modules, unresolved = _import_analysis(path)
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        for module in modules:
            if _matches_namespace(module, retired):
                violations.append((relative_path, module))
        unresolved_dynamic.extend(
            (relative_path, scope, importer, expression)
            for scope, importer, expression in unresolved
        )
    assert violations == []
    assert sorted(unresolved_dynamic) == [
        (
            "carbon/backbones/__init__.py",
            "get_backbone",
            "import_module",
            "module_name",
        ),
        (
            "tests/cpu/test_package_installation.py",
            "test_import_a0_role_package",
            "importlib.import_module",
            "module_name",
        ),
        (
            "tests/cpu/test_package_installation.py",
            "test_import_b02b_module",
            "importlib.import_module",
            "module_name",
        ),
        (
            "tests/cpu/test_package_installation.py",
            "test_import_b02c_module",
            "importlib.import_module",
            "module_name",
        ),
        (
            "tests/cpu/test_package_installation.py",
            "test_import_b03_module",
            "importlib.import_module",
            "module_name",
        ),
    ]

    builtin_adapters = _literal_assignment(
        REPOSITORY_ROOT / "carbon" / "backbones" / "__init__.py",
        "_BUILTIN_ADAPTER_MODULES",
    )
    role_packages = _literal_assignment(
        REPOSITORY_ROOT / "tests" / "cpu" / "test_package_installation.py",
        "ROLE_PACKAGES",
    )
    b02b_modules = _literal_assignment(
        REPOSITORY_ROOT / "tests" / "cpu" / "test_package_installation.py",
        "B02B_MODULES",
    )
    b02c_modules = _literal_assignment(
        REPOSITORY_ROOT / "tests" / "cpu" / "test_package_installation.py",
        "B02C_MODULES",
    )
    b03_modules = _literal_assignment(
        REPOSITORY_ROOT / "tests" / "cpu" / "test_package_installation.py",
        "B03_MODULES",
    )
    assert isinstance(builtin_adapters, dict)
    assert isinstance(role_packages, tuple)
    assert isinstance(b02b_modules, tuple)
    assert isinstance(b02c_modules, tuple)
    assert isinstance(b03_modules, tuple)
    reviewed_dynamic_targets = {
        *builtin_adapters.values(),
        *role_packages,
        *b02b_modules,
        *b02c_modules,
        *b03_modules,
    }
    assert not any(
        _matches_namespace(module, retired) for module in reviewed_dynamic_targets
    )


def test_built_wheel_has_exact_generator_manifest_and_imports_outside_tree(
    tmp_path: Path,
) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheelhouse),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, f"{process.stdout}\n{process.stderr}"
    wheels = tuple(wheelhouse.glob("carbon-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = tuple(archive.namelist())

    retired = tuple(_authority()["retired"]["runtime_namespaces"])
    violations = sorted(
        (name, namespace)
        for name in names
        for namespace in retired
        if _wheel_contains_namespace(name, namespace)
    )
    assert violations == []

    canonical_packages = {
        root
        for root in _authority()["canonical"]["implementation_roots"]
        if root != "carbon/__init__.py"
    }
    assert all(f"{root}/__init__.py" in names for root in canonical_packages)

    b03_modules = _literal_assignment(
        REPOSITORY_ROOT / "tests" / "cpu" / "test_package_installation.py",
        "B03_MODULES",
    )
    assert isinstance(b03_modules, tuple)
    expected_generator_paths = {
        "carbon/generators/__init__.py",
        *(f"{module.replace('.', '/')}.py" for module in b03_modules),
    }
    actual_generator_paths = {
        name
        for name in names
        if name.startswith("carbon/generators/") and name.endswith(".py")
    }
    assert actual_generator_paths == expected_generator_paths

    outside = tmp_path / "outside"
    outside.mkdir()
    script = f"""
import importlib
import importlib.metadata
import json
import pathlib
import sys

wheel = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(wheel))
module_names = {json.dumps(b03_modules)}
modules = tuple(importlib.import_module(name) for name in module_names)
distribution = importlib.metadata.distribution("carbon")
requirements = distribution.requires or ()
print(json.dumps({{
    "module_names": [module.__name__ for module in modules],
    "module_files": [str(pathlib.Path(module.__file__).resolve()) for module in modules],
    "distribution_version": distribution.version,
    "only_optional_requirements": all(
        "extra ==" in requirement.lower() for requirement in requirements
    ),
}}))
"""
    imported = subprocess.run(
        [sys.executable, "-I", "-c", script, str(wheels[0])],
        cwd=outside,
        check=False,
        capture_output=True,
        text=True,
    )
    assert imported.returncode == 0, imported.stderr
    payload = json.loads(imported.stdout)
    assert payload["module_names"] == list(b03_modules)
    assert payload["distribution_version"] == "0.9.0"
    assert payload["only_optional_requirements"] is True
    assert all(
        module_file.startswith(f"{wheels[0].resolve()}/carbon/generators/")
        for module_file in payload["module_files"]
    )


def test_committed_diff_hygiene_rejects_clean_worktree_whitespace_defect(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    base = _initialize_git_repository(repository)
    (repository / "tracked.txt").write_text(
        "committed trailing whitespace \n",
        encoding="utf-8",
    )
    assert _git_at(repository, "add", "--all").returncode == 0
    commit = _git_at(
        repository,
        "commit",
        "--quiet",
        "--message",
        "committed whitespace defect",
    )
    assert commit.returncode == 0, commit.stderr
    assert _git_at(repository, "status", "--porcelain").stdout == ""

    old_gate = _git_at(repository, "diff", "--check")
    assert old_gate.returncode == 0, old_gate.stderr
    repaired_gate = subprocess.run(
        [
            sys.executable,
            str(DIFF_HYGIENE_PATH),
            "--repository",
            str(repository),
            "--base",
            base,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{repaired_gate.stdout}\n{repaired_gate.stderr}"
    assert repaired_gate.returncode == 1, output
    assert "the committed merge-base-to-HEAD range" in output
    assert "tracked.txt" in output
    assert "trailing whitespace" in output


def test_diff_hygiene_checks_both_sides_of_staged_and_committed_rename(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    _initialize_git_repository(repository)
    (repository / "tracked.txt").write_text(
        "existing trailing whitespace \n",
        encoding="utf-8",
    )
    assert _git_at(repository, "add", "tracked.txt").returncode == 0
    assert (
        _git_at(
            repository,
            "commit",
            "--quiet",
            "--message",
            "establish historical fixture",
        ).returncode
        == 0
    )
    base = _git_at(repository, "rev-parse", "HEAD").stdout.strip()
    destination = repository / ".agent/evidence/wave_b/tracked.txt"
    destination.parent.mkdir(parents=True)
    moved = _git_at(
        repository,
        "mv",
        "tracked.txt",
        ".agent/evidence/wave_b/tracked.txt",
    )
    assert moved.returncode == 0, moved.stderr

    staged = subprocess.run(
        [
            sys.executable,
            str(DIFF_HYGIENE_PATH),
            "--repository",
            str(repository),
            "--base",
            base,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    staged_output = f"{staged.stdout}\n{staged.stderr}"
    assert staged.returncode == 1, staged_output
    assert "staged changes" in staged_output
    assert ".agent/evidence/wave_b/tracked.txt" in staged_output

    committed = _git_at(
        repository,
        "commit",
        "--quiet",
        "--message",
        "move historical fixture",
    )
    assert committed.returncode == 0, committed.stderr
    committed_check = subprocess.run(
        [
            sys.executable,
            str(DIFF_HYGIENE_PATH),
            "--repository",
            str(repository),
            "--base",
            base,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    committed_output = f"{committed_check.stdout}\n{committed_check.stderr}"
    assert committed_check.returncode == 1, committed_output
    assert "the committed merge-base-to-HEAD range" in committed_output
    assert ".agent/evidence/wave_b/tracked.txt" in committed_output


def test_diff_hygiene_rejects_unresolvable_comparison_base(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _initialize_git_repository(repository)
    process = subprocess.run(
        [
            sys.executable,
            str(DIFF_HYGIENE_PATH),
            "--repository",
            str(repository),
            "--base",
            "missing-comparison-base",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{process.stdout}\n{process.stderr}"
    assert process.returncode == 2, output
    assert "Could not resolve comparison base" in output
    assert "Fetch the comparison history" in output


def test_devcontainer_runtime_user_and_verifier_are_fail_closed() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    user_directives = tuple(
        line.split(maxsplit=1)[1]
        for line in dockerfile.splitlines()
        if line.strip().upper().startswith("USER ")
    )
    assert user_directives[-1] == "ubuntu"
    assert "USER vscode" not in dockerfile
    assert "ARG USER_UID=1000" in dockerfile
    assert "ARG USER_GID=1000" in dockerfile
    assert "HOME=/home/ubuntu" in dockerfile
    assert (
        "CARBON_CANONICAL_DEV_ENV=ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"
        in dockerfile
    )

    devcontainer = json.loads(DEVCONTAINER_PATH.read_text(encoding="utf-8"))
    assert devcontainer["containerUser"] == "ubuntu"
    assert devcontainer["remoteUser"] == "ubuntu"
    assert devcontainer["updateRemoteUserUID"] is False
    assert "--platform=linux/amd64" in devcontainer["runArgs"]

    doctor = DOCTOR_PATH.read_text(encoding="utf-8")
    assert '[[ "$(id -un)" == "ubuntu" ]]' in doctor
    assert '[[ "$(id -u)" == "1000" ]]' in doctor
    assert '[[ "$(id -g)" == "1000" ]]' in doctor
    assert 'ldd_identity="$(ldd --version 2>&1 || true)"' in doctor
    assert "grep -Eqi 'glibc|GNU libc' <<< \"${ldd_identity}\"" in doctor
    assert "ldd --version 2>&1 | head -n 1 | grep" not in doctor

    verifier = VERIFY_IMAGE_PATH.read_text(encoding="utf-8")
    verifier_index = _run_git("ls-files", "--stage", "scripts/dev/verify_image.sh")
    assert verifier_index.startswith("100755 ")
    required_in_order = (
        "set -euo pipefail",
        "docker image inspect",
        "docker create --platform linux/amd64",
        "docker cp",
        "docker start",
        "{{.State.Running}}",
        "docker exec --user 0:0",
        "chown -R 1000:1000",
        'runtime_user="$("${container_exec[@]}" id -un)"',
        "CARBON_CANONICAL_DEV_ENV",
        "source /etc/os-release",
        "getconf GNU_LIBC_VERSION",
        "ldd --version",
        "uv --version",
        'uv_version="${uv_identity#uv }"',
        'uv_version="${uv_version%% *}"',
        "platform.python_version()",
        "find . -xdev",
        '[[ "${uv_version}" == "0.12.7" ]]',
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/doctor.sh",
        "./scripts/dev/ci.sh",
    )
    positions = tuple(verifier.index(fragment) for fragment in required_in_order)
    assert positions == tuple(sorted(positions))
    assert 'docker start "${container_id}" >/dev/null || true' not in verifier
    assert '"${container_exec[@]}" ./scripts/dev/ci.sh || true' not in verifier


def test_default_workflow_delegates_all_semantics_to_repository_scripts() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    jobs = _workflow_job_blocks(workflow)
    assert set(jobs) == {
        "preflight",
        "canonical",
        "dev-image",
        "contract-authority",
        "hub-validation",
        "derived-documentation",
        "merge-gate",
    }
    assert _yaml_scalar(jobs["preflight"], "name") == "Delivery preflight"
    assert _yaml_scalar(jobs["canonical"], "name") == "Canonical environment"
    assert _yaml_scalar(jobs["dev-image"], "name") == "Clean dev-container image"
    assert _yaml_scalar(jobs["canonical"], "needs") == "preflight"
    assert _yaml_scalar(jobs["dev-image"], "needs") == "preflight"

    assert _inline_run_commands(jobs["preflight"]) == (
        "./scripts/dev/ci_preflight.sh",
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/preflight.sh",
    )
    assert _inline_run_commands(jobs["canonical"]) == (
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/ci.sh",
    )
    assert _inline_run_commands(jobs["dev-image"]) == (
        './scripts/dev/verify_image.sh "${CARBON_DEV_IMAGE}"',
    )
    required_repository_commands = (
        "./scripts/dev/ci_preflight.sh",
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/preflight.sh",
        "./scripts/dev/ci.sh",
        './scripts/dev/verify_image.sh "${CARBON_DEV_IMAGE}"',
        "./scripts/dev/ci_contract_authority.sh",
        "./scripts/dev/ci_hub.sh",
        "./scripts/dev/ci_derived_documentation.sh",
        'python3 "${gate}"',
    )
    assert all(command in workflow for command in required_repository_commands)
    assert "runs-on: ubuntu-24.04" in workflow
    assert "ubuntu-latest" not in workflow
    assert "actions/setup-python" not in workflow
    assert "pip install" not in workflow
    assert "pytest" not in workflow
    assert "check_quality.py" not in workflow
    assert (
        "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8" in workflow
    )
    assert "file: .devcontainer/Dockerfile" in workflow
    assert "platforms: linux/amd64" in workflow
    assert "no-cache: true" in workflow
    assert "pull: true" in workflow
    assert "load: true" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        in jobs["canonical"]
    )
    assert "name: quality-inventory" in jobs["canonical"]
    assert "path: .carbon-artifacts/quality.json" in jobs["canonical"]
    assert jobs["dev-image"].index("docker/build-push-action") < jobs[
        "dev-image"
    ].index("./scripts/dev/verify_image.sh")
    for job in jobs.values():
        assert "continue-on-error" not in job

    trigger_contract = workflow.partition("\njobs:")[0]
    assert "pull_request:" in trigger_contract
    assert "branches: [main]" in trigger_contract
    assert "paths:" not in trigger_contract
    assert "paths-ignore:" not in trigger_contract
    assert "concurrency:" in trigger_contract

    assert workflow.count("name: Merge gate") == 1
    assert (
        "types: [opened, synchronize, reopened, edited, ready_for_review]" in workflow
    )
    assert "pull-requests: read" in workflow
    assert 'gh api "${endpoint}" --jq .head.sha' in workflow
    assert 'gh api "${endpoint}" --jq .base.sha' in workflow
    assert '"${candidate_sha}" != "${EVENT_PR_HEAD}"' in workflow
    assert "ref: ${{ steps.candidate.outputs.candidate_sha }}" in workflow
    assert workflow.count("ref: ${{ needs.preflight.outputs.candidate_sha }}") == 6
    assert workflow.count("fetch-depth: 0") == 7
    assert workflow.count("persist-credentials: false") == 8
    assert (
        jobs["preflight"].count(
            "if: steps.delivery.outputs.change_scope == 'RUNTIME_FULL'"
        )
        == 3
    )
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "github.event.pull_request.number || github.sha" in workflow
    assert 'CARBON_REQUIRE_DOCKER_TESTS: "1"' in workflow
    assert workflow.count("HUB_EXPECTED_CHANGE_SCOPE:") == 2
    assert "ref: ${{ needs.preflight.outputs.base_sha }}" in workflow
    assert "path: .carbon-gate-candidate" in workflow
    assert ".carbon-gate-base/scripts/dev/classify_changes.py" in workflow
    assert "one-time B-01F bootstrap change classifier" in workflow
    assert "--repository .carbon-gate-candidate" in workflow
    assert '[[ "${actual_candidate}" == "${CANDIDATE_SHA}" ]]' in workflow
    assert '[[ "${derived_scope}" != "${PREFLIGHT_SCOPE}" ]]' in workflow
    assert "BOOTSTRAP_BASE_SHA: c6302c7136fc5fa984b03660116f7daa7e3e3e48" in workflow
    assert '--scope "${derived_scope}"' in workflow
    assert '--scope "${{ needs.preflight.outputs.change_scope }}"' not in workflow
    assert "Using exact protected-base Merge gate implementation" in workflow
    assert "one-time B-01F bootstrap Merge gate implementation" in workflow
    assert "if: needs.preflight.outputs.change_scope == 'RUNTIME_FULL'" in workflow
    assert (
        "if: needs.preflight.outputs.change_scope == 'CONTRACT_AUTHORITY'" in workflow
    )
    assert (
        "if: needs.preflight.outputs.change_scope == 'DERIVED_DOCUMENTATION'"
        in workflow
    )
    assert "if: always()" in workflow
    assert "needs: [preflight, canonical, dev-image" in workflow
    assert workflow.index("\n  preflight:") < workflow.index("\n  canonical:")


def test_delivery_preflight_and_canonical_wrapper_are_machine_enforced() -> None:
    preflight = (REPOSITORY_ROOT / "scripts/dev/ci_preflight.sh").read_text(
        encoding="utf-8"
    )
    for required in (
        "scripts/dev/classify_changes.py",
        "scripts/dev/check_delivery_hygiene.py",
        "scripts/dev/check_diff_hygiene.py",
        '[[ "${actual_head}" == "${expected_head}" ]]',
        '"refs/heads/main"',
    ):
        assert required in preflight

    wrapper_path = REPOSITORY_ROOT / "scripts/dev/canonical.sh"
    wrapper = wrapper_path.read_text(encoding="utf-8")
    wrapper_index = _run_git("ls-files", "--stage", "scripts/dev/canonical.sh")
    if wrapper_index:
        assert wrapper_index.startswith("100755 ")
    for required in (
        "--platform linux/amd64",
        "--user 1000:1000",
        "--interactive --tty",
        "--dry-run",
        "--focused",
        "--full",
        "--interactive",
        "--git-common-dir",
        "-f /.dockerenv",
        "/etc/carbon-canonical-environment",
        "target=/carbon-source,readonly",
        "GIT_OPTIONAL_LOCKS=0",
        "target=/workspaces/Carbon/.venv",
        "target=/home/ubuntu/.cache/uv",
        "Docker is unavailable",
    ):
        assert required in wrapper


def test_hub_acceptance_enforces_decision_console_contract() -> None:
    command = "python3 docs/development/carbon_hub/tools/test_decisions.py"
    hub_script = (REPOSITORY_ROOT / "scripts/dev/ci_hub.sh").read_text(encoding="utf-8")

    assert command in hub_script


def test_fast_preflight_owns_the_cheap_fail_closed_gate() -> None:
    preflight = PREFLIGHT_PATH.read_text(encoding="utf-8")
    preflight_index = _run_git("ls-files", "--stage", "scripts/dev/preflight.sh")
    assert preflight_index.startswith("100755 ")
    required_in_order = (
        "set -euo pipefail",
        'echo "==> environment doctor"',
        "./scripts/dev/doctor.sh",
        'echo "==> quality ratchet"',
        "scripts/check_quality.py",
        "--baseline .ci/quality-baseline.json",
        '--base "${quality_base}"',
        'echo "==> committed and local Git diff hygiene"',
        "scripts/dev/check_diff_hygiene.py",
        'echo "Carbon fast preflight gates passed."',
    )
    positions = tuple(preflight.index(fragment) for fragment in required_in_order)
    assert positions == tuple(sorted(positions))
    assert '--report "${artifact_dir}/quality.json"' in preflight
    assert "pytest" not in preflight
    assert "./scripts/dev/test.sh" not in preflight
    assert "verify_image.sh" not in preflight
    assert "docker" not in preflight.lower()
    assert "|| true" not in preflight

    retired_paths = _authority()["retired"]["executable_paths"]
    assert [path for path in retired_paths if path in preflight] == []


def test_default_ci_script_invokes_no_archived_path() -> None:
    ci_source = CI_PATH.read_text(encoding="utf-8")
    preflight_source = PREFLIGHT_PATH.read_text(encoding="utf-8")
    required_in_order = (
        'echo "==> delivery scope and repository hygiene"',
        'echo "==> fast preflight"',
        "./scripts/dev/preflight.sh",
        'echo "==> invariant lane"',
        'echo "==> default CPU lane"',
        'echo "==> package, wheel, and outside-tree lane"',
        'echo "==> canonical/legacy authority boundary"',
        'echo "==> terminal committed and local Git diff hygiene"',
    )
    positions = tuple(ci_source.index(fragment) for fragment in required_in_order)
    retired_paths = _authority()["retired"]["executable_paths"]
    violations = [
        path for path in retired_paths if path in ci_source or path in preflight_source
    ]
    assert positions == tuple(sorted(positions))
    assert ci_source.count("scripts/dev/check_diff_hygiene.py") == 1
    assert preflight_source.count("scripts/dev/check_diff_hygiene.py") == 1
    assert violations == []
    assert "tests/invariants" in ci_source
    assert "./scripts/dev/test.sh" in ci_source
    assert "scripts/dev/classify_changes.py" in ci_source
    assert "scripts/dev/check_delivery_hygiene.py" in ci_source
    assert "scripts/check_quality.py" in preflight_source
    assert "scripts/dev/check_diff_hygiene.py" in preflight_source
    assert "scripts/dev/check_diff_hygiene.py" in ci_source
    assert 'QUALITY_BASE_SHA="${quality_base}" ./scripts/dev/preflight.sh' in ci_source
    assert ci_source.count('--base "${quality_base}"') == 3
    assert '--base "${quality_base_ref}"' not in ci_source
    assert "\ngit diff --check\n" not in ci_source
    assert "tests/cpu/test_package_installation.py" in ci_source
    assert "tests/cpu/test_code_authority.py" in ci_source
