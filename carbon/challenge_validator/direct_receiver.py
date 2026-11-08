"""Finite operator bootstrap for the existing signed DEVELOPMENT recipe intake.

The installed profile supplies trusted source, image and chain identities. An
authenticated hotkey selects only its own durable task workspace. This module
never holds a signer, builds an image or imports participant construction code.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import signal
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
    # Absolute paths to carbon.c03.worker-image.v1 manifests of images a SITTING king was built on before this
    # receiver's parent moved (Validator 5 Nov, route (a)): his regrade may infer on his own retained parent when the
    # image store holds it with exactly that id (`lean_recipe_retention._regrade_inference_image`). Kings only.
    "king_retained_parents",
    # R89 (Validator-2 6 Nov 09:16 option b): {guard, group, chunks: {rate_per_s, burst}}, every value the OWNER's
    # (decision #10). Absent: the shared peer bucket as before. Present with any value unset: the receiver refuses.
    "request_buckets",
    # The Chain Auditor's operator-only coldkey -> allowance-group map (`funder_map`). Absent: each coldkey is its
    # own group. An unreadable or malformed map is no map (each coldkey its own group), never a refusal.
    "funder_map_file",
    # OWNER-PROBING-COUNTERS-01 (a): {unmapped_coldkey, unresolved_hotkey, max_map_age_blocks}, every value the OWNER's
    # (`allowance_groups.policy`). Absent: the exam cap is per hotkey as before. Present with any value unset: refused.
    "allowance_groups",
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
            r"wss?://(127\.0\.0\.1|localhost|\[::1\]):[0-9]{1,5}/?", value["endpoint"]
        )
        is not None
    )


def chain_network_record() -> dict:
    """The network THIS process is bound to (`carbon.chain.models`), as a door's ``chain_network`` record."""
    from carbon.chain import models

    record = {"network": models.CARBON_NETWORK}
    if models.CARBON_NETWORK == models.LOCALNET:
        record.update(
            genesis=models.LOCALNET_GENESIS, endpoint=models.LOCALNET_ENDPOINT
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
    if "king_retained_parents" in value:
        _king_retained_parents(value["king_retained_parents"])
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
    if "crown_average" in value:
        section = value["crown_average"]
        if type(section) is not dict or set(section) != {"key_file"}:
            raise ValueError("invalid crown_average selection")
        from carbon.challenge_validator import crown_average_host

        crown_average_host.read_crown_key(section["key_file"])
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


def _pack_check(root, relative_path, digest, public_root, private_root, challenge):
    """Bind an opted-in pack to registered construction bytes at every use."""
    from carbon.challenge_validator.evaluation_pack import (
        EvaluationPackUnavailable,
        load_pack,
    )

    def checked(material):
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
        for role, document in expected.items():
            observed = snapshot.read_json_role(
                public_root, "public", role, max_bytes=65536
            )
            if canonical(observed) != canonical(document):
                raise EvaluationPackUnavailable("evaluation_pack.construction_mismatch")
        if (
            snapshot.read_role(
                public_root, "public", "train", max_bytes=16 * 1024 * 1024
            )
            != material["train"]
        ):
            raise EvaluationPackUnavailable("evaluation_pack.train_mismatch")

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


def _revision_only_change(frozen, candidate):
    """Whether ``frozen`` and ``candidate`` differ only by the accepted revision: every other field equal, ``runtime``
    and ``receiver_binding`` equal but for their ``implementation`` (so the same images, receiver, Challenge, pack and
    owner), ``campaign_id`` the one the new binding derives."""
    if set(frozen) != set(candidate):
        return False
    if any(frozen[k] != candidate[k] for k in candidate if k not in _REVISION_FIELDS):
        return False
    for key in ("runtime", "receiver_binding"):
        old, new = frozen[key], candidate[key]
        if type(old) is not dict or type(new) is not dict or set(old) != set(new):
            return False
        if any(old[k] != new[k] for k in new if k != "implementation"):
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


def _is_ancestor(old, new, root=None):
    """Whether accepted revision ``old`` is an ancestor of ``new`` in this checkout's history (git)."""
    import subprocess

    if not all(
        type(r) is str and len(r) == 40 and all(c in "0123456789abcdef" for c in r)
        for r in (old, new)
    ):
        return False
    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", old, new],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


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
    "carbon/development_session/graph_gpu_lane.py",
    # the graph rebuild (Validator 16:38): the direct-graph worker, the graph engine and what it stages
    "carbon/development_session/direct_graph_construction_worker.py",
    "carbon/level4/",
    "carbon/development_session/construction_tensor_codec.py",
    "carbon/development_session/build_refusal.py",
    "carbon/development_session/build_refusal_v2.py",
    "carbon/development_session/bundle_prediction_comparison.py",
    "carbon/development_session/single_call_timing.py",
    "carbon/challenge_validator/strict_json.py",
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
    "carbon/challenge_validator/scoring.py",
    "carbon/challenge_validator/koth_registry.py",
    "carbon/challenge_validator/crown_average.py",
    # a menu-D version's coded crown hold (Validator-2B 7 Nov): it decides whether a crown may change
    "carbon/challenge_validator/crown_hold.py",
    # whether a timed build ran on a quiet host decides whose failure a wall stop is (owner 5 Nov: rebuilds consistently
    # timed; Validator-2 21:28)
    "carbon/challenge_validator/host_quiet.py",
    "carbon/challenge_validator/bank_promotion.py",
    "carbon/battery/pool_store.py",
    # registry
    "carbon/registry/",
    "carbon/challenge_registry/",
    "carbon/challenge_kit/version_registry.py",
    "carbon/challenge_kit/served_versions.py",
    "carbon/challenge_kit/version_overlay.py",
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
        "carbon.challenge_validator.repeat_miss_watch",
        "an operator watch: writes no result",
    ),
    ("carbon.development_session.data", "create-only file writing"),
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


