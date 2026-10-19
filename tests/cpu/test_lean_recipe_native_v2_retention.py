"""Retain real v2 build evidence through the existing pending ScoreLab bank."""

import base64
import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from test_direct_clean_rebuild_acceptance import _binding, _digest, _recipe
from test_lean_recipe_retention import _RealLocalRunner, _source_image

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.interface import Admitted
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    retain_served_result,
)
from carbon.development_session.bundle_construction_worker import (
    BUILD_PROGRAM,
    infer_public,
    reconstruct_public,
)
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.research import DirectTaskReceiptV3, DirectTaskStateV3, canonical_bytes


class _InputRetainingRunner(_RealLocalRunner):
    """Keep the exact worker input, rather than invoke retention's fallback."""

    def __call__(self, ledger, **request):
        result = super().__call__(ledger, **request)
        if request["source"] == BUILD_PROGRAM:
            inputs = ledger.root / result["operation"] / "input"
            inputs.mkdir()
            (inputs / "example.npz").write_bytes(request["files"]["example.npz"])
        return result


@pytest.fixture
def served_v2(tmp_path, monkeypatch):
    """Use actual fixed build/inference programs and actual task/bank APIs."""
    material = bundle_material_v5()
    image, installed = _source_image(tmp_path)
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda value: value,
    )
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    campaign = CampaignLedger(tmp_path / "campaign")
    provider = DirectDevelopmentTasksV3(
        root=tmp_path / "tasks",
        requester="miner",
        ledger=campaign,
        owner="miner",
        discovery=discovery,
        image_resolver=lambda ref: image,
        inference_image=image.parent,
    )
    try:
        adapter = LeanRecipeAdapter(
            discovery,
            lambda owner: provider if owner == "miner" else None,
            AttemptLedger(tmp_path / "attempts.sqlite3"),
            measure_query=True,
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
        task_id = adapter.evaluate(admitted)["task_id"]
        runner = _InputRetainingRunner(installed)
        build = reconstruct_public(
            campaign,
            owner="miner",
            identity="native-bank-build",
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
            identity="native-bank-infer",
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
        timed = infer_public(
            campaign,
            owner="miner",
            identity="native-bank-timed",
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
        native_path = build.state_path.parent / "native-predictions.json"
        example_path = campaign.root / build.worker_operation / "input" / "example.npz"
        prediction_path = (
            campaign.root / inferred.worker_operation / "snapshot" / "predictions.json"
        )
        native_raw = native_path.read_bytes()
        example_raw = example_path.read_bytes()
        predictions_raw = prediction_path.read_bytes()
        assert build.receipt["schema"] == "carbon.development.bundle-build.v2"
        assert build.receipt["example_digest"] == _digest(example_raw)
        assert build.receipt["native_predictions_digest"] == _digest(native_raw)
        assert build.receipt["train_digest"] == _digest(material["train"])
        # This scalar linear fixture has an exactly representable frozen graph.
        # Compare the actual outputs independently of the diagnostic helper.
        np.testing.assert_array_equal(
            np.asarray(json.loads(native_raw), dtype=np.float32),
            np.asarray(inferred.predictions, dtype=np.float32),
        )
        comparison = {
            "schema": "carbon.development.bundle-prediction-comparison.v1",
            "recipe_digest": recipe.digest,
            "state_digest": build.state_digest,
            "probe_digest": _digest(example_raw),
            "shape": list(material["expected_output_shape"]),
            "native_dtype": "float32",
            "lowered_dtype": "float32",
            "count": int(np.prod(material["expected_output_shape"])),
            "exact_equal": True,
            "mismatch_count": 0,
            "max_abs_delta": 0.0,
            "mean_abs_delta": 0.0,
        }
        queued = provider._views[task_id]
        terminal = DirectTaskReceiptV3(
            queued.task_id,
            DirectTaskStateV3.SUCCEEDED,
            queued.immutable_bindings,
            build.state_digest,
            inferred.predictions_digest,
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
            "timed_operation": timed.worker_operation,
            "timed_receipt": timed.receipt,
            "predictions_raw_base64": base64.b64encode(predictions_raw).decode(),
            "bundle_digest": image.provisioned.bundle.bundle_digest,
            "context_digest": image.provisioned.context_digest,
            "prediction_comparison": comparison,
        }
        with provider._db() as db:
            db.execute(
                "INSERT INTO direct_evidence VALUES(?,?)", (task_id, canonical(private))
            )
            db.execute(
                "UPDATE direct_tasks SET view=? WHERE id=?",
                (canonical_bytes(succeeded), task_id),
            )
        provider._views[task_id] = succeeded
        artifacts = tmp_path / "bank-artifacts"
        entries = tmp_path / "bank-entries"
        artifacts.mkdir(mode=0o700)
        entries.mkdir(mode=0o700)
        yield SimpleNamespace(
            adapter=adapter,
            provider=provider,
            task_id=task_id,
            artifacts=artifacts,
            entries=entries,
            private=private,
            comparison=comparison,
            native_path=native_path,
            native_raw=native_raw,
            example_path=example_path,
            example_raw=example_raw,
        )
    finally:
        provider.close()


def _retain(case):
    return retain_served_result(
        case.adapter,
        case.task_id,
        artifact_directory=case.artifacts,
        entry_directory=case.entries,
    )


def _store_private(case):
    with case.provider._db() as db:
        db.execute(
            "UPDATE direct_evidence SET body=? WHERE id=?",
            (canonical(case.private), case.task_id),
        )


def test_v2_retains_original_native_probe_and_unroled_diagnostic_in_bank_v5(served_v2):
    case = served_v2
    result = _retain(case)
    assert result["status"] == "CREATED"
    assert result["score_state"] == "NOT_COMPUTED"
    assert result["official_eligible"] is False
    entry_raw = result["entry_path"].read_bytes()
    entry = json.loads(entry_raw)
    assert entry["schema"] == "carbon.scorelab.public-model-entry.v5"
    assert entry["score_state"] == "NOT_COMPUTED"
    assert entry["official_eligible"] is False
    assert entry["qualification_state"] == "NOT_CLAIMED"
    manifest = json.loads(
        (case.artifacts / (case.task_id + ".roles.json")).read_bytes()
    )
    for name, original in (
        ("native-predictions.json", case.native_raw),
        ("example.npz", case.example_raw),
    ):
        assert (result["artifact_path"] / name).read_bytes() == original
        assert manifest["retained_files"][name] == _digest(original)
        assert entry["original_files"][name]["sha256"] == _digest(original)
    assert entry["roles"]["native_predictions"]["sha256"] == _digest(case.native_raw)
    diagnostic_path = result["artifact_path"] / "prediction-comparison.json"
    diagnostic_raw = diagnostic_path.read_bytes()
    assert json.loads(diagnostic_raw) == case.comparison
    assert manifest["retained_files"][diagnostic_path.name] == _digest(diagnostic_raw)
    assert entry["original_files"][diagnostic_path.name]["sha256"] == _digest(
        diagnostic_raw
    )
    assert diagnostic_path.name not in {
        role["file"] for role in entry["roles"].values()
    }
    # The optional private field is checked when present; absent fields still
    # require recomputation from the same retained originals, not a new score.
    case.private.pop("prediction_comparison")
    _store_private(case)
    assert _retain(case)["status"] == "ALREADY_PRESENT_IDENTICAL"
    diagnostic_path.write_bytes(b"{}")
    with pytest.raises(RetentionUnavailable, match="operator_bank_custody_unavailable"):
        _retain(case)
    assert result["entry_path"].read_bytes() == entry_raw


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        ("native", "native_prediction_snapshot_changed"),
        ("example", "build_example_snapshot_changed"),
        ("private_comparison", "native_comparison_changed"),
    ],
)
def test_v2_changed_original_or_private_diagnostic_cannot_enter_bank(
    served_v2, changed, reason
):
    case = served_v2
    if changed == "native":
        case.native_path.write_bytes(b"[0]")
    elif changed == "example":
        case.example_path.write_bytes(b"changed original input")
    else:
        case.private["prediction_comparison"] = {
            **case.comparison,
            "max_abs_delta": 1.0,
        }
        _store_private(case)
    with pytest.raises(RetentionUnavailable, match=reason):
        _retain(case)
    assert list(case.entries.iterdir()) == []
    assert list(case.artifacts.iterdir()) == []
