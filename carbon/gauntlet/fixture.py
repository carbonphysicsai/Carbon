"""Closed B-E4 extension of the existing synthetic construction fixture.

This module registers inert B-02B catalog data only.  It supplies no default
catalog, execution mode, evaluator state, or qualification authority.
"""

from __future__ import annotations

from dataclasses import replace

from carbon.construction import model as m
from carbon.construction.catalog import (
    CandidateAssemblyContract,
    ParameterCatalog,
    validate_parameter_catalog,
)
from carbon.research.model import (
    FixturePriorAuthorization,
    OutcomeDirection,
    PriorAction,
    PriorExpectedOutcome,
    PriorGuidanceItem,
    PriorGuidanceKind,
    PriorLookupResult,
    PriorPack,
    PriorPublicationClass,
)
from carbon.research.prior_publisher import (
    CoarsenedSyntheticAssociation,
    SyntheticEvidenceSummary,
    SyntheticFinding,
)
from carbon.research.prior_store import prior_pack_ref
from carbon.research.refs import (
    PriorChannel,
    PriorPackRef,
    TestOnlyPriorAuthorizationReceiptRef,
)
from carbon.toy import (
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
    FIXTURE_SAMPLING_SURFACE_ID,
)

from .agents import ProposalDirection, ProposalHint

BE4_FIXTURE_CATALOG_ID = "be4_fixture_parameter_catalog"
BE4_FIXTURE_CATALOG_VERSION = "2.0"
BE4_FIXTURE_PRIOR_BUILDER_VERSION = "be4_three_family_fixture_builder_v2"
BE4_FIXTURE_PRIOR_ID = "be4_three_family_fixture_prior"
BE4_FIXTURE_PRIOR_VERSION = "3.0"
BE4_FIXTURE_TEMPLATE_BUILDER_VERSION = "be4_three_family_fixture_template_v2"
BE4_FIXTURE_LIMITATIONS = ("TEST_ONLY", "NOT_UTILITY_QUALIFIED")

_FAMILIES = (
    FIXTURE_SAMPLING_SURFACE_ID,
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
)
_FAMILY_KINDS = {
    FIXTURE_SAMPLING_SURFACE_ID: m.TrainingLeverKind.SAMPLING,
    FIXTURE_CURRICULUM_SURFACE_ID: m.TrainingLeverKind.CURRICULUM,
    FIXTURE_FEATURE_SURFACE_ID: m.TrainingLeverKind.AUGMENTATION,
}
_LOW_VALUE_REF = "uint64_1"
_HIGH_VALUE_REF = "uint64_2"
_MIXED_EFFECT_MAGNITUDE_BAND = "fixture_effect"


def _has_only_mixed_expected_outcomes(item: object) -> bool:
    """Keep the fixture prior exploratory without defining new outcome types."""

    return (
        type(item) is PriorGuidanceItem
        and bool(item.expected_outcomes)
        and all(
            type(outcome) is PriorExpectedOutcome
            and outcome.direction is OutcomeDirection.MIXED
            and outcome.effect_magnitude_band == _MIXED_EFFECT_MAGNITUDE_BAND
            for outcome in item.expected_outcomes
        )
    )


