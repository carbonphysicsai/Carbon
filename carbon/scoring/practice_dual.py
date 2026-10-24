"""Practice feedback from a Challenge's registered dual measurement (C13).

The graded score of every Challenge is 0.5*A + 0.5*D behind its gates. Practice
feedback used to show accuracy-style error only, steering an agent away from
what it is graded on. This module runs the same dual producer
(`<challenge>_dual_pack.measure`) on the Challenge's PUBLIC development bank and
returns one feedback document: gates first, then A, D and the total in (0, 1]
with 1 best. It reads no sealed or hidden material (the bank is the exposed
development bank the public pack already serves) and builds no ScoreInput, so
the total is feedback on public cases, never the exam grade, and compares only
within one Challenge version (AGENTS 7.6).

``predict`` takes the bank's input rows (dicts keyed by the Challenge's
interface names) and returns one flat output row per input, exactly the rows
the receiver feeds the same ``measure`` for a retained model. It is called three
times (graded run plus the two fresh repeats the paired-repeat gate compares).
"""

from __future__ import annotations

import math

from carbon.challenge_kit import physical_pack
from carbon.scoring import physical_dual_pack as physical

SCHEMA = "carbon.practice.dual-feedback.v1"
SCOPE = "PUBLIC_PRACTICE_FEEDBACK"
VALUE_WEIGHT = 0.5
#: The repeat gate compares a graded run with two fresh repeats; practice has one run.
REPEAT_GATE = "paired_repeat"
NOT_TESTED = "NOT_TESTED_ON_PRACTICE"


class PracticeDualRefused(ValueError):
    """A typed refusal; the code names the check, never hidden content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _unavailable(adapter, reason):
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "available": False,
        "reason": reason,
    }


def unavailable(adapter, reason):
    """The explicit "unavailable" document (never a silent omission)."""
    return _unavailable(adapter, reason)


def _rows(adapter):
    bank = physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)
    public = physical_pack.public_roles(adapter.CHALLENGE, adapter.VERSION)
    names = physical.input_names(adapter)
    return bank, public, names, physical.bank_rows(bank, names)


def feedback(adapter, predict):
    """The practice dual document for one model (``predict``), or an explicit
    "unavailable" document with a typed reason. Never raises for a candidate's
    outputs: a refusal inside the measurement becomes ``available`` False."""
    try:
        bank, public, names, rows = _rows(adapter)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        return _unavailable(adapter, f"practice_bank_unavailable:{type(exc).__name__}")
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": SCOPE,
    }
    inputs = [row["inputs"] for row in rows]
    try:
        graded, first, second = (list(map(list, predict(inputs))) for _ in range(3))
    except Exception:
        return _unavailable(adapter, "practice_predict_failed")
    try:
        measured = adapter.measure(
            bank_rows=rows,
            outputs=graded,
            repeats=[first, second],
            definition=definition,
            limits=_json(public["important_limit_definition"]),
            objective=_json(public["design_objective"]),
            train_raw=public["train"],
            names=names,
        )
    except adapter.Refused as exc:
        return _unavailable(adapter, f"practice_{exc.code}")
    # Practice queries the model once, so the paired-repeat gate has nothing to
    # compare: it is shown as not tested (never PASS) and does not count toward
    # eligibility (Validator, C13 receipt). The exam tests it on two fresh runs.
    gates = {
        name: (NOT_TESTED if name == REPEAT_GATE else bool(ok))
        for name, ok in measured["gates"].items()
    }
    eligible = all(ok for name, ok in gates.items() if name != REPEAT_GATE)
    a, d = measured.get("A"), measured.get("D")
    legs = (a, d)
    scored = eligible and all(
        type(v) in (int, float) and math.isfinite(v) for v in legs
    )
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "available": True,
        # How many public cases practice queries the model on (the full public
        # development bank, run on the miner's own machine).
        "n_cases": len(rows),
        # Gates first. A gate failure is "not eligible", never a number.
        "gates": gates,
        "eligible": eligible,
        "total": ((1 - VALUE_WEIGHT) * a + VALUE_WEIGHT * d if scored else None),
        "accuracy": a if scored else None,
        "design_value": d if scored else None,
        "decision_outcome": measured.get("decision_outcome"),
        "note": (
            "Computed on the public development bank; compares only within this "
            "Challenge version; not the exam grade."
        ),
    }


def _json(raw):
    import json

    return json.loads(raw)


def motor_predict(model):
    """``predict`` for a rebuilt Motor model (``model.predict(inputs)`` returning
    a dict with the 60-angle ``torque_nm`` curve), as the receiver's flat rows."""

    def predict(inputs):
        return [[float(v) for v in model.predict(row)["torque_nm"]] for row in inputs]

    return predict


