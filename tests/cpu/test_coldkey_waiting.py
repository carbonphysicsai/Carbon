"""One waiting submission per coldkey (owner 14 Nov 2026, 23:36 CST: "1.0 and yes"; `coldkey_waiting`).

At SUBMIT, before any intent or build, a NEW submission is refused while a hotkey of the same coldkey already has one
waiting on the door (queued, building, or built and not yet graded). The guard's own rules are tested on stub task views;
the wiring through the REAL `LeanRecipeAdapter.evaluate` (a real durable task provider and attempt ledger) on the
synthetic fixture Challenge. Synthetic hotkeys, coldkeys and ids only; the one production value pinned is the committed
Motor 1.8 limit.
"""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import coldkey_waiting as cw

# --- the committed value ------------------------------------------------------------------------------------------


def test_the_committed_registry_sets_one_waiting_submission_for_motor_1_8_only():
    from pathlib import Path

    from carbon.development_session.research_campaign import descendant_path_allowed

    assert json.loads(cw.REGISTRY.read_text()) == {
        "rows": {"electric-motor-magnetics 1.8": {"limit": 1}},
        "schema": cw.SCHEMA,
    }
    assert cw.limit_for("electric-motor-magnetics", "1.8") == 1
    for other in (("electric-motor-magnetics", "1.7"), ("chip-cold-plate", "1.8")):
        assert cw.limit_for(*other) is None
    root = Path(cw.REGISTRY).resolve().parents[2]
    record = json.loads(
        (root / "docs/records/2026-11-14-coldkey-waiting-limit.json").read_text()
    )
    assert record["values"] == json.loads(cw.REGISTRY.read_text())["rows"]
    assert [w["verbatim"] for w in record["owner_words"]] == ["1.0 and yes"]
    # a values-only path: the limit can change (or go off) without a code change
    assert descendant_path_allowed(
        Path(cw.REGISTRY).resolve().relative_to(root).as_posix()
    )


@pytest.mark.parametrize(
    "row",
    [None, {}, {"limit": 0}, {"limit": True}, {"limit": 1.0}, {"limit": 1, "x": 2}],
)
def test_a_missing_or_malformed_row_is_off(tmp_path, row):
    path = tmp_path / "limit.json"
    rows = {} if row is None else {"c 1.0": row}
    path.write_text(json.dumps({"schema": cw.SCHEMA, "rows": rows}))
    assert cw.limit_for("c", "1.0", path=path) is None
    path.write_text("{not json")
    assert cw.limit_for("c", "1.0", path=path) is None
    assert cw.limit_for("c", "1.0", path=tmp_path / "absent.json") is None


# --- the guard on stub views --------------------------------------------------------------------------------------


class _View:
    def __init__(self, state):
        self.state = SimpleNamespace(value=state)


class _Snapshot:
    def __init__(self, coldkeys):
        self.coldkeys = coldkeys

    def resolve(self, hotkey):
        coldkey = self.coldkeys.get(hotkey)
        return None if coldkey is None else SimpleNamespace(coldkey=coldkey)


COLDKEYS = {"hk-a1": "ck-a", "hk-a2": "ck-a", "hk-b": "ck-b"}


def _guard(views, *, pending=(), coldkeys=COLDKEYS, snapshot=True):
    opened = {
        hotkey: SimpleNamespace(_views={t: _View(s) for t, s in tasks.items()})
        for hotkey, tasks in views.items()
    }
    return cw.Guard(
        opened=lambda: opened,
        pending=lambda: list(pending),
        snapshot=lambda: _Snapshot(coldkeys) if snapshot else None,
    )


@pytest.mark.parametrize("state", ["QUEUED", "RUNNING", "CANCEL_REQUESTED"])
def test_a_queued_or_building_submission_of_another_hotkey_of_the_coldkey_refuses_the_next(
    state,
):
    guard = _guard({"hk-a1": {"t1": state}})
    code, message = guard.refusal(hotkey="hk-a2", task_id="t2", limit=1)
    assert code == cw.CODE and "coldkey" in message and "Nothing was built" in message
    # the same hotkey too (a hotkey is one of its coldkey's hotkeys)
    assert guard.refusal(hotkey="hk-a1", task_id="t2", limit=1)[0] == cw.CODE


def test_another_coldkey_is_never_held_back():
    guard = _guard({"hk-a1": {"t1": "QUEUED"}})
    assert guard.refusal(hotkey="hk-b", task_id="t2", limit=1) is None


