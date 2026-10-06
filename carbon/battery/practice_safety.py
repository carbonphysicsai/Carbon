"""Battery decision-value safety feedback on public PRACTICE (PRACTICE-SAFETY-01).

Computed on the trusted host from the 200 public PRACTICE references
(`practice.PracticeSet`, pinned by `PRACTICE_SOURCE_SHA256`) and the worker's
predictions for them. Feedback only: see `carbon.practice_safety_feedback`.

- **B1. Near-limit false acceptance per constraint.** On the published
  important region (`domain.is_important`), the cases the reference resolves
  as FAIL with EV4's bands (`decision.check`), and how many the model calls
  PASS without bands. The worst constraint is named. The same counts as
  `value.false_acceptance.component`.
- **B2. Near-limit optimism.** The mean over the important cases and both
  constraints of how far the model's margin exceeds the reference's, in EV4
  band units: `value.admissibility.near_optimism`, the EV5 gate's measure. The
  value only; the gate's verdict and cutoff are not shown.
- **B3. Signed near-limit margin error.** Per constraint, the mean of
  predicted minus reference margin in band units over the important cases
  (`value.margins._margins`). Positive is optimistic.
- **B4. Feasible-choice rate on the practice decision set.** The committed
  public set (`DECISION_SET_PATH`: 6 conditions x EV4's 35-candidate grid,
  pinned through its `SHA256SUMS`, which is itself pinned). At each
  condition the model's predictions choose a protocol with EV4's rules and
  tie rule (`decision.assess_predicted` / `decision.select`), and the
  reference verifies the choice with EV4's bands
  (`decision.assess_reference`). The rate is reference-FEASIBLE choices over
  choices the reference resolves; abstentions and choices the reference
  leaves UNRESOLVED are counted beside it, never in it. A set that does not
  match its pins is refused with a typed reason and nothing is computed.
  (In practice-feedback v2, before the set was committed, B4 was the
  literal `ps.B4_BLOCKED`; v3 never emits it.)

The value modules named above import the scoring-set module, so this module
reimplements their few lines over `value.decision` alone; a test proves the
results identical on the practice references.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from carbon import practice_safety_feedback as ps

from .challenge import CHALLENGE
from .domain import GRID_POINTS, INPUTS, is_important
from .practice import PRACTICE_SOURCE_PATH, PRACTICE_SOURCE_SHA256
from .value import decision as d

#: Where EV4's decision rules below are copied from. The metric never opens
#: it: the contract also holds EV4's conditions. A test binds the copy.
CONTRACT_SOURCE = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
#: EV4's objective, constraints and reference bands, as `decision.measure`
#: and `decision.check` read them, and nothing else of the contract.
DECISION_RULES = {
    "objective": {"threshold_v": 4.19, "charge_start_s": 120.0, "window_s": 3600.0},
    "constraints": [
        {"id": "reach_cv_in_window"},
        {"id": "no_plating_onset", "threshold": 0.0},
        {"id": "peak_temperature", "threshold": 45.0},
    ],
    "reference": {
        "uncertainty": {
            "bands": {
                "time_to_cv_onset_s": 3.15,
                "plating_margin_v": 0.00197,
                "peak_temperature_c": 0.157,
            }
        }
    },
}
CONSTRAINTS = ("no_plating_onset", "peak_temperature")
#: The committed public practice decision set for B4 (Data Collection, #669).
#: Every condition in it is permanently practice-only.
DECISION_SET_PATH = "docs/development/evidence/practice-decision-set-v1"
#: The sha256 of the set's `SHA256SUMS`, which names the digest of each of
#: `DECISION_SET_FILES`; each file is checked against it before it is read.
DECISION_SET_SUMS_SHA256 = (
    "0e135fddbf8662e26b946bcc3ca6c38edc2a5a7476028a9676645884227bef0f"
)
DECISION_SET_FILES = ("conditions.json", "records.jsonl.gz")
DECISION_SET_SCHEMA = "carbon.battery.practice-decision-set.v1"
DECISION_SET_CONDITIONS = 6
#: EV4's frozen candidate grid (`design_variables`, in `value.contract.
#: candidates` order and ids), copied like `DECISION_RULES`; a test binds it.
CANDIDATE_C1 = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
CANDIDATE_C2 = (0.2, 0.4, 0.6, 0.8, 1.0)
CANDIDATES = tuple(
    {"id": f"c1={c1:g},c2={c2:g}", "c1": c1, "c2": c2}
    for c1 in CANDIDATE_C1
    for c2 in CANDIDATE_C2
)
#: B4's typed refusals: the set does not match its pins or its shape.
B4_REFUSED_MISSING = "REFUSED: practice decision set file missing"
B4_REFUSED_SUMS = "REFUSED: practice decision set SHA256SUMS does not match its pin"
B4_REFUSED_DIGEST = "REFUSED: practice decision set file does not match SHA256SUMS"
B4_REFUSED_SHAPE = (
    "REFUSED: practice decision set is not 6 conditions at EV4's 35-candidate grid"
)
B4_REFUSALS = (
    B4_REFUSED_MISSING,
    B4_REFUSED_SUMS,
    B4_REFUSED_DIGEST,
    B4_REFUSED_SHAPE,
)
#: The ruled exclusion box around every EV1/EV2/EV4/EV5 condition and
#: protected grid point (Test Lead ruling, 2026-10-05): a practice decision
#: condition inside both bounds of one is too close (`_clear`).
DECISION_SET_MIN_T_AMB_C = 2.0
DECISION_SET_MIN_SOC0 = 0.03
POSITIVE_IS_OPTIMISTIC = "predicted minus reference; positive is optimistic"

_RATE_ROW = {
    "false_acceptance": ps.COUNT,
    "reference_fail": ps.COUNT,
    "rate": ps.NUMBER,
}
_SIGNED_ROW = {"signed_mean_bands": ps.NUMBER, "cases": ps.COUNT}
ALLOWED = {
    "B1": {
        **{c: _RATE_ROW for c in CONSTRAINTS},
        "worst": ps.literal(None, *CONSTRAINTS),
        "feedback_only": ps.TRUE,
    },
    "B2": {"near_optimism_bands": ps.NUMBER, "feedback_only": ps.TRUE},
    "B3": {
        **{c: _SIGNED_ROW for c in CONSTRAINTS},
        "sign": ps.literal(POSITIVE_IS_OPTIMISTIC),
        "feedback_only": ps.TRUE,
    },
    "B4": (
        {
            "feasible_choice": ps.COUNT,
            "chosen": ps.COUNT,
            "rate": ps.NUMBER,
            "abstained": ps.COUNT,
            "unresolved": ps.COUNT,
            "feedback_only": ps.TRUE,
        },
        ps.literal(*B4_REFUSALS),
    ),
}


class DecisionSetRefused(ValueError):
    """The practice decision set does not match its pins or its shape."""

    def __init__(self, reason):
        if reason not in B4_REFUSALS:
            raise TypeError("untyped decision set refusal")
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DecisionSet:
    """The verified practice decision set, or (`refused` set) none at all.

    `grid[i]` maps each candidate id to its case id at `conditions[i]`;
    `references` maps each case id to its committed reference record.
    """

    conditions: tuple = ()
    grid: tuple = ()
    references: dict = field(default_factory=dict)
    refused: str | None = None

    @property
    def case_ids(self):
        return [case for cases in self.grid for case in cases.values()]

    def cases(self):
        """What the worker is asked to predict: case ids and inputs only."""
        return [
            {
                "case_id": case,
                "inputs": {k: self.references[case]["inputs"][k] for k in INPUTS},
            }
            for case in self.case_ids
        ]

    @staticmethod
    def from_records(conditions, records):
        """The set over `conditions` [(t_amb_c, soc0)], each at every
        candidate exactly once, every reference an OK unrefined record."""
        conditions = tuple((float(t), float(s)) for t, s in conditions)
        by_input = {}
        for record in records:
            if record.get("status") != "OK" or record.get("refined") is not False:
                raise DecisionSetRefused(B4_REFUSED_SHAPE)
            x = record["inputs"]
            key = (x["t_amb_c"], x["soc0"], x["c1"], x["c2"])
            if key in by_input:
                raise DecisionSetRefused(B4_REFUSED_SHAPE)
            by_input[key] = record
        grid = tuple(
            {
                c["id"]: by_input.get((t, s, c["c1"], c["c2"]), {}).get("case_id")
                for c in CANDIDATES
            }
            for t, s in conditions
        )
        cases = [case for cases in grid for case in cases.values()]
        if (
            len(set(conditions)) != len(conditions)
            or None in cases
            or len(set(cases)) != len(cases)
            or len(cases) != len(records)
        ):
            raise DecisionSetRefused(B4_REFUSED_SHAPE)
        return DecisionSet(conditions, grid, {r["case_id"]: r for r in records})


def _pinned_set_file(root, name, sums):
    """The bytes of one set file, read once and checked against `sums`."""
    try:
        body = (Path(root) / DECISION_SET_PATH / name).read_bytes()
    except OSError:
        raise DecisionSetRefused(B4_REFUSED_MISSING) from None
    if hashlib.sha256(body).hexdigest() != sums.get(name):
        raise DecisionSetRefused(B4_REFUSED_DIGEST)
    return body


def load_decision_set(root="."):
    """The committed practice decision set, verified, or DecisionSetRefused."""
    try:
        body = (Path(root) / DECISION_SET_PATH / "SHA256SUMS").read_bytes()
    except OSError:
        raise DecisionSetRefused(B4_REFUSED_MISSING) from None
    if hashlib.sha256(body).hexdigest() != DECISION_SET_SUMS_SHA256:
        raise DecisionSetRefused(B4_REFUSED_SUMS)
    sums = {}
    for line in body.decode().splitlines():
        digest, name = line.split()
        sums[name] = digest
    if sorted(sums) != sorted(DECISION_SET_FILES):
        raise DecisionSetRefused(B4_REFUSED_SUMS)
    document = json.loads(_pinned_set_file(root, "conditions.json", sums))
    lines = gzip.decompress(_pinned_set_file(root, "records.jsonl.gz", sums))
    records = [json.loads(line) for line in lines.splitlines() if line.strip()]
    conditions = document.get("conditions") or []
    if (
        document.get("schema") != DECISION_SET_SCHEMA
        or len(conditions) != DECISION_SET_CONDITIONS
    ):
        raise DecisionSetRefused(B4_REFUSED_SHAPE)
    return DecisionSet.from_records(
        [(c["t_amb_c"], c["soc0"]) for c in conditions], records
    )


def decision_set(root="."):
    """The verified set, or a set carrying only its typed refusal."""
    try:
        return load_decision_set(root)
    except DecisionSetRefused as refusal:
        return DecisionSet(refused=refusal.reason)


def feasible_choice(predictions, decision):
    """B4 and the number of decision-set cases it could not measure.

    A refused set gives its refusal and computes nothing. Any unmeasurable
    prediction makes B4 None (UNMEASURED).
    """
    if decision.refused is not None:
        return decision.refused, 0
    unmeasured = sum(not measurable(predictions.get(c)) for c in decision.case_ids)
    if unmeasured:
        return None, unmeasured
    counts = {"feasible_choice": 0, "chosen": 0, "abstained": 0, "unresolved": 0}
    for condition, cases in zip(decision.conditions, decision.grid):
        scenario = {"conditions": [condition]}
        quantities = {
            (cid, 0): d.measure(DECISION_RULES, predictions[case])
            for cid, case in cases.items()
        }
        predicted = d.assess_predicted(DECISION_RULES, scenario, CANDIDATES, quantities)
        choice = d.select(CANDIDATES, predicted)
        if choice is None:
            counts["abstained"] += 1
            continue
        references = {
            (cid, 0): decision.references[case] for cid, case in cases.items()
        }
        verified = d.assess_reference(DECISION_RULES, scenario, CANDIDATES, references)
        status = verified[choice]["status"]
        if status in (d.FEASIBLE, d.INFEASIBLE):
            counts["chosen"] += 1
            counts["feasible_choice"] += status == d.FEASIBLE
        else:
            counts["unresolved"] += 1
    return {
        **counts,
        "rate": ps.rate(counts["feasible_choice"], counts["chosen"]),
        "feedback_only": True,
    }, 0


def _finite_series(value):
    return (
        type(value) in (list, tuple)
        and len(value) == GRID_POINTS
        and all(_finite(v) for v in value)
    )


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measurable(outputs):
    """Whether a prediction carries every output the metrics read, finite and
    of its declared shape. Anything else is UNMEASURED, never clean."""
    return (
        type(outputs) is dict
        and _finite_series(outputs.get("voltage_v"))
        and _finite_series(outputs.get("temperature_c"))
        and _finite(outputs.get("plating_margin_v"))
    )


def margins(outputs):
    """Signed margins (positive is safe) in EV4 band units
    (`value.margins._margins` over `DECISION_RULES`)."""
    rules = {c["id"]: c for c in DECISION_RULES["constraints"]}
    bands = DECISION_RULES["reference"]["uncertainty"]["bands"]
    q = d.measure(DECISION_RULES, outputs)
    return {
        "no_plating_onset": (
            q["plating_margin_v"] - rules["no_plating_onset"]["threshold"]
        )
        / bands["plating_margin_v"],
        "peak_temperature": (
            rules["peak_temperature"]["threshold"] - q["peak_temperature_c"]
        )
        / bands["peak_temperature_c"],
    }


def near_case_ids(practice):
    """The practice cases in the published important region."""
    return [r["case_id"] for r in practice.records if is_important(r)]


def safety(predictions, practice, decision):
    """The allow-listed safety document for one practice result.

    `predictions` holds the practice cases' and the decision set's (`decision`,
    from `decision_set`). `unmeasured` counts the cases of both that carry no
    measurable prediction; B1-B3 are None when a practice case does, and B4
    when a decision-set case does.
    """
    refs = {r["case_id"]: r for r in practice.records}
    unmeasured = sum(not measurable(predictions.get(c)) for c in refs)
    b4, decision_unmeasured = feasible_choice(predictions, decision)
    near = near_case_ids(practice)
    counts = {c: {"false_acceptance": 0, "reference_fail": 0} for c in CONSTRAINTS}
    unresolved = 0
    optimism, signed = [], {c: [] for c in CONSTRAINTS}
    bands = DECISION_RULES["reference"]["uncertainty"]["bands"]
    for case_id in near:
        reference = refs[case_id]["outputs"]
        truth = d.check(DECISION_RULES, d.measure(DECISION_RULES, reference), bands)
        for constraint in CONSTRAINTS:
            unresolved += truth[constraint] == d.UNRESOLVED
        if unmeasured:
            continue
        outputs = predictions[case_id]
        said = d.check(DECISION_RULES, d.measure(DECISION_RULES, outputs))
        said_m, truth_m = margins(outputs), margins(reference)
        for constraint in CONSTRAINTS:
            if truth[constraint] == d.FAIL:
                counts[constraint]["reference_fail"] += 1
                counts[constraint]["false_acceptance"] += said[constraint] == d.PASS
            delta = said_m[constraint] - truth_m[constraint]
            optimism.append(max(0.0, delta))
            signed[constraint].append(delta)
    if unmeasured:
        b1 = b2 = b3 = None
    else:
        rows = {
            c: {
                **counts[c],
                "rate": ps.rate(
                    counts[c]["false_acceptance"], counts[c]["reference_fail"]
                ),
            }
            for c in CONSTRAINTS
        }
        rated = {c: rows[c]["rate"] for c in CONSTRAINTS if rows[c]["rate"] is not None}
        b1 = {
            **rows,
            "worst": max(rated, key=lambda c: (rated[c], c)) if rated else None,
            "feedback_only": True,
        }
        b2 = {"near_optimism_bands": ps.signed_mean(optimism), "feedback_only": True}
        b3 = {
            **{
                c: {
                    "signed_mean_bands": ps.signed_mean(signed[c]),
                    "cases": len(signed[c]),
                }
                for c in CONSTRAINTS
            },
            "sign": POSITIVE_IS_OPTIMISTIC,
            "feedback_only": True,
        }
    return ps.document(
        CHALLENGE.challenge_id,
        {"B1": b1, "B2": b2, "B3": b3, "B4": b4},
        unmeasured=unmeasured + decision_unmeasured,
        unresolved=unresolved,
        material={"path": PRACTICE_SOURCE_PATH, "sha256": PRACTICE_SOURCE_SHA256},
        allowed=ALLOWED,
    )


def decision_set_clear(conditions, protected):
    """Whether every practice decision condition `(t_amb_c, soc0)` lies at
    least the ruled distance from every protected condition (`_clear`)."""
    return all(_clear(c, p) for c in conditions for p in protected)


def _clear(condition, protected):
    """The ruled separation (Test Lead ruling, 2026-10-05, correcting the
    ticket's wording): a condition is TOO CLOSE, and refused, when it is
    within BOTH bounds of a protected condition, |dt_amb| < 2 degC AND
    |dsoc0| < 0.03. It is clear when it is at least that far away in at
    least one dimension."""
    too_close = (
        abs(condition[0] - protected[0]) < DECISION_SET_MIN_T_AMB_C
        and abs(condition[1] - protected[1]) < DECISION_SET_MIN_SOC0
    )
    return not too_close
