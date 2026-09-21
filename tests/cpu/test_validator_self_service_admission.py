"""GPU validator admission, under the owner decision of 2026-09-21.

Ticket C-CORE-19, work package P. The decision is that GPU
`VALIDATOR_RECONSTRUCTION` admits through the installed host record and
`doctor`, the same path the miner lane uses, and requires no owner-signed grant
and no exclusive lease.

Two of these tests exist because the decision named them: one fails if the role
silently reverts to requiring a grant, and one fails if a contention fact that
could not be observed is ever recorded as an observed absence. The rest hold the
boundaries the decision deliberately left in place - admission is not
qualification, and the strict and local-development authorities stay the two
never-interchangeable things they already were.
"""

from __future__ import annotations

import inspect

import pytest

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    AcceleratorLane,
    AcceleratorRole,
    assurance_permits_official_use,
    lane_for_role,
    miner_lane_assurance,
    validator_self_service_assurance,
)
from carbon.reconstruction.numerics_environment import (
    OBSERVED,
    UNAVAILABLE,
    numerics_environment,
)
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    SELF_SERVICE_HOST_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    DevelopmentWorkerProfile,
    WorkerFailure,
    registered_run_controls,
)

DIGEST = "sha256:" + "ab" * 32


def profile(role, authority=SELF_SERVICE_HOST_AUTHORITY, **kwargs):
    return DevelopmentWorkerProfile(
        DIGEST,
        DIGEST,
        "carbon.c03.cuda.development.v1",
        "1.0",
        kwargs.get("profile_id", GPU_PROFILE.profile_id),
        DIGEST,
        role.value if type(role) is AcceleratorRole else role,
        authority,
        kwargs.get("plan_digest"),
        "GPU-00000000-1111-2222-3333-444444444444",
        registered_run_controls(),
    )


# --- The test the decision asked for: no silent reversion to a grant ---------


def test_the_validator_role_does_not_require_a_grant():
    """Fails if GPU VALIDATOR_RECONSTRUCTION goes back to the strict path.

    This reads the dispatch itself rather than a comment about it. The strict
    branch is reached only after the self-service branch declines a role, so a
    role named in that branch is a role that never loads a host grant.
    """
    source = inspect.getsource(IsolatedReconstructionController.execute)
    head, _, strict = source.partition("AcceleratorHostAdmission.load()")
    assert strict, "the strict admission call should still exist in the tree"
    assert "VALIDATOR_RECONSTRUCTION" in head
    assert "MINER_RESEARCH" in head
    assert "_execute_self_service_lane" in head


def test_the_validator_profile_carries_no_grant_key():
    """A consumer looking for a strict grant must not find this record in it."""
    body = profile(AcceleratorRole.VALIDATOR_RECONSTRUCTION).body["accelerators"]
    assert "grant_digest" not in body
    assert body["host_record_digest"] == DIGEST
    assert body["authority"] == SELF_SERVICE_HOST_AUTHORITY
    assert body["allocation"] == "TASK_OWNED_NOT_EXCLUSIVE"


# --- The other test the decision asked for: missingness stays missing --------


def test_unobservable_contention_is_never_recorded_as_an_observed_absence():
    """Fails if "could not look" is ever collapsed into "found nothing".

    Compute-process enumeration is genuinely unavailable on some hosts - WDDM
    cannot do it, which is what blocked every miner host under the strict
    apparatus. An absence of evidence recorded as evidence of absence would
    license a conclusion about contention that nothing established.
    """
    record = numerics_environment()
    state = record["device_process_enumeration"]
    assert state in (OBSERVED, UNAVAILABLE, "NOT_APPLICABLE")
    if state != OBSERVED:
        # The count must be absent, not zero. Zero is an observation.
        assert record["device_compute_process_count"] is None


def test_the_three_enumeration_states_are_distinct():
    """UNAVAILABLE, NOT_APPLICABLE and OBSERVED answer different questions."""
    assert len({OBSERVED, UNAVAILABLE, "NOT_APPLICABLE"}) == 3
    assert UNAVAILABLE != "NOT_APPLICABLE"


def test_a_cpu_run_reports_not_applicable_rather_than_unavailable():
    """There is no device to contend for, which is not the same as not looking."""
    record = numerics_environment()
    if record["backend"] != "gpu":
        assert record["device_process_enumeration"] == "NOT_APPLICABLE"
        assert record["device_compute_process_count"] is None
        assert record["device_memory_bytes_in_use"] is None


def test_the_contention_block_is_always_present():
    """A reader must never have to guess whether the fields were omitted."""
    record = numerics_environment()
    for key in (
        "device_memory_bytes_in_use",
        "device_memory_bytes_limit",
        "device_process_enumeration",
        "device_compute_process_count",
    ):
        assert key in record


