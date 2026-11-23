"""Self-trust: an OPTIONAL per-output uncertainty and a per-case send-back flag from a miner's model, scored REPORT-ONLY
(rule ``carbon.self-trust.report-only.v1``). One shared feature for every physics-prediction Challenge; a version adopts it
only through its own registration (`SelfTrustRule`). Design note: codex-queue/reports/SELF_TRUST_20261121/DESIGN.md.

Owner (20-21 Nov): every exam takes "a model that knows when not to trust itself"; "if it is done in time, it does go into
these exams" (G-LEAD-26: BT 3.2, Motor 1.9, RB 2.0, Cooling 1.8, each by its registration cutoff, else its next version).
This module is inert until a version's registration imports it: nothing in the grade path imports it today, and with no
rule (``None``) every helper here is the identity, so no registered output contract, encoding, producer digest or pack moves.

T1  Block. A version that adopts the rule widens its raw model row by ONE trailing block after its registered width W
    (whatever W already holds: native values, law-safe encoded slots, typed-state codes). The block is in NATIVE units of
    the trust outputs (the derived, scored outputs the rule names, in the rule's order), never encoded:
      gaussian_sigma:   [sigma_1 .. sigma_k, flag]             width k + 1, sigma_j finite > 0
      central_interval: [lo_1, hi_1 .. lo_k, hi_k, flag]        width 2k + 1, lo_j <= hi_j, both finite
    flag is exactly 0 (trust this case) or 1 (send this case back to full simulation). The MODE is an explicit DECLARATION of
    the candidate (V2 pre-read 21 Nov: width alone never switches mode), never the row's width: an undeclared candidate's rows
    must be exactly W wide (ABSENT, today's answer byte for byte); a declared candidate's rows must be exactly W + block wide
    (PRESENT, or ``block_invalid`` when the block cannot be read). Any other width is left to today's path unchanged (it
    already refuses a wrong width), so a miner who sends W + k by accident gets OUTPUT_CONTRACT_DIFFERS, not a silent sigma
    mode, and the trust read marks it ``width_invalid``. The physics answer is always derived from the first W values
    only, so a model's trust block can never move its physics score.
T2  Band. The case's stated central band at the registered nominal coverage c: the interval itself, or
    p +- z sigma with z = Phi^-1((1 + c) / 2) (the Gaussian form is the miner's stated distribution, not Carbon's claim).
T3  Calibration (per trust output, over every case of the read set): empirical coverage (truth inside the closed band) vs c,
    an exact two-sided binomial p-value of that count under c (descriptive; no pass/fail threshold is set here), and the
    interval score of Gneiting & Raftery (2007, eq. 43), a proper score for a central (1 - a) interval, a = 1 - c:
        IS = (hi - lo) + (2 / a) (lo - y) [y < lo] + (2 / a) (y - hi) [y > hi],
    divided by the case's U (the version's receipted U of that output). The Gaussian form also reports the closed-form CRPS
    / U (report only, never in a score). Skill_o = clip(1 - mean(IS / U) / anchor_o, 0, 1), anchor_o = the registered mean
    IS / U that scores 0 (e.g. the version's smart-zero panel with its own bands). S_cal = sum_o w_o Skill_o.
    Sharpness (report only, per output): the median band width / U, and the median band width / the median |p - t| over
    the same cases (None when that median error is 0). Coverage alone rates a model that states needlessly WIDE bands as
    well calibrated (wide bands cover everything); sharpness is what exposes it (model-eval 23 Nov). It describes, it sets
    no threshold: what a sharp enough band is stays the version's registration.
T4  Send-back (per case). A case is BADLY WRONG when |p - t| / U > cut_o for ANY output o of ``send_back_outputs``
    (strictly greater). A flagged case counts as routed to full simulation at cost ``send_back_cost``; a badly wrong
    unflagged case costs ``miss_cost``; nothing else costs. With n cases, B badly wrong, F flagged, M missed (badly wrong and
    unflagged): L = (miss_cost M + send_back_cost F) / n. Never flagging gives L_never = miss_cost B / n; flagging exactly
    the badly wrong cases gives L_oracle = send_back_cost B / n (send_back_cost < miss_cost is required, else flagging can
    never pay and the part is meaningless). S_sb = clip((L_never - L) / (L_never - L_oracle), 0, 1): 0 = no better than
    never flagging (or worse), 1 = flags exactly the cases it gets badly wrong. B = 0 gives the part no evidence (None).
T5  Total (report only) = calibration_weight S_cal + (1 - calibration_weight) S_sb. A part with a positive weight and no
    evidence leaves the total None. It never enters any official score, rank, crown or settlement (invariant 11): entering
    a score is a later, separately registered scientific contract. That contract's owner-approved form is the trust
    amplifier (A1-A3 below, owner TRUST-AMPLIFIER 23 Nov): a different quantity (T, against the best constant band), and
    it too enters a grade only through a version's own scoring-path FINAL with the owner's three values set.
T6  Read status per model over the read set: ``absent`` (no case carries a block: no report, physics unchanged), ``invalid``
    (some case carries an unreadable block, a wrong width, or the cases mix present and absent: the candidate's, report only,
    no trust scores), ``scored``.

Every science value (nominal coverage, output weights, anchors, cuts, the two costs, the part weight) is the version's
registration with NO default: None is HUMAN_INPUT and refuses (`SelfTrustRefused`), as does a value outside its domain.
A reference truth or U that cannot be read is the Challenge's refusal, never the candidate's. Pure Python, fixed order,
``math.fsum``: the same inputs give the same report bit for bit. Nothing here names a Challenge.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from statistics import NormalDist, median

RULE_ID = "carbon.self-trust.report-only.v1"
REPORT_SCHEMA = "carbon.self-trust.report.v1"
PUBLIC_SCHEMA = "carbon.self-trust.public.v1"
SIGMA = "gaussian_sigma"
INTERVAL = "central_interval"
FORMS = (SIGMA, INTERVAL)
#: Read statuses (T1, T6).
NOT_ADOPTED, ABSENT, PRESENT, WIDTH_INVALID, BLOCK_INVALID = (
    "not_adopted",
    "absent",
    "present",
    "width_invalid",
    "block_invalid",
)
SCORED, INVALID = "scored", "invalid"
#: The registration fields that are science values (HUMAN_INPUT until registered; none has a default).
SCIENCE_FIELDS = (
    "nominal_coverage",
    "output_weights",
    "interval_score_anchor_u",
    "badly_wrong_cut_u",
    "miss_cost",
    "send_back_cost",
    "calibration_weight",
)
#: PROPOSED public allow-list (pending V2's disclosure ruling; nothing publishes it today): scores and rates only, never a
#: count of cases, a per-case value, a truth-derived count (badly wrong / missed / caught) or a CRPS / interval-score level.
PUBLIC_FIELDS = (
    "schema",
    "rule",
    "status",
    "form",
    "nominal_coverage",
    "coverage",
    "sharpness",
    "calibration_skill",
    "flag_rate",
    "send_back_skill",
    "total",
)


class SelfTrustRefused(ValueError):
    """The registration or the reference cannot give a sound self-trust read: the Challenge's, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise SelfTrustRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class SelfTrustRule:
    """One version's registration of the rule. Structural fields first, then the science values (None = HUMAN_INPUT)."""

    rule: str
    form: str
    outputs: tuple  # the trust outputs: scalar scored outputs, in block column order
    send_back_outputs: tuple  # the outputs whose miss makes a case badly wrong (a non-empty subset of outputs)
    nominal_coverage: object  # c in (0, 1): the central band the miner states
    output_weights: object  # {output: w >= 0}, over exactly `outputs`, summing to 1
    interval_score_anchor_u: (
        object  # {output: mean IS / U that scores 0}, > 0, over exactly `outputs`
    )
    badly_wrong_cut_u: (
        object  # {output: |err| / U cut}, > 0, over exactly `send_back_outputs`
    )
    miss_cost: object  # > 0: one badly wrong case the model did not flag
    send_back_cost: object  # 0 < send_back_cost < miss_cost: one flagged case sent to full simulation
    calibration_weight: (
        object  # in [0, 1]: the calibration part's weight in the report total
    )


