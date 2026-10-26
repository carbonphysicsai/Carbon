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


def rebind(runtime, campaign):
    """`runtime` with its catalog GPU practice scopes (and their remote scopes)
    bound to `campaign`'s Challenge (GPU for every Challenge, owner
    2026-10-22). Every catalog Challenge's scope is the same document but for
    the Challenge it names, so one GPU setup serves them all: a launch binds
    the profile's scopes to the Challenge it launches, and the campaign
    freezes, checks and runs exactly that. A runtime without catalog GPU
    scopes is returned as it is (CPU, or a Challenge's own GPU scope); a
    Challenge that does not share the catalog GPU path is refused."""
    scopes = runtime.get(RUNTIME_KEY) if type(runtime) is dict else None
    if not scopes or type(scopes) is not list or type(scopes[0]) is not dict:
        return runtime
    if scopes[0].get("schema") != SCOPE_SCHEMA:
        return runtime
    if getattr(campaign, "declared_gpu", None) is not declared_scope:
        raise ValueError("this Challenge does not share the catalog GPU practice")
    challenge_id = campaign.key.challenge_id
    bound = {
        **runtime,
        RUNTIME_KEY: [{**scope, "challenge": challenge_id} for scope in scopes],
    }
    if type(runtime.get(REMOTE_KEY)) is list:
        bound[REMOTE_KEY] = [
            {**scope, "challenge": challenge_id} if type(scope) is dict else scope
            for scope in runtime[REMOTE_KEY]
        ]
    return bound


def offers_catalog_gpu(campaign) -> bool:
    """Whether `campaign` practises on GPU through the shared catalog path."""
    return getattr(campaign, "declared_gpu", None) is declared_scope


#: The campaign-root record of each declared GPU worker, in scope order: the
#: first as every profile wrote it, the second for the other backend's
#: worker (Validator ruling: one GPU worker per installed backend).
GPU_IMAGE_RECORDS = ("gpu-worker-image.json", "extra-gpu-worker-image.json")


def declared_scope(runtime):
    """The GPU scopes a runtime declares, one per GPU worker (one or two, of
    distinct backends), checked for shape only; the binding check is
    `registered_gpu_image`, which recomputes them."""
    scopes = runtime.get(RUNTIME_KEY)
    if (
        type(scopes) is not list
        or not 1 <= len(scopes) <= len(GPU_IMAGE_RECORDS)
        or any(
            type(scope) is not dict
            or scope.get("schema") != SCOPE_SCHEMA
            or scope.get("purpose") != "speed_only"
            or scope.get("official_eligible") is not False
            or scope.get("score") is not None
            for scope in scopes
        )
        or len({scope.get("backend") for scope in scopes}) != len(scopes)
    ):
        raise ValueError("exact catalog GPU practice scope required")
    return [dict(scope) for scope in scopes]


def registered_gpu_image(root, declared, challenge_id):
    """The GPU worker(s) the campaign's runtime declares, each verified
    against its record installed in the campaign root (`GPU_IMAGE_RECORDS`):
    one image as before, or a tuple of one per backend; None without GPU
    practice."""
    if RUNTIME_KEY not in declared:
        return None
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    from .research_campaign import private_file

    scopes = declared_scope(declared)
    images = []
    for name in GPU_IMAGE_RECORDS[: len(scopes)]:
        path = private_file(root / name)
        if path.resolve() != path or path.stat().st_size > 65536:
            raise ValueError("fixed bounded GPU image record required")
        images.append(load_image_identity(path))
    if declared[RUNTIME_KEY] != [gpu_scope(challenge_id, image) for image in images]:
        raise ValueError("the installed GPU image differs from the declared scope")
    return images[0] if len(images) == 1 else tuple(images)


