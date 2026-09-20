"""The real stage_request -> load_worker_request boundary for a local request.

Nothing here is mocked: `stage_request` writes the actual request and input files
and `load_worker_request` reads that directory back. No schema check, decoder or
admission dispatch is replaced. Device-free: no container is created and no
accelerator is initialized.
"""

import json

import accelerator_host
import pytest
from test_accelerator_worker import _gpu_fixture
from test_c03_worker_contract import _sha

from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
)
from carbon.reconstruction.worker.protocol import load_worker_request, stage_request

DEVICE_UUID = accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_uuid"]
APPROVAL_DIGEST = _sha("4")
DIAGNOSTIC_PLAN_DIGEST = _sha("5")


def _local_profile(**overrides):
    values = {
        "research_resource_policy_digest": _sha("2"),
        "resource_class_digest": _sha("3"),
        "profile_id": "carbon.c03.cuda.development.v1",
        "profile_version": "1.0",
        "accelerator_profile_id": GPU_PROFILE.profile_id,
        "accelerator_grant_digest": APPROVAL_DIGEST,
        "accelerator_role": AcceleratorRole.MINER_RESEARCH.value,
        "accelerator_authority": LOCAL_DEVELOPMENT_AUTHORITY,
        "accelerator_plan_digest": DIAGNOSTIC_PLAN_DIGEST,
        "accelerator_device_uuid": DEVICE_UUID,
    }
    values.update(overrides)
    return DevelopmentWorkerProfile(**values)


def _strict_profile():
    return DevelopmentWorkerProfile(
        _sha("2"),
        _sha("3"),
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        APPROVAL_DIGEST,
        AcceleratorRole.MINER_RESEARCH.value,
        None,
        None,
        DEVICE_UUID,
    )


def _stage(tmp_path, monkeypatch, worker_profile, name="staging"):
    claimed, repeat, replica, plan, archive, seed, _ = _gpu_fixture(
        tmp_path, monkeypatch
    )
    stage, _ = stage_request(
        stage_root=tmp_path / name,
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        worker_profile=worker_profile,
    )
    return stage, plan


# --- the local request must survive the real writer and the real reader -------


def test_local_request_round_trips_through_the_real_reader(tmp_path, monkeypatch):
    """The regression the outer schema check previously failed."""
    stage, plan = _stage(tmp_path, monkeypatch, _local_profile())
    request = json.loads((stage / "request.json").read_bytes())
    assert request["schema"] == "carbon.c03.worker-request.v4"
    assert request["accelerator"]["authority"] == LOCAL_DEVELOPMENT_AUTHORITY
    assert request["accelerator"]["approval_digest"] == APPROVAL_DIGEST
    assert request["accelerator"]["diagnostic_plan_digest"] == DIAGNOSTIC_PLAN_DIGEST

    _, loaded_plan, _, _, _ = load_worker_request(stage)
    assert loaded_plan.to_ref() == plan.to_ref()


def test_the_device_naming_strict_request_round_trips_under_its_own_version(
    tmp_path, monkeypatch
):
    """Not v2: this block carries a device field that v2 never carried.

    That a request already written under v2 still loads is covered by
    `tests/cpu/test_accelerator_baseline_compatibility.py`, against bytes main
    produced - which is the only thing that can show it.
    """
    stage, plan = _stage(tmp_path, monkeypatch, _strict_profile())
    request = json.loads((stage / "request.json").read_bytes())
    assert request["schema"] == "carbon.c03.worker-request.v5"
    assert request["accelerator"]["device_uuid"] == DEVICE_UUID
    assert request["accelerator"]["grant_digest"] == APPROVAL_DIGEST
    assert "authority" not in request["accelerator"]
    _, loaded_plan, _, _, _ = load_worker_request(stage)
    assert loaded_plan.to_ref() == plan.to_ref()


def test_both_digest_meanings_survive_the_real_round_trip(tmp_path, monkeypatch):
    stage, _ = _stage(tmp_path, monkeypatch, _local_profile())
    accelerator = json.loads((stage / "request.json").read_bytes())["accelerator"]
    assert accelerator["approval_digest"] != accelerator["diagnostic_plan_digest"]
    load_worker_request(stage)


# --- the closed schema/authority pairing ---------------------------------------


def _rewrite(stage, mutate):
    """Edit the staged request in place, as a tampering worker would see it."""
    path = stage / "request.json"
    request = json.loads(path.read_bytes())
    mutate(request)
    path.chmod(0o600)
    path.write_bytes(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    )
    path.chmod(0o400)


@pytest.mark.parametrize(
    "schema",
    [
        "carbon.c03.worker-request.v1",
        "carbon.c03.worker-request.v2",
        "carbon.c03.worker-request.v3",
        "carbon.c03.worker-request.v5",
        "",
    ],
)
def test_a_local_block_under_another_schema_is_refused(tmp_path, monkeypatch, schema):
    stage, _ = _stage(tmp_path, monkeypatch, _local_profile())
    _rewrite(stage, lambda r: r.update(schema=schema))
    with pytest.raises(WorkerFailure) as error:
        load_worker_request(stage)
    assert error.value.code in (WorkerCode.INVALID, WorkerCode.STAGING)


def test_a_strict_block_under_the_local_schema_is_refused(tmp_path, monkeypatch):
    stage, _ = _stage(tmp_path, monkeypatch, _strict_profile())
    _rewrite(stage, lambda r: r.update(schema="carbon.c03.worker-request.v4"))
    with pytest.raises(WorkerFailure):
        load_worker_request(stage)


def test_a_cpu_request_may_not_claim_an_accelerator_schema(tmp_path, monkeypatch):
    stage, _ = _stage(tmp_path, monkeypatch, _local_profile())
    _rewrite(
        stage,
        lambda r: (
            r.pop("accelerator"),
            r.update(schema="carbon.c03.worker-request.v4"),
        ),
    )
    with pytest.raises(WorkerFailure):
        load_worker_request(stage)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["accelerator"].pop("diagnostic_plan_digest"),
        lambda r: r["accelerator"].pop("authority"),
        lambda r: r["accelerator"].pop("device_uuid"),
        lambda r: r["accelerator"].update(
            device_uuid="GPU-99999999-9999-9999-9999-999999999999"
        ),
        lambda r: r["accelerator"].update(grant_digest=APPROVAL_DIGEST),
        lambda r: r["accelerator"].update(authority=STRICT_HOST_GRANT_AUTHORITY),
        lambda r: r["accelerator"].update(approval_digest=_sha("7")),
        lambda r: r["accelerator"].update(diagnostic_plan_digest=_sha("7")),
        lambda r: r["accelerator"].update(role="VALIDATOR_RECONSTRUCTION"),
    ],
)
def test_tampered_local_accelerator_blocks_are_refused(tmp_path, monkeypatch, mutate):
    """Altered identities and hybrids fail closed at the real reader."""
    stage, _ = _stage(tmp_path, monkeypatch, _local_profile())
    _rewrite(stage, mutate)
    with pytest.raises(WorkerFailure):
        load_worker_request(stage)