def _names(value):
    return (
        type(value) is tuple
        and len(value) >= 1
        and all(type(n) is str and n for n in value)
        and len(set(value)) == len(value)
    )


def _per_output(value, names, field, positive):
    _require(
        type(value) is dict and set(value) == set(names),
        f"self_trust_{field}_must_cover_exactly_its_outputs",
    )
    domain = "must_be_positive" if positive else "must_be_non_negative"
    for name in names:
        v = value[name]
        _require(
            _number(v) and (v > 0 if positive else v >= 0),
            f"self_trust_{field}_{domain}",
        )


def check(rule):
    """`SelfTrustRefused` unless ``rule`` is a complete registration of this rule (every science value present and in domain)."""
    _require(isinstance(rule, SelfTrustRule), "self_trust_rule_malformed")
    _require(rule.rule == RULE_ID, "self_trust_rule_is_not_the_registered_one")
    _require(rule.form in FORMS, "self_trust_form_unknown")
    _require(_names(rule.outputs), "self_trust_outputs_malformed")
    _require(
        _names(rule.send_back_outputs)
        and set(rule.send_back_outputs) <= set(rule.outputs),
        "self_trust_send_back_outputs_must_be_a_subset_of_outputs",
    )
    for name in SCIENCE_FIELDS:
        _require(getattr(rule, name) is not None, f"self_trust_{name}_is_human_input")
    _require(
        _number(rule.nominal_coverage) and 0 < rule.nominal_coverage < 1,
        "self_trust_nominal_coverage_must_be_in_0_1",
    )
    _per_output(rule.output_weights, rule.outputs, "output_weights", positive=False)
    _require(
        abs(math.fsum(rule.output_weights[o] for o in rule.outputs) - 1.0) <= 1e-12,
        "self_trust_output_weights_must_sum_to_1",
    )
    _per_output(
        rule.interval_score_anchor_u,
        rule.outputs,
        "interval_score_anchor_u",
        positive=True,
    )
    _per_output(
        rule.badly_wrong_cut_u,
        rule.send_back_outputs,
        "badly_wrong_cut_u",
        positive=True,
    )
    _require(
        _number(rule.miss_cost) and rule.miss_cost > 0,
        "self_trust_miss_cost_must_be_positive",
    )
    _require(
        _number(rule.send_back_cost) and 0 < rule.send_back_cost < rule.miss_cost,
        "self_trust_send_back_cost_must_be_in_0_miss_cost",
    )
    _require(
        _number(rule.calibration_weight) and 0 <= rule.calibration_weight <= 1,
        "self_trust_calibration_weight_must_be_in_0_1",
    )


