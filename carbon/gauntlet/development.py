"""Runnable, non-qualifying B-E4 development-pilot orchestration.

The module contains the bounded provider wire adapter, deterministic offline
transport, cost admission, durable journal, and sequential campaign runner.
An authenticated, separately persisted development-only authorization may open
the real transport. Nothing here can start calibration or create qualifying
B-E4 evidence.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Protocol, Self

from carbon.construction import CandidateAssemblyContract, ParameterCatalog
from carbon.gauntlet.agents import (
    FIXTURE_CORPUS_DIGEST,
    FIXTURE_METHOD_CORPUS,
    REGISTERED_EFFECTFUL_SURFACES,
    bind_data_only_selection,
)
from carbon.gauntlet.development_authority import (
    ControlledExecutionAdmission,
    DevelopmentApprovalUnavailable,
    _RealExecutionAdmission,
    provider_identity_digest,
)
from carbon.gauntlet.execution import (
    GENERIC_WORKFLOW_STEPS,
    AdaptivePreflightBuilder,
    NonQualifyingRunPlan,
    submit_selected_prepared_fixture_run,
)
from carbon.gauntlet.harness import AgentSession
from carbon.gauntlet.lifecycle import (
    LifecycleResourceAccount,
    NonQualifyingLifecycleError,
    OfficialLifecycleBridge,
    ResearchLifecycleBridge,
)
from carbon.gauntlet.meter import PolicyWorkMeter
from carbon.gauntlet.model import AgentProfile, ExperimentalArm
from carbon.gauntlet.pilot_contract import (
    PilotEvent,
    PilotInteractionState,
    PilotPhase,
    advance_pilot_interaction,
    bounded_provider_deadline_seconds,
    build_offline_provider_payload,
    initial_pilot_interaction,
)
from carbon.mcp import SubmissionResult
from carbon.prior_compat import PrivatePriorProjection
from carbon.research import PriorLookupResult
from carbon.traineval.resolved_fixture import ResolvedFixtureCompletedRun

DEVELOPMENT_AUTHORITY_CEILING = (
    "NONQUALIFYING_DEVELOPMENT_INTEGRATION_ONLY_NO_PILOT_OR_QUALIFICATION_AUTHORITY"
)
DEVELOPMENT_SCHEMA_VERSION = "carbon.be4.development-pilot.v2"
RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
REQUESTED_MODEL = "gpt-5.6-terra"
REQUESTED_SERVICE_TIER = "default"
MODEL_CONTEXT_TOKEN_CEILING = 32_768
PROPOSAL_MAX_OUTPUT_TOKENS = 1_536
SELECTION_MAX_OUTPUT_TOKENS = 512
RUN_INPUT_TOKEN_CEILING = 65_536
RUN_OUTPUT_TOKEN_CEILING = 16_384
DEVELOPMENT_INPUT_TOKEN_CEILING = 2_621_440
DEVELOPMENT_OUTPUT_TOKEN_CEILING = 655_360
DEVELOPMENT_WORST_CASE_COST_USD = Decimal("14.41792")
DEVELOPMENT_APPROVAL_REQUEST_USD = Decimal("14.42")
OVERALL_PROPOSED_PILOT_CEILING_USD = Decimal("98.304")

_DIGEST_DOMAIN = b"carbon.be4.development-pilot.v2\x00"
_MANIFEST_DOMAIN = b"carbon.be4.development-manifest.v2\x00"
_PROVIDER_CALL_DOMAIN = b"carbon.be4.provider-call.v1\x00"
_PROVIDER_RESULT_DOMAIN = b"carbon.be4.provider-result.v1\x00"
_JOURNAL_BINDING_DOMAIN = b"carbon.be4.development-journal-binding.v1\x00"


class DevelopmentPilotError(RuntimeError):
    pass


class ProviderVerifiedFailure(DevelopmentPilotError):
    """A transport owner proved that the request was not executed."""


class ProviderAmbiguousTimeout(DevelopmentPilotError):
    """A dispatched request has no trustworthy execution or billing result."""


class UnresolvedOperationError(DevelopmentPilotError):
    """Restart encountered an operation that cannot safely be replayed."""


class ProviderCallKind(str, Enum):
    PROPOSAL = "PROPOSAL"
    SELECTION = "SELECTION"


class ProviderOutcomeKind(str, Enum):
    STRUCTURED = "STRUCTURED"
    REFUSAL = "REFUSAL"
    TRUNCATED = "TRUNCATED"
    MALFORMED = "MALFORMED"


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise DevelopmentPilotError("pilot value is not canonical JSON") from error


def _digest(domain: bytes, value: object) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _strict_strategy_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "challenge_id",
            "backbone",
            "parameters",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": "1.0"},
            "challenge_id": {"type": "string"},
            "backbone": {"type": "string", "const": "fno"},
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": list(REGISTERED_EFFECTFUL_SURFACES),
                "properties": {
                    item: {"type": "integer", "enum": [1, 2]}
                    for item in REGISTERED_EFFECTFUL_SURFACES
                },
            },
        },
    }


def _response_schema(kind: ProviderCallKind) -> dict[str, object]:
    if kind is ProviderCallKind.PROPOSAL:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "surface_id", "strategy", "reason"],
            "properties": {
                "action": {"type": "string", "enum": ["PROPOSE", "STOP"]},
                "surface_id": {
                    "type": ["string", "null"],
                    "enum": [*REGISTERED_EFFECTFUL_SURFACES, None],
                },
                "strategy": {"anyOf": [_strict_strategy_schema(), {"type": "null"}]},
                "reason": {"type": ["string", "null"]},
            },
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "candidate_id", "reason"],
        "properties": {
            "action": {"type": "string", "enum": ["SELECT", "STOP"]},
            "candidate_id": {"type": ["string", "null"]},
            "reason": {"type": ["string", "null"]},
        },
    }


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int
    cache_write_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int

    def __post_init__(self) -> None:
        values = (
            self.input_tokens,
            self.cache_write_input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
            self.reasoning_tokens,
        )
        if (
            type(self) is not ProviderUsage
            or any(type(value) is not int or value < 0 for value in values)
            or self.cache_write_input_tokens + self.cached_input_tokens
            > self.input_tokens
            or self.reasoning_tokens > self.output_tokens
        ):
            raise TypeError("provider usage is invalid")

    @property
    def cost_usd(self) -> Decimal:
        standard = (
            self.input_tokens - self.cache_write_input_tokens - self.cached_input_tokens
        )
        return (
            Decimal(standard) * Decimal("2.0")
            + Decimal(self.cache_write_input_tokens) * Decimal("2.5")
            + Decimal(self.cached_input_tokens) * Decimal("0.2")
            + Decimal(self.output_tokens) * Decimal("12.0")
        ) / Decimal(1_000_000)

    def to_json(self) -> dict[str, int]:
        return {
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }

    @classmethod
    def from_json(cls, value: object) -> ProviderUsage:
        if type(value) is not dict or set(value) != {
            "cache_write_input_tokens",
            "cached_input_tokens",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
        }:
            raise TypeError("provider usage JSON is invalid")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ProviderConversationTurn:
    """One same-run request/result pair replayed into later model calls."""

    run_id: str
    profile: AgentProfile
    arm: ExperimentalArm
    kind: ProviderCallKind
    payload: dict[str, object]
    result: ProviderResult

    def __post_init__(self) -> None:
        if (
            type(self) is not ProviderConversationTurn
            or type(self.run_id) is not str
            or not self.run_id
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.kind) is not ProviderCallKind
            or type(self.payload) is not dict
            or type(self.result) is not ProviderResult
        ):
            raise TypeError("provider conversation turn is invalid")
        build_offline_provider_payload(self.payload)
        policy = self.payload["frozen_system_and_profile_policy"]
        treatment = self.payload["current_arm_permitted_prior_material"]
        if (
            type(policy) is not dict
            or policy.get("profile") != self.profile.value
            or type(treatment) is not dict
            or treatment.get("arm") != self.arm.value
        ):
            raise ValueError("provider turn does not bind its profile and arm")

    @property
    def user_text(self) -> str:
        value = {
            key: item
            for key, item in self.payload.items()
            if key != "frozen_system_and_profile_policy"
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @property
    def assistant_text(self) -> str:
        return json.dumps(
            {
                "outcome": self.result.outcome.value,
                "structured_output": self.result.structured_output,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class ProviderCall:
    operation_id: str
    run_id: str
    draw_ordinal: int
    kind: ProviderCallKind
    profile: AgentProfile
    arm: ExperimentalArm
    payload: dict[str, object]
    conversation_history: tuple[ProviderConversationTurn, ...]
    deadline_seconds: float
    max_output_tokens: int

    def __post_init__(self) -> None:
        if (
            type(self) is not ProviderCall
            or type(self.operation_id) is not str
            or not self.operation_id
            or type(self.run_id) is not str
            or not self.run_id
            or type(self.draw_ordinal) is not int
            or self.draw_ordinal < 0
            or type(self.kind) is not ProviderCallKind
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.payload) is not dict
            or type(self.conversation_history) is not tuple
            or any(
                type(item) is not ProviderConversationTurn
                for item in self.conversation_history
            )
            or type(self.deadline_seconds) is not float
            or self.deadline_seconds <= 0.0
            or type(self.max_output_tokens) is not int
            or self.max_output_tokens < 1
        ):
            raise TypeError("provider call is invalid")
        build_offline_provider_payload(self.payload)
        policy = self.payload["frozen_system_and_profile_policy"]
        treatment = self.payload["current_arm_permitted_prior_material"]
        if (
            type(policy) is not dict
            or policy.get("profile") != self.profile.value
            or type(treatment) is not dict
            or treatment.get("arm") != self.arm.value
        ):
            raise ValueError("provider call does not bind its profile and arm")
        if any(
            item.run_id != self.run_id
            or item.profile is not self.profile
            or item.arm is not self.arm
            or item.payload["frozen_system_and_profile_policy"]
            != self.payload["frozen_system_and_profile_policy"]
            for item in self.conversation_history
        ):
            raise ValueError("provider history crosses a run or arm boundary")
        if (
            self.input_token_upper_bound + self.max_output_tokens
            > MODEL_CONTEXT_TOKEN_CEILING
        ):
            raise ValueError("provider call exceeds the registered context ceiling")

    @property
    def system_text(self) -> str:
        value = self.payload["frozen_system_and_profile_policy"]
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @property
    def user_text(self) -> str:
        value = {
            key: item
            for key, item in self.payload.items()
            if key != "frozen_system_and_profile_policy"
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def responses_body(self) -> dict[str, object]:
        schema_name = (
            "be4_strategy_proposal"
            if self.kind is ProviderCallKind.PROPOSAL
            else "be4_final_selection"
        )
        input_items = [{"role": "system", "content": self.system_text}]
        for turn in self.conversation_history:
            input_items.extend(
                (
                    {"role": "user", "content": turn.user_text},
                    {"role": "assistant", "content": turn.assistant_text},
                )
            )
        input_items.append({"role": "user", "content": self.user_text})
        return {
            "background": False,
            "input": input_items,
            "max_output_tokens": self.max_output_tokens,
            "model": REQUESTED_MODEL,
            "parallel_tool_calls": False,
            "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
            "reasoning": {"effort": "medium"},
            "service_tier": REQUESTED_SERVICE_TIER,
            "store": False,
            "text": {
                "format": {
                    "name": schema_name,
                    "schema": _response_schema(self.kind),
                    "strict": True,
                    "type": "json_schema",
                },
                "verbosity": "low",
            },
            "tool_choice": "none",
            "tools": [],
        }

    @property
    def input_token_upper_bound(self) -> int:
        # Every BPE token represents at least one input byte; UTF-8 byte count
        # is therefore a conservative tokenizer-independent admission bound.
        return len(_canonical_bytes(self.responses_body()))

    @property
    def content_digest(self) -> str:
        return _digest(
            _PROVIDER_CALL_DOMAIN,
            {
                "arm": self.arm.value,
                "body": self.responses_body(),
                "draw_ordinal": self.draw_ordinal,
                "kind": self.kind.value,
                "operation_id": self.operation_id,
                "profile": self.profile.value,
                "run_id": self.run_id,
            },
        )


def _validate_structured_output(
    kind: ProviderCallKind, value: object
) -> dict[str, object]:
    if type(value) is not dict:
        raise DevelopmentPilotError("structured provider output is not an object")
    if kind is ProviderCallKind.PROPOSAL:
        if set(value) != {"action", "surface_id", "strategy", "reason"}:
            raise DevelopmentPilotError("proposal output shape is not exact")
        action = value["action"]
        if action == "STOP":
            if value["surface_id"] is not None or value["strategy"] is not None:
                raise DevelopmentPilotError("stop output cannot carry a Strategy")
        elif action == "PROPOSE":
            if (
                value["surface_id"] not in REGISTERED_EFFECTFUL_SURFACES
                or type(value["strategy"]) is not dict
            ):
                raise DevelopmentPilotError("proposal output is not a typed Strategy")
        else:
            raise DevelopmentPilotError("proposal action is unsupported")
    else:
        if set(value) != {"action", "candidate_id", "reason"}:
            raise DevelopmentPilotError("selection output shape is not exact")
        action = value["action"]
        if action == "STOP":
            if value["candidate_id"] is not None:
                raise DevelopmentPilotError("selection stop cannot carry a candidate")
        elif action == "SELECT":
            if type(value["candidate_id"]) is not str or not value["candidate_id"]:
                raise DevelopmentPilotError("selection must name an existing candidate")
        else:
            raise DevelopmentPilotError("selection action is unsupported")
    if value.get("reason") is not None and type(value["reason"]) is not str:
        raise DevelopmentPilotError("provider reason must be text or null")
    return dict(value)


@dataclass(frozen=True, slots=True)
class ProviderResult:
    outcome: ProviderOutcomeKind
    request_id: str
    requested_model: str
    returned_model: str
    requested_service_tier: str
    returned_service_tier: str
    started_at_utc: str
    completed_at_utc: str
    usage: ProviderUsage
    structured_output: dict[str, object] | None
    raw_response_digest: str
    raw_response_text: str
    response_envelope: dict[str, object]

    def __post_init__(self) -> None:
        if (
            type(self) is not ProviderResult
            or type(self.outcome) is not ProviderOutcomeKind
            or any(
                type(value) is not str or not value
                for value in (
                    self.request_id,
                    self.requested_model,
                    self.returned_model,
                    self.requested_service_tier,
                    self.returned_service_tier,
                    self.started_at_utc,
                    self.completed_at_utc,
                    self.raw_response_digest,
                    self.raw_response_text,
                )
            )
            or type(self.usage) is not ProviderUsage
            or type(self.structured_output) not in (type(None), dict)
            or type(self.response_envelope) is not dict
        ):
            raise TypeError("provider result is invalid")
        _canonical_bytes(self.response_envelope)
        if self.raw_response_digest != (
            "sha256:"
            + hashlib.sha256(self.raw_response_text.encode("utf-8")).hexdigest()
        ):
            raise ValueError(
                "provider raw response digest does not match retained bytes"
            )
        if (self.outcome is ProviderOutcomeKind.STRUCTURED) != (
            self.structured_output is not None
        ):
            raise ValueError("provider result outcome and content disagree")

    @property
    def content_digest(self) -> str:
        return _digest(_PROVIDER_RESULT_DOMAIN, self.to_json())

    def to_json(self) -> dict[str, object]:
        return {
            "completed_at_utc": self.completed_at_utc,
            "outcome": self.outcome.value,
            "raw_response_digest": self.raw_response_digest,
            "raw_response_text": self.raw_response_text,
            "response_envelope": self.response_envelope,
            "request_id": self.request_id,
            "requested_model": self.requested_model,
            "requested_service_tier": self.requested_service_tier,
            "returned_model": self.returned_model,
            "returned_service_tier": self.returned_service_tier,
            "started_at_utc": self.started_at_utc,
            "structured_output": self.structured_output,
            "usage": self.usage.to_json(),
        }

    @classmethod
    def from_json(cls, value: object) -> ProviderResult:
        if type(value) is not dict or set(value) != {
            "completed_at_utc",
            "outcome",
            "raw_response_digest",
            "raw_response_text",
            "response_envelope",
            "request_id",
            "requested_model",
            "requested_service_tier",
            "returned_model",
            "returned_service_tier",
            "started_at_utc",
            "structured_output",
            "usage",
        }:
            raise TypeError("provider result JSON is invalid")
        return cls(
            ProviderOutcomeKind(value["outcome"]),
            value["request_id"],
            value["requested_model"],
            value["returned_model"],
            value["requested_service_tier"],
            value["returned_service_tier"],
            value["started_at_utc"],
            value["completed_at_utc"],
            ProviderUsage.from_json(value["usage"]),
            value["structured_output"],
            value["raw_response_digest"],
            value["raw_response_text"],
            value["response_envelope"],
        )  # type: ignore[arg-type]


class ProviderTransport(Protocol):
    def dispatch(self, call: ProviderCall) -> ProviderResult: ...


class DeterministicOfflineTransport:
    """Seed-free deterministic transport used only for integration evidence."""

    __slots__ = ("_calls", "_faults")

    def __init__(self, faults: Mapping[str, str] | None = None) -> None:
        if faults is not None and not isinstance(faults, Mapping):
            raise TypeError("offline faults must be an operation mapping")
        self._faults = dict(faults or {})
        self._calls: list[str] = []

    @property
    def dispatched_operation_ids(self) -> tuple[str, ...]:
        return tuple(self._calls)

    def dispatch(self, call: ProviderCall) -> ProviderResult:
        if type(call) is not ProviderCall:
            raise TypeError("offline transport requires an exact provider call")
        self._calls.append(call.operation_id)
        fault = self._faults.get(call.operation_id)
        if fault == "VERIFIED_FAILURE":
            raise ProviderVerifiedFailure("offline verified provider failure")
        if fault == "AMBIGUOUS_TIMEOUT":
            raise ProviderAmbiguousTimeout("offline ambiguous provider timeout")
        # Fixed timestamps make the offline integration transcript replayable;
        # they are explicitly not provider timing measurements.
        second = call.draw_ordinal % 60
        started = f"2026-09-09T00:00:{second:02d}Z"
        if fault in {"REFUSAL", "TRUNCATED", "MALFORMED"}:
            outcome = ProviderOutcomeKind(fault)
            structured: dict[str, object] | None = None
        elif fault == "EXPLICIT_STOP":
            outcome = ProviderOutcomeKind.STRUCTURED
            structured = (
                {
                    "action": "STOP",
                    "surface_id": None,
                    "strategy": None,
                    "reason": "offline explicit stop",
                }
                if call.kind is ProviderCallKind.PROPOSAL
                else {
                    "action": "STOP",
                    "candidate_id": None,
                    "reason": "offline explicit stop",
                }
            )
        else:
            outcome = ProviderOutcomeKind.STRUCTURED
            structured = self._structured(call)
            if fault == "INVALID_STRATEGY" and call.kind is ProviderCallKind.PROPOSAL:
                assert structured["action"] == "PROPOSE"
                invalid = json.loads(json.dumps(structured["strategy"]))
                invalid["challenge_id"] = "not-the-registered-challenge"
                structured["strategy"] = invalid
        body = {
            "operation_id": call.operation_id,
            "outcome": outcome.value,
            "structured_output": structured,
        }
        input_tokens = max(1, len(_canonical_bytes(call.responses_body())) // 4)
        output_tokens = max(1, len(_canonical_bytes(body)) // 4)
        raw_response_text = _canonical_bytes(body).decode("ascii")
        return ProviderResult(
            outcome,
            f"offline-{hashlib.sha256(call.operation_id.encode()).hexdigest()[:24]}",
            REQUESTED_MODEL,
            REQUESTED_MODEL,
            REQUESTED_SERVICE_TIER,
            REQUESTED_SERVICE_TIER,
            started,
            f"2026-09-09T00:00:{second:02d}.001Z",
            ProviderUsage(input_tokens, 0, 0, output_tokens, output_tokens // 3),
            structured,
            "sha256:" + hashlib.sha256(raw_response_text.encode("ascii")).hexdigest(),
            raw_response_text,
            body,
        )

    @staticmethod
    def _structured(call: ProviderCall) -> dict[str, object]:
        payload = call.payload
        if call.kind is ProviderCallKind.SELECTION:
            feedback = payload["current_run_permitted_practice_feedback"]
            if type(feedback) is not list or not feedback:
                return {"action": "STOP", "candidate_id": None, "reason": "none"}
            choices = [item for item in feedback if type(item) is dict]
            selected = min(
                choices,
                key=lambda item: (item["comparison_value"], item["candidate_id"]),
            )
            return {
                "action": "SELECT",
                "candidate_id": selected["candidate_id"],
                "reason": "minimum permitted practice comparison",
            }
        facts = payload["public_resource_facts"]
        existing = payload["current_run_existing_candidate_ids"]
        if type(facts) is not dict or type(existing) is not list:
            raise DevelopmentPilotError("offline payload public facts are malformed")
        scaffold = facts.get("scaffold_strategy")
        if type(scaffold) is not dict:
            raise DevelopmentPilotError("offline payload lacks the public scaffold")
        profile_orders = {
            AgentProfile.PLANNER: REGISTERED_EFFECTFUL_SURFACES,
            AgentProfile.CODE_GENERATING: tuple(
                reversed(REGISTERED_EFFECTFUL_SURFACES)
            ),
            AgentProfile.EVOLUTIONARY: (
                REGISTERED_EFFECTFUL_SURFACES[1],
                REGISTERED_EFFECTFUL_SURFACES[0],
                REGISTERED_EFFECTFUL_SURFACES[2],
            ),
            AgentProfile.LITERATURE_GROUNDED: tuple(
                next(
                    surface
                    for surface in REGISTERED_EFFECTFUL_SURFACES
                    if item.surface_keyword in surface
                )
                for item in FIXTURE_METHOD_CORPUS
            ),
            AgentProfile.MINIMALIST: REGISTERED_EFFECTFUL_SURFACES,
        }
        treatment = payload["current_arm_permitted_prior_material"]
        suggested: list[str] = []
        if (
            type(treatment) is dict
            and type(treatment.get("suggested_surfaces")) is list
        ):
            suggested = [
                item
                for item in treatment["suggested_surfaces"]
                if item in REGISTERED_EFFECTFUL_SURFACES
            ]
        order = tuple(dict.fromkeys((*suggested, *profile_orders[call.profile])))
        attempt = len(existing)
        surface = order[attempt % len(order)]
        strategy = json.loads(json.dumps(scaffold))
        parameters = strategy["parameters"]
        assert type(parameters) is dict
        feedback = payload["current_run_permitted_practice_feedback"]
        feedback_offset = len(feedback) if type(feedback) is list else 0
        # Three arm-neutral one-lever configurations exhaust this toy surface.
        # The fourth call deliberately repeats one: Carbon records it as an
        # invalid duplicate before practice, then performs metered selection.
        patterns = (
            (2, 1, 1),
            (1, 2, 1),
            (1, 1, 2),
            (2, 1, 1),
        )
        pattern = patterns[attempt % len(patterns)]
        for index, parameter_surface in enumerate(order):
            parameters[parameter_surface] = pattern[index]
        surface = order[attempt % len(order)]
        return {
            "action": "PROPOSE",
            "surface_id": surface,
            "strategy": strategy,
            "reason": (
                "deterministic offline integration proposal after "
                f"{feedback_offset} permitted feedback results"
            ),
        }


def development_execution_admission_status() -> str:
    """Describe the external inputs still required to issue live authority."""

    return "READY_REQUIRES_AUTHENTICATED_OWNER_ISSUANCE_AND_BOUND_CONFIGURATION"


class OpenAIResponsesTransport:
    """Official Responses adapter guarded by one exact live admission."""

    __slots__ = (
        "_admission",
        "_api_key",
        "_organization_id",
        "_organization_id_digest",
        "_project_id",
        "_project_id_digest",
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        admission: _RealExecutionAdmission | None = None,
    ) -> None:
        if api_key is not None and (type(api_key) is not str or not api_key):
            raise TypeError("provider credential must be non-empty text")
        if project_id is not None and (type(project_id) is not str or not project_id):
            raise TypeError("provider project identity must be non-empty text")
        if organization_id is not None and (
            type(organization_id) is not str or not organization_id
        ):
            raise TypeError("provider organization identity must be non-empty text")
        self._api_key = api_key
        self._project_id = project_id
        self._organization_id = organization_id
        self._admission = admission
        self._project_id_digest = (
            None
            if project_id is None
            else provider_identity_digest(project_id, kind="OPENAI_PROJECT_ID")
        )
        self._organization_id_digest = (
            None
            if organization_id is None
            else provider_identity_digest(
                organization_id, kind="OPENAI_ORGANIZATION_ID"
            )
        )
        if admission is not None and type(admission) is not _RealExecutionAdmission:
            raise DevelopmentApprovalUnavailable(
                "official Responses transport requires an exact live admission"
            )

    def __repr__(self) -> str:
        state = (
            "present" if type(self._admission) is _RealExecutionAdmission else "blocked"
        )
        return f"OpenAIResponsesTransport(<credential-redacted>, admission={state})"

    @staticmethod
    def preview_request(call: ProviderCall) -> dict[str, object]:
        if type(call) is not ProviderCall:
            raise TypeError("request preview requires an exact provider call")
        return call.responses_body()

    def dispatch(self, call: ProviderCall) -> ProviderResult:
        if type(call) is not ProviderCall:
            raise TypeError("Responses transport requires an exact provider call")
        if type(self._admission) is not _RealExecutionAdmission:
            raise DevelopmentApprovalUnavailable(
                development_execution_admission_status()
            )
        if not self._api_key:
            raise DevelopmentApprovalUnavailable("provider credential is unavailable")
        if not self._project_id:
            raise DevelopmentApprovalUnavailable(
                "approved provider project identity is unavailable"
            )
        return self._dispatch(call, endpoint=RESPONSES_ENDPOINT)

    def _dispatch(
        self,
        call: ProviderCall,
        *,
        endpoint: str,
        controlled_admission: ControlledExecutionAdmission | None = None,
    ) -> ProviderResult:
        """Dispatch only after rechecking an exact live or loopback admission.

        The check deliberately lives in the lowest method that can reach the
        network.  Calling this nominally private helper directly therefore
        cannot turn a transport without live authority into a provider client.
        """

        if type(call) is not ProviderCall:
            raise TypeError("Responses transport requires an exact provider call")
        parsed = urllib.parse.urlsplit(endpoint)
        if endpoint == RESPONSES_ENDPOINT:
            if (
                controlled_admission is not None
                or type(self._admission) is not _RealExecutionAdmission
            ):
                raise DevelopmentApprovalUnavailable(
                    "official Responses dispatch requires an exact live admission"
                )
            admission: _RealExecutionAdmission | ControlledExecutionAdmission = (
                self._admission
            )
        elif (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.path == "/v1/responses"
            and type(controlled_admission) is ControlledExecutionAdmission
            and self._admission is None
        ):
            admission = controlled_admission
        else:
            raise DevelopmentApprovalUnavailable(
                "Responses endpoint and admission environment do not match"
            )
        if not self._api_key or not self._project_id:
            raise DevelopmentApprovalUnavailable(
                "provider credential and project identity are unavailable"
            )
        assert self._project_id_digest is not None
        admission.assert_current(
            project_id_digest=self._project_id_digest,
            organization_id_digest=self._organization_id_digest,
        )
        started = _utc_now()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "OpenAI-Project": self._project_id,
        }
        if self._organization_id is not None:
            headers["OpenAI-Organization"] = self._organization_id
        request = urllib.request.Request(
            endpoint,
            data=_canonical_bytes(call.responses_body()),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=call.deadline_seconds
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            # Without a trusted provider usage receipt, even an HTTP error is
            # conservatively ambiguous for billing and is never auto-retried.
            raise ProviderAmbiguousTimeout(
                "provider HTTP outcome is unreconciled"
            ) from error
        except (TimeoutError, OSError) as error:
            raise ProviderAmbiguousTimeout(
                "provider dispatch is unreconciled"
            ) from error
        try:
            raw_response_text = raw.decode("utf-8")
            payload = json.loads(raw_response_text)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ProviderAmbiguousTimeout(
                "provider response is unreconciled"
            ) from error
        return self._parse(call, payload, raw_response_text, started)

    @staticmethod
    def _parse(
        call: ProviderCall, payload: object, raw_response_text: str, started: str
    ) -> ProviderResult:
        if type(payload) is not dict:
            raise ProviderAmbiguousTimeout("provider response shape is unreconciled")
        request_id = payload.get("id")
        model = payload.get("model")
        tier = payload.get("service_tier", REQUESTED_SERVICE_TIER)
        usage_raw = payload.get("usage")
        if (
            type(request_id) is not str
            or type(model) is not str
            or type(tier) is not str
            or type(usage_raw) is not dict
        ):
            raise ProviderAmbiguousTimeout("provider identity or usage is missing")
        input_details = usage_raw.get("input_tokens_details", {})
        output_details = usage_raw.get("output_tokens_details", {})
        if type(input_details) is not dict or type(output_details) is not dict:
            raise ProviderAmbiguousTimeout("provider usage detail is malformed")
        usage_values = (
            usage_raw.get("input_tokens"),
            input_details.get("cache_write_tokens", 0),
            input_details.get("cached_tokens", 0),
            usage_raw.get("output_tokens"),
            output_details.get("reasoning_tokens", 0),
        )
        if any(type(value) is not int or value < 0 for value in usage_values):
            raise ProviderAmbiguousTimeout("provider usage values are malformed")
        try:
            usage = ProviderUsage(*usage_values)
        except TypeError as error:
            raise ProviderAmbiguousTimeout(
                "provider usage relationship is unreconciled"
            ) from error
        status = payload.get("status")
        if status == "incomplete":
            outcome = ProviderOutcomeKind.TRUNCATED
            structured = None
        else:
            output = payload.get("output")
            texts: list[str] = []
            refused = False
            if type(output) is list:
                for item in output:
                    if type(item) is not dict or item.get("type") != "message":
                        continue
                    content = item.get("content")
                    if type(content) is not list:
                        continue
                    for part in content:
                        if type(part) is not dict:
                            continue
                        if part.get("type") == "refusal":
                            refused = True
                        elif (
                            part.get("type") == "output_text"
                            and type(part.get("text")) is str
                        ):
                            texts.append(part["text"])
            if refused:
                outcome = ProviderOutcomeKind.REFUSAL
                structured = None
            else:
                try:
                    decoded = json.loads("".join(texts))
                    structured = _validate_structured_output(call.kind, decoded)
                    outcome = ProviderOutcomeKind.STRUCTURED
                except (DevelopmentPilotError, json.JSONDecodeError):
                    outcome = ProviderOutcomeKind.MALFORMED
                    structured = None
        return ProviderResult(
            outcome,
            request_id,
            REQUESTED_MODEL,
            model,
            REQUESTED_SERVICE_TIER,
            tier,
            started,
            _utc_now(),
            usage,
            structured,
            "sha256:" + hashlib.sha256(raw_response_text.encode("utf-8")).hexdigest(),
            raw_response_text,
            payload,
        )


class ControlledOpenAIResponsesTransport:
    """Loopback-only HTTP adapter with a structurally non-live admission."""

    __slots__ = ("_admission", "_core", "_endpoint")

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        project_id: str,
        organization_id: str | None,
        admission: ControlledExecutionAdmission,
    ) -> None:
        parsed = urllib.parse.urlsplit(endpoint)
        if (
            type(endpoint) is not str
            or parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.path != "/v1/responses"
            or type(admission) is not ControlledExecutionAdmission
        ):
            raise DevelopmentApprovalUnavailable(
                "controlled Responses transport requires an exact loopback fixture"
            )
        self._endpoint = endpoint
        self._admission = admission
        # The official adapter continues to own body/header/parse behavior.
        # Its live admission remains absent; this wrapper calls only its shared
        # HTTP implementation after enforcing the distinct fixture authority.
        self._core = OpenAIResponsesTransport(
            api_key=api_key,
            project_id=project_id,
            organization_id=organization_id,
        )

    def __repr__(self) -> str:
        return "ControlledOpenAIResponsesTransport(loopback-fixture-only)"

    def dispatch(self, call: ProviderCall) -> ProviderResult:
        if type(call) is not ProviderCall:
            raise TypeError("controlled Responses transport requires an exact call")
        assert self._core._project_id_digest is not None
        return self._core._dispatch(
            call,
            endpoint=self._endpoint,
            controlled_admission=self._admission,
        )


@dataclass(frozen=True, slots=True)
class CostSnapshot:
    confirmed_input_tokens: int
    confirmed_output_tokens: int
    reserved_input_tokens: int
    reserved_output_tokens: int
    confirmed_cost_usd: Decimal
    reserved_cost_usd: Decimal

    @property
    def conservative_cost_usd(self) -> Decimal:
        return self.confirmed_cost_usd + self.reserved_cost_usd


class DevelopmentJournal:
    """Small durable operation journal, scoped to one development campaign."""

    __slots__ = ("_connection", "_journal_identity", "_manifest_digest", "path")

    def __init__(self, path: Path, *, manifest_digest: str) -> None:
        if not isinstance(path, Path) or type(manifest_digest) is not str:
            raise TypeError("journal requires an exact path and manifest digest")
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        path.chmod(0o600)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS campaign (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                manifest_digest TEXT NOT NULL,
                started_at_unix REAL NOT NULL,
                journal_identity TEXT,
                authorization_id TEXT,
                execution_request_digest TEXT,
                provider_project_digest TEXT,
                authorization_journal_binding TEXT
            );
            CREATE TABLE IF NOT EXISTS operation (
                operation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                call_digest TEXT NOT NULL,
                call_json TEXT NOT NULL,
                state TEXT NOT NULL,
                reserved_input_tokens INTEGER NOT NULL,
                reserved_output_tokens INTEGER NOT NULL,
                reserved_cost_usd TEXT NOT NULL,
                result_json TEXT,
                confirmed_input_tokens INTEGER NOT NULL DEFAULT 0,
                confirmed_output_tokens INTEGER NOT NULL DEFAULT 0,
                confirmed_cost_usd TEXT NOT NULL DEFAULT '0',
                updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_result (
                run_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                content_digest TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_state (
                run_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                started_at_unix REAL NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            """)
        campaign_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(campaign)")
        }
        for column in (
            "journal_identity",
            "authorization_id",
            "execution_request_digest",
            "provider_project_digest",
            "authorization_journal_binding",
        ):
            if column not in campaign_columns:
                connection.execute(f"ALTER TABLE campaign ADD COLUMN {column} TEXT")
        existing = connection.execute(
            "SELECT manifest_digest, started_at_unix, journal_identity "
            "FROM campaign WHERE singleton = 1"
        ).fetchone()
        journal_identity = "sha256:" + secrets.token_hex(32)
        if existing is None:
            connection.execute(
                "INSERT INTO campaign(singleton, manifest_digest, started_at_unix, "
                "journal_identity) VALUES (1, ?, ?, ?)",
                (manifest_digest, time.time(), journal_identity),
            )
        elif existing[0] != manifest_digest:
            connection.close()
            raise DevelopmentPilotError(
                "journal is bound to a different immutable campaign manifest"
            )
        elif existing[2] is None:
            connection.execute(
                "UPDATE campaign SET journal_identity = ? WHERE singleton = 1 "
                "AND journal_identity IS NULL",
                (journal_identity,),
            )
        elif not _is_digest(existing[2]):
            connection.close()
            raise DevelopmentPilotError("journal identity is invalid")
        else:
            journal_identity = existing[2]
        connection.commit()
        self.path = path
        self._manifest_digest = manifest_digest
        self._journal_identity = journal_identity
        self._connection = connection

    def authorization_binding(self, execution_request_digest: str) -> str:
        """Bind authority to this durable journal instance, not just its path."""

        if not _is_digest(execution_request_digest):
            raise TypeError("journal binding requires an execution request digest")
        return _digest(
            _JOURNAL_BINDING_DOMAIN,
            {
                "campaign_manifest_digest": self._manifest_digest,
                "execution_request_digest": execution_request_digest,
                "journal_identity": self._journal_identity,
            },
        )

    def bind_execution_authorization(
        self,
        *,
        authorization_id: str,
        execution_request_digest: str,
        provider_project_digest: str,
        journal_binding: str,
    ) -> None:
        """Bind one live entitlement before the journal's first dispatch."""

        if (
            type(authorization_id) is not str
            or not authorization_id.startswith(
                ("be4-development-", "fixture-be4-development-")
            )
            or type(execution_request_digest) is not str
            or not _is_digest(execution_request_digest)
            or type(provider_project_digest) is not str
            or not _is_digest(provider_project_digest)
            or journal_binding != self.authorization_binding(execution_request_digest)
        ):
            raise TypeError("journal execution authorization binding is invalid")
        row = self._connection.execute(
            "SELECT authorization_id, execution_request_digest, "
            "provider_project_digest, authorization_journal_binding "
            "FROM campaign WHERE singleton = 1"
        ).fetchone()
        expected = (
            authorization_id,
            execution_request_digest,
            provider_project_digest,
            journal_binding,
        )
        if row == expected:
            return
        if row != (None, None, None, None):
            raise UnresolvedOperationError(
                "journal is already bound to a different execution authorization"
            )
        if self._connection.execute("SELECT 1 FROM operation LIMIT 1").fetchone():
            raise UnresolvedOperationError(
                "authorization cannot be bound after provider intent exists"
            )
        with self._connection:
            changed = self._connection.execute(
                "UPDATE campaign SET authorization_id = ?, "
                "execution_request_digest = ?, provider_project_digest = ?, "
                "authorization_journal_binding = ? "
                "WHERE singleton = 1 AND authorization_id IS NULL AND "
                "execution_request_digest IS NULL AND provider_project_digest IS NULL "
                "AND authorization_journal_binding IS NULL",
                expected,
            ).rowcount
        if changed != 1:
            raise UnresolvedOperationError(
                "journal authorization binding lost its race"
            )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _call_json(call: ProviderCall) -> dict[str, object]:
        return {
            "arm": call.arm.value,
            "body": call.responses_body(),
            "content_digest": call.content_digest,
            "draw_ordinal": call.draw_ordinal,
            "kind": call.kind.value,
            "operation_id": call.operation_id,
            "profile": call.profile.value,
            "run_id": call.run_id,
        }

    def begin_provider_operation(
        self,
        call: ProviderCall,
        *,
        reserved_input_tokens: int,
        reserved_output_tokens: int,
        reserved_cost_usd: Decimal,
    ) -> ProviderResult | None:
        if (
            type(call) is not ProviderCall
            or type(reserved_input_tokens) is not int
            or reserved_input_tokens < 0
            or type(reserved_output_tokens) is not int
            or reserved_output_tokens < 0
            or type(reserved_cost_usd) is not Decimal
            or reserved_cost_usd < 0
        ):
            raise TypeError("provider intent reservation is invalid")
        row = self._connection.execute(
            "SELECT call_digest, state, result_json FROM operation "
            "WHERE operation_id = ?",
            (call.operation_id,),
        ).fetchone()
        if row is not None:
            if row[0] != call.content_digest:
                raise DevelopmentPilotError("operation id was reused with new content")
            if row[1] == "COMPLETED":
                return ProviderResult.from_json(json.loads(row[2]))
            raise UnresolvedOperationError(
                f"operation {call.operation_id} is {row[1]} and cannot be replayed"
            )
        with self._connection:
            self._connection.execute(
                "INSERT INTO operation("
                "operation_id, run_id, call_digest, call_json, state, "
                "reserved_input_tokens, reserved_output_tokens, "
                "reserved_cost_usd, updated_at_utc) "
                "VALUES (?, ?, ?, ?, 'INTENT', ?, ?, ?, ?)",
                (
                    call.operation_id,
                    call.run_id,
                    call.content_digest,
                    _canonical_bytes(self._call_json(call)).decode("ascii"),
                    reserved_input_tokens,
                    reserved_output_tokens,
                    str(reserved_cost_usd),
                    _utc_now(),
                ),
            )
        return None

    def complete_provider_operation(
        self, call: ProviderCall, result: ProviderResult
    ) -> None:
        if type(call) is not ProviderCall or type(result) is not ProviderResult:
            raise TypeError("provider completion requires exact values")
        with self._connection:
            changed = self._connection.execute(
                "UPDATE operation SET state = 'COMPLETED', result_json = ?, "
                "reserved_input_tokens = 0, reserved_output_tokens = 0, "
                "reserved_cost_usd = '0', confirmed_input_tokens = ?, "
                "confirmed_output_tokens = ?, confirmed_cost_usd = ?, "
                "updated_at_utc = ? WHERE operation_id = ? AND call_digest = ? "
                "AND state = 'INTENT'",
                (
                    _canonical_bytes(result.to_json()).decode("ascii"),
                    result.usage.input_tokens,
                    result.usage.output_tokens,
                    str(result.usage.cost_usd),
                    _utc_now(),
                    call.operation_id,
                    call.content_digest,
                ),
            ).rowcount
        if changed != 1:
            raise UnresolvedOperationError("provider completion did not own its intent")

    def mark_provider_failure(self, call: ProviderCall, *, ambiguous: bool) -> None:
        if type(call) is not ProviderCall or type(ambiguous) is not bool:
            raise TypeError("provider failure recording requires exact values")
        state = "UNKNOWN" if ambiguous else "VERIFIED_NOT_EXECUTED"
        release = not ambiguous
        with self._connection:
            changed = self._connection.execute(
                "UPDATE operation SET state = ?, reserved_input_tokens = ?, "
                "reserved_output_tokens = ?, reserved_cost_usd = ?, "
                "updated_at_utc = ? WHERE operation_id = ? AND call_digest = ? "
                "AND state = 'INTENT'",
                (
                    state,
                    0 if release else call.input_token_upper_bound,
                    0 if release else call.max_output_tokens,
                    (
                        "0"
                        if release
                        else str(
                            _worst_case_cost(
                                call.input_token_upper_bound, call.max_output_tokens
                            )
                        )
                    ),
                    _utc_now(),
                    call.operation_id,
                    call.content_digest,
                ),
            ).rowcount
        if changed != 1:
            raise UnresolvedOperationError("provider failure did not own its intent")

    def cost_snapshot(self, *, run_id: str | None = None) -> CostSnapshot:
        query = (
            "SELECT confirmed_input_tokens, confirmed_output_tokens, "
            "reserved_input_tokens, reserved_output_tokens, "
            "confirmed_cost_usd, reserved_cost_usd FROM operation"
        )
        parameters: tuple[object, ...] = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            parameters = (run_id,)
        rows = self._connection.execute(query, parameters).fetchall()
        confirmed_cost = sum((Decimal(row[4]) for row in rows), Decimal(0))
        reserved_cost = sum((Decimal(row[5]) for row in rows), Decimal(0))
        return CostSnapshot(
            sum(int(row[0]) for row in rows),
            sum(int(row[1]) for row in rows),
            sum(int(row[2]) for row in rows),
            sum(int(row[3]) for row in rows),
            confirmed_cost,
            reserved_cost,
        )

    def begin_run(self, run_id: str) -> None:
        """Persist run intent before any Carbon service or provider operation."""

        if type(run_id) is not str or not run_id:
            raise TypeError("run intent requires an exact run id")
        row = self._connection.execute(
            "SELECT state FROM run_state WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is not None:
            if row[0] == "COMPLETED" and self.read_run_result(run_id) is not None:
                return
            raise UnresolvedOperationError(
                f"run {run_id} has incomplete durable state and cannot be replayed"
            )
        with self._connection:
            self._connection.execute(
                "INSERT INTO run_state VALUES (?, 'RUNNING', ?, ?)",
                (run_id, time.time(), _utc_now()),
            )

    def campaign_elapsed_seconds(self) -> float:
        """Return elapsed campaign time from the durable journal origin."""

        row = self._connection.execute(
            "SELECT started_at_unix FROM campaign WHERE singleton = 1"
        ).fetchone()
        if row is None or type(row[0]) not in (int, float):
            raise UnresolvedOperationError("campaign start time is unavailable")
        return max(0.0, time.time() - float(row[0]))

    def run_elapsed_seconds(self, run_id: str) -> float | None:
        """Return durable elapsed time, or ``None`` before run intent exists."""

        if type(run_id) is not str or not run_id:
            raise TypeError("run elapsed lookup requires an exact run id")
        row = self._connection.execute(
            "SELECT started_at_unix FROM run_state WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        if type(row[0]) not in (int, float):
            raise UnresolvedOperationError("run start time is unavailable")
        return max(0.0, time.time() - float(row[0]))

    def has_unresolved_operations(self) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM operation WHERE state IN ('INTENT', 'UNKNOWN') LIMIT 1"
        ).fetchone()
        return row is not None

    def completed_provider_operation_count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM operation WHERE state = 'COMPLETED'"
        ).fetchone()
        assert row is not None
        return int(row[0])

    def provider_operation_summary(self) -> dict[str, object]:
        """Return non-secret durable dispatch and billing state."""

        rows = self._connection.execute(
            "SELECT state, COUNT(*) FROM operation GROUP BY state"
        ).fetchall()
        states = {str(state): int(count) for state, count in rows}
        snapshot = self.cost_snapshot()
        return {
            "confirmed_cost_usd": str(snapshot.confirmed_cost_usd),
            "confirmed_input_tokens": snapshot.confirmed_input_tokens,
            "confirmed_output_tokens": snapshot.confirmed_output_tokens,
            "conservative_cost_usd": str(snapshot.conservative_cost_usd),
            "dispatched_operation_count": sum(states.values()),
            "operation_states": {
                state: states.get(state, 0)
                for state in (
                    "COMPLETED",
                    "INTENT",
                    "UNKNOWN",
                    "VERIFIED_NOT_EXECUTED",
                )
            },
            "reserved_cost_usd": str(snapshot.reserved_cost_usd),
            "reserved_input_tokens": snapshot.reserved_input_tokens,
            "reserved_output_tokens": snapshot.reserved_output_tokens,
        }

    def record_run_result(self, run_id: str, value: dict[str, object]) -> str:
        if type(run_id) is not str or not run_id or type(value) is not dict:
            raise TypeError("run result requires exact JSON data")
        digest = _digest(b"carbon.be4.development-run-result.v1\x00", value)
        encoded = _canonical_bytes(value).decode("ascii")
        with self._connection:
            previous = self._connection.execute(
                "SELECT result_json, content_digest FROM run_result WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if previous is None:
                self._connection.execute(
                    "INSERT INTO run_result VALUES (?, ?, ?, ?)",
                    (run_id, encoded, digest, _utc_now()),
                )
            elif previous != (encoded, digest):
                raise DevelopmentPilotError("completed run identity was rebound")
            state = self._connection.execute(
                "SELECT state FROM run_state WHERE run_id = ?", (run_id,)
            ).fetchone()
            if state is None:
                self._connection.execute(
                    "INSERT INTO run_state VALUES (?, 'COMPLETED', ?, ?)",
                    (run_id, time.time(), _utc_now()),
                )
            elif state[0] == "RUNNING":
                self._connection.execute(
                    "UPDATE run_state SET state = 'COMPLETED', updated_at_utc = ? "
                    "WHERE run_id = ?",
                    (_utc_now(), run_id),
                )
            elif state[0] != "COMPLETED":
                raise UnresolvedOperationError("run completion state is unresolved")
        return digest

    def read_run_result(self, run_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT result_json FROM run_result WHERE run_id = ?", (run_id,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def all_run_results(self) -> tuple[dict[str, object], ...]:
        values = tuple(
            json.loads(row[0])
            for row in self._connection.execute("SELECT result_json FROM run_result")
        )
        return tuple(sorted(values, key=lambda item: int(item["run_ordinal"])))


def _worst_case_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * Decimal("2.5")
        + Decimal(output_tokens) * Decimal("12.0")
    ) / Decimal(1_000_000)


class ProviderDispatcher:
    """Admission and journal wrapper around one exact provider transport."""

    __slots__ = ("_journal", "_transport")

    def __init__(
        self, *, journal: DevelopmentJournal, transport: ProviderTransport
    ) -> None:
        if type(journal) is not DevelopmentJournal or not hasattr(
            transport, "dispatch"
        ):
            raise TypeError("provider dispatcher requires a journal and transport")
        self._journal = journal
        self._transport = transport

    def dispatch(self, call: ProviderCall) -> ProviderResult:
        if type(call) is not ProviderCall:
            raise TypeError("provider dispatcher requires an exact call")
        input_reservation = call.input_token_upper_bound
        output_reservation = call.max_output_tokens
        cost_reservation = _worst_case_cost(input_reservation, output_reservation)
        run = self._journal.cost_snapshot(run_id=call.run_id)
        stage = self._journal.cost_snapshot()
        if (
            run.confirmed_input_tokens + run.reserved_input_tokens + input_reservation
            > RUN_INPUT_TOKEN_CEILING
            or run.confirmed_output_tokens
            + run.reserved_output_tokens
            + output_reservation
            > RUN_OUTPUT_TOKEN_CEILING
            or stage.confirmed_input_tokens
            + stage.reserved_input_tokens
            + input_reservation
            > DEVELOPMENT_INPUT_TOKEN_CEILING
            or stage.confirmed_output_tokens
            + stage.reserved_output_tokens
            + output_reservation
            > DEVELOPMENT_OUTPUT_TOKEN_CEILING
            or stage.conservative_cost_usd + cost_reservation
            > DEVELOPMENT_APPROVAL_REQUEST_USD
        ):
            raise DevelopmentPilotError(
                "provider operation cannot fit the run or development ceiling"
            )
        replay = self._journal.begin_provider_operation(
            call,
            reserved_input_tokens=input_reservation,
            reserved_output_tokens=output_reservation,
            reserved_cost_usd=cost_reservation,
        )
        if replay is not None:
            return replay
        try:
            result = self._transport.dispatch(call)
        except DevelopmentApprovalUnavailable:
            # The local admission boundary fails before network dispatch.
            self._journal.mark_provider_failure(call, ambiguous=False)
            raise
        except ProviderVerifiedFailure:
            self._journal.mark_provider_failure(call, ambiguous=False)
            raise
        except ProviderAmbiguousTimeout:
            self._journal.mark_provider_failure(call, ambiguous=True)
            raise
        except Exception as error:
            self._journal.mark_provider_failure(call, ambiguous=True)
            raise ProviderAmbiguousTimeout(
                "unclassified transport exception is conservatively unresolved"
            ) from error
        self._journal.complete_provider_operation(call, result)
        if (
            result.usage.input_tokens > input_reservation
            or result.usage.output_tokens > output_reservation
            or result.usage.cost_usd > cost_reservation
        ):
            raise DevelopmentPilotError(
                "provider receipt exceeded its per-operation reservation"
            )
        post_run = self._journal.cost_snapshot(run_id=call.run_id)
        post_stage = self._journal.cost_snapshot()
        if (
            post_run.confirmed_input_tokens + post_run.reserved_input_tokens
            > RUN_INPUT_TOKEN_CEILING
            or post_run.confirmed_output_tokens + post_run.reserved_output_tokens
            > RUN_OUTPUT_TOKEN_CEILING
            or post_stage.confirmed_input_tokens + post_stage.reserved_input_tokens
            > DEVELOPMENT_INPUT_TOKEN_CEILING
            or post_stage.confirmed_output_tokens + post_stage.reserved_output_tokens
            > DEVELOPMENT_OUTPUT_TOKEN_CEILING
            or post_stage.conservative_cost_usd > DEVELOPMENT_APPROVAL_REQUEST_USD
        ):
            raise DevelopmentPilotError(
                "provider receipt exceeded its reservation or campaign ceiling"
            )
        return result


_PROFILE_POLICY = {
    AgentProfile.PLANNER: {
        "method": "HYPOTHESIS_TABLE_THEN_MAXIMUM_EXPECTED_INFORMATION_GAIN_FROM_PERMITTED_FEEDBACK",
        "policy_id": "be4_model_planner_policy/2.0",
    },
    AgentProfile.CODE_GENERATING: {
        "method": "EMIT_AND_REVISE_DECLARATIVE_TYPED_STRATEGY_DATA_WITHOUT_EXECUTING_GENERATED_TEXT",
        "policy_id": "be4_model_code_generating_policy/2.0",
    },
    AgentProfile.EVOLUTIONARY: {
        "method": "PARENT_CHILD_MUTATION_LINEAGE_WITH_FEEDBACK_BASED_SURVIVOR_SELECTION",
        "policy_id": "be4_model_evolutionary_policy/2.0",
    },
    AgentProfile.LITERATURE_GROUNDED: {
        "method": "CITE_FROZEN_CORPUS_CHUNKS_AND_UPDATE_HYPOTHESES_FROM_PERMITTED_FEEDBACK",
        "policy_id": "be4_model_literature_grounded_policy/2.0",
    },
    AgentProfile.MINIMALIST: {
        "method": "ONE_PROPOSAL_ATTEMPT_THEN_STOP_INVALID_FIRST_PROPOSAL_GETS_NO_REPLACEMENT_ATTEMPT",
        "policy_id": "be4_model_minimalist_policy/2.0",
    },
}


@dataclass(frozen=True, slots=True)
class DevelopmentTask:
    task_id: str
    cell_id: str
    agent_visible_description: dict[str, object]
    observation_set_digest: str
    candidate_fixture_units: int
    maximum_run_fixture_units: int

    def __post_init__(self) -> None:
        if (
            type(self) is not DevelopmentTask
            or type(self.task_id) is not str
            or not self.task_id
            or type(self.cell_id) is not str
            or not self.cell_id
            or type(self.agent_visible_description) is not dict
            or type(self.observation_set_digest) is not str
            or not self.observation_set_digest.startswith("sha256:")
            or type(self.candidate_fixture_units) is not int
            or self.candidate_fixture_units < 1
            or type(self.maximum_run_fixture_units) is not int
            or self.maximum_run_fixture_units != 9 * self.candidate_fixture_units
        ):
            raise TypeError("development task is invalid")

    @property
    def content_digest(self) -> str:
        return _digest(
            b"carbon.be4.development-task.v1\x00",
            {
                "agent_visible_description": self.agent_visible_description,
                "candidate_fixture_units": self.candidate_fixture_units,
                "cell_id": self.cell_id,
                "maximum_run_fixture_units": self.maximum_run_fixture_units,
                "observation_set_digest": self.observation_set_digest,
                "task_id": self.task_id,
            },
        )


@dataclass(frozen=True, slots=True)
class DevelopmentRunSlot:
    ordinal: int
    run_id: str
    block_id: str
    profile: AgentProfile
    arm: ExperimentalArm
    task_id: str
    task_ordinal: int

    def __post_init__(self) -> None:
        if (
            type(self) is not DevelopmentRunSlot
            or type(self.ordinal) is not int
            or not 0 <= self.ordinal < 40
            or type(self.run_id) is not str
            or not self.run_id
            or type(self.block_id) is not str
            or not self.block_id
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.task_id) is not str
            or not self.task_id
            or type(self.task_ordinal) is not int
            or self.task_ordinal not in (0, 1)
        ):
            raise TypeError("development run slot is invalid")


