"""Issuing and importing a validator's traceable copy of a sealed pack (E4, option
(1): canonical identity; Validator ruling, OWNER-SEALED-EXAM-DELIVERY-01).

Every identity that leaves a validator or is compared between validators keys on the
**canonical manifest digest** M_c: the digest of the pack whose bank-order-sensitive
private roles (case_bank, reference_rows, solver_evidence) are built from the
canonical bank. Each hotkey is delivered its own copy pack (the same manifest with
those three roles permuted and renamed from a Carbon-held per-validator key), so its
manifest digest M_h differs per validator and stays **local**.

Producer (`issue_copy`): from the canonical pack and the sealed batch, derive a
hotkey's copy and sign it as that hotkey's package; the commitment's `fingerprint` is
M_c, its `manifest_digest` is M_h.

Validator (`import_copy`): verify the copy as a pack, bind its batch to its roles,
canonicalise by content, rebuild the canonical pack, and require its manifest digest
to be the signed M_c. The store then holds the delivered copy under `.copies/<M_c>/`
(local) and the canonical pack at `<M_c>/`, an ordinary pack: grading, pack sets, KOTH
bindings, withdrawals and every shared record see only M_c. DEVELOPMENT only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import tempfile
from pathlib import Path

from carbon.scoring import copy_derivation as cd
from carbon.scoring import copy_package as cp
from carbon.scoring import sealed_batch_source as source

from . import copy_route
from . import sealed_pack_import as spi
from .answer_key import AnswerKeyRefused
from .evaluation_pack import EvaluationPackUnavailable, parse_pack

#: The private roles whose bytes depend on the copy (row order and ids).
COPY_ROLES = ("case_bank", "reference_rows", "solver_evidence")
COPIES_DIRECTORY = ".copies"
_PAYLOAD_FIELDS = {"manifest", "files", "copy"}
_COPY_PAYLOAD_FIELDS = {"batch", "header", "canonical_manifest"}


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(value):
    return spi._b64(value)


def validator_key(master_key, hotkey):
    """K_v = HMAC(K_master, hotkey): the per-validator derivation key, derived on
    the producer host only (K_master never leaves custody)."""
    if type(master_key) is not bytes or len(master_key) < 16:
        raise AnswerKeyRefused("copy_master_key_invalid")
    return hmac.new(master_key, hotkey.encode("utf-8"), hashlib.sha256).digest()


def _dump(manifest):
    return (
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _manifest_with(manifest_bytes, roles):
    """The manifest with the COPY_ROLES' pins replaced by those of ``roles``
    (role -> bytes), re-serialised."""
    body = json.loads(manifest_bytes)
    for role in COPY_ROLES:
        entry = body["private"][role]
        if type(entry) is not dict or "sha256" not in entry:
            raise AnswerKeyRefused("copy_pack_roles")
        entry["sha256"] = _sha(roles[role])
    return _dump(body), body


def _role_paths(body):
    return {role: body["private"][role]["path"] for role in COPY_ROLES}


def issue_copy(
    key,
    master_key,
    *,
    challenge,
    version,
    canonical_manifest,
    canonical_files,
    document,
    records,
    hotkey,
    window,
):
    """The signed per-hotkey package for ``hotkey`` (producer side).

    ``canonical_manifest``/``canonical_files`` are the canonical pack's bytes (the
    re-pack); ``document``/``records`` its sealed batch in canonical form."""
    kit = source._kit(challenge)
    if kit is None:
        raise AnswerKeyRefused("copy_challenge_unregistered")
    raw_batch, raw_header = cp.make_copy(
        challenge,
        version,
        document,
        records,
        key=validator_key(master_key, hotkey),
        hotkey=hotkey,
    )
    carried = json.loads(raw_batch)
    copy_bank = source._build(
        challenge, kit, carried["document"], carried["records"], version
    )
    roles = kit.private_roles(copy_bank)
    canonical_body = json.loads(canonical_manifest)
    paths = _role_paths(canonical_body)
    manifest_h, _ = _manifest_with(canonical_manifest, roles)
    files = dict(canonical_files)
    for role in COPY_ROLES:
        if paths[role] not in files:
            raise AnswerKeyRefused("copy_pack_roles")
        files[paths[role]] = roles[role]
    commitment = spi.commitment_for(challenge, version, manifest_h, files, window)
    canonical_digest = _sha(canonical_manifest)
    commitment["fingerprint"] = canonical_digest
    header = json.loads(raw_header)
    payload = spi.payload_for(manifest_h, files)
    payload["copy"] = {
        "batch": _b64(raw_batch),
        "header": _b64(raw_header),
        "canonical_manifest": _b64(canonical_manifest),
    }
    return copy_route.copy_package(
        key,
        commitment,
        payload,
        hotkey=hotkey,
        copy_digest=header["copy_digest"],
        canonical_digest=canonical_digest,
    )


def _fail(code):
    raise AnswerKeyRefused(code)


def verify_copy(commitment, payload, copy, *, hotkey):
    """Verify a copy package in full; returns what the store needs.

    ``copy`` is the signed manifest's copy block. Writes nothing."""
    if (
        type(payload) is not dict
        or set(payload) != _PAYLOAD_FIELDS
        or type(payload["copy"]) is not dict
        or set(payload["copy"]) != _COPY_PAYLOAD_FIELDS
    ):
        _fail("answer_key_malformed")
    if copy["validator_hotkey"] != hotkey:
        _fail("copy_wrong_hotkey")
    canonical_digest = commitment["fingerprint"]
    if copy["canonical_digest"] != canonical_digest:
        _fail("copy_canonical_mismatch")
    # 1. The copy as an ordinary pack, under its own (local) manifest digest.
    own = dict(commitment, fingerprint=commitment["manifest_digest"])
    manifest_h, files, snapshot = spi.verify_payload(
        own, {"manifest": payload["manifest"], "files": payload["files"]}
    )
    # 2. The carried batch and header.
    raw_batch = _unb64(payload["copy"]["batch"])
    raw_header = _unb64(payload["copy"]["header"])
    canonical_manifest = _unb64(payload["copy"]["canonical_manifest"])
    if _sha(canonical_manifest) != canonical_digest:
        _fail("copy_canonical_manifest")
    try:
        header = json.loads(raw_header)
    except ValueError:
        _fail("copy_header_malformed")
    challenge, version = commitment["challenge_id"], commitment["challenge_version"]
    if (
        type(header) is not dict
        or header.get("validator_hotkey") != hotkey
        or header.get("challenge") != challenge
        or header.get("challenge_version") != version
        or header.get("copy_digest") != _sha(raw_batch)
        or header.get("copy_digest") != copy["copy_digest"]
    ):
        _fail("copy_header_mismatch")
    # 3. Bind the batch to the pack's roles, canonicalise by content.
    kit = source._kit(challenge)
    if kit is None:
        _fail("copy_challenge_unregistered")
    try:
        carried = json.loads(raw_batch)
        copy_bank = source._build(
            challenge, kit, carried["document"], carried["records"], version
        )
        opaque = cd.opaque_for(challenge)
        canonical_bank = cd.canonicalize(copy_bank, opaque=opaque)
    except (ValueError, KeyError, TypeError, cd.CopyRefused):
        _fail("copy_batch_malformed")
    copy_roles = kit.private_roles(copy_bank)
    body_h = json.loads(manifest_h)
    paths = _role_paths(body_h)
    for role in COPY_ROLES:
        if files.get(paths[role]) != copy_roles[role]:
            _fail("copy_batch_not_the_pack")
    if cd.content_digest(canonical_bank, opaque=opaque) != header["canonical_digest"]:
        _fail("copy_canonical_content")
    # The canonical pack's roles come from the canonical *batch* rebuilt through the
    # Challenge's own kit (the same path the re-pack takes), not from the in-memory
    # canonical bank: the kit derives the grid ids from content.
    try:
        canonical_raw, _source_fp, _fp = cp.canonical_batch(
            challenge, version, carried["document"], carried["records"]
        )
        canonical_carried = json.loads(canonical_raw)
        canonical_roles = kit.private_roles(
            source._build(
                challenge,
                kit,
                canonical_carried["document"],
                canonical_carried["records"],
                version,
            )
        )
    except (ValueError, KeyError, TypeError, cp.CopyPackageRefused):
        _fail("copy_batch_malformed")
    # 4. The canonical pack, rebuilt, must be the signed one.
    body_c = json.loads(canonical_manifest)
    for role in COPY_ROLES:
        if body_c["private"][role].get("sha256") != _sha(canonical_roles[role]):
            _fail("copy_canonical_roles")
    expected_h, _ = _manifest_with(canonical_manifest, copy_roles)
    if expected_h != manifest_h:
        _fail("copy_manifest_not_the_canonical_one")
    canonical_files = dict(files)
    for role in COPY_ROLES:
        canonical_files[paths[role]] = canonical_roles[role]
    try:
        canonical_snapshot = parse_pack(
            canonical_manifest,
            expected_digest=canonical_digest,
            challenge_id=challenge,
            challenge_version=version,
        )
    except EvaluationPackUnavailable:
        _fail("answer_key_sealed_pack_manifest")
    return {
        "snapshot": snapshot,
        "canonical_snapshot": canonical_snapshot,
        "manifest": manifest_h,
        "files": files,
        "canonical_manifest": canonical_manifest,
        "canonical_files": canonical_files,
        "raw_batch": raw_batch,
        "raw_header": raw_header,
    }


