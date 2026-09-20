"""Prospective composition contracts; synthetic worker, no accelerator execution."""

import json
import time
from dataclasses import asdict, replace
from types import SimpleNamespace

import accelerator_host
import pytest
from test_c03_worker_contract import _image
from test_julia_research import prepared

from carbon import research
from carbon.development_session import gpu_research as gpu
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_admission import Admission
from carbon.development_session.research_carrier import (
    ACTIVE_TASK,
    PRECHARGED_TRIAL,
    request_cancel,
)
from carbon.development_session.research_catalog import compile_recipe, public_catalog
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.miner_mcp.standard_cli import _gpu_image
from carbon.reconstruction.model import ReconstructionStatus
from carbon.reconstruction.worker import accelerator_runtime
from carbon.reconstruction.worker.model import WorkerFailure

STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE.challenge_id,
    "backbone": "fno",
    "parameters": {"steps": 2, "width": 4, "depth": 1, "n_modes": 4, "warmup_steps": 0},
}


def fixture(tmp_path, monkeypatch, *, scope=True, host=True, fail=False, julia=False):
    data, ledger, _ = prepared(tmp_path, monkeypatch, approved=julia)
    image = replace(_image(), lock_digest=gpu.GPU_PROFILE.environment_lock_digest)
    # Assemble a synthetic prospective fixture before invoking any consumer.
    grant = dict(ledger.admission.document)
    runtime = dict(grant["runtime"])
    if scope:
        runtime["gpu_research"] = [gpu.gpu_scope(image, data.role_root)]
    grant["runtime"] = runtime
    ledger.admission.path.write_bytes(canonical(grant))
    ledger.admission = Admission.load(ledger.admission.path)
    with ledger.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
        manifest.update(runtime=runtime, grant=ledger.admission.binding())
        db.execute("UPDATE campaign SET manifest=?", (canonical(manifest),))
    calls = []
    monkeypatch.setattr(
        type(data),
        "prepare",
        lambda self, role: (b"synthetic TRAIN archive", {"role": role}),
    )
    host_root = tmp_path / "host"
    host_root.mkdir(mode=0o700)
    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", host_root)
    # Which device this host has is installed evidence, not a source constant.
    accelerator_host.install(host_root)
    if not scope:
        return data, ledger, image, calls
    practice = gpu.PublicGPUPractice(data=data, image=image)
    material = PublicMaterial(data)
    if julia:
        from carbon.development_session.julia_research import (
            JuliaPublicMaterial,
            PublicJuliaStudy,
        )

        material = JuliaPublicMaterial(material, PublicJuliaStudy(data))
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner=data.owner,
        image=data.image,
        public_material=material,
        practice=practice,
    )
    if host:
        record = {
            "schema": accelerator_runtime.GRANT_SCHEMA,
            "status": "APPROVED",
            "authority": "ENGINEERING_FIXTURE_ONLY",
            "grant_id": "gpu-fixture",
            "host_root": str(host_root),
            "controller_root": str(ledger.root / "gpu-controller"),
            "principal": data.owner,
            "roles": [gpu.AcceleratorRole.MINER_RESEARCH.value],
            "device_uuid": accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE][
                "device_uuid"
            ],
            "execution_profile_digest": gpu.GPU_PROFILE.digest,
            "image_id": image.image_id,
            "resource_policy_digest": composition.inspection.policy_ref.content_digest,
            "resource_class_digest": composition.inspection.resource_class_ref.content_digest,
            "expires_unix": time.time() + 50000,
            "allocation": "EXCLUSIVE_SINGLE_DEVICE",
            "cleanup": "EXACT_GRANT_OWNED_CONTAINERS_AND_DEVICE_RELEASE",
            "host_use": "DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE",
        }
        path = host_root / "grant.json"
        path.write_bytes(canonical(record))
        path.chmod(0o600)

    def execute(self, **kwargs):
        calls.append(kwargs)
        assert kwargs["accelerator_role"] is gpu.AcceleratorRole.MINER_RESEARCH
        assert kwargs["cancelled"]() is False
        if fail:
            request_cancel(ledger, owner=data.owner, identity=ACTIVE_TASK.get())
            assert kwargs["cancelled"]() is True
            raise RuntimeError("synthetic unknown worker consumption")
        receipt = SimpleNamespace(
            status=ReconstructionStatus.COMPLETE,
            completed_steps=2,
            artifact_digest="sha256:" + "c" * 64,
            checkpoint_digest="sha256:" + "d" * 64,
            plan_digest=kwargs["plan"].to_ref().content_digest,
            training_data_digest=kwargs["training_archive"].content_digest,
            compile_seconds=0.1,
            train_execution_seconds=0.2,
        )
        return SimpleNamespace(
            receipt=receipt,
            resource_observation={
                "private_controller": "/secret",
                "memory": {"peak_bytes": 123},
            },
            timings={"numerical": 0.3, "staging": 0.05, "private_path": "/secret"},
        )

    monkeypatch.setattr(gpu.IsolatedReconstructionController, "execute", execute)
    return data, ledger, image, calls, composition


