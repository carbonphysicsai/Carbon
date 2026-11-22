"""Finite operator bootstrap for the existing signed DEVELOPMENT recipe intake.

The installed profile supplies trusted source, image and chain identities. An
authenticated hotkey selects only its own durable task workspace. This module
never holds a signer, builds an image or imports participant construction code.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import functools
import hashlib
import json
import os
import re
import signal
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.intake_targets import ADDRESS, intake_url
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import canonical, digest

SCHEMA = "carbon.construction.direct-receiver-operator.v1"
_FIELDS = {
    "schema",
    "root",
    "runner_profile",
    "receiver_hotkey",
    "host",
    "port",
    "lifetime_seconds",
    "measure_query",
}
_OPTIONAL_FIELDS = {
    # The chain network this door is bound to (N3, lock-in rev 4): written by `receiver_setup prepare` from the network
    # the prepare ran on, set into the unit's environment by `service`/`start`, and checked against the process's own
    # binding at start (`require_chain_network`). Mainnet and testnet doors share one host, so the network is per door.
    "chain_network",
    "material_cache_bytes",
    "construction_image_manifest",
    "inference_image_manifest",
    "evaluation_pack",
    "evaluation_pack_set",
    "challenge",
    "construction_runtimes",
    "auto_grade",
    # The operator-signed launch board file the door serves at GET /carbon/v1/feed/<challenge> and, optionally, the
    # public feed key (64 hex) it must be signed by. The receiver verifies; it never holds the private key.
    "launch_board",
    "launch_board_key",
    # The graph route's GPU lane (OWNER-GPU-REBUILD-RENTED-4090-01): a JAX GPU worker and the record of ops its hardware
    # class repeats bit for bit. Both or neither.
    "graph_gpu_image_manifest",
    "graph_gpu_ops",
    # The GPU workers a receiver rebuilds catalog entries on (their official-grade GPU
    # twins), beside its CPU construction pair, which stays the lane for every other entry.
    "gpu_construction_images",
    # A private file (>= 32 bytes) holding the pack's custody copy key: the speed-sample seed of the pool
    # versions' single-design call timing is derived under it (`single_call_timing.sample_seed`).
    "speed_sample_key_file",
    # the crown multi-rebuild average ruling (lead-records a322dea4): {"key_file": <absolute private file>} holds K_crown and turns the crown's
    # N-rebuild average on (`crown_average.install`). Absent: the crown rule is as before.
    "crown_average",
    "menu_draw",
    # The on-box store of OFFICIAL GPU receipts (`backbone_catalog.receipt_store`, OWNER-GPU-OPEN-WITH-READY-01):
    # an exact absolute operator path in the validator state, written only by the standing receipt worker. Without
    # it no catalog entry is officially gradable (the official route never falls back to a CPU rebuild).
    "official_gpu_receipts",
    # A DECLARED EXAM CHANGE (Validator 5 Nov 06:49, ruled M2 amendment): {from_revision, to_revision, paths, reason,
    # evidence_sha256}. A carried owner's manifest migrates across a grading-path change ONLY when OLD..NEW is exactly
    # this record's revisions and the computed changed grading paths EQUAL its ``paths`` (`_declared_change`).
    "declared_exam_change",
    # The EARLIER declared exam changes still needed (live 116, 18 Nov 2026: owners left lazy across a start stayed
    # frozen one revision back): a list of records shaped like ``declared_exam_change``. A carried manifest migrates
    # OLD..NEW also when the hops OLD -> ... -> NEW are each one of these records or the current one, each hop's paths
    # EQUAL to that hop's own computed changed grading paths (`_declared_change`).
    "earlier_declared_changes",
    # Absolute paths to carbon.c03.worker-image.v1 manifests of images a SITTING king was built on before this
    # receiver's parent moved (Validator 5 Nov, route (a)): his regrade may infer on his own retained parent when the
    # image store holds it with exactly that id (`lean_recipe_retention._regrade_inference_image`). Kings only.
    "king_retained_parents",
    # Absolute path to ONE carbon.c03.worker-image.v1 manifest: the image every counted/regrade GRAPH inference runs on
    # (Lead + Validator 17 Nov: builds may stay on a migrated image, the graded inference runs on the image the sealed
    # pack's leg minimums are pinned to). The local image store must answer to that id directly at grade time
    # (`lean_recipe_retention._regrade_inference_image`); a bundle regrade refuses while it is set. Absent: as before.
    "graded_inference_image",
    # R89 (Validator-2 6 Nov 09:16 option b): {guard, group, chunks: {rate_per_s, burst}}, every value the OWNER's
    # (decision #10). Absent: the shared peer bucket as before. Present with any value unset: the receiver refuses.
    "request_buckets",
    # The Chain Auditor's operator-only coldkey -> allowance-group map (`funder_map`). Absent: each coldkey is its
    # own group. An unreadable or malformed map is no map (each coldkey its own group), never a refusal.
    "funder_map_file",
    # OWNER-PROBING-COUNTERS-01 (a): {unmapped_coldkey, unresolved_hotkey, max_map_age_blocks}, every value the OWNER's
    # (`allowance_groups.policy`). Absent: the exam cap is per hotkey as before. Present with any value unset: refused.
    "allowance_groups",
    # Owner decision #9 (8 Nov): absolute paths of `version_close.close_queued` files of this Challenge's EARLIER
    # versions; the owner asking about one of its closed submissions is answered ``version_closed``. Absent: as before.
    "version_closed_files",
}
#: The one opt-in per-runtime construction set (OWNER-BACKBONE-CATALOG-01):
#: a PyTorch CPU worker and the C-03 CPU worker it was built FROM.
CONSTRUCTION_RUNTIMES = ["python-cpu-py311", "torch-cpu-py311"]


def served_challenges() -> tuple:
    """Every Challenge version this receiver can serve, as ``{"id", "version"}``:
    the synthetic fixture, every served Battery construction version, and every
    registered physical kit. One list, read from the registrations (no
    Challenge is named here), for the configuration check and operator setup."""
    from carbon.battery import challenge as battery_challenge
    from carbon.battery.construction_bundle_material import (
        VERSIONS as BATTERY_VERSIONS,
    )
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.synthetic_linear_field_2d import CHALLENGE

    listed = (
        {"id": CHALLENGE.challenge_id, "version": "1.3"},
        # Every served Battery construction version (1.0; step-2 2.0; 2.1,
        # allowlist v7), each with its approved pack (Validator, 2026-10-20),
        # and the catalog version 2.2 (2.1 plus the catalog; Validator,
        # 2026-10-22). Battery serves its own versioned material, not a
        # physical kit, so it is listed here rather than in REGISTERED.
        *(
            {"id": battery_challenge.CHALLENGE.challenge_id, "version": version}
            for version in BATTERY_VERSIONS
        ),
        *(
            {"id": challenge_id, "version": version}
            for challenge_id, version in physical_material.REGISTERED
        ),
    )
    # Battery's catalog versions (2.2) are also registered physical kits; each
    # (id, version) is listed once, in first-seen order.
    seen = set()
    unique = []
    for item in listed:
        key = (item["id"], item["version"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return tuple(unique)


class ReceiverUnavailable(RuntimeError):
    """A named operator/infrastructure refusal; never a scientific result."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def read_speed_sample_key(name) -> bytes:
    """The speed-sample key of a configured private file: an exact absolute regular file, owner-private, 32 to
    4096 bytes. It is held by the receiver only and never leaves it."""
    selected = Path(name) if type(name) is str else None
    if (
        selected is None
        or not selected.is_absolute()
        or selected.is_symlink()
        or not selected.is_file()
        or selected.resolve() != selected
        or (selected.stat().st_mode & 0o077)
        or not 32 <= selected.stat().st_size <= 4096
    ):
        raise ValueError("exact private speed sample key file required")
    return selected.read_bytes()


def install_official_receipt_store(cfg) -> None:
    """Point the official route at the configured on-box receipt store, or at none.

    The Challenge's registered rebuild noise is the only tolerance a within-noise receipt may carry
    (`koth_registry.rebuild_noise`, the registry itself, never a typed value). A receiver with no
    ``official_gpu_receipts`` has no official GPU receipt, so every catalog entry is refused for official
    grading with `catalog_gpu_receipt_pending`."""
    from carbon.backbone_catalog import gpu_receipt, receipt_store
    from carbon.challenge_validator import koth_registry

    path = cfg.get("official_gpu_receipts")
    gpu_receipt.OFFICIAL_STORE = (
        None
        if path is None
        else receipt_store.ReceiptStore(
            Path(path),
            registered_noise=lambda challenge: (
                koth_registry.rebuild_noise(challenge) or {}
            ).get("value"),
        )
    )


#: The networks a door can be bound to (`carbon.chain.models`; localnet is staging only).
CHAIN_NETWORKS = ("testnet", "finney", "localnet")


def _chain_network_shape(value) -> bool:
    """``{"network": "testnet"|"finney"}``, or the staging localnet with its genesis and its host-local endpoint."""
    if type(value) is not dict or value.get("network") not in CHAIN_NETWORKS:
        return False
    if value["network"] != "localnet":
        return set(value) == {"network"}
    return (
        set(value) == {"network", "genesis", "endpoint"}
        and type(value["genesis"]) is str
        and re.fullmatch(r"0x[0-9a-f]{64}", value["genesis"]) is not None
        and type(value["endpoint"]) is str
        and re.fullmatch(
            r"wss?://(127\.0\.0\.1|localhost|\[::1\]):[0-9]{1,5}", value["endpoint"]
        )
        is not None
    )


def _normal_endpoint(endpoint: str) -> str:
    """The localnet endpoint as ``scheme://host:port``, lower case: `carbon.chain.models` already accepted it (one
    loopback host, a port, nothing else), so this only drops what urlsplit ignores (case, an empty ``/``, ``?``, ``#``)
    and the record names one spelling, which its own reader (`_chain_network_shape`) accepts.
    """
    from urllib.parse import urlsplit

    parts = urlsplit(endpoint)
    host = parts.hostname or ""
    host = f"[{host}]" if ":" in host else host
    return f"{parts.scheme.lower()}://{host}:{parts.port}"


def chain_network_record() -> dict:
    """The network THIS process is bound to (`carbon.chain.models`), as a door's ``chain_network`` record."""
    from carbon.chain import models

    record = {"network": models.CARBON_NETWORK}
    if models.CARBON_NETWORK == models.LOCALNET:
        record.update(
            genesis=models.LOCALNET_GENESIS,
            endpoint=_normal_endpoint(models.LOCALNET_ENDPOINT),
        )
    return record


def require_chain_network(cfg: dict) -> None:
    """(N3) A door runs only on the network its own record names: a process bound elsewhere (an operator shell's
    environment, a unit written by hand, a mainnet door started like a testnet one) refuses before any chain read.
    A record is required whenever the process is bound off testnet; a root prepared before the record existed (no
    ``chain_network``) still starts on testnet, the only network such a root was ever prepared on.
    """
    observed = chain_network_record()
    expected = cfg.get("chain_network")
    if expected is None:
        if observed["network"] != "testnet":
            raise ReceiverUnavailable("chain_network_missing")
        return
    if expected != observed:
        raise ReceiverUnavailable("chain_network_mismatch")


def load_config(path: Path) -> dict:
    """Read the closed bounded private record; miner calls select no paths."""
    value = private_json(path)
    if (
        type(value) is not dict
        or not _FIELDS <= set(value) <= _FIELDS | _OPTIONAL_FIELDS
        or value.get("schema") != SCHEMA
        or value.get("host") not in ("127.0.0.1", "localhost")
        or type(value.get("port")) is not int
        or not 1 <= value["port"] <= 65535
        # None: a service, running until it is stopped (E5); an int: a finite run.
        or (
            value.get("lifetime_seconds") is not None
            and (
                type(value.get("lifetime_seconds")) is not int
                or not 0 < value["lifetime_seconds"] < 2**31
            )
        )
        or type(value.get("measure_query")) is not bool
        or type(value.get("receiver_hotkey")) is not str
        or not ADDRESS.fullmatch(value["receiver_hotkey"])
        or (
            "material_cache_bytes" in value
            and (
                type(value["material_cache_bytes"]) is not int
                or value["material_cache_bytes"] < 1
            )
        )
    ):
        raise ValueError("invalid DEVELOPMENT receiver configuration")
    for name in ("root", "runner_profile"):
        if type(value[name]) is not str:
            raise ValueError("operator path required")
        selected = Path(value[name])
        if not selected.is_absolute() or selected.resolve() != selected:
            raise ValueError("exact private operator path required")
    if "official_gpu_receipts" in value:
        store = value["official_gpu_receipts"]
        if (
            type(store) is not str
            or not Path(store).is_absolute()
            or Path(store).is_symlink()
            or Path(store).resolve() != Path(store)
        ):
            raise ValueError("exact official gpu receipts path required")
    if "gpu_construction_images" in value:
        images = value["gpu_construction_images"]
        if (
            type(images) is not list
            or not 1 <= len(images) <= 2
            or "construction_runtimes" not in value
            or any(type(item) is not str for item in images)
        ):
            raise ValueError(
                "gpu construction images need the construction runtimes and one or two manifests"
            )
        for item in images:
            selected = Path(item)
            if (
                not selected.is_absolute()
                or selected.is_symlink()
                or not selected.is_file()
                or selected.resolve() != selected
            ):
                raise ValueError("exact gpu construction image manifest required")
    if ("graph_gpu_image_manifest" in value) != ("graph_gpu_ops" in value):
        raise ValueError("the graph GPU lane needs both its worker and its ops record")
    for field in (
        "construction_image_manifest",
        "inference_image_manifest",
        "graph_gpu_image_manifest",
        "graph_gpu_ops",
    ):
        if field not in value:
            continue
        selected = value[field]
        refusal = f"exact {field.replace('_', ' ')} required"
        if type(selected) is not str:
            raise ValueError(refusal)
        selected = Path(selected)
        if (
            not selected.is_absolute()
            or selected.is_symlink()
            or not selected.is_file()
            or selected.resolve() != selected
        ):
            raise ValueError(refusal)
    if "speed_sample_key_file" in value:
        read_speed_sample_key(value["speed_sample_key_file"])
    if "declared_exam_change" in value:
        _check_declared_change(value["declared_exam_change"])
    if "earlier_declared_changes" in value:
        _check_earlier_changes(value["earlier_declared_changes"])
    if "king_retained_parents" in value:
        _king_retained_parents(value["king_retained_parents"])
    if "graded_inference_image" in value:
        _graded_inference_image(value["graded_inference_image"])
    if "request_buckets" in value:
        from carbon.challenge_validator import request_buckets

        request_buckets.values(value["request_buckets"])
    if "allowance_groups" in value:
        from carbon.challenge_validator import allowance_groups

        allowance_groups.policy(value["allowance_groups"])
    if "funder_map_file" in value:
        selected = value["funder_map_file"]
        if type(selected) is not str or not Path(selected).is_absolute():
            raise ValueError("exact funder map path required")
    # ``crown_average``: no longer read or checked (over-broad rules audit S7 C2 301; `crown_average_host.install`)
    if "menu_draw" in value:
        section = value["menu_draw"]
        if type(section) is not dict or set(section) != {"key_file"}:
            raise ValueError("invalid menu_draw selection")
        from carbon.challenge_validator import crown_average_host

        crown_average_host.read_crown_key(section["key_file"])
    if "challenge" in value:
        selected = value["challenge"]
        if type(selected) is not dict or selected not in served_challenges():
            raise ValueError("registered direct Challenge selection required")
    if "version_closed_files" in value:
        _version_closed(value)
    if "auto_grade" in value and (
        type(value["auto_grade"]) is not dict
        or set(value["auto_grade"]) - {"pool_store"}
        or (
            "pool_store" in value["auto_grade"]
            and (
                type(value["auto_grade"]["pool_store"]) is not str
                or not Path(value["auto_grade"]["pool_store"]).is_absolute()
            )
        )
    ):
        raise ValueError("invalid auto_grade selection")
    if "launch_board" in value and (
        type(value["launch_board"]) is not str
        or not Path(value["launch_board"]).is_absolute()
    ):
        raise ValueError("invalid launch_board file")
    if "chain_network" in value and not _chain_network_shape(value["chain_network"]):
        raise ValueError("invalid chain_network")
    if "launch_board_key" in value and (
        "launch_board" not in value
        or type(value["launch_board_key"]) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", value["launch_board_key"])
    ):
        raise ValueError("invalid launch_board_key")
    if "auto_grade" in value and "evaluation_pack_set" in value:
        # Set auto-grade (one grade over every batch) is not built: a multi-batch
        # receiver must be graded by --grade-set-entry until it is.
        raise ReceiverUnavailable("auto_grade_pack_set_unsupported")
    if (
        "construction_runtimes" in value
        and value["construction_runtimes"] != CONSTRUCTION_RUNTIMES
    ):
        raise ValueError("exact construction runtimes required")
    if "evaluation_pack" in value:
        selected = value["evaluation_pack"]
        base = {"root", "manifest", "public_root", "private_root"}
        if type(selected) is not dict or set(selected) not in (
            base,
            base | {"sealed_delivery"},
        ):
            raise ValueError("exact evaluation pack selection required")
        delivery = selected.get("sealed_delivery")
        if delivery is not None and (
            type(delivery) is not dict
            or set(delivery) != {"store", "manifest_digest"}
            or type(delivery["store"]) is not str
            or not Path(delivery["store"]).is_absolute()
            or type(delivery["manifest_digest"]) is not str
        ):
            raise ValueError("exact sealed delivery selection required")
        for name in ("root", "public_root", "private_root"):
            path = selected[name]
            if (
                type(path) is not str
                or not Path(path).is_absolute()
                or Path(path).resolve() != Path(path)
            ):
                raise ValueError("exact evaluation pack root required")
        manifest = selected["manifest"]
        if (
            type(manifest) is not str
            or not manifest
            or "\\" in manifest
            or ":" in manifest
            or any(part in {"", ".", ".."} for part in manifest.split("/"))
        ):
            raise ValueError("relative evaluation pack manifest required")
    if "evaluation_pack_set" in value:
        block = value["evaluation_pack_set"]
        digests = block.get("batches") if type(block) is dict else None
        if (
            "evaluation_pack" not in value
            or type(block) is not dict
            or set(block) != {"store", "set_key", "batches"}
            or type(block["store"]) is not str
            or not Path(block["store"]).is_absolute()
            or type(block["set_key"]) is not str
            or type(digests) is not list
            or not digests
            or digests != sorted(set(digests))
            or any(type(d) is not str for d in digests)
            or value["evaluation_pack"]
            .get("sealed_delivery", {})
            .get("manifest_digest")
            != digests[0]
        ):
            raise ValueError("exact evaluation pack set selection required")
    return value


def _private_directory(path: Path) -> Path:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError("exact private operator directory required")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise ValueError("owner-only operator directory required")
    return path


def _pack_file_identity(base, relative_path):
    """``(device, inode, size, mtime_ns, ctime_ns)`` of one pack file, opened exactly as the pack check opens it
    (descriptor-relative, no symbolic link anywhere on the path) and never read; None when it cannot be opened that way
    or is not a regular file."""
    import stat as stat_module

    from carbon.registry import digest as artifact_digest

    try:
        descriptor = artifact_digest._secure_open(
            Path(base), artifact_digest._artifact_parts(relative_path)
        )
    except Exception:  # noqa: BLE001 - unopenable: the full check decides
        return None
    try:
        found = os.fstat(descriptor)
    except OSError:
        return None
    finally:
        os.close(descriptor)
    if not stat_module.S_ISREG(found.st_mode):
        return None
    return (
        found.st_dev,
        found.st_ino,
        found.st_size,
        found.st_mtime_ns,
        found.st_ctime_ns,
    )


def _pack_files(root, relative_path, snapshot, public_root, private_root):
    """Every file the pack check reads: the manifest, then each role's artifact (inline bytes, a hidden batch store and an
    unavailable role read no file here)."""
    from collections.abc import Mapping

    from carbon.challenge_validator.evaluation_pack import UNAVAILABLE

    files = [(root, relative_path)]
    for roles, base in (
        (snapshot.public, public_root),
        (snapshot.private, private_root),
    ):
        for entry in roles.values():
            if (
                entry != UNAVAILABLE
                # a parsed pack's role entry is a read-only mapping (`parse_pack`: MappingProxyType), never a dict
                and isinstance(entry, Mapping)
                and "inline_bytes" not in entry
                and entry.get("kind") != "hidden_batch_store"
                and "path" in entry
            ):
                files.append((base, entry["path"]))
    return tuple(files)


