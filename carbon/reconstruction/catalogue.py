"""Prospective discovery of registered DEVELOPMENT reconstruction implementations.

This catalogue describes code, not host availability, grants, scientific
qualification or permission to access data. Existing campaign catalogues and
their content identities are unchanged. Discovery never initializes a numerical
runtime or observes a device.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from carbon.reconstruction import profile
from carbon.reconstruction.worker.model import PROFILE_ID, PROFILE_VERSION

CATALOGUE_SCHEMA = "carbon.reconstruction-capabilities.v1"


@dataclass(frozen=True)
class ReconstructionCapability:
    """One exact supported implementation; family alone cannot select it."""

    architecture_family: str
    backbone_id: str
    backbone_version: str
    backbone_kind: str
    implementation_id: str
    implementation_version: str
    implementation_digest: str
    reconstruction_profile_id: str
    reconstruction_profile_version: str
    training_objectives: tuple[str, ...]
    current_research_selection: bool
    language: str = "python"
    framework: str = "jax"
    backend: str = "cpu"
    environment_id: str = profile.ENVIRONMENT_ID
    environment_version: str = profile.ENVIRONMENT_VERSION
    environment_digest: str = profile.ENVIRONMENT_DIGEST
    input_interface_digest: str = profile.INPUT_INTERFACE_DIGEST
    output_interface_digest: str = profile.OUTPUT_INTERFACE_DIGEST
    worker_profile_id: str = PROFILE_ID
    worker_profile_version: str = PROFILE_VERSION
    prediction_contract: str = (
        "target-free requested physical times; [case,time,point] float32"
    )
    applicability: str = "1D periodic viscous Burgers; uniform endpoint-excluded grid; carbon_burgers_native_v1"
    precision: str = (
        "float32 model and prediction; physical scaling must be representable"
    )
    evidence_use: str = "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    host_availability: str = "NOT_OBSERVED"


_CAPABILITIES = (
    ReconstructionCapability(
        "fno",
        "carbon_jax_fno1d",
        "1.0",
        "fno1d",
        profile.IMPLEMENTATION_ID,
        profile.IMPLEMENTATION_VERSION,
        profile.UPSTREAM_WHEEL_DIGEST,
        "carbon_c02_jax_development",
        "3.0",
        (
            "TRAIN RMS normalized squared error",
            "optional relative data loss",
            "optional H1 spectral derivative loss",
            "optional Burgers PDE residual loss",
        ),
        True,
    ),
    ReconstructionCapability(
        "deeponet",
        "carbon_jax_deeponet1d",
        "1.0",
        "deeponet1d",
        profile.IMPLEMENTATION_ID,
        profile.IMPLEMENTATION_VERSION,
        profile.UPSTREAM_WHEEL_DIGEST,
        "carbon_c02_jax_development",
        "3.0",
        (
            "TRAIN RMS normalized squared error",
            "optional relative data loss",
            "optional H1 spectral derivative loss",
            "optional Burgers PDE residual loss",
        ),
        True,
    ),
    ReconstructionCapability(
        "physics_attention",
        "carbon_jax_physics_attention1d",
        "1.0",
        "physics_attention1d",
        profile.IMPLEMENTATION_ID,
        profile.IMPLEMENTATION_VERSION,
        profile.UPSTREAM_WHEEL_DIGEST,
        "carbon_c02_jax_development",
        "3.0",
        (
            "TRAIN RMS normalized squared error",
            "optional relative data loss",
            "optional H1 spectral derivative loss",
            "optional Burgers PDE residual loss",
        ),
        True,
    ),
    ReconstructionCapability(
        "fno",
        "foundax_fno1d",
        "0.2.0",
        "foundax_fno1d",
        profile.FOUNDAX_IMPLEMENTATION_ID,
        profile.FOUNDAX_IMPLEMENTATION_VERSION,
        profile.FOUNDAX_WHEEL_DIGEST,
        "carbon_c02_foundax_fno_development",
        "3.0",
        ("TRAIN RMS normalized squared error",),
        False,
    ),
)


def reconstruction_capabilities() -> tuple[ReconstructionCapability, ...]:
    """Return compiler-supported implementations without probing installations."""
    return _CAPABILITIES


def capability_projection(*, audience: str) -> dict[str, object]:
    """Return fresh public metadata for a consumer, never an authorization grant.

    All three audiences receive the same public implementation facts. Validator
    case selection, Workbench draft access and miner campaign selection remain
    with their existing services. A validator projection contains no protected
    case data or additional execution authority.
    """
    if type(audience) is not str or audience not in ("miner", "validator", "workbench"):
        raise ValueError("unsupported capability audience")
    return {
        "schema": CATALOGUE_SCHEMA,
        "audience": audience,
        "scope": "public implementation metadata; admission and data access remain separate",
        "implementations": [asdict(item) for item in _CAPABILITIES],
        "limitations": [
            "Campaign assembly and resource grants determine selectable operations.",
            "Current research selection describes the existing lab-only recipe route, not permission to execute.",
            "CPU registration does not establish device availability or worker isolation.",
            "GPU/TPU execution and native Julia tasks are not supplied by this catalogue.",
            "No scientific, protected-evaluation or production qualification is asserted.",
        ],
    }
