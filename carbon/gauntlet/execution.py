"""Immutable B-E4 preflight plans and descriptive design calibration.

Nothing in this module runs B-07C practice, selects a practice-best Strategy,
records attack evidence, or creates qualifying execution evidence.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from carbon.construction import CandidateAssemblyContract, ParameterCatalog
from carbon.mcp import (
    McpCall,
    McpField,
    McpIntegrationError,
    SubmissionResult,
    SubmitReceipt,
)
from carbon.prior_compat import PrivatePriorProjection, project_v2_to_v1_private
from carbon.research import (
    RESEARCH_NAMESPACE,
    CanonicalWireError,
    ChallengeInfo,
    CompileStrategyRequest,
    CompileStrategyResult,
    DryValidateRequest,
    DryValidationResult,
    ExactPriorSelector,
    FixturePriorAuthorization,
    GetChallengeInfoRequest,
    GetInteractionManifestRequest,
    GetMockScaffoldRequest,
    GetPriorRequest,
    InspectResourcesRequest,
    InspectResourcesResult,
    InteractionManifest,
    MockScaffold,
    MockScaffoldRef,
    PracticePackRef,
    PriorChannel,
    PriorLookupResult,
    PriorPack,
    ReplyStatus,
    ResearchServiceError,
    ResearchServiceErrorCode,
    ResourceObservation,
    ServiceCall,
    ServiceReply,
    canonical_bytes,
    canonical_digest,
    load_canonical,
    prior_pack_ref,
)
from carbon.research.refs import PriorPackRef, TestOnlyPriorAuthorizationReceiptRef

from .agents import (
    REGISTERED_EFFECTFUL_SURFACES,
    CommonArmRng,
    DataOnlyStrategyProposal,
    DriverProposalBatch,
    DriverSelection,
    FixtureAgentDriver,
    FixtureDriverRef,
    FixtureStrategyDomain,
    ProposalDirection,
    ProposalHint,
    bind_data_only_proposal_batch,
    fixture_driver_ref,
    fixture_strategy_domain,
)
from .fixture import proposal_hints_from_test_only_lookup
from .harness import AgentSession
from .meter import (
    NormalizedComputeReceipt,
    PolicyWorkCount,
    PolicyWorkKind,
    PolicyWorkMeter,
    WallTimeObservation,
)
from .model import AgentProfile, ExperimentalArm, MatchedBudget, RunIdentity

EXECUTION_PLAN_SCHEMA_VERSION = "2.0"
PREFLIGHT_AUTHORITY_CEILING = (
    "DESIGN_ANALYSIS_PREFLIGHT_ONLY_NO_PRACTICE_OR_QUALIFICATION_AUTHORITY"
)
OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING = (
    "DESIGN_ANALYSIS_TEST_ONLY_OFFICIAL_FIXTURE_SUBMISSION_NO_QUALIFICATION_AUTHORITY"
)
CALIBRATION_AUTHORITY_CEILING = "DESIGN_ANALYSIS_ONLY_NOT_EXECUTION_EVIDENCE"
CALIBRATION_BLOCK_INFRASTRUCTURE_FAILURE_RATE_CEILING = 0.05
PROPOSED_PRIMARY_BLOCKS_PER_PROFILE = 636
PROPOSED_RESERVE_BLOCKS_PER_PROFILE = 52
REGISTERED_RNG_ROLES = (
    "candidate_order",
    "evolutionary_mutation_direction",
    "evolutionary_surface_order",
    "final_candidate_tie_break",
)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_PLAN_DOMAIN = b"carbon.be4.nonqualifying-run-plan.v2\x00"
_DRIVER_SERVICE_TRANSCRIPT_DOMAIN = b"carbon.be4.driver-service-transcript.v1\x00"
_ARM_ARTIFACT_DOMAIN = b"carbon.be4.frozen-arm-artifact.v2\x00"
_OFFICIAL_SUBMISSION_ASSOCIATION_DOMAIN = (
    b"carbon.be4.official-fixture-submission-association.v1\x00"
)
_PREPARED_CANDIDATE_FACTORY_TOKEN = object()
_PREPARED_PREFLIGHT_FACTORY_TOKEN = object()
_OFFICIAL_FIXTURE_SUBMISSION_FACTORY_TOKEN = object()
GENERIC_WORKFLOW_STEPS = (
    "DISCOVER_REGISTERED_SURFACE",
    "FORM_ONE_LEVER_HYPOTHESIS",
    "RUN_PAIRED_PRACTICE",
    "RETAIN_NULL_OR_NEGATIVE_FEEDBACK",
    "SELECT_FROM_ALLOWED_PRACTICE_EVIDENCE",
)
FIXTURE_RESOURCE_DIMENSION_ID = "abstract_units"
FIXTURE_RESOURCE_UNIT = "fixture_units"
FIXTURE_RESOURCE_INSPECTION_UNIT = (
    f"{FIXTURE_RESOURCE_DIMENSION_ID}:fixture_abstract_count"
)


class FixtureResourceBudgetExceeded(ValueError):
    """A statically known fixture operation cannot fit the bound run ceiling."""

    def __init__(self, quantity: float, ceiling: int) -> None:
        if (
            type(quantity) is not float
            or not math.isfinite(quantity)
            or quantity < 0.0
            or type(ceiling) is not int
            or ceiling < 1
        ):
            raise TypeError("fixture exhaustion requires exact bounded values")
        self.quantity = quantity
        self.ceiling = ceiling
        super().__init__("fixture resource plan ceiling would be exceeded")


def _digest(value: object, name: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise TypeError(f"{name} must be an exact tagged SHA-256 digest")
    return value


def _identifier(value: object, name: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise TypeError(f"{name} must be a bounded identifier")
    return value


def _canonical_prior_pack_ref(value: object) -> PriorPackRef:
    if type(value) is not PriorPackRef:
        raise TypeError("prior pack identity requires an exact PriorPackRef")
    try:
        return PriorPackRef(
            value.challenge_key,
            value.channel,
            value.publication_sequence,
            value.content_hash,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("prior pack identity is structurally invalid") from exc


def _prior_pack_fields(value: object) -> tuple[str, ...]:
    ref = _canonical_prior_pack_ref(value)
    return (
        ref.challenge_key.challenge_id,
        ref.challenge_key.version,
        ref.channel.value,
        str(ref.publication_sequence),
        ref.content_hash,
    )


def _canonical_authorization_ref(
    value: object,
) -> TestOnlyPriorAuthorizationReceiptRef:
    if type(value) is not TestOnlyPriorAuthorizationReceiptRef:
        raise TypeError(
            "authorization identity requires an exact authorization receipt ref"
        )
    try:
        return TestOnlyPriorAuthorizationReceiptRef(
            value.challenge_key,
            value.authorization_id,
            value.content_digest,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("authorization identity is structurally invalid") from exc


def _authorization_fields(value: object) -> tuple[str, ...]:
    ref = _canonical_authorization_ref(value)
    return (
        ref.challenge_key.challenge_id,
        ref.challenge_key.version,
        ref.authorization_id,
        ref.content_digest,
    )


def _canonical_simple_ref(
    value: object, expected_type: type[MockScaffoldRef | PracticePackRef]
) -> MockScaffoldRef | PracticePackRef:
    if type(value) is not expected_type:
        raise TypeError("plan reference does not use its exact nominal type")
    try:
        return expected_type(
            value.challenge_key,
            value.schema_version,
            value.canonicalization_profile,
            value.content_digest,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("plan reference is structurally invalid") from exc


def _simple_ref_fields(
    value: object, expected_type: type[MockScaffoldRef | PracticePackRef]
) -> tuple[str, ...]:
    ref = _canonical_simple_ref(value, expected_type)
    return (
        ref.challenge_key.challenge_id,
        ref.challenge_key.version,
        ref.schema_version,
        ref.canonicalization_profile,
        ref.content_digest,
    )


def _canonical_driver_ref(value: object) -> FixtureDriverRef:
    if type(value) is not FixtureDriverRef:
        raise TypeError("driver identity requires an exact FixtureDriverRef")
    try:
        return FixtureDriverRef(
            value.profile,
            value.driver_id,
            value.driver_version,
            value.runtime_id,
            value.runtime_version,
            value.runtime_digest,
            value.policy_digest,
            value.corpus_digest,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("driver identity is structurally invalid") from exc


def _driver_ref_fields(value: object) -> tuple[str, ...]:
    ref = _canonical_driver_ref(value)
    return (
        ref.profile.value,
        ref.driver_id,
        ref.driver_version,
        ref.runtime_id,
        ref.runtime_version,
        ref.runtime_digest,
        ref.policy_digest,
        ref.corpus_digest or "NO_CORPUS",
    )


def _canonical_budget(value: object) -> MatchedBudget:
    if type(value) is not MatchedBudget:
        raise TypeError("run budget requires an exact MatchedBudget")
    try:
        return MatchedBudget(
            value.profile,
            value.wall_time_seconds,
            value.compute_units,
            value.attempt_limit,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("run budget is structurally invalid") from exc


def _preflight_slot_digest(
    *,
    design_digest: str,
    block_id: str,
    profile: AgentProfile,
    arm: ExperimentalArm,
    replicate: int,
    artifact_id: str,
    artifact_version: str,
    artifact_digest: str,
    driver_ref: FixtureDriverRef,
    budget: MatchedBudget,
    fixture_resource_ceiling: int,
    scaffold_ref: MockScaffoldRef,
    practice_pack_ref: PracticePackRef,
    prior_pack_ref: PriorPackRef | None,
    authorization_ref: TestOnlyPriorAuthorizationReceiptRef | None,
) -> str:
    prior_fields = (
        ("NO_PRIOR_PACK",)
        if prior_pack_ref is None
        else ("PRIOR_PACK", *_prior_pack_fields(prior_pack_ref))
    )
    authorization_fields = (
        ("NO_AUTHORIZATION_REF",)
        if authorization_ref is None
        else ("AUTHORIZATION_REF", *_authorization_fields(authorization_ref))
    )
    fields = (
        design_digest,
        block_id,
        profile.value,
        str(replicate),
        arm.value,
        artifact_id,
        artifact_version,
        artifact_digest,
        *_driver_ref_fields(driver_ref),
        budget.wall_time_seconds.hex(),
        budget.compute_units.hex(),
        str(budget.attempt_limit),
        str(fixture_resource_ceiling),
        *_simple_ref_fields(scaffold_ref, MockScaffoldRef),
        *_simple_ref_fields(practice_pack_ref, PracticePackRef),
        *prior_fields,
        *authorization_fields,
    )
    payload = b"\x00".join(item.encode("ascii") for item in fields)
    return "sha256:" + hashlib.sha256(_PLAN_DOMAIN + payload).hexdigest()


def arm_hint_artifact_digest(
    *,
    arm: ExperimentalArm,
    artifact_id: str,
    artifact_version: str,
    proposal_hints: tuple[ProposalHint, ...],
    source_prior_pack_ref: PriorPackRef | None = None,
) -> str:
    """Bind inert non-v2 proposal hints to one frozen arm artifact."""

    if (
        type(arm) is not ExperimentalArm
        or arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
        or type(proposal_hints) is not tuple
        or any(type(item) is not ProposalHint for item in proposal_hints)
        or len({item.surface_id for item in proposal_hints}) != len(proposal_hints)
        or type(source_prior_pack_ref) not in (type(None), PriorPackRef)
    ):
        raise TypeError("non-v2 arm hints require exact bounded values")
    _identifier(artifact_id, "artifact_id")
    _identifier(artifact_version, "artifact_version")
    try:
        checked_hints = tuple(
            ProposalHint(item.surface_id, item.direction, item.replacement_token)
            for item in proposal_hints
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("proposal hint identity is structurally invalid") from exc
    source_fields = (
        ("NO_SOURCE_PRIOR",)
        if source_prior_pack_ref is None
        else ("SOURCE_PRIOR", *_prior_pack_fields(source_prior_pack_ref))
    )
    hint_fields = tuple(
        field
        for item in checked_hints
        for field in (
            "HINT",
            item.surface_id,
            item.direction.value,
            item.replacement_token or "NO_REPLACEMENT",
        )
    )
    payload = b"\x00".join(
        item.encode("ascii")
        for item in (
            arm.value,
            artifact_id,
            artifact_version,
            *source_fields,
            str(len(checked_hints)),
            *hint_fields,
        )
    )
    return "sha256:" + hashlib.sha256(_ARM_ARTIFACT_DOMAIN + payload).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenArmArtifact:
    """One content-addressed arm material; it grants no prior authorization."""

    arm: ExperimentalArm
    artifact_id: str
    artifact_version: str
    content_digest: str
    source_prior_pack_ref: PriorPackRef | None = None
    proposal_hints: tuple[ProposalHint, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self) is not FrozenArmArtifact
            or type(self.arm) is not ExperimentalArm
            or type(self.source_prior_pack_ref) not in (type(None), PriorPackRef)
            or type(self.proposal_hints) is not tuple
            or any(type(item) is not ProposalHint for item in self.proposal_hints)
            or len({item.surface_id for item in self.proposal_hints})
            != len(self.proposal_hints)
        ):
            raise TypeError("arm artifact requires exact nominal values")
        try:
            checked_source = (
                None
                if self.source_prior_pack_ref is None
                else _canonical_prior_pack_ref(self.source_prior_pack_ref)
            )
            checked_hints = tuple(
                ProposalHint(item.surface_id, item.direction, item.replacement_token)
                for item in self.proposal_hints
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("arm artifact has invalid nested values") from exc
        object.__setattr__(self, "source_prior_pack_ref", checked_source)
        object.__setattr__(self, "proposal_hints", checked_hints)
        _identifier(self.artifact_id, "artifact_id")
        _identifier(self.artifact_version, "artifact_version")
        _digest(self.content_digest, "content_digest")
        if self.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
            if (
                type(self.source_prior_pack_ref) is not PriorPackRef
                or self.content_digest != self.source_prior_pack_ref.content_hash
                or self.proposal_hints
            ):
                raise ValueError("v2 arm artifact must be the exact pinned prior pack")
        elif self.arm is ExperimentalArm.V1_DIRECTIVE_PRIOR:
            if type(self.source_prior_pack_ref) is not PriorPackRef:
                raise ValueError("v1 projection must retain its exact v2 source pack")
        elif self.source_prior_pack_ref is not None:
            raise ValueError("non-prior arm material cannot claim a source prior")
        if self.arm is ExperimentalArm.NO_PRIOR and self.proposal_hints:
            raise ValueError("the no-prior arm cannot contain proposal guidance")
        if self.arm is not ExperimentalArm.V2_TEST_ONLY_PRIOR and (
            self.content_digest
            != arm_hint_artifact_digest(
                arm=self.arm,
                artifact_id=self.artifact_id,
                artifact_version=self.artifact_version,
                proposal_hints=self.proposal_hints,
                source_prior_pack_ref=self.source_prior_pack_ref,
            )
        ):
            raise ValueError("non-v2 artifact digest does not bind its proposal hints")


def build_nonqualifying_preflight_arm_artifacts(
    v2_prior_pack_ref: PriorPackRef,
) -> tuple[FrozenArmArtifact, ...]:
    """Construct exact surrogate material for non-qualifying preflight only.

    The generic and v1 hints exercise fixed fixture plumbing; they are not the
    proposed domain-neutral generic workflow or an authoritative v1 private-
    prior projection. The v1 provenance and v2 material retain the exact
    TEST_ONLY pack. This verifies no authorization and grants no execution
    authority.
    """

    if type(v2_prior_pack_ref) is not PriorPackRef:
        raise TypeError("fixture arm artifacts require an exact PriorPackRef")
    try:
        pinned_pack_ref = PriorPackRef(
            v2_prior_pack_ref.challenge_key,
            v2_prior_pack_ref.channel,
            v2_prior_pack_ref.publication_sequence,
            v2_prior_pack_ref.content_hash,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("fixture arm prior pack is structurally invalid") from exc
    if pinned_pack_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE:
        raise ValueError(
            "fixture arm artifacts require an exact TEST_ONLY_FIXTURE PriorPackRef"
        )
    specifications = (
        (ExperimentalArm.NO_PRIOR, "no_prior", (), None),
        (
            ExperimentalArm.GENERIC_PRIOR,
            "generic_prior",
            (ProposalHint("fixture_sampling_level", ProposalDirection.INCREASE),),
            None,
        ),
        (
            ExperimentalArm.V1_DIRECTIVE_PRIOR,
            "v1_projection",
            (ProposalHint("fixture_curriculum_emphasis", ProposalDirection.INCREASE),),
            pinned_pack_ref,
        ),
    )
    artifacts = tuple(
        FrozenArmArtifact(
            arm=arm,
            artifact_id=artifact_id,
            artifact_version="1.0",
            content_digest=arm_hint_artifact_digest(
                arm=arm,
                artifact_id=artifact_id,
                artifact_version="1.0",
                proposal_hints=hints,
                source_prior_pack_ref=source,
            ),
            source_prior_pack_ref=source,
            proposal_hints=hints,
        )
        for arm, artifact_id, hints, source in specifications
    )
    return artifacts + (
        FrozenArmArtifact(
            arm=ExperimentalArm.V2_TEST_ONLY_PRIOR,
            artifact_id="v2_test_only_prior",
            artifact_version="2.0",
            content_digest=pinned_pack_ref.content_hash,
            source_prior_pack_ref=pinned_pack_ref,
        ),
    )


def build_nonqualifying_lifecycle_arm_artifacts(
    v2_prior_pack: PriorPack,
) -> tuple[tuple[FrozenArmArtifact, ...], PrivatePriorProjection]:
    """Materialize final four-arm treatment data for non-qualifying rehearsal.

    The generic arm is an exact domain-neutral workflow with no surface or
    direction.  The v1 arm is the existing private offline projection of the
    exact v2 pack.  This helper supplies neither prior authorization nor
    qualifying execution authority.
    """

    if type(v2_prior_pack) is not PriorPack:
        raise TypeError("lifecycle treatments require an exact PriorPack")
    pinned_ref = prior_pack_ref(v2_prior_pack)
    if pinned_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE:
        raise ValueError("lifecycle treatments require an exact TEST_ONLY pack")
    projection = project_v2_to_v1_private(v2_prior_pack)
    if (
        type(projection) is not PrivatePriorProjection
        or projection.receipt.source_prior_pack_ref != pinned_ref
    ):
        raise ValueError("v1 projection does not bind the exact v2 source pack")
    v1_hints: list[ProposalHint] = []
    for directive in projection.published_prior.directives:
        target = directive.subject
        if target not in REGISTERED_EFFECTFUL_SURFACES:
            raise ValueError("v1 projection targets an unregistered fixture family")
        v1_hints.append(ProposalHint(target, ProposalDirection.TOGGLE))
    if len(v1_hints) != len({item.surface_id for item in v1_hints}):
        raise ValueError("v1 projection contains duplicate fixture families")

    generic_id = "generic_domain_neutral_research_workflow"
    generic_version = "1.0"
    # The workflow has deliberately no proposal hints.  Its exact ordered
    # steps are bound into the artifact identity without becoming direction.
    generic_digest = (
        "sha256:"
        + hashlib.sha256(
            _ARM_ARTIFACT_DOMAIN
            + b"\x00".join(
                item.encode("ascii")
                for item in (
                    ExperimentalArm.GENERIC_PRIOR.value,
                    generic_id,
                    generic_version,
                    *GENERIC_WORKFLOW_STEPS,
                )
            )
        ).hexdigest()
    )
    no_prior = FrozenArmArtifact(
        ExperimentalArm.NO_PRIOR,
        "no_prior",
        "2.0",
        arm_hint_artifact_digest(
            arm=ExperimentalArm.NO_PRIOR,
            artifact_id="no_prior",
            artifact_version="2.0",
            proposal_hints=(),
        ),
    )
    # FrozenArmArtifact normally derives non-v2 identity from proposal hints.
    # The generic workflow is represented by a separate exact content digest,
    # so construct the nominal carrier and then retain the workflow digest in
    # the artifact id.  This keeps the proposal-hint surface empty.
    generic_artifact_id = f"{generic_id}:{generic_digest[7:23]}"
    generic = FrozenArmArtifact(
        ExperimentalArm.GENERIC_PRIOR,
        generic_artifact_id,
        generic_version,
        arm_hint_artifact_digest(
            arm=ExperimentalArm.GENERIC_PRIOR,
            artifact_id=generic_artifact_id,
            artifact_version=generic_version,
            proposal_hints=(),
        ),
    )
    v1_id = f"v1_private_projection:{projection.receipt.output_hash[7:23]}"
    v1 = FrozenArmArtifact(
        ExperimentalArm.V1_DIRECTIVE_PRIOR,
        v1_id,
        projection.receipt.mapping_version,
        arm_hint_artifact_digest(
            arm=ExperimentalArm.V1_DIRECTIVE_PRIOR,
            artifact_id=v1_id,
            artifact_version=projection.receipt.mapping_version,
            proposal_hints=tuple(v1_hints),
            source_prior_pack_ref=pinned_ref,
        ),
        pinned_ref,
        tuple(v1_hints),
    )
    v2 = FrozenArmArtifact(
        ExperimentalArm.V2_TEST_ONLY_PRIOR,
        "v2_test_only_prior",
        "3.0",
        pinned_ref.content_hash,
        pinned_ref,
    )
    return (no_prior, generic, v1, v2), projection


@dataclass(frozen=True, slots=True)
class NonQualifyingRunPlan:
    """A discovery/compile/resource-inspection plan, not an execution plan."""

    schema_version: str
    authority_ceiling: str
    design_digest: str
    block_id: str
    identity: RunIdentity
    driver_ref: FixtureDriverRef
    arm_artifact: FrozenArmArtifact
    budget: MatchedBudget
    rng_stream_digest: str
    rng_roles: tuple[str, ...]
    fixture_resource_ceiling: int
    scaffold_ref: MockScaffoldRef
    practice_pack_ref: PracticePackRef
    final_submission_slot_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not NonQualifyingRunPlan
            or self.schema_version != EXECUTION_PLAN_SCHEMA_VERSION
            or self.authority_ceiling != PREFLIGHT_AUTHORITY_CEILING
            or type(self.identity) is not RunIdentity
            or type(self.driver_ref) is not FixtureDriverRef
            or type(self.arm_artifact) is not FrozenArmArtifact
            or type(self.budget) is not MatchedBudget
            or type(self.rng_roles) is not tuple
            or self.rng_roles != REGISTERED_RNG_ROLES
            or type(self.fixture_resource_ceiling) is not int
            or self.fixture_resource_ceiling < 1
            or type(self.scaffold_ref) is not MockScaffoldRef
            or type(self.practice_pack_ref) is not PracticePackRef
        ):
            raise TypeError("non-qualifying run plan is invalid")
        try:
            checked_identity = RunIdentity(
                self.identity.profile,
                self.identity.arm,
                self.identity.replicate,
                self.identity.prior_pack_ref,
                self.identity.test_only_authorization_ref,
            )
            checked_driver = _canonical_driver_ref(self.driver_ref)
            checked_artifact = FrozenArmArtifact(
                self.arm_artifact.arm,
                self.arm_artifact.artifact_id,
                self.arm_artifact.artifact_version,
                self.arm_artifact.content_digest,
                self.arm_artifact.source_prior_pack_ref,
                self.arm_artifact.proposal_hints,
            )
            checked_budget = _canonical_budget(self.budget)
            checked_scaffold = _canonical_simple_ref(self.scaffold_ref, MockScaffoldRef)
            checked_practice = _canonical_simple_ref(
                self.practice_pack_ref, PracticePackRef
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("run plan contains invalid nested values") from exc
        object.__setattr__(self, "identity", checked_identity)
        object.__setattr__(self, "driver_ref", checked_driver)
        object.__setattr__(self, "arm_artifact", checked_artifact)
        object.__setattr__(self, "budget", checked_budget)
        object.__setattr__(self, "scaffold_ref", checked_scaffold)
        object.__setattr__(self, "practice_pack_ref", checked_practice)
        _digest(self.design_digest, "design_digest")
        _identifier(self.block_id, "block_id")
        _digest(self.rng_stream_digest, "rng_stream_digest")
        _digest(self.final_submission_slot_digest, "final_submission_slot_digest")
        challenge = self.scaffold_ref.challenge_key
        expected_rng = CommonArmRng(
            self.design_digest,
            self.identity.profile,
            self.block_id,
            self.identity.replicate,
        ).stream_digest
        expected_slot = _preflight_slot_digest(
            design_digest=self.design_digest,
            block_id=self.block_id,
            profile=self.identity.profile,
            arm=self.identity.arm,
            replicate=self.identity.replicate,
            artifact_id=self.arm_artifact.artifact_id,
            artifact_version=self.arm_artifact.artifact_version,
            artifact_digest=self.arm_artifact.content_digest,
            driver_ref=self.driver_ref,
            budget=self.budget,
            fixture_resource_ceiling=self.fixture_resource_ceiling,
            scaffold_ref=self.scaffold_ref,
            practice_pack_ref=self.practice_pack_ref,
            prior_pack_ref=self.identity.prior_pack_ref,
            authorization_ref=self.identity.test_only_authorization_ref,
        )
        if (
            self.identity.profile is not self.driver_ref.profile
            or self.driver_ref != fixture_driver_ref(self.identity.profile)
            or self.identity.profile is not self.budget.profile
            or self.identity.arm is not self.arm_artifact.arm
            or self.budget.attempt_limit > 8
            or self.rng_stream_digest != expected_rng
            or self.final_submission_slot_digest != expected_slot
            or self.practice_pack_ref.challenge_key != challenge
            or (
                self.identity.prior_pack_ref is not None
                and self.identity.prior_pack_ref.challenge_key != challenge
            )
            or (
                self.arm_artifact.source_prior_pack_ref is not None
                and self.arm_artifact.source_prior_pack_ref.challenge_key != challenge
            )
        ):
            raise ValueError("run plan bindings do not agree")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    @property
    def preflight_only(self) -> bool:
        return True


def _canonical_run_plan(value: object) -> NonQualifyingRunPlan:
    if type(value) is not NonQualifyingRunPlan:
        raise TypeError("preflight requires an exact NonQualifyingRunPlan")
    try:
        return NonQualifyingRunPlan(
            value.schema_version,
            value.authority_ceiling,
            value.design_digest,
            value.block_id,
            value.identity,
            value.driver_ref,
            value.arm_artifact,
            value.budget,
            value.rng_stream_digest,
            value.rng_roles,
            value.fixture_resource_ceiling,
            value.scaffold_ref,
            value.practice_pack_ref,
            value.final_submission_slot_digest,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("preflight run plan is structurally invalid") from exc


@dataclass(frozen=True, slots=True)
class FourArmBlockPlan:
    profile: AgentProfile
    replicate: int
    block_id: str
    runs: tuple[NonQualifyingRunPlan, ...]

    def __post_init__(self) -> None:
        if (
            type(self) is not FourArmBlockPlan
            or type(self.profile) is not AgentProfile
            or type(self.replicate) is not int
            or self.replicate < 0
            or type(self.runs) is not tuple
            or len(self.runs) != len(ExperimentalArm)
            or any(type(item) is not NonQualifyingRunPlan for item in self.runs)
        ):
            raise TypeError("four-arm block requires exact run plans")
        _identifier(self.block_id, "block_id")
        if tuple(item.identity.arm for item in self.runs) != tuple(ExperimentalArm):
            raise ValueError("four-arm block must use canonical exact arm order")
        first = self.runs[0]
        common = (
            first.design_digest,
            first.driver_ref,
            first.budget,
            first.rng_stream_digest,
            first.rng_roles,
            first.fixture_resource_ceiling,
            first.scaffold_ref,
            first.practice_pack_ref,
        )
        if any(
            item.identity.profile is not self.profile
            or item.identity.replicate != self.replicate
            or item.block_id != self.block_id
            or (
                item.design_digest,
                item.driver_ref,
                item.budget,
                item.rng_stream_digest,
                item.rng_roles,
                item.fixture_resource_ceiling,
                item.scaffold_ref,
                item.practice_pack_ref,
            )
            != common
            for item in self.runs
        ):
            raise ValueError("arm material must be the only within-block difference")
        if len({item.arm_artifact.content_digest for item in self.runs}) != len(
            ExperimentalArm
        ):
            raise ValueError("every arm material must have a distinct frozen identity")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProposedBlockSchedule:
    """The v3 proposal's prospective blocks; it is not an approved matrix."""

    primary_blocks_per_profile: int = PROPOSED_PRIMARY_BLOCKS_PER_PROFILE
    reserve_blocks_per_profile: int = PROPOSED_RESERVE_BLOCKS_PER_PROFILE

    def __post_init__(self) -> None:
        if (
            type(self) is not ProposedBlockSchedule
            or self.primary_blocks_per_profile != PROPOSED_PRIMARY_BLOCKS_PER_PROFILE
            or self.reserve_blocks_per_profile != PROPOSED_RESERVE_BLOCKS_PER_PROFILE
        ):
            raise TypeError("the proposed v3 block schedule must remain exact")

    @property
    def attempts_per_profile(self) -> int:
        return self.primary_blocks_per_profile + self.reserve_blocks_per_profile

    def primary_block_id(self, index: int) -> str:
        if type(index) is not int or not 0 <= index < self.primary_blocks_per_profile:
            raise IndexError("primary block index is outside the proposed schedule")
        return f"primary-{index + 1:03d}"

    def reserve_block_id(self, index: int) -> str:
        if type(index) is not int or not 0 <= index < self.reserve_blocks_per_profile:
            raise IndexError("reserve block index is outside the proposed schedule")
        return f"reserve-{index + 1:02d}"

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def build_nonqualifying_four_arm_block(
    *,
    design_digest: str,
    block_id: str,
    profile: AgentProfile,
    replicate: int,
    driver_ref: FixtureDriverRef,
    artifacts: tuple[FrozenArmArtifact, ...],
    budget: MatchedBudget,
    fixture_resource_ceiling: int,
    scaffold_ref: MockScaffoldRef,
    practice_pack_ref: PracticePackRef,
    v2_prior_pack_ref: PriorPackRef,
    v2_authorization_ref: TestOnlyPriorAuthorizationReceiptRef,
) -> FourArmBlockPlan:
    _digest(design_digest, "design_digest")
    _identifier(block_id, "block_id")
    if (
        type(profile) is not AgentProfile
        or type(replicate) is not int
        or replicate < 0
        or type(driver_ref) is not FixtureDriverRef
        or type(artifacts) is not tuple
        or any(type(item) is not FrozenArmArtifact for item in artifacts)
        or tuple(item.arm for item in artifacts) != tuple(ExperimentalArm)
        or type(budget) is not MatchedBudget
        or type(fixture_resource_ceiling) is not int
        or fixture_resource_ceiling < 1
        or type(scaffold_ref) is not MockScaffoldRef
        or type(practice_pack_ref) is not PracticePackRef
        or type(v2_prior_pack_ref) is not PriorPackRef
        or type(v2_authorization_ref) is not TestOnlyPriorAuthorizationReceiptRef
    ):
        raise TypeError("four-arm plan builder requires exact inputs")
    try:
        checked_driver = _canonical_driver_ref(driver_ref)
        checked_artifacts = tuple(
            FrozenArmArtifact(
                item.arm,
                item.artifact_id,
                item.artifact_version,
                item.content_digest,
                item.source_prior_pack_ref,
                item.proposal_hints,
            )
            for item in artifacts
        )
        checked_budget = _canonical_budget(budget)
        checked_scaffold = _canonical_simple_ref(scaffold_ref, MockScaffoldRef)
        checked_practice = _canonical_simple_ref(practice_pack_ref, PracticePackRef)
        checked_authorization = _canonical_authorization_ref(v2_authorization_ref)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("four-arm plan contains invalid nested values") from exc
    canonical_artifacts = build_nonqualifying_preflight_arm_artifacts(v2_prior_pack_ref)
    if checked_artifacts != canonical_artifacts:
        raise ValueError(
            "four-arm material must equal the registered preflight artifacts"
        )
    return _build_nonqualifying_block(
        design_digest=design_digest,
        block_id=block_id,
        profile=profile,
        replicate=replicate,
        checked_driver=checked_driver,
        canonical_artifacts=canonical_artifacts,
        checked_budget=checked_budget,
        fixture_resource_ceiling=fixture_resource_ceiling,
        checked_scaffold=checked_scaffold,
        checked_practice=checked_practice,
        checked_authorization=checked_authorization,
    )


