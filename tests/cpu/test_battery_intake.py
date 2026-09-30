"""The battery intake (OD-7(b)): a signed submission from a miner's machine.

Real `btauth/1` signatures, the real NET-2 verifier, receipt journal and
daemon (`DirectBackend`, in process). The chain is a fixed snapshot. These
tests check behaviour; they are not a security audit, and the intake is NOT
SECURITY_QUALIFIED.
"""

import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import bittensor as bt
import pytest
from bittensor.keyfiles import Keypair

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    DIGEST,
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
)

from carbon.battery import intake as ib
from carbon.battery import intake_client as ic
from carbon.battery.daemon import (
    AuthenticatedSubmission,
    submission_identity,
)
from carbon.chain.auth import BittensorHotkeyVerifier
from carbon.chain.models import MetagraphSnapshot, Participant
from carbon.development_session.chain_onboarding import (
    carbon_testnet_context,
)
from carbon.transport.store import ReceiptJournal

MINER = Keypair.create_from_uri("//Alice")
OTHER = Keypair.create_from_uri("//Charlie")
STRANGER = Keypair.create_from_uri("//Dave")
VALIDATOR = Keypair.create_from_uri("//Bob")
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "battery-fastcharge-ageing-development-v1",
    "backbone": "knn",
    "parameters": {"neighbours": 8},
}


def snapshot(block=100):
    return MetagraphSnapshot(
        carbon_testnet_context(),
        block,
        "0x" + f"{block:064x}",
        int(time.time() * 1000),
        (
            Participant(0, VALIDATOR.ss58_address, "cold-v", 1),
            Participant(1, MINER.ss58_address, "cold-m", 2),
            Participant(2, OTHER.ss58_address, "cold-o", 3),
        ),
    )


@pytest.fixture
def deployed(tmp_path, refs, backend):  # noqa: F811
    target = make(tmp_path, refs, backend)
    target.lock_path = str(tmp_path / "state.sqlite3.lock")
    window = ib.SnapshotWindow()
    window.add(snapshot())
    intake = ib.BatteryIntake(
        context=carbon_testnet_context(),
        receiver=VALIDATOR.ss58_address,
        journal=ReceiptJournal(
            tmp_path / "transport.sqlite3", carbon_testnet_context()
        ),
        verifier=BittensorHotkeyVerifier(),
        inbox=ib.Inbox(tmp_path / "inbox.sqlite3"),
        window=window,
        status_reader=target.outcome,
    )
    return intake, target


def facts(intake):
    answer = intake.public()
    assert answer.status == 200
    return answer.body


def signed(key, body, receiver=VALIDATOR):
    return bt.http_auth.sign(
        key,
        method="POST",
        path="/carbon/v1/mcp",
        body=body,
        receiver_ss58=receiver.ss58_address,
    )


def post(intake, key, body, peer="198.51.100.7", receiver=VALIDATOR):
    return intake.handle(
        "POST", "/carbon/v1/mcp", signed(key, body, receiver), body, peer
    )


def test_the_public_facts_carry_no_private_state(deployed):
    intake, _ = deployed
    body = facts(intake)
    assert body["receiver"] == VALIDATOR.ss58_address
    assert body["netuid"] == carbon_testnet_context().netuid
    assert body["tools"] == ["battery_submit", "battery_status"]
    assert body["commitment"].startswith("not_checked")
    assert body["qualification"] is False and body["reward"] is False
    text = json.dumps(body)
    for private in ("pscreen", "pfinal", "seed", "root", "case"):
        assert private not in text


def test_a_signed_submission_is_received_admitted_scored_and_readable(deployed):
    intake, target = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    answer = post(intake, MINER, body)
    assert answer.status == 202, answer
    expected = submission_identity(
        AuthenticatedSubmission(
            MINER.ss58_address, {}, STRATEGY["challenge_id"], "1.0", STRATEGY, DIGEST
        )
    )[1]
    assert answer.body == {"submission_id": expected, "state": "RECEIVED"}
    sid = answer.body["submission_id"]

    status = ic.status_message(facts(intake), sid, request="s1")
    assert post(intake, MINER, status).body == {
        "submission_id": sid,
        "state": "RECEIVED",
    }

    ib.work_once(intake.inbox, target)
    outcome = post(intake, MINER, ic.status_message(facts(intake), sid, request="s2"))
    assert outcome.status == 200
    assert outcome.body["state"] == "SCORED"
    assert outcome.body["qualification"] is False
    assert target.store.submission(sid)["hotkey"] == MINER.ss58_address


def test_another_hotkeys_submission_does_not_exist(deployed):
    intake, _ = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    sid = post(intake, MINER, body).body["submission_id"]
    probe = ic.status_message(facts(intake), sid, request="p1")
    assert post(intake, OTHER, probe).body == {"refused": "not_found"}


def test_an_unregistered_hotkey_is_refused_and_nothing_is_received(deployed):
    intake, _ = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    answer = post(intake, STRANGER, body)
    assert answer.status == 401
    assert answer.body == {"refused": "TRANSPORT_IDENTITY"}
    assert intake.inbox.received() == []


