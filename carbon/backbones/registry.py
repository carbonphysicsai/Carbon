"""Compatibility API for constructing backbones from the canonical registry."""

from __future__ import annotations

from typing import Any

from . import BackboneFactory
from . import get_backbone as _resolve_backbone
from . import list_backbones as _list_backbones
from . import register_backbone as _register_backbone


def register_backbone(name: str, factory: BackboneFactory) -> None:
    """Register a backbone in the package-owned canonical registry."""
    _register_backbone(name, factory)


def get_backbone(name: str, **kwargs: Any) -> Any:
    """Construct a backbone while preserving this module's historical API."""
    return _resolve_backbone(name)(**kwargs)


def list_available_backbones() -> list[str]:
    """Return names from the package-owned canonical registry."""
    return _list_backbones()
