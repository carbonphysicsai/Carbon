"""Operator bank custody for an actual local fixed-program direct result."""

import base64
import io
import json
import tarfile
from dataclasses import replace

import numpy as np
import pytest
from test_direct_clean_rebuild_acceptance import (
    SOURCE,
    LocalProcessRunner,
    _binding,
    _digest,
    _recipe,
)
from test_synthetic_graph_adapter import _graph_case

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.interface import Admitted
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    _collect_graph_artifacts,
    _retain_public_synthetic_measurement,
    retain_served_bundle_result,
    retain_served_result,
)
from carbon.development_session.bundle_construction_worker import (
    _tensors,
    infer_public,
    reconstruct_public,
)
from carbon.development_session.bundle_graph_state import freeze
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    ProvisionedLibraryEnvironment,
    _environment_digest,
    bundle_ref,
    prepare_offline_context,
)
from carbon.development_session.profile import canonical
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.development_session.synthetic_graph_adapter import build_validated_graph
from carbon.level4 import staging, submission
from carbon.level4.allowlist import Allowlist
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.research import DirectTaskReceiptV3, DirectTaskStateV3, canonical_bytes


class _RealLocalRunner(LocalProcessRunner):
    def __call__(self, ledger, **request):
        result = super().__call__(ledger, **request)
        operation = f"operation-{len(self.calls):064x}"
        (ledger.root / result["operation"]).rename(ledger.root / operation)
        return {**result, "operation": operation}


def test_public_measurement_skips_other_challenge_and_selected_pack(tmp_path):
    artifacts_root = tmp_path / "retained"
    artifacts_root.mkdir(mode=0o700)
    entry = tmp_path / "entry.json"
    entry.write_bytes(b"{}")
    result = {
        "entry_path": entry,
        "artifact_path": artifacts_root,
        "entry_id": "sha256:" + "a" * 64,
        "score_state": "NOT_COMPUTED",
        "official_eligible": False,
    }
    battery = {
        "recipe.json": canonical({"challenge": {"id": "battery", "version": "1.0"}})
    }
    assert _retain_public_synthetic_measurement(result, battery, "task", {}) == result
    selected = {
        "recipe.json": canonical(
            {"challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"}}
        )
    }
    bound = {**result, "evaluation_pack_digest": "sha256:" + "b" * 64}
    assert _retain_public_synthetic_measurement(bound, selected, "task", {}) == bound
    assert not list(tmp_path.glob("*.public-measurement"))


