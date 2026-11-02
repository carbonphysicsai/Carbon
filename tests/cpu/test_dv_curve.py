"""DV-CURVE-01 step 1 (scripts/dev/exam_reads/dv_curve.py): the engineer's-shortcut anchor.

Claims: the port of the receipted king-audit arm ``coarse_screen_then_verify`` reproduces the audit's own numbers (live, against the
receipted file when it is present, by its sha256); the equal-wall counts are the audit's; a target with no verified feasible design keeps
the median anchor and is counted; a degenerate target (shortcut = optimum) is dropped and counted per class; classes falling below N are
flagged; the shortcut's own q under the median anchor; a Challenge without a registered shortcut is refused.
"""

from __future__ import annotations

import hashlib
import importlib.util
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

READS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads"
sys.path.insert(0, str(READS))

import dv_curve

from carbon.scoring import pool_grader

AUDIT = (
    Path(__file__).resolve().parents[2]
    / "codex-queue"
    / "reports"
    / "KING_AUDIT_F08_PAYLOAD_20261101"
    / "king_audit_analyze.py"
)
AUDIT_SHA256 = "dbc49e2537f90940c1b0f6537b4d0fa6415350b0d045477352ff5d601e75385a"
F08 = ("f08-ribbed-bracket", "1.7")
WORST, MASS, STATIC = "worst_dynamic_mm_per_n", "cad_mass_kg", "static_tip_mm_per_n"
LIMITS = ((WORST, "<=", 0.15), (MASS, "<=", 0.45), (STATIC, "<=", 0.03))


def _menu(n=24, seed=3):
    """A synthetic F08 menu with no ties in the coarse worst dynamic (the audit breaks ties by sample order, the port by design)."""
    draw = random.Random(seed)
    menu = []
    for i in range(n):
        worst = 0.10 + 0.08 * draw.random()
        menu.append(
            {
                "truth": {
                    WORST: worst,
                    MASS: 0.35 + 0.15 * draw.random(),
                    STATIC: 0.02 + 0.015 * draw.random(),
                },
                "coarse_worst": worst * (1.0 + 0.05 * (draw.random() - 0.5)) + 1e-9 * i,
                "wall": {"h1.7": 1800.0 + i, "h3": 120.0 + i, "h2.25": 400.0},
                "pred": {},
            }
        )
    return menu


def _spec(menu, mass_mult, dyn_mult, objective):
    """The menu as one pool target for the port: every design queryable, the audit's feasibility at the variant's limits."""

    def feasible(truth):
        for output, kind, bound in LIMITS:
            bound *= (
                mass_mult if output == MASS else dyn_mult if output == WORST else 1.0
            )
            if not truth[output] <= bound:
                return False
        return True

    limits = tuple(
        pool_grader.Limit(
            o, k, b * (mass_mult if o == MASS else dyn_mult if o == WORST else 1.0)
        )
        for o, k, b in LIMITS
    )
    return SimpleNamespace(
        target_id="t",
        queryable=tuple(range(len(menu))),
        truths=tuple(r["truth"] for r in menu),
        feasible=tuple(feasible(r["truth"]) for r in menu),
        limits=limits,
        objective=objective,
        sign=-1.0,
        s_ref=None,
        s_low=None,
    )


def test_the_port_reproduces_the_receipted_audits_coarse_screen_then_verify_numbers():
    if not AUDIT.is_file():
        pytest.skip(
            "the receipted king-audit payload is custody-side, not in this checkout"
        )
    assert hashlib.sha256(AUDIT.read_bytes()).hexdigest() == AUDIT_SHA256
    spec_ = importlib.util.spec_from_file_location("king_audit_analyze", AUDIT)
    audit = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(audit)
    menu = _menu()
    reference = audit.menu_race(menu, {}, "king", LIMITS, random.Random(11))["arms"][
        "coarse_screen_then_verify"
    ]
    # replay the audit's rng consumption: per budget, per usable variant, 2000 solver-order permutations, then 200 coarse draws
    import statistics

    walls = sorted(r["wall"]["h1.7"] for r in menu)
    t_ref = statistics.median(walls)
    t_coarse = statistics.median(r["wall"]["h3"] for r in menu)
    rng = random.Random(11)
    coarse = {i: {WORST: r["coarse_worst"]} for i, r in enumerate(menu)}
    for k in audit.BUDGETS:
        means, misses = [], []
        for objective, mass_mult, dyn_mult in audit.VARIANTS:
            spec = _spec(
                menu,
                mass_mult,
                dyn_mult,
                WORST if objective == "O1_min_worst" else MASS,
            )
            good = [i for i in spec.queryable if spec.feasible[i]]
            if len(good) < 2:
                continue
            best = min(menu[i]["truth"][spec.objective] for i in good)
            scale = next(b for o, _, b in LIMITS if o == spec.objective)
            for _ in range(audit.SOLVER_ORDERS):
                rng.sample(menu, len(menu))
            _verify_n, screen_n = dv_curve.screen_counts(k, t_ref, t_coarse, len(menu))
            if screen_n >= len(
                menu
            ):  # the audit still samples a full permutation per draw: advance the stream alike
                for _ in range(dv_curve.DRAWS):
                    rng.sample(menu, screen_n)
                result = dv_curve.shortcut_s_low(
                    F08, spec, coarse, k, t_ref, t_coarse, random.Random(0)
                )
            else:
                result = dv_curve.shortcut_s_low(
                    F08, spec, coarse, k, t_ref, t_coarse, rng
                )
            means.append(
                None if result["s_low"] is None else (-result["s_low"] - best) / scale
            )
            misses.append(result["miss_fraction"])
        mine = audit.summarize(means, misses=misses)
        assert mine == reference[str(k)], k