def test_built_counts_while_ungraded_and_frees_the_place_once_graded():
    """Only queued / building / built-and-ungraded holds the place. ANY terminal state frees it: the grade round writes a
    marker (it leaves `AutoGrader.pending`) for every grade it settles (GRADED, a limit refusal at grading, the
    candidate's wall stop or early stop = CANDIDATE_FAILED, FAILED incl. an infrastructure give-back), and a build that
    failed, was cancelled or ended on infrastructure is never a waiting state."""
    assert (
        _guard({"hk-a1": {"t1": "SUCCEEDED"}}, pending=["t1"]).refusal(
            hotkey="hk-a2", task_id="t2", limit=1
        )[0]
        == cw.CODE
    )
    # graded (no longer pending), failed or cancelled: nothing waits
    for state, pending in (
        ("SUCCEEDED", []),
        ("FAILED", ["t1"]),
        ("CANCELLED", ["t1"]),
        ("FAILED_INFRA", ["t1"]),
    ):
        guard = _guard({"hk-a1": {"t1": state}}, pending=pending)
        assert guard.refusal(hotkey="hk-a2", task_id="t2", limit=1) is None, state


def test_a_resend_of_the_same_submission_is_never_refused():
    guard = _guard({"hk-a1": {"t1": "QUEUED"}})
    assert guard.refusal(hotkey="hk-a1", task_id="t1", limit=1) is None


def test_the_limit_is_the_registered_value():
    guard = _guard({"hk-a1": {"t1": "QUEUED"}})
    assert guard.refusal(hotkey="hk-a2", task_id="t2", limit=2) is None
    guard = _guard({"hk-a1": {"t1": "QUEUED", "t3": "RUNNING"}})
    assert guard.refusal(hotkey="hk-a2", task_id="t2", limit=2)[0] == cw.CODE


def test_an_unresolved_submitter_is_refused_on_the_existing_retry_code_never_a_new_coldkey():
    guard = _guard({})
    code, message = guard.refusal(hotkey="hk-unknown", task_id="t2", limit=1)
    assert code == "allowance_group_unresolved" and "Try again later" in message


def test_a_waiting_task_whose_owner_cannot_be_resolved_counts_for_no_coldkey():
    guard = _guard({"hk-gone": {"t1": "QUEUED"}})
    assert guard.refusal(hotkey="hk-a1", task_id="t2", limit=1) is None


def test_a_read_that_cannot_be_made_never_refuses():
    assert (
        _guard({"hk-a1": {"t1": "QUEUED"}}, snapshot=False).refusal(
            hotkey="hk-a2", task_id="t2", limit=1
        )
        is None
    )

    def broken():
        raise RuntimeError("store busy")

    guard = cw.Guard(
        opened=lambda: {"hk-a1": SimpleNamespace(_views={"t1": _View("QUEUED")})},
        pending=broken,
        snapshot=lambda: _Snapshot(COLDKEYS),
    )
    assert guard.refusal(hotkey="hk-a2", task_id="t2", limit=1) is None
    assert (
        cw.Guard(
            opened=lambda: None, pending=list, snapshot=lambda: _Snapshot(COLDKEYS)
        ).refusal(hotkey="hk-a2", task_id="t2", limit=1)
        is None
    )


# --- the wiring through the REAL adapter --------------------------------------------------------------------------


def _door(tmp_path, monkeypatch, *, limit=1):
    from test_direct_v3_durable_tasks import _fixture

    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator import Adapters, AttemptLedger, Validator
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    ledger = AttemptLedger(root / "ledger.sqlite3")
    adapter = LeanRecipeAdapter(
        discovery, lambda owner: provider if owner == "miner" else None, ledger
    )
    registry = tmp_path / "limit.json"
    rows = (
        {}
        if limit is None
        else {f"{adapter.challenge_id} {adapter.challenge_version}": {"limit": limit}}
    )
    registry.write_text(json.dumps({"schema": cw.SCHEMA, "rows": rows}))
    monkeypatch.setattr(cw, "REGISTRY", registry)
    adapter.coldkey_waiting = cw.Guard(
        opened=lambda: {"miner": provider},
        pending=list,
        snapshot=lambda: _Snapshot({"miner": "ck-miner"}),
    )
    return request, adapter, ledger, Validator(Adapters([adapter]), ledger), provider


def _submit(door, adapter, recipe, sequence):
    from carbon.challenge_validator import Submission

    return door.evaluate(
        Submission(
            "miner",
            {"sequence": sequence, "digest": f"{sequence:064x}"},
            adapter.challenge_id,
            adapter.challenge_version,
            json.dumps(recipe, sort_keys=True),
            adapter.contract_digest,
        )
    )


