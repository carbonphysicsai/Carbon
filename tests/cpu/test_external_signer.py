"""The miner's signer and Carbon's client, across the real process boundary.

A real `python -m carbon_miner_signer` process, holding an encrypted specimen
hotkey whose password is typed into its own terminal (a pty), signs Carbon
requests that Carbon's own verifier then authenticates. Every failure Carbon
can see is its own closed code. And neither the password nor any decrypted key
material appears anywhere Carbon or the signer writes - shown with the
credential itself as the specimen, found where it really is.

The specimen key is derived from a public development URI and the password is
a fixed test string: neither is a credential of anyone's.
"""

import json
import os
import pty
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from carbon.chain.auth import BittensorHotkeyVerifier, BittensorMessageSigner
from carbon.chain.external_signer import (
    SignerCode,
    SignerFailure,
    connect_signer,
    default_socket,
)

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "specimen-password-4c1e9b"
URI = "//carbon-external-signer-specimen"
RECEIVER_URI = "//carbon-external-signer-receiver"


def _keypair(uri):
    from bittensor.keyfiles import Keypair

    return Keypair.create_from_uri(uri)


class _NonceStore:
    def __init__(self):
        self.seen = set()

    def check_and_store(self, hotkey, nonce):
        if (hotkey, nonce) in self.seen:
            return False
        self.seen.add((hotkey, nonce))
        return True


def _short_dir():
    # A Unix socket path is limited to ~104 bytes; pytest's tmp_path can exceed it.
    return Path(tempfile.mkdtemp(prefix="cs-", dir="/tmp"))