def install_declared_change(cfg):
    """Set (or clear) `DECLARED_EXAM_CHANGE` from a loaded receiver configuration."""
    global DECLARED_EXAM_CHANGE
    record = cfg.get("declared_exam_change")
    DECLARED_EXAM_CHANGE = None if record is None else _check_declared_change(record)


def _declared_change(old, new, touched):
    """The declared record when it covers exactly this migration (its revisions are OLD and NEW, and its paths EQUAL the
    computed changed grading paths, in order), else None."""
    record = DECLARED_EXAM_CHANGE
    if (
        record is None
        or touched is None
        or (record["from_revision"], record["to_revision"]) != (old, new)
        or list(record["paths"]) != list(touched)
    ):
        return None
    return record


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
    try:
        moved = build_inputs.listing(root, revision=old) != build_inputs.listing(
            root, revision=new
        )
        names = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "-z", "--no-renames"]
            + [old, new],
            capture_output=True,
            timeout=60,
            check=True,
        ).stdout.decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError, subprocess.SubprocessError):
        return None
    touched = [BUILD_INPUTS_CHANGED] if moved else []
    touched += sorted(path for path in names.split("\0") if path and grading_path(path))
    _GRADING_CHANGES[key] = tuple(touched)
    return _GRADING_CHANGES[key]


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


