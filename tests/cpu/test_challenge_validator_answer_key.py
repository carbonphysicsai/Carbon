"""The shared answer key end to end (VALIDATOR-19 slice 2).

Carbon's producer (its own synthetic root) seals and publishes a battery batch.
The distribution service serves it to a permit holder, and an import-only
validator (another root) verifies and imports it. Everything runs in process:
- a scripted `btauth/1` verifier and signer;
- a scripted permit read;
- synthetic terminal references.
There is no chain, network, container or spend. The checks are signing,
verification, admission, logging and refusal. Not a security audit
(AGENTS.md §13).
"""

import json
import os
import pickle
import sys
from pathlib import Path

import pytest

from carbon.battery import exam, seeds, worker
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import PoolStore, StateError
from carbon.chain.auth import AuthCode, AuthenticatedHotkey, AuthFailure
from carbon.chain.external_signer import SignerFailure
from carbon.chain.models import ChainContext, ChainFailure, FailureCode
from carbon.chain.permits import PermitUnavailable, ValidatorPermitReader
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import distribution as dist
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery import BatteryAdapter, BatteryBatchSource

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_producer import SIZE, scripted_solve

V2 = exam.DEVELOPMENT_RULE_V2
RECEIVER = "5Distribution"
VALIDATOR = "5Validator"
OUTSIDER = "5Outsider"


def battery_validator(directory, *, import_only=False):
    directory.mkdir(mode=0o700)
    root = seeds.PrivateRoot.create(directory / "root.bin")
    journal = seeds.SeedJournal(directory / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "0" * 64, rule_digest(V2)))
    target = BatteryValidator(
        store=PoolStore(directory / "state.sqlite3", rule=V2),
        backend=worker.DirectBackend(REPOSITORY),
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
        import_only=import_only,
    )
    target.start()
    target.lock_path = str(directory / "state.sqlite3.lock")
    target.readonly = False
    return BatteryAdapter(target)


@pytest.fixture
def published(tmp_path):
    """The producer's outbox package for one sealed screening batch."""
    source = BatteryBatchSource(
        battery_validator(tmp_path / "producer-state"),
        overlay=tmp_path / "overlay",
        runner=scripted_solve,
    )
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    challenge = source.challenge_id
    drawn = producer.draw(challenge, "pscreen-K01", kind="screening", size=SIZE)
    producer.solve(challenge, drawn["fingerprint"])
    producer.seal(challenge, drawn["fingerprint"])
    # Rule v2's cadence: slot 1 is blocks [1080, 4320), scheduled at block 0.
    producer.schedule(challenge, drawn["fingerprint"], 1, block=0)
    result = producer.publish(challenge, drawn["fingerprint"])
    path = tmp_path / "producer" / "outbox" / challenge / result["file"]
    return {
        "key": key,
        "producer": producer,
        "source": source,
        "value": json.loads(path.read_text()),
        "path": path,
    }


# -- packages -------------------------------------------------------------------------------


def test_a_published_package_verifies_and_is_owner_only(published):
    key = published["key"]
    commitment, payload = ak.verify(published["value"], key.public_key)
    assert commitment["kind"] == "screening"
    assert set(payload) == {"document", "references", "reconstruction_salt"}
    assert os.lstat(published["path"]).st_mode & 0o077 == 0
    # Publishing again writes the same bytes and journals nothing new.
    producer, source = published["producer"], published["source"]
    producer.publish(source.challenge_id, commitment["fingerprint"])
    events = [e["event"] for e in producer.journal.entries()]
    assert events == ["drawn", "sealed", "scheduled", "published"]


def tampered(value, change):
    copy = json.loads(json.dumps(value))
    change(copy)
    return copy


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            lambda v: v["payload"]["references"].popitem(),
            "answer_key_payload_mismatch",
        ),
        (
            lambda v: v["manifest"]["commitment"].update(cases=1),
            "answer_key_signature",
        ),
        (lambda v: v.update(signature="00" * 64), "answer_key_signature"),
        (lambda v: v.pop("manifest"), "answer_key_malformed"),
    ],
)
def test_a_tampered_package_is_refused(published, change, code):
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.verify(tampered(published["value"], change), published["key"].public_key)
    assert refused.value.code == code


