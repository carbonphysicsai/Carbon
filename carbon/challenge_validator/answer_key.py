"""The shared answer key: signed batch packages and validator import
(VALIDATOR-19 slice 2; OWNER-SHARED-ANSWER-KEY-01).

Carbon's producer draws and solves each hidden batch once (slice 1). Every
validator then scores every miner on that same batch and those same solver
results:

1. **The producer** signs a package for each sealed batch: its public
   commitment, plus the payload (the batch and its reference records). The
   signature uses Carbon's producer key. The producer host is never
   internet-facing; it pushes packages to the distribution host.
2. **The distribution host** (`distribution.py`) serves packages over HTTPS.
   It answers only `btauth/1`-signed requests from hotkeys holding a
   validator permit, and logs every fetch per hotkey.
3. **A validator** fetches the package with its own hotkey and verifies it:
   - the producer's signature against the pinned producer public key;
   - the payload against the signed digest;
   - the batch against the committed fingerprint;
   - the references against the committed references digest;
   - the commitment's contract and rule against its own.
   Only then does it import the package into its own owner-only state. A
   missing or mismatched package imports nothing and returns a typed code: it
   is infrastructure, never a score, and the validator never draws or solves
   a replacement.

    python -m carbon.challenge_validator.answer_key keygen --out PRODUCER.key
    python -m carbon.challenge_validator.answer_key sync --config FETCH.json
    python -m carbon.challenge_validator.answer_key import --deployment DEPLOYMENT.json \\
        --producer-public-key HEX --outbox PRODUCER_DIR/outbox/CHALLENGE

A package carries hidden cases and references: it is owner-only everywhere.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE_SCHEMA = "carbon.challenge-validator.answer-key-package.v1"
MANIFEST_SCHEMA = "carbon.challenge-validator.answer-key-manifest.v1"
FETCH_CONFIG_SCHEMA = "carbon.challenge-validator.answer-key-fetch-config.v1"
REQUEST_SCHEMA = "carbon.challenge-validator.answer-key-request.v1"
PATH = "/carbon/v1/answer-key"
DOMAIN = b"carbon.answer-key/1\x00"
#: A package body limit: an engineering transport bound, not a scientific value.
MAX_PACKAGE = 64 * 1024 * 1024


class AnswerKeyRefused(ValueError):
    """A typed refusal; its code carries no case, input or reference."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _owner_only_file(path):
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise AnswerKeyRefused("answer_key_file_missing") from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise AnswerKeyRefused("answer_key_file_not_owner_only")
    return path


def read_private(path):
    return json.loads(_owner_only_file(path).read_bytes())


def write_private(path, value):
    """Write an owner-only file once; an existing file must hold `value`."""
    path = Path(path)
    if path.exists():
        if read_private(path) != value:
            raise AnswerKeyRefused("answer_key_file_changed")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")


# --- the producer's key ---------------------------------------------------------------


def key_id(public_key):
    return (
        "carbon-producer-" + hashlib.sha256(bytes.fromhex(public_key)).hexdigest()[:16]
    )


class ProducerKey:
    """Carbon's ed25519 producer key, on the producer host only. Its private
    bytes never print."""

    __slots__ = ("_key", "public_key")

    def __init__(self, raw):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        key = Ed25519PrivateKey.from_private_bytes(raw)
        object.__setattr__(self, "_key", key)
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        object.__setattr__(self, "public_key", public.hex())

    def __setattr__(self, name, value):
        raise AttributeError("a producer key is immutable")

    def __repr__(self):
        return "ProducerKey(<redacted>)"

    def __reduce__(self):
        raise TypeError("a producer key is never serialized")

    @staticmethod
    def create(path):
        raw = os.urandom(32)
        # Built before the file exists: a missing `cryptography` (the
        # `archive` dependency group) fails here and leaves no key file
        # behind to block a rerun.
        ProducerKey(raw)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        return ProducerKey.load(path)

    @staticmethod
    def load(path):
        raw = _owner_only_file(path).read_bytes()
        if len(raw) != 32:
            raise AnswerKeyRefused("answer_key_key_malformed")
        return ProducerKey(raw)

    def sign(self, manifest):
        return self._key.sign(DOMAIN + _canonical(manifest)).hex()


# --- packages -------------------------------------------------------------------------


