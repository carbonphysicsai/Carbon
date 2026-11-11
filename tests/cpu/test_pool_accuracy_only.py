"""R1: the ACCURACY-ONLY target kind (Lead + mc-exam-B 11 Nov; a 1.8 version's D is the sealed menu and its A the physics
score, so its targets carry scored cases only, with no optimisation problem).

Claims:
- `build_accuracy_target`: every case is in the reserved slice, none is queryable; >= 1 case; no objective, limits,
  reference, start or seed; no within-U exclusion; an extended target has EVERY case in its shell; its digest is marked
  and never equals a multi-design target's;
- a pool source or pool document carrying an optimisation field beside ``accuracy_only`` is REFUSED, never ignored, and a
  pool document round-trips exactly (a tampered one refuses);
- the optimiser never sees one (`grade_set`, `attach_variants` refuse);
- the official grade: a version's targets are all accuracy-only or none, and all accuracy-only needs a menu AND a physics
  rule; then A per set is the physics family value, D is the menu D capped by C, the in-range gate still decides, the SE
  basis recomposes the graded total, and the public result shows nothing new;
- every other version is unchanged (the existing pool suites, untouched).

Every target, case, key and value here is a SYNTHETIC fixture (the toy targets of test_pool_plugin).
"""

from __future__ import annotations

import dataclasses
import json
import math
import statistics
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import ARGUMENTS, CEILING, FAST, exam_rows, toy_binding
from test_pool_menu import KEY, _rowcheck, _tasks
from test_pool_menu import _rule as menu_rule
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)
from test_pool_physics_score import _registered, _sets
from test_pool_plugin import SHELL, fake_measure, good_serve, toy_target

from carbon.scoring import pool_exam, pool_grader, pool_menu, pool_plugin
from carbon.scoring import pool_physics_score as pps


def _accuracy_only(target, shell=None):
    """A toy target's reserved slice as an accuracy-only target (the same cases, truths and U)."""
    return pool_grader.build_accuracy_target(
        target_id=target.target_id,
        conditions=target.conditions,
        outputs=target.outputs,
        u=target.u,
        box=target.box,
        designs=[list(target.designs[i]) for i in target.agen],
        truths=[dict(target.truths[i]) for i in target.agen],
        shell=shell,
    )


def _source(target, **over):
    document = {
        "design_names": list(toy_binding().design_names),
        "target_id": target.target_id,
        "conditions": target.conditions,
        "accuracy_only": True,
        "outputs": list(target.outputs),
        "u": target.u,
        "box": [list(b) for b in target.box],
        "designs": [list(target.designs[i]) for i in target.agen],
        "truths": [dict(target.truths[i]) for i in target.agen],
    }
    document.update(over)
    return document


# ---------------------------------------------------------------- the target kind


def test_every_case_is_reserved_none_queryable_and_there_is_no_optimisation_problem():
    base = toy_target("t0", 7)
    spec = _accuracy_only(base)
    n = len(base.agen)
    assert spec.accuracy_only is True and base.accuracy_only is False
    assert spec.agen == tuple(range(n)) and spec.queryable == ()
    assert spec.objective is None and spec.limits == () and spec.reference is None
    assert spec.start == () and spec.seed is None and spec.excluded == 0
    assert spec.designs == tuple(tuple(base.designs[i]) for i in base.agen)
    # one case is enough (a one-design duty)
    one = pool_grader.build_accuracy_target(
        target_id="one",
        conditions=base.conditions,
        outputs=base.outputs,
        u=base.u,
        box=base.box,
        designs=[list(base.designs[0])],
        truths=[dict(base.truths[0])],
    )
    assert one.agen == (0,) and one.queryable == ()


def test_no_within_u_exclusion_and_the_digest_is_marked():
    base = toy_target("t0", 7)
    spec = _accuracy_only(base)
    assert spec.pool_size == len(base.agen)  # no limits: nothing dropped
    # the same cases as a multi-design target's pool can never share its digest
    assert spec.digest != base.digest
    assert spec.digest != _accuracy_only(toy_target("t0", 8)).digest


