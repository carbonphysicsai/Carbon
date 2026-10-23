"""The practice identity's chain side: its signer, local context and snapshot.

Practise without registering (LP practice-only).

A miner who chose Setup's "Practise without registering" has no registered
hotkey and no signer. Their campaigns still run through the authenticated
in-process research service, which verifies every request's signature, so
the install makes its own **practice identity**: an sr25519 key generated on
this machine, kept in an owner-only (0600) file, never registered, never
logged and never sent. Requests it signs are verified against a
**local-practice snapshot** built from that key alone.

What keeps it out of everything that matters:
- its principal is ``practice:<64 hex>`` - not an ss58 address, so no hotkey
  check, receiver pin or chain lookup can accept it (``PRINCIPAL``);
- the local-practice snapshot's context is network ``local-practice``
  (``LOCAL_PRACTICE``), which no chain reader reads and no network-path
  gateway, receiver or intake accepts (``refuse_local_practice``);
- a practice-only campaign is admitted ``PRACTICE_ONLY`` and runs research
  and reports only: freeze, submit, finals, commitments and every intake or
  chain path refuse ``registration_required``.

Validator receipt (2026-10-23): CONFIRMED on these conditions.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
import time
from pathlib import Path

PRACTICE_ONLY = "PRACTICE_ONLY"
#: The network a local-practice snapshot names. Never `CARBON_NETWORK`.
LOCAL_PRACTICE = "local-practice"
#: A practice principal: never an ss58 address (base58 has no ':').
PRINCIPAL = re.compile(r"practice:[0-9a-f]{64}")
#: The refusal for work that needs a registration.
REGISTRATION_REQUIRED = "registration_required"
#: The practice identity's file, beside setup's records.
KEY_FILE = "practice-identity.key"
_SEED = re.compile(rb"[0-9a-f]{64}\n?")
_TOKEN = object()


class PracticeIdentityRefused(ValueError):
    """A typed refusal about the practice identity; never key material."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def principal(public_key: bytes) -> str:
    """The practice principal for a practice identity's public key."""
    return "practice:" + public_key.hex()


def is_practice_principal(value) -> bool:
    return type(value) is str and PRINCIPAL.fullmatch(value) is not None


def create(path: Path) -> PracticeSigner:
    """Make this install's practice identity at `path` (0600), once; an
    existing one is kept and loaded."""
    path = Path(path)
    if not path.exists():
        seed = secrets.token_bytes(32).hex().encode("ascii") + b"\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, seed)
        finally:
            os.close(fd)
    return load(path)


def load(path: Path) -> PracticeSigner:
    """The practice identity in `path`: an owner-only regular file holding
    one 32-byte seed in hex. Refused, typed, otherwise."""
    path = Path(path)
    try:
        info = path.lstat()
    except OSError:
        raise PracticeIdentityRefused("practice_identity_missing") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise PracticeIdentityRefused("practice_identity_not_owner_only")
    raw = path.read_bytes()
    if not _SEED.fullmatch(raw):
        raise PracticeIdentityRefused("practice_identity_malformed")
    return PracticeSigner(_TOKEN, raw[:64].decode("ascii"))


def _keypair(seed_hex: str):
    from bittensor.sp_core import Keypair

    return Keypair.create_from_seed(bytes.fromhex(seed_hex))


class PracticeSigner:
    """A bittensor ``Signer`` for the practice identity, built only by
    ``load``. It signs requests to the local research service; nothing on the
    network admits what it signs (its address is registered nowhere and its
    snapshot is local-practice)."""

    __slots__ = ("_keypair", "_publisher", "crypto_type", "ss58_address")

    def __init__(self, token, seed_hex):
        if token is not _TOKEN:
            raise TypeError("a PracticeSigner comes only from practice_identity.load")
        self._keypair = _keypair(seed_hex)
        self.ss58_address = self._keypair.ss58_address
        self.crypto_type = self._keypair.crypto_type
        # The local research service's own receiver address, derived from the
        # same seed: public only, and as local as the identity.
        derived = hashlib.sha256(bytes.fromhex(seed_hex) + b"publisher").hexdigest()
        self._publisher = _keypair(derived).ss58_address

    @property
    def public_key(self) -> bytes:
        return bytes(self._keypair.public_key)

    @property
    def principal(self) -> str:
        return principal(self.public_key)

    @property
    def publisher(self) -> str:
        """The local research service's receiver for this identity."""
        return self._publisher

    def sign(self, payload: bytes) -> bytes:
        return bytes(self._keypair.sign(payload))

    def status_reader(self, body: bytes):
        """No validator status read: that is an intake path, which needs a
        registration."""
        raise PracticeIdentityRefused(REGISTRATION_REQUIRED)

    def __repr__(self):
        return "PracticeSigner(" + self.principal + ")"

    def __reduce__(self):
        raise TypeError("a practice identity is never serialised")


def context():
    """The local-practice chain context: network `local-practice`, an
    endpoint nothing listens on, and Carbon's netuid so the research
    service's own checks hold. No chain reader reads it (`sdk`)."""
    from .models import CARBON_NETUID, ChainContext

    genesis = "0x" + hashlib.sha256(b"carbon-local-practice").hexdigest()
    return ChainContext(
        LOCAL_PRACTICE,
        "ws://127.0.0.1:1",
        "carbon-local-practice",
        genesis,
        CARBON_NETUID,
    )


def is_local_practice(value) -> bool:
    """Whether `value` - a context, or a snapshot naming one - is
    local-practice."""
    ctx = getattr(value, "context", value)
    return getattr(ctx, "network", None) == LOCAL_PRACTICE


def refuse_local_practice(value) -> None:
    """For every network path: a local-practice context or snapshot is
    refused `registration_required`, typed, before anything is read or sent."""
    if is_local_practice(value):
        raise PracticeIdentityRefused(REGISTRATION_REQUIRED)


def snapshot(signer: PracticeSigner):
    """The local-practice snapshot: the practice identity and its local
    publisher, and nothing else, at a block that only moves forward."""
    from .adapter import translate

    block = int(time.time())
    graph = {
        "netuid": context().netuid,
        "num_uids": 2,
        "hotkeys": [signer.publisher, signer.ss58_address],
        "coldkeys": [signer.publisher, signer.ss58_address],
        "block_at_registration": [0, 0],
    }
    digest = "0x" + hashlib.sha256(b"local-practice:%d" % block).hexdigest()
    return translate(context(), block, digest, block * 1000, graph)
