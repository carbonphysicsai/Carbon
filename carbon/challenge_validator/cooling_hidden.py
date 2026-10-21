"""Cooling's sealed exam batches, producer side (owner-approved Cooling draw;
Validator, 2026-10-20: VALIDATOR_COOLING_RR14_DECISION and
VALIDATOR_MAINNET_RECAL_DECISIONS §2).

The family's values:
- version: Cooling 1.1, the step-2 version miners are graded on;
- population: one placed 4 designs x 4 conditions grid per batch
  (`carbon.cold_plate_exam.population`), disjoint from every published case;
- references: graded-hotspot-v1 at r = 2√2, judged by the graded heat-in
  analysis version (`scripts/dev/cold_plate/reference/cooling_exam_runner.py`);
- 16 cases, served kind `screening`; the private pack's cohort
  `decision_sealed_grid` (design_id / condition_id per row) carries the decision;
- rotation: one active version, at most 90 days (648,000 blocks);
- the rule cites the pack and the sealed evaluation version and never
  restates scoring; grading is the dual adapter's sealed version.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "chip-cold-plate"
CHALLENGE_VERSION = "1.1"
RULE_SCHEMA = "carbon.cold-plate.hidden-pool-rule.v1"
DOCUMENT_SCHEMA = "carbon.cold-plate.sealed-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.cold-plate.sealed-deployment.v1"
STORE_SCHEMA = "carbon.cold-plate.sealed-store.v1"
AUTHORITY = "OWNER-CADENCE-AND-ROTATION-02"
#: The pinned Cooling OpenFOAM image (openfoam.IMAGE; a test pins the two equal).
SOLVER_IMAGE = (
    "opencfd/openfoam-default@sha256:"
    "33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319"
)
RUNNER = Path("scripts/dev/cold_plate/reference/cooling_exam_runner.py")
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
KINDS = ("screening",)
BATCH_CASES = 16
ROTATION_EVERY_BLOCKS = 648_000  # the 90-day maximum
ACTIVE_BATCHES = 1
PACK_VERSION = "cooling-normal-construction-development-2"
EVALUATION_VERSION = "cooling-dual-sealed-batch-16-v1"
REFERENCE_OPTIONS = {"mesh_family": "graded-hotspot-v1", "resolution": 2 * math.sqrt(2)}
ANALYSIS_VERSION = "carbon.cold-plate.graded-heat-in.v1"


class CoolingFamilyError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_digest():
    """Cooling 1.1's served construction-kit digest."""
    from carbon.challenge_kit import physical_material

    from .interface import digest

    kit = physical_material.bundle_material(CHALLENGE_ID, CHALLENGE_VERSION)[
        "construction_kit"
    ]
    return digest(kit)


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.cold_plate_exam.population import POPULATION_VERSION

    return {
        "schema": RULE_SCHEMA,
        "authority": AUTHORITY,
        "status": "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING",
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        # Cited, never restated: the scoring producer owns the exam rule.
        "exam": {
            "pack_version": PACK_VERSION,
            "evaluation_version": EVALUATION_VERSION,
        },
        "population": {"version": POPULATION_VERSION, "law": "placed 4 x 4 grid"},
        "solver_image": SOLVER_IMAGE,
        "reference": {**REFERENCE_OPTIONS, "analysis_version": ANALYSIS_VERSION},
        "references": {"terminal": list(TERMINAL), "scored": ["OK"]},
        "kinds": list(KINDS),
        "hidden_duplicates": 0,
        "batch_cases": BATCH_CASES,
        "rotation": {"basis": "finalized_block", "every_blocks": ROTATION_EVERY_BLOCKS},
        "active_batches": ACTIVE_BATCHES,
    }


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def check_document(document):
    """A sealed batch document: 16 admitted cases forming one full grid."""
    from carbon.cold_plate_exam.domain import INPUTS
    from carbon.cold_plate_exam.population import admitted, grid_of

    if (
        type(document) is not dict
        or set(document)
        != {"schema", "challenge", "role", "kind", "population", "cases"}
        or document["schema"] != DOCUMENT_SCHEMA
        or document["challenge"] != {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION}
        or type(document["role"]) is not str
        or document["kind"] not in KINDS
        or type(document["cases"]) is not list
        or len(document["cases"]) != BATCH_CASES
    ):
        raise ValueError("document")
    cases = {}
    for case in document["cases"]:
        if (
            type(case) is not dict
            or set(case) != {"case_id", "inputs"}
            or type(case["case_id"]) is not str
            or case["case_id"] in cases
            or type(case["inputs"]) is not dict
            or set(case["inputs"]) != set(INPUTS)
            or not all(_finite(v) for v in case["inputs"].values())
            or not admitted(case["inputs"])
        ):
            raise ValueError("case")
        cases[case["case_id"]] = case["inputs"]
    grid_of(list(cases.values()))  # ValueError unless one full 4 x 4 grid
    return cases


def check_reference(record, inputs):
    """One terminal record; an OK record was solved on the family at r = 2√2,
    judged by the graded analysis, with finite outputs of the exam's shape."""
    from carbon.cold_plate.analysis import REFERENCE_CHECKS
    from carbon.cold_plate.domain import PROFILE_SEGMENTS

    if (
        type(record) is not dict
        or record.get("status") not in TERMINAL
        or record.get("inputs") != inputs
    ):
        raise ValueError("reference")
    if record["status"] != "OK":
        return
    outputs = record.get("outputs")
    profile = outputs.get("profile_c") if type(outputs) is dict else None
    diagnostics = record.get("diagnostics")
    checks = record.get("checks")
    if (
        record.get("image") != SOLVER_IMAGE
        or record.get("options") != REFERENCE_OPTIONS
        or type(diagnostics) is not dict
        or diagnostics.get("analysis_version") != ANALYSIS_VERSION
        or not _finite(outputs.get("peak_c"))
        or not _finite(outputs.get("pressure_drop_pa"))
        or type(profile) is not list
        or len(profile) != PROFILE_SEGMENTS
        or not all(_finite(v) for v in profile)
        or type(checks) is not dict
        or not _finite(checks.get("energy_balance_rel"))
        or abs(checks["energy_balance_rel"]) > REFERENCE_CHECKS["energy_balance_rel"]
    ):
        raise ValueError("reference")


def _source():
    from .confirmation_sources import PopulationSource

    return PopulationSource(
        CHALLENGE_ID, "cold_plate_exam", ("cold-plate-*", "cooling-*")
    )


def published_keys(repository):
    return _source().published(repository)


def overlap_key(inputs):
    return _source().key(inputs)


def load_deployment(path):
    """`{"schema", "store"}`, plus `"custody"` for the producer. Owner-only."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise CoolingFamilyError("cooling_sealed_deployment_missing") from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise CoolingFamilyError("cooling_sealed_deployment_not_owner_only")
    try:
        config = json.loads(path.read_text())
    except ValueError:
        raise CoolingFamilyError("cooling_sealed_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise CoolingFamilyError("cooling_sealed_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory, name="cooling", schema=STORE_SCHEMA, error_type=CoolingFamilyError
    )
