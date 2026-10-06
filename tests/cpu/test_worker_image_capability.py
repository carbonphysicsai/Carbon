"""The released worker images' capability matrix (IMAGE-RELEASE-01).

The owner (2026-10-06): the released images must keep the full JAX and
PyTorch CPU and GPU capabilities, and the release must say plainly what CI
verified and what stays unverified until an A40 run. The probe and the
carrier are replaced here, so nothing reaches Docker. What is held:
- the pinned versions are read from `uv.lock` and the image exports;
- on a GPU-less host every GPU device and rebuild check is UNVERIFIED, never
  VERIFIED, and the PyTorch GPU cell is UNVERIFIED throughout;
- a version that differs from its lock, or a probe that fails, is FAILED and
  the command exits 1;
- the report carries the owner-reserved items as HUMAN_INPUT.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "worker_image_capability",
    REPOSITORY / "scripts" / "dev" / "worker_image_capability.py",
)
capability = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(capability)

RECORDS = {
    kind: {
        "reference": f"ghcr.io/carbonphysicsai/{kind}@sha256:" + "5" * 64,
        "release_tag": "worker-images-v1",
        "source_commit": "f" * 40,
    }
    for kind in capability.KINDS
}


def test_the_pinned_versions_are_read_from_the_lock_files():
    pins = capability.pinned_versions()
    uv = pins["uv.lock"]
    assert set(uv) == set(capability.JAX_NAMES)
    # The accelerator lock and the torch export agree with uv.lock on the
    # shared stack, and every cell's expectation is complete.
    for name in capability.JAX_NAMES:
        assert pins[capability.ACCELERATOR_LOCK][name] == uv[name]
    assert pins[capability.TORCH_EXPORT]["numpy"] == uv["numpy"]
    for cell in ("jax_cpu", "jax_gpu", "pytorch_cpu"):
        assert all(capability.expected_for(cell, pins).values())
    assert capability.expected_for("pytorch_cpu", pins)["torch"].endswith("+cpu")


def probe_like(pins, *, versions=None, torch_state=None):
    from carbon.reconstruction.torch_profile import DETERMINISM

    def run_probe(reference, mode, names, *, env=None, gpus=False):
        installed = {}
        for source in pins.values():
            installed.update(source)
        installed.update(versions or {})
        out = {"versions": {n: installed.get(n) for n in names}}
        if mode == "jax":
            out.update(
                platform="cpu",
                devices=["cpu:cpu"],
                xla_flags=(env or {}).get("XLA_FLAGS"),
            )
        else:
            out.update(
                cuda_available=False,
                devices=["cpu"],
                determinism=torch_state
                or {**dict(DETERMINISM), "cublas_workspace_config": None},
            )
        return out

    return run_probe


def rebuilt(manifests, backend):
    return {"state_sha256": "sha256:" + "0" * 64, "fit_backend": backend}


@pytest.fixture
def fakes(monkeypatch):
    pins = capability.pinned_versions()
    monkeypatch.setattr(capability, "run_probe", probe_like(pins))
    monkeypatch.setattr(capability, "carrier_rebuild", rebuilt)
    return pins


def test_a_gpu_less_host_verifies_cpu_and_leaves_every_gpu_check_unverified(fakes):
    cells = capability.matrix(RECORDS, {}, pins=fakes)
    assert cells["jax_cpu"]["status"] == "VERIFIED"
    assert cells["pytorch_cpu"]["status"] == "VERIFIED"
    assert cells["pytorch_cpu"]["checks"]["determinism_config"]["status"] == "VERIFIED"
    gpu = cells["jax_gpu"]["checks"]
    assert cells["jax_gpu"]["status"] == "UNVERIFIED"
    assert gpu["imports"]["status"] == gpu["lock_versions"]["status"] == "VERIFIED"
    for name in ("devices", "rebuild", "determinism_config"):
        assert gpu[name]["status"] == "UNVERIFIED", name
    assert cells["pytorch_gpu"]["status"] == "UNVERIFIED"
    assert {c["status"] for c in cells["pytorch_gpu"]["checks"].values()} == {
        "UNVERIFIED"
    }
    assert (
        "no PyTorch GPU worker image"
        in cells["pytorch_gpu"]["checks"]["imports"]["detail"]
    )


def test_a_version_off_its_lock_or_a_failed_probe_is_failed(fakes, monkeypatch):
    monkeypatch.setattr(
        capability, "run_probe", probe_like(fakes, versions={"optax": "0.0.1"})
    )
    cells = capability.matrix(RECORDS, {}, pins=fakes)
    assert cells["jax_cpu"]["status"] == "FAILED"
    assert (
        cells["jax_cpu"]["checks"]["lock_versions"]["detail"]["optax"]["installed"]
        == "0.0.1"
    )

    def broken(*args, **kwargs):
        raise RuntimeError("no such image")

    monkeypatch.setattr(capability, "run_probe", broken)
    cells = capability.matrix(RECORDS, {}, pins=fakes)
    assert cells["jax_cpu"]["checks"]["imports"]["status"] == "FAILED"
    assert cells["jax_cpu"]["checks"]["lock_versions"]["status"] == "FAILED"


def test_a_determinism_setting_not_in_force_is_failed(fakes, monkeypatch):
    from carbon.reconstruction.torch_profile import DETERMINISM

    state = {**dict(DETERMINISM), "intra_op_threads": 4}
    monkeypatch.setattr(capability, "run_probe", probe_like(fakes, torch_state=state))
    found = capability.matrix(RECORDS, {}, pins=fakes)["pytorch_cpu"]["checks"]
    assert found["determinism_config"]["status"] == "FAILED"
    assert found["determinism_config"]["detail"] == {"intra_op_threads": 4}
    # The CUDA-only settings are the PyTorch GPU cell's, never passed on CPU.
    gpu = capability.matrix(RECORDS, {}, pins=fakes)["pytorch_gpu"]["checks"]
    assert gpu["determinism_config"]["status"] == "UNVERIFIED"
    assert "carbon.torch.determinism" in gpu["determinism_config"]["detail"]


def test_the_report_names_the_owner_reserved_items_and_exits_on_failure(
    fakes, monkeypatch, tmp_path
):
    records = tmp_path / "records"
    records.mkdir()
    for kind, value in RECORDS.items():
        (records / f"{kind}-worker-image.release.json").write_text(json.dumps(value))
    out = tmp_path / "report.json"
    argv = ["--records", str(records), "--manifests", str(tmp_path), "--out", str(out)]
    assert capability.main(argv) == 0
    report = json.loads(out.read_text())
    assert report["schema"] == "carbon.worker-image-capability.v1"
    assert report["gpu_host"] is False
    for item in (
        "reproducibility_tolerance",
        "a40_determinism_rerun",
        "security_acceptance",
    ):
        assert report[item] == "HUMAN_INPUT"
    monkeypatch.setattr(
        capability, "run_probe", probe_like(fakes, versions={"jax": "0"})
    )
    assert capability.main(argv) == 1
