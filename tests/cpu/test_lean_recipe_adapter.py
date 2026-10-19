"""The served recipe reaches one durable DEVELOPMENT task, never a score."""

import json
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import Adapters, AttemptLedger, Submission, Validator
from carbon.challenge_validator.interface import Admitted, Unavailable
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter


def test_revoked_retained_owner_does_not_starve_registered_owner_progress(
    tmp_path, monkeypatch
):
    from carbon.research import DirectTaskStateV3

    _, _, discovery = _fixture(tmp_path, monkeypatch, material=bundle_material_v5())
    revoked = "rtsk_" + "1" * 64
    active = "rtsk_" + "2" * 64
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.contract_digest = "sha256:" + "3" * 64
    adapter.discovery = discovery
    adapter.ledger = SimpleNamespace(submitted_outcomes=lambda _: (revoked, active))
    dispatched = []
    provider = SimpleNamespace(
        get_research_result=lambda _: SimpleNamespace(
            task=SimpleNamespace(state=DirectTaskStateV3.QUEUED)
        ),
        run_queued_task=lambda task_id: dispatched.append(task_id.value),
    )

    def owner(submission_id):
        if submission_id == revoked:
            raise Unavailable("direct_provider_registration_unavailable")
        return "registered"

    adapter.owner = owner
    adapter._provider = lambda _: provider
    assert adapter.advance() == 1
    assert dispatched == [active]
    assert adapter.status()["submissions"] == 1


def test_signed_door_screens_and_admits_one_bound_v13_task(tmp_path, monkeypatch):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    start_task = provider.start_research_task
    resolve_image = provider._resolved_image
    starting_task = False

    def resolve_during_task(request):
        assert starting_task, "the signed door must not prepare an environment"
        return resolve_image(request)

    def start_with_source_inspection(*args, **kwargs):
        nonlocal starting_task
        starting_task = True
        try:
            return start_task(*args, **kwargs)
        finally:
            starting_task = False

    monkeypatch.setattr(provider, "_resolved_image", resolve_during_task)
    monkeypatch.setattr(provider, "start_research_task", start_with_source_inspection)
    try:
        attempt_root = tmp_path / "attempts"
        attempt_root.mkdir(mode=0o700)
        attempt_root.chmod(0o700)
        ledger = AttemptLedger(attempt_root / "ledger.sqlite3")
        adapter = LeanRecipeAdapter(
            discovery, lambda owner: provider if owner == "miner" else None, ledger
        )
        door = Validator(Adapters([adapter]), ledger)
        submission = Submission(
            "miner",
            {"sequence": 1, "digest": "0" * 64},
            adapter.challenge_id,
            adapter.challenge_version,
            json.dumps(request.recipe, sort_keys=True),
            adapter.contract_digest,
        )
        screened = door.screen(submission)
        assert screened.admitted.strategy == request.recipe
        first = door.evaluate(submission)
        second = door.evaluate(submission)
        assert first["kind"] == second["kind"] == "OUTCOME"
        outcome = first["outcome"]
        assert outcome["submission_id"] == second["outcome"]["submission_id"]
        assert outcome["state"] == "ADMITTED"
        assert outcome["evidence"].startswith("DEVELOPMENT")
        assert outcome["qualification"] is outcome["reward"] is False
        assert len(provider.queued_tasks()) == 1
        missing_graph = json.loads(submission.strategy_json)
        missing_graph["source"] = {
            "kind": "graph",
            "submission_digest": "sha256:" + "a" * 64,
        }
        missing_graph["procedure"]["entrypoint"] = None
        missing = door.evaluate(
            Submission(
                "miner",
                submission.receipt,
                adapter.challenge_id,
                adapter.challenge_version,
                json.dumps(missing_graph),
                adapter.contract_digest,
            )
        )
        assert (missing["kind"], missing["code"]) == (
            "UNAVAILABLE",
            "construction_recipe_graph_workspace_missing",
        )
        assert len(provider.queued_tasks()) == 1
        assert (
            door.outcome(adapter.contract_digest, outcome["submission_id"], "miner")[
                "outcome"
            ]
            == outcome
        )
        assert (
            door.outcome(adapter.contract_digest, outcome["submission_id"], "other")[
                "code"
            ]
            == "unknown_submission"
        )
        with pytest.raises(LookupError, match="score_pack_unbound"):
            adapter.score_record(outcome["submission_id"])

        wrong = json.loads(submission.strategy_json)
        wrong["challenge"]["train_digest"] = "sha256:" + "f" * 64
        refused = door.screen(
            Submission(
                "miner",
                submission.receipt,
                adapter.challenge_id,
                adapter.challenge_version,
                json.dumps(wrong),
                adapter.contract_digest,
            )
        )
        assert (refused["kind"], refused["code"]) == (
            "REFUSED",
            "construction_recipe_binding_mismatch",
        )
        assert len(provider.queued_tasks()) == 1
        invalid_source = json.loads(submission.strategy_json)
        invalid_source["source"] = {"kind": "unknown"}
        refused_source = door.screen(
            Submission(
                "miner",
                submission.receipt,
                adapter.challenge_id,
                adapter.challenge_version,
                json.dumps(invalid_source),
                adapter.contract_digest,
            )
        )
        assert (refused_source["kind"], refused_source["code"]) == (
            "REFUSED",
            "construction_recipe_source_invalid",
        )
        pretrained = json.loads(submission.strategy_json)
        pretrained["procedure"]["initial_state"] = {"weights": [1]}
        refused_state = door.screen(
            Submission(
                "miner",
                submission.receipt,
                adapter.challenge_id,
                adapter.challenge_version,
                json.dumps(pretrained),
                adapter.contract_digest,
            )
        )
        assert (refused_state["kind"], refused_state["code"]) == (
            "REFUSED",
            "construction_recipe_pretrained_state_forbidden",
        )
        assert (
            door.screen(
                Submission(
                    "miner",
                    submission.receipt,
                    adapter.challenge_id,
                    adapter.challenge_version,
                    submission.strategy_json + " " * 65_536,
                    adapter.contract_digest,
                )
            )["code"]
            == "oversized_submission"
        )
    finally:
        provider.close()