# -- T1: the block -------------------------------------------------------------------------------------------------------


def block_width(rule):
    """The trailing block's width: k + 1 (sigma form) or 2k + 1 (interval form)."""
    check(rule)
    per = 1 if rule.form == SIGMA else 2
    return per * len(rule.outputs) + 1


def accepted_widths(base_width, rule, declared=False):
    """The ONE raw row width a candidate's inference shape gate accepts: ``(W,)`` with no rule or an undeclared candidate
    (today), ``(W + block,)`` for a candidate that declared self-trust under a version's rule. Never both: the declaration,
    not the width, decides the mode."""
    _require(
        type(base_width) is int and base_width >= 1, "self_trust_base_width_malformed"
    )
    if rule is None or not declared:
        return (base_width,)
    return (base_width + block_width(rule),)


@dataclass(frozen=True)
class TrustAnswer:
    """One case's readable block: ``bands`` = {output: (lo, hi)} as stated (interval form) or ``sigmas`` = {output: s}."""

    form: str
    sigmas: dict
    bands: dict
    flag: bool


@dataclass(frozen=True)
class Split:
    """A raw row split by `split_row`: ``base`` is what today's derive reads; ``answer`` the parsed block or None."""

    base: object
    status: str
    answer: object


def _raw_number(value):
    # a raw output cell: numpy / Python numbers, never a bool or a string
    if isinstance(value, (bool, str, bytes)):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_block(rule, values):
    """The block's `TrustAnswer`, or None when any cell is unreadable (the candidate's invalid block, report only)."""
    check(rule)
    try:
        cells = [_raw_number(v) for v in values]
    except TypeError:
        return None
    if len(cells) != block_width(rule) or any(v is None for v in cells):
        return None
    *body, flag = cells
    if flag not in (0.0, 1.0):
        return None
    sigmas, bands = {}, {}
    if rule.form == SIGMA:
        for name, s in zip(rule.outputs, body, strict=True):
            if not s > 0:
                return None
            sigmas[name] = s
    else:
        for j, name in enumerate(rule.outputs):
            lo, hi = body[2 * j], body[2 * j + 1]
            if not lo <= hi:
                return None
            bands[name] = (lo, hi)
    return TrustAnswer(form=rule.form, sigmas=sigmas, bands=bands, flag=flag == 1.0)