def test_another_producer_key_is_refused(tmp_path, published):
    other = ak.ProducerKey.create(tmp_path / "other.key")
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.verify(published["value"], other.public_key)
    assert refused.value.code == "answer_key_wrong_producer"


def test_a_producer_only_kind_is_never_packaged(published):
    commitment = dict(published["value"]["manifest"]["commitment"], kind="tuning")
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.package(published["key"], commitment, published["value"]["payload"])
    assert refused.value.code == "answer_key_kind_not_served"


def test_the_key_never_prints_or_pickles(published):
    assert "redacted" in repr(published["key"])
    with pytest.raises(TypeError):
        pickle.dumps(published["key"])


# -- the distribution host ------------------------------------------------------------------


class ScriptedVerifier:
    """`btauth/1`, scripted: the hotkey and nonce ride in two headers."""

    def verify(self, headers, body, *, method, path, receiver, now_ns, nonce_store):
        assert (method, path, receiver) == ("POST", ak.PATH, RECEIVER)
        hotkey = headers.get("X-Hotkey")
        if hotkey is None:
            raise AuthFailure(AuthCode.SIGNATURE)
        nonce = int(headers["X-Nonce"])
        if not nonce_store.check_and_store(hotkey, nonce):
            raise AuthFailure(AuthCode.REPLAY)
        return AuthenticatedHotkey(hotkey, nonce)


class Permits:
    def __init__(self, table):
        self.table = table

    def read(self, hotkey):
        found = self.table.get(hotkey, "unregistered")
        if found == "down":
            raise PermitUnavailable("permit_read_failed")
        if found == "unregistered":
            return None
        return {"permit": found, "block": 1234}


@pytest.fixture
def host(tmp_path, published):
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    (inbox / published["path"].name).write_text(json.dumps(published["value"]))
    (inbox / published["path"].name).chmod(0o600)
    service = dist.DistributionService(
        dist.Inbox(inbox, published["key"].public_key),
        receiver=RECEIVER,
        verifier=ScriptedVerifier(),
        permits=Permits({VALIDATOR: True, OUTSIDER: False}),
        nonces=dist.NonceStore(tmp_path / "nonces.sqlite3"),
        log=dist.FetchLog(tmp_path / "fetch.jsonl"),
    )
    return {"service": service, "inbox": inbox, "log": tmp_path / "fetch.jsonl"}


def fetcher(service, hotkey):
    counter = iter(range(1, 10**6))

    def sign(body, *, receiver, nonce_ns, path):
        return {"X-Hotkey": hotkey, "X-Nonce": str(next(counter))}

    def post(url, body, headers):
        return service.handle(headers, body)

    return ak.Fetcher("http://127.0.0.1:1", None, RECEIVER, post=post, sign=sign)


