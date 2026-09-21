"""The exam environment Carbon publishes to miners; no dispatch, no execution.

These check a disclosure, not a qualification. Nothing here establishes that the
environment is scientifically qualified, and several cases exist specifically to
stop it ever reading as though it were.
"""

import json

import pytest

from carbon.development_session.exam_environment import (
    SCHEMA,
    exam_environment,
)
from carbon.reconstruction import profile as reconstruction_profile
from carbon.reconstruction.worker import model as worker


def test_every_published_value_is_read_from_the_runtime_it_describes():
    """A published exam environment that has drifted is worse than none.

    Asserted against the constants the reconstruction path runs under, so a
    change to the real envelope that is not reflected here fails rather than
    leaving miners reading a document Carbon no longer honours.
    """
    value = exam_environment()
    envelope = value["resource_envelope"]
    assert value["backend_profile"]["profile_id"] == worker.PROFILE_ID
    assert value["backend_profile"]["profile_version"] == worker.PROFILE_VERSION
    assert value["backend_profile"]["scope"] == worker.SCOPE
    assert (
        value["backend_profile"]["environment_digest"]
        == reconstruction_profile.ENVIRONMENT_DIGEST
    )
    assert envelope["memory_bytes"] == worker.MEMORY_BYTES
    assert envelope["cpu_count"] == worker.CPU_COUNT
    assert envelope["pids_limit"] == worker.PIDS_LIMIT
    assert envelope["scratch_bytes"] == worker.SCRATCH_BYTES
    assert envelope["output_bytes"] == worker.OUTPUT_BYTES
    assert envelope["output_members"] == worker.OUTPUT_MEMBERS
    assert envelope["productive_deadline_seconds"] == worker.PRODUCTIVE_DEADLINE_SECONDS
    assert (
        envelope["graceful_cancellation_seconds"]
        == worker.GRACEFUL_CANCELLATION_SECONDS
    )
    assert value["containment"]["user"] == f"{worker.WORKER_UID}:{worker.WORKER_GID}"
    assert [
        (entry["name"], entry["version"], entry["identity"])
        for entry in value["pinned_dependencies"]
    ] == list(reconstruction_profile.DEPENDENCY_SPECS)


def test_envelope_tracks_the_accepted_host_allocation_change():
    """C-CORE-19 replaced a literal cpuset with one resolved from the host.

    Before it, the cpuset was the exact string "0,1", so two reconstructions
    could never run at once on any host. The published envelope said
    "concurrency: 1" as a flat literal, which would now understate what a
    validator can do. This asserts the disclosure moved with the runtime rather
    than being left behind, since a hardcoded field is exactly what the
    read-from-source drift test cannot catch.
    """
    envelope = exam_environment()["resource_envelope"]
    assert envelope["concurrency_per_launch"] == 1
    assert envelope["concurrent_launches_possible"] is True
    assert envelope["cpu_allocation"] == "QUOTA_FIXED_CPUSET_RESOLVED_FROM_HOST"
    assert "concurrency" not in envelope, "the flat literal must not linger"


def test_resource_sizing_claim_carries_its_scope_limit():
    """A measured result published without its limits is a bigger claim."""
    sizing = exam_environment()["resource_sizing"]
    assert sizing["affects_numerical_result"] is False
    assert "one host" in sizing["scope_limit"].lower()
    assert sizing["evidence"].startswith(".agent/evidence/")


def test_declared_is_never_served_as_qualified():
    value = exam_environment()
    assert value["qualification"]["declared"] is True
    assert value["qualification"]["qualified"] is False
    assert value["qualification"]["backend_support"] == "UNRESOLVED"
    assert "MQ-008" in value["qualification"]["owner"]
    assert "SCIENTIFIC_QUALIFICATION_OF_THIS_ENVIRONMENT" in value["not_established"]
    assert "CROSS_HOST_REPRODUCIBILITY" in value["not_established"]
    assert "ANY_TOLERANCE_OR_ACCEPTANCE_THRESHOLD" in value["not_established"]


def test_the_contract_does_not_constrain_miner_hardware():
    """The owner's direction, made checkable rather than left in prose."""
    miner = exam_environment()["miner_research_hardware"]
    assert miner["constrained_by_this_contract"] is False
    assert miner["must_match_validator"] is False
    assert miner["provider_prescribed"] is False


def test_submitted_object_stays_declarative():
    submission = exam_environment()["submission"]
    assert submission["accepted"] == "DECLARATIVE_TRAINING_STRATEGY"
    for refused in (
        "TRAINED_CHECKPOINT",
        "MINER_COMPUTED_SCORE",
        "MINER_HARDWARE_CLAIM",
        "MINER_RESEARCH_RESULT_AS_EVIDENCE",
    ):
        assert refused in submission["not_accepted"]


def test_the_known_divergence_is_disclosed_not_omitted():
    """A miner is entitled to know what the pinned set does not fix."""
    limitations = exam_environment()["known_limitations"]
    identifiers = {entry["id"] for entry in limitations}
    assert "CPU_INSTRUCTION_SET_DIVERGENCE" in identifiers
    entry = next(e for e in limitations if e["id"] == "CPU_INSTRUCTION_SET_DIVERGENCE")
    assert entry["status"] == "DISCLOSED_UNRESOLVED_OWNER_QUESTION"
    assert entry["evidence"].startswith(".agent/evidence/")


def test_disclosure_carries_no_hidden_evaluation_material():
    """Public means public. Nothing here is derived from hidden state."""
    body = json.dumps(exam_environment()).lower()
    for forbidden in (
        "seed",
        "draw",
        "answer",
        "secret",
        "token",
        "password",
        "credential",
        "private-",
        "/home/",
        "/var/lib/carbon",
    ):
        assert forbidden not in body, forbidden
    assert exam_environment()["disclosure"] == "PUBLIC_READ_ONLY"


def test_projection_is_stable_and_not_shared_mutable_state():
    first, second = exam_environment(), exam_environment()
    assert first == second and first is not second
    first["qualification"]["qualified"] = True
    assert exam_environment()["qualification"]["qualified"] is False
    assert first["schema"] == SCHEMA


@pytest.mark.parametrize(
    "path",
    ["backend_profile", "resource_envelope", "containment", "pinned_dependencies"],
)
def test_required_sections_are_present(path):
    assert exam_environment()[path]