def package(key, commitment, payload):
    """One signed package: the producer commitment and its payload."""
    from .batch_source import COMMITMENT_SCHEMA, SERVED_KINDS

    if type(key) is not ProducerKey:
        raise TypeError("a ProducerKey is required")
    if commitment.get("schema") != COMMITMENT_SCHEMA:
        raise AnswerKeyRefused("answer_key_commitment_malformed")
    if commitment.get("kind") not in SERVED_KINDS:
        # Producer-only sets (tuning, confirmation) are never packaged.
        raise AnswerKeyRefused("answer_key_kind_not_served")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "commitment": commitment,
        "payload_digest": _digest(payload),
    }
    return {
        "schema": PACKAGE_SCHEMA,
        "manifest": manifest,
        "key_id": key_id(key.public_key),
        "public_key": key.public_key,
        "signature": key.sign(manifest),
        "payload": payload,
    }


def verify_manifest(value, producer_public_key):
    """The signed manifest of a package (or of its public listing entry),
    checked against the pinned producer key. Returns the commitment."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from .batch_source import COMMITMENT_SCHEMA, SERVED_KINDS

    try:
        manifest = value["manifest"]
        if value["public_key"] != producer_public_key or value["key_id"] != key_id(
            producer_public_key
        ):
            raise AnswerKeyRefused("answer_key_wrong_producer")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(producer_public_key)).verify(
            bytes.fromhex(value["signature"]), DOMAIN + _canonical(manifest)
        )
    except AnswerKeyRefused:
        raise
    except InvalidSignature:
        raise AnswerKeyRefused("answer_key_signature") from None
    except (KeyError, TypeError, ValueError):
        raise AnswerKeyRefused("answer_key_malformed") from None
    commitment = manifest.get("commitment") if type(manifest) is dict else None
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or type(commitment) is not dict
        or commitment.get("schema") != COMMITMENT_SCHEMA
    ):
        raise AnswerKeyRefused("answer_key_malformed")
    if commitment.get("kind") not in SERVED_KINDS:
        raise AnswerKeyRefused("answer_key_kind_not_served")
    return commitment


def verify(value, producer_public_key):
    """A whole package: the manifest, then the payload against its signed
    digest. Returns `(commitment, payload)`."""
    if type(value) is not dict or value.get("schema") != PACKAGE_SCHEMA:
        raise AnswerKeyRefused("answer_key_malformed")
    commitment = verify_manifest(value, producer_public_key)
    payload = value.get("payload")
    try:
        matches = _digest(payload) == value["manifest"]["payload_digest"]
    except (TypeError, ValueError):
        matches = False
    if not matches:
        raise AnswerKeyRefused("answer_key_payload_mismatch")
    return commitment, payload


def listing_entry(value):
    """A package without its payload: what any permit holder may list."""
    return {k: value[k] for k in ("manifest", "key_id", "public_key", "signature")}


# --- the validator's fetch ------------------------------------------------------------


def load_fetch_config(path):
    config = read_private(path)
    required = {
        "schema",
        "url",
        "receiver",
        "hotkey",
        "producer_public_key",
        "deployment",
        "challenge_id",
    }
    if (
        type(config) is not dict
        or config.get("schema") != FETCH_CONFIG_SCHEMA
        or not required <= set(config)
        or set(config) - required - {"signer_socket", "ca"}
    ):
        raise AnswerKeyRefused("answer_key_config_malformed")
    if not config["url"].startswith("https://") and not config["url"].startswith(
        "http://127.0.0.1"
    ):
        raise AnswerKeyRefused("answer_key_needs_tls")
    return config


class Fetcher:
    """POSTs `btauth/1`-signed requests with the validator's own hotkey."""

    def __init__(self, url, signer, receiver, *, ca=None, post=None, sign=None):
        """`sign(body, receiver=, nonce_ns=, path=)` returns the `btauth/1`
        headers; by default the validator's external signer signs."""
        self.url = url.rstrip("/") + PATH
        self.signer, self.receiver = signer, receiver
        self.ca = ca
        self._post = post or self._https
        self._sign = sign or self._btauth

    def _btauth(self, body, *, receiver, nonce_ns, path):
        from carbon.chain.auth import BittensorMessageSigner

        return BittensorMessageSigner(self.signer).sign(
            body, receiver=receiver, nonce_ns=nonce_ns, path=path
        )

    def _https(self, url, body, headers):
        import ssl
        import urllib.error
        import urllib.request

        context = (
            None if self.ca is None else ssl.create_default_context(cafile=self.ca)
        )
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=120, context=context
            ) as answer:
                return answer.status, json.loads(answer.read(MAX_PACKAGE))
        except urllib.error.HTTPError as failure:
            return failure.code, json.loads(failure.read(MAX_PACKAGE) or b"{}")

    def ask(self, challenge_id, fingerprint=None):
        body = _canonical(
            {
                "schema": REQUEST_SCHEMA,
                "challenge_id": challenge_id,
                "fingerprint": fingerprint,
            }
        )
        headers = self._sign(
            body, receiver=self.receiver, nonce_ns=time.time_ns(), path=PATH
        )
        try:
            status, answer = self._post(self.url, body, headers)
        except (OSError, ValueError):
            raise AnswerKeyRefused("answer_key_unreachable") from None
        if status != 200 or type(answer) is not dict:
            code = answer.get("refused") if type(answer) is dict else None
            raise AnswerKeyRefused(str(code or "answer_key_unavailable"))
        return answer


