"""Exact audience-safe package-root surface frozen by B-04-D11."""

from __future__ import annotations

import importlib

from carbon import evaluation

_EXPECTED_PUBLIC_EXPORTS = (
    "AdmissionGrantIssuanceOutcome",
    "AdmissionGrantIssuanceReason",
    "ConditioningStatus",
    "PublicReferenceOutcomeProjection",
    "PublicReferencePolicyProjection",
    "ReferenceAuthorityFunction",
    "ReferenceAuthorityTargetKind",
    "ReferenceComparisonOutcome",
    "ReferenceComparisonReason",
    "ReferenceCompositionKind",
    "ReferenceFailureReason",
    "ReferenceRunOutcome",
    "ReferenceSourceClass",
    "ReferenceWitnessTargetKind",
    "ResolutionOutcome",
    "ResolutionReason",
    "SupportApplicabilityStatus",
    "TruthAssetAdmissionOutcome",
    "TruthAssetAdmissionReason",
    "UncertaintyStatus",
    "create_public_reference_outcome_projection",
    "create_public_reference_policy_projection",
)

_PROTECTED_NAMES = (
    "FixturePrimaryReferenceRunner",
    "FixtureReferenceAsset",
    "FixtureWitnessReferenceRunner",
    "PrimaryReferenceRequest",
    "PrimaryReferenceRunner",
    "ReferenceArtifact",
    "ReferenceComparisonRecord",
    "ReferencePolicy",
    "ReferencePolicyEntry",
    "ReferenceResolutionRecord",
    "ReferenceRunRecord",
    "TruthAsset",
    "TruthAssetAdmissionDecisionRecord",
    "TruthAssetAdmissionGrant",
    "TruthAssetAdmissionGrantIssuanceRecord",
    "WitnessReferenceRequest",
    "WitnessReferenceRunner",
    "canonical_bytes",
    "decode_canonical_bytes",
)


def test_evaluation_root_has_exact_ordered_d11_surface() -> None:
    assert type(evaluation.__all__) is list
    assert tuple(evaluation.__all__) == _EXPECTED_PUBLIC_EXPORTS
    assert len(evaluation.__all__) == len(set(evaluation.__all__))
    assert all(name in vars(evaluation) for name in evaluation.__all__)


def test_protected_reference_runtime_is_not_root_exported() -> None:
    reloaded = importlib.import_module("carbon.evaluation")
    for name in _PROTECTED_NAMES:
        assert name not in reloaded.__all__
        assert name not in vars(reloaded)