def with_gpu(runtime, declared, challenge_id, gpu_image):
    """`runtime` plus the GPU scope when `declared` asks for GPU practice,
    and the remote scope beside it when `declared` asks for remote practice
    (recomposed against this host's GPU worker, over the declared
    transport)."""
    if RUNTIME_KEY not in declared:
        if REMOTE_KEY in declared:
            raise ValueError("remote GPU practice needs the GPU practice scope")
        return runtime
    from .gpu_practice import gpu_images

    images = gpu_images(gpu_image)
    if not images:
        raise ValueError("a GPU practice runtime needs its installed GPU image")
    runtime = {
        **runtime,
        RUNTIME_KEY: [gpu_scope(challenge_id, image) for image in images],
    }
    if REMOTE_KEY in declared:
        from carbon.compute.remote_route import declared_remote, remote_scope
        from carbon.compute.remote_transport import SSH_DOCKER

        transport = declared_remote(declared)["transport"]
        if transport != SSH_DOCKER:
            # A bundle job lays its inputs out as the local carrier mounts
            # them, which only Carbon's hardened job container provides.
            raise ValueError("catalog practice on a remote GPU runs over ssh-docker")
        # Every backend the host registers, on the miner's remote setup too.
        runtime[REMOTE_KEY] = [
            remote_scope(challenge_id, image, transport) for image in images
        ]
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
        # M1 E2E R9-3: a GPU host that ran the CPU build says so in words,
        # where the result is read, not only as a code.
        record["fallback"] = (
            "Ran on CPU: "
            + FALLBACK_WORDS.get(gpu_note, "the GPU build did not run")
            + ". The score is the CPU build's."
        )
    return record


#: Why a GPU host ran the CPU build (`gpu_practice.device_build`'s notes).
FALLBACK_WORDS = {
    "catalog_gpu_build_missing": "this catalog entry has no GPU build yet",
    "catalog_gpu_build_not_offered": "the entry's GPU build has no GPU receipt yet",
    "gpu_overlay_not_installed": "the entry's GPU build is not installed here",
    "gpu_build_failed": "the entry's GPU build failed",
    "graph_gpu_worker_missing": (
        "your graph practises on the JAX GPU worker and only the PyTorch one is "
        "installed here; install the JAX GPU worker, then practise again"
    ),
    "gpu_uv_image_missing": (
        "the pinned uv image GPU builds prepare with is not on this machine; "
        "run: docker pull "
        "ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945"
        " (the installer pulls it with --gpu), then practise again"
    ),
    "gpu_driver_too_old": (
        "your GPU machine's NVIDIA driver is older than this GPU worker's CUDA "
        "runtime; update the driver (nvidia-smi shows the newest CUDA it "
        "runs), then check Compute again"
    ),
}


def campaign_remote(key, runtime, machine, gpu_image):
    """The practice runner on the miner's own remote GPU for a catalog
    campaign's run, built by its Challenge's campaign (`remote_runner`) from
    the profile's `remote_machine` when the runtime declares remote
    practice; None otherwise. Every catalog campaign's own run path builds
    it, as battery's does (M1 E2E S4: without it a catalog campaign's GPU
    work - the overlay preparation included - ran on the controller, which
    has no GPU)."""
    from carbon.compute.remote_route import RUNTIME_KEY as REMOTE

    if REMOTE not in runtime:
        return None
    from carbon.challenge_registry.campaigns import campaign_for

    campaign = campaign_for({"id": key.challenge_id, "version": key.version})
    return campaign.remote_runner(runtime, machine, gpu_image)


class RemotePractice:
    """A catalog practice's runner with the miner's own remote GPU: a run on
    the remote worker's image (the GPU parent) goes to the remote setup, and
    every other run (the CPU parent's, the source-free inference) to the
    controller's own carrier, unchanged. Names no Challenge."""

    def __init__(self, remote, local=None):
        from carbon.compute.remote_runner import RemoteRunner

        # One remote runner per GPU worker the host registers (one per
        # backend); a run goes to the one whose image it names.
        runners = tuple(remote) if type(remote) in (tuple, list) else (remote,)
        if not runners or any(type(r) is not RemoteRunner for r in runners):
            raise ValueError("the remote practice runner is the remote route's")
        if len({r.image_id for r in runners}) != len(runners):
            raise ValueError("one remote runner per GPU worker")
        self.runners, self.local = runners, local
        self.remote = runners[0]

    @property
    def image_id(self):
        return self.remote.image_id

    def __call__(self, ledger, **kwargs):
        named = getattr(kwargs.get("image"), "image_id", None)
        for runner in self.runners:
            if named == runner.image_id:
                return runner(ledger, **kwargs)
        if self.local is not None:
            return self.local(ledger, **kwargs)
        from .research_carrier import _run

        return _run(ledger, **kwargs)