def _pack_check(root, relative_path, digest, public_root, private_root, challenge):
    """Bind an opted-in pack to registered construction bytes at every use.

    CACHED BY FILE IDENTITY (TEAM_RULES #13; live 116, 19 Nov 2026: every research request ran this twice, so every
    source-upload chunk re-hashed the whole pack and re-read TRAIN). Every use still opens each file the check reads,
    exactly as the check opens it, and reads its identity (device, inode, size, mtime, ctime: a write moves ctime).
    The full check (load the manifest, digest every artifact, compare the construction roles and TRAIN) runs again
    whenever any identity differs, a file cannot be opened that way, the material's TRAIN is another object, or its
    three construction documents differ. A result is trusted only after a full check that ran BETWEEN two equal
    identity readings (so a write during the check is never trusted), and a failed check is never cached.
    """
    from carbon.challenge_validator.evaluation_pack import (
        EvaluationPackUnavailable,
        load_pack,
    )

    #: ``files`` (the files the last full check read) and ``trusted`` ((identities, TRAIN object, documents) or None)
    memo = {"files": None, "trusted": None}
    memo_lock = threading.Lock()  # guards the two references only (no I/O under it)

    def identities(files):
        if files is None:
            return None
        found = tuple(_pack_file_identity(base, path) for base, path in files)
        return None if any(item is None for item in found) else found

    def checked(material):
        documents = canonical(
            [
                material["construction_kit"],
                material["interface_document"],
                material["physics_contract"],
            ]
        )
        train = material["train"]
        before = identities(memo["files"])
        trusted = memo["trusted"]
        if (
            before is not None
            and trusted is not None
            and trusted[0] == before
            # the same TRAIN, or equal bytes (as safe: the full check compares content; V2 20:30Z)
            and (trusted[1] is train or trusted[1] == train)
            and trusted[2] == documents
        ):
            return
        try:
            files = full(material)
        except BaseException:
            with memo_lock:
                memo["trusted"] = None  # a failed check is never trusted
            raise
        after = identities(files)
        with memo_lock:
            memo["files"] = files
            stable = after is not None and after == before
            memo["trusted"] = (after, train, documents) if stable else None

    def full(material):
        snapshot = load_pack(
            root,
            relative_path,
            expected_digest=digest,
            challenge_id=challenge.challenge_id,
            challenge_version=challenge.version,
        )
        snapshot.verify_available(public_root, private_root)
        expected = {
            "construction_kit": material["construction_kit"],
            "interface": material["interface_document"],
            "physics_contract": material["physics_contract"],
        }
        # The read bounds follow the REGISTERED material (CAPS.md 3 item 8: a fixed 64 KiB / 16 MiB refused every
        # research and source request of a door whose pack outgrew them, with no harm named). This is an equality
        # check, so a role can only pass at the registered size: TRAIN exactly; a JSON role at least 64 KiB as before, or
        # 8x its canonical size (room for the pack's own formatting), whichever is larger.
        for role, document in expected.items():
            observed = snapshot.read_json_role(
                public_root,
                "public",
                role,
                max_bytes=max(65536, 8 * len(canonical(document))),
            )
            if canonical(observed) != canonical(document):
                raise EvaluationPackUnavailable("evaluation_pack.construction_mismatch")
        if (
            snapshot.read_role(
                public_root, "public", "train", max_bytes=max(1, len(material["train"]))
            )
            != material["train"]
        ):
            raise EvaluationPackUnavailable("evaluation_pack.train_mismatch")
        return _pack_files(root, relative_path, snapshot, public_root, private_root)

    return checked


def _delivered_sealed(selection, challenge) -> bool:
    """Whether the selected pack arrived through the answer-key route
    (`SealedPackStore.delivered`): the selection names its store and digest,
    the pack root is exactly that store's directory for the digest, and the
    store's own delivery record and verification hold now. An operator-typed
    `--pack` directory never qualifies."""
    delivery = selection.get("sealed_delivery")
    if delivery is None:
        return False
    from carbon.challenge_validator.answer_key import AnswerKeyRefused
    from carbon.challenge_validator.sealed_pack_import import SealedPackStore

    store = SealedPackStore(delivery["store"])
    try:
        directory = store.pack_directory(
            delivery["manifest_digest"], challenge.challenge_id, challenge.version
        )
    except AnswerKeyRefused:
        return False
    return {
        selection["root"],
        selection["public_root"],
        selection["private_root"],
    } == {str(directory)} and store.delivered(
        delivery["manifest_digest"], challenge.challenge_id, challenge.version
    )


def _sealed_pack(root, selection, challenge, *, bound=True):
    """Prepare once; a restart reloads its retained bytes, never the draft.
    ``bound`` False prepares a pack that is not the receiver's bound (primary)
    pack and never takes the retained binding's digest (a pack-set batch)."""
    from carbon.challenge_validator.evaluation_pack import load_pack, prepare_pack

    public_root = Path(selection["public_root"])
    private_root = Path(selection["private_root"])
    pack_root = _private_directory(root / "evaluation-packs")
    # The door's retained pack (door binding, or an older state's receiver-binding.json): `state_binding`.
    from carbon.challenge_validator.state_binding import retained_pack_digest

    digest = retained_pack_digest(root) if bound else None
    if bound:
        # A fixed door state (MAINNET_UPDATE_ARCHITECTURE s1) outlives every release root: a later release whose
        # configuration selects another pack would otherwise reload the retained one silently. The bound selection
        # is pinned once, beside the binding; another selection refuses (a new pack is a new door).
        pinned = canonical({key: selection[key] for key in sorted(selection)})
        try:
            write_once(root / "evaluation-pack-selection.json", pinned)
        except ValueError:
            raise ReceiverUnavailable("evaluation_pack_selection_differs") from None
    if digest is None:
        prepared = prepare_pack(
            Path(selection["root"]),
            selection["manifest"],
            public_root=public_root,
            private_root=private_root,
            challenge_id=challenge.challenge_id,
            challenge_version=challenge.version,
        )
        digest = prepared.snapshot.manifest_digest
        write_once(pack_root / (digest[7:] + ".json"), prepared.sealed_bytes)
    relative_path = digest[7:] + ".json"
    snapshot = load_pack(
        pack_root,
        relative_path,
        expected_digest=digest,
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
    )
    return (
        digest,
        _pack_check(
            pack_root, relative_path, digest, public_root, private_root, challenge
        ),
        snapshot,
    )


def _set_batch_adapters(cfg, root, challenge, material, discovery, providers, ledger):
    """One trusted served adapter per batch of the configured pack set, each
    bound to that batch's own pack (OWNER-FULL-EXAM-BANK-01). The receiver's
    primary pack keeps its existing discovery; every other batch is prepared like
    a pack of its own and re-checked as delivered. Keyed by the delivered
    manifest digest (the set's batch id)."""
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.challenge_validator.sealed_pack_import import SealedPackStore
    from carbon.development_session.research_service import DirectFixtureDiscovery

    block = cfg["evaluation_pack_set"]
    store = SealedPackStore(block["store"])
    primary = block["batches"][0]
    adapters = {}
    for batch_digest in block["batches"]:
        if batch_digest == primary:
            batch_discovery = discovery
        else:
            directory = store.pack_directory(
                batch_digest, challenge.challenge_id, challenge.version
            )
            selection = {
                "root": str(directory),
                "manifest": "evaluation-pack.json",
                "public_root": str(directory),
                "private_root": str(directory),
                "sealed_delivery": {
                    "store": block["store"],
                    "manifest_digest": batch_digest,
                },
            }
            pack_digest, pack_check, snapshot = _sealed_pack(
                root, selection, challenge, bound=False
            )
            batch_discovery = DirectFixtureDiscovery(
                material,
                task_admission=True,
                pack_check=pack_check,
                evaluation_pack_digest=pack_digest,
                evaluation_pack_snapshot=snapshot,
                evaluation_pack_sealed=_delivered_sealed(selection, challenge),
                evaluation_pack_public_root=Path(selection["public_root"]),
                evaluation_pack_private_root=Path(selection["private_root"]),
            )
        adapters[batch_digest] = LeanRecipeAdapter(
            batch_discovery,
            providers,
            ledger,
            measure_query=cfg["measure_query"],
            copy_hotkey=cfg["receiver_hotkey"],
            speed_sample_key=_speed_key(cfg),
        )
    return adapters


def _request_buckets(cfg):
    """R89's per-group request buckets when configured (every value the owner's), else None (the peer bucket)."""
    from carbon.challenge_validator.request_buckets import RequestBuckets

    block = cfg.get("request_buckets")
    return None if block is None else RequestBuckets(block)


def _version_closed(cfg):
    """``{submission_id: owner}`` of the configured earlier versions' closed submissions (`version_close.load`), or
    ``{}`` without the field. A field that names no file of an earlier version of THIS Challenge refuses.
    """
    if "version_closed_files" not in cfg:
        return {}
    from carbon.challenge_validator import version_close

    selected = cfg["version_closed_files"]
    challenge = cfg.get("challenge")
    if type(selected) is not list or not selected or type(challenge) is not dict:
        raise ValueError("version_closed_files needs a list of files and the Challenge")
    return version_close.load(
        selected, challenge_id=challenge.get("id"), version=challenge.get("version")
    )


def _funder_map(cfg):
    """The configured allowance-group map; with none, every coldkey is its own group."""
    from carbon.challenge_validator import funder_map

    return funder_map.load(cfg.get("funder_map_file"))


def _speed_key(cfg):
    """The configured speed-sample key, or None (a pool grade then has no speed evidence: typed unavailable)."""
    name = cfg.get("speed_sample_key_file")
    return None if name is None else read_speed_sample_key(name)


