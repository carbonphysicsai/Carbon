"""Structural seam for one trusted fixture leaderboard publication provider."""

from __future__ import annotations

from typing import Protocol

from carbon.registry import ChallengeKey

from .model import (
    FixtureLeaderboardCandidateSnapshot,
    LeaderboardSnapshotSequence,
)


class FixtureLeaderboardProvider(Protocol):
    """Trusted structural provider of retained immutable fixture snapshots."""

    def get_snapshot(
        self,
        challenge_key: ChallengeKey,
        snapshot_sequence: LeaderboardSnapshotSequence | None,
    ) -> FixtureLeaderboardCandidateSnapshot | None:
        """Return the requested retained fixture snapshot, or exact ``None``."""
        ...