def test_a_request_signed_for_another_validator_is_refused(deployed):
    intake, _ = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    answer = post(intake, MINER, body, receiver=OTHER)
    assert answer.body == {"refused": "AUTH_WRONG_RECEIVER"}
    assert intake.inbox.received() == []


def test_a_resend_is_a_replay_and_the_same_recipe_is_the_same_submission(deployed):
    intake, _ = deployed
    first = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    sid = post(intake, MINER, first).body["submission_id"]
    assert post(intake, MINER, first).body == {"refused": "TRANSPORT_REPLAY"}
    again = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r2")
    assert post(intake, MINER, again).body["submission_id"] == sid
    assert len(intake.inbox.received()) == 1


class Exploding:
    """A chain reader that must never be called by a request."""

    calls = 0

    async def capture(self, context):
        Exploding.calls += 1
        raise AssertionError("a request caused a chain read")


def test_an_unknown_snapshot_is_refused_before_any_chain_read(deployed):
    intake, _ = deployed
    stale = dict(facts(intake), snapshot={"id": "sha256:" + "9" * 64})
    body = ic.submission_message(stale, STRATEGY, DIGEST, request="r1")
    answer = post(intake, MINER, body)
    assert answer.body == {"refused": "snapshot_unknown"}
    assert Exploding.calls == 0
    # The specimen: the only chain reader is the refresher's, and it is the
    # one that would call this reader.
    stop = threading.Event()
    stop.set()
    ib.refresher(intake.window, carbon_testnet_context(), reader=Exploding(), stop=stop)
    assert Exploding.calls == 0


def test_the_refresher_is_the_only_chain_reader():
    class Once:
        calls = 0

        async def capture(self, context):
            Once.calls += 1
            stop.set()
            return snapshot(200)

    window, stop = ib.SnapshotWindow(), threading.Event()
    ib.refresher(window, carbon_testnet_context(), reader=Once(), stop=stop, period=0)
    assert Once.calls == 1
    assert window.latest().finalized_block == 200


def test_limits_apply_before_authentication(deployed):
    intake, _ = deployed
    answers = [
        intake.handle("POST", "/carbon/v1/mcp", {}, b"not a message", "203.0.113.9")
        for _ in range(ib.PEER_BURST + 1)
    ]
    assert [a.status for a in answers[:-1]] == [400] * ib.PEER_BURST
    assert answers[-1].body == {"refused": "rate"}
    assert intake.handle("GET", "/other", {}, b"", "203.0.113.10").status == 404


def test_a_stale_window_answers_unavailable_not_a_refusal(deployed):
    intake, _ = deployed
    intake.window.clock = lambda: time.time() + 3600
    assert intake.public().body == {"refused": "snapshot_unavailable"}


def test_the_listener_binds_loopback_unless_the_exposure_is_recorded(tmp_path):
    (tmp_path / ".agent").mkdir()
    decisions = tmp_path / ".agent" / "DECISIONS.md"
    decisions.write_text(
        "## 2026-09-30 — OWNER-BATTERY-INTAKE-01: the intake path is chosen\n"
    )
    base = {"host": "0.0.0.0"}
    # Another owner decision, even the one that chose the intake, is not an
    # exposure record.
    for record in (None, "OWNER-INTAKE-EXPOSURE-01", "OWNER-BATTERY-INTAKE-01"):
        with pytest.raises(ib.IntakeUnavailable) as refused:
            ib.require_exposure(
                {**base, "exposure_record": record}, repository=tmp_path
            )
        assert refused.value.code == "intake_exposure_unrecorded"
    decisions.write_text(
        "## 2026-09-30 — OWNER-INTAKE-EXPOSURE-01: expose the battery intake\n"
    )
    ib.require_exposure(
        {**base, "exposure_record": "OWNER-INTAKE-EXPOSURE-01"}, repository=tmp_path
    )
    ib.require_exposure({"host": "127.0.0.1"}, repository=tmp_path)


def test_the_client_has_no_signing_code():
    source = (REPOSITORY / "carbon/battery/intake_client.py").read_text()
    code = source.split('"""', 2)[2]  # past the docstring's usage example
    for forbidden in ("http_auth", "Keypair", "Wallet", "keyfile", ".sign("):
        assert forbidden not in code
    # Specimen: the docstring shows the miner's own signing call, so the
    # search is looking at real text.
    assert "http_auth.sign" in source.split('"""', 2)[1]


def test_one_submission_over_real_http(deployed):
    intake, target = deployed
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ib._handler(intake))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        public = ic.read_intake(url)
        body = ic.submission_message(public, STRATEGY, DIGEST, request="h1")
        status, answer = ic.post(url, body, signed(MINER, body))
        assert (status, answer["state"]) == (202, "RECEIVED")
        ib.work_once(intake.inbox, target)
        poll = ic.status_message(public, answer["submission_id"], request="h2")
        status, outcome = ic.post(url, poll, signed(MINER, poll))
        assert (status, outcome["state"]) == (200, "SCORED")
        status, refused = ic.post(url, b"x" * (ib.MAX_BODY + 1), {})
        assert (status, refused) == (413, {"refused": "body"})
    finally:
        httpd.shutdown()
        httpd.server_close()
