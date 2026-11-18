"""Lazy owner restore (restart speed, owner via the Lead, 18 Nov 2026; V2 Y with conditions).

Live 116: an in-place restart reopened every retained owner one by one before listening (388 owners, 571-638 s) while
2 had a live task and 10 an unfinished operation. `OwnerProviders.restore` now opens at start only the owners that may
hold work (`_has_work`; doubt opens it), the crown average's host owner, and, before listening, the crown's owners
(`_open_crown_owners`). Every other owner is LAZY: its first touch opens it by the same restoring path, under its own
gate only (`_restore_lazy`), and a failure there sets it aside exactly as `restore` would.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_receiver as receiver

OWNER = "5" + "1" * 47
OTHER = "5" + "2" * 47
RECEIVER = "5" + "3" * 47

POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX task/owner-only ledger")


def _pools(tmp_path):
    """A real receiver owner pool over two owners (the restart fixture of `test_direct_receiver`), and a factory of
    restarted pools over the same files."""
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    inference_image = WorkerImageIdentity(*("sha256:" + "5" * 64 for _ in range(8)))
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    root = receiver._private_directory(tmp_path / "owners")

    def pool():
        return receiver.OwnerProviders(
            root,
            discovery,
            parent,
            tmp_path / "cache",
            inference_image=inference_image,
            implementation={"revision": "a" * 40},
            snapshot=snapshot,
            receiver=RECEIVER,
        )

    first = pool()
    first(OWNER), first(OTHER)
    first.cancel()
    first.close()
    return root, pool


def _events(capsys, name):
    return [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("{") and json.loads(line).get("event") == name
    ]


@POSIX
def test_owners_with_no_work_are_lazy_and_the_first_touch_opens_them_as_restore_would(
    tmp_path, capsys
):
    _root, pool = _pools(tmp_path)
    eager = pool()
    expected = {
        hotkey: eager._open(hotkey, restoring=True) for hotkey in (OWNER, OTHER)
    }
    views = {hotkey: dict(provider._views) for hotkey, provider in expected.items()}
    ledgers = {hotkey: provider.ledger.root for hotkey, provider in expected.items()}
    admissions = dict(eager._admissions)
    eager.cancel()
    eager.close()
    capsys.readouterr()

    restarted = pool()
    restarted.restore()
    names = {hashlib.sha256(h.encode()).hexdigest(): h for h in (OWNER, OTHER)}
    # nothing opened at start: both owners hold no work
    assert restarted._providers == {}
    assert restarted._lazy == names
    (timing,) = _events(capsys, "owner_restore_timing")
    assert timing["owners"] == 2 and timing["lazy"] == 2
    restarted.log_open_counts()
    assert _events(capsys, "owners_open_at_listening") == [
        {"event": "owners_open_at_listening", "open": 0, "lazy": 2, "set_aside": 0}
    ]
    # the first touch opens it by the restoring path: the same ledger, views and frozen admission as an eager restore
    provider = restarted(OWNER)
    assert provider.ledger.root == ledgers[OWNER]
    assert dict(provider._views) == views[OWNER]
    assert restarted._admissions[OWNER] == admissions[OWNER]
    assert restarted(OWNER) is provider
    assert list(restarted._lazy.values()) == [OTHER]
    (opened,) = _events(capsys, "owner_lazy_restored")
    assert opened["owner_sha256"] == hashlib.sha256(OWNER.encode()).hexdigest()
    restarted.cancel()
    restarted.close()


@POSIX
def test_an_owner_that_may_hold_work_is_opened_at_start(tmp_path, monkeypatch):
    _root, pool = _pools(tmp_path)
    restarted = pool()
    real = restarted._has_work
    owner_name = hashlib.sha256(OWNER.encode()).hexdigest()

    def has_work(directory):
        if directory.name == owner_name:
            return True, {}
        return real(directory)

    monkeypatch.setattr(restarted, "_has_work", has_work)
    restarted.restore()
    assert set(restarted._providers) == {OWNER}
    assert list(restarted._lazy.values()) == [OTHER]
    restarted.cancel()
    restarted.close()


@POSIX
def test_an_owner_whose_stores_cannot_be_read_is_opened_at_start(tmp_path, monkeypatch):
    """Doubt never makes an owner lazy: an unreadable store opens the owner at start, as before."""
    _root, pool = _pools(tmp_path)
    restarted = pool()
    monkeypatch.setattr(restarted, "_has_work", lambda directory: None)
    restarted.restore()
    assert set(restarted._providers) == {OWNER, OTHER} and restarted._lazy == {}
    restarted.cancel()
    restarted.close()


@POSIX
def test_a_lazy_owner_that_cannot_reopen_is_set_aside_at_its_first_touch(
    tmp_path, monkeypatch, capsys
):
    """V2: a lazy open that fails takes the set-aside path at that moment (named in the journal, every request of it
    refused `direct_provider_owner_set_aside`, `set_aside` names it for the crown steps), never an error of the request
    that touched it; the other owners are unaffected."""
    from carbon.challenge_validator.interface import Unavailable

    _root, pool = _pools(tmp_path)
    restarted = pool()
    restarted.restore()
    build = restarted._build

    def failing(hotkey, **kwargs):
        if hotkey == OWNER:
            raise ValueError("retained direct owner campaign binding changed")
        return build(hotkey, **kwargs)

    monkeypatch.setattr(restarted, "_build", failing)
    capsys.readouterr()
    name = hashlib.sha256(OWNER.encode()).hexdigest()
    with pytest.raises(Unavailable, match="direct_provider_owner_set_aside"):
        restarted(OWNER)
    assert restarted.set_aside() == {name: "ValueError"}
    assert name not in restarted._lazy and OWNER not in restarted._providers
    (logged,) = _events(capsys, "owner_restore_set_aside")
    assert logged["owner_sha256"] == name and logged["lazy"] is True
    with pytest.raises(Unavailable, match="direct_provider_owner_set_aside"):
        restarted(OWNER)
    assert restarted(OTHER).owner == OTHER
    restarted.cancel()
    restarted.close()


@POSIX
def test_the_lazy_owners_tasks_are_read_from_the_starts_scan(tmp_path, monkeypatch):
    """The advance pass skips a lazy owner's tasks (all terminal) before any owner check, and the public queue indexes
    them, from the start's scan; once the owner is open its own views take over."""
    _root, pool = _pools(tmp_path)
    restarted = pool()
    names = {h: hashlib.sha256(h.encode()).hexdigest() for h in (OWNER, OTHER)}
    scanned = {
        names[OWNER]: {"rtsk_" + "a" * 64: ("SUCCEEDED", 1.0)},
        names[OTHER]: {"rtsk_" + "b" * 64: ("CANCELLED", 2.0)},
    }
    monkeypatch.setattr(
        restarted, "_has_work", lambda directory: (False, scanned[directory.name])
    )
    restarted.restore()
    assert restarted.lazy_tasks() == {"rtsk_" + "a" * 64, "rtsk_" + "b" * 64}
    assert restarted.lazy_index() == {
        "rtsk_" + "a" * 64: ("SUCCEEDED", 1.0),
        "rtsk_" + "b" * 64: ("CANCELLED", 2.0),
    }
    restarted(OWNER)
    assert restarted.lazy_tasks() == {"rtsk_" + "b" * 64}
    restarted.cancel()
    restarted.close()


