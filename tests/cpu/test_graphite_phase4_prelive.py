"""Graphite phase 4's pre-live gate (`phase4_prelive`): every real code path
of a live run up to the network boundary, under the live run's threading,
with fakes only at the boundary and no spend.

Claims tested:
- the gate's sqlite thread guard catches a deliberate cross-thread use: a
  connection opened on the main thread and used through `asyncio.to_thread`
  fails its check loudly, with the exception's type, even when the caller
  swallows the error or asks for `check_same_thread=False`;
- the network guard refuses and records any socket connect or name lookup;
- the whole gate runs the live session, Carbon's side and the pod path, and
  passes phase 4 with nothing spent and no network use; a failure on the pod
  path (which phase 4 does not use) is a blocking finding outside phase 4;
- a threading defect injected into the phase-4 session path fails the gate.

The live run's grant and code checks are L1's own tests
(`test_graphite_phase4.py`); here they are replaced by a digest check
against the committed grant, because a gate run inside a pull request's
checkout has no pushed HEAD.
"""

from __future__ import annotations

import asyncio
import io
import json
import socket
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from test_graphite_phase4 import _synthetic_adapter

from carbon.agent_campaign.graphite import phase4
from carbon.agent_campaign.graphite import phase4_prelive as prelive
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILE = REPOSITORY / phase4.PHASE4_GRANTS[BATTERY_CHALLENGE].grant_file
PHASE4_PATHS = (
    "grant_and_code_checks",
    "session_model_ledger_controller",
    "carbon_side_store_pin_replay",
)
POD_PATHS = (
    "pods_compute_store_creating_thread",
    "pods_compute_store_phase3_threading",
)


# -- the guards ---------------------------------------------------------------------------------
def _cross_thread(path, *, swallow=False, check_same_thread=True):
    def call():
        db = sqlite3.connect(path, check_same_thread=check_same_thread)

        def use():
            try:
                return db.execute("SELECT 1").fetchall()
            except sqlite3.Error:
                if not swallow:
                    raise
                return None

        async def drive():
            # The phase-3 shape: opened on the main thread, used from
            # `asyncio.to_thread`.
            return await asyncio.to_thread(use)

        try:
            return asyncio.run(drive())
        finally:
            db.close()

    return call


@pytest.mark.parametrize(
    "swallow, check_same_thread",
    [(False, True), (True, True), (False, False), (True, False)],
)
def test_a_deliberate_cross_thread_sqlite_use_is_caught(
    tmp_path, swallow, check_same_thread
):
    """Mutation: drop the guard's connection factory, and a swallowed or
    `check_same_thread=False` use passes the check."""
    with prelive.sqlite_thread_guard() as uses:
        gate = prelive._Gate(uses)
        ok, detail = gate.check(
            "cross_thread",
            ("a deliberate cross-thread use",),
            _cross_thread(
                tmp_path / "x.sqlite3",
                swallow=swallow,
                check_same_thread=check_same_thread,
            ),
        )
    assert not ok and gate.paths[0]["status"] == "FAIL"
    use, *_ = detail["sqlite_cross_thread_uses"]
    assert use["database"] == "x.sqlite3"
    assert use["opened_on"] == "MainThread" and use["used_on"] != "MainThread"
    if not swallow:
        assert detail["error"] == "ProgrammingError"


def test_a_same_thread_sqlite_use_passes(tmp_path):
    with prelive.sqlite_thread_guard() as uses:
        gate = prelive._Gate(uses)

        def call():
            db = sqlite3.connect(tmp_path / "y.sqlite3")
            try:
                return db.execute("SELECT 1").fetchall()
            finally:
                db.close()

        ok, detail = gate.check("same_thread", (), call)
    assert ok and detail == [(1,)]
    assert sqlite3.connect is not None and uses.cross_thread == []


def test_the_network_guard_refuses_and_records(monkeypatch):
    with prelive.network_guard() as attempts:
        with pytest.raises(prelive.NetworkUseRefused):
            socket.create_connection(("example.invalid", 443), timeout=1)
        with pytest.raises(prelive.NetworkUseRefused):
            socket.getaddrinfo("example.invalid", 443)
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(prelive.NetworkUseRefused):
                probe.connect(("127.0.0.1", 9))
        finally:
            probe.close()
    assert [a["call"] for a in attempts] == [
        "create_connection",
        "getaddrinfo",
        "connect",
    ]
    assert socket.create_connection is not None  # restored