@pytest.mark.parametrize(
    "change, code",
    [
        (
            {"designs": [], "truths": []},
            "accuracy_only_target_needs_matching_designs_and_truths",
        ),
        ({"truths": None}, "accuracy_only_target_needs_matching_designs_and_truths"),
        ({"u": {"f": 0.1}}, "u_must_cover_exactly_the_outputs"),
        ({"box": [[0.0, 1.0]]}, "design_must_match_the_box_and_be_finite"),
        ({"public": "no"}, "public_must_be_a_bool"),
    ],
)
def test_malformed_material_refuses(change, code):
    base = toy_target("t0", 7)
    kwargs = {
        "target_id": "t0",
        "conditions": base.conditions,
        "outputs": base.outputs,
        "u": base.u,
        "box": base.box,
        "designs": [list(base.designs[i]) for i in base.agen],
        "truths": [dict(base.truths[i]) for i in base.agen],
    }
    kwargs.update(change)
    if kwargs["truths"] is None:
        kwargs["truths"] = [dict(base.truths[0])]
    with pytest.raises(pool_grader.PoolRefused, match=code):
        pool_grader.build_accuracy_target(**kwargs)


def test_an_extended_target_needs_every_case_in_its_shell():
    extended = toy_target("e0", 9, shell=SHELL)
    spec = _accuracy_only(extended, shell=SHELL)
    assert spec.extended
    # a case outside the shell (both inputs below the extension) refuses, even though no case is queryable
    inside = pool_grader.build_accuracy_target(
        target_id="e1",
        conditions=extended.conditions,
        outputs=extended.outputs,
        u=extended.u,
        box=extended.box,
        designs=[list(extended.designs[0])],
        truths=[dict(extended.truths[0])],
        shell=SHELL,
    )
    assert inside.extended
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_case_outside_the_ood_shell"
    ):
        pool_grader.build_accuracy_target(
            target_id="e2",
            conditions=extended.conditions,
            outputs=extended.outputs,
            u=extended.u,
            box=extended.box,
            designs=[list(extended.designs[0]), [0.05, 0.05]],
            truths=[dict(extended.truths[0]), dict(extended.truths[1])],
            shell=SHELL,
        )


# ---------------------------------------------------------------- pool source + pool document


def test_the_pool_source_builds_it_and_refuses_any_optimisation_field():
    base = toy_target("t0", 7)
    spec = pool_plugin.spec_from_source(_source(base), toy_binding())
    assert spec == _accuracy_only(base)
    # agen, if given, must be every case
    n = len(base.agen)
    assert (
        pool_plugin.spec_from_source(
            _source(base, agen=list(range(n))), toy_binding()
        ).digest
        == spec.digest
    )
    bad = [
        {"agen": list(range(n - 1))},
        {"accuracy_only": "true"},
        {"accuracy_only": False},
        *({field: None} for field in sorted(pool_grader.ACCURACY_ONLY_ABSENT)),
    ]
    for change in bad:
        with pytest.raises(
            pool_plugin.PluginRefused, match="accuracy_only_pool_source_malformed"
        ):
            pool_plugin.spec_from_source(_source(base, **change), toy_binding())


def test_the_pool_document_round_trips_and_a_tampered_one_refuses():
    spec = _accuracy_only(toy_target("e0", 9, shell=SHELL), shell=SHELL)
    document = json.loads(json.dumps(pool_grader.dump_pool(spec)))
    assert document["accuracy_only"] is True
    assert not (pool_grader.ACCURACY_ONLY_ABSENT & set(document))
    again = pool_grader.load_pool(document)
    assert again == spec and pool_grader.dump_pool(again) == document
    tampered = json.loads(json.dumps(document))
    tampered["truths"][0]["f"] += 1.0
    with pytest.raises(
        pool_grader.PoolRefused, match="pool_digest_does_not_match_its_content"
    ):
        pool_grader.load_pool(tampered)
    for extra in ({"objective": "f"}, {"seed": 1}, {"excluded": 0}):
        with pytest.raises(
            pool_grader.PoolRefused, match="accuracy_only_pool_document_malformed"
        ):
            pool_grader.load_pool({**document, **extra})
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_pool_document_malformed"
    ):
        pool_grader.load_pool({**document, "accuracy_only": 1})
    # a multi-design target's document is unchanged: no accuracy_only key, and it loads as before
    plain = pool_grader.dump_pool(toy_target("t0", 7))
    assert "accuracy_only" not in plain
    assert pool_grader.load_pool(json.loads(json.dumps(plain))).accuracy_only is False


