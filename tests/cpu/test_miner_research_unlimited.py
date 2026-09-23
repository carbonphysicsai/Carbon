"""The miner's own research has no Carbon limits; Carbon's work keeps its own.

Owner direction (23 September 2026): the research environment is the miner's
machine, cost, time and choice. Each absence asserted here is paired with the
same limit still present on the validator's lane, so a test cannot pass merely
because the limit never existed anywhere.
"""

from pathlib import Path

import pytest

from carbon.development_session.miner_container import (
    MinerResearchLaunch,
    create_arguments,
    prepare_scratch,
)
from carbon.development_session.research_ledger import VERSION, CampaignLedger

LAUNCH = "sha256:" + "a" * 64
IMAGE = "sha256:" + "b" * 64
CAPS = ("--memory", "--memory-swap", "--cpus", "--cpuset-cpus", "--pids-limit")
ISOLATION = ("--read-only", "--cap-drop", "--security-opt", "--user")


def launch(tmp_path):
    stage = tmp_path / "input"
    stage.mkdir()
    return MinerResearchLaunch(
        "carbon-d4-" + "c" * 24, IMAGE, LAUNCH, stage, prepare_scratch(tmp_path / "s")
    )


def test_the_miner_lane_carries_isolation_and_no_resource_caps(tmp_path):
    arguments = create_arguments(launch(tmp_path))
    assert not set(CAPS) & set(arguments)
    assert "nofile=1024:1024" not in arguments
    for flag in ISOLATION:
        assert flag in arguments
    assert arguments[arguments.index("--network") + 1] == "none"
    assert "type=bind" in " ".join(arguments) and "target=/scratch" in " ".join(
        arguments
    )


def test_the_validator_lane_still_carries_every_cap(tmp_path):
    """Specimen: the caps the miner lane lacks are real, and unchanged here."""
    from carbon.reconstruction.worker.docker_runtime import create_arguments as grade
    from carbon.reconstruction.worker.model import DevelopmentWorkerProfile

    stage = tmp_path / "input"
    stage.mkdir()
    arguments = grade(
        container_name="carbon-grade-" + "d" * 16,
        image_id=IMAGE,
        input_directory=stage,
        cpuset="0,1",
        launch_digest=LAUNCH,
        worker_profile=DevelopmentWorkerProfile(
            "sha256:" + "e" * 64, "sha256:" + "f" * 64
        ),
    )
    for flag in CAPS:
        assert flag in arguments
    assert "--tmpfs" in arguments


def test_a_raw_request_cannot_become_a_miner_launch(tmp_path):
    with pytest.raises(Exception):
        create_arguments({"container_name": "x", "image_id": IMAGE})
    with pytest.raises(Exception):
        MinerResearchLaunch("x", IMAGE, LAUNCH, Path("relative"), tmp_path)


def ledger(tmp_path, schema=VERSION, **budget):
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    value = CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)
    value.freeze(
        {
            "schema": schema,
            "campaign_id": "metering",
            "owner": "miner",
            "implementation": "x",
            "objective": "x",
            "sampling": "x",
            "control": "x",
            "selection": "x",
            "replica_policy": "x",
            "provider": "x",
            **budget,
        }
    )
    return value


def test_research_time_and_bytes_are_metered_not_capped(tmp_path):
    value = ledger(tmp_path)
    value.reserve(
        "run",
        owner="miner",
        phase="research",
        request={},
        resources={"numerical_milliseconds": 0, "retained_bytes": 1},
    )
    value.finish(
        "run",
        owner="miner",
        state="SUCCEEDED",
        actual={"numerical_milliseconds": 7_200_000, "retained_bytes": 10**11},
        result={},
    )
    assert value.status(owner="miner")["used"]["numerical_milliseconds"] == 7_200_000


def test_an_attempt_counter_still_may_not_exceed_its_reservation(tmp_path):
    """Specimen for the metering rule: it covers time and bytes, nothing else."""
    value = ledger(tmp_path)
    value.reserve(
        "run",
        owner="miner",
        phase="research",
        request={},
        resources={"research_trials": 1, "numerical_milliseconds": 0},
    )
    with pytest.raises(ValueError, match="reservation exceeded"):
        value.finish(
            "run",
            owner="miner",
            state="SUCCEEDED",
            actual={"research_trials": 2, "numerical_milliseconds": 5},
            result={},
        )


def test_a_long_research_worker_is_admitted_and_a_long_final_one_is_not(tmp_path):
    value = ledger(tmp_path)
    value.reserve(
        "long-research",
        owner="miner",
        phase="research",
        request={},
        resources={"numerical_milliseconds": 24 * 3600 * 1000},
    )
    with pytest.raises(ValueError, match="per-worker"):
        value.reserve(
            "long-final",
            owner="miner",
            phase="final",
            request={},
            resources={"numerical_milliseconds": 24 * 3600 * 1000},
        )


def test_a_miners_own_time_budget_still_binds(tmp_path):
    from carbon.development_session.research_carrier import _has_time_budget

    assert not _has_time_budget(ledger(tmp_path / "a"))
    budgeted = ledger(tmp_path / "b", ceilings={"numerical_milliseconds": 60_000})
    assert _has_time_budget(budgeted)
