"""Explicit intake context keeps the existing signed NET-2 identity boundary."""

import asyncio
import json
import sqlite3
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from carbon.battery import campaign, intake_client, remote_submission
from carbon.battery.challenge import CHALLENGE
from carbon.battery.intake import PUBLIC_SCHEMA
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.auth import AuthCode, AuthenticatedHotkey, AuthFailure
from carbon.development_session.chain_onboarding import carbon_testnet_context
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import (
    TransportCode,
    TransportFailure,
    digest,
    parse_message,
)
from carbon.transport.store import ReceiptJournal

NOW = 100_000_000_000
FINNEY = ChainContext(
    "finney", "wss://finney.example.org", "configured", "0x" + "a" * 64, 42
)


def facts(context):
    return {
        "schema": PUBLIC_SCHEMA,
        "network": context.network,
        "genesis": context.genesis_hash,
        "netuid": context.netuid,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "snapshot": {"id": "0x" + "b" * 64},
        "receiver": "validator",
        "path": "/carbon/v1/mcp",
    }


def body(public, *, context=None, request="context-test"):
    return intake_client.submission_message(
        public,
        {"challenge_id": CHALLENGE.challenge_id},
        "sha256:" + "c" * 64,
        request=request,
        context=context,
    )


def test_explicit_context_selects_network_without_changing_testnet_default():
    default = parse_message(body(facts(carbon_testnet_context())))
    assert (default["network"], default["genesis"], default["netuid"]) == (
        carbon_testnet_context().network,
        carbon_testnet_context().genesis_hash,
        carbon_testnet_context().netuid,
    )
    selected = parse_message(body(facts(FINNEY), context=FINNEY))
    assert (selected["network"], selected["genesis"], selected["netuid"]) == (
        FINNEY.network,
        FINNEY.genesis_hash,
        FINNEY.netuid,
    )
    status = parse_message(
        intake_client.status_message(
            facts(FINNEY), "submission-1", request="status-1", context=FINNEY
        )
    )
    assert status["network"] == FINNEY.network
    assert status["fields"] == {"submission_id": "submission-1"}


@pytest.mark.parametrize(
    "change",
    [
        {"network": "testnet"},
        {"genesis": "0x" + "d" * 64},
        {"netuid": 43},
    ],
)
def test_wrong_public_chain_identity_refuses_before_message_or_signature(change):
    with pytest.raises(intake_client.IntakeMismatch, match="another chain"):
        body({**facts(FINNEY), **change}, context=FINNEY)
    with pytest.raises(intake_client.IntakeMismatch, match="another chain"):
        body(facts(FINNEY))
    with pytest.raises(intake_client.IntakeMismatch, match="configured chain context"):
        body(facts(FINNEY), context=object())


class Adapter:
    def __init__(self, state):
        self.state = state

    async def observe(self, *, minimum_finalized_block):
        return self.state


class Verifier:
    """Offline signer stand-in: binds exactly the bytes and receiving hotkey."""

    def verify(self, headers, data, *, method, path, receiver, now_ns, nonce_store):
        if headers["body"] != digest(data):
            raise AuthFailure(AuthCode.SIGNATURE)
        if headers["receiver"] != receiver:
            raise AuthFailure(AuthCode.RECEIVER)
        nonce = int(headers["nonce"])
        if not nonce_store.check_and_store(headers["hotkey"], nonce):
            raise AuthFailure(AuthCode.REPLAY)
        return AuthenticatedHotkey(headers["hotkey"], nonce)


def headers(data, *, receiver="validator", nonce=NOW):
    return {
        "body": digest(data),
        "receiver": receiver,
        "nonce": str(nonce),
        "hotkey": "miner",
    }


