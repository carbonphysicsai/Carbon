"""Physics gates on every pool answer, the truths-pass-gates check, and the speed gate.

OWNER-GATES-ON-POOL-3A-01: each Challenge's physics gates (its physics contract) run on EVERY pool answer, in range
and out of range, queryable rows and the A_gen slice alike. Any violation is GATE_FAILED for the whole submission,
with the gate NAMES only and never a target, a row or a value. The gates themselves are the Challenge's own,
supplied by its adapter (`pool_adapters.physics_gates`: `.failed(inputs_row, raw_row)` -> sorted failed names); this
module only applies them to the model's single table of answers.

OWNER-SPEED-GATE-500X-01: a pass/fail gate, never a score input: time per design must be at most the recorded solver
time per design divided by 500. The factor and each Challenge's solver time are REQUIRED arguments (registered with
their source records by the Challenge, never defaulted or re-measured silently); the closed code is GATE_FAILED
(speed).

Nothing here names a Challenge.
"""

from __future__ import annotations

import math

from carbon.scoring import pool_plugin

GATE_FAILED = "GATE_FAILED"
SPEED_CODE = "GATE_FAILED (speed)"


def pool_rows(binding, specs):
    """Every kept pool row of every target (queryable and A_gen) as bank-style rows {"case_id", "inputs",
    "reference"}: the model's inputs, and the pool's raw truth where `attach_raw` put it (else None).
    """
    rows = []
    for spec in specs:
        for index, design in enumerate(spec.designs):
            rows.append(
                {
                    "case_id": f"{spec.target_id}:{index}",
                    "inputs": pool_plugin.model_input_row(
                        binding, spec.conditions, design
                    ),
                    "reference": None if spec.raw is None else list(spec.raw[index]),
                }
            )
    return rows


def _gates(binding):
    gates = binding.physics_gates
    if gates is None:
        raise pool_plugin.PluginRefused("binding_supplies_no_physics_gates")
    return gates


def failed_gates(binding, rows, raw_rows):
    """The sorted, de-duplicated NAMES of the gates any answer fails (empty = every answer passes)."""
    gates = _gates(binding)
    if len(rows) != len(raw_rows):
        raise pool_plugin.PluginRefused("one_raw_row_per_pool_row")
    names = set()
    for row, raw in zip(rows, raw_rows, strict=True):
        names.update(gates.failed(row["inputs"], list(raw)))
    return sorted(names)


def pool_gate_result(binding, specs, descriptor):
    """The gate outcome of a model descriptor's single table over every pool row: {"status": "PASSED" |
    "GATE_FAILED", "gates": [names]}. Names only. A truth-based descriptor needs the raw truths attached.
    """
    rows = pool_rows(binding, specs)
    if descriptor.get("kind") in pool_plugin.TRUTH_MODELS:
        pool_plugin._require(
            all(s.raw is not None for s in specs),
            "raw_truths_missing_for_a_truth_model",
        )
    raw = pool_plugin.model_outputs(binding, rows, descriptor)
    names = failed_gates(binding, rows, raw)
    return {"status": GATE_FAILED if names else "PASSED", "gates": names}


def check_truths_pass_gates(binding, specs):
    """The proof-suite check (Validator, exam additions): the pool's own raw TRUTHS must pass every gate on every
    row, else a gate is miscalibrated against reality: STOP, back to the Validator. Needs `attach_raw` first.
    """
    if any(s.raw is None for s in specs):
        raise pool_plugin.TruthCheckStop("truths_gate_check_needs_the_raw_truths")
    rows = pool_rows(binding, specs)
    names = failed_gates(binding, rows, [r["reference"] for r in rows])
    if names:
        raise pool_plugin.TruthCheckStop(f"pool_truths_fail_gates: {names}")
    return {"rows": len(rows), "gates": sorted(_gates(binding).gate_names)}


def speed_gate(measured_seconds, rows, *, solver_seconds_per_design, factor):
    """The speed gate. `measured_seconds` is the wall time of the single all-rows inference on the validator machine
    class inside the sandbox (model load included, image pull and container start excluded); `rows` the number of
    rows answered. Passes when seconds per design <= solver_seconds_per_design / factor.
    """
    for name, value in (
        ("measured_seconds", measured_seconds),
        ("solver_seconds_per_design", solver_seconds_per_design),
        ("factor", factor),
    ):
        pool_plugin._require(
            type(value) in (int, float) and math.isfinite(value) and value > 0,
            f"{name}_must_be_positive_and_finite",
        )
    pool_plugin._require(type(rows) is int and rows > 0, "rows_must_be_a_positive_int")
    per_design = measured_seconds / rows
    ceiling = solver_seconds_per_design / factor
    passed = per_design <= ceiling
    return {
        "passed": passed,
        "code": None if passed else SPEED_CODE,
        "seconds_per_design": per_design,
        "ceiling_seconds_per_design": ceiling,
    }


def registered_speed_params(challenge_id):
    """The speed gate's registered numbers for a Challenge, from the ONE source the exam page, the published scoring
    rules tool and this gate all read (`carbon.challenge_registry.speed_gate`: RATIO and the recorded solver seconds
    per design): {"solver_seconds_per_design", "factor"}, ready for `speed_gate` or `make_plugin(speed=...)`.
    """
    from carbon.challenge_registry import speed_gate as registered

    try:
        solver = registered.SOLVER_SECONDS_PER_DESIGN[challenge_id]
    except KeyError:
        raise pool_plugin.PluginRefused("speed_gate_challenge_not_registered") from None
    return {"solver_seconds_per_design": solver, "factor": registered.RATIO}


def registered_speed_gate(challenge_id, measured_seconds, rows):
    """`speed_gate` with the registered ratio and solver time of `challenge_id` (never retyped here)."""
    return speed_gate(measured_seconds, rows, **registered_speed_params(challenge_id))


def total_rows(specs):
    return sum(len(spec.designs) for spec in specs)


__all__ = [
    "GATE_FAILED",
    "SPEED_CODE",
    "check_truths_pass_gates",
    "failed_gates",
    "pool_gate_result",
    "pool_rows",
    "registered_speed_gate",
    "registered_speed_params",
    "speed_gate",
    "total_rows",
]
