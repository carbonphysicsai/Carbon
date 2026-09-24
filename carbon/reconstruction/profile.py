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
from carbon.reconstruction.scaling import BurgersPhysicalScaling

UPSTREAM_WHEEL_DIGEST = (
    "sha256:3941af49fb7441b9ee37408db2b759bdc65088f0bda089f2a774adc3506935db"
)
IMPLEMENTATION_ID = "carbon_jax_lab"
IMPLEMENTATION_VERSION = "0.1.1"
FOUNDAX_IMPLEMENTATION_ID = "foundax"
FOUNDAX_IMPLEMENTATION_VERSION = "0.2.0"
FOUNDAX_REVISION = "b02b1da52bb03cfad8e437983fc1d1e411e78b04"
FOUNDAX_WHEEL_DIGEST = (
    "sha256:9240526f8bcf9860033807404c6e2402dfb10a73ed75088409c37aa58a6fc9b2"
)
FOUNDAX_LICENSE_DIGEST = (
    "sha256:209fe24bf55677bbf81c2b0481c1403201fab57b3b4c609971eba4ec8162b99c"
)
ENVIRONMENT_ID = "carbon_jax_linux_x86_64_py311"
ENVIRONMENT_VERSION = "2.0"


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


ENVIRONMENT_DIGEST = _tagged(
    b"python==3.11.*\0jax==0.10.2\0jaxlib==0.10.2\0numpy==2.4.6\0scipy==1.17.1\0optax==0.2.8\0chex==0.1.92\0equinox==0.13.8\0einops==0.8.2\0foundax==0.2.0\0pyyaml==6.0.3\0linux-x86_64-cpu"
)
INPUT_INTERFACE_DIGEST = _tagged(
    b"u0[case,point]:physical-float;nu[case]:physical-float;t[case,time]:physical-float;y[case,time,point]:physical-float;x[point]:physical-float;unit-system=carbon_burgers_native_v1;periodic-uniform-endpoint-excluded"
)
OUTPUT_INTERFACE_DIGEST = _tagged(
    b"prediction[case,time,point]:physical-float32;unit-system=carbon_burgers_native_v1;requested-time-order;target-free-inference"
)
DEPENDENCY_SPECS = (
    ("jax", "0.10.2", _tagged(b"pypi:jax==0.10.2")),
    ("jaxlib", "0.10.2", _tagged(b"pypi:jaxlib==0.10.2")),
    ("numpy", "2.4.6", _tagged(b"pypi:numpy==2.4.6")),
    ("scipy", "1.17.1", _tagged(b"pypi:scipy==1.17.1")),
    ("optax", "0.2.8", _tagged(b"pypi:optax==0.2.8")),
    ("chex", "0.1.92", _tagged(b"pypi:chex==0.1.92")),
    ("equinox", "0.13.8", _tagged(b"pypi:equinox==0.13.8")),
    ("einops", "0.8.2", _tagged(b"pypi:einops==0.8.2")),
    ("foundax", "0.2.0", _tagged(b"pypi:foundax==0.2.0")),
    ("pyyaml", "6.0.3", _tagged(b"pypi:pyyaml==6.0.3")),
)

