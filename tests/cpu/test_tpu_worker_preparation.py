"""TPU request preparation must never become local device admission."""

from dataclasses import replace

import pytest

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    TPU_PROFILE,
    AcceleratorRole,
    accelerator_dependency_specs,
    require_reconstruction_profile_admission,
)
from carbon.reconstruction.model import ReconstructionFailure
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.worker.model import (
    DevelopmentWorkerProfile,
    RequestDerivedWorkerProfile,
    WorkerCode,
    WorkerFailure,
)
from carbon.reconstruction.worker.protocol import _request_worker_profile


def _sha(character):
    return "sha256:" + character * 64


def _profile(role=AcceleratorRole.MINER_RESEARCH):
    return DevelopmentWorkerProfile(
        _sha("1"),
        _sha("2"),
        "carbon.c03.tpu.preparation.v1",
        "1.0",
        TPU_PROFILE.profile_id,
        _sha("3"),
        role.value,
    )


@pytest.mark.parametrize("role", tuple(AcceleratorRole))
def test_prepared_tpu_profile_is_distinct_and_role_bound(role):
    profile = _profile(role)
    assert profile.body["schema"] == "carbon.c03.development-worker-profile.v3"
    assert profile.body["accelerators"]["host_dispatch"] == "UNAVAILABLE"
    request = {
        "schema": "carbon.c03.worker-request.v3",
        "replicate": {
            "policy_digest": _sha("1"),
            "resource_class_digest": _sha("2"),
        },
        "accelerator": {
            "profile_id": TPU_PROFILE.profile_id,
            "grant_digest": _sha("3"),
            "role": role.value,
        },
    }
    # The reader returns its narrowed, verification-only profile rather than the
    # full one: it carries the digest the comparison needs and the identity
    # fields admission routes on, and deliberately no bound. Comparing against
    # the narrowing of the expected profile asserts the same identity as before
    # and additionally that the narrowing happened.
    assert _request_worker_profile(request) == RequestDerivedWorkerProfile.of(profile)
    for schema in ("carbon.c03.worker-request.v1", "carbon.c03.worker-request.v2"):
        with pytest.raises(WorkerFailure):
            _request_worker_profile({**request, "schema": schema})
    for extra in ("device_path", "admission_enabled", "script", "tolerance"):
        with pytest.raises(WorkerFailure):
            _request_worker_profile(
                {**request, "accelerator": {**request["accelerator"], extra: True}}
            )


@pytest.mark.parametrize("role", tuple(AcceleratorRole))
def test_fabricated_typed_tpu_profile_cannot_enable_reconstruction(
    monkeypatch, tmp_path, role
):
    import c02_fixtures

    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_ID", TPU_PROFILE.profile_id)
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_VERSION", "1.0")
    monkeypatch.setattr(
        c02_fixtures,
        "DEPENDENCY_SPECS",
        c02_fixtures.DEPENDENCY_SPECS + accelerator_dependency_specs(TPU_PROFILE),
    )
    plan = c02_fixtures.compile_c02_plan(
        tmp_path, environment_digest=TPU_PROFILE.digest
    )
    compiled = compile_development_profile(plan)
    assert compiled.profile_id == TPU_PROFILE.profile_id
    with pytest.raises(ReconstructionFailure) as failure:
        require_reconstruction_profile_admission(
            compiled, worker_profile=_profile(role)
        )
    assert failure.value.code == "reconstruction.accelerator.admission_disabled"


def test_profile_families_and_invalid_roles_cannot_be_substituted():
    for changes in (
        {"accelerator_profile_id": GPU_PROFILE.profile_id},
        {"profile_id": "carbon.c03.cuda.development.v1"},
        {"accelerator_role": "OPERATOR"},
        {"profile_version": "2.0"},
    ):
        with pytest.raises(WorkerFailure):
            replace(_profile(), **changes)
    assert (
        _profile().digest != _profile(AcceleratorRole.VALIDATOR_RECONSTRUCTION).digest
    )


def test_nvidia_docker_adapter_rejects_tpu_before_runtime_calls(tmp_path):
    from carbon.reconstruction.worker.docker_runtime import create_arguments

    with pytest.raises(WorkerFailure) as failure:
        create_arguments(
            container_name="fixture",
            image_id=_sha("4"),
            input_directory=tmp_path,
            cpuset="0,1",
            launch_digest=_sha("5"),
            worker_profile=_profile(),
        )
    assert failure.value.code is WorkerCode.UNSUPPORTED


def test_package_instrument_reconciles_uncertain_create_and_rejects_foreign_owner():
    from types import SimpleNamespace

    from scripts.dev.inspect_tpu_worker_image import _cleanup_instrument

    calls = []
    name = "fixture-owned-instrument"
    cli = SimpleNamespace(
        json=lambda command: {
            "Config": {"Labels": {"carbon.package.instrument": name}}
        },
        run=lambda command, **kwargs: (
            calls.append(command) or SimpleNamespace(stdout=b"")
        ),
    )
    _cleanup_instrument(cli, name)
    assert calls[0] == ["rm", "--force", name]
    assert calls[1][-1] == f"name=^/{name}$"
    calls.clear()
    cli.json = lambda command: {
        "Config": {"Labels": {"carbon.package.instrument": "other"}}
    }
    with pytest.raises(ValueError, match="ownership"):
        _cleanup_instrument(cli, name)
    assert calls == []


def test_package_instrument_absence_requires_successful_confirmation():
    from types import SimpleNamespace

    from scripts.dev.inspect_tpu_worker_image import _cleanup_instrument

    def missing(command):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    cli = SimpleNamespace(json=missing, run=lambda command: SimpleNamespace(stdout=b""))
    _cleanup_instrument(cli, "fixture")
    cli.run = lambda command: SimpleNamespace(stdout=b"container-present")
    with pytest.raises(ValueError, match="uncertain"):
        _cleanup_instrument(cli, "fixture")