def test_the_equal_wall_counts_are_the_audits():
    assert dv_curve.screen_counts(4, 1800.0, 120.0, 1000) == (1, 45)
    assert dv_curve.screen_counts(8, 1800.0, 120.0, 1000) == (2, 90)
    assert dv_curve.screen_counts(16, 1800.0, 120.0, 30) == (
        4,
        30,
    )  # capped at the menu


def _target(tid, truths, feasible, shell=None):
    return SimpleNamespace(
        target_id=tid,
        queryable=tuple(range(len(truths))),
        truths=tuple({WORST: w, MASS: 0.4} for w in truths),
        feasible=tuple(feasible),
        limits=(
            pool_grader.Limit(WORST, "<=", 0.15),
            pool_grader.Limit(MASS, "<=", 0.45),
        ),
        objective=WORST,
        sign=-1.0,
        s_ref=-min(w for w, f in zip(truths, feasible) if f),
        s_low=-sorted(w for w, f in zip(truths, feasible) if f)[
            len([f for f in feasible if f]) // 2
        ],
        shell=shell,
        extended=shell is not None,
    )


def test_anchors_count_no_feasible_and_degenerate_targets_per_class_and_flag_classes_below_n():
    covering = {"walls": (100.0, 10.0)}  # B x 100 s buys every screen: deterministic
    best_found = _target(
        "a", [0.10, 0.12, 0.14], [True, True, True]
    )  # the screen finds the optimum: degenerate
    none_feasible = _target("b", [0.20, 0.12, 0.14], [False, True, True])
    coarse = {
        "a": {0: {WORST: 0.10}, 1: {WORST: 0.12}, 2: {WORST: 0.14}},
        "b": {
            0: {WORST: 0.10},
            1: {WORST: 0.30},
            2: {WORST: 0.31},
        },  # the coarse rung ranks the infeasible design first
    }
    replace, counts = dv_curve.anchors(
        F08,
        [best_found, none_feasible],
        coarse,
        4,
        *covering["walls"],
        random.Random(1),
        pool_grader.region_class,
    )
    assert counts == {
        "in_train": {
            "targets": 2,
            "shortcut_anchor": 0,
            "no_verified_feasible": 1,
            "degenerate": 1,
        }
    }
    assert replace == {"a": None}  # b keeps the median anchor; a is dropped
    assert dv_curve.classes_below_floor(counts, 3) == ["in_train"]


def test_the_shortcuts_own_q_under_the_median_anchor_and_an_unregistered_challenge_is_refused():
    spec = _target("a", [0.10, 0.12, 0.14], [True, True, True])
    assert dv_curve.shortcut_q_under_median(spec, spec.s_ref) == 1.0
    assert dv_curve.shortcut_q_under_median(spec, spec.s_low) == 0.0
    assert dv_curve.shortcut_q_under_median(spec, None) is None
    with pytest.raises(dv_curve.CurveRefused, match="no_registered_shortcut"):
        dv_curve.shortcut_s_low(
            ("electric-motor-magnetics", "1.6"),
            spec,
            {},
            4,
            100.0,
            10.0,
            random.Random(1),
        )


