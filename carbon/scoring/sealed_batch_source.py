"""The sealed bank of a sealed evaluation pack (E4; Validator ruling, carriage (a)).

A sealed pack pins a ``case_bank`` role that is not the development bank's. The
dual producer must grade it on the sealed batch, never on the exposed
development bank (a score against the wrong bank is a silent wrong grade). The
signed package therefore carries the sealed batch document and its terminal
records beside the pack, as ``sealed-batch.json`` in the pack's private root.

``resolve`` returns ``None`` for a pack whose ``case_bank`` is the development
bank's (the caller keeps its development path), the sealed ``(bank, adapter)``
when the carried batch rebuilds exactly the pack's pinned ``case_bank`` bytes,
and refuses otherwise: ``sealed_bank_missing`` when the batch is not carried,
``sealed_bank_mismatch`` when it does not reproduce the pinned role. Dispatch is
static per Challenge (no computed imports). DEVELOPMENT only; the batch is
private and never reaches a miner surface.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SEALED_BATCH_FILE = "sealed-batch.json"
SCHEMA = "carbon.challenge-validator.sealed-batch-carriage.v1"
_FIELDS = {"schema", "document", "records"}
_MAX_BYTES = 8 * 1024 * 1024
MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"
F02 = "f02"
F08 = "f08-ribbed-bracket"


class SealedBankRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def batch_bytes(document, records) -> bytes:
    """The carried batch file's canonical bytes (`document`, `records`)."""
    return (
        json.dumps(
            {"schema": SCHEMA, "document": document, "records": list(records)},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def read_batch(private_root):
    """``(document, records)`` from the pack's private root, or None if absent."""
    path = Path(private_root) / SEALED_BATCH_FILE
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size > _MAX_BYTES:
        raise SealedBankRefused("sealed_bank_malformed")
    try:
        body = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise SealedBankRefused("sealed_bank_malformed") from None
    if (
        type(body) is not dict
        or set(body) != _FIELDS
        or body["schema"] != SCHEMA
        or type(body["records"]) is not list
    ):
        raise SealedBankRefused("sealed_bank_malformed")
    return body["document"], body["records"]


def _kit(challenge):
    """The Challenge's sealed pack module (static dispatch)."""
    if challenge == MOTOR:
        from carbon.challenge_kit import motor_sealed_pack as kit
    elif challenge == COOLING:
        from carbon.challenge_kit import cooling_sealed_pack as kit
    elif challenge == F02:
        from carbon.challenge_kit import f02_sealed_pack as kit
    elif challenge == F08:
        from carbon.challenge_kit import f08_sealed_pack as kit
    else:
        return None
    return kit


def _build(challenge, kit, document, records, version):
    if challenge == MOTOR:
        from carbon.challenge_validator import motor_sealed_grid as grid

        try:
            grid.check_document(document)
        except ValueError:
            return kit.sealed_bank(document, records, version=version)
        return kit.grid_bank(document, records, version=version)
    return kit.sealed_bank(document, records, version=version)


def _adapter(challenge, bank, version, development_adapter):
    """The sealed grader for ``bank``, or None when the Challenge has none."""
    if challenge == MOTOR:
        from carbon.scoring import motor_sealed_dual_pack as sealed

        try:
            return sealed.adapter_for_bank(bank, version)
        except ValueError:  # a population with no sealed grader
            return None
    if challenge == F08:
        from carbon.scoring import f08_dual_pack

        return f08_dual_pack.sealed_adapter(version)
    if challenge == F02:
        return development_adapter  # bank_kind() reads the bank's population
    return None


def _pinned_case_bank(selected_pack):
    entry = selected_pack.private.get("case_bank")
    digest = entry.get("sha256") if type(entry) is dict else None
    return digest if type(digest) is str else None


def resolve(*, challenge, version, selected_pack, private_root, development_adapter):
    """``None`` (development pack) or ``(bank, adapter)`` for a sealed pack."""
    kit = _kit(challenge)
    if kit is None:
        return None
    from carbon.challenge_kit import physical_pack

    pinned = _pinned_case_bank(selected_pack)
    if pinned is None:
        return None
    development = physical_pack.development_bank(challenge, version)
    if "sha256:" + hashlib.sha256(kit.private_roles(development)["case_bank"]).hexdigest() == pinned:
        return None
    carried = read_batch(private_root)
    if carried is None:
        raise SealedBankRefused("sealed_bank_missing")
    try:
        bank = _build(challenge, kit, carried[0], carried[1], version)
    except ValueError as exc:  # SealedPackRefused is a ValueError
        raise SealedBankRefused("sealed_bank_malformed") from exc
    rebuilt = "sha256:" + hashlib.sha256(kit.private_roles(bank)["case_bank"]).hexdigest()
    if rebuilt != pinned:
        raise SealedBankRefused("sealed_bank_mismatch")
    adapter = _adapter(challenge, bank, version, development_adapter)
    if adapter is None:
        raise SealedBankRefused("sealed_adapter_unavailable")
    return bank, adapter