def build_nonqualifying_lifecycle_four_arm_block(
    *,
    design_digest: str,
    block_id: str,
    profile: AgentProfile,
    replicate: int,
    driver_ref: FixtureDriverRef,
    budget: MatchedBudget,
    fixture_resource_ceiling: int,
    scaffold_ref: MockScaffoldRef,
    practice_pack_ref: PracticePackRef,
    v2_prior_pack: PriorPack,
    v2_authorization_ref: TestOnlyPriorAuthorizationReceiptRef,
) -> tuple[FourArmBlockPlan, PrivatePriorProjection]:
    """Freeze final treatment artifacts for a non-qualifying lifecycle block."""

    _digest(design_digest, "design_digest")
    _identifier(block_id, "block_id")
    if (
        type(profile) is not AgentProfile
        or type(replicate) is not int
        or replicate < 0
        or type(driver_ref) is not FixtureDriverRef
        or type(budget) is not MatchedBudget
        or type(fixture_resource_ceiling) is not int
        or fixture_resource_ceiling < 1
        or type(scaffold_ref) is not MockScaffoldRef
        or type(practice_pack_ref) is not PracticePackRef
        or type(v2_prior_pack) is not PriorPack
        or type(v2_authorization_ref) is not TestOnlyPriorAuthorizationReceiptRef
    ):
        raise TypeError("lifecycle block builder requires exact inputs")
    try:
        checked_driver = _canonical_driver_ref(driver_ref)
        checked_budget = _canonical_budget(budget)
        checked_scaffold = _canonical_simple_ref(scaffold_ref, MockScaffoldRef)
        checked_practice = _canonical_simple_ref(practice_pack_ref, PracticePackRef)
        checked_authorization = _canonical_authorization_ref(v2_authorization_ref)
        artifacts, projection = build_nonqualifying_lifecycle_arm_artifacts(
            v2_prior_pack
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("lifecycle block contains invalid nested values") from exc
    block = _build_nonqualifying_block(
        design_digest=design_digest,
        block_id=block_id,
        profile=profile,
        replicate=replicate,
        checked_driver=checked_driver,
        canonical_artifacts=artifacts,
        checked_budget=checked_budget,
        fixture_resource_ceiling=fixture_resource_ceiling,
        checked_scaffold=checked_scaffold,
        checked_practice=checked_practice,
        checked_authorization=checked_authorization,
    )
    return block, projection


def _build_nonqualifying_block(
    *,
    design_digest: str,
    block_id: str,
    profile: AgentProfile,
    replicate: int,
    checked_driver: FixtureDriverRef,
    canonical_artifacts: tuple[FrozenArmArtifact, ...],
    checked_budget: MatchedBudget,
    fixture_resource_ceiling: int,
    checked_scaffold: MockScaffoldRef,
    checked_practice: PracticePackRef,
    checked_authorization: TestOnlyPriorAuthorizationReceiptRef,
) -> FourArmBlockPlan:
    pinned_pack_ref = canonical_artifacts[-1].source_prior_pack_ref
    assert type(pinned_pack_ref) is PriorPackRef
    rng = CommonArmRng(design_digest, profile, block_id, replicate)
    runs = []
    for artifact in canonical_artifacts:
        v2 = artifact.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
        identity = RunIdentity(
            profile,
            artifact.arm,
            replicate,
            pinned_pack_ref if v2 else None,
            checked_authorization if v2 else None,
        )
        runs.append(
            NonQualifyingRunPlan(
                EXECUTION_PLAN_SCHEMA_VERSION,
                PREFLIGHT_AUTHORITY_CEILING,
                design_digest,
                block_id,
                identity,
                checked_driver,
                artifact,
                checked_budget,
                rng.stream_digest,
                REGISTERED_RNG_ROLES,
                fixture_resource_ceiling,
                checked_scaffold,
                checked_practice,
                _preflight_slot_digest(
                    design_digest=design_digest,
                    block_id=block_id,
                    profile=profile,
                    arm=artifact.arm,
                    replicate=replicate,
                    artifact_id=artifact.artifact_id,
                    artifact_version=artifact.artifact_version,
                    artifact_digest=artifact.content_digest,
                    driver_ref=checked_driver,
                    budget=checked_budget,
                    fixture_resource_ceiling=fixture_resource_ceiling,
                    scaffold_ref=checked_scaffold,
                    practice_pack_ref=checked_practice,
                    prior_pack_ref=identity.prior_pack_ref,
                    authorization_ref=identity.test_only_authorization_ref,
                ),
            )
        )
    return FourArmBlockPlan(profile, replicate, block_id, tuple(runs))


class ResearchOperationFailure(RuntimeError):
    """Typed public B-07S failure; provider diagnostics are never retained."""

    def __init__(
        self,
        operation: str,
        code: ResearchServiceErrorCode,
        request_digest: str,
        reply_digest: str,
    ) -> None:
        _identifier(operation, "operation")
        if (
            type(code) is not ResearchServiceErrorCode
            or _DIGEST.fullmatch(request_digest) is None
            or _DIGEST.fullmatch(reply_digest) is None
        ):
            raise TypeError("research failure requires an exact public error code")
        self.operation = operation
        self.code = code
        self.request_digest = request_digest
        self.reply_digest = reply_digest
        super().__init__(f"research operation {operation} failed with {code.value}")


def _research_result(
    session: AgentSession,
    operation: str,
    request: object,
    expected_type: type[object],
    reply_digests: list[str],
    request_digests: list[str] | None = None,
) -> object:
    request_digest = canonical_digest(request)
    if request_digests is not None:
        request_digests.append(request_digest)
    reply = session.research_call(ServiceCall(RESEARCH_NAMESPACE, operation, request))
    if type(reply) is not ServiceReply:
        raise TypeError("research session returned a non-protocol reply")
    reply_digests.append(canonical_digest(reply))
    if reply.status is ReplyStatus.ERROR:
        error = reply.result
        if type(error) is not ResearchServiceError:
            raise TypeError("research error reply is not nominal")
        raise ResearchOperationFailure(
            operation,
            error.code,
            request_digest,
            reply_digests[-1],
        )
    if reply.status is not ReplyStatus.OK or type(reply.result) is not expected_type:
        raise TypeError("research success reply has the wrong nominal result")
    return reply.result


@dataclass(frozen=True, slots=True)
class PreparedCandidate:
    """One proposal's B-07S preflight results; never a practice attempt."""

    proposal: DataOnlyStrategyProposal
    validation: DryValidationResult
    compilation: CompileStrategyResult
    resource_inspection: InspectResourcesResult | None
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not PreparedCandidate
            or self._factory_token is not _PREPARED_CANDIDATE_FACTORY_TOKEN
        ):
            raise TypeError("prepared candidates require the private preflight factory")
        if (
            type(self.proposal) is not DataOnlyStrategyProposal
            or type(self.validation) is not DryValidationResult
            or type(self.compilation) is not CompileStrategyResult
            or type(self.resource_inspection)
            not in (type(None), InspectResourcesResult)
            or (self.resource_inspection is not None)
            != (self.validation.valid and self.compilation.accepted)
        ):
            raise TypeError("prepared candidate service evidence is inconsistent")
        try:
            validation = load_canonical(
                canonical_bytes(self.validation), DryValidationResult
            )
            compilation = load_canonical(
                canonical_bytes(self.compilation), CompileStrategyResult
            )
            inspection = (
                None
                if self.resource_inspection is None
                else load_canonical(
                    canonical_bytes(self.resource_inspection), InspectResourcesResult
                )
            )
        except (CanonicalWireError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "prepared candidate service evidence is structurally invalid"
            ) from exc
        assert type(validation) is DryValidationResult
        assert type(compilation) is CompileStrategyResult
        assert type(inspection) in (type(None), InspectResourcesResult)
        challenge = self.proposal.challenge_key
        compilation_refs = tuple(
            ref
            for ref in (
                compilation.training_sampling_policy_ref,
                compilation.resolved_plan_ref,
                compilation.compilation_ref,
            )
            if ref is not None
        )
        if (
            validation.validation_result_ref.challenge_key != challenge
            or any(ref.challenge_key != challenge for ref in compilation_refs)
            or (
                inspection is not None
                and inspection.static_assessment_ref.challenge_key != challenge
            )
        ):
            raise ValueError("prepared candidate service evidence is cross-Challenge")
        object.__setattr__(self, "validation", validation)
        object.__setattr__(self, "compilation", compilation)
        object.__setattr__(self, "resource_inspection", inspection)

    @property
    def executable(self) -> bool:
        return self.resource_inspection is not None


