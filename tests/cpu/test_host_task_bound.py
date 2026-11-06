"""The research-task provider's admission bound (256 tasks per owner) on the crown average's HOST owner.

A miner's owner counts every task it holds. The host owner counts only its LIVE tasks: its finished averaging and king
rebuilds are kept and reused (a re-decision asks for the same task id, and the bank files under that id are
write-once), so they never fill the bound (Lead 5 Nov: at ~11 host tasks per averaged decision, 256 would fill after
~23).

The REAL provider's `start_research_task` runs; only what sits past the bound is stood in (`_verify_images`, the first
step after it, raises `_Admitted`).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_crown_graph_rebuild import HOST, _Admitted, _provider

from carbon.research import DirectTaskStateV3
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError

MINER = "5" + "M" * 47
LIVE = (
    DirectTaskStateV3.QUEUED,
    DirectTaskStateV3.RUNNING,
    DirectTaskStateV3.CANCEL_REQUESTED,
)
FINISHED = tuple(state for state in DirectTaskStateV3 if state not in LIVE)


class _Bundle:
    """A bundle recipe as the provider's guard reads it (no staged material: nothing past the bound runs)."""

    def to_dict(self):
        return {
            "challenge": {
                "id": "carbon-host-bound-fixture",
                "version": "1.0",
                "train_digest": "sha256:" + "5" * 64,
                "interface_digest": "sha256:" + "a" * 64,
                "construction_limits_digest": "sha256:" + "b" * 64,
            },
            "source": {"kind": "bundle"},
        }


def _held(owner, states, tmp_path):
    provider, request = _provider(
        owner, _Bundle(), seeded=owner == HOST, tmp_path=tmp_path
    )

    def admitted():
        raise _Admitted

    provider._verify_images = admitted
    for n, state in enumerate(states):
        provider._views["rtsk_" + f"{n:064x}"] = SimpleNamespace(state=state)
    return provider, request


def _bounded(provider, request):
    with pytest.raises(ResearchTaskProviderError) as refused:
        provider.start_research_task(request)
    return refused.value.code


def test_the_host_owners_finished_tasks_never_fill_its_bound(tmp_path):
    finished = [FINISHED[n % len(FINISHED)] for n in range(300)]
    provider, request = _held(HOST, finished, tmp_path)
    with pytest.raises(_Admitted):
        provider.start_research_task(request)


def test_the_host_owners_bound_counts_its_live_tasks(tmp_path):
    live = [LIVE[n % len(LIVE)] for n in range(256)]
    provider, request = _held(HOST, [*live, *FINISHED], tmp_path)
    assert _bounded(provider, request) is ResearchServiceErrorCode.BOUND_EXCEEDED
    provider, request = _held(HOST, [*live[:255], *FINISHED], tmp_path)
    with pytest.raises(_Admitted):
        provider.start_research_task(request)


@pytest.mark.parametrize("state", [*LIVE, *FINISHED])
def test_a_miners_owner_still_counts_every_task_it_holds(tmp_path, state):
    provider, request = _held(MINER, [state] * 256, tmp_path)
    assert _bounded(provider, request) is ResearchServiceErrorCode.BOUND_EXCEEDED
    provider, request = _held(MINER, [state] * 255, tmp_path)
    with pytest.raises(_Admitted):
        provider.start_research_task(request)


def test_only_the_exact_host_name_is_the_host(tmp_path):
    for near in (HOST + " ", HOST.upper(), "x" + HOST):
        provider, request = _held(near, [DirectTaskStateV3.SUCCEEDED] * 256, tmp_path)
        assert _bounded(provider, request) is ResearchServiceErrorCode.BOUND_EXCEEDED
