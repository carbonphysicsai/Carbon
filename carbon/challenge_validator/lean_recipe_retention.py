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
from dataclasses import asdict, dataclass
from pathlib import Path

from carbon.challenge_kit.interface_dtype import output_dtype


class RetentionUnavailable(ValueError):
    """The named original-byte or custody dependency is unavailable."""


#: Custody reads a state the worker already admitted under its version's
#: ceiling (`bundle_graph_state.state_limit`: none for an uncapped version), so
#: the bound here is the worker's registered output envelope, what any build
#: could have written, never a model-size rule of its own.
_STATE_CUSTODY_BYTES = 128 * 1024**2  # carbon.reconstruction.worker.model.OUTPUT_BYTES


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
    # A measured graph keeps its batched cold query as a separate timed receipt.
    timed_fields = (
        {"timed_operation", "timed_receipt"}
        if type(evidence) is dict and "timed_receipt" in evidence
        else set()
    )
    if (
        type(evidence) is not dict
        or set(evidence) != worker_fields | timed_fields | {"predictions"}
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
        limit=_STATE_CUSTODY_BYTES,
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
    timed_receipt = None
    if timed_fields:
        if (
            type(evidence["timed_operation"]) is not str
            or re.fullmatch(r"operation-[0-9a-f]{64}", evidence["timed_operation"])
            is None
        ):
            raise RetentionUnavailable("timed_operation_invalid")
        timed_receipt = _receipt_snapshot(
            root / evidence["timed_operation"] / "snapshot" / "receipt.json",
            evidence["timed_receipt"],
            "timed_receipt",
        )
        # The timed run's own outputs, for the producer's agreement check.
        timed_predictions = _snapshot(
            root / evidence["timed_operation"] / "snapshot" / "predictions.json",
            limit=16 * 1024**2,
            digest=evidence["timed_receipt"].get("predictions_digest"),
            label="timed_prediction_snapshot",
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
        **(
            {}
            if timed_receipt is None
            else {
                "timed-query-receipt.json": timed_receipt,
                "timed-query-predictions.json": timed_predictions,
            }
        ),
    }
    return artifacts


def _retain_graph_artifacts(
    artifacts, submission_id, *, artifact_directory, entry_directory
):
    from carbon.development_session.data import write_once

    try:
        from scripts.dev.score_lab.public_unbound_custody import (
            GRAPH_ROLE_SCHEMA_V5,
            prepare_custody_v5,
        )
        from scripts.dev.score_lab.public_unbound_entry import create_entry_v5
    except ImportError as exc:
        raise RetentionUnavailable("graph_bank_role_contract_unavailable") from exc
    if GRAPH_ROLE_SCHEMA_V5 != "carbon.scorelab.public-model-artifact-roles.v5":
        raise RetentionUnavailable("graph_bank_role_contract_unavailable")
    # Graded one case at a time, as a bundle is; timing is the timed query's.
    if json.loads(artifacts["inference-receipt.json"]).get("schema") != (
        "carbon.development.bundle-inference.v1"
    ):
        raise RetentionUnavailable("graph_per_case_receipt_unavailable")
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
        **(
            {"timed_receipt": ("timed-query-receipt.json", "json")}
            if "timed-query-receipt.json" in artifacts
            else {}
        ),
    }
    role_manifest = {
        "schema": GRAPH_ROLE_SCHEMA_V5,
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


def _private_evaluation_directory(result, submission_id):
    if (
        type(submission_id) is not str
        or re.fullmatch(r"rtsk_[0-9a-f]{64}", submission_id) is None
    ):
        raise RetentionUnavailable("task_identity_invalid")
    task_root = _owner_directory(result["artifact_path"], "task_artifacts")
    directory = task_root.parent / (submission_id + ".evaluation")
    directory.mkdir(mode=0o700, exist_ok=True)
    return _owner_directory(directory, "private_evaluation_directory")


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

    directory = _private_evaluation_directory(result, submission_id)
    sidecar = directory / "evaluation-pack-binding.json"
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


def _private_measurement_bytes(path, limit):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise RetentionUnavailable("public_measurement_bytes_unavailable")
    return path.read_bytes()


def _retain_public_synthetic_measurement(result, artifacts, submission_id, evidence):
    """Keep a separate private, descriptive v1.3 measurement beside the bank.

    Bank custody succeeds independently. A missing or invalid measurement is
    explicit and cannot change the immutable entry or its NOT_COMPUTED score.
    """
    try:
        task_root = _owner_directory(result["artifact_path"], "task_artifacts")
        entry = json.loads(_private_measurement_bytes(result["entry_path"], 1024**2))
        graph = "worker-evidence.json" in artifacts
        kit = (
            json.loads(artifacts["construction-kit.json"])
            if graph
            else json.loads(artifacts["recipe.json"])["challenge"]
        )
        if (kit["id"], kit["version"]) != ("synthetic-linear-field-2d", "1.3"):
            return result
        if result.get("evaluation_pack_digest") is not None:
            return result
        from carbon.development_session.data import write_once
        from scripts.dev.score_lab.synthetic_linear_field_reference import (
            prepare_public_measurement,
            reduce_public_measurement,
        )

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
            source_raw = _private_measurement_bytes(source_path, 1024**2)
            receipt_raw = _private_measurement_bytes(receipt_path, 1024**2)
            reference_raw = _private_measurement_bytes(reference_path, 1024**2)
        else:
            if (
                type(evidence) is not dict
                or type(evidence.get("inference_image_id")) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["inference_image_id"])
                is None
            ):
                raise ValueError("inference image identity unavailable")
            prepared = prepare_public_measurement(
                query_bytes=artifacts["inputs.npz"],
                model_device="C03_DOCKER_IMAGE_" + evidence["inference_image_id"],
                reference_device="IN_PROCESS_NUMPY_CPU",
            )
            source_raw = prepared["source_registration_raw"]
            receipt_raw = prepared["source_receipt_raw"]
            reference_raw = prepared["reference_row_raw"]
            write_once(source_path, source_raw)
            write_once(receipt_path, receipt_raw)
            write_once(reference_path, reference_raw)
        worker = json.loads(artifacts["worker-evidence.json"]) if graph else evidence
        # The measurement belongs to the batched cold query kept for timing; a
        # graph binds its graded receipt and passes that query separately.
        timed_query = (
            {
                "receipt_raw": artifacts["timed-query-receipt.json"],
                "registered_sha256": _sha(artifacts["timed-query-receipt.json"]),
            }
            if graph and "timed-query-receipt.json" in artifacts
            else None
        )
        inference_receipt = json.loads(
            artifacts["inference-receipt.json"]
            if graph
            else artifacts.get(
                "timed-query-receipt.json", artifacts["inference-receipt.json"]
            )
        )
        inference = {
            "recipe_digest": entry["recipe_digest"],
            "state_digest": entry["state_digest"],
            "predictions_digest": entry["prediction_digest"],
            "predictions": json.loads(artifacts["predictions.json"]),
            "worker_operation": worker["inference_operation"],
            "receipt": inference_receipt,
        }
        if graph:
            inference["inference_receipt_raw"] = artifacts["inference-receipt.json"]
            inference["worker_evidence_raw"] = artifacts["worker-evidence.json"]
        custody_path = task_root.parent / (submission_id + ".custody.json")
        reduced = reduce_public_measurement(
            entry=entry,
            custody_receipt_raw=_private_measurement_bytes(custody_path, 1024**2),
            source_registration_raw=source_raw,
            source_receipt_raw=receipt_raw,
            reference_row_raw=reference_raw,
            query_bytes=artifacts["inputs.npz"],
            inference=inference,
            graph_originals=(
                {
                    "inference_receipt_raw": artifacts["inference-receipt.json"],
                    "worker_evidence_raw": artifacts["worker-evidence.json"],
                    **({} if timed_query is None else {"timed_query": timed_query}),
                }
                if graph
                else None
            ),
            timed_query=timed_query,
        )
        document = {
            "schema": "carbon.lean-recipe.public-development-measurement.v1",
            "task_id": submission_id,
            "entry_id": result["entry_id"],
            **reduced,
        }
        write_once(result_path, _json(document))
    except (ImportError, OSError, ValueError, KeyError, TypeError) as exc:
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


