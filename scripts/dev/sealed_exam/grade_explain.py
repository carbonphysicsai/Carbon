"""Explain a counted grade's producer checks: every failing check in ONE pass, with the values behind the binding.

The dual producer refuses with one typed code at its first failed check, and a live receiver keeps only
that code. ``dual_native_producer_or_train_binding`` stands for THREE conditions at once (the pack's
accuracy definition names this code's producer digest, the pack's train and the resolved bank). This module,
installed by ``receiver_copy_repro.py grade``, changes nothing a grade decides:

- the producer's ``require`` records a failed check and goes on (a later step may then fail for the same
  root cause; the FIRST line of the list is the root), and
- the producer's input step prints the values behind the binding: the definition's producer / train / bank
  digests against the ones this host computes, and this host's per-file producer hashes (digests only, no
  row values, no keys), so a mismatch names which of the three differs and, for the producer, which file.

It patches module attributes in the running process only; no file is written, no state is changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

FAILED: list = []


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def producer_files(adapter) -> dict:
    """``{file name: sha256}`` of every file the producer digest covers (CRLF read as LF), as this host has them."""
    from carbon.scoring import physical_dual_pack as pdp

    here = Path(pdp.__file__).parent
    names = sorted({*pdp._SHARED_FILES, *adapter.FILES})
    return {
        name: _sha((here / name).read_bytes().replace(b"\r\n", b"\n")) for name in names
    }


def bank_field_digests(bank) -> dict:
    """Per-field digests of the parts ``bank_digest`` pins, each as the bank lists them and in ``case_id`` order.

    ``{field: {"as_listed": sha, "by_case_id": sha}}`` for case_ids, cohorts, inputs, records and (when the bank
    is masked) reference_present, plus ``records.<key>`` for each native record key. Equal ``by_case_id`` with
    different ``as_listed`` is an ORDER-only difference; a different ``by_case_id`` is a CONTENT difference.
    Digests only: no row value is printed."""
    from carbon.scoring import physical_dual_pack as pdp

    ids = list(bank["case_ids"])
    order = sorted(range(len(ids)), key=lambda i: ids[i])
    columns = {
        "case_ids": ids,
        "cohorts": list(bank["cohorts"]),
        "inputs": [[float(v) for v in row] for row in bank["inputs"]],
        "records": list(bank["reference_records"]),
    }
    if "reference_present" in bank:
        columns["reference_present"] = list(pdp.reference_mask(bank))
    keys = sorted({k for r in columns["records"] if type(r) is dict for k in r})
    for key in keys:
        columns["records." + key] = [
            r.get(key) if type(r) is dict else None for r in columns["records"]
        ]

    def digest(rows):
        return pdp.sha(pdp.canonical(rows))

    return {
        name: {
            "as_listed": digest(rows),
            "by_case_id": digest([rows[i] for i in order]),
        }
        for name, rows in columns.items()
    }


def field_lines(bank, label) -> list:
    lines = [f"bank fields ({label}; {len(bank['case_ids'])} rows):"]
    for name, pair in bank_field_digests(bank).items():
        lines.append(
            f"   {name:<28} as listed {pair['as_listed'][7:23]}…  by case_id {pair['by_case_id'][7:23]}…"
        )
    return lines


def binding_lines(adapter, definition, entry, train_raw, bank) -> list:
    """The three conditions of the binding check, each with both sides, as printable lines."""
    from carbon.scoring import physical_dual_pack as pdp

    computed = pdp.producer_digest(adapter)
    train = _sha(train_raw)
    bank_now = pdp.bank_digest(bank)
    producer_ok = definition.get("producer_digest") == computed
    train_ok = definition.get("train_digest") == entry.get("train_digest") == train
    bank_ok = definition.get("bank_digest") == bank_now
    lines = [
        f"binding  PRODUCER {'ok' if producer_ok else 'DIFFERS'}",
        f"           pack definition {definition.get('producer_digest')}",
        f"           this host       {computed}",
    ]
    if not producer_ok:
        lines.append(
            "           this host's files (compare with the host that built the pack):"
        )
        lines += [f"             {n}  {d}" for n, d in producer_files(adapter).items()]
    lines += [
        f"binding  TRAIN {'ok' if train_ok else 'DIFFERS'}",
        f"           pack definition {definition.get('train_digest')}",
        f"           task's entry    {entry.get('train_digest')}",
        f"           pack train role {train}",
        f"binding  BANK {'ok' if bank_ok else 'DIFFERS'}",
        f"           pack definition {definition.get('bank_digest')}",
        f"           resolved bank   {bank_now}  ({len(bank['case_ids'])} rows)",
    ]
    if not bank_ok:
        lines += field_lines(bank, "the bank this host resolved")
        lines.append(
            "           (run bank_fields.py on the build host's canonical batch and compare field by field)"
        )
    return lines


def install(print_=print) -> list:
    """Patch the producer in this process: collect failed checks, explain the binding. Returns the shared list."""
    from carbon.scoring import physical_dual_pack as pdp
    from carbon.scoring import private_evaluation_source as source

    FAILED.clear()

    def collecting(condition, code):
        if not condition:
            FAILED.append(code)
            print_(f"CHECK FAILED #{len(FAILED)}: {code}  (continuing)")

    source._producer_require = collecting
    real_inputs = pdp._inputs

    def traced(adapter, *, selected, public_root, private_root, entry, bank, **rest):
        try:
            definition = selected.read_json_role(
                public_root, "public", "accuracy_definition", max_bytes=1024 * 1024
            )
            train_raw = selected.read_role(
                public_root, "public", "train", max_bytes=16 * 1024**2
            )
            print_(
                f"producer input step: {getattr(adapter, 'CHALLENGE', '?')} "
                f"{getattr(adapter, 'VERSION', '?')}  pool_graded={bool(getattr(adapter, 'POOL_GRADED', False))}"
            )
            for line in binding_lines(adapter, definition, entry, train_raw, bank):
                print_(line)
        except Exception as failure:  # noqa: BLE001
            # (an explainer never decides the grade)
            print_(f"(explainer could not read the binding: {type(failure).__name__})")
        return real_inputs(
            adapter,
            selected=selected,
            public_root=public_root,
            private_root=private_root,
            entry=entry,
            bank=bank,
            **rest,
        )

    pdp._inputs = traced
    return FAILED


def report(print_=print) -> None:
    if FAILED:
        print_(
            f"{len(FAILED)} producer check(s) failed, in order (the first is the root):"
        )
        for number, code in enumerate(FAILED, 1):
            print_(f"   {number}. {code}")
    else:
        print_("no producer check recorded a failure")
