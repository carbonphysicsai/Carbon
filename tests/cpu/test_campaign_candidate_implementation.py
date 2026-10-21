"""A product campaign on a development-candidate install runs that candidate
(BUG MOTOR_RUN_INTERRUPTED_CANDIDATE_20261020).

On M1, installed as a development candidate, every Motor Graphite launch was
INTERRUPTED at `run` as a bare `builtins.ValueError`: Motor's and Cooling's
campaigns asked for the exact accepted revision in fetched main, which a
candidate install is not, while Battery's resolved the installed candidate.
Every Challenge now resolves it the same way.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from carbon.battery.campaign import prepare_battery
from carbon.cold_plate.campaign import prepare_cold_plate
from carbon.development_session import research_campaign
from carbon.motor.campaign import prepare_motor
from carbon.reconstruction.worker import docker_runtime
from scripts.dev.miner_launchpad import installed

REVISION = "a" * 40
PREPARES = {
    "battery": prepare_battery,
    "cooling": prepare_cold_plate,
    "motor": prepare_motor,
}


class ReachedImages(Exception):
    """Preparation got past the implementation to the worker image."""


@pytest.fixture
def launch(tmp_path, monkeypatch):
    environment = tmp_path / "environment"
    root = environment / "campaigns" / "cmp-1"
    root.mkdir(parents=True)
    for path in (tmp_path, environment, environment / "campaigns", root):
        path.chmod(0o700)

    def accepted(revision):
        raise ValueError("campaign requires the exact clean accepted revision")

    def images(*_args, **_kwargs):
        raise ReachedImages

    monkeypatch.setattr(research_campaign, "accepted_implementation", accepted)
    monkeypatch.setattr(docker_runtime, "load_image_identity", images)
    return SimpleNamespace(
        root=root,
        command="run",
        product=SimpleNamespace(runtime={}, agent="none"),
        source_profile=environment / "runner-profile.json",
        accepted_revision=REVISION,
        image_manifest=None,
    )


@pytest.mark.parametrize("name", sorted(PREPARES))
def test_a_candidate_install_runs_its_candidate(name, launch, monkeypatch):
    monkeypatch.setattr(
        installed, "profile_candidate", lambda path: {"revision": REVISION}
    )
    with pytest.raises(ReachedImages):
        asyncio.run(PREPARES[name](launch, campaign=None))


@pytest.mark.parametrize("name", sorted(PREPARES))
def test_without_a_candidate_the_accepted_revision_is_required(
    name, launch, monkeypatch
):
    monkeypatch.setattr(installed, "profile_candidate", lambda path: None)
    with pytest.raises(ValueError, match="exact clean accepted revision"):
        asyncio.run(PREPARES[name](launch, campaign=None))


@pytest.mark.parametrize("name", sorted(PREPARES))
def test_a_candidate_for_another_revision_is_refused(name, launch, monkeypatch):
    monkeypatch.setattr(
        installed, "profile_candidate", lambda path: {"revision": "b" * 40}
    )
    with pytest.raises(ValueError, match="differs from profile"):
        asyncio.run(PREPARES[name](launch, campaign=None))