def _migrate_owner_manifest(ledger, hotkey, raw, frozen, candidate):
    """Re-freeze a retained owner's campaign manifest to a NEW accepted revision (Lead 4 Nov, option (a)), or False.

    A byte-exact carry of the owners/ store into a receiver on a newer revision met its own frozen manifest
    (the revision is part of it) and refused to start. The manifest is re-frozen only when the change is the revision
    alone (`_revision_only_change`), the old revision is an ANCESTOR of the new one (`_is_ancestor`), and every retained
    task names the contract this receiver serves (the recipe contract is unchanged); otherwise the start refuses as
    before. Only the campaign row changes (compare-and-swap on its old bytes); every task, evidence and view row is
    kept. The change is logged to stderr and appended to ``manifest-migrations.jsonl`` beside the owner's ledger.
    """
    import sys

    from carbon.development_session.profile import canonical, digest
    from carbon.reconstruction.served_recipe_contract import registered

    if not _revision_only_change(frozen, candidate):
        return False
    old, new = (
        frozen["implementation"]["revision"],
        candidate["implementation"]["revision"],
    )
    if not _is_ancestor(old, new):
        return False
    touched = _grading_change(old, new)
    declared = _declared_change(old, new, touched) if touched else None
    if declared is not None:
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
    elif touched != ():
        # M2: a grading or rebuild change is never carried under an old owner's manifest. Said once per owner, so a
        # spare proof shows why the start refused.
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
        return False
    if not _retained_contracts(ledger) <= {contract}:
        return False
    payload = canonical(candidate)
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE campaign SET manifest=?, digest=? WHERE id=1 AND manifest=?",
            (payload, digest(payload), raw),
        ).rowcount
    if changed != 1:
        return False
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
    }
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


def gpu_construction_parents(cfg, implementation, parents, chain_network):
    """`parents` plus the configured GPU workers as the parents of their GPU build runtimes
    (``jax-cuda13-py311`` / ``torch-cu130-py311``): ``(DirectParents, host device record)``.

    The CPU pair stays: an entry with no official-grade GPU twin (a smoke-only or
    non-repeating build) rebuilds on the CPU parent of its own runtime. Each worker is
    verified as the receiver's other workers are, must be eligible on this host, and its
    backend's accelerator profile must have the owner's hardware acceptance for the host's
    GPU class on this chain network, or the receiver refuses to start."""
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
    device = research_carrier._gpu_device()
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