# -- the gate -----------------------------------------------------------------------------------
def _grant_copy(tmp_path, challenge=BATTERY_CHALLENGE):
    """The committed grant registered for `challenge`, with an expiry the
    test clock is always under."""
    copy = tmp_path / "grant.json"
    name = phase4.PHASE4_GRANTS[challenge].grant_file
    document = json.loads((REPOSITORY / name).read_bytes())
    copy.write_text(json.dumps({**document, "expires_at": "2099-01-01T00:00:00Z"}))
    return copy


def _committed_by_digest(monkeypatch, copy):
    """L1's git checks need a pushed HEAD; a pull request's checkout has
    none, so the gate's grant check here keeps the real registry lookup and
    id binding and compares digests with `copy` in place of the git blobs."""
    expected = phase4.grant_digest(json.loads(copy.read_bytes()))

    def check(path, repository=phase4.REPOSITORY, *, challenge):
        document = json.loads(Path(path).read_bytes())
        phase4.bind_grant_to_challenge(document, phase4.phase4_grant(challenge))
        if phase4.grant_digest(document) != expected:
            raise phase4.RunnerRefused("grant_differs_from_the_committed_phase4_grant")
        return expected

    monkeypatch.setattr(phase4, "check_committed_grant", check)
    monkeypatch.setattr(phase4, "check_code_ref", lambda ref, repository=None: None)


#: The synthetic stand-in Challenge has no registered scoring; the gate runs
#: it under battery's, as `test_graphite_phase4` does (#584).
SCORING = challenge_scoring.scoring_for(BATTERY_CHALLENGE)


def _gate(tmp_path, adapter, atk):
    printed = []
    code = prelive.prelive(
        tmp_path / "root",
        adapter,
        atk,
        grant_path=_grant_copy(tmp_path),
        challenge=BATTERY_CHALLENGE,
        emit=printed.append,
        scoring=SCORING,
    )
    return code, json.loads(printed[-1])


def _assert_pod_step(report, code):
    """The pod and compute-store step: phase 4 does not use it, but it
    blocks the gate until the pod store is thread-safe
    (claude/fix-pod-store-threads); then it, and the gate, go green."""
    rows = {row["path"]: row for row in report["paths"]}
    for name in POD_PATHS:
        assert rows[name]["phase4_live_path"] is False
    # The control: the pod path itself works on the thread that built it.
    assert rows["pods_compute_store_creating_thread"]["status"] == "PASS", rows[
        "pods_compute_store_creating_thread"
    ]["detail"]
    threaded = rows[prelive.POD_STEP]
    blocking = {row["path"]: row for row in report["blocking_findings"]}
    assert report["phase4_live_path"] == "PASS"
    if threaded["status"] == "FAIL":
        # The phase-3 threading defect: a loud, blocking gate failure.
        assert threaded["detail"]["sqlite_cross_thread_uses"]
        assert blocking[prelive.POD_STEP]["blocks_phase4_live_run"] is False
        assert report["verdict"] == "FAIL" and code == 4
    else:
        assert prelive.POD_STEP not in blocking
        assert report["verdict"] == "PASS" and code == 0


@pytest.fixture()
def engine_modules():
    return phase4.attack_modules()


def test_the_gate_runs_every_phase4_path_and_spends_nothing(
    tmp_path, monkeypatch, engine_modules
):
    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    code, report = _gate(tmp_path, _synthetic_adapter(weak=False), engine_modules)
    rows = {row["path"]: row for row in report["paths"]}
    assert [row["path"] for row in report["paths"]] == [*PHASE4_PATHS, *POD_PATHS]
    for name in PHASE4_PATHS:
        assert rows[name]["status"] == "PASS", rows[name]["detail"]
        assert rows[name]["phase4_live_path"] is True
        assert rows[name]["exercised"]
    session = rows["session_model_ledger_controller"]["detail"]
    assert session["provider_state"] == "succeeded"
    assert session["model_requests"] == len(
        prelive.session_script(_synthetic_adapter(weak=False))
    )
    assert session["settled_usd"] == "0" and session["pending_usd"] == "0"
    assert "MainThread" not in session["model_request_threads"]
    assert session["code_runs_dispatched"] == 1
    assert session["pod_backend"]["backend"] == "none"
    side = rows["carbon_side_store_pin_replay"]["detail"]
    assert side["replay_under_another_digest"] in (
        "attack_knowledge_replay_under_another_digest",
        "no_other_digest_yet",
    )
    assert side["journal_entries"] >= 1
    assert rows["grant_and_code_checks"]["detail"]["tampered_copy"] == (
        "grant_differs_from_the_committed_phase4_grant"
    )
    _assert_pod_step(report, code)
    assert report["network_attempts"] == []
    assert report["claims"] == {
        "security_acceptance": False,
        "live_run": False,
        "spend": False,
    }


