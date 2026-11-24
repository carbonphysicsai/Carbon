"""Ribbed Bracket 2.0's public construction material: its build module.

`f08_public` serves F08 1.x only: 6 inputs, 7 outputs, the 1.x TRAIN and the 1.x limits. RB 2.0 is a new interface, and
`f08_v2_train` is its one source: the inputs, the graded outputs, their units, the dtype and the TRAIN are read from
there, so no size, name, unit or value is written here.

A registry row names this module (``build.module``) and every build site asks it by version. Its functions are the build
module contract, each called as ``function(challenge_id, version)``.

**Fail closed.** `f08_v2_train.load_public_train` refuses while a ruling, an artifact sha or an output unit is
HUMAN_INPUT. Everything here that names the TRAIN goes through it, so the kit, the limits and the roles refuse with it.
Two things RB 2.0 has no registered material for are never filled in from 1.x:

- the ``important_limit_definition`` and ``design_objective`` roles (1.x's mass and compliance limits are its own): they
  are absent from `public_roles`, so they stay unbound in a manifest;
- a public development bank: `development_bank` refuses.

DEVELOPMENT only: no held-out reference, no evaluation authority.
"""

from __future__ import annotations

from . import f08_v2_train

SCOPE = "PUBLIC_F08_DEVELOPMENT_ONLY"
LIMITS_SCHEMA = "carbon.f08-ribbed-bracket.bundle-construction-limits.v2"
RESOURCE_SCHEMA = "carbon.f08-ribbed-bracket.reconstruction-resources.v1"
INTERFACE_SCHEMA = "carbon.f08-ribbed-bracket.construction-interface.v2"


def _digest(document: object) -> str:
    from carbon.development_session.profile import canonical, digest

    return digest(canonical(document))


def _check_identity(challenge_id: str, version: str) -> None:
    if (challenge_id, version) != (
        f08_v2_train.CHALLENGE_ID,
        f08_v2_train.CHALLENGE_VERSION,
    ):
        raise ValueError("unknown public RB 2.0 Challenge identity")


def load_public_train(challenge_id: str, version: str) -> dict:
    """`f08_v2_train.load_public_train`: refuses while anything it needs is HUMAN_INPUT."""
    _check_identity(challenge_id, version)
    return f08_v2_train.load_public_train(version)


def interface_document(challenge_id: str, version: str) -> dict:
    """One row per case: the inputs and the graded outputs in `f08_v2_train`'s order, under its names and units."""
    load_public_train(challenge_id, version)
    numeric = f08_v2_train.interface_document()
    inputs, outputs = numeric["input_names"], numeric["target_names"]
    return {
        "schema": INTERFACE_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "train_dtype": numeric["dtype"],
        "input": {
            "names": inputs,
            "units": numeric["input_units"],
            "shape": [len(inputs)],
        },
        "output": {
            "names": outputs,
            "units": numeric["target_units"],
            "shape": [len(outputs)],
            "named_slices": {
                name: [index, index + 1] for index, name in enumerate(outputs)
            },
        },
        "alloy_ids": numeric["alloy_ids"],
        "exact_outputs": numeric["exact_outputs"],
        "one_row_per_case": True,
        "learned_targets_only": True,
    }


def construction_limits_document(challenge_id: str, version: str) -> dict:
    """The TRAIN's identity and the C-03 envelope the version's builds and inferences run under."""
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    from . import served_versions, version_registry
    from .task_wall_overrides import total_wall_seconds

    provenance = load_public_train(challenge_id, version)["provenance"]
    entry = version_registry.entry(challenge_id, version)
    profile = _worker_profile(
        None,
        LIBRARY_BUILD_PROVENANCE,
        served_versions.worker_resources(challenge_id, version),
        rebuild_wall_seconds=entry.rebuild_wall_seconds,
    ).body
    document = {
        "schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": challenge_id, "version": version},
        "train_cases": len(provenance["case_ids"]),
        "train_dtype": f08_v2_train.interface_document()["dtype"],
        "train_case_ids_sha256": _digest(provenance["case_ids"]),
        "train_provenance_sha256": "sha256:" + f08_v2_train.PROVENANCE_SHA256,
        "train_mesh": f08_v2_train.RULINGS["mesh_statement"],
        "reconstruction_resource_policy": {
            "schema": RESOURCE_SCHEMA,
            "cpu_count_max": profile["cpu"]["count"],
            "memory_bytes_max": profile["memory"]["bytes"],
            "swap_bytes_max": profile["memory"]["swap_bytes"],
            "pids_max": profile["pids"],
            "nofile_max": profile["nofile_per_process"],
            "scratch_bytes_max": profile["scratch"]["bytes"],
            "scratch_inodes_max": profile["scratch"]["inodes"],
            "build_wall_seconds_max": profile["deadline_seconds"],
            "inference_wall_seconds_max": profile["deadline_seconds"],
            "total_reconstruction_wall_seconds_max": total_wall_seconds(
                challenge_id, version, entry.rebuild_wall_seconds
            ),
            "network": profile["security"]["network"],
            "cleanup_required": True,
        },
        "accuracy_gate": None,
        "live_eligible": False,
    }
    if not served_versions.step_caps(challenge_id, version):
        # OWNER-REBUILD-TIME-LIMIT-01: the build wall above is the only training limit (as f08_public)
        document["training_step_cap"] = None
        document["training_limit"] = "build_wall_seconds_max"
    if served_versions.serves_catalog(challenge_id, version):
        from carbon.backbone_catalog import served

        document["backbone_catalog"] = {
            "schema": served.SCHEMA,
            "digest": served.digest(challenge_id, version),
        }
    if entry.graph_adapter == "v2":
        from carbon.development_session import graph_adapters

        document["graph_training_adapter"] = graph_adapters.adapter_block(
            challenge_id, version
        )
    return document


def construction_kit(challenge_id: str, version: str) -> dict:
    """The five-field kit: the version's TRAIN, interface and limits, by digest."""
    train = load_public_train(challenge_id, version)
    return {
        "id": challenge_id,
        "version": version,
        "train_digest": train["provenance"]["train_sha256"],
        "interface_digest": _digest(interface_document(challenge_id, version)),
        "construction_limits_digest": _digest(
            construction_limits_document(challenge_id, version)
        ),
    }


def trusted_material(challenge_id: str, version: str) -> dict:
    """Fresh source-owned selector content for the separate worker guard."""
    return {
        "limits_document": construction_limits_document(challenge_id, version),
        "limits_schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "resource_schema": RESOURCE_SCHEMA,
    }


def development_bank(challenge_id: str, version: str) -> dict:
    """Refused: no public RB 2.0 development bank is registered, and 1.x's is another interface's."""
    _check_identity(challenge_id, version)
    raise ValueError("no public RB 2.0 development bank is registered (HUMAN_INPUT)")


def physics_contract(challenge_id: str, version: str) -> None:
    """No generated physics contract: `f08_20_dual_pack.physics_contract` is None for 2.0 too."""
    _check_identity(challenge_id, version)


def public_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    """The bound public roles' exact bytes; a role with no registered material is absent, never defaulted."""
    from carbon.development_session.profile import canonical

    return {
        "construction_kit": canonical(construction_kit(challenge_id, version)),
        "interface": canonical(interface_document(challenge_id, version)),
        "train": load_public_train(challenge_id, version)["train"],
    }