def test_the_optimiser_never_sees_an_accuracy_only_target():
    from test_pool_exam import POLICIES

    spec = _accuracy_only(toy_target("t0", 7))
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_target_has_no_optimizer_pick"
    ):
        pool_grader.grade_set(
            [spec], lambda c, d: [], POLICIES.optimizer, POLICIES.honesty
        )
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_target_has_no_variants"
    ):
        pool_grader.attach_variants(spec, {"limits": ["g"], "shifts": [0.1]}, [{}])


# ---------------------------------------------------------------- the official grade (measure_pool)


def _accuracy_sets(per_class=1):
    return tuple(
        tuple(_accuracy_only(t, shell=SHELL if t.extended else None) for t in group)
        for group in _sets(per_class)
    )


AUTO = object()


def _grade(
    the_sets, *, threshold=2.5, menu=True, physics=True, serve=good_serve, kind=AUTO
):
    policies, material = _registered(the_sets, threshold)
    if kind is AUTO:
        # the registration names the kind of the material it grades (Validator-2B M-1)
        every = all(t.accuracy_only for group in the_sets for t in group)
        kind = "accuracy_only" if every else None
    policies = dataclasses.replace(
        policies, physics=dataclasses.replace(policies.physics, target_kind=kind)
    )
    if menu:
        policies = dataclasses.replace(policies, menu=menu_rule())
    if not physics:
        policies = dataclasses.replace(policies, physics=None)
        material = {k: v for k, v in material.items() if k != "scoring_cells"}
    tasks = _tasks()
    rows = exam_rows(the_sets)
    if menu:
        for row in pool_menu.bank_rows(tasks, ("x", "y")):
            rows.append(
                {
                    "case_id": "menu-row",
                    "inputs": row,
                    "reference": None,
                    "cohort": pool_exam.POOL_COHORT,
                }
            )
    outputs = serve([r["inputs"] for r in rows])
    capture = {}
    result = pool_exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        **material,
        **(
            {
                "menu_tasks": tasks,
                "menu_key": KEY,
                "menu_rowcheck": _rowcheck(rows, outputs),
                "menu_rowcheck_key": KEY,
            }
            if menu
            else {}
        ),
    )
    return result, capture


