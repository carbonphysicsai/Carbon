"""Lazy wrapper for the optional NVIDIA PhysicsNeMo backend."""

from importlib import import_module

from . import register_backbone


def _fno_class():
    try:
        module = import_module("physicsnemo.models.fno")
    except ModuleNotFoundError as exc:
        if exc.name != "physicsnemo":
            raise
        raise ModuleNotFoundError(
            "PhysicsNeMo is an optional Carbon backend. Install the "
            '`physicsnemo` extra with `python -m pip install -e ".[physicsnemo]"`.',
            name="physicsnemo",
        ) from exc
    return module.FNO


class PhysicsNeMoFNOWrapper:
    """Wrapper for the documented PhysicsNeMo FNO model API."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1, **kwargs):
        model = _fno_class()
        self.model = model(
            in_channels=in_channels,
            out_channels=out_channels,
            **kwargs,
        )

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


register_backbone("physicsnemo_fno", PhysicsNeMoFNOWrapper)
