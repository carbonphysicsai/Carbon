"""Read retained f13 SaveScalars integrals. Never runs a solver or repairs truth.

See docs/development/challenge_pipeline/round1/f13-saved-integral-check.md.
Stdlib only; usable by Data Collection outside the installed Carbon package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

SCHEMA = "carbon.f13-saved-integral-input.v1"
REPORT = "carbon.f13-saved-integral-report.v1"
CLOSURE = 0.01  # round1/f13-compressor-silencer.md section 5; not a new gate
QUANTITIES = (
    "frequency",
    "in_real",
    "out_real",
    "in_imag",
    "out_imag",
    "in_abs2",
    "out_abs2",
)
HEX = re.compile(r"^[0-9a-f]{64}$")
REV = re.compile(r"^[0-9a-f]{40}$")
NAME = re.compile(r"^\s*(\d+)\s*:\s*(.*?)\s*$")
MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 10000  # file/resource guard, not a scientific frequency law


class InputError(ValueError):
    """Bounded input errors contain no raw file contents or paths."""


def _require(ok, code):
    if not ok:
        raise InputError(code)


def _shape(value, keys, code):
    _require(isinstance(value, dict) and set(value) == set(keys), code)


def _number(value, code, *, positive=False):
    _require(type(value) in (int, float), code)
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise InputError(code) from error
    _require(math.isfinite(result) and (not positive or result > 0), code)
    return result


def _json(data):
    def pairs(items):
        out = {}
        for key, value in items:
            _require(key not in out, "DUPLICATE_JSON_KEY")
            out[key] = value
        return out

    try:
        return json.loads(data, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise InputError("INVALID_JSON") from error


def _read(path):
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError as error:
        raise InputError("DATA_REQUIRED") from error
    _require(0 < len(data) <= MAX_BYTES, "FILE_SIZE")
    return data


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _text(data):
    try:
        return data.decode("utf-8")
    except UnicodeError as error:
        raise InputError("INVALID_UTF8") from error


def check_saved(data: bytes, names: bytes, deck: bytes, mapping: bytes) -> dict:
    """Validate identities/coverage before reporting any closure conclusion."""
    for raw in (data, names, deck, mapping):
        _require(0 < len(raw) <= MAX_BYTES, "FILE_SIZE")
    side = _json(mapping)
    _shape(
        side,
        ("schema", "scope", "sha256", "source", "area_basis", "columns"),
        "INPUT_SHAPE",
    )
    _require(side["schema"] == SCHEMA, "SCHEMA")
    _require(side["scope"] in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"), "SCOPE")
    _shape(side["sha256"], ("data", "names", "deck"), "HASH_SHAPE")
    identity = {
        key: _digest(raw)
        for key, raw in (("data", data), ("names", names), ("deck", deck))
    }
    for key, value in side["sha256"].items():
        _require(isinstance(value, str) and HEX.fullmatch(value), "HASH_FORMAT")
        _require(value == identity[key], "HASH_MISMATCH")
    source = side["source"]
    _shape(source, ("revision", "image_digest", "model", "phasor"), "SOURCE_SHAPE")
    _require(
        isinstance(source["revision"], str) and REV.fullmatch(source["revision"]),
        "REVISION",
    )
    _require(
        isinstance(source["image_digest"], str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", source["image_digest"]),
        "IMAGE",
    )
    _require(source["model"] == "EQUAL_PORT_PLANE_ROBIN_REAL_INCIDENT", "MODEL")
    _require(source["phasor"] == "exp(+i*omega*t)", "PHASOR")
    _require(
        side["area_basis"] == "OPERATOR_VERIFIED_EQUAL_PORT_AREAS_AND_BC_IDS",
        "AREA_BASIS",
    )
    meta = _json(deck)
    _require(isinstance(meta, dict), "DECK_SHAPE")
    # Acquisition deck has additional geometry/meshing fields; none executed.
    required = {"rho", "c", "port_area_m2", "amplitude_pa", "frequencies_hz"}
    _require(required <= set(meta), "DECK_FIELDS")
    rho, c, area, amp = (
        _number(meta[key], "DECK_NUMBER", positive=True)
        for key in ("rho", "c", "port_area_m2", "amplitude_pa")
    )
    expected = meta["frequencies_hz"]
    _require(
        isinstance(expected, list) and 0 < len(expected) <= MAX_ROWS, "FREQUENCY_LIST"
    )
    expected = [_number(f, "FREQUENCY", positive=True) for f in expected]
    _require(expected == sorted(set(expected)), "FREQUENCY_ORDER")

    entries = {}
    for line in _text(names).splitlines():
        match = NAME.fullmatch(line)
        if match:
            _require(len(match[1]) <= 5, "NAMES_INDEX")
            column, label = int(match[1]), match[2]
            _require(column > 0 and column not in entries and label, "NAMES_INDEX")
            entries[column] = label
    _require(
        entries
        and len(entries) <= MAX_ROWS
        and sorted(entries) == list(range(1, len(entries) + 1)),
        "NAMES_COVERAGE",
    )
    columns = side["columns"]
    _shape(columns, QUANTITIES, "COLUMN_SHAPE")
    used = []
    for column in columns.values():
        _shape(column, ("index", "name"), "COLUMN_ENTRY")
        index = column["index"]
        _require(type(index) is int and index in entries, "COLUMN_INDEX")
        _require(column["name"] == entries[index], "COLUMN_NAME")
        used.append(index)
    _require(len(set(used)) == len(used), "COLUMN_ALIAS")
    rows = []
    for line in _text(data).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        _require(len(parts) == len(entries), "ROW_WIDTH")
        try:
            values = [float(part.replace("D", "E").replace("d", "e")) for part in parts]
        except ValueError as error:
            raise InputError("ROW_NUMBER") from error
        _require(all(math.isfinite(v) for v in values), "ROW_NONFINITE")
        rows.append({key: values[col["index"] - 1] for key, col in columns.items()})
        _require(len(rows) <= MAX_ROWS, "ROW_COUNT")
    # No deduplication, favorable filtering or silently skipped frequencies.
    _require([row["frequency"] for row in rows] == expected, "FREQUENCY_COVERAGE")
    scale = 2 * rho * c
    _require(math.isfinite(scale) and scale > 0, "DECK_SCALE")
    try:
        p_inc = amp**2 * area / scale
    except (OverflowError, ZeroDivisionError) as error:
        raise InputError("INCIDENT_POWER") from error
    _require(math.isfinite(p_inc) and p_inc > 0, "INCIDENT_POWER")
    results = []
    try:
        for row in rows:
            i_in = complex(row["in_real"], row["in_imag"])
            i_out = complex(row["out_real"], row["out_imag"])
            h_in, h_out = row["in_abs2"], row["out_abs2"]
            terms = [abs(i_in) ** 2 / area, abs(i_out) ** 2 / area]
            v_in, v_out = (h_in - terms[0]) / scale, (h_out - terms[1]) / scale
            # Only floating-point subtraction noise; no physical/quadrature allowance.
            floors = [
                64 * sys.float_info.epsilon * max(abs(h), term) / scale
                for h, term in zip((h_in, h_out), terms)
            ]
            variance_valid = (
                h_in >= 0 and h_out >= 0 and v_in >= -floors[0] and v_out >= -floors[1]
            )
            p_ref_pw = abs(i_in / area - amp) ** 2 * area / scale
            p_out_pw = terms[1] / scale
            p_out_all = h_out / scale
            p_ref_all = (h_in - 2 * amp * i_in.real + amp**2 * area) / scale
            r_old = p_inc - p_ref_pw - p_out_all
            r_robin = r_old - v_in
            result = {
                "frequency_hz": row["frequency"],
                "incident_w": p_inc,
                "reflected_plane_w": p_ref_pw,
                "outlet_plane_w": p_out_pw,
                "reflected_robin_w": p_ref_all,
                "outlet_all_w": p_out_all,
                "inlet_variance_w": v_in,
                "outlet_variance_w": v_out,
                "old_residual_w": r_old,
                "robin_residual_w": r_robin,
                "identity_error_w": r_robin - (p_inc - p_ref_all - p_out_all),
                "old_residual_fraction": r_old / p_inc,
                "robin_residual_fraction": r_robin / p_inc,
                "variance_valid": variance_valid,
            }
            _require(
                all(math.isfinite(v) for v in result.values()), "DERIVED_NONFINITE"
            )
            result["old_closure"] = variance_valid and abs(r_old / p_inc) <= CLOSURE
            result["robin_closure"] = variance_valid and abs(r_robin / p_inc) <= CLOSURE
            results.append(result)
    except (OverflowError, ZeroDivisionError) as error:
        raise InputError("DERIVED_NONFINITE") from error
    old_ok = all(row["old_closure"] for row in results)
    robin_ok = all(row["robin_closure"] for row in results)
    invalid = sum(not row["variance_valid"] for row in results)
    status = (
        "INTEGRAL_FINDING"
        if invalid
        else (
            "ACCOUNTING_CLOSURE"
            if old_ok and robin_ok
            else "MIXED_EXTRACTION_FINDING" if robin_ok else "CLOSURE_FINDING"
        )
    )

    def worst(key):
        # First (lowest) frequency wins exact ties; input is ordered/complete.
        row = max(results, key=lambda item: abs(item[key]))
        return {"frequency_hz": row["frequency_hz"], "signed_fraction": row[key]}

    return {
        "schema": REPORT,
        "status": status,
        "physical_reference_status": "UNRESOLVED",
        "scope": side["scope"],
        "basis": {
            "sha256": identity | {"mapping": _digest(mapping)},
            "source": source,
            "area_basis": side["area_basis"],
            "operator_assertions_independently_verified": False,
            "rows_examined": len(results),
            "expected_rows": len(expected),
            "closure_abs_fraction": CLOSURE,
            "criterion_source": "round1/f13-compressor-silencer.md#5-reference-policy",
            "incident_w": p_inc,
            "incident_minus_unit_w": p_inc - 1.0,
            "not_checked": [
                "physical modal/velocity flux",
                "mesh/lead convergence",
                "quadrature adequacy",
                "full-band buyer feasibility",
                "Tier 2 agreement",
            ],
        },
        "old_closure": old_ok,
        "robin_closure": robin_ok,
        "invalid_variance_rows": invalid,
        "worst_old": worst("old_residual_fraction"),
        "worst_robin": worst("robin_residual_fraction"),
        "rows": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--names", type=Path, required=True)
    parser.add_argument("--deck", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = check_saved(
            *(_read(path) for path in (args.data, args.names, args.deck, args.mapping))
        )
    except InputError as error:
        print(
            json.dumps(
                {
                    "schema": REPORT,
                    "status": "INPUT_REQUIRED",
                    "code": str(error),
                    "physical_reference_status": "UNRESOLVED",
                    "rows_examined": 0,
                }
            )
        )
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["status"] == "ACCOUNTING_CLOSURE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