def test_the_advance_skip_and_the_queue_index_include_the_lazy_owners():
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.challenge_validator.queue_view import QueueView

    lazy_task = "rtsk_" + "c" * 64
    provider_for = SimpleNamespace(
        _providers={},
        lazy_tasks=lambda: frozenset({lazy_task}),
        lazy_index=lambda: {lazy_task: ("SUCCEEDED", 3.0)},
    )
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.provider_for = provider_for
    assert lazy_task in adapter._not_queued_views()
    view = object.__new__(QueueView)
    view.intake = SimpleNamespace(adapter=SimpleNamespace(provider_for=provider_for))
    assert view._index() == {lazy_task: ("SUCCEEDED", 3.0)}


def test_the_crown_owners_are_opened_before_listening():
    """`_open_crown_owners` resolves the incumbent's steps' owners (`AutoGrader._prelude_owners`), which opens each one;
    a grader that cannot resolve them never stops the start."""
    calls = []
    receiver._open_crown_owners(
        SimpleNamespace(_prelude_owners=lambda: calls.append(1) or {OWNER})
    )
    assert calls == [1]

    def broken():
        raise RuntimeError("pool unreadable")

    receiver._open_crown_owners(SimpleNamespace(_prelude_owners=broken))


@POSIX
def test_an_unfinished_ledger_operation_is_work(tmp_path):
    """An operation of the owner's ledger with no finish row (RESERVED included) is work: its owner is opened at start
    (its dead-op settle needs it). An owner with only finished tasks and operations is not.
    """
    root, pool = _pools(tmp_path)
    live = pool()
    directory = root / hashlib.sha256(OWNER.encode()).hexdigest()
    assert live._has_work(directory) == (False, {})
    provider = live(OWNER)
    provider.ledger.reserve(
        "open-op",
        owner=OWNER,
        phase="research",
        request={"kind": "direct"},
        resources={},
    )
    found = live._has_work(directory)
    assert found is not None and found[0] is True


