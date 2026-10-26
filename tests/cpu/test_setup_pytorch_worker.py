"""A Challenge version built on the PyTorch CPU worker is named at setup.

M1 rehearsal, 2026-10-21: an install made without --pytorch reached a Motor
1.3 launch, which its campaign refused ("motor catalog practice needs the
PyTorch CPU worker image"). The torch-cpu execution profiles now require the
PyTorch CPU worker as a host fact; setup's compute check names the worker's
CPU parent, and the compute check and Review both say which Challenge
versions need --pytorch, before any launch.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_miner_launchpad_environment_setup import (
    RUNTIME,
    Checks,
    Onboarding,
    completed,
)

from carbon.challenge_registry import HostFacts, catalog
from carbon.challenge_registry.registry import IMPLEMENTED, TORCH_CPU_WORKER
from scripts.dev.miner_launchpad.environment_setup import (
    PYTORCH_STEP,
    EnvironmentSetup,
    torch_challenges,
)

TORCH = {
    ("electric-motor-magnetics", "1.2"),
    ("electric-motor-magnetics", "1.3"),
    ("chip-cold-plate", "1.2"),
    ("chip-cold-plate", "1.3"),
    ("f08-ribbed-bracket", "1.4"),
    ("f02", "2.3"),
    # Graph route v2: each is its predecessor plus the graph adapter, and
    # practises on the same workers.
    ("electric-motor-magnetics", "1.4"),
    ("chip-cold-plate", "1.4"),
    ("f08-ribbed-bracket", "1.5"),
    ("f02", "2.4"),
}


def _implemented():
    return {
        (entry["challenge_id"], entry["version"]): entry
        for entry in catalog()["challenges"]
        if entry["status"] == IMPLEMENTED
    }


def test_only_the_torch_cpu_profiles_require_the_pytorch_worker():
    implemented = _implemented()
    assert TORCH <= set(implemented)
    for key, entry in implemented.items():
        for profile in entry["profiles"]:
            required = TORCH_CPU_WORKER in profile["requirements"]
            # The shared GPU profile (S3) builds on the PyTorch CPU worker too.
            assert required == (
                profile["backend"]
                in ("torch-cpu/isolated-carrier", "torch-cuda/isolated-carrier")
            )
        torch = any(p["backend"].startswith("torch-cpu") for p in entry["profiles"])
        assert torch == (key in TORCH), key
    assert {(c["id"], c["version"]) for c in torch_challenges()} == TORCH


def test_without_the_pytorch_worker_a_torch_version_is_not_usable_here():
    host = HostFacts(frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"}))
    for entry in catalog(host)["challenges"]:
        key = (entry["challenge_id"], entry["version"])
        if key not in TORCH:
            continue
        cpu = [p for p in entry["profiles"] if p["profile"] == "cpu_research"]
        assert cpu and not cpu[0]["usable_here"], key
        assert TORCH_CPU_WORKER in cpu[0]["missing_here"], key
    with_torch = HostFacts(host.facts | {TORCH_CPU_WORKER})
    for entry in catalog(with_torch)["challenges"]:
        if (entry["challenge_id"], entry["version"]) in TORCH:
            cpu = [p for p in entry["profiles"] if p["profile"] == "cpu_research"]
            assert TORCH_CPU_WORKER not in cpu[0]["missing_here"]


@pytest.mark.parametrize("backend, expected", [("torch_cpu", True), (None, False)])
def test_the_configured_worker_counts_as_pytorch_only_when_it_is(
    monkeypatch, backend, expected
):
    from carbon.development_session import gpu_practice
    from carbon.miner_mcp.mcp_challenges import configured_host_facts
    from carbon.reconstruction.worker import docker_runtime

    image = SimpleNamespace(image_id="sha256:" + "d" * 64)
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: image)
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **kw: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(gpu_practice, "direct_parent_backend", lambda found: backend)
    facts = configured_host_facts({"paths": {"image_manifest": "/w.json"}}).facts
    assert "trusted_worker_image" in facts
    assert (TORCH_CPU_WORKER in facts) is expected


def test_a_runner_profile_s_string_manifest_path_reaches_the_loader_as_a_path(
    monkeypatch,
):
    """Test Runner 03:20Z: configured_host_facts passed the profile's STRING path to a loader
    that reads `path.read_text`, the AttributeError was swallowed, and no host whose profile came
    from JSON ever reported a trusted worker image (every agent was told the Challenge was
    unusable here). The loader now gets a Path, like the real one needs."""
    from pathlib import Path

    from carbon.development_session import gpu_practice
    from carbon.miner_mcp.mcp_challenges import configured_host_facts
    from carbon.reconstruction.worker import docker_runtime

    seen = []

    def strict_loader(path):
        seen.append(path)
        path.read_text  # noqa: B018 - a str has no read_text, as the real loader needs
        return SimpleNamespace(image_id="sha256:" + "d" * 64)

    monkeypatch.setattr(docker_runtime, "load_image_identity", strict_loader)
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **kw: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(
        gpu_practice, "direct_parent_backend", lambda found: "torch_cpu"
    )
    facts = configured_host_facts({"paths": {"image_manifest": "/w.json"}}).facts
    assert seen == [Path("/w.json")] and isinstance(seen[0], Path)
    assert "trusted_worker_image" in facts and TORCH_CPU_WORKER in facts


def test_an_unusable_image_is_a_missing_fact_and_the_log_says_why(monkeypatch, caplog):
    from carbon.miner_mcp.mcp_challenges import configured_host_facts
    from carbon.reconstruction.worker import docker_runtime

    def broken(path):
        raise ValueError("manifest unreadable")

    monkeypatch.setattr(docker_runtime, "load_image_identity", broken)
    with caplog.at_level("WARNING"):
        facts = configured_host_facts({"paths": {"image_manifest": "/w.json"}}).facts
    assert "trusted_worker_image" not in facts
    assert any(
        "trusted worker image fact unavailable" in r.message for r in caplog.records
    )
    assert any(r.exc_info for r in caplog.records)


class WorkerChecks(Checks):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def compute(self, image, analysis):
        found = super().compute(image, analysis)
        return found if self.parent is None else {**found, "worker_parent": self.parent}


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


def test_a_jax_worker_names_each_torch_version_at_compute_and_review(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=WorkerChecks("cpu"))
    completed(tmp_path, setup)
    check = setup.state()["steps"]["compute"]["check"]
    assert check["worker_parent"] == "cpu"
    assert {(c["id"], c["version"]) for c in check["pytorch_needed_for"]} == TORCH
    assert check["pytorch_step"] == PYTORCH_STEP and "--pytorch" in PYTORCH_STEP
    warnings = [
        w
        for w in setup.review({"confirm": True})["warnings"]
        if w["code"] == "pytorch_worker_required"
    ]
    assert {(w["challenge"], w["version"]) for w in warnings} == TORCH
    for warning in warnings:
        assert "--pytorch" in warning["message"]


@pytest.mark.parametrize("parent", ["torch_cpu", None])
def test_a_pytorch_worker_or_an_unnamed_parent_warns_of_nothing(
    tmp_path, state, parent
):
    setup = EnvironmentSetup(
        state, onboarding=Onboarding(), checks=WorkerChecks(parent)
    )
    completed(tmp_path, setup)
    check = setup.state()["steps"]["compute"]["check"]
    assert "pytorch_needed_for" not in check
    assert ("worker_parent" in check) is (parent is not None)
    assert RUNTIME.get("worker_parent") is None
    codes = [w["code"] for w in setup.review({"confirm": True})["warnings"]]
    assert "pytorch_worker_required" not in codes


# --- M1 rehearsal, 2026-10-21: the profile setup writes must load -------------


def test_the_profile_setup_writes_loads_and_holds_no_worker_parent(tmp_path, state):
    """Round trip: setup checks a PyTorch worker and writes the profile; the
    runner's own key check accepts that runtime. The worker's CPU parent stays
    in the compute check, never in the runtime (840cf69b1 wrote it there, and
    every Challenge read research_runtime_interface_unavailable)."""
    import json

    from scripts.dev.miner_launchpad import runner

    setup = EnvironmentSetup(
        state, onboarding=Onboarding(), checks=WorkerChecks("torch_cpu")
    )
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    assert setup.state()["steps"]["compute"]["check"]["worker_parent"] == "torch_cpu"
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert "worker_parent" not in cfg["runtime"]
    assert set(cfg["runtime"]) <= runner.SUPPORTED_RUNTIME_KEYS
    assert runner.REQUIRED_RUNTIME_KEYS <= set(cfg["runtime"])


@pytest.mark.parametrize(
    "parent, loads", [("torch_cpu", True), ("cpu", True), ("gpu", False)]
)
def test_a_profile_written_with_worker_parent_still_loads(parent, loads):
    """A profile written while setup put worker_parent in the runtime loads
    with a known parent, and the runtime a campaign sees drops it; an unknown
    one is refused as before."""
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    runtime = {**RUNTIME, "worker_parent": parent}
    host = SimpleNamespace(
        _configuration=lambda: {"enabled": True, "runtime": dict(runtime)}
    )
    if loads:
        cfg = RunnerAdapter.configured(host)
        assert cfg["runtime"] == RUNTIME
    else:
        with pytest.raises(Rejected) as refused:
            RunnerAdapter.configured(host)
        assert refused.value.code == "research_runtime_interface_unavailable"
