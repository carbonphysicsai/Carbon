"""Fixes for the VALIDATOR-01 security review (2026-10-04), one test group each.

1. The reserved and sealed seed-role guard holds in every spelling, and on
   battery's own pool path (`operate prepare`, `import_batch`) as well as the
   neutral one.
2. The intake reads a body under an absolute deadline before it takes an
   in-flight slot, caps connections overall and per address, and evicts the
   least recently seen peer buckets instead of clearing them.
5. Nothing under a `private/` directory ships to a Graphite pod.
6. A pod's own files cannot crash the experiment loop, and what Carbon fetches
   from a pod is bounded.
7. The attempt ledger keeps at most a bounded number of refused rows per
   hotkey per hour, counting the rest exactly.

These are regression tests, not a security audit (AGENTS.md §13).
"""

import json
import socket
import threading
from pathlib import Path

import pytest
from test_challenge_validator_battery import (  # noqa: F401 - fixtures
    DIGEST,
    backend,
    make,
    refs,
)

from carbon.battery import intake as ib
from carbon.battery import operate
from carbon.battery.pool_store import StateError
from carbon.challenge_validator import Adapters, AttemptLedger, Operator, ReservedRole
from carbon.challenge_validator.battery import BatteryAdapter
from carbon.challenge_validator.interface import canonical_role, role_reserved

REPOSITORY = Path(__file__).resolve().parents[2]
VARIANTS = (
    "ev5-confirmation",
    "EV5-CONFIRMATION",
    "Ev5-Confirmation",
    "GRAPHITE-CONFIRMATION-V1",
    "graphite-Confirmation-v1",
)


# --- 1. the seed-role guard -----------------------------------------------------


def test_reserved_roles_match_in_every_spelling():
    for role in VARIANTS:
        assert role_reserved(role), role
    assert canonical_role("EV5-Confirmation") == "ev5-confirmation"
    assert not role_reserved("pscreen-B07")
    assert role_reserved("Study-X", sealed={"study-x"})
    assert canonical_role(None) is None and not role_reserved(None)


@pytest.fixture
def target(tmp_path, refs, backend):  # noqa: F811
    validator = make(tmp_path / "v", refs, backend)
    return validator


@pytest.mark.parametrize("role", VARIANTS)
def test_battery_refuses_a_reserved_role_on_its_own_pool_path(target, role):
    before = target.journal.public()
    with pytest.raises(StateError) as refused:
        target.prepare_batch(role, kind="screening", count=4, duplicates=1)
    assert refused.value.code == "seed_role_reserved"
    assert target.journal.public() == before  # nothing committed


@pytest.mark.parametrize("role", ["Study-Sealed", "STUDY-SEALED", "study-sealed"])
def test_a_sealed_role_cannot_be_recalled_into_the_pool_in_any_spelling(target, role):
    target.seal_batch("study-sealed", count=4, duplicates=1)
    pooled = {b["fingerprint"] for b in target.store.batches()}
    with pytest.raises(StateError) as refused:
        target.prepare_batch(role, kind="screening", count=4, duplicates=1)
    assert refused.value.code == "seed_role_sealed"
    assert {b["fingerprint"] for b in target.store.batches()} == pooled


def test_an_imported_batch_under_a_reserved_role_is_refused_before_commit(
    target,
    refs,  # noqa: F811
):
    from test_challenge_validator_battery import batch

    from carbon.battery import seeds

    original = batch(refs, "pscreen-B00")
    renamed = seeds.PrivateBatch(
        "EV5-Confirmation", original.cases, original.duplicates
    )
    before = target.journal.public()
    with pytest.raises(StateError, match="seed_role_reserved"):
        target.import_batch(renamed, kind="screening")
    assert target.journal.public() == before


