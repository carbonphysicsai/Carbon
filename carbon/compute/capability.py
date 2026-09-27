"""Provider capability summary for the Control Center UI.

This reports configuration only. It sends no provider request: a configured
RunPod credential says "can try", not "capacity exists"; offers and balance are
observed separately, each with its own observation time.
"""

from __future__ import annotations

from pathlib import Path

from .credentials import CredentialStatus, FileCredentialProvider

__all__ = ["capability_summary"]

RUNPOD_CAPABILITIES = (
    "offers",
    "balance",
    "provision",
    "status",
    "health_check",
    "cancel_provisioning",
    "stop",
    "terminate",
    "reconcile",
    "charges",
)


def capability_summary(*, runpod_key_file: Path | None) -> dict[str, object]:
    status = FileCredentialProvider(runpod_key_file).status()
    runpod = {
        "id": "runpod",
        "kind": "carbon_provisioned",
        "available": status is CredentialStatus.CONFIGURED,
        "reason": (
            "credential_configured_capacity_not_queried"
            if status is CredentialStatus.CONFIGURED
            else str(status)
        ),
        "capabilities": list(RUNPOD_CAPABILITIES),
        "requires_balance_observation_before_provision": True,
    }
    user_host = {
        "id": "user-managed-host",
        "kind": "user_managed",
        "available": True,
        "reason": "miner_brings_own_host",
        "capabilities": ["connect", "health_check"],
    }
    return {
        "schema": "carbon.compute.capability-summary.v1",
        "providers": [runpod, user_host],
    }
