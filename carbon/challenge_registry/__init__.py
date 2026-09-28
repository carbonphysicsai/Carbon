"""Carbon's Challenge adapter registry: one shared workflow, per-Challenge capability.

A miner selects a Challenge by its exact id and version plus an execution
profile, and Carbon resolves that selection here or refuses it with a typed
reason. There is no default and no fallback: an unknown, unimplemented,
deferred or unusable combination is an error, never another Challenge.
"""

from .registry import (
    CATALOG_SCHEMA,
    DESCRIPTION_SCHEMA,
    ChallengeDeferred,
    ChallengeNotImplemented,
    ChallengeRetired,
    HostFacts,
    ProfileUnavailable,
    ResolutionError,
    UnknownChallenge,
    UnsupportedVersion,
    catalog,
    describe,
    entries,
    resolve,
)

__all__ = [
    "CATALOG_SCHEMA",
    "DESCRIPTION_SCHEMA",
    "ChallengeDeferred",
    "ChallengeNotImplemented",
    "ChallengeRetired",
    "HostFacts",
    "ProfileUnavailable",
    "ResolutionError",
    "UnknownChallenge",
    "UnsupportedVersion",
    "catalog",
    "describe",
    "entries",
    "resolve",
]