def sync(adapter, fetcher, producer_public_key, challenge_id):
    """Import every listed package this validator does not hold yet.

    Each listing entry is checked before its package is fetched, and each
    package is verified in full before anything is imported. Returns public
    values only: fingerprints and verdicts.
    """
    if adapter.challenge_id != challenge_id:
        raise AnswerKeyRefused("answer_key_wrong_challenge")
    listed = fetcher.ask(challenge_id).get("packages")
    if type(listed) is not list:
        raise AnswerKeyRefused("answer_key_malformed")
    results = []
    for entry in listed:
        commitment = verify_manifest(entry, producer_public_key)
        fingerprint = commitment["fingerprint"]
        if commitment["challenge_id"] != challenge_id:
            raise AnswerKeyRefused("answer_key_wrong_challenge")
        if adapter.holds_answer_key(commitment):
            results.append({"fingerprint": fingerprint, "state": "HELD"})
            continue
        value = fetcher.ask(challenge_id, fingerprint).get("package")
        fetched, payload = verify(value, producer_public_key)
        if fetched != commitment:
            raise AnswerKeyRefused("answer_key_listing_mismatch")
        adapter.import_answer_key(commitment, payload)
        results.append({"fingerprint": fingerprint, "state": "IMPORTED"})
    return {"challenge_id": challenge_id, "packages": results}


def import_local(adapter, producer_public_key, outbox):
    """Import every package in a same-host producer's `outbox` directory: the
    development pool on the producer host (the Test Lead's ruling,
    2026-10-07), without a distribution host or a network hop.

    Each package is verified in full exactly as a fetched one is (`verify`,
    then the adapter's own re-derivation of fingerprint, references, quiz and
    identities); a package that fails is refused by code and imports nothing,
    and the rest still import. Public values only: fingerprints and
    verdicts."""
    directory = Path(outbox)
    try:
        info = os.lstat(directory)
    except FileNotFoundError:
        raise AnswerKeyRefused("answer_key_outbox_missing") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise AnswerKeyRefused("answer_key_outbox_not_owner_only")
    results = []
    for path in sorted(directory.glob("*.json")):
        try:
            commitment, payload = verify(read_private(path), producer_public_key)
            if commitment["challenge_id"] != adapter.challenge_id:
                raise AnswerKeyRefused("answer_key_wrong_challenge")
            if adapter.holds_answer_key(commitment):
                state = "HELD"
            else:
                adapter.import_answer_key(commitment, payload)
                state = "IMPORTED"
            results.append({"fingerprint": commitment["fingerprint"], "state": state})
        except AnswerKeyRefused as refused:
            results.append(
                {"file": path.name, "state": "REFUSED", "code": refused.code}
            )
    return {"challenge_id": adapter.challenge_id, "packages": results}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.answer_key")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("keygen").add_argument("--out", required=True)
    sub.add_parser("sync").add_argument("--config", required=True)
    local = sub.add_parser("import")
    local.add_argument("--deployment", required=True)
    local.add_argument("--producer-public-key", required=True)
    local.add_argument("--outbox", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            from .battery import BatteryAdapter

            adapter = BatteryAdapter.from_deployment(
                args.deployment, repository=REPOSITORY
            )
            result = import_local(adapter, args.producer_public_key, args.outbox)
        elif args.command == "keygen":
            key = ProducerKey.create(args.out)
            result = {"public_key": key.public_key, "key_id": key_id(key.public_key)}
        else:
            from carbon.chain.external_signer import connect_signer

            from .battery import BatteryAdapter

            config = load_fetch_config(args.config)
            socket = config.get("signer_socket")
            signer = connect_signer(
                config["hotkey"], socket_path=None if socket is None else Path(socket)
            )
            adapter = BatteryAdapter.from_deployment(
                config["deployment"], repository=REPOSITORY
            )
            fetcher = Fetcher(
                config["url"], signer, config["receiver"], ca=config.get("ca")
            )
            result = sync(
                adapter, fetcher, config["producer_public_key"], config["challenge_id"]
            )
    except AnswerKeyRefused as refused:
        # FAILED_INFRA: nothing was imported for the refused package, and
        # this validator never draws or solves a replacement.
        print(json.dumps({"state": "FAILED_INFRA", "refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