def cooling_predict(model):
    """``predict`` for a rebuilt Cooling model (``model.predict(inputs)`` returning
    ``peak_c``, ``profile_c`` and ``pressure_drop_pa``), as the receiver's flat
    rows: peak, the profile, then the pressure drop."""

    def predict(inputs):
        rows = []
        for row in inputs:
            out = model.predict(row)
            rows.append(
                [
                    float(out["peak_c"]),
                    *[float(v) for v in out["profile_c"]],
                    float(out["pressure_drop_pa"]),
                ]
            )
        return rows

    return predict


def query_inputs(adapter, like):
    """The public development bank's inputs as one numeric array in the
    interface's input order, cast to ``like``'s dtype: the rows a practice must
    query the model on for the dual measurement to be computable."""
    import numpy as np

    _bank, _public, names, rows = _rows(adapter)
    return np.asarray(
        [[float(row["inputs"][name]) for name in names] for row in rows],
        dtype=like.dtype,
    )


def bank_cases(adapter):
    """The public development bank as ``[(case_id, cohort, inputs)]`` in the bank's
    order, ``inputs`` a dict keyed by the interface's input names: the cases a
    practice must query the model on for the dual measurement."""
    _bank, _public, _names, rows = _rows(adapter)
    return [(row["case_id"], row["cohort"], dict(row["inputs"])) for row in rows]


def from_rows(adapter, rows):
    """The dual block for ``rows``: the model's flat outputs on exactly the
    bank's inputs (`query_inputs`), in the bank's order. The model is queried
    once, so the paired repeat is the same rows."""
    values = [[float(v) for v in row] for row in rows]

    def predict(cases):
        if len(cases) != len(values):
            raise ValueError("practice rows differ from the bank")
        return values

    return feedback(adapter, predict)


def versioned(module, version):
    """The dual adapter for exactly ``version`` of ``module``'s Challenge, or
    None when that version has no registered measurement."""
    return physical.versioned(module, version)


SCHEMA_V2 = "carbon.practice.dual-feedback.v2"
BANK_LABEL = "practice (public bank)"


def unavailable_v2(kind, version, reason):
    return {
        "schema": SCHEMA_V2,
        "scope": SCOPE,
        "bank": BANK_LABEL,
        "challenge": {"kind": kind, "version": version},
        "available": False,
        "reason": reason,
    }


def query_inputs_v2(kind, version, like=None):
    """The practice grid query: the public cells with the public-seeded probes
    interleaved, as one numeric array in the interface's input order (cast to
    ``like``'s dtype when given). A practice must query the model on exactly
    these rows for the v2 dual measurement to be computable."""
    import numpy as np

    from carbon.scoring import practice_grid

    bank = practice_grid.practice_bank(kind, version)
    inputs = np.asarray(bank["inputs"])
    return inputs if like is None else inputs.astype(like.dtype)


def from_rows_v2(kind, version, rows):
    """The v2 dual block for ``rows``: the model flat outputs on exactly
    `query_inputs_v2`, in its order. The model is queried once, so the paired
    repeat is the same rows."""
    values = [[float(v) for v in row] for row in rows]

    def predict(cases):
        if len(cases) != len(values):
            raise ValueError("practice rows differ from the practice grid query")
        return values

    return feedback_v2(kind, version, predict)


def _minimums_block(adapter, version, values, pack_kwargs):
    """The version's registered leg minimums beside the practice leg values. They come
    ONLY from the registered score pack (``adapter.applied_pack``, the constant the
    published exam block reads): no default is ever supplied. A leg whose minimum is not
    registered is absent; with none registered the status is NOT_YET_SET. A leg is met
    when its value reaches the minimum (equality passes); an unscored value (a gate
    failed) is neither met nor unmet. This is practice only: it never names an official
    status and the document stays a public-bank practice."""
    try:
        pack_legs = adapter.applied_pack(**pack_kwargs)["legs"]
    except (KeyError, TypeError, ValueError):
        pack_legs = {}
    legs = {}
    for leg in ("A", "D"):
        minimum = (pack_legs.get(leg) or {}).get("minimum")
        if type(minimum) not in (int, float) or not math.isfinite(minimum):
            continue
        value = values.get(leg)
        legs[leg] = {
            "minimum": minimum,
            "value": value,
            "met": None if value is None else value >= minimum,
        }
    return {
        "source": "published_exam",
        "version": version,
        "status": "SET" if legs else "NOT_YET_SET",
        "legs": legs,
    }


