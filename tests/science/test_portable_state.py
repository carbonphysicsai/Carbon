"""Actual CPU state transport plus explicitly simulated cross-backend metadata.

Engineering comparison tolerances here are not physics/qualification thresholds.
"""

import hashlib
import json
import shutil

import jax
import numpy as np
import pytest
from test_c02_jax_conformance import _data

from carbon.reconstruction import portable_state as portable
from carbon.reconstruction._vendor.carbon_jax_lab import checkpoint
from carbon.reconstruction._vendor.carbon_jax_lab.config import (
    ModelConfig,
    TaskConfig,
    TrainConfig,
)
from carbon.reconstruction._vendor.carbon_jax_lab.training import (
    Trainer,
    predict_trajectories,
)


def trainer():
    return Trainer(
        ModelConfig(kind="fno1d", width=8, depth=1, n_modes=4),
        TaskConfig(),
        TrainConfig(steps=4, warmup_steps=0, batch_size=2),
        _data(),
    )


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    value = trainer()
    value.fit(until_step=2)
    path = tmp_path_factory.mktemp("portable") / "state"
    fingerprint = portable.save_research_state(
        value, path, principal="miner-a", operation_id="research-original"
    )
    return value, path, fingerprint


def test_cpu_logical_export_predictions_and_continuation(saved):
    source, path, fingerprint = saved
    details = portable.inspect_research_state(path, expected_digest=fingerprint)
    meta = details["logical_state"]
    assert meta["step"] == 2
    assert meta["physical_scaling"] == source.physical_scaling.to_dict()
    assert len(meta["paths"]) == len(meta["leaves"]) > 5
    assert details["binding"]["placement"]["backend"] == "cpu"
    continued = trainer()
    receipt = portable.load_research_continuation(
        continued,
        path,
        principal="miner-a",
        operation_id="research-continuation",
        expected_digest=fingerprint,
    )
    assert receipt["backend_changed"] is False
    assert receipt["continued_from_step"] == 2
    for expected, actual in zip(
        jax.tree.leaves(source.state), jax.tree.leaves(continued.state), strict=True
    ):
        np.testing.assert_array_equal(expected, actual)
    np.testing.assert_array_equal(
        predict_trajectories(source.predictor, source.state.params, source.data),
        predict_trajectories(
            continued.predictor, continued.state.params, continued.data
        ),
    )
    # Compare resumed research against the unchanged strict checkpoint loader.
    baseline = trainer()
    checkpoint.load_checkpoint(baseline, path / "checkpoint")
    baseline.fit()
    continued.fit()
    for expected, actual in zip(
        jax.tree.leaves(baseline.state), jax.tree.leaves(continued.state), strict=True
    ):
        np.testing.assert_array_equal(expected, actual)


@pytest.mark.parametrize(
    ("principal", "operation", "error"),
    [
        ("miner-b", "research-new", "cross-principal"),
        ("miner-a", "research-original", "new bound operation"),
        ("", "research-new", "bounded principal"),
        ("miner-a", "invalid\noperation", "bounded principal"),
    ],
)
def test_invalid_binding_rejected_before_state_change(
    saved, principal, operation, error
):
    _, path, fingerprint = saved
    value = trainer()
    before = value.state
    with pytest.raises(ValueError, match=error):
        portable.load_research_continuation(
            value,
            path,
            principal=principal,
            operation_id=operation,
            expected_digest=fingerprint,
        )
    assert value.state is before


def _rehash_test_metadata(path, *, backend=None, x64=None, extra=None):
    """Test-only metadata simulation; this does NOT execute on a GPU/TPU."""
    meta_path = path / "checkpoint/manifest.json"
    meta = json.loads(meta_path.read_bytes())
    if backend is not None:
        meta["environment"]["backend"] = backend
    if x64 is not None:
        meta["environment"]["x64"] = x64
    meta_path.write_bytes(portable._canonical(meta) + b"\n")
    binding_path = path / "binding.json"
    binding = json.loads(binding_path.read_bytes())
    binding["checkpoint_manifest_sha256"] = portable._digest(meta_path.read_bytes())
    if backend is not None:
        binding["placement"]["backend"] = backend
        binding["placement"]["device_kind"] = "SIMULATED_METADATA_NOT_HARDWARE"
    if extra is not None:
        binding.update(extra)
    raw = portable._canonical(binding)
    binding_path.write_bytes(raw)
    return portable._digest(raw)


def test_simulated_backend_change_requires_new_attempt_and_keeps_strict_resume(
    saved, tmp_path
):
    _, original, _ = saved
    path = tmp_path / "simulated"
    shutil.copytree(original, path)
    fingerprint = _rehash_test_metadata(path, backend="gpu")
    with pytest.raises(ValueError, match="resume environment mismatch"):
        checkpoint.load_checkpoint(trainer(), path / "checkpoint")
    receipt = portable.load_research_continuation(
        trainer(),
        path,
        principal="miner-a",
        operation_id="new-attempt",
        expected_digest=fingerprint,
    )
    assert receipt["backend_changed"] is True
    assert (
        receipt["source_placement"]["device_kind"] == "SIMULATED_METADATA_NOT_HARDWARE"
    )
    assert receipt["target_placement"]["backend"] == "cpu"
    assert receipt["scientifically_qualified"] is False


def test_precision_change_rejected_even_with_rebound_integrity(saved, tmp_path):
    _, original, _ = saved
    path = tmp_path / "precision"
    shutil.copytree(original, path)
    fingerprint = _rehash_test_metadata(path, x64=True)
    with pytest.raises(ValueError, match="precision change"):
        portable.load_research_continuation(
            trainer(),
            path,
            principal="miner-a",
            operation_id="new-attempt",
            expected_digest=fingerprint,
        )


def test_tampering_and_unknown_metadata_rejected(saved, tmp_path):
    _, original, fingerprint = saved
    path = tmp_path / "tampered"
    shutil.copytree(original, path)
    changed = _rehash_test_metadata(path, extra={"official_eligible": True})
    with pytest.raises(ValueError, match="digest differs"):
        portable.inspect_research_state(path, expected_digest=fingerprint)
    with pytest.raises(ValueError, match="closed canonical"):
        portable.inspect_research_state(path, expected_digest=changed)
    shutil.copyfile(original / "binding.json", path / "binding.json")
    with (path / "checkpoint/state.npz").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="byte integrity"):
        portable.inspect_research_state(path, expected_digest=fingerprint)


def test_immutable_bundle_and_non_array_state_rejected(saved, tmp_path):
    source, path, fingerprint = saved
    with pytest.raises(FileExistsError):
        portable.save_research_state(
            source, path, principal="miner-a", operation_id="new"
        )
    assert portable._digest((path / "binding.json").read_bytes()) == fingerprint
    with pytest.raises(ValueError, match="fully addressable"):
        portable._placement({"state": np.array([1.0])})
    path = tmp_path / "oversized"
    path.mkdir()
    (path / "checkpoint").mkdir()
    (path / "binding.json").write_bytes(b" " * 8193)
    with pytest.raises(ValueError, match="bounded research"):
        portable.inspect_research_state(path, expected_digest="sha256:" + "0" * 64)


def test_manifest_and_digest_use_no_executable_serialization(saved):
    _, path, fingerprint = saved
    assert {p.name for p in path.iterdir()} == {"binding.json", "checkpoint"}
    assert (
        fingerprint
        == "sha256:" + hashlib.sha256((path / "binding.json").read_bytes()).hexdigest()
    )
    assert {p.name for p in (path / "checkpoint").iterdir()} == {
        "state.npz",
        "manifest.json",
    }