def _inference_pair_raw(adapter, submission_id, result, artifacts, entry, regrade=None):
    """The two fresh repeat queries of the retained model, kept write-once beside
    the dual measurement. Two new carrier operations with new identities; a
    retry reads the retained bytes and never replays an identity."""
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.data import write_once
    from carbon.development_session.paired_inference import (
        InferencePairFailure,
        infer_frozen_pair,
    )

    path = _private_evaluation_directory(result, submission_id) / "inference-pair.json"
    if path.exists() or path.is_symlink():
        return _private_measurement_bytes(path, 1024**2)
    owner = adapter.owner(submission_id) if regrade is None else regrade.owner
    provider = adapter._provider(owner)
    material = adapter.discovery._material
    kit = material["construction_kit"]
    limits = material["construction_limits_document"]
    policy = limits["reconstruction_resource_policy"]
    interface = material["interface_document"]
    # The selected pack's public accuracy definition registers the repeat form.
    accuracy = adapter.discovery.evaluation_pack_snapshot.read_json_role(
        adapter.discovery.evaluation_pack_public_root,
        "public",
        "accuracy_definition",
        max_bytes=65536,
    )
    if type(accuracy) is not dict:
        raise RetentionUnavailable("inference_pair_procedure_unreadable")
    try:
        pair = infer_frozen_pair(
            provider.ledger,
            owner=owner,
            identity="pair-"
            + adapter.discovery.evaluation_pack_snapshot.manifest_digest
            + "-"
            + submission_id,
            inference_image=provider.inference_image,
            recipe=(
                ConstructionRecipe.from_dict(provider._requests[submission_id].recipe)
                if regrade is None
                else regrade.recipe
            ),
            challenge_binding={
                "challenge_id": kit["id"],
                "challenge_version": kit["version"],
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            },
            limits_document=limits,
            state_bytes=artifacts["state.npz"],
            expected_state_digest=entry["state_digest"],
            inputs=material["practice_inputs"],
            expected_output_shape=tuple(material["expected_output_shape"]),
            expected_output_dtype=output_dtype(interface),
            allowlist_bytes=material["allowlist_bytes"],
            seconds=policy["inference_wall_seconds_max"],
            total_seconds=policy["total_reconstruction_wall_seconds_max"],
            accelerator=getattr(provider, "inference_accelerator", None),
            procedure=accuracy.get("paired_repeat_procedure", "batched_measured"),
        )
    except InferencePairFailure as failure:
        raise RetentionUnavailable("inference_pair_incomplete") from failure
    raw = _json(pair.evidence)
    write_once(path, raw)
    return raw


