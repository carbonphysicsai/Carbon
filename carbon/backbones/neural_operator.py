"""NeuralOperator library backbone wrappers.

Supports multiple models from the neuraloperator package.
"""

try:
    from neuralop.models import FNO, DeepONet, UNO
    NEURALOPERATOR_AVAILABLE = True
except ImportError:
    NEURALOPERATOR_AVAILABLE = False
    FNO = None
    DeepONet = None
    UNO = None


from . import register_backbone


def _get_fno(in_channels=3, out_channels=1, modes=16, width=64, **kwargs):
    if not NEURALOPERATOR_AVAILABLE:
        raise ImportError("neuraloperator not installed")
    return FNO(in_channels=in_channels, out_channels=out_channels, modes=modes, width=width, **kwargs)


def _get_deeponet(branch_net, trunk_net, **kwargs):
    if not NEURALOPERATOR_AVAILABLE:
        raise ImportError("neuraloperator not installed")
    return DeepONet(branch_net=branch_net, trunk_net=trunk_net, **kwargs)


def _get_uno(in_channels=3, out_channels=1, hidden_channels=64, **kwargs):
    if not NEURALOPERATOR_AVAILABLE:
        raise ImportError("neuraloperator not installed")
    return UNO(in_channels=in_channels, out_channels=out_channels, hidden_channels=hidden_channels, **kwargs)


class NeuralOperatorFNO:
    def __init__(self, in_channels: int = 3, out_channels: int = 1, modes: int = 16, width: int = 64, **kwargs):
        self.model = _get_fno(in_channels, out_channels, modes, width, **kwargs)

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


class NeuralOperatorDeepONet:
    def __init__(self, branch_net, trunk_net, **kwargs):
        self.model = _get_deeponet(branch_net, trunk_net, **kwargs)

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


class NeuralOperatorUNO:
    """U-shaped Neural Operator (UNO)."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1, hidden_channels: int = 64, **kwargs):
        self.model = _get_uno(in_channels, out_channels, hidden_channels, **kwargs)

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


# Register all
if NEURALOPERATOR_AVAILABLE:
    register_backbone("fno", NeuralOperatorFNO)
    register_backbone("deeponet", NeuralOperatorDeepONet)
    register_backbone("uno", NeuralOperatorUNO)