def invoke(practice, identity="gpu-engineering-task-0001", strategy=STRATEGY):
    token = ACTIVE_TASK.set(identity)
    try:
        return practice(identity, strategy)
    finally:
        ACTIVE_TASK.reset(token)


def test_gpu_pins_precede_compilation_and_cpu_contracts_unchanged():
    before = canonical(public_catalog())
    cpu = compile_recipe(STRATEGY)[1]
    compiled, profile = compile_recipe(STRATEGY, contracts=gpu.gpu_contracts())
    assert profile.profile_id == gpu.GPU_PROFILE.profile_id
    assert profile.environment_digest == gpu.GPU_PROFILE.digest
    assert profile.profile_version == "4.0"
    assert compiled.construction_plan.to_ref().content_digest != cpu.plan_digest
    assert compile_recipe(STRATEGY)[1] == cpu
    assert canonical(public_catalog()) == before


def test_cpu_campaign_scope_cannot_enable_gpu(tmp_path, monkeypatch):
    data, ledger, image, calls = fixture(tmp_path, monkeypatch, scope=False)
    with pytest.raises(ValueError, match="prospective GPU"):
        gpu.PublicGPUPractice(data=data, image=image)
    assert not calls and not ledger.status(owner=data.owner)["operations"]


def test_missing_host_grant_blocks_before_numerical_reservation(tmp_path, monkeypatch):
    data, ledger, _gpu_image, calls, composition = fixture(
        tmp_path, monkeypatch, host=False
    )
    with pytest.raises(WorkerFailure, match="worker operation failed"):
        invoke(composition.executor.practice)
    assert not calls and not ledger.status(owner=data.owner)["operations"]
    composition.tasks.close()


def test_real_service_task_non_score_result_replay_and_precharged_trial(
    tmp_path, monkeypatch
):
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    request = research.StartResearchTaskRequest(
        CHALLENGE,
        "gpu-service-request-0001",
        research.PracticeTaskSpec(STRATEGY, None),
        c.contracts.assembly.training_support_ref,
        research.NoPriorSelector(),
        c.inspection.policy_ref,
        c.inspection.resource_class_ref,
        c.discovery.manifest.practice_scope_ref,
    )
    task = c.tasks.start_research_task(request).task
    token = PRECHARGED_TRIAL.set("existing-proposal-charge")
    try:
        done = c.tasks.run_queued_task(task.task_id)
    finally:
        PRECHARGED_TRIAL.reset(token)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    result = c.executor.public_result(done)["result"]
    assert result["schema"] == gpu.RESULT and result["score"] is None
    assert result["official_eligible"] is False
    assert "/secret" not in canonical(result).decode()
    assert result["observations"]["host_memory_peak_bytes"] == 123
    assert result["observations"]["timings"]["staging"] == 0.05
    assert c.tasks.start_research_task(request).task.task_id == task.task_id
    assert c.executor.public_result(done)["result"] == result
    assert len(calls) == 1
    assert ledger.status(owner=data.owner)["used"]["research_trials"] == 0
    from carbon.reconstruction.worker.operator import _stores

    assert ledger.root / "gpu-controller" / "launches.sqlite3" in _stores(ledger.root)
    c.tasks.close()


def test_cancelled_unknown_work_stays_charged_and_cannot_replay(tmp_path, monkeypatch):
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="unknown worker"):
        invoke(c.executor.practice)
    with pytest.raises(ValueError, match="uncertain"):
        invoke(c.executor.practice)
    status = ledger.status(owner=data.owner)
    assert status["used"]["numerical_milliseconds"] == 720000
    assert status["operations"][0]["actual"] is None
    assert len(calls) == 1
    c.tasks.close()