def _other(recipe):
    changed = json.loads(json.dumps(recipe))
    changed["procedure"]["configuration"] = {"variant": 2}
    return changed


def _intents(ledger):
    with ledger._db() as db:
        return db.execute("SELECT COUNT(*) FROM recipe_task_intents").fetchone()[0]


def test_through_the_real_adapter_a_second_waiting_submission_is_refused_before_any_intent(
    tmp_path, monkeypatch
):
    request, adapter, ledger, door, provider = _door(tmp_path, monkeypatch)
    first = _submit(door, adapter, request.recipe, 1)
    assert first["kind"] == "OUTCOME"
    sid = first["outcome"]["submission_id"]
    assert provider._views[sid].state.value == "QUEUED"
    intents = _intents(ledger)
    refused = _submit(door, adapter, _other(request.recipe), 2)
    assert (refused["kind"], refused["code"]) == ("UNAVAILABLE", cw.CODE)
    assert refused["retry"]["message"] == cw.MESSAGE
    assert _intents(ledger) == intents  # nothing written, nothing started
    assert list(provider._views) == [sid]
    # the SAME recipe again (a resend of the waiting submission) is not refused by this rule
    again = _submit(door, adapter, request.recipe, 3)
    assert again.get("code") != cw.CODE


def test_through_the_real_adapter_with_no_registered_limit_nothing_changes(
    tmp_path, monkeypatch
):
    request, adapter, _ledger, door, provider = _door(tmp_path, monkeypatch, limit=None)
    assert _submit(door, adapter, request.recipe, 1)["kind"] == "OUTCOME"
    second = _submit(door, adapter, _other(request.recipe), 2)
    assert second["kind"] == "OUTCOME" and len(provider._views) == 2


def test_the_lock_is_held_until_the_task_has_started(tmp_path, monkeypatch):
    """Two hotkeys of one coldkey can never both pass: the guard's lock is held from the check to the task's start."""
    request, adapter, _ledger, door, provider = _door(tmp_path, monkeypatch)
    seen = []
    real_start = provider.start_research_task

    def start(*args, **kwargs):
        seen.append(adapter.coldkey_waiting.lock.locked())
        return real_start(*args, **kwargs)

    monkeypatch.setattr(provider, "start_research_task", start)
    assert _submit(door, adapter, request.recipe, 1)["kind"] == "OUTCOME"
    assert seen == [True] and not adapter.coldkey_waiting.lock.locked()
    assert isinstance(adapter.coldkey_waiting.lock, type(threading.Lock()))


def _race(monkeypatch, *, locked):
    """Two hotkeys of ONE coldkey released at the same instant through `LeanRecipeAdapter._coldkey_place`; each, once
    past the check, starts its task (a QUEUED view) a moment later, as the real start does.
    """
    import contextlib
    import time

    from carbon.challenge_validator.interface import Unavailable
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    providers = {
        "hk-a1": SimpleNamespace(_views={}),
        "hk-a2": SimpleNamespace(_views={}),
    }
    guard = cw.Guard(
        opened=lambda: providers,
        pending=list,
        snapshot=lambda: _Snapshot(COLDKEYS),
    )
    if not locked:
        guard.lock = (
            contextlib.nullcontext()
        )  # the control: the same check with no lock
    monkeypatch.setattr(cw, "limit_for", lambda challenge, version: 1)
    adapter = SimpleNamespace(
        coldkey_waiting=guard, challenge_id="c", challenge_version="1.0"
    )
    start = threading.Barrier(2)
    results = []

    def submit(hotkey, task_id):
        start.wait()
        try:
            with LeanRecipeAdapter._coldkey_place(adapter, hotkey, task_id):
                time.sleep(0.05)
                providers[hotkey]._views[task_id] = _View("QUEUED")
            results.append("admitted")
        except Unavailable as refused:
            results.append(refused.code)

    threads = [
        threading.Thread(target=submit, args=("hk-a1", "t1")),
        threading.Thread(target=submit, args=("hk-a2", "t2")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    return sorted(results)


def test_two_hotkeys_of_one_coldkey_at_the_same_instant_only_one_is_admitted(
    monkeypatch,
):
    assert _race(monkeypatch, locked=True) == sorted(["admitted", cw.CODE])
    # the control proves the test sees the race: without the lock both would pass
    assert _race(monkeypatch, locked=False) == ["admitted", "admitted"]
