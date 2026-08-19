"""Lazy wrappers for the optional NeuralOperator backend."""

from importlib import import_module

from . import register_backbone


def _models_module():
    try:
        return import_module("neuralop.models")
    except ModuleNotFoundError as exc:
        if exc.name != "neuralop":
            raise
        raise ModuleNotFoundError(
            "NeuralOperator is an optional Carbon backend. Install the "
            '`neuraloperator` extra with `python -m pip install -e ".[neuraloperator]"`.',
            name="neuralop",
        ) from exc


def _get_fno(in_channels=3, out_channels=1, modes=16, width=64, **kwargs):
    model = _models_module().FNO
    return model(
        in_channels=in_channels,
        out_channels=out_channels,
        modes=modes,
        width=width,
        **kwargs,
    )


def _get_deeponet(branch_net, trunk_net, **kwargs):
    model = _models_module().DeepONet
    return model(branch_net=branch_net, trunk_net=trunk_net, **kwargs)


def _get_uno(in_channels=3, out_channels=1, hidden_channels=64, **kwargs):
    model = _models_module().UNO
    return model(
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        **kwargs,
    )


class NeuralOperatorFNO:
    def __init__(
        self,
        in_channels: int = 3,
        out_channels: int = 1,
        modes: int = 16,
        width: int = 64,
        **kwargs,
    ):
        self.model = _get_fno(
            in_channels,
            out_channels,
            modes,
            width,
            **kwargs,
        )

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

    def __init__(
        self,
        in_channels: int = 3,
        out_channels: int = 1,
        hidden_channels: int = 64,
        **kwargs,
    ):
        self.model = _get_uno(
            in_channels,
            out_channels,
            hidden_channels,
            **kwargs,
        )

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)


# Registration is unconditional so registry users receive the same actionable
# missing-extra error as direct wrapper users. Installed-backend API and
# scientific compatibility remain explicitly unqualified by A1.
register_backbone("fno", NeuralOperatorFNO)
register_backbone("deeponet", NeuralOperatorDeepONet)
register_backbone("uno", NeuralOperatorUNO)
