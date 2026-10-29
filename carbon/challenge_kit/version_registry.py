"""Every served Challenge version, declared once (the Lead, 2026-10-23;
OWNER-MODULAR-CHALLENGES-01).

Each (Challenge, version) names, explicitly and resolved, what it is built
from and judged by: its TRAIN, its output encoding, its served allowlist and
step caps, its development pack, its development and sealed evaluation
versions, its construction routes (Level 0, catalog, direct) and graph
training adapter, the catalog entries it offers, and its approved facts.
Readers ask here; an unregistered version is refused (`UnregisteredVersion`),
never mapped to a nearby or earlier one. Nothing is inherited at read time:
a construction-only successor (graph route v2: "1.5 = 1.4's TRAIN and scorer
plus graph v2") writes its predecessor's values out in full, and
`predecessor` records where they came from.

Pure data with no imports, so any module may read it. The scorers' own
tables (`scoring.*_dual_pack.VERSIONS`, `SEALED_VERSIONS`) stay the authority
inside each producer's identity; a test holds them equal to this one.
"""

from __future__ import annotations

from dataclasses import dataclass

MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"
F08 = "f08-ribbed-bracket"
F02 = "f02"
BATTERY = "battery-fastcharge-ageing-development-v1"

#: TRAIN artifacts, by name (each pinned by sha256 in its loader).
F08_TRAIN_V1 = "f08-dev-train-255-v1"
F08_TRAIN_V2 = "f08-pinned-train-v2"
F02_TRAIN = "f02-pinned-train40-v2"
MOTOR_TRAIN = "motor-dev-train-150-v1"
COOLING_TRAIN = "cooling-dev-train-400-v1"
COOLING_TRAIN_ENCODED = "cooling-dev-train-400-v2-encoded"
BATTERY_TRAIN_V1 = "battery-public-train-v1"
BATTERY_TRAIN_V2 = "battery-public-train-v2"
#: Cooling 1.3's law-safe output encoding (`cold_plate.output_encoding`).
COOLING_LAW_SAFE = "cooling-law-safe-output-encoding"
#: The rebuild wall of the graph route v2 versions, in seconds, for the build and
#: for inference each: twice the slowest served entry (323.8 s), rounded up
#: (OWNER-REBUILD-WALL-11MIN-01, testnet; supersedes OWNER-SANDBOX-REBUILD-WALL-01's
#: 30 minutes). Every other version keeps the C-03 600 seconds.
REBUILD_LIMIT_SECONDS = 648
#: The whole-task wall of those versions: REBUILD_LIMIT_SECONDS plus twice the measured
#: 149.5 s non-build part. Every other version keeps `MAX_TASK_WALL_SECONDS` (1800), so
#: its published kit bytes do not move.
REBUILD_TASK_WALL_SECONDS = 947


def task_wall_seconds(rebuild_wall_seconds):
    """The published whole-task wall for a version with this rebuild wall (None: legacy)."""
    from carbon.development_session.local_diagnostic_plan import MAX_TASK_WALL_SECONDS

    return (
        MAX_TASK_WALL_SECONDS
        if rebuild_wall_seconds is None
        else REBUILD_TASK_WALL_SECONDS
    )


class UnregisteredVersion(ValueError):
    """A (Challenge, version) the registry does not declare."""


