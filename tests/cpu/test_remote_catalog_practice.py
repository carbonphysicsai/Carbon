"""Shared GPU practice path, stage S4: catalog bundle practice on the miner's
own remote GPU (OWNER-MINER-COMPUTE-LINK-ONLY-01, LINKONLY-D4).

The shared bundle worker's GPU phases pass the carrier's own layout: a
bootstrap, a verified overlay and the pinned uv stage. `FakeRemote` (from
`test_remote_runner`) runs the real job server; the carrier's `/input` and
`/scratch` are named by the adapter's test variables, as the hardened job
container's tmpfs mounts are in production. What these tests hold:
- the machine receives only the practice's staged public inputs and
  Carbon's fixed programs, and returns only the carrier's output set;
- a carrier-layout job runs only in Carbon's hardened job container
  (`ssh-docker`), refused over `ssh-container` before anything is reserved;
- a failed program or a refused output is infrastructure, still cleaned up;
- the catalog campaigns declare remote practice through the shared hooks,
  speed only and never official, and setup lists every catalog version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_remote_runner import (
    FakeRemote,
    campaign_ledger,
    fast_job,
    gpu_worker,
    loopback_without_proxy,  # noqa: F401 - autouse fixture
    state,
)

from carbon.compute import remote_runner
from carbon.compute.remote_runner import RemoteRunner, RemoteWorker
from carbon.compute.remote_transport import SSHContainer, SSHDocker
from carbon.development_session import catalog_gpu
from carbon.development_session.library_environment_cache import (
    VerifiedLibraryOverlay,
    _overlay_digest,
    _overlay_rows,
)
from carbon.development_session.profile import canonical, digest

#: The test carrier's bootstrap: the local carrier's BOOTSTRAP, with the
#: adapter's test roots for `/input` and `/scratch` and this interpreter.
BOOTSTRAP = """
import os, shutil, sys
from pathlib import Path
stage = Path(os.environ['CARBON_CARRIER_INPUT'])
scratch = Path(os.environ['CARBON_CARRIER_SCRATCH'])
work = scratch / 'workspace'; work.mkdir()
(scratch / 'output').mkdir()
for item in stage.iterdir():
    if item.name not in ('program.py', 'overlay'):
        shutil.copyfile(item, work / item.name)
