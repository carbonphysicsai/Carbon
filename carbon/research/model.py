"""Exact shared wire values for ``carbon_research_v2``.

The records in this module are protocol vocabulary only.  They do not execute
domain operations, grant provider authority, or compose the full service.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields
from enum import Enum
from types import UnionType
from typing import Annotated, ClassVar, TypeAlias, get_args, get_origin, get_type_hints

from carbon.authoring.refs import (
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    TrainingSupportContractRef,
)
from carbon.construction.refs import (
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    TrainingSamplingPolicyRef,
)
from carbon.fees import StrategyHash
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)
from carbon.resource_policy.refs import (
    ObservedResourceReceiptRef,
    ResearchResourcePolicyRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
)

from .errors import ResearchServiceError
from .refs import (
    RESEARCH_CANONICALIZATION_PROFILE,
    RESEARCH_SCHEMA_VERSION,
    ChallengeInfoRef,
    CompilerEnvironmentRef,
    DisclosurePolicyRef,
    InteractionManifestRef,
    MockScaffoldRef,
    PracticePackRef,
    PracticeScopeStatementRef,
    PriorAlignmentRef,
    PriorChannel,
    PriorChannelRef,
    PriorIndexSnapshotRef,
    PriorPackRef,
    PriorPolicyBundleRef,
    PriorPublicationReceiptRef,
    PublicAggregatePublicationRef,
    PublicEstimandRef,
    PublicMethodArtifactRef,
    PublicMethodResourceCodebookRef,
    PublicPracticeTestRef,
    PublicScaffoldCatalogRef,
    PublicScorePolicyRef,
    PublicSearchScopeRef,
    ResearchReceiptRef,
    ResearchTaskId,
    ResourceForecastRef,
    StrategyCompilationRef,
    StrategySchemaRef,
    TestOnlyPriorAuthorizationReceiptRef,
    ValidationResultRef,
)

UInt64 = Annotated[int, "uint64"]
Int64 = Annotated[int, "int64"]
TrainingStrategy: TypeAlias = dict[str, object]

RESEARCH_NAMESPACE = "carbon_research_v2"
OFFICIAL_V1_NAMESPACE = "carbon_protocol_v1"


class ForbiddenControlField(ValueError):
    """Internal construction signal for a prohibited nested control field."""


class ResearchOperation(str, Enum):
    GET_CHALLENGE_INFO = "get_challenge_info"
    GET_INTERACTION_MANIFEST = "get_interaction_manifest"
    GET_PRIOR = "get_prior"
    GET_MOCK_SCAFFOLD = "get_mock_scaffold"
    DRY_VALIDATE = "dry_validate"
    COMPILE_STRATEGY = "compile_strategy"
    INSPECT_PRIOR_ALIGNMENT = "inspect_prior_alignment"
    INSPECT_RESOURCES = "inspect_resources"
    FORECAST_RESOURCES = "forecast_resources"
    START_RESEARCH_TASK = "start_research_task"
    GET_RESEARCH_RESULT = "get_research_result"
    CANCEL_RESEARCH_TASK = "cancel_research_task"


SUPPORTED_OPERATIONS = tuple(operation.value for operation in ResearchOperation)
OFFICIAL_V1_OPERATIONS = ("submit", "get_submission_result")


class ReplyStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"


class DisclosureClass(str, Enum):
    PUBLIC_RESEARCH = "PUBLIC_RESEARCH"


class PriorLookupStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class PriorPublicationClass(str, Enum):
    TEST_ONLY = "TEST_ONLY"
    BOOTSTRAP_PUBLIC = "BOOTSTRAP_PUBLIC"
    LEARNED_PUBLIC = "LEARNED_PUBLIC"


class PriorGuidanceKind(str, Enum):
    STEER = "STEER"
    AVOID = "AVOID"
    EXPLORE = "EXPLORE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PriorAction(str, Enum):
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"
    INCREASE_CATALOG_BAND = "INCREASE_CATALOG_BAND"
    DECREASE_CATALOG_BAND = "DECREASE_CATALOG_BAND"
    SUBSTITUTE = "SUBSTITUTE"
    COMPARE = "COMPARE"


class OutcomeDirection(str, Enum):
    IMPROVE = "IMPROVE"
    DEGRADE = "DEGRADE"
    MIXED = "MIXED"
    UNRESOLVED = "UNRESOLVED"


class CounterevidenceFinding(str, Enum):
    NULL = "NULL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class EvidenceOrigin(str, Enum):
    SYNTHETIC_TEST_FIXTURE = "synthetic_test_fixture"
    CURATED_PUBLIC_SCIENCE = "curated_public_science"
    QUALIFIED_OFFICIAL_AGGREGATE = "qualified_official_aggregate"


class EpistemicType(str, Enum):
    OBSERVED = "observed"
    PREDICTIVE = "predictive"
    CAUSAL_CANDIDATE = "causal_candidate"
    EXPERIMENTALLY_SUPPORTED = "experimentally_supported"


class EvidenceBand(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    UNKNOWN = "UNKNOWN"


class PublicFindingEvidenceClass(str, Enum):
    PUBLIC_OBSERVATIONAL = "PUBLIC_OBSERVATIONAL"
    PUBLIC_DERIVED = "PUBLIC_DERIVED"
    TEST_ONLY = "TEST_ONLY"


class PriorAlignmentStatus(str, Enum):
    ALIGNED = "ALIGNED"
    PARTIAL = "PARTIAL"
    NOT_ALIGNED = "NOT_ALIGNED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ResearchTaskState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED_INFRA = "FAILED_INFRA"
    CANCELLED = "CANCELLED"


class ResearchTaskKind(str, Enum):
    RECONSTRUCTION_REHEARSAL = "RECONSTRUCTION_REHEARSAL"
    PRACTICE = "PRACTICE"
    PAIRED_PRACTICE = "PAIRED_PRACTICE"
    RESOURCE_CALIBRATION = "RESOURCE_CALIBRATION"


class StrategyTaskRole(str, Enum):
    PRIMARY = "PRIMARY"
    BASELINE = "BASELINE"
    INTERVENTION = "INTERVENTION"


class CancellationDisposition(str, Enum):
    ACCEPTED = "ACCEPTED"
    ALREADY_ACCEPTED = "ALREADY_ACCEPTED"
    TOO_LATE = "TOO_LATE"


class InfrastructureFailureClass(str, Enum):
    QUEUE_LOST = "QUEUE_LOST"
    WORKER_LOST = "WORKER_LOST"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    INTERNAL = "INTERNAL"


class _ExactRecord:
    WIRE_NAME: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = WIRE_RECORD_TYPES_BY_NAME.get(self.WIRE_NAME)
        if expected is None or type(self) is not expected:
            raise TypeError("wire record must use its exact nominal type")
        _validate_declared_fields(self)
        _validate_semantics(self)


WIRE_RECORD_TYPES_BY_NAME: dict[str, type[_ExactRecord]] = {}
WIRE_RECORD_NAMES_BY_TYPE: dict[type[object], str] = {}


def wire_record(name: str):
    def decorate(cls: type[_ExactRecord]) -> type[_ExactRecord]:
        wrapped = dataclass(frozen=True, slots=True)(cls)
        wrapped.WIRE_NAME = name
        WIRE_RECORD_TYPES_BY_NAME[name] = wrapped
        WIRE_RECORD_NAMES_BY_TYPE[wrapped] = name
        return wrapped

    return decorate


def _validate_annotation(value: object, annotation: object, field_name: str) -> None:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        marker = args[1]
        if type(value) is not int:
            raise TypeError(f"{field_name} must be an exact integer")
        if marker == "uint64" and not 0 <= value <= (1 << 64) - 1:
            raise ValueError(f"{field_name} is outside UInt64")
        if marker == "int64" and not -(1 << 63) <= value <= (1 << 63) - 1:
            raise ValueError(f"{field_name} is outside Int64")
        return
    if annotation is object:
        return
    if annotation is type(None):
        if value is not None:
            raise TypeError(f"{field_name} must be NONE")
        return
    if origin in (UnionType, __import__("typing").Union):
        if not any(_annotation_matches(value, member) for member in args):
            raise TypeError(f"{field_name} has the wrong union member")
        return
    if origin is tuple:
        if type(value) is not tuple:
            raise TypeError(f"{field_name} must be an exact tuple")
        if len(value) > 4_096:
            raise ValueError(f"{field_name} exceeds the tuple bound")
        member = args[0]
        for item in value:
            _validate_annotation(item, member, field_name)
        return
    if origin is dict:
        if type(value) is not dict:
            raise TypeError(f"{field_name} must be an exact Strategy object")
        _validate_strategy(value)
        return
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if type(value) is not annotation:
            raise TypeError(f"{field_name} must use its exact closed enum")
        return
    if annotation in (str, bool, int, float, bytes):
        if type(value) is not annotation:
            raise TypeError(f"{field_name} has the wrong exact scalar type")
        if annotation is str and len(value.encode("utf-8", errors="strict")) > 16_384:
            raise ValueError(f"{field_name} exceeds the text bound")
        if annotation is float and not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return
    if isinstance(annotation, type) and type(value) is not annotation:
        raise TypeError(f"{field_name} must use exact {annotation.__name__}")
    if annotation is ChallengeKey:
        if len(value.challenge_id.encode("utf-8")) > 256:
            raise ValueError("Challenge identifier exceeds the v2 bound")
        if len(value.version.encode("utf-8")) > 128:
            raise ValueError("Challenge version exceeds the v2 bound")


def _annotation_matches(value: object, annotation: object) -> bool:
    try:
        _validate_annotation(value, annotation, "union")
    except (TypeError, ValueError, UnicodeError):
        return False
    return True


def _validate_declared_fields(value: _ExactRecord) -> None:
    hints = get_type_hints(type(value), include_extras=True)
    for field in fields(value):
        _validate_annotation(getattr(value, field.name), hints[field.name], field.name)


def _validate_strategy(value: dict[str, object]) -> None:
    active: set[int] = set()
    stack: list[tuple[object, int, bool]] = [(value, 0, False)]
    while stack:
        current, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(current))
            continue
        if depth > 32:
            raise ValueError("Strategy exceeds the v2 nesting bound")
        kind = type(current)
        if kind in (dict, list):
            if id(current) in active:
                raise ValueError("Strategy contains a cycle")
            active.add(id(current))
            stack.append((current, depth, True))
            if kind is dict:
                items = list(dict.items(current))
                if len(items) > 4_096:
                    raise ValueError("Strategy object exceeds the v2 bound")
                for key, child in reversed(items):
                    if type(key) is not str:
                        raise TypeError("Strategy keys must be exact text")
                    if len(key.encode("utf-8", errors="strict")) > 16_384:
                        raise ValueError("Strategy key exceeds the v2 text bound")
                    normalized = re.sub(r"[-_ ]+", "", key).casefold()
                    if normalized in _FORBIDDEN_CONTROL_FORMS:
                        raise ForbiddenControlField(
                            "Strategy contains a forbidden control field"
                        )
                    stack.append((child, depth + 1, False))
            else:
                if len(current) > 4_096:
                    raise ValueError("Strategy list exceeds the v2 bound")
                stack.extend((child, depth + 1, False) for child in reversed(current))
        elif current is None or kind in (bool, int, str):
            if kind is int and not -(1 << 63) <= current <= (1 << 63) - 1:
                raise ValueError("Strategy integer exceeds Int64")
            if kind is str and len(current.encode("utf-8", errors="strict")) > 16_384:
                raise ValueError("Strategy text exceeds the v2 bound")
        elif kind is float:
            if not math.isfinite(current):
                raise ValueError("Strategy numbers must be finite")
        else:
            raise TypeError("Strategy contains a non-JSON value")


_FORBIDDEN_CONTROL_FORMS = frozenset(
    re.sub(r"[-_ ]+", "", field).casefold()
    for field in (
        "raw_data",
        "custom_data",
        "dataset",
        "data_path",
        "filesystem_path",
        "path",
        "uri",
        "url",
        "seed",
        "seeds",
        "official_seed",
        "P",
        "Q",
        "w",
        "stress_set",
        "reference",
        "truth",
        "gate",
        "scorer",
        "execution_context",
        "context",
        "provider",
        "evidence_class",
        "qualification_label",
        "mode",
        "credential",
        "credentials",
        "key",
        "private_key",
        "signing_key",
        "listener",
        "address",
        "port",
    )
)


def _same_challenge(value: object, challenge: ChallengeKey) -> bool:
    return hasattr(value, "challenge_key") and value.challenge_key == challenge


def _validate_semantics(value: _ExactRecord) -> None:
    if type(value) is ProtocolLimit:
        validate_canonical_identifier(value.name, "limit name")
        if value.value <= 0:
            raise ValueError("protocol limits must be positive")
    elif type(value) is CompilerIdentity:
        validate_canonical_identifier(value.name, "compiler name")
        validate_version(value.version)
        if not is_sha256_digest(value.implementation_digest):
            raise ValueError("compiler digest is invalid")
        if (
            len(value.name.encode("utf-8")) > 128
            or len(value.version.encode("utf-8")) > 128
        ):
            raise ValueError("compiler identity exceeds the v2 identifier bound")
    elif type(value) is ChallengeInfo:
        if value.schema_version != RESEARCH_SCHEMA_VERSION:
            raise ValueError("ChallengeInfo requires schema 2.0")
        if value.challenge_version != value.challenge_key.version:
            raise ValueError("challenge version conflicts with ChallengeKey")
        if value.disclosure_class is not DisclosureClass.PUBLIC_RESEARCH:
            raise ValueError("ChallengeInfo must use PUBLIC_RESEARCH")
        _require_challenge_refs(value, value.challenge_key, fields(value)[3:10])
    elif type(value) is InteractionManifest:
        if value.schema_version != RESEARCH_SCHEMA_VERSION:
            raise ValueError("InteractionManifest requires schema 2.0")
        _require_challenge_refs(value, value.challenge_key, fields(value)[2:])
        if value.supported_operations != SUPPORTED_OPERATIONS:
            raise ValueError("manifest operation vocabulary or order differs")
        if value.limits != PROTOCOL_LIMITS:
            raise ValueError("manifest limits differ from the ratified bounds")
        if value.capability_labels not in ((), ("TEST_ONLY_FIXTURE_PRIOR",)):
            raise ValueError("manifest capability labels are invalid")
        digests = tuple(
            ref.content_digest for ref in value.method_resource_codebook_refs
        )
        if digests != tuple(sorted(digests)) or len(set(digests)) != len(digests):
            raise ValueError("codebook refs must be uniquely digest-sorted")
        practice = tuple(ref.content_digest for ref in value.practice_pack_refs)
        if practice != tuple(sorted(practice)) or len(set(practice)) != len(practice):
            raise ValueError("practice refs must be uniquely digest-sorted")
        if (
            len(value.method_resource_codebook_refs) > 256
            or len(value.practice_pack_refs) > 256
        ):
            raise ValueError("manifest catalog tuple exceeds the v2 bound")
    elif type(value) is ResourceLineItem:
        if len(value.confidence_band) != 2 or value.quantity < 0.0:
            raise ValueError("resource quantity must be non-negative")
        if (
            value.confidence_band[0] < 0.0
            or value.confidence_band[0] > value.confidence_band[1]
        ):
            raise ValueError("resource confidence band is invalid")
    elif type(value) is ResourceForecast:
        if (
            len(value.total_wall_seconds_band) != 2
            or value.total_wall_seconds_band[0] < 0.0
            or value.total_wall_seconds_band[0] > value.total_wall_seconds_band[1]
        ):
            raise ValueError("forecast wall-time band is invalid")
        if len(value.line_items) > 128 or len(value.limitations) > 64:
            raise ValueError("resource forecast exceeds the v2 bound")
    elif type(value) in (CompileIssue, ValidationIssue, AlignmentIssue):
        if len(value.path) > 32:
            raise ValueError("issue path exceeds the v2 bound")
    elif type(value) is DryValidationResult:
        if value.valid != (not value.issues):
            raise ValueError("dry-validation validity conflicts with issues")
        if len(value.issues) > 256:
            raise ValueError("validation issue tuple exceeds the v2 bound")
    elif type(value) is CompileStrategyResult:
        present = (
            value.strategy_hash,
            value.training_sampling_policy_ref,
            value.resolved_plan_ref,
            value.compilation_ref,
        )
        if value.accepted != (not value.issues) or value.accepted != all(
            item is not None for item in present
        ):
            raise ValueError("compile result presence invariant is violated")
        if not value.accepted and any(item is not None for item in present):
            raise ValueError("rejected compilation must carry no identities")
        if len(value.issues) > 256:
            raise ValueError("compile issue tuple exceeds the v2 bound")
    elif type(value) is Progress and value.completed_units > value.total_units:
        raise ValueError("progress completed units exceed total units")
    elif type(value) is GetPriorRequest:
        if type(value.selector) is ExactPriorSelector and not _same_challenge(
            value.selector.prior_pack_ref, value.challenge_key
        ):
            raise ValueError("prior selector has a Challenge mismatch")
    elif type(value) is GetMockScaffoldRequest:
        _require_request_refs(
            value.challenge_key,
            value.training_support_ref,
            value.prior_pack_ref,
        )
    elif type(value) is CompileStrategyRequest:
        _require_request_refs(
            value.challenge_key,
            value.expected_training_support_ref,
        )
    elif type(value) is InspectPriorAlignmentRequest:
        _require_request_refs(value.challenge_key, value.prior_pack_ref)
    elif type(value) is InspectResourcesRequest:
        _require_request_refs(value.challenge_key, value.resource_policy_ref)
    elif type(value) is ForecastResourcesRequest:
        _require_request_refs(value.challenge_key, value.resource_policy_ref)
        if not 1 <= value.forecast_horizon_seconds <= 604_800:
            raise ValueError("forecast horizon is outside 1..604800")
    elif type(value) is GetResearchResultRequest and value.poll_sequence > 9_999:
        raise ValueError("poll sequence is outside 0..9999")
    elif type(value) is StartResearchTaskRequest:
        _validate_request_token(value.idempotency_key, "idempotency_key")
        _require_request_refs(
            value.challenge_key,
            value.training_support_ref,
            value.resource_policy_ref,
            value.requested_resource_class_ref,
            value.practice_scope_ref,
        )
        if type(value.prior_selector) is ExactPriorSelector:
            _require_request_refs(
                value.challenge_key,
                value.prior_selector.prior_pack_ref,
            )
    elif type(value) is CancelResearchTaskRequest:
        _validate_request_token(value.cancellation_id, "cancellation_id")
    elif type(value) is PublicResearchFinding:
        if len(value.claim.encode("utf-8")) > 4_096 or len(value.limitations) > 64:
            raise ValueError("public finding exceeds the v2 disclosure bound")
    elif type(value) is PriorIntervention:
        for field_name in ("surface_id", "baseline_ref", "from_ref", "to_ref"):
            field_value = getattr(value, field_name)
            if field_value is not None:
                validate_canonical_identifier(field_value, field_name)
        present = tuple(
            getattr(value, field_name) is not None
            for field_name in ("baseline_ref", "from_ref", "to_ref")
        )
        expected = {
            PriorAction.ENABLE: (True, False, False),
            PriorAction.DISABLE: (True, False, False),
            PriorAction.INCREASE_CATALOG_BAND: (False, True, True),
            PriorAction.DECREASE_CATALOG_BAND: (False, True, True),
            PriorAction.SUBSTITUTE: (False, True, True),
            PriorAction.COMPARE: (True, False, True),
        }[value.action]
        if present != expected:
            raise ValueError("prior intervention refs conflict with its action")
    elif type(value) is PriorScope:
        for refs in (
            value.backbone_refs,
            value.context_refs,
            value.resource_class_refs,
        ):
            if not 1 <= len(refs) <= 64:
                raise ValueError("prior scope tuples require 1..64 refs")
        for field_name, refs in (
            ("backbone_refs", value.backbone_refs),
            ("context_refs", value.context_refs),
        ):
            for ref in refs:
                validate_canonical_identifier(ref, field_name)
            if "ALL_REGISTERED_PUBLIC_CONTEXTS" in refs and refs != (
                "ALL_REGISTERED_PUBLIC_CONTEXTS",
            ):
                raise ValueError("universal public context must be an exact singleton")
    elif type(value) is PriorExpectedOutcome:
        if value.effect_magnitude_band is not None:
            validate_canonical_identifier(
                value.effect_magnitude_band, "effect_magnitude_band"
            )
    elif type(value) is PriorEvidence:
        _validate_code_tuples(
            value.selection_bias_codes,
            value.caveat_codes,
        )
    elif type(value) is CounterevidenceEntry:
        _validate_code_tuples(
            value.applicability_codes,
            value.limitation_codes,
            value.caveat_codes,
        )
    elif type(value) is CounterevidenceEntries:
        if not 1 <= len(value.entries) <= 64:
            raise ValueError("counterevidence requires 1..64 entries")
    elif type(value) is PriorFalsification:
        if (
            len(value.public_practice_test_refs) > 64
            or len(value.public_method_artifact_refs) > 64
        ):
            raise ValueError("falsification refs exceed the v2 bound")
    elif type(value) is PriorProvenance:
        if not 1 <= len(value.public_aggregate_publication_refs) <= 64:
            raise ValueError("prior provenance requires 1..64 refs")
    elif type(value) is PriorGuidanceItem:
        validate_canonical_identifier(value.item_id, "item_id")
        if not 1 <= len(value.expected_outcomes) <= 64:
            raise ValueError("prior item requires 1..64 expected outcomes")
    elif type(value) is ResearchTaskBindings:
        challenge = value.challenge_info_ref.challenge_key
        _require_request_refs(
            challenge,
            value.interaction_manifest_ref,
            value.training_support_ref,
            value.prior_index_snapshot_ref,
            value.prior_pack_ref,
            value.resource_policy_ref,
            value.requested_resource_class_ref,
            value.practice_scope_ref,
        )
        for binding in value.strategy_bindings:
            _require_request_refs(
                challenge,
                binding.training_sampling_policy_ref,
                binding.resolved_plan_ref,
            )
        expected_roles = {
            ResearchTaskKind.RECONSTRUCTION_REHEARSAL: (StrategyTaskRole.PRIMARY,),
            ResearchTaskKind.PRACTICE: (StrategyTaskRole.PRIMARY,),
            ResearchTaskKind.PAIRED_PRACTICE: (
                StrategyTaskRole.BASELINE,
                StrategyTaskRole.INTERVENTION,
            ),
            ResearchTaskKind.RESOURCE_CALIBRATION: (StrategyTaskRole.PRIMARY,),
        }[value.task_kind]
        if tuple(binding.role for binding in value.strategy_bindings) != expected_roles:
            raise ValueError("strategy binding roles conflict with the task kind")
        if value.task_kind is ResearchTaskKind.RESOURCE_CALIBRATION:
            if value.practice_scope_ref is not None:
                raise ValueError("resource calibration has no practice scope")
        elif value.practice_scope_ref is None:
            raise ValueError("practice execution requires an exact practice scope")
        if (value.prior_index_snapshot_ref is None) != (value.prior_pack_ref is None):
            raise ValueError("prior index and pack refs must be present together")
    elif type(value) is PriorPack:
        if len(value.items) > 256:
            raise ValueError("PriorPack exceeds the v2 item bound")
        if (
            value.schema_version != RESEARCH_SCHEMA_VERSION
            or value.canonicalization_profile != RESEARCH_CANONICALIZATION_PROFILE
        ):
            raise ValueError("PriorPack uses the wrong v2 schema/profile")
        if not (
            value.evidence_cutoff_epoch
            <= value.publication_epoch
            <= value.activation_epoch
        ):
            raise ValueError("PriorPack epochs are inconsistent")
        if value.channel is PriorChannel.TEST_ONLY_FIXTURE:
            allowed_origins = {EvidenceOrigin.SYNTHETIC_TEST_FIXTURE}
            if value.publication_class is not PriorPublicationClass.TEST_ONLY:
                raise ValueError("fixture prior requires TEST_ONLY publication class")
        elif value.publication_class is PriorPublicationClass.BOOTSTRAP_PUBLIC:
            allowed_origins = {EvidenceOrigin.CURATED_PUBLIC_SCIENCE}
        elif value.publication_class is PriorPublicationClass.LEARNED_PUBLIC:
            allowed_origins = {
                EvidenceOrigin.CURATED_PUBLIC_SCIENCE,
                EvidenceOrigin.QUALIFIED_OFFICIAL_AGGREGATE,
            }
        else:
            raise ValueError("public prior cannot use TEST_ONLY publication class")
        if any(
            item.evidence.evidence_origin not in allowed_origins for item in value.items
        ):
            raise ValueError("prior item origin exceeds its publication ceiling")
        item_ids = tuple(item.item_id for item in value.items)
        if item_ids != tuple(sorted(item_ids)) or len(item_ids) != len(set(item_ids)):
            raise ValueError("prior items must be uniquely item-id sorted")
        _require_challenge_refs(value, value.challenge_key, fields(value)[11:])
    elif type(value) is ResearchReceipt:
        if len(value.public_findings) > 256 or len(value.limitations) > 64:
            raise ValueError("research receipt exceeds the v2 item bound")
        if value.receipt_ref.task_id != value.task_id:
            raise ValueError("research receipt ref binds a different task")
        if value.terminal_state is ResearchTaskState.SUCCEEDED:
            if value.infrastructure_failure_class is not None:
                raise ValueError(
                    "successful receipt cannot carry infrastructure failure"
                )
        elif value.terminal_state is ResearchTaskState.FAILED_INFRA:
            if value.public_findings or value.infrastructure_failure_class is None:
                raise ValueError("infrastructure receipt fields are inconsistent")
        elif value.terminal_state is ResearchTaskState.CANCELLED:
            if value.public_findings or value.infrastructure_failure_class is not None:
                raise ValueError("cancelled receipt fields are inconsistent")
        else:
            raise ValueError("research receipt requires a terminal state")
    elif type(value) is ResearchTaskView:
        if (
            value.challenge_key
            != value.immutable_bindings.challenge_info_ref.challenge_key
        ):
            raise ValueError("task view Challenge conflicts with immutable bindings")
        if value.updated_at_micros < value.created_at_micros:
            raise ValueError("task timestamps must be nondecreasing")
        terminal = value.state in {
            ResearchTaskState.SUCCEEDED,
            ResearchTaskState.FAILED_INFRA,
            ResearchTaskState.CANCELLED,
        }
        if terminal != (value.terminal_receipt is not None):
            raise ValueError("task terminal state and receipt presence disagree")
        if value.terminal_receipt is not None and (
            value.terminal_receipt.task_id != value.task_id
            or value.terminal_receipt.terminal_state is not value.state
            or value.terminal_receipt.immutable_bindings != value.immutable_bindings
        ):
            raise ValueError("task terminal receipt conflicts with the view")
        if value.terminal_receipt is not None and not (
            value.created_at_micros
            <= value.terminal_receipt.completed_at_micros
            <= value.updated_at_micros
        ):
            raise ValueError("terminal receipt time conflicts with task timestamps")
    elif type(value) in (
        DryValidationResult,
        CompileStrategyResult,
        PriorAlignmentResult,
    ):
        if len(value.issues) > 256:
            raise ValueError("issue tuple exceeds the v2 bound")
    elif type(value) in (InspectResourcesResult, ResourceForecast):
        if len(value.line_items) > 128 or len(value.limitations) > 64:
            raise ValueError("resource result exceeds the v2 bound")


_REQUEST_TOKEN = re.compile(r"[A-Za-z0-9._:-]+\Z", re.ASCII)


def _validate_request_token(value: str, field: str) -> None:
    try:
        length = len(value.encode("ascii", errors="strict"))
    except UnicodeError:
        raise ValueError(f"{field} is outside the closed token grammar") from None
    if not 16 <= length <= 128 or _REQUEST_TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is outside the closed token grammar")


def _validate_code_tuples(*values: tuple[str, ...]) -> None:
    for codes in values:
        if len(codes) > 32:
            raise ValueError("prior code tuple exceeds the v2 bound")
        for code in codes:
            validate_canonical_identifier(code, "prior code")


def _require_request_refs(challenge: ChallengeKey, *references: object) -> None:
    for reference in references:
        if reference is not None and not _same_challenge(reference, challenge):
            raise ValueError("request reference has a Challenge mismatch")


def _require_challenge_refs(
    value: object, challenge: ChallengeKey, selected_fields: tuple[object, ...]
) -> None:
    for field in selected_fields:
        item = getattr(value, field.name)
        candidates = item if type(item) is tuple else (item,)
        for candidate in candidates:
            if candidate is None or type(candidate) in (str, ProtocolLimit):
                continue
            if type(candidate) is CompilerIdentity:
                candidate = candidate.environment_ref
            if type(candidate) is NoPriorAvailability:
                continue
            if type(candidate) is AvailablePriorAvailability:
                candidates = (
                    candidate.prior_channel_ref,
                    candidate.prior_policy_bundle_ref,
                )
                for nested in candidates:
                    if not _same_challenge(nested, challenge):
                        raise ValueError(f"{field.name} has a Challenge mismatch")
                continue
            if hasattr(candidate, "challenge_key") and not _same_challenge(
                candidate, challenge
            ):
                raise ValueError(f"{field.name} has a Challenge mismatch")


@wire_record("protocol_limit")
class ProtocolLimit(_ExactRecord):
    name: str
    value: UInt64


@wire_record("compiler_identity")
class CompilerIdentity(_ExactRecord):
    name: str
    version: str
    implementation_digest: str
    environment_ref: CompilerEnvironmentRef


@wire_record("no_prior_availability")
class NoPriorAvailability(_ExactRecord):
    pass


@wire_record("available_prior_availability")
class AvailablePriorAvailability(_ExactRecord):
    prior_channel_ref: PriorChannelRef
    prior_policy_bundle_ref: PriorPolicyBundleRef


PriorAvailability: TypeAlias = NoPriorAvailability | AvailablePriorAvailability


@wire_record("challenge_info")
class ChallengeInfo(_ExactRecord):
    schema_version: str
    challenge_key: ChallengeKey
    challenge_version: str
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    instance_distribution_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    training_support_ref: TrainingSupportContractRef
    measurement_contract_ref: MeasurementContractRef
    public_score_policy_ref: PublicScorePolicyRef
    disclosure_class: DisclosureClass

    def to_ref(self) -> ChallengeInfoRef:
        from .canonical import canonical_digest

        return ChallengeInfoRef(
            self.challenge_key, content_digest=canonical_digest(self)
        )


@wire_record("interaction_manifest")
class InteractionManifest(_ExactRecord):
    schema_version: str
    challenge_key: ChallengeKey
    challenge_info_ref: ChallengeInfoRef
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    instance_distribution_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    training_support_ref: TrainingSupportContractRef
    measurement_contract_ref: MeasurementContractRef
    public_score_policy_ref: PublicScorePolicyRef
    candidate_assembly_ref: CandidateAssemblyContractRef
    strategy_schema_ref: StrategySchemaRef
    parameter_catalog_ref: ParameterCatalogRef
    compiler_identity: CompilerIdentity
    method_resource_codebook_refs: tuple[PublicMethodResourceCodebookRef, ...]
    practice_scope_ref: PracticeScopeStatementRef | None
    practice_pack_refs: tuple[PracticePackRef, ...]
    scaffold_catalog_ref: PublicScaffoldCatalogRef | None
    prior_availability: PriorAvailability
    resource_policy_ref: ResearchResourcePolicyRef
    disclosure_policy_ref: DisclosurePolicyRef
    supported_operations: tuple[str, ...]
    limits: tuple[ProtocolLimit, ...]
    capability_labels: tuple[str, ...]

    def to_ref(self) -> InteractionManifestRef:
        from .canonical import canonical_digest

        return InteractionManifestRef(
            self.challenge_key, content_digest=canonical_digest(self)
        )


@wire_record("compile_issue")
class CompileIssue(_ExactRecord):
    code: str
    path: tuple[str, ...]
    message: str


@wire_record("validation_issue")
class ValidationIssue(_ExactRecord):
    code: str
    path: tuple[str, ...]
    message: str


@wire_record("alignment_issue")
class AlignmentIssue(_ExactRecord):
    code: str
    path: tuple[str, ...]
    message: str


@wire_record("resource_line_item")
class ResourceLineItem(_ExactRecord):
    resource_class_ref: ResourceClassRef
    quantity: float
    unit: str
    confidence_band: tuple[float, ...]


@wire_record("resource_forecast")
class ResourceForecast(_ExactRecord):
    resource_forecast_ref: ResourceForecastRef
    static_assessment_ref: StaticResourceAssessmentRef
    line_items: tuple[ResourceLineItem, ...]
    total_wall_seconds_band: tuple[float, ...]
    limitations: tuple[str, ...]


@wire_record("public_research_finding")
class PublicResearchFinding(_ExactRecord):
    kind: str
    claim: str
    evidence_class: PublicFindingEvidenceClass
    measurement_ref: MeasurementContractRef
    uncertainty_band: tuple[float, ...]
    limitations: tuple[str, ...]


@wire_record("get_challenge_info_request")
class GetChallengeInfoRequest(_ExactRecord):
    challenge_key: ChallengeKey


@wire_record("get_interaction_manifest_request")
class GetInteractionManifestRequest(_ExactRecord):
    challenge_key: ChallengeKey


@wire_record("exact_prior_selector")
class ExactPriorSelector(_ExactRecord):
    prior_pack_ref: PriorPackRef


@wire_record("active_prior_selector")
class ActivePriorSelector(_ExactRecord):
    channel: PriorChannel


@wire_record("no_prior_selector")
class NoPriorSelector(_ExactRecord):
    pass


PriorSelector: TypeAlias = ExactPriorSelector | ActivePriorSelector | NoPriorSelector


@wire_record("get_prior_request")
class GetPriorRequest(_ExactRecord):
    challenge_key: ChallengeKey
    selector: PriorSelector


@wire_record("get_mock_scaffold_request")
class GetMockScaffoldRequest(_ExactRecord):
    challenge_key: ChallengeKey
    training_support_ref: TrainingSupportContractRef
    prior_pack_ref: PriorPackRef | None


@wire_record("dry_validate_request")
class DryValidateRequest(_ExactRecord):
    challenge_key: ChallengeKey
    strategy: TrainingStrategy


@wire_record("compile_strategy_request")
class CompileStrategyRequest(_ExactRecord):
    challenge_key: ChallengeKey
    strategy: TrainingStrategy
    expected_training_support_ref: TrainingSupportContractRef


@wire_record("inspect_prior_alignment_request")
class InspectPriorAlignmentRequest(_ExactRecord):
    challenge_key: ChallengeKey
    strategy: TrainingStrategy
    prior_pack_ref: PriorPackRef


@wire_record("inspect_resources_request")
class InspectResourcesRequest(_ExactRecord):
    challenge_key: ChallengeKey
    strategy: TrainingStrategy
    resource_policy_ref: ResearchResourcePolicyRef


@wire_record("forecast_resources_request")
class ForecastResourcesRequest(_ExactRecord):
    challenge_key: ChallengeKey
    strategy: TrainingStrategy
    resource_policy_ref: ResearchResourcePolicyRef
    forecast_horizon_seconds: UInt64


@wire_record("reconstruction_rehearsal_spec")
class ReconstructionRehearsalSpec(_ExactRecord):
    strategy: TrainingStrategy
    parent_strategy_hash: StrategyHash | None


@wire_record("practice_task_spec")
class PracticeTaskSpec(_ExactRecord):
    strategy: TrainingStrategy
    parent_strategy_hash: StrategyHash | None


@wire_record("paired_practice_task_spec")
class PairedPracticeTaskSpec(_ExactRecord):
    baseline_strategy: TrainingStrategy
    intervention_strategy: TrainingStrategy


@wire_record("resource_calibration_task_spec")
class ResourceCalibrationTaskSpec(_ExactRecord):
    strategy: TrainingStrategy


ResearchTaskSpec: TypeAlias = (
    ReconstructionRehearsalSpec
    | PracticeTaskSpec
    | PairedPracticeTaskSpec
    | ResourceCalibrationTaskSpec
)


@wire_record("start_research_task_request")
class StartResearchTaskRequest(_ExactRecord):
    challenge_key: ChallengeKey
    idempotency_key: str
    task_spec: ResearchTaskSpec
    training_support_ref: TrainingSupportContractRef
    prior_selector: PriorSelector
    resource_policy_ref: ResearchResourcePolicyRef
    requested_resource_class_ref: ResourceClassRef
    practice_scope_ref: PracticeScopeStatementRef | None


@wire_record("get_research_result_request")
class GetResearchResultRequest(_ExactRecord):
    challenge_key: ChallengeKey
    task_id: ResearchTaskId
    poll_sequence: UInt64


@wire_record("cancel_research_task_request")
class CancelResearchTaskRequest(_ExactRecord):
    challenge_key: ChallengeKey
    task_id: ResearchTaskId
    cancellation_id: str


@wire_record("mock_scaffold")
class MockScaffold(_ExactRecord):
    scaffold_ref: MockScaffoldRef
    strategy_template: TrainingStrategy
    limitations: tuple[str, ...]


@wire_record("dry_validation_result")
class DryValidationResult(_ExactRecord):
    valid: bool
    issues: tuple[ValidationIssue, ...]
    validation_result_ref: ValidationResultRef


@wire_record("compile_strategy_result")
class CompileStrategyResult(_ExactRecord):
    accepted: bool
    issues: tuple[CompileIssue, ...]
    strategy_hash: StrategyHash | None
    training_sampling_policy_ref: TrainingSamplingPolicyRef | None
    resolved_plan_ref: ResolvedConstructionPlanRef | None
    compilation_ref: StrategyCompilationRef | None


@wire_record("prior_alignment_result")
class PriorAlignmentResult(_ExactRecord):
    alignment_ref: PriorAlignmentRef
    status: PriorAlignmentStatus
    issues: tuple[AlignmentIssue, ...]


@wire_record("inspect_resources_result")
class InspectResourcesResult(_ExactRecord):
    static_assessment_ref: StaticResourceAssessmentRef
    line_items: tuple[ResourceLineItem, ...]
    limitations: tuple[str, ...]


@wire_record("strategy_task_binding")
class StrategyTaskBinding(_ExactRecord):
    role: StrategyTaskRole
    strategy_hash: StrategyHash
    training_sampling_policy_ref: TrainingSamplingPolicyRef
    resolved_plan_ref: ResolvedConstructionPlanRef


@wire_record("research_task_bindings")
class ResearchTaskBindings(_ExactRecord):
    task_kind: ResearchTaskKind
    challenge_info_ref: ChallengeInfoRef
    interaction_manifest_ref: InteractionManifestRef
    strategy_bindings: tuple[StrategyTaskBinding, ...]
    training_support_ref: TrainingSupportContractRef
    prior_index_snapshot_ref: PriorIndexSnapshotRef | None
    prior_pack_ref: PriorPackRef | None
    resource_policy_ref: ResearchResourcePolicyRef
    requested_resource_class_ref: ResourceClassRef
    practice_scope_ref: PracticeScopeStatementRef | None


@wire_record("progress")
class Progress(_ExactRecord):
    completed_units: UInt64
    total_units: UInt64


@wire_record("research_receipt")
class ResearchReceipt(_ExactRecord):
    receipt_ref: ResearchReceiptRef
    task_id: ResearchTaskId
    terminal_state: ResearchTaskState
    immutable_bindings: ResearchTaskBindings
    public_findings: tuple[PublicResearchFinding, ...]
    observed_resource_receipt_ref: ObservedResourceReceiptRef | None
    infrastructure_failure_class: InfrastructureFailureClass | None
    limitations: tuple[str, ...]
    completed_at_micros: Int64


@wire_record("research_task_view")
class ResearchTaskView(_ExactRecord):
    task_id: ResearchTaskId
    challenge_key: ChallengeKey
    state: ResearchTaskState
    revision: UInt64
    created_at_micros: Int64
    updated_at_micros: Int64
    immutable_bindings: ResearchTaskBindings
    progress: Progress | None
    terminal_receipt: ResearchReceipt | None


@wire_record("start_research_task_result")
class StartResearchTaskResult(_ExactRecord):
    created: bool
    task: ResearchTaskView


@wire_record("get_research_result_result")
class GetResearchResultResult(_ExactRecord):
    task: ResearchTaskView


@wire_record("cancel_research_task_result")
class CancelResearchTaskResult(_ExactRecord):
    task: ResearchTaskView
    disposition: CancellationDisposition


@wire_record("prior_intervention")
class PriorIntervention(_ExactRecord):
    surface_id: str
    action: PriorAction
    baseline_ref: str | None
    from_ref: str | None
    to_ref: str | None


@wire_record("prior_scope")
class PriorScope(_ExactRecord):
    backbone_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    resource_class_refs: tuple[ResourceClassRef, ...]


@wire_record("prior_expected_outcome")
class PriorExpectedOutcome(_ExactRecord):
    public_estimand_ref: PublicEstimandRef
    direction: OutcomeDirection
    effect_magnitude_band: str | None


@wire_record("prior_evidence")
class PriorEvidence(_ExactRecord):
    evidence_origin: EvidenceOrigin
    epistemic_type: EpistemicType
    evidence_strength: EvidenceBand
    uncertainty: EvidenceBand
    stability: EvidenceBand
    replication: EvidenceBand
    coarse_support: EvidenceBand
    contributor_diversity: EvidenceBand
    selection_bias_codes: tuple[str, ...]
    caveat_codes: tuple[str, ...]


@wire_record("counterevidence_entry")
class CounterevidenceEntry(_ExactRecord):
    public_estimand_ref: PublicEstimandRef
    finding: CounterevidenceFinding
    scope: PriorScope
    evidence_origin: EvidenceOrigin
    epistemic_type: EpistemicType
    evidence_strength: EvidenceBand
    uncertainty: EvidenceBand
    replication: EvidenceBand
    applicability_codes: tuple[str, ...]
    limitation_codes: tuple[str, ...]
    caveat_codes: tuple[str, ...]


@wire_record("counterevidence_entries")
class CounterevidenceEntries(_ExactRecord):
    entries: tuple[CounterevidenceEntry, ...]


@wire_record("counterevidence_none_found")
class CounterevidenceNoneFound(_ExactRecord):
    public_search_scope_ref: PublicSearchScopeRef
    evidence_cutoff_epoch: UInt64


Counterevidence: TypeAlias = CounterevidenceEntries | CounterevidenceNoneFound


@wire_record("prior_falsification")
class PriorFalsification(_ExactRecord):
    public_practice_test_refs: tuple[PublicPracticeTestRef, ...]
    public_method_artifact_refs: tuple[PublicMethodArtifactRef, ...]


@wire_record("prior_provenance")
class PriorProvenance(_ExactRecord):
    public_aggregate_publication_refs: tuple[PublicAggregatePublicationRef, ...]


@wire_record("prior_guidance_item")
class PriorGuidanceItem(_ExactRecord):
    item_id: str
    kind: PriorGuidanceKind
    intervention: PriorIntervention
    scope: PriorScope
    expected_outcomes: tuple[PriorExpectedOutcome, ...]
    evidence: PriorEvidence
    counterevidence_and_applicability: Counterevidence
    falsification: PriorFalsification
    provenance: PriorProvenance


@wire_record("prior_pack")
class PriorPack(_ExactRecord):
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    prior_id: str
    prior_version: str
    channel: PriorChannel
    publication_sequence: UInt64
    publication_class: PriorPublicationClass
    evidence_cutoff_epoch: UInt64
    publication_epoch: UInt64
    activation_epoch: UInt64
    interaction_manifest_ref: InteractionManifestRef
    parameter_catalog_ref: ParameterCatalogRef
    prior_policy_bundle_ref: PriorPolicyBundleRef
    builder_version: str
    predecessor_pack_ref: PriorPackRef | None
    items: tuple[PriorGuidanceItem, ...]
    disclosure_policy_ref: DisclosurePolicyRef
    limitations: tuple[str, ...]


@wire_record("public_prior_authorization")
class PublicPriorAuthorization(_ExactRecord):
    receipt_ref: PriorPublicationReceiptRef


@wire_record("fixture_prior_authorization")
class FixturePriorAuthorization(_ExactRecord):
    receipt_ref: TestOnlyPriorAuthorizationReceiptRef


PriorAuthorization: TypeAlias = PublicPriorAuthorization | FixturePriorAuthorization


@wire_record("prior_lookup_result")
class PriorLookupResult(_ExactRecord):
    index_snapshot_ref: PriorIndexSnapshotRef
    prior_pack: PriorPack
    prior_pack_ref: PriorPackRef
    lookup_status: PriorLookupStatus
    authorization: PriorAuthorization


Request: TypeAlias = (
    GetChallengeInfoRequest
    | GetInteractionManifestRequest
    | GetPriorRequest
    | GetMockScaffoldRequest
    | DryValidateRequest
    | CompileStrategyRequest
    | InspectPriorAlignmentRequest
    | InspectResourcesRequest
    | ForecastResourcesRequest
    | StartResearchTaskRequest
    | GetResearchResultRequest
    | CancelResearchTaskRequest
)

Result: TypeAlias = (
    ChallengeInfo
    | InteractionManifest
    | PriorLookupResult
    | MockScaffold
    | DryValidationResult
    | CompileStrategyResult
    | PriorAlignmentResult
    | InspectResourcesResult
    | ResourceForecast
    | StartResearchTaskResult
    | GetResearchResultResult
    | CancelResearchTaskResult
)


@wire_record("service_call")
class ServiceCall(_ExactRecord):
    namespace: str
    operation: str
    request: Request


@wire_record("service_reply")
class ServiceReply(_ExactRecord):
    status: ReplyStatus
    result: Result | ResearchServiceError

    def __post_init__(self) -> None:
        _ExactRecord.__post_init__(self)
        if (self.status is ReplyStatus.ERROR) != (
            type(self.result) is ResearchServiceError
        ):
            raise ValueError("reply status and payload disagree")


PROTOCOL_LIMITS = (
    ProtocolLimit("canonical_call_reply_bytes", 1_048_576),
    ProtocolLimit("canonical_resource_bytes", 8_388_608),
    ProtocolLimit("nesting_depth", 32),
    ProtocolLimit("default_tuple_items", 4_096),
    ProtocolLimit("utf8_field_bytes", 16_384),
    ProtocolLimit("identifier_version_enum_utf8_bytes", 128),
    ProtocolLimit("challenge_identifier_utf8_bytes", 256),
    ProtocolLimit("error_message_utf8_bytes", 1_024),
    ProtocolLimit("error_path_components", 32),
    ProtocolLimit("error_detail_entries", 32),
    ProtocolLimit("manifest_catalog_entries", 256),
    ProtocolLimit("manifest_parameter_entries", 1_024),
    ProtocolLimit("prior_pack_items", 256),
    ProtocolLimit("finding_items_per_terminal_receipt", 256),
    ProtocolLimit("compile_validation_alignment_issues", 256),
    ProtocolLimit("resource_line_items", 128),
    ProtocolLimit("task_polls_per_identity", 10_000),
)


WIRE_RECORD_TYPES = tuple(WIRE_RECORD_NAMES_BY_TYPE)


__all__ = tuple(
    name
    for name, value in globals().items()
    if (
        isinstance(value, type)
        and (
            issubclass(value, (Enum, _ExactRecord))
            if value not in (Enum, _ExactRecord)
            else False
        )
    )
    or name
    in {
        "Int64",
        "OFFICIAL_V1_NAMESPACE",
        "OFFICIAL_V1_OPERATIONS",
        "PROTOCOL_LIMITS",
        "PriorAvailability",
        "PriorAuthorization",
        "PriorSelector",
        "RESEARCH_NAMESPACE",
        "Request",
        "ResearchTaskSpec",
        "Result",
        "SUPPORTED_OPERATIONS",
        "TrainingStrategy",
        "UInt64",
        "WIRE_RECORD_NAMES_BY_TYPE",
        "WIRE_RECORD_TYPES",
        "WIRE_RECORD_TYPES_BY_NAME",
        "CandidateAssemblyContractRef",
        "CandidateOutputContractRef",
        "ChallengeKey",
        "InstanceDistributionContractRef",
        "MeasurementContractRef",
        "ObservedResourceReceiptRef",
        "ParameterCatalogRef",
        "PhysicalSystemSpecRef",
        "ResearchResourcePolicyRef",
        "ResolvedConstructionPlanRef",
        "ResourceClassRef",
        "SamplingPlanRef",
        "StaticResourceAssessmentRef",
        "StrategyHash",
        "TrainingSamplingPolicyRef",
        "TrainingSupportContractRef",
    }
)
