"""Battery families only the PyTorch backend rebuilds (OWNER-PYTORCH-BACKEND-01).

Each builds a `torch_training.Network`: a flat, ordered list of tensors and an
`apply(params, features)` that returns the same normalized outputs `z` as the
dense families, in the same column layout, so the shared target layout, loss,
structure head and prediction format apply unchanged.

* ``fno``: neuraloperator 2.0's Fourier neural operator over the 30 s time
  grid. The input features, broadcast over the 121 time points, are its input
  channels; its own grid embedding adds the time coordinate. Its two output
  channels are the voltage and temperature trajectories. A dense head on the
  same features gives plating margin and the capacity checkpoints.
  ``width`` is its hidden channels, ``depth`` its Fourier layers and
  ``n_modes`` the modes each layer keeps. Everything else is neuraloperator's
  default for the pinned version. Its spectral weights are complex64, so it
  trains in float32 only (the compiler refuses float64 by name). Carbon holds
  each complex weight as its real view, a trailing axis of (real, imaginary),
  so every optimizer and the stored state see real tensors only.

Module parameters are initialized under a seed drawn from Carbon's generator,
inside a forked global RNG, so a rebuild never reads or disturbs any other
random state.
"""

from __future__ import annotations

import torch

from .torch_training import Network, _flatten, apply_stack, dense_stack


def _seeded_module(generator, factory):
    seed = int(torch.randint(0, 2**62, (1,), generator=generator))
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        return factory()


def fno_network(model, generator, n_in, n_out, dtype):
    from neuralop.models import FNO

    if dtype is not torch.float32:
        raise ValueError("the FNO family trains in float32 only")
    s, layout = model.settings, model.layout
    module = _seeded_module(
        generator,
        lambda: FNO(
            n_modes=(s["n_modes"],),
            in_channels=n_in,
            out_channels=2,
            hidden_channels=model.width,
            n_layers=model.depth,
        ),
    )
    module.eval()
    names, complex_ = zip(
        *((name, p.is_complex()) for name, p in module.named_parameters())
    )
    head = dense_stack(generator, [n_in, model.width, 1 + layout.k], "he_normal", dtype)
    count = len(names)
    first_v = 0 if layout.predict_v0 else 1
    if layout.nv + layout.nt + 1 + layout.k != n_out:
        raise ValueError("the FNO output layout does not match the targets")

    def apply(params, f):
        x = f[:, :, None].expand(-1, -1, layout.g)
        weights = {
            name: torch.view_as_complex(p) if c else p
            for name, c, p in zip(names, complex_, params[:count])
        }
        out = torch.func.functional_call(module, weights, (x,))
        tail = params[count:]
        scalars = apply_stack(
            [tail[2 * i : 2 * i + 2] for i in range(len(tail) // 2)],
            f,
            "gelu",
            "none",
        )
        return torch.cat([out[:, 0, first_v:], out[:, 1, 1:], scalars], dim=1)

    params = [
        (torch.view_as_real(p) if p.is_complex() else p).detach().clone()
        for p in module.parameters()
    ] + _flatten(head)
    return Network(params, apply)


TORCH_FAMILIES = {"fno": fno_network}
