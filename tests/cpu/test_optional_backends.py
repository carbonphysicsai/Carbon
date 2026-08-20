"""Cold-start failure contracts for optional scientific backend adapters."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BUILTIN_CASES = (
    (
        "physicsnemo_fno",
        "PhysicsNeMoFNOWrapper",
        "carbon.backbones.physicsnemo",
    ),
    ("fno", "NeuralOperatorFNO", "carbon.backbones.neural_operator"),
    (
        "deeponet",
        "NeuralOperatorDeepONet",
        "carbon.backbones.neural_operator",
    ),
    ("uno", "NeuralOperatorUNO", "carbon.backbones.neural_operator"),
)
BUILTIN_BACKBONES = tuple(case[0] for case in BUILTIN_CASES)
BACKEND_CASES = (
    (
        "carbon.backbones.physicsnemo",
        "physicsnemo_fno",
        "physicsnemo",
        "physicsnemo",
    ),
    (
        "carbon.backbones.neural_operator",
        "fno",
        "neuralop",
        "neuraloperator",
    ),
)


def _run_isolated(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("registry_name", "wrapper_name", "adapter_module"),
    BUILTIN_CASES,
)
def test_each_builtin_resolves_cold_without_scientific_imports(
    tmp_path: Path,
    registry_name: str,
    wrapper_name: str,
    adapter_module: str,
) -> None:
    script = f"""
import importlib.abc
import json
import sys

blocked_roots = {{"torch", "neuralop", "physicsnemo"}}
adapter_modules = {{
    "carbon.backbones.physicsnemo",
    "carbon.backbones.neural_operator",
}}

class ScientificDependencyBlocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if fullname.partition(".")[0] in blocked_roots:
            self.attempted.append(fullname)
            raise ModuleNotFoundError(
                f"blocked optional dependency: {{fullname}}",
                name=fullname.partition(".")[0],
            )
        return None

blocker = ScientificDependencyBlocker()
sys.meta_path.insert(0, blocker)
assert adapter_modules.isdisjoint(sys.modules)

import carbon.backbones as backbones

adapters_before_list = sorted(adapter_modules.intersection(sys.modules))
names = backbones.list_backbones()
adapters_after_list = sorted(adapter_modules.intersection(sys.modules))
resolved = backbones.get_backbone({registry_name!r})
expected_wrapper = getattr(sys.modules[{adapter_module!r}], {wrapper_name!r})
same_wrapper = resolved is expected_wrapper
assert same_wrapper
loaded_adapters = sorted(adapter_modules.intersection(sys.modules))
loaded_scientific = sorted(
    name
    for name in sys.modules
    if name.partition(".")[0] in blocked_roots
)
print(json.dumps({{
    "adapters_after_list": adapters_after_list,
    "adapters_before_list": adapters_before_list,
    "attempted_scientific_imports": blocker.attempted,
    "loaded_adapter_modules": loaded_adapters,
    "loaded_scientific_modules": loaded_scientific,
    "names": names,
    "resolved": resolved.__name__,
    "same_wrapper": same_wrapper,
}}))
"""
    result = _run_isolated(tmp_path, script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "adapters_after_list": [],
        "adapters_before_list": [],
        "attempted_scientific_imports": [],
        "loaded_adapter_modules": [adapter_module],
        "loaded_scientific_modules": [],
        "names": sorted(BUILTIN_BACKBONES),
        "resolved": wrapper_name,
        "same_wrapper": True,
    }


@pytest.mark.parametrize(
    ("module_name", "registry_name", "dependency_root", "extra_name"),
    BACKEND_CASES,
)
def test_cold_registry_missing_backend_names_actionable_extra(
    tmp_path: Path,
    module_name: str,
    registry_name: str,
    dependency_root: str,
    extra_name: str,
) -> None:
    script = f"""
import importlib.abc
import json
import sys

dependency_root = {dependency_root!r}

class MissingBackendBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if fullname.partition(".")[0] == dependency_root:
            raise ModuleNotFoundError(
                f"No module named {{dependency_root!r}}",
                name=dependency_root,
            )
        return None

sys.meta_path.insert(0, MissingBackendBlocker())
assert {module_name!r} not in sys.modules

import carbon.backbones as backbones

assert {module_name!r} not in sys.modules
wrapper = backbones.get_backbone({registry_name!r})
try:
    wrapper()
except ModuleNotFoundError as exc:
    assert exc.name == dependency_root
    message = str(exc)
    assert "optional Carbon backend" in message
    assert {f'.[{extra_name}]'!r} in message
    assert "python -m pip install" in message
    print(json.dumps({{
        "dependency": exc.name,
        "message": message,
        "wrapper_module": wrapper.__module__,
    }}))
else:
    raise AssertionError("blocked optional backend was constructed")
"""
    result = _run_isolated(tmp_path, script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dependency"] == dependency_root
    assert f".[{extra_name}]" in payload["message"]
    assert payload["wrapper_module"] == module_name


@pytest.mark.parametrize(
    ("module_name", "registry_name"),
    tuple((case[0], case[1]) for case in BACKEND_CASES),
)
def test_cold_registry_does_not_mask_transitive_module_error(
    tmp_path: Path,
    module_name: str,
    registry_name: str,
) -> None:
    script = f"""
import json
import sys

assert {module_name!r} not in sys.modules

import carbon.backbones as backbones

wrapper = backbones.get_backbone({registry_name!r})
backend = sys.modules[{module_name!r}]
sentinel = ModuleNotFoundError(
    "No module named 'backend_transitive_dependency'",
    name="backend_transitive_dependency",
)

def broken_backend(module_name):
    del module_name
    raise sentinel

backend.import_module = broken_backend
try:
    wrapper()
except ModuleNotFoundError as exc:
    assert exc is sentinel
    assert exc.name == "backend_transitive_dependency"
    assert "optional Carbon backend" not in str(exc)
    print(json.dumps({{
        "dependency": exc.name,
        "message": str(exc),
        "same_exception": exc is sentinel,
    }}))
else:
    raise AssertionError("transitive backend failure was not raised")
"""
    result = _run_isolated(tmp_path, script)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "dependency": "backend_transitive_dependency",
        "message": "No module named 'backend_transitive_dependency'",
        "same_exception": True,
    }


def test_compatibility_registry_delegates_to_canonical_state(tmp_path: Path) -> None:
    script = """
import json

import carbon.backbones as canonical
from carbon.backbones import registry as compatibility

class RootRegistered:
    def __init__(self, value):
        self.value = value

class CompatibilityRegistered:
    pass

canonical.register_backbone("root_registered", RootRegistered)
constructed = compatibility.get_backbone("root_registered", value=7)
compatibility.register_backbone("compatibility_registered", CompatibilityRegistered)
resolved = canonical.get_backbone("compatibility_registered")

assert canonical.list_backbones() == compatibility.list_available_backbones()
print(json.dumps({
    "constructed_value": constructed.value,
    "resolved_name": resolved.__name__,
    "same_class": resolved is CompatibilityRegistered,
}))
"""
    result = _run_isolated(tmp_path, script)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "constructed_value": 7,
        "resolved_name": "CompatibilityRegistered",
        "same_class": True,
    }
