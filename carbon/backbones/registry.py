"""Simple backbone registry for multi-backend support."""

from typing import Callable, Dict, Any

_backbones: Dict[str, Callable] = {}


def register_backbone(name: str, factory: Callable):
    _backbones[name.lower()] = factory


def get_backbone(name: str, **kwargs):
    name = name.lower()
    if name not in _backbones:
        raise ValueError(f"Unknown backbone: {name}. Available: {list(_backbones.keys())}")
    return _backbones[name](**kwargs)


def list_available_backbones():
    return list(_backbones.keys())