@dataclass(frozen=True)
class Version:
    challenge_id: str
    version: str
    #: The TRAIN artifact's name (above).
    train: str
    #: The served Level 4 allowlist: "v5", "v6", "v7" or "v8".
    allowlist: str
    #: Whether the construction limits keep fixed training-step caps.
    step_caps: bool
    #: The development pack version (`physical_pack`, `battery_pack`).
    pack_version: str
    #: (evaluation version, case id) of the development dual pack, or None.
    development_evaluation: tuple | None
    #: The sealed evaluation version that grades it, or None.
    sealed_evaluation: str | None
    #: The campaign it composes: "level0", "catalog" (Motor/Cooling catalog
    #: practice), "direct" (F08/F02 direct recipes), "battery_catalog"
    #: (Battery's catalog version) or None (none).
    campaign: str | None
    #: Whether it serves Carbon's backbone catalog (`backbone_catalog`).
    catalog: bool = False
    #: The graph training adapter it serves: None, "v1", "v2" (graph route v2)
    #: or "battery" (`battery_graph_adapter`).
    graph_adapter: str | None = None
    #: The law-safe output encoding of its rows, or None (native outputs).
    output_encoding: str | None = None
    #: The versions whose catalog manifest entries it offers. Each entry's
    #: pair-identity receipt binds TRAIN and interface digests; a successor
    #: lists its predecessor only where those digests are equal (a test).
    catalog_entries_from: tuple = ()
    #: The `direct_campaign.facts` key whose owner-approved facts it uses.
    facts: str | None = None
    #: The version it adds a construction change to, recorded, never read
    #: through.
    predecessor: str | None = None
    #: Its build and inference wall, in seconds: REBUILD_LIMIT_SECONDS, or
    #: None for the C-03 600 seconds (every version before graph route v2).
    rebuild_wall_seconds: int | None = None


def _v(*args, **kwargs):
    entry = Version(*args, **kwargs)
    return (entry.challenge_id, entry.version), entry


_F08_DEV_V1 = ("f08-dual-accepted-bank-8-v1", "f08-accepted-bank-8")
_F08_DEV_NL1 = ("f08-dual-near-limit-bank-8-v1", "f08-near-limit-bank-8")
_F08_DEV_NL2 = ("f08-dual-near-limit-bank-8-v2", "f08-near-limit-bank-8")
_F08_SEALED = "f08-dual-sealed-grid-8x1-v2"
#: Pool-graded sealed evaluation names (V8_RULINGS section 11; the Validator names them): a new
#: evaluation is a new exam key, so no king carries over.
_F08_POOL_SEALED = "f08-pool-sealed-v1"
_F02_POOL_SEALED = "f02-pool-sealed-v1"
_MOTOR_POOL_SEALED = "motor-pool-sealed-v1"
_COOLING_POOL_SEALED = "cooling-pool-sealed-v1"
_F02_DEV_1 = ("f02-dual-development-bank-8-v1", "f02-development-bank-8")
_F02_DEV_2 = ("f02-dual-development-bank-8-v2", "f02-development-bank-8")
#: Dev-pack v2 (Validator 2026-10-23): the new graph-route-v2 versions' development pack is
#: the practice grid (public cells and public-seeded probes) graded by the sealed v2
#: grader (`scoring.dev_grid`); a new version, pre-publish.
_F08_DEV_GRID = ("f08-dual-development-grid-v2", "f08-development-grid-8x1")
_F02_DEV_GRID = ("f02-dual-development-grid-v2", "f02-development-grid-8x1")
_MOTOR_DEV_GRID = ("motor-dual-development-grid-v2", "motor-development-grid-8x6")
_COOLING_DEV_GRID = ("cooling-dual-development-grid-v2", "cooling-development-grid-8x6")
_F02_SEALED = "f02-dual-sealed-grid-8x1-v2"
_MOTOR_DEV_2 = ("motor-dual-development-bank-90-v2", "motor-development-bank-90")
_MOTOR_DEV_3 = ("motor-dual-development-bank-90-v3", "motor-development-bank-90")
_MOTOR_SEALED = "motor-dual-sealed-batch-30-v2"
_COOLING_DEV_2 = ("cooling-dual-development-bank-48-v2", "cooling-development-bank-48")
_COOLING_DEV_3 = ("cooling-dual-development-bank-48-v3", "cooling-development-bank-48")
_COOLING_DEV_4 = ("cooling-dual-development-bank-48-v4", "cooling-development-bank-48")
_COOLING_SEALED = "cooling-dual-sealed-batch-16-v2"
_BATTERY_DEV = ("battery-dual-development-bank-v2", "battery-development-bank")
_BATTERY_SEALED = "battery-dual-sealed-grid-4x35-v1"