def proposed_development_schedule(
    tasks: tuple[DevelopmentTask, DevelopmentTask],
) -> tuple[DevelopmentRunSlot, ...]:
    """Return the prospective balanced/interleaved sequential 40-run order."""

    if (
        type(tasks) is not tuple
        or len(tasks) != 2
        or any(type(item) is not DevelopmentTask for item in tasks)
        or tasks[0].task_id == tasks[1].task_id
    ):
        raise TypeError("development schedule requires two exact public tasks")
    blocks = tuple(
        (profile, task_ordinal, task)
        for task_ordinal, task in enumerate(tasks)
        for profile in AgentProfile
    )
    arms = tuple(ExperimentalArm)
    slots: list[DevelopmentRunSlot] = []
    for arm_round in range(len(arms)):
        for block_index, (profile, task_ordinal, task) in enumerate(blocks):
            arm = arms[(arm_round + block_index) % len(arms)]
            block_id = f"be4-development-{profile.value.lower()}-{task.task_id.lower()}"
            run_id = f"{block_id}-{arm.value.lower()}"
            slots.append(
                DevelopmentRunSlot(
                    len(slots),
                    run_id,
                    block_id,
                    profile,
                    arm,
                    task.task_id,
                    task_ordinal,
                )
            )
    if (
        len(slots) != 40
        or len({item.run_id for item in slots}) != 40
        or {(item.profile, item.arm, item.task_id) for item in slots}
        != {
            (profile, arm, task.task_id)
            for profile in AgentProfile
            for arm in ExperimentalArm
            for task in tasks
        }
    ):
        raise DevelopmentPilotError("development schedule is not the exact matrix")
    return tuple(slots)