def copies_directory(store_root, canonical_digest):
    return (
        Path(store_root) / COPIES_DIRECTORY / canonical_digest.removeprefix("sha256:")
    )


def import_copy(store, package, producer_public_key, *, hotkey):
    """Verify and store this validator's copy package; returns the canonical
    manifest digest M_c (the only identity that leaves this machine)."""
    commitment, payload, copy = copy_route.verify_package(package, producer_public_key)
    canonical_digest = commitment["fingerprint"]
    if store.withdrawn(canonical_digest):
        _fail("answer_key_withdrawn")
    built = verify_copy(commitment, payload, copy, hotkey=hotkey)
    store._owner_only_root()
    directory = store._directory(canonical_digest)
    if directory.exists():
        return canonical_digest
    local = copies_directory(store.root, canonical_digest)
    local.parent.mkdir(mode=0o700, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".import-", dir=store.root))
    try:
        staging.chmod(0o700)
        # The canonical pack: an ordinary pack under M_c.
        (staging / "canonical").mkdir(mode=0o700)
        (staging / "canonical" / spi.MANIFEST_NAME).write_bytes(
            built["canonical_manifest"]
        )
        for name, body in built["canonical_files"].items():
            target = staging / "canonical" / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(body)
            target.chmod(0o600)
        try:
            built["canonical_snapshot"].verify_available(
                staging / "canonical", staging / "canonical"
            )
        except EvaluationPackUnavailable:
            _fail("answer_key_sealed_pack_files")
        # The delivered copy, kept local with its signed commitment.
        (staging / "copy").mkdir(mode=0o700)
        (staging / "copy" / spi.MANIFEST_NAME).write_bytes(built["manifest"])
        for name, body in built["files"].items():
            target = staging / "copy" / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(body)
            target.chmod(0o600)
        for name, body in (
            (source.SEALED_BATCH_FILE, built["raw_batch"]),
            (cp.HEADER_FILE, built["raw_header"]),
            (
                "commitment.json",
                json.dumps(commitment, sort_keys=True, separators=(",", ":")).encode(),
            ),
        ):
            (staging / "copy" / name).write_bytes(body)
            (staging / "copy" / name).chmod(0o600)
        os.rename(staging / "copy", local)
        os.rename(staging / "canonical", directory)
        store._record_delivery(
            dict(
                commitment,
                manifest_digest=canonical_digest,
                files=len(built["canonical_files"]),
            )
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return canonical_digest


def sync_copies(store, fetcher, producer_public_key, challenge_id, *, hotkey):
    """Import every listed copy this validator does not hold yet (the per-hotkey
    route: the host only ever lists this hotkey's own packages)."""
    results = []
    listed = fetcher.ask(challenge_id)["packages"]
    for entry in listed:
        commitment, _copy = copy_route.verify_manifest(entry, producer_public_key)
        fingerprint = commitment["fingerprint"]
        if store.withdrawn(fingerprint):
            results.append({"fingerprint": fingerprint, "state": "WITHDRAWN"})
            continue
        if store.holds(dict(commitment, manifest_digest=fingerprint)):
            results.append({"fingerprint": fingerprint, "state": "HELD"})
            continue
        package = fetcher.ask(challenge_id, fingerprint)["package"]
        import_copy(store, package, producer_public_key, hotkey=hotkey)
        results.append({"fingerprint": fingerprint, "state": "IMPORTED"})
    return {"packages": results}


def sync_sets(store, fetcher, producer_public_key, challenge_id, challenge_version):
    """Import the signed pack-set commitment(s) of one Challenge version (first
    route). A set names its batches by canonical manifest digest only (digests, no
    exam content), so every validator receives the same bytes; the batches
    themselves come from this hotkey's own copies (`sync_copies`). Sets of other
    versions and other kinds are skipped; verified withdrawals apply first.

    Returns ``{"sets": [{"set_key", "state"}]}``."""
    from .answer_key import apply_withdrawals, verify, verify_manifest

    answer = fetcher.ask(challenge_id)
    listed, notices = answer.get("packages"), answer.get("withdrawals", [])
    if type(listed) is not list or type(notices) is not list:
        raise AnswerKeyRefused("answer_key_malformed")
    adapter = spi.SealedPackAdapter(challenge_id, challenge_version, store)
    withdrawn = apply_withdrawals(adapter, notices, producer_public_key, challenge_id)
    results = [{"set_key": f, "state": "WITHDRAWN"} for f in withdrawn]
    for entry in listed:
        commitment = verify_manifest(entry, producer_public_key)
        if (
            commitment.get("schema") != spi.SET_COMMITMENT_SCHEMA
            or commitment["challenge_id"] != challenge_id
            or commitment["challenge_version"] != challenge_version
        ):
            continue
        key = commitment["set_key"]
        if key in withdrawn:
            continue
        if store.holds_set(commitment):
            results.append({"set_key": key, "state": "HELD"})
            continue
        value = fetcher.ask(challenge_id, commitment["fingerprint"]).get("package")
        fetched, payload = verify(value, producer_public_key)
        if fetched != commitment:
            raise AnswerKeyRefused("answer_key_listing_mismatch")
        store.import_pack_set(commitment, payload)
        results.append({"set_key": key, "state": "IMPORTED"})
    return {"sets": results}
