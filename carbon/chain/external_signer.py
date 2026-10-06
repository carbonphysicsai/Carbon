"""Carbon's side of the miner's local signer: a payload out, a signature in.

Carbon never opens a key file, reads a password or builds a signer from key
material. The miner runs ``carbon-miner-signer`` (``carbon_miner_signer``),
which holds their hotkey; this module talks to it over a Unix socket, sends it
the exact ``btauth/1`` payload bytes, and verifies the signature it returns
against the hotkey's public address before anything uses it.

An ``ExternalSigner`` exists only as the result of ``connect_signer``, which
has already confirmed the signer holds the expected hotkey. There is no other
way to build one, so ``BittensorMessageSigner`` accepting only this type means
no key material can reach it.

Every failure is one closed ``SignerCode``; a refusal also carries the
signer's own closed reason. Nothing from the signer's side is echoed.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from enum import Enum
from pathlib import Path

PROTOCOL = "carbon.miner-signer.v1"
DEFAULT_TIMEOUT_S = 5.0
MAX_RESPONSE_BYTES = 4096
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
_SIGNATURE = re.compile(r"0x[0-9a-f]{128}")
#: The signer's closed refusal reasons (`carbon_miner_signer.Refusal`).
SIGNER_REFUSALS = frozenset(
    {
        "MALFORMED_REQUEST",
        "NOT_A_CARBON_REQUEST",
        "WRONG_SENDER",
        "STALE_NONCE",
        "RECEIVER_NOT_ALLOWED",
    }
)
#: Its closed commit refusals (`carbon_miner_signer.CommitRefusal`).
COMMIT_REFUSALS = frozenset(
    {
        "MALFORMED_REQUEST",
        "COMMITMENT_NOT_PINNED",
        "NOT_A_COMMITMENT",
        "BAD_DIGEST",
        "WRONG_NETUID",
        "WRONG_NETWORK",
        "NONZERO_TIP",
        "IMMORTAL_ERA",
        "ERA_TOO_LONG",
        "PAYLOAD_MISMATCH",
        "FEE_UNKNOWN",
        "FEE_OVER_CEILING",
        "ALREADY_COMMITTED_THIS_TEMPO",
        "STALE_CHAIN_CONTEXT",
        "COMMIT_IN_FLIGHT",
        "NOT_CONFIRMED",
        "LEDGER_UNAVAILABLE",
    }
)
#: How long a commit request may wait: the miner reads the prompt and types
#: (the signer's own window is 120 s), plus the exchange itself.
COMMIT_TIMEOUT_S = 150.0
_CALL = re.compile(r"0x(?:[0-9a-f]{2})+")


class SignerCode(str, Enum):
    #: Nothing is listening: start ``carbon-miner-signer``.
    NOT_RUNNING = "signer_not_running"
    #: The signer is running and declined this request.
    REFUSED = "signer_refused"
    #: The signer holds a different hotkey than the registered miner's.
    WRONG_HOTKEY = "signer_wrong_hotkey"
    #: The signer did not answer in time.
    TIMEOUT = "signer_timeout"
    #: A signature came back that does not verify for the hotkey.
    INVALID_SIGNATURE = "signer_invalid_signature"
    #: Something answered that does not speak the signer protocol.
    PROTOCOL = "signer_protocol"


class SignerFailure(Exception):
    """Signing did not happen. Nothing signed by this call left Carbon."""

    def __init__(self, code: SignerCode, refusal: str | None = None):
        self.code = code.value
        known = SIGNER_REFUSALS | COMMIT_REFUSALS
        self.refusal = refusal if refusal in known else None
        super().__init__(
            code.value if self.refusal is None else f"{code.value}:{self.refusal}"
        )


def default_socket(hotkey: str) -> Path:
    """The same derivation as the signer's, from the public hotkey alone."""
    if not _SS58.fullmatch(hotkey):
        raise ValueError("a hotkey ss58 address is required")
    return Path.home() / ".carbon" / "signer" / (hotkey + ".sock")


def _connect(path: Path, timeout: float) -> socket.socket:
    """Connect to the signer, telling "not running" from "busy".

    Nothing at the path, or nothing listening, is NOT_RUNNING. A full accept
    queue (EAGAIN) means a signer is there and busy: retry until the deadline,
    then TIMEOUT - never report a busy signer as one that is not running.
    """
    deadline = time.monotonic() + timeout
    delay = 0.005
    while True:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(max(deadline - time.monotonic(), 0.001))
        try:
            client.connect(str(path))
            return client
        except (BlockingIOError, InterruptedError):
            client.close()
        except TimeoutError:
            client.close()
            raise SignerFailure(SignerCode.TIMEOUT) from None
        except OSError:
            client.close()
            raise SignerFailure(SignerCode.NOT_RUNNING) from None
        if time.monotonic() + delay >= deadline:
            raise SignerFailure(SignerCode.TIMEOUT)
        time.sleep(delay)
        delay = min(delay * 2, 0.1)