class SignerProcess:
    """`carbon-miner-signer` as a miner runs it: its own process and terminal."""

    def __init__(self, key_file, socket_path, *extra):
        self.socket_path = socket_path
        master, slave = pty.openpty()
        self.master = master
        self.output = b""
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "carbon_miner_signer",
                "--key-file",
                str(key_file),
                "--socket",
                str(socket_path),
                *extra,
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=ROOT,
        )
        os.close(slave)
        self.typed = b""

    def read(self, until=None, timeout=60.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if until is not None and until in self.output:
                return
            ready, _, _ = select.select([self.master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(self.master, 4096)
                except OSError:
                    return
                if not chunk:
                    return
                self.output += chunk
            elif self.process.poll() is not None and until is not None:
                return
        if until is not None:
            raise AssertionError(f"signer never printed {until!r}: {self.output!r}")

    def type_password(self, password):
        self.read(until=b"password")
        self.typed += password.encode() + b"\n"
        os.write(self.master, password.encode() + b"\n")

    def wait_listening(self):
        self.read(until=b"listening on")

    def stop(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.read(timeout=1.0)
        os.close(self.master)


@pytest.fixture
def specimen_key(tmp_path):
    from bittensor.keyfiles import Keyfile

    pair = _keypair(URI)
    path = tmp_path / "wallets" / "specimen" / "hotkeys" / "miner"
    path.parent.mkdir(parents=True)
    Keyfile(path).set_keypair(pair, encrypt=True, overwrite=True, password=PASSWORD)
    return path, pair.ss58_address


@pytest.fixture
def signer(specimen_key):
    key_file, hotkey = specimen_key
    directory = _short_dir()
    process = SignerProcess(key_file, directory / "s.sock")
    process.type_password(PASSWORD)
    process.wait_listening()
    try:
        yield process, hotkey
    finally:
        process.stop()


def _signed(external, body, receiver):
    return BittensorMessageSigner(external).sign(
        body, receiver=receiver, nonce_ns=time.time_ns()
    )


def _verify(headers, body, receiver):
    return BittensorHotkeyVerifier().verify(
        headers,
        body,
        method="POST",
        path="/carbon/v1/mcp",
        receiver=receiver,
        now_ns=time.time_ns(),
        nonce_store=_NonceStore(),
    )


def test_a_request_signed_by_the_miners_signer_authenticates(signer):
    process, hotkey = signer
    receiver = _keypair(RECEIVER_URI).ss58_address
    external = connect_signer(hotkey, socket_path=process.socket_path)
    body = json.dumps({"tool": "battery_submit", "n": 1}).encode()
    headers = _signed(external, body, receiver)
    assert _verify(headers, body, receiver).hotkey == hotkey
    assert external.issued == 1
    process.read(until=b"signed a Carbon request")


def test_the_bytes_signed_are_the_bytes_verified(signer, monkeypatch):
    """4.4: both sides derive the payload with the SDK's one `build_payload`,
    and a signature covers the body exactly - one changed byte, or the same
    JSON serialized differently, does not verify."""
    from bittensor import http_auth

    from carbon.chain.auth import AuthCode, AuthFailure

    process, hotkey = signer
    receiver = _keypair(RECEIVER_URI).ss58_address
    built = []
    original = http_auth.build_payload

    def spy(**kwargs):
        payload = original(**kwargs)
        built.append(payload)
        return payload

    monkeypatch.setattr(http_auth, "build_payload", spy)
    external = connect_signer(hotkey, socket_path=process.socket_path)
    body = b'{"a":1,"b":2}'
    headers = _signed(external, body, receiver)
    _verify(headers, body, receiver)
    assert len(built) == 2 and built[0] == built[1]
    for altered in (b'{"a":1,"b":3}', b'{"a": 1, "b": 2}'):
        with pytest.raises(AuthFailure) as refused:
            _verify(headers, altered, receiver)
        assert refused.value.code is AuthCode.SIGNATURE


def test_no_signer_running_is_its_own_condition(specimen_key):
    _, hotkey = specimen_key
    with pytest.raises(SignerFailure) as failure:
        connect_signer(hotkey, socket_path=_short_dir() / "absent.sock")
    assert failure.value.code == SignerCode.NOT_RUNNING.value


def test_a_different_hotkey_is_its_own_condition(signer):
    process, _ = signer
    other = _keypair("//someone-else").ss58_address
    with pytest.raises(SignerFailure) as failure:
        connect_signer(other, socket_path=process.socket_path)
    assert failure.value.code == SignerCode.WRONG_HOTKEY.value


def test_a_refusal_is_its_own_condition_and_names_why(signer):
    """The signer signs Carbon request payloads only: not an arbitrary
    message, and not a request for another receiver than it was told."""
    process, hotkey = signer
    external = connect_signer(hotkey, socket_path=process.socket_path)
    with pytest.raises(SignerFailure) as failure:
        external.sign(b"transfer everything")
    assert failure.value.code == SignerCode.REFUSED.value
    assert failure.value.refusal == "NOT_A_CARBON_REQUEST"
    assert external.issued == 0
    process.read(until=b"refused a request: NOT_A_CARBON_REQUEST")


def test_a_receiver_restriction_refuses_other_receivers(specimen_key):
    key_file, hotkey = specimen_key
    allowed = _keypair(RECEIVER_URI).ss58_address
    other = _keypair("//another-validator").ss58_address
    process = SignerProcess(key_file, _short_dir() / "s.sock", "--receiver", allowed)
    try:
        process.type_password(PASSWORD)
        process.wait_listening()
        external = connect_signer(hotkey, socket_path=process.socket_path)
        _verify(_signed(external, b"{}", allowed), b"{}", allowed)
        with pytest.raises(SignerFailure) as failure:
            _signed(external, b"{}", other)
        assert failure.value.refusal == "RECEIVER_NOT_ALLOWED"
    finally:
        process.stop()


def _fake_signer(path, reply):
    """A socket that answers `identity` honestly for the specimen hotkey and
    then answers a sign request with `reply` (None: never answer)."""
    hotkey = _keypair(URI).ss58_address
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(4)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            with connection:
                request = json.loads(connection.recv(4096).split(b"\n")[0])
                if request["op"] == "identity":
                    answer = {"ok": True, "hotkey": hotkey, "crypto_type": 1}
                elif reply is None:
                    stop.wait(10)
                    continue
                else:
                    answer = reply
                connection.sendall(
                    (
                        answer
                        if isinstance(answer, bytes)
                        else json.dumps(answer).encode()
                    )
                    + b"\n"
                )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return hotkey, lambda: (stop.set(), listener.close())


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (None, SignerCode.TIMEOUT),
        ({"ok": True, "signature": "0x" + "00" * 64}, SignerCode.INVALID_SIGNATURE),
        (b"not json", SignerCode.PROTOCOL),
        ({"ok": True, "signature": "zz"}, SignerCode.PROTOCOL),
    ],
)
def test_timeouts_and_bad_answers_are_their_own_conditions(reply, code):
    path = _short_dir() / "fake.sock"
    hotkey, close = _fake_signer(path, reply)
    try:
        external = connect_signer(hotkey, socket_path=path, timeout=1.0)
        receiver = _keypair(RECEIVER_URI).ss58_address
        with pytest.raises(SignerFailure) as failure:
            _signed(external, b"{}", receiver)
        assert failure.value.code == code.value
        # Nothing unverified is ever counted as a signature Carbon holds.
        assert external.issued == 0
    finally:
        close()


def test_the_signer_payload_rule():
    from bittensor.http_auth import build_payload

    from carbon_miner_signer import Refusal, refusal_for

    miner = _keypair(URI).ss58_address
    receiver = _keypair(RECEIVER_URI).ss58_address
    now = time.time_ns()

    def payload(**change):
        fields = {
            "scheme": "sr25519",
            "method": "POST",
            "path": "/carbon/v1/mcp",
            "body": b"{}",
            "nonce_ns": now,
            "sender_ss58": miner,
            "receiver_ss58": receiver,
        }
        fields.update(change)
        return build_payload(**fields)

    def rule(value):
        return refusal_for(
            value, hotkey=miner, scheme="sr25519", receivers=None, now_ns=now
        )

    assert rule(payload()) is None
    assert rule(payload(path="/other")) is Refusal.NOT_A_CARBON_REQUEST
    # The answer-key fetch is not a miner's request: refused unless started for it.
    answer_key = payload(path="/carbon/v1/answer-key")
    assert rule(answer_key) is Refusal.NOT_A_CARBON_REQUEST
    started_for_it = frozenset({"/carbon/v1/answer-key"})
    for value, expected in (
        (answer_key, None),
        (payload(), Refusal.NOT_A_CARBON_REQUEST),
    ):
        found = refusal_for(
            value,
            hotkey=miner,
            scheme="sr25519",
            receivers=frozenset({receiver}),
            now_ns=now,
            paths=started_for_it,
        )
        assert found is expected
    assert rule(payload(method="GET")) is Refusal.NOT_A_CARBON_REQUEST
    assert rule(payload(scheme="ed25519")) is Refusal.NOT_A_CARBON_REQUEST
    assert rule(payload(sender_ss58=receiver)) is Refusal.WRONG_SENDER
    assert rule(payload(nonce_ns=now - 60 * 10**9)) is Refusal.STALE_NONCE
    assert rule(payload(nonce_ns=now + 60 * 10**9)) is Refusal.STALE_NONCE
    assert rule(payload(receiver_ss58=None)) is Refusal.RECEIVER_NOT_ALLOWED
    assert rule(b"\xff" * 10) is Refusal.NOT_A_CARBON_REQUEST


def test_both_sides_derive_the_same_socket_path():
    from carbon_miner_signer import default_socket as signer_side

    hotkey = _keypair(URI).ss58_address
    assert default_socket(hotkey) == signer_side(hotkey)
    with pytest.raises(ValueError):
        default_socket("../../etc/passwd")


def test_the_socket_is_the_miners_alone(signer):
    process, _ = signer
    assert (process.socket_path.stat().st_mode & 0o777) == 0o600
    assert (process.socket_path.parent.stat().st_mode & 0o777) == 0o700


def test_a_wrong_password_starts_nothing_and_says_nothing(specimen_key):
    key_file, _ = specimen_key
    process = SignerProcess(key_file, _short_dir() / "s.sock")
    try:
        process.type_password("not-the-" + PASSWORD)
        process.read(until=b"could not unlock the hotkey")
        assert process.process.wait(timeout=20) != 0
        assert not process.socket_path.exists()
    finally:
        process.stop()


def test_no_secret_reaches_anything_either_side_writes(specimen_key, tmp_path):
    """4.6, with the credential itself as the specimen.

    Everything the signer printed to its terminal and everything Carbon's side
    produced - signed headers, every typed failure's text and repr, the
    client's repr - is searched for the password and for each piece of
    decrypted key material. The same search is shown finding each of them
    where they really are, so a clean result means absent, not unsearched.
    """
    from bittensor.sp_core import decrypt_keyfile_data

    key_file, hotkey = specimen_key
    decrypted = json.loads(bytes(decrypt_keyfile_data(key_file.read_bytes(), PASSWORD)))
    secrets = {PASSWORD}
    for field in ("privateKey", "secretSeed", "secretPhrase"):
        value = decrypted.get(field)
        if value:
            secrets.add(value)
            secrets.add(value.removeprefix("0x"))
    assert len(secrets) >= 3, sorted(decrypted)

    def leaks(haystack: bytes):
        return {s for s in secrets if s.encode() in haystack}

    # Specimen: the search finds the password in what the miner typed, and the
    # key material in the decrypted key file.
    process = SignerProcess(key_file, _short_dir() / "s.sock")
    carbon_side = []
    try:
        process.type_password(PASSWORD)
        process.wait_listening()
        assert PASSWORD in leaks(process.typed)
        assert leaks(json.dumps(decrypted).encode()) == secrets - {PASSWORD}
        receiver = _keypair(RECEIVER_URI).ss58_address
        external = connect_signer(hotkey, socket_path=process.socket_path)
        carbon_side.append(repr(external))
        carbon_side.append(json.dumps(_signed(external, b"{}", receiver)))
        for attempt in (
            lambda: external.sign(b"not carbon"),
            lambda: connect_signer(
                _keypair("//other").ss58_address, socket_path=process.socket_path
            ),
            lambda: connect_signer(hotkey, socket_path=_short_dir() / "none.sock"),
        ):
            try:
                attempt()
            except SignerFailure as failure:
                carbon_side.extend([str(failure), repr(failure), failure.code])
            else:
                raise AssertionError("expected a typed signer failure")
        process.read(until=b"refused a request")
    finally:
        process.stop()
    assert b"signed a Carbon request" in process.output
    assert leaks(process.output) == set(), "the signer's terminal shows a secret"
    assert leaks("\n".join(carbon_side).encode()) == set()


def test_concurrent_campaigns_all_sign_and_a_stalled_client_holds_up_nothing():
    """Several campaigns sign at once, and another client that connects and
    never finishes its request delays none of them. Before each connection had
    its own thread, most of these failed as `signer_not_running`: the signer
    was running, only busy."""
    from concurrent.futures import ThreadPoolExecutor

    from tests.cpu._signer_harness import in_thread_signer

    receiver = _keypair(RECEIVER_URI).ss58_address
    with in_thread_signer(_keypair(URI)) as external:
        stalled = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stalled.connect(str(external._path))
        stalled.sendall(b'{"protocol":')  # and never the rest
        try:
            started = time.monotonic()
            with ThreadPoolExecutor(32) as pool:
                signed = list(
                    pool.map(
                        lambda n: _signed(external, b'{"n":%d}' % n, receiver),
                        range(200),
                    )
                )
            assert len(signed) == 200
            assert time.monotonic() - started < 4  # not waiting out the stall
        finally:
            stalled.close()


def test_a_busy_signer_is_a_timeout_never_not_running(tmp_path):
    """Specimen for the distinction: a socket whose accept queue is full is a
    signer that exists and is busy. Carbon waits until its deadline and says
    `signer_timeout`; only a missing socket is `signer_not_running`."""
    path = _short_dir() / "busy.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(0)  # never accepted: the queue fills at once
    held = []
    try:
        for _ in range(4):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.setblocking(False)
            try:
                client.connect(str(path))
            except BlockingIOError:
                pass
            held.append(client)
        with pytest.raises(SignerFailure) as busy:
            connect_signer(_keypair(URI).ss58_address, socket_path=path, timeout=0.5)
        assert busy.value.code == SignerCode.TIMEOUT.value
    finally:
        for client in held:
            client.close()
        listener.close()
    with pytest.raises(SignerFailure) as absent:
        connect_signer(_keypair(URI).ss58_address, socket_path=path, timeout=0.5)
    assert absent.value.code == SignerCode.NOT_RUNNING.value


ANSWER_KEY_PATH = "/carbon/v1/answer-key"


def _signed_answer_key(external, body, receiver):
    return BittensorMessageSigner(external).sign(
        body, receiver=receiver, nonce_ns=time.time_ns(), path=ANSWER_KEY_PATH
    )


def test_a_miners_signer_never_signs_an_answer_key_fetch(signer):
    """3a at r2: started as a miner's signer, the answer-key fetch is refused
    by name, and nothing is signed."""
    process, hotkey = signer
    receiver = _keypair(RECEIVER_URI).ss58_address
    external = connect_signer(hotkey, socket_path=process.socket_path)
    with pytest.raises(SignerFailure) as failure:
        _signed_answer_key(external, b"{}", receiver)
    assert failure.value.refusal == "NOT_A_CARBON_REQUEST"
    assert external.issued == 0


def test_answer_key_signing_needs_a_named_receiver(specimen_key):
    key_file, _hotkey = specimen_key
    process = SignerProcess(
        key_file, _short_dir() / "s.sock", "--request", "answer-key"
    )
    try:
        process.read(until=b"--request answer-key needs --receiver")
        assert process.process.wait(timeout=20) != 0
    finally:
        process.stop()


def test_a_validators_signer_signs_the_answer_key_fetch_and_nothing_else(specimen_key):
    """Started with `--request answer-key --receiver R`: the fetch to R is
    signed and verifies at the answer-key path; another receiver and a miner's
    MCP request are refused."""
    from carbon.challenge_validator.answer_key import PATH

    assert PATH == ANSWER_KEY_PATH
    key_file, hotkey = specimen_key
    allowed = _keypair(RECEIVER_URI).ss58_address
    other = _keypair("//another-validator").ss58_address
    process = SignerProcess(
        key_file,
        _short_dir() / "s.sock",
        "--request",
        "answer-key",
        "--receiver",
        allowed,
    )
    try:
        process.type_password(PASSWORD)
        process.wait_listening()
        process.read(until=ANSWER_KEY_PATH.encode())
        external = connect_signer(hotkey, socket_path=process.socket_path)
        headers = _signed_answer_key(external, b"{}", allowed)
        verified = BittensorHotkeyVerifier().verify(
            headers,
            b"{}",
            method="POST",
            path=ANSWER_KEY_PATH,
            receiver=allowed,
            now_ns=time.time_ns(),
            nonce_store=_NonceStore(),
        )
        assert verified.hotkey == hotkey
        process.read(until=b"signed a Carbon request (" + ANSWER_KEY_PATH.encode())
        for sign, receiver, refusal in (
            (_signed_answer_key, other, "RECEIVER_NOT_ALLOWED"),
            (_signed, allowed, "NOT_A_CARBON_REQUEST"),
        ):
            with pytest.raises(SignerFailure) as failure:
                sign(external, b"{}", receiver)
            assert failure.value.refusal == refusal
        assert external.issued == 1
    finally:
        process.stop()


def _allowlist_file(directory, hotkeys):
    path = Path(directory) / "allowlist.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.signer.autoconfirm-allowlist.v1",
                "network": "testnet",
                "netuid": 567,
                "hotkeys": hotkeys,
            }
        )
    )
    path.chmod(0o600)
    return path


