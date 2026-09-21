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

# ptxas writes intermediates under TMPDIR; the worker's scratch is a fresh
# tmpfs, so the directory has to exist before the first compilation.
for _scratch in (os.environ.get("TMPDIR"), "/scratch/tmp", "/work/tmp"):
    if _scratch:
        os.makedirs(_scratch, exist_ok=True)
os.environ.setdefault("TMPDIR", "/work/tmp")

import jax

from carbon.construction import (
    ResolvedConstructionPlanRef,
    decode_resolved_construction_plan,
)
from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
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
    "runs": [],
}
for index in range(runs):
    target = Path("/work") / f"{label}-{index}"
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