def test_trusted_query_measurement_is_prospective_and_keeps_default_unbound(
    tmp_path, monkeypatch
):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    try:
        root = tmp_path / "attempts"
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        ledger = AttemptLedger(root / "ledger.sqlite3")
        owner_provider = lambda owner: provider if owner == "miner" else None
        default = LeanRecipeAdapter(discovery, owner_provider, ledger)
        measured = LeanRecipeAdapter(
            discovery, owner_provider, ledger, measure_query=True
        )
        with pytest.raises(TypeError, match="verified discovery"):
            LeanRecipeAdapter(discovery, owner_provider, ledger, measure_query=1)
        recipe = default.validate_strategy(request.recipe)
        assert (
            default.identities()["rule_digest"] != measured.identities()["rule_digest"]
        )
        assert (
            default._request("miner", recipe).idempotency_key
            != measured._request("miner", recipe).idempotency_key
        )
        submission = Admitted(
            "miner",
            {},
            default.challenge_id,
            default.challenge_version,
            request.recipe,
            default.contract_digest,
        )
        historical = default.evaluate(submission)
        prospective = measured.evaluate(submission)
        assert historical["state"] == prospective["state"] == "ADMITTED"
        assert historical["task_id"] != prospective["task_id"]
        assert historical["task_id"] not in provider._measured_tasks
        assert prospective["task_id"] in provider._measured_tasks
        assert default.owner(historical["task_id"]) == "miner"
        assert measured.owner(prospective["task_id"]) == "miner"
        assert default.owner(prospective["task_id"]) is None
        assert measured.owner(historical["task_id"]) is None
        assert default.status()["submissions"] == 1
        assert measured.status()["submissions"] == 1
        assert default.status()["score_pack"] is None
        assert measured.status()["score_pack"] is None
        with pytest.raises(LookupError, match="score_pack_unbound"):
            measured.score_record(prospective["submission_id"])
    finally:
        provider.close()
    reopened = provider_factory()
    try:
        retained_ledger = AttemptLedger(root / "ledger.sqlite3")
        retained_provider = lambda owner: reopened if owner == "miner" else None
        measured_reopened = LeanRecipeAdapter(
            discovery, retained_provider, retained_ledger, measure_query=True
        )
        assert measured_reopened.owner(prospective["task_id"]) == "miner"
        assert measured_reopened.owner(historical["task_id"]) is None
        assert measured_reopened.status()["submissions"] == 1
    finally:
        reopened.close()


