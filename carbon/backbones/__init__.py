"""Backbone registry for Hydrogen.

Supports multiple neural operator implementations:
- PhysicsNeMo (NVIDIA)
- NeuralOperator library (community standard)
"""

from typing import Dict, Type, Any

_backbones: Dict[str, Type] = {}


def register_backbone(name: str, cls: Type):
    _backbones[name.lower()] = cls


def get_backbone(name: str):
    name = name.lower()
    if name not in _backbones:
        raise ValueError(f"Unknown backbone: {name}. Available: {list(_backbones.keys())}")
    return _backbones[name]


def list_backbones():
    return list(_backbones.keys())
