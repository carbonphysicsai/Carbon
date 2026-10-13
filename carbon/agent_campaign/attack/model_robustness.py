"""Public DEVELOPMENT model-boundary probes; not a hostile-code executor.

The host supplies a trusted callable (possibly an isolated endpoint proxy).
No model loader, reference solver, registered campaign, score or public claim.
The first geometry grammar is explicitly 2D oriented triangle meshes only.
"""

from __future__ import annotations

import math
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass

from . import engine

SCHEMA = "carbon.model-robustness.probe.v1"
FAMILIES = ("geometric_deformation", "adversarial_mesh")
_PIN = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_NODES = 16384  # harness allocation bound, NOT a physical/support limit
MAX_CELLS = 32768


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _pin(value):
    return type(value) is str and _PIN.fullmatch(value) is not None


@dataclass(frozen=True)
class Mesh:
    """Bounded transport shape. Invalid *geometry* is deliberately representable."""

    nodes: tuple[tuple[float, float], ...]
    cells: tuple[tuple[int, int, int], ...]

    def __post_init__(self):
        if (
            type(self.nodes) is not tuple
            or not 3 <= len(self.nodes) <= MAX_NODES
            or type(self.cells) is not tuple
            or not 1 <= len(self.cells) <= MAX_CELLS
            or any(
                type(p) is not tuple or len(p) != 2 or not all(map(_number, p))
                for p in self.nodes
            )
            or any(
                type(c) is not tuple
                or len(c) != 3
                or any(type(i) is not int for i in c)
                for c in self.cells
            )
        ):
            raise ValueError("mesh_transport_shape")

    @property
    def identity(self):
        return engine.digest(asdict(self))

    def payload(self):
        # Fresh mutable transport for each call; never share witness/control state.
        return {
            "nodes": [list(p) for p in self.nodes],
            "cells": [list(c) for c in self.cells],
        }


def grid(segments: int, *, irregularity: float = 0.0) -> Mesh:
    """Deterministic unit-square triangulation; no seeds or protected input."""
    if type(segments) is not int or not 1 <= segments <= 64:
        raise ValueError("grid_segments_1_to_64")
    if not _number(irregularity) or not 0 <= irregularity < 0.25:
        raise ValueError("grid_fixture_irregularity")
    nodes = []
    for j in range(segments + 1):
        for i in range(segments + 1):
            shift = (
                irregularity * (-1 if (i + j) % 2 else 1) / segments
                if 0 < i < segments and 0 < j < segments
                else 0.0
            )
            nodes.append((i / segments + shift, j / segments - shift))
    cells = []
    for j in range(segments):
        for i in range(segments):
            a = j * (segments + 1) + i
            b, c, d = a + 1, a + segments + 1, a + segments + 2
            cells.extend(((a, b, d), (a, d, c)))
    return Mesh(tuple(nodes), tuple(cells))


def deform(mesh: Mesh, *, stretch: float, shear: float) -> Mesh:
    """Affine stretch/shear; effect size is measured, not called radical here."""
    if not _number(stretch) or not _number(shear):
        raise ValueError("finite_deformation")
    return Mesh(tuple((stretch * x + shear * y, y) for x, y in mesh.nodes), mesh.cells)


def corrupt(mesh: Mesh, kind: str) -> Mesh:
    """First bounded invalid-connectivity/element specimens, not a general CAD grammar."""
    cells = list(mesh.cells)
    a, b, c = cells[0]
    if kind == "degenerate":
        cells[0] = (a, a, c)
    elif kind == "inverted":
        cells[0] = (a, c, b)
    elif kind == "invalid_index":
        cells[0] = (a, b, len(mesh.nodes))
    else:
        raise ValueError("mesh_corruption_unknown")
    return Mesh(mesh.nodes, tuple(cells))


