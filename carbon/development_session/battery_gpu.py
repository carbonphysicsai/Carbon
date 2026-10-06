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
from carbon.development_session.gpu_practice import SPEED_ONLY, is_gpu_image
from carbon.development_session.profile import canonical, digest

SCOPE_SCHEMA = "carbon.battery.gpu-practice.scope.v1"
#: The operator-installed record naming the GPU worker image; the runner
#: installs it from the miner's profile (`gpu_image`).
GPU_IMAGE_RECORD = "gpu-worker-image.json"
#: The backends the GPU worker rebuilds. It carries JAX with the CUDA plugin
#: and no PyTorch, so a PyTorch recipe practises on the CPU PyTorch worker.
BACKENDS = ("jax",)
JAX_PLATFORMS = "cuda"

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

#: KNN-STATE-GPU-01: the GPU program's versions. v1 is `GPU_PROGRAM`, byte for
#: byte as before: every non-KNN recipe (so every Level-0 pin), every Level-1
#: trial and the miner's GPU practice scope keep it. v2 is v1 plus the
#: versioned KNN state digest (`carbon.battery.knn_state`), staged as the
#: other battery modules are; Carbon's pods build a KNN recipe with it.
PROGRAM_V1 = "carbon.battery.gpu-practice.program.v1"
PROGRAM_V2 = "carbon.battery.gpu-practice.program.v2-knn-state"
KNN_STATE_STAGED = {"battery-knn-state.py": "knn_state.py"}
_FIT = 'stats = model.fit(train, structure, recipe["seed"])\n'
_KNN_STATE = r"""shutil.copyfile(work / "battery-knn-state.py", lab / "knn_state.py")
from carbon_battery_lab.knn_state import with_state  # noqa: E402

stats = with_state(model, stats)
"""
if GPU_PROGRAM.count(_FIT) != 1:
    raise RuntimeError("the practice program's fit line moved")
KNN_GPU_PROGRAM = GPU_PROGRAM.replace(_FIT, _FIT + _KNN_STATE)
#: Every GPU program version, by program digest, so a record pinned under
#: either version resolves to the exact program it names.
PROGRAMS = {
    digest(GPU_PROGRAM.encode()): (PROGRAM_V1, GPU_PROGRAM),
    digest(KNN_GPU_PROGRAM.encode()): (PROGRAM_V2, KNN_GPU_PROGRAM),
}


def pod_program(family):
    """(program, extra staged files) a Level-0 pod build runs for `family`:
    v2 and the staged `knn_state.py` for a KNN, v1 and nothing else otherwise."""
    if family != "knn":
        return GPU_PROGRAM, {}
    from pathlib import Path

    from carbon import battery

    here = Path(battery.__file__).parent
    return KNN_GPU_PROGRAM, {
        staged: (here / module).read_bytes()
        for staged, module in KNN_STATE_STAGED.items()
    }


def program_version(program_digest):
    """The GPU program version a record's `program` digest names; an unknown
    digest is refused, never read as another version."""
    if program_digest not in PROGRAMS:
        raise ValueError("unknown battery GPU program")
    return PROGRAMS[program_digest][0]


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


def remote_worker(image):
    """Battery's worker on the miner's own remote setup: the pinned GPU
    worker, with the JAX platform its GPU practice program runs on
    (OWNER-MINER-COMPUTE-LINK-ONLY-01). The route itself is the Challenge-
    neutral `carbon.compute.remote_route`."""
    from carbon.compute.remote_runner import RemoteWorker

    if not is_gpu_image(image):
        raise ValueError("exact pinned GPU worker image required")
    return RemoteWorker(image=image, environment=(("JAX_PLATFORMS", JAX_PLATFORMS),))


def remote_backend_record(remote, observed):
    """What the feedback records about a practice run on the miner's own
    remote setup (OWNER-MINER-COMPUTE-LINK-ONLY-01): the one remote record
    (transport, how the worker was verified, job transport, cleanup), what
    JAX observed, and that it is speed only."""
    return {
        "kind": "REMOTE_GPU",
        "runner": "carbon.compute.remote_runner",
        "transport": remote.get("transport"),
        "image_verified_by": remote.get("image_verified_by"),
        "job_transport": remote.get("job_transport"),
        "cleanup": remote.get("cleanup"),
        "jax_platforms": JAX_PLATFORMS,
        "observed": observed,
        "purpose": "speed_only",
        "note": SPEED_ONLY,
    }
