"""A Challenge's public training pool: retired bank cases, published
automatically (VALIDATOR-23; OWNER-AUTO-PUBLISH-RETIRED-01).

The producer writes one signed training file per bank and publication
(`bank.BankLedger.publish`). The distribution host serves them to anyone,
read-only, at `GET /carbon/v1/training/<challenge>` (the listing) and
`GET /carbon/v1/training/<challenge>/<file>`.

Anyone can check a file with `verify`:
- the manifest's signature against Carbon's producer public key;
- the records against the manifest's records digest;
- each case's `(case_id, inputs, reference)` against its tranche's committed
  Merkle root.

A file only ever holds cases that retired at E, after every window that drew
them was revealed. Nothing here can publish an unretired case.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from . import bank_proof

TRAINING_FILE_SCHEMA = "carbon.challenge-validator.training-file.v1"
TRAINING_MANIFEST_SCHEMA = "carbon.challenge-validator.training-manifest.v1"
TRAINING_PATH = "/carbon/v1/training/"
CHALLENGE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,80}")
FILE_NAME = re.compile(r"[0-9a-f]{64}\.json")


class TrainingRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def verify(value, producer_public_key):
    """A training file, checked in full. Returns its manifest."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from .answer_key import DOMAIN, key_id
    from .answer_key import _canonical as signed_bytes

    try:
        if value["schema"] != TRAINING_FILE_SCHEMA:
            raise TrainingRefused("training_malformed")
        manifest, records = value["manifest"], value["records"]
        if value["public_key"] != producer_public_key or value["key_id"] != key_id(
            producer_public_key
        ):
            raise TrainingRefused("training_wrong_producer")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(producer_public_key)).verify(
            bytes.fromhex(value["signature"]),
            DOMAIN + signed_bytes(manifest),
        )
    except TrainingRefused:
        raise
    except InvalidSignature:
        raise TrainingRefused("training_signature") from None
    except (KeyError, TypeError, ValueError):
        raise TrainingRefused("training_malformed") from None
    if (
        type(manifest) is not dict
        or manifest.get("schema") != TRAINING_MANIFEST_SCHEMA
        or type(records) is not list
        or manifest.get("cases") != len(records)
        or manifest.get("records_digest") != _digest(records)
    ):
        raise TrainingRefused("training_records_mismatch")
    roots = {t.get("tranche"): t.get("root") for t in manifest.get("tranches", [])}
    for record in records:
        try:
            ok = bank_proof.verify(
                record["case_id"],
                record["inputs"],
                record["reference"],
                record["proof"],
                roots.get(record["tranche"]),
            )
        except (KeyError, TypeError):
            ok = False
        if not ok:
            raise TrainingRefused("training_proof")
    return manifest


class TrainingPool:
    """The distribution host's `training/<challenge>/` files, each verified
    before it is listed or served. A file that fails is never served."""

    def __init__(self, directory, producer_public_key):
        self.directory = Path(directory)
        self.producer_public_key = producer_public_key

    def files(self, challenge_id):
        if type(challenge_id) is not str or not CHALLENGE_ID.fullmatch(challenge_id):
            raise TrainingRefused("training_unknown_challenge")
        folder = self.directory / challenge_id
        if not folder.is_dir():
            return {}
        found = {}
        for path in sorted(folder.glob("*.json")):
            if not FILE_NAME.fullmatch(path.name):
                continue
            try:
                info = os.lstat(path)
                if not stat.S_ISREG(info.st_mode):
                    continue
                value = json.loads(path.read_text())
                manifest = verify(value, self.producer_public_key)
            except (OSError, ValueError, TrainingRefused):
                continue
            if manifest["challenge_id"] != challenge_id:
                continue
            if (
                path.name
                != manifest["records_digest"].removeprefix("sha256:") + ".json"
            ):
                continue
            found[path.name] = value
        return found

    def answer(self, path):
        """`(status, value)` for a `GET` under `TRAINING_PATH`."""
        rest = path[len(TRAINING_PATH) :].strip("/").split("/")
        try:
            if len(rest) == 1:
                files = self.files(rest[0])
                return 200, {
                    "challenge_id": rest[0],
                    "files": [
                        {"file": name, "manifest": value["manifest"]}
                        for name, value in sorted(files.items())
                    ],
                }
            if len(rest) == 2 and FILE_NAME.fullmatch(rest[1]):
                files = self.files(rest[0])
                if rest[1] in files:
                    return 200, files[rest[1]]
        except TrainingRefused as refused:
            return 404, {"refused": refused.code}
        return 404, {"refused": "training_not_found"}


__all__ = ["TRAINING_PATH", "TrainingPool", "TrainingRefused", "verify"]
