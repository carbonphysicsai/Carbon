"""Pool adapters: what each Challenge supplies to the pool grader (Test Engineer, 2026-10-24).

The pool grader (`pool_grader`) works in derived-output space: the objective and limit quantities of a
Challenge's registered decision. A model returns RAW output rows. A `PoolAdapter` is the Challenge's
side of that seam and nothing else: the names of its inputs (model input order), which of them are
design variables (the pool box) and which are fixed per target (conditions), the derived outputs, the
registered objective and limits, and `derive`, which turns one raw output row into the derived outputs
with the registered decision functions the sealed grader already uses. No new science.

Every limit is read from the version's public `important_limit_definition` role and every objective
direction from its public `design_objective` role, so a registered value is never retyped here. A
reference uncertainty U appears only where one is registered (`registered_u`); anywhere else the pool
document carries it (Data Collection's solver record) and this module has none to give.

`derive` returns None for a raw row the Challenge's own validity gates refuse (a malformed or
physically impossible prediction): the pool grader scores that as the candidate's `prediction_invalid`,
never as an infrastructure failure.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

KINDS = ("motor", "cooling", "f02", "f08")


class PoolAdapterRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PoolAdapter:
    kind: str
    version: str
    input_names: tuple  # the model's input row order
    design_names: tuple  # the pool box order (a subset of input_names)
    condition_names: tuple  # the rest: fixed per target
    outputs: tuple  # derived outputs, the keys `derive` returns
    objective: str
    sense: str  # "max" | "min"
    limits: tuple  # (output, "<=" | ">=", bound), as registered
    derive: object  # derive(inputs_row: dict, raw_row) -> {output: value} | None
    registered_u: dict  # output -> U, only where one is registered

    def model_row(self, fixed, design):
        """The model input row (in `input_names` order) for a target's fixed values and one design."""
        values = {**fixed, **dict(zip(self.design_names, design, strict=True))}
        if set(values) != set(self.input_names):
            raise PoolAdapterRefused("pool_inputs_do_not_complete_the_model_row")
        return [float(values[name]) for name in self.input_names]

    def derive_row(self, row, raw):
        """`derive` over one model input row (list in `input_names` order) and its raw output row."""
        return self.derive(dict(zip(self.input_names, row, strict=True)), raw)


def _roles(kind, version):
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import practice_grid

    chosen = practice_grid.adapter(kind, version)
    if chosen is None:
        raise PoolAdapterRefused("version_has_no_sealed_v2_grader")
    public = physical_pack.public_roles(chosen.CHALLENGE, version)
    return (
        chosen,
        json.loads(public["important_limit_definition"]),
        json.loads(public["design_objective"]),
        practice_grid.input_names(kind, version),
    )


def _finite_row(raw):
    try:
        values = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    return values if all(math.isfinite(v) for v in values) else None


# -- Motor ----------------------------------------------------------------------------------------


def _motor(version):
    from carbon.motor import customer_decision as decision

    _chosen, limits, objective, names = _roles("motor", version)
    contract = objective["decision_contract"]
    constraints = limits["constraints"]
    direction = contract["objective"]["direction"]
    if (
        contract["objective"]["quantity"] != "worst_case_torque_ripple_fraction"
        or direction != "MINIMIZE"
    ):
        raise PoolAdapterRefused("motor_objective_is_not_the_registered_one")

    def derive(_inputs, raw):
        curve = _finite_row(raw)
        if curve is None:
            return None
        try:
            quantities = decision.quantities(contract, {"torque_nm": curve})
        except decision.DecisionError:
            return None
        return {
            "mean_nm": quantities["mean_nm"],
            "ripple_fraction": quantities["ripple_fraction"],
        }

    return PoolAdapter(
        kind="motor",
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("mean_nm", "ripple_fraction"),
        objective="ripple_fraction",
        sense="min",
        limits=(
            ("mean_nm", ">=", float(constraints["min_mean_torque_nm"])),
            ("ripple_fraction", "<=", float(constraints["max_ripple_fraction"])),
        ),
        derive=derive,
        registered_u={},
    )


# -- Cooling --------------------------------------------------------------------------------------


