"""GPU execution splits by role: miner research and validator reconstruction.

Accelerator admission was built as one path written to validator requirements -
a host grant asserting exclusive use of a dedicated device - and applied to both
roles. Because dispatch was disabled nobody had to find out whether a miner
could satisfy it, and when a real host appeared it could not: compute-process
enumeration is unavailable under WDDM. A requirement nobody had argued for on
the miner side blocked the host.

The authority for the split is `docs/development/GPU_EXECUTION_LANES.md`. The
reason it is safe is specific, and worth restating where it is tested: Carbon's
submission is a declarative training strategy, not a trained checkpoint.
Validators reconstruct and train from scratch. **Nothing a miner computes
locally is submitted, verified or scored**, so there is nothing on a miner host
to protect and device side-channels defend nothing. Carbon's interest is only
that more of that search happens.

These drive the real public `execute` and the real admission functions. No
device is attached, no container is created, no grant or approval is installed,
and no attempt of the owner's authorised batch is consumed.
"""

import json

import pytest
import scripted_docker  # noqa: F401  (fixtures)
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    TPU_PROFILE,
    AcceleratorLane,
    AcceleratorRole,
    assurance_permits_official_use,
    lane_for_role,
    miner_lane_assurance,
)
from carbon.reconstruction.onboarding import (
    MINER_LANE_REQUIRED_CHECKS,
    miner_lane_blockers,
)
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    MINER_HOST_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    registered_run_controls,
)

harness = _lifecycle_harness

POLICY_DIGEST = "sha256:" + "2" * 64
RESOURCE_DIGEST = "sha256:" + "3" * 64
AUTHORITY_DIGEST = "sha256:" + "4" * 64
DEVICE_UUID = "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81"


def _profile(role, authority, *, device=DEVICE_UUID, controls=None):
    return DevelopmentWorkerProfile(
        POLICY_DIGEST,
        RESOURCE_DIGEST,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        AUTHORITY_DIGEST,
        role.value,
        authority,
        None,
        device,
        controls,
    )


# --- the lane is the role ------------------------------------------------------


def test_each_role_has_exactly_one_lane():
    assert lane_for_role(AcceleratorRole.MINER_RESEARCH) is (
        AcceleratorLane.MINER_CONTAINED
    )
    assert lane_for_role(AcceleratorRole.VALIDATOR_RECONSTRUCTION) is (
        AcceleratorLane.VALIDATOR_ISOLATED
    )
    for value in ("MINER_RESEARCH", None, 0, AcceleratorLane.MINER_CONTAINED):
        with pytest.raises(ValueError):
            lane_for_role(value)


def test_the_miner_authority_is_the_miner_role_only():
    """The lane is reached by being that role, not by presenting an authority."""
    _profile(AcceleratorRole.MINER_RESEARCH, MINER_HOST_AUTHORITY)
    with pytest.raises(WorkerFailure):
        _profile(AcceleratorRole.VALIDATOR_RECONSTRUCTION, MINER_HOST_AUTHORITY)


# --- no fallback, in either direction ------------------------------------------


def test_a_miner_run_never_loads_a_host_grant(harness):
    """A miner host has no grant and never will.

    If the miner role reached strict admission it would fail UNAVAILABLE trying
    to load one, so this proves the strict path was not entered rather than that
    it forgave something.
    """
    assert not (harness.host / "grant.json").exists()
    with pytest.raises(WorkerFailure) as error:
        harness.run(
            local_diagnostic=None, accelerator_role=AcceleratorRole.MINER_RESEARCH
        )
    assert error.value.code is not WorkerCode.UNAVAILABLE


def test_a_refused_strict_admission_does_not_become_a_miner_run(harness):
    assert not (harness.host / "grant.json").exists()
    with pytest.raises(WorkerFailure) as error:
        harness.run(
            local_diagnostic=None,
            accelerator_role=AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        )
    assert error.value.code is WorkerCode.UNAVAILABLE
    assert not harness.cli.created, "a refused strict run must build nothing"


# --- what the miner lane requires, and what it refuses to require --------------


def test_the_required_checks_are_named_and_do_not_include_the_removed_ones():
    removed = {
        "compute_process_enumeration",
        "installed_authority",
        "device_quarantine",
        "display_output",
        "attempt_accounting",
    }
    assert not removed & set(MINER_LANE_REQUIRED_CHECKS)
    assert "host_device_record" in MINER_LANE_REQUIRED_CHECKS
    assert "container_device_runtime" in MINER_LANE_REQUIRED_CHECKS


