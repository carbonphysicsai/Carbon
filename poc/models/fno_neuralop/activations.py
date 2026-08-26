"""Shared activation helpers, pinned to match PyTorch defaults exactly.

`jax.nn.gelu` defaults to `approximate=True` (tanh approximation); PyTorch's
`torch.nn.functional.gelu` — the default `non_linearity` throughout
`neuralop` — defaults to the exact erf-based formula. Verified empirically:
the two differ by up to ~4e-4 on `x` in `[-4, 4]`, which would blow through
the fp32 parity tolerance used by these tests. Every activation in this
port must use `exact_gelu`, not `jax.nn.gelu` directly.
"""

from __future__ import annotations

import functools

import jax.nn as jnn

exact_gelu = functools.partial(jnn.gelu, approximate=False)