@dataclass(frozen=True, slots=True)
class DevelopmentCampaignManifest:
    campaign_id: str
    proposal_digest: str
    implementation_digest: str
    artifact_manifest_digest: str
    owner_decisions_digest: str
    tasks: tuple[DevelopmentTask, DevelopmentTask]
    schedule: tuple[DevelopmentRunSlot, ...]
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not DevelopmentCampaignManifest
            or self.campaign_id != "be4-autonomous-development-v2"
            or self.proposal_digest
            != "sha256:86979a14c38239fdad84c1f9fa190fc6a49e70fc31a996ae6ee61e844dfaff31"
            or any(
                type(value) is not str
                or not value.startswith("sha256:")
                or len(value) != 71
                for value in (
                    self.implementation_digest,
                    self.artifact_manifest_digest,
                    self.owner_decisions_digest,
                    self.content_digest,
                )
            )
            or type(self.tasks) is not tuple
            or len(self.tasks) != 2
            or self.schedule != proposed_development_schedule(self.tasks)
            or self.content_digest != _development_manifest_digest(self)
        ):
            raise TypeError("development campaign manifest is invalid")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    def to_json(self) -> dict[str, object]:
        return _development_manifest_value(self, include_digest=True)


def _development_manifest_value(
    value: DevelopmentCampaignManifest, *, include_digest: bool
) -> dict[str, object]:
    result: dict[str, object] = {
        "approval_boundary": {
            "actual_execution_evidence": False,
            "authenticated_five_owner_approval": False,
            "owner_decisions_recorded": True,
            "one_use_execution_authorization": False,
            "paid_provider_execution": False,
        },
        "artifact_manifest_digest": value.artifact_manifest_digest,
        "authority_ceiling": DEVELOPMENT_AUTHORITY_CEILING,
        "budget": {
            "adaptive_logical_calls_per_run": 5,
            "call_wall_seconds": 120,
            "campaign_wall_seconds": 432_000,
            "development_approval_request_usd": str(DEVELOPMENT_APPROVAL_REQUEST_USD),
            "development_input_token_ceiling": DEVELOPMENT_INPUT_TOKEN_CEILING,
            "development_maximum_provider_request_attempts": 336,
            "development_output_token_ceiling": DEVELOPMENT_OUTPUT_TOKEN_CEILING,
            "development_stage_wall_seconds": 57_600,
            "development_worst_case_cost_usd": str(DEVELOPMENT_WORST_CASE_COST_USD),
            "maximum_fixture_units": sum(
                item.maximum_run_fixture_units for item in value.tasks
            )
            * 20,
            "maximum_provider_attempts_per_logical_call": 2,
            "minimalist_logical_calls_per_run": 1,
            "overall_proposed_pilot_ceiling_usd": str(
                OVERALL_PROPOSED_PILOT_CEILING_USD
            ),
            "run_input_token_ceiling": RUN_INPUT_TOKEN_CEILING,
            "run_normalized_policy_work_ceiling": 64,
            "run_output_token_ceiling": RUN_OUTPUT_TOKEN_CEILING,
            "run_research_service_call_ceiling": 64,
            "run_wall_seconds": 900,
        },
        "campaign_id": value.campaign_id,
        "implementation_digest": value.implementation_digest,
        "owner_decisions_digest": value.owner_decisions_digest,
        "model": {
            "api": "RESPONSES",
            "built_in_tools": [],
            "context_limit_tokens": MODEL_CONTEXT_TOKEN_CEILING,
            "model_id": REQUESTED_MODEL,
            "reasoning_effort": "medium",
            "service_tier": REQUESTED_SERVICE_TIER,
            "store": False,
            "verbosity": "low",
        },
        "provider_contract": {
            "account_controls": {
                "abuse_monitoring_default_retention_days": 30,
                "background_mode": False,
                "credential_values_must_not_be_recorded": True,
                "project_retention_selection": (
                    "STANDARD_API_ABUSE_MONITORING_APPROVED_FOR_SYNTHETIC_DEVELOPMENT"
                ),
                "prompt_cache": (
                    "EXPLICIT_MODE_TTL_30M_DOCUMENTED_PROVIDER_RETENTION_ACCEPTED"
                ),
                "prompt_cache_ttl_claims_deletion": False,
                "required_runtime_configuration_names": [
                    "OPENAI_API_KEY",
                    "OPENAI_PROJECT_ID",
                    "OPENAI_ORGANIZATION_ID_OPTIONAL",
                ],
                "store_false_is_not_zero_data_retention": True,
                "training_or_data_sharing_opt_in": False,
                "zero_data_retention_or_modified_abuse_monitoring_required": False,
            },
            "payload_allowlist": [
                "frozen_system_and_profile_policy",
                "agent_visible_synthetic_task_description",
                "current_arm_permitted_prior_material",
                "current_run_permitted_practice_feedback",
                "public_resource_facts",
                "current_run_existing_candidate_ids",
            ],
            "pricing_per_million_usd": {
                "cache_write_input": "2.50",
                "cached_input": "0.20",
                "output_including_reasoning": "12.00",
                "standard_input": "2.00",
            },
            "pricing_verified_utc_date": "2026-09-09",
            "pricing_and_contract_sources": [
                "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
                "https://developers.openai.com/api/reference/cli/resources/responses/methods/create",
                "https://developers.openai.com/api/docs/guides/your-data",
            ],
            "spend_exclusions": [
                "TAXES",
                "INDEPENDENTLY_BILLED_INFRASTRUCTURE",
                "OFFLINE_TASK_GENERATION_AND_INCLUSION_AUDIT",
            ],
            "usage_accounting": (
                "REPEATED_INPUT_HISTORY_AND_OUTPUT_INCLUDING_REASONING_TOKENS"
            ),
        },
        "proposal_digest": value.proposal_digest,
        "reserve_policy": "NO_DEVELOPMENT_RESERVES_ALLOCATED_NO_SILENT_REPLACEMENT",
        "run_count": 40,
        "schema_version": DEVELOPMENT_SCHEMA_VERSION,
        "schedule": [
            {
                "arm": item.arm.value,
                "block_id": item.block_id,
                "ordinal": item.ordinal,
                "profile": item.profile.value,
                "run_id": item.run_id,
                "task_id": item.task_id,
                "task_ordinal": item.task_ordinal,
            }
            for item in value.schedule
        ],
        "stage": "DEVELOPMENT",
        "stopping_rule": (
            "ATTEMPT_EACH_REGISTERED_SLOT_ONCE_SEQUENTIALLY_STOP_ON_STAGE_BUDGET_"
            "OR_UNRESOLVED_PROVIDER_DISPATCH_NEVER_START_CALIBRATION"
        ),
        "tasks": [
            {
                "agent_visible_description": item.agent_visible_description,
                "candidate_fixture_units": item.candidate_fixture_units,
                "cell_id": item.cell_id,
                "content_digest": item.content_digest,
                "maximum_run_fixture_units": item.maximum_run_fixture_units,
                "observation_set_digest": item.observation_set_digest,
                "task_id": item.task_id,
            }
            for item in value.tasks
        ],
    }
    if include_digest:
        result["content_digest"] = value.content_digest
    return result


