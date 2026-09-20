"""Unit behaviour of the accelerator-block encoder, decoder and admission dispatch.

SCOPE: these build the accelerator block as a dictionary and call
`_request_worker_profile` directly. That is the inner profile decoder, not the
full staged request reader, and no file is written. The real
`stage_request` -> `load_worker_request` boundary is covered by
`test_local_staged_request_reader.py`.

Synthetic fixtures only; no accelerator is initialized, no container is created
and no device is attached.
"""

import json

import pytest
from test_c03_worker_contract import _sha

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    require_local_diagnostic_profile_admission,
    require_profile_admission,
    require_reconstruction_profile_admission,
)
from carbon.reconstruction.model import ReconstructionFailure
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
)
from carbon.reconstruction.worker.protocol import (
    _accelerator_request_schema,
    _request_worker_profile,
)

# Three deliberately different identities.
APPROVAL_DIGEST = _sha("4")
DIAGNOSTIC_PLAN_DIGEST = _sha("5")
POLICY_DIGEST = _sha("2")
RESOURCE_CLASS_DIGEST = _sha("3")


def _local_profile(**overrides):
    values = {
        "research_resource_policy_digest": POLICY_DIGEST,
        "resource_class_digest": RESOURCE_CLASS_DIGEST,
        "profile_id": "carbon.c03.cuda.development.v1",
        "profile_version": "1.0",
        "accelerator_profile_id": GPU_PROFILE.profile_id,
        "accelerator_grant_digest": APPROVAL_DIGEST,
        "accelerator_role": "MINER_RESEARCH",
        "accelerator_authority": LOCAL_DEVELOPMENT_AUTHORITY,
        "accelerator_plan_digest": DIAGNOSTIC_PLAN_DIGEST,
    }
    values.update(overrides)
    return DevelopmentWorkerProfile(**values)


def _strict_profile():
    return DevelopmentWorkerProfile(
        POLICY_DIGEST,
        RESOURCE_CLASS_DIGEST,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        APPROVAL_DIGEST,
        "MINER_RESEARCH",
    )


def _request(profile):
    """The accelerator block the production writer emits for this profile."""
    if profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
        accelerator = {
            "profile_id": profile.accelerator_profile_id,
            "authority": LOCAL_DEVELOPMENT_AUTHORITY,
            "approval_digest": profile.accelerator_grant_digest,
            "diagnostic_plan_digest": profile.accelerator_plan_digest,
            "role": profile.accelerator_role,
        }
    else:
        accelerator = {
            "profile_id": profile.accelerator_profile_id,
            "grant_digest": profile.accelerator_grant_digest,
            "role": profile.accelerator_role,
        }
    return {
        "schema": _accelerator_request_schema(profile),
        "replicate": {
            "policy_digest": POLICY_DIGEST,
            "resource_class_digest": RESOURCE_CLASS_DIGEST,
        },
        "accelerator": accelerator,
    }


# --- the local form is closed and separately versioned ------------------------


def test_local_and_strict_requests_use_different_schemas():
    assert _accelerator_request_schema(_strict_profile()) == (
        "carbon.c03.worker-request.v2"
    )
    assert _accelerator_request_schema(_local_profile()) == (
        "carbon.c03.worker-request.v4"
    )


def test_the_real_reader_round_trips_a_local_request():
    """The production decoder, not a stand-in, must accept the written form."""
    original = _local_profile()
    decoded = _request_worker_profile(_request(original))
    assert decoded.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY
    assert decoded.accelerator_grant_digest == APPROVAL_DIGEST
    assert decoded.accelerator_plan_digest == DIAGNOSTIC_PLAN_DIGEST
    assert decoded.digest == original.digest


def test_the_real_reader_still_round_trips_a_strict_request():
    original = _strict_profile()
    decoded = _request_worker_profile(_request(original))
    assert decoded.accelerator_authority == STRICT_HOST_GRANT_AUTHORITY
    assert decoded.accelerator_plan_digest is None
    assert decoded.digest == original.digest


def test_both_identities_survive_serialization():
    """The two digests must not be collapsed or swapped in transit."""
    payload = json.loads(json.dumps(_request(_local_profile())))
    accelerator = payload["accelerator"]
    assert accelerator["approval_digest"] == APPROVAL_DIGEST
    assert accelerator["diagnostic_plan_digest"] == DIAGNOSTIC_PLAN_DIGEST
    assert accelerator["approval_digest"] != accelerator["diagnostic_plan_digest"]
    decoded = _request_worker_profile(payload)
    assert decoded.accelerator_grant_digest == APPROVAL_DIGEST
    assert decoded.accelerator_plan_digest == DIAGNOSTIC_PLAN_DIGEST


