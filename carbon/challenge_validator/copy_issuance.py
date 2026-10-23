"""The issuance job: sign each permitted hotkey's traceable copy of a sealed pack and
write it where the distribution host serves it (E4; OWNER-TESTNET-EXAM-KEYS-01).

    python -m carbon.challenge_validator.copy_issuance issue --config JOB.json
    python -m carbon.challenge_validator.copy_issuance publish-set --config SET.json

Runs on the custody host only. It reads the producer key and K_master from owner-only
files there, derives K_v = HMAC(K_master, hotkey) per hotkey, and writes
`<copies>/<hotkey>/<canonical digest>.json` create-only, owner-only. K_master and the
producer key are never printed, logged, exported or written anywhere else; the output
is counts and digests only. A hotkey that already has a copy of this pack keeps it
(create-only: a copy is never re-derived under a different window). DEVELOPMENT only.

Job config (owner-only JSON): schema, producer_key, master_key (file paths),
challenge_id, challenge_version, pack (directory holding the canonical
`evaluation-pack.json` and its files), batch (the canonical `sealed-batch.json`),
copies (output directory), window, hotkeys (a JSON list file of permitted hotkeys,
read from the finalized chain by the operator).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import copy_delivery, copy_route
from .answer_key import (
    AnswerKeyRefused,
    ProducerKey,
    _owner_only_file,
    read_private,
)
from .sealed_pack_import import MANIFEST_NAME

CONFIG_SCHEMA = "carbon.challenge-validator.copy-issuance-config.v1"
_FIELDS = {
    "schema",
    "producer_key",
    "master_key",
    "challenge_id",
    "challenge_version",
    "pack",
    "batch",
    "copies",
    "window",
    "hotkeys",
}
_HOTKEY = re.compile(r"[1-9A-HJ-NP-Za-km-z]{40,60}")


def load_master_key(path):
    """K_master from an owner-only file of at least 32 raw bytes."""
    raw = _owner_only_file(path).read_bytes()
    if len(raw) < 32:
        raise AnswerKeyRefused("copy_master_key_invalid")
    return raw


def _pack_files(directory):
    directory = Path(directory)
    manifest = (directory / MANIFEST_NAME).read_bytes()
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise AnswerKeyRefused("answer_key_sealed_pack_files")
        relative = path.relative_to(directory).as_posix()
        if path.is_file() and relative != MANIFEST_NAME:
            files[relative] = path.read_bytes()
    return manifest, files


def _write_once(path, value):
    if path.exists():
        return False
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")
    return True


def issue(config, *, hotkeys=None):
    """Issue every permitted hotkey's copy; returns counts and digests only."""
    if (
        type(config) is not dict
        or set(config) != _FIELDS
        or config["schema"] != CONFIG_SCHEMA
    ):
        raise AnswerKeyRefused("copy_issuance_config_malformed")
    key = ProducerKey.load(config["producer_key"])
    master = load_master_key(config["master_key"])
    if hotkeys is None:
        hotkeys = read_private(config["hotkeys"])
    if (
        type(hotkeys) is not list
        or not hotkeys
        or len(set(hotkeys)) != len(hotkeys)
        or not all(type(h) is str and _HOTKEY.fullmatch(h) for h in hotkeys)
    ):
        raise AnswerKeyRefused("copy_issuance_hotkeys")
    challenge, version = config["challenge_id"], config["challenge_version"]
    manifest, files = _pack_files(config["pack"])
    carried = json.loads(_owner_only_file(config["batch"]).read_bytes())
    if type(carried) is not dict or set(carried) != {"schema", "document", "records"}:
        raise AnswerKeyRefused("copy_issuance_batch")
    copies = Path(config["copies"])
    copies.mkdir(mode=0o700, parents=True, exist_ok=True)
    canonical = copy_delivery._sha(manifest)
    written, held = [], []
    for hotkey in hotkeys:
        folder = copies / hotkey
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / (canonical.removeprefix("sha256:") + ".json")
        if path.exists():
            held.append(hotkey)
            continue
        package = copy_delivery.issue_copy(
            key,
            master,
            challenge=challenge,
            version=version,
            canonical_manifest=manifest,
            canonical_files=files,
            document=carried["document"],
            records=carried["records"],
            hotkey=hotkey,
            window=config["window"],
        )
        # Verified before it is written: a package the host would refuse is never left.
        copy_route.verify_package(package, key.public_key)
        _write_once(path, package)
        written.append(hotkey)
    return {
        "canonical_digest": canonical,
        "written": len(written),
        "held": len(held),
        "hotkeys": len(hotkeys),
        "challenge": challenge,
        "challenge_version": version,
    }


SET_CONFIG_SCHEMA = "carbon.challenge-validator.pack-set-publication-config.v1"
_SET_FIELDS = {
    "schema",
    "producer_key",
    "challenge_id",
    "challenge_version",
    "batches",
    "window",
    "inbox",
}


def publish_set(config):
    """Sign and publish a Challenge version's pack set (OWNER-FULL-EXAM-BANK-01).

    The set names its batches by **canonical manifest digest** (digests only, no exam
    content), so every validator receives the same bytes. It goes into the first
    route's inbox (`<inbox>/<challenge>/set-<key>.json`, create-only, 0600); the host
    serves it to permit holders like any signed package. Returns the set key and the
    batch count only."""
    from . import sealed_pack_import as spi
    from .answer_key import package

    if (
        type(config) is not dict
        or set(config) != _SET_FIELDS
        or config["schema"] != SET_CONFIG_SCHEMA
    ):
        raise AnswerKeyRefused("copy_issuance_config_malformed")
    key = ProducerKey.load(config["producer_key"])
    commitment = spi.set_commitment_for(
        config["challenge_id"],
        config["challenge_version"],
        config["batches"],
        config["window"],
    )
    signed = package(key, commitment, spi.set_payload_for(commitment))
    folder = Path(config["inbox"]) / config["challenge_id"]
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / ("set-" + commitment["set_key"].removeprefix("sha256:") + ".json")
    created = _write_once(path, signed)
    return {
        "set_key": commitment["set_key"],
        "batches": len(commitment["batches"]),
        "written": created,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.copy_issuance")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("issue").add_argument("--config", required=True)
    sub.add_parser("publish-set").add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        run = publish_set if args.command == "publish-set" else issue
        print(json.dumps(run(read_private(args.config)), sort_keys=True))
    except AnswerKeyRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
