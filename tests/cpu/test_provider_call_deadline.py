"""GRAPHITE-D27: every provider call has a hard total wall-clock deadline.

urllib's `timeout` bounds each socket operation, not the call. These tests
run a LOCAL fake HTTPS server on 127.0.0.1 with a throwaway self-signed
certificate - no network, no real key, no model - that stalls before
headers, trickles its body one byte at a time forever, or accepts and never
speaks. Each call must end within its (small, injected) deadline plus a
margin as an UNKNOWN outcome: full reservation kept, never resent.
"""

from __future__ import annotations

import contextlib
import datetime
import ipaddress
import json
import socket
import ssl
import threading
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from graphite_phase2_fixtures import backfill, entry, replies, reply, scripted, seed
from test_cw1_research_ledger import ledger

from carbon.agent_campaign.graphite import triage
from carbon.development_session import model_provider as mp
from carbon.development_session.research_agent import (
    ProviderCallFailed,
    request_model,
)

#: The injected deadline and the slack allowed beyond it for teardown.
DEADLINE = 0.5
SLACK = 2.0
#: The selection's per-operation timeout (its validated minimum): far longer
#: than DEADLINE, so only the deadline can end these calls quickly.
PER_OPERATION = 10

FAST_REPLY = {
    "model": "fixture-model",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "ok"}],
        }
    ],
    "usage": {
        "input_tokens": 10,
        "output_tokens": 2,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    """A throwaway self-signed certificate for 127.0.0.1 (test only)."""
    folder = tmp_path_factory.mktemp("tls")
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "carbon-fixture")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = folder / "cert.pem", folder / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class FakeProvider:
    """A local HTTPS server with one behaviour for every connection."""

    def __init__(self, mode, certificate):
        self.mode, self.connections = mode, 0
        self.stop = threading.Event()
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(*map(str, certificate))
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.held = []
        threading.Thread(target=self._accept, daemon=True).start()

    @property
    def endpoint(self):
        return f"https://127.0.0.1:{self.port}/v1/responses"

    def _accept(self):
        while not self.stop.is_set():
            try:
                raw, _ = self.listener.accept()
            except OSError:
                return
            self.connections += 1
            self.held.append(raw)
            threading.Thread(target=self._serve, args=(raw,), daemon=True).start()

    def _request(self, conn):
        data = b""
        while b"\r\n\r\n" not in data:
            data += conn.recv(65536)
        head, _, body = data.partition(b"\r\n\r\n")
        length = int(
            next(
                line.split(b":")[1]
                for line in head.split(b"\r\n")
                if line.lower().startswith(b"content-length")
            )
        )
        while len(body) < length:
            body += conn.recv(65536)

    def _serve(self, raw):
        try:
            if self.mode == "silent":  # accepts, never speaks, not even TLS
                self.stop.wait()
                return
            conn = self.context.wrap_socket(raw, server_side=True)
            self.held.append(conn)
            self._request(conn)
            if self.mode == "stall":  # request read, headers never sent
                self.stop.wait()
            elif self.mode == "trickle":  # one body byte at a time, forever
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Content-Length: 10000000\r\n\r\n"
                )
                while not self.stop.wait(0.02):
                    conn.sendall(b" ")
            else:
                body = json.dumps(FAST_REPLY).encode()
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
        except (OSError, ssl.SSLError):
            pass

    def close(self):
        self.stop.set()
        self.listener.close()
        for sock in self.held:
            try:
                sock.close()
            except OSError:
                pass


@pytest.fixture
def server(certificate, monkeypatch):
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate[0]))
    started = []

    def start(mode):
        fake = FakeProvider(mode, certificate)
        started.append(fake)
        return fake

    yield start
    for fake in started:
        fake.close()


