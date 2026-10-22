"""The per-hotkey evaluation-pack route (E4; Validator ruling, OWNER-SEALED-EXAM-
DELIVERY-01).

A second route on the answer-key distribution host. It has its own signing domain
(`carbon.evaluation-pack/1`), the same admission as the first route (btauth/1 plus a
validator permit on the finalized chain) and its own per-hotkey fetch log. Unlike
the first route it never serves one set of bytes to every validator:

- the **producer** derives each permitted hotkey's traceable copy (`copy_package`,
  from a Carbon-held per-validator key) and signs it as that hotkey's package;
- the **host** holds those signed packages only, never the producer root or the key
  they were derived from, and serves a hotkey **only its own** package;
- the **fetch log** binds hotkey -> copy digest, so a leaked exam narrows to one
  validator, not to the set that fetched the same bytes.

A hotkey with no issued copy gets a typed refusal (`evaluation_pack_copy_not_issued`),
never another hotkey's package. DEVELOPMENT only; security-sensitive (AGENTS.md
section 13): not a security audit.
"""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path

from .answer_key import (
    AnswerKeyRefused,
    Fetcher,
    ProducerKey,
    _canonical,
    _digest,
    key_id,
    read_private,
    verify_in,
)
from .distribution import DistributionService

PACK_PATH = "/carbon/v1/evaluation-pack"
PACK_DOMAIN = b"carbon.evaluation-pack/1\x00"
PACK_REQUEST_SCHEMA = "carbon.challenge-validator.evaluation-pack-request.v1"
PACK_MANIFEST_SCHEMA = "carbon.challenge-validator.evaluation-pack-manifest.v1"
PACK_PACKAGE_SCHEMA = "carbon.challenge-validator.evaluation-pack-package.v1"
_COPY_FIELDS = {"validator_hotkey", "copy_digest", "canonical_digest"}


def copy_package(key, commitment, payload, *, hotkey, copy_digest, canonical_digest):
    """One signed per-hotkey package: the producer commitment, its payload, and the
    hotkey and copy it is for, all under the evaluation-pack domain."""
    from .sealed_pack_import import SEALED_COMMITMENT_SCHEMA, SEALED_KIND

    if type(key) is not ProducerKey:
        raise TypeError("a ProducerKey is required")
    if (
        commitment.get("schema") != SEALED_COMMITMENT_SCHEMA
        or commitment.get("kind") != SEALED_KIND
    ):
        raise AnswerKeyRefused("answer_key_kind_not_served")
    if type(hotkey) is not str or not hotkey:
        raise AnswerKeyRefused("answer_key_malformed")
    manifest = {
        "schema": PACK_MANIFEST_SCHEMA,
        "commitment": commitment,
        "payload_digest": _digest(payload),
        "copy": {
            "validator_hotkey": hotkey,
            "copy_digest": copy_digest,
            "canonical_digest": canonical_digest,
        },
    }
    return {
        "schema": PACK_PACKAGE_SCHEMA,
        "manifest": manifest,
        "key_id": key_id(key.public_key),
        "public_key": key.public_key,
        "signature": key.sign_in(PACK_DOMAIN, manifest),
        "payload": payload,
    }