def test_cli_fixed_record_requires_exact_scope(tmp_path, monkeypatch):
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    assert _gpu_image(ledger.root, {}, data.role_root) is None
    path = ledger.root / "gpu-worker-image.json"
    path.write_bytes(
        canonical({"schema": "carbon.c03.worker-image.v1", **asdict(image)})
    )
    path.chmod(0o600)
    assert _gpu_image(ledger.root, runtime, data.role_root) == image
    from carbon.miner_mcp.standard_cli import _science

    _material, callback = _science(ledger, data.owner, data.image, data.role_root)
    assert type(callback) is gpu.PublicGPUPractice
    assert callback.scope == c.executor.practice.scope
    for scopes in (
        [],
        None,
        [runtime["gpu_research"][0]] * 2,
        [{"schema": gpu.SCHEMA}],
    ):
        with pytest.raises(ValueError, match="exact prospective GPU"):
            _gpu_image(ledger.root, {"gpu_research": scopes}, data.role_root)
    c.tasks.close()


@pytest.mark.parametrize("outside", [True, False])
def test_outside_campaign_host_root_is_not_an_admissible_consumer(
    tmp_path, monkeypatch, outside
):
    data, ledger, _image, calls, c = fixture(tmp_path, monkeypatch)
    path = accelerator_runtime.HOST_ROOT / "grant.json"
    record = json.loads(path.read_bytes())
    record["controller_root"] = str(
        tmp_path / "unrelated-controller" if outside else ledger.root
    )
    path.write_bytes(canonical(record))
    with pytest.raises(ValueError, match="exact campaign"):
        invoke(c.executor.practice)
    assert not calls and not ledger.status(owner=data.owner)["operations"]
    c.tasks.close()


@pytest.mark.parametrize("relative", [".", "child", ".."])
def test_controller_storage_cannot_overlap_operation(tmp_path, relative):
    directory = tmp_path / "operation"
    with pytest.raises(ValueError, match="must be disjoint"):
        gpu._check_storage_layout(directory / relative, directory)
    gpu._check_storage_layout(tmp_path / "controller", directory)


def test_physical_storage_ceiling_prevents_staging(tmp_path, monkeypatch):
    data, ledger, _image, calls, c = fixture(tmp_path, monkeypatch)

    def full(additional=0):
        assert additional == 384 * 1024**2
        raise ValueError("physical campaign retained-data ceiling")

    monkeypatch.setattr(ledger, "check_storage", full)
    with pytest.raises(ValueError, match="physical campaign"):
        invoke(c.executor.practice)
    assert not calls
    assert not list(ledger.root.glob("gpu-*/train.npz"))
    assert ledger.status(owner=data.owner)["used"]["numerical_milliseconds"] == 720000
    c.tasks.close()


def test_combined_julia_gpu_capability_digest_matches_manifest_and_saved_bytes(
    tmp_path, monkeypatch
):
    _data, ledger, _image, calls, c = fixture(tmp_path, monkeypatch, julia=True)
    primary = c.executor.public_material("capabilities", c.executor.workspace)
    result = c.executor.practice.projection(
        "capabilities", primary, c.executor.workspace
    )
    document = result["document"]
    assert (
        document["scientific_tasks"]
        == ledger.admission.document["runtime"]["scientific_tasks"]
    )
    assert (
        document["public_scaffold_catalogue_digest"]
        == c.discovery.manifest.scaffold_catalog_ref.content_digest
    )
    assert c.executor.workspace.get(result["file"]) == canonical(document)
    assert result["digest"] == gpu.digest(canonical(document))
    assert c.executor.workspace.get(primary["file"]) == canonical(primary["document"])
    assert primary["document"]["recipes"] == public_catalog()
    assert not calls
    c.tasks.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("principal", "another-principal"),
        ("roles", ["VALIDATOR_RECONSTRUCTION"]),
        ("expires_unix", 0),
        ("resource_policy_digest", "sha256:" + "0" * 64),
        ("image_id", "sha256:" + "0" * 64),
        ("host_use", "DISPLAY_ACTIVE"),
    ],
)
def test_host_authority_rejections_precede_dispatch(
    tmp_path, monkeypatch, field, value
):
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    path = accelerator_runtime.HOST_ROOT / "grant.json"
    record = json.loads(path.read_bytes())
    record[field] = value
    path.write_bytes(canonical(record))
    with pytest.raises((WorkerFailure, ValueError)):
        invoke(c.executor.practice)
    assert not calls and not ledger.status(owner=data.owner)["operations"]
    c.tasks.close()


