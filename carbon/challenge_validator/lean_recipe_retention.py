"""Operator-only custody of a served recipe's actual DEVELOPMENT bytes.

The signed validator path never calls this helper. It indexes an already
terminal, owner-bound task in the existing create-only ScoreLab bank; it does
not replay a worker, grade predictions, or grant receiver/official authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict
from pathlib import Path


class RetentionUnavailable(ValueError):
    """The named original-byte or custody dependency is unavailable."""


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _json(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _owner_directory(value, label: str) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_dir()
        or path.resolve(strict=True) != path
    ):
        raise RetentionUnavailable(label + "_unavailable")
    if os.name == "posix":
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise RetentionUnavailable(label + "_not_owner_only")
    return path


def _snapshot(path: Path, *, limit: int, digest: str, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RetentionUnavailable(label + "_unavailable")
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise RetentionUnavailable(label + "_size")
    raw = path.read_bytes()
    if len(raw) != size or _sha(raw) != digest:
        raise RetentionUnavailable(label + "_changed")
    return raw


def _receipt_snapshot(path: Path, expected: dict, label: str) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 65536:
        raise RetentionUnavailable(label + "_unavailable")
    raw = path.read_bytes()
    try:
        observed = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RetentionUnavailable(label + "_malformed") from exc
    if len(raw) != path.stat().st_size or observed != expected:
        raise RetentionUnavailable(label + "_changed")
    return raw


def _collect_graph_artifacts(provider, submission_id, task, evidence, recipe, material):
    """Gather only the graph task's original, verified DEVELOPMENT bytes."""
    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.reconstruction.worker.model import WorkerImageIdentity
    from carbon.research import canonical_bytes

    worker_fields = {
        "schema",
        "image_id",
        "parent_image_id",
        "inference_image_id",
        "build_operation",
        "inference_operation",
        "build_controls_digest",
        "inference_controls_digest",
        "state_digest",
        "predictions_digest",
        "build_receipt",
        "inference_receipt",
        "predictions_raw_base64",
        "submission_digest",
    }
    if (
        type(evidence) is not dict
        or set(evidence) != worker_fields | {"predictions"}
        or type(evidence["build_receipt"]) is not dict
        or type(evidence["inference_receipt"]) is not dict
        or any(
            type(evidence[field]) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", evidence[field]) is None
            for field in ("build_controls_digest", "inference_controls_digest")
        )
    ):
        raise RetentionUnavailable("graph_worker_evidence_unavailable")
    request = provider._requests[submission_id]
    try:
        image = provider._resolved_image(request)
    except (FileNotFoundError, ValueError) as exc:
        raise RetentionUnavailable("source_image_unavailable") from exc
    admitted_binding = provider._task_image_bindings.get(submission_id)
    if admitted_binding is None:
        raise RetentionUnavailable("admitted_image_binding_unavailable")
    if (
        type(image) is not WorkerImageIdentity
        or provider._image_binding(image) != admitted_binding
        or image != provider.inference_image
        or evidence.get("schema") != "carbon.direct-private-attempt.graph.v1"
        or any(
            evidence.get(field) != image.image_id
            for field in ("image_id", "parent_image_id", "inference_image_id")
        )
    ):
        raise RetentionUnavailable("admitted_image_changed")
    source_digest = recipe.to_dict()["source"]["submission_digest"]
    if evidence.get("submission_digest") != source_digest:
        raise RetentionUnavailable("admitted_graph_source_changed")
    challenge = recipe.to_dict()["challenge"]
    build_evidence = evidence["build_receipt"]
    if (
        set(build_evidence)
        != {
            "schema",
            "recipe_digest",
            "submission_digest",
            "train_digest",
            "state_digest",
            "allowlist_digest",
            "framework",
            "fit",
        }
        or build_evidence["schema"] != "carbon.development.graph-build.v1"
        or build_evidence["recipe_digest"] != recipe.digest
        or build_evidence["submission_digest"] != source_digest
        or build_evidence["train_digest"] != challenge["train_digest"]
        or build_evidence["state_digest"] != task.terminal_receipt.state_digest
        or build_evidence["allowlist_digest"] != _sha(material["allowlist_bytes"])
        or build_evidence["framework"] != "jax"
        or type(build_evidence["fit"]) is not dict
    ):
        raise RetentionUnavailable("graph_build_receipt_changed")
    try:
        source = provider._source_envelope(submission_id, recipe)
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable("admitted_graph_source_unavailable") from exc

    root = provider.ledger.root
    if any(
        type(evidence.get(name)) is not str
        or re.fullmatch(r"operation-[0-9a-f]{64}", evidence[name]) is None
        for name in ("build_operation", "inference_operation")
    ):
        raise RetentionUnavailable("worker_operation_invalid")
    build = root / evidence["build_operation"] / "snapshot"
    inference = root / evidence["inference_operation"] / "snapshot"
    state = _snapshot(
        build / "state.npz",
        limit=64 * 1024**2,
        digest=task.terminal_receipt.state_digest,
        label="state_snapshot",
    )
    predictions = _snapshot(
        inference / "predictions.json",
        limit=16 * 1024**2,
        digest=task.terminal_receipt.predictions_digest,
        label="prediction_snapshot",
    )
    build_receipt = _receipt_snapshot(
        build / "receipt.json", evidence["build_receipt"], "build_receipt"
    )
    inference_receipt = _receipt_snapshot(
        inference / "receipt.json", evidence["inference_receipt"], "inference_receipt"
    )
    train = material["train"]
    if _sha(train) != recipe.to_dict()["challenge"]["train_digest"]:
        raise RetentionUnavailable("public_train_changed")
    if "practice_inputs" not in material or "practice_reference" not in material:
        raise RetentionUnavailable("public_input_target_unavailable")
    inputs = _tensors(inputs=material["practice_inputs"])
    fixture = _tensors(
        inputs=material["practice_inputs"],
        targets=material["practice_reference"],
    )
    if evidence["inference_receipt"].get("inputs_digest") != _sha(inputs):
        raise RetentionUnavailable("practice_inputs_changed")
    worker = dict(evidence)
    worker.pop("predictions", None)
    artifacts = {
        "recipe.json": recipe.canonical_bytes,
        "construction-kit.json": _json(material["construction_kit"]),
        "train.npz": train,
        "fixture.npz": fixture,
        "inputs.npz": inputs,
        "state.npz": state,
        "predictions.json": predictions,
        "source-envelope.json": source,
        "image.json": _json(asdict(image)),
        "allowlist.json": material["allowlist_bytes"],
        "build-receipt.json": build_receipt,
        "inference-receipt.json": inference_receipt,
        "worker-evidence.json": _json(worker),
        "task-receipt.json": canonical_bytes(task.terminal_receipt),
    }
    return artifacts


