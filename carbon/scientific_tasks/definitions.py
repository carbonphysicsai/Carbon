"""Closed physical definitions, without a PDE language or execution authority.

Burgers follows the existing C-AUTH1 law and candidate-query convention. Linear
advection is a definition-only reuse control corresponding to Workbench atlas
PHY-A03, which is NOT_PROFILED; it is not a registered Challenge or solver.

Authoring PhysicalSystemSpec, CandidateOutputContract and CanonicalChallengeCase
remain the authority. Trusted adapters establish custody from their authenticated
service and provenance; caller-provided custody is never an access grant. The
projection check prevents accidental cross-role serialization, not impersonation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum

from carbon.authoring.cases import CanonicalChallengeCase
from carbon.authoring.physical import CandidateOutputContract, PhysicalSystemSpec
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    PhysicalSystemSpecRef,
)
from carbon.generators.burgers_dynamics import DOMAIN_LENGTH, CandidateQuery

SCHEMA = "carbon.scientific-definition.v1"
MAX_ARRAY_ELEMENTS = 65536  # Serialization bound, not a physical admissibility gate.


class Template(str, Enum):
    BURGERS = "periodic_viscous_burgers_1d_v1"
    ADVECTION_CONTROL = "periodic_linear_advection_definition_control_v1"


class Audience(str, Enum):
    MINER = "miner"
    VALIDATOR = "validator"
    WORKBENCH = "workbench"


class Custody(str, Enum):
    PUBLIC_DEVELOPMENT = "PUBLIC_DEVELOPMENT"
    VALIDATOR_INTERNAL = "VALIDATOR_INTERNAL"
    WORKBENCH_PRIVATE = "WORKBENCH_PRIVATE"


def _finite(value):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("finite binary64 float required; implicit conversion rejected")


def _array(values):
    if type(values) is not tuple or not 1 <= len(values) <= MAX_ARRAY_ELEMENTS:
        raise ValueError("bounded nonempty tuple required")
    for value in values:
        _finite(value)


def _unit_system(template):
    return (
        "carbon_burgers_native_v1"
        if template is Template.BURGERS
        else "carbon_advection_definition_native_v1"
    )


@dataclass(frozen=True, slots=True, repr=False)
class AuthoringBinding:
    physical_system: PhysicalSystemSpecRef
    candidate_output: CandidateOutputContractRef
    canonical_case: CanonicalChallengeCaseRef | None

    def __post_init__(self):
        for value, expected in (
            (self.physical_system, PhysicalSystemSpecRef),
            (self.candidate_output, CandidateOutputContractRef),
        ):
            if type(value) is not expected:
                raise ValueError("exact authoring reference required")
        if self.physical_system.challenge_key != self.candidate_output.challenge_key:
            raise ValueError("authoring Challenge mismatch")
        if self.canonical_case is not None and (
            type(self.canonical_case) is not CanonicalChallengeCaseRef
            or self.canonical_case.challenge_key != self.physical_system.challenge_key
        ):
            raise ValueError("authoring case Challenge mismatch")
        # The first adapter recognizes only the existing concrete session
        # contracts. Mere schema compatibility does not establish the same PDE.
        from carbon.development_session.contracts import authored_contracts

        physical, candidate, _ = authored_contracts()
        if (
            self.physical_system != physical.to_ref()
            or self.candidate_output != candidate.to_ref()
        ):
            raise ValueError("unsupported physical/candidate authoring identity")


def bind_authoring(physical, candidate, case=None) -> AuthoringBinding:
    """Retain existing exact authoring identities; never synthesize registration."""
    if (
        type(physical) is not PhysicalSystemSpec
        or type(candidate) is not CandidateOutputContract
    ):
        raise ValueError("exact authored contracts required")
    physical_ref, candidate_ref = physical.to_ref(), candidate.to_ref()
    if candidate.physical_system_ref != physical_ref:
        raise ValueError("candidate physical-system binding mismatch")
    if case is not None and (
        type(case) is not CanonicalChallengeCase
        or case.physical_system_ref != physical_ref
        or case.candidate_output_ref != candidate_ref
    ):
        raise ValueError("canonical-case binding mismatch")
    return AuthoringBinding(
        physical_ref, candidate_ref, None if case is None else case.to_ref()
    )


@dataclass(frozen=True, slots=True, repr=False)
class PeriodicDefinition:
    """Explicit one-case inputs; no population, tolerance, solver or grader field.

    The canonical arrays use binary64, zero-based indexing and C axis order.
    Bridge adapters must explicitly convert layouts/precision without changing
    coordinates or units. Requested-time order, including repetitions, is kept.
    """

    template: Template
    custody: Custody
    domain_length: float
    initial_field: tuple[float, ...]
    requested_times: tuple[float, ...]
    parameter: float
    unit_system: str
    source_lineage: str
    authoring: AuthoringBinding | None = None

    def __post_init__(self):
        if type(self.template) is not Template or type(self.custody) is not Custody:
            raise ValueError("exact template and custody required")
        if type(self.unit_system) is not str or self.unit_system != _unit_system(
            self.template
        ):
            raise ValueError("incompatible physical units; no implicit conversion")
        _finite(self.domain_length)
        _finite(self.parameter)
        _array(self.initial_field)
        _array(self.requested_times)
        if self.domain_length <= 0.0 or len(self.initial_field) < 2:
            raise ValueError(
                "positive periodic domain and at least two samples required"
            )
        if self.domain_length / len(self.initial_field) == 0.0:
            raise ValueError("grid spacing is not representable in binary64")
        if any(value < 0.0 for value in self.requested_times):
            raise ValueError("requested times must not precede the initial condition")
        if self.template is Template.BURGERS and self.parameter <= 0.0:
            raise ValueError("viscous Burgers requires positive viscosity")
        if (
            type(self.source_lineage) is not str
            or not 1 <= len(self.source_lineage) <= 256
        ):
            raise ValueError("bounded source lineage required")
        if self.authoring is not None and type(self.authoring) is not AuthoringBinding:
            raise ValueError("exact authoring binding required")
        if self.template is Template.ADVECTION_CONTROL and self.authoring is not None:
            raise ValueError("advection control has no registered authoring adapter")
        if self.authoring is not None:
            if (
                self.domain_length != DOMAIN_LENGTH
                or len(self.initial_field) != 64
                or len(self.requested_times) != 13
            ):
                raise ValueError("inputs do not match the bound session domain/layout")
            if (
                self.authoring.canonical_case is not None
                and self.custody is not Custody.VALIDATOR_INTERNAL
            ):
                raise ValueError(
                    "canonical-case material must remain validator internal"
                )

    def _record(self):
        binding = None
        if self.authoring is not None:
            binding = {
                "physical_system_digest": self.authoring.physical_system.content_digest,
                "candidate_output_digest": self.authoring.candidate_output.content_digest,
                "canonical_case_digest": (
                    None
                    if self.authoring.canonical_case is None
                    else self.authoring.canonical_case.content_digest
                ),
            }
        return {
            "schema": SCHEMA,
            "template": self.template.value,
            "custody": self.custody.value,
            "domain_length": self.domain_length,
            "initial_field": list(self.initial_field),
            "requested_times": list(self.requested_times),
            "parameters": {
                (
                    "viscosity"
                    if self.template is Template.BURGERS
                    else "transport_velocity"
                ): self.parameter
            },
            "unit_system": self.unit_system,
            "source_lineage": self.source_lineage,
            "authoring": binding,
        }

    @property
    def content_digest(self) -> str:
        # This digest itself is private when the underlying definition is private.
        value = json.dumps(
            self._record(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()

    def project(self, audience: Audience) -> dict[str, object]:
        if type(audience) is not Audience:
            raise ValueError("exact audience required")
        permitted = {
            Custody.PUBLIC_DEVELOPMENT: tuple(Audience),
            Custody.VALIDATOR_INTERNAL: (Audience.VALIDATOR,),
            Custody.WORKBENCH_PRIVATE: (Audience.WORKBENCH,),
        }
        if audience not in permitted[self.custody]:
            raise PermissionError("definition custody forbids this projection")
        return {
            **template_projection(self.template, audience),
            "inputs": self._record(),
            "content_digest": self.content_digest,
            "requested_horizon": max(self.requested_times),
            "positions": [
                self.domain_length * (index / len(self.initial_field))
                for index in range(len(self.initial_field))
            ],
            "shapes": {
                "initial_field": [len(self.initial_field)],
                "requested_times": [len(self.requested_times)],
                "solution": [len(self.requested_times), len(self.initial_field)],
            },
        }


def from_public_burgers_query(
    query: CandidateQuery, *, source_lineage: str
) -> PeriodicDefinition:
    """Adapt already-public causal inputs; never accept generator/canonical cases."""
    if type(query) is not CandidateQuery:
        raise ValueError("exact public CandidateQuery required")
    return PeriodicDefinition(
        Template.BURGERS,
        Custody.PUBLIC_DEVELOPMENT,
        query.domain_length,
        query.initial_field,
        query.requested_times,
        query.viscosity,
        "carbon_burgers_native_v1",
        source_lineage,
    )


def template_projection(template: Template, audience: Audience) -> dict[str, object]:
    """Only static public facts; no case values, lineage or private digests."""
    if type(template) is not Template or type(audience) is not Audience:
        raise ValueError("exact template and audience required")
    burgers = template is Template.BURGERS
    return {
        "schema": SCHEMA,
        "template": template.value,
        "audience": audience.value,
        "equation": "u_t + d_x(u^2/2) = nu*u_xx" if burgers else "u_t + c*u_x = 0",
        "variables": {
            "u": {
                "meaning": "velocity" if burgers else "transported scalar",
                "unit": "L/T" if burgers else "Q",
            },
            "x": {"meaning": "spatial position", "unit": "L"},
            "t": {"meaning": "time from initial condition", "unit": "T"},
        },
        "parameters": {
            "viscosity" if burgers else "transport_velocity": {
                "symbol": "nu" if burgers else "c",
                "unit": "L^2/T" if burgers else "L/T",
                "constraint": (
                    "positive finite constant" if burgers else "finite constant"
                ),
            }
        },
        "unit_system": _unit_system(template),
        "unit_convention": "native declared L/T/Q scales; no implicit SI conversion",
        "domain": "[0,domain_length); endpoint excluded; length explicitly supplied",
        "coordinates": "x_i=domain_length*i/N; i=0,...,N-1",
        "initial_condition": "u(x_i,0)=initial_field[i]",
        "boundary_condition": "periodic values and flux; endpoints identified",
        "forcing": "none",
        "requested_output": "solution at the supplied requested_times, preserving order",
        "array_layouts": {
            "initial_field": ["space"],
            "requested_times": ["time"],
            "solution": ["time", "space"],
        },
        "encoding": {"dtype": "float64", "array_order": "C", "index_origin": 0},
        "availability": (
            "EXISTING_BURGERS_ADAPTER_REQUIRED"
            if burgers
            else "DEFINITION_ONLY_NOT_EXECUTABLE"
        ),
        "role_boundary": {
            Audience.MINER: "permitted public research only; no protected cases or grader selection",
            Audience.VALIDATOR: "evaluator-owned cases and registered methods remain internal",
            Audience.WORKBENCH: "draft-scoped design evidence; no automatic public training handoff",
        }[audience],
        "qualification": "UNASSESSED_NOT_QUALIFIED",
    }
