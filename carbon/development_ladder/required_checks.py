"""Retained required-check consumption at the development composition door.

No public caller supplies a status or an acceptance Boolean. The registered
Challenge's validated check source owns its obligations. Unknown evidence is
infrastructure unavailability, never a scientific candidate failure. This module
belongs beside the development compiler, outside protected import closures.
"""

from __future__ import annotations


class ChecksUnavailable(RuntimeError):
    code = "construction_checks_unavailable"

    def __init__(self, issues=()):
        super().__init__(self.code)
        self.issues = tuple(issues)


def _source(challenge):
    from carbon.challenge_registry.campaigns import campaign_for_id

    provider = campaign_for_id(challenge).construction_contract
    if provider is None:
        raise ChecksUnavailable()
    return provider()


def _expected(challenge):
    # Independent, closed producer: the provider may supply current statuses,
    # never a weaker roster, different fields, arms, bounds or source version.
    from carbon.battery.unified_contract import contract
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    if challenge != BATTERY_CHALLENGE:
        raise ChecksUnavailable()
    return contract()


def _roster(document):
    for row in document["types"]:
        ids = [check["id"] for check in row["checks"]]
        if not ids or len(ids) != len(set(ids)):
            raise ChecksUnavailable()
        for required in row["checks"]:
            required["status"] = "UNAVAILABLE"
    return document


def check(strategy, composition):
    """Consume original changed types BEFORE stripping/compiling/dispatch.

    Membership authenticates the check's subject. It never changes a check's
    status or substitutes for actual compiler/security evidence.
    """
    from dataclasses import asdict

    from carbon.development_session.unified_construction import (
        UnifiedContract,
        canonical,
        derive,
    )
    from carbon.reconstruction import development_composition as dc

    if type(composition) is not dc.Composition or canonical(
        asdict(dc.registered(composition.digest))
    ) != canonical(asdict(composition)):
        raise ChecksUnavailable()
    try:
        contract = _source(composition.challenge)
    except (AttributeError, OSError, RuntimeError, ValueError):
        raise ChecksUnavailable() from None
    if type(contract) is not UnifiedContract:
        raise ChecksUnavailable()
    # Structural schema validity alone cannot authenticate completeness.
    # Compare the entire expected subject/obligation source, allowing only the
    # trusted provider's current check statuses to vary. No input carries them.
    try:
        expected = _expected(composition.challenge)
    except (AttributeError, OSError, RuntimeError, ValueError):
        raise ChecksUnavailable() from None
    if type(expected) is not UnifiedContract or canonical(
        _roster(contract.document)
    ) != canonical(_roster(expected.document)):
        raise ChecksUnavailable()
    doc = contract.document
    if (
        doc["challenge"] != composition.challenge
        or doc["base_contract_digest"] != composition.base_contract_digest
    ):
        raise ChecksUnavailable()
    binding = derive(strategy, contract)
    pins = {variant.level: variant.digest for variant in composition.variants}
    parameters = strategy.get("parameters") or {}
    issues = []
    for row in doc["types"]:
        if row["type"] not in binding["change_set"]:
            continue
        paths = ["/parameters/" + name for name in row["fields"] if name in parameters]
        if binding["arms"][row["type"]]["variant_digest"] != pins.get(row["label"]):
            issues.extend(
                {"code": "construction_check_subject_unmatched", "path": path}
                for path in paths
            )
        for required in row["checks"]:
            if required["status"] != "PASS":
                issues.extend({"code": required["id"], "path": path} for path in paths)
    if issues:
        raise ChecksUnavailable(issues)
    return binding
