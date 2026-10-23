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

Installing each entry's child image is the owner installer's
(`python -m scripts.dev.catalog_install`, on a miner or a receiver host): this
package imports nothing from `scripts/`, and miner paths read only
`listing` (Validator, 2026-10-20).

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
import functools
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

from .listing import (  # noqa: F401  (the owner commands' API)
    HERE,
    MANIFEST,
    CatalogBroken,
    _json,
    entries,
    entry,
    load,
)

BUNDLES = HERE / "bundles"
RECEIPTS = HERE / "receipts"
#: A receipt: the pair-identity run's clean pairs, and its run facts
#: (`RUN_FACTS`). tested_on is the packet's version; an entry is offered on
#: another version only when its TRAIN and interface digests are byte-equal
#: (Validator ruling 1, 2026-10-21).
RECEIPT_SCHEMA = "carbon.backbone-catalog-pair-identity.v1"
FILES = ("bundle.json", "source.tar.gz", "LICENSE", "requirements.txt", "baseline.json")
_CHALLENGE = re.compile(r"([a-z0-9][a-z0-9-]*)@([0-9]+\.[0-9]+)\Z")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: The run facts every receipt binds (Validator, 2026-10-21): the Challenge
#: (id@version, the packet's kit) its pairs were rebuilt on, that version's
#: TRAIN and interface digests (from the same kit), and the worker image
#: digest they ran on, all from the pair-identity run's records. The offered
#: Challenges are not copied here: `verify` checks the manifest's own offers
#: against them.
RUN_FACTS = (
    "tested_on",
    "tested_train_digest",
    "tested_interface_digest",
    "image_digest",
)
#: The kit fields each tested digest is compared with.
TESTED_DIGESTS = {
    "tested_train_digest": "train_digest",
    "tested_interface_digest": "interface_digest",
}


@functools.cache
def _served_kit_digests(challenge_id, version):
    """The served kit's TRAIN and interface digests for a version."""
    from carbon.challenge_kit import physical_material

    kit = physical_material.bundle_material(challenge_id, version)["construction_kit"]
    return {field: kit[field] for field in TESTED_DIGESTS.values()}


def _digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


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
    """Raise `CatalogBroken` unless `item` is exactly what it claims.

    tested_on is the packet's version; an entry is offered on another version
    only when its TRAIN and interface digests are byte-equal (Validator ruling
    1, 2026-10-21): every offered version's served kit must carry the
    receipt's tested digests, or the entry needs a re-run there."""
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
    tested = _CHALLENGE.fullmatch(str(receipt.get("tested_on", "")))
    if tested is None:
        raise CatalogBroken(
            f"{item['catalog_id']}: receipt binds no tested Challenge (id@version)"
        )
    if _IMAGE.fullmatch(str(receipt.get("image_digest", ""))) is None:
        raise CatalogBroken(f"{item['catalog_id']}: receipt binds no worker image")
    for name in TESTED_DIGESTS:
        if _IMAGE.fullmatch(str(receipt.get(name, ""))) is None:
            raise CatalogBroken(
                f"{item['catalog_id']}: receipt binds no {name.replace('_', ' ')}"
            )
    from carbon.challenge_kit.served_versions import UnregisteredVersion, serves_catalog

    for challenge in item["challenges"]:
        if set(challenge) != {"id", "version"}:
            raise CatalogBroken(f"{item['catalog_id']}: Challenge binding malformed")
        if challenge["id"] != tested[1]:
            raise CatalogBroken(
                f"{item['catalog_id']}: offered on {challenge['id']} but tested on "
                f"{tested[0]}"
            )
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
        served_digests = _served_kit_digests(challenge["id"], challenge["version"])
        for name, field in TESTED_DIGESTS.items():
            if served_digests[field] != receipt[name]:
                raise CatalogBroken(
                    f"{item['catalog_id']}: {challenge['id']} {challenge['version']} "
                    f"{field.replace('_', ' ')} differs from the tested "
                    f"{tested[0]}'s: re-run it there"
                )
    for runtime, ref in (item.get("bundle_refs") or {}).items():
        _verify_runtime_ref(item, runtime, ref, files, manifest)
    settings.resolve(item, {}, {})  # the defaults pass their own door