def split_row(raw, base_width, rule, declared=False):
    """T1: one raw model row as (what the physics derive reads, the trust read).

    No rule: the row itself, untouched (``not_adopted``). Undeclared candidate, width W: the row itself (``absent``).
    Declared candidate, width W + block: the first W values (``present``, or ``block_invalid`` when the block cannot be
    read). Any other width, including W + block from an undeclared candidate: the row itself, untouched, so today's path
    judges it exactly as before (``width_invalid``).
    """
    if rule is None:
        return Split(base=raw, status=NOT_ADOPTED, answer=None)
    (width,) = accepted_widths(base_width, rule, declared)
    try:
        n = len(raw)
    except TypeError:
        return Split(base=raw, status=WIDTH_INVALID, answer=None)
    if n != width:
        return Split(base=raw, status=WIDTH_INVALID, answer=None)
    if not declared:
        return Split(base=raw, status=ABSENT, answer=None)
    answer = parse_block(rule, list(raw[base_width:]))
    return Split(
        base=raw[:base_width],
        status=PRESENT if answer is not None else BLOCK_INVALID,
        answer=answer,
    )


# -- T2-T5: the read -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TrustCase:
    """One graded case: the model's VALID physics answer, the reference truth and U, and the trust read of its row.

    ``predictions`` / ``truths`` / ``u`` carry at least the rule's outputs (numbers). Only cases whose physics answer is
    valid are read (an invalid physics answer is already the grade's); for a typed-state output only cases where truth and
    prediction both carry a value are passed (v1 reads values only). ``status`` is the `Split` status of the row.
    """

    predictions: dict
    truths: dict
    u: dict
    status: str
    answer: object


def _z(coverage):
    return NormalDist().inv_cdf((1.0 + coverage) / 2.0)


def band(rule, prediction, answer, output):
    """T2: the stated closed central band (lo, hi) of ``output`` at the registered nominal coverage."""
    if rule.form == INTERVAL:
        return answer.bands[output]
    half = _z(rule.nominal_coverage) * answer.sigmas[output]
    return (prediction - half, prediction + half)


def interval_score(lo, hi, y, coverage):
    """T3: Gneiting & Raftery's interval score of the central band [lo, hi] at nominal coverage ``coverage`` for outcome y."""
    alpha = 1.0 - coverage
    score = hi - lo
    if y < lo:
        score += (2.0 / alpha) * (lo - y)
    elif y > hi:
        score += (2.0 / alpha) * (y - hi)
    return score


def gaussian_crps(mu, sigma, y):
    """The closed-form CRPS of N(mu, sigma^2) at y (report only)."""
    z = (y - mu) / sigma
    unit = NormalDist()
    return sigma * (
        z * (2.0 * unit.cdf(z) - 1.0) + 2.0 * unit.pdf(z) - 1.0 / math.sqrt(math.pi)
    )


