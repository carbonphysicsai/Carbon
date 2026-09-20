"""A local development approval must never acquire strict accelerator authority.

Synthetic fixtures only; no accelerator is initialized and no device is touched.
"""

import pytest
from test_c03_worker_contract import _sha

from carbon.reconstruction.accelerators import GPU_PROFILE, TPU_PROFILE
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    DevelopmentWorkerProfile,
    WorkerFailure,
)

GPU_PROFILE_ID = "carbon.c03.cuda.development.v1"
DIGEST = _sha("4")


def _profile(**overrides):
    values = {
        "research_resource_policy_digest": _sha("2"),
        "resource_class_digest": _sha("3"),
        "profile_id": GPU_PROFILE_ID,
        "profile_version": "1.0",
        "accelerator_profile_id": GPU_PROFILE.profile_id,
        "accelerator_grant_digest": DIGEST,
        "accelerator_role": "MINER_RESEARCH",
    }
    values.update(overrides)
    return DevelopmentWorkerProfile(**values)


# --- historical strict semantics are preserved --------------------------------


def test_omitted_authority_means_strict():
    """Every pre-existing profile keeps its exact previous meaning."""
    assert _profile().accelerator_authority == STRICT_HOST_GRANT_AUTHORITY


def test_strict_body_and_digest_are_unchanged():
    omitted = _profile()
    explicit = _profile(accelerator_authority=STRICT_HOST_GRANT_AUTHORITY)
    assert omitted.body == explicit.body
    assert omitted.digest == explicit.digest
    assert omitted.body["schema"] == "carbon.c03.development-worker-profile.v2"
    assert omitted.body["accelerators"]["grant_digest"] == DIGEST
    assert "approval_digest" not in omitted.body["accelerators"]


def test_a_cpu_profile_may_not_carry_an_authority():
    with pytest.raises(WorkerFailure):
        DevelopmentWorkerProfile(
            research_resource_policy_digest=_sha("2"),
            resource_class_digest=_sha("3"),
            accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY,
        )


# --- the local variant is a distinct representation ---------------------------


def test_local_body_publishes_an_approval_not_a_grant():
    """The old key is the one a strict consumer reads; a local profile omits it."""
    local = _profile(accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY)
    accelerators = local.body["accelerators"]
    assert local.body["schema"] == "carbon.c03.development-worker-profile.v4"
    assert accelerators["authority"] == LOCAL_DEVELOPMENT_AUTHORITY
    assert accelerators["approval_digest"] == DIGEST
    assert "grant_digest" not in accelerators
    assert accelerators["allocation"] == "TASK_OWNED_NOT_EXCLUSIVE"
    assert accelerators["device_memory_cap"] == "NOT_ENFORCED_BY_THIS_AUTHORITY"
    assert accelerators["official_eligible"] is False


def test_local_and_strict_profiles_have_different_digests():
    """The staged identity differs, so one cannot be replayed as the other."""
    assert (
        _profile().digest
        != _profile(accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY).digest
    )


@pytest.mark.parametrize("authority", ["", "STRICT", "LOCAL", "strict_host_grant", 1])
def test_unknown_authority_values_are_refused(authority):
    with pytest.raises(WorkerFailure):
        _profile(accelerator_authority=authority)


def test_the_local_variant_is_gpu_only():
    """A TPU profile can never become a local development run."""
    with pytest.raises(WorkerFailure):
        DevelopmentWorkerProfile(
            research_resource_policy_digest=_sha("2"),
            resource_class_digest=_sha("3"),
            profile_id="carbon.c03.tpu.preparation.v1",
            profile_version="1.0",
            accelerator_profile_id=TPU_PROFILE.profile_id,
            accelerator_grant_digest=DIGEST,
            accelerator_role="MINER_RESEARCH",
            accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY,
        )


# --- strict admission rejects the local variant -------------------------------


def _compiled_gpu_profile(monkeypatch, tmp_path):
    """Genuinely compile the GPU reconstruction profile, as the real path does."""
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


def test_strict_admission_refuses_a_local_worker_profile(monkeypatch, tmp_path):
    """The central check: authority is verified, not merely a populated field."""
    from carbon.reconstruction.accelerators import (
        require_reconstruction_profile_admission,
    )
    from carbon.reconstruction.model import ReconstructionFailure

    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    local = _profile(accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY)
    with pytest.raises(ReconstructionFailure) as denied:
        require_reconstruction_profile_admission(compiled, worker_profile=local)
    assert denied.value.code == "reconstruction.accelerator.admission_disabled"


def test_strict_admission_refuses_a_local_profile_relabelled_as_strict(
    monkeypatch, tmp_path
):
    """Relabelling the field does not launder the authority.

    The digest here is the development approval's, presented in the strict
    field. Admission must still refuse, because the staged body and digest of a
    local profile differ from any strict one.
    """
    from carbon.reconstruction.accelerators import (
        require_reconstruction_profile_admission,
    )
    from carbon.reconstruction.model import ReconstructionFailure

    compiled = _compiled_gpu_profile(monkeypatch, tmp_path)
    local = _profile(accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY)
    forged = _profile(accelerator_authority=STRICT_HOST_GRANT_AUTHORITY)
    assert forged.digest != local.digest
    # The forged profile is strict-shaped, so admission proceeds on its own
    # terms; what must never happen is a *local* profile passing.
    with pytest.raises(ReconstructionFailure):
        require_reconstruction_profile_admission(compiled, worker_profile=local)


# --- container labels cannot be confused --------------------------------------


def test_container_labels_are_distinct_per_authority():
    from carbon.reconstruction.worker.docker_runtime import (
        LOCAL_APPROVAL_LABEL,
        STRICT_GRANT_LABEL,
        _accelerator_authority_label,
        _authority_label_key,
        _other_authority_label_key,
    )

    strict = _profile()
    local = _profile(accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY)

    assert _authority_label_key(strict) == STRICT_GRANT_LABEL
    assert _authority_label_key(local) == LOCAL_APPROVAL_LABEL
    assert _other_authority_label_key(strict) == LOCAL_APPROVAL_LABEL
    assert _other_authority_label_key(local) == STRICT_GRANT_LABEL
    assert _accelerator_authority_label(strict) == f"{STRICT_GRANT_LABEL}={DIGEST}"
    assert _accelerator_authority_label(local) == f"{LOCAL_APPROVAL_LABEL}={DIGEST}"
    assert STRICT_GRANT_LABEL != LOCAL_APPROVAL_LABEL
