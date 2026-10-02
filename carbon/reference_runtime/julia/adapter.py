"""The one registered Julia diagnostic behind the existing C-04 request API.

Trusted miner, Workbench and validator compositions may select this instrument
after their own rights/resource admission. No caller can select a grader,
script, tolerance, package or protected case through this adapter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.reference_runtime.julia.protocol import (
    JULIA_VERSION,
    METHOD_ID,
    JuliaBurgersRequest,
    JuliaFailure,
    JuliaFailureCode,
    execute_in_worker,
    source_digest,
)
from carbon.reference_runtime.model import (
    JULIA_METHOD_VARIANT,
    JULIA_POLICY_ID,
    BurgersReferenceArtifact,
    BurgersReferenceRequest,
    BurgersReferenceRole,
    BurgersReferenceRun,
    reference_settings,
    runtime_environment_digest,
)

JULIA_TARBALL_DIGEST = (
    "sha256:8975da61c128a5e5ded3e719e868da8c8781deb7ad7913d37fb99be02a81904b"
)


def julia_environment_digest() -> str:
    """Describe pinned expected bytes without starting Julia in the controller.

    The content-addressed worker image binds the runtime archive. The child
    additionally verifies its actual Julia version; this descriptor alone is
    neither installation evidence nor resource or scientific authorization.
    """
    body = {
        "schema": "carbon.julia.reference-environment.v1",
        "python_environment": runtime_environment_digest(),
        "julia": JULIA_VERSION,
        "julia_tarball": JULIA_TARBALL_DIGEST,
        "instrument_source": source_digest(),
        "platform": "linux-x86_64-cpu",
        "precision": "float64",
        "method": METHOD_ID,
        "third_party_packages": [],
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def julia_crosscheck_request(
    source: BurgersReferenceRequest, *, units: str
) -> BurgersReferenceRequest:
    """Bind an existing authorized physical case to the fixed Julia diagnostic.

    Explicit units are required because v1 did not serialize a units field.
    This returns a new v2 request/diagnostic policy identity; it never replaces
    the supplied primary/witness request or inherits scientific authority.
    """
    if type(source) is not BurgersReferenceRequest or type(units) is not str:
        raise ValueError("exact reference request and declared units required")
    return replace(
        source,
        role=BurgersReferenceRole.DEVELOPMENT_CROSSCHECK,
        method_variant=JULIA_METHOD_VARIANT,
        policy_id=JULIA_POLICY_ID,
        units=units,
        environment_digest=julia_environment_digest(),
        settings=reference_settings(
            BurgersReferenceRole.DEVELOPMENT_CROSSCHECK,
            len(source.spatial_points),
            method_variant=JULIA_METHOD_VARIANT,
        ),
    )


def execute_julia_reference(request: BurgersReferenceRequest) -> BurgersReferenceRun:
    """Execute only inside C-04's already-admitted, supervised reference worker."""
    if (
        type(request) is not BurgersReferenceRequest
        or request.method_variant != JULIA_METHOD_VARIANT
        or request.role is not BurgersReferenceRole.DEVELOPMENT_CROSSCHECK
    ):
        raise ValueError("registered Julia diagnostic request required")
    if request.environment_digest != julia_environment_digest():
        return BurgersReferenceRun(
            request.request_digest,
            request.role,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
            None,
            (("environment", "MISMATCH_OR_UNAVAILABLE"),),
        )
    bridge_request = JuliaBurgersRequest(
        case_digest=request.case_digest,
        domain_length=request.domain_length,
        viscosity=request.viscosity,
        mean=request.mean,
        cosine_coefficients=request.cosine_coefficients,
        sine_coefficients=request.sine_coefficients,
        requested_times=request.requested_times,
        output_points=len(request.spatial_points),
        units=request.units,
    )
    try:
        # Leave time within the existing 600-second outer worker deadline for
        # startup, output export and controller cleanup. No caller override.
        result = execute_in_worker(bridge_request, deadline_seconds=540.0)
    except JuliaFailure as failure:
        outcome, reason = {
            JuliaFailureCode.INVALID: (
                ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
                ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
            ),
            JuliaFailureCode.ENVIRONMENT: (
                ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
                ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
            ),
            JuliaFailureCode.UNAVAILABLE: (
                ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
                ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
            ),
            JuliaFailureCode.NUMERICAL: (
                ReferenceRunOutcome.NUMERICAL_FAILURE,
                ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            ),
            JuliaFailureCode.DEADLINE: (
                ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
                ReferenceFailureReason.TIMEOUT,
            ),
            JuliaFailureCode.CANCELLED: (
                ReferenceRunOutcome.CANCELLED,
                ReferenceFailureReason.TRUSTED_CANCELLATION,
            ),
            JuliaFailureCode.OUTPUT_LIMIT: (
                ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
                ReferenceFailureReason.RESOURCE_LIMIT,
            ),
            JuliaFailureCode.PROCESS: (
                ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
                ReferenceFailureReason.PROCESS_FAILURE,
            ),
            JuliaFailureCode.CLEANUP: (
                ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
                ReferenceFailureReason.PROCESS_FAILURE,
            ),
        }[failure.code]
        return BurgersReferenceRun(
            request.request_digest,
            request.role,
            outcome,
            reason,
            None,
            (("method", request.method_id), ("native_failure", failure.code.value)),
        )
    diagnostics = {
        "method": request.method_id,
        "language": "julia",
        "runtime_version": JULIA_VERSION,
        "units": request.units,
        "coarse_points": result.coarse_points,
        "fine_points": result.fine_points,
        "coarse_steps": result.coarse_steps,
        "fine_steps": result.fine_steps,
        "coarse_internal_mean_drift": result.coarse_mean_drift,
        "fine_internal_mean_drift": result.fine_mean_drift,
        "refinement_rms": result.refinement_rms,
        "refinement_max": result.refinement_max,
        "completed_horizon": result.completed_horizon,
        "solver_seconds": result.solver_seconds,
        "julia_cumulative_allocated_bytes": result.allocated_bytes,
        "refinement_interpretation": "DISCREPANCY_NOT_CERTIFIED_ERROR_BOUND",
    }
    return BurgersReferenceRun(
        request.request_digest,
        request.role,
        ReferenceRunOutcome.SUPPORTED,
        None,
        BurgersReferenceArtifact(request.request_digest, result.shape, result.payload),
        tuple(sorted(diagnostics.items())),
    )
