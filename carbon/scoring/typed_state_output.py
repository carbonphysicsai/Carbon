"""Typed-state outputs: an output whose true value can be EMPTY by physics, scored in two parts (rule
``bt32-threshold-recovery-two-part.v1``, Burst Thermal 3.2 only).

Basis: the Lead's decision under the owner's delegation (8 Nov 2026, E1 two-part, event weight 1/2) and Carbon
Validator-BT's spec line ``BT32_THRESHOLD_RECOVERY_SPEC_LINE.md`` rev 3 (sha256 8d812755...), sections S1-S7. This module
holds the rule's arithmetic and nothing Challenge-specific beyond the two output KINDS the spec names. Every number
(the threshold, the event weight, the band U, the value U) is the version's registration (`TypedOutput`); none has a
default, and a missing one refuses (HUMAN_INPUT until the U panel is receipted).

S1  States. Truth and prediction each take one state. ``recovery`` (``threshold_recovery_s``): NEVER_REACHED,
    NOT_RECOVERED or a value; ``first_crossing`` (``first_95c_crossing_s``): NOT_REACHED or a value. A prediction is a
    finite number >= 0 or one of its kind's tokens; a token is a valid answer, never a gate failure. A missing key, a
    null, another kind's token or any other value is INVALID (the schema gate, unchanged).
S2  Band. A case whose truth peak is within ``band_u`` of ``threshold_c`` (|peak - threshold| <= band_u) is not
    resolvable: it is neither credited nor charged in the EVENT part.
S3  EVENT. m = resolvable cases whose predicted state differs from the true state. S_event = clip(1 - m / m_anchor, 0, 1),
    admitted only when m_anchor >= 1, the cell's (V) PASS and n >= n_min (rev 3). m_anchor is the panel's count over the class's resolvable cases of the WHOLE exam
    (R of them); a set graded on r of them compares RATES, clip(1 - (m / r) / (m_anchor / R), 0, 1), which is the spec's
    formula exactly when the set is the whole exam (r = R), and gives the event part no evidence (None) when r = 0.
S4  VALUE. T = truth-value cases, minus band cases the model calls empty; B = the cases of T the model gives a value.
    E = geometric mean over B of max(|err| / value_u, 1). S_value = clip(ln(A_c / E) / ln(A_c), 0, 1) x |B| / |T| (the
    LOG skill as the spec writes it, whatever the version's skill form: only the log form makes calling a case empty
    never pay where the model's own error is <= A_c; 0 when B is empty), admitted only when the registered admission
    tests pass and |T| >= 1.
S5  Combination: both admitted w S_event + (1 - w) S_value; one admitted, that part; neither, the cell is not scored.
S6  The panel predicts the same two-part form: a state and a value on every case (`panel_anchor`).
S7  The in-range gate reads |err| / value_u on B only (`gate_ratios`); a state mismatch never enters the gate.

Contributions are SUMS (`cell_sums`) so a set's cell pools over its targets and a target bootstrap recomposes it
exactly, as the headroom cells do.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RULE_ID = "bt32-threshold-recovery-two-part.v1"
VALUE = "VALUE"
#: The kinds the spec defines, and the empty-state tokens of each (S1; rev 2 adds first_crossing).
KIND_TOKENS = {
    "recovery": ("NEVER_REACHED", "NOT_RECOVERED"),
    "first_crossing": ("NOT_REACHED",),
}
#: The BT 3.2 kit page's scoring text for these outputs, verbatim from the spec line rev 2 "Public text" (the blockquote
#: lines with their "> " removed, joined by newlines). Its sha256 is pinned by the tests.
PUBLIC_TEXT = (
    "**Threshold recovery (85 C).** Some designs never get hot enough to cross 85 C, and some may still be above it when\n"
    'the window ends. For each design, give either a time in seconds or one of the words `"NEVER_REACHED"` or\n'
    '`"NOT_RECOVERED"`. Both words are valid answers, not errors; leaving the field out is still an error.\n'
    "- **Half your score** for this output is calling the right one of the three. Designs whose peak sits too close to\n"
    "  85 C for our reference to tell are not counted for this half.\n"
    "- **The other half** is the accuracy of your time where both you and the reference give a time. A design that\n"
    "  recovers but that you call empty counts the same as the best classical fit there.\n"
    "\n"
    '**First 95 C crossing.** The same rule, with two answers: a time in seconds, or `"NOT_REACHED"`. Designs whose\n'
    "peak sits too close to 95 C for our reference to tell are not counted for the first half.\n"
    "\n"
    "As everywhere in BT 3.2, 0 = the best classical method we could build, 1 = reference accuracy."
)


class TypedOutputRefused(ValueError):
    """The registration or the reference cannot give a sound typed-output score: the Challenge's, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise TypedOutputRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class TypedOutput:
    """One registered typed output. Every field is the version's; None (HUMAN_INPUT) refuses in `check`."""

    output: str
    kind: str
    rule: str
    threshold_c: object  # the owner's threshold (85 C recovery, 95 C first crossing)
    band_output: str  # the finite output whose truth decides the S2 band (peak_top_c)
    band_u: object  # the receipted 3.2 U of band_output
    value_u: object  # the receipted 3.2 U of this output's value
    event_weight: object  # w (1/2, the Lead's decision under the owner's delegation)