def test_a_threading_defect_in_the_phase4_path_fails_the_gate(
    tmp_path, monkeypatch, engine_modules
):
    """A sqlite object made on the main thread and used from a worker
    thread inside the session's tool path (the phase-3 session 3 defect's
    shape) fails the session check and the gate, loudly."""
    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    held = {}
    real_call = phase4.AttackerTools.call

    async def defective(self, name, arguments, identity):
        if "db" not in held:
            held["db"] = sqlite3.connect(tmp_path / "defect.sqlite3")
        await asyncio.to_thread(held["db"].execute, "SELECT 1")
        return await real_call(self, name, arguments, identity)

    monkeypatch.setattr(phase4.AttackerTools, "call", defective)
    code, report = _gate(tmp_path, _synthetic_adapter(weak=False), engine_modules)
    rows = {row["path"]: row for row in report["paths"]}
    session = rows["session_model_ledger_controller"]
    assert session["status"] == "FAIL"
    assert session["detail"]["sqlite_cross_thread_uses"]
    assert "harness_error" in session["detail"]["message"]
    assert report["verdict"] == "FAIL" and report["phase4_live_path"] == "FAIL"
    assert code == 4
    assert any(f["blocks_phase4_live_run"] for f in report["blocking_findings"])


def test_a_refused_grant_stops_the_gate_before_anything_opens(
    tmp_path, monkeypatch, engine_modules
):
    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    other = tmp_path / "other.json"
    other.write_text(
        json.dumps({**json.loads(copy.read_bytes()), "monetary_ceiling": "100.00"})
    )
    printed = []
    code = prelive.prelive(
        tmp_path / "root",
        _synthetic_adapter(weak=False),
        engine_modules,
        grant_path=other,
        challenge=BATTERY_CHALLENGE,
        emit=printed.append,
        scoring=SCORING,
    )
    report = json.loads(printed[-1])
    (row,) = report["paths"]
    assert row["path"] == "grant_and_code_checks" and row["status"] == "FAIL"
    assert row["detail"]["refusal"] == "grant_differs_from_the_committed_phase4_grant"
    assert code == 4
    # Release evidence names no grant when the grant was refused.
    assert report["grant"] is None and report["challenge"] == BATTERY_CHALLENGE


@pytest.mark.parametrize("challenge", [BATTERY_CHALLENGE, COLD_PLATE_CHALLENGE])
def test_the_gate_through_the_cli(tmp_path, monkeypatch, challenge):
    """`phase4 prelive` at battery and at cooling Level 0. The report is
    release evidence (WAVE-05 §3): it names the Challenge and the grant it
    accepted, bound to that Challenge, and shows the other Challenge's
    grant refused."""
    copy = _grant_copy(tmp_path, challenge)
    _committed_by_digest(monkeypatch, copy)
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            [
                "prelive",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                challenge,
                "--grant",
                str(copy),
            ]
        )
    report = json.loads(out.getvalue())
    rows = {row["path"]: row for row in report["paths"]}
    for name in PHASE4_PATHS:
        assert rows[name]["status"] == "PASS", rows[name]["detail"]
    _assert_pod_step(report, code)
    assert rows["session_model_ledger_controller"]["detail"]["settled_usd"] == "0"
    entry = phase4.PHASE4_GRANTS[challenge]
    assert report["schema"] == "carbon.graphite.phase4-prelive.v2"
    assert report["challenge"] == challenge
    assert report["grant"] == {
        "challenge": challenge,
        "grant_id": entry.grant_id,
        "grant_file": entry.grant_file,
        "grant_digest": phase4.grant_digest(json.loads(copy.read_bytes())),
    }
    detail = rows["grant_and_code_checks"]["detail"]
    assert detail["other_challenges_grants"] == {
        other.grant_id: "grant_is_for_another_challenge"
        for other in phase4.PHASE4_GRANTS.values()
        if other.challenge != challenge
    }


