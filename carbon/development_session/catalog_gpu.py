"""Shared GPU practice path, stage S3: one GPU scope for every Challenge's
catalog campaign, declared, never coded per Challenge.

Design notes/LAUNCHPAD_GPU_PATH_DESIGN_20261022.md; Validator approval with
conditions, the parity condition replaced by the owner's same-GPU-class pair
receipt. A campaign whose runtime declares `gpu_research` practises its
catalog entries' GPU builds on the host's pinned GPU worker
(`gpu_practice.device_build`); everything else is unchanged:

- public practice material only (the same practice the CPU runs);
- speed only, with no score authority and never official
  (`score: None`, `official_eligible: False`), labelled
  "measured on GPU, not official";
- recipes stay device-free: the frozen catalog recipe names no runtime, and
  every receiver expands it as before.
"""

from __future__ import annotations

from dataclasses import asdict

SCOPE_SCHEMA = "carbon.catalog.gpu-practice-scope.v1"
RUNTIME_KEY = "gpu_research"
LABEL = "measured on GPU, not official"
#: Said wherever a GPU practice result is shown (owner, 2026-10-22).
DIFFER = "CPU and GPU results can differ."


def gpu_scope(challenge_id, image):
    """The GPU practice scope of `challenge_id`'s catalog campaign on the
    pinned GPU worker `image`: the same document shape for every Challenge."""
    from carbon.reconstruction.accelerators import AcceleratorRole

    from .gpu_practice import gpu_image_backend, gpu_runtime
    from .profile import canonical, digest

    runtime = gpu_runtime(image)
    if type(challenge_id) is not str or runtime is None:
        raise ValueError("exact pinned GPU worker image required")
    return {
        "schema": SCOPE_SCHEMA,
        "challenge": challenge_id,
        "image": image.image_id,
        "image_manifest_digest": digest(canonical(asdict(image))),
        "backend": gpu_image_backend(image),
        "bundle_runtime": runtime,
        "role": AcceleratorRole.MINER_RESEARCH.value,
        "purpose": "speed_only",
        "label": LABEL,
        "score": None,
        "official_eligible": False,
    }


def declared_scope(runtime):
    """The GPU scope a runtime declares, checked for shape only; the binding
    check is `registered_gpu_image`, which recomputes it."""
    scopes = runtime.get(RUNTIME_KEY)
    if (
        type(scopes) is not list
        or len(scopes) != 1
        or type(scopes[0]) is not dict
        or scopes[0].get("schema") != SCOPE_SCHEMA
        or scopes[0].get("purpose") != "speed_only"
        or scopes[0].get("official_eligible") is not False
        or scopes[0].get("score") is not None
    ):
        raise ValueError("exact catalog GPU practice scope required")
    return [dict(scopes[0])]


def registered_gpu_image(root, declared, challenge_id):
    """The GPU worker the campaign's runtime declares, verified against the
    record installed in the campaign root; None without GPU practice."""
    if RUNTIME_KEY not in declared:
        return None
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    from .gpu_research import GPU_IMAGE_RECORD
    from .research_campaign import private_file

    declared_scope(declared)
    path = private_file(root / GPU_IMAGE_RECORD)
    if path.resolve() != path or path.stat().st_size > 65536:
        raise ValueError("fixed bounded GPU image record required")
    image = load_image_identity(path)
    if declared[RUNTIME_KEY] != [gpu_scope(challenge_id, image)]:
        raise ValueError("the installed GPU image differs from the declared scope")
    return image


def with_gpu(runtime, declared, challenge_id, gpu_image):
    """`runtime` plus the GPU scope when `declared` asks for GPU practice."""
    if RUNTIME_KEY not in declared:
        return runtime
    if gpu_image is None:
        raise ValueError("a GPU practice runtime needs its installed GPU image")
    return {**runtime, RUNTIME_KEY: [gpu_scope(challenge_id, gpu_image)]}
