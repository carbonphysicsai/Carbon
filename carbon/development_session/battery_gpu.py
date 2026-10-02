# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Battery practice on the miner's own GPU (C-MLP-03 slice 3).

The same practice as the CPU carrier, on a GPU: the same compiled recipe, the
same staged battery files, the same public TRAIN v1 and PRACTICE inputs, scored
on the host by the same exam gates. Only where the worker runs differs. It runs
in the pinned GPU worker image (`scripts/dev/accelerator_worker_image.sh`), with
`JAX_PLATFORMS=cuda` and the device named by the host's installed device record
(`carbon.reconstruction.host_inventory`), on the miner lane.

**GPU practice is for speed only.** Nothing here is evidence the validator
reads: the validator rebuilds every submitted recipe on its own pinned backend
and resources. The scope says so in its own fields (`purpose`, `score`,
`official_eligible`), and the feedback records which backend ran and what the
worker observed, so a GPU result is never mistaken for a CPU one.

Burgers' GPU scope (`development_session.gpu_research`) binds Burgers' recipe
catalogue and public TRAIN cases; this is battery's own, under its own schema.
"""

from __future__ import annotations

from dataclasses import asdict

from carbon.battery.practice import PROGRAM
from carbon.development_session.profile import canonical, digest

SCOPE_SCHEMA = "carbon.battery.gpu-practice.scope.v1"
#: The operator-installed record naming the GPU worker image; the runner
#: installs it from the miner's profile (`gpu_image`).
GPU_IMAGE_RECORD = "gpu-worker-image.json"
#: The backends the GPU worker rebuilds. It carries JAX with the CUDA plugin
#: and no PyTorch, so a PyTorch recipe practises on the CPU PyTorch worker.
BACKENDS = ("jax",)
JAX_PLATFORMS = "cuda"
SPEED_ONLY = (
    "GPU practice is for speed only. The validator rebuilds your recipe on its "
    "own pinned backend and resources; nothing measured here is scored."
)

#: The practice program with one addition: the worker records what JAX
#: actually ran on, so the feedback states the backend observed, not assumed.
#: The CPU program is unchanged, so no existing practice identity moves.
GPU_PROGRAM = PROGRAM + r"""
import os

import jax