def test_another_challenges_grant_stops_the_gate(tmp_path, monkeypatch):
    """Battery's grant handed to `prelive --challenge chip-cold-plate` fails
    the grant check typed, and the gate opens nothing after it."""
    copy = _grant_copy(tmp_path, BATTERY_CHALLENGE)
    _committed_by_digest(monkeypatch, copy)
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            [
                "prelive",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                COLD_PLATE_CHALLENGE,
                "--grant",
                str(copy),
            ]
        )
    report = json.loads(out.getvalue())
    (row,) = report["paths"]
    assert row["detail"]["refusal"] == "grant_is_for_another_challenge"
    assert report["grant"] is None and code == 4


def test_mutation_an_unbound_grant_check_fails_the_gate(
    tmp_path, monkeypatch, engine_modules
):
    """The gate's own negative: with the id binding disabled, a copy naming
    the other Challenge's grant is no longer refused typed, and the grant
    check fails the gate."""
    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    monkeypatch.setattr(phase4, "bind_grant_to_challenge", lambda d, e: e)
    code, report = _gate(tmp_path, _synthetic_adapter(weak=False), engine_modules)
    row = report["paths"][0]
    assert row["path"] == "grant_and_code_checks" and row["status"] == "FAIL"
    assert "was not refused" in row["detail"]["message"]
    assert report["grant"] is None and code == 4


def test_mutation_a_grant_check_that_takes_a_raised_ceiling_fails_the_gate(
    tmp_path, monkeypatch, engine_modules
):
    """The gate's tamper negative: a grant check that accepts a copy with
    its ceiling raised fails the gate, and names no accepted grant."""
    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)

    def lax(path, repository=phase4.REPOSITORY, *, challenge):
        document = json.loads(Path(path).read_bytes())
        phase4.bind_grant_to_challenge(document, phase4.phase4_grant(challenge))
        return phase4.grant_digest(document)

    monkeypatch.setattr(phase4, "check_committed_grant", lax)
    code, report = _gate(tmp_path, _synthetic_adapter(weak=False), engine_modules)
    row = report["paths"][0]
    assert row["path"] == "grant_and_code_checks" and row["status"] == "FAIL"
    assert "ceiling raised was not refused" in row["detail"]["message"]
    assert report["grant"] is None and code == 4


def test_the_pod_step_calls_the_pod_layers_shared_check_when_it_exists(
    tmp_path, monkeypatch, engine_modules
):
    """Once `pods.real_path_check` exists (claude/fix-pod-store-threads), the
    pod step is that check: its answer decides the step and the gate."""
    from carbon.agent_campaign.graphite import pods

    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    calls = []

    def shared(*, root, scoring=None):
        calls.append(root)
        return {"launched": True, "terminated": True}

    monkeypatch.setattr(pods, "real_path_check", shared, raising=False)
    code, report = _gate(tmp_path, _synthetic_adapter(weak=False), engine_modules)
    rows = {row["path"]: row for row in report["paths"]}
    step = rows[prelive.POD_STEP]
    assert len(calls) == 1 and step["status"] == "PASS"
    assert step["detail"] == {"launched": True, "terminated": True}
    assert any("pods.real_path_check" in line for line in step["exercised"])
    assert report["verdict"] == "PASS" and code == 0

    def failing(*, root, scoring=None):
        raise sqlite3.ProgrammingError("SQLite objects created in a thread ...")

    monkeypatch.setattr(pods, "real_path_check", failing, raising=False)
    (tmp_path / "again").mkdir()
    code, report = _gate(
        tmp_path / "again", _synthetic_adapter(weak=False), engine_modules
    )
    rows = {row["path"]: row for row in report["paths"]}
    assert rows[prelive.POD_STEP]["detail"]["error"] == "ProgrammingError"
    assert report["verdict"] == "FAIL" and code == 4
    assert report["phase4_live_path"] == "PASS"
