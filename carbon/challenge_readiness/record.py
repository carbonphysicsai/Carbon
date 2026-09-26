"""One versioned readiness record per launch-portfolio Challenge (#347).

A readiness record makes the Challenges comparable for readiness and cost.
It does not grade anything. Each Challenge keeps its own scientific ruler,
and this module owns no scheduler, scorer, seed service or evidence store.
It reads committed JSON and the typed records that
`scripts/dev/exam_design/runner.py` already writes.

Properties this module enforces when it builds a record, rather than
leaving them as conventions:
- **A pilot's outcome counts are the only source of its failure type.**
  Reference and infrastructure outcomes come from a closed vocabulary, and
  attribution is derived from the outcome, never declared beside it. A
  candidate-side outcome such as `GATE_FAILED` cannot appear in a reference
  pilot.
- **Maturity above SCOPED needs a case that actually ran OK.** A record
  cannot claim PILOTED, or recommend PROCEED or NARROW, with no OK case.
- **Unknown is not zero.** A cost with basis `unknown` or `not_applicable`
  carries no amount, and a cost total with any unknown item is unknown.
- **Proposed is not approved.** A limit carries a proposed value (or
  `HUMAN_INPUT`) and an approval slot. The approval is accepted only with a
  named authority and a scientific review in state APPROVED under that same
  authority.
- **Review axes are separate.** Numerical reference, scientific, security,
  customer and launch each have their own state. Launch cannot be APPROVED
  while any other axis is not.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

SCHEMA = "carbon.challenge-readiness.v1"
STATUS = "PROPOSED_DEVELOPMENT_DESIGN"
RECORDS = Path(__file__).resolve().parent / "records"

KEYS = {
    "schema",
    "challenge_id",
    "record_version",
    "status",
    "tracking",
    "sources",
    "decision",
    "design_variables",
    "outputs",
    "reference",
    "population",
    "limits",
    "maturity",
    "pilots",
    "costs",
    "reviews",
    "unresolved",
    "next_experiment",
    "recommendation",
}

#: The units a v1 record may declare. A unit outside this set is refused,
#: never passed through as free text.
UNITS = frozenset(
    {
        "1",
        "s",
        "K",
        "degC",
        "m",
        "mm",
        "um",
        "nm",
        "m^2",
        "kg",
        "kg/s",
        "L/min",
        "m^3/s",
        "Pa",
        "W",
        "W/m^2",
        "J",
        "V",
        "A",
        "A.h",
        "C-rate",
        "Ohm",
        "H",
        "T",
        "A/m",
        "N.m",
        "rpm",
        "rad",
        "dB",
    }
)

#: Reference-pilot outcomes. The first word of each attribution is what the
#: failure is charged to; nothing is ever charged to a candidate here.
OUTCOMES = {
    "OK": "none",
    "REFERENCE_SOLVER_FAILED": "reference",
    "REFERENCE_TIMEOUT": "reference",
    "REFERENCE_INVALID": "reference",
    "FAILED_INFRA": "infrastructure",
}
CANDIDATE_OUTCOMES = frozenset(
    {"GATE_FAILED", "SCORABLE", "CANDIDATE_FAILED", "REGRESSION", "IMPROVEMENT"}
)
CASE_KINDS = frozenset({"ordinary", "corner", "refinement", "diagnostic", "mixed"})

MATURITY = ("NOT_STARTED", "SCOPED", "PILOTED", "CAMPAIGN_COMPLETE")
BASELINE = ("NOT_STARTED", "SELECTED", "MEASURED")
COST_ITEMS = frozenset(
    {
        "startup",
        "mesh",
        "reference",
        "reconstruction",
        "inference",
        "finalist",
        "cleanup",
        "discarded",
    }
)
COST_BASES = frozenset({"measured", "estimated", "unknown", "not_applicable"})
REVIEW_AXES = ("numerical_reference", "scientific", "security", "customer", "launch")
REVIEW_STATES = frozenset({"NOT_STARTED", "IN_REVIEW", "BLOCKED", "APPROVED"})
RECOMMENDATIONS = frozenset({"PROCEED", "NARROW", "DEFER", "NONE"})
HUMAN_INPUT = "HUMAN_INPUT"


class ReadinessError(ValueError):
    """A record Carbon refuses, with a stable code."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(document):
    return "sha256:" + hashlib.sha256(canonical(document)).hexdigest()


