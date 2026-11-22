"""Case-level typed state (RUNAWAY) for the joint chip-thermal exam, rule ``joint-chip-thermal-typed-state.v1``.

Basis: model-eval's ruling of 22 Nov 2026 03:03:09Z (RECEIPTS) on the joint exam code map
(``codex-queue/reports/JOINT_EXAM_CODE_MAP_20261122.md``, section "Seat answers folded in"), shape only, on exam-bt's
die-side proposal (02:44Z). This module holds the rule's arithmetic. Every number (the band and the event weight) is
the version's registration (`CaseState`). None has a default: a missing one refuses (HUMAN_INPUT). It is a NEW module
and changes no BT 3.2 byte: `typed_state_output` is only imported, never edited.

C1  States. A case's reference truth and a model's answer each take one case state: ``RUNAWAY`` (the design runs away
    and has no truth number) or ``BOUNDED`` (it does not). An unreadable REFERENCE state is the reference's fault and is
    refused. An unreadable ANSWER is INVALID (the schema gate) and is never a state.
C2  Masking. A REFERENCE RUNAWAY masks every numeric output of that case for every model: no truth number exists. A
    model's RUNAWAY on a reference-BOUNDED case leaves that model's numeric cells for the case unscored. Numeric outputs
    are scored on a case only when both are BOUNDED (`numeric_scored`). This includes the two typed time outputs, which
    keep the BT 3.2 kinds (`first_crossing`, `recovery`) under this rule's id (`check_time`).
C3  Band. A case whose reference ``band_output`` truth lies within ``band_u`` of ``band_center`` is not resolvable: it
    is neither credited nor charged in the EVENT part. Both numbers are HUMAN_INPUT, and so is the choice of the band
    output.
C4  EVENT, SYMMETRIC. m = resolvable cases whose answered state differs from the reference state, counted in BOTH
    directions: a model RUNAWAY on a BOUNDED case, and a model BOUNDED (finite answers) on a RUNAWAY case. The second is
    the dangerous miss for a buyer, and model-eval ruled it is charged the same. The score uses BT 3.2's event form
    (`typed_state_output` S3): S_event = clip(1 - m / m_anchor, 0, 1), or, for a set graded on r of the exam's R
    resolvable cases, clip(1 - (m / r) / (m_anchor / R), 0, 1). The score is None (no evidence) when m_anchor = 0 or
    r = 0.
C5  Panel. m_anchor = the least resolvable miss count over the classical panel's state answers (`panel_anchor`).
C6  Combination. w S_event + (1 - w) S_numeric, where w = ``event_weight`` (HUMAN_INPUT) and S_numeric = the version's
    score over its numeric outputs on the C2-unmasked cases. When only one is admitted, that one is the score. When
    neither is, the cell is not scored.
C7  Gates are split. Energy closure is a REFERENCE qualification gate (seal time, custody), never applied to a
    candidate. A REFERENCE_INVALID case is excluded at the seal and never reaches this module as a state. Candidate
    admissibility gates read numeric answers only on C2-unmasked cases.

Contributions are SUMS (`cell_sums`), so a set's cell pools over its cases and a bootstrap recomposes it exactly, as
`typed_state_output` does.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from carbon.scoring import typed_state_output as tso

RULE_ID = "joint-chip-thermal-typed-state.v1"
RUNAWAY = "RUNAWAY"
BOUNDED = "BOUNDED"
CASE_STATES = (RUNAWAY, BOUNDED)
ZERO = (0, 0)


class CaseStateRefused(ValueError):
    """The registration or the reference cannot give a sound case-state score: the Challenge's fault, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise CaseStateRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class CaseState:
    """One registered case-state output. Every field is the version's own. None (HUMAN_INPUT) refuses in `check`."""

    output: str
    rule: str
    band_output: (
        object  # the reference output whose truth decides the C3 band (HUMAN_INPUT)
    )
    band_center: object  # HUMAN_INPUT
    band_u: object  # HUMAN_INPUT
    event_weight: object  # w (HUMAN_INPUT)


def check(registration):
    """Raise `CaseStateRefused` unless ``registration`` is a complete registration of this rule."""
    _require(isinstance(registration, CaseState), "case_state_malformed")
    _require(
        type(registration.output) is str and registration.output,
        "case_state_name_missing",
    )
    _require(registration.rule == RULE_ID, "case_state_rule_is_not_the_registered_one")
    for name in ("band_output", "band_center", "band_u", "event_weight"):
        _require(
            getattr(registration, name) is not None,
            f"case_state_{name}_is_human_input",
        )
    _require(
        type(registration.band_output) is str
        and registration.band_output
        and registration.band_output != registration.output,
        "case_state_band_output_missing",
    )
    _require(
        _number(registration.band_center), "case_state_band_center_must_be_a_number"
    )
    _require(
        _number(registration.band_u) and registration.band_u >= 0,
        "case_state_band_u_must_be_non_negative",
    )
    _require(
        _number(registration.event_weight) and 0 < registration.event_weight < 1,
        "case_state_event_weight_must_be_in_0_1",
    )


