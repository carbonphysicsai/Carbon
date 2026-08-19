"""Failure-contract tests for optional scientific backend adapters."""

from __future__ import annotations

import importlib

import pytest

BACKEND_CASES = (
    (
        "carbon.backbones.physicsnemo",
        "PhysicsNeMoFNOWrapper",
        "physicsnemo_fno",
        "physicsnemo",
        "physicsnemo",
    ),
    (
        "carbon.backbones.neural_operator",
        "NeuralOperatorFNO",
        "fno",
        "neuralop",
        "neuraloperator",
    ),
)


@pytest.mark.parametrize(
    (
        "module_name",
        "wrapper_name",
        "registry_name",
        "dependency_root",
        "extra_name",
    ),
    BACKEND_CASES,
)
def test_missing_backend_names_actionable_extra(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    wrapper_name: str,
    registry_name: str,
    dependency_root: str,
    extra_name: str,
) -> None:
    backend = importlib.import_module(module_name)
    registry = importlib.import_module("carbon.backbones")
    wrapper = getattr(backend, wrapper_name)

    assert registry.get_backbone(registry_name) is wrapper

    def missing_backend(_module_name: str):
        raise ModuleNotFoundError(
            f"No module named {dependency_root!r}",
            name=dependency_root,
        )

    monkeypatch.setattr(backend, "import_module", missing_backend)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        registry.get_backbone(registry_name)()

    assert exc_info.value.name == dependency_root
    message = str(exc_info.value)
    assert "optional Carbon backend" in message
    assert f".[{extra_name}]" in message
    assert "python -m pip install" in message


@pytest.mark.parametrize(
    (
        "module_name",
        "wrapper_name",
        "registry_name",
        "dependency_root",
        "extra_name",
    ),
    BACKEND_CASES,
)
def test_backend_does_not_mask_transitive_module_error(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    wrapper_name: str,
    registry_name: str,
    dependency_root: str,
    extra_name: str,
) -> None:
    del registry_name, dependency_root, extra_name
    backend = importlib.import_module(module_name)

    def broken_backend(_module_name: str):
        raise ModuleNotFoundError(
            "No module named 'backend_transitive_dependency'",
            name="backend_transitive_dependency",
        )

    monkeypatch.setattr(backend, "import_module", broken_backend)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        getattr(backend, wrapper_name)()

    assert exc_info.value.name == "backend_transitive_dependency"
    assert "optional Carbon backend" not in str(exc_info.value)