def verify_manifest(value, producer_public_key):
    """`(commitment, copy)` of a package or listing entry, checked against the pinned
    producer key in the evaluation-pack domain."""
    from .sealed_pack_import import SEALED_COMMITMENT_SCHEMA, SEALED_KIND

    try:
        manifest = value["manifest"]
        if value["public_key"] != producer_public_key or value["key_id"] != key_id(
            producer_public_key
        ):
            raise AnswerKeyRefused("answer_key_wrong_producer")
        if not verify_in(
            PACK_DOMAIN, manifest, value["signature"], producer_public_key
        ):
            raise AnswerKeyRefused("answer_key_signature")
        commitment, copy = manifest["commitment"], manifest["copy"]
    except AnswerKeyRefused:
        raise
    except (KeyError, TypeError, ValueError):
        raise AnswerKeyRefused("answer_key_malformed") from None
    if (
        manifest.get("schema") != PACK_MANIFEST_SCHEMA
        or type(commitment) is not dict
        or commitment.get("schema") != SEALED_COMMITMENT_SCHEMA
        or commitment.get("kind") != SEALED_KIND
        or type(copy) is not dict
        or set(copy) != _COPY_FIELDS
        or not all(type(copy[n]) is str and copy[n] for n in _COPY_FIELDS)
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    return commitment, copy


def verify_package(value, producer_public_key):
    """`(commitment, payload, copy)` of a whole package: the manifest, then the
    payload against its signed digest."""
    if type(value) is not dict or value.get("schema") != PACK_PACKAGE_SCHEMA:
        raise AnswerKeyRefused("answer_key_malformed")
    commitment, copy = verify_manifest(value, producer_public_key)
    payload = value.get("payload")
    try:
        matches = _digest(payload) == value["manifest"]["payload_digest"]
    except (TypeError, ValueError):
        matches = False
    if not matches:
        raise AnswerKeyRefused("answer_key_payload_mismatch")
    return commitment, payload, copy


def listing_entry(value):
    """A package without its payload."""
    return {k: value[k] for k in ("manifest", "key_id", "public_key", "signature")}


class CopyInbox:
    """The signed per-hotkey packages the producer pushed: one owner-only
    subdirectory per hotkey, `<hotkey>/<anything>.json`. A package is served only
    from its own hotkey's directory AND only when it names that hotkey."""

    def __init__(self, directory, producer_public_key, *, withdrawn=None):
        self.directory = Path(directory)
        self.producer_public_key = producer_public_key
        #: A callable `(challenge_id) -> set of withdrawn fingerprints`.
        self.withdrawn = withdrawn or (lambda challenge_id: set())

    def packages(self, challenge_id, hotkey, *, block=None):
        if type(hotkey) is not str or "/" in hotkey or hotkey in ("", ".", ".."):
            raise AnswerKeyRefused("answer_key_malformed")
        info = os.lstat(self.directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise AnswerKeyRefused("answer_key_inbox_not_owner_only")
        found, skipped = {}, 0
        folder = self.directory / hotkey
        if not folder.is_dir() or folder.is_symlink():
            return found, skipped
        withdrawn = self.withdrawn(challenge_id)
        for path in sorted(folder.glob("*.json")):
            try:
                value = read_private(path)
                commitment, _payload, copy = verify_package(
                    value, self.producer_public_key
                )
            except (AnswerKeyRefused, OSError, ValueError):
                skipped += 1
                continue
            if (
                copy["validator_hotkey"] != hotkey
                or commitment["challenge_id"] != challenge_id
                or commitment["fingerprint"] in withdrawn
                or copy["copy_digest"] in withdrawn
            ):
                continue
            window = commitment.get("window")
            if block is not None and (
                type(window) is not dict or window.get("retire_block", 0) <= block
            ):
                continue
            found[commitment["fingerprint"]] = value
        return found, skipped

    def withdrawals(self, challenge_id):
        return []


class PackDistributionService(DistributionService):
    """The evaluation-pack route: same admission, per-hotkey packages, a fetch log
    that binds hotkey -> copy digest."""

    route = PACK_PATH
    request_schema = PACK_REQUEST_SCHEMA

    def __init__(self, inbox, *, host_service=None, **kwargs):
        super().__init__(inbox, **kwargs)
        self.host_service = host_service

    def _packages(self, challenge_id, block, hotkey):
        return self.inbox.packages(challenge_id, hotkey, block=block)

    def _served_extra(self, package):
        _commitment, copy = verify_manifest(package, self.inbox.producer_public_key)
        return {
            "copy_digest": copy["copy_digest"],
            "canonical_digest": copy["canonical_digest"],
            "route": "evaluation-pack",
        }


def attach(service, copies_directory, producer_public_key):
    """Give a first-route service the second route (`service.pack_service`), sharing
    its admission, nonces, log and delivery signer."""
    pack = PackDistributionService(
        CopyInbox(copies_directory, producer_public_key),
        receiver=service.receiver,
        verifier=service.verifier,
        permits=service.permits,
        nonces=service.nonces,
        log=service.log,
        clock_ns=service.clock_ns,
        signer=service.signer,
    )
    service.pack_service = pack
    return pack


class PackFetcher(Fetcher):
    """The validator's client for the per-hotkey route; it verifies in the
    evaluation-pack domain, so a first-route package never verifies here."""

    def __init__(self, url, signer, receiver, **kwargs):
        super().__init__(url, signer, receiver, **kwargs)
        self.url = url.rstrip("/") + PACK_PATH

    def ask(self, challenge_id, fingerprint=None):
        body = _canonical(
            {
                "schema": PACK_REQUEST_SCHEMA,
                "challenge_id": challenge_id,
                "fingerprint": fingerprint,
            }
        )
        headers = self._sign(
            body, receiver=self.receiver, nonce_ns=time.time_ns(), path=PACK_PATH
        )
        try:
            status, answer = self._post(self.url, body, headers)
        except (OSError, ValueError):
            raise AnswerKeyRefused("answer_key_unreachable") from None
        if status != 200 or type(answer) is not dict:
            code = answer.get("refused") if type(answer) is dict else None
            raise AnswerKeyRefused(str(code or "answer_key_unavailable"))
        return answer


__all__ = [
    "PACK_DOMAIN",
    "PACK_PATH",
    "CopyInbox",
    "PackDistributionService",
    "PackFetcher",
    "attach",
    "copy_package",
    "verify_package",
]
