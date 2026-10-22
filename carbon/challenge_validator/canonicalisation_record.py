"""The signed, append-only record that a sealed batch in custody was re-packed in
its canonical form (traceable copies; Validator ruling, carriage (a)).

A legacy batch keeps its values and references: it is re-packed from its custody
document and records alone, with no re-solve. The record binds the batch's source
fingerprint (today's custody bytes) to the canonical fingerprint every copy shares
and to the canonical re-pack's digest, signed by the producer key in its own
domain. Records are create-only (one per source fingerprint): a canonical identity
is never re-pointed. DEVELOPMENT only.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .answer_key import AnswerKeyRefused, key_id, verify_in

SCHEMA = "carbon.challenge-validator.canonicalisation-record.v1"
DOMAIN = b"carbon.canonicalisation-record/1\x00"
_FIELDS = {
    "schema",
    "challenge",
    "challenge_version",
    "source_fingerprint",
    "canonical_fingerprint",
    "repack_digest",
    "re_solved",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def manifest_for(challenge, version, document, records):
    """``(manifest, canonical batch bytes)`` for one custody batch."""
    import hashlib

    from carbon.scoring import copy_package

    raw, source_fp, canonical_fp = copy_package.canonical_batch(
        challenge, version, document, records
    )
    return (
        {
            "schema": SCHEMA,
            "challenge": challenge,
            "challenge_version": version,
            "source_fingerprint": source_fp,
            "canonical_fingerprint": canonical_fp,
            "repack_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "re_solved": False,
        },
        raw,
    )


def sign(signer, manifest):
    """The producer's signed record (``signer``: an ``answer_key.ProducerKey``)."""
    return {
        "manifest": manifest,
        "key_id": key_id(signer.public_key),
        "public_key": signer.public_key,
        "signature": signer.sign_in(DOMAIN, manifest),
    }


def verify(record, public_key):
    """The record's manifest when it is ``public_key``'s signature in this
    domain over a well-formed manifest, else None."""
    try:
        manifest = record["manifest"]
        if (
            record["public_key"] != public_key
            or record["key_id"] != key_id(public_key)
            or type(manifest) is not dict
            or set(manifest) != _FIELDS
            or manifest["schema"] != SCHEMA
            or manifest["re_solved"] is not False
            or not all(
                type(manifest[n]) is str and _DIGEST.fullmatch(manifest[n])
                for n in (
                    "source_fingerprint",
                    "canonical_fingerprint",
                    "repack_digest",
                )
            )
            or not verify_in(DOMAIN, manifest, record["signature"], public_key)
        ):
            return None
    except (KeyError, TypeError):
        return None
    return manifest


class RecordStore:
    """Create-only records, one file per source fingerprint."""

    def __init__(self, root):
        self.root = Path(root)

    def _path(self, source_fingerprint):
        if not _DIGEST.fullmatch(source_fingerprint or ""):
            raise AnswerKeyRefused("answer_key_malformed")
        return self.root / (source_fingerprint[7:] + ".json")

    def append(self, record, public_key):
        manifest = verify(record, public_key)
        if manifest is None:
            raise AnswerKeyRefused("answer_key_signature")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        body = (
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        try:
            fd = os.open(
                self._path(manifest["source_fingerprint"]),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            raise AnswerKeyRefused("canonicalisation_record_exists") from None
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        return manifest

    def get(self, source_fingerprint, public_key):
        """The verified manifest for a source fingerprint, or None."""
        path = self._path(source_fingerprint)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            return verify(json.loads(path.read_bytes()), public_key)
        except (OSError, ValueError):
            return None
