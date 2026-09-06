from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from carbon import qualification
from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.invariant
def test_b_e3_has_no_execution_registry_store_or_live_authority_imports() -> None:
    modules = set(
        direct_import_modules(
            REPOSITORY_ROOT,
            REPOSITORY_ROOT / "carbon/qualification/credibility.py",
        )
        + direct_import_modules(
            REPOSITORY_ROOT,
            REPOSITORY_ROOT / "carbon/qualification/credibility_canonical.py",
        )
        + direct_import_modules(
            REPOSITORY_ROOT,
            REPOSITORY_ROOT / "carbon/qualification/credibility_report.py",
        )
    )
    forbidden_prefixes = (
        "carbon.evaluation",
        "carbon.generators",
        "carbon.scoring",
        "carbon.traineval",
        "carbon.mcp",
        "carbon.cards",
        "carbon.fees",
        "carbon.leaderboard",
        "carbon.chain",
        "carbon.registry.gate",
        "carbon.registry.store",
    )
    assert not any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for module_name, _ in modules
        for prefix in forbidden_prefixes
    )


@pytest.mark.invariant
def test_b_e3_schema_has_no_protected_payload_or_authority_boolean_fields() -> None:
    classes = (
        qualification.CredibilityRef,
        qualification.HumanInputBinding,
        qualification.CredibilityEvidenceSource,
        qualification.ClaimEvidenceLink,
        qualification.CredibilityCrosswalk,
    )
    forbidden = (
        "seed",
        "draw",
        "case_id",
        "sample",
        "payload",
        "path",
        "url",
        "locator",
        "approved",
        "qualified",
        "certified",
        "live",
    )
    for cls in classes:
        names = {item.name.lower() for item in fields(cls)}
        assert not any(token in name for token in forbidden for name in names)


@pytest.mark.invariant
def test_b_e3_mms_and_assessment_ceiling_are_mechanically_closed() -> None:
    allowed = qualification.SOURCE_KIND_ALLOWED_CLAIMS[
        qualification.EvidenceSourceKind.MMS_CODE_VERIFICATION
    ]
    assert allowed == {
        qualification.DossierClaimRole.IMPLEMENTATION_VERIFICATION,
        qualification.DossierClaimRole.DISCRETIZATION_CONVERGENCE,
        qualification.DossierClaimRole.REFERENCE_AGREEMENT,
        qualification.DossierClaimRole.LIMITING_CASE_BEHAVIOR,
    }
    assessment = qualification.CredibilityAssessment((), True)
    assert assessment.certifies_scientific_adequacy is False
    with pytest.raises(ValueError):
        qualification.CredibilityAssessment((), True, True)
