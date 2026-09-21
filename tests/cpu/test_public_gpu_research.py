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


def test_personal_research_reaches_dispatch_without_any_strict_host_grant(
    tmp_path, monkeypatch
):
    """The superseded requirement, inverted.

    This case previously asserted that a miner with no owner-signed host grant
    was blocked before reservation. That requirement was written for the
    validator lane and applied to both; the miner lane does not make the claim
    it supported, so its absence is no longer an error.

    The negative boundary is asserted alongside it rather than assumed: strict
    admission really is unsatisfiable here - there is no grant to load - and the
    run reaches its proper external launch boundary anyway, carrying the miner
    role.
    """
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch, host=False)
    with pytest.raises(WorkerFailure):
        accelerator_runtime.AcceleratorHostAdmission.load()

    result = invoke(c.executor.practice)

    assert len(calls) == 1
    assert calls[0]["accelerator_role"] is gpu.AcceleratorRole.MINER_RESEARCH
    assert result["lane"] == "MINER_CONTAINED"
    assert result["assurance"]["not_established"] == [
        "WHOLE_DEVICE_EXCLUSIVITY",
        "FOREIGN_COMPUTE_PROCESS_ABSENCE",
        "DEVICE_MEMORY_SANITIZATION_BETWEEN_TENANTS",
        "WHOLE_DEVICE_RELEASE_AFTER_RUN",
    ]
    assert result["score"] is None and result["official_eligible"] is False
    assert ledger.status(owner=data.owner)["used"]["research_trials"] == 1
    c.tasks.close()


def test_unknown_whole_device_telemetry_is_not_a_personal_research_error(
    tmp_path, monkeypatch
):
    """An empty enumeration registry blocks nothing on this lane.

    The platform that prompted the split cannot enumerate compute processes at
    all. That telemetry only ever supported an exclusivity claim the miner lane
    does not make, so it stays unknown instead of stopping a miner.
    """
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch, host=False)

    assert accelerator_runtime.ESTABLISHED_OBSERVATION_CONTRACTS == frozenset()
    result = invoke(c.executor.practice)
    assert len(calls) == 1
    assert result["observations"]["device_memory_peak_bytes"] is None
    assert (
        result["observations"]["device_memory_peak_status"]
        == "NOT_MEASURED_BY_THIS_PROJECTION"
    )
    assert ledger.status(owner=data.owner)["operations"][0]["state"] == "SUCCEEDED"
    c.tasks.close()


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
def test_operator_record_cannot_redirect_campaign_controller_storage(
    tmp_path, monkeypatch, outside
):
    """Where controller state lives is the campaign's, not an operator field's.

    This case previously installed a `controller_root` into the host grant and
    asserted the campaign rejected one pointing outside itself. The miner lane
    reads no such field, so the stronger property is asserted instead: the
    location is derived from the campaign root, and an operator record carrying
    a competing path changes nothing.
    """
    _data, ledger, _image, calls, c = fixture(tmp_path, monkeypatch)
    path = accelerator_runtime.HOST_ROOT / "grant.json"
    record = json.loads(path.read_bytes())
    record["controller_root"] = str(
        tmp_path / "unrelated-controller" if outside else ledger.root
    )
    path.write_bytes(canonical(record))

    invoke(c.executor.practice)

    assert len(calls) == 1
    assert calls[0]["claimed"] is not None
    assert gpu._controller_root(ledger) == ledger.root / gpu.CONTROLLER_DIRECTORY
    assert not (tmp_path / "unrelated-controller").exists()
    from carbon.reconstruction.worker.operator import _stores

    assert ledger.root / "gpu-controller" / "launches.sqlite3" in _stores(ledger.root)
    c.tasks.close()


def test_campaign_controller_storage_refuses_a_relocated_or_symlinked_root(tmp_path):
    """The containment check survives the grant it used to be checked against."""
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    ledger = SimpleNamespace(root=root)
    assert gpu._controller_root(ledger) == root / gpu.CONTROLLER_DIRECTORY

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    linked = tmp_path / "linked"
    linked.mkdir(mode=0o700)
    (linked / gpu.CONTROLLER_DIRECTORY).symlink_to(elsewhere)
    with pytest.raises(ValueError, match="must not be a symlink"):
        gpu._controller_root(SimpleNamespace(root=linked))


