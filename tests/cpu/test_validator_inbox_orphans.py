"""Synthetic inbox/pass controls, not a live deployment or file-lock acceptance.

Native Windows diagnostics use an import-only fcntl stub that refuses locking.
The tests explicitly replace the writer boundary; canonical Linux imports real
fcntl. No chain, keys, signer, solver, hidden cases or real submissions.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import threading
import types

import pytest


@pytest.fixture
def modules(monkeypatch):
    if sys.platform == "win32":
        stub = types.ModuleType("fcntl")

        def no_native_lock(*args, **kwargs):
            raise AssertionError("native unit fixture cannot claim flock acceptance")

        stub.flock = no_native_lock
        monkeypatch.setitem(sys.modules, "fcntl", stub)
    intake = importlib.import_module("carbon.battery.intake")
    operate = importlib.import_module("carbon.battery.operate")
    deployment = importlib.import_module("carbon.battery.deployment")
    pool_store = importlib.import_module("carbon.battery.pool_store")
    monkeypatch.setattr(deployment, "writer", lambda target: contextlib.nullcontext())
    monkeypatch.setattr(operate, "writer", lambda target: contextlib.nullcontext())
    monkeypatch.setattr(deployment, "processes_here", lambda target: True)
    return intake, operate, deployment, pool_store


class Target:
    def __init__(self, state_error):
        self.state_error = state_error
        self.states = {"known-first": "ADMITTED", "known-last": "ADMITTED"}
        self.processed = []
        self.pending_calls = 0

    def outcome(self, sid):
        if sid not in self.states:
            raise self.state_error("unknown_submission")
        return {"state": self.states[sid]}

    def process(self, sid):
        self.processed.append(sid)
        self.states[sid] = "SCORED"

    def run_pending(self):
        self.pending_calls += 1
        return ["synthetic-pending-advanced"]

    def status(self):
        return {"pool": {"status": "OPEN"}, "pending": 0, "open_finals": 0}


def planted_inbox(intake, tmp_path, rows):
    inbox = intake.Inbox(tmp_path / "public-synthetic-inbox.sqlite3")
    with inbox._db() as db:
        for order, sid in enumerate(rows):
            db.execute(
                "INSERT INTO inbox VALUES(?,?,?,?,'ADMITTED',NULL,NULL)",
                (sid, "synthetic-no-key-hotkey", "{}", order),
            )
    return inbox


@pytest.mark.parametrize(
    "rows",
    [
        ("orphan-one", "known-first", "known-last"),
        ("known-first", "orphan-one", "orphan-two", "known-last"),
        ("known-first", "known-last", "orphan-one"),
    ],
)
def test_planted_orphan_does_not_block_other_rows_or_pending_work(
    modules, tmp_path, capsys, rows
):
    intake, _, _, store = modules
    inbox = planted_inbox(intake, tmp_path, rows)
    before = {sid: inbox.row(sid) for sid in rows}
    target = Target(store.StateError)
    moved = intake.work_once(inbox, target)
    assert target.processed == ["known-first", "known-last"]
    assert target.pending_calls == 1
    assert moved["processed"] == 2 and moved["advanced"] == 1
    assert moved["orphaned"] == sum(sid.startswith("orphan") for sid in rows)
    assert {sid: inbox.row(sid) for sid in rows} == before
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert len(events) == moved["orphaned"]
    assert all(event["event"] == "worker_orphan_skipped" for event in events)
    assert all(
        event["code"] == "unknown_submission" and event["count"] == 1
        for event in events
    )
    assert all(sid not in json.dumps(events) for sid in rows)


def test_typed_other_state_errors_still_propagate(modules, tmp_path):
    intake, _, _, store = modules
    inbox = planted_inbox(intake, tmp_path, ("known-first",))
    target = Target(store.StateError)

    def broken(sid):
        raise store.StateError("submission_replay_conflict", "private detail")

    target.outcome = broken
    with pytest.raises(store.StateError) as caught:
        intake.work_once(inbox, target)
    assert caught.value.code == "submission_replay_conflict"
    assert target.pending_calls == 0 and target.processed == []


def test_spoofed_unknown_code_is_not_an_orphan(modules, tmp_path):
    intake, _, _, store = modules
    target = Target(store.StateError)
    inbox = planted_inbox(intake, tmp_path, ("known-first",))
    failure = RuntimeError("unknown_submission")
    failure.code = "unknown_submission"
    target.outcome = lambda sid: (_ for _ in ()).throw(failure)
    with pytest.raises(RuntimeError) as caught:
        intake.work_once(inbox, target)
    assert caught.value is failure and target.pending_calls == 0


def test_nonstring_state_code_cannot_spoof_equality_with_unknown_submission(
    modules, tmp_path
):
    intake, _, _, store = modules

    class SpoofCode:
        def __ne__(self, other):
            return False

    target = Target(store.StateError)
    inbox = planted_inbox(intake, tmp_path, ("known-first",))
    failure = store.StateError("different_code")
    failure.code = SpoofCode()
    target.outcome = lambda sid: (_ for _ in ()).throw(failure)
    with pytest.raises(store.StateError) as caught:
        intake.work_once(inbox, target)
    assert caught.value is failure and target.pending_calls == 0


def test_unknown_error_from_process_is_not_silently_skipped(modules, tmp_path):
    intake, _, _, store = modules
    target = Target(store.StateError)
    inbox = planted_inbox(intake, tmp_path, ("known-first",))
    target.process = lambda sid: (_ for _ in ()).throw(
        store.StateError("unknown_submission")
    )
    with pytest.raises(store.StateError):
        intake.work_once(inbox, target)
    assert target.pending_calls == 0


def test_outcome_infrastructure_failure_is_not_an_orphan(modules, tmp_path):
    intake, _, _, store = modules
    target = Target(store.StateError)
    inbox = planted_inbox(intake, tmp_path, ("known-first",))
    failure = OSError("private-state-path-sentinel")
    target.outcome = lambda sid: (_ for _ in ()).throw(failure)
    with pytest.raises(OSError) as caught:
        intake.work_once(inbox, target)
    assert caught.value is failure and target.pending_calls == 0


def test_intake_without_scoring_capability_does_not_advance_or_recover(
    modules, monkeypatch, tmp_path, capsys
):
    intake, _, deployment, store = modules
    monkeypatch.setattr(deployment, "processes_here", lambda target: False)
    inbox = planted_inbox(intake, tmp_path, ("orphan-one", "known-first"))
    target = Target(store.StateError)
    moved = intake.work_once(inbox, target)
    assert moved["orphaned"] == moved["processed"] == moved["advanced"] == 0
    assert target.pending_calls == 0 and target.processed == []
    assert inbox.row("orphan-one")["state"] == "ADMITTED"
    assert capsys.readouterr().err == ""


def test_operator_pass_keeps_orphan_skip_in_its_own_log_stream(modules, tmp_path):
    intake, operate, _, store = modules
    inbox = planted_inbox(intake, tmp_path, ("orphan-one", "known-first"))
    target, out = Target(store.StateError), io.StringIO()
    assert operate._pass(None, target, tmp_path, out, inbox=inbox.path) == (
        target,
        "ok",
    )
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert events[0]["event"] == "worker_orphan_skipped"
    assert events[0]["code"] == "unknown_submission"
    assert events[-1]["event"] == "pass"
    assert target.processed == ["known-first"]
    assert target.pending_calls == 2  # preserve existing work_once + operator routing
    assert "orphan-one" not in out.getvalue()


@pytest.mark.parametrize("detail", ["", "private-case-and-path-sentinel"])
def test_operator_failure_records_closed_code_not_private_details(
    modules, tmp_path, detail
):
    _, operate, _, store = modules
    target, out = Target(store.StateError), io.StringIO()
    target.run_pending = lambda: (_ for _ in ()).throw(
        store.StateError("unknown_submission", detail)
    )
    assert operate._pass(None, target, tmp_path, out) == (target, "failed")
    event = json.loads(out.getvalue())
    assert event["type"] == "StateError"
    assert event["code"] == "unknown_submission"
    assert event["arg_count"] == 1
    assert "private-case-and-path-sentinel" not in out.getvalue()
    assert "args" not in event and "message" not in event and "traceback" not in event


def test_unknown_state_code_and_spoofed_code_are_withheld(modules, tmp_path):
    _, operate, _, store = modules
    for failure in (
        store.StateError("private-code-sentinel"),
        RuntimeError("private-args-sentinel"),
    ):
        if type(failure) is RuntimeError:
            failure.code = "unknown_submission"
        target, out = Target(store.StateError), io.StringIO()
        target.run_pending = lambda failure=failure: (_ for _ in ()).throw(failure)
        assert operate._pass(None, target, tmp_path, out)[1] == "failed"
        event = json.loads(out.getvalue())
        assert event["code"] == "exception_details_withheld" and event["arg_count"] == 1
        assert "private" not in out.getvalue()


def test_absent_state_code_does_not_break_the_retry_handler(modules, tmp_path):
    _, operate, _, store = modules
    failure = store.StateError("unknown_submission", "private-sentinel")
    del failure.code
    target, out = Target(store.StateError), io.StringIO()
    target.run_pending = lambda: (_ for _ in ()).throw(failure)
    assert operate._pass(None, target, tmp_path, out)[1] == "failed"
    assert json.loads(out.getvalue())["code"] == "exception_details_withheld"
    assert "private-sentinel" not in out.getvalue()


def test_only_the_closed_fingerprint_key_is_loggable(modules, tmp_path):
    _, operate, _, store = modules
    for key, expected in (
        ("fingerprint", "missing_fingerprint_key"),
        ("private-fingerprint-value-sentinel", "exception_details_withheld"),
    ):
        target, out = Target(store.StateError), io.StringIO()
        target.run_pending = lambda key=key: (_ for _ in ()).throw(KeyError(key))
        assert operate._pass(None, target, tmp_path, out)[1] == "failed"
        assert json.loads(out.getvalue())["code"] == expected
        assert "private-fingerprint-value-sentinel" not in out.getvalue()


def test_logging_never_calls_arbitrary_repr_or_spoofed_properties(modules, tmp_path):
    _, operate, _, store = modules

    class Unprintable:
        def __repr__(self):
            raise AssertionError("must not print private object")

    class Spoof(RuntimeError):
        @property
        def code(self):
            raise AssertionError("must not read spoofed diagnostic code")

        @property
        def args(self):
            raise AssertionError("must not read overridden args")

    failure = Spoof(Unprintable(), {"private-object-sentinel": "private-data"})
    target, out = Target(store.StateError), io.StringIO()
    target.run_pending = lambda: (_ for _ in ()).throw(failure)
    assert operate._pass(None, target, tmp_path, out)[1] == "failed"
    event = json.loads(out.getvalue())
    assert event["code"] == "exception_details_withheld" and event["arg_count"] == 2
    assert "private" not in out.getvalue()


def test_pending_infrastructure_failure_is_logged_and_retryable(modules, tmp_path):
    intake, operate, _, store = modules
    inbox = planted_inbox(intake, tmp_path, ("orphan-one", "known-first"))
    target, out = Target(store.StateError), io.StringIO()
    original = target.run_pending

    def interrupted():
        raise OSError("private-path-sentinel")

    target.run_pending = interrupted
    assert operate._pass(None, target, tmp_path, out, inbox=inbox.path)[1] == "failed"
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [e["event"] for e in events] == ["worker_orphan_skipped", "pass_failed"]
    assert events[-1]["type"] == "OSError"
    assert "private-path-sentinel" not in out.getvalue()
    assert inbox.row("orphan-one")["state"] == "ADMITTED"
    target.run_pending = original
    assert operate._pass(None, target, tmp_path, out, inbox=inbox.path)[1] == "ok"


def test_worker_log_contains_count_and_preserves_orphan(modules, tmp_path):
    intake, _, _, store = modules
    inbox = planted_inbox(intake, tmp_path, ("orphan-one", "known-first"))
    stop, wake, out = threading.Event(), threading.Event(), io.StringIO()
    target = Target(store.StateError)

    def pending():
        stop.set()
        return []

    target.run_pending = pending
    intake.worker(inbox, target, wake, stop=stop, idle_s=0, out=out)
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert events[0]["event"] == "worker_orphan_skipped"
    assert events[-1]["event"] == "worker_pass" and events[-1]["orphaned"] == 1
    assert inbox.row("orphan-one")["state"] == "ADMITTED"
