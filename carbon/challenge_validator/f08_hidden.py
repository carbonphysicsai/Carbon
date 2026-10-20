"""F08's sealed exam batches (OWNER-F02-F08-EXAM-DRAW-01), producer side.

The family's values (Validator, 2026-10-20), as F02's:
- version: F08 1.2, the step-2 version miners are graded on;
- population: the approved TRAIN near-limit law N1r, stratified so the seed
  chooses the geometry (`carbon.f08.population`, Validator-accepted
  2026-10-20), disjoint from every published F08 geometry;
- 8 cases per batch, served kind `screening` (the producer's served tier; the
  private pack's cohort `decision_near_limit` carries the decision at the
  0.15 mm/N limit, as the development exam's);
- rotation: one active version, at most 90 days (648,000 blocks);
- the rule cites the pack and the sealed evaluation version and never
  restates scoring;
- a sealed batch is graded as a private evaluation pack in the development
  pack's format (`carbon.challenge_kit.f08_sealed_pack`) by the dual
  adapter's sealed evaluation version (no response pairs; the interval
  receipt is the batch's own solver evidence). There is no second scoring
  path.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "f08-ribbed-bracket"
CHALLENGE_VERSION = "1.2"
RULE_SCHEMA = "carbon.f08.hidden-pool-rule.v1"
DOCUMENT_SCHEMA = "carbon.f08.hidden-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.f08.hidden-deployment.v1"
STORE_SCHEMA = "carbon.f08.hidden-store.v1"
AUTHORITY = "OWNER-F02-F08-EXAM-DRAW-01"
#: RR-PACKS-07's verified native solver build: SHA-256 of the canonical
#: {kind, solvers} of rr07-pod-environment.json (f08_exam_runner.solvers_id;
#: a test pins the two equal).
SOLVER_IMAGE = "sha256:6098f39d40d642ab7aaa3fc300a44ff866e330db52b8d8b1bd9ee9709b0098c3"
RUNNER = Path("scripts/dev/reference_packages/calculix/f08_exam_runner.py")
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
KINDS = ("screening",)
BATCH_CASES = 8
ROTATION_EVERY_BLOCKS = 648_000  # the 90-day maximum
ACTIVE_BATCHES = 1
PACK_VERSION = "f08-normal-construction-development-3"
#: The Test Engineer's sealed F08 evaluation version (1.2's measurement
#: unchanged; Validator, 2026-10-20).
EVALUATION_VERSION = "f08-dual-sealed-batch-8-v1"
RUNGS = ("h3", "h2.25", "h1.7")
ZETAS = ("zeta_0.005", "zeta_0.01", "zeta_0.02")
OBSERVED = (
    "static_tip_mm_per_n",
    "worst_dynamic_mm_per_n",
    "mass_kg",
    "cad_mass_kg",
    "modes",
    "mode_ladder",
    "in_band_modes_hz",
)


class F08FamilyError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_digest():
    """F08 1.2's construction-kit digest (the sealed family binds the kit)."""
    from carbon.challenge_kit import f08_public

    from .interface import digest

    return digest(f08_public.construction_kit(CHALLENGE_ID, CHALLENGE_VERSION))


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.f08.population import POPULATION_VERSION

    if EVALUATION_VERSION is None:
        raise F08FamilyError("f08_sealed_evaluation_version_unregistered")
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
        "population": {"version": POPULATION_VERSION, "law": "TRAIN near-limit N1r"},
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
    from carbon.f08.domain import INPUTS
    from carbon.f08.population import admitted

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


def _solvers_digest(solvers):
    raw = json.dumps(solvers, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def check_reference(record, inputs):
    """One terminal record for a case with `inputs`; an OK record carries the
    development bank's reference-rung values, its three rungs' worst dynamic
    compliance and a passing, asymptotic convergence verdict, all finite."""
    if (
        type(record) is not dict
        or record.get("status") not in TERMINAL
        or record.get("inputs") != inputs
        or record.get("image") != SOLVER_IMAGE
    ):
        raise ValueError("reference")
    if record["status"] != "OK":
        return
    outputs = record.get("outputs")
    damping = record.get("damping")
    rungs = record.get("rung_worst_dynamic_mm_per_n")
    verdict = record.get("convergence")
    if (
        type(outputs) is not dict
        or set(outputs) != set(OBSERVED)
        or not _finite(outputs["static_tip_mm_per_n"])
        or not _finite(outputs["worst_dynamic_mm_per_n"])
        or (outputs["mode_ladder"] or {}).get("verdict") != "PASS"
        or type(damping) is not dict
        or set(damping) != set(ZETAS)
        or not all(
            _finite(damping[z].get("worst_mm_per_n"))
            and _finite(damping[z].get("worst_hz"))
            for z in ZETAS
        )
        or type(rungs) is not dict
        or set(rungs) != set(RUNGS)
        or not all(_finite(v) for v in rungs.values())
        or rungs["h1.7"] != outputs["worst_dynamic_mm_per_n"]
        or record.get("reference_rung_h_mm") != 1.7
        or type(verdict) is not dict
        or verdict.get("asymptotic_ok") is not True
        or set(verdict.get("rungs") or {}) != {"h3", "h2.25"}
        or any(r.get("verdict") != "PASS" for r in verdict["rungs"].values())
        or type(record.get("solvers")) is not dict
        or _solvers_digest(record["solvers"]) != SOLVER_IMAGE
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
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise F08FamilyError("f08_hidden_deployment_not_owner_only")
        config = json.loads(path.read_text())
    except FileNotFoundError:
        raise F08FamilyError("f08_hidden_deployment_missing") from None
    except ValueError:
        raise F08FamilyError("f08_hidden_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise F08FamilyError("f08_hidden_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory, name="f08", schema=STORE_SCHEMA, error_type=F08FamilyError
    )
