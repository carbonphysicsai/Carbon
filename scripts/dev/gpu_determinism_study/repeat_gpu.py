"""Run the real Carbon reconstruction on the GPU, N times, in one container.

Repeats live inside a single device session rather than one admission each,
because the question is whether the numerics reproduce - not whether the
orchestration does, which is covered elsewhere. Admission is still the real one:
the miner-lane check runs, and a mismatched plan or profile is refused here
exactly as it would be through the controller.
"""

import hashlib
import json
import os
import traceback
from pathlib import Path

materials = Path(os.environ["D3_MATERIALS"])
runs = int(os.environ.get("D3_RUNS", "3"))
label = os.environ.get("D3_LABEL", "unlabelled")
out = Path(os.environ["D3_RESULTS"])
# Where reconstruction writes its artifacts. `/work` is the tmpfs the container
# path mounts, and it is a default rather than a constant because on a pod there
# is no daemon to mount it: the filesystem is the image's, and only /tmp is
# writable by the nonroot user. Hardcoding it made every in-pod reconstruction
# fail at `mkdir` before any numerics ran - a difference between the two paths
# that the study would have discovered on rented hardware.
artifacts = Path(os.environ.get("D3_ARTIFACTS", "/work"))

# ptxas writes intermediates under TMPDIR; the worker's scratch is a fresh
# tmpfs, so the directory has to exist before the first compilation.
#
# TMPDIR is required and created; the others are best-effort. Under `docker run`
# both are tmpfs mounts this process owns, and in a pod neither exists and the
# filesystem is read-only to the nonroot user the image runs as - so creating
# them unconditionally turned a convenience into a crash in the one environment
# the study actually runs in.
_tmpdir = os.environ.get("TMPDIR") or "/tmp/carbon-study/tmp"
os.makedirs(_tmpdir, exist_ok=True)
os.environ["TMPDIR"] = _tmpdir
for _scratch in ("/scratch/tmp", "/work/tmp"):
    try:
        os.makedirs(_scratch, exist_ok=True)
    except OSError:
        # Absent and unwritable is the normal case on a pod, and TMPDIR above is
        # what ptxas actually uses.
        pass

import jax

from carbon.construction import (
    ResolvedConstructionPlanRef,
    decode_resolved_construction_plan,
)
from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.numerics_environment import numerics_environment
from carbon.reconstruction.service import reconstruct
from carbon.reconstruction.worker.model import (
    MINER_HOST_AUTHORITY,
    DevelopmentWorkerProfile,
)
from carbon.registry import ChallengeKey
from carbon.seeding import DerivedSeed

spec = json.loads((materials / "materials.json").read_text())
ref = spec["plan_ref"]
plan = decode_resolved_construction_plan(
    (materials / "plan.bin").read_bytes(),
    expected_ref=ResolvedConstructionPlanRef(
        ChallengeKey(ref["challenge_id"], ref["challenge_version"]),
        ref["schema_version"],
        ref["canonicalization_profile"],
        ref["digest"],
    ),
)
archive = PublicTrainingArchive.from_file(
    materials / "train.npz", provenance="d3_gpu_determinism"
)
seed = DerivedSeed((materials / "randomness.bin").read_bytes())
execution = ExecutionAttemptRef(SubmissionId(spec["submission_id"]), 1)

device_uuid = os.environ["D3_DEVICE_UUID"]
worker_profile = DevelopmentWorkerProfile(
    "sha256:" + "2" * 64,
    "sha256:" + "3" * 64,
    "carbon.c03.cuda.development.v1",
    "1.0",
    GPU_PROFILE.profile_id,
    "sha256:" + "4" * 64,
    "MINER_RESEARCH",
    MINER_HOST_AUTHORITY,
    None,
    device_uuid,
)

