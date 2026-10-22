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

Stage S4 runs the same practice on the miner's own remote GPU
(`carbon.compute.remote_route`, OWNER-MINER-COMPUTE-LINK-ONLY-01): a runtime
that also declares `remote_gpu` sends the GPU phases (the overlay
preparation and the overlay build) to one hardened job container on the
miner's machine over their own SSH (`ssh-docker`), with the same public
practice inputs; the CPU phases stay on the controller.
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
    """`runtime` plus the GPU scope when `declared` asks for GPU practice,
    and the remote scope beside it when `declared` asks for remote practice
    (recomposed against this host's GPU worker, over the declared
    transport)."""
    if RUNTIME_KEY not in declared:
        if REMOTE_KEY in declared:
            raise ValueError("remote GPU practice needs the GPU practice scope")
        return runtime
    if gpu_image is None:
        raise ValueError("a GPU practice runtime needs its installed GPU image")
    runtime = {**runtime, RUNTIME_KEY: [gpu_scope(challenge_id, gpu_image)]}
    if REMOTE_KEY in declared:
        from carbon.compute.remote_route import declared_remote, remote_scope
        from carbon.compute.remote_transport import SSH_DOCKER

        transport = declared_remote(declared)["transport"]
        if transport != SSH_DOCKER:
            # A bundle job lays its inputs out as the local carrier mounts
            # them, which only Carbon's hardened job container provides.
            raise ValueError("catalog practice on a remote GPU runs over ssh-docker")
        runtime[REMOTE_KEY] = [remote_scope(challenge_id, gpu_image, transport)]
    return runtime


#: The runtime key a remote GPU practice campaign declares
#: (`carbon.compute.remote_route.RUNTIME_KEY`).
REMOTE_KEY = "remote_gpu"


def remote_worker(image):
    """Every catalog Challenge's worker on the miner's own remote setup: the
    pinned GPU worker, with the device environment its GPU build gets from
    the local carrier (`accelerators.worker_environment`) less what names
    the controller's own device. The same for every Challenge."""
    from carbon.compute.remote_runner import RemoteWorker
    from carbon.reconstruction.accelerators import GPU_DETERMINISM_ENVIRONMENT

    from .gpu_practice import gpu_runtime

    if gpu_runtime(image) is None:
        raise ValueError("exact pinned GPU worker image required")
    return RemoteWorker(
        image=image,
        environment=(
            ("JAX_PLATFORMS", "cuda"),
            ("XLA_PYTHON_CLIENT_PREALLOCATE", "false"),
            *sorted(GPU_DETERMINISM_ENVIRONMENT.items()),
        ),
    )


def backend_record(accelerator, parent, gpu_note, runner):
    """What a catalog practice's feedback records about where it ran, the
    same for every Challenge: this machine's CPU or GPU, or the miner's own
    remote GPU (with its transport), a GPU run labelled as such (Validator
    condition 4). Never a score input."""
    remote = accelerator is not None and type(runner) is RemotePractice
    record = {
        "kind": (
            "REMOTE_GPU"
            if remote
            else "C03_DOCKER_GPU" if accelerator is not None else "C03_DOCKER"
        ),
        "parent": getattr(parent, "image_id", None),
    }
    if remote:
        record["transport"] = runner.remote.transport.name
    if accelerator is not None:
        record["label"] = LABEL
    if gpu_note:
        record["gpu_note"] = gpu_note
    return record


class RemotePractice:
    """A catalog practice's runner with the miner's own remote GPU: a run on
    the remote worker's image (the GPU parent) goes to the remote setup, and
    every other run (the CPU parent's, the source-free inference) to the
    controller's own carrier, unchanged. Names no Challenge."""

    def __init__(self, remote, local=None):
        from carbon.compute.remote_runner import RemoteRunner

        if type(remote) is not RemoteRunner:
            raise ValueError("the remote practice runner is the remote route's")
        self.remote, self.local = remote, local

    @property
    def image_id(self):
        return self.remote.image_id

    def __call__(self, ledger, **kwargs):
        if getattr(kwargs.get("image"), "image_id", None) == self.remote.image_id:
            return self.remote(ledger, **kwargs)
        if self.local is not None:
            return self.local(ledger, **kwargs)
        from .research_carrier import _run

        return _run(ledger, **kwargs)
