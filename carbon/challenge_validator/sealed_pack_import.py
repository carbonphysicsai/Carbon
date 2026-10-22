"""Sealed evaluation-pack delivery over the answer-key route (Workstream I2).

A sealed pack (`evaluation-pack.json` plus the role files it pins) is held by
Carbon's producer. It reaches a validator the same way hidden batches do, and
by no second channel:

1. **The producer** signs a package (`answer_key.package`) whose commitment
   names the pack by its manifest digest and carries a delivery window; the
   payload is the manifest and the role files, base64 in JSON.
2. **The distribution host** serves it to permit-holding hotkeys only
   (`distribution.py`, unchanged: the commitment has a challenge id, a
   fingerprint, and a window).
3. **A validator** (`answer_key sync`) verifies it in full, then imports it
   into its owner-only pack store. Verification, before anything is stored:
   the producer signature and payload digest (`answer_key.verify`); the
   manifest bytes against the committed digest; the manifest through
   `evaluation_pack.parse_pack` for the committed Challenge and version; the
   file set equal to exactly the files the manifest pins; every pinned digest
   reproduced; every path inside the pack. A failure imports nothing and is
   typed (`FAILED_INFRA` at the CLI), never a score.
4. **The receiver** takes the pack by digest from the store
   (`SealedPackStore.pack_directory`), re-verified at use, instead of an
   operator-typed directory.

The pack is owner-only everywhere and never reaches a miner surface; a path
is never printed (only the manifest digest). DEVELOPMENT only: no
qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath

from .answer_key import AnswerKeyRefused
from .evaluation_pack import UNAVAILABLE, EvaluationPackUnavailable, parse_pack

SEALED_COMMITMENT_SCHEMA = "carbon.challenge-validator.sealed-pack-commitment.v1"
SEALED_KIND = "sealed_pack"
DEPLOYMENT_SCHEMA = "carbon.challenge-validator.sealed-pack-deployment.v1"
MANIFEST_NAME = "evaluation-pack.json"
_COMMITMENT_FIELDS = {
    "schema",
    "kind",
    "challenge_id",
    "challenge_version",
    "fingerprint",
    "manifest_digest",
    "files",
    "window",
}
_PAYLOAD_FIELDS = {"manifest", "files"}
#: The signed pack-set manifest of a Challenge version (OWNER-FULL-EXAM-BANK-01):
#: the active batch packs by manifest digest; its key is the evaluation key.
SET_COMMITMENT_SCHEMA = "carbon.challenge-validator.sealed-pack-set-commitment.v1"
SET_KIND = "sealed_pack_set"
SETS_DIRECTORY = ".sets"
#: A producer-signed withdrawal (VALIDATOR-24) of a pack or a pack set: create-only
#: records beside the store. A withdrawn exam is never graded on or imported again;
#: its files stay for audit.
WITHDRAWN_DIRECTORY = ".withdrawn"
_SET_COMMITMENT_FIELDS = {
    "schema",
    "kind",
    "challenge_id",
    "challenge_version",
    "fingerprint",
    "set_key",
    "batches",
    "window",
}
#: Transport bounds only (the package body is bounded by `MAX_PACKAGE`).
MAX_FILES = 256
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
DELIVERED_DIRECTORY = ".delivered"


def commitment_for(challenge_id, challenge_version, manifest_bytes, files, window):
    """The commitment a producer signs for a pack (`files`: relpath -> bytes)."""
    digest = "sha256:" + _sha(manifest_bytes)
    return {
        "schema": SEALED_COMMITMENT_SCHEMA,
        "kind": SEALED_KIND,
        "challenge_id": challenge_id,
        "challenge_version": challenge_version,
        "fingerprint": digest,
        "manifest_digest": digest,
        "files": len(files),
        "window": window,
    }


def set_commitment_for(challenge_id, challenge_version, batch_digests, window):
    """The commitment a producer signs for a pack set: the Challenge version and
    the active batch packs. The set key (the evaluation key) is its fingerprint."""
    from . import sealed_exam_common as common

    document = common.pack_set_document(challenge_id, challenge_version, batch_digests)
    key = common.pack_set_key(document)
    return {
        "schema": SET_COMMITMENT_SCHEMA,
        "kind": SET_KIND,
        "challenge_id": challenge_id,
        "challenge_version": challenge_version,
        "fingerprint": key,
        "set_key": key,
        "batches": document["batches"],
        "window": window,
    }


def set_payload_for(commitment):
    """The signed payload of a set: its body (digests only, no exam content)."""
    return {"batches": list(commitment["batches"])}


def verify_set(commitment, payload):
    """Verify a pack-set commitment against its payload; returns the set body.
    The payload must be exactly the committed batches, in the set's one order,
    and the committed key must be the body's digest. Writes nothing."""
    from . import sealed_exam_common as common

    if (
        type(commitment) is not dict
        or set(commitment) != _SET_COMMITMENT_FIELDS
        or commitment["schema"] != SET_COMMITMENT_SCHEMA
        or commitment["kind"] != SET_KIND
        or commitment["fingerprint"] != commitment["set_key"]
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    try:
        document = common.pack_set_document(
            commitment["challenge_id"],
            commitment["challenge_version"],
            commitment["batches"],
        )
        key = common.pack_set_key(document)
    except common.PackSetRefused:
        raise AnswerKeyRefused("answer_key_pack_set") from None
    if (
        type(payload) is not dict
        or set(payload) != {"batches"}
        or payload["batches"] != document["batches"]
        or commitment["batches"] != document["batches"]
        or key != commitment["set_key"]
    ):
        raise AnswerKeyRefused("answer_key_pack_set")
    return document


def payload_for(manifest_bytes, files):
    """The signed payload: the manifest and the role files, base64."""
    return {
        "manifest": base64.b64encode(manifest_bytes).decode("ascii"),
        "files": {
            name: base64.b64encode(body).decode("ascii")
            for name, body in sorted(files.items())
        },
    }


def _sha(body):
    import hashlib

    return hashlib.sha256(body).hexdigest()


def _b64(value):
    if type(value) is not str:
        raise AnswerKeyRefused("answer_key_malformed")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, ValueError, UnicodeError):
        raise AnswerKeyRefused("answer_key_malformed") from None


