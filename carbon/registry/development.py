"""Trusted configuration for unqualified DEVELOPMENT service admission only."""

from dataclasses import dataclass

from .model import ChallengeKey, is_sha256_digest, validate_canonical_identifier


@dataclass(frozen=True, slots=True)
class DevelopmentServiceAdmission:
    challenge: ChallengeKey
    artifact_id: str
    profile_digest: str

    def __post_init__(self):
        if type(self.challenge) is not ChallengeKey or not is_sha256_digest(
            self.profile_digest
        ):
            raise ValueError("exact development admission required")
        validate_canonical_identifier(self.artifact_id, "artifact_id")
