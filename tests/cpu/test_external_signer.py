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