def _safe_name(name):
    parts = PurePosixPath(name).parts if type(name) is str else ()
    if (
        not parts
        or name.startswith("/")
        or "\\" in name
        or any(part in ("", ".", "..") for part in parts)
        or name == MANIFEST_NAME
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    return name


def _pinned_paths(snapshot):
    """The file paths a snapshot's roles pin, with their digests (inline and
    unavailable roles pin none). Refuses a role that needs a store this import
    does not carry."""
    paths = {}
    for roles in (snapshot.public, snapshot.private):
        for entry in roles.values():
            if entry == UNAVAILABLE or "inline_bytes" in entry:
                continue
            if entry.get("kind") == "hidden_batch_store":
                raise AnswerKeyRefused("answer_key_sealed_pack_needs_store")
            paths[entry["path"]] = entry["sha256"]
    return paths


def verify_payload(commitment, payload):
    """Verify a pack payload against its commitment; returns
    `(manifest_bytes, {relpath: bytes}, snapshot)`. Writes nothing."""
    if (
        type(commitment) is not dict
        or set(commitment) != _COMMITMENT_FIELDS
        or commitment["schema"] != SEALED_COMMITMENT_SCHEMA
        or commitment["kind"] != SEALED_KIND
        or commitment["fingerprint"] != commitment["manifest_digest"]
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    if (
        type(payload) is not dict
        or set(payload) != _PAYLOAD_FIELDS
        or type(payload["files"]) is not dict
        or len(payload["files"]) > MAX_FILES
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    manifest = _b64(payload["manifest"])
    if "sha256:" + _sha(manifest) != commitment["manifest_digest"]:
        raise AnswerKeyRefused("answer_key_fingerprint_mismatch")
    try:
        snapshot = parse_pack(
            manifest,
            expected_digest=commitment["manifest_digest"],
            challenge_id=commitment["challenge_id"],
            challenge_version=commitment["challenge_version"],
        )
    except EvaluationPackUnavailable:
        raise AnswerKeyRefused("answer_key_sealed_pack_manifest") from None
    files = {_safe_name(name): _b64(body) for name, body in payload["files"].items()}
    if len(files) != commitment["files"]:
        raise AnswerKeyRefused("answer_key_fingerprint_mismatch")
    pinned = _pinned_paths(snapshot)
    if set(files) != set(pinned) or any(
        "sha256:" + _sha(files[name]) != digest for name, digest in pinned.items()
    ):
        raise AnswerKeyRefused("answer_key_sealed_pack_files")
    return manifest, files, snapshot


class SealedPackStore:
    """Owner-only pack directories, one per manifest digest, under ``root``."""

    def __init__(self, root):
        self.root = Path(root)

    def _directory(self, manifest_digest):
        # Operator-typed through --pack-digest: exactly 64 lowercase hex.
        if (
            type(manifest_digest) is not str
            or _DIGEST.fullmatch(manifest_digest) is None
        ):
            raise AnswerKeyRefused("answer_key_malformed")
        return self.root / manifest_digest.removeprefix("sha256:")

    def _owner_only_root(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = os.lstat(self.root)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise AnswerKeyRefused("answer_key_outbox_not_owner_only")

    def holds(self, commitment):
        try:
            if self.withdrawn(commitment["manifest_digest"]):
                return False
            return self._verified_directory(commitment) is not None
        except AnswerKeyRefused:
            return False

    def _verified_directory(self, commitment):
        directory = self._directory(commitment["manifest_digest"])
        if directory.is_symlink() or not directory.is_dir():
            return None
        manifest = (directory / MANIFEST_NAME).read_bytes()
        files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise AnswerKeyRefused("answer_key_sealed_pack_files")
            relative = path.relative_to(directory).as_posix()
            if path.is_file() and relative != MANIFEST_NAME:
                files[relative] = path.read_bytes()
        probe = dict(commitment, files=len(files))
        verify_payload(probe, payload_for(manifest, files))
        return directory

    def import_pack(self, commitment, payload):
        manifest, files, snapshot = verify_payload(commitment, payload)
        if self.withdrawn(commitment["manifest_digest"]):
            raise AnswerKeyRefused("answer_key_withdrawn")
        self._owner_only_root()
        directory = self._directory(commitment["manifest_digest"])
        if directory.exists():
            return commitment["manifest_digest"]
        staging = Path(tempfile.mkdtemp(prefix=".import-", dir=self.root))
        try:
            staging.chmod(0o700)
            (staging / MANIFEST_NAME).write_bytes(manifest)
            for name, body in files.items():
                target = staging / name
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.write_bytes(body)
                target.chmod(0o600)
            try:
                snapshot.verify_available(staging, staging)
            except EvaluationPackUnavailable:
                raise AnswerKeyRefused("answer_key_sealed_pack_files") from None
            os.rename(staging, directory)
            self._record_delivery(commitment)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return commitment["manifest_digest"]

    def _withdrawn_path(self, fingerprint):
        if type(fingerprint) is not str or _DIGEST.fullmatch(fingerprint) is None:
            raise AnswerKeyRefused("answer_key_malformed")
        return (
            self.root
            / WITHDRAWN_DIRECTORY
            / (fingerprint.removeprefix("sha256:") + ".json")
        )

    def withdrawn(self, fingerprint):
        """Whether a producer-signed withdrawal of this pack (its manifest digest)
        or pack set (its key) is recorded here."""
        return self._withdrawn_path(fingerprint).is_file()

    def withdraw(self, fingerprint, reason, block):
        """Record a verified withdrawal, create-only; a repeat of the same one is
        a no-op and a different one for the same fingerprint is refused. The
        exam files stay in place for audit but can never be used again."""
        record = {"fingerprint": fingerprint, "reason": reason, "block": block}
        path = self._withdrawn_path(fingerprint)
        self._owner_only_root()
        path.parent.mkdir(mode=0o700, exist_ok=True)
        raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        if path.exists():
            if path.read_bytes() != raw:
                raise AnswerKeyRefused("answer_key_withdrawal_changed")
            return
        path.write_bytes(raw)
        path.chmod(0o600)

    def _set_path(self, set_key):
        if type(set_key) is not str or _DIGEST.fullmatch(set_key) is None:
            raise AnswerKeyRefused("answer_key_malformed")
        return self.root / SETS_DIRECTORY / (set_key.removeprefix("sha256:") + ".json")

    def holds_set(self, commitment):
        try:
            if self.withdrawn(commitment["set_key"]):
                return False
            return self._set_path(commitment["set_key"]).is_file()
        except (AnswerKeyRefused, KeyError, TypeError):
            return False

    def import_pack_set(self, commitment, payload):
        """Record a verified pack-set commitment, create-only. The batch packs
        need not be here yet (a sync may deliver them in any order); they are
        verified, one by one, when the set is used (`pack_set`)."""
        verify_set(commitment, payload)
        if self.withdrawn(commitment["set_key"]):
            raise AnswerKeyRefused("answer_key_withdrawn")
        self._owner_only_root()
        record = self.root / SETS_DIRECTORY
        record.mkdir(mode=0o700, exist_ok=True)
        path = self._set_path(commitment["set_key"])
        if not path.exists():
            path.write_bytes(
                json.dumps(commitment, sort_keys=True, separators=(",", ":")).encode()
            )
            path.chmod(0o600)
        return commitment["set_key"]

    def pack_set(self, set_key, challenge_id, challenge_version):
        """The verified batch directories of a Challenge version's pack set, in
        the set's order: ``[(manifest_digest, directory)]``. Every batch must be
        in this store, re-verified now and delivered through the answer-key
        route; otherwise `AnswerKeyRefused` (an unset or partial set grades
        nothing)."""
        if self.withdrawn(set_key):
            raise AnswerKeyRefused("answer_key_pack_set_withdrawn")
        try:
            commitment = json.loads(self._set_path(set_key).read_bytes())
        except (OSError, ValueError):
            raise AnswerKeyRefused("answer_key_pack_set_missing") from None
        verify_set(commitment, set_payload_for(commitment))
        if (
            commitment["set_key"] != set_key
            or commitment["challenge_id"] != challenge_id
            or commitment["challenge_version"] != challenge_version
        ):
            raise AnswerKeyRefused("answer_key_wrong_challenge")
        batches = []
        for digest in commitment["batches"]:
            if self.withdrawn(digest):
                raise AnswerKeyRefused("answer_key_pack_set_batch_withdrawn")
            if not self.delivered(digest, challenge_id, challenge_version):
                raise AnswerKeyRefused("answer_key_pack_set_batch_missing")
            batches.append(
                (digest, self.pack_directory(digest, challenge_id, challenge_version))
            )
        return batches

    def _record_delivery(self, commitment):
        """Record that this pack arrived through the answer-key route: the
        signed commitment, create-only, outside the pack directory. A pack
        placed in the store any other way has no such record."""
        record = self.root / DELIVERED_DIRECTORY
        record.mkdir(mode=0o700, exist_ok=True)
        name = record / (
            commitment["manifest_digest"].removeprefix("sha256:") + ".json"
        )
        if not name.exists():
            name.write_bytes(
                json.dumps(commitment, sort_keys=True, separators=(",", ":")).encode()
            )
            name.chmod(0o600)

    def delivered(self, manifest_digest, challenge_id, challenge_version):
        """Whether the verified pack in this store was delivered through the
        answer-key route for this Challenge version: the delivery record
        exists, names exactly this pack and Challenge, and the pack
        re-verifies now. This is the one definition of a sealed delivery
        (Validator, Workstream I5): never the pack's shape."""
        try:
            self.pack_directory(manifest_digest, challenge_id, challenge_version)
            recorded = json.loads(
                (
                    self.root
                    / DELIVERED_DIRECTORY
                    / (manifest_digest.removeprefix("sha256:") + ".json")
                ).read_bytes()
            )
        except (AnswerKeyRefused, OSError, ValueError):
            return False
        return (
            type(recorded) is dict
            and recorded.get("schema") == SEALED_COMMITMENT_SCHEMA
            and recorded.get("kind") == SEALED_KIND
            and recorded.get("manifest_digest") == manifest_digest
            and recorded.get("challenge_id") == challenge_id
            and recorded.get("challenge_version") == challenge_version
        )

    def pack_directory(self, manifest_digest, challenge_id, challenge_version):
        """The verified directory of a stored pack, for the receiver; raises
        `AnswerKeyRefused` when it is absent, altered, or another Challenge's."""
        directory = self._directory(manifest_digest)
        if self.withdrawn(manifest_digest):
            raise AnswerKeyRefused("answer_key_sealed_pack_withdrawn")
        if directory.is_symlink() or not (directory / MANIFEST_NAME).is_file():
            raise AnswerKeyRefused("answer_key_sealed_pack_missing")
        probe = {
            "schema": SEALED_COMMITMENT_SCHEMA,
            "kind": SEALED_KIND,
            "challenge_id": challenge_id,
            "challenge_version": challenge_version,
            "fingerprint": manifest_digest,
            "manifest_digest": manifest_digest,
            "files": 0,
            "window": None,
        }
        if self._verified_directory(probe) is None:
            raise AnswerKeyRefused("answer_key_sealed_pack_missing")
        return directory


class SealedPackAdapter:
    """What `answer_key.sync` and `import_local` need of a validator adapter,
    for one sealed pack Challenge version. It never draws, solves or scores."""

    def __init__(self, challenge_id, challenge_version, store):
        self.challenge_id = challenge_id
        self.challenge_version = challenge_version
        self.store = store

    @classmethod
    def from_deployment(cls, path, repository=None):
        document = json.loads(Path(path).read_text())
        if (
            type(document) is not dict
            or set(document) != {"schema", "challenge_id", "challenge_version", "store"}
            or document["schema"] != DEPLOYMENT_SCHEMA
        ):
            raise AnswerKeyRefused("answer_key_malformed")
        return cls(
            document["challenge_id"],
            document["challenge_version"],
            SealedPackStore(document["store"]),
        )

    def holds_answer_key(self, commitment):
        if commitment.get("schema") == SET_COMMITMENT_SCHEMA:
            return self.store.holds_set(commitment)
        return self.store.holds(commitment)

    def import_answer_key(self, commitment, payload):
        if (
            commitment.get("challenge_id") != self.challenge_id
            or commitment.get("challenge_version") != self.challenge_version
        ):
            raise AnswerKeyRefused("answer_key_wrong_challenge")
        if commitment.get("schema") == SET_COMMITMENT_SCHEMA:
            return self.store.import_pack_set(commitment, payload)
        return self.store.import_pack(commitment, payload)

    def withdraw_answer_key(self, manifest):
        """A verified producer withdrawal of a pack or a pack set (the manifest's
        fingerprint is the pack's manifest digest or the set's key)."""
        if manifest.get("challenge_id") != self.challenge_id:
            raise AnswerKeyRefused("answer_key_wrong_challenge")
        self.store.withdraw(
            manifest["fingerprint"], manifest["reason"], manifest["block"]
        )


__all__ = [
    "DEPLOYMENT_SCHEMA",
    "SEALED_COMMITMENT_SCHEMA",
    "SEALED_KIND",
    "SET_COMMITMENT_SCHEMA",
    "SET_KIND",
    "SealedPackAdapter",
    "SealedPackStore",
    "commitment_for",
    "payload_for",
    "set_commitment_for",
    "set_payload_for",
    "verify_payload",
    "verify_set",
]
