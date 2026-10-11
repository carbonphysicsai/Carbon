"""CPU-only field/order checker. Does not execute a reference solver."""

import argparse
import hashlib
import json
import math
import re
from itertools import pairwise
from pathlib import Path


class VerificationError(ValueError):
    pass


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def exact(kind, point, t):
    if kind == "elmer-heat":
        return 1 + math.prod(math.sin(math.pi * v) for v in point) * math.cos(
            2 * math.pi * t
        )
    if kind == "getdp-a":
        x, y = point
        return math.sin(math.pi * x) * math.sin(math.pi * y)
    if kind == "pybamm-particle":
        (r,) = point
        return math.exp(-t) * (1 + r**2 + r**4)
    if kind == "elmer-helmholtz":
        x, y, z = point
        return math.sin(math.pi * x) * math.sin(math.pi * y) * math.sin(math.pi * z)
    if kind == "openfoam-scalar":
        x, y = point
        return 1 + math.exp(-t) * math.sin(math.pi * x) * math.sin(math.pi * y)
    if kind == "calculix-ux":
        x, y, z = point
        return math.sin(math.pi * x) * math.sin(math.pi * y) * math.sin(math.pi * z)
    if kind == "calculix-rod-mode":
        (mode,) = point
        if mode not in (0, 1, 2):
            raise VerificationError("registered axial mode required")
        return (2 * mode + 1) / 4
    if kind == "meep-bloch-mode":
        (k,) = point
        return abs(k)
    if kind == "openfoam-periodic":
        (x,) = point
        return 1 + 0.2 * math.exp(-4 * math.pi**2 * 0.01 * t) * math.sin(
            2 * math.pi * (x - t)
        )
    raise VerificationError("unsupported manufactured field")


def field_norm(kind, row):
    points, values, weights = row["points"], row["values"], row["weights"]
    if (
        not points
        or not len(points) == len(values) == len(weights)
        or len(points) > 1000000
    ):
        raise VerificationError("nonempty complete field sample required")
    dimensions = {
        "getdp-a": 2,
        "pybamm-particle": 1,
        "openfoam-scalar": 2,
        "calculix-rod-mode": 1,
        "meep-bloch-mode": 1,
        "openfoam-periodic": 1,
    }.get(kind, 3)
    if type(row["t"]) not in (int, float) or not math.isfinite(row["t"]):
        raise VerificationError("finite time required")
    errors = []
    for p, value, weight in zip(points, values, weights, strict=True):
        if (
            len(p) != dimensions
            or not all(
                type(x) in (int, float) and math.isfinite(x)
                for x in (*p, value, weight)
            )
            or weight <= 0
        ):
            raise VerificationError("finite, positive-weight field samples required")
        errors.append(value - exact(kind, p, row["t"]))
    return {
        "l2": math.sqrt(
            sum(w * e**2 for w, e in zip(weights, errors, strict=True)) / sum(weights)
        ),
        "linf": max(abs(e) for e in errors),
        "samples": len(points),
    }


def observed_orders(h, errors):
    if len(h) < 3 or len(h) != len(errors):
        raise VerificationError("at least three complete refinement rungs required")
    if not all(
        type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (*h, *errors)
    ):
        raise VerificationError(
            "positive errors/scales; zero error does not demonstrate order"
        )
    if any(a <= b for a, b in pairwise(h)):
        raise VerificationError("strictly refining scales required")
    return [
        math.log(a / b) / math.log(ha / hb)
        for ha, hb, a, b in zip(h, h[1:], errors, errors[1:])
    ]


def verify(data, criteria, *, expected_image):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_image):
        raise VerificationError("immutable image identity required")
    if criteria["status"] not in ("HUMAN_INPUT", "ACCEPTED_DEVELOPMENT"):
        raise VerificationError("explicit proposed/adopted criteria required")
    required = {
        "schema",
        "scope",
        "kind",
        "family",
        "image_digest",
        "spec_digest",
        "adapter_digest",
        "rows",
        "raw_outputs",
    }
    if (
        set(data) != required
        or data["schema"] != "carbon.code-verification.fields.v1"
        or data["scope"] != "PUBLIC_DEVELOPMENT"
    ):
        raise VerificationError("closed public DEVELOPMENT field export required")
    if data["image_digest"] != expected_image:
        raise VerificationError("rebuild/repin requires fresh verification")
    for name in ("spec_digest", "adapter_digest"):
        if (
            not re.fullmatch(r"sha256:[0-9a-f]{64}", data[name])
            or data[name] != criteria[name]
        ):
            raise VerificationError("spec/adapter identity mismatch")
    if criteria["family"] != data["family"] or criteria["kind"] != data["kind"]:
        raise VerificationError("inapplicable acceptance criteria")
    if not data["raw_outputs"] or any(
        not re.fullmatch(r"sha256:[0-9a-f]{64}", x) for x in data["raw_outputs"]
    ):
        raise VerificationError("retained raw-output identities required")
    rows = data["rows"]
    expected_h = criteria["h"]
    if [r["h"] for r in rows] != expected_h or len(rows) != len(data["raw_outputs"]):
        raise VerificationError("registered ladder/output inventory mismatch")
    if any(r["t"] != criteria["t"] for r in rows):
        raise VerificationError("registered observer time mismatch")
    norms = [field_norm(data["kind"], row) for row in rows]
    orders = {
        key: observed_orders(expected_h, [r[key] for r in norms])
        for key in ("l2", "linf")
    }
    band = criteria["order_band"]
    if (
        len(band) != 2
        or not all(type(x) in (int, float) and math.isfinite(x) for x in band)
        or band[0] > band[1]
    ):
        raise VerificationError("finite recommended/adopted order band required")
    agrees = all(band[0] <= values[-1] <= band[1] for values in orders.values())
    accepted = criteria["status"] == "ACCEPTED_DEVELOPMENT"
    return {
        "schema": "carbon.code-verification.result.v1",
        "kind": "code_verification",
        "family": data["family"],
        "image_digest": expected_image,
        "source_digest": digest(data),
        "criteria_digest": digest(criteria),
        "norms": norms,
        "orders": orders,
        "metrics": {"l2_order": orders["l2"][-1], "linf_order": orders["linf"][-1]},
        "recommendation_agrees": agrees,
        "accepted_development_pass": agrees and accepted,
        "state": (
            "PASS"
            if agrees and accepted
            else "HUMAN_INPUT" if agrees else "REFERENCE_FINDING"
        ),
        "qualified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fields", type=Path)
    parser.add_argument("criteria", type=Path)
    parser.add_argument("--expected-image", required=True)
    args = parser.parse_args(argv)
    try:
        for path in (args.fields, args.criteria):
            if path.stat().st_size > 64 * 1024 * 1024:
                raise VerificationError("bounded export required")
        result = verify(
            json.loads(args.fields.read_text()),
            json.loads(args.criteria.read_text()),
            expected_image=args.expected_image,
        )
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["accepted_development_pass"] else 3
    except (VerificationError, ValueError, KeyError, TypeError, OSError):
        print("verification refused: missing, unbound or invalid public evidence")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