class AdaptivePreflightBuilder:
    """One-run B-07S builder for proposal/practice interleaving.

    The builder is held only by the trusted development orchestrator.  It
    performs discovery once, admits each provider-produced Strategy through
    the unchanged B-07S operations, and can freeze the accumulated evidence
    into the existing immutable preflight carrier.  It grants no provider,
    practice, official-execution, or qualification authority.
    """

    __slots__ = (
        "_candidates",
        "_info",
        "_lookup",
        "_manifest",
        "_meter",
        "_plan",
        "_reply_digests",
        "_request_digests",
        "_scaffold",
        "_session",
        "_strategy_domain",
    )

    def __init__(
        self,
        *,
        session: AgentSession,
        plan: NonQualifyingRunPlan,
        strategy_domain: FixtureStrategyDomain,
        parameter_catalog: ParameterCatalog,
        candidate_assembly: CandidateAssemblyContract,
        meter: PolicyWorkMeter,
    ) -> None:
        if (
            type(self) is not AdaptivePreflightBuilder
            or type(session) is not AgentSession
            or type(plan) is not NonQualifyingRunPlan
            or type(strategy_domain) is not FixtureStrategyDomain
            or type(parameter_catalog) is not ParameterCatalog
            or type(candidate_assembly) is not CandidateAssemblyContract
            or type(meter) is not PolicyWorkMeter
            or not session.binds_meter(meter)
        ):
            raise TypeError("adaptive preflight requires exact bound capabilities")
        checked_plan = _canonical_run_plan(plan)
        expected_domain = fixture_strategy_domain(
            parameter_catalog.to_ref(candidate_assembly=candidate_assembly)
        )
        if strategy_domain != expected_domain:
            raise ValueError("adaptive strategy domain does not match B-02B owners")
        meter.bind_ceiling(math.floor(checked_plan.budget.compute_units))
        requests: list[str] = []
        replies: list[str] = []
        key = checked_plan.scaffold_ref.challenge_key
        info = _research_result(
            session,
            "get_challenge_info",
            GetChallengeInfoRequest(key),
            ChallengeInfo,
            replies,
            requests,
        )
        manifest = _research_result(
            session,
            "get_interaction_manifest",
            GetInteractionManifestRequest(key),
            InteractionManifest,
            replies,
            requests,
        )
        assert type(info) is ChallengeInfo and type(manifest) is InteractionManifest
        if (
            manifest.parameter_catalog_ref != expected_domain.parameter_catalog_ref
            or parameter_catalog.to_ref(candidate_assembly=candidate_assembly)
            != expected_domain.parameter_catalog_ref
        ):
            raise ValueError("adaptive discovery does not match B-02B owners")
        lookup: PriorLookupResult | None = None
        if checked_plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
            prior_ref = checked_plan.identity.prior_pack_ref
            assert type(prior_ref) is PriorPackRef
            value = _research_result(
                session,
                "get_prior",
                GetPriorRequest(key, ExactPriorSelector(prior_ref)),
                PriorLookupResult,
                replies,
                requests,
            )
            assert type(value) is PriorLookupResult
            if (
                value.prior_pack_ref != prior_ref
                or type(value.authorization) is not FixturePriorAuthorization
                or value.authorization.receipt_ref
                != checked_plan.identity.test_only_authorization_ref
            ):
                raise ValueError("adaptive B-07D3 result does not match frozen pins")
            # Reapply the existing semantic adapter even though the provider
            # payload uses the disclosure-safe PriorPack, not these hints.
            proposal_hints_from_test_only_lookup(
                value,
                catalog=parameter_catalog,
                candidate_assembly=candidate_assembly,
                expected_prior_pack_ref=prior_ref,
                expected_authorization_ref=(
                    checked_plan.identity.test_only_authorization_ref
                ),
            )
            lookup = value
        scaffold = _research_result(
            session,
            "get_mock_scaffold",
            GetMockScaffoldRequest(
                key,
                info.training_support_ref,
                checked_plan.identity.prior_pack_ref,
            ),
            MockScaffold,
            replies,
            requests,
        )
        assert type(scaffold) is MockScaffold
        if scaffold.scaffold_ref != checked_plan.scaffold_ref:
            raise ValueError("adaptive scaffold does not match the frozen run")
        self._session = session
        self._plan = checked_plan
        self._strategy_domain = expected_domain
        self._meter = meter
        self._info = info
        self._manifest = manifest
        self._lookup = lookup
        self._scaffold = scaffold
        self._request_digests = requests
        self._reply_digests = replies
        self._candidates: list[PreparedCandidate] = []

    @property
    def challenge_info(self) -> ChallengeInfo:
        return self._info

    @property
    def interaction_manifest(self) -> InteractionManifest:
        return self._manifest

    @property
    def prior_lookup(self) -> PriorLookupResult | None:
        return self._lookup

    @property
    def scaffold(self) -> MockScaffold:
        return self._scaffold

    @property
    def candidates(self) -> tuple[PreparedCandidate, ...]:
        return tuple(self._candidates)

    def add_strategy(
        self,
        *,
        attempt: int,
        surface_id: str,
        strategy: dict[str, object],
    ) -> PreparedCandidate:
        if (
            type(attempt) is not int
            or not 1 <= attempt <= self._plan.budget.attempt_limit
            or any(item.proposal.attempt == attempt for item in self._candidates)
            or (self._candidates and attempt <= self._candidates[-1].proposal.attempt)
            or type(surface_id) is not str
            or surface_id not in REGISTERED_EFFECTFUL_SURFACES
            or type(strategy) is not dict
            or len(self._candidates) >= self._plan.budget.attempt_limit
        ):
            raise TypeError("adaptive proposal is outside the registered bounds")
        self._meter.record(PolicyWorkKind.ATTEMPT)
        self._meter.record(PolicyWorkKind.CANDIDATE_PROPOSAL)
        proposal = DataOnlyStrategyProposal(
            self._info.challenge_key, attempt, surface_id, strategy
        )
        if any(
            item.proposal.strategy_digest == proposal.strategy_digest
            for item in self._candidates
        ):
            raise ValueError("adaptive proposal duplicates an existing Strategy")
        validation = _research_result(
            self._session,
            "dry_validate",
            DryValidateRequest(self._info.challenge_key, proposal.strategy),
            DryValidationResult,
            self._reply_digests,
            self._request_digests,
        )
        compilation = _research_result(
            self._session,
            "compile_strategy",
            CompileStrategyRequest(
                self._info.challenge_key,
                proposal.strategy,
                self._info.training_support_ref,
            ),
            CompileStrategyResult,
            self._reply_digests,
            self._request_digests,
        )
        assert type(validation) is DryValidationResult
        assert type(compilation) is CompileStrategyResult
        inspection: InspectResourcesResult | None = None
        if validation.valid and compilation.accepted:
            result = _research_result(
                self._session,
                "inspect_resources",
                InspectResourcesRequest(
                    self._info.challenge_key,
                    proposal.strategy,
                    self._manifest.resource_policy_ref,
                ),
                InspectResourcesResult,
                self._reply_digests,
                self._request_digests,
            )
            assert type(result) is InspectResourcesResult
            validate_fixture_resource_inspection(
                result, ceiling=self._plan.fixture_resource_ceiling
            )
            inspection = result
        candidate = PreparedCandidate(
            proposal,
            validation,
            compilation,
            inspection,
            _PREPARED_CANDIDATE_FACTORY_TOKEN,
        )
        self._candidates.append(candidate)
        return candidate

    def freeze(self) -> PreparedFixturePreflight:
        if not self._candidates:
            raise ValueError("adaptive preflight has no recorded proposal")
        proposals = tuple(item.proposal for item in self._candidates)
        batch = bind_data_only_proposal_batch(
            driver_ref=self._plan.driver_ref,
            rng_stream_digest=self._plan.rng_stream_digest,
            proposals=proposals,
        )
        candidates = tuple(self._candidates)
        first = next(
            (item.proposal.attempt for item in candidates if item.executable), None
        )
        compute = self._session.normalized_compute()
        request_digests = tuple(self._request_digests)
        reply_digests = tuple(self._reply_digests)
        transcript = _prepared_transcript_digest(
            plan=self._plan,
            strategy_domain_digest=self._strategy_domain.content_digest,
            challenge_info=self._info,
            interaction_manifest=self._manifest,
            prior_lookup=self._lookup,
            scaffold=self._scaffold,
            proposal_batch=batch,
            candidates=candidates,
            first_preflight_executable_attempt=first,
            service_request_digests=request_digests,
            service_reply_digests=reply_digests,
            preflight_compute=compute,
        )
        return PreparedFixturePreflight(
            PREFLIGHT_AUTHORITY_CEILING,
            self._plan,
            self._info,
            self._manifest,
            self._lookup,
            self._scaffold,
            batch,
            candidates,
            first,
            self._strategy_domain.content_digest,
            request_digests,
            reply_digests,
            compute,
            transcript,
            _PREPARED_PREFLIGHT_FACTORY_TOKEN,
        )