@pytest.mark.parametrize(
    "scopes",
    [
        None,
        [],
        [{"schema": gpu.SCHEMA}] * 2,
        [{"schema": "carbon.other.v1"}],
        # A declared scope claiming the validator role, or claiming to be worth
        # something official, is refused as malformed rather than accepted and
        # then quietly downgraded.
        [{"schema": gpu.SCHEMA, "role": "VALIDATOR_RECONSTRUCTION"}],
        [{"schema": gpu.SCHEMA, "role": "MINER_RESEARCH", "official_eligible": True}],
    ],
)
def test_declared_gpu_runtime_refuses_a_shape_no_runner_could_assemble(scopes):
    with pytest.raises(ValueError, match="exact prospective GPU"):
        gpu.declared_gpu_runtime({"gpu_research": scopes})


def test_declared_gpu_runtime_is_shape_only_and_copies_what_it_returns():
    """It must not be mistaken for the binding check, nor alias the grant."""
    declared = {
        "schema": gpu.SCHEMA,
        "role": "MINER_RESEARCH",
        "official_eligible": False,
        "score": None,
    }
    runtime = {"gpu_research": [declared]}
    returned = gpu.declared_gpu_runtime(runtime)
    assert returned == [declared]
    returned[0]["role"] = "VALIDATOR_RECONSTRUCTION"
    assert runtime["gpu_research"][0]["role"] == "MINER_RESEARCH"


def test_registered_gpu_image_binds_the_campaign_material(tmp_path, monkeypatch):
    """The real check: the scope is recomputed, never believed as declared."""
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    assert gpu.registered_gpu_image(ledger.root, {}, data.role_root) is None
    path = ledger.root / gpu.GPU_IMAGE_RECORD
    path.write_bytes(
        canonical({"schema": "carbon.c03.worker-image.v1", **asdict(image)})
    )
    path.chmod(0o600)
    assert gpu.registered_gpu_image(ledger.root, runtime, data.role_root) == image
    # A structurally valid scope that does not describe this campaign's material
    # is refused, which is what `declared_gpu_runtime` deliberately cannot do.
    altered = dict(runtime["gpu_research"][0])
    altered["public_train_digest"] = "sha256:" + "0" * 64
    assert gpu.declared_gpu_runtime({"gpu_research": [altered]}) == [altered]
    with pytest.raises(ValueError, match="exact prospective GPU"):
        gpu.registered_gpu_image(
            ledger.root, {"gpu_research": [altered]}, data.role_root
        )
    c.tasks.close()


def test_campaign_selects_the_research_runtime_its_manifest_declares(
    tmp_path, monkeypatch
):
    """The browser campaign can finally assemble what it could only describe.

    A grant declaring `runtime.gpu_research` used to reach a runner that refused
    the key outright, so no campaign could ever compose the GPU callback. This
    drives the campaign's own selection, both ways.
    """
    from carbon.development_session.research_campaign import research_practice
    from carbon.development_session.research_provider import PublicPractice

    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    path = ledger.root / gpu.GPU_IMAGE_RECORD
    path.write_bytes(
        canonical({"schema": "carbon.c03.worker-image.v1", **asdict(image)})
    )
    path.chmod(0o600)
    selected = {
        "data": data,
        "role_root": data.role_root,
        "ledger": ledger,
        "owner": data.owner,
        "image": data.image,
    }

    chosen = research_practice(ledger.root, {"runtime": runtime}, **selected)
    assert type(chosen) is gpu.PublicGPUPractice
    assert chosen.scope == c.executor.practice.scope

    # A campaign that declares no GPU runtime gets exactly what it always got.
    for manifest in ({"runtime": {"implementation": {}, "images": []}}, {}):
        assert type(research_practice(ledger.root, manifest, **selected)) is (
            PublicPractice
        )
    c.tasks.close()


def _install_gpu_record(root, image, *, name=None, padding=0):
    """Write the operator's fixed GPU image record, as an operator tool would."""
    path = root / (name or gpu.GPU_IMAGE_RECORD)
    document = {"schema": "carbon.c03.worker-image.v1", **asdict(image)}
    if padding:
        document["padding"] = "x" * padding
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    return path


def test_gpu_record_positive_control_resolves(tmp_path, monkeypatch):
    """The control for the three guard cases below.

    Without a case that is *supposed* to succeed, a guard test proves only that
    something failed, not that the guard is what failed it.
    """
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    _install_gpu_record(ledger.root, image)
    assert gpu.registered_gpu_image(ledger.root, runtime, data.role_root) == image
    c.tasks.close()