def test_the_neutral_operator_refuses_every_spelling(tmp_path, target):
    (tmp_path / "ledger").mkdir(mode=0o700)
    ledger = AttemptLedger(tmp_path / "ledger/attempts.sqlite3")
    operator = Operator(Adapters([BatteryAdapter(target)]), ledger)
    for role in VARIANTS:
        with pytest.raises(ReservedRole) as refused:
            operator.prepare_batch(
                DIGEST, role, kind="screening", count=4, duplicates=1
            )
        assert refused.value.code == "seed_role_reserved"


def test_operate_prepare_answers_a_refusal_by_name(target, monkeypatch, capsys):
    monkeypatch.setattr(operate, "load_config", lambda path: {})
    monkeypatch.setattr(operate, "validator", lambda *args, **kwargs: target)
    code = operate.main(
        [
            "prepare",
            "--config",
            "x",
            "--role",
            "Ev5-Confirmation",
            "--kind",
            "screening",
        ]
    )
    assert code == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "seed_role_reserved"}


# --- 2. the intake's connection and body limits ------------------------------------


def test_peer_buckets_evict_the_least_recent_never_reset_all(monkeypatch):
    monkeypatch.setattr(ib, "MAX_PEERS", 3)
    now = [0.0]
    limits = ib.PeerLimits(burst=2, rate=0.0, clock=lambda: now[0])
    assert limits.allow("victim") and limits.allow("victim")
    assert not limits.allow("victim")  # exhausted
    for peer in ("a", "b"):
        limits.allow(peer)
    # Two new peers fit beside the victim: its exhausted bucket survives.
    assert not limits.allow("victim")
    for peer in ("c", "d", "e", "f"):
        limits.allow(peer)
    assert len(limits._buckets) == 3  # bounded; the oldest evicted one by one


def test_connection_slots_cap_overall_and_per_address():
    slots = ib.ConnectionSlots(total=3, per_peer=2)
    assert slots.acquire("p") and slots.acquire("p")
    assert not slots.acquire("p")  # per-address cap
    assert slots.acquire("q")
    assert not slots.acquire("r")  # overall cap
    slots.release("p")
    assert slots.acquire("r") and slots.open() == 3
    for peer in ("p", "q", "r"):
        slots.release(peer)
    assert slots.open() == 0


def test_a_trickled_body_times_out_within_the_deadline():
    server, client = socket.socketpair()
    try:
        client.sendall(b"abc")  # three of ten bytes, then nothing
        with pytest.raises(TimeoutError):
            ib.read_body(server, server.makefile("rb"), 10, 0.3)
    finally:
        server.close()
        client.close()


def test_a_whole_body_is_read_and_the_socket_timeout_restored():
    server, client = socket.socketpair()
    try:
        sender = threading.Thread(target=client.sendall, args=(b"0123456789",))
        sender.start()
        assert ib.read_body(server, server.makefile("rb"), 10, 2.0) == b"0123456789"
        sender.join()
        assert server.gettimeout() == ib.SOCKET_TIMEOUT_S
    finally:
        server.close()
        client.close()


def test_a_closed_connection_mid_body_is_refused():
    server, client = socket.socketpair()
    try:
        client.sendall(b"ab")
        client.close()
        with pytest.raises(ConnectionError):
            ib.read_body(server, server.makefile("rb"), 10, 2.0)
    finally:
        server.close()


# --- 5. nothing private ships to a pod -------------------------------------------


def test_no_private_directory_ships_to_a_graphite_pod():
    import subprocess

    from carbon.agent_campaign.graphite import pods
    from carbon.challenge_validator import scoring as challenge_scoring
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    head = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # #584: the pod layer names its Challenge's scoring; battery's ships here.
    shipped = pods.ship_list(
        head, scoring=challenge_scoring.scoring_for(BATTERY_CHALLENGE)
    )
    assert not [p for p in shipped if "private" in Path(p).parts[:-1]]
    assert "scripts/dev/exam_design/private/refs-b-v1.bin" not in shipped
    # A module whose file name says "private" is code, and still ships.
    assert "carbon/development_session/private_records.py" in shipped


# --- 6. hostile pod files ------------------------------------------------------------


