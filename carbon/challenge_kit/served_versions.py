"""What each registered Challenge version serves: its Level 4 allowlist and
whether its construction limits keep fixed training-step caps.

The step-2 batch (Validator, STEP2_BATCH_VERSIONS_20261020) gives each
Challenge one new version carrying v6 as the served allowlist and no step caps
(OWNER-REBUILD-TIME-LIMIT-01: the registered rebuild wall time is the only
training limit). Existing versions keep their bytes, v5 and their caps, and
are never rescored. There is no default: an unregistered (Challenge, version)
is refused, never mapped to a nearby one.

Allowlist v7 (Test Engineer, 294c3f1e7; Validator 2026-10-20) is served only
on each Challenge's catalog version: Cooling 1.2, Battery 2.1, F08 1.3, F02 2.2
and Motor 1.3 (Motor 1.2 plus v7). Motor 1.2 keeps v6. Motor 1.2, Motor 1.3
and Cooling 1.2 also serve the backbone catalog.

F08 1.4 and F02 2.3 (the Validator, 2026-10-20: graph joins them before they
freeze; no 1.5 / 2.4) serve v7, the backbone catalog binding and Carbon's
graph training adapter (`development_session.physical_graph_adapter`); F08
1.3 and F02 2.2 keep their bytes.
"""

from __future__ import annotations

MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"
F08 = "f08-ribbed-bracket"
F02 = "f02"
BATTERY = "battery-fastcharge-ageing-development-v1"

#: The step-2 versions: served v6, no fixed training-step caps.
STEP2 = frozenset(
    {
        (MOTOR, "1.1"),
        (COOLING, "1.1"),
        (F08, "1.2"),
        (F02, "2.1"),
        (BATTERY, "2.0"),
    }
)
#: The backbone-catalog versions (OWNER-BACKBONE-CATALOG-01; Validator: each
#: Challenge's next version, never in place): step-2 serving plus Carbon's
#: tested backbones by catalog id (`carbon.backbone_catalog`).
#: Cooling 1.2 serves it too (owner priority via the Test Lead, 2026-10-20):
#: only Motor served the catalog before because no Cooling entry was tested.
#: Cooling's entries arrive by pipeline add, each with its own Cooling
#: pair-identity receipt; until one does, Cooling 1.2's catalog is empty and
#: its catalog campaign refuses to start (`carbon.cold_plate.campaign`). This
#: binds Cooling 1.2's limits to its catalog before it freezes (open for the
#: Validator to confirm, as F08 1.4 / F02 2.3 bind theirs before freezing).
CATALOG = frozenset(
    {
        (MOTOR, "1.2"),
        (MOTOR, "1.3"),
        (COOLING, "1.2"),
        (COOLING, "1.3"),
        # The Validator, 2026-10-20: F08 1.4 and F02 2.3 bind the catalog (and
        # Carbon's graph training adapter) before they freeze.
        (F08, "1.4"),
        (F02, "2.3"),
        # Graph route v2 (`version_lineage.GRAPH_ROUTE_V2`): each its
        # predecessor plus Carbon's graph training adapter v2.
        (MOTOR, "1.4"),
        (COOLING, "1.4"),
        (F08, "1.5"),
        (F02, "2.4"),
    }
)
#: Each Challenge's catalog version, serving allowlist v7 (the Validator,
#: 2026-10-20) with step-2 serving. A version's construction limits bind the
#: exact catalog it serves: Motor 1.3 and Cooling 1.2, and F08 1.4 / F02 2.3
#: (no entries yet); Battery 2.1, F08 1.3 and F02 2.2 bind none, and are never
#: changed in place to bind one.
V7 = frozenset(
    {
        (MOTOR, "1.3"),
        (COOLING, "1.2"),
        (COOLING, "1.3"),
        (F08, "1.3"),
        (F02, "2.2"),
        (BATTERY, "2.1"),
        # The Validator, 2026-10-20: F08 1.4 / F02 2.3 serve v7 with the catalog
        # binding and the graph training adapter.
        (F08, "1.4"),
        (F02, "2.3"),
        # Graph route v2, as their predecessors.
        (MOTOR, "1.4"),
        (COOLING, "1.4"),
        (F08, "1.5"),
        (F02, "2.4"),
    }
)
#: Versions registered before step 2: served v5 and their step caps, unchanged.
EXISTING = frozenset(
    {
        (MOTOR, "1.0"),
        (COOLING, "1.0"),
        (F08, "1.0"),
        (F08, "1.1"),
        (F02, "2.0"),
        (BATTERY, "1.0"),
    }
)


class UnregisteredVersion(ValueError):
    """A (Challenge, version) neither the step-2 batch nor history registers."""


def _known(challenge_id: str, version: str) -> tuple[str, str]:
    key = (challenge_id, version)
    if key not in STEP2 and key not in EXISTING and key not in CATALOG | V7:
        raise UnregisteredVersion(f"unregistered Challenge version {key!r}")
    return key


def is_step2(challenge_id: str, version: str) -> bool:
    """True for a step-2 version (v6, no step caps), catalog versions included;
    False for an existing one."""
    key = _known(challenge_id, version)
    return key in STEP2 or key in CATALOG or key in V7


def serves_catalog(challenge_id: str, version: str) -> bool:
    """Whether a version serves Carbon's backbone catalog."""
    return _known(challenge_id, version) in CATALOG


def serves_v7(challenge_id: str, version: str) -> bool:
    """Whether a version serves allowlist v7."""
    return _known(challenge_id, version) in V7


def material_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The allowlist a version's served construction material carries: v7 on
    the v7 catalog versions, v6 on the other step-2 and catalog versions, v5
    on the versions registered before step 2."""
    from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes
    from carbon.level4.allowlist import served_bytes, v7_bytes

    if serves_v7(challenge_id, version):
        return v7_bytes()
    return served_bytes() if is_step2(challenge_id, version) else allowlist_v5_bytes()


def graph_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The allowlist a version's direct graph recipes validate against: its
    material's, except Battery 1.0, whose graph path has always used v1."""
    from carbon.level4.allowlist import PATH

    if _known(challenge_id, version) == (BATTERY, "1.0"):
        return PATH.read_bytes()
    return material_allowlist_bytes(challenge_id, version)


def step_caps(challenge_id: str, version: str) -> bool:
    """Whether a version's construction limits keep fixed training-step caps."""
    return not is_step2(challenge_id, version)


def graph_intake_bounds(challenge_id: str, version: str) -> dict:
    """The intake bounds a version's graph submissions are read under: those
    of its graph allowlist (`intake.bounds_for`), containment only on a v7
    version (owner, 2026-10-21: no model-size caps) and the owner's `BOUNDS`
    on every other. A version this table does not register (the synthetic
    Challenge, or an unknown one) gets the owner's `BOUNDS`, never v7's."""
    from carbon.level4 import intake
    from carbon.level4.allowlist import Allowlist

    try:
        raw = graph_allowlist_bytes(challenge_id, version)
    except UnregisteredVersion:
        return dict(intake.BOUNDS)
    return intake.bounds_for(Allowlist(raw))
