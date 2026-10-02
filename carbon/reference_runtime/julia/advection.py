"""Closed advection study bytes; execution remains in the admitted Julia carrier."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from carbon.scientific_tasks.definitions import (
    Audience,
    Custody,
    PeriodicDefinition,
    Template,
)

METHOD_ID = "julia_periodic_advection_upwind_refinement_v1"
VERSION = "1.13.0"
UNITS = "carbon_advection_definition_native_v1"
LAYOUT = "time,x;C;<f8;point_estimate;periodic"
MAX_BYTES = 32768
MAX_STEPS = 200000
CASE_ID = "carbon.public.advection.translating-sine.v1"


def source() -> str:
    return Path(__file__).with_suffix(".jl").read_text(encoding="utf8")


def source_digest() -> str:
    return "sha256:" + hashlib.sha256(source().encode()).hexdigest()


def public_definition() -> PeriodicDefinition:
    """One public analytic control, not a sampled Challenge population."""
    return PeriodicDefinition(
        Template.ADVECTION_CONTROL,
        Custody.PUBLIC_DEVELOPMENT,
        2.0 * math.pi,
        tuple(1.0 + 0.25 * math.sin(2 * math.pi * i / 64) for i in range(64)),
        (0.0, 0.25, 0.5, 0.75, 1.0),
        1.0,
        UNITS,
        CASE_ID,
    )


@dataclass(frozen=True)
class AdvectionRequest:
    definition: PeriodicDefinition

    def __post_init__(self):
        d = self.definition
        if (
            type(d) is not PeriodicDefinition
            or d.template is not Template.ADVECTION_CONTROL
            or d.custody is not Custody.PUBLIC_DEVELOPMENT
            or d.authoring is not None
        ):
            raise ValueError("public advection definition required")
        n = len(d.initial_field)
        dx = d.domain_length / (2 * n)
        if (
            not 16 <= n <= 512
            or n & (n - 1)
            or len(d.requested_times) > 64
            or dx <= 0
            or not math.isfinite(abs(d.parameter) / dx)
            or max(d.requested_times) * abs(d.parameter) / dx / 0.75
            + len(d.requested_times)
            > MAX_STEPS
        ):
            raise ValueError("advection serialization or work bound exceeded")
        if len(self.encode()) > MAX_BYTES:
            raise ValueError("advection request byte bound exceeded")

    def _body(self):
        d = self.definition
        return "\n".join(
            [
                "CARBON_JULIA_ADVECTION_REQUEST_V1",
                METHOD_ID,
                VERSION,
                d.content_digest,
                source_digest(),
                d.unit_system,
                LAYOUT,
                repr(d.domain_length),
                repr(d.parameter),
                str(len(d.initial_field)),
                ",".join(map(repr, d.initial_field)),
                ",".join(map(repr, d.requested_times)),
            ]
        )

    @property
    def digest(self):
        return "sha256:" + hashlib.sha256(self._body().encode("ascii")).hexdigest()

    def encode(self):
        return (self._body() + "\n" + self.digest + "\n").encode("ascii")

    def public_view(self):
        return {
            "definition": self.definition.project(Audience.MINER),
            "execution_capability": "REGISTERED_DEVELOPMENT_STUDY_REQUIRES_GRANT",
            "method": METHOD_ID,
            "source_digest": source_digest(),
            "request_digest": self.digest,
            "CFL": 0.75,
            "refinement": "2x grid; periodic linear interpolation of nodal initial values",
            "interpretation": "DISCREPANCY_NOT_CERTIFIED_ERROR_BOUND",
            "scientifically_qualified": False,
            "training_support_eligible": False,
        }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate result field")
        result[key] = value
    return result


def decode_outputs(files: dict[str, bytes], request: AdvectionRequest) -> dict:
    """Validate closed metadata and exact finite C-order arrays before association."""
    if type(request) is not AdvectionRequest or type(files) is not dict:
        raise ValueError("typed advection result required")
    if set(files) != {"result.json", "coarse.f64le", "fine.f64le"}:
        raise ValueError("unexpected advection output")
    if (
        any(type(v) is not bytes for v in files.values())
        or len(files["result.json"]) > 4096
    ):
        raise ValueError("bounded output bytes required")
    m = json.loads(files["result.json"], object_pairs_hook=_unique)
    numeric = {
        "coarse_mean_drift",
        "fine_mean_drift",
        "refinement_rms",
        "refinement_max",
        "completed_horizon",
        "solver_seconds",
    }
    integers = {
        "coarse_points",
        "fine_points",
        "coarse_steps",
        "fine_steps",
        "allocated_bytes",
    }
    if type(m) is not dict or set(m) != numeric | integers | {
        "schema",
        "method",
        "request_digest",
        "units",
        "layout",
        "shape",
    }:
        raise ValueError("closed advection metadata required")
    n, times = len(request.definition.initial_field), len(
        request.definition.requested_times
    )
    if (
        m["schema"] != "carbon.julia.advection-result.v1"
        or m["method"] != METHOD_ID
        or m["request_digest"] != request.digest
        or m["units"] != UNITS
        or m["layout"] != LAYOUT
        or m["shape"] != [times, n]
        or any(type(v) is not int for v in m["shape"])
        or any(type(m[k]) is not int or m[k] < 0 for k in integers)
        or m["coarse_points"] != n
        or m["fine_points"] != 2 * n
        or max(m["coarse_steps"], m["fine_steps"]) > MAX_STEPS
        or any(
            type(m[k]) not in (float, int) or not math.isfinite(m[k]) or m[k] < 0
            for k in numeric
        )
        or m["completed_horizon"] != max(request.definition.requested_times)
    ):
        raise ValueError("advection result contract mismatch")
    values = {}
    for name in ("coarse.f64le", "fine.f64le"):
        if len(files[name]) != times * n * 8:
            raise ValueError("advection array shape mismatch")
        values[name] = [v[0] for v in struct.iter_unpack("<d", files[name])]
        if not all(math.isfinite(v) for v in values[name]):
            raise ValueError("advection array must be finite")
        seen = {}
        for index, requested_time in enumerate(request.definition.requested_times):
            row = values[name][index * n : (index + 1) * n]
            if requested_time == 0.0 and row != list(request.definition.initial_field):
                raise ValueError("advection initial-condition layout mismatch")
            if requested_time in seen and seen[requested_time] != row:
                raise ValueError("repeated advection time has inconsistent output")
            seen[requested_time] = row
    # Recompute diagnostic consistency; this is a serialization check, not a
    # numerical acceptance threshold or certified estimate of reference error.
    errors = [a - b for a, b in zip(values["fine.f64le"], values["coarse.f64le"])]
    expected = math.sqrt(sum(e * e for e in errors) / len(errors))
    if not math.isclose(
        m["refinement_rms"], expected, rel_tol=1e-12, abs_tol=1e-15
    ) or m["refinement_max"] != max(map(abs, errors)):
        raise ValueError("advection diagnostic/array mismatch")
    return {**m, "scientifically_qualified": False, "training_support_eligible": False}