def _retain_graph_artifacts(
    artifacts, submission_id, *, artifact_directory, entry_directory
):
    from carbon.development_session.data import write_once

    try:
        from scripts.dev.score_lab.public_unbound_custody import (
            GRAPH_ROLE_SCHEMA_V3,
            prepare_custody_v5,
        )
        from scripts.dev.score_lab.public_unbound_entry import create_entry_v5
    except ImportError as exc:
        raise RetentionUnavailable("graph_bank_role_contract_unavailable") from exc
    if GRAPH_ROLE_SCHEMA_V3 != "carbon.scorelab.public-model-artifact-roles.v3":
        raise RetentionUnavailable("graph_bank_role_contract_unavailable")
    if json.loads(artifacts["inference-receipt.json"]).get("schema") != (
        "carbon.development.bundle-inference.v2"
    ):
        raise RetentionUnavailable("graph_measured_receipt_unavailable")
    roles = {
        "recipe": ("recipe.json", "json"),
        "construction_kit": ("construction-kit.json", "json"),
        "train": ("train.npz", "numeric_npz"),
        "fixture": ("fixture.npz", "numeric_npz"),
        "inputs": ("inputs.npz", "numeric_npz"),
        "state": ("state.npz", "bundle_graph_npz"),
        "predictions": ("predictions.json", "json"),
        "source": ("source-envelope.json", "json"),
        "image": ("image.json", "json"),
        "allowlist": ("allowlist.json", "json"),
        "build_receipt": ("build-receipt.json", "json"),
        "inference_receipt": ("inference-receipt.json", "json"),
        "worker_evidence": ("worker-evidence.json", "json"),
        "task_receipt": ("task-receipt.json", "raw_bytes"),
    }
    role_manifest = {
        "schema": GRAPH_ROLE_SCHEMA_V3,
        "scope": "PUBLIC_DEVELOPMENT_BUNDLE_MODEL",
        "source_schema": "carbon.development.graph-source-state.v1",
        "roles": {
            role: {"file": name, "codec": codec}
            for role, (name, codec) in sorted(roles.items())
        },
        "retained_files": {name: _sha(raw) for name, raw in sorted(artifacts.items())},
        "physics_contract": None,
    }
    base = _owner_directory(artifact_directory, "artifact_directory")
    entries = _owner_directory(entry_directory, "entry_directory")
    task_root = base / submission_id
    task_root.mkdir(mode=0o700, exist_ok=True)
    _owner_directory(task_root, "task_artifacts")
    try:
        for name, raw in artifacts.items():
            write_once(task_root / name, raw)
        manifest_path = base / (submission_id + ".roles.json")
        write_once(manifest_path, _json(role_manifest))
        custody = prepare_custody_v5(task_root, manifest_path)
        custody_path = base / (submission_id + ".custody.json")
        write_once(custody_path, _json(custody))
        saved = create_entry_v5(task_root, manifest_path, custody_path, entries)
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable("operator_bank_custody_unavailable") from exc
    return {
        "status": saved["status"],
        "entry_id": saved["entry"]["entry_id"],
        "entry_path": entries / saved["path"],
        "artifact_path": task_root,
        "score_state": saved["entry"]["score_state"],
        "official_eligible": False,
    }


