"""Read-only, allow-listed review of configured authority, never admission.

No backend initialization, key access, ledger creation or task execution occurs.
Expected dependencies and configured identities are not observations or evidence.
"""

from __future__ import annotations

import math
import time

from carbon.development_session.profile import CHALLENGE
from carbon.development_session.research_admission import PROFILE, SCHEMA
from carbon.development_session.research_catalog import public_catalog
from carbon.development_session.research_ledger import CEILINGS, FINAL_RESERVE
from carbon.reconstruction.profile import DEPENDENCY_SPECS, ENVIRONMENT_ID
from carbon.scoring.development import rule_digest


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
    if set(runtime) != {"implementation", "images"}:
        blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
    requested = {"profile": ENVIRONMENT_ID, "backend": "cpu"}
    if "gpu_research" in runtime:
        from carbon.reconstruction.accelerators import GPU_PROFILE

        requested = {
            "profile": GPU_PROFILE.profile_id,
            "backend": GPU_PROFILE.backend.value,
        }
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
        "execution": {
            **requested,
            "basis": "CONFIGURATION_ONLY; current Launchpad campaign composition is CPU",
            "installed_dependencies": "NOT_INSPECTED",
            "device_visibility": "NOT_OBSERVED",
            "runtime_evidence": "NOT_ATTACHED",
            "admission_readiness": "NOT_ESTABLISHED_BY_REVIEW",
            "compiled_updates": "DEFAULT_UNCHANGED; no GPU speedup inferred",
        },
        "capabilities": {
            "catalog_version": catalog["version"],
            "backbones": catalog["backbones"],
            "training": catalog["training"],
            "surfaces": list(catalog["surfaces"]),
            "selection": "Agent selects a legal strategy during research; no trained model selected at prelaunch",
        },
        "expected_dependencies": [
            {"name": name, "version": version, "identity": identity}
            for name, version, identity in DEPENDENCY_SPECS
        ],
        "challenge": PROFILE,
        "challenge_identity": {
            "id": CHALLENGE.challenge_id,
            "version": CHALLENGE.version,
        },
        "development_rule_digest": rule_digest(),
        "reconstruction": "Fresh independent DEVELOPMENT reconstruction; practice checkpoints do not replace final evaluation",
    }