def entries(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_a_permit_holder_lists_then_fetches(host, published):
    challenge = published["source"].challenge_id
    asker = fetcher(host["service"], VALIDATOR)
    listed = asker.ask(challenge)["packages"]
    assert len(listed) == 1 and "payload" not in listed[0]
    fingerprint = ak.verify_manifest(listed[0], published["key"].public_key)[
        "fingerprint"
    ]
    package = asker.ask(challenge, fingerprint)["package"]
    assert package == published["value"]
    log = entries(host["log"])
    assert [(e["hotkey"], e["verdict"]) for e in log] == [
        (VALIDATOR, "LISTED"),
        (VALIDATOR, "SERVED"),
    ]
    assert log[1]["fingerprint"] == fingerprint and log[1]["block"] == 1234


@pytest.mark.parametrize(
    ("hotkey", "table", "code"),
    [
        (OUTSIDER, None, "answer_key_no_validator_permit"),
        ("5Stranger", None, "answer_key_no_validator_permit"),
        (VALIDATOR, {VALIDATOR: "down"}, "answer_key_chain_unavailable"),
    ],
)
def test_no_permit_no_answer_key(host, published, hotkey, table, code):
    if table is not None:
        host["service"].permits = Permits(table)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        fetcher(host["service"], hotkey).ask(published["source"].challenge_id)
    assert refused.value.code == code
    [entry] = entries(host["log"])
    assert (entry["hotkey"], entry["verdict"]) == (hotkey, code)


def test_an_unsigned_or_replayed_request_is_refused(host, published):
    service = host["service"]
    body = json.dumps(
        {
            "schema": ak.REQUEST_SCHEMA,
            "challenge_id": published["source"].challenge_id,
            "fingerprint": None,
        }
    ).encode()
    assert service.handle({}, body) == (401, {"refused": "AUTH_BAD_SIGNATURE"})
    headers = {"X-Hotkey": VALIDATOR, "X-Nonce": "7"}
    assert service.handle(headers, body)[0] == 200
    assert service.handle(headers, body) == (401, {"refused": "AUTH_REPLAY"})


def test_an_unverifiable_inbox_file_is_never_served(host, published):
    forged = tampered(
        published["value"], lambda v: v["payload"]["references"].popitem()
    )
    path = host["inbox"] / "forged.json"
    path.write_text(json.dumps(forged))
    path.chmod(0o600)
    packages, skipped = host["service"].inbox.packages(published["source"].challenge_id)
    assert skipped == 1 and list(packages.values()) == [published["value"]]


# -- the validator's import -----------------------------------------------------------------


def test_an_import_only_validator_imports_the_shared_batch(tmp_path, host, published):
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    challenge = published["source"].challenge_id
    asker = fetcher(host["service"], VALIDATOR)
    key = published["key"].public_key
    first = ak.sync(adapter, asker, key, challenge)
    assert [p["state"] for p in first["packages"]] == ["IMPORTED"]
    commitment = published["value"]["manifest"]["commitment"]
    # Same cases and the same references digest as the producer's.
    row = adapter.target.store.batch(commitment["fingerprint"])
    assert row["references_digest"] == commitment["references_digest"]
    assert row["document"] == published["value"]["payload"]["document"]
    again = ak.sync(adapter, asker, key, challenge)
    assert [p["state"] for p in again["packages"]] == ["HELD"]
    # It never draws one itself.
    with pytest.raises(StateError) as refused:
        adapter.target.prepare_batch("pscreen-own", kind="screening", count=SIZE)
    assert refused.value.code == "batch_import_only"


def test_sync_runs_through_the_real_signer_and_verifier(tmp_path, published):
    """3a at r2: `answer_key sync` signs with the validator's own signer,
    started for the answer-key fetch to the distribution host's receiver, and
    the host checks it with the real `btauth/1` verifier. No signing or
    verifying is scripted here."""
    from _signer_harness import in_thread_signer
    from bittensor.keyfiles import Keypair

    from carbon.chain.auth import BittensorHotkeyVerifier

    validator = Keypair.create_from_uri("//carbon-answer-key-validator")
    receiver = Keypair.create_from_uri("//carbon-answer-key-host").ss58_address
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    (inbox / published["path"].name).write_text(json.dumps(published["value"]))
    (inbox / published["path"].name).chmod(0o600)
    service = dist.DistributionService(
        dist.Inbox(inbox, published["key"].public_key),
        receiver=receiver,
        verifier=BittensorHotkeyVerifier(),
        permits=Permits({validator.ss58_address: True}),
        nonces=dist.NonceStore(tmp_path / "nonces.sqlite3"),
        log=dist.FetchLog(tmp_path / "fetch.jsonl"),
    )

    def post(url, body, headers):
        return service.handle(headers, body)

    adapter = battery_validator(tmp_path / "validator", import_only=True)
    challenge = published["source"].challenge_id
    key = published["key"].public_key
    with in_thread_signer(
        validator, receivers=[receiver], requests=["answer-key"]
    ) as signer:
        asker = ak.Fetcher("http://127.0.0.1:1", signer, receiver, post=post)
        synced = ak.sync(adapter, asker, key, challenge)
        assert [p["state"] for p in synced["packages"]] == ["IMPORTED"]
        assert signer.issued >= 2  # the listing, then the package
    # A signer started as a miner's (the default) refuses the fetch by name.
    with in_thread_signer(validator) as miners_default:
        asker = ak.Fetcher("http://127.0.0.1:1", miners_default, receiver, post=post)
        with pytest.raises(SignerFailure) as refused:
            ak.sync(adapter, asker, key, challenge)
        assert refused.value.refusal == "NOT_A_CARBON_REQUEST"


def test_silent_clients_never_freeze_the_host(tmp_path, published, capsys, monkeypatch):
    """3a, 2026-10-08: the host's first listener ran every TLS handshake
    inside `accept`, so one client that connected and sent nothing froze it
    (`LISTEN 6 5`). Now silent connections wait in their own threads, a real
    signed fetch over TLS still succeeds at once, a connection over the
    per-peer cap is refused, and each refused or timed-out connection is one
    log line."""
    import socket
    import threading
    import time

    from _signer_harness import in_thread_signer
    from bittensor.keyfiles import Keypair
    from test_battery_validator_service import self_signed

    from carbon.battery import intake as ib
    from carbon.chain.auth import BittensorHotkeyVerifier

    monkeypatch.setattr(ib.LoggedHandler, "timeout", 2.0)
    validator = Keypair.create_from_uri("//carbon-answer-key-validator")
    receiver = Keypair.create_from_uri("//carbon-answer-key-host").ss58_address
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    (inbox / published["path"].name).write_text(json.dumps(published["value"]))
    (inbox / published["path"].name).chmod(0o600)
    service = dist.DistributionService(
        dist.Inbox(inbox, published["key"].public_key),
        receiver=receiver,
        verifier=BittensorHotkeyVerifier(),
        permits=Permits({validator.ss58_address: True}),
        nonces=dist.NonceStore(tmp_path / "nonces.sqlite3"),
        log=dist.FetchLog(tmp_path / "fetch.jsonl"),
    )
    tls = tmp_path / "tls"
    tls.mkdir(mode=0o700)
    cert, key = self_signed(tls)
    config = {
        "host": "127.0.0.1",
        "port": 0,
        "tls_cert": str(cert),
        "tls_key": str(key),
    }
    server = dist.make_server(service, config)
    assert server.request_queue_size == ib.LISTEN_BACKLOG
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    silent = []
    try:
        # Three clients connect and never start a handshake (one under the
        # per-peer cap, so this peer's own fetch still has a slot).
        silent = [socket.create_connection(("127.0.0.1", port)) for _ in range(3)]
        with in_thread_signer(
            validator, receivers=[receiver], requests=["answer-key"]
        ) as signer:
            asker = ak.Fetcher(
                f"https://127.0.0.1:{port}", signer, receiver, ca=str(cert)
            )
            started = time.monotonic()
            listing = asker.ask(published["source"].challenge_id)
            assert time.monotonic() - started < 2.0
            assert listing["packages"]
            # A fifth connection from this peer, with four open, is refused.
            asker_slot = socket.create_connection(("127.0.0.1", port))
            extra = socket.create_connection(("127.0.0.1", port))
            extra.settimeout(5.0)
            assert extra.recv(1) == b""
            extra.close()
            asker_slot.close()
        # The silent clients are closed by the host after the socket timeout.
        for connection in silent:
            connection.settimeout(10.0)
            assert connection.recv(1) == b""
    finally:
        for connection in silent:
            connection.close()
        server.shutdown()
        server.server_close()
    lines = [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("{")
    ]
    events = [x["event"] for x in lines if x["service"] == dist.SERVICE]
    assert events.count("connection_refused") >= 1
    assert events.count("connection_timed_out") >= 3
    assert "127.0.0.1" not in json.dumps(lines)


def test_a_window_opens_on_the_chain_clock_without_a_submission(
    tmp_path, host, published
):
    """3a at r3: a pool whose only submission was received before its
    window's start stayed ROTATION_PENDING after the window opened. The sync
    now advances the clock with the finalized head (slot 1 is blocks
    [1080, 4320))."""
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    adapter.target.store.open_pool()  # `operate open`: a windowed pool opens empty
    challenge = published["source"].challenge_id
    asker = fetcher(host["service"], VALIDATOR)
    key = published["key"].public_key
    early = ak.sync(adapter, asker, key, challenge, head=500)
    assert [p["state"] for p in early["packages"]] == ["IMPORTED"]
    assert early["clock"] == {"block": 500, "pool": "ROTATION_PENDING", "version": 0}
    opened = ak.sync(adapter, asker, key, challenge, head=1080)
    assert opened["clock"] == {"block": 1080, "pool": "OPEN", "version": 1}
    fingerprint = published["value"]["manifest"]["commitment"]["fingerprint"]
    assert adapter.target.store.pool()["active"] == [fingerprint]
    # The head never moves backwards, and an older read rotates nothing.
    again = ak.sync(adapter, asker, key, challenge, head=900)
    assert again["clock"]["pool"] == "OPEN" and again["clock"]["version"] == 1
    # Past the window's end, the pool keeps scoring its batches (never stalls).
    late = ak.sync(adapter, asker, key, challenge, head=4320)
    assert late["clock"]["pool"] == "OPEN"
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.observe_head(-1)
    assert refused.value.code == "answer_key_chain_head_malformed"


def test_the_clock_reads_the_deployments_own_chain(tmp_path, monkeypatch):
    from carbon.chain import permits

    deployment = tmp_path / "deployment.json"
    deployment.write_text(json.dumps({"schema": "x"}))
    assert ak.finalized_head(deployment) is None  # no chain reader: no clock
    chain = {
        "network": "testnet",
        "endpoint": "wss://test.finney.opentensor.ai:443",
        "provider": "bittensor-official-test",
        "genesis_hash": "0x" + "8" * 64,
        "netuid": 567,
    }
    deployment.write_text(json.dumps({"commitment_reader": chain}))
    seen = []

    def head(context, **kwargs):
        seen.append(context.netuid)
        return 1234

    monkeypatch.setattr(permits, "finalized_block", head)
    assert ak.finalized_head(deployment) == 1234 and seen == [567]

    def down(context, **kwargs):
        raise permits.PermitUnavailable("head_read_failed")

    monkeypatch.setattr(permits, "finalized_block", down)
    assert ak.finalized_head(deployment) is None


def resigned(published, *, commitment=None, payload=None):
    value = published["value"]
    return ak.verify(
        ak.package(
            published["key"],
            commitment or value["manifest"]["commitment"],
            payload or value["payload"],
        ),
        published["key"].public_key,
    )


@pytest.mark.parametrize(
    ("commitment_change", "payload_change", "code"),
    [
        ({"rule_digest": "sha256:" + "1" * 64}, None, "answer_key_identity_mismatch"),
        ({"references_digest": "sha256:" + "2" * 64}, None, "answer_key_references_mismatch"),
        ({"fingerprint": "sha256:" + "3" * 64}, None, "answer_key_fingerprint_mismatch"),
        (None, "drop_reference", "answer_key_references_mismatch"),
        (None, "change_reference", "answer_key_references_mismatch"),
    ],
)  # fmt: skip
def test_a_correctly_signed_but_wrong_package_imports_nothing(
    tmp_path, published, commitment_change, payload_change, code
):
    """The producer's signature is not enough: the validator re-derives the
    fingerprint and references digest itself."""
    value = published["value"]
    commitment = dict(value["manifest"]["commitment"], **(commitment_change or {}))
    payload = json.loads(json.dumps(value["payload"]))
    references = payload["references"]
    if payload_change == "drop_reference":
        references.pop(min(references))
    elif payload_change == "change_reference":
        first = min(references)
        references[first] = dict(references[first], status="REFERENCE_TIMEOUT")
    commitment, payload = resigned(published, commitment=commitment, payload=payload)
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(commitment, payload)
    assert refused.value.code == code
    assert adapter.target.store.batches() == []


# -- the permit read ------------------------------------------------------------------------


CONTEXT = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)


@pytest.mark.parametrize(
    ("found", "expected"),
    [
        ((True, True, 9), {"permit": True, "block": 9}),
        ((True, False, 9), {"permit": False, "block": 9}),
        ((False, False, 9), None),
    ],
)
def test_the_permit_read(found, expected):
    async def fetch(context, hotkey):
        return found

    assert ValidatorPermitReader(CONTEXT, fetch=fetch).read("5Any") == expected


def test_a_chain_failure_is_infrastructure():
    async def fetch(context, hotkey):
        raise ChainFailure(FailureCode.UNAVAILABLE)

    with pytest.raises(PermitUnavailable):
        ValidatorPermitReader(CONTEXT, fetch=fetch).read("5Any")