record = {
    "label": label,
    "backend": jax.default_backend(),
    "devices": [str(d) for d in jax.devices()],
    "numerics": numerics_environment(),
    # The NVML identity of the device, driver build included, as `run_on_pod.sh`
    # read it. `compare_units.py` refuses a record without it. Absent when run
    # some other way, which is recorded as absent rather than filled in.
    "device_identity": (
        json.loads(os.environ["D3_DEVICE_IDENTITY"])
        if os.environ.get("D3_DEVICE_IDENTITY")
        else None
    ),
    "runs": [],
}

# Verify this is the declared execution environment, rather than assuming it.
#
# Under `docker run` the image was named by digest in the command, so the daemon
# enforced it. On a pod the image is whatever was selected at provisioning, and a
# tag instead of a digest, or a mis-selected template, resolves to something else
# silently - the same failure shape as an unpinned run: correct in every respect,
# numbers from a different CUDA or jaxlib stack, divergence blamed on the device.
#
# **This is strictly weaker than comparing the image digest, and deliberately so.**
# A container cannot read its own image digest: labels and digests are registry
# and daemon metadata, not filesystem. So this checks the *properties the digest
# was pinning* - interpreter, jax and jaxlib versions, CUDA major - against what
# the profile declares. It catches the realistic failure. It does not establish
# byte identity with the published image and must never be recorded as if it had.
#
# It runs on both conditions, not only the pinned one: an unpinned contrast run
# on the wrong image would make the contrast meaningless.
if os.environ.get("STUDY_REQUIRE_IMAGE") == "1":
    import platform

    from carbon.reconstruction.environment_guard import (
        DECLARED_PROPERTIES,
        environment_check_record,
        environment_problems,
        nothing_was_verified,
    )

    declared = GPU_PROFILE.document()
    numerics = record["numerics"]
    found = {
        "python": platform.python_version(),
        "jax": getattr(jax, "__version__", None),
    }
    try:
        import jaxlib

        found["jaxlib"] = getattr(jaxlib, "__version__", None)
    except Exception:  # noqa: BLE001
        found["jaxlib"] = None
    assert set(found) == set(DECLARED_PROPERTIES)

    mismatched, unverifiable, verified = environment_problems(
        declared=declared, found=found, cuda_version=numerics.get("cuda_version")
    )
    record["environment_check"] = environment_check_record(verified, unverifiable)
    # A guard that checked nothing is not a guard that passed. On a rented pod
    # the image is the least certain thing in the run, so this refuses rather
    # than recording an inert check and proceeding.
    if nothing_was_verified(verified, unverifiable):
        mismatched = [
            "UNVERIFIED_ENVIRONMENT: no declared property could be compared - "
            + "; ".join(unverifiable)
        ]
    if mismatched:
        print("RECORD_BEGIN")
        print(
            json.dumps(
                {
                    "label": label,
                    "status": "REFUSED_WRONG_ENVIRONMENT",
                    "checked": record["environment_check"]["note"],
                    "problems": mismatched,
                    "numerics": numerics,
                },
                indent=1,
                sort_keys=True,
            )
        )
        print("RECORD_END")
        raise SystemExit(
            "refusing to run: this is not the declared execution environment. "
            + "; ".join(mismatched)
        )

