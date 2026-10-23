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
    "material_cache_bytes",
    "construction_image_manifest",
    "inference_image_manifest",
    "evaluation_pack",
    "evaluation_pack_set",
    "challenge",
    "construction_runtimes",
    "auto_grade",
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
    for field in ("construction_image_manifest", "inference_image_manifest"):
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
    binding_path = root / "receiver-binding.json"
    if binding_path.is_symlink():
        raise ValueError("receiver binding link refused")
    retained = private_json(binding_path) if binding_path.exists() else None
    if bound and retained is not None and "evaluation_pack_digest" in retained:
        digest = retained["evaluation_pack_digest"]
    else:
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
        )
    return adapters


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


def installed_source(
    profile_path: Path, *, construction_image_manifest: Path | None = None
):
    """Verify installed source/images; a private operator may pin its constructor."""
    from carbon.development_session.gpu_practice import direct_parent_backend
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import (
        accepted_implementation,
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
        implementation = accepted_implementation(cfg["accepted_revision"])
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
    ):
        from carbon.development_session.gpu_practice import DirectParents

        if parents is not None and (
            type(parents) is not DirectParents
            or parents.for_runtime("torch-cpu-py311") != parent
        ):
            raise ValueError("per-runtime parents must include the receiver parent")
        self.parents = parents
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

    def _manifest(self, hotkey, ledger, *, restoring):
        """Freeze the signed owner's one DEVELOPMENT receiver campaign.

        Registration is observed, not asserted by an operator or a recipe. A
        restart keeps the first observation while checking the same registered
        identity is still present in the current finalized snapshot.
        """
        from carbon.battery.challenge import CHALLENGE as BATTERY_CHALLENGE
        from carbon.challenge_kit import physical_material
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.product_campaign import AUTHORITY
        from carbon.development_session.research_ledger import PRODUCT

        if (
            self.implementation is None
            or self.snapshot is None
            or self.receiver is None
        ):
            raise ValueError("direct receiver authority binding required")
        admission = self._admission(hotkey)
        challenge = self.discovery.info.challenge_key
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
                raise ValueError("retained direct owner campaign binding changed")
            candidate = frozen
        elif restoring:
            raise ValueError("retained direct owner campaign manifest missing")
        elif admission is None:
            raise Unavailable("direct_provider_registration_unavailable")
        ledger.freeze(candidate)
        return candidate["admission"], self._same_registration(
            candidate["admission"], admission
        )

    def _open(self, hotkey, *, restoring):
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.research_control import CampaignControl
        from carbon.development_session.research_ledger import CampaignLedger
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
        from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

        if type(hotkey) is not str or not ADDRESS.fullmatch(hotkey):
            raise Unavailable("direct_provider_owner_invalid")
        with self._lock:
            if self._closing:
                raise Unavailable("direct_receiver_stopping")
            if hotkey not in self._providers:
                if not restoring and self._admission(hotkey) is None:
                    raise Unavailable("direct_provider_registration_unavailable")
                directory = _private_directory(
                    self.root / hashlib.sha256(hotkey.encode()).hexdigest()
                )
                ledger = CampaignLedger(directory / "ledger")
                frozen_admission, live = self._manifest(
                    hotkey, ledger, restoring=restoring
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
            if not restoring and not self._same_registration(
                self._admissions[hotkey], self._admission(hotkey)
            ):
                raise Unavailable("direct_provider_registration_unavailable")
            return self._providers[hotkey]

    def __call__(self, hotkey):
        return self._open(hotkey, restoring=False)

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
            self._open(owner["hotkey"], restoring=True)

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
    permits=None,
):
    """Run the same signed intake/task loop with finite admission and owned stop.

    ``permits`` replaces the chain's validator-permit read (tests only)."""
    from carbon.battery import challenge as battery_challenge
    from carbon.battery.construction_bundle_material import (
        versioned_material as battery_versioned_material,
    )
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.chain.sdk import BittensorReader
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.direct_intake import (
        DirectRecipeIntake,
        serve_loopback,
    )
    from carbon.challenge_validator.ledger import AttemptLedger
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.transport.store import ReceiptJournal
    from scripts.dev.miner_launchpad.controller import owner_lock

    cfg = load_config(config_path)
    selected_parent = (
        {"construction_image_manifest": Path(cfg["construction_image_manifest"])}
        if "construction_image_manifest" in cfg
        else {}
    )
    implementation, parent, network, cache = installed_source(
        Path(cfg["runner_profile"]), **selected_parent
    )
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
    if build_accelerator is not None and "material_cache_bytes" not in cfg:
        raise ReceiverUnavailable("gpu_overlay_cache_unconfigured")
    if not doctor(
        image_id=inference_image.image_id, image_identity=inference_image
    ).eligible:
        raise ReceiverUnavailable("installed_inference_worker_unavailable")
    # The receiver is the operator's own validator hotkey (E2): Carbon's network
    # publisher, or a hotkey holding a validator permit on the subnet now.
    _require_receiver_identity(cfg["receiver_hotkey"], network, permits)
    stop = threading.Event() if stop is None else stop
    reader = BittensorReader() if reader is None else reader
    snapshot = asyncio.run(reader.capture(network.context))
    if (
        snapshot.context != network.context
        or snapshot.resolve(cfg["receiver_hotkey"]) is None
    ):
        raise ValueError("registered receiver snapshot required")
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
        if "material_cache_bytes" in cfg:
            immutable["material_cache_bytes"] = cfg["material_cache_bytes"]
        if pack_digest is not None:
            immutable["evaluation_pack_digest"] = pack_digest
        write_once(root / "receiver-binding.json", canonical(immutable))
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
            )
            if retention is not None:
                task_id, artifact_directory, entry_directory = retention
                # No intake feeds snapshots in this mode: refresh them for the
                # run's life so a run past the 60 s window keeps its authority.
                with retention_snapshots(window, network.context, reader):
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
            grader = None
            if "auto_grade" in cfg:
                from carbon.challenge_validator.auto_grade import AutoGrader

                grader = AutoGrader(
                    intake, root, pool_store=cfg["auto_grade"].get("pool_store")
                )
            if "auto_grade" in cfg and cfg["auto_grade"].get("pool_store"):
                intake.koth_view = _king_view(intake, cfg["auto_grade"]["pool_store"])
            serve_loopback(
                intake,
                {"host": cfg["host"], "port": cfg["port"]},
                stop=stop,
                reader=reader,
                grader=grader,
                ready=listening,
                closing=providers.cancel,
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
    except PermitUnavailable:
        raise ReceiverUnavailable("receiver_permit_unavailable") from None
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
    )


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
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--entry-directory", type=Path)
    args = parser.parse_args(argv)
    if (
        sum(
            value is not None
            for value in (args.retain_task, args.regrade_entry, args.grade_set_entry)
        )
        > 1
    ):
        parser.error("retain a task, regrade an entry, or grade a set entry, not more")
    if args.exam_se and args.regrade_entry is None:
        parser.error("--exam-se applies to --regrade-entry only")
    if args.pool_store is not None and (
        args.regrade_entry is None
        and args.retain_task is None
        and args.grade_set_entry is None
    ):
        parser.error(
            "--pool-store applies to --retain-task, --regrade-entry or "
            "--grade-set-entry"
        )
    retention_args = (
        (
            args.grade_set_entry
            if args.grade_set_entry is not None
            else args.retain_task if args.regrade_entry is None else args.regrade_entry
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
        return 1
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
        ):
            reported["private_evaluation_state"] = result["private_evaluation_state"]
            reason = result.get("private_evaluation_reason")
            if type(reason) is str and re.fullmatch(r"[A-Za-z0-9_]{1,80}", reason):
                reported["private_evaluation_reason"] = reason
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
