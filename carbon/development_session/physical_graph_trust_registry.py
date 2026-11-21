"""Per-version registration of the self-trust TRAINING values (SELF_TRUST DESIGN_v2, H3d-2c).

A trust candidate's phase-2 training (`physical_graph_trainer_v4`) needs, per version: the jax-traceable `derive` that maps the W
native physics columns to the k derived scored outputs, and the owner's values (a sigma floor per trust output, the phase-2
epochs, the learning rate). Those values are SCIENCE-adjacent and NEVER defaulted here: `REGISTRATIONS` is EMPTY until a version
registers one, and a value left `None` refuses typed at fit time (`trust_value_is_human_input`). So registering a trust
`Spec` (`Spec.trust_outputs`) without an entry here cannot train: `trust_spec` refuses `trust_version_not_registered`.

This module holds no judge authority and reads no participant code; it is staged into the trust build container with the trainer.
"""

from __future__ import annotations

from . import physical_graph_trainer_v4 as v4

#: (challenge_id, version) -> {"derive": callable, "sigma_floor": tuple | None, "epochs": int | None, "learning_rate": float | None}
REGISTRATIONS: dict = {}


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
