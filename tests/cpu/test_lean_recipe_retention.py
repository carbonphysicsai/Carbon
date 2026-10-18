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

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.interface import Admitted
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    retain_served_bundle_result,
)
from carbon.development_session.bundle_construction_worker import (
    infer_public,
    reconstruct_public,
)
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
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.research import DirectTaskReceiptV3, DirectTaskStateV3, canonical_bytes


class _RealLocalRunner(LocalProcessRunner):
    def __call__(self, ledger, **request):
        result = super().__call__(ledger, **request)
        operation = f"operation-{len(self.calls):064x}"
        (ledger.root / result["operation"]).rename(ledger.root / operation)
        return {**result, "operation": operation}


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
            measure_query=measure_query,
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
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
        assert ("inference_receipt" in manifest["roles"]) is (not measure_query)
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
