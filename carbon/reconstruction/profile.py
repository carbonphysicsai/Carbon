"""Exact compiler-plan to JAX-lab development profile mapping."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.construction import (
    ConstructionValidationError,
    DefaultedSurface,
    NotApplicableSurface,
    ResolvedConstructionPlan,
    SelectedSurface,
)
from carbon.reconstruction.model import ReconstructionFailure, ReconstructionProfile

UPSTREAM_WHEEL_DIGEST = (
    "sha256:3941af49fb7441b9ee37408db2b759bdc65088f0bda089f2a774adc3506935db"
)
IMPLEMENTATION_ID = "carbon_jax_lab"
IMPLEMENTATION_VERSION = "0.1.0"
ENVIRONMENT_ID = "carbon_jax_linux_x86_64_py311"
ENVIRONMENT_VERSION = "1.0"


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


ENVIRONMENT_DIGEST = _tagged(
    b"python==3.11.*\0jax==0.9.0.1\0jaxlib==0.9.0.1\0numpy==2.3.5\0scipy==1.17.0\0pyyaml==6.0.3\0linux-x86_64"
)
INPUT_INTERFACE_DIGEST = _tagged(
    b"u0[case,point]:float;nu[case]:float;t[case,time]:float;y[case,time,point]:float;x[point]:float;periodic-uniform-endpoint-excluded"
)
OUTPUT_INTERFACE_DIGEST = _tagged(
    b"prediction[case,time,point]:float32;requested-time-order;target-free-inference"
)
DEPENDENCY_SPECS = (
    ("jax", "0.9.0.1", _tagged(b"pypi:jax==0.9.0.1")),
    ("jaxlib", "0.9.0.1", _tagged(b"pypi:jaxlib==0.9.0.1")),
    ("numpy", "2.3.5", _tagged(b"pypi:numpy==2.3.5")),
    ("scipy", "1.17.0", _tagged(b"pypi:scipy==1.17.0")),
    ("pyyaml", "6.0.3", _tagged(b"pypi:pyyaml==6.0.3")),
)

_BACKBONES = {
    "fno": ("carbon_jax_fno1d", "fno1d"),
    "deeponet": ("carbon_jax_deeponet1d", "deeponet1d"),
}
_MODEL_DEFAULTS = {
    "width": 8,
    "depth": 1,
    "n_modes": 8,
    "heads": 2,
    "slices": 4,
    "wavelet_levels": 2,
    "graph_radius": 0.2,
    "latent_points": 12,
    "branch_points": 16,
    "expansion": 2,
    "remat": False,
}
_TASK_DEFAULTS = {
    "domain_length": 1.0,
    "time_scale": 0.3,
    "nu_scale": 0.05,
    "hard_initial_condition": True,
    "enforce_mean": False,
}
_TRAIN_DEFAULTS = {
    "steps": 8,
    "batch_size": 2,
    "microbatches": 1,
    "seed": 0,
    "learning_rate": 0.002,
    "min_learning_rate_ratio": 0.1,
    "warmup_steps": 1,
    "weight_decay": 0.0001,
    "clip_norm": 1.0,
    "beta1": 0.9,
    "beta2": 0.999,
    "adam_epsilon": 1e-8,
    "ema_decay": 0.99,
    "relative_loss": False,
    "h1_weight": 0.0,
    "pde_weight": 0.0,
    "physics_warmup_steps": 0,
    "inference_weights": "params",
}
_TARGETS = {
    **{("carbon_jax_lab_model", field): ("model", field) for field in _MODEL_DEFAULTS},
    **{("carbon_jax_lab_task", field): ("task", field) for field in _TASK_DEFAULTS},
    **{
        ("carbon_jax_lab_train", field): ("train", field)
        for field in _TRAIN_DEFAULTS
        if field != "seed"
    },
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _vendored_source_digest() -> str:
    root = Path(__file__).parent / "_vendor" / "carbon_jax_lab"
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def compile_development_profile(
    plan: ResolvedConstructionPlan,
) -> ReconstructionProfile:
    """Map one compiler/decoder-verified plan; reject every unbound surface."""
    if type(plan) is not ResolvedConstructionPlan:
        raise ReconstructionFailure("reconstruction.plan.type_invalid")
    try:
        plan_digest = plan.to_ref().content_digest
    except ConstructionValidationError:
        raise ReconstructionFailure("reconstruction.plan.unverified") from None

    backbone = plan.backbone_binding
    expected = _BACKBONES.get(backbone.selector_token)
    if (
        expected is None
        or backbone.backbone_id != expected[0]
        or backbone.backbone_version != "1.0"
    ):
        raise ReconstructionFailure("reconstruction.backbone.unsupported")
    if backbone.content_digest != UPSTREAM_WHEEL_DIGEST:
        raise ReconstructionFailure("reconstruction.backbone.digest_mismatch")
    implementation = backbone.implementation_pin
    if (
        implementation.implementation_id != IMPLEMENTATION_ID
        or implementation.implementation_version != IMPLEMENTATION_VERSION
        or implementation.content_digest != UPSTREAM_WHEEL_DIGEST
    ):
        raise ReconstructionFailure("reconstruction.implementation.pin_mismatch")
    environment = backbone.environment_pin
    if (
        environment.environment_id != ENVIRONMENT_ID
        or environment.environment_version != ENVIRONMENT_VERSION
        or environment.content_digest != ENVIRONMENT_DIGEST
    ):
        raise ReconstructionFailure("reconstruction.environment.pin_mismatch")
    if backbone.input_interface_pin.content_digest != INPUT_INTERFACE_DIGEST:
        raise ReconstructionFailure("reconstruction.input_interface.pin_mismatch")
    if backbone.output_interface_pin.content_digest != OUTPUT_INTERFACE_DIGEST:
        raise ReconstructionFailure("reconstruction.output_interface.pin_mismatch")
    observed_dependencies = tuple(
        (pin.dependency_id, pin.dependency_version, pin.content_digest)
        for pin in backbone.dependency_pins
    )
    if frozenset(observed_dependencies) != frozenset(DEPENDENCY_SPECS):
        raise ReconstructionFailure("reconstruction.dependency.pin_mismatch")
    if plan.resolved_components:
        raise ReconstructionFailure("reconstruction.component.unsupported")

    model = dict(_MODEL_DEFAULTS)
    model["kind"] = expected[1]
    task = dict(_TASK_DEFAULTS)
    train = dict(_TRAIN_DEFAULTS)
    mapped = []
    for surface in plan.resolved_surfaces:
        if surface.surface_id == backbone.surface_id:
            continue
        if type(surface) is NotApplicableSurface:
            mapped.append(
                {"surface_id": surface.surface_id, "status": "not_applicable"}
            )
            continue
        if type(surface) not in (SelectedSurface, DefaultedSurface):
            raise ReconstructionFailure("reconstruction.surface.type_invalid")
        key = (surface.consumer_target.consumer_id, surface.consumer_target.field_id)
        destination = _TARGETS.get(key)
        if destination is None:
            raise ReconstructionFailure("reconstruction.surface.unbound")
        group, field = destination
        target = {"model": model, "task": task, "train": train}[group]
        target[field] = surface.value.value
        mapped.append(
            {
                "surface_id": surface.surface_id,
                "consumer_id": key[0],
                "field_id": key[1],
                "source": (
                    "selected" if type(surface) is SelectedSurface else "defaulted"
                ),
                "value": surface.value.value,
            }
        )

    if (
        type(train["steps"]) is not int
        or type(train["warmup_steps"]) is not int
        or type(train["physics_warmup_steps"]) is not int
        or train["steps"] < 1
        or not 0 <= train["warmup_steps"] < train["steps"]
        or not 0 <= train["physics_warmup_steps"] < train["steps"]
    ):
        raise ReconstructionFailure("reconstruction.profile.train_invalid")

    receipt = {
        "schema": "carbon.c02.plan-mapping.v1",
        "backbone_surface_id": backbone.surface_id,
        "backbone_selector": backbone.selector_token,
        "fixed_values": {
            "model": _MODEL_DEFAULTS,
            "task": _TASK_DEFAULTS,
            "train": _TRAIN_DEFAULTS,
        },
        "mapped_surfaces": mapped,
        "seed_policy": "runtime DerivedSeed bytes; excluded from plan/profile identity",
    }
    body = {
        "schema": "carbon.c02.development-profile.v2",
        "plan_digest": plan_digest,
        "backbone_kind": expected[1],
        "model": model,
        "task": task,
        "train": train,
        "source_digest": _vendored_source_digest(),
        "environment_digest": ENVIRONMENT_DIGEST,
        "input_interface_digest": INPUT_INTERFACE_DIGEST,
        "output_interface_digest": OUTPUT_INTERFACE_DIGEST,
        "mapping": receipt,
    }
    profile_digest = _tagged(_canonical(body).encode("utf-8"))
    return ReconstructionProfile(
        profile_id="carbon_c02_jax_development",
        profile_version="2.0",
        profile_digest=profile_digest,
        plan_digest=plan_digest,
        backbone_kind=expected[1],
        model_config_json=_canonical(model),
        task_config_json=_canonical(task),
        train_config_json=_canonical(train),
        source_digest=body["source_digest"],
        environment_digest=ENVIRONMENT_DIGEST,
        input_interface_digest=INPUT_INTERFACE_DIGEST,
        output_interface_digest=OUTPUT_INTERFACE_DIGEST,
        mapping_receipt_json=_canonical(receipt),
    )


__all__ = [
    "DEPENDENCY_SPECS",
    "ENVIRONMENT_DIGEST",
    "ENVIRONMENT_ID",
    "ENVIRONMENT_VERSION",
    "IMPLEMENTATION_ID",
    "IMPLEMENTATION_VERSION",
    "INPUT_INTERFACE_DIGEST",
    "OUTPUT_INTERFACE_DIGEST",
    "UPSTREAM_WHEEL_DIGEST",
    "compile_development_profile",
]
