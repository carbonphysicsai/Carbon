"""A hotkey that left the subnet and registered again may submit again (live 116, 25 Nov 2026; v2 7631).

Claims: a LATER registration of the same hotkey in a FRESH snapshot is accepted for new requests, whether its owner is open,
lazy or restored while its registration was unknown; an equal or earlier block, another hotkey's, no registration or a snapshot
that is not fresh refuses as before and cancels nothing; every queued task that could be the old registration's is cancelled,
never built and never re-run; the frozen admission on disk and every count keyed by the hotkey are untouched. Doubles only.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from carbon.chain.models import (
    CARBON_NETUID,
    CARBON_NETWORK,
    ChainContext,
    MetagraphSnapshot,
    Participant,
)
from carbon.challenge_validator import direct_receiver as receiver
from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.interface import Unavailable

OWNER, OTHER, RECEIVER = "5" + "1" * 47, "5" + "2" * 47, "5" + "3" * 47
CONTEXT = ChainContext(
    CARBON_NETWORK,
    "wss://entrypoint-finney.opentensor.ai:443",
    "opentensor",
    "0x" + "1" * 64,
    CARBON_NETUID,
)
NOW_MS = int(time.time() * 1000)
#: The new registration is 100 blocks (1,200 s) before the snapshot's own block.
BLOCK, BEGAN = 10_000, NOW_MS / 1000 - 1200
UNAVAILABLE = "direct_provider_registration_unavailable"


def _snapshot(uid=1, registered=BLOCK - 100, hotkey=OWNER, coldkey="cold"):
    members = [Participant(0, RECEIVER, "owner", 1)]
    if hotkey is not None:
        # (a metagraph's UIDs run on: the ones before the hotkey's are other miners)
        members += [Participant(n, f"5{n:047d}", "c", 1) for n in range(1, uid)]
        members.append(Participant(uid, hotkey, coldkey, registered))
    return MetagraphSnapshot(CONTEXT, BLOCK, "0x" + "2" * 64, NOW_MS, tuple(members))


def _frozen(uid=1, registered=2):
    return receiver.OwnerProviders._record_in(
        _snapshot(uid=uid, registered=registered), OWNER
    )


class _Provider:
    def __init__(self, **created):
        self.tasks = [SimpleNamespace(value=name) for name in created]
        self._views = {
            name: SimpleNamespace(
                created_at_micros=None if at is None else int(at * 1e6)
            )
            for name, at in created.items()
        }
        self.cancelled, self.fail = [], False

    def queued_tasks(self):
        return tuple(t for t in self.tasks if t.value not in self.cancelled)

    def cancel_observed_task(self, task_id, challenge):
        if self.fail:
            raise RuntimeError("cancel failed")
        self.cancelled.append(task_id.value)


class _Window:
    """`latest` is the request window (60 s), `latest_good` the epoch bound admitted work reads."""

    def __init__(self, fresh, good=None):
        self.fresh, self.good = fresh, fresh if good is None else good

    def latest(self):
        return self.fresh

    def latest_good(self, _max_age_s):
        return self.good

    def age_s(self, _snapshot):
        return 0.0


def _pool(tmp_path, window, provider=None, *, frozen=None):
    pool = receiver.OwnerProviders(
        tmp_path,
        SimpleNamespace(info=SimpleNamespace(challenge_key="key")),
        None,
        None,
        snapshot=_snapshot(),
        window=window,
        receiver=RECEIVER,
    )
    if provider is not None:
        pool._providers[OWNER] = provider
        pool._admissions[OWNER] = _frozen() if frozen is None else frozen
    return pool


def _events(text):
    return [
        json.loads(line)
        for line in text.splitlines()
        if "owner_registration_renewed" in line
    ]


def test_a_returning_hotkey_submits_again_and_its_old_queue_is_cancelled(tmp_path):
    provider = _Provider(old=BEGAN - 60, new=BEGAN + 60, unknown=None)
    pool = _pool(tmp_path, _Window(_snapshot(uid=7)), provider)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert pool(OWNER) is provider
        assert pool(OWNER) is provider
    # conservative: a task whose time is unknown goes with the old ones; the new registration's own task stays
    assert provider.cancelled == ["old", "unknown"]
    (event,) = _events(err.getvalue())
    assert event["cancelled"] == 2 and OWNER not in err.getvalue()
    # the registration it is judged by now is the newer one, and one more return is one more renewal
    assert pool._admissions[OWNER]["uid"] == 7
    pool.window.fresh = pool.window.good = _snapshot(uid=9, registered=BLOCK - 10)
    assert pool(OWNER) is provider
    assert provider.cancelled == ["old", "unknown", "new"]


def test_another_coldkey_under_the_same_hotkey_does_not_refuse(tmp_path):
    provider = _Provider()
    window = _Window(_snapshot(uid=7, coldkey="another"))
    assert _pool(tmp_path, window, provider)(OWNER) is provider


@pytest.mark.parametrize(
    "window",
    [
        # an equal block under another UID, an earlier block, no registration
        _Window(_snapshot(uid=7, registered=2)),
        _Window(_snapshot(uid=7, registered=1)),
        _Window(_snapshot(hotkey=None)),
        _Window(_snapshot(hotkey=OTHER, uid=7)),
        # no snapshot at all, and one good for admitted work but not FRESH
        _Window(None),
        _Window(None, good=_snapshot(uid=7)),
        # another chain context
        _Window(
            replace(
                _snapshot(uid=7), context=replace(CONTEXT, genesis_hash="0x" + "9" * 64)
            )
        ),
    ],
)
def test_anything_else_refuses_as_before_and_cancels_nothing(tmp_path, window):
    provider = _Provider(old=BEGAN - 60)
    pool = _pool(tmp_path, window, provider)
    for _ in range(2):
        with pytest.raises(Unavailable, match=UNAVAILABLE):
            pool(OWNER)
    assert provider.cancelled == []
    assert pool._admissions[OWNER] == _frozen()
    assert not pool.former_registration(OWNER, BEGAN - 60)


def test_the_same_registration_is_served_as_before(tmp_path):
    provider = _Provider(old=BEGAN - 60)
    pool = _pool(
        tmp_path,
        _Window(_snapshot(uid=1, registered=BLOCK - 100)),
        provider,
        frozen=_frozen(1, BLOCK - 100),
    )
    assert pool(OWNER) is provider
    assert provider.cancelled == [] and pool._renewed_at == {}


def test_a_failed_cancellation_refuses_and_is_decided_again(tmp_path):
    provider = _Provider(old=BEGAN - 60)
    provider.fail = True
    pool = _pool(tmp_path, _Window(_snapshot(uid=7)), provider)
    with pytest.raises(Unavailable, match=UNAVAILABLE):
        pool(OWNER)
    assert pool._admissions[OWNER] == _frozen() and pool._renewed_at == {}
    provider.fail = False
    assert pool(OWNER) is provider and provider.cancelled == ["old"]


def test_a_restored_owner_that_came_back_keeps_what_its_new_registration_queued(
    tmp_path,
):
    """Every start finds the newer registration again from the snapshot: a restart never cancels the new one's queue."""
    for _start in range(2):
        provider = _Provider(old=BEGAN - 60, new=BEGAN + 60)
        pool = _pool(tmp_path, _Window(_snapshot(uid=7)))
        pool._register(OWNER, provider, None, _frozen(), False, restoring=True)
        assert provider.cancelled == ["old"] and pool._unobserved == set()
        assert pool(OWNER) is provider and provider.cancelled == ["old"]