def _retain_selected_pack_evaluation(
    adapter,
    submission_id,
    result,
    artifacts,
    evidence=None,
    regrade=None,
    pool_store=None,
):
    """Apply only trusted, versioned measurement evidence after bank custody."""
    if result.get("evaluation_pack_digest") is None:
        return result
    cap = reservation = None
    try:
        from carbon.development_session.data import write_once
        from carbon.scoring import dual_score
        from carbon.scoring.engine import ScoreEngine
        from carbon.scoring.private_evaluation_evidence import (
            bind_private_evaluation_evidence,
        )

        discovery = adapter.discovery
        snapshot = discovery.evaluation_pack_snapshot
        private_root = discovery.evaluation_pack_private_root
        score_document = snapshot.read_json_role(
            private_root, "private", "score_pack", max_bytes=65536
        )
        if (
            type(score_document) is not dict
            or score_document.get("schema") != dual_score.PACK_SCHEMA
        ):
            return result
        graph = "worker-evidence.json" in artifacts
        if not graph and (
            type(evidence) is not dict
            or type(evidence.get("inference_operation")) is not str
            or type(evidence.get("inference_image_id")) is not str
        ):
            raise RetentionUnavailable("dual_model_originals_unavailable")
        from carbon.scoring import battery_dual_pack, physical_adapters
        from carbon.scoring.private_evaluation_source import (
            produce_registered_dual_measurement,
        )

        # Validator-only: Battery's adapter is never imported by the shared
        # dispatch, which miner surfaces reach (physical_adapters).
        physical_adapters.register(battery_dual_pack)

        source = snapshot.read_source_registration(private_root)
        # The daily allowance, the epoch limit and the exam key's age refuse here, before
        # any grading (and so before any exam wear); the slot is settled once the
        # outcome is known.
        from carbon.challenge_validator import exam_cap

        # Recovery of crashed reservations runs at receiver start-up, never here.
        cap = exam_cap.ExamCap(
            adapter.ledger, cadence=getattr(adapter, "exam_cadence", None)
        )
        reservation = cap.reserve(
            hotkey=adapter.owner(submission_id) if regrade is None else regrade.owner,
            challenge_id=adapter.challenge_id,
            challenge_version=adapter.challenge_version,
            # The sealed exam's identity: the pack digest binds the case bank, so a
            # rotation that changes the bank starts new counts.
            exam_key=snapshot.manifest_digest,
            submission_id=submission_id,
            block=(
                exam_cap.submission_block(
                    adapter.ledger, adapter.contract_digest, submission_id
                )
                if regrade is None
                else None
            ),
            regrade=regrade is not None,
        )
        queries = [artifacts["inputs.npz"]]
        registered = _register_retained_pack_source(
            adapter,
            submission_id,
            result,
            trusted_job=source["trusted_job"],
            registration=source["benchmark_registration"],
            ordered_query_bytes=queries,
            evaluation_version=source["evaluation_version"],
        )
        if graph:
            originals = {
                "inference_receipt_raw": artifacts["inference-receipt.json"],
                "worker_evidence_raw": artifacts["worker-evidence.json"],
            }
        else:
            # A bundle has no worker-evidence.json: its originals are the inference
            # receipt, the predictions and the trusted task evidence's identities.
            originals = {
                "inference_receipt_raw": artifacts["inference-receipt.json"],
                "predictions_raw": artifacts["predictions.json"],
                "bundle_evidence_raw": _json(
                    {
                        "schema": "carbon.lean-recipe.bundle-inference-evidence.v1",
                        "inference_operation": evidence["inference_operation"],
                        "inference_image_id": evidence["inference_image_id"],
                        "state_digest": registered["entry"]["state_digest"],
                        "predictions_digest": registered["entry"]["prediction_digest"],
                    }
                )
                + b"\n",
            }
        # A per-case graded query (graph or bundle) carries its pinned timed query.
        if "timed-query-receipt.json" in artifacts:
            originals["timed_query"] = {
                "receipt_raw": artifacts["timed-query-receipt.json"],
                "registered_sha256": _sha(artifacts["timed-query-receipt.json"]),
                **(
                    {"predictions_raw": artifacts["timed-query-predictions.json"]}
                    if "timed-query-predictions.json" in artifacts
                    else {}
                ),
            }
        # Graph and bundle alike: the paired repeat is what the KOTH comparison
        # binds (v4). Never gates retention: this runs after bank custody, and a
        # missing or failed pair leaves the evaluation UNAVAILABLE with a typed reason.
        pair_raw = _inference_pair_raw(
            adapter,
            submission_id,
            result,
            artifacts,
            registered["entry"],
            regrade,
        )
        originals["inference_pair_raw"] = pair_raw
        originals["inference_pair_sha256"] = _sha(pair_raw)
        prepared = produce_registered_dual_measurement(
            selected_pack=snapshot,
            public_root=discovery.evaluation_pack_public_root,
            private_root=private_root,
            entry=registered["entry"],
            trusted_job=source["trusted_job"],
            registration=source["benchmark_registration"],
            references=registered["references"],
            graph_originals=originals,
            evaluation_source_receipt_raw=registered["evaluation_source_receipt_raw"],
            timing_step=_timing_step(adapter),
        )
        directory = _private_evaluation_directory(result, submission_id)
        measurement_path = directory / "dual-measurement.json"
        pin_path = directory / "dual-measurement-registration.json"
        write_once(measurement_path, prepared.raw)
        write_once(
            pin_path,
            _json(
                {
                    "schema": "carbon.lean-recipe.private-dual-registration.v1",
                    "task_id": submission_id,
                    "entry_id": result["entry_id"],
                    "evaluation_pack_digest": snapshot.manifest_digest,
                    "dual_measurement_sha256": prepared.sha256,
                }
            ),
        )
        raw = _private_measurement_bytes(measurement_path, 1024**2)
        pin = json.loads(_private_measurement_bytes(pin_path, 65536))
        expected_pin = {
            "schema": "carbon.lean-recipe.private-dual-registration.v1",
            "task_id": submission_id,
            "entry_id": result["entry_id"],
            "evaluation_pack_digest": snapshot.manifest_digest,
            "dual_measurement_sha256": prepared.sha256,
        }
        if pin != expected_pin or _sha(raw) != pin["dual_measurement_sha256"]:
            raise RetentionUnavailable("dual_measurement_registration_changed")
        benchmark = json.loads(raw)["benchmark"]
        scoring = ScoreEngine.score_dual_benchmark_v4(
            benchmark, registered["score_pack"]
        )
        # The exam was applied: a graded outcome keeps the slot, anything else gives it back.
        cap.settle(
            reservation,
            scoring["models"][0]["status"],
            cpu_seconds=(
                None
                if regrade is not None
                else _rebuild_cpu_seconds(
                    adapter, submission_id, evidence, snapshot.manifest_digest
                )
            ),
        )
        reservation = None
        expected_result = _sha(
            (
                json.dumps(
                    scoring, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                + "\n"
            ).encode("utf-8")
        )
        task_root = _owner_directory(result["artifact_path"], "task_artifacts")
        bind_inputs = {
            "entry": registered["entry"],
            "custody_receipt_raw": _private_measurement_bytes(
                task_root.parent / (submission_id + ".custody.json"), 1024**2
            ),
            "trusted_job": source["trusted_job"],
            "registration": source["benchmark_registration"],
            "references": registered["references"],
            "measured_model": prepared.measured_model,
            "score_pack": registered["score_pack"],
            "graph_originals": originals,
            "expected_result_digest": expected_result,
            "ordered_query_bytes": queries,
            "evaluation_source_receipt_raw": registered[
                "evaluation_source_receipt_raw"
            ],
            "expected_evaluation_pack_digest": snapshot.manifest_digest,
            "dual_measurement_receipt_raw": raw,
            "registered_dual_measurement_sha256": pin["dual_measurement_sha256"],
            "selected_evaluation_pack": snapshot,
        }
        source_pin = registered["registered_source_receipt_sha256"]
        binding = bind_private_evaluation_evidence(
            registered_source_receipt_sha256=source_pin, **bind_inputs
        )
        binding_path = directory / "private-evaluation-binding.json"
        write_once(binding_path, _json(binding))
        if regrade is not None and regrade.promotion is not None:
            _record_regraded_evidence(regrade, bind_inputs, source_pin)
        if regrade is not None and regrade.exam_se:
            _write_exam_se(
                adapter,
                snapshot,
                directory,
                registered,
                source,
                originals,
                scoring,
            )
        koth = None
        if pool_store is not None and regrade is None:
            koth = _contend(
                adapter,
                pool_store,
                submission_id,
                artifacts,
                bind_inputs,
                source_pin,
            )
    except (
        ImportError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        if reservation is not None:
            # Grading did not complete (infrastructure or evidence), so the slot is returned.
            cap.settle(reservation, "UNAVAILABLE")
        reason = (
            str(exc)
            if isinstance(exc, RetentionUnavailable)
            else getattr(exc, "code", type(exc).__name__)
        )
        return {
            **result,
            "private_evaluation_state": "UNAVAILABLE",
            "private_evaluation_reason": reason,
        }
    return {
        **result,
        "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
        "private_evaluation_path": binding_path,
        # A regrade is not a graded submission of the miner: it never feeds the Ladder.
        **(
            {}
            if regrade is not None
            else {
                "ladder_feedback_state": _record_ladder(
                    adapter,
                    submission_id,
                    exam_key=snapshot.manifest_digest,
                    exam_version=source["evaluation_version"],
                    gates=registered["score_pack"]["hard_gates"],
                    graded=scoring["models"][0],
                )
            }
        ),
        **({} if koth is None else {"koth_comparison": koth}),
    }


def _write_exam_se(
    adapter, snapshot, directory, registered, source, originals, scoring
):
    """The exam-total standard error of this evaluation (a case bootstrap), write-once beside
    the binding; an adapter that cannot measure a resample leaves UNAVAILABLE with the reason.
    Read only by the operator's weekly fresh-draw check (``exam_rotation``)."""
    from carbon.challenge_kit import physical_pack
    from carbon.challenge_validator import exam_rotation
    from carbon.development_session.data import write_once
    from carbon.scoring import physical_dual_pack, private_evaluation_source

    document = {
        "schema": exam_rotation.SE_SCHEMA,
        "exam_key": snapshot.manifest_digest,
        "resamples": 200,
        "total": scoring["models"][0].get("score"),
    }
    try:
        module = private_evaluation_source._physical_adapter(
            adapter.challenge_id, adapter.challenge_version
        )
        if module is None:
            raise private_evaluation_source.PrivateEvaluationSourceRefused(
                "bootstrap_adapter_unavailable"
            )
        discovery = adapter.discovery
        document["standard_error"] = physical_dual_pack.bootstrap_total_se(
            module,
            selected=snapshot,
            public_root=discovery.evaluation_pack_public_root,
            private_root=discovery.evaluation_pack_private_root,
            entry=registered["entry"],
            job=source["trusted_job"],
            registration=source["benchmark_registration"],
            references=registered["references"],
            originals=originals,
            source_raw=registered["evaluation_source_receipt_raw"],
            bank=physical_pack.development_bank(
                adapter.challenge_id, adapter.challenge_version
            ),
            interface_names=physical_dual_pack.input_names(module),
            exam_key=snapshot.manifest_digest,
            resamples=document["resamples"],
        )
        document["status"] = "MEASURED"
    except private_evaluation_source.PrivateEvaluationSourceRefused as refused:
        document["status"] = "UNAVAILABLE"
        document["reason"] = refused.code
    write_once(directory / exam_rotation.SE_SIDECAR, _json(document))


def _rebuild_cpu_seconds(adapter, submission_id, evidence, exam_key):
    """Allocated CPU-seconds of one graded submission's rebuild, from the ledger's receipts:
    the metered compute time of its worker operations (build, graded inference, timed
    query, repeat pair) times the policy's CPU count. None when the receipts carry none,
    so the registered placeholder keeps standing in for it."""
    try:
        from carbon.development_session.paired_inference import pair_identities

        policy = adapter.discovery._material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        cpus = policy["cpu_count_max"]
        provider = adapter._provider(adapter.owner(submission_id))
        operations = [
            evidence.get(name)
            for name in ("build_operation", "inference_operation", "timed_operation")
        ]
        operations += list(pair_identities("pair-" + exam_key + "-" + submission_id))
        milliseconds = 0
        with provider.ledger.db() as db:
            for operation in operations:
                if type(operation) is not str:
                    continue
                row = db.execute(
                    "SELECT actual FROM operations WHERE id=?", (operation,)
                ).fetchone()
                if row is not None and row[0]:
                    milliseconds += json.loads(row[0]).get("numerical_milliseconds", 0)
        if type(cpus) is not int or cpus < 1 or milliseconds <= 0:
            return None
        return milliseconds / 1000.0 * cpus
    # A missing receipt only leaves the registered placeholder in force.
    except Exception:  # noqa: BLE001
        return None


def _pool_admit(store, adapter, submission_id, entry, artifacts):
    """Admit the retained, already-reconstructed model into the pool store once, so its
    private evaluation can be filed and contend. Replays keep the first rows."""
    from carbon.battery.pool_store import StateError

    try:
        store.submission(submission_id)
        return
    except StateError as missing:
        if missing.code != "unknown_submission":
            raise
    hotkey = adapter.owner(submission_id)
    if hotkey is None:
        raise RetentionUnavailable("pool_owner_unknown")
    with adapter.ledger._db() as db:
        row = db.execute(
            "SELECT request_sha256 FROM recipe_task_intents "
            "WHERE contract_digest=? AND submission_id=?",
            (adapter.contract_digest, submission_id),
        ).fetchone()
    if row is None:
        # No made-up digest: it would misstate the submission's provenance in the pool.
        raise RetentionUnavailable("pool_admit_request_digest_unavailable")
    request_digest = row[0]
    recipe = json.loads(artifacts["recipe.json"])
    store.admit(
        submission_id,
        request_digest=request_digest,
        hotkey=hotkey,
        challenge=entry["challenge"],
        strategy=recipe,
        binding={
            "challenge": {
                "id": entry["challenge"],
                "version": entry["challenge_version"],
            },
            "recipe_digest": entry["recipe_digest"],
        },
    )
    store.retain_model(
        submission_id,
        recipe_digest=entry["recipe_digest"],
        seed=0,
        state=artifacts["state.npz"],
        reconstruction={
            "scope": "LEAN_RECIPE_RETAINED_DEVELOPMENT",
            "seed": "unrecorded",
        },
    )
    store.mark(submission_id, "RECONSTRUCTED")


def _contend(adapter, pool_store, submission_id, artifacts, bind_inputs, pin):
    """File the bound evaluation in the pool store and let it meet the incumbent
    (DEVELOPMENT king of the hill). Its own failure never unbinds the evaluation: the
    result names the outcome and reason, or the refusal."""
    try:
        from carbon.battery.pool_store import PoolStore
        from carbon.challenge_validator import koth_registry
        from carbon.challenge_validator.bank_promotion import BankPromotion

        promotion = (
            BankPromotion(pool_store, registered_source_receipt_sha256=pin)
            if type(pool_store) is PoolStore
            else pool_store
        )
        _pool_admit(
            promotion.store, adapter, submission_id, bind_inputs["entry"], artifacts
        )
        filed = promotion.retain_private(submission_id, **bind_inputs)
        discovery = adapter.discovery
        accuracy = discovery.evaluation_pack_snapshot.read_json_role(
            discovery.evaluation_pack_public_root,
            "public",
            "accuracy_definition",
            max_bytes=65536,
        )
        outcome = promotion.consider_private(
            submission_id,
            filed["evaluation_key"],
            koth_registry.comparator(
                adapter.challenge_id, bind_inputs["score_pack"], accuracy
            ),
        )
    # A pool refusal, whatever its type, never unbinds the evaluation.
    except Exception as exc:  # noqa: BLE001
        return {
            "error": (
                str(exc)
                if isinstance(exc, RetentionUnavailable)
                else str(getattr(exc, "code", type(exc).__name__))
            )
        }
    return {
        "outcome": outcome["outcome"],
        "reason": outcome["reason"],
        "evaluation_key": outcome["evaluation_key"],
    }


def _timing_step(adapter):
    """The Ladder step for this Challenge, max(eta, its registered rebuild
    noise): the precision a timed query must agree with the graded run to."""
    from carbon.challenge_validator import koth_registry
    from carbon.scoring import grade_feedback

    noise = koth_registry.rebuild_noise(
        adapter.discovery.info.challenge_key.challenge_id
    )
    return grade_feedback.step(None if noise is None else noise["value"])


def _record_ladder(adapter, submission_id, *, exam_key, exam_version, gates, graded):
    """Apply the bound result to the miner's private-exam Ladder
    (`ladder_store`), stepped by the Challenge's registered rebuild noise from
    the one source the KOTH comparator also reads (`koth_registry`). Its own
    failure never unbinds the evaluation: the state says RECORDED or names the
    refusal."""
    try:
        from carbon.challenge_validator import koth_registry
        from carbon.challenge_validator.ladder_store import LadderStore

        hotkey = adapter.owner(submission_id)
        if hotkey is None:
            return "UNAVAILABLE: ladder_owner_unknown"
        LadderStore(adapter.ledger).record(
            hotkey,
            adapter.discovery.info.challenge_key,
            exam_key,
            graded,
            exam_version=exam_version,
            gates=gates,
            rebuild_noise=koth_registry.rebuild_noise(
                adapter.discovery.info.challenge_key.challenge_id
            ),
        )
    except (ImportError, OSError, ValueError, KeyError, TypeError) as exc:
        return "UNAVAILABLE: " + str(getattr(exc, "code", type(exc).__name__))
    return "RECORDED"


def retain_served_result(
    adapter,
    submission_id: str,
    *,
    artifact_directory: Path,
    entry_directory: Path,
    pool_store=None,
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
        bound = _retain_selected_pack_evaluation(
            adapter,
            submission_id,
            bound,
            artifacts,
            evidence,
            pool_store=pool_store,
        )
        return _retain_public_synthetic_measurement(
            bound, artifacts, submission_id, evidence
        )
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
        limit=_STATE_CUSTODY_BYTES,
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
    timed_receipt = None
    if "timed_receipt" in evidence:
        # The batched cold query kept only for timing, retained as an original.
        if (
            type(evidence.get("timed_operation")) is not str
            or re.fullmatch(r"operation-[0-9a-f]{64}", evidence["timed_operation"])
            is None
        ):
            raise RetentionUnavailable("timed_operation_invalid")
        timed_receipt = _receipt_snapshot(
            root / evidence["timed_operation"] / "snapshot" / "receipt.json",
            evidence["timed_receipt"],
            "timed_receipt",
        )
        # The timed run's own outputs, for the producer's agreement check.
        timed_predictions = _snapshot(
            root / evidence["timed_operation"] / "snapshot" / "predictions.json",
            limit=16 * 1024**2,
            digest=evidence["timed_receipt"].get("predictions_digest"),
            label="timed_prediction_snapshot",
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
        else material["disclosure"]["scope"]
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
        **(
            {}
            if timed_receipt is None
            else {
                "timed-query-receipt.json": timed_receipt,
                "timed-query-predictions.json": timed_predictions,
            }
        ),
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
                expected_output_dtype=output_dtype(material["interface_document"]),
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
    bound = _retain_private_pack_binding(adapter, provider, submission_id, task, result)
    bound = _retain_selected_pack_evaluation(
        adapter,
        submission_id,
        bound,
        artifacts,
        evidence,
        pool_store=pool_store,
    )
    return _retain_public_synthetic_measurement(
        bound, artifacts, submission_id, evidence
    )


def retain_served_bundle_result(
    adapter,
    submission_id: str,
    *,
    artifact_directory: Path,
    entry_directory: Path,
    pool_store=None,
) -> dict:
    """Compatibility name for the original bundle-only operator call site."""
    return retain_served_result(
        adapter,
        submission_id,
        artifact_directory=artifact_directory,
        entry_directory=entry_directory,
        pool_store=pool_store,
    )


@dataclass(frozen=True)
class _Regrade:
    """The incumbent's identity for one regrade, copied from its own retained task."""

    owner: str
    recipe: object
    origin_task_id: str
    origin_entry_id: str
    #: A BankPromotion: the regraded evidence is recorded under the origin task's own
    #: submission id on the new evaluation key, so KOTH finds it for the incumbent.
    promotion: object = None
    #: Also compute the exam-total standard error (case bootstrap) into a sidecar.
    exam_se: bool = False


def _record_regraded_evidence(regrade, bind_inputs, pin=None):
    """Record the regrade's evaluation for the incumbent's submission id (new key).

    ``promotion`` is a BankPromotion with its own registered pin, or a bare PoolStore, which
    gets the pin this evaluation registered in owner custody (the operator's own).
    """
    from carbon.battery.pool_store import PoolStore, StateError
    from carbon.challenge_validator.bank_promotion import BankPromotion

    promotion = regrade.promotion
    if type(promotion) is PoolStore:
        promotion = BankPromotion(promotion, registered_source_receipt_sha256=pin)
    try:
        return promotion.retain_private(regrade.origin_task_id, **bind_inputs)
    except StateError as refused:
        raise RetentionUnavailable("regrade_record_" + refused.code) from refused


def _regrade_origin(adapter, base, entries, entry_id):
    """The retained task behind one bank entry, with its owner from the receiver's ledger."""
    from carbon.development_session.construction_recipe import ConstructionRecipe

    if (
        type(entry_id) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", entry_id) is None
    ):
        raise RetentionUnavailable("regrade_entry_identity_invalid")
    entry_path = entries / (entry_id.removeprefix("sha256:") + ".json")
    entry = json.loads(_private_measurement_bytes(entry_path, 1024**2))
    if type(entry) is not dict or entry.get("entry_id") != entry_id:
        raise RetentionUnavailable("regrade_entry_changed")
    receipt_name = (entry.get("custody_receipt") or {}).get("file")
    match = re.fullmatch(r"(rtsk_[0-9a-f]{64})\.custody\.json", str(receipt_name))
    if match is None:
        raise RetentionUnavailable("regrade_origin_task_unavailable")
    origin = match.group(1)
    owner = adapter.ledger.owned_outcome(adapter.contract_digest, origin)
    if owner is None:
        raise RetentionUnavailable("regrade_owner_unavailable")
    task_root = _owner_directory(base / origin, "task_artifacts")
    manifest = json.loads(
        _private_measurement_bytes(base / (origin + ".roles.json"), 1024**2)
    )
    files = {}
    for name, digest in sorted(manifest["retained_files"].items()):
        raw = _private_measurement_bytes(task_root / name, 128 * 1024**2)
        if _sha(raw) != digest:
            raise RetentionUnavailable("regrade_origin_file_changed")
        files[name] = raw
    # The state is the entry's own: never a stand-in.
    if _sha(files["state.npz"]) != entry["state_digest"]:
        raise RetentionUnavailable("regrade_state_digest_changed")
    recipe = ConstructionRecipe.from_dict(json.loads(files["recipe.json"]))
    if recipe.digest != entry["recipe_digest"]:
        raise RetentionUnavailable("regrade_recipe_changed")
    return entry, origin, owner, manifest, files, recipe


def regrade_retained_entry(
    adapter,
    entry_id: str,
    *,
    artifact_directory: Path,
    entry_directory: Path,
    runner=None,
    promotion=None,
    exam_se: bool = False,
) -> dict:
    """Regrade a retained model on the receiver's selected (rotated) evaluation pack.

    Operator-only, like retention. The retained frozen state runs again on the pack's own
    case bank, becoming a new bank entry (the same state, new inputs and predictions), and
    that entry is graded through the standard private evaluation, so the result carries the
    v4 receipts on the new evaluation key. The owner is the retained task's own, the cap
    slot is a REGRADE (never counted, no epoch limit), and provenance is recorded beside
    the result. With ``promotion`` (a BankPromotion or a PoolStore), the evaluation is also recorded under
    the origin task's submission id on the new evaluation key, which is where the incumbent
    comparison looks it up. Only bundle recipes are supported; a graph recipe is typed
    unavailable.
    """
    import io
    from types import SimpleNamespace

    import numpy as np

    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.bundle_construction_worker import (
        _checked_binding,
        _infer_state,
        _tensors,
        verify_direct_resource_policy,
    )
    from carbon.development_session.construction_recipe import RecipeRefused
    from carbon.development_session.data import write_once

    if type(adapter) is not LeanRecipeAdapter:
        raise TypeError("trusted served adapter required")
    discovery = adapter.discovery
    snapshot = discovery.evaluation_pack_snapshot
    if snapshot is None or discovery.evaluation_pack_digest != snapshot.manifest_digest:
        raise RetentionUnavailable("evaluation_pack_not_selected")
    base = _owner_directory(artifact_directory, "artifact_directory")
    entries = _owner_directory(entry_directory, "entry_directory")
    entry, origin, owner, manifest, files, recipe = _regrade_origin(
        adapter, base, entries, entry_id
    )
    if recipe.to_dict()["source"]["kind"] != "bundle":
        raise RetentionUnavailable("regrade_source_kind_unavailable")
    if (entry["challenge"], entry["challenge_version"]) != (
        adapter.challenge_id,
        adapter.challenge_version,
    ):
        raise RetentionUnavailable("regrade_challenge_changed")
    regrade_id = (
        "rtsk_"
        + hashlib.sha256(
            (origin + "\0REGRADE\0" + snapshot.manifest_digest).encode()
        ).hexdigest()
    )
    material = discovery._material
    provider = adapter._provider(owner)
    try:
        bank_raw = snapshot.read_role(
            discovery.evaluation_pack_private_root,
            "private",
            "case_bank",
            max_bytes=16 * 1024 * 1024,
        )
        with np.load(io.BytesIO(bank_raw), allow_pickle=False) as loaded:
            if list(loaded.files) != ["inputs"]:
                raise ValueError("case bank members differ")
            bank = loaded["inputs"]
    except (OSError, ValueError, KeyError) as exc:
        raise RetentionUnavailable("regrade_case_bank_unavailable") from exc
    practice = material["practice_inputs"]
    if (
        bank.dtype != practice.dtype
        or bank.ndim != practice.ndim
        or bank.shape[1:] != practice.shape[1:]
        or not len(bank)
        or _tensors(inputs=bank) != bank_raw
    ):
        raise RetentionUnavailable("regrade_case_bank_contract_changed")

    task_root = base / regrade_id
    operations_path = base / (regrade_id + ".regrade-operation.json")
    # Like the origin: the graded query runs one case at a time (v1 receipt, a bank role);
    # a task that kept the batched cold query for timing gets the same on the new bank.
    timed = "timed-query-receipt.json" in files
    if (task_root / "inference-receipt.json").exists():
        # A retry reads the retained bytes and never replays an identity.
        task_root = _owner_directory(task_root, "task_artifacts")
        predictions = _private_measurement_bytes(
            task_root / "predictions.json", 16 * 1024**2
        )
        receipt_raw = _private_measurement_bytes(
            task_root / "inference-receipt.json", 65536
        )
        timed_raw = (
            _private_measurement_bytes(task_root / "timed-query-receipt.json", 65536)
            if timed
            else None
        )
        timed_predictions = (
            _private_measurement_bytes(
                task_root / "timed-query-predictions.json", 16 * 1024**2
            )
            if timed
            else None
        )
        operations = json.loads(_private_measurement_bytes(operations_path, 65536))
    else:
        kit = material["construction_kit"]
        limits = material["construction_limits_document"]
        policy = limits["reconstruction_resource_policy"]
        interface = material["interface_document"]
        output_shape = (len(bank), *tuple(material["expected_output_shape"])[1:])
        try:
            binding = _checked_binding(
                recipe,
                {
                    "challenge_id": kit["id"],
                    "challenge_version": kit["version"],
                    "train_digest": kit["train_digest"],
                    "interface_digest": kit["interface_digest"],
                    "construction_limits_digest": kit["construction_limits_digest"],
                },
            )
            verify_direct_resource_policy(binding, limits)

            def infer(label, measure):
                return _infer_state(
                    provider.ledger,
                    owner=owner,
                    identity="regrade-"
                    + label
                    + "-"
                    + hashlib.sha256(regrade_id.encode()).hexdigest(),
                    inference_image=provider.inference_image,
                    recipe=recipe,
                    binding=binding,
                    state=files["state.npz"],
                    state_digest=entry["state_digest"],
                    inputs=bank,
                    expected_output_shape=output_shape,
                    expected_output_dtype=output_dtype(interface),
                    allowlist_bytes=material["allowlist_bytes"],
                    measure_query=measure,
                    seconds=policy["inference_wall_seconds_max"],
                    accelerator=getattr(provider, "inference_accelerator", None),
                    runner=runner,
                )

            graded = infer("graded", False)
            timed_result = infer("timed", True) if timed else None
        except RecipeRefused as refused:
            raise RetentionUnavailable("regrade_inference_" + refused.code) from refused

        def kept(result, label):
            output = provider.ledger.root / result.worker_operation / "snapshot"
            return _snapshot(
                output / "predictions.json",
                limit=16 * 1024**2,
                digest=result.predictions_digest,
                label=label + "_prediction_snapshot",
            ), _receipt_snapshot(
                output / "receipt.json", result.receipt, label + "_inference_receipt"
            )

        predictions, receipt_raw = kept(graded, "regrade")
        timed_predictions, timed_raw = (
            kept(timed_result, "regrade_timed") if timed else (None, None)
        )
        operations = {
            "inference_operation": graded.worker_operation,
            "timed_operation": (
                timed_result.worker_operation if timed_result is not None else None
            ),
        }
    operation = operations["inference_operation"]

    artifacts = dict(files)
    artifacts["inputs.npz"] = bank_raw
    artifacts["predictions.json"] = predictions
    artifacts["inference-receipt.json"] = receipt_raw
    if timed:
        artifacts["timed-query-receipt.json"] = timed_raw
        artifacts["timed-query-predictions.json"] = timed_predictions
    lineage = json.loads(artifacts["lineage.json"])
    lineage.update(
        task_id=regrade_id,
        prediction_digest=_sha(predictions),
        inference_operation=operation,
    )
    artifacts["lineage.json"] = _json(lineage)
    new_manifest = dict(manifest)
    new_manifest["roles"] = {
        role: spec
        for role, spec in manifest["roles"].items()
        if spec["file"] in artifacts
    }
    new_manifest["retained_files"] = {
        name: _sha(raw) for name, raw in sorted(artifacts.items())
    }

    from scripts.dev.score_lab.public_unbound_custody import prepare_custody_v5
    from scripts.dev.score_lab.public_unbound_entry import create_entry_v5

    task_root.mkdir(mode=0o700, exist_ok=True)
    _owner_directory(task_root, "task_artifacts")
    try:
        for name, raw in artifacts.items():
            write_once(task_root / name, raw)
        # Beside the task (not in it): the custody inventory is exactly the declared files.
        write_once(
            base / (regrade_id + ".regrade-operation.json"),
            _json(operations),
        )
        manifest_path = base / (regrade_id + ".roles.json")
        write_once(manifest_path, _json(new_manifest))
        custody = prepare_custody_v5(task_root, manifest_path)
        custody_path = base / (regrade_id + ".custody.json")
        write_once(custody_path, _json(custody))
        saved = create_entry_v5(task_root, manifest_path, custody_path, entries)
    except (OSError, ValueError) as exc:
        raise RetentionUnavailable("operator_bank_custody_unavailable") from exc
    if saved["entry"]["state_digest"] != entry["state_digest"]:
        raise RetentionUnavailable("regrade_state_digest_changed")
    result = {
        "status": saved["status"],
        "entry_id": saved["entry"]["entry_id"],
        "entry_path": entries / saved["path"],
        "artifact_path": task_root,
        "score_state": saved["entry"]["score_state"],
        "official_eligible": False,
    }
    stand_in = SimpleNamespace(
        terminal_receipt=SimpleNamespace(
            state_digest=entry["state_digest"], predictions_digest=_sha(predictions)
        )
    )
    bound = _retain_private_pack_binding(
        adapter, provider, regrade_id, stand_in, result
    )
    directory = _private_evaluation_directory(bound, regrade_id)
    write_once(
        directory / "regrade-provenance.json",
        _json(
            {
                "schema": "carbon.lean-recipe.regrade-provenance.v1",
                "kind": "REGRADE",
                "regrade_task_id": regrade_id,
                "origin_task_id": origin,
                "origin_entry_id": entry_id,
                "entry_id": result["entry_id"],
                "hotkey": owner,
                "state_digest": entry["state_digest"],
                "evaluation_pack_digest": snapshot.manifest_digest,
            }
        ),
    )
    evidence = {
        "inference_operation": operation,
        "inference_image_id": provider.inference_image.image_id,
    }
    regraded = _retain_selected_pack_evaluation(
        adapter,
        regrade_id,
        bound,
        artifacts,
        evidence,
        _Regrade(owner, recipe, origin, entry_id, promotion, exam_se),
    )
    return {**regraded, "regrade_of": entry_id, "regrade_task_id": regrade_id}


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
    """Register source for an operator-selected already successful task."""
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    if type(adapter) is not LeanRecipeAdapter or type(submission_id) is not str:
        raise TypeError("trusted served adapter and task identity required")
    snapshot = adapter.discovery.evaluation_pack_snapshot
    if (
        snapshot is None
        or adapter.discovery.evaluation_pack_digest != snapshot.manifest_digest
    ):
        raise RetentionUnavailable("evaluation_pack_not_selected")
    retained = retain_served_result(
        adapter,
        submission_id,
        artifact_directory=artifact_directory,
        entry_directory=entry_directory,
    )
    return _register_retained_pack_source(
        adapter,
        submission_id,
        retained,
        trusted_job=trusted_job,
        registration=registration,
        ordered_query_bytes=ordered_query_bytes,
        evaluation_version=evaluation_version,
        hidden_store=hidden_store,
        fingerprint=fingerprint,
        expected_references_digest=expected_references_digest,
    )


def _register_retained_pack_source(
    adapter,
    submission_id,
    retained,
    *,
    trusted_job,
    registration,
    ordered_query_bytes,
    evaluation_version,
    hidden_store=None,
    fingerprint=None,
    expected_references_digest=None,
):
    """Register actual v2 source bytes under an already retained private task.

    The selected pack comes from receiver admission, and reference rows and
    ScorePack are read again from its verified private roles. The returned
    source pin is read back from owner-only write-once custody; callers pass
    that registered value to the existing private ScoreLab binder.
    """
    from carbon.challenge_validator.evaluation_pack import PRIVATE_ROLES
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.data import write_once
    from carbon.scoring import dual_score
    from carbon.scoring.benchmark_evidence import physics_contract_identity
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
    dual = score_document.get("schema") == dual_score.PACK_SCHEMA
    try:
        score_pack = dual_score.register_pack(body) if dual else register_pack(body)
    except (BenchmarkScoreRefused, dual_score.DualScoreRefused) as exc:
        raise RetentionUnavailable("evaluation_pack_score_pack_invalid") from exc
    if (
        declared_pack_digest is not None
        and declared_pack_digest != score_pack["pack_digest"]
    ):
        raise RetentionUnavailable("evaluation_pack_score_pack_invalid")
    if (
        score_pack["challenge"] != snapshot.challenge_id
        or (
            dual
            and score_pack["physics_contract_digest"]
            != physics_contract_identity(physics)["definition_digest"]
        )
        or (
            not dual
            and (
                score_pack["benchmark_registration_digest"]
                != registration.get("registration_digest")
                or score_pack["accuracy_ceiling"] is None
            )
        )
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
    public_rule = None
    if not dual:
        try:
            public_rule = ScoreEngine.public_solver_benchmark_rule_v3(
                registration, score_pack
            )
        except BenchmarkScoreRefused as exc:
            raise RetentionUnavailable("evaluation_pack_public_rule_invalid") from exc
    directory = _private_evaluation_directory(retained, submission_id)
    source_path = directory / "evaluation-source-receipt.json"
    registration_path = directory / "evaluation-source-registration.json"
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