def _extension_entry(
    *,
    sampling: m.ParameterCatalogEntry,
    surface_id: str,
    consumer_field: str,
    lever_kind: m.TrainingLeverKind,
    semantic_clause_ref: object,
    executable_semantics_ref: object,
    resource_impact_tag: str,
) -> m.ParameterCatalogEntry:
    owner = sampling.semantic_owner_binding
    if (
        type(owner) is not m.TrainingSupportSemanticOwner
        or type(sampling.applicability) is not m.AlwaysApplicable
        or type(sampling.unit_binding) is not m.BoundUnit
        or type(sampling.component_slot_binding)
        is not m.ComponentSelectionNotApplicable
    ):
        raise ValueError("the base sampling fixture has incompatible semantics")
    return m.ParameterCatalogEntry(
        surface_id=surface_id,
        input_source=m.InputSource.PARAMETER_KEY,
        consumer_target=m.ConsumerTarget("fixture_training", consumer_field),
        value_type=m.SurfaceValueType.UINT64,
        unit_binding=sampling.unit_binding,
        domain=m.UInt64RangeDomain(1, 2),
        dependency_surface_ids=(),
        applicability=sampling.applicability,
        requirement=m.ExplicitDefaultSurface(
            m.SurfaceValue(m.SurfaceValueType.UINT64, 1)
        ),
        compatibility_rule_ids=(),
        # One conservative fixed abstract unit covers the bounded semantic
        # dispatch and arithmetic for this fixture family at either value.
        # B-02B declares the fact; B-07E remains the policy evaluator.
        static_resource_contributions=(
            m.FixedResourceContribution(
                "abstract_units",
                sampling.unit_binding.unit_ref,
                1,
                (resource_impact_tag,),
            ),
        ),
        resource_impact_tags=(resource_impact_tag,),
        public_outcome_family_tags=(surface_id,),
        semantic_owner_binding=m.TrainingSupportSemanticOwner(
            semantic_clause_ref, owner.authority_ref
        ),
        lifecycle=m.ActiveLifecycle(),
        training_lever_binding=m.BoundTrainingLever(
            lever_kind, executable_semantics_ref, ()
        ),
        component_slot_binding=sampling.component_slot_binding,
    )


def extend_toy_parameter_catalog(
    *,
    base_catalog: ParameterCatalog,
    candidate_assembly: CandidateAssemblyContract,
    curriculum_semantic_clause_ref: object,
    curriculum_executable_semantics_ref: object,
    feature_semantic_clause_ref: object,
    feature_executable_semantics_ref: object,
) -> ParameterCatalog:
    """Return one prospectively versioned, three-family fixture catalog."""

    if (
        type(base_catalog) is not ParameterCatalog
        or type(candidate_assembly) is not CandidateAssemblyContract
    ):
        raise TypeError("exact B-02B catalog and assembly values are required")
    validate_parameter_catalog(base_catalog, candidate_assembly=candidate_assembly)
    by_id = {entry.surface_id: entry for entry in base_catalog.entries}
    if FIXTURE_CURRICULUM_SURFACE_ID in by_id or FIXTURE_FEATURE_SURFACE_ID in by_id:
        raise ValueError("the fixture extension cannot be applied twice")
    try:
        sampling = by_id[FIXTURE_SAMPLING_SURFACE_ID]
    except KeyError:
        raise ValueError("the registered sampling fixture is unavailable") from None
    lever = sampling.training_lever_binding
    owner = sampling.semantic_owner_binding
    if (
        type(lever) is not m.BoundTrainingLever
        or lever.kind is not m.TrainingLeverKind.SAMPLING
        or sampling.consumer_target
        != m.ConsumerTarget("fixture_training", "sampling_level")
        or sampling.value_type is not m.SurfaceValueType.UINT64
        or type(sampling.domain) is not m.UInt64RangeDomain
        or (sampling.domain.minimum, sampling.domain.maximum) != (1, 2)
        or type(owner) is not m.TrainingSupportSemanticOwner
    ):
        raise ValueError("the registered sampling fixture is incompatible")
    if (
        len(
            {
                owner.semantic_clause_ref,
                curriculum_semantic_clause_ref,
                feature_semantic_clause_ref,
            }
        )
        != 3
        or len(
            {
                lever.executable_semantics_ref,
                curriculum_executable_semantics_ref,
                feature_executable_semantics_ref,
            }
        )
        != 3
    ):
        raise ValueError("fixture families require distinct owner semantic identities")

    curriculum = _extension_entry(
        sampling=sampling,
        surface_id=FIXTURE_CURRICULUM_SURFACE_ID,
        consumer_field="curriculum_emphasis",
        lever_kind=m.TrainingLeverKind.CURRICULUM,
        semantic_clause_ref=curriculum_semantic_clause_ref,
        executable_semantics_ref=curriculum_executable_semantics_ref,
        resource_impact_tag="curriculum_impact",
    )
    feature = _extension_entry(
        sampling=sampling,
        surface_id=FIXTURE_FEATURE_SURFACE_ID,
        consumer_field="feature_degree",
        lever_kind=m.TrainingLeverKind.AUGMENTATION,
        semantic_clause_ref=feature_semantic_clause_ref,
        executable_semantics_ref=feature_executable_semantics_ref,
        resource_impact_tag="feature_impact",
    )
    extended = replace(
        base_catalog,
        object_id=BE4_FIXTURE_CATALOG_ID,
        object_version=BE4_FIXTURE_CATALOG_VERSION,
        entries=(*base_catalog.entries, curriculum, feature),
    )
    validate_parameter_catalog(extended, candidate_assembly=candidate_assembly)
    return extended