def _exchange(path: Path, request: dict, timeout: float) -> dict:
    client = _connect(path, timeout)
    try:
        data = b""
        try:
            client.sendall(json.dumps(request).encode() + b"\n")
            while b"\n" not in data:
                chunk = client.recv(1024)
                if not chunk:
                    break
                data += chunk
                if len(data) > MAX_RESPONSE_BYTES:
                    raise SignerFailure(SignerCode.PROTOCOL)
        except TimeoutError:
            raise SignerFailure(SignerCode.TIMEOUT) from None
        except OSError:
            raise SignerFailure(SignerCode.NOT_RUNNING) from None
    finally:
        client.close()
    try:
        response = json.loads(data.split(b"\n", 1)[0])
    except ValueError:
        response = None
    if type(response) is not dict or type(response.get("ok")) is not bool:
        raise SignerFailure(SignerCode.PROTOCOL)
    if not response["ok"]:
        raise SignerFailure(SignerCode.REFUSED, response.get("refusal"))
    return response


_TOKEN = object()
_obtained_lock = threading.Lock()
_obtained_total = 0


def signatures_obtained() -> int:
    """How many verified signatures this process has obtained, ever.

    Process-wide on purpose: a caller compares it before and after an
    operation, and any concurrent signing can only make that comparison say a
    signed request may exist - never that nothing happened when it did.
    """
    return _obtained_total


def _count_signature() -> None:
    global _obtained_total
    with _obtained_lock:
        _obtained_total += 1


class ExternalSigner:
    """A bittensor ``Signer`` whose key lives in the miner's signer process."""

    __slots__ = (
        "_path",
        "_public_key",
        "_timeout",
        "crypto_type",
        "issued",
        "ss58_address",
    )

    def __init__(self, token, path, timeout, hotkey, crypto_type, public_key):
        if token is not _TOKEN:
            raise TypeError("an ExternalSigner comes only from connect_signer")
        self._path = path
        self._timeout = timeout
        self.ss58_address = hotkey
        self.crypto_type = crypto_type
        self._public_key = public_key
        #: Signatures this connection has obtained. A signature can outlive the
        #: request it was for, so a caller that fails after signing reports
        #: that a signed request may exist rather than that nothing happened.
        self.issued = 0

    @property
    def public_key(self) -> bytes:
        return self._public_key

    def __repr__(self):
        return f"ExternalSigner(hotkey={self.ss58_address!r})"

    def sign(self, payload: bytes) -> bytes:
        response = _exchange(
            self._path,
            {"protocol": PROTOCOL, "op": "sign", "payload": payload.decode("ascii")},
            self._timeout,
        )
        encoded = response.get("signature")
        if type(encoded) is not str or not _SIGNATURE.fullmatch(encoded):
            raise SignerFailure(SignerCode.PROTOCOL)
        signature = bytes.fromhex(encoded[2:])
        from bittensor.sp_core import verify

        if not verify(payload, signature, self.ss58_address, self.crypto_type):
            raise SignerFailure(SignerCode.INVALID_SIGNATURE)
        self.issued += 1
        _count_signature()
        return signature


def request_commitment(signer: ExternalSigner, request: dict) -> dict:
    """Ask the miner's signer to sign one strategy commitment.

    The signer rebuilds and checks the call and extensions itself and asks
    the miner on its own terminal; this only carries the closed request and
    the answer. Returns ``{"signature": bytes, "call": bytes,
    "fee_ceiling_rao": int, "tempo_index": int}``. The caller verifies the
    signature over its own prepared payload before anything is broadcast.
    """
    response = _exchange(
        signer._path,
        {"protocol": PROTOCOL, "op": "commit", **request},
        COMMIT_TIMEOUT_S,
    )
    signature, call = response.get("signature"), response.get("call")
    ceiling, tempo = response.get("fee_ceiling_rao"), response.get("tempo_index")
    if (
        set(response) != {"ok", "signature", "call", "fee_ceiling_rao", "tempo_index"}
        or type(signature) is not str
        or not _SIGNATURE.fullmatch(signature)
        or type(call) is not str
        or not _CALL.fullmatch(call)
        or type(ceiling) is not int
        or ceiling <= 0
        or type(tempo) is not int
        or tempo < 0
    ):
        raise SignerFailure(SignerCode.PROTOCOL)
    signer.issued += 1
    _count_signature()
    return {
        "signature": bytes.fromhex(signature[2:]),
        "call": bytes.fromhex(call[2:]),
        "fee_ceiling_rao": ceiling,
        "tempo_index": tempo,
    }


def connect_signer(
    hotkey: str, *, socket_path: Path | None = None, timeout: float = DEFAULT_TIMEOUT_S
) -> ExternalSigner:
    """Reach the miner's signer and confirm it holds ``hotkey``."""
    path = Path(socket_path) if socket_path is not None else default_socket(hotkey)
    response = _exchange(path, {"protocol": PROTOCOL, "op": "identity"}, timeout)
    crypto_type = response.get("crypto_type")
    if type(response.get("hotkey")) is not str or crypto_type not in (0, 1):
        raise SignerFailure(SignerCode.PROTOCOL)
    if response["hotkey"] != hotkey:
        raise SignerFailure(SignerCode.WRONG_HOTKEY)
    from bittensor.sp_core import ss58_decode

    try:
        public_key = bytes(ss58_decode(hotkey))
    except (TypeError, ValueError):
        raise SignerFailure(SignerCode.PROTOCOL) from None
    return ExternalSigner(_TOKEN, path, timeout, hotkey, crypto_type, public_key)


def miner_signer(public: dict, socket_path: Path | None = None) -> ExternalSigner:
    """The signer for a miner's public identity document.

    Reads only the public hotkey. A ``key_file`` field, if the document still
    carries one from before external signing, is not read.
    """
    return connect_signer(public["hotkey"], socket_path=socket_path)