def test_a_swapped_pair_does_not_decode_to_the_original():
    swapped = _request(_local_profile())
    swapped["accelerator"]["approval_digest"] = DIAGNOSTIC_PLAN_DIGEST
    swapped["accelerator"]["diagnostic_plan_digest"] = APPROVAL_DIGEST
    decoded = _request_worker_profile(swapped)
    assert decoded.digest != _local_profile().digest


# --- malformed and hybrid requests fail closed --------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.pop("diagnostic_plan_digest"),
        lambda a: a.pop("authority"),
        lambda a: a.update(grant_digest=APPROVAL_DIGEST),
        lambda a: a.update(authority="STRICT_HOST_GRANT"),
        lambda a: a.update(authority=""),
        lambda a: a.update(extra=1),
    ],
)
def test_malformed_or_hybrid_accelerator_blocks_are_refused(mutate):
    payload = _request(_local_profile())
    mutate(payload["accelerator"])
    with pytest.raises(WorkerFailure) as error:
        _request_worker_profile(payload)
    assert error.value.code in (WorkerCode.INVALID, WorkerCode.UNSUPPORTED)


def test_a_local_block_claiming_the_strict_schema_is_refused():
    payload = _request(_local_profile())
    payload["schema"] = "carbon.c03.worker-request.v2"
    with pytest.raises(WorkerFailure):
        _request_worker_profile(payload)


def test_a_strict_block_claiming_the_local_schema_is_refused():
    payload = _request(_strict_profile())
    payload["schema"] = "carbon.c03.worker-request.v4"
    with pytest.raises(WorkerFailure):
        _request_worker_profile(payload)


# --- admission dispatch never falls back --------------------------------------


def _compiled_gpu_profile(monkeypatch, tmp_path):
    import c02_fixtures

    from carbon.reconstruction.accelerators import accelerator_dependency_specs
    from carbon.reconstruction.profile import compile_development_profile

    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_ID", GPU_PROFILE.profile_id)
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_VERSION", "1.0")
    monkeypatch.setattr(
        c02_fixtures,
        "DEPENDENCY_SPECS",
        c02_fixtures.DEPENDENCY_SPECS + accelerator_dependency_specs(GPU_PROFILE),
    )
    plan = c02_fixtures.compile_c02_plan(
        tmp_path, environment_digest=GPU_PROFILE.digest
    )
    return compile_development_profile(plan)


def test_dispatcher_admits_a_local_profile(monkeypatch, tmp_path):
    """The previously unreachable path is now reachable, by declared authority."""
    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    assert require_profile_admission(compiled, worker_profile=_local_profile()) is None


def test_dispatcher_routes_a_strict_profile_to_the_strict_helper(monkeypatch, tmp_path):
    """Same outcome as calling the strict helper directly: no separate path."""
    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    strict = _strict_profile()
    direct = require_reconstruction_profile_admission(compiled, worker_profile=strict)
    dispatched = require_profile_admission(compiled, worker_profile=strict)
    assert direct == dispatched is None


def test_dispatcher_refuses_an_accelerator_plan_with_no_worker_profile(
    monkeypatch, tmp_path
):
    """Without a controller-staged profile there is no authority of either kind."""
    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    with pytest.raises(ReconstructionFailure) as denied:
        require_profile_admission(compiled, worker_profile=None)
    assert denied.value.code == "reconstruction.accelerator.admission_disabled"


def test_strict_helper_still_refuses_a_local_profile(monkeypatch, tmp_path):
    """No fallback, and no acceptance of a local profile at a strict entry."""
    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    with pytest.raises(ReconstructionFailure):
        require_reconstruction_profile_admission(
            compiled, worker_profile=_local_profile()
        )


def test_local_helper_refuses_a_strict_profile(monkeypatch, tmp_path):
    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    with pytest.raises(ReconstructionFailure):
        require_local_diagnostic_profile_admission(
            compiled, worker_profile=_strict_profile()
        )


def test_local_helper_refuses_a_cpu_plan(tmp_path):
    """A CPU plan carries no accelerator, so a local authority is meaningless."""
    from c02_fixtures import compile_c02_plan

    from carbon.reconstruction.profile import compile_development_profile

    compiled = compile_development_profile(compile_c02_plan(tmp_path))
    with pytest.raises(ReconstructionFailure):
        require_local_diagnostic_profile_admission(
            compiled, worker_profile=_local_profile()
        )


def test_both_helpers_refuse_the_same_malformed_profile():
    """Drift guard: the two self-contained validations must stay aligned."""
    for helper in (
        require_reconstruction_profile_admission,
        require_local_diagnostic_profile_admission,
    ):
        with pytest.raises(ReconstructionFailure) as denied:
            helper(object(), worker_profile=_local_profile())
        assert denied.value.code == "reconstruction.profile.invalid"
