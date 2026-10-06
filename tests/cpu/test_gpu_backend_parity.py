"""JAX and PyTorch on the GPU, one mechanism (TORCH-GPU-01).

The owner (2026-10-06): "I want it to work the same way JAX does. Consistency
is key." Every assertion below runs for both backends. Where the two differ,
the difference is the frameworks', named in a comment:
- device selection: one accelerator overlay (`accelerators.worker_environment`)
  chooses the platform for both;
- the bound device kind: both read it from the same overlay and refuse a run
  bound to none;
- identity: both GPU worker images carry the same accelerator labels, and the
  release records the same extra labels for both;
- determinism: the CUDA library controls are one shared pin, delivered to both
  by the overlay;
- a missing device: Carbon's environment failure for both, never the
  candidate's;
- partitioning: one device-class rule, so a JAX GPU score and a PyTorch GPU
  score of one device kind are one class, and neither is compared with CPU;
- the capability cell: the same checks, probed under the same overlay.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from carbon.battery import exam
from carbon.battery import rebuild_identity as ri
from carbon.reconstruction import accelerators, torch_gpu, torch_profile

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

import accelerator_host

from carbon.development_session.profile import canonical

BACKENDS = ("jax", "pytorch")
KIND = "NVIDIA A40"
#: Each backend's GPU worker image recipe and release kind.
RECIPES = {
    "jax": REPOSITORY / ".devcontainer/accelerators/Dockerfile",
    "pytorch": REPOSITORY / ".devcontainer/torch/Dockerfile.gpu",
}
RELEASE_KINDS = {"jax": "accelerator", "pytorch": "torch-gpu"}
CELLS = {"jax": "jax_gpu", "pytorch": "pytorch_gpu"}


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _module(
    "worker_image_release", REPOSITORY / "scripts/dev/worker_image_release.py"
)
capability = _module(
    "worker_image_capability", REPOSITORY / "scripts/dev/worker_image_capability.py"
)


@pytest.fixture(scope="module")
def overlay():
    """The controller's overlay for a validator GPU rebuild on an A40 host."""
    from carbon.reconstruction.host_inventory import HostDeviceRecord
    from carbon.reconstruction.worker.model import tagged_sha256

    document = accelerator_host.document("workstation_linux", device_kind=KIND)
    record = HostDeviceRecord(document, tagged_sha256(canonical(document)))
    return accelerators.worker_environment(
        accelerators.GPU_PROFILE,
        accelerators.AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        host_device=record,
    )


def platform(backend, environ):
    """The platform each backend rebuilds on. JAX reads `JAX_PLATFORMS` itself
    (it is JAX's own variable); PyTorch reads the same variable through
    `torch_gpu.platform`."""
    if backend == "jax":
        return environ.get("JAX_PLATFORMS", "cpu")
    return torch_gpu.platform(environ)


@pytest.mark.parametrize("backend", BACKENDS)
def test_one_overlay_selects_the_device_for_both(backend, overlay):
    assert platform(backend, overlay) == "cuda"
    # With no overlay, both rebuild on the CPU, as the C-03 image's default.
    assert platform(backend, {"JAX_PLATFORMS": "cpu"}) == "cpu"


@pytest.mark.parametrize("backend", BACKENDS)
def test_both_read_and_require_the_bound_device_kind(backend, overlay):
    assert overlay["CARBON_ACCELERATOR_DEVICE_KIND"] == KIND
    if backend == "jax":
        # JAX's worker refuses a run bound to no device kind
        # (`accelerators.validate_worker_observation`), checked before any
        # observation is compared.
        with pytest.raises(ValueError, match="expected device kind required"):
            accelerators.validate_worker_observation(
                accelerators.GPU_PROFILE,
                None,
                global_device_count=1,
                process_count=1,
                matmul_precision="highest",
                expected_device_kind="",
            )
    else:
        assert torch_gpu.expected_device_kind(overlay) == KIND
        with pytest.raises(torch_gpu.EnvironmentIneligible, match="no device kind"):
            torch_gpu.expected_device_kind({})


@pytest.mark.parametrize("backend", BACKENDS)
def test_both_gpu_images_carry_the_same_accelerator_labels(backend):
    recipe = RECIPES[backend].read_text()
    for label in torch_profile.ACCELERATOR_LABELS:
        assert label + "=" in recipe, label
    assert release.KINDS[RELEASE_KINDS[backend]][1] == torch_profile.ACCELERATOR_LABELS


