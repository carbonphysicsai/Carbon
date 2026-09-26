"""Challenge entries, resolution and discovery documents.

Each entry names one Challenge and version, its lifecycle status and its
execution profiles. An IMPLEMENTED entry also carries an adapter that
describes the Challenge from its executable registrations:
- the construction contract and its capabilities;
- the public material allow-list;
- the exam semantics;
- the permitted feedback;
- an example validated by the same admission a submission meets.

RESERVED entries are launch Challenges whose interface exists only as a name
and a tracking issue. They say so, and refuse selection. DEFERRED entries are
portfolio candidates kept for history. RETIRED entries were once selectable and
are no longer on the research path; their code stays in the repository as
reference, they stay listed, and selecting one is refused.

A description separates *implemented* (Carbon has the code) from *usable
here* (this host, as the operator configured it, can run the profile now).
Usability is observed from the host: a present module, a configured image or
an installed runtime. It is never assumed, and never declared by the caller's
wish.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field

CATALOG_SCHEMA = "carbon.challenge-catalog.v1"
DESCRIPTION_SCHEMA = "carbon.challenge-description.v1"

IMPLEMENTED, RESERVED, DEFERRED, RETIRED = (
    "IMPLEMENTED",
    "RESERVED",
    "DEFERRED",
    "RETIRED",
)
CAPABILITY_REQUEST = (
    "Ask with the research workspace action capability_request "
    "{request:{purpose,operation,hypothesis,public_evidence,reason,"
    "expected_benefit,estimated_cost,minimal_safe_design,verification}} and an "
    "optional capability (a registry id). A request is recorded as demand; it "
    "grants nothing."
)


class ResolutionError(LookupError):
    """A selection Carbon refuses, with a stable code and the next step."""

    code = "challenge_resolution_failed"
    next_action = "List challenges and select an implemented, usable one."

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail

    def public(self):
        return {
            "code": self.code,
            "detail": self.detail,
            "next_action": self.next_action,
        }


class UnknownChallenge(ResolutionError):
    code = "challenge_unknown"


class UnsupportedVersion(ResolutionError):
    code = "challenge_version_unsupported"
    next_action = "Select a version the catalog lists for this Challenge."


class ChallengeNotImplemented(ResolutionError):
    code = "challenge_not_implemented"
    next_action = (
        "This launch Challenge is reserved; follow its tracking issue. "
        + CAPABILITY_REQUEST
    )


class ChallengeDeferred(ResolutionError):
    code = "challenge_deferred"
    next_action = "Deferred portfolio candidate; not selectable in this version."


class ChallengeRetired(ResolutionError):
    code = "challenge_retired"
    next_action = (
        "Retired from the research path; its code is kept for reference only. "
        "Select an implemented Challenge from the catalog."
    )


class ProfileUnavailable(ResolutionError):
    code = "execution_profile_unavailable"
    next_action = (
        "Select a profile the description lists as usable here, or ask the "
        "operator to configure the missing host requirement."
    )


@dataclass(frozen=True)
class ExecutionProfile:
    """One way a Challenge's research runs, and what the host must supply."""

    name: str
    summary: str
    backend: str
    #: Named host facts (`HostFacts`) this profile needs, all of them.
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class HostFacts:
    """What this host can run, observed rather than declared.

    `configured` holds operator-configured facts (a verified trusted worker
    image, a configured evaluation deployment); `observe()` adds the ones the
    host itself can answer.
    """

    facts: frozenset = frozenset()

    @staticmethod
    def observe(configured=()):
        found = set(configured)
        for module, fact in (("jax", "jax"), ("optax", "optax"), ("pybamm", "pybamm")):
            if importlib.util.find_spec(module) is not None:
                found.add(fact)
        if shutil.which("docker") is not None:
            found.add("docker_cli")
        return HostFacts(frozenset(found))

    def missing(self, profile):
        return [r for r in profile.requirements if r not in self.facts]


@dataclass(frozen=True)
class Entry:
    challenge_id: str
    version: str | None
    title: str
    status: str
    portfolio: str
    tracking: str | None
    profiles: tuple[ExecutionProfile, ...] = ()
    #: () -> the Challenge's own description (IMPLEMENTED only).
    describe: Callable | None = field(default=None, compare=False)

    def summary(self, host):
        profiles = []
        for profile in self.profiles:
            missing = host.missing(profile)
            profiles.append(
                {
                    "profile": profile.name,
                    "summary": profile.summary,
                    "backend": profile.backend,
                    "requirements": list(profile.requirements),
                    "implemented": self.status == IMPLEMENTED,
                    "usable_here": self.status == IMPLEMENTED and not missing,
                    "missing_here": missing,
                }
            )
        return {
            "challenge_id": self.challenge_id,
            "version": self.version,
            "title": self.title,
            "status": self.status,
            "portfolio": self.portfolio,
            "tracking": self.tracking,
            "profiles": profiles,
        }