def binomial_two_sided_p(k, n, p):
    """Exact two-sided binomial p-value of k successes in n at rate p (the sum of every outcome no likelier than k)."""
    _require(
        type(k) is int and type(n) is int and 0 <= k <= n and n >= 1 and 0 < p < 1,
        "self_trust_binomial_arguments_malformed",
    )
    log_p, log_q = math.log(p), math.log1p(-p)
    head = math.lgamma(n + 1)

    def log_pmf(j):
        return (
            head
            - math.lgamma(j + 1)
            - math.lgamma(n - j + 1)
            + j * log_p
            + (n - j) * log_q
        )

    observed = log_pmf(k)
    tail = math.fsum(
        math.exp(log_pmf(j)) for j in range(n + 1) if log_pmf(j) <= observed + 1e-9
    )
    return min(1.0, tail)


def _case_values(rule, case):
    for field in ("predictions", "truths", "u"):
        values = getattr(case, field)
        _require(
            type(values) is dict and set(rule.outputs) <= set(values),
            f"self_trust_case_{field}_missing_an_output",
        )
    for name in rule.outputs:
        _require(_number(case.truths[name]), "self_trust_truth_not_a_number")
        _require(
            _number(case.u[name]) and case.u[name] > 0,
            "self_trust_u_must_be_positive",
        )
        # the grade passes only valid physics answers: a non-number here is the caller's wiring, refused
        _require(
            _number(case.predictions[name]),
            "self_trust_prediction_not_a_valid_answer",
        )


def _status(cases):
    statuses = [c.status for c in cases]
    _require(
        all(s in (ABSENT, PRESENT, WIDTH_INVALID, BLOCK_INVALID) for s in statuses),
        "self_trust_case_status_unknown",
    )
    if all(s == ABSENT for s in statuses):
        return ABSENT, None
    bad = sum(s in (WIDTH_INVALID, BLOCK_INVALID) for s in statuses)
    if bad:
        return INVALID, "self_trust_block_unreadable"
    if any(s == ABSENT for s in statuses):
        return INVALID, "self_trust_block_present_on_some_cases_only"
    return SCORED, None


def _clip01(value):
    return min(1.0, max(0.0, value))


def _calibration(rule, cases):
    c = rule.nominal_coverage
    rows = {}
    for name in rule.outputs:
        covered, scores, crps, widths, widths_u, errors = 0, [], [], [], [], []
        for case in cases:
            p, y, u = case.predictions[name], case.truths[name], case.u[name]
            lo, hi = band(rule, p, case.answer, name)
            covered += lo <= y <= hi
            scores.append(interval_score(lo, hi, y, c) / u)
            widths.append(hi - lo)
            widths_u.append((hi - lo) / u)
            errors.append(abs(p - y))
            if rule.form == SIGMA:
                crps.append(gaussian_crps(p, case.answer.sigmas[name], y) / u)
        n = len(cases)
        mean_is = math.fsum(scores) / n
        raw = 1.0 - mean_is / rule.interval_score_anchor_u[name]
        median_error = median(errors)
        rows[name] = {
            "n": n,
            "covered": covered,
            "coverage": covered / n,
            "nominal_coverage": c,
            "coverage_gap": covered / n - c,
            "coverage_p_two_sided": binomial_two_sided_p(covered, n, c),
            "median_width_u": median(widths_u),
            "sharpness": median(widths) / median_error if median_error > 0 else None,
            "mean_interval_score_u": mean_is,
            "mean_crps_u": math.fsum(crps) / n if rule.form == SIGMA else None,
            "calibration_skill_raw": raw,
            "calibration_skill": _clip01(raw),
        }
    total = math.fsum(
        rule.output_weights[name] * rows[name]["calibration_skill"]
        for name in rule.outputs
    )
    return rows, total


def badly_wrong(rule, case):
    """T4: True when |p - t| / U > cut for any send-back output of this case (strictly greater)."""
    return any(
        abs(case.predictions[o] - case.truths[o]) / case.u[o]
        > rule.badly_wrong_cut_u[o]
        for o in rule.send_back_outputs
    )