# --- live 116, 18 Nov 2026: a lazy owner was frozen one revision back; the declared chain and the start migration ----


def _record(old, new, paths, reason="r"):
    return {
        "from_revision": old,
        "to_revision": new,
        "paths": paths,
        "reason": reason,
        "evidence_sha256": "sha256:" + "e" * 64,
    }


def test_a_chain_of_declared_hops_migrates_an_owner_two_revisions_back(monkeypatch):
    a, b, c = ("a" * 40, "b" * 40, "c" * 40)
    computed = {(a, b): ("x.py",), (b, c): ("y.py",), (a, c): ("x.py", "y.py")}
    monkeypatch.setattr(
        receiver, "_grading_change", lambda old, new: computed[(old, new)]
    )
    monkeypatch.setattr(
        receiver, "DECLARED_EXAM_CHANGE", _record(b, c, ["y.py"], "now")
    )
    monkeypatch.setattr(
        receiver, "EARLIER_DECLARED_CHANGES", (_record(a, b, ["x.py"], "before"),)
    )
    found = receiver._declared_change(a, c, computed[(a, c)])
    assert (found["from_revision"], found["to_revision"]) == (a, c)
    assert found["paths"] == ["x.py", "y.py"] and found["reason"] == "before | now"
    # the single exact record still answers for its own hop
    assert receiver._declared_change(b, c, ("y.py",))["reason"] == "now"
    # a hop whose own computed paths differ from its record: no chain
    computed[(a, b)] = ("x.py", "z.py")
    assert receiver._declared_change(a, c, computed[(a, c)]) is None
    # a missing hop: no chain
    monkeypatch.setattr(receiver, "EARLIER_DECLARED_CHANGES", ())
    assert receiver._declared_change(a, c, computed[(a, c)]) is None


def test_the_earlier_changes_are_checked_records_one_per_revision():
    a, b = ("a" * 40, "b" * 40)
    assert receiver._check_earlier_changes([_record(a, b, ["x.py"])])
    twice = [_record(a, b, ["x"]), _record(a, b, ["y"])]
    for bad in ([], [{"from_revision": a}], twice):
        with pytest.raises(ValueError, match="declared"):
            receiver._check_earlier_changes(bad)


@POSIX
def test_a_lazy_owners_manifest_moves_to_the_start_revision_only_when_it_differs(
    tmp_path, monkeypatch
):
    _root, pool = _pools(tmp_path)
    restarted = pool()
    calls = []
    monkeypatch.setattr(
        restarted, "_manifest", lambda hotkey, ledger, **kw: calls.append(hotkey)
    )
    # frozen at this start's revision: nothing migrated, nothing written
    restarted.restore()
    assert calls == [] and len(restarted._lazy) == 2
    moved = pool()
    moved.implementation = {"revision": "b" * 40}
    monkeypatch.setattr(
        moved, "_manifest", lambda hotkey, ledger, **kw: calls.append(hotkey)
    )
    moved.restore()
    assert sorted(calls) == sorted([OWNER, OTHER]) and len(moved._lazy) == 2


@POSIX
def test_a_lazy_owner_whose_manifest_cannot_move_is_set_aside_at_start(
    tmp_path, monkeypatch
):
    _root, pool = _pools(tmp_path)
    moved = pool()
    moved.implementation = {"revision": "b" * 40}

    def refused(hotkey, ledger, **kw):
        if hotkey == OWNER:
            raise ValueError("retained direct owner campaign binding changed")

    monkeypatch.setattr(moved, "_manifest", refused)
    moved.restore()
    name = hashlib.sha256(OWNER.encode()).hexdigest()
    assert moved.set_aside() == {name: "ValueError"}
    assert list(moved._lazy.values()) == [OTHER]