(out / "runtime.json").write_text(
    json.dumps(
        {
            "jax_platforms": os.environ.get("JAX_PLATFORMS"),
            "default_backend": jax.default_backend(),
            "devices": sorted({d.device_kind for d in jax.devices()}),
            "device_count": jax.device_count(),
        },
        sort_keys=True,
    )
)
"""


def is_gpu_image(image):
    """Whether `image` is the pinned GPU worker (its lock is the GPU profile's)."""
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return (
        type(image) is WorkerImageIdentity
        and image.lock_digest == GPU_PROFILE.environment_lock_digest
    )


def gpu_scope(image):
    """The battery GPU practice scope for the pinned GPU worker `image`."""
    from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    if not is_gpu_image(image):
        raise ValueError("exact pinned GPU worker image required")
    return {
        "schema": SCOPE_SCHEMA,
        "challenge": BATTERY_CHALLENGE,
        "profile_digest": GPU_PROFILE.digest,
        "image": image.image_id,
        "image_manifest_digest": digest(canonical(asdict(image))),
        "program": digest(GPU_PROGRAM.encode()),
        "role": AcceleratorRole.MINER_RESEARCH.value,
        "backends": list(BACKENDS),
        "jax_platforms": JAX_PLATFORMS,
        "purpose": "speed_only",
        "score": None,
        "official_eligible": False,
    }


def declared_scope(runtime):
    """The battery GPU scope a runtime declares, checked for shape only.

    The binding check is `registered_gpu_image`, which recomputes the scope
    from the installed image record.
    """
    scopes = runtime.get("gpu_research")
    if (
        type(scopes) is not list
        or len(scopes) != 1
        or type(scopes[0]) is not dict
        or scopes[0].get("schema") != SCOPE_SCHEMA
        or scopes[0].get("purpose") != "speed_only"
        or scopes[0].get("official_eligible") is not False
        or scopes[0].get("score") is not None
    ):
        raise ValueError("exact battery GPU practice scope required")
    return [dict(scopes[0])]


def registered_gpu_image(root, declared):
    """The GPU worker image this campaign's runtime declares, verified.

    None when the runtime declares no GPU practice. Otherwise the installed
    record is read and the scope recomputed from it; a declared scope that
    differs from the installed image is refused.
    """
    if "gpu_research" not in declared:
        return None
    from carbon.development_session.research_campaign import private_file
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    declared_scope(declared)
    path = private_file(root / GPU_IMAGE_RECORD)
    if path.resolve() != path or path.stat().st_size > 65536:
        raise ValueError("fixed bounded GPU image record required")
    image = load_image_identity(path)
    if declared["gpu_research"] != [gpu_scope(image)]:
        raise ValueError("the installed GPU image differs from the declared scope")
    return image


def backend_record(device, observed):
    """What the feedback records about a GPU practice run."""
    from carbon.reconstruction.accelerators import GPU_PROFILE, miner_lane_assurance

    return {
        "kind": "ISOLATED_CARRIER_GPU",
        "carrier": "carbon.development_session.research_carrier",
        "profile": GPU_PROFILE.profile_id,
        "jax_platforms": JAX_PLATFORMS,
        "device_record_digest": device.digest,
        "device_kind": device.device_kind,
        "observed": observed,
        "assurance": miner_lane_assurance(),
        "purpose": "speed_only",
        "note": SPEED_ONLY,
    }


def rented_backend_record(rented, observed):
    """What the feedback records about a practice run on a rented GPU."""
    teardown = rented.get("teardown") or {}
    return {
        "kind": "RENTED_GPU",
        "runner": "carbon.compute.rented_runner",
        "provider": rented["provider"],
        "image_ref": rented["image_ref"],
        "gpu_type_id": rented["gpu_type_id"],
        "resource_id": rented.get("resource_id"),
        "rate_usd_per_hr": rented.get("rate_usd_per_hr"),
        "job_transport": rented.get("job_transport"),
        "teardown_verified": teardown.get("verified") is True,
        "provider_charge": teardown.get("charge"),
        "jax_platforms": JAX_PLATFORMS,
        "observed": observed,
        "purpose": "speed_only",
        "note": SPEED_ONLY,
    }


RENTED_SCHEMA = "carbon.battery.rented-gpu.v1"


def rented_scope(compute, image):
    """The battery rented-GPU scope: the miner's provider choice, bound to the
    campaign's pinned GPU worker (the image the pod pulls by digest)."""
    if not is_gpu_image(image):
        raise ValueError("exact pinned GPU worker image required")
    return {
        "schema": RENTED_SCHEMA,
        **compute.document(),
        "pinned_image": image.image_id,
        "purpose": "speed_only",
        "score": None,
        "official_eligible": False,
    }


def declared_rented(runtime):
    """The rented choice a runtime declares, checked for shape; None without one.

    A rented GPU runs the GPU practice program, so it needs the GPU practice
    scope beside it.
    """
    if "rented_gpu" not in runtime:
        return None
    declared_scope(runtime)
    scopes = runtime["rented_gpu"]
    if (
        type(scopes) is not list
        or len(scopes) != 1
        or type(scopes[0]) is not dict
        or scopes[0].get("schema") != RENTED_SCHEMA
        or scopes[0].get("purpose") != "speed_only"
        or scopes[0].get("official_eligible") is not False
        or scopes[0].get("score") is not None
        or scopes[0].get("pinned_image") != runtime["gpu_research"][0].get("image")
    ):
        raise ValueError("exact battery rented GPU scope required")
    return compute_from_scope(scopes[0])


def compute_from_scope(scope):
    from carbon.compute.rented_runner import RentedCompute

    return RentedCompute(
        provider=scope["provider"],
        image_ref=scope["image_ref"],
        gpu_type_id=scope["gpu_type_id"],
        max_rate_usd_per_hr=scope["max_rate_usd_per_hr"],
        storage_usd_per_gb_month=scope["storage_usd_per_gb_month"],
        cloud_type=scope["cloud_type"],
    )
