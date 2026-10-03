"""Remote GPU practice for any Challenge (LINKONLY-D9).

The route is Challenge-neutral: it takes the Challenge's campaign (its id, its
GPU worker and the environment that worker's practice program needs) as a
parameter and names no Challenge itself. A synthetic second Challenge,
registered nowhere, proves it: its campaign gets a working remote runner from
the same route, and its own worker environment, never battery's, reaches the
job. What is held:
- the `remote_gpu` scope is closed and says it is speed only, never scored or
  official; it needs the GPU scope beside it, for the same Challenge and
  pinned worker; `endpoint` is refused by name;
- the destination is the profile's and never enters the scope;
- the runner is built only from a scope that matches this host's GPU worker,
  and from a profile machine with the campaign's transport; nothing is reached
  until a trial runs;
- battery offers the route through its campaign, with `JAX_PLATFORMS=cuda`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from carbon.challenge_registry.campaigns import ChallengeCampaign, campaign_for_id
from carbon.compute import remote_route
from carbon.compute.remote_machine import RemoteMachineError
from carbon.compute.remote_route import (
    campaign_runner,
    declared_remote,
    remote_scope,
)
from carbon.compute.remote_runner import RemoteRunner, RemoteWorker
from carbon.compute.remote_transport import SSHContainer, SSHDocker
from carbon.registry.model import ChallengeKey

SYNTHETIC = "synthetic-remote-practice-v1"
MACHINE = {"transport": "ssh-container", "destination": "root@pod-1", "port": 40122}


def image(tag="9"):
    from test_battery_gpu_practice import gpu_image

    return gpu_image(tag)


def synthetic_campaign(environment=(("SYNTHETIC_BACKEND", "gpu"),)):
    """A second Challenge's campaign: its own id, GPU scope and worker
    environment. Its research callbacks are never called here."""

    def unused(*args, **kwargs):
        raise AssertionError("the remote route calls no research callback")

    return ChallengeCampaign(
        key=ChallengeKey(SYNTHETIC, "1.0.0"),
        prepare=unused,
        evaluate=unused,
        observation=unused,
        refusal_retains_candidate=True,
        check_attached=unused,
        compose=unused,
        gpu_scope=lambda gpu: {"challenge": SYNTHETIC, "image": gpu.image_id},
        remote_worker=lambda gpu: RemoteWorker(gpu, environment),
    )


def runtime(challenge, gpu, transport):
    return {
        "implementation": {"revision": "r"},
        "images": [],
        "gpu_research": [{"challenge": challenge, "image": gpu.image_id}],
        "remote_gpu": [remote_scope(challenge, gpu, transport)],
    }


#: Every client `NeverReached` was built for: (destination, port).
MADE = []


class NeverReached:
    """An SSH client that must not be used while a runner is built."""

    def __init__(self, destination, *, port=None):
        MADE.append((destination, port))

    def run(self, script, *, timeout):
        raise AssertionError("nothing is reached until a trial runs")

    def tunnel(self, port, *, host="127.0.0.1"):
        raise AssertionError("nothing is reached until a trial runs")


# --- the scope -------------------------------------------------------------------------


def test_the_scope_names_the_challenge_transport_and_worker_and_is_speed_only():
    scope = remote_scope(SYNTHETIC, image(), "ssh-container")
    assert scope == {
        "schema": "carbon.compute.remote-gpu-practice.scope.v1",
        "challenge": SYNTHETIC,
        "transport": "ssh-container",
        "image": image().image_id,
        "image_verified_by": "build-identity",
        "job_transport": "ssh-tunnel",
        "purpose": "speed_only",
        "score": None,
        "official_eligible": False,
    }
    assert remote_scope(SYNTHETIC, image(), "ssh-docker")["image_verified_by"] == (
        "image-id"
    )
    # Where the machine is never enters a campaign's runtime.
    assert "destination" not in json.dumps(scope) and "root@" not in json.dumps(scope)


def test_the_endpoint_transport_never_becomes_a_scope():
    with pytest.raises(RemoteMachineError) as refused:
        remote_scope(SYNTHETIC, image(), "endpoint")
    assert refused.value.code == "endpoint_transport_not_built"
    declared = runtime(SYNTHETIC, image(), "ssh-docker")
    declared["remote_gpu"][0]["transport"] = "endpoint"
    with pytest.raises(RemoteMachineError):
        declared_remote(declared)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.pop("gpu_research"),
        lambda r: r["gpu_research"][0].update(image="sha256:" + "8" * 64),
        lambda r: r["gpu_research"][0].update(challenge="another-challenge-v1"),
        lambda r: r["remote_gpu"][0].update(official_eligible=True),
        lambda r: r["remote_gpu"][0].update(score=1.0),
        lambda r: r["remote_gpu"][0].update(image_verified_by="image-id"),
        lambda r: r["remote_gpu"][0].update(destination="root@pod"),
        lambda r: r["remote_gpu"].append(dict(r["remote_gpu"][0])),
    ],
)
def test_a_scope_that_is_not_exactly_the_routes_is_refused(change):
    declared = runtime(SYNTHETIC, image(), "ssh-container")
    change(declared)
    with pytest.raises(ValueError, match="remote GPU practice scope"):
        declared_remote(declared)


def test_a_runtime_without_remote_practice_declares_nothing():
    assert declared_remote({"implementation": {}, "images": []}) is None
    assert (
        campaign_runner(
            synthetic_campaign(),
            runtime={"implementation": {}, "images": []},
            machine=MACHINE,
            gpu_image=image(),
        )
        is None
    )


# --- the runner, for any Challenge ---------------------------------------------------------


def test_a_second_challenge_gets_a_runner_from_the_same_route():
    MADE.clear()
    # The campaign's own hook: the miner's ssh client, built, not run.
    runner = synthetic_campaign().remote_runner(
        runtime(SYNTHETIC, image(), "ssh-container"), MACHINE, image()
    )
    assert isinstance(runner, RemoteRunner)
    assert runner.transport.ssh.destination == "root@pod-1"
    # The same route, driven with a client that refuses to be reached.
    runner = campaign_runner(
        synthetic_campaign(),
        runtime=runtime(SYNTHETIC, image(), "ssh-container"),
        machine=MACHINE,
        gpu_image=image(),
        ssh=NeverReached,
    )
    assert isinstance(runner.transport, SSHContainer)
    assert runner.worker.environment == (("SYNTHETIC_BACKEND", "gpu"),)
    assert MADE == [("root@pod-1", 40122)]


def test_a_second_challenges_practice_runs_end_to_end_with_its_own_worker(tmp_path):
    """The synthetic Challenge's trial runs through the route to a real job
    server process in a local container, with its own environment."""
    from remote_container_fixture import container, local_worker
    from test_remote_runner import PROGRAM, call, campaign_ledger, fast_job

    tmp_path.chmod(0o700)
    transport, ssh, python = container(tmp_path, image())
    route_runner = campaign_runner(
        synthetic_campaign(),
        runtime=runtime(SYNTHETIC, image(), "ssh-container"),
        machine=MACHINE,
        gpu_image=image(),
        ssh=NeverReached,
    )
    # The route's runner, with this machine standing in for the container
    # and the container's Python for the pinned worker's.
    runner = RemoteRunner(
        transport=transport,
        worker=local_worker(image(), python, route_runner.worker.environment),
        clock=lambda: 100.0,
        job=fast_job,
    )
    ledger = campaign_ledger(tmp_path)
    result = call(runner, ledger)
    assert result["remote"]["transport"] == "ssh-container"
    assert result["remote"]["cleanup"] == "confirmed"
    start = ssh.scripts[1]
    assert "SYNTHETIC_BACKEND=gpu" in start and "JAX_PLATFORMS" not in start
    assert PROGRAM


@pytest.mark.parametrize(
    "machine,match",
    [
        (None, "remote_machine in your runner profile"),
        (
            {"transport": "ssh-docker", "destination": "gpu-box"},
            "another transport",
        ),
        ({"transport": "ssh-container"}, "transport and a destination"),
    ],
)
def test_the_profile_machine_must_exist_and_use_the_campaigns_transport(machine, match):
    with pytest.raises(ValueError, match=match):
        campaign_runner(
            synthetic_campaign(),
            runtime=runtime(SYNTHETIC, image(), "ssh-container"),
            machine=machine,
            gpu_image=image(),
            ssh=NeverReached,
        )


def test_a_scope_for_another_worker_or_challenge_is_refused():
    with pytest.raises(ValueError, match="differs from this GPU worker"):
        campaign_runner(
            synthetic_campaign(),
            runtime=runtime(SYNTHETIC, image("8"), "ssh-container"),
            machine=MACHINE,
            gpu_image=image(),
            ssh=NeverReached,
        )
    with pytest.raises(ValueError, match="differs from this GPU worker"):
        campaign_runner(
            synthetic_campaign(),
            runtime=runtime("another-challenge-v1", image(), "ssh-container"),
            machine=MACHINE,
            gpu_image=image(),
            ssh=NeverReached,
        )


def test_a_challenge_without_a_remote_worker_is_refused():
    from dataclasses import replace

    campaign = replace(synthetic_campaign(), remote_worker=None)
    with pytest.raises(ValueError, match="offers no remote GPU practice"):
        campaign.remote_runner(
            runtime(SYNTHETIC, image(), "ssh-container"), MACHINE, image()
        )


def test_the_route_names_no_challenge():
    for name in (
        "remote_route",
        "remote_runner",
        "remote_transport",
        "remote_container",
    ):
        body = (REPOSITORY / "carbon" / "compute" / (name + ".py")).read_text().lower()
        assert "battery" not in body and "burgers" not in body, name


# --- battery offers the route through its campaign -----------------------------------------


def test_battery_offers_remote_practice_with_its_gpu_program_environment():
    from carbon.development_session.battery_gpu import gpu_scope
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    campaign = campaign_for_id(BATTERY_CHALLENGE)
    declared = {
        "implementation": {"revision": "r"},
        "images": [],
        "gpu_research": [gpu_scope(image())],
        "remote_gpu": [remote_scope(BATTERY_CHALLENGE, image(), "ssh-docker")],
    }
    runner = campaign_runner(
        campaign,
        runtime=declared,
        machine={"transport": "ssh-docker", "destination": "miner@gpu-box"},
        gpu_image=image(),
        ssh=NeverReached,
    )
    assert isinstance(runner.transport, SSHDocker)
    assert runner.worker.environment == (("JAX_PLATFORMS", "cuda"),)
    from carbon.challenge_registry.campaigns import declared_remote as by_challenge

    assert by_challenge(declared) == declared["remote_gpu"][0]
    assert remote_route.RUNTIME_KEY == "remote_gpu"