def test_a_pod_listing_over_the_limits_is_infrastructure():
    from carbon.agent_campaign.graphite import pods

    row = {"path": "a", "size": 1, "sha256": "0" * 64}
    assert pods.fetch_limits([row]) == [row]
    for listing, code in (
        ([row] * (pods.MAX_FETCH_FILES + 1), "listing_over_limits"),
        ([{**row, "size": pods.MAX_FETCH_BYTES + 1}], "listing_over_limits"),
        ([{**row, "size": -1}], "listing_malformed"),
        ([{**row, "size": "1"}], "listing_malformed"),
        (["a"], "listing_malformed"),
        ({"a": 1}, "listing_over_limits"),
    ):
        with pytest.raises(pods.PodFailure) as refused:
            pods.fetch_limits(listing)
        assert refused.value.detail == code and refused.value.executed


@pytest.mark.parametrize(
    "failure",
    [
        b"[1, 2]",
        b'"timeout"',
        b"7",
        b'{"stage": ["timeout"]}',
        b'{"stage": "' + b"x" * 40 + b'"}',
    ],
    ids=["list", "string", "number", "stage-list", "stage-long"],
)
def test_a_hostile_failure_file_never_crashes_the_loop(tmp_path, failure):
    from test_graphite_pod_timeout import CONFIRMED, experiment, run_baseline

    from carbon.agent_campaign.graphite.pods import Step, synthetic_outputs

    honest = synthetic_outputs(0.2)

    def outputs(job):
        return {"built.json": honest(job)["built.json"], "failure.json": failure}

    run, _ = experiment(
        tmp_path, [Step(outcome="failed", outputs=outputs, timing=CONFIRMED)]
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("FAILED_INFRA", "pod")
    assert record["attempts"][0]["claimed_stage"] is None


def test_a_hostile_fit_file_never_crashes_scoring(tmp_path):
    from test_graphite_pod_timeout import experiment, run_baseline

    from carbon.agent_campaign.graphite.pods import Step, synthetic_outputs

    honest = synthetic_outputs(0.2)

    def outputs(job):
        return {**honest(job), "fit.json": b'["final_loss", 1]'}

    run, _ = experiment(tmp_path, [Step(outcome="done", outputs=outputs)])
    record = run_baseline(run)
    assert record["status"] == "SCORED" and record["fit"] == {}


# --- 7. the ledger stays bounded and exact ---------------------------------------------


def test_refused_rows_are_bounded_per_hour_and_counted_exactly(tmp_path, monkeypatch):
    from carbon.challenge_validator import Submission
    from carbon.challenge_validator import ledger as lg

    monkeypatch.setattr(lg, "MAX_REFUSED_ROWS_PER_HOUR", 5)
    tmp_path.chmod(0o700)
    now = [10**12]
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: now[0])

    def attempt(hotkey="hk-1"):
        return Submission(hotkey, {"sequence": 1}, "c", "1", "[]", DIGEST)

    for _ in range(12):
        ledger.record(attempt(), kind="REFUSED", code="strategy_not_object")
    ledger.record(attempt(), kind="RECEIVED", submission_id="s-1", state="RECEIVED")
    ledger.record(attempt("hk-2"), kind="REFUSED", code="strategy_not_object")
    assert len(ledger.attempts(hotkey="hk-1")) == 6  # five refused rows + received
    counts = ledger.attempt_counts("hk-1")
    assert counts["by_kind"]["REFUSED"] == 12 and counts["total"] == 13
    assert counts["by_contract"] == {DIGEST: 13}
    assert ledger.totals()["REFUSED"] == 13
    now[0] += lg.HOUR_NS + 1  # a new hour: rows resume
    ledger.record(attempt(), kind="REFUSED", code="strategy_not_object")
    assert len(ledger.attempts(hotkey="hk-1")) == 7
    assert ledger.attempt_counts("hk-1")["by_kind"]["REFUSED"] == 13