def test_a_restored_owner_whose_return_is_not_fresh_waits_for_a_fresh_snapshot(
    tmp_path,
):
    provider = _Provider(old=BEGAN - 60, new=BEGAN + 60)
    pool = _pool(tmp_path, _Window(None, good=_snapshot(uid=7)))
    pool._register(OWNER, provider, None, _frozen(), False, restoring=True)
    assert provider.cancelled == [] and pool._unobserved == {OWNER}
    with pytest.raises(Unavailable, match=UNAVAILABLE):
        pool(OWNER)
    assert provider.cancelled == [] and pool._unobserved == {OWNER}
    pool.window.fresh = _snapshot(uid=7)
    assert pool(OWNER) is provider
    assert provider.cancelled == ["old"] and pool._unobserved == set()


@pytest.mark.parametrize(
    "gone", [_snapshot(hotkey=None), _snapshot(uid=7, registered=1)]
)
def test_a_restored_owner_that_is_gone_still_loses_its_whole_queue(tmp_path, gone):
    provider = _Provider(old=BEGAN - 60, new=BEGAN + 60)
    pool = _pool(tmp_path, _Window(gone))
    pool._register(OWNER, provider, None, _frozen(), False, restoring=True)
    assert provider.cancelled == ["old", "new"]
    with pytest.raises(Unavailable, match=UNAVAILABLE):
        pool(OWNER)


