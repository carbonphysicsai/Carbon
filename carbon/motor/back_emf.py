"""Motor 1.8: the line-linkage derivative k_e,ll and its graded SHAPE error (Validator, exam science, 6 Nov 05:23 / 05:25).

The model outputs the per-angle phase flux linkages lambda_a, lambda_b, lambda_c (Wb, the 60 recorded rotor steps of one
15 degree mechanical window). The grader derives, never the model:

    k_e,ll(theta) = d(lambda_a - lambda_b) / d theta_mech        [V s / rad]

so the line voltage is e = omega x k_e,ll and no speed is needed. Sign convention (stated once, here and in the kit
text): lambda_a minus lambda_b, differentiated with respect to INCREASING mechanical rotor angle, no minus sign.

- Derivative: central differences on the 0.25 degree grid, one-sided second order at both ends, NO wrap (the window
  is not a full period).
- Graded trait (3)(A): SHAPE only. Each waveform is divided by its OWN RMS over the window, and the error is the RMS
  of the difference. Amplitude is removed (Kt = Ke would otherwise be a torque copy) and a scale cannot game it.
- Two cells, the same derivation and trait: ``back_emf_open_circuit`` (J = 0: the magnet linkage, the physical
  back-EMF) and ``ke_ll_loaded`` (at the load point: armature reaction and saturation included; never called
  back-EMF).
- Pair ab is graded; bc and ca are derived and RECORDED in custody as a consistency check (a balanced winding gives
  equal shapes; a large difference flags the reference, not the model).
- No cell scores before its own U of record, measured ON k_e,ll itself, is registered (`require_u`).
- Six-segment THD is REPORT-ONLY and is not computed here (it would bake a winding-symmetry assumption into a grader).

Never a public path: flux linkage is custody-only (the kit, TRAIN and practice never compute or return it).
"""

from __future__ import annotations

import math

from .domain import ANGLE_STEPS, PERIOD_DEG

#: The two graded cells (Validator 6 Nov 05:23 / 05:25).
CELLS = ("back_emf_open_circuit", "ke_ll_loaded")
#: The recorded rotor step, in mechanical radians (0.25 degree).
STEP_RAD = math.radians(PERIOD_DEG / ANGLE_STEPS)
#: The phase pairs: ab graded, bc and ca custody consistency only.
GRADED_PAIR = ("a", "b")
CHECK_PAIRS = (("b", "c"), ("c", "a"))
PHASES = ("a", "b", "c")


class BackEmfUnavailable(ValueError):
    """A waveform that cannot be graded; ``code`` names why (no values are carried)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _waveform(values, code):
    if type(values) not in (list, tuple) or len(values) != ANGLE_STEPS:
        raise BackEmfUnavailable(code)
    out = []
    for value in values:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise BackEmfUnavailable(code)
        out.append(float(value))
    return out


def linkages(phase_flux_linkage, code="flux_linkage_invalid"):
    """``{"a", "b", "c"}`` -> three 60-step finite waveforms, or a typed refusal."""
    if type(phase_flux_linkage) is not dict or set(phase_flux_linkage) != set(PHASES):
        raise BackEmfUnavailable(code)
    return {phase: _waveform(phase_flux_linkage[phase], code) for phase in PHASES}


def derivative(values, step=STEP_RAD):
    """d values / d theta on a uniform grid: central differences inside, one-sided second order at both ends, no
    wrap."""
    y = _waveform(values, "derivative_input_invalid")
    n = len(y)
    out = [0.0] * n
    out[0] = (-3.0 * y[0] + 4.0 * y[1] - y[2]) / (2.0 * step)
    out[-1] = (3.0 * y[-1] - 4.0 * y[-2] + y[-3]) / (2.0 * step)
    for k in range(1, n - 1):
        out[k] = (y[k + 1] - y[k - 1]) / (2.0 * step)
    return out


def ke_line(lam, pair=GRADED_PAIR):
    """k_e of the line ``pair`` (V s/rad): d(lambda_p - lambda_q)/d theta_mech."""
    first, second = pair
    return derivative([p - q for p, q in zip(lam[first], lam[second], strict=True)])


def _rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values))


def shape_error(predicted, reference):
    """The RMS difference of the two waveforms, each over its OWN RMS. A reference with no shape (zero RMS) is a
    REFERENCE fault; a prediction with none is a prediction that has no shape to compare (both typed).
    """
    pred = _waveform(predicted, "prediction_waveform_invalid")
    true = _waveform(reference, "reference_waveform_invalid")
    pred_rms, true_rms = _rms(pred), _rms(true)
    if not true_rms > 0:
        raise BackEmfUnavailable("reference_waveform_has_no_shape")
    if not pred_rms > 0:
        raise BackEmfUnavailable("prediction_waveform_has_no_shape")
    return _rms([p / pred_rms - t / true_rms for p, t in zip(pred, true, strict=True)])


def grade(predicted_linkage, reference_linkage):
    """The graded ab shape error between a predicted and a reference set of phase linkages."""
    pred = linkages(predicted_linkage, "prediction_flux_linkage_invalid")
    true = linkages(reference_linkage, "reference_flux_linkage_invalid")
    return shape_error(ke_line(pred), ke_line(true))


def consistency(reference_linkage):
    """CUSTODY-only record of a reference's balance: the shape error of bc and of ca against ab (never graded)."""
    lam = linkages(reference_linkage, "reference_flux_linkage_invalid")
    ab = ke_line(lam)
    return {"".join(pair): shape_error(ke_line(lam, pair), ab) for pair in CHECK_PAIRS}


def feasibility_pk_pk(outputs, *, min_torque_nm, max_ripple_pk_pk_nm):
    """Motor 1.8 (mc-exam 6 Nov): the ABSOLUTE peak-to-peak ripple (N.m) over the same 60 angles in place of the ripple
    fraction, which is ill-conditioned near zero mean torque. Whether a machine makes at least `min_torque_nm` on
    average with a pk-pk ripple of at most `max_ripple_pk_pk_nm`; a None limit is not given, so nothing is feasible
    against it. A decision property, never a gate. (Here, not in `exam.py`: that file is pinned by the counted Motor
    decision study, `customer_decision.CODE_PATHS`.)"""
    curve = list(outputs["torque_nm"])
    mean = sum(curve) / len(curve)
    ripple = max(curve) - min(curve)
    limits = (min_torque_nm, max_ripple_pk_pk_nm)
    return {
        "mean_nm": mean,
        "ripple_pk_pk_nm": ripple,
        "feasible": None not in limits
        and mean >= min_torque_nm
        and ripple <= max_ripple_pk_pk_nm,
    }


def require_u(registered_u, cell):
    """The cell's registered U of record (measured on k_e,ll itself), or a refusal: no cell scores before it."""
    if cell not in CELLS:
        raise BackEmfUnavailable("back_emf_cell_unregistered")
    value = (
        (registered_u or {}).get(cell)
        if type(registered_u) in (dict, type(None))
        else None
    )
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise BackEmfUnavailable("back_emf_u_not_registered_" + cell)
    return float(value)