def check(typed):
    """`TypedOutputRefused` unless ``typed`` is a complete registration of this rule."""
    _require(isinstance(typed, TypedOutput), "typed_output_malformed")
    _require(type(typed.output) is str and typed.output, "typed_output_name_missing")
    _require(typed.kind in KIND_TOKENS, "typed_output_kind_unknown")
    _require(typed.rule == RULE_ID, "typed_output_rule_is_not_the_registered_one")
    _require(
        type(typed.band_output) is str
        and typed.band_output
        and typed.band_output != typed.output,
        "typed_output_band_output_missing",
    )
    for name in ("threshold_c", "band_u", "value_u", "event_weight"):
        _require(
            getattr(typed, name) is not None, f"typed_output_{name}_is_human_input"
        )
    _require(_number(typed.threshold_c), "typed_output_threshold_must_be_a_number")
    _require(
        _number(typed.band_u) and typed.band_u >= 0,
        "typed_output_band_u_must_be_non_negative",
    )
    _require(
        _number(typed.value_u) and typed.value_u > 0,
        "typed_output_value_u_must_be_positive",
    )
    _require(
        _number(typed.event_weight) and 0 < typed.event_weight < 1,
        "typed_output_event_weight_must_be_in_0_1",
    )


def state(kind, value):
    """S1: ``(VALUE, v)`` or ``(token, None)``, or None for an INVALID answer (missing, null, a token of another kind, a
    negative or non-finite number, any other type)."""
    if type(value) is str:
        return (value, None) if value in KIND_TOKENS[kind] else None
    if _number(value) and value >= 0:
        return (VALUE, float(value))
    return None


def truth_state(kind, value):
    """A REFERENCE truth's state; an unreadable truth is the reference's fault (refused), never the candidate's."""
    typed = state(kind, value)
    _require(typed is not None, "typed_output_truth_unreadable")
    return typed


def truth_from_deck(kind, value):
    """A BT 3.2 deck record's value of a typed output as a pool truth (Validator-BT's adapter condition (a), spec rev 3).
    The deck writes ``threshold_recovery_s`` as a number, ``"NOT_RECOVERED"``, or None (the peak never crossed the
    threshold), and ``first_95c_crossing_s`` as a number or ``"NOT_REACHED"``. Only the recovery kind maps None, to
    ``"NEVER_REACHED"``; every other value passes unchanged and must already be a readable truth (`truth_state`), so a
    None of the first-crossing kind, or anything else unreadable, is the reference's fault (refused), never mapped.
    """
    _require(kind in KIND_TOKENS, "typed_output_kind_unknown")
    if value is None and kind == "recovery":
        value = "NEVER_REACHED"
    truth_state(kind, value)
    return value


def in_band(typed, peak_truth):
    """S2: True when the truth peak sits within ``band_u`` of the threshold (not resolvable)."""
    _require(_number(peak_truth), "typed_output_band_truth_not_finite")
    return abs(peak_truth - typed.threshold_c) <= typed.band_u


def case_sums(typed, truth, prediction, peak_truth):
    """One case's contribution ``(m, r, log_b, b, t)``: the EVENT miss count and resolvable count (S2, S3), the sum over B
    of ln max(|err| / value_u, 1), |B| and |T| (S4). ``truth`` and ``prediction`` are raw values (the prediction already
    validated by `state`)."""
    t_state, t_value = truth_state(typed.kind, truth)
    p = state(typed.kind, prediction)
    _require(
        p is not None, "typed_output_prediction_invalid"
    )  # callers gate invalid answers first
    p_state, p_value = p
    band = in_band(typed, peak_truth)
    m = 1 if (not band and p_state != t_state) else 0
    r = 0 if band else 1
    log_b, b, t = 0.0, 0, 0
    if t_state == VALUE:
        if p_state == VALUE:
            t, b = 1, 1
            log_b = math.log(max(abs(p_value - t_value) / typed.value_u, 1.0))
        elif not band:
            t = 1  # a resolvable truth value called empty: in T, not in B (the coverage factor charges it)
    return (m, r, log_b, b, t)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b, strict=True))