def fixture_executable_semantics(
    catalog: ParameterCatalog,
) -> tuple[tuple[str, object], ...]:
    """Project the three exact registered executable-semantics identities."""

    if type(catalog) is not ParameterCatalog:
        raise TypeError("an exact ParameterCatalog is required")
    expected = (
        FIXTURE_SAMPLING_SURFACE_ID,
        FIXTURE_CURRICULUM_SURFACE_ID,
        FIXTURE_FEATURE_SURFACE_ID,
    )
    by_id = {entry.surface_id: entry for entry in catalog.entries}
    result: list[tuple[str, object]] = []
    for surface_id in expected:
        try:
            binding = by_id[surface_id].training_lever_binding
        except KeyError:
            raise ValueError("the three-family fixture catalog is incomplete") from None
        if type(binding) is not m.BoundTrainingLever:
            raise ValueError("a fixture family lacks executable semantics")
        result.append((surface_id, binding.executable_semantics_ref))
    return tuple(result)


class ThreeFamilyTestOnlyPackBuilder:
    """B-07D2 builder for one closed, three-item fixture pack.

    Publication, disclosure checks, durable storage, authorization, and
    retrieval remain owned by B-07D2/B-07D3.  This object only supplies the
    deterministic builder callback consumed by ``SyntheticPriorPublisher``.
    """

    __slots__ = ("__catalog_ref", "__template", "__template_ref")

    def __init__(
        self,
        *,
        catalog: ParameterCatalog,
        candidate_assembly: CandidateAssemblyContract,
        template_pack: PriorPack,
        template_pack_ref: PriorPackRef,
    ) -> None:
        if (
            type(catalog) is not ParameterCatalog
            or type(candidate_assembly) is not CandidateAssemblyContract
            or type(template_pack) is not PriorPack
            or type(template_pack_ref) is not PriorPackRef
            or template_pack.channel is not PriorChannel.TEST_ONLY_FIXTURE
            or template_pack.publication_class is not PriorPublicationClass.TEST_ONLY
            or template_pack.challenge_key != catalog.challenge_key
            or len(template_pack.items) != 1
            or type(template_pack.items[0]) is not PriorGuidanceItem
            or template_pack.prior_id != BE4_FIXTURE_PRIOR_ID
            or template_pack.prior_version != BE4_FIXTURE_PRIOR_VERSION
            or template_pack.builder_version != BE4_FIXTURE_TEMPLATE_BUILDER_VERSION
            or template_pack.limitations != BE4_FIXTURE_LIMITATIONS
            or not _has_only_mixed_expected_outcomes(template_pack.items[0])
        ):
            raise TypeError("the fixture prior template is not exact TEST_ONLY data")
        catalog_ref = catalog.to_ref(candidate_assembly=candidate_assembly)
        if (
            template_pack.parameter_catalog_ref != catalog_ref
            or template_pack_ref != prior_pack_ref(template_pack)
            or template_pack_ref.challenge_key != catalog.challenge_key
            or template_pack_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE
        ):
            raise ValueError("the prior template does not pin the supplied catalog")
        fixture_executable_semantics(catalog)
        object.__setattr__(
            self, "_ThreeFamilyTestOnlyPackBuilder__catalog_ref", catalog_ref
        )
        object.__setattr__(
            self, "_ThreeFamilyTestOnlyPackBuilder__template", template_pack
        )
        object.__setattr__(
            self, "_ThreeFamilyTestOnlyPackBuilder__template_ref", template_pack_ref
        )

    def build(
        self,
        snapshot: SyntheticEvidenceSummary,
        *,
        publication_sequence: int,
        activation_epoch: int,
    ) -> PriorPack:
        if (
            type(snapshot) is not SyntheticEvidenceSummary
            or snapshot.challenge_key != self.__template.challenge_key
            or type(publication_sequence) is not int
            or publication_sequence != 0
            or type(activation_epoch) is not int
            or activation_epoch < 1
            or len(snapshot.associations) != len(_FAMILIES)
            or any(
                type(item) is not CoarsenedSyntheticAssociation
                or item.finding is not SyntheticFinding.MIXED
                or item.effect_band != "null"
                for item in snapshot.associations
            )
            or {item.surface_id for item in snapshot.associations} != set(_FAMILIES)
        ):
            raise ValueError(
                "the fixture builder requires one ordered genesis family set"
            )
        template_item = self.__template.items[0]
        covered_estimands = {
            outcome.public_estimand_ref for outcome in template_item.expected_outcomes
        }
        for association in snapshot.associations:
            if (
                association.public_estimand_ref not in covered_estimands
                or association.public_context_id not in template_item.scope.context_refs
                or association.public_backbone_id
                not in template_item.scope.backbone_refs
                or association.public_provenance_ref
                not in template_item.provenance.public_aggregate_publication_refs
            ):
                raise ValueError(
                    "the fixture summary exceeds the template disclosure scope"
                )
        items = tuple(
            sorted(
                (
                    replace(
                        template_item,
                        item_id=f"be4_{surface_id}_guidance",
                        # Hidden construction-seed order can reverse the sign
                        # of sampling/curriculum changes.  This prior may name
                        # causal families worth comparing, but cannot claim a
                        # realized direction of improvement.
                        kind=PriorGuidanceKind.EXPLORE,
                        intervention=replace(
                            template_item.intervention,
                            surface_id=surface_id,
                            action=PriorAction.COMPARE,
                            baseline_ref=_LOW_VALUE_REF,
                            from_ref=None,
                            to_ref=_HIGH_VALUE_REF,
                        ),
                    )
                    for surface_id in _FAMILIES
                ),
                key=lambda item: item.item_id,
            )
        )
        built = replace(
            self.__template,
            prior_id=BE4_FIXTURE_PRIOR_ID,
            prior_version=BE4_FIXTURE_PRIOR_VERSION,
            publication_sequence=0,
            publication_epoch=activation_epoch - 1,
            activation_epoch=activation_epoch,
            predecessor_pack_ref=None,
            builder_version=BE4_FIXTURE_PRIOR_BUILDER_VERSION,
            items=items,
            limitations=BE4_FIXTURE_LIMITATIONS,
        )
        if any(not _has_only_mixed_expected_outcomes(item) for item in built.items):
            raise ValueError("the fixture prior must retain MIXED expected outcomes")
        return built


