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
        return _retain_private_pack_binding(
            adapter, provider, submission_id, task, result
        )
    if recipe.to_dict()["source"]["kind"] != "bundle":
        raise RetentionUnavailable("source_kind_unavailable")
    try:
        image = provider._resolved_image(provider._requests[submission_id])
    except (FileNotFoundError, ValueError) as exc:
        raise RetentionUnavailable("source_image_unavailable") from exc
    admitted_binding = provider._task_image_bindings.get(submission_id)
    if provider.image_resolver is not None and admitted_binding is None:
        raise RetentionUnavailable("admitted_image_binding_unavailable")
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
        "train.npz": train,
        "fixture.npz": fixture,
        "inputs.npz": inputs,
        "state.npz": state,
        "predictions.json": predictions,
        "source.tar.gz": source,
        "environment.json": manifest_raw,
        "image.json": _json(
            {
                "image_id": image.image_id,
                "parent_image_id": image.parent.image_id,
                "context_digest": image.provisioned.context_digest,
            }
        ),
        "build-receipt.json": build_receipt,
        "inference-receipt.json": inference_receipt,
        "task-receipt.json": canonical_bytes(task.terminal_receipt),
        "lineage.json": _json(
            {
                "schema": "carbon.lean-recipe-bank-lineage.v1",
                "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
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
        "train": ("train.npz", "numeric_npz"),
        "fixture": ("fixture.npz", "numeric_npz"),
        "inputs": ("inputs.npz", "numeric_npz"),
        "state": ("state.npz", "bundle_graph_npz"),
        "predictions": ("predictions.json", "json"),
        "source": ("source.tar.gz", "raw_bytes"),
        "environment": ("environment.json", "raw_bytes"),
        "image": ("image.json", "json"),
        "build_receipt": ("build-receipt.json", "json"),
    }
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