# Verify the pinned configuration took effect, rather than assuming it did.
#
# Under `docker run` the flags arrived as `-e` arguments the daemon applied, so
# a missing one showed up as a failed container. On a pod there is no daemon and
# no container to fail: whoever starts the process exports the variables, and if
# they are absent the run proceeds perfectly happily - unpinned, and looking
# pinned in every respect except the numbers.
#
# That is the failure this guards. An unpinned run recorded as pinned would put
# process-level divergence into a cross-device comparison and invite attributing
# it to the device. So the record is read back and checked against what the
# validator determinism policy requires, and a mismatch stops the run before any
# reconstruction rather than being discovered in the digests afterwards.
if os.environ.get("STUDY_REQUIRE_PINNED") == "1":
    numerics = record["numerics"]
    flags = numerics.get("xla_flags") or ""
    missing = [
        flag
        for flag in (
            "--xla_gpu_deterministic_ops=true",
            "--xla_gpu_exclude_nondeterministic_ops=true",
            "--xla_gpu_autotune_level=0",
        )
        if flag not in flags
    ]
    problems = [f"XLA flag not in effect: {flag}" for flag in missing]
    if numerics.get("nvidia_tf32_override") != "0":
        problems.append(
            f"NVIDIA_TF32_OVERRIDE is {numerics.get('nvidia_tf32_override')!r}, not '0'"
        )
    if numerics.get("cublas_workspace_config") != ":4096:8":
        problems.append(
            "CUBLAS_WORKSPACE_CONFIG is "
            f"{numerics.get('cublas_workspace_config')!r}, not ':4096:8'"
        )
    if record["backend"] != "gpu":
        problems.append(f"backend is {record['backend']!r}, not 'gpu'")
    if problems:
        print("RECORD_BEGIN")
        print(
            json.dumps(
                {
                    "label": label,
                    "status": "REFUSED_UNPINNED",
                    "problems": problems,
                    "numerics": numerics,
                },
                indent=1,
                sort_keys=True,
            )
        )
        print("RECORD_END")
        raise SystemExit(
            "refusing to run: the pinned determinism configuration is not in "
            "effect. " + "; ".join(problems)
        )

for index in range(runs):
    target = artifacts / f"{label}-{index}"
    entry = {"index": index}
    try:
        receipt = reconstruct(
            execution_ref=execution,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=target,
            worker_profile=worker_profile,
        )
        weights = target / "checkpoint" / "state.npz"
        # Predictions, when the divergence measurement asked for them. A digest
        # establishes *different* and not *how different*, and the quantity the
        # study reasons about is prediction divergence rather than parameter
        # divergence - two to three orders of magnitude apart on the CPU work.
        #
        # Produced through the registered `predict()` rather than a forward pass
        # written here, and from the same archive inputs on every run, so what
        # differs between two runs is the reconstruction and nothing else.
        if os.environ.get("STUDY_PREDICTIONS") == "1":
            import numpy as _np

            from carbon.reconstruction.service import predict as _predict

            _traj = Trajectories.load(materials / "train.npz")
            _preds, _ = _predict(
                receipt,
                initial=_traj.initial,
                viscosity=_traj.viscosity,
                requested_times=_traj.times,
                positions=_traj.positions,
            )
            _np.save(target / "predictions.npy", _np.asarray(_preds))
        entry.update(
            {
                "status": receipt.status.value,
                "completed_steps": receipt.completed_steps,
                "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                "checkpoint_digest": receipt.checkpoint_digest,
                # The throughput trade, measured rather than asserted. Compile time
                # is where disabling autotuning is expected to show up, and it is
                # reported separately from execution for that reason.
                "compile_seconds": receipt.compile_seconds,
                "train_execution_seconds": receipt.train_execution_seconds,
            }
        )
    except BaseException as exc:  # noqa: BLE001 - every disposition is recorded
        entry.update(
            {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-1500:],
            }
        )
    record["runs"].append(entry)

digests = {r.get("weights_sha256") for r in record["runs"] if "weights_sha256" in r}
record["successful_runs"] = len(
    digests and [r for r in record["runs"] if "weights_sha256" in r] or []
)
record["distinct_weight_digests"] = len(digests)
record["bit_identical"] = len(digests) == 1 and record["successful_runs"] == runs
# Printed before it is written. A device session is expensive enough that a
# failed file write must not be able to discard its result.
print("RECORD_BEGIN")
print(json.dumps(record, indent=1, sort_keys=True))
print("RECORD_END")
try:
    out.write_text(json.dumps(record, indent=1, sort_keys=True))
except OSError as exc:
    print("could not write results file:", exc)
