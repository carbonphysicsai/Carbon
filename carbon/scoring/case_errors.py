"""LL2: the per-case error file every pool grade with an accuracy record writes beside it (owner LL-A, 23 Nov 2026).

Owner line LL-A (row 4905, filed G-LEAD-57): "every exam grade writes a per-case error file beside its accuracy record,
kept with the grade and copied into custody2." The accuracy record (`pool_physics_score.accuracy_record`) keeps only
class x output aggregates (median / p90 / max); this file keeps the per-case values those aggregates were reduced from,
so the bank's one reviewed runner (owner LL-B) can study them on custody2 without re-deriving the grader.

What it is and is not:
- Hidden-derived CUSTODY evidence, retained with the grade; never served, never a miner or public surface, never a score
  input, never on the crown's path. Writing it cannot change or refuse a grade: `Sink` only appends, `assemble` runs
  after the record is measured and the grader catches its failure (`pool_exam.measure_pool`).
- One entry per ANSWERED case in the order the grader asked them (one served row each): the target cases of
  `pool_physics_score._ratios` (source 0), then the registered in-range case set (source 1).
- ``row_index`` joins a case to the grade's retained positional predictions: the index in the exam's ``bank_rows`` of
  the row the model's table answered it from (the same quantised exact-input key the table looks up; door-code 5141).
  A key that two bank rows share maps to its FIRST row, as the table's dict does; ``n_duplicate_keys`` counts them.
- No case id, draw id or seed is written: ordinals, class labels, output names and errors only. No truth is written as
  such, but ``abs_error`` with ``pct`` gives |truth|: the file is as private as the hidden pack it was graded on.

Arrays (``.npz``, no pickles; every float is float64, NaN where a value is absent):
``row_index``, ``source``, ``spec_index`` (-1 for an in-range set case), ``case_index``, ``class_index`` (into
``class_names``), ``invalid`` (the candidate's invalid answer: no error is measured), ``output_names``, ``abs_error``,
``u``, ``ratio`` (|err| / U, NaN where U is 0), ``pct`` (100 |err| / |truth| for a finite non-zero scalar truth),
``typed_names``, ``typed_ratio`` (S7 |err| / value_u where truth and answer both carry a value), ``n_duplicate_keys``,
``schema``, ``exam_key``.
"""

from __future__ import annotations

import io
import math

SIDECAR = "case-errors.npz"
SCHEMA = "carbon.exam.case-errors.v1"
SOURCE_TARGET, SOURCE_IN_RANGE = 0, 1


class CaseErrorsRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise CaseErrorsRefused(code)


def _number(value):
    """A float, or NaN for anything that is not one finite real number (a waveform's error is already a scalar)."""
    if type(value) is bool:
        return math.nan
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


class _Case:
    __slots__ = (
        "bad",
        "case_index",
        "name",
        "outputs",
        "source",
        "spec_index",
        "typed_values",
    )

    def __init__(self, source, spec_index, case_index, name):
        self.source = source
        self.spec_index = spec_index
        self.case_index = case_index
        self.name = name
        self.bad = False
        self.outputs = {}
        self.typed_values = {}

    def invalid(self):
        self.bad = True

    def output(self, output, error, u, truth):
        self.outputs[output] = (error, u, truth)

    def typed(self, output, ratio):
        self.typed_values[output] = ratio


class Sink:
    """The per-case collector `pool_physics_score.accuracy_record` fills (``case_sink``); append-only, never raises."""

    def __init__(self):
        self.cases = []

    def case(self, source, spec_index, case_index, name):
        case = _Case(source, spec_index, case_index, name)
        self.cases.append(case)
        return case


class ServedKeys:
    """Wraps a table ``serve(rows)``: records each served row's table key, in order, then serves it unchanged."""

    def __init__(self, serve, key_of):
        self._serve, self._key_of = serve, key_of
        self.keys = []

    def __call__(self, rows):
        self.keys.extend(self._key_of(row) for row in rows)
        return self._serve(rows)


def assemble(sink, served_keys, bank_keys):
    """The file's arrays from one grade's `Sink`, the keys served while it was filled, and every bank row's key."""
    import numpy as np

    cases = sink.cases
    _require(len(served_keys) == len(cases), "case_errors_served_rows_misaligned")
    first = {}
    for index, key in enumerate(bank_keys):
        first.setdefault(key, index)
    rows = []
    for key in served_keys:
        _require(key in first, "case_errors_served_row_not_in_the_bank")
        rows.append(first[key])
    class_names = sorted({case.name for case in cases})
    output_names = sorted({o for case in cases for o in case.outputs})
    typed_names = sorted({o for case in cases for o in case.typed_values})
    classes = {name: i for i, name in enumerate(class_names)}
    shape = (len(cases), len(output_names))
    abs_error, u_values, ratio, pct = (np.full(shape, np.nan) for _ in range(4))
    typed_ratio = np.full((len(cases), len(typed_names)), np.nan)
    for i, case in enumerate(cases):
        for j, name in enumerate(output_names):
            if name not in case.outputs:
                continue
            error, u, truth = case.outputs[name]
            error, u, truth = _number(error), _number(u), _number(truth)
            abs_error[i, j], u_values[i, j] = abs(error), u
            if u > 0:
                ratio[i, j] = abs(error) / u
            if truth != 0 and not math.isnan(truth):
                pct[i, j] = 100.0 * abs(error) / abs(truth)
        for j, name in enumerate(typed_names):
            if case.typed_values.get(name) is not None:
                typed_ratio[i, j] = _number(case.typed_values[name])
    return {
        "row_index": np.asarray(rows, dtype=np.int64),
        "source": np.asarray([c.source for c in cases], dtype=np.int8),
        "spec_index": np.asarray([c.spec_index for c in cases], dtype=np.int64),
        "case_index": np.asarray([c.case_index for c in cases], dtype=np.int64),
        "class_index": np.asarray([classes[c.name] for c in cases], dtype=np.int64),
        "class_names": np.asarray(class_names, dtype=np.str_),
        "invalid": np.asarray([c.bad for c in cases], dtype=np.bool_),
        "output_names": np.asarray(output_names, dtype=np.str_),
        "abs_error": abs_error,
        "u": u_values,
        "ratio": ratio,
        "pct": pct,
        "typed_names": np.asarray(typed_names, dtype=np.str_),
        "typed_ratio": typed_ratio,
        "n_duplicate_keys": np.asarray(len(bank_keys) - len(first), dtype=np.int64),
    }


def encode(arrays, exam_key):
    """The sidecar's bytes: ``arrays`` plus ``schema`` and ``exam_key``, an ``.npz`` that `numpy.load` reads with
    ``allow_pickle=False``. Deterministic (members sorted, fixed zip times), so a retried write of the same grade holds
    exactly the bytes already written (`write_once`)."""
    import zipfile

    import numpy as np

    _require(type(exam_key) is str and exam_key, "case_errors_exam_key_missing")
    members = {
        **arrays,
        "schema": np.asarray(SCHEMA, dtype=np.str_),
        "exam_key": np.asarray(exam_key, dtype=np.str_),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            member = io.BytesIO()
            np.lib.format.write_array(
                member, np.asanyarray(members[name]), allow_pickle=False
            )
            info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, member.getvalue())
    return out.getvalue()