def feedback_v2(kind, version, predict):
    """The practice dual document on the v2 legs: the exam own sealed grader
    (D = min(V, C) with V three decision measures, A its four legs, the law
    gate) run on the FULL exposed public bank as a grid with public-seeded
    probes. Aggregate leg values and the names of failed gates only; labelled
    "practice (public bank)", never comparable with a sealed grade."""
    from carbon.scoring import practice_grid

    try:
        adapter = practice_grid.adapter(kind, version)
        if adapter is None:
            return unavailable_v2(kind, version, "practice_version_not_registered")
        bank = practice_grid.practice_bank(kind, version)
        public = physical_pack.public_roles(adapter.CHALLENGE, version)
        names = practice_grid.input_names(kind, version)
        rows = physical.bank_rows(bank, names)
    except (KeyError, ValueError, FileNotFoundError, OSError) as exc:
        return unavailable_v2(
            kind, version, f"practice_bank_unavailable:{type(exc).__name__}"
        )
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"kind": kind, "version": version},
        "scope": SCOPE,
    }
    inputs = [row["inputs"] for row in rows]
    try:
        graded, first, second = (list(map(list, predict(inputs))) for _ in range(3))
    except Exception:
        return unavailable_v2(kind, version, "practice_predict_failed")
    try:
        measured = adapter.measure(
            bank_rows=rows,
            outputs=graded,
            repeats=[first, second],
            definition=definition,
            limits=_json(public["important_limit_definition"]),
            objective=_json(public["design_objective"]),
            train_raw=public["train"],
            names=names,
        )
    except ValueError as exc:
        code = getattr(exc, "code", type(exc).__name__)
        return unavailable_v2(kind, version, f"practice_{code}")
    gates = {
        name: (NOT_TESTED if name == REPEAT_GATE else bool(ok))
        for name, ok in measured["gates"].items()
    }
    eligible = all(ok for name, ok in gates.items() if name != REPEAT_GATE)
    a, d = measured.get("A"), measured.get("D")
    scored = eligible and all(
        type(v) in (int, float) and math.isfinite(v) for v in (a, d)
    )
    fidelity = measured.get("design_fidelity") or {}
    value = fidelity.get("value") or {}
    physics = measured.get("physics_half") or {}

    def number(x):
        return x if type(x) in (int, float) and math.isfinite(x) else None

    minimums = _minimums_block(
        adapter,
        version,
        {"A": a if scored else None, "D": d if scored else None},
        {
            "bank_rows": rows,
            "definition": definition,
            "limits": _json(public["important_limit_definition"]),
            "objective": _json(public["design_objective"]),
            "train_raw": public["train"],
            "names": names,
        },
    )
    below = [leg for leg, row in minimums["legs"].items() if row["met"] is False]
    return {
        "schema": SCHEMA_V2,
        "scope": SCOPE,
        "bank": BANK_LABEL,
        "challenge": {"kind": kind, "version": version},
        "available": True,
        "n_cases": len(rows),
        # Practice status: the gates first (a gate failure outranks a minimum), then the
        # version's registered leg minimums (OWNER-PRACTICE-SHOWS-MINIMUMS-01).
        "status": (
            "PRACTICE_GATE_FAILED"
            if not eligible
            else "PRACTICE_BELOW_MINIMUM" if below else "PRACTICE_SCORED"
        ),
        "failed_legs": below if eligible else [],
        "minimums": minimums,
        "gates": gates,
        "gates_failed_laws": list(physics.get("gate_failed_laws", [])),
        "eligible": eligible,
        "total": ((1 - VALUE_WEIGHT) * a + VALUE_WEIGHT * d if scored else None),
        "accuracy": a if scored else None,
        "design_value": d if scored else None,
        # The legs, aggregate values only.
        "accuracy_legs": {
            k: number(v) for k, v in (measured.get("A_legs") or {}).items()
        },
        "design_parts": {
            "V_pair": number(value.get("V_pair")),
            "V_feas": number(value.get("V_feas")),
            "V_var": number(value.get("V_var")),
            "C": number(fidelity.get("C")),
        },
        "decision_outcome": measured.get("decision_outcome"),
        "note": (
            "Computed on the full public bank with public probes, by the exam own "
            "v2 grader; compares only within this Challenge version; not the exam "
            "grade and not comparable with a sealed grade."
        ),
    }


def attach(outcome, adapter, predict):
    """``outcome`` plus the shared ``practice_dual`` block: the one call every
    practice evaluator makes (its outcome schema is bumped and its disclosure
    allow-list gains ``practice_dual``)."""
    return {**outcome, "practice_dual": feedback(adapter, predict)}
