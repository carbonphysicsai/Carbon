"""Which Challenge versions are another version plus a construction change.

Graph route v2 (owner: "No carbon limits please!"; Launchpad brief
LP_GRAPH_ROUTE_V2_BRIEF_20261023; Validator ruling, no-limits binding in
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022) adds one version per Challenge
that is its predecessor plus Carbon's graph training adapter v2
(`development_session.physical_graph_adapter_v2`). It changes construction
only: the TRAIN, interface, development bank, measurement, sealed exam and
evaluation version are the predecessor's, recorded here and never implied.

A reader that needs a version's material (TRAIN, bank, facts, pack, sealed
evaluation) asks `material_version`, so a new version resolves to the one
that owns that material, and an unregistered version is refused, never mapped
to a nearby one. What is the version's own - its identity, construction
limits and graph adapter - is keyed by the version itself.
"""

from __future__ import annotations

MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"
F08 = "f08-ribbed-bracket"
F02 = "f02"
BATTERY = "battery-fastcharge-ageing-development-v1"

#: Graph route v2: (Challenge, new version) -> its predecessor. Battery 2.3
#: joins once its 2.2 graph adapter lands (Launchpad, 2026-10-23).
GRAPH_ROUTE_V2 = {
    (F08, "1.5"): "1.4",
    (F02, "2.4"): "2.3",
    (MOTOR, "1.4"): "1.3",
    (COOLING, "1.4"): "1.3",
}
PREDECESSORS = dict(GRAPH_ROUTE_V2)
#: The successors that also offer their predecessor's catalog entries: each
#: entry's pair-identity receipt binds TRAIN and interface digests, and these
#: versions' digests equal their predecessor's (a test holds them equal).
#: F08 1.5 and F02 2.4 do not: their interface documents name their version,
#: so their digests differ and their entries need receipts of their own.
INHERITS_CATALOG = frozenset({(MOTOR, "1.4"), (COOLING, "1.4")})


def predecessor(challenge_id: str, version: str) -> str | None:
    """The version this one adds a construction change to, or None."""
    return PREDECESSORS.get((challenge_id, version))


def material_version(challenge_id: str, version: str) -> str:
    """The version that owns this version's material: itself, or its
    predecessor's, followed back while the predecessor is itself a
    construction-only successor."""
    seen = set()
    while (challenge_id, version) in PREDECESSORS:
        if version in seen:
            raise ValueError("version lineage cycle")
        seen.add(version)
        version = PREDECESSORS[(challenge_id, version)]
    return version


def catalog_versions(challenge_id: str, version: str) -> tuple:
    """The versions whose catalog entries `version` offers: itself, and its
    predecessor's where it inherits them (`INHERITS_CATALOG`)."""
    if (challenge_id, version) in INHERITS_CATALOG:
        return (
            version,
            *catalog_versions(challenge_id, predecessor(challenge_id, version)),
        )
    return (version,)


def serves_graph_route_v2(challenge_id: str, version: str) -> bool:
    """Whether a version serves Carbon's graph training adapter v2."""
    return (challenge_id, version) in GRAPH_ROUTE_V2


def successors(challenge_id: str, version: str) -> tuple:
    """Every registered version whose material is `version`'s, `version`
    first: the versions a reader of that material also serves."""
    return (version,) + tuple(
        new
        for (challenge, new), _ in sorted(PREDECESSORS.items())
        if challenge == challenge_id
        and new != version
        and material_version(challenge_id, new) == version
    )