CPU_RESEARCH = "cpu_research"


def _burgers():
    from .burgers import describe

    return describe()


def _battery():
    from .battery import describe

    return describe()


def _entries():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        BATTERY_CONTRACT,
        BURGERS_CHALLENGE,
        BURGERS_CONTRACT,
    )

    carrier = ("docker_cli", "trusted_worker_image", "jax", "optax")
    return (
        Entry(
            BURGERS_CHALLENGE,
            BURGERS_CONTRACT.version,
            "Burgers dynamics (DEVELOPMENT autoresearch, retired)",
            RETIRED,
            "historical_development",
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "JAX CPU practice in the isolated research carrier",
                    "jax-cpu/isolated-carrier",
                    carrier,
                ),
            ),
            _burgers,
        ),
        Entry(
            BATTERY_CHALLENGE,
            BATTERY_CONTRACT.version,
            "Battery fast charge and ageing (DEVELOPMENT)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#341",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "JAX CPU practice in the isolated research carrier; "
                    "exact Carbon recipe and training bytes staged",
                    "jax-cpu/isolated-carrier",
                    carrier,
                ),
            ),
            _battery,
        ),
        Entry(
            "chip-cold-plate",
            None,
            "AI-chip liquid cold plate (reserved)",
            RESERVED,
            "launch",
            "carbonphysicsai/Carbon#342",
        ),
        Entry(
            "electric-motor-magnetics",
            None,
            "Electric-motor magnetic design (reserved)",
            RESERVED,
            "launch",
            "carbonphysicsai/Carbon#344",
        ),
        Entry(
            "photonic-coupler",
            None,
            "Photonic coupler (reserved)",
            RESERVED,
            "launch",
            "carbonphysicsai/Carbon#345",
        ),
        Entry(
            "power-magnetics",
            None,
            "Power magnetics (deferred portfolio candidate)",
            DEFERRED,
            "deferred",
            "carbonphysicsai/Carbon#343",
        ),
        Entry(
            "airfoil",
            None,
            "Airfoils (deferred portfolio candidate)",
            DEFERRED,
            "deferred",
            "carbonphysicsai/Carbon#346",
        ),
    )


def entries():
    return _entries()


def _find(challenge_id, version):
    if type(challenge_id) is not str:
        raise UnknownChallenge("a challenge id string is required")
    matches = [e for e in _entries() if e.challenge_id == challenge_id]
    if not matches:
        raise UnknownChallenge(f"no Challenge {challenge_id!r} is registered")
    entry = matches[0]
    if entry.status == RETIRED:
        raise ChallengeRetired(f"{challenge_id} is retired from the research path")
    if entry.status == DEFERRED:
        raise ChallengeDeferred(f"{challenge_id} is a deferred portfolio candidate")
    if entry.status == RESERVED:
        raise ChallengeNotImplemented(
            f"{challenge_id} is a reserved launch Challenge ({entry.tracking})"
        )
    if version != entry.version:
        raise UnsupportedVersion(
            f"{challenge_id} is registered at version {entry.version}, not {version!r}"
        )
    return entry


def resolve(challenge_id, version, profile, *, host=None):
    """The entry for an exact (id, version, profile) usable on `host`.

    With `host=None` only implementation is checked: that is what a record
    or a validator needs. A door that is about to run work passes the host.
    """
    entry = _find(challenge_id, version)
    chosen = [p for p in entry.profiles if p.name == profile]
    if not chosen:
        raise ProfileUnavailable(f"{challenge_id} has no execution profile {profile!r}")
    if host is not None:
        missing = host.missing(chosen[0])
        if missing:
            raise ProfileUnavailable(
                f"{profile} is implemented but not usable here: "
                + ", ".join(missing)
                + " missing"
            )
    return entry, chosen[0]


def catalog(host=None):
    """Every registered Challenge, including the ones that cannot be selected."""
    host = host if host is not None else HostFacts.observe()
    return _json(
        {
            "schema": CATALOG_SCHEMA,
            "challenges": [e.summary(host) for e in _entries()],
            "selection": (
                "Select by exact challenge_id and version plus a profile. There is "
                "no default Challenge and no fallback."
            ),
            "authority": "discovery grants no authority",
        }
    )


def describe(challenge_id, version, *, host=None):
    """One Challenge's full description, or a typed refusal."""
    entry = _find(challenge_id, version)
    host = host if host is not None else HostFacts.observe()
    return _json(
        {
            "schema": DESCRIPTION_SCHEMA,
            **entry.summary(host),
            **entry.describe(),
            "how_to_request_unsupported": CAPABILITY_REQUEST,
        }
    )


def _json(document):
    """Plain, finite JSON: what every door can carry unchanged."""
    return json.loads(json.dumps(document, allow_nan=False))