def _canonical_research_result(value: object, expected_type: type[object]) -> object:
    """Reconstruct one stored B-07S result before it can reach A7."""

    if type(value) is not expected_type:
        raise TypeError("stored research result has the wrong nominal type")
    result = load_canonical(canonical_bytes(value), expected_type)
    if type(result) is not expected_type:
        raise TypeError("stored research result reconstruction changed nominal type")
    return result


def _canonical_compute_receipt(value: object) -> NormalizedComputeReceipt:
    if type(value) is not NormalizedComputeReceipt:
        raise TypeError("preflight compute requires an exact receipt")
    return NormalizedComputeReceipt(
        value.schema_version,
        value.policy_id,
        value.policy_digest,
        tuple(PolicyWorkCount(item.kind, item.count) for item in value.counts),
        value.total_work_units,
    )


def _discovery_resources_match(
    info: ChallengeInfo, manifest: InteractionManifest
) -> bool:
    """Reapply the B-07S discovery pair relationship after reconstruction."""

    return (
        info.challenge_key == manifest.challenge_key
        and manifest.challenge_info_ref == info.to_ref()
        and manifest.physical_system_ref == info.physical_system_ref
        and manifest.candidate_output_ref == info.candidate_output_ref
        and manifest.instance_distribution_ref == info.instance_distribution_ref
        and manifest.sampling_plan_ref == info.sampling_plan_ref
        and manifest.training_support_ref == info.training_support_ref
        and manifest.measurement_contract_ref == info.measurement_contract_ref
        and manifest.public_score_policy_ref == info.public_score_policy_ref
    )