@pytest.fixture
def key_file(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    path = folder / "provider.key"
    path.write_text("fixture-not-a-key")
    path.chmod(0o600)
    return path


def selection(fake, key_file):
    return mp.select(
        provider_id="openai-compatible-responses",
        model_id="fixture-model",
        endpoint=fake.endpoint,
        credential={"kind": "file", "reference": str(key_file)},
        settings={"reasoning_effort": None, "timeout_seconds": PER_OPERATION},
        declared_pricing={
            "input_nano": 100,
            "cached_input_nano": 10,
            "output_nano": 400,
            "observed": "2026-10-02",
            "note": "test fixture price",
        },
    )


def request(chosen):
    return {
        "model": chosen.model_id,
        "instructions": "fixture",
        "input": [{"role": "user", "content": "observe"}],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": chosen.settings.max_output_tokens,
        "reasoning": None,
    }


def _workers():
    return [t for t in threading.enumerate() if t.name == "carbon-provider-call"]


def _drained(timeout=SLACK):
    end = time.monotonic() + timeout
    while _workers() and time.monotonic() < end:
        time.sleep(0.02)
    return not _workers()


# -- the deadline ------------------------------------------------------------


def test_the_deadline_is_the_timeout_plus_a_named_margin():
    settings = mp.DEFAULT_SETTINGS
    assert mp.call_deadline_seconds(settings) == 120 + mp.DEADLINE_MARGIN_SECONDS
    assert mp.DEADLINE_MARGIN_SECONDS == 10


@pytest.mark.parametrize("mode", ["stall", "trickle", "silent"])
def test_a_hung_call_ends_at_its_deadline_as_unknown(server, key_file, mode):
    fake = server(mode)
    chosen = selection(fake, key_file)
    transport = mp.SelectionTransport(chosen, deadline_seconds=DEADLINE)
    began = time.monotonic()
    with pytest.raises(mp.ProviderDeadlineExceeded) as raised:
        transport(request(chosen))
    took = time.monotonic() - began
    assert DEADLINE <= took < DEADLINE + SLACK
    failure = mp.classify(raised.value, chosen.errors)
    assert failure.outcome is mp.ProviderOutcome.UNKNOWN
    assert not failure.unbilled and not failure.retry_safe
    assert fake.connections == 1
    # The call's socket was shut: its worker ends and holds nothing open.
    assert _drained(), "the abandoned worker is still blocked"


@pytest.mark.parametrize("mode", ["stall", "trickle", "silent"])
def test_a_hung_call_keeps_its_reservation_and_is_never_resent(
    server, key_file, tmp_path, mode
):
    fake = server(mode)
    chosen = selection(fake, key_file)
    meter = ledger(tmp_path)
    transport = mp.SelectionTransport(chosen, deadline_seconds=DEADLINE)
    began = time.monotonic()
    with pytest.raises(ProviderCallFailed, match="uncertain") as failed:
        request_model(
            meter,
            owner="alice",
            identity="model-1",
            request=request(chosen),
            credential_file=None,
            provider=chosen,
            transport=transport,
            sleep=pytest.fail,
        )
    assert time.monotonic() - began < DEADLINE + SLACK
    assert failed.value.outcome is mp.ProviderOutcome.UNKNOWN
    (op,) = meter.status(owner="alice")["operations"]
    assert op["state"] == "RESERVED" and op["actual"] is None
    assert op["reservation"]["provider_nanodollars"] == chosen.reservation_nano
    # The same call again is refused for reconciliation and not sent.
    with pytest.raises(ValueError, match="reconciliation required, no resend"):
        request_model(
            meter,
            owner="alice",
            identity="model-1",
            request=request(chosen),
            credential_file=None,
            provider=chosen,
            transport=transport,
            sleep=pytest.fail,
        )
    assert fake.connections == 1
    assert _drained()


def test_a_fast_reply_is_unchanged(server, key_file, tmp_path):
    fake = server("fast")
    chosen = selection(fake, key_file)
    meter = ledger(tmp_path)
    response = request_model(
        meter,
        owner="alice",
        identity="model-1",
        request=request(chosen),
        credential_file=None,
        provider=chosen,
        transport=mp.SelectionTransport(chosen),  # the real default deadline
        sleep=pytest.fail,
    )
    assert response == FAST_REPLY
    (op,) = meter.status(owner="alice")["operations"]
    assert op["state"] == "SUCCEEDED"
    assert op["actual"]["provider_nanodollars"] == 10 * 100 + 2 * 400
    assert fake.connections == 1
    assert _drained()


def test_a_rejection_still_crosses_the_worker_typed(key_file, monkeypatch):
    import io
    import urllib.error
    from email.message import Message

    class Opener:
        def open(self, outgoing, timeout):
            assert timeout == PER_OPERATION
            raise urllib.error.HTTPError(
                "https://fixture.invalid",
                429,
                "fixture",
                Message(),
                io.BytesIO(b'{"error": {"code": "rate_limit"}}'),
            )

    chosen = mp.select(
        provider_id="openai-compatible-responses",
        model_id="fixture-model",
        endpoint="https://fixture.invalid/v1/responses",
        credential={"kind": "file", "reference": str(key_file)},
        settings={"timeout_seconds": PER_OPERATION},
    )
    with pytest.raises(mp.ProviderHTTPError) as raised:
        mp.SelectionTransport(chosen, opener=Opener())(request(chosen))
    assert raised.value.status == 429 and raised.value.code == "rate_limit"
    assert raised.value.__suppress_context__


# -- mutation: without the deadline the stall is not bounded ------------------


def test_without_the_deadline_a_stalled_call_outlives_the_bound(
    server, key_file, monkeypatch
):
    fake = server("stall")
    chosen = selection(fake, key_file)
    monkeypatch.setattr(mp, "call_deadline_seconds", lambda settings: None)
    finished = threading.Event()

    def call():
        # Only the timing matters here; the call's error is irrelevant.
        with contextlib.suppress(Exception):
            mp.SelectionTransport(chosen)(request(chosen))
        finished.set()

    threading.Thread(target=call, daemon=True).start()
    assert not finished.wait(DEADLINE + SLACK), "the stall ended without a deadline"
    fake.close()  # release the per-operation wait
    assert finished.wait(PER_OPERATION + SLACK)


# -- the triage treats it as any unknown outcome -----------------------------


def test_triage_stops_for_reconciliation_and_writes_off_on_the_next_start(tmp_path):
    def hang():
        raise mp.ProviderDeadlineExceeded("provider call deadline passed")

    raw = seed(tmp_path, entry(1), entry(2), entry(3))
    model = scripted([reply(), {**reply(), "hook": hang}])
    job = backfill(tmp_path, raw, model)
    summary = job.run("run-1")
    assert summary["status"] == "RECONCILIATION_REQUIRED"
    assert summary["outcome"] == "unknown"
    assert summary["written_off_unknown"] == 0 and len(model.requests) == 2
    stuck = [
        op
        for op in job._ledger("run-1").status(owner=triage.OWNER)["operations"]
        if op["state"] == "RESERVED"
    ]
    assert len(stuck) == 1
    model.script.extend(replies(1))
    resumed = job.run("run-1")
    assert resumed["status"] == "COMPLETED"
    assert resumed["written_off_unknown"] == 1
    assert len(model.requests) == 3  # the hung call was never resent
