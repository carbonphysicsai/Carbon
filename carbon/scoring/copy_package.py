"""Per-validator copies of a sealed batch on the answer-key route (c'; Validator
ruling, carriage (a)).

The signed package carries the pack and the sealed batch file (`sealed-batch.json`,
document + records, ``sealed_batch_source``). A validator's copy renames the batch's
opaque ids and reorders its document from a Carbon-held per-validator key
(``copy_derivation``); a ``copy-header.json`` rides beside it and carries digests and
the validator hotkey only (no permutation, no id map). The receiver rebuilds the
copy's bank, checks the copy digest, canonicalises by content, checks the canonical
digest, and grades the canonical bank, so every validator's grade is byte-identical.

Not a watermark: it changes ids and order, never a value that is scored. DEVELOPMENT
only; the key's custody and the owner's acceptance are mainnet-gate items.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from carbon.scoring import copy_derivation as cd
from carbon.scoring import sealed_batch_source as source

HEADER_FILE = "copy-header.json"
HEADER_SCHEMA = "carbon.challenge-validator.copy-header.v1"
_FIELDS = {
    "schema",
    "challenge",
    "challenge_version",
    "canonical_digest",
    "copy_digest",
    "validator_hotkey",
}
_DIGEST = ("canonical_digest", "copy_digest")


class CopyPackageRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def header_bytes(header) -> bytes:
    return (json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _build(challenge, version, document, records):
    kit = source._kit(challenge)
    if kit is None:
        raise CopyPackageRefused("copy_challenge_unregistered")
    try:
        return kit, source._build(challenge, kit, document, records, version)
    except ValueError as exc:
        raise CopyPackageRefused("copy_batch_malformed") from exc


def make_copy(challenge, version, document, records, *, key, hotkey):
    """``(batch file bytes, header bytes)`` for one validator's copy of the batch.

    The copy's document lists its cases in the derived order under the derived
    ids; its records carry the same renames."""
    if type(hotkey) is not str or not hotkey:
        raise CopyPackageRefused("copy_hotkey_missing")
    opaque = cd.opaque_for(challenge)
    _kit, bank = _build(challenge, version, document, records)
    derived, _objective, mapping = cd.derive_copy_with_mapping(
        bank, None, key=key, opaque=opaque
    )
    new_document, new_records = _renamed(
        document, records, mapping, derived["case_ids"], opaque
    )
    raw = source.batch_bytes(new_document, new_records)
    header = {
        "schema": HEADER_SCHEMA,
        "challenge": challenge,
        "challenge_version": version,
        "canonical_digest": cd.content_digest(bank, opaque=opaque),
        "copy_digest": _sha(raw),
        "validator_hotkey": hotkey,
    }
    return raw, header_bytes(header)


def _renamed(document, records, mapping, ordered_ids, opaque):
    """The batch with its opaque ids renamed by ``mapping`` and its cases listed in
    ``ordered_ids`` (the new ids) order."""
    inverse = {fresh: old for old, fresh in mapping.items()}
    cases = {c["case_id"]: c for c in document["cases"]}
    new_document = copy.deepcopy(document)
    new_document["cases"] = [
        dict(copy.deepcopy(cases[inverse.get(new, new)]), case_id=new)
        for new in ordered_ids
    ]
    new_records = []
    for record in records:
        record = copy.deepcopy(record)
        for name in opaque:
            if name in record:
                record[name] = mapping.get(record[name], record[name])
        new_records.append(record)
    new_records.sort(key=lambda r: r["case_id"])
    return new_document, new_records


def canonical_batch(challenge, version, document, records):
    """``(batch file bytes, source fingerprint, canonical fingerprint)``: the
    batch re-packed in its canonical form (rank ids, content order), from its
    custody document and records alone (no re-solve; values unchanged). The source
    fingerprint pins today's custody bytes, the canonical fingerprint the exam's
    content identity every copy shares."""
    opaque = cd.opaque_for(challenge)
    _kit, bank = _build(challenge, version, document, records)
    canonical = cd.canonicalize(bank, opaque=opaque)
    n = len(bank["case_ids"])
    ids = {
        cd._cell_key(canonical, k, opaque): canonical["case_ids"][k] for k in range(n)
    }
    mapping = {
        bank["case_ids"][i]: ids[cd._cell_key(bank, i, opaque)] for i in range(n)
    }
    mapping = {old: new for old, new in mapping.items() if old != new}
    new_document, new_records = _renamed(
        document, records, mapping, canonical["case_ids"], opaque
    )
    raw = source.batch_bytes(new_document, new_records)
    return (
        raw,
        _sha(source.batch_bytes(document, records)),
        cd.content_digest(canonical, opaque=opaque),
    )


def read_header(private_root):
    """The copy header beside the pack, or None."""
    path = Path(private_root) / HEADER_FILE
    if path.is_symlink() or not path.is_file():
        return None
    try:
        header = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise CopyPackageRefused("copy_header_malformed") from None
    if (
        type(header) is not dict
        or set(header) != _FIELDS
        or header["schema"] != HEADER_SCHEMA
        or not all(type(header[n]) is str for n in _FIELDS)
        or not all(header[n].startswith("sha256:") for n in _DIGEST)
    ):
        raise CopyPackageRefused("copy_header_malformed")
    return header


def receive(challenge, version, private_root, *, hotkey, copies_root=None):
    """The copy's rebuilt bank and its canonical form, verified.

    Refuses a package without a header (``copy_header_missing``), a header for
    another Challenge, version or validator, a batch that is not the header's copy
    (``copy_digest_mismatch``), or one whose content is not the canonical exam it
    names (``canonical_digest_mismatch``). Returns ``(copy bank, canonical bank)``."""
    # The delivered copy lives beside the pack (``copies_root``) when the pack in
    # ``private_root`` is the canonical one the store rebuilt from it.
    private_root = private_root if copies_root is None else copies_root
    header = read_header(private_root)
    if header is None:
        raise CopyPackageRefused("copy_header_missing")
    if (
        header["challenge"] != challenge
        or header["challenge_version"] != version
        or header["validator_hotkey"] != hotkey
    ):
        raise CopyPackageRefused("copy_header_mismatch")
    path = Path(private_root) / source.SEALED_BATCH_FILE
    if path.is_symlink() or not path.is_file():
        raise source.SealedBankRefused("sealed_bank_missing")
    if _sha(path.read_bytes()) != header["copy_digest"]:
        raise CopyPackageRefused("copy_digest_mismatch")
    carried = source.read_batch(private_root)
    _kit, bank = _build(challenge, version, carried[0], carried[1])
    opaque = cd.opaque_for(challenge)
    canonical = cd.canonicalize(bank, opaque=opaque)
    if cd.content_digest(canonical, opaque=opaque) != header["canonical_digest"]:
        raise CopyPackageRefused("canonical_digest_mismatch")
    return bank, canonical