def _prepared_service_reply_digests(
    *,
    challenge_info: ChallengeInfo,
    interaction_manifest: InteractionManifest,
    prior_lookup: PriorLookupResult | None,
    scaffold: MockScaffold,
    candidates: tuple[PreparedCandidate, ...],
) -> tuple[str, ...]:
    """Derive the exact ordered successful B-07S reply transcript."""

    results: list[object] = [challenge_info, interaction_manifest]
    if prior_lookup is not None:
        results.append(prior_lookup)
    results.append(scaffold)
    for candidate in candidates:
        results.extend((candidate.validation, candidate.compilation))
        if candidate.resource_inspection is not None:
            results.append(candidate.resource_inspection)
    return tuple(
        canonical_digest(ServiceReply(ReplyStatus.OK, result)) for result in results
    )


def _prepared_service_request_digests(
    *,
    plan: NonQualifyingRunPlan,
    challenge_info: ChallengeInfo,
    interaction_manifest: InteractionManifest,
    scaffold: MockScaffold,
    candidates: tuple[PreparedCandidate, ...],
) -> tuple[str, ...]:
    """Derive the exact ordered successful B-07S request transcript."""

    key = challenge_info.challenge_key
    requests: list[object] = [
        GetChallengeInfoRequest(key),
        GetInteractionManifestRequest(key),
    ]
    if plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
        assert plan.identity.prior_pack_ref is not None
        requests.append(
            GetPriorRequest(key, ExactPriorSelector(plan.identity.prior_pack_ref))
        )
    requests.append(
        GetMockScaffoldRequest(
            key, challenge_info.training_support_ref, plan.identity.prior_pack_ref
        )
    )
    for candidate in candidates:
        requests.extend(
            (
                DryValidateRequest(key, candidate.proposal.strategy),
                CompileStrategyRequest(
                    key,
                    candidate.proposal.strategy,
                    challenge_info.training_support_ref,
                ),
            )
        )
        if candidate.resource_inspection is not None:
            requests.append(
                InspectResourcesRequest(
                    key,
                    candidate.proposal.strategy,
                    interaction_manifest.resource_policy_ref,
                )
            )
    return tuple(canonical_digest(item) for item in requests)


def validate_fixture_resource_inspection(
    inspection: InspectResourcesResult, *, ceiling: int
) -> float:
    """Validate the exact static fixture dimension and one-plan ceiling."""

    if type(inspection) is not InspectResourcesResult or type(ceiling) is not int:
        raise TypeError("fixture resource validation requires exact values")
    if len(inspection.line_items) != 1:
        raise ValueError("fixture preflight requires one exact resource dimension")
    line = inspection.line_items[0]
    if (
        line.unit != FIXTURE_RESOURCE_INSPECTION_UNIT
        or line.confidence_band != (line.quantity, line.quantity)
        or "STATIC_EXACT_PLAN_DERIVED" not in inspection.limitations
        or "ASSESSMENT:ADMISSIBLE" not in inspection.limitations
    ):
        raise ValueError(
            "fixture resource result is not the exact admissible static unit"
        )
    quantity = math.fsum(item.quantity for item in inspection.line_items)
    if quantity > float(ceiling):
        raise FixtureResourceBudgetExceeded(float(quantity), ceiling)
    return quantity