def test_an_owner_not_open_is_built_for_a_returning_hotkey_and_for_no_other(
    tmp_path, monkeypatch
):
    """`_build` for a request: the retained manifest's frozen admission, the same rule as an open provider's."""
    from carbon.development_session import research_control, research_tasks
    from carbon.miner_mcp import standard_cli

    monkeypatch.setattr(
        standard_cli, "DirectOwnerImageResolver", lambda *_args, **_kwargs: None
    )
    built = _Provider()
    monkeypatch.setattr(
        research_tasks, "DirectDevelopmentTasksV3", lambda **_kwargs: built
    )
    monkeypatch.setattr(
        research_control,
        "CampaignControl",
        lambda _ledger: SimpleNamespace(acquire=lambda: 1),
    )
    monkeypatch.setattr(receiver, "_private_directory", lambda path: path)
    monkeypatch.setattr(receiver, "write_once", lambda *_args: None)
    from carbon.development_session import research_ledger

    monkeypatch.setattr(
        research_ledger, "CampaignLedger", lambda _root: SimpleNamespace()
    )
    for window, accepted in (
        (_Window(_snapshot(uid=7)), True),
        (_Window(_snapshot(uid=7, registered=2)), False),
        (_Window(None, good=_snapshot(uid=7)), False),
    ):
        pool = _pool(tmp_path, window)
        pool._manifest = lambda *_args, **_kwargs: (_frozen(), False)
        pool.parent = SimpleNamespace(image_id="p")
        if accepted:
            assert pool._build(OWNER, restoring=False, host=False)[0] is built
        else:
            with pytest.raises(Unavailable, match=UNAVAILABLE):
                pool._build(OWNER, restoring=False, host=False)


def test_nothing_the_old_registration_submitted_is_re_run(tmp_path):
    from carbon.challenge_validator import lean_recipe
    from carbon.research import DirectTaskStateV3

    provider = _Provider()
    pool = _pool(tmp_path, _Window(_snapshot(uid=7)), provider)
    assert not pool.former_registration(OWNER, None)  # it never came back yet
    pool(OWNER)
    assert pool.former_registration(OWNER, BEGAN - 1)
    assert pool.former_registration(OWNER, None)
    assert not pool.former_registration(OWNER, BEGAN + 1)
    assert not pool.former_registration(OTHER, BEGAN - 1)

    asked = []

    class Ledger:
        path = str(tmp_path / "ledger")

        def requeue_failed_build(self, *_args, **_kwargs):
            asked.append("requeue")

    for created, operator in ((BEGAN - 60, None), (BEGAN - 60, "LO-1")):
        adapter = object.__new__(lean_recipe.LeanRecipeAdapter)
        adapter.provider_for = pool
        adapter.discovery = SimpleNamespace(info=SimpleNamespace(challenge_key="key"))
        adapter.ledger = Ledger()
        provider.get_research_result = lambda _request, at=created: SimpleNamespace(
            task=SimpleNamespace(
                state=DirectTaskStateV3.FAILED_INFRA, created_at_micros=int(at * 1e6)
            )
        )
        provider._requests = {}
        err = io.StringIO()
        from carbon import research

        original = research.DirectGetTaskRequestV3
        research.DirectGetTaskRequestV3 = lambda *_args: None
        try:
            with contextlib.redirect_stderr(err):
                result = adapter._requeue_failed_build(
                    OWNER,
                    SimpleNamespace(value="rtsk_old"),
                    provider,
                    operator=operator,
                )
        finally:
            research.DirectGetTaskRequestV3 = original
        assert result is None and asked == []
        assert "former_registration" in err.getvalue()


def test_no_count_or_limit_reads_a_registration(tmp_path):
    """Coming back resets no count: the round, the day, the waiting rule and the groups are keyed by hotkey (and coldkey), and
    a hotkey's own rows always count for it (`exam_cap`), so nothing of them reads a UID or a registration block.
    """
    from carbon.challenge_validator import allowance_groups, ledger

    for module in (exam_cap, allowance_groups, ledger):
        text = inspect.getsource(module)
        assert "registered_at" not in text and ".uid" not in text, module.__name__
