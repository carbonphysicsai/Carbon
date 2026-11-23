"""LL2: the per-case error file every pool grade with an accuracy record writes beside it (owner LL-A, 23 Nov 2026).

Owner line LL-A (row 4905, filed G-LEAD-57): "every exam grade writes a per-case error file beside its accuracy record,
kept with the grade and copied into custody2." The accuracy record (`pool_physics_score.accuracy_record`) keeps only
class x output aggregates (median / p90 / max); this file keeps the per-case values those aggregates were reduced from,
so the bank's one reviewed runner (owner LL-B) can study them on custody2 without re-deriving the grader.

What it is and is not:
- Hidden-derived CUSTODY evidence, retained with the grade; never served, never a miner or public surface, never a score
  input, never on the crown's path. Writing it cannot change or refuse a grade: `Sink` only appends, `assemble` runs
  after the record is measured and the grader catches its failure (`pool_exam.measure_pool`). The capture holds plain
  lists (`assemble`); `encode` makes the arrays.
- Written from the receiver's staged capture (every live pool grade). The re-measured SE path of a SUBSET-REPEAT
  version (`subset_repeat_produce.bootstrap_total_se`) does not hand it on: that file is in Motor 1.8's producer
  digest (`motor18_dual_pack._SUBSET_FILES`), so such a grade journals ``grade_case_errors_unavailable`` instead.
- One entry per ANSWERED case in the order the grader asked them (one served row each): the target cases of
  `pool_physics_score._ratios` (source 0), then the registered in-range case set (source 1).
- ``row_index`` joins a case to the grade's retained positional predictions: the index in the exam's ``bank_rows`` of
  the row the model's table answered it from (the same quantised exact-input key the table looks up; door-code 5141).
  A key that two bank rows share maps to its FIRST row, as the table's dict does; ``n_duplicate_keys`` counts them.
- No case id, draw id or seed is written: ordinals, class labels, output names and errors only. No truth is written as
  such, but ``abs_error`` with ``pct`` gives |truth|: the file is as private as the hidden pack it was graded on.

Members (``.npz``, no pickles; every float is float64, NaN where a value is absent; `DTYPES`):
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
    """A float, or None for anything that is not one finite real number (a waveform's error is already a scalar)."""
    if type(value) is bool:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


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


#: The file's members and their dtypes (`to_arrays`); 2-D members are (cases, names).
DTYPES = {
    "row_index": "int64",
    "source": "int8",
    "spec_index": "int64",
    "case_index": "int64",
    "class_index": "int64",
    "class_names": "str",
    "invalid": "bool",
    "output_names": "str",
    "abs_error": "float64",
    "u": "float64",
    "ratio": "float64",
    "pct": "float64",
    "typed_names": "str",
    "typed_ratio": "float64",
    "n_duplicate_keys": "int64",
}
_BY_OUTPUT = ("abs_error", "u", "ratio", "pct")


def assemble(sink, served_keys, bank_keys):
    """The file's content from one grade's `Sink`, the keys served while it was filled, and every bank row's key: plain
    lists and numbers (None where a value is absent), so a capture holding it still compares with ``==``.
    """
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
    columns = {name: [] for name in _BY_OUTPUT}
    typed_ratio = []
    for case in cases:
        line = {name: [None] * len(output_names) for name in _BY_OUTPUT}
        for j, name in enumerate(output_names):
            if name not in case.outputs:
                continue
            error, u, truth = (_number(v) for v in case.outputs[name])
            size = None if error is None else abs(error)
            line["abs_error"][j], line["u"][j] = size, u
            if size is not None and u is not None and u > 0:
                line["ratio"][j] = size / u
            if size is not None and truth:
                line["pct"][j] = 100.0 * size / abs(truth)
        for name in _BY_OUTPUT:
            columns[name].append(line[name])
        typed_ratio.append([_number(case.typed_values.get(n)) for n in typed_names])
    return {
        "row_index": rows,
        "source": [c.source for c in cases],
        "spec_index": [c.spec_index for c in cases],
        "case_index": [c.case_index for c in cases],
        "class_index": [classes[c.name] for c in cases],
        "class_names": class_names,
        "invalid": [c.bad for c in cases],
        "output_names": output_names,
        **columns,
        "typed_names": typed_names,
        "typed_ratio": typed_ratio,
        "n_duplicate_keys": len(bank_keys) - len(first),
    }


def to_arrays(content):
    """`assemble`'s content as the file's numpy arrays (`DTYPES`; None is NaN in a float member)."""
    import numpy as np

    _require(set(content) == set(DTYPES), "case_errors_members_differ")
    out = {}
    for name, dtype in DTYPES.items():
        value = content[name]
        if dtype == "str":
            out[name] = np.asarray(value, dtype=np.str_)
            continue
        array = np.asarray(
            (
                [[math.nan if v is None else v for v in row] for row in value]
                if name in _BY_OUTPUT or name == "typed_ratio"
                else value
            ),
            dtype=dtype,
        )
        if name in _BY_OUTPUT or name == "typed_ratio":
            names = content["typed_names" if name == "typed_ratio" else "output_names"]
            array = array.reshape(len(content["row_index"]), len(names))
        out[name] = array
    return out


def encode(content, exam_key):
    """The sidecar's bytes: `to_arrays` of ``content`` plus ``schema`` and ``exam_key``, an ``.npz`` that `numpy.load`
    reads with ``allow_pickle=False``. Deterministic (members sorted, fixed zip times), so a retried write of the same
    grade holds exactly the bytes already written (`write_once`)."""
    import zipfile

    import numpy as np

    _require(type(exam_key) is str and exam_key, "case_errors_exam_key_missing")
    members = {
        **to_arrays(content),
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