# --- Admission is not qualification -----------------------------------------


def test_a_validator_self_service_run_is_not_officially_eligible():
    """The decision says so explicitly, and this is where it is enforced."""
    assurance = validator_self_service_assurance()
    assert assurance["official_eligible"] is False
    assert assurance["validator_grade"] is False
    assert assurance["strict_equivalent"] is False
    assert assurance_permits_official_use(assurance) is False


def test_neither_lane_permits_official_use():
    assert assurance_permits_official_use(miner_lane_assurance()) is False
    assert assurance_permits_official_use(validator_self_service_assurance()) is False


def test_the_validator_label_does_not_claim_downstream_verification():
    """A validator's own run has no downstream validator to verify it."""
    assurance = validator_self_service_assurance()
    assert assurance["verification"] == "BACKEND_QUALIFICATION_REQUIRED_MQ008"
    assert assurance["verification"] != miner_lane_assurance()["verification"]


def test_the_admission_facts_are_identical_because_the_admission_is():
    """Claiming more for the validator would assert an unrequired guarantee."""
    miner, validator = miner_lane_assurance(), validator_self_service_assurance()
    assert miner["established"] == validator["established"]
    assert miner["not_established"] == validator["not_established"]
    assert "WHOLE_DEVICE_EXCLUSIVITY" in validator["not_established"]
    assert "FOREIGN_COMPUTE_PROCESS_ABSENCE" in validator["not_established"]


# --- The lane follows the role, and the schema keeps its meaning -------------


@pytest.mark.parametrize(
    "role,lane,schema",
    [
        (
            AcceleratorRole.MINER_RESEARCH,
            AcceleratorLane.MINER_CONTAINED,
            "carbon.c03.development-worker-profile.v5",
        ),
        (
            AcceleratorRole.VALIDATOR_RECONSTRUCTION,
            AcceleratorLane.VALIDATOR_ISOLATED,
            "carbon.c03.development-worker-profile.v6",
        ),
    ],
)
def test_the_lane_and_schema_follow_the_role(role, lane, schema):
    document = profile(role).body
    assert document["schema"] == schema
    assert document["accelerators"]["lane"] == lane.value
    assert document["accelerators"]["role"] == role.value
    assert lane_for_role(role) is lane


def test_v5_still_means_exactly_a_miner_run():
    """Every v5 record already written is a miner run, and must stay one.

    Widening v5 in place would have silently changed what those records assert
    to a consumer that reads the version, which is why the validator body is v6.
    """
    document = profile(AcceleratorRole.MINER_RESEARCH).body
    assert document["schema"] == "carbon.c03.development-worker-profile.v5"
    assert document["accelerators"]["lane"] == AcceleratorLane.MINER_CONTAINED.value
    assert document["accelerators"]["assurance"] == miner_lane_assurance()


# --- Boundaries the decision left in place -----------------------------------


def test_the_two_reserved_authorities_stay_distinct():
    """STRICT_HOST_GRANT and LOCAL_DEVELOPMENT_APPROVAL are not interchangeable."""
    assert STRICT_HOST_GRANT_AUTHORITY != LOCAL_DEVELOPMENT_AUTHORITY
    assert SELF_SERVICE_HOST_AUTHORITY not in (
        STRICT_HOST_GRANT_AUTHORITY,
        LOCAL_DEVELOPMENT_AUTHORITY,
    )


def test_self_service_is_not_a_relaxed_strict_grant():
    """No third 'validator self-service' authority was invented for this."""
    from carbon.reconstruction.worker.model import MINER_HOST_AUTHORITY

    assert SELF_SERVICE_HOST_AUTHORITY == MINER_HOST_AUTHORITY


def test_self_service_admission_is_refused_for_a_non_gpu_profile():
    """Neither weaker authority exists for anything but the portable GPU profile."""
    with pytest.raises(WorkerFailure):
        profile(
            AcceleratorRole.VALIDATOR_RECONSTRUCTION,
            profile_id="carbon_jax_tpu_preparation_v1",
        )


def test_an_unknown_role_does_not_inherit_self_service_admission():
    """A third role, if one is ever added, does not get this by default."""
    with pytest.raises(WorkerFailure):
        profile("SOME_FUTURE_ROLE")


def test_the_strict_path_is_still_in_the_tree():
    """Not removed and not built on: the decision forbids both."""
    source = inspect.getsource(IsolatedReconstructionController.execute)
    assert "AcceleratorHostAdmission.load()" in source
    assert "exclusive_lease()" in inspect.getsource(IsolatedReconstructionController)
