"""The development observation outcome must never satisfy a strict caller.

Synthetic fixtures only; no accelerator is initialized, no device is touched and
no real host grant or quarantine storage is used.
"""

import hashlib
from types import SimpleNamespace

import accelerator_host
import pytest

from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

PLAN_DIGEST = "sha256:" + hashlib.sha256(b"synthetic-plan").hexdigest()
SYNTHETIC_CONTRACT = "synthetic-test-only-observation-contract"

# What this host reports comes from the installed record, not from Carbon.
DEVICE_UUID = accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_uuid"]
IDENTITY_ROW = accelerator_host.identity_row()


def _cli(driver_model=b"WDDM", *, processes=b""):
    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(stdout=driver_model)
        if "--query-compute-apps=pid,gpu_uuid" in command:
            return SimpleNamespace(stdout=processes)
        return SimpleNamespace(stdout=IDENTITY_ROW.encode())

    return SimpleNamespace(run=run)


@pytest.fixture(autouse=True)
def installed_host(tmp_path, monkeypatch):
    """A synthetic host root with a device record, as an operator would install.

    `_identity_values` compares what the container reports against this record,
    so the comparison is against installed evidence rather than a constant.
    """
    root = tmp_path / "host"
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    accelerator_host.install(root)
    return root


@pytest.fixture
def registered_contract(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "ESTABLISHED_OBSERVATION_CONTRACTS",
        frozenset({SYNTHETIC_CONTRACT}),
    )
    return SYNTHETIC_CONTRACT


# --- the development outcome ---------------------------------------------------


def test_development_observation_records_unknown_not_an_empty_list():
    """The whole point: it must not assert that nothing else holds the device."""
    observation = runtime.inspect_gpu_device(
        cli=_cli(b"WDDM"),
        container_name="fixture",
        development_plan_digest=PLAN_DIGEST,
    )
    assert observation["other_compute_processes"] is None
    assert observation["other_compute_processes"] != []
    assert observation["exclusivity"] == "UNESTABLISHED_DEVELOPMENT_OBSERVATION"
    assert observation["evidence"] == "DEVELOPMENT_ONLY_NOT_SECURITY_QUALIFIED"
    assert observation["device_memory_cap"] == "NOT_ENFORCED_BY_THIS_OBSERVATION"
    assert observation["official_eligible"] is False
    assert observation["observation_mode"] == "DEVELOPMENT"
    assert observation["development_plan_digest"] == PLAN_DIGEST


def test_development_observation_works_on_the_unsupported_host():
    """WDDM is UNSUPPORTED for strict use, yet a development run may proceed."""
    assert runtime.enumeration_capability("WDDM") == runtime.ENUMERATION_UNSUPPORTED
    runtime.inspect_gpu_device(
        cli=_cli(b"WDDM"),
        container_name="fixture",
        development_plan_digest=PLAN_DIGEST,
    )


def test_development_observation_still_verifies_device_identity():
    stale = IDENTITY_ROW.replace(DEVICE_UUID, "GPU-other").encode()

    def run(command, **kwargs):
        if "--query-compute-apps=pid,gpu_uuid" in command:
            return SimpleNamespace(stdout=b"")
        return SimpleNamespace(stdout=stale)

    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run),
            container_name="fixture",
            development_plan_digest=PLAN_DIGEST,
        )


def test_development_observation_still_blocks_a_reported_foreign_process():
    """Counter-evidence is still counter-evidence."""
    with pytest.raises(WorkerFailure) as error:
        runtime.inspect_gpu_device(
            cli=_cli(b"WDDM", processes=b"123, GPU-foreign"),
            container_name="fixture",
            development_plan_digest=PLAN_DIGEST,
        )
    assert error.value.code is WorkerCode.POLICY


@pytest.mark.parametrize(
    "digest", ["", "not-a-digest", "sha256:xyz", PLAN_DIGEST.upper(), 0, b"x", []]
)
def test_malformed_development_plan_digest_is_refused(digest):
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=_cli(), container_name="fixture", development_plan_digest=digest
        )


def test_both_modes_requested_at_once_is_refused(registered_contract):
    """One observation cannot carry two different claims."""
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=_cli(b"N/A"),
            container_name="fixture",
            observation_contract=registered_contract,
            development_plan_digest=PLAN_DIGEST,
        )


# --- no promotion into the strict path ----------------------------------------


def test_development_observation_cannot_satisfy_a_strict_caller():
    observation = runtime.inspect_gpu_device(
        cli=_cli(b"WDDM"),
        container_name="fixture",
        development_plan_digest=PLAN_DIGEST,
    )
    with pytest.raises(WorkerFailure):
        runtime.require_strict_observation(observation)


def test_strict_observation_satisfies_a_strict_caller(registered_contract):
    observation = runtime.inspect_gpu_device(
        cli=_cli(b"N/A"),
        container_name="fixture",
        observation_contract=registered_contract,
    )
    assert runtime.require_strict_observation(observation) is observation
    assert observation["observation_mode"] == "STRICT"
    assert observation["other_compute_processes"] == []


@pytest.mark.parametrize(
    "forged",
    [
        {"observation_mode": "STRICT", "evidence": "OBSERVED_NOT_SECURITY_QUALIFIED"},
        {
            "observation_mode": "STRICT",
            "evidence": "OBSERVED_NOT_SECURITY_QUALIFIED",
            "other_compute_processes": None,
        },
        {
            "observation_mode": "STRICT",
            "evidence": "DEVELOPMENT_ONLY_NOT_SECURITY_QUALIFIED",
            "other_compute_processes": [],
        },
        {
            "observation_mode": "DEVELOPMENT",
            "evidence": "OBSERVED_NOT_SECURITY_QUALIFIED",
            "other_compute_processes": [],
        },
        "not-a-mapping",
        None,
    ],
)
def test_forged_or_partial_observations_are_refused(forged):
    with pytest.raises(WorkerFailure):
        runtime.require_strict_observation(forged)


def test_relabelled_development_observation_is_still_refused():
    """Renaming the mode does not launder the weaker evidence."""
    observation = dict(
        runtime.inspect_gpu_device(
            cli=_cli(b"WDDM"),
            container_name="fixture",
            development_plan_digest=PLAN_DIGEST,
        )
    )
    observation["observation_mode"] = "STRICT"
    observation["evidence"] = "OBSERVED_NOT_SECURITY_QUALIFIED"
    observation["other_compute_processes"] = []
    with pytest.raises(WorkerFailure):
        runtime.require_strict_observation(observation)


# --- the strict path is unchanged ---------------------------------------------


def test_strict_path_still_refuses_an_unestablished_source():
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(cli=_cli(b"WDDM"), container_name="fixture")
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(cli=_cli(b"N/A"), container_name="fixture")


def test_registry_ships_empty_and_is_untouched_by_this_change():
    assert runtime.ESTABLISHED_OBSERVATION_CONTRACTS == frozenset()


def test_strict_admission_helper_still_refuses():
    from carbon.reconstruction.accelerators import (
        AcceleratorRole,
        AcceleratorUnavailable,
        require_accelerator_admission,
    )

    with pytest.raises(AcceleratorUnavailable, match="dispatch_disabled"):
        require_accelerator_admission(GPU_PROFILE, AcceleratorRole.MINER_RESEARCH)