def _verify_runtime_ref(item, runtime, ref, cpu_files, cpu_manifest):
    """A GPU build is the CPU build plus the one registered change, and nothing else (U58).

    The GPU files under `bundles/<id>/<runtime>/` are re-derived from the CPU files with `gpu_build`; any
    difference, or a ref that is not the derived manifest's, is refused. `bundle_ref` stays the CPU build.
    """
    from . import gpu_build

    if item["catalog_id"] in gpu_build.NO_GPU_TWIN:
        raise CatalogBroken(f"{item['catalog_id']}: it has no GPU twin (CPU only)")
    if (
        runtime not in gpu_build.TWINS.values()
        or gpu_build.TWINS.get(cpu_manifest["runtime_profile_id"]) != runtime
    ):
        raise CatalogBroken(
            f"{item['catalog_id']}: no GPU build is registered for {runtime}"
        )
    root = BUNDLES / item["catalog_id"] / runtime
    names = ("bundle.json", "source.tar.gz", "LICENSE", "requirements.txt")
    try:
        files = {name: (root / name).read_bytes() for name in names}
    except OSError:
        raise CatalogBroken(
            f"{item['catalog_id']}: the {runtime} bundle files are missing"
        ) from None
    try:
        source = gpu_build.derived_source(
            cpu_manifest["runtime_profile_id"],
            cpu_files["source.tar.gz"],
            item["catalog_id"],
        )
        expected = gpu_build.gpu_manifest(
            cpu_manifest, source, gpu_build.base_lock(runtime)
        )
    except gpu_build.GpuBuildRefused as refused:
        raise CatalogBroken(f"{item['catalog_id']}: {refused}") from None
    if (
        files["source.tar.gz"] != source
        or files["LICENSE"] != cpu_files["LICENSE"]
        or files["requirements.txt"] != cpu_files["requirements.txt"]
        or json.loads(files["bundle.json"]) != expected
        or ref != gpu_build.bundle_ref(expected)
    ):
        raise CatalogBroken(
            f"{item['catalog_id']}: the {runtime} build is not its CPU build's derivation"
        )
    from . import gpu_receipt

    try:
        gpu_receipt.load(
            item["catalog_id"], runtime
        )  # a receipt, once there is one, must prove its kind
    except gpu_receipt.GpuReceiptBroken as broken:
        raise CatalogBroken(str(broken)) from None


def verify_all(*, wheelhouse=None):
    seen = set()
    for item in load()["entries"]:
        if item["catalog_id"] in seen:
            raise CatalogBroken(f"{item['catalog_id']}: listed twice")
        seen.add(item["catalog_id"])
        verify(item, wheelhouse=wheelhouse)
    return sorted(seen)