def _menu_d():
    return pool_menu.score(
        _tasks(),
        menu_rule(),
        lambda rows: [
            toy_binding().derive(r, out)
            for r, out in zip(rows, good_serve(rows), strict=True)
        ],
        key=KEY,
        design_names=("x", "y"),
    )["D"]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_passing_model_gets_the_physics_a_and_the_menu_d_capped_by_c(monkeypatch):
    the_sets = _accuracy_sets()
    seen = []
    real = pps.family_value

    def recording(*a):
        value = real(*a)
        seen.append((frozenset(s.target_id for s in a[0]), value))
        return value

    monkeypatch.setattr(pps, "family_value", recording)
    result, capture = _grade(the_sets)
    assert all(result["gates"].values())
    assert result["gates"][pool_exam.ACCURACY_GATE] is True
    per_set = dict(seen)
    assert result["A"] == pytest.approx(
        statistics.fmean(
            per_set[frozenset(t.target_id for t in group)] for group in the_sets
        ),
        abs=1e-15,
    )
    c = result["design_fidelity"]["C"]
    assert result["D"] == pytest.approx(min(_menu_d(), c), abs=1e-15)
    assert result["pool"]["menu"] is capture["menu"]
    assert result["pool"]["reasons"] == []  # no pick, so no pick reasons
    # the in-range gate read every reserved case: 8 per in-range target x 2 sets
    inr = [r for r in result["pool"]["accuracy"]["rows"] if r["range"] == "in"]
    assert inr and all(r["n"] == 16 for r in inr)
    shown = json.dumps(pool_exam.public(result))
    assert (
        "menu" not in shown and "accuracy" not in shown and "fixture-epoch" not in shown
    )


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_model_failing_the_in_range_gate_scores_nothing():
    result, capture = _grade(_accuracy_sets(), threshold=1.5)
    assert result["gates"][pool_exam.ACCURACY_GATE] is False and result["D"] == 0.0
    assert capture["se_basis"] == {"gated": True}
    assert pool_exam.public(result)["gates"] == [pool_exam.ACCURACY_GATE]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_target_bootstrap_recomposes_the_graded_total_with_the_menu_d_fixed():
    the_sets = _accuracy_sets(
        per_class=2
    )  # 6 targets per set (the SE needs at least 4)
    result, capture = _grade(the_sets)
    basis = capture["se_basis"]
    assert basis["physics"] is True and basis["menu_d"] == _menu_d()
    assert all(t["d"] is None for targets in basis["sets"] for t in targets)
    graded = 0.5 * result["A"] + 0.5 * result["D"]
    assert basis["total"] == pytest.approx(graded, abs=1e-15)
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        graded, abs=1e-15
    )
    spread, sizes = pool_exam.target_bootstrap_se(basis, "sha256:" + "ab" * 32)
    assert sizes == [6, 6] and math.isfinite(spread) and spread >= 0.0


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_accuracy_only_targets_need_a_menu_and_a_physics_rule_and_never_mix():
    the_sets = _accuracy_sets()
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(the_sets, menu=False)
    assert caught.value.code == "accuracy_only_targets_need_a_menu_and_a_physics_rule"
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(the_sets, physics=False)
    assert caught.value.code == "accuracy_only_targets_need_a_menu_and_a_physics_rule"
    plain = _sets()
    mixed = ((plain[0][0], *the_sets[0][1:]), the_sets[1])
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(mixed)
    assert caught.value.code == "accuracy_only_targets_mixed_with_optimizer_targets"


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_menu_version_with_multi_design_targets_grades_as_before():
    # the same physics + menu grade on the toy multi-design targets: the pick still runs, the menu D replaces it
    result, capture = _grade(_sets())
    assert all(result["gates"].values())
    assert result["D"] == pytest.approx(
        min(_menu_d(), result["design_fidelity"]["C"]), abs=1e-15
    )
    assert all(
        type(t["d"]) is float
        for targets in capture["se_basis"]["sets"]
        for t in targets
    )


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_each_case_is_graded_once_a_case_in_two_targets_refuses():
    the_sets = _accuracy_sets()
    first = the_sets[0][0]  # an in-range target of set 0
    twin = pool_grader.build_accuracy_target(
        target_id="in7k0",  # another in-range id, the SAME cases
        conditions={**first.conditions, "target_id": "in7k0"},
        outputs=first.outputs,
        u=first.u,
        box=first.box,
        designs=[list(d) for d in first.designs],
        truths=[dict(t) for t in first.truths],
    )
    doubled = (the_sets[0], (twin, *the_sets[1][1:]))
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(doubled)
    assert caught.value.code == "accuracy_case_in_two_targets"


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_total_is_exactly_the_registered_a_cells_and_gate_plus_the_menu_d(
    monkeypatch,
):
    """CV-B A3 / CV-Motor (2): no pick D and no A_bank leg is computed for an accuracy-only version (each would raise
    here), the bank's A legs move nothing, and every set's total is 0.5 x its physics A + 0.5 x the menu D capped by C.
    """
    import test_pool_physics_score as physics_tests

    from carbon.scoring import pool_proof_suite

    def forbidden(*_a, **_k):
        raise AssertionError(
            "an accuracy-only version computed a pick or an A_bank leg"
        )

    monkeypatch.setattr(pool_grader, "grade_set", forbidden)
    monkeypatch.setattr(pool_grader, "combine_a", forbidden)
    monkeypatch.setattr(pool_proof_suite, "score_specs", forbidden)
    the_sets = _accuracy_sets()
    result, _capture = _grade(the_sets)
    c = result["design_fidelity"]["C"]
    d = min(_menu_d(), c)
    assert result["D"] == d
    assert result["pool"]["set_totals"] == pytest.approx(
        [0.5 * a + 0.5 * d for a in _per_set_a(the_sets)], abs=1e-15
    )
    # the sealed grader's bank A legs never enter: a different base A gives the same A, D and set totals
    original = physics_tests.fake_measure

    def other_base(**kw):
        return {**original(**kw), "A": 0.123, "A_legs": {"x": 0.9}}

    monkeypatch.setattr(sys.modules[__name__], "fake_measure", other_base)
    again, _ = _grade(the_sets)
    assert (again["A"], again["D"], again["pool"]["set_totals"]) == (
        result["A"],
        result["D"],
        result["pool"]["set_totals"],
    )