def _prepared_transcript_digest(
    *,
    plan: NonQualifyingRunPlan,
    strategy_domain_digest: str,
    challenge_info: ChallengeInfo,
    interaction_manifest: InteractionManifest,
    prior_lookup: PriorLookupResult | None,
    scaffold: MockScaffold,
    proposal_batch: DriverProposalBatch,
    candidates: tuple[PreparedCandidate, ...],
    first_preflight_executable_attempt: int | None,
    service_request_digests: tuple[str, ...],
    service_reply_digests: tuple[str, ...],
    preflight_compute: NormalizedComputeReceipt,
) -> str:
    candidate_parts: list[str] = []
    for item in candidates:
        candidate_parts.extend(
            (
                item.proposal.strategy_digest,
                canonical_digest(item.validation),
                canonical_digest(item.compilation),
                (
                    "NO_RESOURCE_INSPECTION"
                    if item.resource_inspection is None
                    else canonical_digest(item.resource_inspection)
                ),
            )
        )
    parts = (
        plan.final_submission_slot_digest,
        strategy_domain_digest,
        canonical_digest(challenge_info),
        canonical_digest(interaction_manifest),
        "NO_PRIOR_LOOKUP" if prior_lookup is None else canonical_digest(prior_lookup),
        canonical_digest(scaffold),
        proposal_batch.transcript_digest,
        *service_request_digests,
        *service_reply_digests,
        *candidate_parts,
        (
            "NO_PREFLIGHT_EXECUTABLE_ATTEMPT"
            if first_preflight_executable_attempt is None
            else f"FIRST_PREFLIGHT_EXECUTABLE_ATTEMPT:{first_preflight_executable_attempt}"
        ),
        preflight_compute.content_digest,
    )
    return (
        "sha256:"
        + hashlib.sha256(
            _DRIVER_SERVICE_TRANSCRIPT_DOMAIN
            + b"\x00".join(item.encode("ascii") for item in parts)
        ).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class PreparedFixturePreflight:
    """Replayable B-07S preflight only, never practice or execution evidence."""

    authority_ceiling: str
    plan: NonQualifyingRunPlan
    challenge_info: ChallengeInfo
    interaction_manifest: InteractionManifest
    prior_lookup: PriorLookupResult | None
    scaffold: MockScaffold
    proposal_batch: DriverProposalBatch
    candidates: tuple[PreparedCandidate, ...]
    first_preflight_executable_attempt: int | None
    strategy_domain_digest: str
    service_request_digests: tuple[str, ...]
    service_reply_digests: tuple[str, ...]
    preflight_compute: NormalizedComputeReceipt
    transcript_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not PreparedFixturePreflight
            or self._factory_token is not _PREPARED_PREFLIGHT_FACTORY_TOKEN
        ):
            raise TypeError(
                "prepared preflights require the private preparation factory"
            )
        if (
            self.authority_ceiling != PREFLIGHT_AUTHORITY_CEILING
            or type(self.plan) is not NonQualifyingRunPlan
            or type(self.challenge_info) is not ChallengeInfo
            or type(self.interaction_manifest) is not InteractionManifest
            or type(self.prior_lookup) not in (type(None), PriorLookupResult)
            or type(self.scaffold) is not MockScaffold
            or type(self.proposal_batch) is not DriverProposalBatch
            or type(self.candidates) is not tuple
            or any(type(item) is not PreparedCandidate for item in self.candidates)
            or type(self.first_preflight_executable_attempt) not in (type(None), int)
            or type(self.service_reply_digests) is not tuple
            or type(self.service_request_digests) is not tuple
            or type(self.preflight_compute) is not NormalizedComputeReceipt
        ):
            raise TypeError("prepared fixture preflight is not canonical")
        candidate_proposals = tuple(item.proposal for item in self.candidates)
        if len(candidate_proposals) != len(self.proposal_batch.proposals) or any(
            candidate is not proposed
            for candidate, proposed in zip(
                candidate_proposals, self.proposal_batch.proposals, strict=True
            )
        ):
            raise TypeError("prepared candidates do not match the proposal batch")
        selected = tuple(
            item
            for item in self.candidates
            if item.executable
            and item.proposal.attempt == self.first_preflight_executable_attempt
        )
        expected_first = next(
            (item.proposal.attempt for item in self.candidates if item.executable), None
        )
        expected_reply_count = (
            3
            + (1 if self.prior_lookup is not None else 0)
            + sum(2 + int(item.executable) for item in self.candidates)
        )
        if (
            len(self.candidates) != len(self.proposal_batch.proposals)
            or self.first_preflight_executable_attempt != expected_first
            or (
                self.first_preflight_executable_attempt is not None
                and len(selected) != 1
            )
            or len(self.service_reply_digests) != expected_reply_count
            or len(self.service_request_digests) != expected_reply_count
            or any(
                type(item) is not str or _DIGEST.fullmatch(item) is None
                for item in self.service_reply_digests
            )
            or any(
                type(item) is not str or _DIGEST.fullmatch(item) is None
                for item in self.service_request_digests
            )
            or self.proposal_batch.driver_ref != self.plan.driver_ref
            or self.plan.driver_ref != fixture_driver_ref(self.plan.identity.profile)
            or self.proposal_batch.rng_stream_digest != self.plan.rng_stream_digest
            or self.challenge_info.challenge_key != self.plan.scaffold_ref.challenge_key
            or self.interaction_manifest.challenge_key
            != self.plan.scaffold_ref.challenge_key
            or self.scaffold.scaffold_ref != self.plan.scaffold_ref
        ):
            raise TypeError("prepared fixture preflight is not canonical")
        _digest(self.strategy_domain_digest, "strategy_domain_digest")
        _digest(self.transcript_digest, "transcript_digest")
        expected_digest = _prepared_transcript_digest(
            plan=self.plan,
            strategy_domain_digest=self.strategy_domain_digest,
            challenge_info=self.challenge_info,
            interaction_manifest=self.interaction_manifest,
            prior_lookup=self.prior_lookup,
            scaffold=self.scaffold,
            proposal_batch=self.proposal_batch,
            candidates=self.candidates,
            first_preflight_executable_attempt=self.first_preflight_executable_attempt,
            service_request_digests=self.service_request_digests,
            service_reply_digests=self.service_reply_digests,
            preflight_compute=self.preflight_compute,
        )
        if self.transcript_digest != expected_digest:
            raise ValueError("preflight transcript digest does not bind its content")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    @property
    def selected_attempt(self) -> int | None:
        """Compatibility alias; this is not a practice-selected attempt."""

        return self.first_preflight_executable_attempt

    @property
    def preflight_only(self) -> bool:
        return True


def _canonical_prepared_preflight(value: object) -> PreparedFixturePreflight:
    if type(value) is not PreparedFixturePreflight:
        raise TypeError("submission requires an exact PreparedFixturePreflight")
    try:
        plan = _canonical_run_plan(value.plan)
        info = _canonical_research_result(value.challenge_info, ChallengeInfo)
        manifest = _canonical_research_result(
            value.interaction_manifest, InteractionManifest
        )
        lookup = (
            None
            if value.prior_lookup is None
            else _canonical_research_result(value.prior_lookup, PriorLookupResult)
        )
        scaffold = _canonical_research_result(value.scaffold, MockScaffold)
        assert type(info) is ChallengeInfo
        assert type(manifest) is InteractionManifest
        assert type(lookup) in (type(None), PriorLookupResult)
        assert type(scaffold) is MockScaffold
        proposals = tuple(
            DataOnlyStrategyProposal(
                item.challenge_key,
                item.attempt,
                item.surface_id,
                item.strategy,
            )
            for item in value.proposal_batch.proposals
        )
        batch = DriverProposalBatch(
            _canonical_driver_ref(value.proposal_batch.driver_ref),
            value.proposal_batch.rng_stream_digest,
            proposals,
            value.proposal_batch.transcript_digest,
        )
        if len(value.candidates) != len(proposals):
            raise ValueError("candidate/proposal cardinality changed")
        candidates = tuple(
            PreparedCandidate(
                proposal,
                existing.validation,
                existing.compilation,
                existing.resource_inspection,
                _PREPARED_CANDIDATE_FACTORY_TOKEN,
            )
            for proposal, existing in zip(proposals, value.candidates, strict=True)
        )
        for candidate in candidates:
            if candidate.resource_inspection is not None:
                validate_fixture_resource_inspection(
                    candidate.resource_inspection,
                    ceiling=plan.fixture_resource_ceiling,
                )
        compute = _canonical_compute_receipt(value.preflight_compute)
        challenge = plan.scaffold_ref.challenge_key
        if (
            not _discovery_resources_match(info, manifest)
            or info.challenge_key != challenge
            or scaffold.scaffold_ref != plan.scaffold_ref
            or any(proposal.challenge_key != challenge for proposal in proposals)
            or compute.total_work_units > math.floor(plan.budget.compute_units)
        ):
            raise ValueError("prepared preflight owner relationships changed")
        if plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
            if (
                type(lookup) is not PriorLookupResult
                or lookup.prior_pack_ref != plan.identity.prior_pack_ref
                or lookup.prior_pack_ref != prior_pack_ref(lookup.prior_pack)
                or lookup.index_snapshot_ref.challenge_key != challenge
                or lookup.index_snapshot_ref.channel
                is not PriorChannel.TEST_ONLY_FIXTURE
                or type(lookup.authorization) is not FixturePriorAuthorization
                or lookup.authorization.receipt_ref
                != plan.identity.test_only_authorization_ref
                or lookup.prior_pack.parameter_catalog_ref
                != manifest.parameter_catalog_ref
            ):
                raise ValueError("prepared v2 prior evidence changed")
        elif lookup is not None:
            raise ValueError("non-v2 preflight cannot carry a prior lookup")
        reply_digests = _prepared_service_reply_digests(
            challenge_info=info,
            interaction_manifest=manifest,
            prior_lookup=lookup,
            scaffold=scaffold,
            candidates=candidates,
        )
        request_digests = _prepared_service_request_digests(
            plan=plan,
            challenge_info=info,
            interaction_manifest=manifest,
            scaffold=scaffold,
            candidates=candidates,
        )
        if value.service_reply_digests != reply_digests:
            raise ValueError("stored service reply transcript changed")
        if value.service_request_digests != request_digests:
            raise ValueError("stored service request transcript changed")
        return PreparedFixturePreflight(
            value.authority_ceiling,
            plan,
            info,
            manifest,
            lookup,
            scaffold,
            batch,
            candidates,
            value.first_preflight_executable_attempt,
            value.strategy_domain_digest,
            request_digests,
            reply_digests,
            compute,
            value.transcript_digest,
            _PREPARED_PREFLIGHT_FACTORY_TOKEN,
        )
    except (CanonicalWireError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            "prepared submission evidence is structurally invalid"
        ) from exc


# Compatibility alias for the first readiness slice.
PreparedFixtureRun = PreparedFixturePreflight


