"""Reuse B-02C/B-07E static inspection; runtime admission stays in C-03/ledger.

B-02C currently types metadata as non-production fixture authority. This class
does not label actual resource observations or JAX results as synthetic. Its
static/forecast output is not execution evidence or a runtime guarantee.
"""

from carbon import resource_policy as rp
from carbon.construction import StaticResourceDimension
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.research import (
    StaticResourceInspectionProvider,
    UncalibratedResourceForecastProvider,
)

from .profile import CHALLENGE
from .research_authoring import clause


def resources(contracts, compiler, *, gpu=False):
    unit = clause("unit", "cpu_seconds")
    provenance = rp.FixtureResourceProvenance(
        clause("fixture_registration", "development_static_metadata_not_observation"),
        (clause("provenance", "owner_development_resource_envelope"),),
        rp.ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION,
    )
    context = rp.FixturePracticeResourceContext(
        CHALLENGE,
        "autoresearch_static_metadata",
        provenance.fixture_registration_ref,
        clause("internal_service_scope", "public_development_research"),
        rp.ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )
    resource = rp.ResourceClass(
        "resource_class",
        rp.RESOURCE_POLICY_SCHEMA_VERSION,
        rp.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        CHALLENGE,
        "autoresearch_linux_gpu_diagnostic" if gpu else "autoresearch_linux_cpu",
        "1.0",
        contracts.assembly.environment_pins[0],
        contracts.assembly.environment_pins,
        (StaticResourceDimension("cpu_seconds", unit),),
        tuple(
            rp.ResourceObservationMetric(name, unit, role)
            for name, role in (
                ("cpu_consumption", rp.ResourceObservationRole.RESOURCE_CONSUMPTION),
                ("observed_latency", rp.ResourceObservationRole.OBSERVED_LATENCY),
                (
                    "cpu_cost_not_price",
                    rp.ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
                ),
            )
        ),
        provenance,
        rp.ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION,
    )
    ref = rp.resource_class_to_ref(resource)
    readiness = rp.OperationalReadinessRequirements(
        *(rp.OperationalRequirementRequired() for _ in range(4))
    )
    binding = rp.ResourceClassPolicyBinding(
        ref,
        (rp.DeclaredResourceCeiling("cpu_seconds", unit, 1200),),
        (),
        (
            rp.RuntimeResourceLimit(
                "declared_cpu_ceiling",
                "cpu_consumption",
                unit,
                1200,
                rp.EnforcementPoint.PRE_ALLOCATION_READINESS,
                rp.EnforcementMode.PREVENT_START_ON_EXCESS,
            ),
        ),
        readiness,
    )
    policy = rp.ResearchResourcePolicy(
        "research_resource_policy",
        rp.RESOURCE_POLICY_SCHEMA_VERSION,
        rp.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        CHALLENGE,
        "autoresearch_gpu_static_policy" if gpu else "autoresearch_static_policy",
        "1.0",
        contracts.assembly.to_ref(),
        contracts.catalog.to_ref(candidate_assembly=contracts.assembly),
        SUPPORTED_COMPILER_IDENTITY,
        context,
        (binding,),
        clause("policy_authority", "owner_bounded_nonproduction_metadata"),
        provenance,
        rp.UnknownOrInvalidPolicy.REJECT,
        rp.ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION,
    )
    bundle = ((resource, ref),)
    policy_ref = rp.research_resource_policy_to_ref(policy, class_bundle=bundle)
    inspection = StaticResourceInspectionProvider(
        compilation_resolver=compiler,
        expected_training_support_ref=contracts.assembly.training_support_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=bundle,
        selected_resource_class=resource,
        selected_resource_class_ref=ref,
        authority_context=context,
    )
    return (
        inspection,
        UncalibratedResourceForecastProvider(inspection),
        policy,
        resource,
    )
