"""CPU-only installation and canonical package-boundary tests."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest

CARBON_VERSION = "0.9.0"
ROLE_PACKAGES = (
    "carbon.schema",
    "carbon.registry",
    "carbon.authoring",
    "carbon.construction",
    "carbon.seeding",
    "carbon.scoring",
    "carbon.cards",
    "carbon.fees",
    "carbon.traineval",
    "carbon.mcp",
    "carbon.leaderboard",
    "carbon.logging_utils",
    "carbon.evaluation",
    "carbon.audit",
    "carbon.chain",
    "carbon.qualification",
)

B02B_MODULES = (
    "carbon.fees.strategy_identity",
    "carbon.construction.errors",
    "carbon.construction.refs",
    "carbon.construction.model",
    "carbon.construction.canonical",
    "carbon.construction.catalog",
    "carbon.construction.policy",
    "carbon.construction.plan",
    "carbon.construction.compiler",
)

INSTALLED_MODULES = ("carbon", *ROLE_PACKAGES, *B02B_MODULES)


def test_import_carbon() -> None:
    module = importlib.import_module("carbon")

    assert module.__name__ == "carbon"
    assert module.__version__ == CARBON_VERSION


def test_training_policy_builder_is_not_a_public_bypass() -> None:
    construction = importlib.import_module("carbon.construction")

    assert not hasattr(construction, "build_training_sampling_policy")


@pytest.mark.parametrize("module_name", ROLE_PACKAGES)
def test_import_a0_role_package(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B02B_MODULES)
def test_import_b02b_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


def test_distribution_identity() -> None:
    distribution = importlib.metadata.distribution("carbon")

    assert distribution.metadata["Name"] == "carbon"
    assert distribution.version == CARBON_VERSION


def test_outside_tree_installed_imports(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert tmp_path != repository_root
    assert repository_root not in tmp_path.parents

    script = f"""
import importlib
import importlib.metadata
import json

module_names = {json.dumps(INSTALLED_MODULES)}
modules = [importlib.import_module(name) for name in module_names]
distribution = importlib.metadata.distribution("carbon")
print(json.dumps({{
    "distribution_name": distribution.metadata["Name"],
    "distribution_version": distribution.version,
    "module_names": [module.__name__ for module in modules],
}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "distribution_name": "carbon",
        "distribution_version": CARBON_VERSION,
        "module_names": list(INSTALLED_MODULES),
    }


def test_core_imports_without_optional_dependencies(tmp_path: Path) -> None:
    script = f"""
import importlib
import importlib.abc
import json
import sys

blocked_roots = {{
    "bittensor",
    "black",
    "docker",
    "econml",
    "h5py",
    "jax",
    "neuralop",
    "neuraloperator",
    "nvidia",
    "numpy",
    "pandas",
    "physicsnemo",
    "pysr",
    "pytest",
    "ruff",
    "scipy",
    "sklearn",
    "torch",
    "torchvision",
    "tqdm",
    "yaml",
}}

class OptionalDependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.partition(".")[0]
        if root in blocked_roots:
            raise ModuleNotFoundError(
                f"blocked optional dependency: {{fullname}}",
                name=root,
            )
        return None

sys.meta_path.insert(0, OptionalDependencyBlocker())
module_names = {json.dumps(INSTALLED_MODULES)}
modules = [importlib.import_module(name) for name in module_names]
print(json.dumps([module.__name__ for module in modules]))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == list(INSTALLED_MODULES)