def measurements(mesh: Mesh, baseline: Mesh):
    """Geometry and discretization are separate: remeshing has no point correspondence."""
    areas, invalid = [], 0
    for cell in mesh.cells:
        if any(i < 0 or i >= len(mesh.nodes) for i in cell):
            invalid += 1
            continue
        a, b, c = (mesh.nodes[i] for i in cell)
        area = ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
        if not math.isfinite(area):
            raise ValueError("mesh_measurement_overflow")
        areas.append(area)
    xs, ys = zip(*baseline.nodes)
    scale = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("baseline_length_unresolved")
    corresponding = mesh.cells == baseline.cells and len(mesh.nodes) == len(
        baseline.nodes
    )
    displacement = (
        max(math.dist(a, b) for a, b in zip(mesh.nodes, baseline.nodes)) / scale
        if corresponding
        else None
    )
    if displacement is not None and not math.isfinite(displacement):
        raise ValueError("deformation_measurement_overflow")
    return {
        "normalized_max_displacement": displacement,
        "node_count": len(mesh.nodes),
        "cell_count": len(mesh.cells),
        "node_ratio": len(mesh.nodes) / len(baseline.nodes),
        "minimum_signed_area": min(areas) if areas else None,
        "degenerate_elements": sum(a == 0 for a in areas),
        "inverted_elements": sum(a < 0 for a in areas),
        "invalid_connectivity": invalid,
    }


@dataclass(frozen=True)
class Policy:
    """Host-authored public DEVELOPMENT policy. None is HUMAN_INPUT, not a default."""

    challenge: str
    policy_ref: str
    bounds: tuple[float, float, float, float] | None
    supported_nodes: int | None
    radical_displacement: float | None
    tolerance: float | None
    output_unit: str

    def __post_init__(self):
        if not all(
            type(s) is str and s.strip()
            for s in (self.challenge, self.policy_ref, self.output_unit)
        ):
            raise ValueError("policy_identity_and_unit")
        if self.bounds is not None and (
            type(self.bounds) is not tuple
            or len(self.bounds) != 4
            or not all(map(_number, self.bounds))
            or self.bounds[0] >= self.bounds[1]
            or self.bounds[2] >= self.bounds[3]
        ):
            raise ValueError("envelope_bounds")
        if self.supported_nodes is not None and (
            type(self.supported_nodes) is not int
            or not 3 <= self.supported_nodes <= MAX_NODES
        ):
            raise ValueError("supported_node_bound")
        for name in ("radical_displacement", "tolerance"):
            value = getattr(self, name)
            if value is not None and (not _number(value) or value < 0):
                raise ValueError("policy_nonnegative_finite")


@dataclass(frozen=True)
class Boundary:
    """Trusted host adapter only. Content pins are assertions, not attestation."""

    challenge: str
    artifact_digest: str
    runtime_digest: str
    capabilities: frozenset[str] | None
    predict: Callable
    basis: str = "HOST_DECLARED_PUBLIC"

    def __post_init__(self):
        if (
            not _pin(self.artifact_digest)
            or not _pin(self.runtime_digest)
            or not callable(self.predict)
        ):
            raise ValueError("boundary_identity")
        if self.capabilities is not None and (
            type(self.capabilities) is not frozenset
            or not self.capabilities <= set(FAMILIES)
        ):
            raise ValueError("boundary_capabilities")
        if self.basis not in {"SYNTHETIC_FIXTURE", "HOST_DECLARED_PUBLIC"}:
            raise ValueError("public_development_basis_only")


@dataclass(frozen=True)
class Witness:
    """Matched nodal scalar reference values; verified reference scope is host-owned."""

    mesh_digest: str
    reference_digest: str
    values: tuple[float, ...]
    unit: str

    def __post_init__(self):
        if (
            not _pin(self.mesh_digest)
            or not _pin(self.reference_digest)
            or type(self.values) is not tuple
            or not 1 <= len(self.values) <= MAX_NODES
            or not all(map(_number, self.values))
            or type(self.unit) is not str
            or not self.unit
        ):
            raise ValueError("witness_shape")


