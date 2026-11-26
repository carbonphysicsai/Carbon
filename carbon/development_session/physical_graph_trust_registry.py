"""Per-version registration of the self-trust TRAINING values (SELF_TRUST DESIGN_v2, H3d-2c).

A trust candidate's phase-2 training (`physical_graph_trainer_v4`) needs, per version: the jax-traceable `derive` that maps the W
native physics columns to the k derived scored outputs, and the owner's values (a sigma floor per trust output, the phase-2
epochs, the learning rate). Those values are SCIENCE-adjacent and NEVER defaulted here: `REGISTRATIONS` holds only the versions that
registered one in code (none on this tree); every other registered version's are its exam registry build row's (`registered`), and a value
left `None` refuses typed at fit time (`trust_value_is_human_input`). So registering a trust
`Spec` (`Spec.trust_outputs`) without an entry here cannot train: `trust_spec` refuses `trust_version_not_registered`.

This module holds no judge authority and reads no participant code; it is staged into the trust build container with the trainer.
"""

from __future__ import annotations

import json

from . import physical_graph_trainer_v4 as v4

#: (challenge_id, version) -> {"derive": callable, "sigma_floor": tuple | None, "epochs": int | None, "learning_rate": float | None}
REGISTRATIONS: dict = {}


#: The one file that carries a registry version's trust values into its build container, beside its derive module.
STAGED_TRUST = "graph-trust.json"
_STAGED_FIELDS = {
    "challenge_id",
    "version",
    "sigma_floor",
    "epochs",
    "learning_rate",
}


def staged_trust(challenge_id: str, version: str, values: dict) -> bytes:
    """The bytes a registry version's trust build container is staged with: its key and the owner's values, no more."""
    return json.dumps(
        {
            "challenge_id": challenge_id,
            "version": version,
            **{
                name: values[name]
                for name in ("sigma_floor", "epochs", "learning_rate")
            },
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def registered(challenge_id: str, version: str) -> dict | None:
    """The trust registration of a version registered by data, or None: on the host from its build row
    (`carbon.challenge_registry.exam_build`), in its build container from the staged values and derive module.
    """
    from . import physical_graph_adapter_v2 as adapter

    if adapter._ON_HOST:
        from carbon.challenge_registry import exam_build

        values = exam_build.trust(challenge_id, version)
        derive = exam_build.trust_derive(challenge_id, version)
    else:
        staged = adapter._TREE / STAGED_TRUST
        if not staged.is_file():
            return None
        values = json.loads(staged.read_bytes())
        if set(values) != _STAGED_FIELDS or (
            values["challenge_id"],
            values["version"],
        ) != (challenge_id, version):
            raise ValueError("staged graph trust differs")
        from . import registered_trust_derive

        derive = registered_trust_derive.derive
    if values is None:
        return None
    return {
        "derive": derive,
        "sigma_floor": tuple(values["sigma_floor"]),
        "epochs": values["epochs"],
        "learning_rate": values["learning_rate"],
    }


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
        entry = registered(challenge_id, version)
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