@pytest.mark.parametrize("backend", BACKENDS)
def test_one_shared_pin_for_the_cuda_library_controls(backend, overlay):
    shared = accelerators.GPU_DETERMINISM_ENVIRONMENT
    assert all(overlay[k] == v for k, v in shared.items())
    if backend == "jax":
        # XLA takes its framework controls as flags in the environment.
        assert overlay["XLA_FLAGS"] == " ".join(accelerators.GPU_DETERMINISM_XLA_FLAGS)
    else:
        # PyTorch takes them in process; they are pinned beside the XLA flags
        # and inside its accelerator profile's identity.
        assert torch_gpu.worker_environment() == shared
        pinned = dict(torch_profile.GPU_DETERMINISM)
        for key, value in accelerators.GPU_DETERMINISM_TORCH:
            assert pinned[key] == value


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_missing_device_is_the_environments_never_the_candidates(backend):
    if backend == "jax":
        source = (REPOSITORY / "carbon/reconstruction/service.py").read_text()
        assert '"reconstruction.runtime.environment_ineligible"' in source
    else:
        from carbon.battery.worker import RECONSTRUCT_PROGRAM

        # The fixed program reports an ImportError as `stage: environment`,
        # and a PyTorch device failure is one.
        source = (REPOSITORY / "carbon/battery/torch_training.py").read_text()
        assert "class DeviceUnavailable(ImportError):" in source
        assert "except ImportError" in RECONSTRUCT_PROGRAM


def _gpu_reconstruction(backend):
    """What each backend's GPU rebuild records about its device. A GPU carrier
    names the device in its identity, as JAX's GPU backend records do; a
    PyTorch rebuild also records the device kind it verified. Either way the
    field is `device_kind`."""
    if backend == "jax":
        return {"image": "sha256:" + "1" * 64, "device_kind": KIND, "fit": {}}
    return {
        "image": "sha256:" + "1" * 64,
        "pytorch_image": "sha256:" + "2" * 64,
        "fit": {"backend": "pytorch", "device": "cuda", "device_kind": KIND},
    }


@pytest.mark.parametrize("backend", BACKENDS)
def test_one_device_class_rule_for_both(backend):
    identity = ri.from_reconstruction(_gpu_reconstruction(backend))
    assert identity["device_class"] == "gpu:" + KIND
    gpu = {"eligible": True, "score": 0.1, "pool_version": 1, "rebuild": identity}
    cpu = {"eligible": True, "score": 0.5, "pool_version": 1}
    assert exam.nominate(gpu, cpu, 0.05)[0] is False
    assert exam.nominate(gpu, {**cpu, "rebuild": identity}, 0.05)[0] is True


def test_a_jax_and_a_pytorch_gpu_score_of_one_kind_are_one_class():
    classes = {
        ri.from_reconstruction(_gpu_reconstruction(b))["device_class"] for b in BACKENDS
    }
    assert classes == {"gpu:" + KIND}


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_capability_cell_is_the_same_for_both(backend, monkeypatch):
    seen = {}

    def run_probe(reference, mode, names, *, env=None, gpus=False):
        seen[mode] = dict(env or {})
        raise RuntimeError("no image here")

    monkeypatch.setattr(capability, "run_probe", run_probe)
    records = {
        kind: {"reference": f"r/{kind}@sha256:" + "5" * 64} for kind in capability.KINDS
    }
    pins = capability.pinned_versions()
    cells = capability.matrix(records, {}, pins=pins, gpus=True, expect_kind=KIND)
    names = set(cells[CELLS[backend]]["checks"])
    assert names == {
        "imports",
        "devices",
        "lock_versions",
        "determinism_config",
        "rebuild",
    }
    # The rebuild through the validator path stays UNVERIFIED for both while
    # its accelerator dispatch is disabled.
    assert cells[CELLS[backend]]["checks"]["rebuild"]["status"] == "UNVERIFIED"
    mode = "jax" if backend == "jax" else "torch_gpu"
    expected = capability.gpu_environment(gpus=True, expect_kind=KIND)
    assert seen[mode] == expected
