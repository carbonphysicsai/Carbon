"""Registered candidate-triggered adapter-fault classification.

The policy documents live beside Graphite's other attribution policies so the
Attacker and validator bind the same bytes.  This module owns only mechanical
loading and non-negotiable invariants.  It does not choose retry counts, charge
fees, issue refunds or turn infrastructure faults into scientific outcomes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

POLICY_SCHEMA = "carbon.graphite.candidate-fault-policy.v1"
REGISTRY_SCHEMA = "carbon.graphite.pod-attribution-registry.v1"
POLICY_DIR = (
    Path(__file__).resolve().parents[1]
    / "agent_campaign"
    / "graphite"
    / "attribution_policies"
)

FAILED_INFRA = "FAILED_INFRA"
ADAPTER_FAILURE = "adapter_failure"
FAULTS = frozenset({"rebuild_exception", "predict_exception", "non_finite_score"})
_POLICY_KEYS = {
    "schema",
    "version",
    "authority",
    "status",
    "challenge",
    "faults",
    "classification",
    "retry",
    "refund",
    "notes",
}
_CLASSIFICATION_KEYS = {
    "kind",
    "code",
    "scientific_result",
    "candidate_penalty",
}
_RETRY_KEYS = {
    "owner",
    "validator_performs",
    "eligibility",
    "new_charge",
    "retry_credit",
}
_REFUND_KEYS = {
    "owner",
    "validator_performs",
    "charged_terminal",
    "uncharged_terminal",
}


class CandidateFaultPolicyRefused(ValueError):
    """A missing, altered, unregistered or unsafe policy."""


def _digest(document):
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _read(path, why):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CandidateFaultPolicyRefused(why) from None


@dataclass(frozen=True)
class CandidateFaultPolicy:
    """One checked, registered Challenge candidate-fault policy."""

    version: str
    digest: str
    challenge_id: str
    challenge_version: str
    faults: frozenset
    classification: dict
    retry: dict
    refund: dict

    @staticmethod
    def from_document(document, digest):
        if type(document) is not dict or set(document) != _POLICY_KEYS:
            raise CandidateFaultPolicyRefused("candidate-fault policy fields")
        if document["schema"] != POLICY_SCHEMA:
            raise CandidateFaultPolicyRefused("candidate-fault policy schema")
        if not all(
            type(document[name]) is str and document[name]
            for name in ("version", "authority", "status")
        ):
            raise CandidateFaultPolicyRefused("candidate-fault policy identity")
        challenge = document["challenge"]
        if (
            type(challenge) is not dict
            or set(challenge) != {"id", "version"}
            or not all(type(value) is str and value for value in challenge.values())
        ):
            raise CandidateFaultPolicyRefused("candidate-fault challenge")
        faults = document["faults"]
        if (
            type(faults) is not list
            or len(faults) != len(set(faults))
            or frozenset(faults) != FAULTS
        ):
            raise CandidateFaultPolicyRefused(
                "candidate-fault policy covers the registered v1 faults"
            )
        classification = document["classification"]
        if (
            type(classification) is not dict
            or set(classification) != _CLASSIFICATION_KEYS
            or classification
            != {
                "kind": FAILED_INFRA,
                "code": ADAPTER_FAILURE,
                "scientific_result": False,
                "candidate_penalty": False,
            }
        ):
            raise CandidateFaultPolicyRefused(
                "candidate faults are non-scientific FAILED_INFRA"
            )
        retry = document["retry"]
        if (
            type(retry) is not dict
            or set(retry) != _RETRY_KEYS
            or retry
            != {
                "owner": "registered_submission_lifecycle",
                "validator_performs": False,
                "eligibility": "subject_to_registered_attempt_budget",
                "new_charge": False,
                "retry_credit": False,
            }
        ):
            raise CandidateFaultPolicyRefused(
                "candidate-fault retry stays in the registered lifecycle"
            )
        refund = document["refund"]
        if (
            type(refund) is not dict
            or set(refund) != _REFUND_KEYS
            or refund
            != {
                "owner": "registered_fee_service",
                "validator_performs": False,
                "charged_terminal": "full_remaining_balance_refund",
                "uncharged_terminal": "no_fee_event",
            }
        ):
            raise CandidateFaultPolicyRefused(
                "candidate-fault refund stays in the registered fee service"
            )
        notes = document["notes"]
        if (
            type(notes) is not list
            or not notes
            or not all(type(note) is str and note for note in notes)
        ):
            raise CandidateFaultPolicyRefused("candidate-fault policy notes")
        return CandidateFaultPolicy(
            version=document["version"],
            digest=digest,
            challenge_id=challenge["id"],
            challenge_version=challenge["version"],
            faults=frozenset(faults),
            classification=dict(classification),
            retry=dict(retry),
            refund=dict(refund),
        )

    def record(self, fault=None):
        if fault is not None and fault not in self.faults:
            raise CandidateFaultPolicyRefused("candidate fault not registered")
        out = {
            "version": self.version,
            "digest": self.digest,
            "challenge": {
                "id": self.challenge_id,
                "version": self.challenge_version,
            },
            "classification": dict(self.classification),
            "retry": dict(self.retry),
            "refund": dict(self.refund),
        }
        if fault is not None:
            out["fault"] = fault
        return out


def _registry(directory):
    registry = _read(
        Path(directory) / "registry.json",
        "candidate-fault policy registry unreadable",
    )
    section = registry.get("candidate_faults") if type(registry) is dict else None
    if (
        registry.get("schema") != REGISTRY_SCHEMA
        or type(section) is not dict
        or set(section) != {"current_by_challenge", "versions"}
        or type(section["current_by_challenge"]) is not dict
        or type(section["versions"]) is not dict
    ):
        raise CandidateFaultPolicyRefused("candidate-fault policy registry malformed")
    return section


def registered_policies(directory=None):
    directory = POLICY_DIR if directory is None else Path(directory)
    return list(_registry(directory)["versions"])


def load_policy(challenge_id, version=None, *, directory=None):
    """Load the registered policy for `challenge_id`, current when omitted."""

    if type(challenge_id) is not str or not challenge_id:
        raise CandidateFaultPolicyRefused("candidate-fault challenge id")
    directory = POLICY_DIR if directory is None else Path(directory)
    registry = _registry(directory)
    version = (
        registry["current_by_challenge"].get(challenge_id)
        if version is None
        else version
    )
    pinned = registry["versions"].get(version)
    if type(version) is not str or pinned is None:
        raise CandidateFaultPolicyRefused(
            "candidate-fault policy not registered for " + challenge_id
        )
    document = _read(
        directory / f"{version}.json",
        "candidate-fault policy unreadable: " + version,
    )
    digest = _digest(document)
    if digest != pinned:
        raise CandidateFaultPolicyRefused("candidate-fault policy altered: " + version)
    if document.get("version") != version:
        raise CandidateFaultPolicyRefused(
            "candidate-fault policy names another version"
        )
    policy = CandidateFaultPolicy.from_document(document, digest)
    if policy.challenge_id != challenge_id:
        raise CandidateFaultPolicyRefused(
            "candidate-fault policy names another challenge"
        )
    return policy


__all__ = [
    "ADAPTER_FAILURE",
    "FAILED_INFRA",
    "FAULTS",
    "CandidateFaultPolicy",
    "CandidateFaultPolicyRefused",
    "load_policy",
    "registered_policies",
]
