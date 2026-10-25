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
1.3 and F02 2.2 keep their bytes. Battery 2.2, Battery's launch version
(OWNER-BATTERY-LAUNCH-VERSION-01; the Validator, 2026-10-22), is
Battery 2.1 plus the catalog binding (`battery.catalog_version`); 2.1 keeps
its bytes.
"""

from __future__ import annotations

from . import version_registry as _registry

MOTOR = _registry.MOTOR
COOLING = _registry.COOLING
F08 = _registry.F08
F02 = _registry.F02
BATTERY = _registry.BATTERY

#: Each set is read from the one version registry (`version_registry`), where
#: every version declares its allowlist, step caps and catalog explicitly.
#: The step-2 versions: served v6, no fixed training-step caps, no catalog.
STEP2 = _registry.keys(allowlist="v6", step_caps=False, catalog=False)
#: The backbone-catalog versions (OWNER-BACKBONE-CATALOG-01; Validator: each
#: Challenge's next version, never in place), graph route v2 included.
CATALOG = _registry.keys(catalog=True)
#: The versions serving allowlist v7 (the Validator, 2026-10-20).
V7 = _registry.keys(allowlist="v7")
#: The pre-publish graph-route-v2 versions serving allowlist v8 (OWNER-GRAPH-OPS-OPEN-01;
#: Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025): F08 1.5, F02 2.4, Motor 1.4 and
#: Cooling 1.4. Battery 2.2 keeps its base version's v7 until its own table moves.
V8 = _registry.keys(allowlist="v8")
#: Versions registered before step 2: served v5 and their step caps, unchanged.
EXISTING = _registry.keys(step_caps=True)

UnregisteredVersion = _registry.UnregisteredVersion


def _known(challenge_id: str, version: str) -> tuple[str, str]:
    _registry.entry(challenge_id, version)
    return (challenge_id, version)


def is_step2(challenge_id: str, version: str) -> bool:
    """True for a step-2 version (v6, no step caps), catalog versions included;
    False for an existing one."""
    key = _known(challenge_id, version)
    return key in STEP2 or key in CATALOG or key in V7 or key in V8


def serves_catalog(challenge_id: str, version: str) -> bool:
    """Whether a version serves Carbon's backbone catalog."""
    return _known(challenge_id, version) in CATALOG


def serves_v7(challenge_id: str, version: str) -> bool:
    """Whether a version serves allowlist v7."""
    return _known(challenge_id, version) in V7


def serves_v8(challenge_id: str, version: str) -> bool:
    """Whether a version serves allowlist v8."""
    return _known(challenge_id, version) in V8


def serves_uncapped(challenge_id: str, version: str) -> bool:
    """Whether a version serves an allowlist without model-size caps (v7 or v8)."""
    return _known(challenge_id, version) in V7 or _known(challenge_id, version) in V8


def material_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The allowlist a version's served construction material carries: v7 on
    the v7 catalog versions, v6 on the other step-2 and catalog versions, v5
    on the versions registered before step 2."""
    from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes
    from carbon.level4.allowlist import served_bytes, v7_bytes, v8_bytes

    if serves_v8(challenge_id, version):
        return v8_bytes()
    if serves_v7(challenge_id, version):
        return v7_bytes()
    return served_bytes() if is_step2(challenge_id, version) else allowlist_v5_bytes()


def worker_resources(challenge_id: str, version: str):
    """The worker resources version a version's construction limits publish
    (`worker_resources_version` of its served allowlist): the allowlist's
    version string when it gets the larger worker resources, else None
    (today's profile, unchanged). The kit builders pass it into the worker
    profile so the published `reconstruction_resource_policy` is the one the
    executor demands (`verify_direct_resource_policy`)."""
    from carbon.level4.allowlist import Allowlist
    from carbon.reconstruction.worker.model import worker_resources_version

    return worker_resources_version(
        Allowlist(material_allowlist_bytes(challenge_id, version)).version
    )


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
