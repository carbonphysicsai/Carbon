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


#: Which ids a Challenge's copy renames. F02's action names and Battery's
#: registered EV4 candidates carry meaning, so those keep theirs and only their
#: row order differs between copies. (C16: each manifest declares this; until the
#: registry lands, this is the one place.)
OPAQUE_BY_CHALLENGE = {
    "electric-motor-magnetics": OPAQUE,
    "chip-cold-plate": OPAQUE,
    "f08-ribbed-bracket": OPAQUE,
    "f02": (),
    "battery-fastcharge-ageing-development-v1": (),
}


def opaque_for(challenge_id):
    """The opaque ids of a registered Challenge, or a refusal (fail closed)."""
    try:
        return OPAQUE_BY_CHALLENGE[challenge_id]
    except KeyError:
        raise CopyRefused("copy_challenge_unregistered") from None


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


def row_order(cohorts, inputs, case_ids, records, *, opaque=OPAQUE):
    """The canonical order of a bank's rows, as indexes into it: by content
    (cohort, inputs, native record without its opaque ids) when the Challenge's
    case ids are opaque, else by case id. Every copy of one exam has one canonical
    order, so a grader that maps its rows to it first scores them identically."""
    if "case_id" not in opaque:
        order = sorted(range(len(case_ids)), key=lambda i: case_ids[i])
        if len({case_ids[i] for i in order}) != len(order):
            raise CopyRefused("copy_ids_not_unique")
        return order
    keys = [
        _canonical(
            {
                "cohort": cohorts[i],
                "inputs": [float(v) for v in inputs[i]],
                "record": _strip(records[i], opaque),
            }
        )
        for i in range(len(case_ids))
    ]
    if len(set(keys)) != len(keys):
        raise CopyRefused("copy_rows_not_distinct")
    return sorted(range(len(keys)), key=lambda i: keys[i])


def bank_order(bank, *, opaque=OPAQUE):
    return row_order(
        bank["cohorts"],
        bank["inputs"],
        bank["case_ids"],
        bank["reference_records"],
        opaque=opaque,
    )


def canonical_bank(bank, *, opaque=OPAQUE):
    """The bank with its rows in canonical order (a definition built from it is
    the same for every copy)."""
    order = bank_order(bank, opaque=opaque)
    return {
        name: ([bank[name][i] for i in order] if name in PER_ROW else bank[name])
        for name in bank
    }


def canonical_call(rows, outputs, repeats, *, opaque=OPAQUE):
    """``(rows, outputs, repeats)`` for one producer measure, all in canonical
    order. ``rows`` are `physical_dual_pack.bank_rows` rows and ``outputs`` and
    each of ``repeats`` the model's flat rows, in the copy's own order. A producer
    measure never sees a copy's order."""
    order = row_order(
        [r["cohort"] for r in rows],
        [list(r["inputs"].values()) for r in rows],
        [r["case_id"] for r in rows],
        [r["record"] for r in rows],
        opaque=opaque,
    )
    return (
        [rows[i] for i in order],
        [outputs[i] for i in order],
        [[run[i] for i in order] for run in repeats],
    )


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


# --- the canonical identity of a copy (rank ids) -----------------------------------------


def _cell_key(bank, i, opaque):
    """A row's content key: cohort, inputs, native record and reference, without
    its opaque ids."""
    return _canonical(
        {
            "cohort": bank["cohorts"][i],
            "inputs": [float(v) for v in bank["inputs"][i]],
            "record": _strip(bank["reference_records"][i], opaque),
            "reference": [_number(float(v)) for v in bank["references"][i]],
        }
    ).decode("utf-8")


def _group_ranks(keys_by_group):
    """``{group id: rank}`` where a group's rank is its place when the groups are
    ordered by their members' content (never by their ids)."""
    content = {
        group: "\x00".join(sorted(keys)) for group, keys in keys_by_group.items()
    }
    if len(set(content.values())) != len(content):
        raise CopyRefused("copy_groups_not_distinct")
    return {g: r for r, g in enumerate(sorted(content, key=content.__getitem__))}


def canonicalize(bank, *, opaque=OPAQUE, objective=None):
    """The bank in its canonical form: rows in content order, and every opaque id
    renamed by rank (case ``c0000``…, design ``d0``…, condition ``k0``…). Any copy
    of one exam, whatever its order and ids, canonicalizes to the same bank, so a
    receiver recovers today's identity from content alone, and a header needs
    carry no permutation or id map. Ids a Challenge declares meaningful are kept
    and then order by id (`row_order`)."""
    n = len(bank["case_ids"])
    keys = [_cell_key(bank, i, opaque) for i in range(n)]
    if len(set(keys)) != n:
        raise CopyRefused("copy_rows_not_distinct")
    records = bank["reference_records"]
    design_rank = condition_rank = None
    if "design_id" in opaque and any("design_id" in r for r in records):
        design_rank = _group_ranks(
            {
                d: [keys[i] for i in range(n) if records[i].get("design_id") == d]
                for d in {r.get("design_id") for r in records}
            }
        )
    if "condition_id" in opaque and any("condition_id" in r for r in records):
        condition_rank = _group_ranks(
            {
                c: [keys[i] for i in range(n) if records[i].get("condition_id") == c]
                for c in {r.get("condition_id") for r in records}
            }
        )

    def place(i):
        record = records[i]
        return (
            design_rank[record["design_id"]] if design_rank else 0,
            condition_rank[record["condition_id"]] if condition_rank else 0,
            keys[i],
        )

    if "case_id" in opaque:
        order = sorted(range(n), key=place)
    else:
        order = sorted(range(n), key=lambda i: bank["case_ids"][i])
    bank_records_in_order = [bank["reference_records"][i] for i in order]
    derived = {
        name: ([bank[name][i] for i in order] if name in PER_ROW else bank[name])
        for name in bank
    }
    if "case_id" in opaque:
        derived["case_ids"] = [f"c{r:04d}" for r in range(n)]
    out = []
    for r, record in enumerate(derived["reference_records"]):
        record = copy.deepcopy(record)
        if "case_id" in opaque and "case_id" in record:
            record["case_id"] = f"c{r:04d}"
        if design_rank is not None:
            record["design_id"] = f"d{design_rank[record['design_id']]}"
        if condition_rank is not None:
            record["condition_id"] = f"k{condition_rank[record['condition_id']]}"
        out.append(record)
    derived["reference_records"] = out
    if objective is None:
        return derived
    mapping = {}
    for old_record, new_record in zip(bank_records_in_order, out, strict=True):
        for name in opaque:
            if name in old_record and name in new_record:
                mapping[old_record[name]] = new_record[name]
    return derived, _rename(copy.deepcopy(objective), mapping)
