"""Regrade of a retained bundle model on a rotated evaluation pack (Route A).

The grading core is shared with normal retention (test_normal_dual_pack_retention); these
tests cover what a regrade adds: the owner copied from the retained task, the same frozen
state run again on the new case bank, a new bank entry, REGRADE provenance, and a retry
that never replays an identity.
"""

import base64
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_direct_clean_rebuild_acceptance import _binding, _recipe
from test_lean_recipe_retention import _RealLocalRunner, _source_image

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import Admitted
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session.bundle_construction_worker import (
    _tensors,
    infer_public,
    reconstruct_public,
)
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.research import DirectTaskReceiptV3, DirectTaskStateV3, canonical_bytes

PACK = "sha256:" + "e" * 64


def _retained(tmp_path, monkeypatch):
    """One real local bundle result, retained into the bank with its measured query."""
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
    attempts = tmp_path / "attempts"
    attempts.mkdir(mode=0o700)
    adapter = LeanRecipeAdapter(
        discovery,
        lambda owner: provider if owner == "miner" else None,
        AttemptLedger(attempts / "ledger.sqlite3"),
        measure_query=True,
    )
    recipe = _recipe(material, image)
    queued = adapter.evaluate(
        Admitted(
            "miner",
            {},
            adapter.challenge_id,
            adapter.challenge_version,
            recipe.to_dict(),
            adapter.contract_digest,
        )
    )
    task_id = queued["task_id"]
    runner = _RealLocalRunner(installed)
    kwargs = {"owner": "miner", "image": image, "recipe": recipe, "runner": runner}
    build = reconstruct_public(
        campaign,
        identity="test-build",
        challenge_binding=_binding(material),
        train=material["train"],
        example=material["example"],
        seed=11,
        allowlist_bytes=material["allowlist_bytes"],
        **kwargs,
    )
    infer = dict(
        challenge_binding=_binding(material),
        build=build,
        inputs=material["practice_inputs"],
        expected_output_shape=material["expected_output_shape"],
        expected_output_dtype="float32",
        allowlist_bytes=material["allowlist_bytes"],
        inference_image=image.parent,
        **kwargs,
    )
    inferred = infer_public(campaign, identity="test-infer", **infer)
    timed = infer_public(campaign, identity="test-timed", measure_query=True, **infer)
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
    raw = (
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
        "predictions_raw_base64": base64.b64encode(raw).decode(),
        "bundle_digest": image.provisioned.bundle.bundle_digest,
        "context_digest": image.provisioned.context_digest,
        "timed_operation": timed.worker_operation,
        "timed_receipt": timed.receipt,
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
    entries, artifacts = tmp_path / "bank-entries", tmp_path / "bank-artifacts"
    entries.mkdir(mode=0o700)
    artifacts.mkdir(mode=0o700)
    first = retention.retain_served_bundle_result(
        adapter, task_id, artifact_directory=artifacts, entry_directory=entries
    )
    assert first["status"] == "CREATED"
    return SimpleNamespace(
        material=material,
        provider=provider,
        adapter=adapter,
        runner=runner,
        task_id=task_id,
        first=first,
        entries=entries,
        artifacts=artifacts,
        build=build,
        inferred=inferred,
    )


def _rotate(fixture, monkeypatch, tmp_path, *, scale=0.5, copies=1):
    """Select a rotated pack: a new case bank, same shape and dtype. With ``copies`` > 1 the bank is
    larger than the task's practice query (distinct rows), as a sealed/pool pack's bank is.
    """
    import numpy as np

    practice = fixture.material["practice_inputs"]
    bank = np.concatenate(
        [
            (practice * scale * (1 + 0.1 * k)).astype(practice.dtype)
            for k in range(copies)
        ]
    )
    bank_raw = _tensors(inputs=bank)
    snapshot = SimpleNamespace(
        manifest_digest=PACK, read_role=lambda *_args, **_kwargs: bank_raw
    )
    fixture.adapter.discovery = SimpleNamespace(
        _material=fixture.material,
        evaluation_pack_snapshot=snapshot,
        evaluation_pack_digest=PACK,
        evaluation_pack_private_root=Path(tmp_path),
    )
    fixture.adapter._provider = lambda _owner: fixture.provider
    monkeypatch.setattr(
        retention,
        "_retain_private_pack_binding",
        lambda _adapter, _provider, _sid, _task, result: {
            **result,
            "evaluation_pack_digest": PACK,
        },
    )
    graded = []

    def grade(adapter, submission_id, result, artifacts, evidence=None, regrade=None):
        graded.append((submission_id, result, artifacts, evidence, regrade))
        return {**result, "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY"}

    monkeypatch.setattr(retention, "_retain_selected_pack_evaluation", grade)
    return bank_raw, graded


def _regrade(fixture):
    return retention.regrade_retained_entry(
        fixture.adapter,
        fixture.first["entry_id"],
        artifact_directory=fixture.artifacts,
        entry_directory=fixture.entries,
        runner=fixture.runner,
    )


def test_regrade_runs_the_same_state_on_the_new_bank_and_grades_a_new_entry(
    tmp_path, monkeypatch
):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        bank_raw, graded = _rotate(fixture, monkeypatch, tmp_path)
        result = _regrade(fixture)
        assert result["status"] == "CREATED"
        assert result["regrade_of"] == fixture.first["entry_id"]
        assert result["entry_id"] != fixture.first["entry_id"]
        assert result["official_eligible"] is False
        assert result["score_state"] == "NOT_COMPUTED"
        old = json.loads(fixture.first["entry_path"].read_bytes())
        new = json.loads(result["entry_path"].read_bytes())
        assert new["state_digest"] == old["state_digest"]
        assert new["recipe_digest"] == old["recipe_digest"]
        assert new["prediction_digest"] != old["prediction_digest"]
        root = result["artifact_path"]
        assert (root / "inputs.npz").read_bytes() == bank_raw
        assert (root / "state.npz").read_bytes() == (
            fixture.first["artifact_path"] / "state.npz"
        ).read_bytes()
        assert (root / "timed-query-receipt.json").is_file()
        # The grading core got the regrade identity: owner from the retained task.
        ((submission_id, _, artifacts, evidence, regrade),) = graded
        assert submission_id == result["regrade_task_id"]
        assert regrade.owner == "miner"
        assert regrade.origin_entry_id == fixture.first["entry_id"]
        assert artifacts["inputs.npz"] == bank_raw
        assert (
            evidence["inference_image_id"] == fixture.provider.inference_image.image_id
        )
        provenance = json.loads(
            (
                root.parent
                / (submission_id + ".evaluation")
                / "regrade-provenance.json"
            ).read_bytes()
        )
        assert provenance["kind"] == "REGRADE"
        assert provenance["hotkey"] == "miner"
        assert provenance["state_digest"] == old["state_digest"]
        assert provenance["evaluation_pack_digest"] == PACK
        # The origin entry and its files are untouched.
        assert json.loads(fixture.first["entry_path"].read_bytes()) == old
    finally:
        fixture.provider.close()


def test_regrade_retry_reads_retained_bytes_and_never_replays_an_inference(
    tmp_path, monkeypatch
):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        _, graded = _rotate(fixture, monkeypatch, tmp_path)
        first = _regrade(fixture)
        calls = len(fixture.runner.calls)
        again = _regrade(fixture)
        assert again["status"] == "ALREADY_PRESENT_IDENTICAL"
        assert again["entry_id"] == first["entry_id"]
        assert len(fixture.runner.calls) == calls
        assert len(graded) == 2
    finally:
        fixture.provider.close()


def test_regrade_refuses_a_changed_origin_or_an_unknown_entry(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        _rotate(fixture, monkeypatch, tmp_path)
        with pytest.raises(retention.RetentionUnavailable) as unknown:
            retention.regrade_retained_entry(
                fixture.adapter,
                "sha256:" + "0" * 64,
                artifact_directory=fixture.artifacts,
                entry_directory=fixture.entries,
                runner=fixture.runner,
            )
        assert "unavailable" in str(unknown.value) or "regrade" in str(unknown.value)
        state = fixture.first["artifact_path"] / "state.npz"
        state.chmod(0o600)
        state.write_bytes(b"tampered")
        with pytest.raises(
            retention.RetentionUnavailable, match="regrade_origin_file_changed"
        ):
            _regrade(fixture)
    finally:
        fixture.provider.close()


def test_regrade_refuses_a_bank_the_interface_does_not_allow(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        practice = fixture.material["practice_inputs"]
        _rotate(fixture, monkeypatch, tmp_path)
        wrong = _tensors(inputs=practice.astype("float64"))
        fixture.adapter.discovery.evaluation_pack_snapshot.read_role = (
            lambda *_args, **_kwargs: wrong
        )
        with pytest.raises(
            retention.RetentionUnavailable, match="regrade_case_bank_contract_changed"
        ):
            _regrade(fixture)
    finally:
        fixture.provider.close()


def test_regrade_refuses_without_a_selected_pack(tmp_path, monkeypatch):
    fixture = _retained(tmp_path, monkeypatch)
    try:
        with pytest.raises(
            retention.RetentionUnavailable, match="evaluation_pack_not_selected"
        ):
            _regrade(fixture)
    finally:
        fixture.provider.close()


# --- the regrade is recorded for the incumbent's own submission id (KOTH lookup) -------


def test_regraded_evidence_is_found_for_the_incumbent_on_the_new_key(tmp_path):
    from test_bank_private_evaluation import admitted, inputs
    from test_score_lab_private_evaluation_evidence import _graph_case

    from carbon.battery.pool_store import PoolStore, StateError
    from carbon.challenge_validator.bank_promotion import BankPromotion

    case = _graph_case(tmp_path)
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    for model in ("king", "challenger"):
        admitted(store, case, model)
    store.set_incumbent("king", "historical fixture")
    # The king was graded on the old exam version.
    old_pin, old_args = inputs(case, version="synthetic-eval-v1")
    BankPromotion(store, registered_source_receipt_sha256=old_pin).retain_private(
        "king", **old_args
    )
    # The exam rotates: the challenger is graded on the new key, the king has no evidence.
    pin, args = inputs(case, version="synthetic-eval-v2")
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    challenger = flow.retain_private("challenger", **args)
    key = challenger["evaluation_key"]
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        flow.private_pair("challenger", key)
    # The regrade records the king's evaluation under the king's own submission id.
    regrade = retention._Regrade(
        "fixture-king", object(), "king", case["entry"]["entry_id"], flow
    )
    recorded = retention._record_regraded_evidence(regrade, args)
    pair = flow.private_pair("challenger", key)
    assert pair["incumbent"] == recorded
    assert pair["incumbent"]["submission_id"] == "king"
    assert pair["expected_incumbent"] == "king"
    # A bare pool store (the CLI's --pool-store) gets the registered pin and files the same.
    bare = retention._Regrade(
        "fixture-king", object(), "king", case["entry"]["entry_id"], store
    )
    assert retention._record_regraded_evidence(bare, args, pin) == recorded


def test_recording_a_regrade_names_the_store_refusal(tmp_path):
    from test_bank_private_evaluation import admitted, inputs
    from test_score_lab_private_evaluation_evidence import _graph_case

    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator.bank_promotion import BankPromotion

    case = _graph_case(tmp_path)
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    admitted(store, case, "king")
    _, args = inputs(case)
    regrade = retention._Regrade(
        "fixture-king", object(), "king", "e", BankPromotion(store)
    )
    with pytest.raises(
        retention.RetentionUnavailable, match="regrade_record_source_pin_missing"
    ):
        retention._record_regraded_evidence(regrade, args)


def test_the_grading_core_hands_the_binding_inputs_to_the_promotion(
    tmp_path, monkeypatch
):
    from test_normal_dual_pack_retention import _fixture, _producer

    from carbon.scoring import private_evaluation_source as source
    from carbon.scoring.private_evaluation_evidence import (
        bind_private_evaluation_evidence,
    )

    fixture = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(source, "produce_dual_benchmark_input", _producer(fixture))
    first = fixture.retain()
    assert first["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    written = json.loads(first["private_evaluation_path"].read_bytes())

    class Promotion:
        def __init__(self):
            self.calls = []

        def retain_private(self, submission_id, **inputs):
            self.calls.append((submission_id, inputs))
            return {"recorded": submission_id}

    promotion = Promotion()
    regrade = retention._Regrade(
        "fixture-owner", object(), "origin-task", "origin-entry", promotion
    )
    again = retention._retain_selected_pack_evaluation(
        fixture.adapter, fixture.task_id, first, fixture.artifacts, None, regrade
    )
    assert again["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    ((submission_id, inputs),) = promotion.calls
    assert submission_id == "origin-task"
    assert "registered_source_receipt_sha256" not in inputs
    # The same inputs and the registered pin reproduce the written binding exactly.
    assert (
        bind_private_evaluation_evidence(
            registered_source_receipt_sha256=written["source_receipt_sha256"], **inputs
        )
        == written
    )


def test_the_bank_inference_carries_the_versions_registered_rebuild_wall(
    tmp_path, monkeypatch
):
    """valV3, 2026-10-27: the regrade's inference over a pool pack's bank passed the policy's
    inference seconds without the version's rebuild wall, and the carrier refused
    'bounded worker wall allowance required'. The counted bank grade runs the same inference.
    """
    from carbon.challenge_kit.version_registry import REBUILD_LIMIT_SECONDS
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session.construction_recipe import RecipeRefused

    fixture = _retained(tmp_path, monkeypatch)
    try:
        _rotate(fixture, monkeypatch, tmp_path)
        policy = fixture.material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        policy.update(
            build_wall_seconds_max=REBUILD_LIMIT_SECONDS,
            inference_wall_seconds_max=REBUILD_LIMIT_SECONDS,
        )
        seen = []

        def record(ledger, **kwargs):
            seen.append(kwargs)
            raise RecipeRefused("recorded")

        monkeypatch.setattr(worker, "_infer_state", record)
        monkeypatch.setattr(worker, "verify_direct_resource_policy", lambda *_: None)
        with pytest.raises(retention.RetentionUnavailable, match="regrade_inference_"):
            _regrade(fixture)
        assert seen[0]["seconds"] == REBUILD_LIMIT_SECONDS
        assert seen[0]["rebuild_wall_seconds"] == REBUILD_LIMIT_SECONDS
        # The counted flow runs this same inference.
        seen.clear()
        with pytest.raises(retention.RetentionUnavailable, match="regrade_inference_"):
            retention.regrade_retained_entry(
                fixture.adapter,
                fixture.first["entry_id"],
                artifact_directory=fixture.artifacts,
                entry_directory=fixture.entries,
                runner=fixture.runner,
                counted=True,
            )
        assert seen[0]["rebuild_wall_seconds"] == REBUILD_LIMIT_SECONDS
    finally:
        fixture.provider.close()


def test_a_counted_bank_grade_runs_the_retained_state_on_the_bank_and_takes_the_miners_slot(
    tmp_path, monkeypatch
):
    """End to end up to the grading core (stubbed, as in the regrade tests above): the real
    retained state is run over the pack's bank by the real local runner, a new bank entry is
    created, and the grade is filed as the miner's COUNTED one - the slot is a GRADED one
    under the miner's own submission id and signed epoch, not a REGRADE."""
    from carbon.challenge_validator import exam_cap

    fixture = _retained(tmp_path, monkeypatch)
    try:
        bank_raw, graded = _rotate(fixture, monkeypatch, tmp_path)
        pools = []

        def grade(
            adapter,
            submission_id,
            result,
            artifacts,
            evidence=None,
            regrade=None,
            pool_store=None,
        ):
            graded.append((submission_id, result, artifacts, evidence, regrade))
            pools.append(pool_store)
            return {**result, "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY"}

        monkeypatch.setattr(retention, "_retain_selected_pack_evaluation", grade)
        adapter = fixture.adapter
        # the rotated-pack stand-in discovery has no `info`, which the real owner lookup reads
        adapter.owner = lambda _task: "miner"
        adapter.exam_cadence = {
            "capacity_cpu_hours_per_day": 270.0,
            "rebuild_cpu_hours_placeholder": {adapter.challenge_id: 1.0},
        }
        adapter.ledger.record(
            SimpleNamespace(
                hotkey="miner",
                receipt={"sequence": 1, "digest": "d", "block": 360 * 7 + 5},
                contract_digest=adapter.contract_digest,
            ),
            kind="OUTCOME",
            submission_id=fixture.task_id,
        )
        result = retention._counted_bank_grade(
            adapter,
            fixture.task_id,
            fixture.first,
            pool_store="STORE",
            artifact_directory=fixture.artifacts,
            entry_directory=fixture.entries,
            runner=fixture.runner,
        )
        assert (
            result["entry_id"] == fixture.first["entry_id"]
        )  # the retained origin entry
        assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
        bank_entry = json.loads(
            next(
                path
                for path in fixture.entries.iterdir()
                if path.name != fixture.first["entry_path"].name
            ).read_bytes()
        )
        assert result["bank_grade_entry_id"] == bank_entry["entry_id"]
        assert (
            bank_entry["state_digest"]
            == json.loads(fixture.first["entry_path"].read_bytes())["state_digest"]
        )
        # The grading core got a COUNTED identity, keyed by the miner's own submission.
        ((regrade_id, _, artifacts, _, regrade),) = graded
        assert regrade.counted is True and regrade.origin_task_id == fixture.task_id
        assert pools == ["STORE"]  # KOTH is filed in the pool store under the origin id
        assert (
            artifacts["inputs.npz"] == bank_raw
        )  # the pack's bank, not the practice query
        assert regrade_id != fixture.task_id
        with adapter.ledger._db() as db:
            rows = db.execute(
                "SELECT submission_id, kind, state, hotkey, epoch FROM exam_graded"
            ).fetchall()
        assert rows == [(fixture.task_id, "GRADED", "RESERVED", "miner", 7)]
        provenance = json.loads(
            (
                fixture.artifacts
                / (regrade_id + ".evaluation")
                / "regrade-provenance.json"
            ).read_bytes()
        )
        assert provenance["kind"] == "COUNTED_GRADE"
        assert exam_cap.EPOCH_BLOCKS == 360
    finally:
        fixture.provider.close()


def test_a_counted_pool_grade_repeats_and_times_the_bank_it_graded(
    tmp_path, monkeypatch
):
    """valV3 2026-10-27 (single_call_row_not_in_the_delivered_query): the pack's bank is larger than the
    task's practice query. The REAL counted regrade infers over the bank, and then the REAL repeat-pair and
    single-call stages (the real local runner, the real derived program) run on that same bank: the 20 timed
    rows are drawn from the bank's pool rows, found in the delivered rows, and their answers equal the
    graded run's."""
    import numpy as np

    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session import paired_inference, single_call_timing
    from carbon.scoring import pool_exam, sealed_batch_source

    fixture = _retained(tmp_path, monkeypatch)
    try:
        bank_raw, _ = _rotate(fixture, monkeypatch, tmp_path, copies=13)
        adapter = fixture.adapter
        practice_rows = len(fixture.material["practice_inputs"])
        bank = np.load(__import__("io").BytesIO(bank_raw))["inputs"]
        assert len(bank) == 13 * practice_rows
        pool_rows = len(bank) - practice_rows
        assert pool_rows >= single_call_timing.SAMPLE
        cohorts = ["cell"] * practice_rows + [pool_exam.POOL_COHORT] * pool_rows
        # the synthetic fixture stands in for a registered pool version
        monkeypatch.setattr(retention, "_pool_graded_version", lambda _adapter: True)
        adapter.discovery.evaluation_pack_public_root = Path(tmp_path)
        key = bytes(range(32))
        adapter.speed_sample_key = key
        adapter.copy_hotkey = None
        adapter.owner = lambda _task: "miner"
        adapter.exam_cadence = {
            "capacity_cpu_hours_per_day": 270.0,
            "rebuild_cpu_hours_placeholder": {adapter.challenge_id: 1.0},
        }
        adapter.ledger.record(
            SimpleNamespace(
                hotkey="miner",
                receipt={"sequence": 1, "digest": "d", "block": 360 * 7 + 5},
                contract_digest=adapter.contract_digest,
            ),
            kind="OUTCOME",
            submission_id=fixture.task_id,
        )
        monkeypatch.setattr(
            sealed_batch_source,
            "resolve",
            lambda **_: (
                {"inputs": bank, "cohorts": cohorts},
                SimpleNamespace(POOL_GRADED=True),
            ),
        )
        from carbon.challenge_kit import physical_pack

        monkeypatch.setattr(
            physical_pack,
            "development_bank",
            lambda *_: {"inputs": fixture.material["practice_inputs"]},
        )
        # the stages run on the real local runner (the receiver's carrier is not available here)
        real_infer_state = worker._infer_state
        monkeypatch.setattr(
            worker,
            "_infer_state",
            lambda ledger, **kw: real_infer_state(
                ledger, **{**kw, "runner": fixture.runner}
            ),
        )
        # the repeat pair needs the carrier's own accounting rows, which the local runner does not write:
        # record what it is asked to run instead
        pairs = []

        def pair(ledger, **kw):
            pairs.append(kw)
            return paired_inference.InferencePairResult({"recorded": True})

        monkeypatch.setattr(paired_inference, "infer_frozen_pair", pair)
        monkeypatch.setattr(
            adapter.discovery.evaluation_pack_snapshot,
            "read_json_role",
            lambda *_a, **_k: {"paired_repeat_procedure": "per_case"},
            raising=False,
        )
        seen = {}

        def grade(
            adapter,
            submission_id,
            result,
            artifacts,
            evidence=None,
            regrade=None,
            pool_store=None,
        ):
            entry = json.loads(result["entry_path"].read_bytes())
            seen["pair"] = retention._inference_pair_raw(
                adapter, submission_id, result, artifacts, entry, regrade
            )
            # the local runner runs the fixed programs only: admit Carbon's derived single-call program
            import test_direct_clean_rebuild_acceptance as local

            monkeypatch.setattr(
                local,
                "INFER_PROGRAM",
                single_call_timing.program(worker.INFER_PROGRAM),
            )
            seen["single"] = retention._single_call_raw(
                adapter, submission_id, result, artifacts, entry, regrade
            )
            seen["artifacts"] = artifacts
            return {**result, "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY"}

        monkeypatch.setattr(retention, "_retain_selected_pack_evaluation", grade)
        retention._counted_bank_grade(
            adapter,
            fixture.task_id,
            fixture.first,
            pool_store="STORE",
            artifact_directory=fixture.artifacts,
            entry_directory=fixture.entries,
            runner=fixture.runner,
        )
        assert (
            seen["artifacts"]["inputs.npz"] == bank_raw
        )  # the graded query is the bank
        # the repeat pair is asked to run over the bank's rows and their output shape, not the practice query
        assert len(pairs) == 1 and len(pairs[0]["inputs"]) == len(bank)
        assert pairs[0]["expected_output_shape"][0] == len(bank)
        document = json.loads(seen["single"])
        seconds, matched = single_call_timing.read_side_file(seen["single"])
        assert len(seconds) == single_call_timing.SAMPLE
        assert matched is True  # the timed calls answered what the graded run did
        # every timed row is a pool row of the BANK, none is a practice row
        assert all(practice_rows <= i for i in document["indices"])
    finally:
        fixture.provider.close()
