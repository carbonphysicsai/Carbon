"""Deterministic public-safe B-07A discovery fixtures."""

from __future__ import annotations

from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    TrainingSupportContractRef,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
)
from carbon.measurement.refs import (
    MEASUREMENT_CANONICALIZATION_PROFILE,
    MeasurementContractRef,
)
from carbon.registry import ChallengeKey
from carbon.research import (
    PROTOCOL_LIMITS,
    RESEARCH_SCHEMA_VERSION,
    SUPPORTED_OPERATIONS,
    ChallengeInfo,
    CompilerEnvironmentRef,
    CompilerIdentity,
    DisclosureClass,
    DisclosurePolicyRef,
    InteractionManifest,
    NoPriorAvailability,
    PublicScorePolicyRef,
    StrategySchemaRef,
)
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    ResearchResourcePolicyRef,
)


def digest(character: str = "1") -> str:
    return "sha256:" + character * 64


def discovery_resources(
    version: str = "1.0",
    *,
    challenge_id: str = "b07a_fixture",
) -> tuple[ChallengeInfo, InteractionManifest]:
    key = ChallengeKey(challenge_id, version)
    authored = {
        "challenge_key": key,
        "object_id": "fixture_object",
        "object_version": version,
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "content_digest": digest("1"),
    }
    physical = PhysicalSystemSpecRef(**authored)
    candidate = CandidateOutputContractRef(**authored)
    distribution = InstanceDistributionContractRef(
        **authored,
        expected_population_role="TARGET_WORKLOAD_P",
    )
    sampling = SamplingPlanRef(**authored)
    training = TrainingSupportContractRef(**authored)
    measurement = MeasurementContractRef(
        key,
        digest("2"),
        "1.0",
        MEASUREMENT_CANONICALIZATION_PROFILE,
    )
    score = PublicScorePolicyRef(key, content_digest=digest("3"))
    info = ChallengeInfo(
        RESEARCH_SCHEMA_VERSION,
        key,
        version,
        physical,
        candidate,
        distribution,
        sampling,
        training,
        measurement,
        score,
        DisclosureClass.PUBLIC_RESEARCH,
    )
    assembly = CandidateAssemblyContractRef(
        key,
        "fixture_assembly",
        version,
        "1.0",
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        digest("4"),
    )
    catalog = ParameterCatalogRef(
        key,
        "fixture_catalog",
        version,
        "1.0",
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        digest("5"),
    )
    resource_policy = ResearchResourcePolicyRef(
        key,
        "fixture_resource_policy",
        version,
        "1.0",
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        digest("6"),
    )
    compiler = CompilerIdentity(
        "fixture_compiler",
        version,
        digest("7"),
        CompilerEnvironmentRef(key, content_digest=digest("8")),
    )
    manifest = InteractionManifest(
        RESEARCH_SCHEMA_VERSION,
        key,
        info.to_ref(),
        physical,
        candidate,
        distribution,
        sampling,
        training,
        measurement,
        score,
        assembly,
        StrategySchemaRef(key, content_digest=digest("9")),
        catalog,
        compiler,
        (),
        None,
        (),
        None,
        NoPriorAvailability(),
        resource_policy,
        DisclosurePolicyRef(key, content_digest=digest("a")),
        SUPPORTED_OPERATIONS,
        PROTOCOL_LIMITS,
        (),
    )
    return info, manifest


def strategy(*, parameters: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "challenge_id": "b07a_fixture",
        "backbone": "fno",
        "parameters": {} if parameters is None else parameters,
    }
