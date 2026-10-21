"""Tested backbone -> catalog entry -> Launchpad and the miner path, as one pipeline.

OWNER-BACKBONE-CATALOG-01 (2026-10-20): "make sure the pipeline from tested
to on Launchpad and in the miner path is clean and easy". A catalog entry is a
backbone Carbon has already rebuilt and judged: its tested **baseline** bundle
(exact digest), the settings that bundle's own build accepts (defaulted to the
baseline's, never a tuning case's), the Challenges it is offered on, and the
Test Lead's pair-identity receipt. Launchpad and the miner path read
`manifest.json` only; nothing else is edited per backbone.

Adding a backbone:

    python -m carbon.backbone_catalog.pipeline add PACKET_DIR \\
        --challenge electric-motor-magnetics@1.2 \\
        --receipt PAIR_IDENTITY_REPORT.json --receipt-key fno

copies the packet's bundle files, imports its receipt and writes one manifest
line; `verify` re-checks every entry (each entry also runs in the tests):

    python -m carbon.backbone_catalog.pipeline verify [--wheelhouse DIR]

and installs each entry's child image over the PyTorch CPU parent (owner-run).
On a miner it reads the checked Launchpad setup; on a receiver host, which has
no miner setup, it reads the receiver's operator record and installs over the
parent and into the cache the receiver itself verifies at start:

    python -m carbon.backbone_catalog.pipeline install [IDS...] [--wheelhouse DIR]
        [--state-dir DIR | --receiver-config RECEIVER.json]

Checked per entry:
- the bundle's digest is its manifest's canonical digest, and the source,
  lock and licence bytes are the ones it names (with `--wheelhouse`, the full
  `library_bundles.validate_bundle`, wheels included);
- the source's build module is the one its settings schema mirrors;
- the defaults are the tested baseline's own (`train_use` empty, the packet a
  `_baseline`), never a tuning case's;
- the pair-identity receipt shows every paired rebuild identical.
Licence screening (OWNER: KNO and WNO left out) happens before `add`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
BUNDLES = HERE / "bundles"
RECEIPTS = HERE / "receipts"
SCHEMA = "carbon.backbone-catalog-manifest.v1"
RECEIPT_SCHEMA = "carbon.backbone-catalog-pair-identity.v1"
FILES = ("bundle.json", "source.tar.gz", "LICENSE", "requirements.txt", "baseline.json")
_CHALLENGE = re.compile(r"([a-z0-9][a-z0-9-]*)@([0-9]+\.[0-9]+)\Z")


class CatalogBroken(ValueError):
    """The catalog's own files disagree: Carbon's problem, never a miner's."""


def _digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _json(path):
    return json.loads(Path(path).read_bytes())


def load():
    """The manifest: {"schema", "entries": [...]}, ordered by catalog id."""
    if not MANIFEST.exists():
        return {"schema": SCHEMA, "entries": []}
    manifest = _json(MANIFEST)
    if type(manifest) is not dict or manifest.get("schema") != SCHEMA:
        raise CatalogBroken("catalog manifest schema differs")
    return manifest


def entries(challenge_id=None, version=None):
    """Every entry, or those offered on (challenge_id, version)."""
    return [
        e
        for e in load()["entries"]
        if challenge_id is None
        or {"id": challenge_id, "version": version} in e["challenges"]
    ]


def entry(catalog_id, challenge_id=None, version=None):
    for item in entries(challenge_id, version):
        if item["catalog_id"] == catalog_id:
            return item
    return None


def bundle_files(item):
    """The entry's pinned files, by name."""
    root = BUNDLES / item["catalog_id"]
    return {name: (root / name).read_bytes() for name in FILES}


def _source_member(source, suffix):
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as archive:
        members = [
            m for m in archive.getmembers() if m.isfile() and m.name.endswith(suffix)
        ]
        if len(members) != 1:
            raise CatalogBroken(f"bundle source holds {len(members)} {suffix}")
        return archive.extractfile(members[0]).read()