def test_gpu_record_refuses_an_aliased_path(tmp_path, monkeypatch):
    """`path.resolve() != path` - the record itself, and its parent directory.

    A general `private_file` test does not exercise this: `private_file` checks
    absoluteness, symlink-ness and permissions, and this call site adds a
    separate identity condition on top of it. Both aliases are covered because
    a parent alias resolves differently while the leaf is an ordinary file.
    """
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]

    # The record's own path is a symlink to a valid record elsewhere.
    real = _install_gpu_record(ledger.root, image, name="real-gpu-image.json")
    link = ledger.root / gpu.GPU_IMAGE_RECORD
    link.symlink_to(real)
    with pytest.raises(ValueError):
        gpu.registered_gpu_image(ledger.root, runtime, data.role_root)
    link.unlink()

    # The directory the record is read through is an alias of the campaign root.
    _install_gpu_record(ledger.root, image)
    aliased_root = tmp_path / "campaign-alias"
    aliased_root.symlink_to(ledger.root)
    with pytest.raises(ValueError):
        gpu.registered_gpu_image(aliased_root, runtime, data.role_root)

    # Control: through the real path it still resolves.
    assert gpu.registered_gpu_image(ledger.root, runtime, data.role_root) == image
    c.tasks.close()


def test_gpu_record_refuses_an_oversized_record_before_parsing_it(
    tmp_path, monkeypatch
):
    """`stat().st_size > 65536`, and it must refuse *before* the image parser.

    The size bound exists so an unbounded operator file never reaches the
    parser. Asserting only that it raises would pass even if the parser ran
    first, so the parser is replaced with one that fails the test if called.
    """
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    _install_gpu_record(ledger.root, image, padding=70000)
    assert (ledger.root / gpu.GPU_IMAGE_RECORD).stat().st_size > 65536

    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda *a, **k: pytest.fail("oversized record reached the image parser"),
    )
    with pytest.raises(ValueError, match="fixed bounded GPU image record"):
        gpu.registered_gpu_image(ledger.root, runtime, data.role_root)
    c.tasks.close()


def test_gpu_record_refuses_a_wellformed_record_bound_to_other_material(
    tmp_path, monkeypatch
):
    """The scope is recomputed, so an individually valid record is not enough.

    The record here parses, the declared scope passes the shape check, and the
    two still describe different material. Only recomputation catches that.
    """
    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    _install_gpu_record(ledger.root, image)

    altered = dict(runtime["gpu_research"][0])
    altered["public_train_digest"] = "sha256:" + "0" * 64
    assert gpu.declared_gpu_runtime({"gpu_research": [altered]}) == [altered]
    with pytest.raises(ValueError, match="exact prospective GPU"):
        gpu.registered_gpu_image(
            ledger.root, {"gpu_research": [altered]}, data.role_root
        )

    # A different but individually well-formed image record, same declared
    # scope. image_id and config_digest move together because the identity
    # refuses to construct otherwise - the record has to be genuinely valid for
    # this to isolate the scope binding rather than the parser.
    identity = "sha256:" + "9" * 64
    other = replace(image, image_id=identity, config_digest=identity)
    _install_gpu_record(ledger.root, other)
    (ledger.root / gpu.GPU_IMAGE_RECORD).chmod(0o600)
    with pytest.raises(ValueError, match="exact prospective GPU"):
        gpu.registered_gpu_image(ledger.root, runtime, data.role_root)
    c.tasks.close()