def receipt_count(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT count(*) FROM receipt").fetchone()[0]


def test_selected_context_and_receiver_are_verified_before_receipt(tmp_path):
    state = MetagraphSnapshot(
        FINNEY,
        10,
        facts(FINNEY)["snapshot"]["id"],
        NOW // 1_000_000,
        (Participant(0, "validator", "owner", 1), Participant(1, "miner", "cold", 2)),
    )
    journal = ReceiptJournal(tmp_path / "receipts.sqlite", FINNEY)
    gate = AuthenticatedGateway(
        FINNEY,
        CHALLENGE,
        "validator",
        Adapter(state),
        Verifier(),
        journal,
        clock_ns=lambda: NOW,
    )
    selected = body(
        {**facts(FINNEY), "snapshot": {"id": state.snapshot_id}}, context=FINNEY
    )
    with pytest.raises(AuthFailure) as wrong_receiver:
        asyncio.run(gate.receive(selected, headers(selected, receiver="other")))
    assert wrong_receiver.value.code is AuthCode.RECEIVER
    assert receipt_count(journal.path) == 0

    wrong_context = replace(FINNEY, netuid=43)
    alien = body(facts(wrong_context), context=wrong_context, request="alien")
    with pytest.raises(TransportFailure) as wrong_chain:
        asyncio.run(gate.receive(alien, headers(alien)))
    assert wrong_chain.value.code is TransportCode.CONTEXT
    assert receipt_count(journal.path) == 0

    received = asyncio.run(gate.receive(selected, headers(selected)))
    assert (received.receipt.hotkey, received.receipt.uid) == ("miner", 1)
    assert received.call.tool == "battery_submit"
    assert receipt_count(journal.path) == 1


def test_campaign_remote_submit_and_status_forward_selected_context(
    tmp_path, monkeypatch
):
    tmp_path.chmod(0o700)
    public = facts(FINNEY)
    signed, posted = [], []

    def sign(_signer, _facts, data):
        signed.append(data)
        return {"fixture": digest(data)}

    def post(_url, data, headers):
        assert headers == {"fixture": digest(data)}
        envelope = parse_message(data)
        posted.append(envelope)
        assert (envelope["network"], envelope["genesis"], envelope["netuid"]) == (
            FINNEY.network,
            FINNEY.genesis_hash,
            FINNEY.netuid,
        )
        if envelope["tool"] == "battery_submit":
            return 202, {"submission_id": "submitted-1"}
        return 200, {"submission_id": "submitted-1", "state": "SCORED"}

    monkeypatch.setattr(remote_submission, "_signed", sign)
    result = campaign.submit_through_intake(
        "https://validator.example.org",
        object(),
        root=tmp_path,
        epoch=1,
        strategy={"challenge_id": CHALLENGE.challenge_id},
        contract_digest="sha256:" + "c" * 64,
        read=lambda _url: public,
        post=post,
        receiver="validator",
        context=FINNEY,
    )
    assert result[1]["state"] == "SCORED"
    assert [item["tool"] for item in posted] == ["battery_submit", "battery_status"]
    assert len(signed) == 2
    saved = json.loads(remote_submission._record_path(tmp_path, 1).read_bytes())
    assert saved["schema"] == remote_submission.CONTEXT_RECORD_SCHEMA
    assert saved["context"]["genesis_hash"] == FINNEY.genesis_hash

    monkeypatch.setattr(remote_submission, "_status_read_signed", sign)
    signed.clear()
    posted.clear()
    queued = remote_submission.read_status_once(
        "https://validator.example.org",
        object(),
        root=tmp_path,
        epoch=1,
        read=lambda _url: public,
        post=post,
        receiver="validator",
    )
    assert queued[1]["state"] == "SCORED"
    assert [item["tool"] for item in posted] == ["battery_status"]
    assert len(signed) == 1

    epoch_dir = tmp_path / "epoch-1"
    epoch_dir.mkdir()
    (epoch_dir / "selected-recipe.json").write_text(
        json.dumps({"strategy": {"challenge_id": CHALLENGE.challenge_id}}),
        encoding="utf-8",
    )
    (tmp_path / "campaign-manifest.json").write_text("{}", encoding="utf-8")
    signed.clear()
    posted.clear()
    feedback = campaign.queued_verdict(
        SimpleNamespace(
            intakes={CHALLENGE.challenge_id: "https://validator.example.org"},
            receivers={CHALLENGE.challenge_id: "validator"},
            validators={},
        ),
        tmp_path,
        1,
        lambda: object(),
        now=10_000,
        floor=0,
        read=lambda _url: public,
        post=post,
    )
    assert feedback is not None
    assert [item["tool"] for item in posted] == ["battery_status"]
    assert len(signed) == 1

    signed.clear()
    posted.clear()
    with pytest.raises(remote_submission.IntakeRefusal, match="intake_changed"):
        remote_submission.read_status_once(
            "https://validator.example.org",
            object(),
            root=tmp_path,
            epoch=1,
            read=lambda _url: public,
            post=post,
            receiver="validator",
            context=replace(FINNEY, netuid=43),
        )
    with pytest.raises(intake_client.IntakeMismatch, match="another chain"):
        remote_submission.read_status_once(
            "https://validator.example.org",
            object(),
            root=tmp_path,
            epoch=1,
            read=lambda _url: {**public, "netuid": 43},
            post=post,
            receiver="validator",
        )
    assert signed == posted == []

    signed.clear()
    posted.clear()
    with pytest.raises(
        remote_submission.IntakeRefusal, match="intake_receiver_mismatch"
    ):
        campaign.submit_through_intake(
            "https://validator.example.org",
            object(),
            root=tmp_path,
            epoch=2,
            strategy={"challenge_id": CHALLENGE.challenge_id},
            contract_digest="sha256:" + "c" * 64,
            read=lambda _url: {**public, "receiver": "other"},
            post=post,
            receiver="validator",
            context=FINNEY,
        )
    assert signed == posted == []


def test_saved_context_controls_resume_and_not_found_resend(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    public = facts(FINNEY)
    strategy = {"challenge_id": CHALLENGE.challenge_id}
    contract_digest = "sha256:" + "c" * 64
    signer = SimpleNamespace(ss58_address="miner")
    submission_id = intake_client.submission_id(
        signer.ss58_address, strategy, contract_digest
    )
    record = remote_submission._record_path(tmp_path, 1)
    record.write_text(
        json.dumps(
            {
                "schema": remote_submission.CONTEXT_RECORD_SCHEMA,
                "context": asdict(FINNEY),
                "url": "https://validator.example.org",
                "epoch": 1,
                "submission_id": submission_id,
            }
        ),
        encoding="utf-8",
    )
    record.chmod(0o600)
    signed, posted = [], []

    def sign(_signer, _facts, data):
        signed.append(parse_message(data)["tool"])
        return {"fixture": digest(data)}

    def post(_url, data, headers):
        assert headers == {"fixture": digest(data)}
        envelope = parse_message(data)
        assert (envelope["network"], envelope["genesis"], envelope["netuid"]) == (
            FINNEY.network,
            FINNEY.genesis_hash,
            FINNEY.netuid,
        )
        posted.append(envelope["tool"])
        if posted == ["battery_status"]:
            return 404, {"refused": "not_found"}
        if envelope["tool"] == "battery_submit":
            return 202, {"submission_id": submission_id}
        return 200, {"submission_id": submission_id, "state": "SCORED"}

    monkeypatch.setattr(remote_submission, "_signed", sign)
    status, answer, found_id = campaign.submit_through_intake(
        "https://validator.example.org",
        signer,
        root=tmp_path,
        epoch=1,
        strategy=strategy,
        contract_digest=contract_digest,
        read=lambda _url: public,
        post=post,
        receiver="validator",
    )
    assert (status, answer["state"], found_id) == (200, "SCORED", submission_id)
    assert posted == signed == ["battery_status", "battery_submit", "battery_status"]
