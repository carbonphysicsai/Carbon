"""Per-version registration of the self-trust TRAINING values (SELF_TRUST DESIGN_v2, H3d-2c).

A trust candidate's phase-2 training (`physical_graph_trainer_v4`) needs, per version: the jax-traceable `derive` that maps the W
native physics columns to the k derived scored outputs, and the owner's values (a sigma floor per trust output, the phase-2
epochs, the learning rate). Those values are SCIENCE-adjacent and NEVER defaulted here: `REGISTRATIONS` holds only the versions that
registered one (today Motor 1.9), and a value left `None` refuses typed at fit time (`trust_value_is_human_input`). So registering a trust
`Spec` (`Spec.trust_outputs`) without an entry here cannot train: `trust_spec` refuses `trust_version_not_registered`.

This module holds no judge authority and reads no participant code; it is staged into the trust build container with the trainer.
"""

from __future__ import annotations

from . import physical_graph_trainer_v4 as v4

#: (challenge_id, version) -> {"derive": callable, "sigma_floor": tuple | None, "epochs": int | None, "learning_rate": float | None}
REGISTRATIONS: dict = {}


def _motor19():
    """Motor 1.9 (owner MOTOR19-TRUST-REGISTRATION + MOTOR19-TRUST-FLOOR-0, 23 Nov 2026; model-eval 5619 / 5667): k = 5 in pool
    order (`motor19_trust_derive.OUTPUTS`), the derive with emf_scalar 'rms' (on the two EMF outputs trust covers the RMS
    AMPLITUDE of the waveform, not its graded shape), sigma floor 0 for every output (no floor: Motor's U lives only in the
    sealed pack, so no public U can be a floor; door-code 5669 / v2 5674), and epochs / learning rate BY REFERENCE to the
    version's main trainer: the registered defaults of its training surfaces (`TRAIN_SURFACES_V3` steps 512, learning_rate
    0.002), read here, never retyped."""
    from . import motor19_trust_derive as derive
    from .physical_graph_adapter_v2 import TRAIN_SURFACES_V3

    return {
        "derive": derive.make_derive("rms"),
        "sigma_floor": (0.0,) * len(derive.OUTPUTS),
        "epochs": TRAIN_SURFACES_V3["steps"][2],
        "learning_rate": TRAIN_SURFACES_V3["learning_rate"][2],
    }


REGISTRATIONS[("electric-motor-magnetics", "1.9")] = _motor19()


def trust_spec(
    challenge_id: str,
    version: str,
    *,
    width: int,
    outputs: int,
    trust_parameters: tuple,
) -> v4.TrustSpec:
    """The version's `TrustSpec`, with the structural fields from the validated graph; refuses typed when the version registered
    nothing (the owner's values are never invented here)."""
    entry = REGISTRATIONS.get((challenge_id, version))
    if entry is None:
        raise v4.TrustRefused("trust_version_not_registered")
    return v4.TrustSpec(
        width=width,
        outputs=outputs,
        derive=entry.get("derive"),
        trust_parameters=tuple(trust_parameters),
        sigma_floor=entry.get("sigma_floor"),
        epochs=entry.get("epochs"),
        learning_rate=entry.get("learning_rate"),
    )