def _retain_private_pack_binding(adapter, provider, submission_id, task, result):
    """Keep the selected pack identity beside one trusted retained task."""
    digest = provider.evaluation_pack_digest
    if digest is None:
        if adapter.discovery.evaluation_pack_digest is not None:
            raise RetentionUnavailable("evaluation_pack_task_binding_changed")
        return result
    if digest != adapter.discovery.evaluation_pack_digest:
        raise RetentionUnavailable("evaluation_pack_task_binding_changed")
    adapter.discovery._checked(adapter.discovery.info.challenge_key)
    with provider.ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if row is None:
        raise RetentionUnavailable("evaluation_pack_campaign_unavailable")
    try:
        campaign = json.loads(row[0])
        binding = campaign["receiver_binding"]
        if binding["evaluation_pack_digest"] != digest:
            raise ValueError("pack differs")
        campaign_id = campaign["campaign_id"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RetentionUnavailable("evaluation_pack_campaign_changed") from exc
    from carbon.development_session.data import write_once

    task_root = _owner_directory(result["artifact_path"], "task_artifacts")
    sidecar = task_root / "evaluation-pack-binding.json"
    document = {
        "schema": "carbon.lean-recipe.private-evaluation-pack-binding.v1",
        "task_id": submission_id,
        "challenge": {
            "id": adapter.challenge_id,
            "version": adapter.challenge_version,
        },
        "campaign_id": campaign_id,
        "evaluation_pack_digest": digest,
        "entry_id": result["entry_id"],
        "state_digest": task.terminal_receipt.state_digest,
        "predictions_digest": task.terminal_receipt.predictions_digest,
    }
    try:
        write_once(sidecar, _json(document))
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable("evaluation_pack_binding_unavailable") from exc
    return {
        **result,
        "evaluation_pack_digest": digest,
        "evaluation_pack_binding_path": sidecar,
    }


def _retain_public_synthetic_measurement(result, artifacts, submission_id):
    """Keep a separate private, descriptive v1.3 measurement beside the bank.

    Bank custody succeeds independently. A missing or invalid measurement is
    explicit and cannot change the immutable entry or its NOT_COMPUTED score.
    """
    from carbon.development_session.data import write_once
    from scripts.dev.score_lab.synthetic_linear_field_reference import (
        prepare_public_measurement,
        reduce_public_measurement,
    )

    try:
        task_root = _owner_directory(result["artifact_path"], "task_artifacts")
        entry_path = result["entry_path"]
        if entry_path.is_symlink() or not entry_path.is_file():
            raise ValueError("entry unavailable")
        entry = json.loads(entry_path.read_bytes())
        kit = json.loads(artifacts["construction-kit.json"])
        if (kit["id"], kit["version"]) != ("synthetic-linear-field-2d", "1.3"):
            return {**result, "measurement_state": "NOT_APPLICABLE"}
        if result.get("evaluation_pack_digest") is not None:
            return {**result, "measurement_state": "NOT_APPLICABLE"}
        sidecar_root = task_root.parent / (submission_id + ".public-measurement")
        sidecar_root.mkdir(mode=0o700, exist_ok=True)
        _owner_directory(sidecar_root, "public_measurement_directory")
        source_path = sidecar_root / "source-registration.json"
        receipt_path = sidecar_root / "source-receipt.json"
        reference_path = sidecar_root / "reference-row.json"
        result_path = sidecar_root / "result.json"
        if source_path.exists() or receipt_path.exists() or reference_path.exists():
            if not all(
                path.is_file() and not path.is_symlink()
                for path in (source_path, receipt_path, reference_path)
            ):
                raise ValueError("incomplete public source")
            source_raw = source_path.read_bytes()
            receipt_raw = receipt_path.read_bytes()
            reference_raw = reference_path.read_bytes()
        else:
            prepared = prepare_public_measurement(
                query_bytes=artifacts["inputs.npz"],
                model_device="C03_DOCKER_CPU_WORKER",
                reference_device="IN_PROCESS_NUMPY_CPU",
            )
            source_raw = prepared["source_registration_raw"]
            receipt_raw = prepared["source_receipt_raw"]
            reference_raw = prepared["reference_row_raw"]
            write_once(source_path, source_raw)
            write_once(receipt_path, receipt_raw)
            write_once(reference_path, reference_raw)
        worker = json.loads(artifacts["worker-evidence.json"])
        inference_receipt = json.loads(artifacts["inference-receipt.json"])
        inference = {
            "recipe_digest": entry["recipe_digest"],
            "state_digest": entry["state_digest"],
            "predictions_digest": entry["prediction_digest"],
            "predictions": json.loads(artifacts["predictions.json"]),
            "worker_operation": worker["inference_operation"],
            "receipt": inference_receipt,
            "inference_receipt_raw": artifacts["inference-receipt.json"],
            "worker_evidence_raw": artifacts["worker-evidence.json"],
        }
        custody_path = task_root.parent / (submission_id + ".custody.json")
        if custody_path.is_symlink() or not custody_path.is_file():
            raise ValueError("custody unavailable")
        reduced = reduce_public_measurement(
            entry=entry,
            custody_receipt_raw=custody_path.read_bytes(),
            source_registration_raw=source_raw,
            source_receipt_raw=receipt_raw,
            reference_row_raw=reference_raw,
            query_bytes=artifacts["inputs.npz"],
            inference=inference,
            graph_originals={
                "inference_receipt_raw": artifacts["inference-receipt.json"],
                "worker_evidence_raw": artifacts["worker-evidence.json"],
            },
        )
        document = {
            "schema": "carbon.lean-recipe.public-development-measurement.v1",
            "task_id": submission_id,
            "entry_id": result["entry_id"],
            **reduced,
        }
        write_once(result_path, _json(document))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            **result,
            "measurement_state": "UNAVAILABLE",
            "measurement_reason": type(exc).__name__,
        }
    return {
        **result,
        "measurement_state": "DEVELOPMENT_UNRANKED",
        "measurement_path": result_path,
    }