ZERO = (0, 0, 0.0, 0, 0)


def cell_sums(typed, cases):
    """The pooled sums of ``cases`` = [(truth, prediction, peak_truth), ...]."""
    total = ZERO
    for truth, prediction, peak in cases:
        total = add(total, case_sums(typed, truth, prediction, peak))
    return total


def log_skill(anchor, error):
    """clip(ln(A / E) / ln(A), 0, 1); A > 1 (an admitted anchor), E >= 1 (floored)."""
    _require(_number(anchor) and anchor > 1, "typed_output_value_anchor_must_exceed_1")
    return min(1.0, max(0.0, math.log(anchor / error) / math.log(anchor)))


def combine(typed, sums, *, m_anchor, value_anchor, r_anchor=None):
    """S3-S5 from pooled ``sums``: the cell score, or None when neither part is admitted (the cell is not scored).

    ``m_anchor``: the panel's least miss count (S6; the EVENT part needs >= 1), over ``r_anchor`` resolvable cases (the
    whole exam's; None = the same cases as ``sums``, the spec's single-pool form). ``value_anchor``: the VALUE part's A_c
    when its registered admission tests PASS, else None.
    """
    m, r, log_b, b, t = sums
    _require(
        type(m_anchor) is int and m_anchor >= 0, "typed_output_m_anchor_must_be_a_count"
    )
    event = None
    if m_anchor >= 1:
        if r_anchor is None:
            event = min(1.0, max(0.0, 1.0 - m / m_anchor))
        elif r >= 1:
            _require(
                type(r_anchor) is int and r_anchor >= m_anchor,
                "typed_output_r_anchor_must_cover_m_anchor",
            )
            event = min(1.0, max(0.0, 1.0 - (m / r) / (m_anchor / r_anchor)))
    value = None
    if value_anchor is not None and t >= 1:
        value = 0.0 if b == 0 else log_skill(value_anchor, math.exp(log_b / b)) * b / t
    if event is not None and value is not None:
        return typed.event_weight * event + (1.0 - typed.event_weight) * value
    return event if event is not None else value


def gate_ratios(typed, cases):
    """S7: |err| / value_u on B only (truth and prediction both a value); a state mismatch adds nothing."""
    out = []
    for truth, prediction, _peak in cases:
        t_state, t_value = truth_state(typed.kind, truth)
        p = state(typed.kind, prediction)
        if p is not None and t_state == VALUE and p[0] == VALUE:
            out.append(abs(p[1] - t_value) / typed.value_u)
    return out


def panel_anchor(typed, members, cases):
    """S6: ``(m_anchor, A_c)`` from the classical panel's two-part predictions.

    ``members``: {name: [{"state": token-or-number, "value": number}, ...]} aligned with ``cases`` = [(truth, peak), ...].
    Every member gives a state (as a prediction, S1) AND a finite value >= 0 on EVERY case, else it is not a panel member
    for this output (refused here: the panel builder must drop it explicitly). m_anchor = the least resolvable miss count
    over the members; A_c = the least, over the members, geometric-mean floored error of each member's VALUE prediction
    over ALL truth-value cases (None when no case has a truth value).
    """
    _require(type(members) is dict and members, "typed_output_panel_empty")
    misses, errors = [], []
    for name, rows in members.items():
        _require(
            type(rows) is list and len(rows) == len(cases),
            f"typed_output_panel_member_misaligned:{name}",
        )
        m, logs = 0, []
        for row, (truth, peak) in zip(rows, cases):
            _require(
                type(row) is dict and set(row) == {"state", "value"},
                f"typed_output_panel_member_not_two_part:{name}",
            )
            p = state(typed.kind, row["state"])
            _require(p is not None, f"typed_output_panel_member_state_invalid:{name}")
            _require(
                _number(row["value"]) and row["value"] >= 0,
                f"typed_output_panel_member_value_invalid:{name}",
            )
            t_state, t_value = truth_state(typed.kind, truth)
            if not in_band(typed, peak) and p[0] != t_state:
                m += 1
            if t_state == VALUE:
                logs.append(
                    math.log(max(abs(row["value"] - t_value) / typed.value_u, 1.0))
                )
        misses.append(m)
        if logs:
            errors.append(math.exp(sum(logs) / len(logs)))
    return min(misses), (min(errors) if errors else None)


__all__ = [
    "KIND_TOKENS",
    "PUBLIC_TEXT",
    "RULE_ID",
    "VALUE",
    "ZERO",
    "TypedOutput",
    "TypedOutputRefused",
    "add",
    "case_sums",
    "cell_sums",
    "check",
    "combine",
    "gate_ratios",
    "in_band",
    "log_skill",
    "panel_anchor",
    "state",
    "truth_state",
]