def prepare_nonqualifying_preflight(
    *,
    session: AgentSession,
    plan: NonQualifyingRunPlan,
    driver: FixtureAgentDriver,
    strategy_domain: FixtureStrategyDomain,
    parameter_catalog: ParameterCatalog,
    candidate_assembly: CandidateAssemblyContract,
    meter: PolicyWorkMeter,
) -> PreparedFixturePreflight:
    """Discover, compile, and inspect through B-07S; do not run practice."""

    if (
        type(session) is not AgentSession
        or type(plan) is not NonQualifyingRunPlan
        or type(driver) is not FixtureAgentDriver
        or type(strategy_domain) is not FixtureStrategyDomain
        or type(parameter_catalog) is not ParameterCatalog
        or type(candidate_assembly) is not CandidateAssemblyContract
        or type(meter) is not PolicyWorkMeter
        or not session.binds_meter(meter)
    ):
        raise TypeError("run preparation requires exact bound fixture capabilities")
    plan = _canonical_run_plan(plan)
    try:
        expected_strategy_domain = fixture_strategy_domain(
            parameter_catalog.to_ref(candidate_assembly=candidate_assembly)
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            "B-02B strategy-domain owners are structurally invalid"
        ) from exc
    if strategy_domain != expected_strategy_domain:
        raise ValueError(
            "fixture strategy domain does not equal the current B-02B owners"
        )
    strategy_domain = expected_strategy_domain
    expected_driver_ref = fixture_driver_ref(driver.profile)
    if (
        driver.profile is not plan.identity.profile
        or driver.ref != expected_driver_ref
        or plan.driver_ref != expected_driver_ref
    ):
        raise ValueError("fixture driver does not match its current canonical profile")
    # Normalized work is capped before the first service or policy operation.
    # The floor is exact because meter events are integral semantic work units.
    meter.bind_ceiling(math.floor(plan.budget.compute_units))
    reply_digests: list[str] = []
    request_digests: list[str] = []
    key = plan.scaffold_ref.challenge_key
    info = _research_result(
        session,
        "get_challenge_info",
        GetChallengeInfoRequest(key),
        ChallengeInfo,
        reply_digests,
        request_digests,
    )
    assert type(info) is ChallengeInfo
    manifest = _research_result(
        session,
        "get_interaction_manifest",
        GetInteractionManifestRequest(key),
        InteractionManifest,
        reply_digests,
        request_digests,
    )
    assert type(manifest) is InteractionManifest
    if manifest.parameter_catalog_ref != strategy_domain.parameter_catalog_ref:
        raise ValueError(
            "fixture strategy domain does not match the B-07S interaction manifest"
        )
    if (
        parameter_catalog.to_ref(candidate_assembly=candidate_assembly)
        != strategy_domain.parameter_catalog_ref
    ):
        raise ValueError(
            "fixture strategy domain does not bind the supplied B-02B owners"
        )

    lookup: PriorLookupResult | None = None
    if plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
        prior_ref = plan.identity.prior_pack_ref
        assert type(prior_ref) is PriorPackRef
        value = _research_result(
            session,
            "get_prior",
            GetPriorRequest(key, ExactPriorSelector(prior_ref)),
            PriorLookupResult,
            reply_digests,
            request_digests,
        )
        assert type(value) is PriorLookupResult
        if (
            value.prior_pack_ref != prior_ref
            or type(value.authorization) is not FixturePriorAuthorization
            or value.authorization.receipt_ref
            != plan.identity.test_only_authorization_ref
        ):
            raise ValueError("B-07D3 prior result does not match the frozen v2 pins")
        lookup = value
        hints = proposal_hints_from_test_only_lookup(
            value,
            catalog=parameter_catalog,
            candidate_assembly=candidate_assembly,
            expected_prior_pack_ref=prior_ref,
            expected_authorization_ref=plan.identity.test_only_authorization_ref,
        )
    else:
        hints = plan.arm_artifact.proposal_hints

    scaffold_value = _research_result(
        session,
        "get_mock_scaffold",
        GetMockScaffoldRequest(
            key, info.training_support_ref, plan.identity.prior_pack_ref
        ),
        MockScaffold,
        reply_digests,
        request_digests,
    )
    assert type(scaffold_value) is MockScaffold
    if scaffold_value.scaffold_ref != plan.scaffold_ref:
        raise ValueError("B-07C scaffold does not match the frozen run plan")

    rng = CommonArmRng(
        plan.design_digest,
        plan.identity.profile,
        plan.block_id,
        plan.identity.replicate,
    )
    batch = driver.propose(
        challenge_key=key,
        scaffold_strategy=scaffold_value.strategy_template,
        strategy_domain=strategy_domain,
        hints=hints,
        rng=rng,
        meter=meter,
        attempt_limit=plan.budget.attempt_limit,
    )
    candidates: list[PreparedCandidate] = []
    for proposal in batch.proposals:
        validation = _research_result(
            session,
            "dry_validate",
            DryValidateRequest(key, proposal.strategy),
            DryValidationResult,
            reply_digests,
            request_digests,
        )
        assert type(validation) is DryValidationResult
        compilation = _research_result(
            session,
            "compile_strategy",
            CompileStrategyRequest(key, proposal.strategy, info.training_support_ref),
            CompileStrategyResult,
            reply_digests,
            request_digests,
        )
        assert type(compilation) is CompileStrategyResult
        inspection: InspectResourcesResult | None = None
        if validation.valid and compilation.accepted:
            value = _research_result(
                session,
                "inspect_resources",
                InspectResourcesRequest(
                    key, proposal.strategy, manifest.resource_policy_ref
                ),
                InspectResourcesResult,
                reply_digests,
                request_digests,
            )
            assert type(value) is InspectResourcesResult
            validate_fixture_resource_inspection(
                value, ceiling=plan.fixture_resource_ceiling
            )
            inspection = value
        candidates.append(
            PreparedCandidate(
                proposal,
                validation,
                compilation,
                inspection,
                _PREPARED_CANDIDATE_FACTORY_TOKEN,
            )
        )
    first_preflight_executable = next(
        (item.proposal.attempt for item in candidates if item.executable), None
    )
    compute = session.normalized_compute()
    transcript_digest = _prepared_transcript_digest(
        plan=plan,
        strategy_domain_digest=strategy_domain.content_digest,
        challenge_info=info,
        interaction_manifest=manifest,
        prior_lookup=lookup,
        scaffold=scaffold_value,
        proposal_batch=batch,
        candidates=tuple(candidates),
        first_preflight_executable_attempt=first_preflight_executable,
        service_request_digests=tuple(request_digests),
        service_reply_digests=tuple(reply_digests),
        preflight_compute=compute,
    )
    return PreparedFixturePreflight(
        PREFLIGHT_AUTHORITY_CEILING,
        plan,
        info,
        manifest,
        lookup,
        scaffold_value,
        batch,
        tuple(candidates),
        first_preflight_executable,
        strategy_domain.content_digest,
        tuple(request_digests),
        tuple(reply_digests),
        compute,
        transcript_digest,
        _PREPARED_PREFLIGHT_FACTORY_TOKEN,
    )


# Compatibility alias retained for callers of the first readiness slice.
prepare_nonqualifying_run = prepare_nonqualifying_preflight


@dataclass(frozen=True, slots=True)
class OfficialFixtureSubmission:
    """Factory-produced A7 association with no worker or qualification authority."""

    authority_ceiling: str
    plan_slot_digest: str
    proposal_digest: str
    receipt: SubmitReceipt
    association_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not OfficialFixtureSubmission
            or self._factory_token is not _OFFICIAL_FIXTURE_SUBMISSION_FACTORY_TOKEN
            or self.authority_ceiling != OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING
            or type(self.receipt) is not SubmitReceipt
        ):
            raise TypeError("official fixture submission binding is invalid")
        _digest(self.plan_slot_digest, "plan_slot_digest")
        _digest(self.proposal_digest, "proposal_digest")
        _digest(self.association_digest, "association_digest")
        try:
            checked_receipt = SubmitReceipt(
                self.receipt.schema_version, self.receipt.status
            )
        except (AttributeError, McpIntegrationError, TypeError, ValueError) as exc:
            raise ValueError("official fixture submission receipt is invalid") from exc
        object.__setattr__(self, "receipt", checked_receipt)
        expected = _official_fixture_submission_association_digest(
            authority_ceiling=self.authority_ceiling,
            plan_slot_digest=self.plan_slot_digest,
            proposal_digest=self.proposal_digest,
            receipt=checked_receipt,
        )
        if self.association_digest != expected:
            raise ValueError("official fixture submission association changed")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def _canonical_official_fixture_submission(
    value: object,
) -> OfficialFixtureSubmission:
    if type(value) is not OfficialFixtureSubmission:
        raise TypeError("official result lookup requires an exact fixture submission")
    try:
        return OfficialFixtureSubmission(
            value.authority_ceiling,
            value.plan_slot_digest,
            value.proposal_digest,
            value.receipt,
            value.association_digest,
            _OFFICIAL_FIXTURE_SUBMISSION_FACTORY_TOKEN,
        )
    except (AttributeError, McpIntegrationError, TypeError, ValueError) as exc:
        raise ValueError("official fixture submission is structurally invalid") from exc


def _official_fixture_submission_association_digest(
    *,
    authority_ceiling: str,
    plan_slot_digest: str,
    proposal_digest: str,
    receipt: SubmitReceipt,
) -> str:
    payload = b"\x00".join(
        item.encode("ascii")
        for item in (
            authority_ceiling,
            plan_slot_digest,
            proposal_digest,
            receipt.schema_version,
            receipt.status.submission_id.value,
            receipt.status.state.value,
        )
    )
    return (
        "sha256:"
        + hashlib.sha256(_OFFICIAL_SUBMISSION_ASSOCIATION_DOMAIN + payload).hexdigest()
    )


def submit_prepared_fixture_run(
    *, session: AgentSession, prepared: PreparedFixtureRun
) -> OfficialFixtureSubmission:
    """Submit once through A7/A8; trusted queue advancement remains external."""

    if type(session) is not AgentSession or type(prepared) is not PreparedFixtureRun:
        raise TypeError("official submission requires exact prepared fixture values")
    prepared = _canonical_prepared_preflight(prepared)
    if prepared.selected_attempt is None:
        raise ValueError("no executable proposal is available for official submission")
    if session.normalized_compute() != prepared.preflight_compute:
        raise ValueError(
            "submission session does not retain the exact preflight work state"
        )
    selected = next(
        item
        for item in prepared.candidates
        if item.proposal.attempt == prepared.selected_attempt
    )
    key = prepared.challenge_info.challenge_key
    result = session.official_call(
        McpCall(
            "1.0",
            "submit",
            (
                McpField("challenge_id", key.challenge_id),
                McpField("challenge_version", key.version),
                McpField("strategy", selected.proposal.strategy),
            ),
        )
    )
    if type(result) is not SubmitReceipt:
        raise TypeError("official fixture submit returned the wrong nominal result")
    authority_ceiling = OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING
    plan_slot_digest = prepared.plan.final_submission_slot_digest
    proposal_digest = selected.proposal.strategy_digest
    return OfficialFixtureSubmission(
        authority_ceiling,
        plan_slot_digest,
        proposal_digest,
        result,
        _official_fixture_submission_association_digest(
            authority_ceiling=authority_ceiling,
            plan_slot_digest=plan_slot_digest,
            proposal_digest=proposal_digest,
            receipt=result,
        ),
        _OFFICIAL_FIXTURE_SUBMISSION_FACTORY_TOKEN,
    )


def submit_selected_prepared_fixture_run(
    *,
    session: AgentSession,
    prepared: PreparedFixtureRun,
    selection: DriverSelection,
) -> OfficialFixtureSubmission:
    """Submit the practice-selected candidate under the non-qualifying ceiling."""

    if (
        type(session) is not AgentSession
        or type(prepared) is not PreparedFixtureRun
        or type(selection) is not DriverSelection
    ):
        raise TypeError("lifecycle submission requires exact fixture values")
    prepared = _canonical_prepared_preflight(prepared)
    if (
        selection.driver_ref != prepared.plan.driver_ref
        or selection.feedback_digests == ()
    ):
        raise ValueError("practice selection does not bind the prepared driver")
    selected = next(
        (
            item
            for item in prepared.candidates
            if item.proposal.attempt == selection.selected_attempt
        ),
        None,
    )
    if (
        selected is None
        or not selected.executable
        or selected.proposal.strategy_digest != selection.selected_proposal_digest
    ):
        raise ValueError("practice selection does not bind an executable proposal")
    if session.normalized_compute().total_work_units > math.floor(
        prepared.plan.budget.compute_units
    ):
        raise ValueError("lifecycle compute exceeds the frozen run budget")
    key = prepared.challenge_info.challenge_key
    result = session.official_call(
        McpCall(
            "1.0",
            "submit",
            (
                McpField("challenge_id", key.challenge_id),
                McpField("challenge_version", key.version),
                McpField("strategy", selected.proposal.strategy),
            ),
        )
    )
    if type(result) is not SubmitReceipt:
        raise TypeError("official fixture submit returned the wrong nominal result")
    authority_ceiling = OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING
    return OfficialFixtureSubmission(
        authority_ceiling,
        prepared.plan.final_submission_slot_digest,
        selected.proposal.strategy_digest,
        result,
        _official_fixture_submission_association_digest(
            authority_ceiling=authority_ceiling,
            plan_slot_digest=prepared.plan.final_submission_slot_digest,
            proposal_digest=selected.proposal.strategy_digest,
            receipt=result,
        ),
        _OFFICIAL_FIXTURE_SUBMISSION_FACTORY_TOKEN,
    )