def retain_served_result(
    adapter, submission_id: str, *, artifact_directory: Path, entry_directory: Path
) -> dict:
    """Create one pending bank entry from trusted, already-successful task bytes.

    Directory arguments are selected by the operator, never from a submitted
    recipe or signed client request. Original files and manifests are create-only;
    an identical retry returns the existing entry. The bundle and graph source
    variants use the same create-only v5 bank; missing graph roles fail closed.
    """
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.data import write_once
    from carbon.development_session.library_bundles import (
        _context_digest,
        bundle_ref,
        load_cached_bundle_material,
    )
    from carbon.research import (
        DirectGetTaskRequestV3,
        DirectTaskStateV3,
        ResearchTaskId,
        canonical_bytes,
    )

    if type(adapter) is not LeanRecipeAdapter or type(submission_id) is not str:
        raise TypeError("trusted served adapter and task identity required")
    if re.fullmatch(r"rtsk_[0-9a-f]{64}", submission_id) is None:
        raise RetentionUnavailable("task_identity_invalid")
    owner = adapter.owner(submission_id)
    if owner is None:
        raise RetentionUnavailable("owned_task_unavailable")
    provider = adapter._provider(owner)
    task_id = ResearchTaskId(submission_id)
    task = provider.get_research_result(
        DirectGetTaskRequestV3(adapter.discovery.info.challenge_key, task_id)
    ).task
    if task.state is not DirectTaskStateV3.SUCCEEDED:
        raise RetentionUnavailable("task_not_succeeded")
    try:
        evidence = provider.private_attempt(task_id)
    except ValueError as exc:
        raise RetentionUnavailable("verified_attempt_unavailable") from exc
    if evidence is None:
        raise RetentionUnavailable("verified_attempt_unavailable")
    recipe = ConstructionRecipe.from_dict(provider._requests[submission_id].recipe)
    if recipe.to_dict()["source"]["kind"] == "graph":
        artifacts = _collect_graph_artifacts(
            provider, submission_id, task, evidence, recipe, adapter.discovery._material
        )
        result = _retain_graph_artifacts(
            artifacts,
            submission_id,
            artifact_directory=artifact_directory,
            entry_directory=entry_directory,
        )
        bound = _retain_private_pack_binding(
            adapter, provider, submission_id, task, result
        )
        return _retain_public_synthetic_measurement(bound, artifacts, submission_id)
    if recipe.to_dict()["source"]["kind"] != "bundle":
        raise RetentionUnavailable("source_kind_unavailable")
    admitted_binding = provider._task_image_bindings.get(submission_id)
    if provider.image_resolver is not None and admitted_binding is None:
        raise RetentionUnavailable("admitted_image_binding_unavailable")
    overlay = evidence.get("schema") == "carbon.direct-private-attempt.overlay.v1"
    if overlay:
        from carbon.development_session.library_bundles import (
            LibraryBundleRef,
            load_pinned_bundle_directory,
            verify_bundle_parent_environment,
        )
        from carbon.development_session.library_environment_cache import (
            _verified_overlay_tree,
            inspect_staged_bundle_material,
        )

        try:
            selected = LibraryBundleRef.from_dict(
                recipe.to_dict()["source"]["bundle_ref"]
            )
            binding = json.loads(admitted_binding)
            receipt = evidence["prep_receipt"]
            if (
                type(binding) is not list
                or len(binding) != 2
                or binding[0] != "BUNDLE_OVERLAY"
                or type(binding[1]) is not dict
                or binding[1]
                != {
                    "parent_image_id": provider.construction_parent.image_id,
                    "bundle_ref": selected.to_dict(),
                    "tree_digest": evidence["overlay_tree_digest"],
                    "archive_digest": evidence["overlay_archive_digest"],
                }
                or receipt.get("bundle_ref") != selected.to_dict()
                or receipt.get("parent_image_id")
                != provider.construction_parent.image_id
                or receipt.get("tree_digest") != evidence["overlay_tree_digest"]
                or receipt.get("archive_sha256") != evidence["overlay_archive_digest"]
                or evidence.get("image_id") != provider.construction_parent.image_id
                or evidence.get("parent_image_id")
                != provider.construction_parent.image_id
                or evidence.get("inference_image_id")
                != provider.inference_image.image_id
                or any(
                    type(evidence.get(name)) is not str
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", evidence[name]) is None
                    for name in ("overlay_tree_digest", "overlay_archive_digest")
                )
                or re.fullmatch(r"operation-[0-9a-f]{64}", evidence["prep_operation"])
                is None
            ):
                raise ValueError("admitted overlay identity changed")
            cache_root = provider.image_resolver.cache_root
            directory = inspect_staged_bundle_material(cache_root, selected)
            manifest, source, wheels, lock, license_text = load_pinned_bundle_directory(
                directory
            )
            verify_bundle_parent_environment(manifest, provider.construction_parent)
            if bundle_ref(manifest, source, wheels, lock, license_text) != selected:
                raise ValueError("staged bundle identity changed")
            manifest_raw = (directory / "bundle.json").read_bytes()
            prep = provider.ledger.root / evidence["prep_operation"] / "snapshot"
            _receipt_snapshot(prep / "overlay.json", receipt, "prep_receipt")
            _snapshot(
                prep / "overlay.tar",
                limit=128 * 1024**2,
                digest=evidence["overlay_archive_digest"],
                label="prep_archive",
            )
            target = cache_root / "overlays"
            for identity in (
                selected.bundle_digest,
                provider.construction_parent.image_id,
                evidence["overlay_archive_digest"],
                evidence["overlay_tree_digest"],
            ):
                target = target / identity[7:]
            if target.is_symlink() or not target.is_dir():
                raise ValueError("cached overlay unavailable")
            _verified_overlay_tree(target, receipt)
            image_record = {
                "parent_image_id": provider.construction_parent.image_id,
                "bundle_digest": selected.bundle_digest,
                "overlay_tree_digest": evidence["overlay_tree_digest"],
                "overlay_archive_digest": evidence["overlay_archive_digest"],
            }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RetentionUnavailable("source_overlay_unavailable") from exc
    else:
        try:
            image = provider._resolved_image(provider._requests[submission_id])
        except (FileNotFoundError, ValueError) as exc:
            raise RetentionUnavailable("source_image_unavailable") from exc
        if (
            admitted_binding is not None
            and provider._image_binding(image) != admitted_binding
        ) or any(
            evidence.get(field) != value
            for field, value in (
                ("image_id", image.image_id),
                ("parent_image_id", image.parent.image_id),
                ("inference_image_id", provider.inference_image.image_id),
                ("context_digest", image.provisioned.context_digest),
                ("bundle_digest", image.provisioned.bundle.bundle_digest),
            )
        ):
            raise RetentionUnavailable("admitted_image_changed")
        context = image.provisioned.context
        try:
            if context.is_symlink() or not context.is_dir():
                raise ValueError("context unavailable")
            if _context_digest(context) != image.provisioned.context_digest:
                raise ValueError("context changed")
            manifest_raw = (context / "bundle.json").read_bytes()
            manifest = json.loads(manifest_raw)
            source, wheels, lock, license_text = load_cached_bundle_material(
                context, manifest
            )
            if (
                bundle_ref(manifest, source, wheels, lock, license_text)
                != image.provisioned.bundle
                or image.provisioned.bundle.to_dict()
                != recipe.to_dict()["source"]["bundle_ref"]
            ):
                raise ValueError("bundle ref changed")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RetentionUnavailable("source_context_unavailable") from exc
        image_record = {
            "image_id": image.image_id,
            "parent_image_id": image.parent.image_id,
            "context_digest": image.provisioned.context_digest,
        }

    root = provider.ledger.root
    if any(
        re.fullmatch(r"operation-[0-9a-f]{64}", evidence[name]) is None
        for name in ("build_operation", "inference_operation")
    ):
        raise RetentionUnavailable("worker_operation_invalid")
    build = root / evidence["build_operation"] / "snapshot"
    inference = root / evidence["inference_operation"] / "snapshot"
    state = _snapshot(
        build / "state.npz",
        limit=64 * 1024**2,
        digest=task.terminal_receipt.state_digest,
        label="state_snapshot",
    )
    predictions = _snapshot(
        inference / "predictions.json",
        limit=16 * 1024**2,
        digest=task.terminal_receipt.predictions_digest,
        label="prediction_snapshot",
    )
    build_receipt = _receipt_snapshot(
        build / "receipt.json", evidence["build_receipt"], "build_receipt"
    )
    inference_receipt = _receipt_snapshot(
        inference / "receipt.json",
        evidence["inference_receipt"],
        "inference_receipt",
    )
    material = adapter.discovery._material
    train = material["train"]
    if _sha(train) != recipe.to_dict()["challenge"]["train_digest"]:
        raise RetentionUnavailable("public_train_changed")
    from carbon.battery import challenge as battery_challenge

    battery = adapter.discovery.info.challenge_key == battery_challenge.CHALLENGE
    if battery and _sha(train) != "sha256:" + battery_challenge.TRAIN_V1_SHA256:
        raise RetentionUnavailable("public_battery_train_changed")
    train_name = "train-v1.jsonl.gz" if battery else "train.npz"
    train_codec = "raw_bytes" if battery else "numeric_npz"
    public_scope = (
        "PUBLIC_BATTERY_DEVELOPMENT_ONLY"
        if battery
        else "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"
    )
    if "practice_inputs" not in material or "practice_reference" not in material:
        raise RetentionUnavailable("public_input_target_unavailable")
    inputs = _tensors(inputs=material["practice_inputs"])
    fixture = _tensors(
        inputs=material["practice_inputs"],
        targets=material["practice_reference"],
    )
    if evidence["inference_receipt"]["inputs_digest"] != _sha(inputs):
        raise RetentionUnavailable("practice_inputs_changed")

    artifacts = {
        "recipe.json": recipe.canonical_bytes,
        train_name: train,
        "fixture.npz": fixture,
        "inputs.npz": inputs,
        "state.npz": state,
        "predictions.json": predictions,
        "source.tar.gz": source,
        "environment.json": manifest_raw,
        "image.json": _json(image_record),
        "build-receipt.json": build_receipt,
        "inference-receipt.json": inference_receipt,
        "task-receipt.json": canonical_bytes(task.terminal_receipt),
        "lineage.json": _json(
            {
                "schema": "carbon.lean-recipe-bank-lineage.v1",
                "scope": public_scope,
                "task_id": submission_id,
                "recipe_digest": recipe.digest,
                "state_digest": task.terminal_receipt.state_digest,
                "prediction_digest": task.terminal_receipt.predictions_digest,
                "build_operation": evidence["build_operation"],
                "inference_operation": evidence["inference_operation"],
                "official_eligible": False,
            }
        ),
    }
    roles = {
        "recipe": ("recipe.json", "json"),
        "train": (train_name, train_codec),
        "fixture": ("fixture.npz", "numeric_npz"),
        "inputs": ("inputs.npz", "numeric_npz"),
        "state": ("state.npz", "bundle_graph_npz"),
        "predictions": ("predictions.json", "json"),
        "source": ("source.tar.gz", "raw_bytes"),
        "environment": ("environment.json", "raw_bytes"),
        "image": ("image.json", "json"),
        "build_receipt": ("build-receipt.json", "json"),
    }
    if evidence["build_receipt"].get("schema") == "carbon.development.bundle-build.v2":
        from carbon.development_session.bundle_construction_worker import (
            BundleBuildResult,
            BundleInferenceResult,
            compare_build_inference_predictions,
        )

        native = _snapshot(
            build / "native-predictions.json",
            limit=16 * 1024**2,
            digest=evidence["build_receipt"]["native_predictions_digest"],
            label="native_prediction_snapshot",
        )
        example_path = root / evidence["build_operation"] / "input" / "example.npz"
        if example_path.exists() or example_path.is_symlink():
            example = _snapshot(
                example_path,
                limit=16 * 1024**2,
                digest=evidence["build_receipt"]["example_digest"],
                label="build_example_snapshot",
            )
        else:
            # Legacy local runners retain only the output snapshot. Their
            # trusted example may stand in only at the exact worker receipt
            # digest; a distinct or changed probe remains unavailable.
            example = _tensors(inputs=material["example"])
            if _sha(example) != evidence["build_receipt"]["example_digest"]:
                raise RetentionUnavailable("build_example_snapshot_unavailable")
        artifacts["native-predictions.json"] = native
        artifacts["example.npz"] = example
        roles["native_predictions"] = ("native-predictions.json", "json")
        try:
            comparison = compare_build_inference_predictions(
                BundleBuildResult(
                    recipe.digest,
                    task.terminal_receipt.state_digest,
                    build / "state.npz",
                    evidence["build_operation"],
                    evidence["build_receipt"],
                ),
                BundleInferenceResult(
                    recipe.digest,
                    task.terminal_receipt.state_digest,
                    task.terminal_receipt.predictions_digest,
                    json.loads(predictions),
                    evidence["inference_operation"],
                    evidence["inference_receipt"],
                ),
                expected_output_dtype=material["interface_document"]["outputs"][
                    "dtype"
                ],
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise RetentionUnavailable("native_comparison_unavailable") from exc
        if comparison is None or (
            "prediction_comparison" in evidence
            and evidence["prediction_comparison"] != comparison
        ):
            raise RetentionUnavailable("native_comparison_changed")
        artifacts["prediction-comparison.json"] = _json(comparison)
    # Measured v2 is kept verbatim, never relabeled as the bank's v1 role.
    if (
        evidence["inference_receipt"]["schema"]
        == "carbon.development.bundle-inference.v1"
    ):
        roles["inference_receipt"] = ("inference-receipt.json", "json")
    role_manifest = {
        "schema": "carbon.scorelab.public-model-artifact-roles.v2",
        "scope": "PUBLIC_DEVELOPMENT_BUNDLE_MODEL",
        "source_schema": "carbon.development.bundle-graph-state.v1",
        "roles": {
            role: {"file": name, "codec": codec}
            for role, (name, codec) in sorted(roles.items())
        },
        "retained_files": {name: _sha(raw) for name, raw in sorted(artifacts.items())},
        "physics_contract": material.get("physics_contract"),
    }

    # Workbench imports occur only after a trusted operator invokes retention.
    from scripts.dev.score_lab.public_unbound_custody import prepare_custody_v5
    from scripts.dev.score_lab.public_unbound_entry import create_entry_v5

    base = _owner_directory(artifact_directory, "artifact_directory")
    entries = _owner_directory(entry_directory, "entry_directory")
    task_root = base / submission_id
    task_root.mkdir(mode=0o700, exist_ok=True)
    _owner_directory(task_root, "task_artifacts")
    try:
        for name, raw in artifacts.items():
            write_once(task_root / name, raw)
        manifest_path = base / (submission_id + ".roles.json")
        write_once(manifest_path, _json(role_manifest))
        custody = prepare_custody_v5(task_root, manifest_path)
        custody_path = base / (submission_id + ".custody.json")
        write_once(custody_path, _json(custody))
        saved = create_entry_v5(task_root, manifest_path, custody_path, entries)
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable("operator_bank_custody_unavailable") from exc
    result = {
        "status": saved["status"],
        "entry_id": saved["entry"]["entry_id"],
        "entry_path": entries / saved["path"],
        "artifact_path": task_root,
        "score_state": saved["entry"]["score_state"],
        "official_eligible": False,
    }
    return _retain_private_pack_binding(adapter, provider, submission_id, task, result)


def retain_served_bundle_result(
    adapter, submission_id: str, *, artifact_directory: Path, entry_directory: Path
) -> dict:
    """Compatibility name for the original bundle-only operator call site."""
    return retain_served_result(
        adapter,
        submission_id,
        artifact_directory=artifact_directory,
        entry_directory=entry_directory,
    )


def register_served_pack_source(
    adapter,
    submission_id: str,
    *,
    artifact_directory: Path,
    entry_directory: Path,
    trusted_job: dict,
    registration: dict,
    ordered_query_bytes: list[bytes],
    evaluation_version: str,
    hidden_store=None,
    fingerprint=None,
    expected_references_digest=None,
) -> dict:
    """Register actual v2 source bytes under an already retained private task.

    The selected pack comes from receiver admission, and reference rows and
    ScorePack are read again from its verified private roles. The returned
    source pin is read back from owner-only write-once custody; callers pass
    that registered value to the existing private ScoreLab binder.
    """
    from carbon.challenge_validator.evaluation_pack import PRIVATE_ROLES
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.data import write_once
    from carbon.scoring.engine import ScoreEngine
    from carbon.scoring.private_evaluation_source import (
        PrivateEvaluationSourceRefused,
        build_pack_source_receipt,
    )
    from carbon.scoring.solver_benchmark_v3 import (
        BenchmarkScoreRefused,
        register_pack,
    )

    if type(adapter) is not LeanRecipeAdapter or type(submission_id) is not str:
        raise TypeError("trusted served adapter and task identity required")
    discovery = adapter.discovery
    snapshot = discovery.evaluation_pack_snapshot
    if snapshot is None or discovery.evaluation_pack_digest != snapshot.manifest_digest:
        raise RetentionUnavailable("evaluation_pack_not_selected")
    retained = retain_served_result(
        adapter,
        submission_id,
        artifact_directory=artifact_directory,
        entry_directory=entry_directory,
    )
    if retained.get("evaluation_pack_digest") != snapshot.manifest_digest:
        raise RetentionUnavailable("evaluation_pack_retention_changed")
    public_root = discovery.evaluation_pack_public_root
    private_root = discovery.evaluation_pack_private_root
    try:
        missing = snapshot.verify_available(
            public_root, private_root, hidden_store=hidden_store
        )
        if (
            set(missing["public"])
            & {"construction_kit", "interface", "train", "physics_contract"}
            or set(missing["private"]) & PRIVATE_ROLES
        ):
            raise RetentionUnavailable("evaluation_pack_roles_unavailable")
        # This caller only has the registered single-query, static-bank
        # contract. A dynamic bank needs its own Challenge-specific adapter.
        if (
            snapshot.run_bindings_required()
            or snapshot.private["case_bank"].get("kind") == "hidden_batch_store"
        ):
            raise RetentionUnavailable("evaluation_pack_bank_adapter_unavailable")
        train = snapshot.read_role(
            public_root, "public", "train", max_bytes=16 * 1024 * 1024
        )
        interface = snapshot.read_role(
            public_root, "public", "interface", max_bytes=65536
        )
        physics = snapshot.read_json_role(
            public_root, "public", "physics_contract", max_bytes=65536
        )
        case_bank = snapshot.read_role(
            private_root, "private", "case_bank", max_bytes=16 * 1024 * 1024
        )
        solver = snapshot.read_json_role(
            private_root, "private", "solver_evidence", max_bytes=65536
        )
        references = snapshot.read_json_role(
            private_root, "private", "reference_rows", max_bytes=16 * 1024 * 1024
        )
        score_document = snapshot.read_json_role(
            private_root, "private", "score_pack", max_bytes=65536
        )
    except RetentionUnavailable:
        raise
    except ValueError as exc:
        raise RetentionUnavailable("evaluation_pack_material_unavailable") from exc
    if type(references) is not list or type(registration) is not dict:
        raise RetentionUnavailable("evaluation_pack_reference_rows_invalid")
    reference_identity = registration.get("reference")
    if (
        type(trusted_job) is not dict
        or _sha(train) != trusted_job.get("train_digest")
        or _sha(interface) != trusted_job.get("interface_digest")
        or physics != trusted_job.get("physics_contract")
        or type(ordered_query_bytes) is not list
        or len(ordered_query_bytes) != 1
        or type(ordered_query_bytes[0]) is not bytes
        or case_bank != ordered_query_bytes[0]
        or type(reference_identity) is not dict
        or type(solver) is not dict
        or solver != reference_identity
    ):
        raise RetentionUnavailable("evaluation_pack_registered_material_mismatch")
    if type(score_document) is not dict:
        raise RetentionUnavailable("evaluation_pack_score_pack_invalid")
    declared_pack_digest = score_document.get("pack_digest")
    body = {key: value for key, value in score_document.items() if key != "pack_digest"}
    try:
        score_pack = register_pack(body)
    except BenchmarkScoreRefused as exc:
        raise RetentionUnavailable("evaluation_pack_score_pack_invalid") from exc
    if (
        declared_pack_digest is not None
        and declared_pack_digest != score_pack["pack_digest"]
    ):
        raise RetentionUnavailable("evaluation_pack_score_pack_invalid")
    if (
        score_pack["challenge"] != snapshot.challenge_id
        or score_pack["benchmark_registration_digest"]
        != registration.get("registration_digest")
        or score_pack["accuracy_ceiling"] is None
    ):
        raise RetentionUnavailable("evaluation_pack_score_pack_unready")
    entry_path = Path(retained["entry_path"])
    if (
        entry_path.is_symlink()
        or not entry_path.is_file()
        or entry_path.stat().st_size > 1024 * 1024
    ):
        raise RetentionUnavailable("evaluation_pack_entry_unavailable")
    try:
        entry = json.loads(entry_path.read_bytes())
    except (UnicodeError, ValueError) as exc:
        raise RetentionUnavailable("evaluation_pack_entry_unavailable") from exc
    if type(entry) is not dict or entry.get("entry_id") != retained["entry_id"]:
        raise RetentionUnavailable("evaluation_pack_entry_changed")
    try:
        prepared = build_pack_source_receipt(
            selected_pack=snapshot,
            entry=entry,
            trusted_job=trusted_job,
            registration=registration,
            references=references,
            ordered_query_bytes=ordered_query_bytes,
            evaluation_version=evaluation_version,
        )
    except PrivateEvaluationSourceRefused as exc:
        raise RetentionUnavailable("evaluation_pack_source_" + exc.code) from exc
    try:
        public_rule = ScoreEngine.public_solver_benchmark_rule_v3(
            registration, score_pack
        )
    except BenchmarkScoreRefused as exc:
        raise RetentionUnavailable("evaluation_pack_public_rule_invalid") from exc
    task_root = _owner_directory(retained["artifact_path"], "task_artifacts")
    source_path = task_root / "evaluation-source-receipt.json"
    registration_path = task_root / "evaluation-source-registration.json"
    try:
        write_once(source_path, prepared.raw)
        if source_path.is_symlink():
            raise ValueError("source receipt link")
        registered_sha256 = _sha(source_path.read_bytes())
        if registered_sha256 != prepared.sha256:
            raise ValueError("source receipt changed")
        write_once(
            registration_path,
            _json(
                {
                    "schema": "carbon.lean-recipe.private-source-registration.v2",
                    "task_id": submission_id,
                    "entry_id": retained["entry_id"],
                    "evaluation_pack_digest": snapshot.manifest_digest,
                    "source_receipt_sha256": registered_sha256,
                    "registration_digest": registration["registration_digest"],
                }
            ),
        )
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable(
            "evaluation_pack_source_registration_unavailable"
        ) from exc
    return {
        "entry": entry,
        "retained": retained,
        "references": references,
        "score_pack": score_pack,
        "public_rule_definition": public_rule,
        "evaluation_source_receipt_raw": source_path.read_bytes(),
        "registered_source_receipt_sha256": registered_sha256,
        "expected_evaluation_pack_digest": snapshot.manifest_digest,
        "source_registration_path": registration_path,
    }