def _send_back(rule, cases):
    n = len(cases)
    wrong = [badly_wrong(rule, case) for case in cases]
    flags = [case.answer.flag for case in cases]
    b = sum(wrong)
    f = sum(flags)
    caught = sum(w and g for w, g in zip(wrong, flags))
    missed = b - caught
    loss = (rule.miss_cost * missed + rule.send_back_cost * f) / n
    never = rule.miss_cost * b / n
    oracle = rule.send_back_cost * b / n
    raw = (never - loss) / (never - oracle) if b else None
    return {
        "n": n,
        "flagged": f,
        "flag_rate": f / n,
        "badly_wrong": b,
        "caught": caught,
        "missed": missed,
        "false_alarms": f - caught,
        "loss": loss,
        "loss_never_flag": never,
        "loss_oracle": oracle,
        "send_back_skill_raw": raw,
        "send_back_skill": None if raw is None else _clip01(raw),
    }


def report(rule, cases):
    """T3-T6: the custody report of one model's self-trust over one read set. Report only: no score reads it.

    Private (custody) material: it carries truth-derived counts. Miners see only `public` of it, if V2 rules so.
    """
    check(rule)
    _require(type(cases) in (list, tuple), "self_trust_cases_malformed")
    _require(all(isinstance(c, TrustCase) for c in cases), "self_trust_cases_malformed")
    _require(len(cases) >= 1, "self_trust_read_set_empty")
    for case in cases:
        _case_values(rule, case)
    status, reason = _status(cases)
    out = {
        "schema": REPORT_SCHEMA,
        "rule": RULE_ID,
        "form": rule.form,
        "status": status,
        "reason": reason,
        "n_cases": len(cases),
        "nominal_coverage": rule.nominal_coverage,
        "outputs": None,
        "calibration_skill": None,
        "send_back": None,
        "send_back_skill": None,
        "total": None,
        "total_reason": None,
    }
    if status != SCORED:
        return out
    rows, s_cal = _calibration(rule, cases)
    sb = _send_back(rule, cases)
    s_sb = sb["send_back_skill"]
    w = rule.calibration_weight
    if s_sb is None and w < 1:
        total, why = None, "self_trust_send_back_has_no_badly_wrong_case"
    else:
        total, why = (s_cal if w == 1 else w * s_cal + (1 - w) * s_sb), None
    out.update(
        outputs=rows,
        calibration_skill=s_cal,
        send_back=sb,
        send_back_skill=s_sb,
        total=total,
        total_reason=why,
    )
    return out


def public(report_document):
    """The PROPOSED miner-facing projection of a `report` (allow-list `PUBLIC_FIELDS`): scores and rates only.

    Pending V2's disclosure ruling; no door or card calls it today. Per output it keeps the empirical coverage and the
    sharpness (median width / median error) together: coverage shown alone would rate needlessly wide bands as good.
    """
    _require(
        type(report_document) is dict
        and report_document.get("schema") == REPORT_SCHEMA,
        "self_trust_report_malformed",
    )
    rows = report_document.get("outputs") or {}
    sb = report_document.get("send_back") or {}
    projected = {
        "schema": PUBLIC_SCHEMA,
        "rule": report_document["rule"],
        "status": report_document["status"],
        "form": report_document["form"],
        "nominal_coverage": report_document["nominal_coverage"],
        "coverage": {name: row["coverage"] for name, row in rows.items()} or None,
        "sharpness": {name: row["sharpness"] for name, row in rows.items()} or None,
        "calibration_skill": report_document["calibration_skill"],
        "flag_rate": sb.get("flag_rate"),
        "send_back_skill": report_document["send_back_skill"],
        "total": report_document["total"],
    }
    _require(tuple(projected) == PUBLIC_FIELDS, "self_trust_public_fields_drifted")
    return projected


