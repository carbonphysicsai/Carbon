"""F08 (Ribbed Bracket)'s public DEVELOPMENT research parts (the shared direct campaign's,
bound to F08 (Ribbed Bracket)'s spec; `carbon.direct_campaign.research`)."""

from __future__ import annotations

from carbon.direct_campaign import research as _shared

from .contracts import SPEC


def challenge_parts(version):
    """F08 (Ribbed Bracket)'s research parts for exactly `version` (no default)."""
    return _shared.challenge_parts(SPEC, version)


def objective():
    return _shared.objective(SPEC)


def population_and_sampling():
    return _shared.population_and_sampling(SPEC)


def measurement_contract():
    return _shared.measurement_contract(SPEC)


class F08PublicMaterial(_shared.DirectPublicMaterial):
    def __init__(self, version, root="."):
        super().__init__(SPEC, version, root)


def make_research_service(*, version, **kwargs):
    return _shared.make_research_service(SPEC, version=version, **kwargs)