VERSIONS = dict(
    (
        # --- Motor --------------------------------------------------------
        _v(
            MOTOR,
            "1.0",
            MOTOR_TRAIN,
            "v5",
            True,
            "motor-normal-construction-development-1",
            _MOTOR_DEV_2,
            None,
            "level0",
        ),
        _v(
            MOTOR,
            "1.1",
            MOTOR_TRAIN,
            "v6",
            False,
            "motor-normal-construction-development-2",
            _MOTOR_DEV_3,
            _MOTOR_SEALED,
            None,
        ),
        _v(
            MOTOR,
            "1.2",
            MOTOR_TRAIN,
            "v6",
            False,
            "motor-normal-construction-development-3",
            _MOTOR_DEV_3,
            _MOTOR_SEALED,
            "catalog",
            catalog=True,
            catalog_entries_from=("1.2",),
        ),
        _v(
            MOTOR,
            "1.3",
            MOTOR_TRAIN,
            "v7",
            False,
            "motor-normal-construction-development-4",
            _MOTOR_DEV_3,
            _MOTOR_SEALED,
            "catalog",
            catalog=True,
            catalog_entries_from=("1.3",),
        ),
        # Graph route v2: 1.3 plus Carbon's graph training adapter v2.
        _v(
            MOTOR,
            "1.4",
            MOTOR_TRAIN,
            "v8",
            False,
            "motor-normal-construction-development-5",
            _MOTOR_DEV_GRID,
            _MOTOR_SEALED,
            "catalog",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("1.4", "1.3"),
            predecessor="1.3",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # Pool grade: 1.4's construction, TRAIN and interface, graded by the pool grader.
        _v(
            MOTOR,
            "1.5",
            MOTOR_TRAIN,
            "v8",
            False,
            "motor-normal-construction-development-6",
            _MOTOR_DEV_GRID,
            _MOTOR_POOL_SEALED,
            "catalog",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("1.4", "1.3"),
            predecessor="1.4",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # --- Cooling ------------------------------------------------------
        _v(
            COOLING,
            "1.0",
            COOLING_TRAIN,
            "v5",
            True,
            "cooling-normal-construction-development-1",
            _COOLING_DEV_2,
            None,
            "level0",
        ),
        _v(
            COOLING,
            "1.1",
            COOLING_TRAIN,
            "v6",
            False,
            "cooling-normal-construction-development-2",
            _COOLING_DEV_3,
            _COOLING_SEALED,
            None,
        ),
        _v(
            COOLING,
            "1.2",
            COOLING_TRAIN,
            "v7",
            False,
            "cooling-normal-construction-development-3",
            _COOLING_DEV_3,
            _COOLING_SEALED,
            "catalog",
            catalog=True,
            catalog_entries_from=("1.2",),
        ),
        _v(
            COOLING,
            "1.3",
            COOLING_TRAIN_ENCODED,
            "v7",
            False,
            "cooling-normal-construction-development-4",
            _COOLING_DEV_4,
            _COOLING_SEALED,
            "catalog",
            catalog=True,
            output_encoding=COOLING_LAW_SAFE,
            catalog_entries_from=("1.3",),
        ),
        # Graph route v2: 1.3 plus Carbon's graph training adapter v2.
        _v(
            COOLING,
            "1.4",
            COOLING_TRAIN_ENCODED,
            "v8",
            False,
            "cooling-normal-construction-development-5",
            _COOLING_DEV_GRID,
            _COOLING_SEALED,
            "catalog",
            catalog=True,
            graph_adapter="v2",
            output_encoding=COOLING_LAW_SAFE,
            catalog_entries_from=("1.4", "1.3"),
            predecessor="1.3",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # Pool grade: 1.4's construction, TRAIN and interface, graded by the pool grader.
        _v(
            COOLING,
            "1.5",
            COOLING_TRAIN_ENCODED,
            "v8",
            False,
            "cooling-normal-construction-development-6",
            _COOLING_DEV_GRID,
            _COOLING_POOL_SEALED,
            "catalog",
            catalog=True,
            graph_adapter="v2",
            output_encoding=COOLING_LAW_SAFE,
            catalog_entries_from=("1.4", "1.3"),
            predecessor="1.4",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # OWNER-COOLING-HOTSPOT-GATE-DROP-01: a prospective response contract.
        # Construction/TRAIN are unchanged; no constants are adopted here.
        _v(
            COOLING,
            "1.6",
            COOLING_TRAIN_ENCODED,
            "v8",
            False,
            "cooling-normal-construction-development-7",
            ("cooling-dual-development-grid-v3", "cooling-development-grid-8x6"),
            "cooling-pool-sealed-v2",
            "catalog",
            catalog=True,
            graph_adapter="v2",
            output_encoding=COOLING_LAW_SAFE,
            catalog_entries_from=("1.4", "1.3"),
            predecessor="1.5",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # --- F08 (Ribbed Bracket) -----------------------------------------
        _v(
            F08,
            "1.0",
            F08_TRAIN_V1,
            "v5",
            True,
            "f08-normal-construction-development-1",
            _F08_DEV_V1,
            None,
            None,
        ),
        _v(
            F08,
            "1.1",
            F08_TRAIN_V2,
            "v5",
            True,
            "f08-normal-construction-development-2",
            _F08_DEV_NL1,
            None,
            None,
        ),
        _v(
            F08,
            "1.2",
            F08_TRAIN_V2,
            "v6",
            False,
            "f08-normal-construction-development-3",
            _F08_DEV_NL2,
            _F08_SEALED,
            None,
        ),
        _v(
            F08,
            "1.3",
            F08_TRAIN_V2,
            "v7",
            False,
            "f08-normal-construction-development-4",
            _F08_DEV_NL2,
            _F08_SEALED,
            None,
        ),
        _v(
            F08,
            "1.4",
            F08_TRAIN_V2,
            "v7",
            False,
            "f08-normal-construction-development-5",
            _F08_DEV_NL2,
            _F08_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v1",
            catalog_entries_from=("1.4",),
            facts="1.4",
        ),
        # Graph route v2: 1.4 plus the adapter v2. Its interface document
        # names its version, so 1.4's receipted entries are not offered.
        _v(
            F08,
            "1.5",
            F08_TRAIN_V2,
            "v8",
            False,
            "f08-normal-construction-development-6",
            _F08_DEV_GRID,
            _F08_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("1.5",),
            facts="1.5",
            predecessor="1.4",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # Pool grade: 1.5's construction, graded by the pool grader
        # (`scoring.pool_exam`). Its interface document names its version, so it offers
        # 1.5's receipted entries only under the cross-version pair rule: the interface
        # documents differ in identity fields only (`backbone_catalog.carries`).
        _v(
            F08,
            "1.6",
            F08_TRAIN_V2,
            "v8",
            False,
            "f08-normal-construction-development-7",
            _F08_DEV_GRID,
            _F08_POOL_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("1.5",),
            facts="1.6",
            predecessor="1.5",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # OWNER-F08-FREQUENCY-BAND-DROP-01: prospective answer sanity only;
        # construction and design feasibility retain 1.6's registered material.
        _v(
            F08,
            "1.7",
            F08_TRAIN_V2,
            "v8",
            False,
            "f08-normal-construction-development-8",
            ("f08-dual-development-grid-v3", "f08-development-grid-8x1"),
            "f08-pool-sealed-v2",
            "direct",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("1.5",),
            facts="1.7",
            predecessor="1.6",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # --- F02 (Burst Thermal) ------------------------------------------
        _v(
            F02,
            "2.0",
            F02_TRAIN,
            "v5",
            True,
            "f02-normal-construction-development-2",
            _F02_DEV_1,
            None,
            None,
        ),
        _v(
            F02,
            "2.1",
            F02_TRAIN,
            "v6",
            False,
            "f02-normal-construction-development-3",
            _F02_DEV_2,
            _F02_SEALED,
            None,
        ),
        _v(
            F02,
            "2.2",
            F02_TRAIN,
            "v7",
            False,
            "f02-normal-construction-development-4",
            _F02_DEV_2,
            _F02_SEALED,
            None,
        ),
        _v(
            F02,
            "2.3",
            F02_TRAIN,
            "v7",
            False,
            "f02-normal-construction-development-5",
            _F02_DEV_2,
            _F02_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v1",
            catalog_entries_from=("2.3",),
            facts="2.3",
        ),
        _v(
            F02,
            "2.4",
            F02_TRAIN,
            "v8",
            False,
            "f02-normal-construction-development-6",
            _F02_DEV_GRID,
            _F02_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("2.4",),
            facts="2.4",
            predecessor="2.3",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # Pool grade: 2.4's construction, graded by the pool grader (`scoring.pool_exam`);
        # it offers 2.4's entries under the cross-version pair rule (`backbone_catalog.carries`).
        _v(
            F02,
            "2.5",
            F02_TRAIN,
            "v8",
            False,
            "f02-normal-construction-development-7",
            _F02_DEV_GRID,
            _F02_POOL_SEALED,
            "direct",
            catalog=True,
            graph_adapter="v2",
            catalog_entries_from=("2.4",),
            facts="2.5",
            predecessor="2.4",
            rebuild_wall_seconds=REBUILD_LIMIT_SECONDS,
        ),
        # --- Battery (2.3 joins after pack-set-canonical lands) -----------
        _v(
            BATTERY,
            "1.0",
            BATTERY_TRAIN_V1,
            "v5",
            True,
            "battery-normal-construction-development-2",
            None,
            None,
            "level0",
        ),
        _v(
            BATTERY,
            "2.0",
            BATTERY_TRAIN_V2,
            "v6",
            False,
            "battery-normal-construction-development-3",
            _BATTERY_DEV,
            _BATTERY_SEALED,
            None,
        ),
        _v(
            BATTERY,
            "2.1",
            BATTERY_TRAIN_V2,
            "v7",
            False,
            "battery-normal-construction-development-4",
            _BATTERY_DEV,
            _BATTERY_SEALED,
            None,
        ),
        # Battery 2.2 is not served: Battery is out of launch
        # (OWNER-BATTERY-OUT-OF-LAUNCH-01) and 2.2 was never completed.
    )
)


def entry(challenge_id: str, version: str) -> Version:
    """The declared entry, or `UnregisteredVersion`: never a nearby one."""
    found = VERSIONS.get((challenge_id, version))
    if found is None:
        raise UnregisteredVersion(
            f"unregistered Challenge version {(challenge_id, version)!r}"
        )
    return found


def find(challenge_id: str, version: str) -> Version | None:
    return VERSIONS.get((challenge_id, version))


def versions(challenge_id: str, **where) -> tuple:
    """The Challenge's registered versions, in order, whose fields equal
    `where`."""
    return tuple(
        e.version
        for (cid, _), e in sorted(
            VERSIONS.items(), key=lambda item: tuple(map(int, item[0][1].split(".")))
        )
        if cid == challenge_id and all(getattr(e, k) == v for k, v in where.items())
    )


def keys(**where) -> frozenset:
    """Every registered (Challenge, version) whose fields equal `where`."""
    return frozenset(
        key
        for key, e in VERSIONS.items()
        if all(getattr(e, k) == v for k, v in where.items())
    )
