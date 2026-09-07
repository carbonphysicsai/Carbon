"""Deterministic B-07D synthetic prior fixtures."""

from __future__ import annotations

from dataclasses import replace

from test_b02b_catalog import _fixture as catalog_fixture

from carbon import research
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    ResourceClassRef,
)


def digest(character: str = "1") -> str:
    return "sha256:" + character * 64


def prior_fixture():
    fixture = catalog_fixture()
    key = fixture["key"]
    catalog = fixture["catalog"]
    catalog_ref = catalog.to_ref(candidate_assembly=fixture["assembly"])
    estimand = research.PublicEstimandRef(key, content_digest=digest("2"))
    search_scope = research.PublicSearchScopeRef(key, content_digest=digest("3"))
    aggregate = research.PublicAggregatePublicationRef(key, content_digest=digest("4"))
    policy_ref = research.PriorPolicyBundleRef(key, content_digest=digest("5"))
    resource = ResourceClassRef(
        key,
        "fixture_resource",
        "1.0",
        "1.0",
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        digest("6"),
    )
    registry = research.PriorValidationRegistry(
        catalog,
        catalog_ref,
        policy_ref,
        (
            research.PublicEstimandDefinition(
                estimand,
                "public_baseline",
                "public_population",
                "lower_is_better",
                "median",
                "abstract_unit",
                "fixture_lineage",
                "bootstrap_interval",
            ),
        ),
        (
            research.PublicSearchScopeDefinition(
                search_scope, (estimand,), ("fixture_context",), 10
            ),
        ),
        (aggregate,),
        (
            (
                research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
                research.EpistemicType.OBSERVED,
            ),
            (
                research.EvidenceOrigin.CURATED_PUBLIC_SCIENCE,
                research.EpistemicType.OBSERVED,
            ),
        ),
    )
    scope = research.PriorScope(("basic_backbone",), ("fixture_context",), (resource,))
    evidence = research.PriorEvidence(
        research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
        research.EpistemicType.OBSERVED,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.LOW,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.LOW,
        ("fixture_selection",),
        ("synthetic_only",),
    )
    counter = research.CounterevidenceEntries(
        (
            research.CounterevidenceEntry(
                estimand,
                research.CounterevidenceFinding.NEGATIVE,
                scope,
                research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
                research.EpistemicType.OBSERVED,
                research.EvidenceBand.LOW,
                research.EvidenceBand.MEDIUM,
                research.EvidenceBand.LOW,
                ("same_fixture_scope",),
                ("not_utility_qualified",),
                ("synthetic_only",),
            ),
        )
    )
    item = research.PriorGuidanceItem(
        "fixture_guidance",
        research.PriorGuidanceKind.STEER,
        research.PriorIntervention(
            "strategy_backbone",
            research.PriorAction.ENABLE,
            "basic_backbone",
            None,
            None,
        ),
        scope,
        (
            research.PriorExpectedOutcome(
                estimand, research.OutcomeDirection.IMPROVE, "medium_effect"
            ),
        ),
        evidence,
        counter,
        research.PriorFalsification((), ()),
        research.PriorProvenance((aggregate,)),
    )
    base = research.PriorPack(
        research.RESEARCH_SCHEMA_VERSION,
        research.RESEARCH_CANONICALIZATION_PROFILE,
        key,
        "fixture_prior",
        "1.0",
        research.PriorChannel.TEST_ONLY_FIXTURE,
        0,
        research.PriorPublicationClass.TEST_ONLY,
        10,
        11,
        12,
        research.InteractionManifestRef(key, content_digest=digest("7")),
        catalog_ref,
        policy_ref,
        "fixture_builder_v1",
        None,
        (item,),
        research.DisclosurePolicyRef(key, content_digest=digest("8")),
        ("TEST_ONLY", "NOT_UTILITY_QUALIFIED"),
    )
    return fixture, registry, base


class FixtureBuilder:
    def __init__(self, base):
        self._base = base

    def build(self, snapshot, *, publication_sequence, activation_epoch):
        predecessor = None
        if publication_sequence:
            predecessor = research.PriorPackRef(
                self._base.challenge_key,
                self._base.channel,
                publication_sequence - 1,
                digest("9"),
            )
        return replace(
            self._base,
            publication_sequence=publication_sequence,
            activation_epoch=activation_epoch,
            publication_epoch=activation_epoch - 1,
            predecessor_pack_ref=predecessor,
        )


def synthetic_snapshot(key):
    return research.SyntheticEvidenceSnapshot(
        key,
        "fixture_snapshot",
        (
            research.SyntheticPriorRecord(
                "private_record_a",
                key,
                "strategy_backbone",
                research.PublicEstimandRef(key, content_digest=digest("2")),
                "private_lineage_a",
                "private_cell",
                10,
                research.SyntheticFinding.SUPPORT,
                1.0,
                True,
                True,
                private_canary="secret_canary_a",
                public_provenance_ref=research.PublicAggregatePublicationRef(
                    key, content_digest=digest("4")
                ),
            ),
            research.SyntheticPriorRecord(
                "private_record_b",
                key,
                "strategy_backbone",
                research.PublicEstimandRef(key, content_digest=digest("2")),
                "private_lineage_b",
                "private_cell",
                10,
                research.SyntheticFinding.NEGATIVE,
                -1.0,
                True,
                True,
                private_canary="secret_canary_b",
                public_provenance_ref=research.PublicAggregatePublicationRef(
                    key, content_digest=digest("4")
                ),
            ),
        ),
    )


def public_pack(pack):
    item = pack.items[0]
    public_evidence = replace(
        item.evidence,
        evidence_origin=research.EvidenceOrigin.CURATED_PUBLIC_SCIENCE,
    )
    counter = item.counterevidence_and_applicability
    public_counter = research.CounterevidenceEntries(
        tuple(
            replace(
                entry,
                evidence_origin=research.EvidenceOrigin.CURATED_PUBLIC_SCIENCE,
            )
            for entry in counter.entries
        )
    )
    return replace(
        pack,
        channel=research.PriorChannel.PUBLIC,
        publication_class=research.PriorPublicationClass.BOOTSTRAP_PUBLIC,
        items=(
            replace(
                item,
                evidence=public_evidence,
                counterevidence_and_applicability=public_counter,
            ),
        ),
        limitations=("BOOTSTRAP_PUBLIC",),
    )
