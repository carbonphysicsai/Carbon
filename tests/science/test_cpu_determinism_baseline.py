"""The CPU determinism baseline: is this workload deterministic at all?

Before any GPU attempt is spent, one question has to be answered without one: do
two independent trainings of the same registered strategy, under identical R0
identities, produce the same bytes? If they do, a GPU divergence observed later
is attributable to the device. If they do not, there is a determinism problem
that has nothing to do with GPUs and should be understood before attempts are
spent on it.

The measurement's method matters. `reconstruct()` returns `_validate_existing()`
when its `artifact_path` already exists, so calling it twice against one path
measures cache reuse, not determinism. Each repeat here trains independently into
its own directory.

Recorded finding: `.agent/evidence/wave_c/c-core-19-cpu-determinism-baseline.md`.
Nothing here qualifies a backend or sets a tolerance.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from c02_fixtures import compile_c02_plan

from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
from carbon.reconstruction import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.service import reconstruct
from carbon.seeding import DerivedSeed

WEIGHTS = Path("checkpoint") / "state.npz"
CHECKPOINT_MANIFEST = Path("checkpoint") / "manifest.json"

# The manifest keys that record how long a run took, rather than what it
# computed. These are the only values observed to differ between independent
# runs of identical work.
TIMING_KEYS = ("compile_seconds", "train_execution_seconds")


def _data() -> Trajectories:
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


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _repeat(tmp_path: Path, backbone: str, count: int):
    """Train `count` times into distinct paths under identical R0 identities."""
    source = tmp_path / "train.npz"
    _data().save(source)
    archive = PublicTrainingArchive.from_file(
        source, provenance="cpu_determinism_baseline"
    )
    plan = compile_c02_plan(tmp_path, backbone=backbone)
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("12345678-1234-4234-8234-123456789abc"))), 1
    )
    seed = DerivedSeed(bytes(range(32)))

    runs = []
    for index in range(count):
        target = tmp_path / f"artifact-{backbone}-{index}"
        assert not target.exists(), "each repeat must train, not reuse a cache"
        receipt = reconstruct(
            execution_ref=execution,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=target,
        )
        assert receipt.status is ReconstructionStatus.COMPLETE
        runs.append((receipt, target))
    return runs


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_independent_cpu_trainings_produce_identical_weights(
    tmp_path: Path, backbone: str
) -> None:
    """The baseline itself: the numerics are byte-for-byte reproducible.

    This is what makes a later GPU divergence attributable to the device. If it
    ever fails, the correct response is to understand why the workload stopped
    being deterministic - not to introduce a tolerance here, which would hide
    exactly the signal this exists to provide.
    """
    runs = _repeat(tmp_path, backbone, 2)
    weights = {_sha(target / WEIGHTS) for _, target in runs}
    manifests = {_sha(target / CHECKPOINT_MANIFEST) for _, target in runs}

    assert len(weights) == 1, f"independent CPU trainings diverged: {sorted(weights)}"
    assert len(manifests) == 1


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_every_artifact_file_except_the_timing_manifest_is_identical(
    tmp_path: Path, backbone: str
) -> None:
    """Scoped to the whole artifact, so a new non-deterministic file shows up."""
    runs = _repeat(tmp_path, backbone, 2)
    trees = []
    for _, target in runs:
        trees.append(
            {
                str(item.relative_to(target)): _sha(item)
                for item in sorted(target.rglob("*"))
                if item.is_file()
            }
        )
    first, second = trees
    assert set(first) == set(second), "the two runs produced different files"
    differing = sorted(name for name in first if first[name] != second[name])
    assert differing == ["manifest.json"], (
        "only the top-level manifest is expected to differ between identical "
        f"runs; also differing: {differing}"
    )


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_only_the_recorded_timings_differ_between_identical_runs(
    tmp_path: Path, backbone: str
) -> None:
    """Names the cause, so a *new* source of variation cannot hide behind it."""
    runs = _repeat(tmp_path, backbone, 2)
    first, second = (
        json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        for _, target in runs
    )
    assert set(first) == set(second)
    differing = sorted(key for key in first if first[key] != second[key])
    assert differing == sorted(TIMING_KEYS), (
        "identical runs differed in something other than their recorded "
        f"timings: {differing}"
    )


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_the_artifact_digest_is_not_a_determinism_signal(
    tmp_path: Path, backbone: str
) -> None:
    """Pinned deliberately, because a measurement campaign could be built on it.

    `artifact_digest` is a tree digest, and the tree contains wall-clock
    timings, so it differs between two runs that computed identical weights. An
    evidence specification comparing artifact digests would report nondeterminism
    in every case - including CPU against CPU - and would be measuring a clock.

    Asserted rather than merely documented so that if the digest ever does become
    stable, the change is visible and the guidance above can be revisited instead
    of silently going stale.
    """
    runs = _repeat(tmp_path, backbone, 2)
    digests = {receipt.artifact_digest for receipt, _ in runs}
    weights = {_sha(target / WEIGHTS) for _, target in runs}

    assert len(weights) == 1, "precondition: the weights must be identical"
    assert len(digests) == 2, (
        "the artifact digest is now stable across independent runs; the "
        "determinism guidance in the P8 evidence packet should be revisited"
    )
