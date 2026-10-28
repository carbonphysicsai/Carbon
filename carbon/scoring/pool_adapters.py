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
            "mean_torque_nm": quantities["mean_nm"],
            "ripple_fraction": quantities["ripple_fraction"],
        }

    return PoolAdapter(
        kind="motor",
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("mean_torque_nm", "ripple_fraction"),
        objective="ripple_fraction",
        sense="min",
        limits=(
            ("mean_torque_nm", ">=", float(constraints["min_mean_torque_nm"])),
            ("ripple_fraction", "<=", float(constraints["max_ripple_fraction"])),
        ),
        derive=derive,
        registered_u={},
    )


# -- Cooling --------------------------------------------------------------------------------------


def _cooling_encoded(version):
    """Whether the Cooling version answers in the law-safe encoded 32-value space: the version registry's
    `output_encoding`, never a list of versions here."""
    from carbon.challenge_kit import version_registry

    return (
        version_registry.entry("chip-cold-plate", version).output_encoding is not None
    )


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
    encoded = _cooling_encoded(version)

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


def f08_mass_kg(design):
    """F08's exact synthetic CAD mass: `OPTIMIZER_F08_SUMMARY_DUAL_PACKET_20261018.mass` (two full ribs, a
    rounded rectangular relief; aluminium 2.7e-6 kg/mm^3). `design` is in `f08_public` input order. It
    reproduces the recorded `cad_mass_kg` of all 8 RR-07 ladder cases to 1e-9 relative (a test pins that),
    so the mass output is exact (u = 0, the Validator's ruling)."""
    length, width, thick, height, rib, relief = design
    volume = length * width * thick + 2 * length * height * rib
    volume -= (20 * relief - (4 - math.pi) * 3**2) * thick
    return volume * 2.7e-6


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
        mass_of = f08_mass_kg

    def derive(inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != len(targets):
            return None
        design = [inputs[name] for name in names]
        return {
            "static_tip_mm_per_n": row[static],
            "worst_dynamic_mm_per_n": max(row[j] for j in tips),
            "cad_mass_kg": float(mass_of(design)),
        }

    return PoolAdapter(
        kind="f08",
        version=version,
        input_names=tuple(names),
        design_names=tuple(names),
        condition_names=(),
        outputs=("static_tip_mm_per_n", "worst_dynamic_mm_per_n", "cad_mass_kg"),
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
            ("cad_mass_kg", "<=", float(constraints["mass_kg_max"])),
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


# -- The physics-contract gates, per pool answer ----------------------------------------------------------


@dataclass(frozen=True)
class PhysicsGates:
    """The Challenge's registered per-answer physics gates, for the grader to run on EVERY pool answer
    (OWNER-GATES-ON-POOL-3A-01). ``failed(inputs_row, raw_row)`` returns the sorted NAMES of the gates the answer
    fails (an empty tuple passes; a malformed or non-finite row fails its schema gate). Names only, never a value
    or a target. Each gate is one the Challenge already registers with its own tolerance (its `exam.gates`, F02's
    and F08's gated laws); a law whose gate margin is still None is measured elsewhere and is not a gate here.
    """

    kind: str
    version: str
    gate_names: tuple
    failed: object


def _motor_gates(version):
    from carbon.motor import exam

    names = tuple(g.gate_id for g in exam.GATES if g.gate_id != "paired_repeat")

    def failed(_inputs, raw):
        verdicts = exam.gates({"torque_nm": raw})
        return tuple(sorted(n for n, v in verdicts.items() if v == exam.FAIL))

    return PhysicsGates("motor", version, names, failed)


def _cooling_gates(version):
    from carbon.cold_plate import exam, output_encoding

    names = tuple(g.gate_id for g in exam.GATES if g.gate_id != "paired_repeat")
    encoded = _cooling_encoded(version)

    def failed(inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != 32:
            return ("schema_finite",)
        native = output_encoding.decode_flat(row) if encoded else row
        prediction = {
            "peak_c": native[0],
            "profile_c": list(native[1:31]),
            "pressure_drop_pa": native[31],
        }
        verdicts = exam.gates(prediction, dict(inputs))
        return tuple(sorted(n for n, v in verdicts.items() if v == exam.FAIL))

    return PhysicsGates("cooling", version, names, failed)


def _f02_gates(version):
    from carbon.scoring import f02_physics

    names = ("finite_peak", "peak_not_below_initial")

    def failed(_inputs, raw):
        row = _finite_row(raw)
        if row is None or len(row) != 1:
            return ("finite_peak",)
        return () if row[0] >= f02_physics.INITIAL_C else ("peak_not_below_initial",)

    return PhysicsGates("f02", version, names, failed)


def _f08_gates(version):
    from carbon.scoring import f08_dual_measurement, f08_dual_pack, f08_physics

    targets = list(f08_dual_pack._targets(version))
    rule = f08_dual_measurement.SANITY_RULE if version == "1.7" else None
    names = (
        "finite_native_summary",
        *sorted(("peak_not_below_static", "peaks_ordered_by_damping")),
    )

    def failed(_inputs, raw):
        row = _finite_row(raw)
        if row is None or not f08_dual_measurement.native_summary(
            row,
            targets=targets,
            frequency_targets=f08_dual_pack._FREQUENCIES,
            frequency_band_hz=f08_dual_pack._MEASUREMENT["frequency_band_hz"],
            rule=rule,
        ):
            return ("finite_native_summary",)
        laws = f08_physics._logical(dict(zip(targets, row, strict=True)))
        return tuple(sorted(n for n, ok in laws.items() if not ok))

    return PhysicsGates("f08", version, names, failed)


def physics_gates(kind, version):
    """The `PhysicsGates` of one Challenge version (static dispatch, as `adapter`)."""
    if kind == "motor":
        return _motor_gates(version)
    if kind == "cooling":
        return _cooling_gates(version)
    if kind == "f02":
        return _f02_gates(version)
    if kind == "f08":
        return _f08_gates(version)
    raise PoolAdapterRefused("pool_adapter_kind_unregistered")


# -- The binding the pool plugin takes ---------------------------------------------------------------

#: Which derived output's U applies to each raw output element (the rest get 0: a noisy oracle must not
#: push an element that feeds no decision quantity out of its native range). A proposal for the Validator,
#: not a registered rule: the U VALUES are the DECISION record's (`pool_plan.py targets`), never defaults.
_RAW_U_NEEDS = {
    "motor": ("mean_torque_nm",),
    "cooling": ("die_peak_c", "hydraulic_w"),
    "f02": ("peak_top_c",),
    "f08": ("static_tip_mm_per_n", "worst_dynamic_mm_per_n"),
}


def _raw_u_of(kind, version, u):
    missing = [name for name in _RAW_U_NEEDS[kind] if name not in u]
    if missing:
        raise PoolAdapterRefused("u_missing:" + ",".join(missing))
    if kind == "f08":
        from carbon.scoring import f08_dual_pack

        targets = list(f08_dual_pack._targets(version))
        by_element = [
            (
                u["static_tip_mm_per_n"]
                if name == "static_tip_mm_per_n"
                else u["worst_dynamic_mm_per_n"] if name in f08_dual_pack._TIPS else 0.0
            )
            for name in targets
        ]
    elif kind == "f02":
        by_element = [u["peak_top_c"]]
    elif kind == "motor":
        by_element = (
            None  # every one of the 60 torque elements carries the mean-torque U
        )
    else:
        # Elements 1-31 (the peak and the 30 profile values) carry the die peak's absolute U. Element 32 is the
        # pressure drop: hydraulic power is dp x Q with Q fixed by the inputs, so the decision's RELATIVE U on
        # hydraulic_w carries over unchanged: r x |that row's own dp|, never an absolute number (Validator).
        relative = u["hydraulic_w"]
        if (
            type(relative) is not dict
            or set(relative) != {"relative"}
            or type(relative["relative"]) not in (int, float)
            or not 0 < relative["relative"] < 1
        ):
            raise PoolAdapterRefused("hydraulic_w_u_must_be_relative")
        by_element = None
        share = float(relative["relative"])
        encoded = _cooling_encoded(version)

        def cooling_raw_u(_inputs, reference_row):
            if len(reference_row) != 32:
                raise PoolAdapterRefused("raw_row_width_is_not_the_interface_width")
            die, profile = float(u["die_peak_c"]), [float(u["die_peak_c"])] * 30
            first, last = float(reference_row[0]), float(reference_row[31])
            if not encoded:
                # Cooling 1.3: the row is native (peak, 30 profile values, dp).
                return [die, *profile, share * abs(last)]
            # Cooling 1.4: the row is the encoded one. The peak is the profile maximum plus softplus(e) and the
            # pressure drop is softplus(q). The step that moves the DECODED quantity by U at this row's own
            # reference is exact, not the first-order U / sigmoid (which overshoots where softplus is curved,
            # i.e. a peak close to the profile maximum): U_e = softplus^-1(softplus(e) + U_die) - e and
            # U_q = softplus^-1((1 + r) softplus(q)) - q. They equal U / sigmoid where the encoding is locally
            # linear; a step down moves the decoded value by no more than U (softplus is convex).
            from carbon.cold_plate import output_encoding

            def step(x, increase):
                y = float(output_encoding._softplus(x))
                return float(output_encoding._inverse_softplus([y + increase])[0]) - x

            return [
                step(first, die),
                *profile,
                step(last, share * float(output_encoding._softplus(last))),
            ]

        return cooling_raw_u

    def raw_u(_inputs, reference_row):
        if by_element is None:
            return [float(u["mean_torque_nm"])] * len(reference_row)
        if len(by_element) != len(reference_row):
            raise PoolAdapterRefused("raw_row_width_is_not_the_interface_width")
        return list(by_element)

    return raw_u


def _train_arrays(kind, version):
    import io

    from carbon.challenge_kit import physical_pack
    from carbon.scoring import practice_grid

    chosen = practice_grid.adapter(kind, version)
    public = physical_pack.public_roles(chosen.CHALLENGE, version)
    native = getattr(chosen, "_native_train", None)
    raw = native() if native is not None else public["train"]
    import numpy as np

    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        inputs = np.asarray(data["inputs"], dtype=float)
        targets = np.asarray(data["targets"], dtype=float)
    return native is not None, inputs, targets


def train_mean_row(kind, version):
    """The TRAIN-mean raw output row in the space the grader measures (the default model's answer): the
    floor `ctrl.train_mean` of `calibration_grade`, as `practice_v2_curves.train_mean_row` computes it.
    """
    encoded, _inputs, targets = _train_arrays(kind, version)
    mean = targets.mean(axis=0)
    if encoded:
        from carbon.cold_plate import output_encoding

        mean = output_encoding.encode_targets(mean[None, :])[0]
    return [float(v) for v in mean]


def train_box(kind, version, design_names, input_names):
    """The TRAIN box over the design variables, ((lo, hi), ...) in design units."""
    _encoded, inputs, _targets = _train_arrays(kind, version)
    if inputs.shape[1] != len(input_names):
        raise PoolAdapterRefused("train_inputs_do_not_match_the_interface")
    column = {name: i for i, name in enumerate(input_names)}
    return tuple(
        (float(inputs[:, column[n]].min()), float(inputs[:, column[n]].max()))
        for n in design_names
    )


def train_spread(kind, version, chosen):
    """{derived output: population standard deviation over the TRAIN rows}, the derived outputs of
    `chosen.derive` in the grader's model space (Cooling 1.4's rows encoded as `train_mean_row` does). A row
    `derive` refuses (None) is skipped; an output with no spread at all is refused, not silently scaled by 0.
    """
    import numpy as np

    encoded, inputs, targets = _train_arrays(kind, version)
    if encoded:
        from carbon.cold_plate import output_encoding

        targets = output_encoding.encode_targets(targets)
    rows = []
    for row, raw in zip(inputs, targets, strict=True):
        derived = chosen.derive_row([float(v) for v in row], [float(v) for v in raw])
        if derived is not None:
            rows.append(derived)
    if not rows:
        raise PoolAdapterRefused("no_train_row_derives")
    spread = {name: float(np.std([r[name] for r in rows])) for name in chosen.outputs}
    if not all(v > 0.0 for v in spread.values()):
        raise PoolAdapterRefused("a_derived_output_has_no_train_spread")
    return spread


def _to_model_space(kind, version):
    """Cooling 1.4's model answers in the encoded 32-value space; the bank's references and a solver's truths
    are native, so they are encoded before they stand in for a model's answer. Every other row is already
    in the model's space."""
    if kind != "cooling" or not _cooling_encoded(version):
        return None

    def convert(reference_row):
        import numpy as np

        from carbon.cold_plate import output_encoding

        return [
            float(v)
            for v in output_encoding.encode_targets(
                np.asarray([reference_row], dtype=float)
            )[0]
        ]

    return convert


def binding(
    kind,
    version,
    *,
    u,
    serve_good,
    serve_train,
    serve_default,
    mass_of=None,
    probe_truth=None,
):
    """The `pool_plugin.ChallengeBinding` of one Challenge version.

    `u` is the DECISION record's U per derived output (the pools' own); `serve_good` and `serve_train`
    are the real models' raw-output servers (`rows -> raw output rows`), which run on the build host.
    Nothing here has a default for any of them."""
    from carbon.scoring import pool_plugin

    chosen = adapter(kind, version, mass_of=mass_of)
    box = train_box(kind, version, chosen.design_names, chosen.input_names)
    mean_row = train_mean_row(kind, version)
    return pool_plugin.ChallengeBinding(
        kind=kind,
        version=version,
        input_names=chosen.input_names,
        design_names=chosen.design_names,
        derive=chosen.derive,
        raw_u=_raw_u_of(kind, version, dict(u)),
        train_mean_row=lambda: list(mean_row),
        serve_good=serve_good,
        serve_train=serve_train,
        serve_default=serve_default,
        train_box=lambda _spec: box,
        probe_truth=probe_truth,
        to_model_space=_to_model_space(kind, version),
        train_spread=lambda: train_spread(kind, version, chosen),
        physics_gates=physics_gates(kind, version),
    )


def official_binding(kind, version):
    """The binding of the OFFICIAL grade of one submitted model (`pool_exam`): the Challenge's derive, its physics
    gates and its design order, and nothing from the proof suite. The proof suite's controls (the TRAIN fit, the
    default, the floor, the truth models' U) are not part of the official grade, so each refuses if asked.
    """
    from carbon.scoring import pool_plugin

    chosen = adapter(kind, version)

    def not_official(*_args, **_kwargs):
        raise PoolAdapterRefused("proof_suite_input_is_not_part_of_the_official_grade")

    return pool_plugin.ChallengeBinding(
        kind=kind,
        version=version,
        input_names=chosen.input_names,
        design_names=chosen.design_names,
        derive=chosen.derive,
        raw_u=not_official,
        train_mean_row=not_official,
        serve_good=not_official,
        serve_train=not_official,
        serve_default=not_official,
        train_box=not_official,
        to_model_space=_to_model_space(kind, version),
        physics_gates=physics_gates(kind, version),
    )


CONFIG_ENV = "CARBON_POOL_BINDING_CONFIG"


def binding_for(kind, version):
    """The binding `scripts/dev/pool_proof_grid.py --binding carbon.scoring.pool_adapters:binding_for` takes.

    Everything the grid run needs from outside the repository comes from one JSON file named by the
    environment variable `CARBON_POOL_BINDING_CONFIG`; there is no default for any of it:
      {"decision": path to the DECISION record (its "u" per derived output is the pools' own),
       "good_table": path to the good model's prediction table (`pool_serving.write_table`),
       "train_table": path to the TRAIN-fit model's prediction table (it is never inferred from the good table,
                      so the in-distribution control cannot silently grade the wrong model),
       "train_live": true, instead of "train_table": serve the TRAIN-fit model live (`pool_baseline.fit`, cheap),
                      so the in-distribution control's clamped rows need no table that holds them (V8_RULINGS 14)}
    The solver truths of the probe rows come in through the script's own `--probe-truth-file`.
    """
    import os

    from carbon.scoring import pool_serving

    path = os.environ.get(CONFIG_ENV)
    if not path:
        raise PoolAdapterRefused("pool_binding_config_missing")
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if type(config) is not dict or set(config) - {
        "decision",
        "good_table",
        "train_table",
        "train_live",
        "default_table",
    }:
        raise PoolAdapterRefused("pool_binding_config_malformed")
    live = config.get("train_live")
    if live is not None and (live is not True or "train_table" in config):
        raise PoolAdapterRefused("pool_binding_config_malformed")
    for key in ("decision", "good_table", "train_table", "default_table"):
        if live and key == "train_table":
            continue
        if type(config.get(key)) is not str:
            raise PoolAdapterRefused("pool_binding_config_lacks_" + key)
    with open(config["decision"], encoding="utf-8") as handle:
        decision = json.load(handle)
    if type(decision) is not dict or type(decision.get("u")) is not dict:
        raise PoolAdapterRefused("decision_record_lacks_u")
    names = adapter(kind, version).input_names
    good = pool_serving.TableServer(
        pool_serving.load_table(config["good_table"]), names
    )
    if live:
        from carbon.scoring import pool_baseline

        predict, _choice = pool_baseline.fit(kind, version)
        train = pool_serving.LiveServer(predict, names)
    else:
        train = pool_serving.TableServer(
            pool_serving.load_table(config["train_table"]), names
        )
    default = pool_serving.TableServer(
        pool_serving.load_table(config["default_table"]), names
    )
    return binding(
        kind,
        version,
        u=decision["u"],
        serve_good=good,
        serve_train=train,
        serve_default=default,
    )
