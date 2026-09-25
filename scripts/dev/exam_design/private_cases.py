"""Private exam cases for the exam-design campaign, from a private root with a public commitment.

Earlier roles (``plans.py``) derive their seeds from a *public* campaign string,
so anyone can regenerate them: they are **offline development evidence**, not a
hidden exam, and are labelled that way. Private roles use this module instead:

* a 32-byte root, written once with ``os.urandom`` to
  ``~/.carbon-exam-design/private_root.bin`` (mode 600, outside the repository,
  never sent to a pod, never logged);
* seeds derived with the repository's own ``carbon.seeding`` HKDF path
  (``MockContext`` + ``derive_mock_seed``), bound to a ``SeedPin`` naming this
  experiment's challenge, generator and scoring identities - the same pattern as
  ``development_session.research_profile``;
* a **public commitment** ``sha256(domain || root)`` plus the ``SeedPin``
  binding, committed to the repository before any private case is generated,
  so the root can later be revealed and every case re-derived and checked.

The namespace is the mock one on purpose: this is DEVELOPMENT research with no
official or LIVE authority, and nothing here touches official seed state.
Pods receive only the case *inputs* they must solve, like any validator would.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

ROOT_PATH = Path.home() / ".carbon-exam-design" / "private_root.bin"
COMMIT_DOMAIN = b"carbon.exam-design.private-root.v1"
CHALLENGE_ID, CHALLENGE_VERSION = "battery-charge-degradation-dev", "0.1"


def _root() -> bytes:
    if not ROOT_PATH.exists():
        ROOT_PATH.parent.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(ROOT_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(os.urandom(32))
    if ROOT_PATH.is_symlink() or ROOT_PATH.stat().st_size != 32:
        raise ValueError("invalid private root")
    return ROOT_PATH.read_bytes()


def _pin_material() -> dict:
    from scripts.dev.exam_design import battery_reference, scoring

    gen = hashlib.sha256(Path(battery_reference.__file__).read_bytes()).hexdigest()
    sco = hashlib.sha256(Path(scoring.__file__).read_bytes()).hexdigest()
    binding = hashlib.sha256(
        f"{CHALLENGE_ID}/{CHALLENGE_VERSION}/{gen}/{sco}".encode()
    ).hexdigest()
    return {
        "challenge": [CHALLENGE_ID, CHALLENGE_VERSION],
        "generator_version": battery_reference.SPEC_VERSION,
        "generator_digest": "sha256:" + gen,
        "scoring_version": "exam-design-scoring-v1",
        "scoring_digest": "sha256:" + sco,
        "evaluation_binding": binding,
    }


def commitment(pin: dict | None = None) -> dict:
    pin = pin or _pin_material()
    return {
        "schema": "carbon.exam-design.private-commitment.v1",
        "root_commitment": hashlib.sha256(COMMIT_DOMAIN + _root()).hexdigest(),
        "seed_pin": pin,
        "derivation": "carbon.seeding.derive_mock_seed(MockContext(MockEntropy(root), SeedPin), RoleKey(role), i)",
    }


def _context(pin: dict):
    from carbon.registry.model import ChallengeKey
    from carbon.seeding.model import (
        EvaluationBinding,
        MockContext,
        MockEntropy,
        SeedPin,
    )

    sp = SeedPin(
        ChallengeKey(*pin["challenge"]),
        pin["generator_version"],
        pin["generator_digest"],
        pin["scoring_version"],
        pin["scoring_digest"],
        EvaluationBinding(bytes.fromhex(pin["evaluation_binding"])),
    )
    return MockContext(MockEntropy(_root()), sp)


def cases(role: str, n: int, bounds: dict, pin: dict) -> list[dict]:
    """``n`` uniform draws over ``bounds`` for ``role``; draw ``i`` uses its own derived seed."""
    from carbon.seeding.derive import derive_mock_seed
    from carbon.seeding.model import RoleKey

    ctx = _context(pin)
    out = []
    for i in range(n):
        seed = derive_mock_seed(
            ctx, RoleKey(role.lower()), i
        )  # carbon.seeding role keys are lowercase canonical
        material = seed.as_backend_bytes()
        rng = np.random.default_rng(
            int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        )
        out.append(
            {
                "case_id": f"{role}-{i:04d}",
                **{
                    k: float(np.round(rng.uniform(lo, hi), 4))
                    for k, (lo, hi) in bounds.items()
                },
            }
        )
    return out


def _keystream(key: bytes, n: int) -> bytes:
    import hmac

    out = bytearray()
    counter = 0
    while len(out) < n:
        out += hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:n])


def seal(obj, name: str) -> tuple[bytes, dict]:
    """Encrypt a private job list for delivery to a pod.

    HMAC-SHA256 counter-mode keystream under a fresh 32-byte key (stdlib only).
    The ciphertext may be committed and fetched by hash like any other file; the
    key stays in ``~/.carbon-exam-design/keys`` and reaches the pod only as an
    environment value. The plaintext digest is recorded so the revealed jobs can
    be checked against it after the campaign.
    """
    import json

    plain = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    key = os.urandom(32)
    kdir = ROOT_PATH.parent / "keys"
    kdir.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(kdir / f"{name}.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    cipher = bytes(a ^ b for a, b in zip(plain, _keystream(key, len(plain))))
    return cipher, {
        "name": name,
        "plaintext_sha256": hashlib.sha256(plain).hexdigest(),
        "ciphertext_sha256": hashlib.sha256(cipher).hexdigest(),
        "bytes": len(cipher),
    }


def unseal(cipher: bytes, key_hex: str):
    import json

    key = bytes.fromhex(key_hex)
    return json.loads(
        bytes(a ^ b for a, b in zip(cipher, _keystream(key, len(cipher))))
    )


def key_hex(name: str) -> str:
    return (ROOT_PATH.parent / "keys" / f"{name}.key").read_bytes().hex()