def _per_set_a(the_sets):
    seen = []
    real = pps.family_value

    def recording(*a):
        value = real(*a)
        seen.append(value)
        return value

    pps.family_value = recording
    try:
        _grade(the_sets)
    finally:
        pps.family_value = real
    return seen


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_version_without_the_key_still_runs_the_pick_on_every_set(monkeypatch):
    """CV-B A1: no accuracy-only target, so the existing path runs unchanged (score_specs once per set)."""
    from carbon.scoring import pool_proof_suite

    calls = []
    real = pool_proof_suite.score_specs

    def recording(plugin, specs, *a):
        calls.append(tuple(s.target_id for s in specs))
        return real(plugin, specs, *a)

    monkeypatch.setattr(pool_proof_suite, "score_specs", recording)
    the_sets = _sets()
    _grade(the_sets)
    assert calls == [tuple(t.target_id for t in group) for group in the_sets]


# ---------------------------------------------------------------- the REGISTRATION keys the kind (Validator-2B M-1, N-1)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_registered_kind_and_the_material_kind_must_agree_both_ways():
    # accuracy-only material on a registration that does not name the kind: refused (the pack builder cannot decide it)
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(_accuracy_sets(), kind=None)
    assert caught.value.code == "accuracy_only_targets_not_registered"
    # a registration naming the kind, with multi-design material: refused
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(_sets(), kind="accuracy_only")
    assert caught.value.code == "registered_target_kind_not_in_the_material"


def test_the_target_kind_registers_with_no_default():
    from carbon.scoring import pool_version

    block = {
        "scoring": "headroom",
        "cells_sha256": "c" * 64,
        "gate_statistic": "p90",
        "gate_threshold": {"f": 1.0},
        "gate_cases": "agen",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "skill_form": "log",
        "h_min": 4,
        "h_lo": 2.5,
        "n_min": 12,
    }
    assert pool_version._physics(block).target_kind is None  # absent: today's kind
    assert (
        pool_version._physics({**block, "target_kind": "accuracy_only"}).target_kind
        == "accuracy_only"
    )
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        pool_version._physics({**block, "target_kind": pool_version.HUMAN_INPUT})
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        pool_version._physics({**block, "target_kind": None})
    for bad in ("multi_design", "", 1, ["accuracy_only"]):
        with pytest.raises(pool_version.PoolConstantsNotRegistered, match="malformed"):
            pool_version._physics({**block, "target_kind": bad})


def test_both_1_8_rows_register_the_accuracy_only_kind_and_no_other_row_does():
    from carbon.scoring import pool_version

    rows = json.loads(pool_version.CONSTANTS.read_bytes())["versions"]
    kinds = {
        key: row["physics"].get("target_kind")
        for key, row in rows.items()
        if "physics" in row
    }
    assert kinds == {
        "chip-cold-plate 1.8": "accuracy_only",
        "electric-motor-magnetics 1.8": "accuracy_only",
    }
    assert all(
        "target_kind" not in json.dumps(row)
        for key, row in rows.items()
        if key not in kinds
    )
    for key in kinds:
        # each row's physics block parses with its kind once its HUMAN_INPUT leaves are filled (synthetic here)
        block = {
            k: ("c" * 64 if v == pool_version.HUMAN_INPUT else v)
            for k, v in rows[key]["physics"].items()
        }
        assert pool_version._physics(block).target_kind == "accuracy_only"
        assert "menu" in rows[key]  # the kind needs the menu (its D)


def test_an_accuracy_only_target_is_never_public():
    base = toy_target("t0", 7)
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_target_is_never_public"
    ):
        pool_grader.build_accuracy_target(
            target_id="t0",
            conditions=base.conditions,
            outputs=base.outputs,
            u=base.u,
            box=base.box,
            designs=[list(base.designs[0])],
            truths=[dict(base.truths[0])],
            public=True,
        )
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_target_is_never_public"
    ):
        pool_plugin.spec_from_source(_source(base, public=True), toy_binding())