def graph_gpu_lane(cfg, implementation, allowlist_bytes, chain_network):
    """The validator's graph GPU lane for an operator that configures one:
    ``(worker image, ops frozenset, ops record digest, host device record)``, else four Nones.

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
    from carbon.reconstruction.hardware_acceptance import require_accepted

    # The host's installed GPU record, and the owner's hardware acceptance for its class on
    # this chain network: a validator scores only on an accepted class, and refuses at start
    # otherwise (hardware_acceptance.py; the same gate the Battery GPU validator applies).
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
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
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
        from carbon.development_session.chain_onboarding import (
            OnboardingFailure,
            PublicAddress,
            RegisteredMiner,
        )

        observed = self.window.latest() if self.window is not None else self.snapshot
        if (
            observed is None
            or self.snapshot is None
            or observed.context != self.snapshot.context
        ):
            return None
        try:
            return RegisteredMiner(observed, PublicAddress(hotkey)).record()
        except OnboardingFailure:
            return None

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
                        ledger, hotkey, row[0], frozen, candidate
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

    def _open(self, hotkey, *, restoring, host=False):
        from carbon.challenge_validator import crown_average
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.research_control import CampaignControl
        from carbon.development_session.research_ledger import CampaignLedger
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
        from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

        if host:
            # ONLY the host owner of the crown average's derived rebuilds, by exact equality: a miner's owner
            # is always a verified ss58 address (below), which this string is not.
            if hotkey != crown_average.HOST_OWNER:
                raise Unavailable("direct_provider_owner_invalid")
        elif type(hotkey) is not str or not ADDRESS.fullmatch(hotkey):
            raise Unavailable("direct_provider_owner_invalid")
        with self._lock:
            if self._closing:
                raise Unavailable("direct_receiver_stopping")
            if hotkey not in self._providers:
                if not restoring and not host and self._admission(hotkey) is None:
                    raise Unavailable("direct_provider_registration_unavailable")
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
                self._providers[hotkey] = provider
                self._controls[hotkey] = control
                self._admissions[hotkey] = frozen_admission
                if restoring and not live:
                    # A revoked/recycled miner retains cleanup custody, never
                    # the right to launch a queued child from old authority.
                    for task_id in provider.queued_tasks():
                        provider.cancel_observed_task(
                            task_id, self.discovery.info.challenge_key
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

    def __call__(self, hotkey):
        from carbon.challenge_validator import crown_average

        # The derived-rebuild path asks for its host owner by name; a miner's request never can (its owner is a
        # verified ss58 address, and `LeanRecipeAdapter.evaluate` refuses the host owner as a submitter).
        return self._open(
            hotkey, restoring=False, host=hotkey == crown_average.HOST_OWNER
        )

    def restore(self):
        """Reopen every retained owner before listening, including interrupted work."""
        for directory in sorted(self.root.iterdir()):
            _private_directory(directory)
            owner = private_json(directory / "owner.json")
            if (
                type(owner) is not dict
                or set(owner) != {"hotkey"}
                or type(owner["hotkey"]) is not str
                or hashlib.sha256(owner["hotkey"].encode()).hexdigest()
                != directory.name
            ):
                raise ValueError("retained receiver owner binding differs")
            from carbon.challenge_validator import crown_average

            self._open(
                owner["hotkey"],
                restoring=True,
                host=owner["hotkey"] == crown_average.HOST_OWNER,
            )

    def cancel(self):
        """Close admission and request only our providers' domain cancellation."""
        with self._lock:
            self._closing = True
            providers = tuple(self._providers.values())
        errors = []
        for provider in providers:
            with provider._lock:
                views = tuple(provider._views.values())
            for view in views:
                try:
                    provider.cancel_observed_task(
                        view.task_id, self.discovery.info.challenge_key
                    )
                except Exception as failure:  # noqa: BLE001 - cancel all owned tasks
                    errors.append(type(failure).__name__)
        if errors:
            raise ReceiverUnavailable("direct_receiver_cancellation_unresolved")

    def close(self):
        """Release no provider lock while its children need reconciliation."""
        providers = tuple(self._providers.values())
        if any(
            provider.requires_reconciliation(view.task_id)
            for provider in providers
            for view in tuple(provider._views.values())
        ):
            raise ReceiverUnavailable("direct_receiver_cleanup_unresolved")
        for hotkey, provider in tuple(self._providers.items()):
            if hotkey in self._controls:
                state = self._controls[hotkey].settled(
                    provider.ledger.generation, cleanup_verified=True, ready=True
                )
                if state == "RECONCILIATION_REQUIRED":
                    raise ReceiverUnavailable("direct_receiver_cleanup_unresolved")
            provider.close()


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
    remeasure=None,
    rebind=None,
    permits=None,
):
    """Run the same signed intake/task loop with finite admission and owned stop.

    ``remeasure`` (``(evaluation_key, entry_id)``) with ``retention`` naming the sitting king's submission id
    re-measures that king's crown-average mean (`lean_recipe_retention.remeasure_incumbent_pack`), one-shot.

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
            cfg, implementation, parents, network.context.network
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
    one_shot = (
        retention is not None
        or regrade
        or grade_set
        or remeasure is not None
        or rebind is not None
    )
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
    with owner_lock(root):
        pack_check = None
        pack_digest = None
        pack_snapshot = None
        if "evaluation_pack" in cfg:
            pack_digest, pack_check, pack_snapshot = _sealed_pack(
                root, cfg["evaluation_pack"], challenge
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
            immutable["gpu_construction_device"] = {
                "kind": gpu_device.device_kind,
                "record": gpu_device.digest,
            }
        if "material_cache_bytes" in cfg:
            immutable["material_cache_bytes"] = cfg["material_cache_bytes"]
        if pack_digest is not None:
            immutable["evaluation_pack_digest"] = pack_digest
        if graph_gpu_image is not None:
            # Said only when configured: a CPU receiver's binding is what it was.
            immutable["graph_gpu_image"] = asdict(graph_gpu_image)
            immutable["graph_gpu_ops_digest"] = graph_gpu_ops_digest
            immutable["graph_gpu_device"] = {
                "kind": graph_gpu_device.device_kind,
                "record": graph_gpu_device.digest,
            }
        # The door part is write-once for the state's life; each release's whole binding is added beside it, so a
        # later release (or a rollback to an earlier one) starts on the same state (`state_binding`).
        from carbon.challenge_validator.state_binding import bind as bind_state

        bind_state(root, immutable)
        window = ReceiverSnapshotWindow(root, network.context, cfg["receiver_hotkey"])
        window.add(snapshot)
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
        )
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
                    if remeasure is not None:
                        # ``task_id`` is the sitting king's submission id.
                        from carbon.challenge_validator.lean_recipe_retention import (
                            remeasure_incumbent_pack,
                        )

                        (
                            evaluation_key,
                            entry_id,
                            record_out,
                            record_in,
                            only,
                            accept_revision,
                        ) = remeasure
                        from carbon.challenge_validator import (
                            crown_average,
                            crown_import,
                        )

                        store = _open_pool_store(pool_store)
                        if record_in is not None:
                            # C10: file a spare's verified measurement of this king; no rebuild runs here.
                            return crown_import.import_record(
                                record_in,
                                active=crown_average.ACTIVE,
                                store=store,
                                challenge_id=intake.adapter.challenge_id,
                                evaluation_key=evaluation_key,
                                entry_id=entry_id,
                                entry_directory=entry_directory,
                                receiver_binding=immutable,
                                accept_measured_revision=accept_revision,
                            )
                        if only:
                            # C10 write-only: the spare re-measured earlier and filed; record that, no rebuild.
                            crown_import.write_record(
                                record_out,
                                outcome=None,
                                active=crown_average.ACTIVE,
                                store=store,
                                challenge_id=intake.adapter.challenge_id,
                                submission_id=task_id,
                                evaluation_key=evaluation_key,
                                entry_id=entry_id,
                                entry_directory=entry_directory,
                                receiver_binding=immutable,
                            )
                            return {"state": "CROWN_MEASUREMENT_RECORDED"}
                        result = remeasure_incumbent_pack(
                            intake.adapter,
                            store,
                            submission_id=task_id,
                            evaluation_key=evaluation_key,
                            entry_id=entry_id,
                            artifact_directory=artifact_directory,
                            entry_directory=entry_directory,
                        )
                        if record_out is not None:
                            # C10, the spare's side: the record the live receiver verifies and files.
                            crown_import.write_record(
                                record_out,
                                outcome=result["outcome"],
                                active=crown_average.ACTIVE,
                                store=store,
                                challenge_id=intake.adapter.challenge_id,
                                submission_id=task_id,
                                evaluation_key=evaluation_key,
                                entry_id=entry_id,
                                entry_directory=entry_directory,
                                receiver_binding=immutable,
                            )
                        return result
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
                # The public queue (`queue_public`): counts and the door's state, read from this door's own records.
                from carbon.challenge_validator.queue_view import QueueView

                intake.queue_view = QueueView(intake, grader, root)
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
            try:
                if retention is None:
                    providers.cancel()
            finally:
                providers.close()


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
    from carbon.challenge_validator import exam_cap, koth_public, koth_registry

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
        rebuild_noise_of=lambda: koth_registry.rebuild_noise(challenge.challenge_id),
        # The comparator's baseline total, registered when the comparator was built for
        # the exam set (`BankPromotion.consider_private`): never the private score pack.
        baseline=lambda: _open_pool_store(pool_store).latest_baseline(
            challenge.challenge_id
        ),
        crown_bar_of=lambda challenge_id: _crown_bar(pool_store, challenge_id),
    )


def _crown_bar(pool_store, challenge_id):
    """The averaged bar of the king page (`koth_public.TO_BEAT_RULE_AVERAGED`, Lead 5 Nov) when this receiver runs crown
    averaging, or None. A screening grade must beat the king's N-rebuild MEAN by more than margin_N
    (`crown_average.Active.screening`): ``{"base": mean, "margin": margin_N}``. A KING_UNSTABLE king's single standing
    total stands for his mean; with no king, Carbon's baseline. None (the single-grade bar stays) when averaging is off,
    margin_N is not registered at the configured N, the store is absent, or the king has no filed measurement
    (KING_UNMEASURED: crowns wait). Private: the page publishes only the rounded-up sum.
    """
    from carbon.challenge_validator import crown_average

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
        "--remeasure-king",
        help="re-measure this SITTING king's crown-average mean under the configured "
        "rule (needs --evaluation-key, --remeasure-entry, --pool-store)",
    )
    parser.add_argument("--evaluation-key", help="with --remeasure-king")
    parser.add_argument(
        "--remeasure-entry", help="with --remeasure-king: the king's retained entry"
    )
    parser.add_argument(
        "--measurement-record",
        type=Path,
        help="with --remeasure-king on a SPARE: write the measurement record (a new 0600 file) for the live import",
    )
    parser.add_argument(
        "--record-only",
        action="store_true",
        help="with --measurement-record: write the record from the spare's already filed re-measure, with no rebuild",
    )
    parser.add_argument(
        "--accept-measured-revision",
        help="with --import-crown-measurement: the FULL sha of the revision the record was measured at, accepted "
        "explicitly when it differs from this receiver's (logged)",
    )
    parser.add_argument(
        "--import-crown-measurement",
        type=Path,
        help="with --remeasure-king on the LIVE receiver (stopped): verify a spare's measurement record of this king "
        "against this receiver and file its mean; no rebuild runs",
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
                args.remeasure_king,
                args.rebind_origin,
            )
        )
        > 1
    ):
        parser.error(
            "retain a task, regrade an entry, grade a set entry, or re-measure a "
            "king, not more"
        )
    if args.rebind_source is not None and args.rebind_origin is None:
        parser.error("--rebind-source applies to --rebind-origin only")
    if args.rebind_origin is not None and args.pool_store is None:
        parser.error("--rebind-origin needs --pool-store")
    if (args.remeasure_king is None) != (
        args.evaluation_key is None and args.remeasure_entry is None
    ) or (
        args.remeasure_king is not None
        and (
            args.evaluation_key is None
            or args.remeasure_entry is None
            or args.pool_store is None
        )
    ):
        parser.error(
            "--remeasure-king needs --evaluation-key, --remeasure-entry and "
            "--pool-store, and they apply to it only"
        )
    if (
        args.measurement_record is not None or args.import_crown_measurement is not None
    ) and (
        args.remeasure_king is None
        or (args.measurement_record is not None)
        == (args.import_crown_measurement is not None)
    ):
        parser.error(
            "--measurement-record (spare) or --import-crown-measurement (live), one of "
            "them, with --remeasure-king"
        )
    if (
        args.accept_measured_revision is not None
        and args.import_crown_measurement is None
    ):
        parser.error(
            "--accept-measured-revision applies to --import-crown-measurement only"
        )
    if args.record_only and args.measurement_record is None:
        parser.error("--record-only applies to --measurement-record only")
    if args.exam_se and args.regrade_entry is None:
        parser.error("--exam-se applies to --regrade-entry only")
    if args.pool_store is not None and (
        args.regrade_entry is None
        and args.retain_task is None
        and args.grade_set_entry is None
        and args.remeasure_king is None
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
                args.remeasure_king
                if args.remeasure_king is not None
                else (
                    args.grade_set_entry
                    if args.grade_set_entry is not None
                    else (
                        args.retain_task
                        if args.regrade_entry is None
                        else args.regrade_entry
                    )
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
        signal.signal(number, lambda *_: stop.set())
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
            remeasure=(
                None
                if args.remeasure_king is None
                else (
                    args.evaluation_key,
                    args.remeasure_entry,
                    args.measurement_record,
                    args.import_crown_measurement,
                    args.record_only,
                    args.accept_measured_revision,
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
    if args.import_crown_measurement is not None or args.record_only:
        printed = {"schema": SCHEMA, "state": result["state"]}
        if "accepted_measured_revision" in result:
            printed["accepted_measured_revision"] = result["accepted_measured_revision"]
        print(json.dumps(printed), flush=True)
        return 0
    if args.remeasure_king is not None:
        # Operator-only: the outcome and reason; the seeds, totals and mean stay private.
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "state": "KING_REMEASURE",
                    "outcome": result["outcome"],
                    "reason": result["reason"],
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
