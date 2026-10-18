"""Operator composition checks; fixtures confer no real model/chain acceptance."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sqlite3
import sys
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_receiver as receiver
from carbon.development_session.profile import canonical

OWNER = "5" + "1" * 47
OTHER = "5" + "2" * 47
RECEIVER = "5" + "3" * 47
POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX task/owner-only ledger")


def _config(tmp_path):
    return {
        "schema": receiver.SCHEMA,
        "root": str(tmp_path / "receiver"),
        "runner_profile": str(tmp_path / "profile.json"),
        "host": "127.0.0.1",
        "port": 8767,
        "receiver_hotkey": RECEIVER,
        "lifetime_seconds": 30,
        "measure_query": True,
    }


def _allow_windows_receiver_fixture(monkeypatch):
    if os.name != "nt":
        return
    # The ledger transaction remains real. POSIX runs use the actual flock,
    # owner-only mode gate, and private JSON reader.
    monkeypatch.setitem(
        sys.modules,
        "fcntl",
        SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None),
    )

    def directory(path):
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(receiver, "_private_directory", directory)
    monkeypatch.setattr(
        receiver, "private_json", lambda path: json.loads(path.read_bytes())
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("host", "0.0.0.0"),
        ("port", True),
        ("port", 0),
        ("lifetime_seconds", 0),
        ("lifetime_seconds", True),
        ("measure_query", 1),
        ("material_cache_bytes", 0),
        ("material_cache_bytes", True),
        ("material_cache_bytes", "1024"),
        ("receiver_hotkey", "validator"),
        ("root", "relative"),
        ("runner_profile", None),
        ("construction_image_manifest", "relative-torch.json"),
        ("construction_image_manifest", None),
        ("inference_image_manifest", "relative-jax.json"),
        ("inference_image_manifest", None),
        ("challenge", {"id": "unregistered", "version": "1.0"}),
        (
            "challenge",
            {"id": "battery-fastcharge-ageing-development-v1", "version": "9.9"},
        ),
        ("challenge", "battery-fastcharge-ageing-development-v1"),
        ("exposure", {}),
    ],
)
def test_closed_private_configuration_refuses_untrusted_shape(
    tmp_path, monkeypatch, field, value
):
    cfg = {**_config(tmp_path), field: value}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


def test_configuration_retains_explicit_finite_measurement_policy(
    tmp_path, monkeypatch
):
    cfg = _config(tmp_path)
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    assert receiver.load_config(tmp_path / "config.json")["measure_query"] is True


def test_optional_material_capacity_is_exact_private_operator_input(
    tmp_path, monkeypatch
):
    cfg = {**_config(tmp_path), "material_cache_bytes": 1024**3}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg


def test_operator_selects_only_registered_public_battery_challenge(
    tmp_path, monkeypatch
):
    from carbon.battery import challenge

    cfg = {
        **_config(tmp_path),
        "challenge": {
            "id": challenge.CHALLENGE.challenge_id,
            "version": challenge.CHALLENGE.version,
        },
    }
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg


def test_evaluation_pack_selection_is_private_and_closed(tmp_path, monkeypatch):
    selection = {
        "root": str(tmp_path / "draft"),
        "manifest": "evaluation-pack.json",
        "public_root": str(tmp_path / "public"),
        "private_root": str(tmp_path / "private"),
    }
    cfg = {**_config(tmp_path), "evaluation_pack": selection}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    selection["manifest"] = "../other.json"
    with pytest.raises(ValueError, match="relative evaluation pack manifest"):
        receiver.load_config(tmp_path / "config.json")
    selection["manifest"] = "evaluation-pack.json"
    selection["private_root"] = "relative"
    with pytest.raises(ValueError, match="exact evaluation pack root"):
        receiver.load_config(tmp_path / "config.json")


@pytest.mark.parametrize(
    "field", ("construction_image_manifest", "inference_image_manifest")
)
def test_private_direct_image_manifest_requires_exact_regular_file(
    tmp_path, monkeypatch, field
):
    manifest = tmp_path / "torch.json"
    manifest.write_text("{}")
    cfg = {**_config(tmp_path), field: str(manifest)}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    cfg[field] = str(tmp_path / "missing.json")
    with pytest.raises(ValueError, match=field.replace("_", " ")):
        receiver.load_config(tmp_path / "config.json")
    cfg[field] = str(tmp_path)
    with pytest.raises(ValueError, match=field.replace("_", " ")):
        receiver.load_config(tmp_path / "config.json")


def test_installed_source_joins_only_exact_owner_candidate_and_installed_images(
    tmp_path, monkeypatch
):
    from carbon.development_session import (
        gpu_practice,
        miner_network,
        research_campaign,
        research_image,
    )
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import installed, runner

    state = tmp_path / "state"
    profile = state / "environment" / "runner-profile.json"
    campaigns = profile.parent / "campaigns"
    accepted = {"revision": "a" * 40, "source_tree_digest": "sha256:" + "a" * 64}
    candidate = {
        "revision": "b" * 40,
        "tree": "c" * 40,
        "source_tree_digest": "sha256:" + "b" * 64,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    worker = SimpleNamespace(
        image_id="sha256:" + "1" * 64,
        source_tree_digest=candidate["source_tree_digest"],
    )
    analysis = SimpleNamespace(
        image_id="sha256:" + "2" * 64, parent_image=worker.image_id
    )
    gpu = SimpleNamespace(
        image_id="sha256:" + "3" * 64,
        source_tree_digest=candidate["source_tree_digest"],
    )
    cfg = {
        "enabled": True,
        "accepted_revision": candidate["revision"],
        "campaigns_root": str(campaigns),
        "runtime": {
            "implementation": candidate,
            "images": [worker.image_id, analysis.image_id],
        },
        "paths": {
            "image_manifest": str(tmp_path / "worker.json"),
            "analysis_image_manifest": str(tmp_path / "analysis.json"),
        },
        "gpu_image": str(tmp_path / "gpu.json"),
    }
    calls = []
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(
        installed,
        "candidate_implementation",
        lambda selected: calls.append(("candidate", selected)) or candidate,
        raising=False,
    )
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        lambda revision: calls.append(("accepted", revision)) or accepted,
    )
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: {"worker.json": worker, "gpu.json": gpu}[path.name],
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _: analysis)
    monkeypatch.setattr(research_image, "verify_image", lambda _: None)
    monkeypatch.setattr(
        gpu_practice,
        "gpu_image_backend",
        lambda image: "jax" if image is gpu else None,
    )
    checked_images = []
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kwargs: checked_images.append(kwargs["image_identity"])
        or SimpleNamespace(eligible=True),
    )
    monkeypatch.setattr(miner_network, "binding", lambda **_: "installed-network")
    implementation, parent, network, cache = receiver.installed_source(profile)
    assert (implementation, parent, network) == (candidate, gpu, "installed-network")
    assert cache == campaigns / ".direct-development" / "library-cache"
    assert calls == [("candidate", state)]

    # Normal CPU Review records a present null GPU path. The same pinned base
    # worker is the parent; no unregistered GPU image is admitted by fallback.
    cfg["gpu_image"] = None
    implementation, parent, network, _ = receiver.installed_source(profile)
    assert (implementation, parent, network) == (
        candidate,
        worker,
        "installed-network",
    )
    assert checked_images[-1] is worker
    del cfg["gpu_image"]
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (candidate, worker)
    cfg["runtime"]["gpu_research"] = ["declared"]
    with pytest.raises(ValueError, match="installed GPU parent required"):
        receiver.installed_source(profile)
    del cfg["runtime"]["gpu_research"]
    cfg["gpu_image"] = 7
    with pytest.raises(ValueError, match="installed GPU parent required"):
        receiver.installed_source(profile)
    calls[:] = [("candidate", state)]
    cfg["gpu_image"] = str(tmp_path / "gpu.json")

    # The source-matched CPU worker is not a registered direct GPU parent.
    monkeypatch.setattr(gpu_practice, "gpu_image_backend", lambda _: None)
    with pytest.raises(ValueError, match="direct parent backend is unregistered"):
        receiver.installed_source(profile)
    monkeypatch.setattr(
        gpu_practice,
        "gpu_image_backend",
        lambda image: "jax" if image is gpu else None,
    )

    # A present but invalid candidate pin cannot silently use accepted main.
    def invalid_candidate(_):
        raise ValueError("development candidate record differs")

    monkeypatch.setattr(installed, "candidate_implementation", invalid_candidate)
    with pytest.raises(ValueError, match="candidate record differs"):
        receiver.installed_source(profile)
    assert calls == [("candidate", state)] * 2

    monkeypatch.setattr(installed, "candidate_implementation", lambda _: candidate)
    cfg["runtime"]["implementation"] = accepted
    with pytest.raises(ValueError, match="candidate profile differs"):
        receiver.installed_source(profile)
    cfg["runtime"]["implementation"] = candidate
    cfg["runtime"]["images"] = [worker.image_id, gpu.image_id]
    with pytest.raises(ValueError, match="candidate installed images differ"):
        receiver.installed_source(profile)

    # An exact installed profile with no candidate pin remains main-only.
    cfg["accepted_revision"] = accepted["revision"]
    cfg["runtime"]["implementation"] = accepted
    cfg["runtime"]["images"] = [worker.image_id, analysis.image_id]
    gpu.source_tree_digest = accepted["source_tree_digest"]
    monkeypatch.setattr(installed, "candidate_implementation", lambda _: None)
    cfg["gpu_image"] = None
    with pytest.raises(ValueError, match="installed GPU parent required"):
        receiver.installed_source(profile)
    cfg["gpu_image"] = str(tmp_path / "gpu.json")
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, gpu)
    assert calls[-1] == ("accepted", accepted["revision"])

    # The signed v1.3 receiver accepts an older Torch image only when its
    # registered lock, entrypoint and build recipe match the current ABI.
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    root = Path(receiver.__file__).resolve().parents[2]
    older_torch = WorkerImageIdentity(
        "sha256:" + "3" * 64,
        "sha256:" + "3" * 64,
        "sha256:" + "4" * 64,
        "sha256:" + "5" * 64,
        torch_profile.GPU_LOCK_DIGEST,
        "sha256:" + "6" * 64,
        "sha256:"
        + hashlib.sha256(
            (root / ".devcontainer/torch/Dockerfile.gpu").read_bytes()
        ).hexdigest(),
        "sha256:"
        + hashlib.sha256(
            (root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
        ).hexdigest(),
    )
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else older_torch,
    )
    monkeypatch.setattr(
        gpu_practice,
        "gpu_image_backend",
        lambda image: "pytorch" if type(image) is WorkerImageIdentity else None,
    )
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, older_torch)
    wrong_torch = replace(older_torch, entrypoint_digest="sha256:" + "f" * 64)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else wrong_torch,
    )
    with pytest.raises(ValueError, match="ABI or entrypoint differs"):
        receiver.installed_source(profile)

    # The distinct Torch CPU lock selects the existing CPU Torch image, not
    # the generic C-03 CPU parent or either CUDA backend.
    older_torch_cpu = replace(
        older_torch,
        lock_digest=torch_profile.requirements_digest(root),
        build_recipe_digest="sha256:"
        + hashlib.sha256(
            (root / ".devcontainer/torch/Dockerfile").read_bytes()
        ).hexdigest(),
    )
    monkeypatch.setattr(gpu_practice, "gpu_image_backend", lambda _: None)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else older_torch_cpu,
    )
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, older_torch_cpu)
    assert checked_images[-1] is older_torch_cpu
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: (
            worker
            if path.name == "worker.json"
            else replace(older_torch_cpu, build_recipe_digest="sha256:" + "f" * 64)
        ),
    )
    with pytest.raises(ValueError, match="ABI or entrypoint differs"):
        receiver.installed_source(profile)

    # install_miner.sh --pytorch records the Torch CPU image as the primary
    # worker paired with its analysis image; no GPU profile field is present.
    primary_torch_cpu = replace(
        older_torch_cpu, source_tree_digest=accepted["source_tree_digest"]
    )
    cfg["gpu_image"] = None
    cfg["runtime"]["images"] = [primary_torch_cpu.image_id, analysis.image_id]
    analysis.parent_image = primary_torch_cpu.image_id
    monkeypatch.setattr(
        docker_runtime, "load_image_identity", lambda _: primary_torch_cpu
    )
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, primary_torch_cpu)
    assert checked_images[-1] is primary_torch_cpu
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda _: replace(primary_torch_cpu, build_recipe_digest="sha256:" + "f" * 64),
    )
    with pytest.raises(ValueError, match="ABI or entrypoint differs"):
        receiver.installed_source(profile)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda _: replace(
            primary_torch_cpu, source_tree_digest=candidate["source_tree_digest"]
        ),
    )
    with pytest.raises(ValueError, match="exact accepted source revision"):
        receiver.installed_source(profile)
    cfg["gpu_image"] = str(tmp_path / "gpu.json")
    cfg["runtime"]["images"] = [worker.image_id, analysis.image_id]
    analysis.parent_image = worker.image_id

    from carbon.reconstruction.accelerators import GPU_PROFILE

    older_jax = replace(
        older_torch,
        lock_digest=GPU_PROFILE.environment_lock_digest,
        build_recipe_digest="sha256:"
        + hashlib.sha256(
            (root / ".devcontainer/accelerators/Dockerfile").read_bytes()
        ).hexdigest(),
    )
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else older_jax,
    )
    monkeypatch.setattr(
        gpu_practice,
        "gpu_image_backend",
        lambda image: "jax" if type(image) is WorkerImageIdentity else None,
    )
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, older_jax)
    wrong_jax = replace(older_jax, build_recipe_digest="sha256:" + "f" * 64)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else wrong_jax,
    )
    with pytest.raises(ValueError, match="ABI or entrypoint differs"):
        receiver.installed_source(profile)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else older_torch,
    )
    monkeypatch.setattr(
        gpu_practice,
        "gpu_image_backend",
        lambda image: "pytorch" if type(image) is WorkerImageIdentity else None,
    )

    # A private receiver may pin the older Torch constructor for a candidate
    # CPU setup, while retaining the separately verified CPU inference image.
    torch_manifest = tmp_path / "torch.json"
    torch_manifest.write_text("{}")
    cfg["accepted_revision"] = candidate["revision"]
    cfg["runtime"]["implementation"] = candidate
    cfg["gpu_image"] = None
    monkeypatch.setattr(installed, "candidate_implementation", lambda _: candidate)
    implementation, parent, _, _ = receiver.installed_source(
        profile, construction_image_manifest=torch_manifest
    )
    assert (implementation, parent) == (candidate, older_torch)
    assert checked_images[-1] is older_torch
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **_: SimpleNamespace(eligible=False),
    )
    with pytest.raises(receiver.ReceiverUnavailable, match="worker_unavailable"):
        receiver.installed_source(profile, construction_image_manifest=torch_manifest)
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kwargs: checked_images.append(kwargs["image_identity"])
        or SimpleNamespace(eligible=True),
    )
    cfg["gpu_image"] = str(tmp_path / "other-gpu.json")
    with pytest.raises(ValueError, match="conflicts with profile"):
        receiver.installed_source(profile, construction_image_manifest=torch_manifest)
    cfg["gpu_image"] = None
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else wrong_torch,
    )
    with pytest.raises(ValueError, match="ABI or entrypoint differs"):
        receiver.installed_source(profile, construction_image_manifest=torch_manifest)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: worker if path.name == "worker.json" else older_torch,
    )
    monkeypatch.setattr(installed, "candidate_implementation", lambda _: None)
    cfg["accepted_revision"] = accepted["revision"]
    cfg["runtime"]["implementation"] = accepted
    worker.source_tree_digest = accepted["source_tree_digest"]
    implementation, parent, _, _ = receiver.installed_source(
        profile, construction_image_manifest=torch_manifest
    )
    assert (implementation, parent) == (accepted, older_torch)
    assert checked_images[-1] is older_torch
    worker.source_tree_digest = candidate["source_tree_digest"]
    with pytest.raises(ValueError, match="exact accepted source revision"):
        receiver.installed_source(profile, construction_image_manifest=torch_manifest)
    worker.source_tree_digest = accepted["source_tree_digest"]

    # A profile outside the exact installed state path never reads the pin.
    cfg["gpu_image"] = str(tmp_path / "gpu.json")
    monkeypatch.setattr(installed, "candidate_implementation", invalid_candidate)
    regular = tmp_path / "other-profile.json"
    implementation, parent, _, _ = receiver.installed_source(regular)
    assert (implementation, parent) == (accepted, older_torch)
    assert calls[-1] == ("accepted", accepted["revision"])


def test_serve_forwards_only_private_constructor_manifest(tmp_path, monkeypatch):
    _allow_windows_receiver_fixture(monkeypatch)
    manifest = tmp_path / "torch.json"
    manifest.write_text("{}")
    cfg = {**_config(tmp_path), "construction_image_manifest": str(manifest)}
    monkeypatch.setattr(receiver, "load_config", lambda _: cfg)

    class Seen(Exception):
        pass

    def installed(profile, **kwargs):
        assert profile == Path(cfg["runner_profile"])
        assert kwargs == {"construction_image_manifest": manifest}
        raise Seen

    monkeypatch.setattr(receiver, "installed_source", installed)
    with pytest.raises(Seen):
        receiver.serve(tmp_path / "config.json")


@pytest.mark.parametrize(
    "inference_backend,accepted",
    (
        ("jax_gpu", True),
        ("cpu", True),
        ("torch_cpu", True),
        ("torch_cpu_bad", False),
        ("torch_cpu_main", True),
        ("torch_cpu_main_bad_abi", False),
        ("torch_cpu_main_stale", False),
        ("jax_bad", False),
        ("torch_gpu", False),
        ("unknown", False),
    ),
)
def test_selected_inference_image_admits_only_compatible_jax_or_cpu(
    tmp_path, monkeypatch, inference_backend, accepted
):
    _allow_windows_receiver_fixture(monkeypatch)
    from carbon.development_session import research_campaign
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker import docker_runtime
    from carbon.reconstruction.worker.model import WorkerImageIdentity
    from scripts.dev.miner_launchpad import runner

    def sha(char):
        return "sha256:" + char * 64

    repo = Path(receiver.__file__).resolve().parents[2]

    def image(lock, recipe):
        return WorkerImageIdentity(
            sha("1"),
            sha("1"),
            sha("2"),
            sha("3"),
            lock,
            sha("4"),
            research_campaign.digest((repo / recipe).read_bytes()),
            research_campaign.digest(
                (repo / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
            ),
        )

    jax = image(
        GPU_PROFILE.environment_lock_digest,
        ".devcontainer/accelerators/Dockerfile",
    )
    cpu = image(
        research_campaign.digest((repo / "uv.lock").read_bytes()),
        ".devcontainer/Dockerfile.reconstruction-worker",
    )
    torch = image(torch_profile.GPU_LOCK_DIGEST, ".devcontainer/torch/Dockerfile.gpu")
    torch_cpu = image(
        torch_profile.requirements_digest(repo), ".devcontainer/torch/Dockerfile"
    )
    jax_bad = replace(jax, entrypoint_digest=sha("e"))
    unknown = replace(cpu, lock_digest=sha("e"), source_tree_digest=sha("f"))
    selected = {
        "jax_gpu": jax,
        "cpu": cpu,
        "torch_cpu": torch_cpu,
        "torch_cpu_bad": replace(torch_cpu, build_recipe_digest=sha("e")),
        "torch_cpu_main": replace(torch_cpu, source_tree_digest=sha("f")),
        "torch_cpu_main_bad_abi": replace(
            torch_cpu, source_tree_digest=sha("f"), build_recipe_digest=sha("e")
        ),
        "torch_cpu_main_stale": torch_cpu,
        "jax_bad": jax_bad,
        "torch_gpu": torch,
        "unknown": unknown,
    }[inference_backend]
    cfg = {
        **_config(tmp_path),
        "inference_image_manifest": str(tmp_path / "selected.json"),
        "material_cache_bytes": 1024,
    }
    implementation = {
        "source_tree_digest": sha("f"),
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    if inference_backend.startswith("torch_cpu_main"):
        del implementation["source_authority"]
    monkeypatch.setattr(receiver, "load_config", lambda _: cfg)
    monkeypatch.setattr(
        receiver,
        "installed_source",
        lambda *_args, **_kwargs: (implementation, jax, None, tmp_path),
    )
    monkeypatch.setattr(receiver, "private_json", lambda _: {})
    monkeypatch.setattr(
        runner, "validated_profile", lambda _: {"paths": {"image_manifest": "cpu.json"}}
    )
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda _: selected)

    class ReachedDoctor(Exception):
        pass

    def doctor(**kwargs):
        assert kwargs["image_identity"] is selected
        raise ReachedDoctor

    monkeypatch.setattr(docker_runtime, "doctor", doctor)
    if accepted:
        with pytest.raises(ReachedDoctor):
            receiver.serve(tmp_path / "config.json")
    else:
        with pytest.raises(ValueError):
            receiver.serve(tmp_path / "config.json")


def test_main_uses_process_stop_and_closed_failure_without_private_text(
    tmp_path, monkeypatch, capsys
):
    def fail(*args, **kwargs):
        assert isinstance(kwargs["stop"], threading.Event)
        raise ValueError("PRIVATE PATH MUST NOT APPEAR")

    monkeypatch.setattr(receiver, "serve", fail)
    monkeypatch.setattr(receiver.signal, "signal", lambda *_: None)
    assert receiver.main(["--config", str(tmp_path / "config.json")]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "direct_receiver_unavailable"
    }


def test_main_one_shot_retention_uses_operator_paths_and_reports_only_bank_status(
    tmp_path, monkeypatch, capsys
):
    task_id = "rtsk_" + "a" * 64
    artifacts = tmp_path / "private-artifacts"
    entries = tmp_path / "private-entries"
    calls = []

    def retain(config, **kwargs):
        calls.append((config, kwargs["retention"]))
        assert isinstance(kwargs["stop"], threading.Event)
        return {
            "status": "CREATED" if len(calls) == 1 else "ALREADY_PRESENT_IDENTICAL",
            "entry_id": "entry-verified",
            "score_state": "NOT_COMPUTED",
            "official_eligible": False,
        }

    monkeypatch.setattr(receiver, "serve", retain)
    monkeypatch.setattr(receiver.signal, "signal", lambda *_: None)
    argv = [
        "--config",
        str(tmp_path / "config.json"),
        "--retain-task",
        task_id,
        "--artifact-directory",
        str(artifacts),
        "--entry-directory",
        str(entries),
    ]
    for expected in ("CREATED", "ALREADY_PRESENT_IDENTICAL"):
        assert receiver.main(argv) == 0
        reported = json.loads(capsys.readouterr().out)
        assert reported == {
            "schema": receiver.SCHEMA,
            "state": "RETAINED",
            "status": expected,
            "entry_id": "entry-verified",
            "score_state": "NOT_COMPUTED",
            "official_eligible": False,
        }
    assert calls == [(tmp_path / "config.json", (task_id, artifacts, entries))] * 2


@pytest.mark.parametrize(
    "measurement_state,expected_code",
    (("DEVELOPMENT_UNRANKED", 0), ("UNAVAILABLE", 0), ({"raw": "secret"}, 1)),
)
def test_operator_retention_reports_only_closed_optional_measurement_state(
    tmp_path, monkeypatch, capsys, measurement_state, expected_code
):
    monkeypatch.setattr(
        receiver,
        "serve",
        lambda *_args, **_kwargs: {
            "status": "CREATED",
            "entry_id": "entry-verified",
            "score_state": "NOT_COMPUTED",
            "official_eligible": False,
            "measurement_state": measurement_state,
            "sidecar": {"raw": "secret"},
        },
    )
    monkeypatch.setattr(receiver.signal, "signal", lambda *_: None)
    code = receiver.main(
        [
            "--config",
            str(tmp_path / "config.json"),
            "--retain-task",
            "rtsk_" + "a" * 64,
            "--artifact-directory",
            str(tmp_path / "artifacts"),
            "--entry-directory",
            str(tmp_path / "entries"),
        ]
    )
    assert code == expected_code
    reported = json.loads(capsys.readouterr().out)
    assert "secret" not in json.dumps(reported)
    if expected_code == 0:
        assert reported["measurement_state"] == measurement_state
        assert reported["score_state"] == "NOT_COMPUTED"
    else:
        assert reported == {"unavailable": "direct_receiver_unavailable"}


@pytest.mark.parametrize("reason", ["owned_task_unavailable", "task_not_succeeded"])
def test_main_one_shot_retention_reports_only_closed_refusal(
    tmp_path, monkeypatch, capsys, reason
):
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    def refused(*_args, **_kwargs):
        raise RetentionUnavailable(reason)

    monkeypatch.setattr(receiver, "serve", refused)
    monkeypatch.setattr(receiver.signal, "signal", lambda *_: None)
    assert (
        receiver.main(
            [
                "--config",
                str(tmp_path / "config.json"),
                "--retain-task",
                "rtsk_" + "a" * 64,
                "--artifact-directory",
                str(tmp_path / "artifacts"),
                "--entry-directory",
                str(tmp_path / "entries"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {"unavailable": reason}


def test_shutdown_refuses_to_release_unreconciled_provider_lock(tmp_path):
    calls = []
    provider = SimpleNamespace(
        _views={"task": SimpleNamespace(task_id="task")},
        requires_reconciliation=lambda _: True,
        close=lambda: calls.append("CLOSED"),
    )
    pool = receiver.OwnerProviders(tmp_path, None, None, None)
    pool._providers[OWNER] = provider
    with pytest.raises(receiver.ReceiverUnavailable, match="cleanup_unresolved"):
        pool.close()
    assert calls == []


@POSIX
def test_owner_provider_restart_shares_exact_ledger_and_refuses_work_during_stop(
    tmp_path,
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    inference_image = WorkerImageIdentity(*("sha256:" + "5" * 64 for _ in range(8)))
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    authority = {
        "implementation": {"revision": "a" * 40},
        "snapshot": snapshot,
        "receiver": RECEIVER,
    }
    root = receiver._private_directory(tmp_path / "owners")
    pool = receiver.OwnerProviders(
        root,
        discovery,
        parent,
        tmp_path / "cache",
        inference_image=inference_image,
        **authority,
    )
    one, two = pool(OWNER), pool(OTHER)
    assert pool(OWNER) is one
    assert one.discovery is two.discovery is discovery
    assert one.owner == OWNER and two.owner == OTHER
    assert one.construction_parent == parent
    assert one.inference_image == inference_image
    with one.ledger.db() as db:
        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["runtime"]["images"] == [parent.image_id, inference_image.image_id]
    assert frozen["receiver_binding"]["inference_image"] == inference_image.image_id
    assert one.ledger.root != two.ledger.root
    first_root = one.ledger.root
    pool.cancel()
    with pytest.raises(Unavailable, match="direct_receiver_stopping"):
        pool(OWNER)
    pool.close()
    restarted = receiver.OwnerProviders(
        root,
        discovery,
        parent,
        tmp_path / "cache",
        inference_image=inference_image,
        **authority,
    )
    restarted.restore()
    assert restarted(OWNER).ledger.root == first_root
    assert len(restarted._providers) == 2
    restarted.cancel()
    restarted.close()


def test_first_direct_child_reserves_under_frozen_registered_owner_and_reopens(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot
    from test_direct_v3_durable_tasks import _fixture

    from carbon import research
    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session import research_carrier
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    _allow_windows_receiver_fixture(monkeypatch)
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    implementation = {"revision": "a" * 40}
    root = receiver._private_directory(tmp_path / "owners")

    def pool(observed):
        return receiver.OwnerProviders(
            root,
            discovery,
            parent,
            tmp_path / "cache",
            implementation=implementation,
            snapshot=observed,
            receiver=RECEIVER,
        )

    first = pool(snapshot)
    provider = first(OWNER)
    ledger = provider.ledger
    with ledger.db() as db:
        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["schema"] == "carbon.launchpad.campaign.v1"
    assert frozen["scope"] == "DEVELOPMENT_PUBLIC_SYNTHETIC_ONLY"
    assert frozen["owner"] == OWNER
    assert frozen["admission"]["hotkey"] == OWNER
    assert frozen["admission"]["snapshot_id"] == snapshot.snapshot_id
    assert "ceilings" not in frozen and "grant" not in frozen

    from carbon.battery.construction_bundle_material import (
        bundle_material as battery_material,
    )
    from carbon.development_session.research_ledger import CampaignLedger

    battery_discovery = DirectFixtureDiscovery(battery_material(), task_admission=True)
    battery_pool = receiver.OwnerProviders(
        receiver._private_directory(tmp_path / "battery-owners"),
        battery_discovery,
        parent,
        tmp_path / "cache",
        implementation=implementation,
        snapshot=snapshot,
        receiver=RECEIVER,
    )
    battery_ledger = CampaignLedger(tmp_path / "battery-ledger")
    battery_pool._manifest(OWNER, battery_ledger, restoring=False)
    with battery_ledger.db() as db:
        battery_frozen = json.loads(
            db.execute("SELECT manifest FROM campaign").fetchone()[0]
        )
    assert battery_frozen["scope"] == "DEVELOPMENT_PUBLIC_BATTERY_ONLY"
    assert battery_frozen["objective"] == (
        "Battery public direct construction and practice inference"
    )

    # The real C-03 carrier reaches ledger.reserve before host inspection.
    # A deliberately unavailable host settles FAILED_INFRA; no container or
    # candidate program is launched and no scientific outcome is inferred.
    monkeypatch.setattr(research_carrier, "DockerCLI", object)
    monkeypatch.setattr(
        research_carrier,
        "doctor",
        lambda **_: SimpleNamespace(eligible=False),
    )
    with pytest.raises(ValueError, match="research host ineligible"):
        research_carrier._run_locked(
            ledger,
            owner=OWNER,
            identity="first-build-child",
            source="pass",
            files={},
            image=parent,
            seconds=40,
            provenance="DIRECT_GRAPH_PUBLIC_RECONSTRUCTION",
            extra_resources={},
        )
    assert ledger.operation_state("first-build-child", owner=OWNER) == "FAILED_INFRA"
    with pytest.raises(ValueError, match="authenticated campaign owner differs"):
        ledger.reserve(
            "second-owner-child",
            owner=OTHER,
            phase="research",
            request={"kind": "direct"},
            resources={},
        )
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 1
    request, fixed_factory, _ = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    fixed = fixed_factory()
    image = fixed.image
    fixed.close()
    inspected = []

    def inspect_source(self, bundle):
        assert bundle.to_dict() == image.bundle_ref
        inspected.append(bundle.to_dict())
        return bundle

    monkeypatch.setattr(DirectOwnerImageResolver, "inspect_source", inspect_source)
    monkeypatch.setattr(
        DirectOwnerImageResolver,
        "__call__",
        lambda *_: pytest.fail("queued source must not resolve an image"),
    )
    monkeypatch.setattr(
        DirectOwnerImageResolver,
        "provision_admitted",
        lambda *_args, **_kwargs: pytest.fail("queue/restart must not provision"),
    )
    queued = provider.start_research_task(request).task
    assert queued.state is research.DirectTaskStateV3.QUEUED
    assert inspected == [image.bundle_ref]
    first.close()

    advanced = replace(
        snapshot,
        finalized_block=snapshot.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=snapshot.timestamp_ms + 1000,
    )
    resumed = pool(advanced)
    resumed.restore()
    assert resumed(OWNER).ledger.generation > ledger.generation
    assert resumed(OWNER).queued_tasks() == (queued.task_id,)
    with resumed(OWNER).ledger.db() as db:
        retained = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert retained == frozen
    resumed.close()

    recycled = replace(
        advanced,
        participants=(
            advanced.participants[0],
            Participant(1, OWNER, "cold", 3),
            advanced.participants[2],
        ),
    )
    cleanup = pool(recycled)
    cleanup.restore()
    assert (
        cleanup._providers[OWNER].ledger.operation_state(
            "first-build-child", owner=OWNER
        )
        == "FAILED_INFRA"
    )
    retained = (
        cleanup._providers[OWNER]
        .get_research_result(
            research.DirectGetTaskRequestV3(
                discovery.info.challenge_key, queued.task_id
            )
        )
        .task
    )
    assert retained.state is research.DirectTaskStateV3.CANCELLED
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        cleanup(OWNER)
    # Revocation of one retained owner does not stop a second registered
    # miner from opening a fresh campaign through the same receiver.
    assert cleanup(OTHER).owner == OTHER
    cleanup.close()


def test_new_owner_uses_refreshed_finalized_snapshot_not_startup_registration(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    _allow_windows_receiver_fixture(monkeypatch)
    from carbon.battery.intake import SnapshotWindow
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    now = time.time()
    startup = replace(
        _snapshot(sender=OTHER, receiver=RECEIVER, context=context),
        timestamp_ms=int(now * 1000),
    )
    window = SnapshotWindow(clock=lambda: now)
    window.add(startup)
    root = receiver._private_directory(tmp_path / "owners")
    pool = receiver.OwnerProviders(
        root,
        DirectFixtureDiscovery(bundle_material_v5(), task_admission=True),
        WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8))),
        tmp_path / "cache",
        implementation={"revision": "a" * 40},
        snapshot=startup,
        window=window,
        receiver=RECEIVER,
    )
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)
    assert list(root.iterdir()) == []
    refreshed = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        finalized_block=startup.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=int(now * 1000) + 1000,
    )
    window.add(refreshed)
    provider = pool(OWNER)
    with provider.ledger.db() as db:
        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["admission"]["snapshot_id"] == refreshed.snapshot_id
    assert frozen["admission"]["registered_at_block"] == 2
    pool.close()


def test_lagged_refresh_cannot_restore_revoked_owner_or_background_dispatch(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    _allow_windows_receiver_fixture(monkeypatch)
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    now = time.time()
    old = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        timestamp_ms=int(now * 1000),
    )
    revoked = replace(
        old,
        finalized_block=old.finalized_block + 2,
        block_hash="0x" + "4" * 64,
        timestamp_ms=int(now * 1000) + 2000,
        participants=tuple(p for p in old.participants if p.hotkey != OWNER),
    )
    lagged = replace(
        old,
        finalized_block=old.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=int(now * 1000) + 1000,
    )
    root = receiver._private_directory(tmp_path / "receiver")
    owners = receiver._private_directory(root / "owners")
    window = receiver.ReceiverSnapshotWindow(root, context, RECEIVER, clock=lambda: now)
    window.add(old)
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    authority = {
        "implementation": {"revision": "a" * 40},
        "snapshot": old,
        "window": window,
        "receiver": RECEIVER,
    }
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    pool = receiver.OwnerProviders(
        owners, discovery, parent, tmp_path / "cache", **authority
    )
    assert pool(OWNER).owner == OWNER
    record = window._record

    def failed_record(*_, **__):
        raise OSError("test-only durable write failure")

    monkeypatch.setattr(window, "_record", failed_record)
    with pytest.raises(OSError, match="durable write failure"):
        window.add(revoked)
    assert window.latest() is None
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)
    monkeypatch.setattr(window, "_record", record)
    window.add(revoked)
    window.add(lagged)
    assert window.latest() == revoked
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)

    # The operator advance loop has no new HTTP request. It still cannot
    # dispatch a retained queued child from the old owner's authority.
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.contract_digest = "sha256:" + "7" * 64
    adapter.ledger = SimpleNamespace(submitted_outcomes=lambda _: ("rtsk_" + "1" * 64,))
    adapter.owner = lambda _: pool(OWNER).owner
    adapter._provider = lambda _: pytest.fail("revoked owner dispatched")
    assert adapter.advance() == 0
    pool.close()

    # Restarting against the lagged read cannot roll back the durable block.
    restarted_window = receiver.ReceiverSnapshotWindow(
        root, context, RECEIVER, clock=lambda: now
    )
    restarted_window.add(lagged)
    assert restarted_window.latest() is None
    restarted = receiver.OwnerProviders(
        owners,
        discovery,
        parent,
        tmp_path / "cache",
        **{**authority, "snapshot": lagged, "window": restarted_window},
    )
    restarted.restore()
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        restarted(OWNER)
    restarted.close()

    # A contradictory identity at the same finalized block fails closed,
    # including after another restart; only a higher block can recover it.
    restarted_window.add(replace(revoked, block_hash="0x" + "5" * 64))
    assert restarted_window.latest() is None
    conflicted = receiver.ReceiverSnapshotWindow(
        root, context, RECEIVER, clock=lambda: now
    )
    conflicted.add(revoked)
    assert conflicted.latest() is None
    recovered = replace(
        revoked,
        finalized_block=revoked.finalized_block + 1,
        block_hash="0x" + "6" * 64,
        timestamp_ms=int(now * 1000) + 3000,
    )
    conflicted.add(recovered)
    assert conflicted.latest() == recovered


@POSIX
def test_real_loopback_bootstrap_stages_and_admits_same_owner_without_model_dispatch(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _headers, _snapshot, _Verifier

    from carbon import research
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_validator import direct_intake
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
    from carbon.level4 import staging, submission
    from carbon.reconstruction.worker.model import WorkerImageIdentity
    from carbon.transport.models import message

    cfg = _config(tmp_path)
    # Port zero is injected after config validation only for this disposable
    # unit fixture. Production requires a fixed configured target port.
    cfg["port"] = 0
    monkeypatch.setattr(receiver, "load_config", lambda _: cfg)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    source_root = Path(receiver.__file__).resolve().parents[2]
    inference_image = WorkerImageIdentity(
        "sha256:" + "5" * 64,
        "sha256:" + "5" * 64,
        "sha256:" + "5" * 64,  # Older source; the fixed C03 program is staged.
        "sha256:" + "5" * 64,
        "sha256:" + hashlib.sha256((source_root / "uv.lock").read_bytes()).hexdigest(),
        "sha256:" + "5" * 64,
        "sha256:"
        + hashlib.sha256(
            (
                source_root / ".devcontainer/Dockerfile.reconstruction-worker"
            ).read_bytes()
        ).hexdigest(),
        "sha256:"
        + hashlib.sha256(
            (source_root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
        ).hexdigest(),
    )
    # This ingress-only fixture supplies the separately read private profile.
    # Profile/image correctness has its own tests; model dispatch remains forbidden.
    from carbon.development_session import research_campaign
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import runner

    profile = {"paths": {"image_manifest": str(tmp_path / "inference-image.json")}}
    profile_path = Path(cfg["runner_profile"])
    profile_path.write_bytes(canonical(profile))
    profile_path.chmod(0o600)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)

    def load_inference(path):
        assert path == Path(profile["paths"]["image_manifest"])
        return inference_image

    monkeypatch.setattr(docker_runtime, "load_image_identity", load_inference)
    checked = []
    verify_exact_source = research_campaign.verify_current_worker

    def check_source(image, implementation):
        checked.append((image, implementation))
        verify_exact_source(image, implementation)

    monkeypatch.setattr(research_campaign, "verify_current_worker", check_source)
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kwargs: SimpleNamespace(
            eligible=kwargs["image_identity"] == inference_image
        ),
    )
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    monkeypatch.setattr(
        receiver,
        "installed_source",
        lambda _: (
            {"revision": "a" * 40, "source_tree_digest": "sha256:" + "6" * 64},
            parent,
            SimpleNamespace(context=context, publisher_hotkey=RECEIVER),
            tmp_path / "cache",
        ),
    )
    now = time.time_ns()
    snapshot = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        timestamp_ms=now // 1_000_000,
    )
    reader = SimpleNamespace()

    async def capture(observed_context):
        assert observed_context == context
        return snapshot

    reader.capture = capture
    dispatched = []

    def forbidden(*_):
        dispatched.append(True)
        raise AssertionError("this fixture must not dispatch a model")

    monkeypatch.setattr(DirectDevelopmentTasksV3, "run_queued_task", forbidden)
    # This fixture checks ingress and custody, not execution. A slow CI host
    # must not turn the queued-task assertion into a model dispatch.
    monkeypatch.setattr(direct_intake, "_advance_loop", lambda *args: args[1].wait())
    stop, retained = threading.Event(), {}

    def ready(facts):
        target = facts["direct_intake_target"]
        assert target["receiver_hotkey"] == RECEIVER
        with urllib.request.urlopen(
            target["intake_url"] + direct_intake.INFO_PATH
        ) as stream:
            public = json.load(stream)
        assert public["challenge"] == {
            "id": "synthetic-linear-field-2d",
            "version": "1.3",
        }
        assert public["score_pack"] is None
        key = research.ChallengeKey(public["challenge"]["id"], "1.3")
        document = b'{"untrusted":"inert fixture source"}'
        fingerprint = submission.name(document)
        manifest = canonical({"documents": {"forward": fingerprint}})
        nonce = time.time_ns()

        def post(tool, fields, number):
            body = message(
                context,
                public["snapshot"]["id"],
                key,
                session="bootstrap-fixture",
                request=f"bootstrap-call-{number:04}",
                tool=tool,
                fields=fields,
            )
            request = urllib.request.Request(
                target["intake_url"] + direct_intake.SUBMIT_PATH,
                data=body,
                headers={
                    **_headers(body, nonce + number, hotkey=OWNER),
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request) as stream:
                return json.load(stream)

        for index, (name, raw) in enumerate(
            (
                (staging.WORKSPACE_PREFIX + fingerprint[7:] + ".json", document),
                (staging.WORKSPACE_MANIFEST, manifest),
            ),
            1,
        ):
            call = research.ServiceCall(
                research.RESEARCH_NAMESPACE,
                "stage_research_source",
                research.DirectStageSourceRequestV1(
                    key, name, 0, len(raw), submission.name(raw), None, raw
                ),
            )
            reply = post(
                research.RESEARCH_NAMESPACE,
                {
                    "call_base64": base64.b64encode(
                        research.canonical_bytes(call)
                    ).decode()
                },
                index,
            )
            assert reply["schema"] == direct_intake.SOURCE_REPLY_SCHEMA

        from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

        kit = bundle_material_v5()["construction_kit"]
        recipe = {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": submission.name(manifest)},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
        admitted = post(
            direct_intake.SUBMIT_TOOL,
            {
                "strategy_json": json.dumps(recipe),
                "contract_digest": public["served_contracts"][0]["digest"],
            },
            3,
        )
        assert admitted["outcome"]["state"] == "ADMITTED"
        retained["task"] = admitted["outcome"]["task_id"]
        stop.set()

    class Verifier(_Verifier):
        def verify(self, headers, *args, **kwargs):
            return super().verify(
                {key.lower(): value for key, value in headers.items()},
                *args,
                **kwargs,
            )

    receiver.serve(
        tmp_path / "config.json",
        stop=stop,
        reader=reader,
        verifier=Verifier(),
        ready=ready,
    )
    assert retained["task"] and not dispatched
    assert checked and all(image == inference_image for image, _ in checked)
    bound = json.loads((Path(cfg["root"]) / "receiver-binding.json").read_bytes())
    assert bound["parent"]["image_id"] == parent.image_id
    assert bound["inference_image"]["image_id"] == inference_image.image_id
    owner_root = (
        Path(cfg["root"]) / "owners" / hashlib.sha256(OWNER.encode()).hexdigest()
    )
    assert (owner_root / "tasks" / "direct-tasks.sqlite3").is_file()
    assert (owner_root / "ledger" / "campaign.sqlite3").is_file()
    with sqlite3.connect(owner_root / "tasks" / "direct-tasks.sqlite3") as db:
        assert db.execute(
            "SELECT profile FROM direct_task_measurements"
        ).fetchall() == [("COLD_QUERY_V2",)]
        view = research.load_canonical(
            db.execute("SELECT view FROM direct_tasks").fetchone()[0],
            research.DirectTaskViewV3,
        )
        assert view.state is research.DirectTaskStateV3.CANCELLED

    # Reopen the signed task under the same receiver identity without
    # listening, dispatching, or cancelling any retained work. A cancelled
    # task and an unowned identity cannot enter the existing bank.
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    artifacts, entries = tmp_path / "bank-artifacts", tmp_path / "bank-entries"
    artifacts.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)
    with monkeypatch.context() as one_shot:
        one_shot.setattr(
            direct_intake,
            "serve_loopback",
            lambda *_args, **_kwargs: pytest.fail("listener started"),
        )
        one_shot.setattr(
            receiver.OwnerProviders,
            "cancel",
            lambda self: pytest.fail("retention cancelled unrelated work"),
        )
        one_shot.setattr(
            receiver.OwnerProviders,
            "restore",
            lambda self: pytest.fail("retention restored every owner"),
        )
        one_shot.setattr(
            DirectDevelopmentTasksV3,
            "cancel_observed_task",
            lambda *_args, **_kwargs: pytest.fail("retention cancelled a queued task"),
        )
        with pytest.raises(RetentionUnavailable, match="task_not_succeeded"):
            receiver.serve(
                tmp_path / "config.json",
                reader=reader,
                verifier=Verifier(),
                retention=(retained["task"], artifacts, entries),
            )
        with pytest.raises(RetentionUnavailable, match="owned_task_unavailable"):
            receiver.serve(
                tmp_path / "config.json",
                reader=reader,
                verifier=Verifier(),
                retention=("rtsk_" + "0" * 64, artifacts, entries),
            )
    assert not list(artifacts.iterdir())
    assert not list(entries.iterdir())


@POSIX
def test_listener_cancels_before_waiting_and_does_not_return_with_worker_active(
    monkeypatch,
):
    from carbon.challenge_validator import direct_intake

    stop, started, release, finished = (threading.Event() for _ in range(4))
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()

    def advance(*_):
        started.set()
        assert release.wait(5)
        finished.set()

    def closing():
        assert started.is_set()
        assert not finished.is_set()
        release.set()

    def ready(_):
        assert started.wait(5)
        stop.set()

    monkeypatch.setattr(direct_intake, "_advance_loop", advance)
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    direct_intake.serve_loopback(
        intake,
        {"host": "127.0.0.1", "port": 0},
        stop=stop,
        ready=ready,
        closing=closing,
    )
    assert finished.is_set()


@POSIX
def test_failed_readiness_stops_worker_before_return(monkeypatch):
    from carbon.challenge_validator import direct_intake

    stop, finished = threading.Event(), threading.Event()
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()

    def advance(*_):
        stop.wait()
        finished.set()

    def ready(_):
        raise ValueError("readiness refused")

    monkeypatch.setattr(direct_intake, "_advance_loop", advance)
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    with pytest.raises(ValueError, match="readiness refused"):
        direct_intake.serve_loopback(
            intake, {"host": "127.0.0.1", "port": 0}, stop=stop, ready=ready
        )
    assert stop.is_set() and finished.is_set()


@POSIX
def test_incomplete_headers_cannot_hold_graceful_shutdown(monkeypatch):
    from carbon.challenge_validator import direct_intake

    stop = threading.Event()
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()
    monkeypatch.setattr(direct_intake, "SOCKET_TIMEOUT_S", 0.1)
    monkeypatch.setattr(direct_intake, "_advance_loop", lambda *a: stop.wait())
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    clients = []

    def ready(address):
        connection = socket.create_connection(address, timeout=2)
        clients.append(connection)
        connection.sendall(b"GET / HTTP/1.1\r\nX-Incomplete:")
        stop.set()

    started = time.monotonic()
    try:
        direct_intake.serve_loopback(
            intake, {"host": "127.0.0.1", "port": 0}, stop=stop, ready=ready
        )
        assert time.monotonic() - started < 3
        try:
            closed = clients[0].recv(1)
        except ConnectionResetError:
            closed = b""
        assert closed == b""
    finally:
        for client in clients:
            client.close()
