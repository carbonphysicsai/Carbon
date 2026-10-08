"""Every PyTorch battery family follows the device it is called on
(BATTERY-IMPL-3).

worker-images-v2's CUDA rebuild of `fno` trained on the GPU and then failed
predicting on the CPU: neuraloperator's grid embedding caches its grid as a
plain attribute, which `Module.to` does not move, so the cached CUDA grid met
CPU features. Implementation 3.0 places every tensor a family's modules hold
on the inputs' device before each call (`torch_training.follow_device`).

These tests call every family on the CPU and then on a second device: CUDA
where present, else PyTorch's `meta` device, which runs shapes without data.
Every tensor the network's modules hold, and its output, must be on the device
of the call. With CUDA the network is then called on the CPU again, as the
failing rebuild did, and must give the first CPU output exactly.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and (
        importlib.util.find_spec("torch") is None
        or importlib.util.find_spec("neuralop") is None
    ),
    reason="the science-torch group is not installed",
)
pytestmark = needs_torch

#: Every family the PyTorch backend builds (`torch_training.build_network`).
FAMILIES = ("mlp", "deeponet", "fno")
#: The battery grid: 121 points at 30 s, and two capacity checkpoints.
G, K, CASES = 121, 2, 3


def _network(family):
    import torch
    from test_battery_construction_contract import BATTERY, SMALL, strategy

    from carbon.battery import recipes, torch_training
    from carbon.battery.compile import compile_recipe

    parameters = {**SMALL[family], "backend": "pytorch"}
    recipe = compile_recipe(strategy(BATTERY, family, **parameters))[1]
    model = recipes.build(recipe.family, dict(recipe.values))
    model.layout = recipes.Layout(
        G,
        K,
        bounded_v=model.bounded_v,
        predict_v0=model.predict_v0,
        fade=model.fade,
    )
    dtype = torch_training.torch_dtype(model.settings["precision"])
    n_in = 6
    n_out = model.layout.nv + model.layout.nt + 1 + K
    generator = torch.Generator().manual_seed(0)
    network = torch_training.build_network(model, generator, n_in, n_out, dtype)
    f = torch.tensor(
        np.linspace(-1.0, 1.0, CASES * n_in).reshape(CASES, n_in), dtype=dtype
    )
    return network, f


def _held(network):
    """Every tensor the network's modules hold, cached attributes included."""
    import torch

    for module in network.modules:
        for sub in module.modules():
            yield from sub.parameters(recurse=False)
            yield from sub.buffers(recurse=False)
            for value in vars(sub).values():
                values = value if isinstance(value, (list, tuple)) else (value,)
                yield from (v for v in values if isinstance(v, torch.Tensor))


def _second_device():
    import torch

    return (
        torch.device("cuda", 0) if torch.cuda.is_available() else torch.device("meta")
    )


def _call(network, f, device):
    import torch

    with torch.no_grad():
        params = [p.detach().to(device) for p in network.params]
        out = network(params, f.to(device))
    assert out.device == device
    assert all(t.device == device for t in _held(network))
    return out


@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_follows_the_device_it_is_called_on(family):
    import torch

    cpu, second = torch.device("cpu"), _second_device()
    network, f = _network(family)
    first = _call(network, f, cpu)
    _call(network, f, second)
    if second.type == "meta":
        return  # a meta tensor has no data to bring back
    # Trained on the GPU, predicted on the CPU: worker-images-v2's failure.
    again = _call(network, f, cpu)
    assert torch.equal(first, again)


def test_the_fno_holds_a_cached_grid_that_module_to_leaves_behind():
    """The case the fix is for, so this test cannot pass vacuously: after a
    call, the FNO's grid embedding holds tensors `Module.to` does not move."""
    import torch

    network, f = _network("fno")
    _call(network, f, torch.device("cpu"))
    (module,) = network.modules
    registered = {id(t) for t in module.parameters()} | {
        id(t) for t in module.buffers()
    }
    cached = [t for t in _held(network) if id(t) not in registered]
    assert cached
    module.to(_second_device())
    assert any(t.device.type == "cpu" for t in _held(network))


def test_every_family_is_covered():
    from carbon.battery.torch_families import TORCH_FAMILIES

    assert set(FAMILIES) == {"mlp", "deeponet", *TORCH_FAMILIES}
