"""Synthetic admission/accounting tests; native Julia evidence uses the real worker lane."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from b07b_fixtures import make_fixture
from test_cw1_research_data import case
from test_cw1_research_tasks import request

from carbon import research
from carbon.development_session import julia_research as julia
from carbon.development_session import research_data
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_carrier import ACTIVE_TASK, request_cancel
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    CampaignLedger,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_tasks import (
    PublicDevelopmentResearchTasks,
    PublicResearchExecutor,
)
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.evaluation.enums import ReferenceRunOutcome


def prepared(
    tmp_path, monkeypatch, *, approved=True, fail=False, image=None, owner="test-miner"
):
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    roles = tmp_path / "roles"
    roles.mkdir()
    body = canonical([case().public_record()])
    (roles / "research-train-cases.json").write_bytes(body)
    (roles / "private-role-manifest.json").write_bytes(
        canonical({"research-train": {"digest": digest(body)}})
    )
    synthetic = image is None
    if synthetic:
        image = SimpleNamespace(image_id="sha256:" + "a" * 64)
    runtime = {"implementation": "fixture", "images": [image.image_id]}
    if approved:
        runtime["scientific_tasks"] = [julia.julia_burgers_scope(image, roles)]
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "julia-fixture",
        "campaign_id": "julia-fixture-campaign",
        "root": str(root),
        "principal": "alice",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "fixture-no-credentials",
        "campaign_count": 1,
        "ceilings": dict(CEILINGS),
        "elapsed_seconds": ELAPSED_SECONDS,
        "expires_unix": 50000,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path = tmp_path / "grant.json"
    path.write_bytes(canonical(grant))
    path.chmod(0o600)
    admission = Admission.load(path)
    ledger = CampaignLedger(root, clock=lambda: 1000, admission=admission)
    ledger.generation = CampaignControl(ledger).acquire()
    manifest = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": "alice",
        "owner": owner,
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": grant["ceilings"],
        "elapsed_seconds": ELAPSED_SECONDS,
        **{
            key: "fixture"
            for key in (
                "implementation",
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            )
        },
    }
    ledger.freeze(manifest)
    if synthetic:
        monkeypatch.setattr(
            research_data, "IsolatedBurgersReferenceController", lambda **kw: None
        )
    data = research_data.PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=roles
    )
    calls = []

    def execute(value, *, cancelled):
        calls.append(value)
        if fail:
            request_cancel(ledger, owner=data.owner, identity=ACTIVE_TASK.get())
            assert cancelled() is True
            raise RuntimeError("fixture uncertain cancellation")
        assert cancelled() is False
        path = data.root / "c04" / "snapshots" / "fixture"
        path.mkdir(parents=True, exist_ok=True)
        (path / "solution.f64le").write_bytes(np.zeros((13, 64), dtype="<f8").tobytes())
        return SimpleNamespace(
            snapshot_path=path,
            snapshot_digest=digest(b"snapshot"),
            result=SimpleNamespace(
                outcome=ReferenceRunOutcome.SUPPORTED,
                artifact_digest=digest(b"artifact"),
                shape=(13, 64),
                diagnostics=(("refinement_rms", 0.01), ("private_path", "/controller")),
            ),
            controls={"private": "controller-only"},
            resources={"private": "controller-only"},
            timings={},
        )

    if synthetic:
        data.controller = SimpleNamespace(execute=execute)
    return data, ledger, calls


def invoke(study, workspace, identity="fixture-task"):
    token = ACTIVE_TASK.set(identity)
    try:
        return study(workspace)
    finally:
        ACTIVE_TASK.reset(token)


def test_prospective_grant_required_before_dispatch(tmp_path, monkeypatch):
    data, ledger, calls = prepared(tmp_path, monkeypatch, approved=False)
    with pytest.raises(ValueError, match="prospective Julia scope"):
        julia.PublicJuliaStudy(data)
    assert calls == []
    assert ledger.status(owner=data.owner)["operations"] == []


def test_replay_across_tasks_one_charge_owned_portable_artifacts(tmp_path, monkeypatch):
    data, ledger, calls = prepared(tmp_path, monkeypatch)
    workspace = ResearchWorkspace(ledger, data.owner)
    result = invoke(julia.PublicJuliaStudy(data), workspace)
    again = invoke(julia.PublicJuliaStudy(data), workspace, "second-task")
    assert result == again
    assert len(calls) == 1
    assert calls[0].method_variant == "julia_v1"
    assert calls[0].role.value == "DEVELOPMENT_CROSSCHECK"
    assert result["axes"] == ["time", "space"]
    assert (
        result["scientifically_qualified"]
        is result["training_support_eligible"]
        is False
    )
    assert "controller" not in canonical(result).decode()
    assert "private_path" not in result["diagnostics"]
    used = ledger.status(owner=data.owner)["used"]
    assert used["reference_invocations"] == used["reference_trajectories"] == 2
    assert used["provider_attempts"] == 0
    assert len(workspace.get(result["solution"])) == 13 * 64 * 8
    (data.root / "c04/snapshots/fixture/solution.f64le").write_bytes(b"tamper")
    with pytest.raises(ValueError, match="association conflict"):
        invoke(julia.PublicJuliaStudy(data), workspace, "third-task")
    assert len(calls) == 1


def test_cross_owner_unadmitted_and_changed_grant_rejected(tmp_path, monkeypatch):
    data, ledger, calls = prepared(tmp_path, monkeypatch)
    study = julia.PublicJuliaStudy(data)
    with pytest.raises(ValueError, match="owned admitted"):
        study(ResearchWorkspace(ledger, data.owner))
    with pytest.raises(ValueError, match="owned admitted"):
        invoke(study, ResearchWorkspace(ledger, "other-miner"))
    grant = dict(ledger.admission.document, status="REQUESTED_NOT_GRANTED")
    ledger.admission.path.write_bytes(canonical(grant))
    with pytest.raises(ValueError, match="changed or revoked"):
        invoke(study, ResearchWorkspace(ledger, data.owner))
    assert not calls


def test_cancellation_reaches_controller_retains_unknown_consumption(
    tmp_path, monkeypatch
):
    data, ledger, calls = prepared(tmp_path, monkeypatch, fail=True)
    study = julia.PublicJuliaStudy(data)
    workspace = ResearchWorkspace(ledger, data.owner)
    with pytest.raises(RuntimeError, match="uncertain cancellation"):
        invoke(study, workspace)
    with pytest.raises(ValueError, match="reconciliation"):
        invoke(study, workspace, "reconnected-task")
    assert len(calls) == 1
    status = ledger.status(owner=data.owner)
    assert status["operations"][0]["state"] == "RESERVED"
    assert status["used"]["numerical_milliseconds"] == 720000


def test_actual_durable_task_seam_and_legacy_catalogue_preserved(tmp_path, monkeypatch):
    data, ledger, calls = prepared(tmp_path, monkeypatch)
    f = make_fixture(tmp_path / "fixtures")
    p = f.provider
    primary = PublicMaterial(data)
    material = julia.JuliaPublicMaterial(primary, julia.PublicJuliaStudy(data))
    e = PublicResearchExecutor(
        ledger=ledger,
        owner=data.owner,
        image=data.image,
        public_material=material,
        practice=None,
    )
    provider = PublicDevelopmentResearchTasks(
        root=tmp_path / "tasks",
        requester=data.owner,
        challenge_catalog_provider=p._catalog,
        manifest_provider=p._manifests,
        compilation_resolver=p._compiler,
        prior_resolver=p._priors,
        resource_resolver=p._resources,
        executor=e,
        task_queue=p._queue,
        clock=p._clock,
        worker_implementation_digest=p._worker_digest,
        environment_digest=p._environment_digest,
    )
    e.request_resolver = provider.request_for_execution
    try:
        req = request(f, "public_material", {"name": julia.MATERIAL})
        task = provider.start_research_task(req).task
        done = provider.run_queued_task(task.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
        assert e.public_result(done)["result"]["language"] == "julia"
        assert provider.start_research_task(req).task.task_id == task.task_id
        assert len(calls) == 1
        assert (
            provider.get_experiment_record(task.task_id).evidence_class
            is research.ResearchEvidenceClass.STRUCTURAL_ONLY
        )
        e.public_material = primary
        legacy = replace(req, idempotency_key="legacy-julia-must-fail")
        old_task = provider.start_research_task(legacy).task
        assert (
            provider.run_queued_task(old_task.task_id).state
            is research.ResearchTaskState.FAILED_INFRA
        )
        assert len(calls) == 1
        capability = material("capabilities", e.workspace)
        assert capability["document"]["scientific_task_usage"]["arguments"] == {
            "name": julia.MATERIAL
        }
        assert (
            "scientific_tasks" not in primary("capabilities", e.workspace)["document"]
        )
    finally:
        provider.close()
