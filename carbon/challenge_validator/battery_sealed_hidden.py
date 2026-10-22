"""Battery's sealed exam batches (VALIDATOR_BATTERY_SEALED_RULINGS_20261022), producer side.

The family's values (Validator, 2026-10-22), as F02's and F08's:
- producer id `battery-sealed-exam`: a producer-only id, never a registry
  Challenge; the batches serve whichever Battery version the owner launches;
- population: fresh uniform draws over the hull of the 2.0 material's 420-grid
  region (`carbon.battery_sealed.population`), disjoint from every published
  Battery case;
- 8 cases per batch, served kind `screening`;
- rotation: one active version, at most 90 days (648,000 blocks);
- the rule cites the pack and the sealed evaluation version and never
  restates scoring;
- a reference is the pinned truth image's standard 30-cycle record plus the
  cycle-1 plating margin at mesh 160 (rtol 1e-6) and the battery-plating-ref-v2
  label from the pinned reader (`carbon.battery.plating_v2`), never
  reimplemented;
- a sealed batch is graded as a private evaluation pack in the development
  pack's format (`carbon.challenge_kit.battery_sealed_pack`) by
  `battery-dual-sealed-batch-8-v1`. There is no second scoring path.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "battery-sealed-exam"
CHALLENGE_VERSION = "1.0"
RULE_SCHEMA = "carbon.battery.sealed-pool-rule.v1"
DOCUMENT_SCHEMA = "carbon.battery.sealed-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.battery.sealed-deployment.v1"
STORE_SCHEMA = "carbon.battery.sealed-store.v1"
AUTHORITY = "VALIDATOR_BATTERY_SEALED_RULINGS_20261022"
#: The pinned truth image's digest (`carbon.battery.truth.TRUTH_IMAGE`; a test
#: pins the two equal). Its PyBaMM overlay is pinned by the lock whose sha256
#: every record carries (`overlay_lock_sha256`).
SOLVER_IMAGE = "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
RUNNER = Path("scripts/dev/battery/battery_exam_runner.py")
TERMINAL = ("OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
KINDS = ("screening",)
BATCH_CASES = 8
ROTATION_EVERY_BLOCKS = 648_000  # the 90-day maximum
ACTIVE_BATCHES = 1
PACK_VERSION = "battery-sealed-development-1"
EVALUATION_VERSION = "battery-dual-sealed-batch-8-v1"
LABELS = ("FEASIBLE", "INFEASIBLE", "UNRESOLVED")
VOLTAGE_POINTS = 121
CAPACITY_POINTS = 4
MESH = 160


class BatterySealedError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_digest():
    """The sealed family's contract: the 2.0 charge-protocol inputs and outputs."""
    from carbon.battery import domain

    from .interface import digest

    return digest(
        {
            "inputs": list(domain.INPUTS),
            "outputs": list(domain.OUTPUTS),
            "grid": [domain.GRID_STEP_S, domain.WINDOW_S],
            "capacity_cycles": list(domain.CAPACITY_CYCLES),
        }
    )


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.battery_sealed.population import POPULATION_VERSION

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
        "population": {
            "version": POPULATION_VERSION,
            "law": "420-grid hull, fresh uniform draws",
        },
        "solver_image": SOLVER_IMAGE,
        "plating": {"reference": "battery-plating-ref-v2", "mesh": MESH},
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
    """A sealed batch document's shape and admissibility: `{case_id: inputs}`."""
    from carbon.battery_sealed.domain import INPUTS
    from carbon.battery_sealed.population import admitted

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
    return cases


def overlay_lock_sha256(repository=REPOSITORY):
    """The overlay lock's sha256 (hex): what every record must carry."""
    from carbon.battery import truth

    return truth.lock_digest(repository).removeprefix("sha256:")


def check_reference(record, inputs):
    """One terminal record for a case with `inputs`. An OK record carries the
    standard reference's outputs, the mesh-160 plating margin and the v2 label
    from the pinned reader, all finite and consistent."""
    if (
        type(record) is not dict
        or record.get("status") not in TERMINAL
        or record.get("inputs") != inputs
        or record.get("image") != SOLVER_IMAGE
        or record.get("overlay_lock_sha256") != overlay_lock_sha256()
    ):
        raise ValueError("reference")
    if record["status"] != "OK":
        return
    outputs = record.get("outputs")
    m160 = record.get("plating_margin_m160_v")
    plating = record.get("plating")
    if (
        type(outputs) is not dict
        or set(outputs)
        != {"voltage_v", "temperature_c", "plating_margin_v", "capacity_ah"}
        or len(outputs["voltage_v"]) != VOLTAGE_POINTS
        or len(outputs["temperature_c"]) != VOLTAGE_POINTS
        or len(outputs["capacity_ah"]) != CAPACITY_POINTS
        or not _finite(outputs["plating_margin_v"])
        or not all(
            _finite(v)
            for key in ("voltage_v", "temperature_c", "capacity_ah")
            for v in outputs[key]
        )
        or not _finite(m160)
        or type(plating) is not dict
        or set(plating) != {"label", "rule"}
        or plating["label"] not in LABELS
    ):
        raise ValueError("reference")
    if plating_label(outputs["plating_margin_v"], m160) != plating:
        raise ValueError("reference")


def plating_label(m20, m160):
    """The case's plating-onset label: the pinned v2 reader's, recomputed, never
    trusted. Where v2 makes no claim (|m20| >= 15 mV) the gate-plating-v2 rule
    keeps the mesh-20 verdict, which at that distance from EV4's 1.97 mV band
    is the margin's sign (OWNER-BATTERY-GATE-PLATING-V2-01)."""
    from carbon.battery import plating_v2

    claim = plating_v2.reader(str(REPOSITORY))(float(m20), float(m160))
    if claim is not None:
        return claim
    return {
        "label": "FEASIBLE" if m20 > 0 else "INFEASIBLE",
        "rule": "m20-no-claim-gate-plating-v2",
    }


def published_keys(repository):
    from .confirmation_sources import source_for

    return source_for(CHALLENGE_ID).published(repository)


def overlap_key(inputs):
    from .confirmation_sources import source_for

    return source_for(CHALLENGE_ID).key(inputs)


def _source():
    from .confirmation_sources import source_for

    return source_for(CHALLENGE_ID)


def load_deployment(path):
    """`{"schema", "store"}`, plus `"custody"` for the producer. Owner-only."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise BatterySealedError("battery_sealed_deployment_missing") from None
    # Checked outside the parse's `except ValueError`, which the typed error
    # (a ValueError) would otherwise be relabelled by.
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise BatterySealedError("battery_sealed_deployment_not_owner_only")
    try:
        config = json.loads(path.read_text())
    except ValueError:
        raise BatterySealedError("battery_sealed_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise BatterySealedError("battery_sealed_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory,
        name="battery_sealed",
        schema=STORE_SCHEMA,
        error_type=BatterySealedError,
    )
