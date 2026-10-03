"""Carbon rents no compute (OWNER-MINER-COMPUTE-LINK-ONLY-01).

C-MLP-03 slices 4 and 4b rented a GPU per practice trial with the miner's
provider key. The owner retired that route on 2026-10-02: a miner rents and
stops their own machines, and Carbon only connects to one the miner already
runs. These tests hold that what a miner may still hold from the old route is
refused by name, `rented_gpu_retired_connect_your_machine`, and never read as
something else:
- a runner profile declaring `rented_gpu`, or naming a `compute_credential`;
- a setup request choosing `rented-gpu`, and a compute step an earlier page
  checked for one; Carbon's stored copy of the provider key is deleted;
- a frozen campaign declaring `rented_gpu`, at both campaign doors, before
  any network or SSH call;
and that nothing under `carbon/` or the Launchpad names a compute provider's
API or imports a removed provider module.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_gpu_practice import gpu_setup

from carbon.compute import retired
from carbon.compute.retired import RENTED_GPU_RETIRED, RentedComputeRetired
from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    LOCAL_CPU,
    SetupRefused,
    choices,
)
from scripts.dev.miner_launchpad.runner import PATH_FIELDS, validated_profile

REVISION = "a" * 40
#: A rented scope as slice 4 froze it; its content is never read.
RENTED_SCOPE = {
    "schema": "carbon.battery.rented-gpu.v1",
    "provider": "runpod",
    "purpose": "speed_only",
    "score": None,
    "official_eligible": False,
}


def profile(tmp_path, **changes):
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "opaque-profile",
        "principal": "alice",
        "enabled": True,
        "accepted_revision": REVISION,
        "campaigns_root": str(tmp_path / "campaigns"),
        "runtime": {"implementation": {"revision": REVISION}, "images": []},
        "paths": {
            key: str(tmp_path / key) for key in PATH_FIELDS | {"operator_config"}
        },
    }
    cfg.update(changes)
    return cfg


@pytest.fixture
def no_network(monkeypatch):
    """Any socket connection or child process fails the test."""

    def forbidden(*args, **kwargs):
        raise AssertionError("reached the network or started a process")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


# --- an old runner profile -------------------------------------------------------


def test_a_profile_declaring_a_rented_gpu_is_refused_by_name(tmp_path):
    cfg = profile(tmp_path)
    # Specimen: the same profile without it validates.
    assert validated_profile(json.loads(json.dumps(cfg)))["runtime"]
    cfg["runtime"]["rented_gpu"] = [RENTED_SCOPE]
    with pytest.raises(Rejected) as refused:
        validated_profile(cfg)
    assert (refused.value.code, refused.value.status) == (RENTED_GPU_RETIRED, 409)


def test_a_profile_naming_a_compute_credential_is_refused_by_name(tmp_path):
    cfg = profile(tmp_path)
    cfg["paths"]["compute_credential"] = str(tmp_path / "keys" / "x.compute-key")
    with pytest.raises(Rejected) as refused:
        validated_profile(cfg)
    assert (refused.value.code, refused.value.status) == (RENTED_GPU_RETIRED, 409)


def test_the_launch_review_names_the_retirement(tmp_path, monkeypatch):
    from test_miner_launchpad_prelaunch import configured_bridge, write

    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    write(bridge, {**cfg, "runtime": {**cfg["runtime"], "rented_gpu": [{}]}})
    result = bridge.preflight()
    assert (result["available"], result["status"]) == (False, "RENTED_GPU_RETIRED")
    assert "Start and stop your machine yourself" in result["reason"]
    assert "revoke" in result["reason"]


# --- an old setup request and setup record -------------------------------------------


def test_setup_offers_no_rented_gpu():
    assert retired.RENTED_CHOICE not in {c["id"] for c in choices()["compute"]}


def test_a_rented_gpu_setup_request_is_refused_and_its_stored_key_deleted(
    tmp_path,
):
    setup, checks, home, paths = gpu_setup(tmp_path)
    keys = setup.root / "keys"
    stored = keys / "runpod.compute-key"
    stored.write_text("rk-fixture-compute-key")
    stored.chmod(0o600)
    inference_key = next(keys.glob("*.key"))
    request = {
        "choice": "rented-gpu",
        **paths,
        "gpu_image_manifest": str(home / "gpu.json"),
        "challenge": {
            "id": "battery-fastcharge-ageing-development-v1",
            "version": "1.0",
        },
        "rented": {"provider": "runpod", "image_ref": "x", "gpu_type_id": "A40"},
        "key": "rk-fixture-compute-key",
    }
    calls = list(checks.calls)
    with pytest.raises(SetupRefused) as refused:
        setup.compute(request)
    assert (refused.value.field, refused.value.code) == ("choice", RENTED_GPU_RETIRED)
    assert "revoke" in refused.value.next_step
    # Carbon's copy of the provider key is gone; the request's key was never
    # written; nothing was checked; the inference key is untouched.
    assert not stored.exists()
    assert list(keys.glob("*.compute-key")) == []
    assert checks.calls == calls
    assert inference_key.exists()
    assert "compute" not in setup._record()


def test_the_next_compute_setup_deletes_a_stored_provider_key_and_says_so(tmp_path):
    setup, _, _, paths = gpu_setup(tmp_path)
    stored = setup.root / "keys" / "lium.compute-key"
    stored.write_text("lk-fixture")
    stored.chmod(0o600)
    state = setup.compute({"choice": LOCAL_CPU, **paths})
    check = state["steps"]["compute"]["check"]
    assert "Revoke" in check["retired_compute_key"]
    assert not stored.exists()
    # Specimen: with nothing stored, nothing is said.
    state = setup.compute({"choice": LOCAL_CPU, **paths})
    assert "retired_compute_key" not in state["steps"]["compute"]["check"]


def test_a_compute_step_checked_for_a_rented_gpu_is_never_written(tmp_path):
    setup, _, home, paths = gpu_setup(tmp_path)
    setup.compute({"choice": LOCAL_CPU, **paths})
    setup.agent({"choice": AUTONOMOUS, "operator_config": str(home / "operator.json")})
    record = setup._record()
    record["compute"]["choice"] = "rented-gpu"
    record["compute"]["runtime"]["rented_gpu"] = [RENTED_SCOPE]
    record["compute"]["paths"]["compute_credential"] = str(home / "x.compute-key")
    setup._save(record)
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert (refused.value.field, refused.value.code) == ("compute", RENTED_GPU_RETIRED)
    assert not setup.profile_path.exists()


# --- a frozen campaign -----------------------------------------------------------------


def frozen(root, runtime):
    root.mkdir(mode=0o700, parents=True)
    manifest = root / "campaign-manifest.json"
    manifest.write_bytes(canonical({"runtime": runtime}))
    manifest.chmod(0o600)
    return manifest


def test_a_frozen_rented_campaign_is_refused_before_anything_is_reached(
    tmp_path, no_network
):
    from carbon.battery import campaign as battery

    root = tmp_path / "campaign"
    frozen(root, {"implementation": {}, "images": [], "rented_gpu": [RENTED_SCOPE]})
    args = SimpleNamespace(root=root, command="resume")
    with pytest.raises(RentedComputeRetired) as refused:
        asyncio.run(battery.prepare_battery(args, campaign=None))
    assert refused.value.code == RENTED_GPU_RETIRED
    # Nothing was opened: no ledger, no session, no compute state.
    assert [p.name for p in root.iterdir()] == ["campaign-manifest.json"]


def test_the_mcp_door_refuses_a_frozen_rented_campaign_before_attaching(
    tmp_path, no_network
):
    from carbon.miner_mcp.standard_cli import load_profile

    tmp_path.chmod(0o700)
    cfg = profile(tmp_path)
    path = tmp_path / "profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    campaign = "0" * 32
    root = Path(cfg["campaigns_root"]) / campaign
    Path(cfg["campaigns_root"]).mkdir(mode=0o700)
    frozen(root, {"implementation": {"revision": REVISION}, "rented_gpu": [{}]})
    (root / "campaign.sqlite3").write_bytes(b"")
    with pytest.raises(RentedComputeRetired):
        load_profile(path, campaign)
    # Specimen: the same campaign without it gets past this refusal.
    frozen_path = root / "campaign-manifest.json"
    frozen_path.unlink()
    frozen_path.write_bytes(canonical({"implementation": {"revision": REVISION}}))
    frozen_path.chmod(0o600)
    with pytest.raises(ValueError) as other:
        load_profile(path, campaign)
    assert not isinstance(other.value, RentedComputeRetired)


def test_a_runtime_without_a_rented_gpu_is_not_refused():
    for runtime in (None, {}, {"gpu_research": []}, ["rented_gpu"]):
        retired.refuse_rented(runtime)
    with pytest.raises(RentedComputeRetired):
        retired.refuse_rented({"rented_gpu": []})


# --- no provider API on the miner path ---------------------------------------------------

#: The provider APIs the retired route called, as hosts.
PROVIDER_HOSTS = ("runpod.io", "lium.io", "targon.com")
#: Every module the retirement removed from `carbon.compute`.
REMOVED = (
    "accounting",
    "admission",
    "capability",
    "cli",
    "credentials",
    "errors",
    "lium",
    "model",
    "provider",
    "providers",
    "reconcile",
    "rented_runner",
    "runpod",
    "service",
    "store",
    "targon",
)
REMOVED_IMPORT = re.compile(r"carbon\.compute\.(" + "|".join(REMOVED) + r")\b")
#: Inside `carbon/compute` itself, the same modules imported relatively.
REMOVED_RELATIVE = re.compile(
    r"^\s*from \.(" + "|".join(REMOVED) + r") import", re.MULTILINE
)
#: The miner path: every package under `carbon/` (no operator code there uses
#: a provider API) and the Launchpad. Operator scripts on the operator's own
#: RunPod account (`scripts/dev/challenge_pools`, `scripts/dev/exam_design`)
#: are outside the decision and are not scanned.
MINER_PATH = (REPOSITORY / "carbon", REPOSITORY / "scripts/dev/miner_launchpad")


def _files():
    for root in MINER_PATH:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                yield path


def _names_a_provider_api(path):
    body = path.read_bytes().lower()
    return any(host.encode() in body for host in PROVIDER_HOSTS)


def test_nothing_on_the_miner_path_names_a_compute_provider_api():
    found = [
        path.relative_to(REPOSITORY).as_posix()
        for path in _files()
        if _names_a_provider_api(path)
    ]
    assert found == []
    # Specimen: the search finds the operator's own RunPod script, which the
    # decision leaves as it is.
    assert _names_a_provider_api(
        REPOSITORY / "scripts/dev/exam_design/runpod/pod_control.py"
    )


def test_nothing_on_the_miner_path_imports_a_removed_provider_module():
    names = {p.stem for p in (REPOSITORY / "carbon/compute").glob("*.py")}
    assert not set(REMOVED) & names
    found = [
        path.relative_to(REPOSITORY).as_posix()
        for path in _files()
        if path.suffix in (".py", ".js")
        and REMOVED_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    found += [
        path.relative_to(REPOSITORY).as_posix()
        for path in sorted((REPOSITORY / "carbon/compute").glob("*.py"))
        if REMOVED_RELATIVE.search(path.read_text(encoding="utf-8"))
    ]
    assert found == []
    # Specimen: the searches find such an import where one is written.
    assert REMOVED_IMPORT.search("from carbon.compute.runpod import RunPodAdapter")
    assert REMOVED_RELATIVE.search("x = 1\nfrom .targon import TargonAdapter\n")
