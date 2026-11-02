"""DV-CURVE-01 step 1 (EXAM_QUALIFICATION_SYSTEM §3b): the engineer's-shortcut anchor of D, per target and per candidate budget B.

CUSTODY / SCRATCH only (the ``dvcurve`` mode of `q3_q8_whatif.py` grades with it); nothing here is imported by a grader.

The shortcut is the RECEIPTED king-audit arm ``coarse_screen_then_verify`` (KING_AUDIT_F08_PAYLOAD_20261101/king_audit_analyze.py,
sha256 dbc49e2537f90940c1b0f6537b4d0fa6415350b0d045477352ff5d601e75385a, `menu_race.coarse_order` + `verify`), ported here because
the audit defines it inside `menu_race` (a parity test pins this port to the audit's own output). Its EQUAL-WALL rule (Validator
11-01, ruling 2): at budget B the shortcut has B x t_ref of wall; it verifies verify_n = max(1, B // 4) designs at the exam rung and
spends the rest on coarse screens at t_coarse each; it ranks the screened designs cheap-feasible first, then by the cheap objective,
ties by design order (the audit breaks ties by its sample order; this port uses design order, as ruled), and verifies the first
verify_n. t_ref and t_coarse are the measured rung-record medians (inputs). When the screens cannot cover the menu, the screened
designs are a seeded sample and s_low is the mean over ``draws`` samples (SOLVER_ORDERS // 10 = 200, the audit's count), seed recorded.

s_low(B), in the grader's sign x objective: the best FEASIBLE verified value (the pool's own truths and feasibility). No feasible design
among the verified ones: "no verified feasible" (counted; the target keeps the median anchor). s_low(B) >= s_ref: DEGENERATE (the
shortcut finds the optimum; dropped from the D means, never set to 0; counted per class).

What the cheap method screens on is the registered one, per Challenge AND version (`SHORTCUT_SCREENS`; the cheap methods of the
owner's record 5328e97c, registered by the Validator 11-01): F08 1.7 = the coarse h = 3 mm worst dynamic compliance against the dynamic
limit, and the EXACT CAD mass against the mass limit (geometry, no solve); RB 2.0 = the h = 3 rung of the 2.0 registered ladder at the
base fillet mesh, every solved target output coarse, the CAD mass exact (its single-rung parity is checked first, outside this module);
BT 3.0 = the modal-sum (adversary 1 of f02_closed_form_gate.py, its own defaults, fit on public TRAIN) predicting the peak only, against
the target's own limits: a target whose objective it does not predict REFUSES (counted per class, no anchor claimed, dropped from the
D means); Cooling 1.8 = COOL-ADV-01 (the choice fixed, Validator 17:51 / 04:09: rev 3, SUMS 7e30282a) predicting die_peak_c,
hydraulic_w and pressure_drop_pa against the target's own limits, a target whose objective it does not predict REFUSING alone. The coarse
rows (``coarse``) are those cheap outputs per design, produced outside. A Challenge version without a registered shortcut here is
refused, never approximated.
"""

from __future__ import annotations

import math
import statistics

#: The audit's coarse-screen draw count (king_audit_analyze.SOLVER_ORDERS // 10).
DRAWS = 2000 // 10
#: ``coarse`` = every output the target's truths carry except the exact ones (RB 2.0: "every solved target output").
EVERY_SOLVED = "every_solved_target_output"
#: Per (Challenge, version): the outputs the registered cheap method screens on, and which of them it measures (``coarse``) or takes
#: exactly from the pool's own truth (``exact``, geometry); ``per_target_refusal``: a target whose objective it does not screen refuses
#: alone instead of the whole read. None: registered, but its choice of method is not fixed yet (refused).
SHORTCUT_SCREENS = {
    ("f08-ribbed-bracket", "1.7"): {
        "coarse": ("worst_dynamic_mm_per_n",),
        "exact": ("cad_mass_kg",),
    },
    ("f08-ribbed-bracket", "2.0"): {"coarse": EVERY_SOLVED, "exact": ("cad_mass_kg",)},
    ("f02", "3.0"): {
        "coarse": ("peak_top_c",),
        "exact": (),
        "per_target_refusal": True,
    },
    ("chip-cold-plate", "1.8"): {
        "coarse": ("die_peak_c", "hydraulic_w", "pressure_drop_pa"),
        "exact": (),
        "per_target_refusal": True,
    },
}


class CurveRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise CurveRefused(code)


