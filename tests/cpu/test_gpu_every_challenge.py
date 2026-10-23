"""GPU for every Challenge: one GPU setup serves every catalog Challenge,
on both backends (owner, 2026-10-22: "a must", "easy ... for any challenge").

Every catalog Challenge's GPU practice scope is the same document but for
the Challenge it names. Setup checks it once, through one Challenge; each
launch binds it to the Challenge it launches (`catalog_gpu.rebind`), and that
campaign freezes, registers and runs exactly its own scopes - the JAX GPU
worker and the PyTorch one beside it, locally or on the miner's own remote
machine. A Challenge's own GPU path (outside the catalog) still serves only
the Challenge it was set up for.
"""

from __future__ import annotations

import pytest
from test_gpu_per_backend import JAX, MOTOR, TORCH, record

from carbon.challenge_registry.campaigns import campaign_for
from carbon.compute import remote_route
from carbon.development_session import catalog_gpu
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import RunnerAdapter

#: The four launch Challenges' catalog versions (Motor, Cooling, Ribbed
#: Bracket, Burst Thermal).
LAUNCH = (
    {"id": "electric-motor-magnetics", "version": "1.3"},
    {"id": "chip-cold-plate", "version": "1.2"},
    {"id": "f08-ribbed-bracket", "version": "1.4"},
    {"id": "f02", "version": "2.3"},
)


def profile_runtime(*, remote=False):
    """A profile's runtime as Setup writes it: both workers, checked with
    Motor, locally or on the miner's own remote machine."""
    declared = {"gpu_research": []}
    if remote:
        # `with_gpu` reads the transport from a well-formed declaration.
        declared = {
            "gpu_research": [
                catalog_gpu.gpu_scope(MOTOR["id"], image) for image in (JAX, TORCH)
            ],
            "remote_gpu": [
                remote_route.remote_scope(MOTOR["id"], image, "ssh-docker")
                for image in (JAX, TORCH)
            ],
        }
    return catalog_gpu.with_gpu({}, declared, MOTOR["id"], (JAX, TORCH))


@pytest.mark.parametrize("challenge", LAUNCH, ids=lambda c: c["id"])
@pytest.mark.parametrize("remote", [False, True], ids=["local", "remote"])
def test_one_setup_launches_gpu_practice_on_every_launch_challenge(
    tmp_path, challenge, remote
):
    runtime = profile_runtime(remote=remote)
    request = {"challenge": challenge["id"], "challenge_version": challenge["version"]}
    # The launch is accepted, and binds the profile's scopes to this one.
    assert RunnerAdapter._challenge(request, runtime) == challenge
    bound = RunnerAdapter._bound_runtime(runtime, challenge)
    campaign = campaign_for(challenge)
    assert catalog_gpu.offers_catalog_gpu(campaign)
    # Exactly the scopes this Challenge's own campaign recomputes, for both
    # workers: JAX for jno.* entries, PyTorch for the catalog's torch ones.
    assert bound["gpu_research"] == [
        campaign.gpu_scope(image) for image in (JAX, TORCH)
    ]
    assert [s["backend"] for s in bound["gpu_research"]] == ["jax", "pytorch"]
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    record(root, "gpu-worker-image.json", JAX)
    record(root, "extra-gpu-worker-image.json", TORCH)
    assert campaign.gpu_image(root, bound) == (JAX, TORCH)
    if remote:
        # The remote scopes follow: one per worker, for this Challenge.
        assert remote_route.declared_remotes(bound) == [
            remote_route.remote_scope(challenge["id"], image, "ssh-docker")
            for image in (JAX, TORCH)
        ]
    else:
        assert "remote_gpu" not in bound
    # Nothing else in the runtime moves.
    assert {
        k: v for k, v in bound.items() if k not in ("gpu_research", "remote_gpu")
    } == {k: v for k, v in runtime.items() if k not in ("gpu_research", "remote_gpu")}


def test_the_profile_itself_is_unchanged_by_a_launch():
    runtime = profile_runtime()
    before = repr(runtime)
    RunnerAdapter._bound_runtime(runtime, LAUNCH[1])
    assert repr(runtime) == before


def test_a_cpu_runtime_and_a_challenge_s_own_gpu_path_are_left_as_they_are():
    cpu = {"implementation": {"revision": "a" * 40}, "images": []}
    assert RunnerAdapter._bound_runtime(cpu, LAUNCH[0]) is cpu
    own = {"gpu_research": [{"schema": "another-gpu-scope", "challenge": "x"}]}
    assert catalog_gpu.rebind(own, campaign_for(LAUNCH[0])) is own
    # Launching another Challenge with a Challenge's own GPU scope: refused.
    request = {"challenge": LAUNCH[0]["id"], "challenge_version": "1.3"}
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._challenge(request, own)
    assert refused.value.code == "gpu_scope_is_for_another_challenge"


def test_a_challenge_outside_the_catalog_gpu_path_is_not_bound_to_it():
    from types import SimpleNamespace

    outside = SimpleNamespace(
        key=SimpleNamespace(challenge_id="elsewhere"), declared_gpu=None
    )
    with pytest.raises(ValueError, match="catalog GPU practice"):
        catalog_gpu.rebind(profile_runtime(), outside)
    assert not catalog_gpu.offers_catalog_gpu(outside)