class ReceiverSnapshotWindow:
    """Persist the highest finalized observation before it can grant work.

    The intake's ordinary snapshot window retains request-pinned snapshots.
    It does not order refreshes, so a lagged chain read must never restore an
    earlier registration after a newer revocation or recycled identity.
    """

    _SCHEMA = "carbon.construction.receiver-snapshot-high-water.v1"

    def __init__(self, root, context, receiver, *, clock=time.time):
        from carbon.battery.intake import SnapshotWindow

        self._window = SnapshotWindow(clock=clock)
        self._lock = threading.RLock()
        self._path = root / "snapshot-high-water.json"
        self._binding = {"context": asdict(context), "receiver": receiver}
        self._unavailable = False
        if self._path.is_symlink():
            raise ValueError("receiver snapshot high-water link refused")
        self._state = private_json(self._path) if self._path.exists() else None
        if self._state is not None and (
            type(self._state) is not dict
            or set(self._state)
            != {
                "schema",
                "context",
                "receiver",
                "finalized_block",
                "snapshot_id",
                "conflict",
            }
            or self._state["schema"] != self._SCHEMA
            or any(
                self._state[field] != value for field, value in self._binding.items()
            )
            or type(self._state["finalized_block"]) is not int
            or self._state["finalized_block"] < 0
            or type(self._state["snapshot_id"]) is not str
            or not self._state["snapshot_id"].startswith("sha256:")
            or len(self._state["snapshot_id"]) != 71
            or any(
                digit not in "0123456789abcdef"
                for digit in self._state["snapshot_id"][7:]
            )
            or type(self._state["conflict"]) is not bool
        ):
            raise ValueError("retained receiver snapshot high-water differs")

    def _record(self, snapshot, *, conflict):
        state = {
            "schema": self._SCHEMA,
            **self._binding,
            "finalized_block": snapshot.finalized_block,
            "snapshot_id": snapshot.snapshot_id,
            "conflict": conflict,
        }
        descriptor, staged = tempfile.mkstemp(
            prefix=f".{self._path.name}.", dir=self._path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(canonical(state))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(staged, 0o600)
            if self._path.is_symlink():
                raise ValueError("receiver snapshot high-water link refused")
            os.replace(staged, self._path)
            if os.name != "nt":
                directory = os.open(self._path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)
        self._state = state

    def add(self, snapshot):
        if asdict(snapshot.context) != self._binding["context"]:
            raise ValueError("receiver snapshot context differs")
        with self._lock:
            try:
                prior = self._state
                if prior is not None:
                    if snapshot.finalized_block < prior["finalized_block"]:
                        return
                    if snapshot.finalized_block == prior["finalized_block"]:
                        if snapshot.snapshot_id != prior["snapshot_id"]:
                            if not prior["conflict"]:
                                self._record(snapshot, conflict=True)
                            return
                        if prior["conflict"]:
                            return
                        self._window.add(snapshot)
                        return
                self._record(snapshot, conflict=False)
                self._window.add(snapshot)
                self._unavailable = False
            except Exception:
                # A fresher read without a durable watermark is never allowed
                # to leave earlier registration usable for background dispatch.
                self._unavailable = True
                raise

    def get(self, snapshot_id):
        return self._window.get(snapshot_id)

    def latest(self):
        with self._lock:
            if self._state is None or self._state["conflict"] or self._unavailable:
                return None
            return self._window.latest()

    def latest_good(self, max_age_s):
        """`latest` at another age bound (`battery.intake.grading_snapshot`: one epoch for already-admitted work). Still
        None on a high-water conflict or while ``_unavailable`` (a fresher read whose watermark could not be made
        durable: the older snapshot may predate a revocation, so it never grants work), whatever its age.
        """
        with self._lock:
            if self._state is None or self._state["conflict"] or self._unavailable:
                return None
            return self._window.latest_good(max_age_s)

    def age_s(self, snapshot):
        return self._window.age_s(snapshot)


#: How often a retain or regrade run reads a fresh finalized snapshot. The
#: 60 s freshness window (`battery.intake.SNAPSHOT_MAX_AGE_S`) is part of the
#: registration authority check and is not lengthened.
RETENTION_REFRESH_S = 20.0


@contextlib.contextmanager
def retention_snapshots(window, context, reader, *, period=RETENTION_REFRESH_S):
    """Keep fresh finalized snapshots flowing into ``window`` for a retain or
    regrade run's whole life.

    Serve mode gets fresh snapshots from the intake; a retain or regrade has no
    intake, so a run longer than the window's freshness (60 s) would find no
    snapshot at the provider's registration re-check and refuse with
    ``direct_provider_registration_unavailable``. This reads a finalized
    snapshot with the same chain reader and context as startup every
    ``period`` seconds into the same ``ReceiverSnapshotWindow`` (which enforces
    the durable high-water, so a lagged read never restores an earlier
    registration), and stops with the run. A failed read keeps the previous
    snapshots and is logged by exception type only (``battery.intake.refresher``):
    once they age out the re-check refuses as infrastructure
    (``Unavailable``), never as a candidate failure.
    """
    from carbon.battery.intake import refresher

    stop = threading.Event()
    thread = threading.Thread(
        target=refresher,
        args=(window, context),
        kwargs={"reader": reader, "period": period, "stop": stop},
        name="retention-snapshot-refresher",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)


#: The manifest fields an accepted-revision change may move, and how (`_migrate_owner_manifest`).
_REVISION_FIELDS = frozenset(
    {"implementation", "runtime", "receiver_binding", "campaign_id"}
)


#: The image fields of an owner's frozen manifest that may follow a DECLARED door migration of the worker images
#: (`state_binding.migrated_images`): the run binding's image ids and the runtime's image list. Nothing else.
_MIGRATED_IMAGE_FIELDS = {
    "receiver_binding": frozenset(
        {"parent_image", "inference_image", "construction_parents"}
    ),
    "runtime": frozenset({"images"}),
}


def _revision_only_change(frozen, candidate, *, images_migrated=False):
    """Whether ``frozen`` and ``candidate`` differ only by the accepted revision: every other field equal, ``runtime``
    and ``receiver_binding`` equal but for their ``implementation`` (so the same images, receiver, Challenge, pack and
    owner), ``campaign_id`` the one the new binding derives. With ``images_migrated`` (this state's door was moved to
    new worker images by a declared migration, `state_binding.migrated_images`) the image fields
    (`_MIGRATED_IMAGE_FIELDS`) may also differ, present or added, never dropped."""
    if set(frozen) != set(candidate):
        return False
    if any(frozen[k] != candidate[k] for k in candidate if k not in _REVISION_FIELDS):
        return False
    for key in ("runtime", "receiver_binding"):
        old, new = frozen[key], candidate[key]
        movable = _MIGRATED_IMAGE_FIELDS[key] if images_migrated else frozenset()
        if type(old) is not dict or type(new) is not dict:
            return False
        if not set(old) <= set(new) or set(new) - set(old) - movable:
            return False
        if any(
            old.get(k) != new[k]
            for k in new
            if k != "implementation" and k not in movable
        ):
            return False
    old, new = frozen["implementation"], candidate["implementation"]
    return (
        type(old) is dict
        and type(new) is dict
        and set(old) == set(new)
        and type(old.get("revision")) is str
        and type(new.get("revision")) is str
        and old["revision"] != new["revision"]
    )


#: `git` bounds for the start's history reads, first try then one retry (18 Nov 2026: a start runs them once per
#: retained owner; a bound hit under load must not set an owner aside, so a timeout is retried once, longer).
GIT_READ_SECONDS = (30, 120)
#: (old, new, root) -> the ancestry git answered (True / False), read once per start; an unanswered read is not kept
_ANCESTRY = {}
#: (old, new) pairs git could not answer at all (timeout or error): the refusal's reason says so (`_migration_refused`)
_ANCESTRY_UNKNOWN = set()


def _is_ancestor(old, new, root=None):
    """Whether accepted revision ``old`` is an ancestor of ``new`` in this checkout's history (git). Answered once per
    start (`_ANCESTRY`); a read that times out is retried once with a longer bound (`GIT_READ_SECONDS`); one git
    still cannot answer is False (the migration refuses, as before) and noted in `_ANCESTRY_UNKNOWN`.
    """
    import subprocess

    if not all(
        type(r) is str and len(r) == 40 and all(c in "0123456789abcdef" for c in r)
        for r in (old, new)
    ):
        return False
    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    key = (old, new, str(root))
    if key in _ANCESTRY:
        return _ANCESTRY[key]
    for seconds in GIT_READ_SECONDS:
        try:
            done = subprocess.run(
                ["git", "-C", str(root), "merge-base", "--is-ancestor", old, new],
                capture_output=True,
                timeout=seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            continue
        except OSError:
            break
        if done.returncode in (0, 1):
            # git's own answer: an ancestor (0) or not (1); anything else is an error (an unknown commit)
            _ANCESTRY[key] = done.returncode == 0
            _ANCESTRY_UNKNOWN.discard((old, new))
            return _ANCESTRY[key]
        break
    _ANCESTRY_UNKNOWN.add((old, new))
    return False


#: M2 (Validator 4 Nov 12:55): the grading and rebuild paths, by the Validator's categories. A carried owner's manifest
#: is migrated only when OLD..NEW changes none of them AND leaves the worker build inputs (`build_inputs.txt`, the
#: scope of every image identity) byte-identical. A path ending in ``/`` is a directory prefix; the rest are exact.
GRADING_PATHS = (
    # reconstruction: how a submitted recipe is rebuilt and run
    "carbon/reconstruction/",
    "carbon/execution/",
    "carbon/development_session/bundle_construction_worker.py",
    "carbon/development_session/construction_recipe.py",
    "carbon/development_session/research_carrier.py",
    "carbon/development_session/research_tasks.py",
    "carbon/development_session/paired_inference.py",
    # every graded and retained reader takes a snapshot's RAW bytes through data.read_raw (V2 21 Nov 2026, DATA head)
    "carbon/development_session/data.py",
    "carbon/development_session/graph_gpu_lane.py",
    # the graph rebuild (Validator 16:38): the direct-graph worker, the graph engine and what it stages
    "carbon/development_session/direct_graph_construction_worker.py",
    # the graded per-case loop over pinned worker processes (Lead's order 16 Nov): it runs the graded calls
    "carbon/development_session/case_procs.py",
    "carbon/level4/",
    "carbon/development_session/construction_tensor_codec.py",
    "carbon/development_session/build_refusal.py",
    "carbon/development_session/build_refusal_v2.py",
    "carbon/development_session/bundle_prediction_comparison.py",
    "carbon/development_session/single_call_timing.py",
    # the self-trust inference program variant (SELF_TRUST H3f): the graded container's split of a trust candidate's output
    "carbon/development_session/trust_infer.py",
    # the per-version trust training registration (SELF_TRUST H3d-2c): the derive and the owner's values the trust trainer reads
    "carbon/development_session/physical_graph_trust_registry.py",
    "carbon/challenge_validator/strict_json.py",
    # which changed grading paths a door's served version never reads (v2 RE-RULING #5): it decides that a change
    # needs no declared record on this door, so its own edits are grading changes
    "carbon/challenge_validator/grading_scope.py",
    # the construction material a rebuild reads (bundles, kits, TRAIN)
    "carbon/development_session/library_bundles.py",
    "carbon/development_session/library_environment_cache.py",
    "carbon/development_session/library_overlay_prep.py",
    "carbon/challenge_kit/physical_material.py",
    "carbon/challenge_kit/physical_public.py",
    "carbon/challenge_kit/physical_pack.py",
    "carbon/challenge_kit/f02_public.py",
    "carbon/challenge_kit/f08_public.py",
    "carbon/challenge_kit/synthetic_linear_field_2d.py",
    "carbon/challenge_kit/interface_dtype.py",
    "carbon/battery/challenge.py",
    "carbon/battery/construction_bundle_material.py",
    "carbon/battery/construction_material.py",
    # images
    "carbon/development_session/research_image.py",
    # catalog
    "carbon/backbone_catalog/",
    "carbon/backbones/",
    # scoring, and the official grade that applies it
    "carbon/scoring/",
    "carbon/measurement/",
    "carbon/measurement_runtime/",
    "carbon/challenge_validator/lean_recipe_retention.py",
    # the same-ceiling gate the grade's pair reads hold (owner LO-3; `pair_read_bound`'s lock replaced at runtime)
    "carbon/challenge_validator/pair_read_gate.py",
    "carbon/challenge_validator/scoring.py",
    "carbon/challenge_validator/koth_registry.py",
    "carbon/challenge_validator/crown_average.py",
    # the live crown pieces moved out of crown_average (over-broad audit S7, crown delete stage 2a)
    "carbon/challenge_validator/crown_common.py",
    # a menu-D version's coded crown hold (Validator-2B 7 Nov): it decides whether a crown may change
    "carbon/challenge_validator/crown_hold.py",
    # the crown rule (owner 14 Nov, the default for every version since 17 Nov): official totals + the version's margin row
    "carbon/challenge_validator/crown_official.py",
    "scripts/validator_host_classes/crown_official_score.json",
    # a vmap-64 version's speed-match tolerance (CV-Motor-B S2, 15 Nov): it decides whether a timed stage matches or is
    # Carbon's FAILED_INFRA
    "carbon/challenge_validator/speed_match.py",
    # whether a timed build ran on a quiet host decides whose failure a wall stop is (owner 5 Nov: rebuilds consistently
    # timed; Validator-2 21:28)
    "carbon/challenge_validator/host_quiet.py",
    # one door grading a round per lane commits settles, crowns and markers in claim order (owner's order 16 Nov): it
    # decides which king a crown is compared against
    "carbon/challenge_validator/grade_sequencer.py",
    "carbon/challenge_validator/bank_promotion.py",
    "carbon/battery/pool_store.py",
    # registry
    "carbon/registry/",
    "carbon/challenge_registry/",
    "carbon/challenge_kit/version_registry.py",
    "carbon/challenge_kit/served_versions.py",
    "carbon/challenge_kit/version_overlay.py",
    # a version's own whole-task wall (Motor 1.8: owner wall rule 12 Nov), read by the published limits and the rebuild
    "carbon/challenge_kit/task_wall_overrides.py",
    # pack
    "carbon/evaluation_packs/",
    "carbon/challenge_validator/evaluation_pack.py",
    "carbon/challenge_validator/pack_set_grading.py",
    "carbon/challenge_validator/pack_set_result.py",
    "carbon/challenge_validator/sealed_pack_import.py",
    "carbon/challenge_validator/sealed_exam_common.py",
    "carbon/challenge_validator/hidden_batch_store.py",
    "carbon/challenge_validator/exam_rotation.py",
)
#: The per-Challenge grading modules (``f02_hidden.py``, ``motor_scoring.py``, ``battery_bank.py`` ...) and every graph
#: adapter, state and trainer module, including later versions (``physical_graph_adapter_v3.py``).
_GRADING_MODULE = re.compile(
    r"carbon/challenge_validator/[a-z0-9_]+_(hidden|source|scoring|sealed|bank)\.py"
    r"|carbon/development_session/(physical_graph_(adapter|state|trainer)(_v[0-9]+)?"
    r"|graph_adapters|[a-z0-9_]+_graph_adapter|bundle_graph_state)\.py"
)
#: Modules the official grade or rebuild imports that are NOT grading paths, each with its reason (Validator 16:38; the
#: closure test, `test_grading_paths`, fails on any import of the grade/rebuild entry points that is in neither list).
GRADING_EXCLUDED = (
    (
        "carbon.challenge_validator.exam_cap",
        "slot accounting, not results (Validator 16:38)",
    ),
    ("carbon.challenge_validator.lean_recipe", "task identity (Validator 16:38)"),
    (
        "carbon.challenge_validator.ladder_store",
        "the miner's feedback documents: display of a result, not the result",
    ),
    (
        "carbon.challenge_validator.part_feedback",
        "which feedback schema is served: display",
    ),
    (
        "carbon.challenge_validator.gate_failure_feedback",
        (
            "the failing output names and closed reasons published after a gate-failed grade: display derived from the grade's record"
            " by an allow-list, never a grade input or a score (Bundle A; Validator to confirm)"
        ),
    ),
    (
        "carbon.challenge_validator.repeat_miss_watch",
        "an operator watch: writes no result",
    ),
    (
        "carbon.challenge_validator.grade_archive",
        (
            "storage only: puts an operator-archived origin's retained files back by sha256 before a regrade reads"
            " them; the regrade then re-checks every file against its role manifest digest (V2 to confirm)"
        ),
    ),
    (
        "carbon.development_session.profile",
        "canonical JSON and digest helpers: identity, verified where bound",
    ),
    (
        "carbon.development_session.research_workspace",
        "the owner's staged graph workspace: the worker re-checks every byte by its digest",
    ),
    (
        "carbon.file_seal",
        "a stat cache for the allowlist read: the bytes are sha256-verified (allowlist V8_SHA256)",
    ),
    ("carbon.research", "the task protocol's wire types and codec: orchestration"),
    (
        "carbon.challenge_validator.koth_journal",
        "journal lines of crown events (ids, keys, outcome and reason codes): an operator log, never a grade input",
    ),
    (
        "scripts.dev.score_lab.public_unbound_custody",
        (
            "ScoreLab custody of the retained graph artifacts (role schema, byte and codec checks, read ceiling): it computes"
            " no grade value; a defect fails retention (FAILED_INFRA), and retention refuses unless the role schema is the"
            " pinned v5 string (v2 01:51:15Z note; case-procs 02:00:17Z)"
        ),
    ),
    (
        "scripts.dev.score_lab.public_unbound_entry",
        "the create-only ScoreLab index receipt of a retained artifact group: storage, never a grade input or a score",
    ),
    (
        "scripts.dev.score_lab.synthetic_linear_field_reference",
        (
            "the public practice measurement sidecar of synthetic-linear-field-2d 1.3 only, and only when the result has no"
            " evaluation pack: never an official pack grade"
        ),
    ),
    ("carbon.challenge_validator", "package __init__: re-exports only"),
    ("carbon.development_session", "package __init__: re-exports only"),
    ("carbon.challenge_kit", "package __init__: re-exports only"),
    ("carbon.battery", "package __init__: re-exports only"),
)
#: Named in a refusal instead of a path: the worker build inputs moved.
BUILD_INPUTS_CHANGED = "build_inputs"


def grading_path(path):
    """Whether repo-relative ``path`` is a grading or rebuild path (M2)."""
    return _GRADING_MODULE.fullmatch(path) is not None or any(
        path.startswith(prefix) if prefix.endswith("/") else path == prefix
        for prefix in GRADING_PATHS
    )


_GRADING_CHANGES = {}

#: The receiver configuration's declared exam change (`install_declared_change`), or None: no grading-path change migrates.
DECLARED_EXAM_CHANGE = None
#: The configuration's earlier declared changes (`earlier_declared_changes`): hops a chain may take (`_declared_change`).
EARLIER_DECLARED_CHANGES = ()
_DECLARED_FIELDS = {
    "from_revision",
    "to_revision",
    "paths",
    "reason",
    "evidence_sha256",
}


def _check_declared_change(record):
    """A declared exam change record is exactly its five fields: two full commit ids, a non-empty sorted list of
    distinct repo paths (or `BUILD_INPUTS_CHANGED`), a reason, and the evidence's sha256 digest.
    """
    if (
        type(record) is not dict
        or set(record) != _DECLARED_FIELDS
        or any(
            type(record[name]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", record[name])
            for name in ("from_revision", "to_revision")
        )
        or type(record["paths"]) is not list
        or not record["paths"]
        or any(type(path) is not str or not path for path in record["paths"])
        or record["paths"] != sorted(set(record["paths"]), key=record["paths"].index)
        or type(record["reason"]) is not str
        or not record["reason"].strip()
        or type(record["evidence_sha256"]) is not str
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", record["evidence_sha256"])
    ):
        raise ValueError("invalid declared_exam_change")
    return record


def _check_earlier_changes(records):
    """A non-empty list of declared exam change records (`_check_declared_change` each), no two from one revision."""
    if type(records) is not list or not records:
        raise ValueError("invalid earlier_declared_changes")
    for record in records:
        _check_declared_change(record)
    if len({record["from_revision"] for record in records}) != len(records):
        raise ValueError("invalid earlier_declared_changes")
    return tuple(records)


def _king_retained_parents(paths):
    """The identities a ``king_retained_parents`` list names: a non-empty list of distinct absolute manifest paths, each
    a valid worker-image manifest, with distinct image ids."""
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    if (
        type(paths) is not list
        or not paths
        or any(type(p) is not str or not Path(p).is_absolute() for p in paths)
        or len(set(paths)) != len(paths)
    ):
        raise ValueError("invalid king_retained_parents")
    try:
        identities = [load_image_identity(Path(p)) for p in paths]
    except Exception:  # noqa: BLE001
        raise ValueError("invalid king_retained_parents") from None
    if len({i.image_id for i in identities}) != len(identities):
        raise ValueError("invalid king_retained_parents")
    return identities


def install_king_retained_parents(cfg):
    """Install the configuration's king retained parents (`lean_recipe_retention.KING_RETAINED_PARENTS`)."""
    from carbon.challenge_validator import lean_recipe_retention

    paths = cfg.get("king_retained_parents")
    lean_recipe_retention.install_king_retained_parents(
        [] if paths is None else _king_retained_parents(paths)
    )


def _graded_inference_image(path):
    """The identity a ``graded_inference_image`` names: one absolute path of a valid worker-image manifest (loaded
    exactly like one ``king_retained_parents`` entry)."""
    try:
        (identity,) = _king_retained_parents([path])
    except ValueError:
        raise ValueError("invalid graded_inference_image") from None
    return identity


def install_graded_inference_image(cfg):
    """Install the configuration's graded inference image (`lean_recipe_retention.GRADED_INFERENCE_IMAGE`)."""
    from carbon.challenge_validator import lean_recipe_retention

    path = cfg.get("graded_inference_image")
    lean_recipe_retention.install_graded_inference_image(
        None if path is None else _graded_inference_image(path)
    )


def install_declared_change(cfg):
    """Set (or clear) `DECLARED_EXAM_CHANGE` from a loaded receiver configuration."""
    global DECLARED_EXAM_CHANGE, EARLIER_DECLARED_CHANGES
    record = cfg.get("declared_exam_change")
    DECLARED_EXAM_CHANGE = None if record is None else _check_declared_change(record)
    earlier = cfg.get("earlier_declared_changes")
    EARLIER_DECLARED_CHANGES = (
        () if earlier is None else _check_earlier_changes(earlier)
    )


def _declared_change(old, new, touched):
    """The declared record when it covers exactly this migration (its revisions are OLD and NEW, and its paths EQUAL the
    computed changed grading paths, in order), else None.

    A CHAIN (live 116, 18 Nov 2026: an owner left lazy across one start is frozen one revision back): when no single
    record covers OLD..NEW, the hops OLD -> ... -> NEW must each be a declared record (`EARLIER_DECLARED_CHANGES` or the
    current one), each hop's paths EQUAL to that hop's OWN computed changed grading paths. A stretch with NO grading
    change needs no record (exactly as a single-hop migration needs none): the chain steps over it to the next record's
    revision, or to NEW, when that revision descends from where it stands and git computes no changed grading path. The
    answer is then one record naming OLD..NEW, the computed paths, every hop's reason and the last hop's evidence.
    """
    record = DECLARED_EXAM_CHANGE
    if record is None or touched is None:
        return None
    if (record["from_revision"], record["to_revision"]) == (old, new):
        return record if list(record["paths"]) == list(touched) else None
    hops = {item["from_revision"]: item for item in (*EARLIER_DECLARED_CHANGES, record)}

    def unchanged(start, end):
        # no grading change from START to END: no record is needed for that stretch
        return _is_ancestor(start, end) and _grading_change(start, end) == ()

    at, used = old, []
    while at != new:
        if unchanged(at, new):
            break
        hop = hops.get(at)
        if hop is None:
            hop = next(
                (
                    item
                    for item in hops.values()
                    if item not in used and unchanged(at, item["from_revision"])
                ),
                None,
            )
        if hop is None or hop in used:
            return None
        own = _grading_change(hop["from_revision"], hop["to_revision"])
        if own is None or list(own) != list(hop["paths"]):
            return None
        used.append(hop)
        at = hop["to_revision"]
    if not used:
        return None
    return {
        "from_revision": old,
        "to_revision": new,
        "paths": list(touched),
        "reason": " | ".join(hop["reason"] for hop in used),
        "evidence_sha256": used[-1]["evidence_sha256"],
    }


def _grading_change(old, new, root=None):
    """M2: the grading or rebuild paths OLD..NEW changes (`BUILD_INPUTS_CHANGED` first when the worker build inputs
    moved), ``()`` when none, or None when git cannot tell (the migration then refuses). Renames count both sides.
    """
    import subprocess

    from carbon.reconstruction.worker import build_inputs

    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    key = (old, new, str(root))
    if key in _GRADING_CHANGES:
        return _GRADING_CHANGES[key]
    names = None
    # a bound hit under load is retried once, longer (see `GIT_READ_SECONDS`)
    for seconds in (60, 180):
        try:
            moved = build_inputs.listing(root, revision=old) != build_inputs.listing(
                root, revision=new
            )
            names = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", "-z", "--no-renames"]
                + [old, new],
                capture_output=True,
                timeout=seconds,
                check=True,
            ).stdout.decode("utf-8")
            break
        except subprocess.TimeoutExpired:
            continue
        except (OSError, ValueError, UnicodeDecodeError, subprocess.SubprocessError):
            return None
    if names is None:
        return None
    touched = [BUILD_INPUTS_CHANGED] if moved else []
    touched += sorted(path for path in names.split("\0") if path and grading_path(path))
    _GRADING_CHANGES[key] = tuple(touched)
    return _GRADING_CHANGES[key]


def _grading_change_not_served(old, new, touched, challenge, root=None):
    """``{path: reason}`` when every changed grading path of OLD..NEW is one the served ``challenge`` never reads
    (`grading_scope.not_served`: another pair's keyed registry entry, or a pure ``.py`` addition), else None. A build
    input move, an unreadable challenge or any doubt is None: the migration then decides exactly as before.
    """
    from carbon.challenge_validator import grading_scope

    if not touched or BUILD_INPUTS_CHANGED in touched or type(challenge) is not dict:
        return None
    challenge_id, version = challenge.get("id"), challenge.get("version")
    if type(challenge_id) is not str or type(version) is not str:
        return None
    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    return grading_scope.not_served(
        root, old, new, touched, {f"{challenge_id} {version}"}, grading_path
    )


def _retained_contracts(ledger):
    """Every ``contract_digest`` the owner's retained task requests name."""
    found = set()

    def walk(value):
        if type(value) is dict:
            for key, item in value.items():
                if key == "contract_digest" and type(item) is str:
                    found.add(item)
                else:
                    walk(item)
        elif type(value) is list:
            for item in value:
                walk(item)

    with ledger.db() as db:
        try:
            rows = db.execute("SELECT request FROM direct_tasks").fetchall()
        except Exception:  # noqa: BLE001 - no task table yet: no retained task
            rows = []
    for (raw,) in rows:
        try:
            walk(json.loads(raw))
        except (ValueError, TypeError):
            found.add("unreadable")
    return found


def _migration_refused(hotkey, old, new, reason):
    """Log why one owner's manifest was not migrated (18 Nov 2026: switch 3's start refused with no reason), then
    False. The owner appears as its sha256 only; the revisions are the frozen and the candidate ones.
    """
    import sys

    def revision(implementation):
        return implementation.get("revision") if type(implementation) is dict else None

    print(
        json.dumps(
            {
                "event": "owner_manifest_migration_refused",
                "reason": reason,
                "owner_sha256": hashlib.sha256(str(hotkey).encode()).hexdigest(),
                "from_revision": revision(old),
                "to_revision": revision(new),
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )
    return False


#: Grade-marker states that carry NO grade evidence (`auto_grade`): the grade failed Carbon-side (no score was accepted;
#: an automatic retry grades it again) or the miner withdrew the task. Every other marker state is a grade.
_UNGRADED_MARKERS = frozenset({"FAILED", "WITHDRAWN_BY_MINER"})


def _owner_task_states(owner_dir):
    """``[(task id, state name)]`` of every task in ``owner_dir``'s task store (read-only), or None when it cannot be
    read (doubt keeps the declaration: `_ungraded_owner`)."""
    import sqlite3

    from carbon.research import DirectTaskViewV3, load_canonical

    path = Path(owner_dir) / "tasks" / "direct-tasks.sqlite3"
    if not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            rows = db.execute("SELECT id, view FROM direct_tasks").fetchall()
        finally:
            db.close()
        found = []
        for identity, view_raw in rows:
            view = load_canonical(view_raw, DirectTaskViewV3)
            if view.task_id.value != identity:
                return None
            found.append((identity, view.state.value))
    except Exception:  # noqa: BLE001 - unreadable: the declaration decides, as before
        return None
    return found


def _marker_state(markers_dir, task_id):
    """The grade marker state of ``task_id`` (None: no marker; ``"UNREADABLE"``: a marker that cannot be read)."""
    path = Path(markers_dir) / f"{task_id}.json"
    try:
        if path.is_symlink():
            return "UNREADABLE"
        if not path.exists():
            return None
        body = json.loads(path.read_text())
    except (OSError, ValueError):
        return "UNREADABLE"
    state = body.get("state") if type(body) is dict else None
    return state if type(state) is str else "UNREADABLE"


def _ungraded_owner(owner_dir, markers_dir, *, build_inputs_changed):
    """Over-broad rules audit #12 (M2 narrowed): the counts ``{"tasks", "unbuilt", "built_ungraded"}`` when NOTHING this
    owner holds was graded under the old program, else None (the hand-declared change stays required).

    What M2 protects is the evidence a grade bound to the program that made it: a grading or rebuild change is never
    carried under an owner whose tasks were graded (or may be regraded, repeated or rebuilt for a crown) under the old
    program, without the declared record V2 receipts. An owner with no grade evidence at all has nothing bound to the old
    program: its unbuilt tasks are built and graded on the new one; a built task with no grade (no marker, or a FAILED
    or withdrawn one) is graded on the new one for the first time, and only when the worker build inputs are unchanged
    (``build_inputs_changed`` False: the state was built by the same worker images the new door runs). Doubt (no door
    markers, an unreadable store or marker) keeps the declaration.
    """
    if markers_dir is None:
        return None
    states = _owner_task_states(owner_dir)
    if states is None:
        return None
    unbuilt = built = 0
    for task_id, state in states:
        marker = _marker_state(markers_dir, task_id)
        if marker is not None and marker not in _UNGRADED_MARKERS:
            return None  # graded under the old program (or a marker that cannot be read): declared only
        if state == "SUCCEEDED" and marker != "WITHDRAWN_BY_MINER":
            if build_inputs_changed:
                return None  # a built state from the old worker images would be graded: declared only
            built += 1
        else:
            unbuilt += 1
    return {"tasks": len(states), "unbuilt": unbuilt, "built_ungraded": built}


def _migrate_owner_manifest(
    ledger,
    hotkey,
    raw,
    frozen,
    candidate,
    *,
    images_migrated=False,
    markers_dir=None,
    host=False,
):
    """Re-freeze a retained owner's campaign manifest to a NEW accepted revision (Lead 4 Nov, option (a)), or False.

    A byte-exact carry of the owners/ store into a receiver on a newer revision met its own frozen manifest
    (the revision is part of it) and refused to start. The manifest is re-frozen only when the change is the revision
    alone (`_revision_only_change`), the old revision is an ANCESTOR of the new one (`_is_ancestor`), and every retained
    task names the contract this receiver serves (the recipe contract is unchanged); otherwise the start refuses as
    before. A change of grading or rebuild paths (M2) migrates under the declared record, or with none for an owner that
    holds no grade evidence (`_ungraded_owner`, over-broad rules audit #12; never the crown's host owner, ``host``,
    whose rebuilds are crown evidence; ``markers_dir`` is the door's grade-marker directory). Only the campaign row changes (compare-and-swap on its old bytes); every task, evidence and view row is
    kept. The change is logged to stderr and appended to ``manifest-migrations.jsonl`` beside the owner's ledger.
    """
    import sys

    from carbon.development_session.profile import canonical, digest
    from carbon.reconstruction.served_recipe_contract import registered

    refused = functools.partial(
        _migration_refused,
        hotkey,
        frozen.get("implementation") if type(frozen) is dict else None,
        candidate.get("implementation") if type(candidate) is dict else None,
    )
    if not _revision_only_change(frozen, candidate, images_migrated=images_migrated):
        return refused("change_not_revision_only")
    old, new = (
        frozen["implementation"]["revision"],
        candidate["implementation"]["revision"],
    )
    if not _is_ancestor(old, new):
        return refused(
            "ancestry_unknown"
            if (old, new) in _ANCESTRY_UNKNOWN
            else "revision_not_ancestor"
        )
    touched = _grading_change(old, new)
    declared = _declared_change(old, new, touched) if touched else None
    basis = "no_grading_change" if touched == () else None
    not_served = (
        _grading_change_not_served(old, new, touched, candidate.get("challenge"))
        if touched and declared is None
        else None
    )
    if declared is not None:
        basis = "declared"
        # the ruled amendment: a change the Validator receipted by its declaration and per-door evidence
        print(
            json.dumps(
                {
                    "event": "owner_manifest_migration_declared",
                    "from_revision": old,
                    "to_revision": new,
                    "paths": list(touched[:20]),
                    "reason": declared["reason"],
                    "evidence_sha256": declared["evidence_sha256"],
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
    elif not_served is not None:
        # v2 RE-RULING #5: every changed path is another pair's registry entry or a pure addition no served import can
        # reach (`grading_scope.not_served`, the release precheck's own verdict); journaled file by file
        basis = "grading_change_not_served"
        print(
            json.dumps(
                {
                    "event": "grading_change_not_served",
                    "from_revision": old,
                    "to_revision": new,
                    "files": not_served,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
    elif touched and not host:
        ungraded = _ungraded_owner(
            Path(ledger.root).parent,
            markers_dir,
            build_inputs_changed=BUILD_INPUTS_CHANGED in touched,
        )
        if ungraded is not None:
            # audit #12: nothing this owner holds was graded under the old program, so nothing is re-bound (counts only)
            basis = "ungraded_owner"
            print(
                json.dumps(
                    {
                        "event": "owner_manifest_migration_ungraded",
                        "from_revision": old,
                        "to_revision": new,
                        "paths": len(touched),
                        **ungraded,
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
    if basis is None:
        # M2: a grading or rebuild change is never carried under a manifest whose owner holds grade evidence of the old
        # program without the declared record. Said once per owner, so a spare proof shows why the start refused.
        print(
            json.dumps(
                {
                    "event": "owner_manifest_migration_refused",
                    "reason": (
                        "grading_change_unknown"
                        if touched is None
                        else "grading_path_changed"
                    ),
                    "from_revision": old,
                    "to_revision": new,
                    "paths": [] if touched is None else list(touched[:20]),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        return False
    challenge = candidate["challenge"]
    try:
        contract = registered(challenge["id"], challenge["version"]).digest
    except LookupError:
        return refused("contract_unregistered")
    if not _retained_contracts(ledger) <= {contract}:
        return refused("retained_contract_not_served")
    payload = canonical(candidate)
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE campaign SET manifest=?, digest=? WHERE id=1 AND manifest=?",
            (payload, digest(payload), raw),
        ).rowcount
    if changed != 1:
        return refused("manifest_changed_meanwhile")
    record = {
        "event": "owner_manifest_migrated",
        "owner_sha256": hashlib.sha256(hotkey.encode()).hexdigest(),
        "from_revision": old,
        "to_revision": new,
        "from_campaign": frozen["campaign_id"],
        "to_campaign": candidate["campaign_id"],
        # Validator 13:53 follow-up: the manifests themselves, by digest (the old one stays in the record as history).
        "from_manifest_sha256": hashlib.sha256(
            raw if type(raw) is bytes else str(raw).encode("utf-8")
        ).hexdigest(),
        "to_manifest_sha256": hashlib.sha256(payload).hexdigest(),
        # why it was allowed: no grading change, the declared record, a change the served version never reads (v2
        # RE-RULING #5), or an owner with no grade evidence (audit #12)
        "basis": basis,
    }
    if not_served is not None:
        record["files_not_served"] = not_served
    with open(
        Path(ledger.root) / "manifest-migrations.jsonl", "a", encoding="utf-8"
    ) as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)
    return True


def installed_source(
    profile_path: Path,
    *,
    construction_image_manifest: Path | None = None,
    running: dict | None = None,
):
    """Verify installed source/images; a private operator may pin its constructor.

    The checkout may be the accepted revision or a clean, values-only descendant of it (`accepted_values_descendant`).
    The returned implementation is always the ACCEPTED revision's identity, so every binding made from it is unchanged
    by a values push; the commit the receiver runs on is put in ``running["head"]`` for the grade records.
    """
    from carbon.development_session.gpu_practice import direct_parent_backend
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import (
        DescendantRefused,
        accepted_values_descendant,
        verify_current_worker,
        verify_direct_v13_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg = validated_profile(private_json(profile_path))
    if cfg["enabled"] is not True:
        raise ValueError("installed dispatch is disabled")
    implementation = None
    development_candidate = False
    if (
        profile_path.is_absolute()
        and profile_path.resolve() == profile_path
        and profile_path.name == "runner-profile.json"
        and profile_path.parent.name == "environment"
    ):
        implementation = installed.candidate_implementation(profile_path.parent.parent)
        development_candidate = implementation is not None
        if development_candidate and (
            cfg["runtime"]["implementation"] != implementation
            or cfg["accepted_revision"] != implementation["revision"]
            or Path(cfg["campaigns_root"]) != profile_path.parent / "campaigns"
        ):
            raise ValueError("development candidate profile differs")
    if implementation is None:
        try:
            implementation = accepted_values_descendant(cfg["accepted_revision"])
        except DescendantRefused as refused:
            raise ReceiverUnavailable(refused.code) from None
        if running is not None:
            running["head"] = implementation["running_head"]
        implementation = {
            name: value
            for name, value in implementation.items()
            if name != "running_head"
        }
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    gpu_image_path = cfg.get("gpu_image")
    if construction_image_manifest is not None:
        if (
            not isinstance(construction_image_manifest, Path)
            or not construction_image_manifest.is_absolute()
            or construction_image_manifest.is_symlink()
            or not construction_image_manifest.is_file()
            or construction_image_manifest.resolve() != construction_image_manifest
            or gpu_image_path is not None
            or "gpu_research" in cfg["runtime"]
        ):
            raise ValueError("private construction parent conflicts with profile")
        gpu_image_path = str(construction_image_manifest)
    primary_torch_cpu = None
    if gpu_image_path is None and not development_candidate:
        primary_torch_cpu = load_image_identity(paths["image_manifest"])
        if direct_parent_backend(primary_torch_cpu) != "torch_cpu":
            raise ValueError("installed GPU parent required for direct development")
    if (
        development_candidate
        or construction_image_manifest is not None
        or gpu_image_path is None
    ):
        worker = primary_torch_cpu or load_image_identity(paths["image_manifest"])
        try:
            verify_current_worker(worker, implementation)
        except ValueError:
            if not development_candidate:
                raise
            verify_direct_v13_worker(
                worker,
                implementation,
                role=(
                    "torch_cpu"
                    if direct_parent_backend(worker) == "torch_cpu"
                    else "cpu"
                ),
            )
        if direct_parent_backend(worker) == "torch_cpu":
            verify_direct_v13_worker(worker, implementation, role="torch_cpu")
        analysis = load_analysis_image(paths["analysis_image_manifest"])
        verify_image(analysis)
        if analysis.parent_image != worker.image_id or cfg["runtime"].get("images") != [
            worker.image_id,
            analysis.image_id,
        ]:
            if development_candidate:
                raise ValueError("development candidate installed images differ")
            raise ValueError("installed CPU and analysis images differ")
    if gpu_image_path is None:
        if (
            not development_candidate and direct_parent_backend(worker) != "torch_cpu"
        ) or "gpu_research" in cfg["runtime"]:
            raise ValueError("installed GPU parent required for direct development")
        # The verified primary CPU worker is the direct construction parent.
        parent = worker
    else:
        if type(gpu_image_path) is not str:
            raise ValueError("installed GPU parent required for direct development")
        parent = load_image_identity(Path(gpu_image_path))
        backend = direct_parent_backend(parent)
        if backend not in {"jax", "pytorch", "torch_cpu"}:
            raise ValueError("installed direct parent backend is unregistered")
        if backend == "pytorch":
            verify_direct_v13_worker(parent, implementation, role="torch_gpu")
        elif backend == "torch_cpu":
            verify_direct_v13_worker(parent, implementation, role="torch_cpu")
        else:
            try:
                verify_current_worker(parent, implementation)
            except ValueError:
                verify_direct_v13_worker(parent, implementation, role="jax_gpu")
    if not doctor(image_id=parent.image_id, image_identity=parent).eligible:
        raise ReceiverUnavailable("installed_reconstruction_worker_unavailable")
    network = binding(
        operator_config=paths.get("operator_config"),
        miner_network=paths.get("miner_network"),
    )
    cache = Path(cfg["campaigns_root"]) / ".direct-development" / "library-cache"
    if not cache.is_absolute() or cache.resolve() != cache or cache.is_symlink():
        raise ValueError("installed library cache path differs")
    return implementation, parent, network, cache


def construction_parents(parent, implementation):
    """Both CPU construction parents for an operator that opts in.

    The C-03 CPU worker is derived from the verified PyTorch CPU worker built
    FROM it (`gpu_practice.derived_cpu_parent`), never read from a separate
    path, then checked against the worker ABI and the real image. Each bundle
    task then builds on the parent of its pinned runtime only.
    """
    from carbon.development_session.gpu_practice import (
        DirectParents,
        derived_cpu_parent,
        direct_parent_backend,
    )
    from carbon.development_session.research_campaign import verify_direct_v13_worker
    from carbon.reconstruction.worker.docker_runtime import doctor

    if direct_parent_backend(parent) != "torch_cpu":
        raise ValueError("per-runtime construction parents need the PyTorch CPU worker")
    cpu = derived_cpu_parent(parent)
    verify_direct_v13_worker(cpu, implementation, role="cpu")
    if not doctor(image_id=cpu.image_id, image_identity=cpu).eligible:
        raise ReceiverUnavailable("installed_cpu_construction_worker_unavailable")
    return DirectParents({"torch-cpu-py311": parent, "python-cpu-py311": cpu})


def gpu_construction_parents(
    cfg, implementation, parents, chain_network, challenge_id=None, version=None
):
    """`parents` plus the configured GPU workers as the parents of their GPU build runtimes
    (``jax-cuda13-py311`` / ``torch-cu130-py311``): ``(DirectParents, host device record)``.

    The CPU pair stays: an entry with no official-grade GPU twin (a smoke-only or
    non-repeating build) rebuilds on the CPU parent of its own runtime. Each worker is
    verified as the receiver's other workers are, must be eligible on this host, and its
    backend's accelerator profile must have the owner's hardware acceptance for the host's
    GPU class on this chain network, or the receiver refuses to start.

    A host with NO GPU device record whose door builds on a GPU box pool (`remote_gpu_build.door_pool` for
    ``challenge_id version``) binds the pool's CLASS instead (`remote_gpu_build.GpuClass`), as `graph_gpu_lane` does:
    the autoscaler may have released every box, and a start must not fail for it (V2, 17 Nov 2026); builds wait for a
    box or run on the CPU parent meanwhile. A host with a record binds it exactly as before.
    """
    from carbon.development_session import research_carrier
    from carbon.development_session.gpu_practice import (
        gpu_image_backend,
        gpu_images,
        with_gpu_parent,
    )
    from carbon.development_session.research_campaign import (
        verify_current_worker,
        verify_direct_v13_worker,
    )
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.hardware_acceptance import require_accepted
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    images = tuple(
        load_image_identity(Path(item)) for item in cfg["gpu_construction_images"]
    )
    gpu_images(images)  # one registered GPU worker per backend
    try:
        device = research_carrier._gpu_device()
    except ValueError:
        from carbon.reconstruction import remote_gpu_build

        pool = (
            None
            if challenge_id is None
            else remote_gpu_build.door_pool(challenge_id, version)
        )
        if pool is None:
            raise
        device = remote_gpu_build.GpuClass(pool.kind)
    profiles = {
        "jax": research_carrier._gpu_profile_id(),
        "pytorch": torch_profile.GPU_PROFILE_ID,
    }
    for image in images:
        backend = gpu_image_backend(image)
        if backend not in profiles:
            raise ValueError("a gpu construction image is a registered GPU worker")
        require_accepted(device.device_kind, profiles[backend], chain_network)
        try:
            verify_current_worker(image, implementation)
        except ValueError:
            verify_direct_v13_worker(
                image,
                implementation,
                role="jax_gpu" if backend == "jax" else "torch_gpu",
            )
        if not doctor(image_id=image.image_id, image_identity=image).eligible:
            raise ReceiverUnavailable("installed_gpu_construction_worker_unavailable")
    return with_gpu_parent(parents, images), device


def graph_gpu_lane(cfg, implementation, allowlist_bytes, chain_network, challenge=None):
    """The validator's graph GPU lane for an operator that configures one:
    ``(worker image, ops frozenset, ops record digest, host device record)``, else four Nones.

    With a GPU build box pool for the door's ``challenge`` (`remote_gpu_build.door_pool`), the device is the pool's
    CLASS (`remote_gpu_build.GpuClass`, bound as ``{"kind", "class": true}``): no box is needed at start, and each
    build checks its own box's GPU and worker image there (`remote_gpu_build.check_host`).

    The worker is the registered JAX GPU worker, verified as the receiver's other workers are;
    the ops are the record the hardware class check wrote, valid for the served graph allowlist
    only. Rebuild on the GPU, grade on the CPU: the lane changes where a graph is built, never
    how it is graded."""
    if "graph_gpu_image_manifest" not in cfg:
        return None, None, None, None
    from carbon.development_session.gpu_practice import gpu_image_backend
    from carbon.development_session.graph_gpu_lane import load_record
    from carbon.development_session.research_campaign import (
        verify_current_worker,
        verify_direct_v13_worker,
    )
    from carbon.level4.allowlist import Allowlist
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    if allowlist_bytes is None:
        raise ValueError("the graph GPU lane needs a graph-route version")
    from carbon.development_session import research_carrier

    # The host's installed GPU record, and the owner's hardware acceptance for its class on
    # this chain network: a validator scores only on an accepted class, and refuses at start
    # otherwise (hardware_acceptance.py; the same gate the Battery GPU validator applies).
    from carbon.reconstruction import remote_gpu_build
    from carbon.reconstruction.hardware_acceptance import require_accepted

    pool = (
        None
        if challenge is None
        else remote_gpu_build.door_pool(challenge.challenge_id, challenge.version)
    )
    if challenge is not None:
        # every graph build of this door runs on a box of exactly the CLASS bound here, or refuses as Carbon's; boxes
        # come and go without a restart (`remote_gpu_build`: read at every build)
        remote_gpu_build.pin(challenge.challenge_id, challenge.version, pool)
    if pool is not None:
        # the CLASS, never a box: no box is needed to start (a build with no eligible box is Carbon's, FAILED_INFRA),
        # and each build re-reads its box's GPU and image there before its container is created
        device = remote_gpu_build.GpuClass(pool.kind)
    else:
        device = research_carrier._gpu_device()
    require_accepted(
        device.device_kind, research_carrier._gpu_profile_id(), chain_network
    )
    image = load_image_identity(Path(cfg["graph_gpu_image_manifest"]))
    if gpu_image_backend(image) != "jax":
        raise ValueError("the graph GPU lane needs the JAX GPU worker")
    try:
        verify_current_worker(image, implementation)
    except ValueError:
        verify_direct_v13_worker(image, implementation, role="jax_gpu")
    if (
        pool is None
        and not doctor(image_id=image.image_id, image_identity=image).eligible
    ):
        raise ReceiverUnavailable("installed_graph_gpu_worker_unavailable")
    raw = canonical(private_json(Path(cfg["graph_gpu_ops"])))
    ops = load_record(raw, allowlist_digest=Allowlist(allowlist_bytes).digest)
    return image, ops, digest(raw), device


class OwnerProviders:
    """One maintained task supervisor and ledger per authenticated hotkey."""

    def __init__(
        self,
        root,
        discovery,
        parent,
        cache_root,
        *,
        inference_image=None,
        material_cache_bytes=None,
        implementation=None,
        snapshot=None,
        window=None,
        receiver=None,
        evaluation_pack_digest=None,
        parents=None,
        graph_gpu_image=None,
        graph_gpu_ops=None,
        images_migrated=False,
        binding_migrated=False,
        migrated_image_bindings=frozenset(),
        migrated_graph_gpu_images=None,
        migrated_bundle_images=None,
    ):
        from carbon.development_session.gpu_practice import DirectParents

        if parents is not None and (
            type(parents) is not DirectParents
            or parents.for_runtime("torch-cpu-py311") != parent
        ):
            raise ValueError("per-runtime parents must include the receiver parent")
        self.parents = parents
        self.graph_gpu_image, self.graph_gpu_ops = graph_gpu_image, graph_gpu_ops
        self.root, self.discovery = root, discovery
        self.parent, self.cache_root = parent, cache_root
        self.inference_image = parent if inference_image is None else inference_image
        self.material_cache_bytes = material_cache_bytes
        self.evaluation_pack_digest = evaluation_pack_digest
        #: the door of this state was moved to new worker images by a declared migration (`state_binding`)
        self.images_migrated = images_migrated
        #: a declared migration moved a door key an owner's provider binding freezes (images, graph GPU lane)
        self.binding_migrated = binding_migrated
        #: graph image bindings of the earlier doors of the checked migration chain (`state_binding`)
        self.migrated_image_bindings = migrated_image_bindings
        #: the earlier doors' graph GPU worker image ids per graph binding, and their bundle images per construction
        #: parent id (`state_binding.migrated_graph_gpu_images`, `state_binding.migrated_bundle_images`): a task built
        #: under an earlier door is graded with its admitted images (`lean_recipe_retention`)
        self.migrated_graph_gpu_images = dict(migrated_graph_gpu_images or {})
        self.migrated_bundle_images = dict(migrated_bundle_images or {})
        self.implementation, self.snapshot, self.window, self.receiver = (
            implementation,
            snapshot,
            window,
            receiver,
        )
        self._lock = threading.RLock()
        self._providers = {}
        self._controls = {}
        self._admissions = {}
        #: Owners restored while their registration was UNKNOWN (no usable snapshot): their queues were kept; the first
        #: fresh snapshot decides each (`_settle_unobserved`).
        self._unobserved = set()
        #: owner directory name (the owner's sha256) -> why `restore` set it aside (see `restore`)
        self._set_aside = {}
        #: LAZY owners (restart speed, owner 18 Nov 2026): directory name -> hotkey of each retained owner `restore` found
        #: with no work (`_has_work`), opened by the same restoring path on its first touch (`_restore_lazy`)
        self._lazy = {}
        #: directory name -> ``{task id: (state name, created unix seconds)}`` of a lazy owner, read by `restore`'s scan:
        #: every one terminal, so the readers of the open providers' views see them too (`lazy_index`)
        self._lazy_index = {}
        #: directory name -> the lock one lazy owner's first open holds (never the receiver's own lock)
        self._lazy_gates = {}
        #: hotkey -> the lock a BRAND-NEW owner's first open holds while its provider is built (`_open`): never the
        #: receiver's own lock, so no other owner's request waits on it (mcp_slow, live 116 21 Nov 02:1xZ)
        self._open_gates = {}
        #: the background warm-up of recently active lazy owners (`start_lazy_warmer`), or None
        self._warmer = None
        self._reconciler = None
        #: the grader's verdict marker directory (``<state>/auto-grade/markers``) when this door grades, else None
        self.markers_dir = None
        self._closing = False

    def gpu_runtimes(self):
        """The GPU build runtimes this receiver holds a worker for, in a stable order: what its
        grading rebuild may expand a catalog entry to (`served.expand_official`)."""
        from carbon.development_session.gpu_practice import gpu_runtime

        images = (
            [self.parent]
            if self.parents is None
            else [self.parents.for_runtime(r) for r in self.parents.runtimes()]
        )
        return tuple(
            sorted({runtime for runtime in map(gpu_runtime, images) if runtime})
        )

    def _admission(self, hotkey):
        """Recheck registration against the current finalized receiver window."""
        observed = self._observed()
        if observed is None:
            return None
        return self._record_in(observed, hotkey)

    @staticmethod
    def _record_in(observed, hotkey):
        """``hotkey``'s registration record in the ONE snapshot ``observed``, or None when it is not registered there."""
        from carbon.development_session.chain_onboarding import (
            OnboardingFailure,
            PublicAddress,
            RegisteredMiner,
        )

        try:
            return RegisteredMiner(observed, PublicAddress(hotkey)).record()
        except OnboardingFailure:
            return None

    def _observed(self):
        """The finalized snapshot a registration is checked against, or None when there is NO usable one: none held, older
        than one epoch (`battery.intake.grading_snapshot`), a durable high-water conflict, or another chain context. None
        means the registration is UNKNOWN, which is not the same as a registration the chain shows to be revoked or recycled.

        Over-broad audit #10 (V2: NARROW to one epoch): this re-check is for work ALREADY admitted (a request reached it
        through the intake's 60 s authentication), so a chain blip past 60 s no longer refuses it; the window's durable
        high-water means the last good snapshot is never older than an observation already made, and a deregistration
        is caught at the next fresh snapshot, before any crown (`operator_pause.hold_crowns_until_fresh`).
        """
        from carbon.battery.intake import grading_snapshot

        observed = (
            grading_snapshot(self.window) if self.window is not None else self.snapshot
        )
        if (
            observed is None
            or self.snapshot is None
            or observed.context != self.snapshot.context
        ):
            return None
        return observed

    @staticmethod
    def _same_registration(frozen, current):
        return current is not None and all(
            frozen.get(field) == current[field]
            for field in (
                "admission",
                "network",
                "netuid",
                "hotkey",
                "uid",
                "registered_at_block",
            )
        )

    def _manifest(self, hotkey, ledger, *, restoring, host=False):
        """Freeze the signed owner's one DEVELOPMENT receiver campaign.

        Registration is observed, not asserted by an operator or a recipe. A
        restart keeps the first observation while checking the same registered
        identity is still present in the current finalized snapshot. The host-owned
        owner of the crown average's derived rebuilds (``host``) has no registration
        to observe: its campaign records the closed HOST_REBUILD admission (the Challenge it serves, no hotkey)
        and is always live.
        """
        from carbon.battery.challenge import CHALLENGE as BATTERY_CHALLENGE
        from carbon.challenge_kit import physical_material
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.product_campaign import AUTHORITY
        from carbon.development_session.research_ledger import (
            HOST_REBUILD_ADMISSION,
            PRODUCT,
        )

        if (
            self.implementation is None
            or self.snapshot is None
            or self.receiver is None
        ):
            raise ValueError("direct receiver authority binding required")
        challenge = self.discovery.info.challenge_key
        admission = (
            {
                "admission": HOST_REBUILD_ADMISSION,
                "challenge_id": challenge.challenge_id,
            }
            if host
            else self._admission(hotkey)
        )
        # Battery 1.0 and the step-2 2.0 share the scope and objective labels.
        battery_selected = challenge.challenge_id == BATTERY_CHALLENGE.challenge_id
        physical_selected = physical_material.is_registered(
            challenge.challenge_id, challenge.version
        )
        binding = {
            "schema": "carbon.construction.direct-receiver-run.v1",
            "implementation": self.implementation,
            "parent_image": self.parent.image_id,
            "receiver": self.receiver,
            "challenge": {"id": challenge.challenge_id, "version": challenge.version},
            "owner": hotkey,
        }
        if self.inference_image != self.parent:
            binding["inference_image"] = self.inference_image.image_id
        if self.parents is not None:
            binding["construction_parents"] = {
                runtime: self.parents.for_runtime(runtime).image_id
                for runtime in self.parents.runtimes()
            }
        if self.material_cache_bytes is not None:
            binding["material_cache_bytes"] = self.material_cache_bytes
        if self.evaluation_pack_digest is not None:
            binding["evaluation_pack_digest"] = self.evaluation_pack_digest
        candidate = {
            "schema": PRODUCT,
            "authority": AUTHORITY,
            "scope": (
                "DEVELOPMENT_PUBLIC_BATTERY_ONLY"
                if battery_selected
                else (
                    "DEVELOPMENT_PUBLIC_PHYSICAL_ONLY"
                    if physical_selected
                    else "DEVELOPMENT_PUBLIC_SYNTHETIC_ONLY"
                )
            ),
            "campaign_id": "direct-" + hashlib.sha256(canonical(binding)).hexdigest(),
            "principal": hotkey,
            "owner": hotkey,
            "implementation": self.implementation,
            "runtime": {
                "implementation": self.implementation,
                "images": [
                    self.parent.image_id,
                    *(
                        [self.inference_image.image_id]
                        if self.inference_image != self.parent
                        else []
                    ),
                    *(
                        []
                        if self.parents is None
                        else [
                            self.parents.for_runtime(runtime).image_id
                            for runtime in self.parents.runtimes()
                            if self.parents.for_runtime(runtime)
                            not in (self.parent, self.inference_image)
                        ]
                    ),
                ],
            },
            "admission": admission,
            "agent": "none",
            "challenge": binding["challenge"],
            "receiver_binding": binding,
            "objective": (
                "Battery public direct construction and practice inference"
                if battery_selected
                else (
                    "physical public direct construction and development-bank inference"
                    if physical_selected
                    else "synthetic direct construction and public practice inference"
                )
            ),
            "sampling": "Challenge-owned frozen TRAIN and public practice inputs",
            "control": "authenticated owner direct task supervisor",
            "selection": "owner-submitted ConstructionRecipe",
            "replica_policy": "one independent construction per task",
            "provider": "no model provider selected by receiver",
        }
        with ledger.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        if row is not None:
            frozen = json.loads(row[0])
            candidate["admission"] = frozen.get("admission")
            if set(frozen) != set(candidate) or any(
                frozen.get(field) != candidate[field] for field in candidate
            ):
                if not (
                    restoring
                    and _migrate_owner_manifest(
                        ledger,
                        hotkey,
                        row[0],
                        frozen,
                        candidate,
                        images_migrated=self.images_migrated,
                        markers_dir=self.markers_dir,
                        host=host,
                    )
                ):
                    raise ValueError("retained direct owner campaign binding changed")
            else:
                candidate = frozen
        elif restoring:
            raise ValueError("retained direct owner campaign manifest missing")
        elif admission is None and not host:
            raise Unavailable("direct_provider_registration_unavailable")
        ledger.freeze(candidate)
        if host:
            return candidate["admission"], True
        return candidate["admission"], self._same_registration(
            candidate["admission"], admission
        )

    def _build(self, hotkey, *, restoring, host):
        """A not-yet-open owner's provider, its campaign control and its frozen admission (`_open`): the ledger, the
        campaign manifest (migrated only when ``restoring``), the task store and the control's acquisition. Touches
        only this owner's files; `_open` holds the receiver's lock around it, `_restore_lazy` only the owner's gate.
        Returns ``(provider, control, frozen_admission, live)``."""
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.research_control import CampaignControl
        from carbon.development_session.research_ledger import CampaignLedger
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
        from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

        directory = _private_directory(
            self.root / hashlib.sha256(hotkey.encode()).hexdigest()
        )
        ledger = CampaignLedger(directory / "ledger")
        frozen_admission, live = self._manifest(
            hotkey, ledger, restoring=restoring, host=host
        )
        if not restoring and not live:
            raise Unavailable("direct_provider_registration_unavailable")
        write_once(directory / "owner.json", canonical({"hotkey": hotkey}))
        provider = DirectDevelopmentTasksV3(
            root=directory / "tasks",
            requester=hotkey,
            owner=hotkey,
            ledger=ledger,
            discovery=self.discovery,
            image=None,
            inference_image=self.inference_image,
            **(
                {"construction_parent": self.parent}
                if self.parents is None
                else {"construction_parents": self.parents}
            ),
            evaluation_pack_digest=self.evaluation_pack_digest,
            binding_migrated=getattr(self, "binding_migrated", False),
            migrated_image_bindings=getattr(
                self, "migrated_image_bindings", frozenset()
            ),
            migrated_graph_gpu_images=getattr(self, "migrated_graph_gpu_images", {}),
            migrated_bundle_images=getattr(self, "migrated_bundle_images", {}),
            **(
                {}
                if self.graph_gpu_image is None
                else {
                    "graph_gpu_image": self.graph_gpu_image,
                    "graph_gpu_ops": self.graph_gpu_ops,
                }
            ),
            image_resolver=DirectOwnerImageResolver(
                self.cache_root,
                **(
                    {"parent": self.parent}
                    if self.parents is None
                    else {"parents": self.parents}
                ),
                **(
                    {"material_cache_bytes": self.material_cache_bytes}
                    if self.material_cache_bytes is not None
                    else {}
                ),
            ),
        )
        try:
            control = CampaignControl(ledger)
            ledger.generation = control.acquire()
        except BaseException:
            provider.close()
            raise
        return provider, control, frozen_admission, live

    def _open(self, hotkey, *, restoring, host=False):
        from carbon.challenge_validator import crown_common
        from carbon.challenge_validator.interface import Unavailable

        if host:
            # ONLY the host owner of the crown average's derived rebuilds, by exact equality: a miner's owner
            # is always a verified ss58 address (below), which this string is not.
            if hotkey != crown_common.HOST_OWNER:
                raise Unavailable("direct_provider_owner_invalid")
        elif type(hotkey) is not str or not ADDRESS.fullmatch(hotkey):
            raise Unavailable("direct_provider_owner_invalid")
        if not restoring and not host:
            # a lazy owner (`restore`) is reopened first, exactly as `restore` would have, under its own gate only
            self._restore_lazy(hotkey)
            # a brand-new owner is built under its own gate, outside the receiver's lock (`_open_new`)
            self._open_new(hotkey)
        with self._lock:
            if self._closing:
                raise Unavailable("direct_receiver_stopping")
            if hashlib.sha256(hotkey.encode()).hexdigest() in self._set_aside:
                # set aside at this start (`restore`): refused until a later start reopens it
                raise Unavailable("direct_provider_owner_set_aside")
            if not restoring:
                self._settle_unobserved()
            if hotkey not in self._providers:
                if not restoring and not host and self._admission(hotkey) is None:
                    raise Unavailable("direct_provider_registration_unavailable")
                provider, control, frozen_admission, live = self._build(
                    hotkey, restoring=restoring, host=host
                )
                self._register(
                    hotkey,
                    provider,
                    control,
                    frozen_admission,
                    live,
                    restoring=restoring,
                )
            if (
                not restoring
                and not host
                and not self._same_registration(
                    self._admissions[hotkey], self._admission(hotkey)
                )
            ):
                raise Unavailable("direct_provider_registration_unavailable")
            return self._providers[hotkey]

    def _open_new(self, hotkey):
        """Build a BRAND-NEW miner owner's provider (its first submit or status call; never `restore`'s) holding only
        that owner's gate, then register it under the receiver's lock, so every other owner's request goes on meanwhile
        (mcp_slow, live 116 21 Nov 2026: `_open` built it under the receiver's lock, and every request of every owner
        waited the build). The same checks as `_open`, in the same order: closing, set aside, registration (under the
        lock, before and after the build); nothing for an owner already open, lazy or set aside (the caller's `_open`
        then answers as before). A failed build raises to the caller exactly as `_open`'s did; nothing is registered.
        """
        from carbon.challenge_validator.interface import Unavailable

        name = hashlib.sha256(hotkey.encode()).hexdigest()
        with self._lock:
            if (
                self._closing
                or hotkey in self._providers
                or name in self._set_aside
                or name in self._lazy
            ):
                return
            self._settle_unobserved()
            if self._admission(hotkey) is None:
                return  # `_open` refuses it under the lock, as before
            gate = self.__dict__.setdefault("_open_gates", {}).setdefault(
                hotkey, threading.Lock()
            )
        with gate:
            with self._lock:
                if hotkey in self._providers or self._closing:
                    return  # opened by the touch that held the gate first (or stopping: `_open` answers)
            provider, control, frozen_admission, live = self._build(
                hotkey, restoring=False, host=False
            )
            with self._lock:
                if self._closing:
                    provider.close()
                    raise Unavailable("direct_receiver_stopping")
                if hotkey not in self._providers:
                    self._register(
                        hotkey,
                        provider,
                        control,
                        frozen_admission,
                        live,
                        restoring=False,
                    )
                else:
                    provider.close()

    #: The background warm-up (`start_lazy_warmer`): a lazy owner whose newest task was created within this many seconds
    #: is opened after listening, newest first, at most `WARM_MAX` of them, one at a time, `WARM_PAUSE_SECONDS` apart.
    #: Live 116, 21 Nov 05:10-05:30Z (live-ops 05:49Z): at a 2 s pause the 200 restores ran ~20 min nearly back to back
    #: and every /mcp call slowed meanwhile (p90 13.6 s vs ~5.8 s after); 10 s halves the restores' share of the door's
    #: one Python process for ~60 min instead (an operational value, not science).
    WARM_RECENT_SECONDS = 24 * 3600
    WARM_MAX = 200
    WARM_PAUSE_SECONDS = 10.0
    #: The storage reconcile (`start_storage_reconcile`): one full pass over the open owners' ledgers every
    #: RECONCILE_SECONDS, RECONCILE_PAUSE_SECONDS between owners. Operational pacing only (no limit or grade).
    RECONCILE_SECONDS = 900.0
    RECONCILE_PAUSE_SECONDS = 0.5
    #: During a pass, a ``storage_reconcile_progress`` line at least this often (sre 16:00:31Z: a pass grows ~5 s per open
    #: owner, ~45 min at 512 owners, so a pass-end line alone would look silent on a healthy door).
    RECONCILE_PROGRESS_SECONDS = 300.0

    def lazy_warm_order(self, now=None):
        """The hotkeys of the lazy owners with recent activity (a task created within `WARM_RECENT_SECONDS`), newest
        first, at most `WARM_MAX`: read from this start's scan (`lazy_index`), never opening anything.
        """
        now = time.time() if now is None else now
        with self._lock:
            newest = []
            for name, hotkey in self._lazy.items():
                created = [
                    entry[1]
                    for entry in self._lazy_index.get(name, {}).values()
                    if type(entry) in (tuple, list)
                    and len(entry) > 1
                    and type(entry[1]) in (int, float)
                ]
                if created and now - max(created) <= self.WARM_RECENT_SECONDS:
                    newest.append((max(created), hotkey))
        newest.sort(reverse=True)
        return [hotkey for _created, hotkey in newest[: self.WARM_MAX]]

    def start_storage_reconcile(self, *, interval=None, pause=None, sleep=time.sleep):
        """The whole-tree storage walk OFF every request's path (live 116 21 Nov 2026: the per-submit walk of an owner's
        store was 4.5 s typical, 40 s worst): ONE daemon thread walks each OPEN owner's ledger in turn
        (`CampaignLedger.reconcile_storage`), a pause between owners, a full pass every `RECONCILE_SECONDS`. A symlink
        it finds records the ledger's storage fault, after which that owner's fast checks refuse every write
        (fail closed, as the walk did). One ``storage_reconcile`` journal line per pass. Stops at a stop; never raises.
        """
        interval = self.RECONCILE_SECONDS if interval is None else interval
        pause = self.RECONCILE_PAUSE_SECONDS if pause is None else pause

        def reconcile():
            while True:
                with self._lock:
                    if self._closing:
                        return
                    ledgers = [
                        getattr(provider, "ledger", None)
                        for provider in self._providers.values()
                    ]
                began, walked, faults = time.monotonic(), 0, 0
                reported = began
                for ledger in ledgers:
                    with self._lock:
                        if self._closing:
                            return
                    if ledger is None or not callable(
                        getattr(ledger, "reconcile_storage", None)
                    ):
                        continue
                    try:
                        ledger.reconcile_storage()
                        walked += 1
                    except ValueError:
                        faults += 1
                    # one ledger's fault never stops the pass
                    except Exception:  # noqa: BLE001, S110
                        pass
                    if time.monotonic() - reported >= self.RECONCILE_PROGRESS_SECONDS:
                        reported = time.monotonic()
                        print(
                            json.dumps(
                                {
                                    "event": "storage_reconcile_progress",
                                    "walked": walked,
                                    "faults": faults,
                                    "of": len(ledgers),
                                    "ms": round((reported - began) * 1000),
                                },
                                sort_keys=True,
                            ),
                            file=sys.stderr,
                            flush=True,
                        )
                    sleep(pause)
                print(
                    json.dumps(
                        {
                            "event": "storage_reconcile",
                            "walked": walked,
                            "faults": faults,
                            "ms": round((time.monotonic() - began) * 1000),
                        },
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                sleep(interval)

        thread = threading.Thread(
            target=reconcile, name="storage-reconcile", daemon=True
        )
        self._reconciler = thread
        thread.start()
        return thread

    def start_lazy_warmer(self, *, pause=None, sleep=time.sleep):
        """After listening (mcp_slow, live 116 21 Nov 2026: an active miner's first status call after a restart waited
        its owner's whole lazy restore, 11-17 s): ONE daemon thread opens the recently active lazy owners
        (`lazy_warm_order`) by the same `_restore_lazy` a request would, one at a time with a pause between, so most
        first calls find their owner open. It stops at a stop (`_closing`) and skips an owner a request already opened;
        a failure sets that owner aside exactly as a request's touch would. Owners with no recent activity stay lazy
        (start time unchanged). Never raises; returns the thread (None when there is nothing to warm).
        """
        order = self.lazy_warm_order()
        if not order:
            return None
        pause = self.WARM_PAUSE_SECONDS if pause is None else pause

        def warm():
            warmed = 0
            for hotkey in order:
                with self._lock:
                    if self._closing:
                        break
                try:
                    self._restore_lazy(hotkey)
                    warmed += 1
                except Exception:  # noqa: BLE001, S110
                    pass  # `_restore_lazy` sets a failing owner aside itself
                sleep(pause)
            print(
                json.dumps(
                    {"event": "owners_warmed", "count": warmed, "planned": len(order)},
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )

        thread = threading.Thread(target=warm, name="lazy-owner-warmer", daemon=True)
        self._warmer = thread
        thread.start()
        return thread

    def _register(
        self, hotkey, provider, control, frozen_admission, live, *, restoring
    ):
        """Hold a just-built provider (`_build`) as this receiver's: called under the receiver's lock. A restored owner
        whose registration a FRESH snapshot shows revoked keeps cleanup custody only (its queued tasks cancelled).
        """
        self._providers[hotkey] = provider
        self._controls[hotkey] = control
        self._admissions[hotkey] = frozen_admission
        observed = self._observed() if restoring and not live else None
        if restoring and not live and observed is None:
            self._unobserved.add(hotkey)
        elif (
            restoring
            and not live
            and not self._same_registration(
                frozen_admission, self._record_in(observed, hotkey)
            )
        ):
            # A revoked/recycled miner retains cleanup custody, never
            # the right to launch a queued child from old authority.
            # Only when a FRESH snapshot positively shows a different (or no) registration: with NO usable
            # snapshot the registration is unknown, not revoked (the start snapshot ages past 60 s during start-up,
            # before the intake's refresher runs: 14 Nov, 112 live queued tasks of 80 owners cancelled), so the queue
            # stays QUEUED, the owner cannot launch from old authority (the registration re-check below refuses while
            # there is no snapshot) and the first fresh snapshot decides.
            for task_id in provider.queued_tasks():
                provider.cancel_observed_task(
                    task_id, self.discovery.info.challenge_key
                )

    def _settle_unobserved(self):
        """The FIRST fresh snapshot decides every owner restored while its registration was unknown: the same registration
        keeps its (kept) queue, now allowed to build; a different or absent one cancels its queued tasks exactly as a restore
        against a fresh snapshot does (`cancel_observed_task`) and never builds them. Runs at every provider request after
        restore (the intake's and the advance loop's), under the lock; nothing happens until a fresh snapshot exists. A
        cancellation that fails leaves the owner to be decided again on the next call (it cannot launch meanwhile: the
        registration re-check in `_open` refuses it)."""
        if not self._unobserved:
            return
        observed = self._observed()  # ONE read decides this whole sweep
        if observed is None:
            return
        for hotkey in sorted(self._unobserved):
            provider = self._providers.get(hotkey)
            if provider is None:
                self._unobserved.discard(hotkey)
                continue
            if self._same_registration(
                self._admissions[hotkey], self._record_in(observed, hotkey)
            ):
                self._unobserved.discard(hotkey)
                continue
            try:
                for task_id in provider.queued_tasks():
                    provider.cancel_observed_task(
                        task_id, self.discovery.info.challenge_key
                    )
            except Exception:  # noqa: BLE001, S112 - decided again on the next call
                continue
            self._unobserved.discard(hotkey)

    def __call__(self, hotkey):
        from carbon.challenge_validator import crown_common

        # The derived-rebuild path asks for its host owner by name; a miner's request never can (its owner is a
        # verified ss58 address, and `LeanRecipeAdapter.evaluate` refuses the host owner as a submitter).
        return self._open(
            hotkey, restoring=False, host=hotkey == crown_common.HOST_OWNER
        )

    def hotkey_of(self, task_id):
        """The hotkey whose provider (open, or lazy: `restore`'s scan) holds ``task_id``, read from this receiver's own
        keys, never opening a provider; None when none does (the grade scan's owner and allowance group).
        """
        name = task_id if type(task_id) is str else getattr(task_id, "value", None)
        if type(name) is not str:
            return None
        with self._lock:
            for hotkey, provider in self._providers.items():
                views = getattr(provider, "_views", None)
                if type(views) is dict and name in views:
                    return hotkey
            for directory, index in self._lazy_index.items():
                if name in index:
                    return self._lazy.get(directory)
        return None

    def lazy_tasks(self):
        """The task ids every lazy owner holds (all terminal): what the advance pass skips before any owner check, as it
        skips an open provider's non-QUEUED tasks (`LeanRecipeAdapter._advance_skip`).
        """
        with self._lock:
            return frozenset(
                task for index in self._lazy_index.values() for task in index
            )

    def lazy_tasks_of(self, hotkeys):
        """The task ids the LAZY owners among ``hotkeys`` hold (all terminal): `lazy_tasks` for one allowance group's
        hotkeys only, so an admission never gathers every lazy owner's tasks (LOCK + CACHE AUDIT #2b). Memory only.
        """
        wanted = frozenset(hotkeys)
        with self._lock:
            return frozenset(
                task
                for directory, index in self._lazy_index.items()
                if self._lazy.get(directory) in wanted
                for task in index
            )

    def lazy_index(self):
        """``{task id: (state name, created unix seconds)}`` over every lazy owner, read by `restore`'s scan (the public
        queue's index of the providers not open yet, `QueueView._index`)."""
        with self._lock:
            return {
                task: entry
                for index in self._lazy_index.values()
                for task, entry in index.items()
            }

    def _has_work(self, directory):
        """Whether ``directory``'s owner may hold work, from a READ-ONLY look at its two stores, or None when it cannot
        be read (then the owner is opened at start, as before: doubt never makes an owner lazy). Work (V2, 18 Nov 2026):
        a task not terminal (QUEUED, RUNNING, CANCEL_REQUESTED), a SUCCEEDED task with no grade marker yet on a door
        that grades, or an operation of its ledger with no finish row (RESERVED included). Returns ``(work, index)``,
        ``index`` = ``{task id: (state name, created unix seconds)}``.
        """
        import sqlite3

        from carbon.research import DirectTaskStateV3, DirectTaskViewV3, load_canonical

        waiting = (
            DirectTaskStateV3.QUEUED,
            DirectTaskStateV3.RUNNING,
            DirectTaskStateV3.CANCEL_REQUESTED,
        )
        tasks_path = directory / "tasks" / "direct-tasks.sqlite3"
        ledger_path = directory / "ledger" / "campaign.sqlite3"
        if not tasks_path.is_file() or not ledger_path.is_file():
            return None
        index = {}
        try:
            db = sqlite3.connect(f"file:{tasks_path}?mode=ro", uri=True, timeout=5)
            try:
                rows = db.execute("SELECT id, view FROM direct_tasks").fetchall()
            finally:
                db.close()
            for identity, raw in rows:
                view = load_canonical(raw, DirectTaskViewV3)
                if view.task_id.value != identity:
                    return None
                if view.state in waiting:
                    return True, {}
                if (
                    view.state is DirectTaskStateV3.SUCCEEDED
                    and self.markers_dir is not None
                    and not (self.markers_dir / f"{identity}.json").exists()
                ):
                    return True, {}
                index[identity] = (view.state.value, view.created_at_micros / 1e6)
            db = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True, timeout=5)
            try:
                open_ops = db.execute(
                    "SELECT COUNT(*) FROM operations o LEFT JOIN operation_finished f ON f.id = o.id "
                    "WHERE f.id IS NULL"
                ).fetchone()[0]
            finally:
                db.close()
        except Exception:  # noqa: BLE001 - unreadable: opened at start, as before
            return None
        return bool(open_ops), index

    def _frozen_revision(self, directory):
        """The revision ``directory``'s campaign manifest is frozen at (read-only), or None when it cannot be read."""
        import sqlite3

        path = directory / "ledger" / "campaign.sqlite3"
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            try:
                row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
            finally:
                db.close()
            return json.loads(row[0])["implementation"]["revision"]
        except Exception:  # noqa: BLE001 - unreadable: the migration below decides
            return None

    def _migrate_lazy_manifest(self, hotkey, directory):
        """At start, a LAZY owner's campaign manifest frozen at another revision than this start's is migrated now by
        the restoring path's own check (`_manifest`, restoring: `_migrate_owner_manifest` under this start's declared
        change); one frozen at this revision is left untouched (no write). A refusal raises, as an eager restore's
        does: `restore` sets the owner aside."""
        from carbon.development_session.research_ledger import CampaignLedger

        current = (
            self.implementation.get("revision")
            if type(self.implementation) is dict
            else None
        )
        if current is not None and self._frozen_revision(directory) == current:
            return
        self._manifest(hotkey, CampaignLedger(directory / "ledger"), restoring=True)

    def _restore_lazy(self, hotkey):
        """Open a lazy owner (`restore`) on its first touch by the SAME restoring path `restore` takes (its campaign
        manifest migrated under this start's declared migration, its interrupted work reconciled), holding only that
        owner's gate: any other owner's request goes on meanwhile. A failure sets it aside exactly as `restore` does
        (``owner_restore_set_aside``; its requests refused ``direct_provider_owner_set_aside``; `set_aside` names it),
        never an error of the request that touched it. Nothing for an owner that is not lazy.
        """
        name = hashlib.sha256(hotkey.encode()).hexdigest()
        with self._lock:
            if self._lazy.get(name) != hotkey:
                return
            gate = self._lazy_gates.setdefault(name, threading.Lock())
        with gate:
            with self._lock:
                if self._lazy.get(name) != hotkey:
                    return  # opened (or set aside) by the touch that held the gate first
            began = time.monotonic()
            try:
                built = self._build(hotkey, restoring=True, host=False)
            except Exception as failure:  # noqa: BLE001 - sets the owner aside
                with self._lock:
                    self._lazy.pop(name, None)
                    self._lazy_index.pop(name, None)
                    self._set_aside[name] = (
                        getattr(failure, "code", None) or type(failure).__name__
                    )
                _log_start_failure(
                    "owner_restore_set_aside", failure, owner_sha256=name, lazy=True
                )
                return
            provider, control, frozen_admission, live = built
            with self._lock:
                if self._closing:
                    provider.close()
                    return
                self._lazy.pop(name, None)
                self._lazy_index.pop(name, None)
                self._register(
                    hotkey, provider, control, frozen_admission, live, restoring=True
                )
            print(
                json.dumps(
                    {
                        "event": "owner_lazy_restored",
                        "owner_sha256": name,
                        "s": round(time.monotonic() - began, 2),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )

    def restore(self):
        """Reopen every retained owner that may hold work before listening, including interrupted work.

        Restart speed (owner, 18 Nov 2026: a restart reopened all 388 owners one by one, ~10 min before listening, while
        2 had a live task and 10 an unfinished operation): an owner whose stores show NO work (`_has_work`: every task
        terminal, every SUCCEEDED one graded, no unfinished operation) is LAZY, not opened here; its first touch opens it
        by this same restoring path (`_restore_lazy`), and its tasks are read meanwhile from this start's scan
        (`lazy_tasks`, `lazy_index`). Doubt (a store that cannot be read) opens it here. The crown average's host owner is
        always opened here, and the crown's owners before listening (`_open_crown_owners`).

        An owner this start cannot reopen (its campaign manifest cannot be migrated to this revision, its directory or
        owner binding is unreadable, ...) is SET ASIDE, not the whole door (Lead R2, owner G4, 18 Nov 2026: an in-place
        restart runs this migration on live state, and switch 3's start refused 343 owners for one). It is not opened
        and nothing of it is cancelled; every request of it is refused ``direct_provider_owner_set_aside`` (fail closed,
        a grade of it given back as Carbon's), and the journal names it (``owner_restore_set_aside``: its sha256 and
        why). Its files are as the failure left them: a failure AFTER its campaign manifest was migrated
        (`_migrate_owner_manifest` commits the row first) leaves that row on the new revision, which a rollback's row
        revert covers. While any owner the crown steps need is set aside, those steps hold (`AutoGrader._crown_held`,
        V2 18 Nov). The start still refuses, as before, when the owner is the crown average's host owner (its derived
        rebuilds decide the crown), when its provider was already opened (it holds work), or when NO owner opened.
        """
        import time

        from carbon.challenge_validator import crown_common

        first = None
        began = time.monotonic()
        #: this start's wall time: an op RESERVED before it is a previous receiver process's (`settle_previous_runs`)
        start_wall = time.time()
        took = []
        for directory in sorted(self.root.iterdir()):
            name = directory.name
            started = time.monotonic()
            try:
                _private_directory(directory)
                owner = private_json(directory / "owner.json")
                if (
                    type(owner) is not dict
                    or set(owner) != {"hotkey"}
                    or type(owner["hotkey"]) is not str
                    or hashlib.sha256(owner["hotkey"].encode()).hexdigest() != name
                ):
                    raise ValueError("retained receiver owner binding differs")
                host = owner["hotkey"] == crown_common.HOST_OWNER
                found = None if host else self._has_work(directory)
                if found is not None and not found[0]:
                    # no work (restart speed, owner 18 Nov 2026): opened on its first touch (`_restore_lazy`); its
                    # manifest still moves to this start's revision NOW, so no lazy owner is ever more than this start's
                    # declared hop behind (live 116, 18 Nov 2026)
                    self._migrate_lazy_manifest(owner["hotkey"], directory)
                    with self._lock:
                        self._lazy[name] = owner["hotkey"]
                        self._lazy_index[name] = found[1]
                    continue
                provider = self._open(owner["hotkey"], restoring=True, host=host)
                # its ops a previous receiver process left RESERVED: container stopped, settled FAILED_INFRA (V2)
                from carbon.development_session.research_carrier import (
                    settle_previous_runs,
                )

                ledger = getattr(provider, "ledger", None)
                if ledger is not None:
                    settle_previous_runs(
                        ledger, owner=owner["hotkey"], before=start_wall
                    )
            except Exception as failure:
                opened = any(
                    hashlib.sha256(hotkey.encode()).hexdigest() == name
                    for hotkey in self._providers
                )
                host = name == _owner_name(crown_common.HOST_OWNER)
                if opened or host:
                    # its provider holds work (never left half-open behind a set-aside), or it is the crown average's
                    # host owner (V2 18 Nov: the crown is never decided without it)
                    _log_start_failure(
                        "owner_restore_failed", failure, owner_sha256=name
                    )
                    raise
                code = getattr(failure, "code", None) or type(failure).__name__
                with self._lock:
                    self._set_aside[name] = code
                _log_start_failure(
                    "owner_restore_set_aside", failure, owner_sha256=name
                )
                first = failure if first is None else first
            finally:
                took.append((time.monotonic() - started, name))
        _log_restore_timing(time.monotonic() - began, took, lazy=len(self._lazy))
        if first is not None and not self._providers and not self._lazy:
            # no owner could be reopened: a whole-door failure, never one owner's
            raise first

    def log_open_counts(self):
        """One stderr line before listening: how many owners are open and how many are lazy (`restore`)."""
        with self._lock:
            record = {
                "event": "owners_open_at_listening",
                "open": len(self._providers),
                "lazy": len(self._lazy),
                "set_aside": len(self._set_aside),
            }
        print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)

    def set_aside(self):
        """``{owner sha256: code}`` of the owners this start set aside (`restore`)."""
        with self._lock:
            return dict(self._set_aside)

    def cancel(self):
        """Close admission and request our providers' domain cancellation of every task that holds work.

        A task still QUEUED holds nothing (no container, no reserved operation): it is LEFT QUEUED, durable in its
        owner's task store, and the next start restores it for a live owner and builds it (`restore`, then the advance
        loop), so a restart or a door switch carries the queue instead of cancelling every miner's not-yet-built
        submission (13 Nov: two stops cancelled 75 and left every identical resubmission waiting behind them). A task
        RUNNING or already CANCEL_REQUESTED is still cancelled: it holds a worker that must be reconciled. A revoked or
        recycled owner's queue is still cancelled, at the restore (`_open`: ``restoring and not live``).

        EXCEPT a RUNNING task whose remote GPU build program runs on (owner, 20 Nov 2026: a restart must never cancel an
        in-flight build; live 116 01:52Z, ~22 cancelled and re-run from zero): first the stop is announced
        (`research_carrier.door_stopping`: nothing new starts, this process's own stream clients of those programs end),
        then such a task (`detached_build`) is left RUNNING with its program running on its box, and the next start
        adopts it (`register_adoptable`) or, when it cannot, settles it as before. Each is still listed in the stop's
        record (`_record_stop_cancelled`), so one the next start cannot adopt is re-run at its place as before.
        """
        from carbon.development_session.research_carrier import door_stopping
        from carbon.research import DirectTaskStateV3

        with self._lock:
            self._closing = True
            providers = tuple(self._providers.values())
        door_stopping()
        errors = []
        stopped = []
        for provider in providers:
            with provider._lock:
                views = tuple(provider._views.values())
            for view in views:
                if view.state is DirectTaskStateV3.QUEUED:
                    continue
                building = view.state in (
                    DirectTaskStateV3.RUNNING,
                    DirectTaskStateV3.CANCEL_REQUESTED,
                )
                if view.state is DirectTaskStateV3.RUNNING and _left_detached(
                    provider, view.task_id
                ):
                    # left by an earlier cancel of this stop (`serve` cancels, then its last step again): listed once
                    continue
                left = getattr(provider, "detached_build", None)
                if (
                    view.state is DirectTaskStateV3.RUNNING
                    and callable(left)
                    and left(view.task_id)
                ):
                    # its build's program runs on: left for the next start, never cancelled
                    stopped.append(getattr(view.task_id, "value", view.task_id))
                    continue
                try:
                    provider.cancel_observed_task(
                        view.task_id, self.discovery.info.challenge_key
                    )
                except Exception as failure:  # noqa: BLE001 - cancel all owned tasks
                    errors.append(type(failure).__name__)
                    continue
                if building:
                    stopped.append(getattr(view.task_id, "value", view.task_id))
        _record_stop_cancelled(self.root.parent, stopped)
        if errors:
            raise ReceiverUnavailable("direct_receiver_cancellation_unresolved")

    def close(self):
        """Release no provider lock while its children need reconciliation."""
        providers = tuple(self._providers.values())
        # a task this stop left for the next start (`cancel`: its build's program runs on) holds its op on purpose
        if any(
            provider.requires_reconciliation(view.task_id)
            and not _left_detached(provider, view.task_id)
            for provider in providers
            for view in tuple(provider._views.values())
        ):
            raise ReceiverUnavailable("direct_receiver_cleanup_unresolved")
        for hotkey, provider in tuple(self._providers.items()):
            if hotkey in self._controls:
                state = self._controls[hotkey].settled(
                    provider.ledger.generation, cleanup_verified=True, ready=True
                )
                if state == "RECONCILIATION_REQUIRED" and not any(
                    _left_detached(provider, view.task_id)
                    for view in tuple(provider._views.values())
                ):
                    raise ReceiverUnavailable("direct_receiver_cleanup_unresolved")
            provider.close()


def _open_crown_owners(grader):
    """Before listening, open the owners the incumbent's steps take (`AutoGrader._prelude_owners`: the king's, the
    crown host's, each paused crown's and each due retry's): resolving each one opens it (`LeanRecipeAdapter.owner`), so
    a crown owner is never lazy (V2 / Lead, 18 Nov 2026). An owner that cannot be resolved is opened on its first touch,
    as any lazy owner; never a reason not to start."""
    try:
        grader._prelude_owners()
    except Exception:  # noqa: BLE001, S110 - opens on first touch
        pass


def _left_detached(provider, task_id):
    """Whether this stop left ``task_id`` for the next start (`OwnerProviders.cancel`, the provider's `detached`)."""
    detached = getattr(provider, "detached", None)
    return callable(detached) and bool(detached(task_id))


def _announce_stop():
    """The receiver's stop signal: announced to the carrier at once (`research_carrier.announce_stop`), so a remote
    GPU build whose stream the stop cuts is left for the next start, never cleaned up as a failure. Never raises.
    """
    try:
        from carbon.development_session.research_carrier import announce_stop

        announce_stop()
    except Exception:  # noqa: BLE001, S110 - a stop never fails on its announcement
        pass


def _record_stop_cancelled(state_root, tasks):
    """The builds THIS stop cancelled, one line each (`lean_recipe.STOP_CANCELLED`): the next start re-runs each once
    as Carbon's, uncharged, at its original place (CARBON-CUT REQUEUE, V2 18 Nov 2026). Only the receiver writes it,
    so a miner's own cancel is never re-run. Never raises: a stop never fails on its record.
    """
    if not tasks:
        return
    try:
        from carbon.challenge_validator.lean_recipe import STOP_CANCELLED

        directory = Path(state_root) / "auto-grade" / "requeued"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        at = time.time_ns()
        with open(directory / STOP_CANCELLED, "a", encoding="utf-8") as log:
            for task in tasks:
                line = json.dumps({"task": task, "at_ns": at}, sort_keys=True)
                log.write(line + "\n")
    except Exception:  # noqa: BLE001, S110 - a stop never fails on its record
        pass


def _stop_providers(providers, *, cancel):
    """serve's last step: cancel (unless retaining) then close the owner providers.

    Switch 3, 18 Nov 2026: a start that failed with restored work still held made close() refuse, and its
    `direct_receiver_cleanup_unresolved` REPLACED the failure that stopped the start (the journal said only that). When
    a failure is already on its way out, it stays the one raised and the close's refusal is logged beside it; with
    none, close() refuses exactly as before.
    """
    first = sys.exc_info()[1]
    try:
        if cancel:
            providers.cancel()
    finally:
        try:
            providers.close()
        except Exception as late:
            if first is None:
                raise
            _log_start_failure("receiver_close_refused", late, first=first)
        finally:
            # nothing of this process may outlive it: a docker client child left now would hold the unit's stop for its
            # 90 s timeout (live 116, 20 Nov 2026)
            from carbon.development_session import research_carrier

            research_carrier.release_own_docker_clients()


def _owner_name(hotkey):
    """An owner's directory name under the receiver's owners/ (the hotkey's sha256)."""
    return hashlib.sha256(hotkey.encode()).hexdigest()


def _log_restore_timing(total, took, lazy=0):
    """One stderr line (the unit's journal, operator-only): how long the owner restore took, how many owners, and the
    five slowest by sha256 (Lead, 18 Nov 2026: a restart's ~10 min restore, to aim its next speed-up at real data).
    """
    slowest = sorted(took, reverse=True)[:5]
    record = {
        "event": "owner_restore_timing",
        "owners": len(took),
        # of them: opened now (``owners - lazy``) and left LAZY, opened on their first touch (`_restore_lazy`)
        "lazy": lazy,
        "total_s": round(total, 1),
        "slowest": [{"owner_sha256": name, "s": round(s, 2)} for s, name in slowest],
    }
    print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)


def _raised_at(failure):
    """``path:line in function`` of the innermost frame that raised ``failure`` (a code location only), or None."""
    import traceback

    frames = traceback.extract_tb(failure.__traceback__)
    if not frames:
        return None
    last = frames[-1]
    path = last.filename.replace("\\", "/")
    marker = "/carbon/"
    path = "carbon/" + path.split(marker, 1)[1] if marker in path else Path(path).name
    return f"{path}:{last.lineno} in {last.name}"


def _log_start_failure(event, failure, **fields):
    """One stderr line (the unit's journal, operator-only) naming a start failure by its code or type."""
    if "first" in fields:
        first = fields.pop("first")
        fields["first"] = getattr(first, "code", None) or type(first).__name__
    record = {
        "event": event,
        "code": getattr(failure, "code", None) or type(failure).__name__,
        # Carbon's own refusals carry fixed text (`retained direct owner campaign binding changed`); bounded.
        "reason": str(failure)[:200],
        **fields,
    }
    print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)


def _require_speed_match(challenge_id, version):
    """Refuse to serve a vmap-64 version whose speed-match tolerance is unset or malformed (`speed_match`)."""
    from carbon.challenge_validator import speed_match

    try:
        speed_match.require_served(challenge_id, version)
    except speed_match.SpeedMatchUnregistered as gap:
        raise ReceiverUnavailable(gap.code) from gap


def serve(
    config_path: Path,
    *,
    stop=None,
    reader=None,
    verifier=None,
    ready=None,
    retention=None,
    regrade=False,
    pool_store=None,
    exam_se=False,
    grade_set=False,
    rebind=None,
    permits=None,
):
    """Run the same signed intake/task loop with finite admission and owned stop.

    ``permits`` replaces the chain's validator-permit read (tests only)."""
    from carbon.challenge_validator import cpu_pin

    cpu_pin.require()  # fail closed: never score on unpinned CPU kernels
    from carbon.battery import challenge as battery_challenge
    from carbon.battery.construction_bundle_material import (
        versioned_material as battery_versioned_material,
    )
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.chain.sdk import PersistentBittensorReader
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    # Loading this module reads the installed-commit record (the code every grade of this run is recorded against): it is
    # read HERE, at the receiver's start, never at the first grade (which imports it lazily).
    from carbon.challenge_validator import lean_recipe_retention
    from carbon.challenge_validator.direct_intake import (
        DirectRecipeIntake,
        serve_loopback,
    )
    from carbon.challenge_validator.ledger import AttemptLedger
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.transport.store import ReceiptJournal
    from scripts.dev.miner_launchpad.controller import owner_lock

    cfg = load_config(config_path)
    require_chain_network(cfg)
    install_official_receipt_store(cfg)
    from carbon.challenge_validator import crown_average_host

    crown_average_host.install(cfg)
    install_declared_change(cfg)
    install_king_retained_parents(cfg)
    install_graded_inference_image(cfg)
    # a verified inference snapshot's predictions.json is held compressed on the door (DATA, sre 21 Nov 2026: 90.6% of
    # the owner-ledger growth); every reader gets its RAW bytes, checked (`data.read_raw`)
    from carbon.development_session.bundle_construction_worker import (
        compress_snapshot_predictions,
    )

    compress_snapshot_predictions(True)
    selected_parent = (
        {"construction_image_manifest": Path(cfg["construction_image_manifest"])}
        if "construction_image_manifest" in cfg
        else {}
    )
    running = {}
    implementation, parent, network, cache = installed_source(
        Path(cfg["runner_profile"]), running=running, **selected_parent
    )
    # Every official grade records the commit it ran on (`grade-installed-commit.json`, read when the grading module
    # loaded). The checkout that was just accepted must be that same commit, or the records would name the wrong code.
    if (
        "head" in running
        and lean_recipe_retention._installed_commit().get("commit") != running["head"]
    ):
        raise ReceiverUnavailable("receiver_running_head_moved")
    from carbon.development_session.gpu_practice import (
        direct_bundle_accelerators,
        direct_parent_backend,
        gpu_image_backend,
    )
    from carbon.development_session.research_campaign import (
        verify_current_worker,
        verify_direct_v13_worker,
    )
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
    from scripts.dev.miner_launchpad.runner import validated_profile

    runner = validated_profile(private_json(Path(cfg["runner_profile"])))
    selected_inference = cfg.get("inference_image_manifest")
    inference_image = load_image_identity(
        Path(
            runner["paths"]["image_manifest"]
            if selected_inference is None
            else selected_inference
        )
    )
    backend = gpu_image_backend(inference_image)
    if selected_inference is None or backend is None:
        torch_cpu = direct_parent_backend(inference_image) == "torch_cpu"
        if (
            selected_inference is not None
            and not torch_cpu
            and inference_image.lock_digest
            != digest((Path(__file__).resolve().parents[2] / "uv.lock").read_bytes())
        ):
            raise ValueError("private inference worker backend is unregistered")
        try:
            verify_current_worker(inference_image, implementation)
        except ValueError:
            if (
                torch_cpu
                and implementation.get("source_authority") != "DEVELOPMENT_CANDIDATE"
            ):
                raise
            verify_direct_v13_worker(
                inference_image,
                implementation,
                role="torch_cpu" if torch_cpu else "cpu",
            )
        if torch_cpu:
            verify_direct_v13_worker(inference_image, implementation, role="torch_cpu")
    else:
        if backend == "pytorch":
            raise ValueError("fixed direct inference requires JAX worker")
        elif backend == "jax":
            try:
                verify_current_worker(inference_image, implementation)
            except ValueError:
                verify_direct_v13_worker(
                    inference_image, implementation, role="jax_gpu"
                )
        else:
            raise ValueError("private inference worker backend is unregistered")
    build_accelerator, _ = direct_bundle_accelerators(parent, inference_image)
    parents = (
        construction_parents(parent, implementation)
        if "construction_runtimes" in cfg
        else None
    )
    gpu_device = None
    if "gpu_construction_images" in cfg:
        parents, gpu_device = gpu_construction_parents(
            cfg,
            implementation,
            parents,
            network.context.network,
            cfg.get("challenge", {}).get("id"),
            cfg.get("challenge", {}).get("version"),
        )
    if (
        build_accelerator is not None or gpu_device is not None
    ) and "material_cache_bytes" not in cfg:
        raise ReceiverUnavailable("gpu_overlay_cache_unconfigured")
    if not doctor(
        image_id=inference_image.image_id, image_identity=inference_image
    ).eligible:
        raise ReceiverUnavailable("installed_inference_worker_unavailable")
    # The receiver is the operator's own validator hotkey (E2): Carbon's network
    # publisher, or a hotkey holding a validator permit on the subnet now.
    stop = threading.Event() if stop is None else stop
    reader = PersistentBittensorReader() if reader is None else reader
    one_shot = retention is not None or regrade or grade_set or rebind is not None
    snapshot = await_chain_identity(
        cfg["receiver_hotkey"],
        network,
        permits,
        reader,
        stop,
        Path(cfg["root"]),
        wait=not one_shot,
    )
    root = _private_directory(Path(cfg["root"]))
    # A standalone receiver has no local miner attachment to create the
    # shared cache parent before its first authenticated material chunk.
    _private_directory(cache.parent)
    _private_directory(cache)
    selected_id = cfg.get("challenge", {}).get("id")
    material = (
        # The configured Battery version exactly (1.0, 2.0, 2.1 or 2.2).
        battery_versioned_material(cfg["challenge"]["version"])
        if selected_id == battery_challenge.CHALLENGE.challenge_id
        else (
            physical_material.bundle_material(selected_id, cfg["challenge"]["version"])
            if physical_material.is_registered(
                selected_id, cfg.get("challenge", {}).get("version")
            )
            else bundle_material_v5()
        )
    )
    challenge = material["challenge_key"]
    # A menu-D version's coded crown hold, keyed on the version this receiver ACTUALLY serves (Validator-2B 7 Nov)
    from carbon.challenge_validator import crown_hold

    crown_hold.install(challenge.challenge_id, challenge.version)
    # OFFICIAL-SCORE CROWNS (owner 14 Nov; `crown_official`): read once for the SERVED version; on, the crown average is off
    from carbon.challenge_validator import crown_official

    crown_official.install(challenge.challenge_id, challenge.version)
    # the registries' version key (noise, control, margin_N): this receiver's own version's entry first, else the Challenge's
    from carbon.challenge_validator import registry_version

    registry_version.serve(challenge.challenge_id, challenge.version)
    # a vmap-64 version (Motor 1.8) is not served until its speed-match tolerance is registered (owner, Sun 15 Nov 2026
    # ~11:1x): every other version passes unchanged
    _require_speed_match(challenge.challenge_id, challenge.version)
    with owner_lock(root):
        pack_check = None
        pack_digest = None
        pack_snapshot = None
        if "evaluation_pack" in cfg:
            pack_digest, pack_check, pack_snapshot = _sealed_pack(
                root, cfg["evaluation_pack"], challenge
            )
        # the sealed pack this receiver serves: a registered crown hold-off applies to exactly that pack (and menu epoch)
        crown_hold.bind_pack(pack_digest)
        # a subset-repeat version (Motor 1.8): no registered promise, no grading-host K_speed, or a pack whose pinned
        # producer does not bind this code (exactly or through its ONE successor row), and the door does not serve (R-5)
        from carbon.scoring import subset_repeat_evidence

        try:
            subset_repeat = lean_recipe_retention.subset_repeat_serve_check(
                challenge.challenge_id,
                challenge.version,
                pack_snapshot=pack_snapshot,
                public_root=(
                    Path(cfg["evaluation_pack"]["public_root"])
                    if pack_snapshot is not None
                    else None
                ),
                private_root=(
                    Path(cfg["evaluation_pack"]["private_root"])
                    if pack_snapshot is not None
                    else None
                ),
                copy_hotkey=cfg["receiver_hotkey"],
                # (read only for a subset version: every other door's start-up is unchanged)
                speed_key=(
                    _speed_key(cfg)
                    if subset_repeat_evidence.is_subset_version(
                        challenge.challenge_id, challenge.version
                    )
                    else None
                ),
            )
        except lean_recipe_retention.RetentionUnavailable as refused:
            raise ReceiverUnavailable(str(refused)) from refused
        if subset_repeat is not None:
            import sys

            print(
                json.dumps({"subset_repeat": subset_repeat}, sort_keys=True),
                file=sys.stderr,
                flush=True,
            )
        discovery = DirectFixtureDiscovery(
            material,
            task_admission=True,
            pack_check=pack_check,
            evaluation_pack_digest=pack_digest,
            evaluation_pack_snapshot=pack_snapshot,
            evaluation_pack_sealed=(
                pack_snapshot is not None
                and _delivered_sealed(cfg["evaluation_pack"], challenge)
            ),
            evaluation_pack_public_root=(
                Path(cfg["evaluation_pack"]["public_root"])
                if pack_snapshot is not None
                else None
            ),
            evaluation_pack_private_root=(
                Path(cfg["evaluation_pack"]["private_root"])
                if pack_snapshot is not None
                else None
            ),
        )
        (
            graph_gpu_image,
            graph_gpu_ops,
            graph_gpu_ops_digest,
            graph_gpu_device,
        ) = graph_gpu_lane(
            cfg,
            implementation,
            material.get("allowlist_bytes"),
            network.context.network,
            challenge,
        )
        immutable = {
            "schema": SCHEMA,
            "implementation": implementation,
            "parent": asdict(parent),
            "context": asdict(network.context),
            "receiver_hotkey": cfg["receiver_hotkey"],
            "challenge": {
                "id": challenge.challenge_id,
                "version": challenge.version,
            },
            "measure_query": cfg["measure_query"],
        }
        if inference_image != parent:
            immutable["inference_image"] = asdict(inference_image)
        if parents is not None:
            immutable["construction_parents"] = parents.identities()
        if gpu_device is not None:
            # a host with its own record binds it, as before; one with none binds the box pool's CLASS
            immutable["gpu_construction_device"] = (
                gpu_device.door_binding()
                if hasattr(gpu_device, "door_binding")
                else {"kind": gpu_device.device_kind, "record": gpu_device.digest}
            )
        if "material_cache_bytes" in cfg:
            immutable["material_cache_bytes"] = cfg["material_cache_bytes"]
        if pack_digest is not None:
            immutable["evaluation_pack_digest"] = pack_digest
        if graph_gpu_image is not None:
            # Said only when configured: a CPU receiver's binding is what it was.
            immutable["graph_gpu_image"] = asdict(graph_gpu_image)
            immutable["graph_gpu_ops_digest"] = graph_gpu_ops_digest
            # a box pool binds its CLASS (`remote_gpu_build.GpuClass`); a door building on this host's GPU, its record
            immutable["graph_gpu_device"] = (
                graph_gpu_device.door_binding()
                if hasattr(graph_gpu_device, "door_binding")
                else {
                    "kind": graph_gpu_device.device_kind,
                    "record": graph_gpu_device.digest,
                }
            )
        # The door part is write-once for the state's life; each release's whole binding is added beside it, so a
        # later release (or a rollback to an earlier one) starts on the same state (`state_binding`).
        from carbon.challenge_validator.state_binding import bind as bind_state
        from carbon.challenge_validator.state_binding import (
            migrated_bundle_images,
            migrated_graph_gpu_images,
            migrated_graph_image_bindings,
            migrated_images,
            migrated_keys,
        )

        # a door moved by the operator's DECLARED migration (state_binding, M1-M5) is accepted here; nothing else moves
        bind_state(root, immutable)
        window = ReceiverSnapshotWindow(root, network.context, cfg["receiver_hotkey"])
        window.add(snapshot)
        # Over-broad audit #10 (V2): grading goes on with the last good snapshot up to one epoch, but no crown in this
        # process (a serving door or a retain/regrade one-shot) is decided until the window is fresh (60 s) again: a
        # crown-changing decision files as paused and the sweep decides it once the snapshot is fresh.
        from carbon.challenge_validator import operator_pause

        operator_pause.hold_crowns_until_fresh(lambda: window.latest() is not None)
        providers = OwnerProviders(
            _private_directory(root / "owners"),
            discovery,
            parent,
            cache,
            inference_image=inference_image,
            material_cache_bytes=cfg.get("material_cache_bytes"),
            implementation=implementation,
            snapshot=snapshot,
            window=window,
            receiver=cfg["receiver_hotkey"],
            evaluation_pack_digest=pack_digest,
            parents=parents,
            graph_gpu_image=graph_gpu_image,
            graph_gpu_ops=graph_gpu_ops,
            images_migrated=migrated_images(root),
            binding_migrated=bool(migrated_keys(root)),
            migrated_image_bindings=migrated_graph_image_bindings(root),
            migrated_graph_gpu_images=migrated_graph_gpu_images(root),
            migrated_bundle_images=migrated_bundle_images(root),
        )
        if "auto_grade" in cfg:
            # a SUCCEEDED task with no grade marker is work: its owner is opened at start (`OwnerProviders._has_work`)
            providers.markers_dir = root / "auto-grade" / "markers"
        # A service (no lifetime) runs until it is stopped.
        timer = (
            None
            if cfg["lifetime_seconds"] is None
            else threading.Timer(cfg["lifetime_seconds"], stop.set)
        )
        if timer is not None:
            timer.daemon = True

        def listening(address):
            target = {
                "intake_url": f"http://{cfg['host']}:{address[1]}",
                "receiver_hotkey": cfg["receiver_hotkey"],
            }
            if not intake_url(target["intake_url"]):
                raise ValueError("invalid listening target")
            if ready is not None:
                ready(
                    {
                        "schema": SCHEMA,
                        "state": "LISTENING",
                        "direct_intake_target": target,
                        "qualification": False,
                        "reward": False,
                    }
                )

        try:
            ledger = AttemptLedger(root / "attempts.sqlite3")
            if retention is None:
                # The start snapshot ages past the window's 60 s during pack verification and the restore of every owner;
                # keep fresh snapshots flowing until the intake's own refresher takes over, so no owner is restored against
                # a snapshot that has silently expired.
                with retention_snapshots(window, network.context, reader):
                    _exam_cap_startup(ledger, discovery, providers.restore)
            intake = DirectRecipeIntake(
                context=network.context,
                receiver=cfg["receiver_hotkey"],
                journal=ReceiptJournal(root / "transport.sqlite3", network.context),
                verifier=BittensorHotkeyVerifier() if verifier is None else verifier,
                window=window,
                discovery=discovery,
                provider_for=providers,
                attempt_ledger=ledger,
                measure_query=cfg["measure_query"],
                copy_hotkey=cfg["receiver_hotkey"],
                speed_sample_key=_speed_key(cfg),
                request_buckets=_request_buckets(cfg),
                funder_map=_funder_map(cfg),
            )
            # The map file is re-read when the refresh job rewrites it (Test Lead-B 7 Nov (b)), for R89 and (a) alike.
            from carbon.challenge_validator import funder_map as funder_maps

            intake.funder_map_watch = funder_maps.Watched(
                cfg.get("funder_map_file"), intake.funder_map
            )
            # Owner decision #9: the earlier versions' closed submissions this door answers ``version_closed`` for.
            intake.version_closed = _version_closed(cfg)
            # OWNER-PROBING-COUNTERS-01 (a): the exam cap's allowance group, on the SAME in-memory funder map as R89's
            # request bucket (one group(), Validator-2 11:32); None (no block) = per hotkey as before.
            from carbon.challenge_validator import allowance_groups, exam_cap

            exam_cap.install_grouping(
                allowance_groups.from_config(cfg, window, intake._current_map)
            )
            if retention is not None:
                task_id, artifact_directory, entry_directory = retention
                # No intake feeds snapshots in this mode: refresh them for the
                # run's life so a run past the 60 s window keeps its authority.
                with retention_snapshots(window, network.context, reader):
                    if rebind is not None:
                        # ``task_id`` is the sitting king's submission id; ``rebind`` its retained source bytes or None.
                        from carbon.challenge_validator.lean_recipe_retention import (
                            rebind_origin,
                        )

                        (source_envelope,) = rebind
                        return rebind_origin(
                            intake.adapter,
                            _open_pool_store(pool_store),
                            submission_id=task_id,
                            source_envelope=source_envelope,
                        )
                    if grade_set:
                        # ``task_id`` is the retained bank entry to grade on the
                        # whole configured pack set (OWNER-FULL-EXAM-BANK-01).
                        from carbon.challenge_validator import pack_set_grading

                        if "evaluation_pack_set" not in cfg:
                            raise ReceiverUnavailable(
                                "direct_receiver_pack_set_unconfigured"
                            )
                        block = cfg["evaluation_pack_set"]
                        return pack_set_grading.grade_set_entry(
                            _set_batch_adapters(
                                cfg,
                                root,
                                challenge,
                                material,
                                discovery,
                                providers,
                                ledger,
                            ),
                            batches=block["batches"],
                            set_key=block["set_key"],
                            entry_id=task_id,
                            artifact_directory=artifact_directory,
                            entry_directory=entry_directory,
                            promotion=_open_pool_store(pool_store),
                        )
                    if regrade:
                        # ``task_id`` is the retained bank entry id to regrade.
                        return intake.regrade_result(
                            task_id,
                            artifact_directory=artifact_directory,
                            entry_directory=entry_directory,
                            promotion=_open_pool_store(pool_store),
                            exam_se=exam_se,
                        )
                    return intake.retain_result(
                        task_id,
                        artifact_directory=artifact_directory,
                        entry_directory=entry_directory,
                        pool_store=_open_pool_store(pool_store),
                    )
            if timer is not None:
                timer.start()
            watch = PermitWatch(cfg["receiver_hotkey"], network, permits, stop).start()
            ChainStateWatch(window, root, stop).start()
            grader = None
            if "auto_grade" in cfg:
                from carbon.challenge_validator.auto_grade import AutoGrader

                grader = AutoGrader(
                    intake,
                    root,
                    pool_store=cfg["auto_grade"].get("pool_store"),
                    # each grade then runs under the host's official-grading lock (serve_loopback's _WorkLock)
                    host_lock="official_gpu_receipts" in cfg,
                )
                # The caller's own submission's grade state (exam_feedback v2) reads its marker.
                intake.grade_marker = grader.marker
                # A miner's withdrawal of its own queued submission writes its terminal marker (`construction_withdraw_v1`).
                intake.withdraw_marker = grader.withdrawn
                # The public queue (`queue_public`): counts and the door's state, read from this door's own records.
                from carbon.challenge_validator.queue_view import QueueView

                intake.queue_view = QueueView(intake, grader, root)
                # exam_feedback v8's public grade-worker line: whether the official inference image is a GPU image
                intake.grading_gpu = backend is not None
                # One waiting submission per coldkey (owner 14 Nov; `coldkey_waiting`): ON only for a version whose
                # limit is registered; waiting = this door's open task views + the grader's ungraded list
                from carbon.challenge_validator import coldkey_waiting

                intake.adapter.coldkey_waiting = coldkey_waiting.Guard(
                    opened=lambda: getattr(
                        intake.adapter.provider_for, "_providers", None
                    ),
                    pending=grader.pending,
                    snapshot=window.latest,
                    stalled=lambda: getattr(grader, "stalled", frozenset()),
                    # per built task, not the whole ungraded list, under the coldkey place's lock (submit latency)
                    pending_one=grader.is_pending,
                )
            if "auto_grade" in cfg and cfg["auto_grade"].get("pool_store"):
                intake.koth_view = _king_view(intake, cfg["auto_grade"]["pool_store"])
            if "launch_board" in cfg:
                import functools

                from carbon.challenge_validator.launch_board_file import read_board

                intake.board_feed = functools.partial(
                    read_board,
                    cfg["launch_board"],
                    intake.challenge.challenge_id,
                    cfg.get("launch_board_key"),
                )
            if grader is not None:
                _open_crown_owners(grader)
            providers.log_open_counts()
            # the recently active lazy owners are opened in the background, off every request's path (mcp_slow)
            providers.start_lazy_warmer()
            # the whole-tree storage walk runs here, off every request's path (submit latency, 21 Nov 2026)
            providers.start_storage_reconcile()
            serve_loopback(
                intake,
                {"host": cfg["host"], "port": cfg["port"]},
                stop=stop,
                reader=reader,
                grader=grader,
                ready=listening,
                closing=providers.cancel,
                # The standing receipt worker yields to this lock (`receipt_job`): it sits beside the receipt store.
                grading_lock_dir=(
                    Path(cfg["official_gpu_receipts"]).parent
                    if "official_gpu_receipts" in cfg
                    else None
                ),
                # The per-door DRAINING flag and in-flight record live in this door's state.
                state_dir=root,
            )
            if watch.lost:
                # The service exits non-zero; its next start refuses until the
                # permit is back.
                raise ReceiverUnavailable("receiver_permit_lost")
        finally:
            stop.set()
            if timer is not None:
                timer.cancel()
            # The shared listener waits for its worker, even if cancellation
            # raises. No worker or carrier is reimplemented here.
            _stop_providers(providers, cancel=retention is None)


#: Chain failures a starting receiver waits out (infrastructure: the endpoint is down, slow, throttled or behind).
#: A malformed, mismatched or unsupported answer is never waited out: the start refuses as before (fail closed).
CHAIN_WAIT_CODES = frozenset(
    {
        "PROVIDER_UNAVAILABLE",
        "TRANSPORT_TIMEOUT",
        "TRANSPORT_FAILURE",
        "CHAIN_FAILURE",
        "INCOMPLETE_RESPONSE",
        "STALE_SNAPSHOT",
        "PROVIDER_RATE_LIMITED",
    }
)
CHAIN_STATE_NAME = "chain-state.json"
#: How a starting receiver re-reads an unavailable chain: first wait, doubling to the cap (operational values).
CHAIN_RETRY_S, CHAIN_RETRY_MAX_S = 15.0, 120.0


def write_chain_state(state_dir, state, *, code=None, since_ns=None, attempts=0):
    """``<state>/chain-state.json`` (H8): OK or DEGRADED, since when, the last failure code and how many reads failed.
    Atomic, owner-only; never raises (a state file must not stop a receiver)."""
    import json

    try:
        if Path(state_dir).is_symlink() or not Path(state_dir).is_dir():
            return
        path = Path(state_dir) / CHAIN_STATE_NAME
        staged = path.with_name(f".{path.name}.{os.getpid()}")
        staged.write_text(
            json.dumps(
                {
                    "schema": "carbon.challenge-validator.chain-state.v1",
                    "state": state,
                    "since_ns": since_ns if since_ns is not None else time.time_ns(),
                    "code": code,
                    "failed_reads": attempts,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.chmod(staged, 0o600)
        os.replace(staged, path)
    except OSError:
        pass


#: How often a serving receiver records whether its snapshot window is fresh (operational value).
CHAIN_STATE_EVERY_S = 30.0


class ChainStateWatch:
    """Keeps ``chain-state.json`` current while the receiver serves (H8): DEGRADED from the first check that finds no
    fresh snapshot (``window.latest()`` is None), with the time it began; OK when the window reads again. Written on
    every change and every check while DEGRADED (its ``failed_reads`` counts checks), so a watcher alerts on age.
    It reads only the window; it never reads the chain itself or touches grading."""

    def __init__(self, window, state_dir, stop, *, every=None):
        self.window, self.state_dir, self.stop = window, Path(state_dir), stop
        self.every = CHAIN_STATE_EVERY_S if every is None else every
        self.since, self.checks = None, 0

    def check_once(self):
        try:
            fresh = self.window.latest() is not None
        except Exception:  # noqa: BLE001
            # an unreadable window is a degraded one
            fresh = False
        if fresh:
            if self.since is not None:
                write_chain_state(self.state_dir, "OK", attempts=self.checks)
            self.since, self.checks = None, 0
            return "OK"
        self.checks += 1
        self.since = time.time_ns() if self.since is None else self.since
        write_chain_state(
            self.state_dir,
            "DEGRADED",
            code="snapshot_stale",
            since_ns=self.since,
            attempts=self.checks,
        )
        return "DEGRADED"

    def run(self):
        while not self.stop.wait(self.every):
            self.check_once()

    def start(self):
        threading.Thread(
            target=self.run, name="carbon-chain-state", daemon=True
        ).start()
        return self


def await_chain_identity(
    hotkey, network, permits, reader, stop, state_dir, *, wait=True, sleep=None
):
    """The receiver's identity check and its first registered snapshot, waiting out an unavailable chain (H8).

    A throttled, cut or slow chain at start used to exit the receiver, and systemd restarted it every 30 s: a restart
    loop with the door down (R38). Now a service start waits IN PROCESS: it re-reads every `CHAIN_RETRY_S`, doubling
    to `CHAIN_RETRY_MAX_S`, logs each failure (`receiver_waiting_for_chain`) and keeps `chain-state.json` DEGRADED,
    and proceeds the moment the chain answers. A stop request ends the wait. Nothing is served or admitted before the
    identity check passes; a hotkey with no permit, or not in the snapshot, refuses exactly as before. One-shot operator
    commands (``wait=False``) keep the old behaviour: the first chain failure is their answer.
    """
    from carbon.battery.intake import log
    from carbon.chain.models import ChainFailure

    pause = stop.wait if sleep is None else sleep
    delay, attempts, since = CHAIN_RETRY_S, 0, None
    while True:
        try:
            _require_receiver_identity(hotkey, network, permits)
            snapshot = asyncio.run(reader.capture(network.context))
        except (ReceiverUnavailable, ChainFailure) as failed:
            code = (
                failed.code.value
                if isinstance(failed, ChainFailure)
                else str(failed) or type(failed).__name__
            )
            inner = str(failed.__cause__) if failed.__cause__ is not None else None
            waitable = code in CHAIN_WAIT_CODES or (
                code == "receiver_permit_unavailable"
                and (inner in CHAIN_WAIT_CODES or inner == "permit_read_failed")
            )
            if not wait or not waitable:
                raise
            attempts += 1
            since = time.time_ns() if since is None else since
            write_chain_state(
                state_dir, "DEGRADED", code=code, since_ns=since, attempts=attempts
            )
            log("receiver_waiting_for_chain", code=code, attempts=attempts)
            if pause(delay):
                raise ReceiverUnavailable(
                    "receiver_stopped_waiting_for_chain"
                ) from None
            delay = min(delay * 2, CHAIN_RETRY_MAX_S)
            continue
        if snapshot.context != network.context or snapshot.resolve(hotkey) is None:
            raise ValueError("registered receiver snapshot required")
        if wait:  # a one-shot operator command never overwrites a serving door's record
            write_chain_state(state_dir, "OK", attempts=attempts)
        if attempts:
            log("receiver_chain_recovered", attempts=attempts)
        return snapshot


def _require_receiver_identity(hotkey, network, permits=None):
    """The receiver hotkey is Carbon's network publisher, or a hotkey that holds
    a validator permit on the subnet at the finalized head (the answer-key
    distribution's own rule). An unreadable chain is infrastructure."""
    if hotkey == network.publisher_hotkey:
        return
    from carbon.chain.permits import PermitUnavailable, ValidatorPermitReader

    reader = ValidatorPermitReader(network.context) if permits is None else permits
    try:
        permit = reader.read(hotkey)
    except PermitUnavailable as unavailable:
        # the chain's own code rides along (H8: only an unavailable chain is waited out at start)
        raise ReceiverUnavailable("receiver_permit_unavailable") from unavailable
    if permit is None or permit["permit"] is not True:
        raise ValueError("receiver hotkey holds no validator permit on the subnet")


#: One round: an epoch of 360 blocks of 12 s. The permit is read again once a
#: round while the receiver serves (Validator, E2 note).
PERMIT_RECHECK_SECONDS = 360 * 12


class PermitWatch:
    """Reads the receiver's identity again every round while it serves. A lost
    permit stops the receiver (``lost``); an unreadable chain is infrastructure
    and is read again next round. Carbon's publisher needs no read."""

    def __init__(self, hotkey, network, permits, stop, *, interval=None):
        self.hotkey, self.network, self.permits = hotkey, network, permits
        self.stop = stop
        self.interval = PERMIT_RECHECK_SECONDS if interval is None else interval
        self.lost = False

    def check_once(self) -> bool:
        """Whether the receiver may keep serving; sets ``lost`` and stops it if not."""
        try:
            _require_receiver_identity(self.hotkey, self.network, self.permits)
        except ReceiverUnavailable:
            return True
        except ValueError:
            self.lost = True
            self.stop.set()
            return False
        return True

    def run(self):
        while not self.stop.wait(self.interval):
            if not self.check_once():
                return

    def start(self):
        if self.hotkey != self.network.publisher_hotkey:
            threading.Thread(
                target=self.run, name="carbon-permit-watch", daemon=True
            ).start()
        return self


def _king_view(intake, pool_store):
    """The public king view (`koth_public`) over this receiver's pool store."""
    from carbon.challenge_validator import exam_cap, koth_public

    adapter = intake.adapter
    challenge = intake.challenge

    def epoch_of(submission_id):
        block = exam_cap.submission_block(
            adapter.ledger, adapter.contract_digest, submission_id
        )
        return None if block is None else exam_cap.epoch_of(block)

    snapshot = getattr(adapter.discovery, "evaluation_pack_snapshot", None)
    label = getattr(snapshot, "evaluation_version", None)
    return koth_public.PoolKingView(
        open_store=lambda: _open_pool_store(pool_store),
        epoch_of=epoch_of,
        exam_version_label=label if type(label) is str and label else "exam",
        rebuild_noise_of=lambda: _page_noise(challenge),
        # The comparator's baseline total, registered when the comparator was built for
        # the exam set (`BankPromotion.consider_private`): never the private score pack.
        baseline=lambda: _open_pool_store(pool_store).latest_baseline(
            challenge.challenge_id
        ),
        crown_bar_of=lambda challenge_id: _crown_bar(pool_store, challenge_id),
    )


def _page_noise(challenge):
    """The margin the king page shows: the official-score rule's margin when it is on (`crown_official`: the decision's
    margin), else the registered rebuild noise, as before."""
    from carbon.challenge_validator import crown_official, koth_registry

    if crown_official.ACTIVE is not None:
        if crown_official.margin_unset():
            return None  # no margin in force yet (V2 17 Nov): the page shows none, never a value it does not decide with
        return {
            "value": crown_official.ACTIVE["margin"],
            "measurement_digest": crown_official.ACTIVE["digest"],
        }
    return koth_registry.rebuild_noise(
        challenge.challenge_id, version=challenge.version
    )


def _crown_bar(pool_store, challenge_id):
    """The averaged bar of the king page (`koth_public.TO_BEAT_RULE_AVERAGED`, Lead 5 Nov) when this receiver runs crown
    averaging, or None. A screening grade must beat the king's N-rebuild MEAN by more than margin_N
    (`crown_average.Active.screening`): ``{"base": mean, "margin": margin_N}``. A KING_UNSTABLE king's single standing
    total stands for his mean; with no king, Carbon's baseline. None (the single-grade bar stays) when averaging is off,
    margin_N is not registered at the configured N, the store is absent, or the king has no filed measurement
    (KING_UNMEASURED: crowns wait). Private: the page publishes only the rounded-up sum.
    """
    from carbon.challenge_validator import crown_average, crown_official

    if crown_official.ACTIVE is not None:
        # Official-score crowns (owner 14 Nov) ARE the single-grade rule: the king's official total + the rule's margin.
        # So the page keeps the original bar (`koth_public.TO_BEAT_RULE`: the step-floored king total + step + margin,
        # rounded up, with `_page_noise`'s margin), under its original id, never the averaged one.
        return None
    active = crown_average.ACTIVE
    if active is None:
        return None
    margin = active.rule.margin_for(challenge_id)
    store = None if margin is None else _open_pool_store(pool_store)
    if store is None:
        return None
    incumbent = store.incumbent()
    if incumbent is None:
        base = store.latest_baseline(challenge_id)
    else:
        model = incumbent["model_id"]
        # the mean on the king's latest key only, as the screening reads it (no carry from another exam)
        key = store.incumbent_evaluation_key(model)
        base = None if key is None else store.crown_mean(model, key)
        if (
            base is None
            and key is not None
            and store.crown_average_unstable(model, key)
        ):
            standing = store.incumbent_standing(model)
            base = None if standing is None else standing["total"]
    return None if base is None else {"base": base, "margin": margin}


class PoolStoreUnavailable(ValueError):
    code = "pool_store_unavailable"


def _open_pool_store(path):
    """The existing pool store a regrade is recorded in, or None; never created here."""
    if path is None:
        return None
    from carbon.battery.pool_store import PoolStore

    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PoolStoreUnavailable
    return PoolStore(path)


def _exam_cap_startup(ledger, discovery, restore):
    """Start-up, nothing is grading: return reservations a crash left open.

    A capped Challenge without the wall-limit policy refuses to start
    (``exam_cap_deadline_unregistered``), before anything is restored.
    """
    from carbon.challenge_validator import exam_cap

    deadline = exam_cap.require_grading_deadline(
        getattr(discovery, "_material", None),
        discovery.info.challenge_key.challenge_id,
    )
    restore()
    exam_cap.ExamCap(ledger, grading_deadline_seconds=deadline)


def _dump_stacks(signum=None, frame=None, stream=None):
    """Write every thread's stack (code locations only: file, line, function; never a value) to ``stream`` (stderr), in
    faulthandler's layout. Runs as a Python signal handler, so in the main thread with the GIL held: the other threads'
    frames are read through `sys._current_frames`, which is safe while they run.
    """
    import traceback

    out = sys.stderr if stream is None else stream
    names = {thread.ident: thread.name for thread in threading.enumerate()}
    lines = []
    for ident, top in sys._current_frames().items():
        lines.append(
            f"Thread {ident:#018x} {names.get(ident, '?')} (most recent call first):"
        )
        for entry in reversed(traceback.extract_stack(top)):
            lines.append(
                f'  File "{entry.filename}", line {entry.lineno} in {entry.name}'
            )
    try:
        out.write("\n".join(lines) + "\n")
        out.flush()
    except (OSError, ValueError, AttributeError):
        pass  # no stream to write to: a diagnosis aid, never a reason to stop


def register_stack_dump():
    """Ops diagnosis (Live ops, 17 Nov 2026: two grades parked for 90 min and their stacks were lost at the restart; no
    py-spy, ptrace_scope 1, no root): ``kill -USR1 <door pid>`` writes every thread's stack to stderr (the journal).
    Code locations only, never a value; the door goes on.

    A Python handler (`_dump_stacks`), NOT ``faulthandler.register(all_threads=True)``: faulthandler walks the other
    threads' frames from the signal context without the GIL, and on live 116 (19 Nov 2026 06:28:27Z) it crashed the
    receiver (SEGV, core dumped) mid-walk, killing two in-flight grades. A platform without SIGUSR1, or a call off the
    main thread: nothing, and the start goes on.
    """
    if not hasattr(signal, "SIGUSR1"):
        return
    try:
        signal.signal(signal.SIGUSR1, _dump_stacks)
    except (OSError, ValueError):
        pass  # not the main thread: a diagnosis aid, never a reason not to start


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.direct_receiver"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--retain-task")
    parser.add_argument(
        "--pool-store",
        type=Path,
        help="with --regrade-entry: also record the regrade for the incumbent in this "
        "existing pool store, where the takeover comparison looks it up",
    )
    parser.add_argument(
        "--exam-se",
        action="store_true",
        help="with --regrade-entry: also write the exam-total standard error (a case "
        "bootstrap) beside the binding, for the weekly fresh-draw check",
    )
    parser.add_argument(
        "--regrade-entry",
        help="regrade this retained bank entry on the receiver's selected pack",
    )
    parser.add_argument(
        "--grade-set-entry",
        help="grade this retained bank entry on the receiver's whole configured "
        "pack set and record the one set-level result (OWNER-FULL-EXAM-BANK-01)",
    )
    parser.add_argument(
        "--rebind-origin",
        help="rebind this SITTING king's origin under its own hotkey on this root "
        "(after an image move), cancelled at once; needs --pool-store",
    )
    parser.add_argument(
        "--rebind-source",
        type=Path,
        help="with --rebind-origin: a graph king's retained source-envelope.json",
    )
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--entry-directory", type=Path)
    args = parser.parse_args(argv)
    import sys

    from carbon.challenge_validator import cpu_pin

    try:
        cpu_pin.require()  # every scoring mode of this program (serve, retain, regrade, set) runs pinned
    except cpu_pin.CpuPinRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    if (
        sum(
            value is not None
            for value in (
                args.retain_task,
                args.regrade_entry,
                args.grade_set_entry,
                args.rebind_origin,
            )
        )
        > 1
    ):
        parser.error(
            "retain a task, regrade an entry, grade a set entry, or rebind an origin, "
            "not more"
        )
    if args.rebind_source is not None and args.rebind_origin is None:
        parser.error("--rebind-source applies to --rebind-origin only")
    if args.rebind_origin is not None and args.pool_store is None:
        parser.error("--rebind-origin needs --pool-store")
    if args.exam_se and args.regrade_entry is None:
        parser.error("--exam-se applies to --regrade-entry only")
    if args.pool_store is not None and (
        args.regrade_entry is None
        and args.retain_task is None
        and args.grade_set_entry is None
        and args.rebind_origin is None
    ):
        parser.error(
            "--pool-store applies to --retain-task, --regrade-entry or "
            "--grade-set-entry"
        )
    retention_args = (
        (
            args.rebind_origin
            if args.rebind_origin is not None
            else (
                args.grade_set_entry
                if args.grade_set_entry is not None
                else (
                    args.retain_task
                    if args.regrade_entry is None
                    else args.regrade_entry
                )
            )
        ),
        args.artifact_directory,
        args.entry_directory,
    )
    if any(value is not None for value in retention_args) and not all(
        value is not None for value in retention_args
    ):
        parser.error("retention requires task and both operator directories")
    retention = retention_args if retention_args[0] is not None else None
    if not args.config.is_file():
        # The one missing input an operator can fix, named instead of the generic code.
        print(
            json.dumps(
                {
                    "unavailable": "receiver_config_missing",
                    "config": str(args.config),
                    "next": "write it with `python -B -m carbon.challenge_validator."
                    "receiver_setup prepare`",
                }
            ),
            flush=True,
        )
        return 1
    stop = threading.Event()
    for number in (signal.SIGTERM, signal.SIGINT):
        # announced to the carrier first: a remote build whose stream the stop cuts is left running (`_announce_stop`)
        signal.signal(number, lambda *_: (_announce_stop(), stop.set()))
    register_stack_dump()
    try:
        result = serve(
            args.config,
            stop=stop,
            ready=lambda item: print(json.dumps(item), flush=True),
            retention=retention,
            regrade=args.regrade_entry is not None,
            grade_set=args.grade_set_entry is not None,
            rebind=(
                None
                if args.rebind_origin is None
                else (
                    (
                        None
                        if args.rebind_source is None
                        else args.rebind_source.read_bytes()
                    ),
                )
            ),
            pool_store=args.pool_store,
            exam_se=args.exam_se,
        )
    except Exception as failure:  # noqa: BLE001 - no private exception text
        code = getattr(failure, "code", None)
        if retention is not None:
            from carbon.challenge_validator.lean_recipe_retention import (
                RetentionUnavailable,
            )

            if isinstance(failure, RetentionUnavailable):
                code = str(failure)
        from scripts.dev.miner_launchpad.controller import LockHeld

        if isinstance(failure, LockHeld):
            # A running serve owns this receiver state (Validator RECV3
            # follow-up): say so, not the generic unavailable.
            print(
                json.dumps(
                    {
                        "unavailable": "receiver_state_locked",
                        "next": "stop the receiver's serve unit first, then "
                        "run this again",
                    }
                ),
                flush=True,
            )
            return 1
        if type(code) is not str:
            # 18 Nov 2026 (c8bf7b24 exited 2 s into every start with only this code): the journal (operator-only) gets
            # the failure's type, Carbon's fixed message and where it was raised; stdout keeps the closed code
            _log_start_failure(
                "receiver_start_failed", failure, where=_raised_at(failure)
            )
            code = "direct_receiver_unavailable"
        print(json.dumps({"unavailable": code}), flush=True)
        # a stop request while waiting for the chain (H8) is a clean stop, not a failed unit
        return 0 if code == "receiver_stopped_waiting_for_chain" else 1
    if args.rebind_origin is not None:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "state": result["state"],
                    "origin": result["origin"],
                }
            ),
            flush=True,
        )
        return 0
    if retention is not None:
        reported = {
            "schema": SCHEMA,
            "state": "RETAINED",
            "status": result["status"],
            "entry_id": result["entry_id"],
            "score_state": result["score_state"],
            "official_eligible": result["official_eligible"],
        }
        if "measurement_state" in result:
            state = result["measurement_state"]
            if state not in ("DEVELOPMENT_UNRANKED", "UNAVAILABLE"):
                print(
                    json.dumps({"unavailable": "direct_receiver_unavailable"}),
                    flush=True,
                )
                return 1
            reported["measurement_state"] = state
        # Operator-only: whether the selected pack graded the retained model, and why not.
        if result.get("private_evaluation_state") in (
            "BOUND_DEVELOPMENT_ONLY",
            "UNAVAILABLE",
            "CANDIDATE_FAILED",
        ):
            reported["private_evaluation_state"] = result["private_evaluation_state"]
            reason = result.get("private_evaluation_reason")
            if type(reason) is str and re.fullmatch(r"[A-Za-z0-9_]{1,80}", reason):
                reported["private_evaluation_reason"] = reason
            message = result.get("private_evaluation_message")
            if type(message) is str and message:
                reported["private_evaluation_message"] = message
        koth = result.get("koth_comparison")
        if type(koth) is dict:
            # Operator-only: the DEVELOPMENT king-of-the-hill outcome, or the pool refusal.
            for key in ("outcome", "reason", "error"):
                value = koth.get(key)
                if type(value) is str and re.fullmatch(r"[A-Za-z0-9_]{1,80}", value):
                    reported["koth_" + key] = value
        for key in ("regrade_of", "regrade_task_id"):
            if type(result.get(key)) is str:
                reported[key] = result[key]
        print(
            json.dumps(reported),
            flush=True,
        )
        return 0
    print(json.dumps({"schema": SCHEMA, "state": "STOPPED"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