def test_restarted_callback_replays_same_operation_and_changed_recipe_conflicts(
    tmp_path, monkeypatch
):
    data, ledger, image, calls, c = fixture(tmp_path, monkeypatch)
    first = invoke(c.executor.practice)
    restarted = gpu.PublicGPUPractice(data=data, image=image)
    restarted.inspection = c.inspection
    assert invoke(restarted) == first
    altered = {**STRATEGY, "parameters": {**STRATEGY["parameters"], "steps": 3}}
    with pytest.raises(ValueError, match="replay conflict"):
        invoke(restarted, strategy=altered)
    assert len(calls) == 1
    assert ledger.status(owner=data.owner)["used"]["research_trials"] == 1
    c.tasks.close()


def test_plain_public_result_projection_keeps_gpu_score_absent(tmp_path, monkeypatch):
    _data, _ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    for name in ("capabilities", "objective"):
        request = research.StartResearchTaskRequest(
            CHALLENGE,
            "gpu-discovery-" + name,
            research.DevelopmentWorkspaceTaskSpecV1(
                "carbon.autoresearch.workspace.v1",
                "public_material",
                canonical({"name": name}).decode(),
            ),
            c.contracts.assembly.training_support_ref,
            research.NoPriorSelector(),
            c.inspection.policy_ref,
            c.inspection.resource_class_ref,
            c.discovery.manifest.practice_scope_ref,
        )
        task = c.tasks.start_research_task(request).task
        done = c.tasks.run_queued_task(task.task_id)
        envelope = c.executor.public_result(done)["result"]
        result = envelope["document"]
        assert c.executor.workspace.get(envelope["file"]) == canonical(result)
        assert envelope["digest"] == gpu.digest(canonical(result))
        if name == "capabilities":
            assert (
                result["recipes"]["execution"]["hardware_acceptance"] == "NOT_EXECUTED"
            )
        else:
            assert result["score"] is None and "score_rule" not in result
    assert not calls
    c.tasks.close()


def test_replaced_host_grant_rejects_before_numerical_work_and_keeps_reservation(
    tmp_path, monkeypatch
):
    data, ledger, image, calls, c = fixture(tmp_path, monkeypatch)
    path = accelerator_runtime.HOST_ROOT / "grant.json"
    original = accelerator_runtime.AcceleratorHostAdmission.load()
    reached = []

    def execute(self, **kwargs):
        assert (
            ledger.status(owner=data.owner)["used"]["numerical_milliseconds"] == 720000
        )
        replacement = dict(original.document, grant_id="gpu-fixture-replacement")
        path.write_bytes(canonical(replacement))
        fresh = accelerator_runtime.AcceleratorHostAdmission.load()
        fresh.verify(
            principal=data.owner,
            state_root=self.state_root,
            image=image,
            role=gpu.AcceleratorRole.MINER_RESEARCH,
            now=float(time.time()),
        )
        reached.append("valid replacement installed")
        kwargs["cancelled"]()
        pytest.fail("replaced grant reached numerical execution")

    monkeypatch.setattr(gpu.IsolatedReconstructionController, "execute", execute)
    with pytest.raises(WorkerFailure):
        invoke(c.executor.practice)
    assert reached == ["valid replacement installed"]
    assert not calls
    assert ledger.status(owner=data.owner)["used"]["numerical_milliseconds"] == 720000
    assert not list(ledger.root.glob("gpu-*/result.json"))
    c.tasks.close()


def test_campaign_stop_reaches_existing_controller_cancel_predicate(
    tmp_path, monkeypatch
):
    data, ledger, _gpu_image, _calls, c = fixture(tmp_path, monkeypatch)

    def execute(self, **kwargs):
        assert kwargs["cancelled"]() is False
        control = CampaignControl(ledger)
        control.request("stop")
        assert kwargs["cancelled"]() is True
        raise RuntimeError("synthetic stopped allocation")

    monkeypatch.setattr(gpu.IsolatedReconstructionController, "execute", execute)
    with pytest.raises(RuntimeError, match="stopped allocation"):
        invoke(c.executor.practice)
    assert ledger.status(owner=data.owner)["used"]["numerical_milliseconds"] == 720000
    c.tasks.close()