def test_a_real_signer_auto_confirms_an_allow_listed_testnet_commitment(specimen_key):
    """OWNER-SIGNER-TESTNET-AUTOCONFIRM-01, end to end: the real process,
    started with the flag under the committed testnet 567 record, signs a
    commitment nobody types for, shows it marked and records it."""
    from carbon.chain.external_signer import request_commitment
    from tests.cpu.test_miner_signer_commit import DIGEST, _request

    key_file, hotkey = specimen_key
    directory = _short_dir()
    allowlist = _allowlist_file(directory, [hotkey])
    process = SignerProcess(
        key_file, directory / "s.sock", "--auto-confirm-commitments", str(allowlist)
    )
    try:
        process.type_password(PASSWORD)
        process.wait_listening()
        process.read(until=b"read once: restart to change it")
        external = connect_signer(hotkey, socket_path=process.socket_path)
        body = _request(fee=(0, 0))
        del body["protocol"], body["op"]
        answer = request_commitment(external, body)
        assert len(answer["signature"]) == 64
        process.read(until=b"signed commitment " + DIGEST.encode())
        assert b"AUTO-CONFIRMED (allow-listed testnet hotkey)" in process.output
        assert b"Type the last 8" not in process.output
        with pytest.raises(SignerFailure) as refused:
            request_commitment(external, body)
        assert refused.value.refusal == "ALREADY_COMMITTED_THIS_TEMPO"
        ledger = directory / (hotkey + ".commitments.jsonl")
        (row,) = [json.loads(line) for line in ledger.read_text().splitlines()]
        assert row["confirmation"] == "AUTO-CONFIRMED (allow-listed testnet hotkey)"
        assert row["digest"] == DIGEST and row["network"] == "testnet"
        # Nothing but the password was ever typed into the signer's terminal.
        assert process.typed == PASSWORD.encode() + b"\n"
    finally:
        process.stop()


def test_a_real_signer_refuses_to_auto_confirm_an_unlisted_hotkey(specimen_key):
    key_file, _hotkey = specimen_key
    directory = _short_dir()
    other = _keypair("//another-validator").ss58_address
    allowlist = _allowlist_file(directory, [other])
    process = SignerProcess(
        key_file, directory / "s.sock", "--auto-confirm-commitments", str(allowlist)
    )
    try:
        process.type_password(PASSWORD)
        process.read(until=b"not in the auto-confirm allow-list")
        assert process.process.wait(timeout=20) != 0
        assert not process.socket_path.exists()
    finally:
        process.stop()