def _development_manifest_digest(value: DevelopmentCampaignManifest) -> str:
    return _digest(
        _MANIFEST_DOMAIN, _development_manifest_value(value, include_digest=False)
    )


def build_development_manifest(
    *,
    implementation_digest: str,
    artifact_manifest_digest: str,
    owner_decisions_digest: str,
    tasks: tuple[DevelopmentTask, DevelopmentTask],
) -> DevelopmentCampaignManifest:
    schedule = proposed_development_schedule(tasks)
    placeholder = "sha256:" + "0" * 64
    value = DevelopmentCampaignManifest.__new__(DevelopmentCampaignManifest)
    object.__setattr__(value, "campaign_id", "be4-autonomous-development-v2")
    object.__setattr__(
        value,
        "proposal_digest",
        "sha256:86979a14c38239fdad84c1f9fa190fc6a49e70fc31a996ae6ee61e844dfaff31",
    )
    object.__setattr__(value, "implementation_digest", implementation_digest)
    object.__setattr__(value, "artifact_manifest_digest", artifact_manifest_digest)
    object.__setattr__(value, "owner_decisions_digest", owner_decisions_digest)
    object.__setattr__(value, "tasks", tasks)
    object.__setattr__(value, "schedule", schedule)
    object.__setattr__(value, "content_digest", placeholder)
    digest = _development_manifest_digest(value)
    return DevelopmentCampaignManifest(
        value.campaign_id,
        value.proposal_digest,
        implementation_digest,
        artifact_manifest_digest,
        owner_decisions_digest,
        tasks,
        schedule,
        digest,
    )