def verify(item, *, wheelhouse=None):
    """Raise `CatalogBroken` unless `item` is exactly what it claims."""
    from . import settings

    files = bundle_files(item)
    manifest = json.loads(files["bundle.json"])
    ref = item["bundle_ref"]
    if _digest(_canonical(manifest)) != ref["bundle_digest"]:
        raise CatalogBroken(f"{item['catalog_id']}: bundle digest differs")
    if (
        manifest["environment_digest"] != ref["environment_digest"]
        or manifest["runtime_profile_id"] != ref["runtime_profile_id"]
        or manifest["language"] != ref["language"]
        or _digest(files["source.tar.gz"]) != manifest["source_sha256"]
        or _digest(files["requirements.txt"]) != manifest["lock_sha256"]
        or _digest(files["LICENSE"]) != manifest["license_sha256"]
    ):
        raise CatalogBroken(
            f"{item['catalog_id']}: bundle bytes differ from its manifest"
        )
    # An empty lock is genuine only beside an empty wheel set, and the other
    # way round: a lock step that silently produced nothing is refused.
    if (files["requirements.txt"] == b"") != (manifest["wheels"] == {}):
        raise CatalogBroken(f"{item['catalog_id']}: lock and wheel set disagree")
    if wheelhouse is not None:
        from carbon.development_session.library_bundles import (
            load_cached_wheels,
            validate_bundle,
        )

        wheels = load_cached_wheels(wheelhouse, manifest)
        if (
            validate_bundle(
                manifest,
                files["source.tar.gz"],
                wheels,
                files["requirements.txt"],
                files["LICENSE"],
            )
            != ref["bundle_digest"]
        ):
            raise CatalogBroken(f"{item['catalog_id']}: full bundle validation differs")
    schema = settings.SCHEMAS.get(item["settings_schema"])
    if schema is None:
        raise CatalogBroken(f"{item['catalog_id']}: unknown settings schema")
    if (
        _digest(_source_member(files["source.tar.gz"], schema.build_member))
        != schema.build_sha256
    ):
        raise CatalogBroken(
            f"{item['catalog_id']}: build module differs from its settings schema"
        )
    baseline = json.loads(files["baseline.json"])
    if (
        not baseline["packet"].endswith("_baseline")
        or baseline["train_use"] != {}
        or baseline["bundle_ref"] != ref
        or baseline["entrypoint"] != item["entrypoint"]
        or item["defaults"]
        != {"configuration": baseline["configuration"], "train_use": {}}
        or baseline["configuration"].get("backbone") != item["backbone"]
    ):
        raise CatalogBroken(
            f"{item['catalog_id']}: defaults are not the tested baseline's"
        )
    receipt = _json(RECEIPTS / (item["catalog_id"] + ".json"))
    if (
        receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("catalog_id") != item["catalog_id"]
        or not receipt.get("pairs")
        or receipt.get("identical") != receipt["pairs"]
        or receipt.get("differ")
    ):
        raise CatalogBroken(f"{item['catalog_id']}: no clean pair-identity receipt")
    from carbon.challenge_kit.served_versions import UnregisteredVersion, serves_catalog

    for challenge in item["challenges"]:
        if set(challenge) != {"id", "version"}:
            raise CatalogBroken(f"{item['catalog_id']}: Challenge binding malformed")
        # Offered only on a version that serves the catalog: its construction
        # limits bind the catalog, so no other version can name an entry.
        try:
            served = serves_catalog(challenge["id"], challenge["version"])
        except UnregisteredVersion:
            served = False
        if not served:
            raise CatalogBroken(
                f"{item['catalog_id']}: {challenge['id']} {challenge['version']} "
                "serves no backbone catalog"
            )
    settings.resolve(item, {}, {})  # the defaults pass their own door


def verify_all(*, wheelhouse=None):
    seen = set()
    for item in load()["entries"]:
        if item["catalog_id"] in seen:
            raise CatalogBroken(f"{item['catalog_id']}: listed twice")
        seen.add(item["catalog_id"])
        verify(item, wheelhouse=wheelhouse)
    return sorted(seen)


def add(packet, *, challenges, receipt, receipt_key):
    """Copy a tested packet's bundle in, import its receipt, write its line."""
    from . import settings

    packet = Path(packet)
    if not packet.name.endswith("_baseline"):
        raise CatalogBroken(
            "only a tested baseline packet becomes an entry; tuning cases stay private"
        )
    recipe = _json(packet / "recipe.json")
    procedure = recipe["procedure"]
    if procedure["train_use"] != {}:
        raise CatalogBroken("a baseline packet trains with no levers")
    backbone = procedure["configuration"]["backbone"]
    report = _json(receipt)
    record = report[receipt_key]
    root = BUNDLES / backbone
    root.mkdir(parents=True, exist_ok=True)
    for name in FILES[:-1]:
        (root / name).write_bytes((packet / name).read_bytes())
    baseline = {
        "configuration": procedure["configuration"],
        "train_use": {},
        "entrypoint": procedure["entrypoint"],
        "output_format": recipe["output"]["format"],
        "bundle_ref": recipe["source"]["bundle_ref"],
        "packet": packet.name,
    }
    (root / "baseline.json").write_bytes(
        (json.dumps(baseline, sort_keys=True, indent=1) + "\n").encode()
    )
    RECEIPTS.mkdir(exist_ok=True)
    (RECEIPTS / (backbone + ".json")).write_bytes(
        (
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "catalog_id": backbone,
                    "source_report": Path(receipt).name,
                    "source_report_sha256": _digest(Path(receipt).read_bytes()),
                    "key": receipt_key,
                    **{
                        k: record[k]
                        for k in (
                            "pairs",
                            "identical",
                            "differ",
                            "unpaired",
                            "distinct_states",
                            "files",
                        )
                        if k in record
                    },
                },
                sort_keys=True,
                indent=1,
            )
            + "\n"
        ).encode()
    )
    bound = []
    for text in challenges:
        match = _CHALLENGE.fullmatch(text)
        if match is None:
            raise CatalogBroken("a Challenge is named id@version")
        bound.append({"id": match[1], "version": match[2]})
    item = {
        "catalog_id": backbone,
        "backbone": backbone,
        "bundle_ref": recipe["source"]["bundle_ref"],
        "entrypoint": procedure["entrypoint"],
        "output_format": recipe["output"]["format"],
        "settings_schema": settings.schema_for_build(
            _digest(
                _source_member(
                    (root / "source.tar.gz").read_bytes(), "carbon_candidate/build.py"
                )
            )
        ),
        "defaults": {"configuration": procedure["configuration"], "train_use": {}},
        "challenges": bound,
    }
    manifest = load()
    manifest["entries"] = sorted(
        [e for e in manifest["entries"] if e["catalog_id"] != backbone] + [item],
        key=lambda e: e["catalog_id"],
    )
    verify(item)
    MANIFEST.write_bytes(
        (json.dumps(manifest, sort_keys=True, indent=1) + "\n").encode()
    )
    return item