def screen_counts(budget_b, t_ref, t_coarse, menu_size):
    """``(verify_n, screen_n)`` under the equal-wall rule: B x t_ref of wall, verify_n exam-rung solves, the rest h3 screens."""
    _need(type(budget_b) is int and budget_b >= 1, "budget_b")
    _need(t_ref > 0 and t_coarse > 0, "rung_walls")
    verify_n = max(1, budget_b // 4)
    screen_n = max(
        0, min(menu_size, int((budget_b * t_ref - verify_n * t_ref) // t_coarse))
    )
    return verify_n, screen_n


def _screens(key):
    """The registered screens of ``key`` = (Challenge id, version), or a refusal."""
    _need(key in SHORTCUT_SCREENS, "no_registered_shortcut_for_the_challenge")
    screens = SHORTCUT_SCREENS[key]
    _need(screens is not None, "shortcut_method_choice_not_fixed")
    return screens


def _coarse_names(screens, spec, index):
    if screens["coarse"] == EVERY_SOLVED:
        return tuple(n for n in spec.truths[index] if n not in screens["exact"])
    return screens["coarse"]


def _cheap(key, spec, coarse_row, index):
    """``(cheap-feasible, cheap value)`` of one design: the registered screens only (coarse outputs from the cheap method, the exact
    ones from the pool's own truth, which is geometry), against the target's own limits; the value is sign x the objective as screened.
    """
    screens = _screens(key)
    values = {}
    for name in _coarse_names(screens, spec, index):
        value = coarse_row.get(name) if coarse_row is not None else None
        values[name] = (
            value if (type(value) in (int, float) and math.isfinite(value)) else None
        )
    for name in screens["exact"]:
        values[name] = spec.truths[index][name]
    ok = True
    for limit in spec.limits:
        if limit.output in values:
            value = values[limit.output]
            ok = ok and value is not None and limit.margin(value) >= 0
    objective = values.get(spec.objective)
    _need(spec.objective in values, "shortcut_does_not_screen_the_objective")
    cheap_value = None if objective is None else spec.sign * objective
    return ok, cheap_value


def _verified_best(spec, picked):
    """The best FEASIBLE exam-truth value among the verified designs, in sign x objective; None when none is feasible."""
    values = [
        spec.sign * spec.truths[i][spec.objective] for i in picked if spec.feasible[i]
    ]
    return max(values) if values else None


def shortcut_s_low(key, spec, coarse, budget_b, t_ref, t_coarse, rng, *, draws=DRAWS):
    """The shortcut's anchor for one target at budget B: ``{"s_low", "sampled", "miss_fraction", "verify_n", "screen_n"}``;
    ``key`` = (Challenge id, version). ``coarse`` maps a design index to its cheap outputs (None: no coarse result; it ranks last, as
    unobserved). A target whose objective the method does not screen, where that refuses per target: ``{"s_low": None, "refused":
    code}``.
    """
    menu = list(spec.queryable)
    _need(menu, "target_has_no_queryable_designs")
    screens = _screens(key)
    if spec.objective not in screens["exact"] and spec.objective not in _coarse_names(
        screens, spec, menu[0]
    ):
        _need(
            screens.get("per_target_refusal") is True,
            "shortcut_does_not_screen_the_objective",
        )
        return {"s_low": None, "refused": "shortcut_does_not_screen_the_objective"}
    verify_n, screen_n = screen_counts(budget_b, t_ref, t_coarse, len(menu))

    def rank(index):
        ok, value = _cheap(key, spec, coarse.get(index), index)
        return (0 if ok else 1, -value if value is not None else math.inf, index)

    def one(screened):
        return _verified_best(spec, sorted(screened, key=rank)[:verify_n])

    if screen_n >= len(menu):
        value = one(menu)
        return {"s_low": value, "sampled": False, "miss_fraction": 0.0 if value is not None else 1.0,
                "verify_n": verify_n, "screen_n": screen_n}  # fmt: skip
    values = [one(rng.sample(menu, screen_n)) for _ in range(draws)]
    hits = [v for v in values if v is not None]
    return {
        "s_low": statistics.fmean(hits) if hits else None,
        "sampled": True,
        "miss_fraction": (len(values) - len(hits)) / len(values),
        "verify_n": verify_n,
        "screen_n": screen_n,
    }


def anchors(
    key,
    specs,
    coarse_by_target,
    budget_b,
    t_ref,
    t_coarse,
    rng,
    region_class,
    *,
    draws=DRAWS,
):
    """Per target at budget B: the shortcut anchor and its fate. Returns ``(s_low_by_target, counts)``: the anchors that REPLACE the
    median (only targets with a verified feasible design that is not degenerate) and per-class counts of each outcome (``refused``
    only where a target refused).
    """
    replace, counts = {}, {}
    for spec in specs:
        cls = region_class(spec)
        row = counts.setdefault(
            cls,
            {
                "targets": 0,
                "shortcut_anchor": 0,
                "no_verified_feasible": 0,
                "degenerate": 0,
            },
        )
        row["targets"] += 1
        result = shortcut_s_low(
            key,
            spec,
            coarse_by_target.get(spec.target_id, {}),
            budget_b,
            t_ref,
            t_coarse,
            rng,
            draws=draws,
        )
        if "refused" in result:
            row["refused"] = (
                row.get("refused", 0) + 1
            )  # no anchor claimed: dropped from the D means
            replace[spec.target_id] = None
        elif result["s_low"] is None:
            row["no_verified_feasible"] += 1  # keeps the median anchor (ruling 3)
        elif result["s_low"] >= spec.s_ref:
            row["degenerate"] += 1  # dropped from the D means, never 0 (ruling 4)
            replace[spec.target_id] = None
        else:
            row["shortcut_anchor"] += 1
            replace[spec.target_id] = result["s_low"]
    return replace, counts


def classes_below_floor(counts, floor_n):
    """The region classes whose usable targets (shortcut anchor or median kept) fall below the registered floor N."""
    return sorted(
        cls
        for cls, row in counts.items()
        if row["targets"] - row["degenerate"] - row.get("refused", 0) < floor_n
    )


def shortcut_q_under_median(spec, s_shortcut):
    """The shortcut's own q under the MEDIAN anchor (ruling 5): how far the engineer's screen already gets, in the grader's q."""
    if s_shortcut is None:
        return None
    return min(1.0, max(0.0, (s_shortcut - spec.s_low) / (spec.s_ref - spec.s_low)))
