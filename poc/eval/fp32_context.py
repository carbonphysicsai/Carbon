"""Force fp32 (or stable float32) for physics gate / residual evaluation.

SPEC §11: Physics gates run in fp32 — not reduced precision.
PoC path is NumPy; we still force float32 arrays and optionally set JAX
matmul precision when jax is present.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import numpy as np


@contextmanager
def physics_fp32_context() -> Iterator[None]:
    """Context manager: JAX default matmul precision float32 if available."""
    prev = None
    try:
        import jax

        try:
            prev = jax.config.read("jax_default_matmul_precision")
        except Exception:
            prev = None
        try:
            jax.config.update("jax_default_matmul_precision", "float32")
        except Exception:
            pass
        yield
    except ImportError:
        yield
    finally:
        if prev is not None:
            try:
                import jax

                jax.config.update("jax_default_matmul_precision", prev)
            except Exception:
                pass


def as_fp32(*arrays: np.ndarray) -> tuple:
    """Cast arrays to float32 for gate metrics."""
    return tuple(np.asarray(a, dtype=np.float32) for a in arrays)
