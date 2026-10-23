"""The pod job's artifact writer round-trips through the calibration-grade verifier."""

from __future__ import annotations

import json

import pytest

from carbon.agent_campaign import calibration_artifact_job as job
from carbon.challenge_validator import calibration_grade as cg

COMMON = {
    "challenge_id": "f02",
    "version": "2.3",
    "bundle_ref": "catalog/f02.x",
    "bundle_sha256": "sha256:" + "b" * 64,
    "worker_image_digest": "sha256:" + "c" * 64,
    "parent_image_digest": "sha256:" + "d" * 64,
    "train_sha256": "sha256:" + "e" * 64,
    "seed": 0,
    "build_wall_s": 12.5,
    "pod_id": "pod-ref-1",
}


def test_the_written_artifact_verifies_and_pins_match(tmp_path):
    out = tmp_path / "a"
    manifest = job.write_artifact(
        out,
        recipe_bytes=b'{"r":1}',
        state_bytes=b"state",
        runtime="torch-cu130-py311",
        gpu=("RTX 4090", "580.1", "13.0"),
        **COMMON,
    )
    artifact = cg.load_artifact(
        out,
        challenge_id="f02",
        recipe_digest=manifest["recipe_digest"],
        state_sha256=manifest["state_sha256"],
        worker_image_digest=COMMON["worker_image_digest"],
        train_sha256=COMMON["train_sha256"],
    )
    assert artifact.manifest["gpu_model"] == "RTX 4090"
    assert set(artifact.manifest) == cg.MANIFEST_KEYS


def test_a_cpu_runtime_needs_no_gpu_and_the_manifest_has_no_credentials(tmp_path):
    job.write_artifact(
        tmp_path / "c",
        recipe_bytes=b"{}",
        state_bytes=b"s",
        runtime="torch-cpu-py311",
        **COMMON,
    )
    text = (tmp_path / "c" / "manifest.json").read_text()
    assert json.loads(text)["gpu_model"] == "none"
    for word in ("key", "token", "password", "balance", "account"):
        assert word not in text.lower().replace("pod_id", "")


@pytest.mark.parametrize(
    "change",
    [
        {"runtime": "other"},
        {"bundle_sha256": "nope"},
        {"pod_id": "has space"},
        {"seed": -1},
    ],
)
def test_malformed_fields_refuse(tmp_path, change):
    args = {"runtime": "torch-cpu-py311", **COMMON, **change}
    with pytest.raises(job.ArtifactRefused):
        job.write_artifact(tmp_path / "x", recipe_bytes=b"{}", state_bytes=b"s", **args)