def _report(**states):
    base = {
        "host_device_record": "READY",
        "container_daemon": "READY",
        "container_runtime": "READY",
        "container_device_runtime": "READY",
        "compute_process_enumeration": "READY",
        "display_output": "READY",
        "device_quarantine": "READY",
        "installed_authority": "READY",
        "attempt_accounting": "READY",
    }
    base.update(states)
    return {
        "findings": [
            {"check": check, "state": state, "detail": ""}
            for check, state in base.items()
        ]
    }


def test_unavailable_enumeration_does_not_block_a_miner():
    """The exact condition that blocked the real host. It must not block here."""
    assert miner_lane_blockers(_report(compute_process_enumeration="BLOCKED")) == []


@pytest.mark.parametrize(
    "check",
    [
        "installed_authority",
        "device_quarantine",
        "display_output",
        "attempt_accounting",
    ],
)
def test_the_removed_requirements_do_not_block_a_miner(check):
    assert miner_lane_blockers(_report(**{check: "BLOCKED"})) == []


@pytest.mark.parametrize("check", MINER_LANE_REQUIRED_CHECKS)
def test_each_required_check_does_block_a_miner(check):
    """Removing requirements is not removing all of them."""
    assert miner_lane_blockers(_report(**{check: "BLOCKED"})) == [check]


def test_an_unknown_required_check_does_not_block():
    """Unknown telemetry stays unknown; it is not folded into a refusal."""
    assert miner_lane_blockers(_report(host_device_record="UNKNOWN")) == []


# --- controls are resolved, and nothing is invented ---------------------------


def test_miner_controls_are_the_registered_bounds_with_nothing_added():
    controls = registered_run_controls()
    from carbon.reconstruction.worker.model import (
        MEMORY_BYTES,
        OUTPUT_BYTES,
        PRODUCTIVE_DEADLINE_SECONDS,
    )

    assert controls == {
        "productive_seconds": PRODUCTIVE_DEADLINE_SECONDS,
        "host_ram_bytes": MEMORY_BYTES,
        "output_bytes": OUTPUT_BYTES,
        "worker_network": "DISABLED",
    }
    # Batch authority is absent rather than defaulted: nothing registers a
    # whole-attempt deadline, a batch window or a step ceiling, so publishing
    # one here would be a bound nobody set.
    assert not {
        "attempt_seconds",
        "batch_seconds",
        "batch_output_bytes",
        "training_steps",
    } & set(controls)


def test_the_resolved_controls_reach_the_launch():
    profile = _profile(
        AcceleratorRole.MINER_RESEARCH,
        MINER_HOST_AUTHORITY,
        controls=registered_run_controls(),
    )
    controls = registered_run_controls()
    assert profile.effective_deadline_seconds == controls["productive_seconds"]
    assert profile.effective_output_bytes == controls["output_bytes"]


# --- the published body -------------------------------------------------------


def test_the_miner_body_publishes_the_lane_and_claims_no_exclusivity():
    body = _profile(
        AcceleratorRole.MINER_RESEARCH,
        MINER_HOST_AUTHORITY,
        controls=registered_run_controls(),
    ).body
    block = body["accelerators"]
    assert body["schema"] == "carbon.c03.development-worker-profile.v5"
    assert block["lane"] == AcceleratorLane.MINER_CONTAINED.value
    assert block["allocation"] == "TASK_OWNED_NOT_EXCLUSIVE"
    assert "EXCLUSIVE" not in block["allocation"].replace("NOT_EXCLUSIVE", "")
    # No grant key. A consumer looking for one must not find a miner record
    # occupying it.
    assert "grant_digest" not in block
    assert block["host_record_digest"] == AUTHORITY_DIGEST


