"""CPU-only installation and canonical package-boundary tests."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CARBON_VERSION = "0.9.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROLE_PACKAGES = (
    "carbon.schema",
    "carbon.registry",
    "carbon.authoring",
    "carbon.construction",
    "carbon.resource_policy",
    "carbon.generators",
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
    "carbon.reconstruction",
    "carbon.research",
    "carbon.practice",
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

B02C_MODULES = (
    "carbon.resource_policy.errors",
    "carbon.resource_policy.refs",
    "carbon.resource_policy.model",
    "carbon.resource_policy.canonical",
    "carbon.resource_policy.service",
)

B03_MODULES = (
    "carbon.generators.accounting",
    "carbon.generators.authorities",
    "carbon.generators.burgers",
    "carbon.generators.burgers_dynamics",
    "carbon.generators.canonical",
    "carbon.generators.conformance",
    "carbon.generators.disclosure",
    "carbon.generators.errors",
    "carbon.generators.model",
    "carbon.generators.refs",
    "carbon.generators.service",
)

C_AUTH1_MODULES = (
    "carbon.authoring.cli",
    "carbon.authoring.goals",
)

B04_MODULES = (
    "carbon.evaluation.admission",
    "carbon.evaluation.assets",
    "carbon.evaluation.canonical",
    "carbon.evaluation.comparison",
    "carbon.evaluation.disclosure",
    "carbon.evaluation.enums",
    "carbon.evaluation.errors",
    "carbon.evaluation.execution",
    "carbon.evaluation.fixtures",
    "carbon.evaluation.model",
    "carbon.evaluation.policy",
    "carbon.evaluation.refs",
    "carbon.evaluation.runners",
)

B07A_MODULES = (
    "carbon.research.canonical",
    "carbon.research.discovery",
    "carbon.research.errors",
    "carbon.research.model",
    "carbon.research.providers",
    "carbon.research.refs",
)

B07B_MODULES = (
    "carbon.research.lifecycle",
    "carbon.research.records",
)

B07C_MODULES = (
    "carbon.practice.model",
    "carbon.practice.registry",
    "carbon.practice.service",
)

B07D_MODULES = (
    "carbon.prior_compat",
    "carbon.research.prior_provider",
    "carbon.research.prior_publisher",
    "carbon.research.prior_store",
)

B07E_MODULES = ("carbon.research.resource_estimation",)

B07F_MODULES = ("carbon.traineval.resolved_fixture",)

B07G_MODULES = ("carbon.research.service",)

C02_MODULES = (
    "carbon.reconstruction.model",
    "carbon.reconstruction.profile",
    "carbon.reconstruction.service",
)

INSTALLED_MODULES = (
    "carbon",
    *ROLE_PACKAGES,
    *B02B_MODULES,
    *B02C_MODULES,
    *B03_MODULES,
    *C_AUTH1_MODULES,
    *B04_MODULES,
    *B07A_MODULES,
    *B07B_MODULES,
    *B07C_MODULES,
    *B07D_MODULES,
    *B07E_MODULES,
    *B07F_MODULES,
    *B07G_MODULES,
    *C02_MODULES,
)


@pytest.fixture(scope="module")
def installed_wheel_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("installed-wheel")
    source = root / "source"
    source.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "README.md", source / "README.md")
    shutil.copytree(
        REPOSITORY_ROOT / "carbon",
        source / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    wheelhouse = root / "wheelhouse"
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheelhouse),
        ],
        cwd=source,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
    wheels = tuple(wheelhouse.glob("carbon-0.9.0-*.whl"))
    assert len(wheels) == 1

    installed = root / "installed"
    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(installed),
            str(wheels[0]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
    return installed


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


@pytest.mark.parametrize("module_name", B02C_MODULES)
def test_import_b02c_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B03_MODULES)
def test_import_b03_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B04_MODULES)
def test_import_b04_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B07A_MODULES)
def test_import_b07a_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B07B_MODULES)
def test_import_b07b_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B07D_MODULES)
def test_import_b07d_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B07E_MODULES)
def test_import_b07e_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize("module_name", B07F_MODULES)
def test_import_b07f_module(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


def test_distribution_identity() -> None:
    distribution = importlib.metadata.distribution("carbon")
    requirements = distribution.requires or ()

    assert distribution.metadata["Name"] == "carbon"
    assert distribution.version == CARBON_VERSION
    assert all("extra ==" in requirement.lower() for requirement in requirements)


def test_outside_tree_installed_imports(
    tmp_path: Path,
    installed_wheel_root: Path,
) -> None:
    assert tmp_path != REPOSITORY_ROOT
    assert REPOSITORY_ROOT not in tmp_path.parents

    script = f"""
import importlib
import importlib.metadata
import json
import pathlib
import sys

installed_root = pathlib.Path({json.dumps(str(installed_wheel_root))}).resolve()
sys.path.insert(0, str(installed_root))
module_names = {json.dumps(INSTALLED_MODULES)}
modules = [importlib.import_module(name) for name in module_names]
distribution = importlib.metadata.distribution("carbon")
vendor_root = installed_root / "carbon/reconstruction/_vendor/carbon_jax_lab/licenses"
license_files = [
    vendor_root / "NOTICE.md",
    vendor_root / "third_party/NEURALOPERATOR_LICENSE.txt",
    vendor_root / "third_party/TRANSOLVER_LICENSE.txt",
]
print(json.dumps({{
    "distribution_name": distribution.metadata["Name"],
    "distribution_version": distribution.version,
    "module_names": [module.__name__ for module in modules],
    "module_files": [str(pathlib.Path(module.__file__).resolve()) for module in modules],
    "license_files": [str(path) for path in license_files if path.is_file()],
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
        "module_files": payload["module_files"],
        "license_files": payload["license_files"],
    }
    assert all(
        module_file.startswith(f"{installed_wheel_root.resolve()}/carbon")
        for module_file in payload["module_files"]
    )
    assert len(payload["license_files"]) == 3
    assert all(
        license_file.startswith(
            f"{installed_wheel_root.resolve()}/carbon/reconstruction/_vendor/"
        )
        for license_file in payload["license_files"]
    )


def test_core_imports_without_optional_dependencies(
    tmp_path: Path,
    installed_wheel_root: Path,
) -> None:
    script = f"""
import importlib
import importlib.abc
import json
import pathlib
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
installed_root = pathlib.Path({json.dumps(str(installed_wheel_root))}).resolve()
sys.path.insert(0, str(installed_root))
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
