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
BATTERY = "battery-fastcharge-ageing-development-v1"


#: Challenge id -> sealed adapter module, registered by validator-only code.
_REGISTERED = {}


def register(module):
    """Make a validator-side sealed adapter selectable (idempotent). Only Battery's
    (whose pinned value modules reach the attack harness) is registered this way; a
    different adapter already registered refuses."""
    if module.CHALLENGE != BATTERY:
        raise ValueError("only Battery's sealed adapter is registered")
    known = _REGISTERED.get(module.CHALLENGE)
    if known is not None and known is not module:
        raise ValueError("a different sealed adapter is registered for this Challenge")
    _REGISTERED[module.CHALLENGE] = module
    return module


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
    elif challenge == BATTERY:
        from carbon.challenge_kit import battery_sealed_pack as kit
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
    if challenge in (BATTERY, COOLING):
        # One sealed grid family and bank format, graded under every served
        # version of the same exam (Cooling 1.1-1.3): the family's own version.
        return kit.sealed_bank(document, records)
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
        from carbon.scoring import f08_sealed_dual_pack as sealed

        try:
            return sealed.adapter_for_bank(bank, version)
        except ValueError:  # a population with no sealed grader
            return None
    if challenge == F02:
        from carbon.scoring import f02_sealed_dual_pack as sealed

        try:
            return sealed.adapter_for_bank(bank, version)
        except ValueError:  # a population with no sealed grader
            return None
    if challenge == COOLING:
        from carbon.scoring import cooling_dual_pack, cooling_encoded_dual_pack

        # An interface change (1.3's output encoding) is graded by the adapter that
        # decodes it, never by the raw sealed adapter.
        if version == cooling_encoded_dual_pack.VERSION:
            return cooling_encoded_dual_pack.sealed_adapter(version)
        return cooling_dual_pack.sealed_adapter(version)
    if challenge == BATTERY:
        # Validator-only, never imported here (its value modules reach the attack
        # harness, which no miner surface may import): registered by validator code.
        sealed = _REGISTERED.get(BATTERY)
        if sealed is None:
            return None
        try:
            return sealed.adapter_for_bank(bank, version)
        except ValueError:  # a population with no sealed grader
            return None
    return None


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _pinned_case_bank(selected_pack):
    entry = selected_pack.private.get("case_bank")
    digest = entry.get("sha256") if type(entry) is dict else None
    return digest if type(digest) is str else None


def resolve(
    *,
    challenge,
    version,
    selected_pack,
    private_root,
    development_adapter,
    copy_hotkey=None,
):
    """``None`` (development pack) or ``(bank, adapter)`` for a sealed pack.

    With ``copy_hotkey`` (the validator's own) the package must carry the copy
    header (``copy_header_missing`` otherwise): the batch is verified as that
    validator's copy and graded in its canonical form (``copy_package``)."""
    kit = _kit(challenge)
    if kit is None:
        return None
    from carbon.challenge_kit import physical_pack

    pinned = _pinned_case_bank(selected_pack)
    if pinned is None:
        return None
    try:
        development = physical_pack.development_bank(challenge, version)
    except ValueError as exc:
        # Only "this version has no development bank" means no such pack; any other
        # failure of the development bank is not a reason to treat the pack as sealed.
        if "unknown public physical Challenge version" not in str(exc):
            raise
        development = None
    if (
        development is not None
        and "sha256:"
        + hashlib.sha256(kit.private_roles(development)["case_bank"]).hexdigest()
        == pinned
    ):
        return None
    if copy_hotkey is not None:
        from carbon.scoring import copy_package

        # A store-rebuilt canonical pack keeps the delivered copy beside it
        # (`.copies/<canonical digest>/`, local); a pack that is itself the copy
        # carries it in place.
        copies = Path(private_root).parent / ".copies" / Path(private_root).name
        beside = copies.is_dir() and not copies.is_symlink()
        try:
            copy_bank, bank = copy_package.receive(
                challenge,
                version,
                private_root,
                hotkey=copy_hotkey,
                copies_root=copies if beside else None,
            )
        except copy_package.CopyPackageRefused as exc:
            raise SealedBankRefused(exc.code) from exc
        received = bank if beside else copy_bank
    else:
        carried = read_batch(private_root)
        if carried is None:
            raise SealedBankRefused("sealed_bank_missing")
        try:
            received = bank = _build(challenge, kit, carried[0], carried[1], version)
        except ValueError as exc:  # SealedPackRefused is a ValueError
            raise SealedBankRefused("sealed_bank_malformed") from exc
    rebuilt = (
        "sha256:" + hashlib.sha256(kit.private_roles(received)["case_bank"]).hexdigest()
    )
    if rebuilt != pinned:
        raise SealedBankRefused("sealed_bank_mismatch")
    adapter = _adapter(challenge, bank, version, development_adapter)
    if adapter is None:
        raise SealedBankRefused("sealed_adapter_unavailable")
    return bank, adapter
