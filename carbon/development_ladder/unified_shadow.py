"""Operator-only unified/ladder comparison; never an admission or score input.

Compiler-route agreement alone is incomplete evidence. Rebuilt artifact digests
must come from the two rebuild receipts; recipe/expression/plan digests do not
substitute for them. No candidate content is emitted in diagnostics.
"""

from carbon.development_session.unified_construction import SHA, UnifiedRefused, derive


def compare(
    strategy,
    contract,
    legacy_variant_digest,
    *,
    legacy_artifact=None,
    unified_artifact=None,
):
    result = {
        "schema": "carbon.unified-construction-shadow.v1",
        "unified_digest": contract.digest,
        "status": "INCOMPLETE",
        "derivation_match": None,
        "route_match": None,
        "artifact_match": None,
        "refusal": None,
        "authority": "DEVELOPMENT_DIAGNOSTIC_ONLY",
    }
    try:
        binding = derive(strategy, contract)
    except UnifiedRefused as refused:
        result.update(status="MISMATCH", refusal=refused.code)
        return result
    doc = contract.document
    legacy = [
        (row, arm)
        for row in doc["types"]
        for arm in row["arms"]
        if arm["digest"] == legacy_variant_digest
    ]
    from carbon.reconstruction.capability_registry import (
        development_composition_document,
    )

    composition = development_composition_document(legacy_variant_digest)
    if composition is not None:
        pins = {part["level"]: part["digest"] for part in composition["composes"]}
        rows = {row["type"]: row for row in doc["types"]}
        result["derivation_match"] = (
            composition["challenge"] == doc["challenge"]
            and composition["base_contract"]["digest"] == doc["base_contract_digest"]
            and set(binding["change_set"]) == set(binding["arms"])
            and binding["derived_label"]
            == max((rows[k]["label"] for k in binding["change_set"]), default=0)
        )
        result["route_match"] = result["derivation_match"] and all(
            selected["variant_digest"] == pins.get(rows[k]["label"])
            for k, selected in binding["arms"].items()
        )
    elif legacy_variant_digest == doc["base_contract_digest"]:
        result["derivation_match"] = result["route_match"] = (
            binding["derived_label"] == 0
        )
    elif len(legacy) == 1:
        row, arm = legacy[0]
        result["derivation_match"] = (
            binding["change_set"] == [row["type"]]
            and binding["derived_label"] == row["label"]
        )
        result["route_match"] = (
            result["derivation_match"]
            and binding["arms"][row["type"]]["variant_digest"] == arm["digest"]
        )
    else:
        result["derivation_match"] = result["route_match"] = False
        result["refusal"] = "construction_type_unregistered"
    if legacy_artifact is not None or unified_artifact is not None:
        if not all(
            type(v) is str and SHA.fullmatch(v)
            for v in (legacy_artifact, unified_artifact)
        ):
            result["refusal"] = "shadow_artifact_receipt_unavailable"
        else:
            result["artifact_match"] = legacy_artifact == unified_artifact
    if False in (
        result["derivation_match"],
        result["route_match"],
        result["artifact_match"],
    ):
        result["status"] = "MISMATCH"
    elif result["artifact_match"] is True:
        result["status"] = "MATCH"
    return result


class Observer:
    """Opt-in sink for successful ladder compiles. No artifact claim is made.

    The operator may separately call compare with independent rebuild receipts.
    The caller owns retention of these diagnostics; no public projection exists.
    """

    def __init__(self, contract, sink):
        self.contract = contract
        self.sink = sink

    def __call__(self, strategy, variant_digest):
        self.sink(compare(strategy, self.contract, variant_digest))