def _text(value, code):
    if type(value) is not str or not value.strip():
        raise ReadinessError(code)
    return value


def _number(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _registry_ids():
    from carbon.challenge_registry.registry import entries

    return {e.challenge_id: e for e in entries()}


def _quantities(items, code):
    if type(items) is not list or not items:
        raise ReadinessError(code, "at least one is required")
    names = set()
    for item in items:
        if type(item) is not dict or set(item) != {"name", "unit", "description"}:
            raise ReadinessError(code, "each needs exactly name, unit, description")
        _text(item["name"], code)
        _text(item["description"], code)
        if item["unit"] not in UNITS:
            raise ReadinessError("unsupported_unit", repr(item["unit"]))
        if item["name"] in names:
            raise ReadinessError(code, "duplicate name " + item["name"])
        names.add(item["name"])


def _pilots(pilots):
    if type(pilots) is not list:
        raise ReadinessError("invalid_pilots")
    seen = set()
    ok = 0
    for pilot in pilots:
        if type(pilot) is not dict or set(pilot) != {
            "attempt_id",
            "case_kind",
            "outcomes",
            "evidence",
            "note",
        }:
            raise ReadinessError("invalid_pilot")
        attempt = _text(pilot["attempt_id"], "invalid_pilot")
        if attempt in seen:
            raise ReadinessError("duplicate_result_identity", attempt)
        seen.add(attempt)
        if pilot["case_kind"] not in CASE_KINDS:
            raise ReadinessError("invalid_pilot", "case_kind")
        _text(pilot["evidence"], "pilot_without_evidence")
        outcomes = pilot["outcomes"]
        if type(outcomes) is not dict or not outcomes:
            raise ReadinessError("pilot_without_cases", attempt)
        for outcome, count in outcomes.items():
            if outcome in CANDIDATE_OUTCOMES:
                raise ReadinessError("candidate_outcome_in_reference_pilot", outcome)
            if outcome not in OUTCOMES:
                raise ReadinessError("unknown_outcome", outcome)
            if type(count) is not int or count <= 0:
                raise ReadinessError("invalid_outcome_count", outcome)
        ok += outcomes.get("OK", 0)
    return ok


def _costs(costs):
    if type(costs) is not list or not costs:
        raise ReadinessError("invalid_costs", "list every item, unknown included")
    items = set()
    for cost in costs:
        if type(cost) is not dict or set(cost) != {
            "item",
            "basis",
            "usd",
            "unit",
            "evidence",
        }:
            raise ReadinessError("invalid_cost")
        if cost["item"] not in COST_ITEMS:
            raise ReadinessError("invalid_cost", "item " + repr(cost["item"]))
        if cost["item"] in items:
            raise ReadinessError("duplicate_cost_item", cost["item"])
        items.add(cost["item"])
        basis = cost["basis"]
        if basis not in COST_BASES:
            raise ReadinessError("invalid_cost", "basis " + repr(basis))
        if basis in ("unknown", "not_applicable"):
            if cost["usd"] is not None:
                raise ReadinessError("unknown_cost_with_amount", cost["item"])
        elif not _number(cost["usd"]) or cost["usd"] < 0:
            raise ReadinessError("cost_amount_required", cost["item"])
        if basis == "measured" and not isinstance(cost["evidence"], str):
            raise ReadinessError("measured_cost_without_evidence", cost["item"])
        _text(cost["unit"], "invalid_cost")


def _reviews(reviews):
    if type(reviews) is not dict or set(reviews) != set(REVIEW_AXES):
        raise ReadinessError("invalid_reviews", "exactly " + ", ".join(REVIEW_AXES))
    for axis in REVIEW_AXES:
        review = reviews[axis]
        if type(review) is not dict or set(review) != {"state", "authority"}:
            raise ReadinessError("invalid_reviews", axis)
        if review["state"] not in REVIEW_STATES:
            raise ReadinessError("invalid_reviews", axis + " state")
        if review["state"] == "APPROVED":
            _text(review["authority"], "approval_without_authority")
        elif review["authority"] is not None:
            raise ReadinessError("authority_without_approval", axis)
    others = [a for a in REVIEW_AXES if a != "launch"]
    if reviews["launch"]["state"] == "APPROVED" and any(
        reviews[a]["state"] != "APPROVED" for a in others
    ):
        raise ReadinessError("launch_approved_before_other_reviews")


def _limits(limits, reviews):
    if type(limits) is not list:
        raise ReadinessError("invalid_limits")
    names = set()
    for limit in limits:
        if type(limit) is not dict or set(limit) != {
            "name",
            "unit",
            "proposed",
            "approved",
            "basis",
        }:
            raise ReadinessError("invalid_limit")
        name = _text(limit["name"], "invalid_limit")
        if name in names:
            raise ReadinessError("invalid_limit", "duplicate " + name)
        names.add(name)
        if limit["unit"] not in UNITS:
            raise ReadinessError("unsupported_unit", repr(limit["unit"]))
        if limit["proposed"] != HUMAN_INPUT and not _number(limit["proposed"]):
            raise ReadinessError("invalid_limit", name + ": proposed")
        _text(limit["basis"], "invalid_limit")
        approved = limit["approved"]
        if approved is None:
            continue
        if type(approved) is not dict or set(approved) != {"value", "authority"}:
            raise ReadinessError("invalid_limit", name + ": approved")
        if not _number(approved["value"]):
            raise ReadinessError("invalid_limit", name + ": approved value")
        authority = _text(approved["authority"], "approval_without_authority")
        scientific = reviews["scientific"]
        if scientific["state"] != "APPROVED" or scientific["authority"] != authority:
            raise ReadinessError("approved_limit_without_scientific_approval", name)


def validate(document):
    """Return the document if it is a valid v1 record; refuse it otherwise."""
    if type(document) is not dict:
        raise ReadinessError("invalid_record")
    if document.get("schema") != SCHEMA:
        raise ReadinessError("unsupported_schema", repr(document.get("schema")))
    if set(document) != KEYS:
        raise ReadinessError("exact_keys_required", repr(sorted(set(document) ^ KEYS)))
    if document["status"] != STATUS:
        raise ReadinessError("unsupported_status", repr(document["status"]))
    version = document["record_version"]
    if type(version) is not int or version < 1:
        raise ReadinessError("unsupported_record_version", repr(version))
    registry = _registry_ids()
    entry = registry.get(document["challenge_id"])
    if entry is None:
        raise ReadinessError("unknown_challenge", repr(document["challenge_id"]))
    if document["tracking"] != entry.tracking:
        raise ReadinessError("tracking_mismatch", repr(document["tracking"]))
    sources = document["sources"]
    if type(sources) is not list or not sources:
        raise ReadinessError("sources_required")
    for source in sources:
        _text(source, "sources_required")
    decision = document["decision"]
    if type(decision) is not dict or set(decision) != {
        "engineering_decision",
        "intended_use",
        "buyer",
    }:
        raise ReadinessError("invalid_decision")
    for value in decision.values():
        _text(value, "invalid_decision")
    _quantities(document["design_variables"], "invalid_design_variables")
    _quantities(document["outputs"], "invalid_outputs")
    reference = document["reference"]
    if type(reference) is not dict or set(reference) != {
        "solver",
        "model",
        "licence",
        "applicability",
        "evidence",
    }:
        raise ReadinessError("invalid_reference")
    for key in ("solver", "model", "licence"):
        if reference[key] is not None:
            _text(reference[key], "invalid_reference")
    _text(reference["applicability"], "invalid_reference")
    if type(reference["evidence"]) is not list:
        raise ReadinessError("invalid_reference")
    population = document["population"]
    if type(population) is not dict or set(population) != {"proposed", "approved"}:
        raise ReadinessError("invalid_population")
    _text(population["proposed"], "invalid_population")
    if population["approved"] is not None:
        raise ReadinessError(
            "approved_population_not_supported",
            "v1 records a proposed population only",
        )
    reviews = document["reviews"]
    _reviews(reviews)
    _limits(document["limits"], reviews)
    ok_cases = _pilots(document["pilots"])
    maturity = document["maturity"]
    if type(maturity) is not dict or set(maturity) != {
        "baseline",
        "reference_execution",
    }:
        raise ReadinessError("invalid_maturity")
    if maturity["baseline"] not in BASELINE:
        raise ReadinessError("invalid_maturity", "baseline")
    if maturity["reference_execution"] not in MATURITY:
        raise ReadinessError("invalid_maturity", "reference_execution")
    if MATURITY.index(maturity["reference_execution"]) >= 2 and ok_cases == 0:
        raise ReadinessError("maturity_without_evidence", "no pilot case ran OK")
    _costs(document["costs"])
    unresolved = document["unresolved"]
    if type(unresolved) is not list:
        raise ReadinessError("invalid_unresolved")
    for item in unresolved:
        _text(item, "invalid_unresolved")
    _text(document["next_experiment"], "invalid_next_experiment")
    recommendation = document["recommendation"]
    if type(recommendation) is not dict or set(recommendation) != {
        "decision",
        "basis",
    }:
        raise ReadinessError("invalid_recommendation")
    if recommendation["decision"] not in RECOMMENDATIONS:
        raise ReadinessError("invalid_recommendation", "decision")
    _text(recommendation["basis"], "invalid_recommendation")
    if recommendation["decision"] in ("PROCEED", "NARROW") and ok_cases == 0:
        raise ReadinessError("recommendation_without_evidence", "no pilot case ran OK")
    return document


def load(path):
    """Read and validate one record file; return (document, digest)."""
    document = json.loads(Path(path).read_bytes())
    validate(document)
    return document, digest(document)


def load_all(directory=RECORDS):
    records = []
    for path in sorted(Path(directory).glob("*.json")):
        document, record_digest = load(path)
        if (
            path.name
            != f"{document['challenge_id']}.v{document['record_version']}.json"
        ):
            raise ReadinessError("record_filename_mismatch", path.name)
        records.append((document, record_digest))
    ids = [d["challenge_id"] for d, _ in records]
    if len(ids) != len(set(ids)):
        raise ReadinessError("duplicate_result_identity", "one record per Challenge")
    return records


def import_runner_records(path, *, attempt_id, case_kind, evidence, note):
    """A pilot entry counted from a runner `records.jsonl`. Reads the file
    only: no worker, network or credential is touched."""
    outcomes = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                status = json.loads(line).get("status")
                outcomes[status] = outcomes.get(status, 0) + 1
    pilot = {
        "attempt_id": attempt_id,
        "case_kind": case_kind,
        "outcomes": outcomes,
        "evidence": evidence,
        "note": note,
    }
    _pilots([pilot])
    return pilot


def summary(document):
    """The comparable facts of one record, derived, never declared."""
    counts = {}
    for pilot in document["pilots"]:
        for outcome, count in pilot["outcomes"].items():
            counts[outcome] = counts.get(outcome, 0) + count
    by_attribution = {"none": 0, "reference": 0, "infrastructure": 0}
    for outcome, count in counts.items():
        by_attribution[OUTCOMES[outcome]] += count
    known = [c for c in document["costs"] if c["basis"] in ("measured", "estimated")]
    unknown = [c["item"] for c in document["costs"] if c["basis"] == "unknown"]
    return {
        "challenge_id": document["challenge_id"],
        "reference_execution": document["maturity"]["reference_execution"],
        "baseline": document["maturity"]["baseline"],
        "cases_ok": by_attribution["none"],
        "reference_failures": by_attribution["reference"],
        "infrastructure_failures": by_attribution["infrastructure"],
        "cost_items_known": len(known),
        "cost_items_unknown": unknown,
        "limits_declared": len(document["limits"]),
        "limits_awaiting_approval": sum(
            1 for limit in document["limits"] if limit["approved"] is None
        ),
        "reviews": {a: document["reviews"][a]["state"] for a in REVIEW_AXES},
        "recommendation": document["recommendation"]["decision"],
    }


def table(records):
    """A readable Markdown readiness table over validated records."""
    lines = [
        (
            "| Challenge | Reference execution | Baseline | Cases OK"
            " | Reference / infra failures | Unknown cost items"
            " | Limits awaiting approval / declared | Reviews approved"
            " | Recommendation |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for document, _ in records:
        s = summary(document)
        approved = sum(1 for state in s["reviews"].values() if state == "APPROVED")
        lines.append(
            f"| {s['challenge_id']} | {s['reference_execution']} | {s['baseline']}"
            f" | {s['cases_ok']} | {s['reference_failures']} / {s['infrastructure_failures']}"
            f" | {', '.join(s['cost_items_unknown']) or 'none'}"
            f" | {s['limits_awaiting_approval']} / {s['limits_declared']}"
            f" | {approved} of {len(REVIEW_AXES)}"
            f" | {s['recommendation']} |"
        )
    return "\n".join(lines)