def _limited_spec(tid, truths, objective, limits, sign=-1.0):
    feasible = tuple(
        all(lim.margin(t[lim.output]) >= 0 for lim in limits) for t in truths
    )
    values = sorted(sign * t[objective] for t, f in zip(truths, feasible) if f)
    return SimpleNamespace(
        target_id=tid,
        queryable=tuple(range(len(truths))),
        truths=tuple(truths),
        feasible=feasible,
        limits=tuple(limits),
        objective=objective,
        sign=sign,
        s_ref=values[-1],
        s_low=values[len(values) // 2],
        shell=None,
        extended=False,
    )


def test_the_shortcuts_are_keyed_by_challenge_and_version():
    spec = _target("a", [0.10, 0.12, 0.14], [True, True, True])
    for key, code in (
        (("f08-ribbed-bracket", "1.6"), "no_registered_shortcut_for_the_challenge"),
    ):
        with pytest.raises(dv_curve.CurveRefused) as refused:
            dv_curve.shortcut_s_low(key, spec, {}, 4, 100.0, 10.0, random.Random(1))
        assert refused.value.code == code
    # F08 1.7 keeps its screens and still refuses the whole read for an objective it does not screen
    assert dv_curve.SHORTCUT_SCREENS[F08] == {"coarse": (WORST,), "exact": (MASS,)}
    other = SimpleNamespace(**{**vars(spec), "objective": STATIC})
    with pytest.raises(
        dv_curve.CurveRefused, match="shortcut_does_not_screen_the_objective"
    ):
        dv_curve.shortcut_s_low(F08, other, {}, 4, 100.0, 10.0, random.Random(1))


def test_rb20_screens_every_solved_output_at_h3_and_the_mass_exactly():
    rb = ("f08-ribbed-bracket", "2.0")
    stress = "static_fillet_stress_mpa_per_n"
    limits = (
        pool_grader.Limit(WORST, "<=", 0.15),
        pool_grader.Limit(stress, "<=", 2.0),
    )
    truths = [{WORST: 0.10, MASS: 0.4, stress: 1.0}, {WORST: 0.12, MASS: 0.4, stress: 1.5},
              {WORST: 0.14, MASS: 0.4, stress: 1.2}]  # fmt: skip
    spec = _limited_spec("r", truths, WORST, limits)
    # the coarse rung says design 0 breaks the stress limit (every solved output is screened), so the screen verifies design 1
    coarse = {
        0: {WORST: 0.10, stress: 2.5},
        1: {WORST: 0.12, stress: 1.4},
        2: {WORST: 0.14, stress: 1.1},
    }
    result = dv_curve.shortcut_s_low(rb, spec, coarse, 4, 100.0, 10.0, random.Random(1))
    assert result["s_low"] == -0.12 and result["verify_n"] == 1
    # under F08 1.7's screens the stress is not screened: design 0 is verified
    assert (
        dv_curve.shortcut_s_low(F08, spec, coarse, 4, 100.0, 10.0, random.Random(1))[
            "s_low"
        ]
        == -0.10
    )


def test_bt30_screens_the_peak_only_and_a_target_it_cannot_screen_refuses_alone():
    bt = ("f02", "3.0")
    peak, energy = "peak_top_c", "extra_energy_j"
    limits = (pool_grader.Limit(peak, "<=", 95.0),)
    truths = [
        {peak: 90.0, energy: 5.0},
        {peak: 92.0, energy: 3.0},
        {peak: 99.0, energy: 1.0},
    ]
    on_peak = _limited_spec("p", truths, peak, limits)
    on_energy = _limited_spec("e", truths, energy, limits)
    coarse = {"p": {0: {peak: 93.0}, 1: {peak: 91.0}, 2: {peak: 97.0}}, "e": {}}
    replace, counts = dv_curve.anchors(
        bt,
        [on_peak, on_energy],
        coarse,
        4,
        100.0,
        10.0,
        random.Random(1),
        lambda s: "in_train",
    )
    # the modal-sum ranks design 1 first; its exam truth is feasible: the anchor is -92
    assert replace == {"p": -92.0, "e": None}
    assert counts == {"in_train": {"targets": 2, "shortcut_anchor": 1, "no_verified_feasible": 0, "degenerate": 0,
                                   "refused": 1}}  # fmt: skip
    assert dv_curve.classes_below_floor(counts, 2) == ["in_train"]
    assert dv_curve.shortcut_s_low(
        bt, on_energy, {}, 4, 100.0, 10.0, random.Random(1)
    ) == {
        "s_low": None,
        "refused": "shortcut_does_not_screen_the_objective",
    }
    assert dv_curve.shortcut_q_under_median(on_energy, None) is None


def test_cooling18_screens_cool_adv_01s_three_outputs_and_an_unpredicted_target_refuses_alone():
    cooling = ("chip-cold-plate", "1.8")
    assert dv_curve.SHORTCUT_SCREENS[cooling] == {
        "coarse": ("die_peak_c", "hydraulic_w", "pressure_drop_pa"),
        "exact": (),
        "per_target_refusal": True,
    }
    peak, dp, other = "die_peak_c", "pressure_drop_pa", "flow_uniformity"
    limits = (pool_grader.Limit(dp, "<=", 5000.0),)
    truths = [
        {peak: 80.0, dp: 4000.0, other: 0.9},
        {peak: 75.0, dp: 4500.0, other: 0.8},
        {peak: 70.0, dp: 6000.0, other: 0.7},
    ]
    spec = _limited_spec("c", truths, peak, limits)  # minimise the die peak (sign -1)
    # COOL-ADV-01 says design 2 breaks the pressure-drop limit and design 1 is the coolest feasible: it is verified
    coarse = {
        0: {peak: 81.0, dp: 3900.0},
        1: {peak: 74.0, dp: 4400.0},
        2: {peak: 69.0, dp: 6100.0},
    }
    result = dv_curve.shortcut_s_low(
        cooling, spec, coarse, 4, 100.0, 10.0, random.Random(1)
    )
    assert result["s_low"] == -75.0 and result["verify_n"] == 1
    unpredicted = SimpleNamespace(**{**vars(spec), "objective": other})
    assert dv_curve.shortcut_s_low(
        cooling, unpredicted, {}, 4, 100.0, 10.0, random.Random(1)
    ) == {"s_low": None, "refused": "shortcut_does_not_screen_the_objective"}