def proposal_hints_from_test_only_lookup(
    lookup: PriorLookupResult,
    *,
    catalog: ParameterCatalog,
    candidate_assembly: CandidateAssemblyContract,
    expected_prior_pack_ref: PriorPackRef,
    expected_authorization_ref: TestOnlyPriorAuthorizationReceiptRef,
) -> tuple[ProposalHint, ...]:
    """Adapt a B-07D3/B-07G lookup whose frozen pins are exactly consistent.

    This adapter intentionally does not authorize a pack. Actual receipt
    verification remains with the existing B-07D3 provider and B-07G service.
    The caller must preserve that verified service reply and supply the frozen
    run pins; this layer checks only exact pin consistency.
    """

    if (
        type(lookup) is not PriorLookupResult
        or type(catalog) is not ParameterCatalog
        or type(candidate_assembly) is not CandidateAssemblyContract
        or type(lookup.authorization) is not FixturePriorAuthorization
        or type(lookup.prior_pack) is not PriorPack
        or type(expected_prior_pack_ref) is not PriorPackRef
        or type(expected_authorization_ref) is not TestOnlyPriorAuthorizationReceiptRef
    ):
        raise TypeError("proposal hints require an exact authorized lookup")
    pack = lookup.prior_pack
    catalog_ref = catalog.to_ref(candidate_assembly=candidate_assembly)
    if (
        pack.challenge_key != catalog.challenge_key
        or pack.channel is not PriorChannel.TEST_ONLY_FIXTURE
        or pack.publication_class is not PriorPublicationClass.TEST_ONLY
        or pack.parameter_catalog_ref != catalog_ref
        or lookup.prior_pack_ref != prior_pack_ref(pack)
        or lookup.prior_pack_ref != expected_prior_pack_ref
        or lookup.authorization.receipt_ref != expected_authorization_ref
        or expected_prior_pack_ref.challenge_key != catalog.challenge_key
        or expected_prior_pack_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE
        or expected_authorization_ref.challenge_key != catalog.challenge_key
        or lookup.index_snapshot_ref.challenge_key != catalog.challenge_key
        or lookup.index_snapshot_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE
        or pack.limitations != BE4_FIXTURE_LIMITATIONS
        or len(pack.items) != len(_FAMILIES)
    ):
        raise ValueError("lookup does not bind the closed B-E4 fixture prior")
    by_surface = {item.intervention.surface_id: item for item in pack.items}
    if set(by_surface) != set(_FAMILIES) or len(by_surface) != len(pack.items):
        raise ValueError("fixture guidance families must be exact and unique")
    catalog_entries = {entry.surface_id: entry for entry in catalog.entries}
    for surface_id in _FAMILIES:
        item = by_surface[surface_id]
        entry = catalog_entries.get(surface_id)
        binding = None if entry is None else entry.training_lever_binding
        if (
            type(item) is not PriorGuidanceItem
            or item.kind is not PriorGuidanceKind.EXPLORE
            or item.intervention.action is not PriorAction.COMPARE
            or item.intervention.baseline_ref != _LOW_VALUE_REF
            or item.intervention.from_ref is not None
            or item.intervention.to_ref != _HIGH_VALUE_REF
            or not _has_only_mixed_expected_outcomes(item)
            or type(entry) is not m.ParameterCatalogEntry
            or type(binding) is not m.BoundTrainingLever
            or binding.kind is not _FAMILY_KINDS[surface_id]
            or entry.value_type is not m.SurfaceValueType.UINT64
            or type(entry.domain) is not m.UInt64RangeDomain
            or (entry.domain.minimum, entry.domain.maximum) != (1, 2)
        ):
            raise ValueError(
                "fixture guidance is not the registered 1-to-2 intervention"
            )
    # Pack item order is the frozen, bounded proposal priority. Re-sorting back
    # to catalog order would erase the intended arm material for several fixed
    # driver policies.
    return tuple(
        ProposalHint(item.intervention.surface_id, ProposalDirection.TOGGLE)
        for item in pack.items
    )


__all__ = (
    "BE4_FIXTURE_CATALOG_ID",
    "BE4_FIXTURE_CATALOG_VERSION",
    "BE4_FIXTURE_LIMITATIONS",
    "BE4_FIXTURE_PRIOR_BUILDER_VERSION",
    "BE4_FIXTURE_PRIOR_ID",
    "BE4_FIXTURE_PRIOR_VERSION",
    "BE4_FIXTURE_TEMPLATE_BUILDER_VERSION",
    "ThreeFamilyTestOnlyPackBuilder",
    "extend_toy_parameter_catalog",
    "fixture_executable_semantics",
    "proposal_hints_from_test_only_lookup",
)
