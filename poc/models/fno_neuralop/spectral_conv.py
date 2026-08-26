"""1D SpectralConv, ported from `neuralop.layers.spectral_convolution.SpectralConv`.

Scope: dense (non-factorized) weights, real-valued data, order-1 only — the
configuration `neuralop.layers.spectral_convolution.SpectralConv` reduces to
for `factorization=None, separable=False, complex_data=False` on a single
spatial dimension. Tensor factorization, complex-valued data, domain
padding, and resolution scaling are out of scope for this port (see
`Design_Specs/Burgers_FNO_JAX_Neuraloperator_Parity.md` §3).

Algorithm (see the design note §4 for the empirical verification behind
each numbered step):

    1. m = n_modes // 2 + 1                    # rfft redundancy halving
    2. X = rfft(x, axis=-1, norm=fft_norm)      # (B, C_in, nx//2+1) complex
    3. W = weight_real + i * weight_imag        # (C_in, C_out, m)
    4. Y[..., :m] = einsum('bik,iok->bok', X[..., :m], W); Y[..., m:] = 0
    5. Y[..., 0].imag = 0; if nx even: Y[..., -1].imag = 0   # Hermitian enforcement
    6. y = irfft(Y, n=nx, axis=-1, norm=fft_norm)
    7. y = y + bias[None, :, None]

Step 5 was verified to be a numerical no-op on CPU (see design note §4.3)
but is kept for exactness against current upstream, which enables it by
default.
"""

from __future__ import annotations

import jax
import jax.numpy as jnp
import flax.linen as nn


class SpectralConv1D(nn.Module):
    """Dense, real-valued, 1D spectral convolution.

    Parameters
    ----------
    in_channels, out_channels : int
    n_modes : int
        Requested number of Fourier modes, matching the PyTorch
        `SpectralConv(in_channels, out_channels, (n_modes,), ...)` calling
        convention. The number of complex coefficients actually retained is
        `min(n_modes // 2 + 1, nx // 2 + 1)` — see module docstring step 1.
    bias : bool, default True
    fft_norm : str, default "forward"
        Matches the current `neuralop.layers.spectral_convolution.SpectralConv`
        default (the legacy module defaults to "backward").
    enforce_hermitian_symmetry : bool, default True
        Kept for exactness against upstream; verified to be a no-op on CPU
        for both PyTorch and JAX `irfft` (design note §4.3).
    """

    in_channels: int
    out_channels: int
    n_modes: int
    bias: bool = True
    fft_norm: str = "forward"
    enforce_hermitian_symmetry: bool = True
    param_dtype: jnp.dtype = jnp.float32

    def _kept_modes(self, nx: int) -> int:
        requested = self.n_modes // 2 + 1
        nfreq = nx // 2 + 1
        return min(requested, nfreq)

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """x: (batch, in_channels, nx) real -> (batch, out_channels, nx) real."""
        batch, in_channels, nx = x.shape
        if in_channels != self.in_channels:
            raise ValueError(
                f"expected in_channels={self.in_channels}, got {in_channels}"
            )

        kept_modes = self._kept_modes(nx)
        init_std = (2.0 / (self.in_channels + self.out_channels)) ** 0.5

        def _normal_init(key, shape, dtype):
            return init_std * jax.random.normal(key, shape, dtype=dtype)

        weight_real = self.param(
            "weight_real",
            _normal_init,
            (self.in_channels, self.out_channels, kept_modes),
            self.param_dtype,
        )
        weight_imag = self.param(
            "weight_imag",
            _normal_init,
            (self.in_channels, self.out_channels, kept_modes),
            self.param_dtype,
        )
        weight = weight_real + 1j * weight_imag

        x_ft = jnp.fft.rfft(x, axis=-1, norm=self.fft_norm)
        nfreq = x_ft.shape[-1]

        x_ft_low = x_ft[..., :kept_modes]
        out_low = jnp.einsum("bik,iok->bok", x_ft_low, weight)

        out_ft = jnp.zeros((batch, self.out_channels, nfreq), dtype=x_ft.dtype)
        out_ft = out_ft.at[..., :kept_modes].set(out_low)

        if self.enforce_hermitian_symmetry:
            out_ft = out_ft.at[..., 0].set(out_ft[..., 0].real.astype(out_ft.dtype))
            if nx % 2 == 0:
                out_ft = out_ft.at[..., -1].set(
                    out_ft[..., -1].real.astype(out_ft.dtype)
                )

        y = jnp.fft.irfft(out_ft, n=nx, axis=-1, norm=self.fft_norm)

        if self.bias:
            bias = self.param(
                "bias",
                _normal_init,
                (self.out_channels,),
                self.param_dtype,
            )
            y = y + bias[None, :, None]

        return y
