"""Audience-allow-listed human report for B-E3 credibility crosswalks."""

from __future__ import annotations

from enum import Enum

from .credibility import (
    ClaimEvidenceLink,
    CredibilityCrosswalk,
    CredibilityEvidenceSource,
    EvidenceDisclosure,
    assess_credibility_crosswalk,
)
from .credibility_canonical import credibility_crosswalk_digest
from .evidence import DossierEvidenceManifest


class CredibilityReportAudience(str, Enum):
    PUBLIC = "PUBLIC"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"
    CARBON_PRIVATE = "CARBON_PRIVATE"


_VISIBLE_DISCLOSURES = {
    CredibilityReportAudience.PUBLIC: frozenset({EvidenceDisclosure.PUBLIC}),
    CredibilityReportAudience.INDEPENDENT_REVIEW: frozenset(
        {EvidenceDisclosure.PUBLIC, EvidenceDisclosure.INDEPENDENT_REVIEW}
    ),
    CredibilityReportAudience.CARBON_PRIVATE: frozenset(EvidenceDisclosure),
}


def _source_label(
    source: CredibilityEvidenceSource, audience: CredibilityReportAudience
) -> str:
    if source.disclosure not in _VISIBLE_DISCLOSURES[audience]:
        return "WITHHELD"
    if audience is CredibilityReportAudience.PUBLIC:
        return "ALLOW_LISTED_SOURCE"
    if audience is CredibilityReportAudience.INDEPENDENT_REVIEW:
        return f"digest={source.evidence_ref.content_digest if source.evidence_ref else 'UNAVAILABLE'}"
    evidence = source.evidence_ref
    evidence_label = (
        "UNAVAILABLE"
        if evidence is None
        else (
            f"{evidence.evidence_class.value}:"
            f"{evidence.evidence_id}@{evidence.evidence_version}:"
            f"{evidence.content_digest}"
        )
    )
    return f"{source.source_id}@{source.source_version} / {evidence_label}"


def _link_key(value: ClaimEvidenceLink) -> tuple[str, str, str, str]:
    return (
        value.slot.value,
        value.claim_role.value,
        value.source_id,
        value.source_version,
    )


def _source_key(value: CredibilityEvidenceSource) -> tuple[str, str, str]:
    return (value.source_kind.value, value.source_id, value.source_version)


def render_credibility_report(
    crosswalk: CredibilityCrosswalk,
    evidence_manifests: tuple[DossierEvidenceManifest, ...],
    audience: CredibilityReportAudience,
) -> str:
    """Render deterministic Markdown without exposing non-allow-listed identities."""
    if type(crosswalk) is not CredibilityCrosswalk:
        raise TypeError("crosswalk must have its exact nominal type")
    if type(audience) is not CredibilityReportAudience:
        raise TypeError("audience must have its exact nominal type")
    assessment = assess_credibility_crosswalk(crosswalk, evidence_manifests)
    sources = {
        (item.source_id, item.source_version): item for item in crosswalk.sources
    }
    lines = [
        "# Credibility crosswalk report",
        "",
        f"- Audience: `{audience.value}`",
        (
            "- Challenge: "
            f"`{crosswalk.challenge_key.challenge_id}@{crosswalk.challenge_key.version}`"
        ),
        (
            "- Dossier: "
            f"`{crosswalk.dossier_ref.dossier_id}@{crosswalk.dossier_ref.dossier_version}`"
        ),
        f"- Crosswalk: `{crosswalk.crosswalk_id}@{crosswalk.crosswalk_version}`",
        (
            "- Crosswalk digest: `WITHHELD_BY_AUDIENCE`"
            if audience is CredibilityReportAudience.PUBLIC
            else f"- Crosswalk digest: `{credibility_crosswalk_digest(crosswalk)}`"
        ),
        (
            "- Required claims structurally supported: "
            f"`{'YES' if assessment.all_required_claims_supported else 'NO'}`"
        ),
        "- Scientific adequacy certified: `NO`",
        "",
        "## Claim-to-evidence links",
        "",
        "| Slot | Claim | Claim owner | Source kind | Category | Maturity | Availability | Evidence | Limitations | Unresolved inputs |",
        "|---|---|---|---|---|---|---|---|---:|---:|",
    ]
    for link in sorted(crosswalk.links, key=_link_key):
        source = sources[(link.source_id, link.source_version)]
        limitation_count = sum(
            item.ref_kind.value == "LIMITATION" for item in source.use_refs
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    link.slot.value,
                    link.claim_role.value,
                    link.claim_owner.value,
                    source.source_kind.value,
                    source.category.value,
                    source.maturity.value,
                    source.availability.value,
                    _source_label(source, audience),
                    str(limitation_count),
                    str(len(source.human_inputs)),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Evidence-source inventory",
            "",
            "| Source kind | Category | Maturity | Availability | Owner | Source | Limitations | Unresolved inputs |",
            "|---|---|---|---|---|---|---:|---:|",
        )
    )
    for source in sorted(crosswalk.sources, key=_source_key):
        limitation_count = sum(
            item.ref_kind.value == "LIMITATION" for item in source.use_refs
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    source.source_kind.value,
                    source.category.value,
                    source.maturity.value,
                    source.availability.value,
                    source.owner.value,
                    _source_label(source, audience),
                    str(limitation_count),
                    str(len(source.human_inputs)),
                )
            )
            + " |"
        )
    lines.extend(("", "## Unresolved validation issues", ""))
    if assessment.issues:
        lines.extend(
            f"- `{item.code.value}` at `{item.path}`" for item in assessment.issues
        )
    else:
        lines.append("- None at the structural crosswalk layer.")
    lines.extend(
        (
            "",
            "## Qualification ceiling",
            "",
            (
                "This report is an identity and permitted-use inventory. It does not "
                "establish scientific adequacy, standards compliance, security "
                "acceptance, commercial validation, product or production "
                "qualification, or LIVE authority."
            ),
            "",
        )
    )
    return "\n".join(lines)


__all__ = ("CredibilityReportAudience", "render_credibility_report")
