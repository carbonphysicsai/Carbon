"""Versioned battery implementations (TORCH-GPU-01, the owner's option A).

Ryan chose a new, versioned battery implementation for the PyTorch CUDA
rebuild path: every recipe identity moves forward, and implementation 1.0's
module bytes are kept read-only so run 5 and every 1.0 record still verify
from main. These tests hold:
- the 1.0 snapshot is exactly its pinned bytes; a changed byte, a changed
  manifest, a missing file or a re-pinned digest is refused (no silent
  re-pin);
- an unregistered version is refused;
- 1.0 records verify under 1.0: its implementation, recipe and built-record
  digests and run 5's recipe digests recompile from main;
- 2.0's identities differ from 1.0's, and only the PyTorch modules changed;
- each version stages its own module bytes, and the contracts pin each
  version's own implementation;
- the device is the worker's, never the recipe's: a missing or unknown device
  is Carbon's environment failure, never the candidate's;
- with PyTorch installed (CI), a CPU rebuild through the fixed worker program
  is byte-identical under 1.0 and 2.0.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.battery import implementation_versions as versions

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_level1 import LEVEL0_PINS, LEVEL0_PINS_V2

V1 = "sha256:e4c4f12958ba4cbbe5e088190eaeba19cc4a8e23378c8b119ca2bbaae96cc417"
TORCH_TRAINING = REPOSITORY / "carbon" / "battery" / "torch_training.py"

needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and (
        importlib.util.find_spec("torch") is None
        or importlib.util.find_spec("neuralop") is None
    ),
    reason="the science-torch group is not installed",
)


@pytest.fixture
def snapshots(tmp_path):
    """A copy of the snapshot tree to tamper with."""
    copy = tmp_path / "snapshots"
    shutil.copytree(versions.SNAPSHOTS, copy)
    return copy


# --- the snapshot is read-only ---------------------------------------------------


def test_the_v1_snapshot_is_exactly_its_pinned_bytes():
    assert versions.PINNED == {"1.0": V1}
    assert versions.PINNED["1.0"] == LEVEL0_PINS["implementation"]
    modules = versions.module_bytes("1.0")
    assert set(modules) == set(versions.MODULES)
    assert versions.digest_of(modules) == V1
    manifest = json.loads((versions.SNAPSHOTS / "v1" / "MANIFEST.json").read_text())
    assert manifest["implementation_digest"] == V1
    assert manifest["version"] == "1.0"


@pytest.mark.parametrize("module", versions.MODULES)
def test_a_changed_snapshot_byte_is_refused(snapshots, module):
    path = snapshots / "v1" / (module + ".snapshot")
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(versions.ImplementationUnavailable, match="not its pinned"):
        versions.module_bytes("1.0", root=snapshots)


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(implementation_digest="sha256:" + "0" * 64),
        lambda m: m["modules"].update({"training.py": "sha256:" + "0" * 64}),
        lambda m: m.update(version="2.0"),
        lambda m: m.update(schema="another"),
    ],
)
def test_a_changed_manifest_is_refused(snapshots, change):
    path = snapshots / "v1" / "MANIFEST.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(versions.ImplementationUnavailable):
        versions.module_bytes("1.0", root=snapshots)


def test_a_missing_snapshot_file_is_refused(snapshots):
    (snapshots / "v1" / "recipes.py.snapshot").unlink()
    with pytest.raises(versions.ImplementationUnavailable, match="unreadable"):
        versions.module_bytes("1.0", root=snapshots)


def test_a_silent_re_pin_is_refused(snapshots, monkeypatch):
    """Re-pinning 1.0 to other bytes, even with a matching manifest, fails:
    the bytes are not the digest pinned in code."""
    path = snapshots / "v1" / "training.py.snapshot"
    path.write_bytes(path.read_bytes() + b"# edited\n")
    manifest_path = snapshots / "v1" / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    edited = {
        name: (snapshots / "v1" / (name + ".snapshot")).read_bytes()
        for name in versions.MODULES
    }
    manifest["modules"] = {
        name: versions._sha256(edited[name]) for name in versions.MODULES
    }
    manifest["implementation_digest"] = versions.digest_of(edited)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(versions.ImplementationUnavailable):
        versions.module_bytes("1.0", root=snapshots)
    # Only a new pin would accept it, and a new pin is a new version.
    monkeypatch.setitem(versions.PINNED, "1.0", versions.digest_of(edited))
    assert versions.module_bytes("1.0", root=snapshots) == edited


def test_an_unregistered_version_is_refused():
    for version in ("0.9", "1.1", "3.0", ""):
        with pytest.raises(versions.ImplementationUnavailable):
            versions.module_bytes(version)
    assert versions.VERSIONS == ("1.0", "2.0") and versions.CURRENT == "2.0"
    assert versions.CURRENT not in versions.PINNED


# --- v1 records verify, v2 identities differ ---------------------------------------


def test_v1_identities_verify_and_v2_identities_differ():
    from carbon.battery import contracts
    from carbon.battery.compile import compile_recipe
    from carbon.battery.research import SCAFFOLD

    assert contracts.IMPLEMENTATION_VERSION == versions.CURRENT
    assert contracts.implementation_digest("1.0") == LEVEL0_PINS["implementation"]
    assert contracts.implementation_digest() == LEVEL0_PINS_V2["implementation"]
    v1 = compile_recipe(SCAFFOLD, implementation="1.0")[1]
    v2 = compile_recipe(SCAFFOLD)[1]
    assert v1.recipe_digest == LEVEL0_PINS["scaffold_recipe"]
    assert v2.recipe_digest == LEVEL0_PINS_V2["scaffold_recipe"]
    # The design is the same; only its implementation identity moved.
    assert v1.strategy_hash == v2.strategy_hash
    assert v1.plan_digest != v2.plan_digest
    assert contracts.battery_contracts("1.0") is not contracts.battery_contracts()
    assert contracts.battery_contracts("1.0") is contracts.battery_contracts("1.0")


def test_only_the_pytorch_modules_changed_in_v2():
    v1, v2 = versions.module_bytes("1.0"), versions.module_bytes()
    changed = sorted(name for name in versions.MODULES if v1[name] != v2[name])
    assert changed == ["torch_families.py", "torch_training.py"]


def test_each_version_stages_its_own_module_bytes():
    from carbon.battery import practice, worker

    v1 = versions.module_bytes("1.0")
    staged = practice.staged_modules("1.0")
    assert {practice.STAGED_MODULES[k]: v for k, v in staged.items()} == v1
    assert worker._code_files("1.0") == staged
    assert worker._code_files() == practice.staged_modules()
    assert worker._code_files() != staged


# --- the device is the worker's -----------------------------------------------------


def _function(name):
    tree = ast.parse(TORCH_TRAINING.read_text())
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name
    )


def test_a_device_failure_is_the_environments_never_the_candidates():
    from carbon.battery.worker import RECONSTRUCT_PROGRAM

    unavailable = _function("DeviceUnavailable")
    assert [b.id for b in unavailable.bases] == ["ImportError"]
    # The fixed worker program reports an ImportError as Carbon's environment.
    assert "except ImportError" in RECONSTRUCT_PROGRAM
    assert '"stage": "environment"' in RECONSTRUCT_PROGRAM
    source = TORCH_TRAINING.read_text()
    # The platform is the accelerator overlay's, JAX's own variable.
    assert 'PLATFORM_ENV = "JAX_PLATFORMS"' in source
    assert 'os.environ.get(PLATFORM_ENV, "cpu")' in source
    assert "CARBON_TORCH_DEVICE" not in source
    # The recipe never names a device: no recipe setting reaches it.
    selector = ast.unparse(_function("rebuild_device"))
    assert "settings" not in selector and "model" not in selector


def test_the_overlay_that_chooses_jaxs_platform_chooses_pytorchs():
    import accelerator_host

    from carbon.development_session.profile import canonical
    from carbon.reconstruction import torch_gpu
    from carbon.reconstruction.accelerators import (
        GPU_PROFILE,
        AcceleratorRole,
        worker_environment,
    )
    from carbon.reconstruction.host_inventory import HostDeviceRecord
    from carbon.reconstruction.worker.model import tagged_sha256

    document = accelerator_host.document("workstation_linux")
    record = HostDeviceRecord(document, tagged_sha256(canonical(document)))
    overlay = worker_environment(
        GPU_PROFILE, AcceleratorRole.VALIDATOR_RECONSTRUCTION, host_device=record
    )
    assert torch_gpu.platform(overlay) == "cuda"
    assert torch_gpu.expected_device_kind(overlay) == record.device_kind
    assert all(overlay[k] == v for k, v in torch_gpu.worker_environment().items())
    assert torch_gpu.platform({}) == "cpu"


@needs_torch
def test_device_selection_refuses_what_it_cannot_use(monkeypatch):
    import torch

    from carbon.battery import torch_training

    monkeypatch.delenv("JAX_PLATFORMS", raising=False)
    assert torch_training.rebuild_device() == torch.device("cpu")
    monkeypatch.setenv("JAX_PLATFORMS", "tpu")
    with pytest.raises(torch_training.DeviceUnavailable):
        torch_training.rebuild_device()
    monkeypatch.setenv("JAX_PLATFORMS", "cuda")
    if not torch.cuda.is_available():
        with pytest.raises(torch_training.DeviceUnavailable):
            torch_training.rebuild_device()
    # A CUDA rebuild without the pinned cuBLAS workspace is refused first.
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":16:8")
    with pytest.raises(torch_training.DeviceUnavailable):
        torch_training._determinism(torch.device("cuda"))


def _rebuild_on_cpu(tmp_path, version, recipe):
    """The fixed reconstruction program over `version`'s staged bytes."""
    from carbon.battery.worker import RECONSTRUCT_PROGRAM, reconstruct_files

    work = tmp_path / version / "work"
    (tmp_path / version / "output").mkdir(parents=True)
    work.mkdir()
    for name, body in reconstruct_files(
        REPOSITORY, recipe, 3, implementation=version
    ).items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(RECONSTRUCT_PROGRAM)
    env = {**os.environ, "JAX_PLATFORMS": "cpu"}
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={**env, "PYTHONPATH": str(REPOSITORY)},
        check=True,
        timeout=900,
    )
    return json.loads((tmp_path / version / "output" / "fit.json").read_text())


@needs_torch
@pytest.mark.parametrize("family", ["mlp", "deeponet", "fno"])
def test_a_cpu_rebuild_is_byte_identical_under_v1_and_v2(tmp_path, family):
    from test_battery_construction_contract import BATTERY, SMALL, strategy

    from carbon.battery.compile import compile_recipe

    parameters = {**SMALL[family], "backend": "pytorch"}
    recipe = compile_recipe(strategy(BATTERY, family, **parameters))[1]
    v1 = _rebuild_on_cpu(tmp_path, "1.0", recipe)
    v2 = _rebuild_on_cpu(tmp_path, "2.0", recipe)
    assert v1["params_sha256"] == v2["params_sha256"]
    assert v1["final_loss"] == v2["final_loss"]
    assert "device" not in v2