def check_time(typed):
    """Check a joint-exam typed TIME output (time-to-throttle, recovery). It is a `typed_state_output.TypedOutput` of
    an existing BT 3.2 kind, registered under THIS rule's id. The arithmetic is BT 3.2's unchanged, so it is checked by
    `typed_state_output.check` with the rule id swapped back. Any other rule id refuses.
    """
    _require(isinstance(typed, tso.TypedOutput), "case_state_time_malformed")
    _require(typed.rule == RULE_ID, "case_state_time_rule_is_not_the_joint_one")
    try:
        tso.check(dataclasses.replace(typed, rule=tso.RULE_ID))
    except tso.TypedOutputRefused as refused:
        raise CaseStateRefused(refused.code) from None


def state(value):
    """C1: the answered case state, or None for an INVALID answer (anything but one of `CASE_STATES`)."""
    return value if type(value) is str and value in CASE_STATES else None


def truth_state(value):
    """C1: a REFERENCE case state. An unreadable one is the reference's fault (refused), never the candidate's."""
    typed = state(value)
    _require(typed is not None, "case_state_truth_unreadable")
    return typed


def numeric_scored(truth, prediction):
    """C2: whether a model's numeric outputs on this case are scored. Only when the reference and the model both say
    BOUNDED. A reference RUNAWAY masks the case for everyone; a model RUNAWAY leaves its own cells for it unscored.
    """
    p = state(prediction)
    _require(p is not None, "case_state_prediction_invalid")  # callers gate first
    return truth_state(truth) == BOUNDED and p == BOUNDED


def in_band(registration, band_truth):
    """C3: True when the reference band truth lies within ``band_u`` of ``band_center`` (not resolvable)."""
    _require(_number(band_truth), "case_state_band_truth_not_finite")
    return abs(band_truth - registration.band_center) <= registration.band_u


def case_sums(registration, truth, prediction, band_truth):
    """One case's EVENT contribution ``(m, r)``: a resolvable miss (either direction, C4) and the resolvable count."""
    t = truth_state(truth)
    p = state(prediction)
    _require(p is not None, "case_state_prediction_invalid")  # callers gate first
    if in_band(registration, band_truth):
        return ZERO
    return (1 if p != t else 0, 1)


def cell_sums(registration, cases):
    """The pooled ``(m, r)`` of ``cases`` = [(truth, prediction, band_truth), ...]."""
    m = r = 0
    for truth, prediction, band in cases:
        dm, dr = case_sums(registration, truth, prediction, band)
        m, r = m + dm, r + dr
    return (m, r)


def event_score(sums, *, m_anchor, r_anchor=None):
    """C4: S_event from pooled ``sums``, or None (no evidence) when ``m_anchor`` is 0 or the set has no resolvable
    case. ``r_anchor`` = the whole exam's resolvable count (None means the same cases as ``sums``).
    """
    m, r = sums
    _require(
        type(m_anchor) is int and m_anchor >= 0, "case_state_m_anchor_must_be_a_count"
    )
    if m_anchor < 1 or r < 1:
        return None
    if r_anchor is None:
        return min(1.0, max(0.0, 1.0 - m / m_anchor))
    _require(
        type(r_anchor) is int and r_anchor >= m_anchor,
        "case_state_r_anchor_must_cover_m_anchor",
    )
    return min(1.0, max(0.0, 1.0 - (m / r) / (m_anchor / r_anchor)))


def combine(registration, event, numeric):
    """C6: w S_event + (1 - w) S_numeric. When only one is admitted, that one. When neither is, None (not scored)."""
    if event is not None and numeric is not None:
        return (
            registration.event_weight * event
            + (1.0 - registration.event_weight) * numeric
        )
    return event if event is not None else numeric


def panel_anchor(registration, members, cases):
    """C5: m_anchor, the least resolvable miss count over the classical panel's state answers.

    ``members``: {name: [state, ...]} aligned with ``cases`` = [(truth, band_truth), ...]. Every member must give a
    readable state on EVERY case. Otherwise it is not a panel member for this output: this refuses, and the panel builder
    drops it explicitly."""
    _require(type(members) is dict and members, "case_state_panel_empty")
    misses = []
    for name, rows in members.items():
        _require(
            type(rows) is list and len(rows) == len(cases),
            f"case_state_panel_member_misaligned:{name}",
        )
        _require(
            all(state(row) is not None for row in rows),
            f"case_state_panel_member_state_invalid:{name}",
        )
        m, _r = cell_sums(
            registration,
            [(truth, row, band) for row, (truth, band) in zip(rows, cases)],
        )
        misses.append(m)
    return min(misses)


__all__ = [
    "BOUNDED",
    "CASE_STATES",
    "RULE_ID",
    "RUNAWAY",
    "ZERO",
    "CaseState",
    "CaseStateRefused",
    "case_sums",
    "cell_sums",
    "check",
    "check_time",
    "combine",
    "event_score",
    "in_band",
    "numeric_scored",
    "panel_anchor",
    "state",
    "truth_state",
]