def _scope(mesh, metrics, policy):
    if (
        metrics["invalid_connectivity"]
        or metrics["degenerate_elements"]
        or metrics["inverted_elements"]
    ):
        return "INVALID_MESH"
    if len(mesh.nodes) > policy.supported_nodes:
        return "OUTSIDE_RESOURCE_SUPPORT"
    lo_x, hi_x, lo_y, hi_y = policy.bounds
    if any(not (lo_x <= x <= hi_x and lo_y <= y <= hi_y) for x, y in mesh.nodes):
        return "OUTSIDE_ENVELOPE"
    return "SUPPORTED"


def _response(boundary, mesh, *, expected, tolerance):
    """Judge actual predictor response, never a caller-provided pass boolean."""
    try:
        result = boundary.predict(mesh.payload())
    except engine.InfrastructureFailure:
        return {"verdict": engine.FAILED_INFRA, "reason": "endpoint_infrastructure"}
    except (TimeoutError, subprocess.TimeoutExpired):
        return {"verdict": engine.TIMEOUT, "reason": "endpoint_timeout"}
    except Exception:  # noqa: BLE001 - no exception content/secret echo, never a pass
        return {"verdict": engine.CRASHED, "reason": "endpoint_crashed"}
    if type(result) is not dict or set(result) != {"status", "values", "reason"}:
        return {"verdict": engine.BREACHED, "reason": "response_contract"}
    status, values, reason = result["status"], result["values"], result["reason"]
    if type(status) is not str or status not in {"PREDICT", "REFUSE", "ABSTAIN"}:
        return {"verdict": engine.BREACHED, "reason": "response_contract"}
    if type(values) is not list or type(reason) is not str:
        return {"verdict": engine.BREACHED, "reason": "response_contract"}
    if status != "PREDICT":
        valid_refusal = not values and bool(reason.strip())
        held = expected is None and valid_refusal
        return {
            "verdict": engine.HELD if held else engine.BREACHED,
            "reason": "honest_refusal" if held else "wrongful_or_malformed_refusal",
        }
    if expected is None:
        return {
            "verdict": engine.BREACHED,
            "reason": "prediction_outside_supported_scope",
        }
    if len(values) != len(expected) or not all(map(_number, values)):
        return {"verdict": engine.BREACHED, "reason": "prediction_shape_or_nonfinite"}
    error = max(abs(a - b) for a, b in zip(values, expected))
    if not math.isfinite(error):
        return {"verdict": engine.BREACHED, "reason": "prediction_error_overflow"}
    return {
        "verdict": engine.HELD if error <= tolerance else engine.BREACHED,
        "reason": "matched_witness" if error <= tolerance else "witness_error",
        "max_absolute_error": error,
        "prediction_digest": engine.digest(result),
    }


