"""Machine-enforced current/archived code-authority boundary."""

from __future__ import annotations

import ast
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


def _absolute_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module is None:
                continue
            modules.append(node.module)
            if node.module == "carbon":
                modules.extend(f"carbon.{alias.name}" for alias in node.names)
            continue
        if not isinstance(node, ast.Call) or not node.args:
            continue
        is_dynamic_import = (
            isinstance(node.func, ast.Name) and node.func.id == "__import__"
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
        )
        if is_dynamic_import:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                modules.append(first.value)
    return tuple(modules)


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
    for path in _python_files(roots):
        for module in _absolute_imports(path):
            if _matches_namespace(module, retired):
                violations.append(
                    (path.relative_to(REPOSITORY_ROOT).as_posix(), module)
                )
    assert violations == []


def test_built_wheel_excludes_every_retired_runtime_namespace(tmp_path: Path) -> None:
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


def test_default_workflow_delegates_all_semantics_to_repository_scripts() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    run_commands = tuple(
        line.partition("run:")[2].strip()
        for line in workflow.splitlines()
        if re.match(r"^\s+run:\s+\S", line)
    )
    assert run_commands == (
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/ci.sh",
    )
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


def test_default_ci_script_invokes_no_archived_path() -> None:
    ci_source = (REPOSITORY_ROOT / "scripts" / "dev" / "ci.sh").read_text(
        encoding="utf-8"
    )
    retired_paths = _authority()["retired"]["executable_paths"]
    violations = [path for path in retired_paths if path in ci_source]
    assert violations == []
    assert "tests/invariants" in ci_source
    assert "./scripts/dev/test.sh" in ci_source
    assert "scripts/check_quality.py" in ci_source
    assert "tests/cpu/test_package_installation.py" in ci_source
    assert "tests/cpu/test_code_authority.py" in ci_source