@dataclass(slots=True)
class DevelopmentRunServices:
    plan: NonQualifyingRunPlan
    projection: PrivatePriorProjection
    session: AgentSession
    meter: PolicyWorkMeter
    research_bridge: ResearchLifecycleBridge
    official_bridge: OfficialLifecycleBridge
    strategy_domain: object
    parameter_catalog: ParameterCatalog
    candidate_assembly: CandidateAssemblyContract


class DevelopmentServiceFactory(Protocol):
    def create(
        self, slot: DevelopmentRunSlot, task: DevelopmentTask
    ) -> DevelopmentRunServices: ...


def _profile_policy_payload(profile: AgentProfile) -> dict[str, object]:
    policy = dict(_PROFILE_POLICY[profile])
    policy.update(
        {
            "allowed_action": (
                "ONE_TYPED_STRATEGY_OR_STOP"
                if profile is AgentProfile.MINIMALIST
                else "TYPED_STRATEGY_OR_STOP_THEN_SELECTION_ONLY"
            ),
            "generated_text_execution": False,
            "network_access": False,
            "profile": profile.value,
            "provider_model": REQUESTED_MODEL,
            "response_contract": "STRICT_JSON_SCHEMA",
            "system_policy": (
                "Use only this payload. Return one schema-valid response. "
                "Do not request tools, execute code, or infer unavailable evaluator material."
            ),
        }
    )
    if profile is AgentProfile.LITERATURE_GROUNDED:
        policy["corpus"] = [
            {
                "direction": item.direction.value,
                "method_id": item.method_id,
                "surface_keyword": item.surface_keyword,
            }
            for item in FIXTURE_METHOD_CORPUS
        ]
        policy["corpus_digest"] = FIXTURE_CORPUS_DIGEST
    else:
        policy["corpus"] = None
        policy["corpus_digest"] = None
    return policy