def probe(
    family: str,
    policy: Policy,
    boundary: Boundary,
    *,
    baseline: Mesh,
    attack: Mesh,
    negative: Boundary,
    control_witness: Witness | None,
    attack_witness: Witness | None = None,
):
    """One hostile input, same-path vulnerable specimen, and valid input control.

    HELD requires both discriminating controls. No family/campaign qualification.
    Raw geometry is not automatically exported; return pins and aggregate metrics.
    """
    if (
        family not in FAMILIES
        or type(policy) is not Policy
        or type(boundary) is not Boundary
    ):
        raise ValueError("probe_contract")
    if (
        type(negative) is not Boundary
        or boundary.challenge != policy.challenge
        or negative.challenge != policy.challenge
    ):
        raise ValueError("probe_challenge_mismatch")
    if type(baseline) is not Mesh or type(attack) is not Mesh:
        raise ValueError("probe_mesh_transport_required")
    # Compute pins before ANY callbacks. The transport is separately copied on every call.
    report = {
        "schema": SCHEMA,
        "challenge": policy.challenge,
        "family": family,
        "policy_digest": engine.digest(asdict(policy)),
        "artifact_digest": boundary.artifact_digest,
        "runtime_digest": boundary.runtime_digest,
        "negative_artifact_digest": negative.artifact_digest,
        "negative_runtime_digest": negative.runtime_digest,
        "baseline_digest": baseline.identity,
        "attack_digest": attack.identity,
        "evidence_basis": boundary.basis,
        "provenance": "HOST_ASSERTIONS_NOT_AUTHENTICATED",
        "official_eligible": False,
        "qualification": False,
        "calls": 0,
        "covered_attempts": 0,
        "control": None,
        "specimen": None,
        "attempt": None,
    }

    def finish(verdict, reason):
        report.update(verdict=verdict, reason=reason)
        report["record_digest"] = engine.digest(report)
        return report

    if boundary.capabilities is None:
        return finish("NOT_RUN", "input_capability_unknown")
    if family not in boundary.capabilities:
        return finish("NOT_APPLICABLE", "declared_no_input_capability")
    if negative.capabilities is None or family not in negative.capabilities:
        return finish("NOT_RUN", "negative_control_capability_missing")
    if boundary.artifact_digest == negative.artifact_digest:
        return finish("NOT_RUN", "distinct_negative_control_required")
    if boundary.basis != negative.basis:
        return finish("NOT_RUN", "control_evidence_basis_mismatch")
    if (
        policy.bounds is None
        or policy.supported_nodes is None
        or policy.tolerance is None
    ):
        return finish("NOT_RUN", "HUMAN_INPUT_envelope_or_reference_tolerance")
    try:
        metrics = measurements(attack, baseline)
        control_metrics = measurements(baseline, baseline)
    except ValueError:
        return finish("NOT_RUN", "measurement_unresolved")
    report["measurements"] = metrics
    if _scope(baseline, control_metrics, policy) != "SUPPORTED":
        return finish("NOT_RUN", "supported_control_required")
    if family == "geometric_deformation":
        if policy.radical_displacement is None:
            return finish("NOT_RUN", "HUMAN_INPUT_radical_displacement")
        size = metrics["normalized_max_displacement"]
        if size is None or size < policy.radical_displacement or size == 0:
            return finish("NOT_RUN", "radical_effect_not_demonstrated")
    scope = _scope(attack, metrics, policy)
    report["scope"] = scope
    required = ((baseline, control_witness),)
    if scope == "SUPPORTED":
        required += ((attack, attack_witness),)
    for mesh, witness in required:
        if witness is None:
            return finish("NOT_RUN", "matched_public_reference_missing")
        if (
            type(witness) is not Witness
            or witness.mesh_digest != mesh.identity
            or len(witness.values) != len(mesh.nodes)
            or witness.unit != policy.output_unit
        ):
            return finish("NOT_RUN", "reference_identity_shape_or_units_mismatch")
    report["control_witness_digest"] = engine.digest(asdict(control_witness))
    report["attack_witness_digest"] = (
        engine.digest(asdict(attack_witness)) if scope == "SUPPORTED" else None
    )
    expected = attack_witness.values if scope == "SUPPORTED" else None
    # Controls and attacks always run, so a failed control cannot suppress a breach.
    report["control"] = _response(
        boundary, baseline, expected=control_witness.values, tolerance=policy.tolerance
    )
    report["specimen"] = _response(
        negative, attack, expected=expected, tolerance=policy.tolerance
    )
    report["attempt"] = _response(
        boundary, attack, expected=expected, tolerance=policy.tolerance
    )
    report["calls"] = 3
    attempt = report["attempt"]["verdict"]
    if attempt in engine.NO_ANSWER:
        return finish(attempt, "model_endpoint_incomplete")
    report["covered_attempts"] = 1
    if attempt == engine.BREACHED:
        return finish(engine.BREACHED, "model_boundary_breached")
    if report["control"]["verdict"] == engine.BREACHED:
        return finish(engine.BREACHED, "supported_control_breached")
    if report["control"]["verdict"] != engine.HELD:
        return finish("INCONCLUSIVE", "supported_control_failed")
    if report["specimen"]["verdict"] != engine.BREACHED:
        return finish("INCONCLUSIVE", "negative_control_did_not_fire")
    return finish(engine.HELD, "discriminating_controls_and_attempt_observed")