@pytest.mark.parametrize("measure_query", [False, True])
def test_retained_owner_rejects_opposite_measurement_profile_after_refused_start(
    tmp_path, monkeypatch, measure_query
):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    ledger_path = root / "ledger.sqlite3"
    first = provider_factory()
    try:
        ledger = AttemptLedger(ledger_path)
        adapter = LeanRecipeAdapter(
            discovery,
            lambda owner: first if owner == "miner" else None,
            ledger,
            measure_query=measure_query,
        )
        recipe = adapter.validate_strategy(request.recipe)
        same_request = adapter._request("miner", recipe)
        task = first.start_research_task(
            same_request, measure_query=not measure_query
        ).task
        submission = Admitted(
            "miner",
            {},
            adapter.challenge_id,
            adapter.challenge_version,
            request.recipe,
            adapter.contract_digest,
        )
        with pytest.raises(Unavailable, match="direct_provider_unavailable"):
            adapter.evaluate(submission)
        assert ledger.submitted_outcomes(adapter.contract_digest) == (
            task.task_id.value,
        )
        assert adapter.owner(task.task_id.value) is None
        assert adapter.status()["submissions"] == 0
        with pytest.raises(LookupError, match="unknown_submission"):
            adapter.outcome(task.task_id.value)
        assert adapter.advance() == 0
        assert first._views[task.task_id.value].state == task.state
    finally:
        first.close()

    reopened = provider_factory()
    try:
        retained_ledger = AttemptLedger(ledger_path)
        retained = LeanRecipeAdapter(
            discovery,
            lambda owner: reopened if owner == "miner" else None,
            retained_ledger,
            measure_query=measure_query,
        )
        assert (task.task_id.value in reopened._measured_tasks) is not measure_query
        assert retained.owner(task.task_id.value) is None
        assert retained.status()["submissions"] == 0
        with pytest.raises(LookupError, match="unknown_submission"):
            retained.outcome(task.task_id.value)
        dispatched = []
        monkeypatch.setattr(
            reopened, "run_queued_task", lambda identity: dispatched.append(identity)
        )
        assert retained.advance() == 0
        assert dispatched == []
    finally:
        reopened.close()


