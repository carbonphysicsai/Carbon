"""Private DEVELOPMENT projections, never real scientific authority."""

from dataclasses import asdict, dataclass
from enum import Enum

from carbon.fees import ExecutionEnvironmentPin
from carbon.scoring.model import ScorePackPin
from carbon.transport.models import canonical, digest


class CandidateCode(str, Enum):
    CONTEXT = "CANDIDATE_CONTEXT"
    ARTIFACT = "CANDIDATE_ARTIFACT"
    CONFLICT = "CANDIDATE_CONFLICT"
    CAPACITY = "CANDIDATE_CAPACITY"
    INDETERMINATE = "CANDIDATE_INDETERMINATE"
    NOT_ACCEPTED = "CANDIDATE_NOT_ACCEPTED"
    INFRASTRUCTURE = "CANDIDATE_INFRASTRUCTURE"


class CandidateFailure(RuntimeError):
    def __init__(self, code: CandidateCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, repr=False)
class FixtureEvaluationContext:
    """Operator registration; absent real scientific context fails closed."""

    pack: ScorePackPin
    environment: ExecutionEnvironmentPin

    def __post_init__(self):
        if (
            type(self.pack) is not ScorePackPin
            or type(self.environment) is not ExecutionEnvironmentPin
        ):
            raise CandidateFailure(CandidateCode.CONTEXT)
        # Reconstruct public immutable pin types; never persist seed bindings.
        ScorePackPin(**{**asdict(self.pack), "challenge_key": self.pack.challenge_key})
        ExecutionEnvironmentPin(**asdict(self.environment))

    @property
    def identity(self):
        return digest(
            canonical({"domain": "carbon.fixture.evaluation.v1", **asdict(self)})
        )


@dataclass(frozen=True)
class CandidateRef:
    identity: str


@dataclass(frozen=True, repr=False)
class AcceptedFixtureRecord:
    """Resolved private fixture record. No production counterpart is constructible."""

    candidate: CandidateRef
    context_id: str
    challenge_id: str
    challenge_version: str
    artifact_digest: str
    strategy_hash: str
    receipt_sequence: int
    receipt_digest: str
    hotkey: str
    coldkey: str
    registered_at: int
    snapshot_id: str
    finalized_block: int
    submission_id: str
    score_hex: str
    component_hex: tuple[str, ...]