def _source_image(tmp_path):
    license_text = b"MIT\n"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in (
            ("source/candidate/__init__.py", b""),
            ("source/candidate/build.py", SOURCE.encode()),
            ("source/LICENSE", license_text),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    source = output.getvalue()
    lock = b""
    base = "sha256:" + "1" * 64
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "synthetic-linear-source",
        "language": "python",
        "source_sha256": _digest(source),
        "source_bytes": len(source),
        "runtime_profile_id": "jax-cuda13-py311",
        "base_environment_digest": base,
        "environment_digest": _environment_digest(base, _digest(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cuda13",
        "lock_sha256": _digest(lock),
        "wheels": {},
        "license_sha256": _digest(license_text),
    }
    parent_id = "sha256:" + "2" * 64
    parent = WorkerImageIdentity(*(parent_id for _ in range(8)))
    ref = bundle_ref(manifest, source, {}, lock, license_text)
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    context, observed_ref, seal = prepare_offline_context(
        cache, manifest, source, {}, lock, license_text, parent.image_id
    )
    assert observed_ref == ref.bundle_digest
    image = LibraryWorkerImage(
        ProvisionedLibraryEnvironment(
            ref, parent.image_id, context, seal, "sha256:" + "3" * 64
        ),
        parent,
        ref.to_dict(),
    )
    installed = tmp_path / "installed" / "candidate"
    installed.mkdir(parents=True)
    (installed / "__init__.py").write_bytes(b"")
    (installed / "build.py").write_bytes(SOURCE.encode())
    return image, installed.parent


@pytest.mark.parametrize("measure_query", [False, True])
def test_real_local_result_enters_existing_pending_bank_create_only(
    tmp_path, monkeypatch, measure_query
):
    material = bundle_material_v5()
    image, installed = _source_image(tmp_path)
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda value: value,
    )
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    campaign = CampaignLedger(tmp_path / "campaign")
    resolved = {image.provisioned.bundle.bundle_digest: image}
    provider = DirectDevelopmentTasksV3(
        root=tmp_path / "tasks",
        requester="miner",
        ledger=campaign,
        owner="miner",
        discovery=discovery,
        image_resolver=lambda ref: resolved[ref.bundle_digest],
        inference_image=image.parent,
    )
    try:
        attempts_root = tmp_path / "attempts"
        attempts_root.mkdir(mode=0o700)
        adapter = LeanRecipeAdapter(
            discovery,
            lambda owner: provider if owner == "miner" else None,
            AttemptLedger(attempts_root / "ledger.sqlite3"),
            measure_query=measure_query,
        )
        recipe = _recipe(material, image)
        admitted = Admitted(
            "miner",
            {},
            adapter.challenge_id,
            adapter.challenge_version,
            recipe.to_dict(),
            adapter.contract_digest,
        )
        queued = adapter.evaluate(admitted)
        task_id = queued["task_id"]
        entry_root = tmp_path / "bank-entries"
        artifact_root = tmp_path / "bank-artifacts"
        entry_root.mkdir(mode=0o700)
        artifact_root.mkdir(mode=0o700)
        with pytest.raises(RetentionUnavailable, match="task_not_succeeded"):
            retain_served_bundle_result(
                adapter,
                task_id,
                artifact_directory=artifact_root,
                entry_directory=entry_root,
            )
        runner = _RealLocalRunner(installed)
        build = reconstruct_public(
            campaign,
            owner="miner",
            identity="test-build",
            image=image,
            recipe=recipe,
            challenge_binding=_binding(material),
            train=material["train"],
            example=material["example"],
            seed=11,
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
        )
        inferred = infer_public(
            campaign,
            owner="miner",
            identity="test-infer",
            image=image,
            inference_image=image.parent,
            recipe=recipe,
            challenge_binding=_binding(material),
            build=build,
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            expected_output_dtype="float32",
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
        )
        # A measured task also keeps the batched cold query, for timing only.
        timed = (
            infer_public(
                campaign,
                owner="miner",
                identity="test-timed",
                image=image,
                inference_image=image.parent,
                recipe=recipe,
                challenge_binding=_binding(material),
                build=build,
                inputs=material["practice_inputs"],
                expected_output_shape=material["expected_output_shape"],
                expected_output_dtype="float32",
                measure_query=True,
                allowlist_bytes=material["allowlist_bytes"],
                runner=runner,
            )
            if measure_query
            else None
        )
        original = provider._views[task_id]
        terminal = DirectTaskReceiptV3(
            original.task_id,
            DirectTaskStateV3.SUCCEEDED,
            original.immutable_bindings,
            build.state_digest,
            inferred.predictions_digest,
            None,
            None,
            original.updated_at_micros + 1,
            ("PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",),
        )
        succeeded = replace(
            original,
            state=DirectTaskStateV3.SUCCEEDED,
            revision=1,
            updated_at_micros=terminal.completed_at_micros,
            terminal_receipt=terminal,
        )
        prediction_raw = (
            campaign.root / inferred.worker_operation / "snapshot" / "predictions.json"
        ).read_bytes()
        private = {
            "schema": "carbon.direct-private-attempt.v3",
            "image_id": image.image_id,
            "parent_image_id": image.parent.image_id,
            "inference_image_id": image.parent.image_id,
            "build_operation": build.worker_operation,
            "inference_operation": inferred.worker_operation,
            "build_controls_digest": "sha256:" + "4" * 64,
            "inference_controls_digest": "sha256:" + "5" * 64,
            "state_digest": build.state_digest,
            "predictions_digest": inferred.predictions_digest,
            "build_receipt": build.receipt,
            "inference_receipt": inferred.receipt,
            "predictions_raw_base64": base64.b64encode(prediction_raw).decode(),
            "bundle_digest": image.provisioned.bundle.bundle_digest,
            "context_digest": image.provisioned.context_digest,
        }
        if timed is not None:
            private["timed_operation"] = timed.worker_operation
            private["timed_receipt"] = timed.receipt
        with provider._db() as db:
            db.execute(
                "INSERT INTO direct_evidence VALUES(?,?)",
                (task_id, canonical(private)),
            )
            db.execute(
                "UPDATE direct_tasks SET view=? WHERE id=?",
                (canonical_bytes(succeeded), task_id),
            )
        provider._views[task_id] = succeeded
        assert (
            provider.private_attempt(original.task_id)["predictions"]
            == inferred.predictions
        )
        first = retain_served_bundle_result(
            adapter,
            task_id,
            artifact_directory=artifact_root,
            entry_directory=entry_root,
        )
        assert first["status"] == "CREATED"
        assert first["score_state"] == "NOT_COMPUTED"
        assert first["official_eligible"] is False
        if measure_query:
            assert first["measurement_state"] == "DEVELOPMENT_UNRANKED"
            measured = json.loads(first["measurement_path"].read_bytes())
            assert measured["entry_id"] == first["entry_id"]
            assert measured["result"]["status"] == "BENCHMARK_REDUCED"
            assert measured["result"]["score_status"] == "PACK_NOT_READY"
            assert measured["accuracy_ceiling"] is None
            assert measured["ranking"] is None
            assert measured["speedup_comparability"] == "NOT_ESTABLISHED"
            assert first["measurement_path"].parent != first["artifact_path"]
        else:
            assert first["measurement_state"] == "UNAVAILABLE"
        assert first["entry_path"].is_file()
        assert (
            first["artifact_path"].joinpath("state.npz").read_bytes()
            == build.state_path.read_bytes()
        )
        assert (
            first["artifact_path"].joinpath("predictions.json").read_bytes()
            == prediction_raw
        )
        assert first["artifact_path"].joinpath("fixture.npz").is_file()
        with np.load(
            first["artifact_path"] / "fixture.npz", allow_pickle=False
        ) as fixture:
            np.testing.assert_array_equal(
                fixture["inputs"], material["practice_inputs"]
            )
            np.testing.assert_array_equal(
                fixture["targets"], material["practice_reference"]
            )
        manifest = json.loads((artifact_root / (task_id + ".roles.json")).read_bytes())
        assert "fixture" in manifest["roles"]
        assert "inference_receipt" in manifest["roles"]
        assert (
            first["artifact_path"].joinpath("timed-query-receipt.json").is_file()
        ) is measure_query
        assert (
            retain_served_bundle_result(
                adapter,
                task_id,
                artifact_directory=artifact_root,
                entry_directory=entry_root,
            )["status"]
            == "ALREADY_PRESENT_IDENTICAL"
        )
        resolved[image.provisioned.bundle.bundle_digest] = LibraryWorkerImage(
            replace(image.provisioned, image_id="sha256:" + "9" * 64),
            image.parent,
            image.bundle_ref,
        )
        with pytest.raises(RetentionUnavailable, match="admitted_image_changed"):
            retain_served_bundle_result(
                adapter,
                task_id,
                artifact_directory=artifact_root,
                entry_directory=entry_root,
            )
        resolved[image.provisioned.bundle.bundle_digest] = image
        (
            campaign.root / inferred.worker_operation / "snapshot" / "predictions.json"
        ).write_bytes(b"tampered")
        with pytest.raises(RetentionUnavailable, match="prediction_snapshot_changed"):
            retain_served_bundle_result(
                adapter,
                task_id,
                artifact_directory=artifact_root,
                entry_directory=entry_root,
            )
    finally:
        provider.close()


@pytest.mark.parametrize("timed_shape", ["full", "prefix_with_per_call"])
def test_graph_collector_uses_admitted_source_and_measured_originals_without_worker(
    tmp_path, monkeypatch, timed_shape
):
    material = bundle_material_v5()
    _, _, old_recipe, raw_manifest, graph_files = _graph_case()
    old_manifest = json.loads(raw_manifest)
    forward = json.loads(graph_files[old_manifest["documents"]["forward"]])
    allowed = Allowlist(material["allowlist_bytes"])
    forward["allowlist"] = allowed.version
    init_spec = json.loads(graph_files[old_manifest["documents"]["init_spec"]])
    init_spec["graph"] = _digest(submission.canonical(forward))
    manifest, graph_files = submission.build(
        challenge=material["construction_kit"]["id"],
        interface=old_manifest["interface"],
        allowlist=allowed,
        forward=forward,
        init_spec=init_spec,
    )
    raw_manifest = submission.canonical(manifest)
    recipe_doc = old_recipe.to_dict()
    recipe_doc["challenge"] = material["construction_kit"]
    recipe_doc["source"]["submission_digest"] = submission.digest(manifest)
    recipe = ConstructionRecipe.from_dict(recipe_doc)
    image_id = "sha256:" + "7" * 64
    image = WorkerImageIdentity(*(image_id for _ in range(8)))
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    campaign = CampaignLedger(tmp_path / "campaign")
    provider = DirectDevelopmentTasksV3(
        root=tmp_path / "tasks",
        requester="miner",
        ledger=campaign,
        owner="miner",
        discovery=discovery,
        image_resolver=lambda ref: None,
        inference_image=image,
    )
    try:
        workspace = ResearchWorkspace(campaign, "miner")
        workspace.put(staging.WORKSPACE_MANIFEST, raw_manifest)
        for name, body in graph_files.items():
            workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
        adapter = LeanRecipeAdapter(
            discovery,
            lambda owner: provider if owner == "miner" else None,
            AttemptLedger(tmp_path / "attempts.sqlite3"),
            measure_query=True,
        )
        admitted = Admitted(
            "miner",
            {},
            adapter.challenge_id,
            adapter.challenge_version,
            recipe.to_dict(),
            adapter.contract_digest,
        )
        task_id = adapter.evaluate(admitted)["task_id"]
        source = provider._source_envelope(task_id, recipe)
        workspace.put(
            staging.WORKSPACE_MANIFEST,
            b"{}",
            expected_digest=workspace.current_digest(staging.WORKSPACE_MANIFEST),
        )

        model = build_validated_graph(
            recipe,
            raw_manifest,
            graph_files,
            allowlist_bytes=material["allowlist_bytes"],
            train_cases=material["construction_limits_document"]["train_cases"],
        )
        state = freeze(
            recipe,
            model.forward,
            [np.zeros((1,), dtype=np.float32)],
            allowed,
        )
        predictions = canonical(
            np.zeros(material["expected_output_shape"], dtype=np.float32).tolist()
        )
        inputs = _tensors(inputs=material["practice_inputs"])
        build_operation = "operation-" + "1" * 64
        inference_operation = "operation-" + "2" * 64
        timed_operation = "operation-" + "3" * 64
        build = campaign.root / build_operation / "snapshot"
        inference = campaign.root / inference_operation / "snapshot"
        timed_root = campaign.root / timed_operation / "snapshot"
        build.mkdir(parents=True)
        inference.mkdir(parents=True)
        timed_root.mkdir(parents=True)
        build_receipt = {
            "schema": "carbon.development.graph-build.v1",
            "recipe_digest": recipe.digest,
            "submission_digest": recipe_doc["source"]["submission_digest"],
            "train_digest": recipe_doc["challenge"]["train_digest"],
            "state_digest": _digest(state),
            "allowlist_digest": allowed.digest,
            "framework": "jax",
            "fit": {"fixture_only": True},
        }
        # Graded one case at a time (v1); timing is the separate timed query's.
        inference_receipt = {
            "schema": "carbon.development.bundle-inference.v1",
            "recipe_digest": recipe.digest,
            "state_digest": _digest(state),
            "inputs_digest": _digest(inputs),
            "predictions_digest": _digest(predictions),
        }
        # The timed child runs the first rows of the practice query when the
        # exported graph's batch is smaller, and the derived timed program adds
        # `per_call_s` (valV3, 2026-10-27): custody binds both.
        timed_rows = (
            len(material["practice_inputs"])
            if timed_shape == "full"
            else max(1, len(material["practice_inputs"]) // 2)
        )
        timed_inputs = _tensors(inputs=material["practice_inputs"][:timed_rows])
        timed_receipt = {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": recipe.digest,
            "state_digest": _digest(state),
            "inputs_digest": _digest(timed_inputs),
            "predictions_digest": _digest(predictions),
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": {
                    "preprocess": 0.1,
                    "inference": 0.1,
                    "postprocess": 0.1,
                    "export": 0.1,
                },
                "input_shape": [timed_rows, *material["practice_inputs"].shape[1:]],
                "input_dtype": str(material["practice_inputs"].dtype),
                "output_shape": [
                    timed_rows,
                    *list(material["expected_output_shape"])[1:],
                ],
                "output_dtype": material["interface_document"]["outputs"]["dtype"],
                **(
                    {} if timed_shape == "full" else {"per_call_s": [0.01] * timed_rows}
                ),
            },
        }
        (build / "state.npz").write_bytes(state)
        (build / "receipt.json").write_bytes(canonical(build_receipt))
        (inference / "predictions.json").write_bytes(predictions)
        (inference / "receipt.json").write_bytes(canonical(inference_receipt))
        (timed_root / "receipt.json").write_bytes(canonical(timed_receipt))
        (timed_root / "predictions.json").write_bytes(predictions)
        queued = provider._views[task_id]
        terminal = DirectTaskReceiptV3(
            queued.task_id,
            DirectTaskStateV3.SUCCEEDED,
            queued.immutable_bindings,
            _digest(state),
            _digest(predictions),
            None,
            None,
            queued.updated_at_micros + 1,
            ("PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",),
        )
        succeeded = replace(
            queued,
            state=DirectTaskStateV3.SUCCEEDED,
            revision=1,
            updated_at_micros=terminal.completed_at_micros,
            terminal_receipt=terminal,
        )
        private = {
            "schema": "carbon.direct-private-attempt.graph.v1",
            "image_id": image_id,
            "parent_image_id": image_id,
            "inference_image_id": image_id,
            "build_operation": build_operation,
            "inference_operation": inference_operation,
            "build_controls_digest": "sha256:" + "4" * 64,
            "inference_controls_digest": "sha256:" + "5" * 64,
            "state_digest": _digest(state),
            "predictions_digest": _digest(predictions),
            "build_receipt": build_receipt,
            "inference_receipt": inference_receipt,
            "predictions_raw_base64": base64.b64encode(predictions).decode(),
            "submission_digest": recipe_doc["source"]["submission_digest"],
            "timed_operation": timed_operation,
            "timed_receipt": timed_receipt,
        }
        with provider._db() as db:
            db.execute(
                "INSERT INTO direct_evidence VALUES(?,?)",
                (task_id, canonical(private)),
            )
            db.execute(
                "UPDATE direct_tasks SET view=? WHERE id=?",
                (canonical_bytes(succeeded), task_id),
            )
        provider._views[task_id] = succeeded
        evidence = provider.private_attempt(queued.task_id)
        artifacts = _collect_graph_artifacts(
            provider, task_id, succeeded, evidence, recipe, material
        )
        assert artifacts["source-envelope.json"] == source
        assert artifacts["state.npz"] == state
        assert artifacts["predictions.json"] == predictions
        assert artifacts["inference-receipt.json"] == canonical(inference_receipt)
        assert artifacts["timed-query-receipt.json"] == canonical(timed_receipt)
        assert artifacts["timed-query-predictions.json"] == predictions
        assert "source.tar.gz" not in artifacts
        assert "environment.json" not in artifacts
        assert "lineage.json" not in artifacts
        assert json.loads(artifacts["worker-evidence.json"])["submission_digest"] == (
            recipe_doc["source"]["submission_digest"]
        )
        assert "predictions" not in json.loads(artifacts["worker-evidence.json"])
        assert set(json.loads(artifacts["image.json"])) == set(
            image.__dataclass_fields__
        )
        entry_root = tmp_path / "entries"
        artifact_root = tmp_path / "artifacts"
        entry_root.mkdir(mode=0o700)
        artifact_root.mkdir(mode=0o700)
        import scripts.dev.score_lab.public_unbound_custody as bank_custody
        import scripts.dev.score_lab.public_unbound_entry as bank_entry

        graph_bank_present = hasattr(bank_custody, "GRAPH_ROLE_SCHEMA_V5")
        with monkeypatch.context() as unavailable_role:
            if graph_bank_present:
                unavailable_role.delattr(bank_custody, "GRAPH_ROLE_SCHEMA_V5")
            with pytest.raises(
                RetentionUnavailable, match="graph_bank_role_contract_unavailable"
            ):
                retain_served_result(
                    adapter,
                    task_id,
                    artifact_directory=artifact_root,
                    entry_directory=entry_root,
                )
            assert not list(artifact_root.iterdir())
            assert not list(entry_root.iterdir())
        with monkeypatch.context() as unavailable_entry:
            unavailable_entry.setattr(
                bank_custody,
                "GRAPH_ROLE_SCHEMA_V5",
                "carbon.scorelab.public-model-artifact-roles.v5",
                raising=False,
            )
            unavailable_entry.delattr(bank_entry, "create_entry_v5")
            with pytest.raises(
                RetentionUnavailable, match="graph_bank_role_contract_unavailable"
            ):
                retain_served_result(
                    adapter,
                    task_id,
                    artifact_directory=artifact_root,
                    entry_directory=entry_root,
                )
        assert not list(artifact_root.iterdir())
        assert not list(entry_root.iterdir())
        for changed, reason in (
            (
                {
                    key: value
                    for key, value in private.items()
                    if key != "build_receipt"
                },
                "graph_worker_evidence_unavailable",
            ),
            ({**private, "build_receipt": []}, "graph_worker_evidence_unavailable"),
            (
                {
                    **private,
                    "build_receipt": {
                        **build_receipt,
                        "recipe_digest": _digest(b"other"),
                    },
                },
                "graph_build_receipt_changed",
            ),
        ):
            with provider._db() as db:
                db.execute(
                    "UPDATE direct_evidence SET body=? WHERE id=?",
                    (canonical(changed), task_id),
                )
            with pytest.raises(RetentionUnavailable, match=reason):
                retain_served_result(
                    adapter,
                    task_id,
                    artifact_directory=artifact_root,
                    entry_directory=entry_root,
                )
            assert not list(artifact_root.iterdir())
            assert not list(entry_root.iterdir())
        with provider._db() as db:
            db.execute(
                "UPDATE direct_evidence SET body=? WHERE id=?",
                (canonical(private), task_id),
            )
        (provider._source_path(task_id)).write_bytes(b"{}")
        with pytest.raises(
            RetentionUnavailable, match="admitted_graph_source_unavailable"
        ):
            _collect_graph_artifacts(
                provider, task_id, succeeded, evidence, recipe, material
            )
        provider._source_path(task_id).write_bytes(source)
        if graph_bank_present:
            first = retain_served_result(
                adapter,
                task_id,
                artifact_directory=artifact_root,
                entry_directory=entry_root,
            )
            assert first["status"] == "CREATED"
            assert first["score_state"] == "NOT_COMPUTED"
            assert first["official_eligible"] is False
            if timed_shape != "full":
                # Custody accepted the practice prefix and `per_call_s`; the
                # registered benchmark keeps its exact form at its registered
                # timing batch (tests/cpu/test_timed_receipt_pins.py), so a
                # practice-form receipt gives no public speed measurement: a
                # typed UNAVAILABLE, never a crash or a fabricated figure.
                assert first["measurement_state"] == "UNAVAILABLE"
                return
            assert first["measurement_state"] == "DEVELOPMENT_UNRANKED"
            measured = json.loads(first["measurement_path"].read_bytes())
            assert measured["task_id"] == task_id
            assert measured["entry_id"] == first["entry_id"]
            assert measured["source_state"] == (
                "MEASURED_ENGINEERING_REFERENCE_UNPINNED"
            )
            assert measured["result"]["status"] == "BENCHMARK_REDUCED"
            assert measured["result"]["score_status"] == "PACK_NOT_READY"
            assert measured["accuracy_ceiling"] is None
            assert measured["ranking"] is None
            assert measured["speedup_comparability"] == "NOT_ESTABLISHED"
            assert first["measurement_path"].parent != first["artifact_path"]
            import scripts.dev.score_lab.synthetic_linear_field_reference as public_source

            with monkeypatch.context() as unavailable_measurement:
                unavailable_measurement.setattr(
                    public_source,
                    "reduce_public_measurement",
                    lambda **_kwargs: (_ for _ in ()).throw(ValueError("not ready")),
                )
                retry = retain_served_result(
                    adapter,
                    task_id,
                    artifact_directory=artifact_root,
                    entry_directory=entry_root,
                )
                assert retry["status"] == "ALREADY_PRESENT_IDENTICAL"
                assert retry["score_state"] == "NOT_COMPUTED"
                assert retry["measurement_state"] == "UNAVAILABLE"
                assert first["measurement_path"].read_bytes() == canonical(measured)
            manifest = json.loads(
                (artifact_root / (task_id + ".roles.json")).read_bytes()
            )
            assert manifest["schema"] == bank_custody.GRAPH_ROLE_SCHEMA_V5
            assert manifest["roles"]["timed_receipt"]["file"] == (
                "timed-query-receipt.json"
            )
            assert "environment" not in manifest["roles"]
            assert manifest["roles"]["inference_receipt"]["file"] == (
                "inference-receipt.json"
            )
            assert (
                retain_served_result(
                    adapter,
                    task_id,
                    artifact_directory=artifact_root,
                    entry_directory=entry_root,
                )["status"]
                == "ALREADY_PRESENT_IDENTICAL"
            )
    finally:
        provider.close()


