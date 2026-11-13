"""Build Motor 1.8's development-bank linkage file from the record-now re-solves of the bank's own public cases.

    python scripts/dev/motor/build_dev_bank_1p8.py m2-s07.records.jsonl m2-s08.records.jsonl [--out PATH]

Reads the 1.6 development bank (`motor18_dev_grid._base_bank`: 30 PRACTICE + 48 grid cases with references; the probes
carry none) and, for every case with a reference, exactly one OK record-now record of that case id. Each record's inputs
must equal the bank row's inputs exactly; its torque must be byte-equal to the bank's pinned torque reference, or differ by
host-order rounding inside Carbon Validator-B's 8 Nov ruling bound (`physical_public_train.TORQUE_ROUNDING_RULING`;
listed in the file for Carbon Validator-Motor's read), else it STOPS. The bank keeps its own torque; only the three
phase linkages are taken from the record. Writes the canonical LF bytes of the file and prints its sha256 and counts
(no values). Public in-box cases only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


class BuildRefused(ValueError):
    """The records cannot make the 1.8 bank's linkage file (nothing is written)."""


def _finite_list(values, n):
    return (
        type(values) is list
        and len(values) == n
        and all(type(v) in (int, float) and math.isfinite(v) for v in values)
    )


def build(record_paths):
    """The linkage document from ``record_paths`` (JSONL), or a refusal."""
    import numpy as np

    from carbon.challenge_kit.physical_public_train import TORQUE_ROUNDING_RULING
    from carbon.motor.domain import ANGLE_STEPS, INPUTS
    from carbon.scoring import motor18_dev_grid as m

    bank = m._base_bank()
    present = tuple(bank.get("reference_present") or (True,) * len(bank["case_ids"]))
    rows = {
        case_id: (np.asarray(bank["inputs"][i], dtype=float), bank["references"][i])
        for i, (case_id, has) in enumerate(zip(bank["case_ids"], present, strict=True))
        if has
    }
    found = {}
    for path in record_paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            case_id = record.get("case_id")
            if case_id not in rows or record.get("status") != "OK":
                continue
            if case_id in found:
                raise BuildRefused(f"{case_id}: more than one OK record")
            found[case_id] = record
    missing = sorted(set(rows) - set(found))
    if missing:
        raise BuildRefused(f"{len(missing)} bank case(s) have no OK record")
    cases, rounding, worst, equal = {}, [], 0.0, 0
    bound = TORQUE_ROUNDING_RULING["max_abs_delta_nm"]
    for case_id in sorted(rows):
        record, (inputs, reference) = found[case_id], rows[case_id]
        given = record.get("inputs")
        if type(given) is not dict or set(given) != set(INPUTS):
            raise BuildRefused(f"{case_id}: record inputs are not the eight inputs")
        if [float(given[name]) for name in INPUTS] != [float(v) for v in inputs]:
            raise BuildRefused(f"{case_id}: record inputs differ from the bank's")
        torque = (record.get("outputs") or {}).get("torque_nm")
        if not _finite_list(torque, ANGLE_STEPS):
            raise BuildRefused(f"{case_id}: torque is not 60 finite values")
        want = [float(v) for v in reference]
        if [float(v) for v in torque] == want:
            equal += 1
        else:
            delta = max(abs(float(a) - b) for a, b in zip(torque, want, strict=True))
            if not delta < bound:
                raise BuildRefused(
                    f"{case_id}: torque differs from the bank's beyond the rounding ruling (STOP)"
                )
            rounding.append(case_id)
            worst = max(worst, delta)
        phases = ((record.get("record_now") or {}).get("phase_flux_linkage_wb")) or {}
        if set(phases) != set(m.PHASES) or not all(
            _finite_list(phases[p], ANGLE_STEPS) for p in m.PHASES
        ):
            raise BuildRefused(f"{case_id}: no whole finite phase flux linkage")
        cases[case_id] = {p: [float(v) for v in phases[p]] for p in m.PHASES}
    return {
        "schema": m.SCHEMA,
        "base": {"challenge": m.CHALLENGE, "version": m.BASE_VERSION},
        "cases": cases,
        "torque_check": {
            "byte_equal": equal,
            "host_order_rounding": rounding,
            "max_abs_delta_nm": worst,
            "ruling": TORQUE_ROUNDING_RULING["source"],
        },
    }


def main(argv=None):
    from carbon.scoring import motor18_dev_grid as m

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("records", nargs="+")
    parser.add_argument("--out", default=str(m.LINKAGE_FILE))
    args = parser.parse_args(argv)
    try:
        document = build(args.records)
    except BuildRefused as refused:
        print(json.dumps({"refused": str(refused)}))
        return 2
    raw = m.canonical(document)
    Path(args.out).write_bytes(raw)
    print(
        json.dumps(
            {
                "cases": len(document["cases"]),
                "torque_byte_equal": document["torque_check"]["byte_equal"],
                "torque_host_order_rounding": len(
                    document["torque_check"]["host_order_rounding"]
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