def test_the_strict_and_cpu_bodies_are_untouched_by_the_split():
    """The split adds a lane; it does not edit the bodies that already existed."""
    cpu = DevelopmentWorkerProfile(POLICY_DIGEST, RESOURCE_DIGEST).body
    assert cpu["schema"] == "carbon.c03.development-worker-profile.v1"
    assert cpu["accelerators"] == "NOT_APPLICABLE"

    strict = _profile(AcceleratorRole.VALIDATOR_RECONSTRUCTION, None).body
    assert strict["schema"] == "carbon.c03.development-worker-profile.v2"
    assert set(strict["accelerators"]) == {
        "allocation",
        "device_uuid",
        "grant_digest",
        "profile_digest",
        "profile_id",
        "role",
    }
    assert strict["accelerators"]["allocation"] == "EXCLUSIVE_SINGLE_DEVICE"

    tpu = DevelopmentWorkerProfile(
        POLICY_DIGEST,
        RESOURCE_DIGEST,
        "carbon.c03.tpu.preparation.v1",
        "1.0",
        TPU_PROFILE.profile_id,
        AUTHORITY_DIGEST,
        AcceleratorRole.MINER_RESEARCH.value,
    ).body
    assert tpu["schema"] == "carbon.c03.development-worker-profile.v3"

    for body in (cpu, strict, tpu):
        assert "lane" not in json.dumps(body["accelerators"])
        assert "assurance" not in json.dumps(body["accelerators"])


# --- a miner result is not evidence -------------------------------------------


def test_a_miner_result_is_never_official_or_validator_grade():
    assurance = miner_lane_assurance()
    assert assurance["official_eligible"] is False
    assert assurance["validator_grade"] is False
    assert assurance["verification"] == "DOWNSTREAM_VALIDATOR_RECONSTRUCTION"
    assert not assurance_permits_official_use(assurance)


def test_what_the_miner_lane_does_not_establish_is_written_down():
    """Absent strict claims are recorded as absent, not merely omitted."""
    absent = set(miner_lane_assurance()["not_established"])
    assert "WHOLE_DEVICE_EXCLUSIVITY" in absent
    assert "FOREIGN_COMPUTE_PROCESS_ABSENCE" in absent
    assert "WHOLE_DEVICE_RELEASE_AFTER_RUN" in absent


@pytest.mark.parametrize(
    "assurance",
    [None, {}, {"schema": "other"}, "MINER", 0, {"official_eligible": True}],
)
def test_an_absent_or_unrecognised_label_is_not_official_use(assurance):
    """A consumer that cannot tell what produced a result must not assume."""
    assert not assurance_permits_official_use(assurance)


def test_the_assurance_label_cannot_be_mutated_for_the_next_reader():
    first = miner_lane_assurance()
    first["official_eligible"] = True
    assert miner_lane_assurance()["official_eligible"] is False


# --- a miner's own concurrent runs --------------------------------------------


def test_the_device_lock_excludes_a_second_run_without_quarantine(
    tmp_path, monkeypatch
):
    """Plain mutual exclusion. It marks nothing and forgives the next attempt."""
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)

    with runtime.miner_device_lease(DEVICE_UUID):
        with (
            pytest.raises(WorkerFailure) as error,
            runtime.miner_device_lease(DEVICE_UUID),
        ):
            pytest.fail("two miner runs held the same device")
        assert error.value.code is WorkerCode.CONFLICT

    # Released, and nothing was quarantined on the way out.
    assert not (root / "device-quarantined").exists()
    with runtime.miner_device_lease(DEVICE_UUID):
        pass


def test_the_device_lock_is_per_device_not_a_shared_carbon_slot(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    other = "GPU-00000000-0000-0000-0000-000000000000"
    with runtime.miner_device_lease(DEVICE_UUID), runtime.miner_device_lease(other):
        pass


# --- the local development approval is a bound, not a third lane ---------------


def test_the_development_approval_is_still_its_own_authority():
    """Two lanes, not three. The owner's batch authority is not dissolved."""
    assert LOCAL_DEVELOPMENT_AUTHORITY != MINER_HOST_AUTHORITY
    assert LOCAL_DEVELOPMENT_AUTHORITY != STRICT_HOST_GRANT_AUTHORITY
    local = DevelopmentWorkerProfile(
        POLICY_DIGEST,
        RESOURCE_DIGEST,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        AUTHORITY_DIGEST,
        AcceleratorRole.MINER_RESEARCH.value,
        LOCAL_DEVELOPMENT_AUTHORITY,
        "sha256:" + "5" * 64,
        DEVICE_UUID,
    )
    assert local.body["schema"] == "carbon.c03.development-worker-profile.v4"
    assert local.body["accelerators"]["official_eligible"] is False
