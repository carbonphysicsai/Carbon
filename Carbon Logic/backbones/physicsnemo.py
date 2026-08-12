"""PhysicsNeMo backbone wrapper (existing integration)."""

try:
    from physicsnemo.models import FNO as PhysicsNeMoFNO
    PHYSICSNEMO_AVAILABLE = True
except ImportError:
    PHYSICSNEMO_AVAILABLE = False
    PhysicsNeMoFNO = None


from . import register_backbone


class PhysicsNeMoFNOWrapper:
    """Wrapper for PhysicsNeMo FNO."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1, **kwargs):
        if not PHYSICSNEMO_AVAILABLE:
            raise ImportError("physicsnemo not installed")
        self.model = PhysicsNeMoFNO(in_channels=in_channels, out_channels=out_channels, **kwargs)

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


if PHYSICSNEMO_AVAILABLE:
    register_backbone("physicsnemo_fno", PhysicsNeMoFNOWrapper)