# -- A1-A3: the trust amplifier (owner TRUST-AMPLIFIER, 23 Nov 2026, OWNER_LINES.md) --------------------------------------
#
# A1  Trust skill of one ADMITTED cell (one output of one class, the admission read's cells): with the same predictions p,
#     T_cell = 1 - mean(IS(stated band) / U) / mean(IS(p - w*, p + w*) / U), where w* is the ONE constant half-width that
#     minimises the second mean on these very cases (a hindsight reference, so T never re-scores accuracy: both bands sit
#     on the same predictions). T_cell > 0: the stated uncertainty beats the best single band; 0: no better; < 0: worse.
#     A cell whose every error is 0 has no reference (w* = 0 scores 0) and gives no T_cell.
# A2  T = the mean of T_cell over the admitted cells that give one. T = 0 for a model that states no uncertainty (every
#     case absent) and for an unreadable / partial block (``invalid``): never a penalty for not taking part.
# A3  S = AD x (1 + gain T) for T >= 0 and AD x (1 + penalty max(T, -1)) for T < 0, so a negative T costs at most the
#     ``penalty`` fraction. band level, gain (lambda) and penalty are OWNER values with NO default: None is HUMAN_INPUT and
#     `amplify` refuses. Entering a version's grade is that version's scoring-path FINAL; nothing imports this today.

AMPLIFIER_FIELDS = ("band_level", "gain", "penalty")


@dataclass(frozen=True)
class TrustAmplifier:
    """The owner's three values (None = HUMAN_INPUT): the band level c the stated band is read at, the gain lambda on a
    positive T, and the penalty: the largest fractional cost of a negative T."""

    band_level: object = None
    gain: object = None
    penalty: object = None


#: The owner's values (TRUST-AMPLIFIER-VALUES, typed 2026-11-23T21:12:42Z, OWNER_LINES.md): a 90% central band
#: (interval score alpha 0.1), lambda 0.5 with T capped at 1 (at most +50%; T <= 1 holds by construction), penalty 0.1 on
#: a negative T floored at -1 (at most -10%); no uncertainty: multiplier 1.0. Any retune is a new owner line.
OWNER_AMPLIFIER = TrustAmplifier(band_level=0.9, gain=0.5, penalty=0.1)

#: The versions whose grade the amplifier enters, (challenge_id, version) -> TrustAmplifier. EMPTY: a version is added
#: only by its own scoring-path head (its registration names the amplifier, the real-king test has passed, v2 FINALs it
#: before the seal), so every other version, sealed or live, is byte-unchanged in effect (invariant 10).
VERSION_AMPLIFIERS: dict = {}


def amplifier_for(challenge_id, version):
    """The amplifier a version's registration names, or None: its grade is then exactly the A/D score."""
    return VERSION_AMPLIFIERS.get((challenge_id, version))


def _check_band_level(level):
    _require(level is not None, "self_trust_amplifier_band_level_is_human_input")
    _require(
        _number(level) and 0 < level < 1,
        "self_trust_amplifier_band_level_must_be_in_0_1",
    )


def check_amplifier(amplifier):
    """`SelfTrustRefused` unless all three owner values are present and in their domains."""
    _require(isinstance(amplifier, TrustAmplifier), "self_trust_amplifier_malformed")
    for name in AMPLIFIER_FIELDS:
        _require(
            getattr(amplifier, name) is not None,
            f"self_trust_amplifier_{name}_is_human_input",
        )
    _check_band_level(amplifier.band_level)
    _require(
        _number(amplifier.gain) and amplifier.gain >= 0,
        "self_trust_amplifier_gain_must_be_non_negative",
    )
    _require(
        _number(amplifier.penalty) and 0 <= amplifier.penalty < 1,
        "self_trust_amplifier_penalty_must_be_in_0_1",
    )