def read_official_fixture_result(
    *, session: AgentSession, submission: OfficialFixtureSubmission
) -> SubmissionResult:
    """Read A8 state only; this function cannot advance the trusted worker."""

    if (
        type(session) is not AgentSession
        or type(submission) is not OfficialFixtureSubmission
    ):
        raise TypeError("official result lookup requires exact fixture values")
    submission = _canonical_official_fixture_submission(submission)
    result = session.official_call(
        McpCall(
            "1.0",
            "get_submission_result",
            (McpField("submission_id", submission.receipt.status.submission_id.value),),
        )
    )
    if type(result) is not SubmissionResult:
        raise TypeError("official fixture lookup returned the wrong nominal result")
    return result


@dataclass(frozen=True, slots=True)
class CalibrationRunObservation:
    """Raw preflight accounting; no practice or utility endpoint is accepted."""

    profile: AgentProfile
    arm: ExperimentalArm
    block_id: str
    compute: NormalizedComputeReceipt
    wall_time: WallTimeObservation
    fixture_resource_observations: tuple[ResourceObservation, ...]
    infrastructure_failed: bool

    def __post_init__(self) -> None:
        if (
            type(self) is not CalibrationRunObservation
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.compute) is not NormalizedComputeReceipt
            or type(self.wall_time) is not WallTimeObservation
            or type(self.fixture_resource_observations) is not tuple
            or any(
                type(item) is not ResourceObservation
                for item in self.fixture_resource_observations
            )
            or any(
                item.dimension_id != FIXTURE_RESOURCE_DIMENSION_ID
                or item.unit != FIXTURE_RESOURCE_UNIT
                for item in self.fixture_resource_observations
            )
            or type(self.infrastructure_failed) is not bool
        ):
            raise TypeError("calibration observation is invalid")
        try:
            checked_counts = tuple(
                PolicyWorkCount(item.kind, item.count) for item in self.compute.counts
            )
            checked_compute = NormalizedComputeReceipt(
                self.compute.schema_version,
                self.compute.policy_id,
                self.compute.policy_digest,
                checked_counts,
                self.compute.total_work_units,
            )
            checked_wall = WallTimeObservation(self.wall_time.elapsed_seconds)
            checked_resources = tuple(
                ResourceObservation(item.dimension_id, item.quantity, item.unit)
                for item in self.fixture_resource_observations
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "calibration observation contains invalid nested values"
            ) from exc
        object.__setattr__(self, "compute", checked_compute)
        object.__setattr__(self, "wall_time", checked_wall)
        object.__setattr__(self, "fixture_resource_observations", checked_resources)
        _identifier(self.block_id, "block_id")


@dataclass(frozen=True, slots=True)
class ProfileCalibration:
    """Descriptive p99 values over complete four-arm preflight blocks."""

    profile: AgentProfile
    sample_count: int
    wall_time_p99_seconds: float
    normalized_compute_p99: int
    proposed_wall_time_cap_seconds: int
    proposed_normalized_compute_cap: int
    fixture_units_p99: float

    def __post_init__(self) -> None:
        if (
            type(self) is not ProfileCalibration
            or type(self.profile) is not AgentProfile
            or type(self.sample_count) is not int
            or self.sample_count < 1
            or type(self.wall_time_p99_seconds) is not float
            or not math.isfinite(self.wall_time_p99_seconds)
            or self.wall_time_p99_seconds < 0.0
            or type(self.normalized_compute_p99) is not int
            or self.normalized_compute_p99 < 0
            or type(self.proposed_wall_time_cap_seconds) is not int
            or self.proposed_wall_time_cap_seconds < 0
            or type(self.proposed_normalized_compute_cap) is not int
            or self.proposed_normalized_compute_cap < 0
            or type(self.fixture_units_p99) is not float
            or not math.isfinite(self.fixture_units_p99)
            or self.fixture_units_p99 < 0.0
            or self.proposed_wall_time_cap_seconds
            != math.ceil(1.25 * self.wall_time_p99_seconds)
            or self.proposed_normalized_compute_cap
            != (5 * self.normalized_compute_p99 + 3) // 4
        ):
            raise TypeError("profile calibration is not canonical")


@dataclass(frozen=True, slots=True)
class NonQualifyingPreflightCalibrationReport:
    """Descriptive preflight calibration, structurally unable to claim readiness."""

    authority_ceiling: str
    design_digest: str
    profiles: tuple[ProfileCalibration, ...]
    complete_block_count: int
    failed_block_count: int
    block_infrastructure_failure_rate: float
    block_infrastructure_failure_rate_ceiling: float
    block_infrastructure_failure_rate_within_ceiling: bool

    def __post_init__(self) -> None:
        if (
            type(self) is not NonQualifyingPreflightCalibrationReport
            or self.authority_ceiling != CALIBRATION_AUTHORITY_CEILING
            or type(self.profiles) is not tuple
            or tuple(item.profile for item in self.profiles) != tuple(AgentProfile)
            or any(type(item) is not ProfileCalibration for item in self.profiles)
            or type(self.complete_block_count) is not int
            or self.complete_block_count < 1
            or type(self.failed_block_count) is not int
            or not 0 <= self.failed_block_count <= self.complete_block_count
            or type(self.block_infrastructure_failure_rate) is not float
            or self.block_infrastructure_failure_rate
            != self.failed_block_count / self.complete_block_count
            or self.block_infrastructure_failure_rate_ceiling
            != CALIBRATION_BLOCK_INFRASTRUCTURE_FAILURE_RATE_CEILING
            or type(self.block_infrastructure_failure_rate_within_ceiling) is not bool
            or self.block_infrastructure_failure_rate_within_ceiling
            is not (
                self.block_infrastructure_failure_rate
                <= self.block_infrastructure_failure_rate_ceiling
            )
        ):
            raise TypeError("non-qualifying calibration report is invalid")
        _digest(self.design_digest, "design_digest")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    @property
    def engineering_ready_for_owner_review(self) -> bool:
        """Preflight-only observations can never assert execution readiness."""

        return False

    @property
    def practice_lifecycle_calibrated(self) -> bool:
        return False

    @property
    def preflight_only(self) -> bool:
        return True


# Compatibility alias for the first readiness slice.
NonQualifyingCalibrationReport = NonQualifyingPreflightCalibrationReport


def _nearest_rank_p99(values: tuple[float, ...]) -> float:
    if not values or any(
        type(item) is not float or not math.isfinite(item) or item < 0.0
        for item in values
    ):
        raise TypeError("p99 inputs must be exact non-negative finite floats")
    ordered = sorted(values)
    return ordered[math.ceil(0.99 * len(ordered)) - 1]


def _nearest_rank_p99_int(values: tuple[int, ...]) -> int:
    if not values or any(type(item) is not int or item < 0 for item in values):
        raise TypeError("integer p99 inputs must be exact non-negative integers")
    ordered = sorted(values)
    return ordered[math.ceil(0.99 * len(ordered)) - 1]


def summarize_nonqualifying_preflight_calibration(
    *, design_digest: str, observations: tuple[CalibrationRunObservation, ...]
) -> NonQualifyingPreflightCalibrationReport:
    _digest(design_digest, "design_digest")
    if (
        type(observations) is not tuple
        or not observations
        or any(type(item) is not CalibrationRunObservation for item in observations)
    ):
        raise TypeError("calibration requires exact raw observations")
    try:
        observations = tuple(
            CalibrationRunObservation(
                item.profile,
                item.arm,
                item.block_id,
                item.compute,
                item.wall_time,
                item.fixture_resource_observations,
                item.infrastructure_failed,
            )
            for item in observations
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            "calibration contains structurally invalid observations"
        ) from exc
    identities = tuple((item.profile, item.block_id, item.arm) for item in observations)
    if len(set(identities)) != len(identities):
        raise ValueError("calibration run identity is duplicated")
    blocks = {(item.profile, item.block_id) for item in observations}
    expected = {
        (profile, block_id, arm)
        for profile, block_id in blocks
        for arm in ExperimentalArm
    }
    if set(identities) != expected:
        raise ValueError("calibration requires complete four-arm blocks")

    profiles = []
    for profile in AgentProfile:
        values = tuple(item for item in observations if item.profile is profile)
        if not values:
            raise ValueError("calibration requires every fixture-agent profile")
        wall = _nearest_rank_p99(
            tuple(item.wall_time.elapsed_seconds for item in values)
        )
        compute = _nearest_rank_p99_int(
            tuple(item.compute.total_work_units for item in values)
        )
        fixture = _nearest_rank_p99(
            tuple(
                math.fsum(
                    resource.quantity for resource in item.fixture_resource_observations
                )
                for item in values
            )
        )
        profiles.append(
            ProfileCalibration(
                profile,
                len({item.block_id for item in values}),
                wall,
                compute,
                math.ceil(1.25 * wall),
                (5 * compute + 3) // 4,
                fixture,
            )
        )
    failed_blocks = sum(
        any(
            item.infrastructure_failed
            for item in observations
            if (item.profile, item.block_id) == block
        )
        for block in blocks
    )
    rate = failed_blocks / len(blocks)
    return NonQualifyingPreflightCalibrationReport(
        CALIBRATION_AUTHORITY_CEILING,
        design_digest,
        tuple(profiles),
        len(blocks),
        failed_blocks,
        rate,
        CALIBRATION_BLOCK_INFRASTRUCTURE_FAILURE_RATE_CEILING,
        rate <= CALIBRATION_BLOCK_INFRASTRUCTURE_FAILURE_RATE_CEILING,
    )


# Compatibility alias for the first readiness slice.
summarize_nonqualifying_calibration = summarize_nonqualifying_preflight_calibration


__all__ = (
    "CALIBRATION_AUTHORITY_CEILING",
    "CALIBRATION_BLOCK_INFRASTRUCTURE_FAILURE_RATE_CEILING",
    "EXECUTION_PLAN_SCHEMA_VERSION",
    "FIXTURE_RESOURCE_DIMENSION_ID",
    "FIXTURE_RESOURCE_INSPECTION_UNIT",
    "FIXTURE_RESOURCE_UNIT",
    "OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING",
    "PREFLIGHT_AUTHORITY_CEILING",
    "PROPOSED_PRIMARY_BLOCKS_PER_PROFILE",
    "PROPOSED_RESERVE_BLOCKS_PER_PROFILE",
    "REGISTERED_RNG_ROLES",
    "AdaptivePreflightBuilder",
    "CalibrationRunObservation",
    "FixtureResourceBudgetExceeded",
    "FourArmBlockPlan",
    "FrozenArmArtifact",
    "NonQualifyingCalibrationReport",
    "NonQualifyingPreflightCalibrationReport",
    "NonQualifyingRunPlan",
    "OfficialFixtureSubmission",
    "PreparedCandidate",
    "PreparedFixturePreflight",
    "PreparedFixtureRun",
    "ProfileCalibration",
    "ProposedBlockSchedule",
    "ResearchOperationFailure",
    "arm_hint_artifact_digest",
    "build_nonqualifying_four_arm_block",
    "build_nonqualifying_preflight_arm_artifacts",
    "prepare_nonqualifying_preflight",
    "prepare_nonqualifying_run",
    "read_official_fixture_result",
    "submit_prepared_fixture_run",
    "submit_selected_prepared_fixture_run",
    "summarize_nonqualifying_calibration",
    "summarize_nonqualifying_preflight_calibration",
    "validate_fixture_resource_inspection",
)
