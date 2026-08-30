"""Public-package and owner-boundary checks for B-02A."""

from __future__ import annotations

import ast
import hashlib
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from carbon import authoring

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORING_MODULES = (
    "carbon.authoring",
    "carbon.authoring.canonical",
    "carbon.authoring.cases",
    "carbon.authoring.errors",
    "carbon.authoring.evidence",
    "carbon.authoring.graph",
    "carbon.authoring.history",
    "carbon.authoring.loading",
    "carbon.authoring.model",
    "carbon.authoring.physical",
    "carbon.authoring.populations",
    "carbon.authoring.primitives",
    "carbon.authoring.refs",
    "carbon.authoring.sampling",
    "carbon.authoring.training_support",
)


def test_authoring_root_is_an_ordered_explicit_allow_list() -> None:
    assert type(authoring.__all__) is list
    assert authoring.__all__ == sorted(authoring.__all__)
    assert len(authoring.__all__) == len(set(authoring.__all__))
    assert all(name in vars(authoring) for name in authoring.__all__)


def test_protected_and_capability_types_are_not_root_convenience_exports() -> None:
    forbidden = {
        "AuthoringHistoryStore",
        "AuthoringOriginIssuer",
        "CanonicalChallengeCase",
        "CanonicalChallengeCaseRef",
        "FixtureAuthoringCapability",
        "InternalCaseIdentityProjection",
        "LoadedAuthoringArtifact",
        "ProtectedCaseIdentityProjection",
        "StoreBackedScientificAuthoringVerifier",
    }

    assert forbidden.isdisjoint(authoring.__all__)
    assert all(not hasattr(authoring, name) for name in forbidden)


def test_exact_internal_types_remain_available_only_from_explicit_modules() -> None:
    cases = importlib.import_module("carbon.authoring.cases")
    graph = importlib.import_module("carbon.authoring.graph")
    history = importlib.import_module("carbon.authoring.history")
    refs = importlib.import_module("carbon.authoring.refs")

    assert cases.CanonicalChallengeCase.__module__ == "carbon.authoring.cases"
    assert refs.CanonicalChallengeCaseRef.__module__ == "carbon.authoring.refs"
    assert history.AuthoringHistoryStore.__module__ == "carbon.authoring.history"
    assert (
        graph.StoreBackedScientificAuthoringVerifier.__module__
        == "carbon.authoring.graph"
    )


def test_b02a_package_does_not_implement_reserved_r_strategy() -> None:
    package_root = Path(authoring.__file__).resolve().parent
    implementation_names = {
        "ResolvedTrainingSamplingPolicy",
        "TrainingSamplingPolicyRef",
    }

    for module_path in package_root.glob("*.py"):
        text = module_path.read_text(encoding="utf-8")
        for reserved_name in implementation_names:
            assert f"class {reserved_name}" not in text
            assert f"def {reserved_name}" not in text


def test_source_dependency_direction_is_authoring_to_a3_only() -> None:
    package_root = Path(authoring.__file__).resolve().parent
    for module_path in package_root.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: tuple[str, ...]
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = (node.module,)
            else:
                continue
            for module_name in imported:
                if module_name.startswith("carbon."):
                    assert module_name == "carbon.authoring" or module_name.startswith(
                        ("carbon.authoring.", "carbon.registry")
                    )

    registry_root = package_root.parent / "registry"
    for module_path in registry_root.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("carbon.authoring")
            for node in ast.walk(tree)
        )


def test_fresh_no_dependency_wheel_imports_every_authoring_module_outside_tree(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "README.md", source / "README.md")
    shutil.copytree(
        REPOSITORY_ROOT / "carbon",
        source / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    builder = None
    checked: set[str] = set()
    for candidate in (sys.executable, getattr(sys, "_base_executable", None)):
        if type(candidate) is not str or candidate in checked:
            continue
        checked.add(candidate)
        probe = subprocess.run(
            [candidate, "-I", "-c", "import setuptools, wheel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            builder = candidate
            break
    assert builder is not None

    environment_values = os.environ.copy()
    environment_values.update(
        {
            "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    build = subprocess.run(
        [
            builder,
            "-m",
            "pip",
            "wheel",
            "--no-cache-dir",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(wheelhouse.glob("carbon-0.9.0-*.whl"))
    wheel_digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert len(wheel_digest) == 64

    environment = tmp_path / "venv"
    create = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert create.returncode == 0, create.stderr
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == wheel_digest

    outside = tmp_path / "outside"
    outside.mkdir()
    script = f"""
import importlib
import importlib.abc
import importlib.metadata
import pathlib
import sys

blocked_roots = {{
    "aiohttp", "bittensor", "docker", "fastapi", "jax", "neuralop",
    "numpy", "opentelemetry", "pandas", "physicsnemo", "prometheus_client",
    "pydantic", "requests", "scipy", "sklearn", "statsd", "torch", "yaml",
}}
blocked_carbon = (
    "carbon.cards", "carbon.chain", "carbon.evaluation", "carbon.fees",
    "carbon.leaderboard", "carbon.mcp", "carbon.observability",
    "carbon.qualification", "carbon.scoring", "carbon.seeding",
    "carbon.traineval", "carbon.challenges", "carbon.data", "carbon.physics",
)
attempted = []

class DependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition(".")[0]
        if root in blocked_roots or any(
            fullname == prefix or fullname.startswith(prefix + ".")
            for prefix in blocked_carbon
        ):
            attempted.append(fullname)
            raise ModuleNotFoundError(f"blocked dependency: {{fullname}}", name=fullname)
        return None

sys.meta_path.insert(0, DependencyBlocker())
module_names = {AUTHORING_MODULES!r}
modules = tuple(importlib.import_module(name) for name in module_names)
root = modules[0]
distribution = importlib.metadata.distribution("carbon")
requirements = distribution.requires or ()

assert distribution.version == "0.9.0"
assert all("extra ==" in requirement.lower() for requirement in requirements)
assert root.__all__ == sorted(root.__all__)
assert tuple(module.__name__ for module in modules) == module_names
assert {str(source)!r} not in {{
    str(pathlib.Path(module.__file__).resolve()) for module in modules
}}
assert attempted == []
assert not any(name.startswith(("carbon.challenges", "carbon.data", "carbon.physics")) for name in sys.modules)
"""
    result = subprocess.run(
        [str(python), "-I", "-c", script],
        cwd=outside,
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
