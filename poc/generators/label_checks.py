"""Sanity checks on procedural labels before they enter train/eval.

Periodic viscous Burgers conserves ∫u dx (mean on uniform grid).
Bad labels → fail generation rather than silently poison scoring.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from poc.generators.burgers1d import BurgersBatch

# Mean mass drift allowed on reference labels (numerical IMEX error)
LABEL_MASS_TAU = 5e-3


def label_mass_errors(batch: BurgersBatch) -> np.ndarray:
    """Per-sample |mean(uT) - mean(u0)|."""
    return np.abs(batch.uT.mean(axis=-1) - batch.u0.mean(axis=-1))


def check_label_conservation(
    batch: BurgersBatch,
    tau: float = LABEL_MASS_TAU,
) -> Tuple[bool, Dict[str, Any]]:
    errs = label_mass_errors(batch)
    mean_err = float(np.mean(errs))
    max_err = float(np.max(errs))
    ok = bool(max_err <= tau and np.isfinite(errs).all())
    return ok, {
        "passed": ok,
        "mean_mass_err": mean_err,
        "max_mass_err": max_err,
        "tau": tau,
        "role": batch.role,
        "n": int(batch.u0.shape[0]),
    }


def assert_labels_ok(batch: BurgersBatch, tau: float = LABEL_MASS_TAU) -> None:
    ok, info = check_label_conservation(batch, tau=tau)
    if not ok:
        raise RuntimeError(
            f"label conservation failed role={batch.role}: "
            f"max_mass_err={info['max_mass_err']:.3e} > tau={tau}"
        )
