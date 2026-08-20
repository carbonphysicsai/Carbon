"""Canonical registry for Carbon backbone adapters.

Built-in names resolve through local Carbon adapter modules. Those modules keep
their third-party scientific imports lazy until an adapter is constructed.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

BackboneFactory = Callable[..., Any]

_BUILTIN_ADAPTER_MODULES = {
    "physicsnemo_fno": "carbon.backbones.physicsnemo",
    "fno": "carbon.backbones.neural_operator",
    "deeponet": "carbon.backbones.neural_operator",
    "uno": "carbon.backbones.neural_operator",
}
_backbones: dict[str, BackboneFactory] = {}


def register_backbone(name: str, factory: BackboneFactory) -> None:
    """Register a backbone class or factory in the canonical store."""
    _backbones[name.lower()] = factory


def get_backbone(name: str) -> BackboneFactory:
    """Resolve a backbone class or factory, loading a local adapter if needed."""
    normalized_name = name.lower()
    module_name = _BUILTIN_ADAPTER_MODULES.get(normalized_name)
    if normalized_name not in _backbones and module_name is not None:
        import_module(module_name)

    if normalized_name not in _backbones:
        raise ValueError(
            f"Unknown backbone: {normalized_name}. Available: {list_backbones()}"
        )
    return _backbones[normalized_name]


def list_backbones() -> list[str]:
    """List registered and built-in adapter names without loading adapters."""
    return sorted(_BUILTIN_ADAPTER_MODULES.keys() | _backbones.keys())
