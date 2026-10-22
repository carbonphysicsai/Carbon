"""Per-validator exam copies (traceable copies, c'; Validator ruling, Phase A).

A validator's copy of an evaluation bank differs from every other validator's in
its row order and its opaque ids only, derived from a Carbon-held per-validator
key; its scores, and the exam's identity, do not. This module is the pure
function that derives a copy and the canonical form that identifies the exam
whichever copy is read.

- **Canonical form** (`canonical_form`, `content_digest`): the rows keyed by their
  content (cohort, inputs, native record and reference row, with the opaque ids
  removed) and sorted. Two copies of one exam have one canonical form.
- **Derivation** (`derive_copy`): the rows permuted and the opaque ids renamed by
  HMAC-seeded maps. The same id map is applied to the design objective's id lists,
  so a copy is internally consistent. Ids a Challenge declares meaningful
  (F02's action names, Battery's registered candidates) are kept: ``opaque=()``.

This is not a watermark: re-sorting by content recovers the canonical form. It
traces careless leaks; together with the distribution host's signed delivery
record it narrows the rest. DEVELOPMENT only; no score depends on it.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import random

#: The ids that are opaque by default (Validator ruling): case, design, condition.
OPAQUE = ("case_id", "design_id", "condition_id")
#: The bank's per-row lists.
PER_ROW = (
    "case_ids",
    "cohorts",
    "inputs",
    "references",
    "reference_records",
    "reference_present",
)


class CopyRefused(ValueError):
    """A typed refusal; the code names the check."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _strip(record, opaque):
    return {k: v for k, v in record.items() if k not in opaque}


def _number(value):
    return None if value != value else value  # NaN -> null in the canonical form


def canonical_form(bank, *, opaque=OPAQUE):
    """The bank's rows with the opaque ids removed, keyed by content and sorted."""
    n = len(bank["case_ids"])
    present = bank.get("reference_present")
    rows = []
    for i in range(n):
        reference = [_number(float(v)) for v in bank["references"][i]]
        rows.append(
            {
                "cohort": bank["cohorts"][i],
                "inputs": [float(v) for v in bank["inputs"][i]],
                "record": _strip(bank["reference_records"][i], opaque),
                "reference": reference,
                "present": True if present is None else bool(present[i]),
            }
        )
    return sorted(rows, key=lambda row: _canonical(row))


def content_digest(bank, *, opaque=OPAQUE):
    """The exam's identity over its canonical form: equal for every copy."""
    return _digest(canonical_form(bank, opaque=opaque))


def _prf(key, *parts):
    mac = hmac.new(key, b"\x00".join(p.encode("utf-8") for p in parts), "sha256")
    return mac.digest()


def _rename(value, mapping):
    """``value`` with every string (and mapping key) that is exactly an old id
    replaced by its new one."""
    if type(value) is str:
        return mapping.get(value, value)
    if type(value) is list:
        return [_rename(v, mapping) for v in value]
    if type(value) is dict:
        return {_rename(k, mapping): _rename(v, mapping) for k, v in value.items()}
    return value


def derive_copy(bank, objective, *, key, opaque=OPAQUE):
    """``(bank', objective')``: this validator's copy of the exam.

    ``key`` is the Carbon-held per-validator key (bytes, at least 16). Rows are
    permuted and the opaque ids renamed from HMAC(key, content digest, ...), so the
    copy is a deterministic function of the exam and the key: two derivations are
    equal, two keys give different copies, and nothing here reads the score."""
    if type(key) is not bytes or len(key) < 16:
        raise CopyRefused("copy_key_invalid")
    n = len(bank["case_ids"])
    if any(len(bank[name]) != n for name in PER_ROW if name in bank):
        raise CopyRefused("copy_bank_rows")
    identity = content_digest(bank, opaque=opaque)
    order = list(range(n))
    random.Random(int.from_bytes(_prf(key, identity, "order"), "big")).shuffle(order)
    used = {}

    def new_id(old):
        if old not in used:
            fresh = "x" + _prf(key, identity, "id", old).hex()[:12]
            if fresh in used.values():
                raise CopyRefused("copy_id_collision")
            used[old] = fresh
        return used[old]

    for name in opaque:
        for record in bank["reference_records"]:
            if name in record:
                new_id(record[name])
    if "case_id" in opaque:
        for old in bank["case_ids"]:
            new_id(old)
    mapping = dict(used)

    derived = {
        name: ([bank[name][i] for i in order] if name in PER_ROW else bank[name])
        for name in bank
    }
    derived["case_ids"] = [mapping.get(c, c) for c in derived["case_ids"]]
    records = []
    for record in derived["reference_records"]:
        record = copy.deepcopy(record)
        for name in opaque:
            if name in record:
                record[name] = mapping.get(record[name], record[name])
        records.append(record)
    derived["reference_records"] = records
    return derived, _rename(copy.deepcopy(objective), mapping)
