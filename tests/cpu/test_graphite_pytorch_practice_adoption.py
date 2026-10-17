"""Explicit CPU Torch adoption; all Docker/host observations are fixtures."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_miner_install import (
    RELEASE,
    Sandbox,
    built,
    publish_release,
    pulled,
    run_release,
)
from test_worker_image_release import manifest as worker_manifest
from test_worker_image_release import (
    refused,
    run,
    tools,  # noqa: F401 - fixture
)

from carbon.battery.research import image_backends
from carbon.development_session import research_image
from carbon.reconstruction import torch_profile
from carbon.reconstruction.worker import docker_runtime
from scripts.dev import worker_image_release as release
from scripts.dev.miner_launchpad.environment_setup import LiveChecks, SetupRefused

ROOT = Path(__file__).resolve().parents[2]
PARENT = "sha256:" + "2" * 64
CHILD = "sha256:" + "3" * 64
SOURCE = "sha256:" + "a" * 64
TORCH_KINDS = ("torch", "torch-analysis", "accelerator", "torch-gpu")


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


def offer_fixture_gpu(sandbox):
    sandbox._executable(sandbox.tools / "nvidia-smi", "#!/bin/sh\nexit 0\n")


def test_local_install_builds_torch_and_passes_that_parent_to_analysis(
    sandbox,
):
    script = sandbox.work / "scripts/dev/torch_worker_image.sh"
    sandbox._executable(
        script,
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        'echo "{\\"image_id\\":\\"sha256:torch-$(git rev-parse HEAD)\\"}" > "$1"\n'
        'echo "torch worker" >> "$CARBON_TEST_LOG"\n',
    )
    sandbox.publish("fixture Torch builder")
    result = sandbox.run("--pytorch", "--no-start")
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert "torch worker" in log
    assert not any(line.startswith("worker ") for line in log)
    (analysis,) = [line for line in log if "research_image" in line]
    primary = sandbox.clone / ".carbon-artifacts/torch-worker-image.json"
    assert f"--parent-manifest {primary}" in analysis
    (recorded,) = [line for line in log if "installed write" in line]
    assert f"--image-manifest {primary}" in recorded


def test_local_torch_gpu_install_uses_the_separate_torch_builder(sandbox):
    offer_fixture_gpu(sandbox)
    sandbox._executable(
        sandbox.work / "scripts/dev/torch_worker_image.sh",
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        'echo "{\\"image_id\\":\\"sha256:torch-$(git rev-parse HEAD)\\"}" > "$1"\n'
        'echo "torch worker" >> "$CARBON_TEST_LOG"\n',
    )
    sandbox._executable(
        sandbox.work / "scripts/dev/torch_gpu_worker_image.sh",
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        'echo "{\\"image_id\\":\\"sha256:torch-gpu-$(git rev-parse HEAD)\\"}" > "$1"\n'
        'echo "torch gpu worker" >> "$CARBON_TEST_LOG"\n',
    )
    sandbox.publish("fixture Torch GPU builders")
    result = sandbox.run("--pytorch", "--gpu", "--no-start")
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert "torch worker" in log
    assert "torch gpu worker" in log
    assert "gpu worker" not in log
    (recorded,) = [line for line in log if "installed write" in line]
    gpu = sandbox.clone / ".carbon-artifacts/torch-gpu-worker-image.json"
    assert f"--gpu-image-manifest {gpu}" in recorded


def test_release_installs_the_complete_torch_pair_without_a_build(
    sandbox,
):
    publish_release(sandbox, kinds=TORCH_KINDS)
    result = run_release(sandbox, "--pytorch", "--release", RELEASE, "--no-start")
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert built(log) == []
    assert pulled(log) == [
        "torch-worker-image.release.json",
        "torch-analysis-worker-image.release.json",
    ]
    (recorded,) = [line for line in log if "installed write" in line]
    directory = sandbox.clone / ".carbon-artifacts/releases" / RELEASE
    assert f"--image-manifest {directory}/torch-worker-image.json" in recorded
    assert (
        f"--analysis-image-manifest {directory}/torch-analysis-worker-image.json"
        in recorded
    )


def test_release_torch_gpu_selection_pulls_and_records_its_exact_kind(sandbox):
    offer_fixture_gpu(sandbox)
    publish_release(sandbox, kinds=TORCH_KINDS)
    result = run_release(
        sandbox, "--pytorch", "--gpu", "--release", RELEASE, "--no-start"
    )
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert built(log) == []
    assert pulled(log) == [
        "torch-worker-image.release.json",
        "torch-analysis-worker-image.release.json",
        "torch-gpu-worker-image.release.json",
    ]
    (recorded,) = [line for line in log if "installed write" in line]
    directory = sandbox.clone / ".carbon-artifacts/releases" / RELEASE
    assert f"--gpu-image-manifest {directory}/torch-gpu-worker-image.json" in recorded
    assert (
        f"--gpu-release-record {directory}/torch-gpu-worker-image.release.json"
        in recorded
    )


def test_missing_torch_gpu_record_refuses_before_checkout_or_pull(sandbox):
    offer_fixture_gpu(sandbox)
    before = sandbox.head()
    publish_release(
        sandbox,
        commit=sandbox.publish("newer fixture source"),
        kinds=("torch", "torch-analysis", "accelerator"),
    )
    result = run_release(
        sandbox, "--pytorch", "--gpu", "--release", RELEASE, "--no-start"
    )
    assert result.returncode == 2
    assert "could not download the torch-gpu release record" in result.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def test_missing_torch_companion_stops_before_checkout_bootstrap_or_pull(
    sandbox,
):
    before = sandbox.head()
    publish_release(
        sandbox,
        commit=sandbox.publish("newer fixture source"),
        kinds=("torch", "analysis", "accelerator"),
    )
    result = run_release(sandbox, "--pytorch", "--release", RELEASE, "--no-start")
    assert result.returncode == 2
    assert "could not download the torch-analysis release record" in result.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def test_older_installer_without_selection_is_refused_before_checkout(
    sandbox,
):
    before = sandbox.head()
    script = sandbox.work / "scripts/install_miner.sh"
    text = script.read_text(encoding="utf-8")
    script.write_text(
        text.replace("    --pytorch) PYTORCH=1 ;;\n", ""), encoding="utf-8"
    )
    sandbox.publish("fixture old installer")
    result = sandbox.run("--pytorch", "--no-start")
    assert result.returncode == 2
    assert "has no --pytorch selection" in result.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def analysis_manifest():
    return {
        "schema": research_image.SCHEMA,
        "image_id": CHILD,
        "parent_image": PARENT,
        "runtime_digest": "sha256:" + "4" * 64,
    }


def analysis_record():
    value = analysis_manifest()
    return {
        "schema": release.RECORD_SCHEMA,
        "kind": "torch-analysis",
        "release_tag": "worker-images-v90",
        "source_commit": "f" * 40,
        "repository": "ghcr.io/carbonphysicsai/carbon-torch-miner-analysis",
        "registry_digest": CHILD,
        "reference": f"ghcr.io/carbonphysicsai/carbon-torch-miner-analysis@{CHILD}",
        "scope": release.SCOPE,
        "security_acceptance": release.SECURITY_ACCEPTANCE,
        "image_store": release.IMAGE_STORE,
        "labels": release.identity_labels(value, "torch-analysis"),
        "manifest": value,
    }


def test_torch_analysis_uses_the_closed_analysis_identity():
    record = analysis_record()
    assert release.check_record(record) == record
    assert record["labels"] == {
        release.LABEL + "d4.parent": PARENT,
        release.LABEL + "d4.runtime": record["manifest"]["runtime_digest"],
    }
    for change in (
        {"manifest": worker_manifest()},
        {"labels": {**record["labels"], release.LABEL + "d4.parent": CHILD}},
        {"registry_digest": PARENT},
        {"kind": "torch"},
    ):
        with pytest.raises(release.Refused):
            release.check_record({**record, **change})


@pytest.mark.parametrize("changed_parent", [False, True])
def test_pulled_torch_analysis_requires_its_recorded_parent_label(
    tmp_path, tools, changed_parent  # noqa: F811
):
    record = analysis_record()
    path, out = tmp_path / "release.json", tmp_path / "analysis.json"
    path.write_text(release.canonical(record), encoding="utf-8")
    labels = dict(record["labels"])
    if changed_parent:
        labels[release.LABEL + "d4.parent"] = CHILD
    inspected = {
        "Id": CHILD,
        "RepoDigests": [record["reference"]],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "User": release.USER,
            "Entrypoint": release.ENTRYPOINT,
            "Labels": labels,
        },
    }
    result, calls = run(
        tools,
        "pull",
        "--record",
        str(path),
        "--out",
        str(out),
        inspect=inspected,
        CARBON_FAKE_REF=record["reference"],
        CARBON_FAKE_ID=CHILD,
    )
    assert len(calls) == 2
    if changed_parent:
        assert refused(result) == "label_mismatch"
        assert not out.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(out.read_text(encoding="utf-8")) == record["manifest"]


@pytest.mark.parametrize(
    "kind,repository", [("c03", "carbon-c03-worker"), ("torch", "carbon-torch-worker")]
)
def test_parent_helper_selects_only_the_named_repository(kind, repository):
    script = ROOT / "scripts/dev/worker_parent_ref.sh"
    env = {
        **os.environ,
        "CARBON_WORKER_PARENT_REPOSITORY": f"ghcr.io/carbonphysicsai/{repository}",
    }
    result = subprocess.run(
        ["bash", str(script), PARENT, SOURCE, kind],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{env['CARBON_WORKER_PARENT_REPOSITORY']}@{PARENT}"
    wrong = "c03" if kind == "torch" else "torch"
    result = subprocess.run(
        ["bash", str(script), PARENT, SOURCE, wrong],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2


def test_analysis_release_parent_kind_comes_from_exact_cpu_torch_lock():
    parent = SimpleNamespace(
        image_id=PARENT,
        source_tree_digest=SOURCE,
        lock_digest=torch_profile.requirements_digest(ROOT),
    )
    repository = "ghcr.io/carbonphysicsai/carbon-torch-worker"
    assert (
        research_image.release_parent_reference(parent, repository)
        == f"{repository}@{PARENT}"
    )
    parent.lock_digest = torch_profile.GPU_LOCK_DIGEST
    with pytest.raises(ValueError, match="release parent reference refused"):
        research_image.release_parent_reference(parent, repository)


def test_setup_keeps_parent_source_and_doctor_guards(monkeypatch, tmp_path):
    parent = SimpleNamespace(image_id=PARENT, source_tree_digest=SOURCE)
    child = SimpleNamespace(image_id=CHILD, parent_image=PARENT)
    checks = LiveChecks()
    implementation = {"source_tree_digest": SOURCE}
    monkeypatch.setattr(checks, "revision", lambda: implementation)
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: parent)
    eligible = {"value": True}
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kw: SimpleNamespace(eligible=eligible["value"]),
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda path: child)
    monkeypatch.setattr(research_image, "verify_image", lambda image: image)
    paths = (tmp_path / "primary.json", tmp_path / "analysis.json")
    assert checks.compute(*paths)["images"] == [PARENT, CHILD]
    child.parent_image = CHILD
    with pytest.raises(SetupRefused, match="analysis_image_unverified"):
        checks.compute(*paths)
    child.parent_image = PARENT
    parent.source_tree_digest = CHILD
    with pytest.raises(SetupRefused, match="worker_image_unverified"):
        checks.compute(*paths)
    parent.source_tree_digest = SOURCE
    eligible["value"] = False
    with pytest.raises(SetupRefused, match="worker_image_unverified"):
        checks.compute(*paths)


def test_cpu_backend_selection_remains_exact_lock_and_default_jax():
    assert image_backends(SimpleNamespace(lock_digest=SOURCE), ROOT) == ("jax",)
    parent = SimpleNamespace(lock_digest=torch_profile.requirements_digest(ROOT))
    assert image_backends(parent, ROOT) == ("jax", "pytorch")
    parent.lock_digest = torch_profile.GPU_LOCK_DIGEST
    assert image_backends(parent, ROOT) == ("jax",)


def test_torch_cpu_recipe_reaches_the_existing_cpu_carrier(tmp_path):
    from test_battery_validator_daemon import submission

    from carbon.battery.research import PROGRAM, BatteryPractice

    selected = SimpleNamespace(
        image_id=PARENT, lock_digest=torch_profile.requirements_digest(ROOT)
    )
    seen = []

    def capture(ledger, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("captured-before-dispatch")

    callback = BatteryPractice(
        ledger=SimpleNamespace(root=tmp_path),
        owner="fixture",
        image=selected,
        root=ROOT,
        runner=capture,
    )
    callback._seed = lambda identity: 0
    recipe = submission(
        "hk", "mlp", backend="pytorch", width=8, depth=1, steps=32
    ).strategy
    assert callback.backend_refusal(recipe) is None
    with pytest.raises(RuntimeError, match="captured-before-dispatch"):
        callback("fixture", recipe)
    assert len(seen) == 1
    assert seen[0]["image"] is selected
    assert seen[0]["source"] == PROGRAM
    assert "accelerator" not in seen[0]


def test_release_builds_torch_analysis_after_publishing_its_parent():
    script = (ROOT / "scripts/dev/release_worker_images.sh").read_text(encoding="utf-8")
    pushed = script.index("publish_image torch carbon-torch-worker")
    built = script.index("torch_analysis_built=")
    checked = script.index(
        '"${artifacts}/torch-analysis-worker-image.json" parent_image'
    )
    published = script.index("torch-analysis:carbon-torch-miner-analysis")
    assert pushed < built < checked < published
    assert '--parent-manifest "${artifacts}/torch-worker-image.json"' in script
    assert '--parent-repository "${torch_repository}"' in script
