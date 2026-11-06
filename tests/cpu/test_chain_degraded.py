"""H8: a stale chain never fails a task or charges a slot; a door with no fresh snapshot grades nothing (R38)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator.auto_grade import AutoGrader
from carbon.challenge_validator.interface import Unavailable
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

TASK = "rtsk_" + "a" * 64


class _Window:
    def __init__(self, fresh=True):
        self.fresh = fresh

    def latest(self):
        return object() if self.fresh else None


def _grader(window, retain):
    grader = object.__new__(AutoGrader)
    calls = {"fail": [], "write": [], "keep": []}
    grader.intake = SimpleNamespace(window=window, retain_result=retain)
    grader.artifacts = grader.entries = None
    grader.containers = None
    grader.sample_seconds = 1.0
    grader.pending = lambda: [TASK]
    grader._pool = lambda: None
    grader._king_upkeep = lambda: None
    grader._resume_paused_crowns = lambda: None
    grader._stranded_filed = True
    grader._fail = lambda sid, code: calls["fail"].append((sid, code))
    grader._write = lambda sid, state, **kw: calls["write"].append((sid, state))
    grader._keep = lambda sid, failure: calls["keep"].append(sid)
    return grader, calls


def _refuse(code, kind):
    def retain(*_a, **_k):
        raise kind(code)

    return retain


def test_a_door_without_a_fresh_snapshot_has_no_work_and_grades_nothing():
    retained = []
    grader, calls = _grader(_Window(fresh=False), lambda *a, **k: retained.append(a))
    assert grader.chain_degraded() is True
    assert (
        grader.has_work() is False
    )  # a pending task is not work while the chain is stale
    assert grader.run_once() is None
    assert retained == [] and calls == {"fail": [], "write": [], "keep": []}


@pytest.mark.parametrize("kind", [Unavailable, RetentionUnavailable])
def test_a_chain_that_goes_stale_under_a_round_waits_never_fails(kind):
    window = _Window(fresh=True)

    def retain(*_a, **_k):
        window.fresh = False  # the refresher lost the chain while this round ran
        raise kind("direct_provider_registration_unavailable")

    grader, calls = _grader(window, retain)
    assert grader.run_once() is None
    assert (
        calls["fail"] == [] and calls["write"] == []
    )  # no FAILED marker, no slot given back


@pytest.mark.parametrize("kind", [Unavailable, RetentionUnavailable])
def test_with_a_fresh_snapshot_a_missing_registration_is_handled_as_before(kind):
    grader, calls = _grader(
        _Window(fresh=True), _refuse("direct_provider_registration_unavailable", kind)
    )
    assert grader.run_once() == (TASK, "FAILED")
    assert len(calls["fail"]) == 1


def test_a_grader_without_a_window_is_never_degraded():
    grader, _calls = _grader(None, lambda *a, **k: None)
    del grader.intake.window
    assert grader.chain_degraded() is False


def test_an_unreadable_window_is_a_degraded_chain():
    class Broken:
        def latest(self):
            raise OSError("high-water file unreadable")

    grader, _calls = _grader(Broken(), lambda *a, **k: None)
    assert grader.chain_degraded() is True and grader.has_work() is False


# --- the start waits out an unavailable chain (no restart loop) ---------------------------------------------------


class _Snapshot:
    def __init__(self, context, hotkeys):
        self.context, self._hotkeys = context, set(hotkeys)

    def resolve(self, hotkey):
        return object() if hotkey in self._hotkeys else None


class _Reader:
    """capture() fails with the given codes in order, then returns a snapshot holding ``hotkeys``."""

    def __init__(self, failures, context="ctx", hotkeys=("5Recv",)):
        self.failures, self.context, self.hotkeys = list(failures), context, hotkeys
        self.calls = 0

    async def capture(self, context):
        from carbon.chain.models import ChainFailure

        self.calls += 1
        if self.failures:
            raise ChainFailure(self.failures.pop(0))
        return _Snapshot(self.context, self.hotkeys)


class _Permits:
    def __init__(self, answers=()):
        self.answers = list(answers)

    def read(self, hotkey):
        from carbon.chain.permits import PermitUnavailable

        answer = self.answers.pop(0) if self.answers else {"permit": True}
        if answer == "unavailable":
            raise PermitUnavailable("permit_read_failed")
        if answer == "mismatch":
            raise PermitUnavailable("IDENTITY_MISMATCH")  # a wrong-genesis endpoint
        return answer


NETWORK = SimpleNamespace(context="ctx", publisher_hotkey="5Publisher")


def _await(tmp_path, reader, permits=None, *, wait=True, stop_after=None):
    import threading

    from carbon.challenge_validator import direct_receiver as dr

    stop = threading.Event()
    delays = []

    def sleep(seconds):
        delays.append(seconds)
        return stop_after is not None and len(delays) >= stop_after

    snap = dr.await_chain_identity(
        "5Recv",
        NETWORK,
        permits or _Permits(),
        reader,
        stop,
        tmp_path,
        wait=wait,
        sleep=sleep,
    )
    return snap, delays


def _state(tmp_path):
    return json.loads((tmp_path / "chain-state.json").read_text(encoding="utf-8"))


def test_a_throttled_chain_at_start_is_waited_out_in_process(tmp_path):
    from carbon.chain.models import FailureCode

    reader = _Reader(
        [FailureCode.RATE_LIMITED, FailureCode.UNAVAILABLE, FailureCode.TIMEOUT]
    )
    snap, delays = _await(tmp_path, reader)
    assert snap.resolve("5Recv") is not None and reader.calls == 4
    assert delays == [15.0, 30.0, 60.0]  # doubling to the cap, never a process restart
    state = _state(tmp_path)
    assert state["state"] == "OK" and state["failed_reads"] == 3


def test_while_waiting_the_state_file_says_degraded_with_the_code(tmp_path):
    from carbon.chain.models import FailureCode
    from carbon.challenge_validator.direct_receiver import ReceiverUnavailable

    reader = _Reader([FailureCode.RATE_LIMITED] * 10)
    with pytest.raises(ReceiverUnavailable, match="receiver_stopped_waiting_for_chain"):
        _await(tmp_path, reader, stop_after=2)  # a stop request ends the wait
    state = _state(tmp_path)
    assert state["state"] == "DEGRADED" and state["code"] == "PROVIDER_RATE_LIMITED"
    assert state["failed_reads"] == 2


def test_an_unreadable_permit_is_waited_out_a_missing_permit_refuses(tmp_path):
    snap, delays = _await(
        tmp_path, _Reader([]), _Permits(["unavailable", "unavailable"])
    )
    assert delays == [15.0, 30.0] and snap is not None
    with pytest.raises(ValueError, match="no validator permit"):
        _await(tmp_path, _Reader([]), _Permits([{"permit": False}]))


def test_never_waited_out_malformed_or_one_shot_or_unregistered(tmp_path):
    from carbon.chain.models import ChainFailure, FailureCode

    with pytest.raises(ChainFailure):
        _await(tmp_path, _Reader([FailureCode.MALFORMED]))  # fail closed, as before
    with pytest.raises(ChainFailure):
        _await(
            tmp_path, _Reader([FailureCode.RATE_LIMITED]), wait=False
        )  # an operator one-shot
    with pytest.raises(ValueError, match="registered receiver snapshot required"):
        _await(tmp_path, _Reader([], hotkeys=("5Other",)))


def test_the_serving_watch_records_a_stale_window_and_its_recovery(tmp_path):
    import threading

    from carbon.challenge_validator.direct_receiver import ChainStateWatch

    window = _Window(fresh=True)
    watch = ChainStateWatch(window, tmp_path, threading.Event())
    assert watch.check_once() == "OK" and not (tmp_path / "chain-state.json").exists()
    window.fresh = False
    assert watch.check_once() == "DEGRADED"
    first = _state(tmp_path)
    assert first["state"] == "DEGRADED" and first["code"] == "snapshot_stale"
    watch.check_once()
    again = _state(tmp_path)
    assert again["since_ns"] == first["since_ns"] and again["failed_reads"] == 2
    window.fresh = True
    assert watch.check_once() == "OK" and _state(tmp_path)["state"] == "OK"


def test_status_shows_the_chain_state(tmp_path):
    from carbon.challenge_validator import receiver_setup
    from carbon.challenge_validator.direct_receiver import write_chain_state

    assert receiver_setup._chain_state(tmp_path) is None
    write_chain_state(tmp_path, "DEGRADED", code="PROVIDER_RATE_LIMITED", attempts=3)
    shown = receiver_setup._chain_state(tmp_path)
    assert shown["state"] == "DEGRADED" and shown["failed_reads"] == 3


def test_a_wrong_chain_permit_answer_refuses_at_once_never_waited(tmp_path):
    from carbon.challenge_validator.direct_receiver import ReceiverUnavailable

    with pytest.raises(ReceiverUnavailable, match="receiver_permit_unavailable"):
        _await(tmp_path, _Reader([]), _Permits(["mismatch"]))
    assert not (
        tmp_path / "chain-state.json"
    ).exists()  # nothing waited, nothing recorded


def test_a_one_shot_never_writes_the_doors_chain_state(tmp_path):
    from carbon.challenge_validator.direct_receiver import write_chain_state

    write_chain_state(tmp_path, "DEGRADED", code="PROVIDER_RATE_LIMITED", attempts=4)
    _await(tmp_path, _Reader([]), wait=False)
    assert (
        _state(tmp_path)["state"] == "DEGRADED"
    )  # the serving door's record is left as it was
