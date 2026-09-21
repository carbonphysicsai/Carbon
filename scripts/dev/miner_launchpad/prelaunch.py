"""Read-only, allow-listed review of configured authority, never admission.

No backend initialization, key access, ledger creation or task execution occurs.
Expected dependencies and configured identities are not observations or evidence.
"""

from __future__ import annotations

import math
import time

from carbon.development_session.exam_environment import exam_environment
from carbon.development_session.profile import CHALLENGE
from carbon.development_session.research_admission import PROFILE, SCHEMA
from carbon.development_session.research_catalog import public_catalog
from carbon.development_session.research_ledger import CEILINGS, FINAL_RESERVE
from carbon.reconstruction.profile import DEPENDENCY_SPECS, ENVIRONMENT_ID
from carbon.scoring.development import rule_digest
from scripts.dev.miner_launchpad.runner import (
    REQUIRED_RUNTIME_KEYS,
    SUPPORTED_RUNTIME_KEYS,
)


def review(cfg, doc):
    if doc.get("schema") != SCHEMA or doc.get("profile") != PROFILE:
        raise ValueError("unsupported review contract")
    if doc.get("principal") != cfg.get("principal"):
        raise ValueError("review owner mismatch")
    caps = doc["ceilings"]
    if (
        type(caps) is not dict
        or set(caps) != set(CEILINGS)
        or any(
            type(v) is not int or not FINAL_RESERVE.get(k, 0) <= v <= CEILINGS[k]
            for k, v in caps.items()
        )
    ):
        raise ValueError("invalid review resource bounds")
    expiry = doc["expires_unix"]
    if type(expiry) not in (int, float) or not math.isfinite(expiry):
        raise ValueError("invalid review expiry")
    status = doc["status"]
    if status not in {"APPROVED", "REQUESTED_NOT_GRANTED", "REVOKED"}:
        raise ValueError("unknown grant state")
    runtime = doc["runtime"]
    # Historical engineering fixtures may have nominal runtime values. These
    # do not become asserted image identities in the new review projection.
    implementation = runtime.get("implementation")
    identities = {}
    if type(implementation) is dict:
        for name in ("revision", "tree", "source_tree_digest"):
            value = implementation.get(name)
            if (
                type(value) is not str
                or len(value) > 80
                or any(
                    c not in "0123456789abcdef:" for c in value.removeprefix("sha256:")
                )
            ):
                raise ValueError("invalid configured runtime identity")
            identities[name] = value
    images = runtime.get("images", [])
    if type(images) is not list or len(images) > 8:
        raise ValueError("invalid image identities")
    images = [
        v
        for v in images
        if type(v) is str
        and len(v) == 71
        and v.startswith("sha256:")
        and all(c in "0123456789abcdef" for c in v[7:])
    ]
    catalog = public_catalog()
    blockers = []
    if cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE":
        blockers.append("OWNER_EXPERIMENT_PAUSE")
    if cfg.get("enabled") is not True:
        blockers.append("OPERATOR_DISPATCH_DISABLED")
    if status != "APPROVED":
        blockers.append("GRANT_NOT_APPROVED")
    if time.time() >= expiry:
        blockers.append("GRANT_EXPIRED")
    if type(implementation) is dict and cfg.get(
        "accepted_revision"
    ) != implementation.get("revision"):
        blockers.append("RUNTIME_REVISION_MISMATCH")
    if cfg.get("account_ref") != doc.get("account_ref"):
        blockers.append("ACCOUNT_BINDING_MISMATCH")
    if not set(runtime) <= SUPPORTED_RUNTIME_KEYS:
        blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
    if not REQUIRED_RUNTIME_KEYS <= set(runtime):
        blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
    research_execution = {"profile": ENVIRONMENT_ID, "backend": "cpu"}
    assurance = None
    if "gpu_research" in runtime:
        from carbon.development_session.gpu_research import declared_gpu_runtime
        from carbon.reconstruction.accelerators import GPU_PROFILE, miner_lane_assurance

        try:
            declared_gpu_runtime(runtime)
        except ValueError:
            # A declared GPU runtime whose scope is malformed is not a GPU
            # campaign. Reviewing it as one would show a miner a cuda backend
            # the runner would refuse to assemble, which is the mismatch this
            # projection exists to prevent.
            blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
        else:
            research_execution = {
                "profile": GPU_PROFILE.profile_id,
                "backend": GPU_PROFILE.backend.value,
            }
            assurance = miner_lane_assurance()
    return {
        "schema": "carbon.launchpad.prelaunch-review.v1",
        "experiment_pause": (
            "ACTIVE"
            if cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE"
            else "NOT_DECLARED"
        ),
        "dispatch_enabled": cfg.get("enabled") is True,
        "blockers": blockers,
        "grant": {
            "status": status,
            "expired": time.time() >= expiry,
            "expires_unix": expiry,
            "validity": "RECHECKED_BY_ADMISSION_ON_DISPATCH",
        },
        "resources": {
            "configured_ceilings": caps,
            "final_evaluation_reserve": dict(FINAL_RESERVE),
            "maximum_exploration": {
                k: v - FINAL_RESERVE.get(k, 0) for k, v in caps.items()
            },
            "basis": "Configured limits, not remaining balance or a reservation transaction. CampaignLedger owns actual usage and reservations.",
        },
        "runtime": {
            "implementation": identities,
            "images": images,
            "basis": "CONFIGURATION_ONLY; exact accepted revision and images checked at execution",
        },
        # Two separately described runtimes, deliberately not merged into one
        # badge. The miner chooses where their research runs; they do not choose
        # what judges it. Showing a GPU here while the comparison below stays CPU
        # is the accurate picture, not an inconsistency.
        "execution": {
            **research_execution,
            "scope": "MINER_RESEARCH_ONLY",
            "lane": (
                "MINER_CONTAINED" if assurance is not None else "CPU_NO_ACCELERATOR"
            ),
            "assurance": assurance,
            "basis": (
                "CONFIGURATION_ONLY; this is the runtime the miner's own research runs on"
            ),
            "installed_dependencies": "NOT_INSPECTED",
            "device_visibility": "NOT_OBSERVED",
            "runtime_evidence": "NOT_ATTACHED",
            "admission_readiness": "NOT_ESTABLISHED_BY_REVIEW",
            "compiled_updates": "DEFAULT_UNCHANGED; no GPU speedup inferred",
        },
        "final_evaluation": {
            # Stated before launch rather than discovered afterwards. A GPU
            # research selection neither selects nor rewrites this.
            "profile": ENVIRONMENT_ID,
            "backend": "cpu",
            "route": "INDEPENDENT_DEVELOPMENT_RECONSTRUCTION",
            "selected_by_research_runtime": False,
            "basis": "The independent DEVELOPMENT comparison runs on the accepted CPU reconstruction route regardless of the research runtime chosen above. It is not a GPU-qualified official result.",
        },
        # Recomputed from the runtime actually selected, so an option existing in
        # the interface never by itself advertises a capability.
        "capabilities": {
            "catalog_version": catalog["version"],
            "backbones": catalog["backbones"],
            "training": catalog["training"],
            "surfaces": list(catalog["surfaces"]),
            "julia_scientific_tasks": "authored_research" in runtime,
            # What was actually validated, not which option exists. A malformed
            # GPU scope advertises nothing.
            "gpu_research": assurance is not None,
            # Julia research stays on its own CPU route; nothing about the JAX
            # GPU selection extends to it.
            "julia_on_gpu": False,
            "selection": "Agent selects a legal strategy during research; no trained model selected at prelaunch",
        },
        # Distinct states, never collapsed into one green badge. Review reads
        # configuration; it observes no host, device, dependency or capacity.
        "readiness": {
            "connection_configured": cfg.get("enabled") is True,
            "dependencies_inspected": False,
            "compatible_runtime_available": "NOT_OBSERVED_BY_REVIEW",
            "user_consent_active": status == "APPROVED" and time.time() < expiry,
            "task_admitted": False,
            "device_execution_observed": False,
            "task_completed": False,
            "cleanup_verified": False,
            "independent_development_evaluation_available": "RESOLVED_AT_FINAL_PHASE",
            "official_qualification": False,
            "basis": "Each state is established by its own evidence. Personal research does not require official qualification; a missing runtime does prevent a managed job from executing.",
        },
        "expected_dependencies": [
            {"name": name, "version": version, "identity": identity}
            for name, version, identity in DEPENDENCY_SPECS
        ],
        # What the design will be graded on, published beside what the miner
        # chose to research with. The two are deliberately adjacent and
        # deliberately separate: the miner picks the left one and is told the
        # right one.
        "validator_exam_environment": exam_environment(),
        "challenge": PROFILE,
        "challenge_identity": {
            "id": CHALLENGE.challenge_id,
            "version": CHALLENGE.version,
        },
        "development_rule_digest": rule_digest(),
        "reconstruction": "Fresh independent DEVELOPMENT reconstruction; practice checkpoints do not replace final evaluation",
    }
