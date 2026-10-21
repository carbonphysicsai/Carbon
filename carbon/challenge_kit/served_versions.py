"""What each registered Challenge version serves: its Level 4 allowlist and
whether its construction limits keep fixed training-step caps.

The step-2 batch (Validator, STEP2_BATCH_VERSIONS_20261020) gives each
Challenge one new version carrying v6 as the served allowlist and no step caps
(OWNER-REBUILD-TIME-LIMIT-01: the registered rebuild wall time is the only
training limit). Existing versions keep their bytes, v5 and their caps, and
are never rescored. There is no default: an unregistered (Challenge, version)
is refused, never mapped to a nearby one.
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
CATALOG = frozenset({(MOTOR, "1.2")})
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
    if key not in STEP2 and key not in EXISTING and key not in CATALOG:
        raise UnregisteredVersion(f"unregistered Challenge version {key!r}")
    return key


def is_step2(challenge_id: str, version: str) -> bool:
    """True for a step-2 version (v6, no step caps), catalog versions included;
    False for an existing one."""
    key = _known(challenge_id, version)
    return key in STEP2 or key in CATALOG


def serves_catalog(challenge_id: str, version: str) -> bool:
    """Whether a version serves Carbon's backbone catalog."""
    return _known(challenge_id, version) in CATALOG


def material_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The allowlist a version's served construction material carries."""
    from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes
    from carbon.level4.allowlist import served_bytes

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