def test_cli_and_campaign_reach_the_same_checked_resolver(tmp_path, monkeypatch):
    """Both composition routes delegate; neither carries its own copy."""
    from carbon.development_session.research_campaign import research_practice

    data, ledger, image, _calls, c = fixture(tmp_path, monkeypatch)
    runtime = ledger.admission.document["runtime"]
    _install_gpu_record(ledger.root, image)

    seen = []
    original = gpu.registered_gpu_image

    def recording(*args, **kwargs):
        seen.append(args[:1])
        return original(*args, **kwargs)

    # Patched in both namespaces: the campaign binds the name at import, so
    # patching only the defining module would silently miss that route and the
    # assertion below would be measuring the wrong thing.
    from carbon.development_session import research_campaign as campaign

    monkeypatch.setattr(gpu, "registered_gpu_image", recording)
    monkeypatch.setattr(campaign, "registered_gpu_image", recording)
    assert _gpu_image(ledger.root, runtime, data.role_root) == image
    chosen = research_practice(
        ledger.root,
        {"runtime": runtime},
        data=data,
        role_root=data.role_root,
        ledger=ledger,
        owner=data.owner,
        image=data.image,
    )
    assert type(chosen) is gpu.PublicGPUPractice
    assert len(seen) == 2, "both routes must reach the shared resolver"
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
def test_strict_grant_conditions_no_longer_block_personal_research(
    tmp_path, monkeypatch, field, value
):
    """Each of these used to stop a miner. None of them is a miner-lane fact.

    An expired or wrong-principal grant, a grant scoped to the validator role, a
    stale resource digest, an unrelated image id - and, pointedly, a GPU driving
    a display. The owner's direction is explicit that a miner may have a monitor
    on the GPU they research with, so `DISPLAY_ACTIVE` is in this list rather
    than in the one below.

    The strict lane keeps every one of these checks; `tests/cpu/
    test_gpu_execution_lanes.py` owns that side and is untouched here.
    """
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    path = accelerator_runtime.HOST_ROOT / "grant.json"
    record = json.loads(path.read_bytes())
    record[field] = value
    path.write_bytes(canonical(record))

    invoke(c.executor.practice)

    assert len(calls) == 1
    assert ledger.status(owner=data.owner)["operations"][0]["state"] == "SUCCEEDED"
    c.tasks.close()


@pytest.mark.parametrize(
    "shape,overrides,reason",
    [
        # A device this workload profile does not serve. Compatibility is an
        # engineering fact and still decides whether the software can run.
        ("tpu_host", {}, "incompatible device"),
        # A record describing a different workload profile than the one this
        # campaign compiled against.
        (None, {"workload_profile_id": "carbon.c03.other.v1"}, "wrong profile"),
    ],
)
def test_miner_lane_rejections_still_precede_dispatch(
    tmp_path, monkeypatch, shape, overrides, reason
):
    """What does block a miner, and it blocks before anything is charged."""
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    if shape is None:
        accelerator_host.install(
            accelerator_runtime.HOST_ROOT, accelerator_host.document(**overrides)
        )
    else:
        accelerator_host.install(
            accelerator_runtime.HOST_ROOT, accelerator_host.document(shape, **overrides)
        )
    with pytest.raises((WorkerFailure, ValueError)):
        invoke(c.executor.practice)
    assert not calls, reason
    assert not ledger.status(owner=data.owner)["operations"]
    c.tasks.close()


def test_absent_device_record_fails_before_the_miner_is_charged(tmp_path, monkeypatch):
    """A withdrawn record costs nothing.

    The controller reads the record too, but by then the ledger has reserved.
    Reading it before the reservation is what keeps an unrunnable launch free.
    """
    data, ledger, _gpu_image, calls, c = fixture(tmp_path, monkeypatch)
    from carbon.reconstruction.host_inventory import HOST_DEVICE_RECORD

    (accelerator_runtime.HOST_ROOT / HOST_DEVICE_RECORD).unlink()
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


def test_replaced_device_record_rejects_before_dispatch_and_keeps_its_reservation(
    tmp_path, monkeypatch
):
    """The binding that replaced the grant is rechecked in the same place.

    A record swapped between building the request and taking the numerical lease
    stops the launch. The reservation it already made is deliberately kept:
    unknown consumption is not refunded, and a stopped launch is not a free one.
    """
    _data, ledger, _image, calls, c = fixture(tmp_path, monkeypatch)
    original = gpu.PublicGPUPractice._device
    reads = []

    def device(self):
        if not reads:
            record = original(self)
        else:
            # A different, individually valid record installed underneath the run.
            accelerator_host.install(
                accelerator_runtime.HOST_ROOT,
                accelerator_host.document("workstation_linux"),
            )
            record = original(self)
        reads.append(record.digest)
        return record

    monkeypatch.setattr(gpu.PublicGPUPractice, "_device", device)
    with pytest.raises(ValueError, match="device record changed"):
        invoke(c.executor.practice)
    assert len(reads) == 2 and reads[0] != reads[1]
    assert not calls
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