def development_profile_policy_artifacts() -> tuple[dict[str, object], ...]:
    """Return the exact five provider-facing policy prompts and identities."""

    result = []
    for profile in AgentProfile:
        payload = _profile_policy_payload(profile)
        result.append(
            {
                "content_digest": _digest(
                    b"carbon.be4.development-profile-policy.v1\x00", payload
                ),
                "payload": payload,
                "profile": profile.value,
            }
        )
    return tuple(result)


def development_treatment_payload(
    *,
    plan: NonQualifyingRunPlan,
    projection: PrivatePriorProjection,
    prior_lookup: PriorLookupResult | None,
) -> dict[str, object]:
    """Serialize one exact frozen arm through its existing B-07D3 owners."""

    if type(plan) is not NonQualifyingRunPlan:
        raise TypeError("treatment serialization requires an exact run plan")
    if type(projection) is not PrivatePriorProjection:
        raise TypeError("treatment serialization requires an exact projection")
    arm = plan.identity.arm
    result: dict[str, object] = {
        "arm": arm.value,
        "artifact_digest": plan.arm_artifact.content_digest,
        "artifact_id": plan.arm_artifact.artifact_id,
        "artifact_version": plan.arm_artifact.artifact_version,
        "limitations": [
            "TEST_ONLY",
            "NOT_UTILITY_QUALIFIED",
            "NONQUALIFYING_DEVELOPMENT",
        ],
        "suggested_surfaces": [],
    }
    if arm is ExperimentalArm.NO_PRIOR:
        result["material"] = None
    elif arm is ExperimentalArm.GENERIC_PRIOR:
        result["material"] = list(GENERIC_WORKFLOW_STEPS)
    elif arm is ExperimentalArm.V1_DIRECTIVE_PRIOR:
        result["material"] = [
            {
                "kind": item.kind.value,
                "subject": item.subject,
                "tokens": list(item.tokens),
            }
            for item in projection.published_prior.directives
        ]
        result["suggested_surfaces"] = [
            item.subject for item in projection.published_prior.directives
        ]
    else:
        if type(prior_lookup) is not PriorLookupResult:
            raise DevelopmentPilotError("v2 treatment lacks its B-07D3 lookup")
        pack = prior_lookup.prior_pack
        result["material"] = [
            {
                "action": item.intervention.action.value,
                "baseline_ref": item.intervention.baseline_ref,
                "expected_directions": [
                    outcome.direction.value for outcome in item.expected_outcomes
                ],
                "guidance_kind": item.kind.value,
                "item_id": item.item_id,
                "surface_id": item.intervention.surface_id,
                "to_ref": item.intervention.to_ref,
            }
            for item in pack.items
        ]
        result["pack_ref"] = {
            "challenge_id": prior_lookup.prior_pack_ref.challenge_key.challenge_id,
            "challenge_version": prior_lookup.prior_pack_ref.challenge_key.version,
            "channel": prior_lookup.prior_pack_ref.channel.value,
            "content_hash": prior_lookup.prior_pack_ref.content_hash,
            "publication_sequence": prior_lookup.prior_pack_ref.publication_sequence,
        }
        result["suggested_surfaces"] = [
            item.intervention.surface_id for item in pack.items
        ]
    return result


def _treatment_payload(
    services: DevelopmentRunServices,
    builder: AdaptivePreflightBuilder,
) -> dict[str, object]:
    arm = services.plan.identity.arm
    return development_treatment_payload(
        plan=services.plan,
        projection=services.projection,
        prior_lookup=(
            builder.prior_lookup if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None
        ),
    )


def _feedback_payload(
    *,
    feedback: list[object],
    candidate_ids: dict[str, str],
) -> list[dict[str, object]]:
    result = []
    for evidence in feedback:
        item = evidence.feedback
        result.append(
            {
                "candidate_id": candidate_ids[item.proposal_digest],
                "comparison_value": item.comparison_value,
                "feedback_digest": item.content_digest,
                "observed_range": list(item.observed_range),
                "proposal_digest": item.proposal_digest,
                "status": "PRACTICE_ADMISSIBLE",
            }
        )
    return result


def _provider_payload(
    *,
    slot: DevelopmentRunSlot,
    task: DevelopmentTask,
    services: DevelopmentRunServices,
    builder: AdaptivePreflightBuilder,
    feedback: list[object],
    candidate_ids: dict[str, str],
) -> dict[str, object]:
    return build_offline_provider_payload(
        {
            "frozen_system_and_profile_policy": _profile_policy_payload(slot.profile),
            "agent_visible_synthetic_task_description": (
                task.agent_visible_description
            ),
            "current_arm_permitted_prior_material": _treatment_payload(
                services, builder
            ),
            "current_run_permitted_practice_feedback": _feedback_payload(
                feedback=feedback, candidate_ids=candidate_ids
            ),
            "public_resource_facts": {
                "candidate_fixture_units": task.candidate_fixture_units,
                "maximum_run_fixture_units": task.maximum_run_fixture_units,
                "registered_strategy_surfaces": list(REGISTERED_EFFECTFUL_SURFACES),
                "scaffold_strategy": builder.scaffold.strategy_template,
            },
            "current_run_existing_candidate_ids": list(candidate_ids.values()),
        }
    )


