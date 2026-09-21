"""Stage GPU determinism materials on the host, the way the worker is staged.

Writes the plan, training archive, randomness and a materials manifest that
`repeat_gpu.py` reads inside the container. The shape is the study's subject, so
it is set here rather than defaulted:

    STUDY_OUT=<dir> STUDY_STEPS=32 STUDY_WIDTH=32 STUDY_MODES=16 \
        .venv/bin/python scripts/dev/gpu_determinism_study/prepare.py

Defaults are the representative-scale target recorded in
`docs/development/REPRESENTATIVE_SCALE_TARGET.md` - width 32 and 16 modes, the
values Carbon's own research campaign configures, giving 100,680 parameters
against the 4,696 every determinism result before C-CORE-21 used.

Set STUDY_WIDTH=8 STUDY_MODES=8 STUDY_STEPS=2 to stage the baseline control,
which should reproduce D3's pinned digest exactly and is what establishes the
harness is unchanged.
"""

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "tests/cpu")
sys.path.insert(0, ".")

import c02_fixtures
import numpy as np
from c02_fixtures import compile_c02_plan

from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.accelerators import GPU_PROFILE, accelerator_dependency_specs
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.profile import compile_development_profile
from carbon.seeding import DerivedSeed

out = Path(os.environ["STUDY_OUT"]).resolve()
out.mkdir(parents=True, exist_ok=True)


def data() -> Trajectories:
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack(
        (
            np.sin(2 * np.pi * positions),
            np.cos(2 * np.pi * positions),
            np.sin(4 * np.pi * positions) * 0.5,
            np.cos(4 * np.pi * positions) * 0.5,
        )
    )
    times = np.broadcast_to(np.array([0.05, 0.1]), (4, 2)).copy()
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    return Trajectories(
        initial,
        np.array([0.01, 0.02, 0.015, 0.025]),
        times,
        solution,
        positions,
        "train",
        "carbon_c02_science_fixture",
    )


# A GPU-profiled plan: the same shape `_gpu_fixture` builds for the worker tests.
original = c02_fixtures.DEPENDENCY_SPECS
c02_fixtures.ENVIRONMENT_ID = GPU_PROFILE.profile_id
c02_fixtures.ENVIRONMENT_VERSION = "1.0"
c02_fixtures.DEPENDENCY_SPECS = original + accelerator_dependency_specs(GPU_PROFILE)

workspace = out / "build"
workspace.mkdir(exist_ok=True)
steps = int(os.environ.get("STUDY_STEPS", "32"))
width = int(os.environ.get("STUDY_WIDTH", "32"))
modes = int(os.environ.get("STUDY_MODES", "16"))
# The baseline control is the one shape the fixture expresses without widening,
# so it is requested by omitting the model surfaces rather than by naming their
# defaults - which keeps its plan digest identical to every prior result.
scale = {} if (width, modes) == (8, 8) else {"width": width, "n_modes": modes}
plan = compile_c02_plan(
    workspace,
    backbone="fno",
    steps=steps,
    environment_digest=GPU_PROFILE.digest,
    **scale,
)
profile = compile_development_profile(plan)

data().save(out / "train.npz")
archive = PublicTrainingArchive.from_file(
    out / "train.npz", provenance="d3_gpu_determinism"
)
(out / "plan.bin").write_bytes(plan.canonical_bytes())
seed = DerivedSeed(bytes(range(32)))
(out / "randomness.bin").write_bytes(seed.as_backend_bytes())

ref = plan.to_ref()
(out / "materials.json").write_text(
    json.dumps(
        {
            "plan_ref": {
                "challenge_id": ref.challenge_key.challenge_id,
                "challenge_version": ref.challenge_key.version,
                "schema_version": ref.schema_version,
                "canonicalization_profile": ref.canonicalization_profile,
                "digest": ref.content_digest,
            },
            "archive_digest": archive.content_digest,
            "submission_id": str(uuid.UUID("12345678-1234-4234-8234-123456789abc")),
            "profile_digest": profile.profile_digest,
            "accelerator_profile_id": GPU_PROFILE.profile_id,
            "accelerator_profile_digest": GPU_PROFILE.digest,
        },
        indent=1,
    )
)
print("staged:", sorted(p.name for p in out.iterdir()))
print("plan digest:", ref.content_digest)
print("gpu profile digest:", GPU_PROFILE.digest)