def bundle_directory(item, target, *, wheelhouse=None):
    """Write `item`'s pinned bundle as the directory the owner installer reads
    (bundle.json, source.tar.gz, requirements.txt, LICENSE, wheels/). Wheels
    come from `wheelhouse` by their pinned names and digests; the repository
    holds none."""
    target = Path(target)
    target.mkdir(mode=0o700)
    files = bundle_files(item)
    for name in FILES[:-1]:
        (target / name).write_bytes(files[name])
    wheels = target / "wheels"
    wheels.mkdir(mode=0o700)
    declared = json.loads(files["bundle.json"])["wheels"]
    if declared and wheelhouse is None:
        raise CatalogBroken(
            f"{item['catalog_id']}: its pinned wheels need --wheelhouse"
        )
    for name, expected in declared.items():
        body = (Path(wheelhouse) / name).read_bytes()
        if _digest(body) != expected:
            raise CatalogBroken(
                f"{item['catalog_id']}: wheel {name} differs from its pin"
            )
        (wheels / name).write_bytes(body)
    return target


def install(catalog_ids=None, *, wheelhouse=None, state_dir=None, receiver_config=None):
    """Install each entry's child image over its PyTorch CPU parent, so
    practice and the receiver can build it. Owner-run; never from MCP.

    A miner installs from its checked Launchpad setup (`state_dir`,
    `library_bundle.install_bundle`); a receiver host from its operator record
    (`receiver_config`, `library_bundle.install_receiver_bundle`)."""
    import tempfile

    from scripts.dev import library_bundle

    if state_dir is not None and receiver_config is not None:
        raise CatalogBroken("install for a miner setup or a receiver, not both")
    installed = []
    for item in load()["entries"]:
        if catalog_ids and item["catalog_id"] not in catalog_ids:
            continue
        verify(item)
        with tempfile.TemporaryDirectory() as work:
            directory = bundle_directory(
                item, Path(work) / "bundle", wheelhouse=wheelhouse
            )
            if receiver_config is not None:
                result = library_bundle.install_receiver_bundle(
                    directory, receiver_config
                )
            else:
                kwargs = {} if state_dir is None else {"state_dir": state_dir}
                result = library_bundle.install_bundle(directory, **kwargs)
            installed.append({"catalog_id": item["catalog_id"], **result})
    return installed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--wheelhouse", type=Path)
    grow = commands.add_parser("add")
    grow.add_argument("packet", type=Path)
    grow.add_argument("--challenge", action="append", required=True)
    grow.add_argument("--receipt", type=Path, required=True)
    grow.add_argument("--receipt-key", required=True)
    put = commands.add_parser("install")
    put.add_argument("catalog_id", nargs="*")
    put.add_argument("--wheelhouse", type=Path)
    host = put.add_mutually_exclusive_group()
    host.add_argument("--state-dir", type=Path)
    host.add_argument("--receiver-config", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            print(
                json.dumps(
                    {"verified": verify_all(wheelhouse=args.wheelhouse)}, indent=1
                )
            )
        elif args.command == "install":
            print(
                json.dumps(
                    install(
                        args.catalog_id,
                        wheelhouse=args.wheelhouse,
                        state_dir=args.state_dir,
                        receiver_config=args.receiver_config,
                    ),
                    indent=1,
                    default=str,
                )
            )
        else:
            print(
                json.dumps(
                    add(
                        args.packet,
                        challenges=args.challenge,
                        receipt=args.receipt,
                        receipt_key=args.receipt_key,
                    ),
                    indent=1,
                )
            )
    except CatalogBroken as broken:
        print("refused: " + str(broken), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