class DevelopmentPilotRunner:
    """Sequential executor for the exact 40-slot development matrix."""

    __slots__ = (
        "_factory",
        "_journal",
        "_manifest",
        "_stage_started_ns",
        "_tasks",
        "_transport",
    )

    def __init__(
        self,
        *,
        manifest: DevelopmentCampaignManifest,
        tasks: Mapping[str, DevelopmentTask],
        journal: DevelopmentJournal,
        transport: ProviderTransport,
        service_factory: DevelopmentServiceFactory,
    ) -> None:
        if (
            type(manifest) is not DevelopmentCampaignManifest
            or type(journal) is not DevelopmentJournal
            or manifest.content_digest != journal._manifest_digest
            or not isinstance(tasks, Mapping)
            or set(tasks) != {item.task_id for item in manifest.tasks}
            or any(type(item) is not DevelopmentTask for item in tasks.values())
            or not hasattr(transport, "dispatch")
            or not hasattr(service_factory, "create")
        ):
            raise TypeError("development runner composition is invalid")
        self._manifest = manifest
        self._tasks = dict(tasks)
        self._journal = journal
        self._transport = ProviderDispatcher(journal=journal, transport=transport)
        self._factory = service_factory
        self._stage_started_ns = time.monotonic_ns()

    def run(self) -> dict[str, object]:
        stop_reason: str | None = None
        if self._journal.has_unresolved_operations():
            stop_reason = "UNRESOLVED_PROVIDER_DISPATCH"
        for slot in self._manifest.schedule:
            if stop_reason is not None:
                break
            if self._journal.read_run_result(slot.run_id) is not None:
                continue
            if self._stage_elapsed() >= 57_600.0:
                stop_reason = "DEVELOPMENT_STAGE_DEADLINE_EXHAUSTED"
                break
            try:
                self._journal.begin_run(slot.run_id)
                value = self._run_slot(slot, self._tasks[slot.task_id])
            except (ProviderAmbiguousTimeout, UnresolvedOperationError) as error:
                value = self._failed_run_value(
                    slot,
                    "UNRESOLVED_PROVIDER_DISPATCH",
                    str(error),
                )
                self._journal.record_run_result(slot.run_id, value)
                stop_reason = "UNRESOLVED_PROVIDER_DISPATCH"
                break
            except Exception as error:  # noqa: BLE001 - retained diagnostic boundary.
                value = self._failed_run_value(
                    slot,
                    "RUNNER_OR_LIFECYCLE_FAILURE",
                    type(error).__name__,
                )
                self._journal.record_run_result(slot.run_id, value)
                stop_reason = "RUNNER_OR_LIFECYCLE_FAILURE"
                break
            self._journal.record_run_result(slot.run_id, value)
        rows = self._journal.all_run_results()
        completed = sum(item["status"] == "COMPLETED" for item in rows)
        offline = isinstance(
            self._transport._transport,
            (DeterministicOfflineTransport, ControlledOpenAIResponsesTransport),
        )
        operation_summary = self._journal.provider_operation_summary()
        operation_states = operation_summary["operation_states"]
        assert type(operation_states) is dict
        confirmed_calls = int(operation_states["COMPLETED"])
        unresolved_calls = int(operation_states["INTENT"]) + int(
            operation_states["UNKNOWN"]
        )
        if offline:
            provider_execution_status = "SIMULATED_OFFLINE_ONLY"
            model_inference: bool | None = False
        elif confirmed_calls and unresolved_calls:
            provider_execution_status = "CONFIRMED_WITH_UNRECONCILED_DISPATCH"
            model_inference = True
        elif confirmed_calls:
            provider_execution_status = "CONFIRMED"
            model_inference = True
        elif unresolved_calls:
            provider_execution_status = "POSSIBLE_UNRECONCILED"
            model_inference = None
        else:
            provider_execution_status = "NO_PROVIDER_INFERENCE"
            model_inference = False
        return {
            "authority_ceiling": DEVELOPMENT_AUTHORITY_CEILING,
            "campaign_manifest_digest": self._manifest.content_digest,
            "completed_run_count": completed,
            "model_inference_executed": model_inference,
            "offline_integration_only": offline,
            "paid_execution_occurred": model_inference,
            "provider_execution_status": provider_execution_status,
            "provider_operation_summary": operation_summary,
            "qualifying_execution_ready": False,
            "recorded_run_count": len(rows),
            "remaining_run_count": 40 - len(rows),
            "run_results": list(rows),
            "schema_version": DEVELOPMENT_SCHEMA_VERSION,
            "stage": "DEVELOPMENT",
            "stop_reason": stop_reason or "DEVELOPMENT_MATRIX_COMPLETE",
        }

    def _stage_elapsed(self) -> float:
        return self._journal.campaign_elapsed_seconds()

    def _deadline(self, run_id: str, run_started_ns: int) -> float:
        run_elapsed = self._journal.run_elapsed_seconds(run_id)
        if run_elapsed is None:
            run_elapsed = (time.monotonic_ns() - run_started_ns) / 1_000_000_000
        stage_remaining = 57_600.0 - self._stage_elapsed()
        return bounded_provider_deadline_seconds(
            requested_call_seconds=120.0,
            remaining_run_seconds=float(900.0 - run_elapsed),
            remaining_stage_seconds=float(stage_remaining),
            remaining_campaign_seconds=float(432_000.0 - self._stage_elapsed()),
        )

    def _call_provider(
        self,
        *,
        slot: DevelopmentRunSlot,
        kind: ProviderCallKind,
        call_number: int,
        retry_number: int,
        payload: dict[str, object],
        conversation_history: list[ProviderConversationTurn],
        run_started_ns: int,
        provider_request_ordinal: int,
    ) -> ProviderResult:
        operation_id = (
            f"{slot.run_id}:{kind.value.lower()}:{call_number:02d}:"
            f"try-{retry_number + 1}"
        )
        call = ProviderCall(
            operation_id,
            slot.run_id,
            slot.ordinal * 16 + provider_request_ordinal,
            kind,
            slot.profile,
            slot.arm,
            payload,
            tuple(conversation_history),
            self._deadline(slot.run_id, run_started_ns),
            (
                PROPOSAL_MAX_OUTPUT_TOKENS
                if kind is ProviderCallKind.PROPOSAL
                else SELECTION_MAX_OUTPUT_TOKENS
            ),
        )
        return self._transport.dispatch(call)

    def _run_slot(
        self, slot: DevelopmentRunSlot, task: DevelopmentTask
    ) -> dict[str, object]:
        run_started_ns = time.monotonic_ns()
        services = self._factory.create(slot, task)
        if (
            type(services) is not DevelopmentRunServices
            or services.plan.identity.profile is not slot.profile
            or services.plan.identity.arm is not slot.arm
            or services.plan.block_id != slot.block_id
            or services.plan.fixture_resource_ceiling < task.maximum_run_fixture_units
        ):
            raise DevelopmentPilotError("service factory returned a mismatched run")
        builder = AdaptivePreflightBuilder(
            session=services.session,
            plan=services.plan,
            strategy_domain=services.strategy_domain,
            parameter_catalog=services.parameter_catalog,
            candidate_assembly=services.candidate_assembly,
            meter=services.meter,
        )
        resource_account = LifecycleResourceAccount(
            services.plan.fixture_resource_ceiling
        )
        state = initial_pilot_interaction(slot.profile)
        feedback: list[object] = []
        candidate_ids: dict[str, str] = {}
        provider_results: list[ProviderResult] = []
        conversation_history: list[ProviderConversationTurn] = []
        lifecycle_failures: list[dict[str, object]] = []
        while state.phase is PilotPhase.READY_FOR_PROPOSAL:
            proposal_number = state.proposal_attempts + 1
            payload = _provider_payload(
                slot=slot,
                task=task,
                services=services,
                builder=builder,
                feedback=feedback,
                candidate_ids=candidate_ids,
            )
            result: ProviderResult | None = None
            for retry in range(2):
                try:
                    result = self._call_provider(
                        slot=slot,
                        kind=ProviderCallKind.PROPOSAL,
                        call_number=proposal_number,
                        retry_number=retry,
                        payload=payload,
                        conversation_history=conversation_history,
                        run_started_ns=run_started_ns,
                        provider_request_ordinal=state.provider_requests,
                    )
                except ProviderVerifiedFailure:
                    state = advance_pilot_interaction(
                        state, PilotEvent.VERIFIED_EXTERNAL_PROVIDER_FAILURE
                    )
                    if state.phase is PilotPhase.TERMINAL:
                        break
                    continue
                provider_results.append(result)
                conversation_history.append(
                    ProviderConversationTurn(
                        slot.run_id,
                        slot.profile,
                        slot.arm,
                        ProviderCallKind.PROPOSAL,
                        payload,
                        result,
                    )
                )
                break
            if result is None:
                break
            if result.outcome is ProviderOutcomeKind.REFUSAL:
                state = advance_pilot_interaction(state, PilotEvent.REFUSAL)
                continue
            if result.outcome is ProviderOutcomeKind.TRUNCATED:
                state = advance_pilot_interaction(
                    state, PilotEvent.TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED
                )
                continue
            if result.outcome is ProviderOutcomeKind.MALFORMED:
                state = advance_pilot_interaction(
                    state, PilotEvent.SCHEMA_INVALID_OR_MALFORMED_OUTPUT
                )
                continue
            output = _validate_structured_output(
                ProviderCallKind.PROPOSAL, result.structured_output
            )
            if output["action"] == "STOP":
                state = advance_pilot_interaction(state, PilotEvent.EXPLICIT_AGENT_STOP)
                break
            try:
                candidate = builder.add_strategy(
                    attempt=proposal_number,
                    surface_id=output["surface_id"],
                    strategy=output["strategy"],
                )
            except (TypeError, ValueError):
                state = advance_pilot_interaction(state, PilotEvent.INVALID_STRATEGY)
                continue
            if not candidate.executable:
                state = advance_pilot_interaction(state, PilotEvent.INVALID_STRATEGY)
                continue
            candidate_id = (
                f"candidate-{proposal_number:02d}-"
                f"{candidate.proposal.strategy_digest[7:19]}"
            )
            candidate_ids[candidate.proposal.strategy_digest] = candidate_id
            state = advance_pilot_interaction(
                state, PilotEvent.VALID_PROPOSAL, candidate_id=candidate_id
            )
            prepared = builder.freeze()
            try:
                observed = services.research_bridge.run_paired_practice(
                    session=services.session,
                    prepared=prepared,
                    resource_account=resource_account,
                    meter=services.meter,
                    lifecycle_started_ns=run_started_ns,
                    wall_time_seconds=services.plan.budget.wall_time_seconds,
                    attempt=proposal_number,
                )[0]
            except NonQualifyingLifecycleError as error:
                lifecycle_failures.append(
                    {
                        "kind": error.kind.value,
                        "stage": error.stage,
                        "replacement_eligibility": error.replacement_eligibility.value,
                    }
                )
                state = advance_pilot_interaction(state, PilotEvent.PRACTICE_FAILURE)
                if error.replacement_eligibility.value != "NOT_ELIGIBLE":
                    break
                continue
            feedback.append(observed)
            state = advance_pilot_interaction(state, PilotEvent.PRACTICE_SUCCESS)
        selected_candidate_id = state.selected_ancestor_id
        if state.phase is PilotPhase.READY_FOR_SELECTION:
            payload = _provider_payload(
                slot=slot,
                task=task,
                services=services,
                builder=builder,
                feedback=feedback,
                candidate_ids=candidate_ids,
            )
            result = None
            for retry in range(2):
                try:
                    result = self._call_provider(
                        slot=slot,
                        kind=ProviderCallKind.SELECTION,
                        call_number=1,
                        retry_number=retry,
                        payload=payload,
                        conversation_history=conversation_history,
                        run_started_ns=run_started_ns,
                        provider_request_ordinal=state.provider_requests,
                    )
                except ProviderVerifiedFailure:
                    state = advance_pilot_interaction(
                        state, PilotEvent.VERIFIED_EXTERNAL_PROVIDER_FAILURE
                    )
                    if state.phase is PilotPhase.TERMINAL:
                        break
                    continue
                provider_results.append(result)
                conversation_history.append(
                    ProviderConversationTurn(
                        slot.run_id,
                        slot.profile,
                        slot.arm,
                        ProviderCallKind.SELECTION,
                        payload,
                        result,
                    )
                )
                break
            if result is not None and result.outcome is ProviderOutcomeKind.STRUCTURED:
                output = _validate_structured_output(
                    ProviderCallKind.SELECTION, result.structured_output
                )
                selected_candidate_id = (
                    output["candidate_id"] if output["action"] == "SELECT" else None
                )
                state = advance_pilot_interaction(
                    state,
                    PilotEvent.FINAL_SELECTION_OR_STOP,
                    candidate_id=selected_candidate_id,
                )
            elif result is not None:
                # A malformed/refused/truncated selection cannot become a new
                # proposal or an unmetered deterministic selection.
                selected_candidate_id = None
                state = advance_pilot_interaction(
                    state, PilotEvent.FINAL_SELECTION_OR_STOP, candidate_id=None
                )
        if selected_candidate_id is None:
            return self._terminal_run_value(
                slot=slot,
                task=task,
                state=state,
                builder=builder,
                meter=services.meter,
                resource_account=resource_account,
                run_started_ns=run_started_ns,
                provider_results=provider_results,
                feedback=feedback,
                lifecycle_failures=lifecycle_failures,
            )
        selected_digest = next(
            digest
            for digest, candidate_id in candidate_ids.items()
            if candidate_id == selected_candidate_id
        )
        prepared = builder.freeze()
        selection = bind_data_only_selection(
            driver_ref=services.plan.driver_ref,
            proposal_batch=prepared.proposal_batch,
            feedback=tuple(item.feedback for item in feedback),
            selected_proposal_digest=selected_digest,
        )
        selected = next(
            item
            for item in prepared.candidates
            if item.proposal.strategy_digest == selected_digest
        )
        assert selected.resource_inspection is not None
        final_units = float(
            sum(item.quantity for item in selected.resource_inspection.line_items)
        )
        resource_account.inspect(final_units)
        if not resource_account.admit(final_units):
            raise DevelopmentPilotError("final fixture operation exceeds run resources")
        submission = submit_selected_prepared_fixture_run(
            session=services.session,
            prepared=prepared,
            selection=selection,
        )
        outcome, public_result = services.official_bridge.complete(
            session=services.session,
            submission=submission,
            resource_account=resource_account,
            expected_fixture_units=final_units,
            meter=services.meter,
            lifecycle_started_ns=run_started_ns,
        )
        return self._completed_run_value(
            slot=slot,
            task=task,
            state=state,
            builder=builder,
            meter=services.meter,
            resource_account=resource_account,
            run_started_ns=run_started_ns,
            provider_results=provider_results,
            feedback=feedback,
            lifecycle_failures=lifecycle_failures,
            selection_digest=selection.content_digest,
            selected_candidate_id=selected_candidate_id,
            outcome=outcome,
            public_result=public_result,
            submission_digest=submission.association_digest,
        )

    @staticmethod
    def _interaction_value(state: PilotInteractionState) -> dict[str, object]:
        return {
            "admissible_ancestor_ids": list(state.admissible_ancestor_ids),
            "feedback_results": state.feedback_results,
            "phase": state.phase.value,
            "proposal_attempts": state.proposal_attempts,
            "provider_requests": state.provider_requests,
            "provider_retries_for_current_call": (
                state.provider_retries_for_current_call
            ),
            "selected_ancestor_id": state.selected_ancestor_id,
            "termination_reason": state.termination_reason,
            "unknown_billing_reservation": state.unknown_billing_reservation,
        }

    @staticmethod
    def _provider_values(
        provider_results: list[ProviderResult],
    ) -> list[dict[str, object]]:
        return [
            {
                "content_digest": item.content_digest,
                "outcome": item.outcome.value,
                "raw_response_digest": item.raw_response_digest,
                "request_id": item.request_id,
                "requested_model": item.requested_model,
                "requested_service_tier": item.requested_service_tier,
                "returned_model": item.returned_model,
                "returned_service_tier": item.returned_service_tier,
                "started_at_utc": item.started_at_utc,
                "completed_at_utc": item.completed_at_utc,
                "usage": item.usage.to_json(),
            }
            for item in provider_results
        ]

    @staticmethod
    def _feedback_values(
        feedback: list[object],
    ) -> list[dict[str, object]]:
        values: list[dict[str, object]] = []
        for evidence in feedback:
            item = evidence.feedback
            values.append(
                {
                    "comparison_value": item.comparison_value,
                    "content_digest": evidence.content_digest,
                    "feedback_digest": item.content_digest,
                    "proposal_digest": item.proposal_digest,
                    "research_receipt_digest": (
                        evidence.receipt.receipt_ref.receipt_digest
                    ),
                    "research_task_id": evidence.receipt.task_id.value,
                }
            )
        return values

    @staticmethod
    def _resource_value(
        *,
        resource_account: LifecycleResourceAccount,
        meter: PolicyWorkMeter,
        run_started_ns: int,
    ) -> dict[str, object]:
        observation = resource_account.observation(
            meter=meter, started_ns=run_started_ns
        )
        return {
            "confirmed_fixture_units": observation.confirmed_fixture_units,
            "content_digest": observation.content_digest,
            "normalized_compute": {
                "content_digest": observation.normalized_compute.content_digest,
                "counts": {
                    item.kind.value: item.count
                    for item in observation.normalized_compute.counts
                },
                "total_work_units": (observation.normalized_compute.total_work_units),
            },
            "predicted_fixture_units": observation.predicted_fixture_units,
            "reserved_fixture_units": observation.reserved_fixture_units,
            "unreconciled_fixture_units": (observation.unreconciled_fixture_units),
            "wall_time_seconds": observation.wall_time.elapsed_seconds,
        }

    def _base_run_value(
        self,
        *,
        slot: DevelopmentRunSlot,
        task: DevelopmentTask,
        state: PilotInteractionState,
        builder: AdaptivePreflightBuilder,
        meter: PolicyWorkMeter,
        resource_account: LifecycleResourceAccount,
        run_started_ns: int,
        provider_results: list[ProviderResult],
        feedback: list[object],
        lifecycle_failures: list[dict[str, object]],
    ) -> dict[str, object]:
        candidates = builder.candidates
        prepared_digest = None
        if candidates:
            prepared_digest = builder.freeze().transcript_digest
        return {
            "arm": slot.arm.value,
            "authority_ceiling": DEVELOPMENT_AUTHORITY_CEILING,
            "block_id": slot.block_id,
            "campaign_manifest_digest": self._manifest.content_digest,
            "candidate_records": [
                {
                    "attempt": item.proposal.attempt,
                    "executable": item.executable,
                    "strategy_digest": item.proposal.strategy_digest,
                    "surface_id": item.proposal.surface_id,
                }
                for item in candidates
            ],
            "interaction": self._interaction_value(state),
            "lifecycle_failures": lifecycle_failures,
            "practice_evidence": self._feedback_values(feedback),
            "profile": slot.profile.value,
            "proposal_transcript_digest": prepared_digest,
            "provider_results": self._provider_values(provider_results),
            "qualifying_evidence": False,
            "resource_observation": self._resource_value(
                resource_account=resource_account,
                meter=meter,
                run_started_ns=run_started_ns,
            ),
            "run_id": slot.run_id,
            "run_ordinal": slot.ordinal,
            "schema_version": DEVELOPMENT_SCHEMA_VERSION,
            "task_digest": task.content_digest,
            "task_id": task.task_id,
        }

    def _terminal_run_value(
        self,
        *,
        slot: DevelopmentRunSlot,
        task: DevelopmentTask,
        state: PilotInteractionState,
        builder: AdaptivePreflightBuilder,
        meter: PolicyWorkMeter,
        resource_account: LifecycleResourceAccount,
        run_started_ns: int,
        provider_results: list[ProviderResult],
        feedback: list[object],
        lifecycle_failures: list[dict[str, object]],
    ) -> dict[str, object]:
        value = self._base_run_value(
            slot=slot,
            task=task,
            state=state,
            builder=builder,
            meter=meter,
            resource_account=resource_account,
            run_started_ns=run_started_ns,
            provider_results=provider_results,
            feedback=feedback,
            lifecycle_failures=lifecycle_failures,
        )
        value.update(
            {
                "official_endpoint": None,
                "selected_candidate_id": None,
                "status": "STOPPED",
            }
        )
        return value

    def _completed_run_value(
        self,
        *,
        slot: DevelopmentRunSlot,
        task: DevelopmentTask,
        state: PilotInteractionState,
        builder: AdaptivePreflightBuilder,
        meter: PolicyWorkMeter,
        resource_account: LifecycleResourceAccount,
        run_started_ns: int,
        provider_results: list[ProviderResult],
        feedback: list[object],
        lifecycle_failures: list[dict[str, object]],
        selection_digest: str,
        selected_candidate_id: str,
        outcome: ResolvedFixtureCompletedRun,
        public_result: SubmissionResult,
        submission_digest: str,
    ) -> dict[str, object]:
        if type(outcome) is not ResolvedFixtureCompletedRun:
            raise TypeError("completed development run requires an exact endpoint")
        if type(public_result) is not SubmissionResult or public_result.card is None:
            raise TypeError("completed development run requires its public A8 result")
        value = self._base_run_value(
            slot=slot,
            task=task,
            state=state,
            builder=builder,
            meter=meter,
            resource_account=resource_account,
            run_started_ns=run_started_ns,
            provider_results=provider_results,
            feedback=feedback,
            lifecycle_failures=lifecycle_failures,
        )
        endpoint = outcome.endpoint_observation_receipt
        value.update(
            {
                "official_endpoint": {
                    "endpoint_receipt_ref": endpoint.receipt_ref,
                    "heldout_mean_squared_error": (endpoint.heldout_mean_squared_error),
                    "measurement_contract_ref": (
                        endpoint.measurement_contract_ref.content_digest
                    ),
                    "reconstruction_receipt_ref": (endpoint.reconstruction_receipt_ref),
                    "transfer_mean_squared_error": (
                        endpoint.transfer_mean_squared_error
                    ),
                },
                "public_result": {
                    "card_status": public_result.card.status,
                    "fixture_origin": public_result.card.fixture_origin,
                    "result_id": public_result.card.result_id,
                    "state": public_result.status.state.value,
                    "submission_id": public_result.status.submission_id.value,
                },
                "selected_candidate_id": selected_candidate_id,
                "selection_digest": selection_digest,
                "status": "COMPLETED",
                "submission_digest": submission_digest,
            }
        )
        return value

    def _failed_run_value(
        self,
        slot: DevelopmentRunSlot,
        failure_kind: str,
        diagnostic: str,
    ) -> dict[str, object]:
        return {
            "arm": slot.arm.value,
            "authority_ceiling": DEVELOPMENT_AUTHORITY_CEILING,
            "block_id": slot.block_id,
            "campaign_manifest_digest": self._manifest.content_digest,
            "diagnostic": diagnostic,
            "failure_kind": failure_kind,
            "profile": slot.profile.value,
            "qualifying_evidence": False,
            "run_id": slot.run_id,
            "run_ordinal": slot.ordinal,
            "schema_version": DEVELOPMENT_SCHEMA_VERSION,
            "status": "FAILED",
            "task_id": slot.task_id,
        }


