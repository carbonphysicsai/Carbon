"""Bounded fixture leaderboard without official or operational authority.

This package has no LIVE, persistence, transport, frontier, settlement, chain,
weight, or emission authority.
"""

from . import model, providers, service

PublicationSequence = model.PublicationSequence
LeaderboardSnapshotSequence = model.LeaderboardSnapshotSequence
LeaderboardCursor = model.LeaderboardCursor
ListFixtureLeaderboardRequest = model.ListFixtureLeaderboardRequest
FixtureLeaderboardCandidate = model.FixtureLeaderboardCandidate
FixtureLeaderboardCandidateSnapshot = model.FixtureLeaderboardCandidateSnapshot
FixtureLeaderboardRow = model.FixtureLeaderboardRow
FixtureLeaderboardPage = model.FixtureLeaderboardPage
FixtureLeaderboardResourceLimits = model.FixtureLeaderboardResourceLimits
FixtureLeaderboardProvider = providers.FixtureLeaderboardProvider
FixtureLeaderboardService = service.FixtureLeaderboardService
LeaderboardError = model.LeaderboardError
LeaderboardRequestError = model.LeaderboardRequestError
LeaderboardResourceError = model.LeaderboardResourceError
LeaderboardUnavailableError = model.LeaderboardUnavailableError
LeaderboardIntegrationError = model.LeaderboardIntegrationError

__all__ = (  # noqa: RUF022 - ratified public order is contractual
    "PublicationSequence",
    "LeaderboardSnapshotSequence",
    "LeaderboardCursor",
    "ListFixtureLeaderboardRequest",
    "FixtureLeaderboardCandidate",
    "FixtureLeaderboardCandidateSnapshot",
    "FixtureLeaderboardRow",
    "FixtureLeaderboardPage",
    "FixtureLeaderboardResourceLimits",
    "FixtureLeaderboardProvider",
    "FixtureLeaderboardService",
    "LeaderboardError",
    "LeaderboardRequestError",
    "LeaderboardResourceError",
    "LeaderboardUnavailableError",
    "LeaderboardIntegrationError",
)

del model, providers, service
