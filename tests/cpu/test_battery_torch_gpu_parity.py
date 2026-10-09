"""PyTorch GPU works the way JAX GPU does (backend parity, owner 2026-10-06):
the GPU-host checks the executor runs inside the released torch-gpu image.

    CARBON_REQUIRE_CUDA=1 python -m pytest -q tests/cpu/test_battery_torch_gpu_parity.py

Without CUDA every test skips; with `CARBON_REQUIRE_CUDA=1` a missing device
fails instead, so a GPU run cannot pass vacuously. Each runs every PyTorch
family (mlp, deeponet, fno) at the small test settings:

- **in process,** the path worker-images-v2 failed (BATTERY-IMPL-3): fit on
  CUDA, then predict. Predictions are finite, and two rebuilds are
  bit-identical (weights digest, final loss, every prediction);
- **through Carbon's fixed worker program,** as the validator runs it: two
  rebuilds on the bound device give the same weights digest and final loss,
  and `fit.json` names the device and device kind, which battery's rebuild
  identity reads as a GPU device class (never compared with CPU's).

CPU and CUDA rebuilds are separate evidence and are not required to match
(TORCH-GPU-01), exactly as for JAX. The executor records the pass/fail and
the device in the run's evidence.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

FAMILIES = ("mlp", "deeponet", "fno")
REQUIRED = os.environ.get("CARBON_REQUIRE_CUDA") == "1"


def _cuda():
    if importlib.util.find_spec("torch") is None:
        return False
    import torch

    return torch.cuda.is_available()


pytestmark = pytest.mark.skipif(
    not REQUIRED and not _cuda(), reason="needs a CUDA device (the torch-gpu image)"
)


@pytest.fixture(scope="module")
def environment():
    """The bound GPU environment: the overlay's platform, the pinned CUDA
    library controls and the device kind, the device's own name."""
    assert _cuda(), "CARBON_REQUIRE_CUDA=1 but no CUDA device is visible"
    import torch

    from carbon.reconstruction import torch_gpu

    return {
        **torch_gpu.worker_environment(),
        "JAX_PLATFORMS": "cuda",
        torch_gpu.DEVICE_KIND_ENV: torch.cuda.get_device_name(0),
    }


def _recipe(family):
    from test_battery_construction_contract import BATTERY, SMALL, strategy

    from carbon.battery.compile import compile_recipe

    parameters = {**SMALL[family], "backend": "pytorch"}
    return compile_recipe(strategy(BATTERY, family, **parameters))[1]


def _in_process(recipe, environment, monkeypatch):
    from carbon.battery import challenge as ch
    from carbon.battery.compile import rebuild

    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    material = ch.PublicMaterial.load()
    model, stats = rebuild(recipe, material, 0, train=material.train.subset(48))
    return stats, model.predict(material.train.x[200:208])


@pytest.mark.parametrize("family", FAMILIES)
def test_fit_on_cuda_then_predict_is_finite_and_repeats(
    family, environment, monkeypatch
):
    import numpy as np

    recipe = _recipe(family)
    first = _in_process(recipe, environment, monkeypatch)
    second = _in_process(recipe, environment, monkeypatch)
    (stats, predictions), (again, repeated) = first, second
    assert stats["device"] == "cuda"
    assert stats["device_kind"] == environment["CARBON_ACCELERATOR_DEVICE_KIND"]
    assert stats["params_sha256"] == again["params_sha256"]
    assert stats["final_loss"] == again["final_loss"]
    for key in predictions:
        values = np.asarray(predictions[key], dtype=float)
        assert np.all(np.isfinite(values)), key
        assert np.array_equal(values, np.asarray(repeated[key], dtype=float)), key


def _worker(tmp_path, name, recipe, environment):
    from carbon.battery.worker import RECONSTRUCT_PROGRAM, reconstruct_files

    work, out = tmp_path / name / "work", tmp_path / name / "output"
    work.mkdir(parents=True)
    out.mkdir()
    for path, body in reconstruct_files(REPOSITORY, recipe, 3).items():
        (work / path).write_bytes(body)
    (work / "program.py").write_text(RECONSTRUCT_PROGRAM)
    scratch = tmp_path / name / "tmp"
    scratch.mkdir()
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={
            **os.environ,
            **environment,
            "PYTHONPATH": str(REPOSITORY),
            "TMPDIR": str(scratch),
        },
        check=True,
        timeout=1800,
    )
    return json.loads((out / "fit.json").read_text())


@pytest.mark.parametrize("family", FAMILIES)
def test_the_worker_program_repeats_on_the_bound_gpu(family, environment, tmp_path):
    from carbon.battery import rebuild_identity

    recipe = _recipe(family)
    a = _worker(tmp_path, "a", recipe, environment)
    b = _worker(tmp_path, "b", recipe, environment)
    assert a["params_sha256"] == b["params_sha256"]
    assert a["final_loss"] == b["final_loss"] and math.isfinite(a["final_loss"])
    kind = environment["CARBON_ACCELERATOR_DEVICE_KIND"]
    assert a["device"] == "cuda" and a["device_kind"] == kind
    identity = rebuild_identity.from_reconstruction(
        {"device_kind": kind, "fit": a, "pytorch_image": None}
    )
    assert identity["device_class"] == "gpu:" + kind