def best_constant_half_width(band_level, cases, output):
    """A1: (w*, mean IS / U) of the best constant band p +- w over ``cases`` for ``output``, exactly.

    mean IS / U = (1/n) sum_i [2 w + (2 / a) max(|e_i| - w, 0)] / U_i is convex and piecewise linear in w >= 0 with its
    kinks at the |e_i|, so its minimum is at 0 or at one of them; ties take the smallest w. Fixed order, deterministic.
    """
    _check_band_level(band_level)
    alpha = 1.0 - band_level
    points = sorted(
        (abs(case.predictions[output] - case.truths[output]), 1.0 / case.u[output])
        for case in cases
    )
    n = len(points)
    _require(n >= 1, "self_trust_read_set_empty")
    errors = [e for e, _ in points]
    tail_ev, tail_v = [0.0] * (n + 1), [0.0] * (n + 1)
    for k in range(n - 1, -1, -1):
        e, v = points[k]
        tail_ev[k] = tail_ev[k + 1] + e * v
        tail_v[k] = tail_v[k + 1] + v
    mean_v = tail_v[0] / n
    best = None
    for w in [0.0, *errors]:
        k = bisect_right(errors, w)
        value = 2.0 * w * mean_v + (2.0 / alpha) * (tail_ev[k] - w * tail_v[k]) / n
        if best is None or value < best[1]:
            best = (w, value)
    return best


def _stated_band(form, band_level, case, output):
    if form == INTERVAL:
        return case.answer.bands[output]
    half = _z(band_level) * case.answer.sigmas[output]
    p = case.predictions[output]
    return (p - half, p + half)


def trust_skill(form, band_level, cells):
    """A1-A2: T over the admitted ``cells`` = {(class, output): [TrustCase, ...]}, each case's answer read at
    ``band_level``. Returns {"status", "reason", "t", "cells": {cell: T_cell or None}}; ``t`` is 0 unless scored."""
    _require(form in FORMS, "self_trust_form_unknown")
    _check_band_level(band_level)
    _require(type(cells) is dict and len(cells) >= 1, "self_trust_cells_malformed")
    every = []
    for key, cases in cells.items():
        _require(
            type(key) is tuple and len(key) == 2 and type(key[1]) is str,
            "self_trust_cell_key_malformed",
        )
        _require(
            type(cases) in (list, tuple) and len(cases) >= 1,
            "self_trust_cases_malformed",
        )
        for case in cases:
            _require(isinstance(case, TrustCase), "self_trust_cases_malformed")
            for field in ("predictions", "truths", "u"):
                _require(
                    type(getattr(case, field)) is dict
                    and key[1] in getattr(case, field),
                    f"self_trust_case_{field}_missing_an_output",
                )
            _require(_number(case.truths[key[1]]), "self_trust_truth_not_a_number")
            _require(
                _number(case.u[key[1]]) and case.u[key[1]] > 0,
                "self_trust_u_must_be_positive",
            )
            _require(
                _number(case.predictions[key[1]]),
                "self_trust_prediction_not_a_valid_answer",
            )
        every.extend(cases)
    status, reason = _status(every)
    out = {"status": status, "reason": reason, "t": 0.0, "cells": None}
    if status != SCORED:
        return out
    if any(case.answer.form != form for case in every):
        out.update(status=INVALID, reason="self_trust_block_form_differs")
        return out
    per_cell = {}
    for key in sorted(cells):
        output, cases = key[1], cells[key]
        _, reference = best_constant_half_width(band_level, cases, output)
        if reference <= 0:
            per_cell[key] = None
            continue
        scores = []
        for case in cases:
            lo, hi = _stated_band(form, band_level, case, output)
            y = case.truths[output]
            scores.append(interval_score(lo, hi, y, band_level) / case.u[output])
        per_cell[key] = 1.0 - (math.fsum(scores) / len(cases)) / reference
    given = [v for v in per_cell.values() if v is not None]
    out.update(cells=per_cell, t=math.fsum(given) / len(given) if given else 0.0)
    return out


def amplify(ad_score, t, amplifier):
    """A3: the version's A/D score times the trust factor. Refuses until all three owner values are set."""
    check_amplifier(amplifier)
    _require(_number(ad_score), "self_trust_amplifier_score_not_a_number")
    _require(_number(t) and t <= 1.0, "self_trust_amplifier_t_out_of_range")
    if t >= 0:
        return ad_score * (1.0 + amplifier.gain * t)
    return ad_score * (1.0 + amplifier.penalty * max(t, -1.0))
