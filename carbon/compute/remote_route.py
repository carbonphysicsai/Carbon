"""Remote GPU practice for any Challenge: its runtime scope and its runner.

OWNER-MINER-COMPUTE-LINK-ONLY-01 (as amended on 2026-10-02): a miner may run
practice on any machine or container of their own, and Carbon only connects
to it. This module is the route's Challenge-neutral part (LINKONLY-D9). It
never names a Challenge: each one offers the route through its own campaign
(`ChallengeCampaign.remote_worker` and its GPU practice scope), as it offers
GPU practice.

**What a campaign freezes.** A runtime declaring remote practice carries
`remote_gpu`, beside the Challenge's `gpu_research` scope, because a remote
setup runs the same GPU practice program on the same pinned GPU worker. The
scope names the Challenge, the transport, the pinned worker and how its
identity is verified. It says, in its own fields, that this is speed only and
never scored or official.

**What it does not freeze.** Where the setup is, its SSH destination and
port, is the runner profile's `remote_machine`: a pod's address can change
when the miner restarts it, and no address or SSH material belongs in a
campaign record. A profile whose transport differs from the campaign's is
refused before anything is reached.
"""

from __future__ import annotations

from .remote_runner import RemoteRunner, RemoteWorker
from .remote_transport import (
    BUILD_IDENTITY,
    BUILT,
    ENDPOINT,
    IMAGE_ID,
    JOB_TRANSPORT,
    SSH_CONTAINER,
    SSH_DOCKER,
    RemoteMachine,
    endpoint_refused,
    transport_for,
)

__all__ = [
    "RUNTIME_KEY",
    "SCOPE_SCHEMA",
    "campaign_runner",
    "declared_remote",
    "remote_scope",
]

#: The runtime key a remote GPU practice campaign declares.
RUNTIME_KEY = "remote_gpu"
SCOPE_SCHEMA = "carbon.compute.remote-gpu-practice.scope.v1"
#: The GPU practice scope every Challenge declares beside it.
GPU_KEY = "gpu_research"
VERIFIED_BY = {SSH_DOCKER: IMAGE_ID, SSH_CONTAINER: BUILD_IDENTITY}
SCOPE_FIELDS = frozenset(
    {
        "schema",
        "challenge",
        "transport",
        "image",
        "image_verified_by",
        "job_transport",
        "purpose",
        "score",
        "official_eligible",
    }
)


def remote_scope(challenge_id: str, image, transport: str) -> dict:
    """The remote GPU practice scope of Challenge `challenge_id`, for the
    pinned GPU worker `image` over `transport`."""
    if transport == ENDPOINT:
        raise endpoint_refused()
    if transport not in BUILT:
        raise ValueError("a remote transport is ssh-docker or ssh-container")
    if type(challenge_id) is not str or not challenge_id:
        raise ValueError("a remote scope names its Challenge")
    image_id = getattr(image, "image_id", None)
    if type(image_id) is not str or not image_id.startswith("sha256:"):
        raise ValueError("exact pinned GPU worker image required")
    return {
        "schema": SCOPE_SCHEMA,
        "challenge": challenge_id,
        "transport": transport,
        "image": image_id,
        "image_verified_by": VERIFIED_BY[transport],
        "job_transport": JOB_TRANSPORT,
        "purpose": "speed_only",
        "score": None,
        "official_eligible": False,
    }


def declared_remote(runtime) -> dict | None:
    """The remote scope a runtime declares, checked for shape; None without
    one. It needs the GPU practice scope beside it, for the same Challenge
    and the same pinned worker."""
    if type(runtime) is not dict or RUNTIME_KEY not in runtime:
        return None
    scopes, gpu = runtime[RUNTIME_KEY], runtime.get(GPU_KEY)
    if (
        type(scopes) is not list
        or len(scopes) != 1
        or type(scopes[0]) is not dict
        or type(gpu) is not list
        or len(gpu) != 1
        or type(gpu[0]) is not dict
    ):
        raise ValueError("exact remote GPU practice scope required")
    scope = scopes[0]
    if scope.get("transport") == ENDPOINT:
        raise endpoint_refused()
    if (
        scope.get("schema") != SCOPE_SCHEMA
        or scope.get("transport") not in BUILT
        or set(scope) != SCOPE_FIELDS
        or scope.get("image_verified_by") != VERIFIED_BY[scope["transport"]]
        or scope.get("job_transport") != JOB_TRANSPORT
        or scope.get("purpose") != "speed_only"
        or scope.get("official_eligible") is not False
        or scope.get("score") is not None
        or scope.get("image") != gpu[0].get("image")
        or scope.get("challenge") != gpu[0].get("challenge")
    ):
        raise ValueError("exact remote GPU practice scope required")
    return dict(scope)


def campaign_runner(campaign, *, runtime, machine, gpu_image, ssh=None):
    """The practice runner on the miner's own remote setup for `campaign`, or
    None when its runtime declares no remote practice.

    `campaign` is the Challenge's `ChallengeCampaign`; it supplies the
    Challenge's id, its worker environment (`remote_worker`) and nothing
    else. `machine` is the runner profile's `remote_machine`, and `gpu_image`
    the campaign's verified GPU worker. Nothing is reached here: the runner
    connects on its first trial.
    """
    scope = declared_remote(runtime)
    if scope is None:
        return None
    if getattr(campaign, "remote_worker", None) is None:
        raise ValueError("this Challenge offers no remote GPU practice")
    if gpu_image is None:
        raise ValueError("remote practice runs the campaign's pinned GPU worker")
    expected = remote_scope(campaign.key.challenge_id, gpu_image, scope["transport"])
    if scope != expected:
        raise ValueError("the declared remote scope differs from this GPU worker")
    if machine is None:
        raise ValueError("remote practice needs remote_machine in your runner profile")
    machine = RemoteMachine.from_document(machine)
    if machine.transport != scope["transport"]:
        raise ValueError(
            "your runner profile's remote machine uses another transport than "
            "this campaign"
        )
    worker = campaign.remote_worker(gpu_image)
    if not isinstance(worker, RemoteWorker) or worker.image != gpu_image:
        raise ValueError("the Challenge's remote worker is its pinned GPU worker")
    options = {} if ssh is None else {"ssh": ssh}
    return RemoteRunner(transport=transport_for(machine, **options), worker=worker)