_BACKBONES = {
    "fno": ("carbon_jax_fno1d", "fno1d"),
    "deeponet": ("carbon_jax_deeponet1d", "deeponet1d"),
    "transolver": ("carbon_jax_transolver1d", "physics_attention1d"),
    "haar_operator": ("carbon_jax_haar_operator1d", "haar_operator1d"),
    "gno": ("carbon_jax_gno1d", "gno1d"),
    "gino": ("carbon_jax_gino1d", "gino1d"),
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
    "velocity_scale": 1.0,
    "nu_scale": 0.05,
    "physical_unit_system": "carbon_burgers_native_v1",
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
    # The public name for the lab's graph_radius: "graph" is reserved by
    # B-02B's guard against participant composition graphs, and this field is
    # a neighbourhood radius, not a graph a miner composes.
    ("carbon_jax_lab_model", "neighborhood_radius"): ("model", "graph_radius"),
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
    implementation = backbone.implementation_pin
    foundax = implementation.implementation_id == FOUNDAX_IMPLEMENTATION_ID
    if foundax:
        expected = ("foundax_fno1d", "foundax_fno1d")
        if backbone.selector_token != "fno":
            raise ReconstructionFailure("reconstruction.backbone.unsupported")
    else:
        expected = _BACKBONES.get(backbone.selector_token)
    if expected is None or backbone.backbone_id != expected[0]:
        raise ReconstructionFailure("reconstruction.backbone.unsupported")
    expected_source = FOUNDAX_WHEEL_DIGEST if foundax else UPSTREAM_WHEEL_DIGEST
    expected_implementation_id = (
        FOUNDAX_IMPLEMENTATION_ID if foundax else IMPLEMENTATION_ID
    )
    expected_implementation_version = (
        FOUNDAX_IMPLEMENTATION_VERSION if foundax else IMPLEMENTATION_VERSION
    )
    expected_backbone_version = "0.2.0" if foundax else "1.0"
    if backbone.backbone_version != expected_backbone_version:
        raise ReconstructionFailure("reconstruction.backbone.unsupported")
    if backbone.content_digest != expected_source:
        raise ReconstructionFailure("reconstruction.backbone.digest_mismatch")
    if (
        implementation.implementation_id != expected_implementation_id
        or implementation.implementation_version != expected_implementation_version
        or implementation.content_digest != expected_source
    ):
        raise ReconstructionFailure("reconstruction.implementation.pin_mismatch")
    environment = backbone.environment_pin
    accelerator = None
    if environment.environment_id != ENVIRONMENT_ID:
        from carbon.reconstruction.accelerators import resolve_profile

        try:
            accelerator = resolve_profile(environment.environment_id)
        except ValueError:
            raise ReconstructionFailure(
                "reconstruction.environment.pin_mismatch"
            ) from None
    expected_environment_id = (
        ENVIRONMENT_ID if accelerator is None else accelerator.profile_id
    )
    expected_environment_version = ENVIRONMENT_VERSION if accelerator is None else "1.0"
    expected_environment_digest = (
        ENVIRONMENT_DIGEST if accelerator is None else accelerator.digest
    )
    if (
        environment.environment_id != expected_environment_id
        or environment.environment_version != expected_environment_version
        or environment.content_digest != expected_environment_digest
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
    expected_dependencies = DEPENDENCY_SPECS
    if accelerator is not None:
        from carbon.reconstruction.accelerators import accelerator_dependency_specs

        expected_dependencies += accelerator_dependency_specs(accelerator)
    if frozenset(observed_dependencies) != frozenset(expected_dependencies):
        raise ReconstructionFailure("reconstruction.dependency.pin_mismatch")
    if plan.resolved_components:
        raise ReconstructionFailure("reconstruction.component.unsupported")

    model = dict(_MODEL_DEFAULTS)
    model["kind"] = expected[1]
    if foundax:
        model = {
            "kind": "foundax_fno1d",
            "width": model["width"],
            "depth": model["depth"],
            "n_modes": model["n_modes"],
            "linear_conv": False,
            "dropout_rate": 0.0,
        }
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

    try:
        scaling = BurgersPhysicalScaling(
            task["domain_length"],
            task["time_scale"],
            task["velocity_scale"],
            task["physical_unit_system"],
        )
        scaling.assert_representable("float32")
    except (TypeError, ValueError):
        raise ReconstructionFailure("reconstruction.profile.scaling_invalid") from None

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
        "schema": "carbon.c02.plan-mapping.v2",
        "backbone_surface_id": backbone.surface_id,
        "backbone_selector": backbone.selector_token,
        "implementation_profile": (
            "foundax_fno_v1" if foundax else "carbon_jax_lab_v1"
        ),
        "fixed_values": {
            "model": _MODEL_DEFAULTS,
            "task": _TASK_DEFAULTS,
            "train": _TRAIN_DEFAULTS,
        },
        "mapped_surfaces": mapped,
        "seed_policy": "runtime DerivedSeed bytes; excluded from plan/profile identity",
        "physical_scaling": scaling.to_dict(),
        "physical_scaling_digest": scaling.digest,
        "normalization_policy": "TRAIN RMS is numerical loss scaling and is not physical U",
        "upstream_revision": FOUNDAX_REVISION if foundax else None,
        "upstream_license": "EPL-2.0" if foundax else "supplied notices",
    }
    if accelerator is not None:
        receipt["schema"] = "carbon.c02.plan-mapping.v3"
        receipt["execution_profile"] = accelerator.document()
        receipt["execution_profile_digest"] = accelerator.digest
    body = {
        "schema": (
            "carbon.c02.development-profile.v3"
            if accelerator is None
            else "carbon.c02.development-profile.v4"
        ),
        "plan_digest": plan_digest,
        "backbone_kind": expected[1],
        "model": model,
        "task": task,
        "train": train,
        "source_digest": FOUNDAX_WHEEL_DIGEST if foundax else _vendored_source_digest(),
        "environment_digest": expected_environment_digest,
        "input_interface_digest": INPUT_INTERFACE_DIGEST,
        "output_interface_digest": OUTPUT_INTERFACE_DIGEST,
        "physical_scaling": scaling.to_dict(),
        "physical_scaling_digest": scaling.digest,
        "mapping": receipt,
    }
    profile_digest = _tagged(_canonical(body).encode("utf-8"))
    return ReconstructionProfile(
        profile_id=(
            accelerator.profile_id
            if accelerator is not None
            else (
                "carbon_c02_foundax_fno_development"
                if foundax
                else "carbon_c02_jax_development"
            )
        ),
        profile_version="3.0" if accelerator is None else "4.0",
        profile_digest=profile_digest,
        plan_digest=plan_digest,
        backbone_kind=expected[1],
        model_config_json=_canonical(model),
        task_config_json=_canonical(task),
        train_config_json=_canonical(train),
        source_digest=body["source_digest"],
        environment_digest=expected_environment_digest,
        input_interface_digest=INPUT_INTERFACE_DIGEST,
        output_interface_digest=OUTPUT_INTERFACE_DIGEST,
        physical_scaling_digest=scaling.digest,
        physical_scaling_json=_canonical(scaling.to_dict()),
        mapping_receipt_json=_canonical(receipt),
    )


__all__ = [
    "DEPENDENCY_SPECS",
    "ENVIRONMENT_DIGEST",
    "ENVIRONMENT_ID",
    "ENVIRONMENT_VERSION",
    "FOUNDAX_IMPLEMENTATION_ID",
    "FOUNDAX_IMPLEMENTATION_VERSION",
    "FOUNDAX_LICENSE_DIGEST",
    "FOUNDAX_REVISION",
    "FOUNDAX_WHEEL_DIGEST",
    "IMPLEMENTATION_ID",
    "IMPLEMENTATION_VERSION",
    "INPUT_INTERFACE_DIGEST",
    "OUTPUT_INTERFACE_DIGEST",
    "UPSTREAM_WHEEL_DIGEST",
    "compile_development_profile",
]