def add(packet, *, challenges, receipt, receipt_key, image_digest, catalog_id=None):
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
    # The catalog id names the entry; the build keeps its own backbone name
    # (jNO's "fno1d" is catalogued as "jno.fno1d").
    catalog_id = catalog_id or backbone
    kit = recipe["challenge"]
    tested_on = f"{kit['id']}@{kit['version']}"
    if _IMAGE.fullmatch(str(image_digest)) is None:
        raise CatalogBroken("the worker image the pairs ran on is required (sha256)")
    for text in challenges:
        match = _CHALLENGE.fullmatch(text)
        if match is not None and match[1] != kit["id"]:
            raise CatalogBroken(
                f"{catalog_id}: offered on {match[1]} but its packet was tested on "
                f"{tested_on}"
            )
    report = _json(receipt)
    record = report[receipt_key]
    root = BUNDLES / catalog_id
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
    (RECEIPTS / (catalog_id + ".json")).write_bytes(
        (
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "catalog_id": catalog_id,
                    "source_report": Path(receipt).name,
                    "source_report_sha256": _digest(Path(receipt).read_bytes()),
                    "key": receipt_key,
                    "tested_on": tested_on,
                    **{name: kit[field] for name, field in TESTED_DIGESTS.items()},
                    "image_digest": image_digest,
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
        "catalog_id": catalog_id,
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
        [e for e in manifest["entries"] if e["catalog_id"] != catalog_id] + [item],
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


def twin_directory(item, runtime, target, *, wheelhouse=None):
    """Write `item`'s pinned GPU twin for bundle runtime `runtime` as the
    directory the owner installer reads, as `bundle_directory` writes the CPU
    build: the twin's own files under `bundles/<id>/<runtime>/` (the CPU
    build's derivation, `_verify_runtime_ref`), and its pinned wheels from
    `wheelhouse`. Refused when the entry has no build for `runtime`."""
    builds = item.get("bundle_refs") or {}
    if runtime not in builds:
        raise CatalogBroken(f"{item['catalog_id']}: no {runtime} build")
    root = BUNDLES / item["catalog_id"] / runtime
    target = Path(target)
    target.mkdir(mode=0o700)
    for name in ("bundle.json", "source.tar.gz", "requirements.txt", "LICENSE"):
        (target / name).write_bytes((root / name).read_bytes())
    wheels = target / "wheels"
    wheels.mkdir(mode=0o700)
    declared = json.loads((root / "bundle.json").read_bytes())["wheels"]
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


def bind(
    catalog_id,
    *,
    tested_on,
    image_digest,
    tested_train_digest=None,
    tested_interface_digest=None,
):
    """Backfill an existing receipt's run facts from the pair-identity run's
    records (Validator, 2026-10-21): the packet kit's Challenge and its TRAIN
    and interface digests, and the worker image. Refuses a malformed value or
    one that differs from a fact the receipt already binds."""
    if _CHALLENGE.fullmatch(str(tested_on)) is None:
        raise CatalogBroken("tested_on is a Challenge id@version")
    if _IMAGE.fullmatch(str(image_digest)) is None:
        raise CatalogBroken("image_digest is a sha256 digest")
    facts = {"tested_on": tested_on, "image_digest": image_digest}
    for name, value in (
        ("tested_train_digest", tested_train_digest),
        ("tested_interface_digest", tested_interface_digest),
    ):
        if value is None:
            continue
        if _IMAGE.fullmatch(str(value)) is None:
            raise CatalogBroken(f"{name} is a sha256 digest")
        facts[name] = value
    path = RECEIPTS / (catalog_id + ".json")
    receipt = _json(path)
    for name, value in facts.items():
        if receipt.get(name) not in (None, value):
            raise CatalogBroken(f"{catalog_id}: receipt already binds another {name}")
    receipt.update(facts)
    path.write_bytes((json.dumps(receipt, sort_keys=True, indent=1) + "\n").encode())
    return receipt


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
    grow.add_argument("--catalog-id")
    grow.add_argument("--image-digest", required=True)
    tie = commands.add_parser("bind")
    tie.add_argument("catalog_id")
    tie.add_argument("--tested-on", required=True)
    tie.add_argument("--image-digest", required=True)
    tie.add_argument("--tested-train-digest")
    tie.add_argument("--tested-interface-digest")
    moved = commands.add_parser("install")
    moved.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "install":
        # The installer moved out of this package (Validator, 2026-10-20).
        print(
            "refused: install moved; run python -m scripts.dev.catalog_install "
            + " ".join(args.rest),
            file=sys.stderr,
        )
        return 2
    try:
        if args.command == "verify":
            print(
                json.dumps(
                    {"verified": verify_all(wheelhouse=args.wheelhouse)}, indent=1
                )
            )
        elif args.command == "bind":
            print(
                json.dumps(
                    bind(
                        args.catalog_id,
                        tested_on=args.tested_on,
                        image_digest=args.image_digest,
                        tested_train_digest=args.tested_train_digest,
                        tested_interface_digest=args.tested_interface_digest,
                    ),
                    indent=1,
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
                        image_digest=args.image_digest,
                        catalog_id=args.catalog_id,
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
