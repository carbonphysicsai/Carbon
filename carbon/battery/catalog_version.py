"""Battery's backbone-catalog versions: a base Battery version plus the catalog
binding (the Validator's ruling, 2026-10-22).

Battery 2.2, Battery's launch version (OWNER-BATTERY-LAUNCH-VERSION-01), is
Battery 2.1 plus Carbon's tested backbones by catalog id. Its
exam, public TRAIN, gates, development bank and pack set are 2.1's, unchanged;
only its construction limits differ, by its own version and the exact catalog
it serves (`backbone_catalog.served`), so a catalog recipe binds that catalog.
Its catalog is empty until each entry has its own pair-identity receipt.

This is the binding's own adapter, beside the pinned Battery modules
(`implementation_versions.MODULES`), which it never edits: `BASES` names the
version a catalog version is built on, so binding the catalog onto another
base (2.0, if the owner picks it for launch) is one line here.

It also states, for the shared direct campaign (`carbon.direct_campaign`,
`spec.BATTERY_CATALOG`), the research view of the served interface (names,
units and axes of the established Battery outputs), public TRAIN's facts and
practice scoring: Battery's own registered practice measurement
(`practice.score_practice`: the exam's gates, TRAIN scales and frozen
tolerances) on the bank's public PRACTICE rows. Graph recipes run through
Battery's graph training adapter (`development_session.battery_graph_adapter`;
the Validator's ruling (a), 2026-10-22), on the base version's graph route;
its block is in the limits. Nothing here is an exam, a qualification or LIVE
authority.
"""

from __future__ import annotations

from pathlib import Path

from carbon.development_session.profile import canonical, digest

from . import challenge, construction_material, domain

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = challenge.CHALLENGE.challenge_id
#: Each catalog version and the Battery version whose exam, TRAIN, gates, bank
#: and pack set it serves unchanged.
BASES = {"2.2": "2.1"}
VERSIONS = tuple(BASES)
#: The served interface's units (`scoring.battery_dual_pack.OUTPUT`; the
#: Battery contracts' c_rate, celsius and fraction for the inputs).
INPUT_UNITS = ("C-rate", "C-rate", "degC", "1")
OUTPUT_UNITS = ("V", "degC", "V", "Ah")
#: Each output's axes in the served flat order (`construction_material`).
OUTPUT_AXES = (
    (("time", domain.GRID_POINTS),),
    (("time", domain.GRID_POINTS),),
    (),
    (("cycle", len(domain.CAPACITY_CYCLES)),),
)
PRACTICE_RECORD = (
    "carbon.battery.practice.score_practice: the exam's gates, TRAIN scales "
    "and frozen tolerances on the public PRACTICE references"
)


def _version(challenge_id: str, version: str) -> str:
    if challenge_id != CHALLENGE_ID or version not in BASES:
        raise challenge.MaterialMismatch(
            f"unregistered Battery catalog version {version!r}"
        )
    return BASES[version]


def material(version: str, root: Path | None = None) -> dict:
    """The served construction material of a catalog version: its base's,
    under the version's own key and limits (the base's plus the catalog)."""
    from carbon.backbone_catalog import served
    from carbon.challenge_kit.served_versions import material_allowlist_bytes
    from carbon.development_session import battery_graph_adapter
    from carbon.registry import ChallengeKey

    from .construction_bundle_material import versioned_material

    base = _version(CHALLENGE_ID, version)
    found = versioned_material(base, root)
    if material_allowlist_bytes(CHALLENGE_ID, version) != found["allowlist_bytes"]:
        raise challenge.MaterialMismatch(
            f"Battery {version} serves another allowlist than {base}"
        )
    limits = {
        **found["construction_limits_document"],
        "challenge": {"id": CHALLENGE_ID, "version": version},
        # OWNER-BACKBONE-CATALOG-01: the exact catalog this version serves; a
        # catalog recipe's catalog_digest must equal it.
        "backbone_catalog": {
            "schema": served.SCHEMA,
            "digest": served.digest(CHALLENGE_ID, version),
        },
        # The Validator's ruling (a): Battery's graph training adapter, on the
        # base version's graph route.
        "graph_training_adapter": battery_graph_adapter.adapter_block(
            CHALLENGE_ID, version
        ),
    }
    found.update(
        {
            "challenge_key": ChallengeKey(CHALLENGE_ID, version),
            "construction_kit": {
                **found["construction_kit"],
                "version": version,
                "construction_limits_digest": digest(canonical(limits)),
            },
            "construction_limits_document": limits,
            # The receiver names served cases by canonical identifiers; the
            # base bank's EV4 decision rows are named "ev4:...". So a catalog
            # version names each bank row by its position, as F02's TRAIN rows
            # are named, and keeps the bank's own ids beside them, in order.
            "practice_case_ids": tuple(
                f"bank-{index:04d}" for index in range(len(found["practice_case_ids"]))
            ),
            "practice_case_sources": tuple(found["practice_case_ids"]),
        }
    )
    return found