__all__ = (
    "DEVELOPMENT_APPROVAL_REQUEST_USD",
    "DEVELOPMENT_AUTHORITY_CEILING",
    "DEVELOPMENT_INPUT_TOKEN_CEILING",
    "DEVELOPMENT_OUTPUT_TOKEN_CEILING",
    "DEVELOPMENT_SCHEMA_VERSION",
    "DEVELOPMENT_WORST_CASE_COST_USD",
    "MODEL_CONTEXT_TOKEN_CEILING",
    "OVERALL_PROPOSED_PILOT_CEILING_USD",
    "PROPOSAL_MAX_OUTPUT_TOKENS",
    "REQUESTED_MODEL",
    "REQUESTED_SERVICE_TIER",
    "RESPONSES_ENDPOINT",
    "RUN_INPUT_TOKEN_CEILING",
    "RUN_OUTPUT_TOKEN_CEILING",
    "SELECTION_MAX_OUTPUT_TOKENS",
    "ControlledOpenAIResponsesTransport",
    "CostSnapshot",
    "DeterministicOfflineTransport",
    "DevelopmentApprovalUnavailable",
    "DevelopmentCampaignManifest",
    "DevelopmentJournal",
    "DevelopmentPilotError",
    "DevelopmentPilotRunner",
    "DevelopmentRunServices",
    "DevelopmentRunSlot",
    "DevelopmentServiceFactory",
    "DevelopmentTask",
    "OpenAIResponsesTransport",
    "ProviderAmbiguousTimeout",
    "ProviderCall",
    "ProviderCallKind",
    "ProviderConversationTurn",
    "ProviderDispatcher",
    "ProviderOutcomeKind",
    "ProviderResult",
    "ProviderTransport",
    "ProviderUsage",
    "ProviderVerifiedFailure",
    "UnresolvedOperationError",
    "build_development_manifest",
    "development_execution_admission_status",
    "development_profile_policy_artifacts",
    "development_treatment_payload",
    "proposed_development_schedule",
)