os.chdir(work)
os.execv(sys.executable, [sys.executable, '-I', str(stage / 'program.py')])
"""
#: The carrier's program: it reports what it found where the carrier puts it.
PROGRAM = """
import json, os
from pathlib import Path
stage = Path(os.environ['CARBON_CARRIER_INPUT'])
work = Path.cwd()
data = json.loads((work / 'inputs.json').read_text())
overlay = stage / 'overlay'
(work.parent / 'output' / 'result.json').write_text(json.dumps({
    'sum': sum(data),
    'stage': sorted(p.name for p in stage.iterdir()),
    'overlay': sorted(p.relative_to(overlay).as_posix()
                      for p in overlay.rglob('*') if p.is_file())
               if overlay.is_dir() else None,
    'uv_executable': os.access(stage / 'uv-bin', os.X_OK),
}))
"""
UV_IDENTITY_FIELDS = {"schema", "uv_image", "bundle_ref", "parent_image_id"}


@pytest.fixture
def carrier(tmp_path, monkeypatch):
    """The adapter's `/input` and `/scratch`, as the job container mounts
    them: an empty input and a scratch of its own."""
    stage, scratch = tmp_path / "carrier-input", tmp_path / "carrier-scratch"
    stage.mkdir()
    scratch.mkdir()
    monkeypatch.setenv("CARBON_CARRIER_INPUT", str(stage))
    monkeypatch.setenv("CARBON_CARRIER_SCRATCH", str(scratch))
    return stage


def setup(tmp_path, transport=None):
    tmp_path.chmod(0o700)
    (tmp_path / "machine").mkdir()
    machine = FakeRemote(tmp_path / "machine")
    runner = RemoteRunner(
        transport=transport or SSHDocker(machine),
        worker=RemoteWorker(gpu_worker(), (("JAX_PLATFORMS", "cuda"),)),
        clock=lambda: 100.0,
        job=fast_job,
    )
    return runner, campaign_ledger(tmp_path), machine


def bundle_ref():
    ref = {"schema": "bundle-ref", "bundle_digest": "sha256:" + "4" * 64}
    return SimpleNamespace(to_dict=lambda: dict(ref))


def overlay(tmp_path):
    """A verified overlay tree with its receipt, as the owner cache seals it."""
    root = tmp_path / "overlay-cache"
    (root / "site-packages" / "pkg").mkdir(parents=True)
    (root / "source").mkdir()
    (root / "site-packages" / "pkg" / "__init__.py").write_bytes(b"VALUE = 1\n")
    (root / "source" / "model.py").write_bytes(b"def build():\n    return 2\n")
    rows = _overlay_rows(root)
    receipt = {
        "tree_digest": _overlay_digest(
            json.dumps(rows, separators=(",", ":")).encode()
        ),
        "file_count": len(rows),
        "total_file_bytes": sum(row[1] for row in rows),
        "bundle_ref": bundle_ref().to_dict(),
        "parent_image_id": gpu_worker().image_id,
        "archive_sha256": "sha256:" + "5" * 64,
    }
    (root / ".overlay.json").write_bytes(canonical(receipt))
    return VerifiedLibraryOverlay(
        path=root,
        tree_digest=receipt["tree_digest"],
        bundle_ref=bundle_ref(),
        parent_image_id=gpu_worker().image_id,
        archive_digest=receipt["archive_sha256"],
        file_count=len(rows),
        total_bytes=receipt["total_file_bytes"],
    )


def uv_stage():
    uv = b"#!/bin/sh\nexit 0\n"
    identity = {
        "schema": "carbon.development.pinned-uv-stage.v1",
        "uv_image": "uv",
        "bundle_ref": bundle_ref().to_dict(),
        "parent_image_id": gpu_worker().image_id,
    }
    control = {
        "bundle_ref": identity["bundle_ref"],
        "parent_image_id": identity["parent_image_id"],
        "uv_sha256": digest(uv),
    }
    stage = {"uv-bin": uv, "control.json": canonical(control)}
    return (lambda cli: dict(stage)), identity


def call(runner, ledger, identity="trial-1", **layout):
    return runner(
        ledger,
        owner="miner",
        identity=identity,
        source=PROGRAM,
        files={"inputs.json": canonical([1, 2, 3])},
        image=gpu_worker(),
        seconds=120,
        provenance="DIRECT_BUNDLE_PUBLIC_BUILD",
        extra_resources={},
        bootstrap=BOOTSTRAP,
        **layout,
    )


def test_an_overlay_build_runs_in_the_carrier_layout_and_returns_its_output(
    tmp_path, carrier
):
    runner, ledger, machine = setup(tmp_path)
    seen, verified = [], overlay(tmp_path)
    result = call(
        runner, ledger, trusted_overlay=verified, output_validator=seen.append
    )
    snapshot = ledger.root / result["operation"] / "snapshot"
    out = json.loads((snapshot / "result.json").read_bytes())
    assert out["sum"] == 6
    # The overlay is laid out where the carrier mounts it, and only there.
    assert out["overlay"] == [
        ".overlay.json",
        "site-packages/pkg/__init__.py",
        "source/model.py",
    ]
    # The carrier's output set: the job's stderr stays beside the snapshot.
    assert {p.name for p in snapshot.iterdir()} == {"result.json"}
    assert (ledger.root / result["operation"] / "remote-stderr.txt").is_file()
    assert seen == [snapshot]
    assert state(ledger) == ["SUCCEEDED"]
    assert machine.removed == machine.started
    # The request binds the layout: the bootstrap and the verified overlay.
    record = ledger.root / result["operation"] / "remote-job.json"
    layout = json.loads(record.read_bytes())["request"]["carrier_layout"]
    assert layout["bootstrap"] == digest(BOOTSTRAP.encode())
    assert layout["verified_overlay"]["tree_digest"] == verified.tree_digest
    assert result["official_eligible"] is False
    assert result["scientific_qualification"] is False


def test_the_machine_receives_only_the_staged_public_inputs_and_carbons_programs(
    tmp_path, carrier
):
    runner, ledger, _ = setup(tmp_path)
    provider, identity = uv_stage()
    result = call(
        runner,
        ledger,
        executable_files=("uv-bin",),
        trusted_stage_provider=provider,
        trusted_stage_identity=identity,
    )
    out = json.loads(
        (ledger.root / result["operation"] / "snapshot" / "result.json").read_bytes()
    )
    # Exactly the practice's staged inputs, the pinned uv stage the
    # controller checked, and the carrier's program: no other file, no path.
    assert out["stage"] == ["control.json", "inputs.json", "program.py", "uv-bin"]
    assert out["uv_executable"] is True and out["overlay"] is None


def test_a_uv_stage_that_differs_from_its_binding_sends_nothing(tmp_path, carrier):
    runner, ledger, machine = setup(tmp_path)
    provider, identity = uv_stage()
    with pytest.raises(ValueError):
        call(
            runner,
            ledger,
            executable_files=("uv-bin",),
            trusted_stage_provider=provider,
            trusted_stage_identity={**identity, "parent_image_id": "sha256:other"},
        )
    assert machine.started == [] and state(ledger) == ["FAILED_INFRA"]


def test_a_carrier_layout_job_runs_only_in_carbons_job_container(tmp_path):
    runner, ledger, _ = setup(tmp_path, transport=SSHContainer(object()))
    with pytest.raises(ValueError, match="ssh-docker"):
        call(runner, ledger)
    # Refused before anything was reserved or reached.
    assert state(ledger) == []


def test_a_failed_carrier_program_is_infrastructure_and_still_cleaned(
    tmp_path, carrier
):
    runner, ledger, machine = setup(tmp_path)
    with pytest.raises(remote_runner.RemoteJobFailure):
        runner(
            ledger,
            owner="miner",
            identity="trial-1",
            source="raise SystemExit(3)\n",
            files={"inputs.json": b"[]"},
            image=gpu_worker(),
            seconds=120,
            provenance="DIRECT_BUNDLE_PUBLIC_BUILD",
            extra_resources={},
            bootstrap=BOOTSTRAP,
        )
    assert state(ledger) == ["FAILED_INFRA"]
    assert machine.removed == machine.started


def test_an_output_the_bundle_worker_refuses_is_infrastructure(tmp_path, carrier):
    runner, ledger, machine = setup(tmp_path)

    def refuse(snapshot):
        raise ValueError("bundle build output identity differs")

    with pytest.raises(ValueError, match="identity differs"):
        call(runner, ledger, output_validator=refuse)
    assert state(ledger) == ["FAILED_INFRA"]
    assert machine.removed == machine.started


def test_a_layout_name_in_the_inputs_is_refused(tmp_path, carrier):
    runner, ledger, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="closed stage"):
        runner(
            ledger,
            owner="miner",
            identity="trial-1",
            source=PROGRAM,
            files={remote_runner.CARRIER_PROGRAM: b"x"},
            image=gpu_worker(),
            seconds=120,
            provenance="DIRECT_BUNDLE_PUBLIC_BUILD",
            extra_resources={},
            bootstrap=BOOTSTRAP,
        )
    assert state(ledger) == []


def test_the_job_container_mounts_an_empty_input_beside_its_scratch():
    from carbon.compute.remote_machine import start_script

    script = start_script(
        image_id=gpu_worker().image_id,
        name="carbon-job-" + "a" * 24,
        env=(),
        command=remote_runner.START_COMMAND,
    )
    assert "--tmpfs /input:rw,nosuid,nodev,exec," in script
    # Every LINKONLY-D4 control stays.
    assert "--read-only" in script and "--cap-drop ALL" in script
    assert "no-new-privileges" in script and "network create --internal" in script
    assert '--gpus "driver=nvidia,device=$carbon_gpu"' in script


def test_the_adapter_uses_the_carriers_own_roots():
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session.research_carrier import BOOTSTRAP as LOCAL

    assert '"/input"' in remote_runner.CARRIER_LAYOUT
    assert '"/scratch"' in remote_runner.CARRIER_LAYOUT
    for bootstrap in (LOCAL, worker.PREP_BOOTSTRAP, worker.OVERLAY_BUILD_BOOTSTRAP):
        assert "/input" in bootstrap and "/scratch/" in bootstrap


# --- the shared catalog hooks --------------------------------------------------


def torch_worker():
    from test_battery_gpu_practice import gpu_image

    from carbon.reconstruction import torch_profile

    return gpu_image("7", lock=torch_profile.GPU_LOCK_DIGEST)


def test_the_remote_practice_sends_only_the_gpu_phases_to_the_machine(monkeypatch):
    sent, local = [], []

    def remote_call(self, ledger, **kwargs):
        sent.append(kwargs["image"].image_id)
        return "remote"

    monkeypatch.setattr(RemoteRunner, "__call__", remote_call)
    remote = RemoteRunner(
        transport=SSHDocker(object()), worker=RemoteWorker(gpu_worker())
    )
    practice = catalog_gpu.RemotePractice(
        remote, lambda ledger, **kwargs: local.append(kwargs["image"]) or "local"
    )
    assert practice("ledger", image=gpu_worker()) == "remote"
    assert practice("ledger", image=torch_worker()) == "local"
    assert sent == [gpu_worker().image_id] and local == [torch_worker()]
    with pytest.raises(ValueError):
        catalog_gpu.RemotePractice(lambda *a, **k: None)


def test_the_remote_worker_is_the_pinned_gpu_worker_with_its_device_environment():
    worker = catalog_gpu.remote_worker(torch_worker())
    assert worker.image == torch_worker()
    environment = dict(worker.environment)
    assert environment["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert environment["JAX_PLATFORMS"] == "cuda"
    assert not any(key.startswith("CARBON_") for key in environment)
    with pytest.raises(ValueError):
        catalog_gpu.remote_worker(
            SimpleNamespace(image_id="sha256:" + "1" * 64, lock_digest="x")
        )


def test_the_runtime_declares_remote_practice_beside_the_gpu_scope():
    from carbon.compute.remote_route import declared_remote, remote_scope

    image = torch_worker()
    base = {"implementation": "i", "images": []}
    gpu = catalog_gpu.with_gpu(base, {"gpu_research": []}, "f08-ribbed-bracket", image)
    declared = {
        **gpu,
        "remote_gpu": [remote_scope("f08-ribbed-bracket", image, "ssh-docker")],
    }
    runtime = catalog_gpu.with_gpu(base, declared, "f08-ribbed-bracket", image)
    assert runtime == declared
    scope = declared_remote(runtime)
    assert scope["challenge"] == "f08-ribbed-bracket"
    assert scope["image"] == image.image_id
    assert scope["purpose"] == "speed_only" and scope["score"] is None
    assert scope["official_eligible"] is False
    assert runtime["gpu_research"][0]["label"] == "measured on GPU, not official"
    with pytest.raises(ValueError):
        catalog_gpu.with_gpu(base, {"remote_gpu": []}, "f08-ribbed-bracket", image)


def test_catalog_remote_practice_is_ssh_docker_only():
    image = torch_worker()
    base = {"implementation": "i", "images": []}
    gpu = catalog_gpu.with_gpu(base, {"gpu_research": []}, "f08-ribbed-bracket", image)
    from carbon.compute.remote_route import remote_scope

    over_container = {
        **gpu,
        "remote_gpu": [remote_scope("f08-ribbed-bracket", image, "ssh-container")],
    }
    with pytest.raises(ValueError, match="ssh-docker"):
        catalog_gpu.with_gpu(base, over_container, "f08-ribbed-bracket", image)


def test_every_catalog_version_offers_remote_practice_and_setup_lists_it():
    from carbon.challenge_registry.campaigns import (
        declared_remote,
        implemented_campaigns,
    )
    from carbon.compute.remote_route import remote_scope
    from scripts.dev.miner_launchpad.environment_setup import remote_challenges

    listed = {(item["id"], item["version"]) for item in remote_challenges()}
    catalog = []
    for entry, campaign in implemented_campaigns():
        if campaign.construction_kit is None or entry.compile_strategy is not None:
            continue
        catalog.append((entry.challenge_id, entry.version))
        assert campaign.remote_worker is catalog_gpu.remote_worker
        assert (entry.challenge_id, entry.version) in listed
        image = torch_worker()
        runtime = {
            "gpu_research": [campaign.gpu_scope(image)],
            "remote_gpu": [remote_scope(entry.challenge_id, image, "ssh-docker")],
        }
        # The registry's shape check accepts the shared scope for any catalog
        # Challenge, whichever version the registry lists first.
        assert declared_remote(runtime)["challenge"] == entry.challenge_id
    assert {cid for cid, _ in catalog} >= {
        "electric-motor-magnetics",
        "f08-ribbed-bracket",
    }


def test_a_remote_run_is_recorded_as_such_and_labelled_not_official():
    from carbon.development_session.research_carrier import MINER_GPU

    remote = RemoteRunner(
        transport=SSHDocker(object()), worker=RemoteWorker(gpu_worker())
    )
    practice = catalog_gpu.RemotePractice(remote)
    parent = gpu_worker()
    assert catalog_gpu.backend_record(MINER_GPU, parent, None, practice) == {
        "kind": "REMOTE_GPU",
        "parent": parent.image_id,
        "transport": "ssh-docker",
        "label": "measured on GPU, not official",
    }
    assert catalog_gpu.backend_record(MINER_GPU, parent, None, None) == {
        "kind": "C03_DOCKER_GPU",
        "parent": parent.image_id,
        "label": "measured on GPU, not official",
    }
    # A GPU host that ran the CPU build says why, and is not labelled GPU.
    assert catalog_gpu.backend_record(
        None, parent, "catalog_gpu_build_missing", practice
    ) == {
        "kind": "C03_DOCKER",
        "parent": parent.image_id,
        "gpu_note": "catalog_gpu_build_missing",
    }