def _cooling(version):
    from carbon.cold_plate import customer_decision as decision
    from carbon.cold_plate import output_encoding

    _chosen, limits, objective, names = _roles("cooling", version)
    contract = objective["decision_contract"]
    constraints = limits["constraints"]
    if (
        contract["objective"]["quantity"] != "worst_case_hydraulic_power"
        or contract["objective"]["direction"] != "MINIMIZE"
    ):
        raise PoolAdapterRefused("cooling_objective_is_not_the_registered_one")
    # Cooling 1.4 (graph route v2) returns the encoded 32-value row; 1.3 the native one.
    encoded = version == "1.4"

    def derive(inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != 32:
            return None
        try:
            native = output_encoding.decode_flat(row) if encoded else row
            outputs = {
                "peak_c": native[0],
                "profile_c": list(native[1:31]),
                "pressure_drop_pa": native[31],
            }
            quantities = decision.quantities(contract, dict(inputs), outputs)
        except (decision.DecisionError, ValueError, OverflowError):
            return None
        return {
            "die_peak_c": quantities["die_peak_c"],
            "hydraulic_w": quantities["hydraulic_w"],
        }

    return PoolAdapter(
        kind="cooling",
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("die_peak_c", "hydraulic_w"),
        objective="hydraulic_w",
        sense="min",
        limits=(
            ("die_peak_c", "<=", float(constraints["die_peak_c_max"])),
            ("hydraulic_w", "<=", float(constraints["hydraulic_power_w_max"])),
        ),
        derive=derive,
        registered_u={},
    )


# -- F02 ------------------------------------------------------------------------------------------


def _f02(version):
    _chosen, limits, objective, names = _roles("f02", version)
    if objective["quantity"] != "extra_energy_j" or objective["sense"] != "maximize":
        raise PoolAdapterRefused("f02_objective_is_not_the_registered_one")
    peak_c_max = float(limits["constraints"]["peak_top_c_max"])
    if tuple(names) != ("peak_w", "on_time_s"):
        raise PoolAdapterRefused("f02_inputs_are_not_the_registered_ones")

    def derive(inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != 1:
            return None
        # The analytic extra energy of a schedule: (peak_w - 20) * on_time_s (physics_contract).
        return {
            "peak_top_c": row[0],
            "extra_energy_j": (inputs["peak_w"] - 20.0) * inputs["on_time_s"],
        }

    return PoolAdapter(
        kind="f02",
        version=version,
        input_names=tuple(names),
        design_names=tuple(names),
        condition_names=(),
        outputs=("peak_top_c", "extra_energy_j"),
        objective="extra_energy_j",
        sense="max",
        limits=(("peak_top_c", "<=", peak_c_max),),
        derive=derive,
        registered_u={},
    )


# -- F08 ------------------------------------------------------------------------------------------


def _f08(version, mass_of):
    from carbon.scoring import f08_dual_pack

    _chosen, limits, objective, names = _roles("f08", version)
    if (
        objective["quantity"] != "worst_dynamic_mm_per_n"
        or objective["sense"] != "minimize"
    ):
        raise PoolAdapterRefused("f08_objective_is_not_the_registered_one")
    constraints = limits["constraints"]
    targets = list(f08_dual_pack._targets(version))
    tips = [targets.index(name) for name in f08_dual_pack._TIPS]
    static = targets.index("static_tip_mm_per_n")
    if mass_of is None:
        # The CAD mass is a solver-side number, not a model output and not in this repository: the caller
        # supplies the same source the pool truths use, or no adapter is built.
        raise PoolAdapterRefused("f08_mass_source_required")

    def derive(inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != len(targets):
            return None
        design = [inputs[name] for name in names]
        return {
            "static_tip_mm_per_n": row[static],
            "worst_dynamic_mm_per_n": max(row[j] for j in tips),
            "mass_kg": float(mass_of(design)),
        }

    return PoolAdapter(
        kind="f08",
        version=version,
        input_names=tuple(names),
        design_names=tuple(names),
        condition_names=(),
        outputs=("static_tip_mm_per_n", "worst_dynamic_mm_per_n", "mass_kg"),
        objective="worst_dynamic_mm_per_n",
        sense="min",
        limits=(
            (
                "static_tip_mm_per_n",
                "<=",
                float(constraints["static_tip_mm_per_n_max"]),
            ),
            (
                "worst_dynamic_mm_per_n",
                "<=",
                float(constraints["dynamic_tip_mm_per_n_max"]),
            ),
            ("mass_kg", "<=", float(constraints["mass_kg_max"])),
        ),
        derive=derive,
        registered_u={
            "worst_dynamic_mm_per_n": float(
                limits["exam_straddle"]["reference_uncertainty_mm_per_n"]
            )
        },
    )


def adapter(kind, version, *, mass_of=None):
    """The `PoolAdapter` of one Challenge version. Static dispatch, as `practice_grid`'s (a new Challenge
    adds one branch here and one in `practice_grid`)."""
    if kind == "motor":
        return _motor(version)
    if kind == "cooling":
        return _cooling(version)
    if kind == "f02":
        return _f02(version)
    if kind == "f08":
        return _f08(version, mass_of)
    raise PoolAdapterRefused("pool_adapter_kind_unregistered")


def pool_limits(chosen):
    """The adapter's limits as `pool_grader.Limit` objects."""
    from carbon.scoring import pool_grader

    return tuple(pool_grader.Limit(o, k, b) for o, k, b in chosen.limits)
