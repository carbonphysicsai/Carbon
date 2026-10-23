"""F02's sealed exam batches (OWNER-F02-F08-EXAM-DRAW-01), producer side.

The family's values (Validator, 2026-10-20):
- version: F02 2.1, the step-2 version miners are graded on;
- population: the approved TRAIN near-limit law S1 with fresh seeds
  (`carbon.f02.population`), disjoint from every published F02 schedule;
- 8 cases per batch, served kind `screening` (the producer's served tier; the
  private pack's cohort `decision_cold_eight` carries the decision, as the
  development exam's);
- rotation: one active version, at most 90 days (648,000 blocks); weekly fresh
  draws come from the backlog through exam rotation, not from the family;
- the rule document cites the pack and evaluation versions and never restates
  scoring: the scoring producer stays the single source of truth;
- a sealed batch is graded as a private evaluation pack in the development
  pack's format (`carbon.challenge_kit.f02_sealed_pack`) by the dual adapter's
  sealed evaluation version (no response pairs; the interval receipt is the
  batch's own solver evidence). There is no second scoring path.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "f02"
CHALLENGE_VERSION = "2.1"
#: Challenge versions whose evaluation packs are built from these 2.1 sealed
#: batches: 2.1, the v7 catalog 2.2 and the catalog + graph 2.3, each of which
#: changes only the construction kit (Validator, 2026-10-20: one rule, a catalog version is graded from its
#: predecessor's sealed batches). The batches stay 2.1's.
SERVED_VERSIONS = (CHALLENGE_VERSION, "2.2", "2.3")
RULE_SCHEMA = "carbon.f02.hidden-pool-rule.v1"
DOCUMENT_SCHEMA = "carbon.f02.hidden-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.f02.hidden-deployment.v1"
STORE_SCHEMA = "carbon.f02.hidden-store.v1"
AUTHORITY = "OWNER-F02-F08-EXAM-DRAW-01"
#: The pinned, MMS-verified F02 Elmer image (f02_readiness.IMAGE; a test pins
#: the two equal): the 2026-10-21 rebuild, re-pinned by the Validator on its MMS
#: and A5 lineage (docs/development/evidence/f02-rebuild-20261021/); the RR-04
#: image it replaces is lost on every host.
SOLVER_IMAGE = "sha256:fe8a5b1abebf56bbd9cd1aae2ee08f1825b2991abc0bb14b5be3fae26e6512ec"
RUNNER = Path("scripts/dev/reference_packages/elmer/f02_exam_runner.py")
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
KINDS = ("screening",)
BATCH_CASES = 8
ROTATION_EVERY_BLOCKS = 648_000  # the 90-day maximum
ACTIVE_BATCHES = 1
PACK_VERSION = "f02-normal-construction-development-3"
EVALUATION_VERSION = "f02-dual-sealed-grid-8x1-v2"
OBSERVED = (
    "peak_top_c",
    "extra_energy_j",
    "first_95c_crossing_s",
    "peak_time_s",
    "recovery_s",
)


class F02FamilyError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_digest():
    """F02 2.1's construction-kit digest (F02 has no capability-registry entry)."""
    from carbon.challenge_kit import f02_public

    from .interface import digest

    return digest(f02_public.construction_kit(CHALLENGE_ID, CHALLENGE_VERSION))


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.f02.population import POPULATION_VERSION

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
        "population": {"version": POPULATION_VERSION, "law": "TRAIN near-limit S1"},
        "solver_image": SOLVER_IMAGE,
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
    from carbon.f02.domain import INPUTS
    from carbon.f02.population import admitted

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


def check_reference(record, inputs):
    """One terminal record for a case with `inputs`; an OK record carries the
    development bank's observed values and its three rung peaks, finite."""
    if (
        type(record) is not dict
        or record.get("status") not in TERMINAL
        or record.get("inputs") != inputs
        or record.get("image") != SOLVER_IMAGE
    ):
        raise ValueError("reference")
    if record["status"] == "OK":
        outputs = record.get("outputs")
        peaks = record.get("rung_peaks_c")
        if (
            type(outputs) is not dict
            or set(outputs) != set(OBSERVED)
            or not _finite(outputs["peak_top_c"])
            or not _finite(outputs["extra_energy_j"])
            or type(peaks) is not dict
            or set(peaks) != {"primary", "mesh2", "dt0.5"}
            or not all(_finite(v) for v in peaks.values())
            or peaks["primary"] != outputs["peak_top_c"]
            or (record.get("rung_comparison") or {}).get("pass") is not True
        ):
            raise ValueError("reference")


def published_keys(repository):
    from .confirmation_sources import source_for

    return source_for(CHALLENGE_ID).published(repository)


def overlap_key(inputs):
    from .confirmation_sources import source_for

    return source_for(CHALLENGE_ID).key(inputs)


def load_deployment(path):
    """`{"schema", "store"}`, plus `"custody"` for the producer. Owner-only."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise F02FamilyError("f02_hidden_deployment_missing") from None
    # Checked outside the parse's `except ValueError`, which the typed error
    # (a ValueError) would otherwise be relabelled by.
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise F02FamilyError("f02_hidden_deployment_not_owner_only")
    try:
        config = json.loads(path.read_text())
    except ValueError:
        raise F02FamilyError("f02_hidden_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise F02FamilyError("f02_hidden_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory, name="f02", schema=STORE_SCHEMA, error_type=F02FamilyError
    )