@pytest.mark.parametrize(
    "accuracy, expected",
    [
        ({}, "batched_measured"),
        ({"paired_repeat_procedure": "per_case"}, "per_case"),
    ],
)
def test_pair_procedure_is_the_selected_packs_registered_form(
    tmp_path, monkeypatch, accuracy, expected
):
    """The pack's public accuracy definition registers the paired repeat form."""
    from types import SimpleNamespace

    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.development_session import construction_recipe, paired_inference

    seen = {}

    def fake_pair(ledger, **call):
        seen.update(call)
        return SimpleNamespace(evidence={"fixture": True})

    monkeypatch.setattr(paired_inference, "infer_frozen_pair", fake_pair)
    monkeypatch.setattr(
        construction_recipe.ConstructionRecipe, "from_dict", staticmethod(lambda d: d)
    )
    monkeypatch.setattr(
        retention, "_private_evaluation_directory", lambda result, sid: tmp_path
    )
    roles = []
    snapshot = SimpleNamespace(
        manifest_digest="sha256:" + "a" * 64,
        read_json_role=lambda root, side, role, max_bytes: (
            roles.append((side, role)) or accuracy
        ),
    )
    kit = {
        "id": "c",
        "version": "1",
        "train_digest": "t",
        "interface_digest": "i",
        "construction_limits_digest": "l",
    }
    material = {
        "construction_kit": kit,
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "inference_wall_seconds_max": 60,
                "total_reconstruction_wall_seconds_max": 120,
            }
        },
        "interface_document": {"dtype": "<f8"},
        "practice_inputs": np.zeros((2, 1)),
        "expected_output_shape": (2, 1),
        "allowlist_bytes": b"",
    }
    provider = SimpleNamespace(
        ledger=object(),
        inference_image=object(),
        _requests={"rtsk_x": SimpleNamespace(recipe={})},
    )
    adapter = SimpleNamespace(
        owner=lambda sid: "owner",
        _provider=lambda owner: provider,
        discovery=SimpleNamespace(
            _material=material,
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_public_root=tmp_path,
        ),
    )
    raw = retention._inference_pair_raw(
        adapter, "rtsk_x", {}, {"state.npz": b"s"}, {"state_digest": "sd"}
    )
    assert seen["procedure"] == expected
    assert roles == [("public", "accuracy_definition")]
    assert json.loads(raw) == {"fixture": True}