def construction_kit(challenge_id: str, version: str) -> dict:
    _version(challenge_id, version)
    return material(version)["construction_kit"]


def construction_limits_document(challenge_id: str, version: str) -> dict:
    _version(challenge_id, version)
    return material(version)["construction_limits_document"]


def interface_document(challenge_id: str, version: str) -> dict:
    """The research view of the served interface: its names in the served
    flat order, their units and axes. The kit binds the served interface
    itself (`served_interface_digest`)."""
    from .construction_bundle_material import interface_document as served

    _version(challenge_id, version)
    interface = served()
    return {
        "schema": "carbon.battery.catalog-research-interface.v1",
        "served_interface_digest": digest(canonical(interface)),
        "input": {"names": list(domain.INPUTS), "units": list(INPUT_UNITS)},
        "output": {
            "names": list(interface["outputs"]["flat_order"]),
            "units": list(OUTPUT_UNITS),
            "axes": [[list(axis) for axis in axes] for axes in OUTPUT_AXES],
            "width": construction_material.OUTPUT_WIDTH,
        },
        "train_dtype": "<f8",
    }


def train_facts(challenge_id: str, version: str) -> dict:
    """Public TRAIN's registered facts: TRAIN v1, the base version's."""
    _version(challenge_id, version)
    return {
        "train_cases": challenge.TRAIN_V1_CASES,
        "train_dtype": "<f8",
        "train_provenance_sha256": "sha256:" + challenge.TRAIN_V1_SHA256,
        "file": "train-v1.jsonl.gz",
        "format": "gzip JSON lines: one record per case, inputs and outputs, float64",
    }


def error_scale(version: str) -> dict:
    """Battery's registered practice measurement (no value is chosen here)."""
    return {
        "record": PRACTICE_RECORD,
        "scales": "the exam's TRAIN scales (carbon.battery.calibration)",
        "error": "the exam's per-case error over its TRAIN scales",
        "aggregation": "the exam aggregate over the scored PRACTICE rows",
        "direction": "lower_is_better",
    }


def practice_summary(version: str, rows, found: dict, root=None) -> dict:
    """Score the bank's public PRACTICE rows with Battery's own practice
    measurement; the other bank rows are queried, never scored here."""
    from . import practice

    root = REPOSITORY if root is None else Path(root)
    names = list(found["interface_document"]["outputs"]["flat_order"])
    case_ids = found["practice_case_sources"]
    public = practice.PracticeSet.load(root)
    picked = {case_ids[i]: rows[i] for i in found["public_practice_rows"]}
    if sorted(picked) != sorted(public.case_ids):
        raise ValueError("battery_practice_rows_differ")
    order = list(public.case_ids)
    predictions = construction_material.output_predictions(
        [picked[case] for case in order], order
    )
    _rows, summary = practice.score_practice(
        predictions, public, challenge.PublicMaterial.load(root), root
    )
    clean = practice._summary(summary)
    return {
        "cases": len(rows),
        "outputs": names,
        "dtype": "float64",
        "n_cases": clean["n_cases"],
        "n_scored": clean["n_scored"],
        "score": clean["score"],
        "aggregate_error": clean["score"],
        "eligible": clean["eligible"],
        "gate_failures": clean["gate_failures"],
        "components": clean["components"],
        "error_scale": error_scale(version),
        "status": "battery_practice_measurement",
    }


def research_outputs(challenge_id: str, version: str) -> tuple:
    """The research view's outputs: Battery's trajectories on its time grid,
    its cycle-1 plating margin and its capacity checkpoints, as Battery's own
    research view draws them (`battery.research_view`)."""
    from carbon.challenge_registry.research_view import Axis, OutputSpec

    from .research_view import LABELS

    _version(challenge_id, version)
    grid = Axis("time", "s", tuple(range(0, domain.WINDOW_S + 1, domain.GRID_STEP_S)))
    cycles = Axis("cycle", None, tuple(domain.CAPACITY_CYCLES))
    kinds = {
        "voltage_v": ("time_series", (grid,)),
        "temperature_c": ("time_series", (grid,)),
        "plating_margin_v": ("scalar", ()),
        "capacity_ah": ("checkpoint_vector", (cycles,)),
    }
    return tuple(
        OutputSpec(name, kinds[name][0], unit, LABELS[name], kinds[name][1])
        for name, unit in zip(domain.OUTPUTS, OUTPUT_UNITS, strict=True)
    )