def test_owner_intent_recovers_persisted_task_before_validator_outcome(
    tmp_path, monkeypatch
):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    ledger_path = root / "ledger.sqlite3"
    first = provider_factory()
    try:
        ledger = AttemptLedger(ledger_path)
        adapter = LeanRecipeAdapter(discovery, lambda owner: first, ledger)
        door = Validator(Adapters([adapter]), ledger)
        signed = Submission(
            "miner",
            {"sequence": 1},
            adapter.challenge_id,
            adapter.challenge_version,
            json.dumps(request.recipe),
            adapter.contract_digest,
        )
        admitted = door.screen(signed).admitted
        # Simulate a stop after the direct task commits but before Validator
        # records its OUTCOME in the separate attempt ledger.
        task = adapter.evaluate(admitted)
        assert ledger.submitted_outcomes(adapter.contract_digest) == (
            task["submission_id"],
        )
        assert not [row for row in ledger.attempts() if row["kind"] == "OUTCOME"]
        with pytest.raises(ValueError, match="recipe task intent conflict"):
            ledger.record_recipe_task_intent(
                adapter.contract_digest,
                task["submission_id"],
                "other",
                "sha256:" + "0" * 64,
            )
    finally:
        first.close()

    reopened = provider_factory()
    try:
        ledger = AttemptLedger(ledger_path)
        adapter = LeanRecipeAdapter(discovery, lambda owner: reopened, ledger)
        door = Validator(Adapters([adapter]), ledger)
        assert (
            door.outcome(adapter.contract_digest, task["submission_id"], "miner")[
                "outcome"
            ]
            == task
        )
        assert (
            door.outcome(adapter.contract_digest, task["submission_id"], "other")[
                "code"
            ]
            == "unknown_submission"
        )
        dispatched = []
        monkeypatch.setattr(
            reopened, "run_queued_task", lambda identity: dispatched.append(identity)
        )
        assert adapter.advance() == 1
        assert [identity.value for identity in dispatched] == [task["submission_id"]]
        repeated = door.evaluate(signed)
        assert repeated["outcome"]["submission_id"] == task["submission_id"]
        assert len(reopened.queued_tasks()) == 1
    finally:
        reopened.close()


def test_verified_export_gap_reaches_bounded_served_failure(tmp_path, monkeypatch):
    from carbon.development_session import bundle_construction_worker
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    try:
        root = tmp_path / "attempts"
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        ledger = AttemptLedger(root / "ledger.sqlite3")
        adapter = LeanRecipeAdapter(discovery, lambda owner: provider, ledger)
        door = Validator(Adapters([adapter]), ledger)
        signed = Submission(
            "miner",
            {"sequence": 1},
            adapter.challenge_id,
            adapter.challenge_version,
            json.dumps(request.recipe),
            adapter.contract_digest,
        )
        admitted = door.evaluate(signed)["outcome"]
        from carbon.research import ResearchTaskId

        task_id = ResearchTaskId(admitted["submission_id"])
        build, _ = provider._children(task_id)
        monkeypatch.setattr(
            provider.ledger,
            "operation_state",
            lambda identity, *, owner: (
                "FAILED_INFRA"
                if identity == build and owner == provider.owner
                else None
            ),
        )
        private = b"private path\ncarbon.level4.graph.GraphRefused: aten_op_not_lowered at aten._softmax.default\n"

        def failing(*args, **kwargs):
            raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=private)

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", failing
        )
        provider.run_queued_task(task_id)
        served = door.outcome(adapter.contract_digest, task_id.value, "miner")[
            "outcome"
        ]
        assert served["state"] == "FAILED_INFRA"
        assert served["failure"]["issues"] == [
            {
                "reason_code": "REPORTED_CARBON_EXPORT_OPERATION_GAP",
                "failed_stage": "BUILD_EXPORT",
                "diagnostic_provenance": "WORKER_DIAGNOSTIC_ADVISORY",
                "reported_operation": "aten._softmax.default",
                "next_step": "CHECK_CARBON_ADAPTER_SUPPORT",
            }
        ]
        assert "private path" not in json.dumps(served)
        assert served["qualification"] is served["reward"] is False
    finally:
        provider.close()


@pytest.mark.parametrize(
    "module_name", ["library_bundles.py", "library_overlay_prep.py"]
)
def test_served_identity_binds_effective_preparation_module_bytes(
    monkeypatch, module_name
):
    from pathlib import Path

    from carbon.challenge_validator.lean_recipe import _source_identity

    baseline = _source_identity()
    read_bytes = Path.read_bytes

    def changed(path):
        body = read_bytes(path)
        return (
            body + b"\n# prospective preparation change\n"
            if path.name == module_name
            else body
        )

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert _source_identity() != baseline
