"""The owner's DEVELOPMENT qualification of R1 for four GPU parts.

Authority: Amendment 10 to `docs/development/TWO_HOST_STUDY_ACCEPTANCE.md`,
recorded 2026-09-23 as the owner's decision in place of the MQ-008 scientific
holder. What it rules, and what this module implements:

- **Same part.** Qualified per part for the four parts measured - A40, H100 SXM,
  L4, RTX PRO 6000 SE. Each part has its own backend profile, so two captures
  from different parts differ in `backend_profile_ref`, fail R0, and never reach
  a numerical comparison. A part not listed has no profile here at all.
- **Bit-exact.** `absolute_delta` must be zero on every output. This is what was
  measured - pinned same-part runs were bit-identical every time - so there is
  no tolerance value to carry, and none is embedded.
- **`fixture_authoring 1.0` only.** Every measurement was on the C-02
  development fixture, not a registered Challenge.
- **DEVELOPMENT-typed.** Every record here is fixture-origin, through B-E1's
  existing types. The fixture-only boundary is deliberately not migrated: a
  non-fixture qualification bound to a fixture Challenge would record fixture
  evidence as real authority. Nothing here can enter official or LIVE authority.

Enforced by construction rather than by convention:

- The procedure can only be obtained from `development_procedure(part)`, which
  refuses a part the amendment did not name. A directly built procedure raises.
- The qualification's dossier reference carries the digest of Amendment 10's
  recorded text. `tests/cpu/test_be1_development_qualification.py` recomputes it
  from the repository, so the qualification cannot silently outlive an edit to
  the ruling it implements: changing the ruling means re-pinning it here.
- Nothing constructs a `SUPPORTED` capture on a caller's behalf. A caller asks
  `development_backend_support` for the registered status of a profile, which is
  `SUPPORTED` only for the four registered profiles.

Recorded and not yet reachable: no runtime path builds an R1 capture from a real
reconstruction yet, and matching a running device to one of these profiles needs
the NVML device names of the four parts, which were never recorded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from carbon.measurement import MeasurementDefinitionKind, MeasurementDefinitionRef
from carbon.registry import ChallengeKey

from .canonical import canonical_digest
from .enums import BackendProfileSupport, R1Outcome, ReproducibilityRefKind
from .model import (
    NumericalDelta,
    NumericalProcedureDecision,
    NumericalProcedureQualification,
    NumericalRunCapture,
)
from .refs import ReproducibilityRef

#: The fixture Challenge every measurement was made on.
DEVELOPMENT_CHALLENGE = ChallengeKey("fixture_authoring", "1.0")

#: Where the ruling is recorded, and the digest of its text as recorded there.
#: The section runs from its heading to the next amendment's separator, with
#: trailing whitespace removed and one newline appended.
DEVELOPMENT_AUTHORITY = "docs/development/TWO_HOST_STUDY_ACCEPTANCE.md, Amendment 10"
DEVELOPMENT_AUTHORITY_DIGEST = (
    "sha256:d046da751c477b548602322eacfeddee99d4be7afa8aaa48d9a4f7ab95343466"
)

#: The parts Amendment 10 qualifies, as the evidence names them.
QUALIFIED_PARTS = ("A40", "H100 SXM", "L4", "RTX PRO 6000 SE")

#: The pinned numerics configuration each profile is qualified under. The same
#: values `scripts/dev/gpu_determinism_study/run_on_pod.sh` exports and
#: `repeat_gpu.py` refuses to run without; a test holds the two together.
PINNED_XLA_FLAGS = (
    "--xla_gpu_deterministic_ops=true",
    "--xla_gpu_exclude_nondeterministic_ops=true",
    "--xla_gpu_autotune_level=0",
)
PINNED_NVIDIA_TF32_OVERRIDE = "0"
PINNED_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
ENVIRONMENT_PROFILE_ID = "carbon_jax_cuda13_nvidia_development_v1"

_VERSION = "1.0"
_READ = object()


@dataclass(frozen=True, slots=True)
class DevelopmentBackendProfile:
    """What one part is qualified as: the part, under the pinned configuration."""

    challenge_key: ChallengeKey
    part: str
    xla_flags: tuple[str, ...]
    nvidia_tf32_override: str
    cublas_workspace_config: str
    environment_profile_id: str
    authority: str
    authority_digest: str


@dataclass(frozen=True, slots=True)
class DevelopmentBitExactTolerance:
    """The R1 rule. States the comparison; carries no number to tune."""

    challenge_key: ChallengeKey
    rule: str
    authority: str
    authority_digest: str


def _object_id(part: str) -> str:
    return "gpu-pinned-" + part.lower().replace(" ", "-")


def _profile(part: str) -> DevelopmentBackendProfile:
    return DevelopmentBackendProfile(
        DEVELOPMENT_CHALLENGE,
        part,
        PINNED_XLA_FLAGS,
        PINNED_NVIDIA_TF32_OVERRIDE,
        PINNED_CUBLAS_WORKSPACE_CONFIG,
        ENVIRONMENT_PROFILE_ID,
        DEVELOPMENT_AUTHORITY,
        DEVELOPMENT_AUTHORITY_DIGEST,
    )


def _ref(kind: ReproducibilityRefKind, object_id: str, digest: str):
    return ReproducibilityRef(DEVELOPMENT_CHALLENGE, kind, object_id, _VERSION, digest)


def development_backend_profile_ref(part: str) -> ReproducibilityRef:
    """The registered profile of a qualified part. Any other part is refused."""
    if part not in QUALIFIED_PARTS:
        raise ValueError(
            f"{part!r} is not a part Amendment 10 qualifies; qualification is per "
            "part and does not extend to other parts of the same generation"
        )
    return _ref(
        ReproducibilityRefKind.BACKEND_PROFILE,
        _object_id(part),
        canonical_digest(_profile(part)),
    )


def development_backend_support(profile_ref: object) -> BackendProfileSupport:
    """`SUPPORTED` for the four registered profiles, `UNSUPPORTED` for anything else."""
    registered = {development_backend_profile_ref(part) for part in QUALIFIED_PARTS}
    if type(profile_ref) is ReproducibilityRef and profile_ref in registered:
        return BackendProfileSupport.SUPPORTED
    return BackendProfileSupport.UNSUPPORTED


@dataclass(frozen=True, slots=True)
class DevelopmentProcedureDescription:
    """What the procedure computes, so its reference names this procedure."""

    challenge_key: ChallengeKey
    computes: str
    decides: str
    tolerance_digest: str


_TOLERANCE = DevelopmentBitExactTolerance(
    DEVELOPMENT_CHALLENGE,
    "absolute_delta == 0 for every output",
    DEVELOPMENT_AUTHORITY,
    DEVELOPMENT_AUTHORITY_DIGEST,
)


_PROCEDURE = DevelopmentProcedureDescription(
    DEVELOPMENT_CHALLENGE,
    "absolute_delta = |a - b| for every output of two same-part captures",
    "REPRODUCIBLE when every output is identical, otherwise NOT_REPRODUCIBLE",
    canonical_digest(_TOLERANCE),
)


@dataclass(frozen=True, slots=True)
class DevelopmentBitExactProcedure:
    """The R1 comparison Amendment 10 qualifies, for one part.

    Obtain with `development_procedure(part)`; built directly it raises.
    """

    part: str
    qualification: NumericalProcedureQualification
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _READ:
            raise TypeError(
                "DevelopmentBitExactProcedure is built by development_procedure, "
                "which binds it to a part Amendment 10 names"
            )

    def compare(
        self, first: NumericalRunCapture, second: NumericalRunCapture
    ) -> NumericalProcedureDecision:
        values = {item.output_ref: item.value for item in second.outputs}
        deltas = tuple(
            NumericalDelta(item.output_ref, abs(item.value - values[item.output_ref]))
            for item in first.outputs
        )
        # Equality, not a threshold: bit-exact has no tolerance to compare
        # against. Negative zero and non-finite values are refused when a datum
        # is built, so equal values here are identical values.
        exact = all(item.value == values[item.output_ref] for item in first.outputs)
        evidence = hashlib.sha256()
        for item in (first, second):
            evidence.update(canonical_digest(item).encode("ascii"))
        return NumericalProcedureDecision(
            R1Outcome.REPRODUCIBLE if exact else R1Outcome.NOT_REPRODUCIBLE,
            deltas,
            _ref(
                ReproducibilityRefKind.EVIDENCE,
                "development-bit-exact-decision",
                "sha256:" + evidence.hexdigest(),
            ),
        )


def development_procedure(part: str) -> DevelopmentBitExactProcedure:
    """The qualified bit-exact procedure for one part Amendment 10 names."""
    profile_ref = development_backend_profile_ref(part)
    qualification = NumericalProcedureQualification(
        _ref(
            ReproducibilityRefKind.PROCEDURE,
            "development-bit-exact",
            canonical_digest(_PROCEDURE),
        ),
        _ref(
            ReproducibilityRefKind.TOLERANCE_POLICY,
            "development-bit-exact-tolerance",
            canonical_digest(_TOLERANCE),
        ),
        MeasurementDefinitionRef(
            DEVELOPMENT_CHALLENGE,
            MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
            "mq008-owner-development-qualification",
            _VERSION,
            DEVELOPMENT_AUTHORITY_DIGEST,
        ),
        profile_ref,
        True,
    )
    return DevelopmentBitExactProcedure(part, qualification, _READ)
