"""ACC-NOISE-01 pure helpers (scripts/dev/exam_reads/acc_noise.py): synthetic points only.

Claims: pooled = today's slice over every point; balanced = the mean of the out-of-range class means (in_train never enters), with
n < N classes pooled into other_ood that joins only when asked; mean / min combine as stated; the bootstrap resamples within each
class and is seeded; a missing class, a bad atom or a missing required contender is refused; an unavailable DOWN formula is
reported "not available"; the verdict is `min` only if the max over the graded contenders of the balanced A_gen's bootstrap SD
(2000 within-class draws) is < margin_N, as ruled.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import acc_noise as an

POINTS = (
    [("in_train", "t1", 0.9)] * 4
    + [("regime:inner_band", "t1", 0.8)] * 3
    + [("regime:inner_band", "t2", 0.6)] * 3
    + [("extended_shell", "t2", 0.2)] * 6
    + [("regime:side_x_high", "t3", 0.5)] * 2
)


def test_pooled_is_every_point_and_balanced_is_the_mean_of_ood_class_means():
    points = an.checked_points(POINTS)
    # today's slice: each target's mean, then the mean over targets
    t1, t2, t3 = (4 * 0.9 + 3 * 0.8) / 7, (3 * 0.6 + 6 * 0.2) / 9, 0.5
    assert an.pooled(points) == pytest.approx((t1 + t2 + t3) / 3)
    # inner band 0.7 and shell 0.2 qualify (n >= 3); the side class (n 2) is indicative
    assert an.balanced(points, floor_n=3, other_ood_enters=False) == pytest.approx(
        (0.7 + 0.2) / 2
    )
    assert an.balanced(points, floor_n=3, other_ood_enters=True) == pytest.approx(
        (0.7 + 0.2 + 0.5) / 3
    )
    # a small class cannot be averaged away: the shell's 6 points weigh as one class, not 6 of 14 OOD points
    assert an.balanced(points, floor_n=3, other_ood_enters=False) < an.pooled(points)
    assert (
        an.balanced([("in_train", "t", 1.0)] * 5, floor_n=3, other_ood_enters=True)
        is None
    )


def test_the_grader_combines_and_the_pooled_slice_is_the_graders():
    from types import SimpleNamespace

    from carbon.scoring import pool_grader

    assert an.combine(0.9, 0.5, {"kind": "min"}) == 0.5
    assert an.combine(0.9, 0.5, {"kind": "weighted", "weight": 0.25}) == pytest.approx(
        0.8
    )
    assert (
        an.combine(0.9, None, {"kind": "min"}) == 0.9
    )  # as the grader: no slice leaves A
    with pytest.raises(an.AccNoiseRefused, match="combine_rule"):
        an.combine(0.9, 0.5, {"kind": "median"})
    # pooled == pool_grader.agen_accuracy on the same predictions (per-point atom = the mean over outputs)
    scales = {"f": 2.0, "g": 0.5}
    specs = [
        SimpleNamespace(target_id=f"t{j}", conditions={"j": j}, outputs=("f", "g"), agen=(0, 2, 3),
                        designs=[[float(i)] for i in range(4)],
                        truths=[{"f": float(i), "g": float(i * i)} for i in range(4)])
        for j in range(3)
    ]  # fmt: skip

    def predict(conditions, designs):
        return [
            {"f": d[0] + 0.1 * conditions["j"], "g": d[0] ** 2 - 0.3} for d in designs
        ]

    points = []
    for spec in specs:
        for i, prediction in zip(
            spec.agen, predict(spec.conditions, [spec.designs[i] for i in spec.agen])
        ):
            atoms = [
                pool_grader.benefit(abs(prediction[k] - spec.truths[i][k]) / scales[k])
                for k in spec.outputs
            ]
            points.append(("extended_shell", spec.target_id, sum(atoms) / len(atoms)))
    assert an.pooled(an.checked_points(points)) == pytest.approx(
        pool_grader.agen_accuracy(specs, predict, scales), abs=1e-15
    )


def test_the_bootstrap_resamples_within_each_class_and_is_seeded():
    points = an.checked_points(POINTS)

    def counts(sample):
        out = {}
        for k, _t, _a in sample:
            out[k] = out.get(k, 0) + 1
        return float(out["extended_shell"] * 100 + out["regime:side_x_high"])

    reps = an.bootstrap(points, counts, draws=50, seed=7)
    assert set(reps) == {602.0}  # every replicate keeps each class's size

    def bal(p):
        return an.balanced(p, floor_n=3, other_ood_enters=False)

    a = an.bootstrap(points, bal, draws=200, seed=1)
    b = an.bootstrap(points, bal, draws=200, seed=1)
    assert (a == b).all() and a.std() > 0
    summary = an.spread(a)
    assert summary["width_95"] == pytest.approx(summary["q975"] - summary["q025"])
    assert summary["half_width_95"] == pytest.approx(summary["width_95"] / 2)


def _contenders(**over):
    base = {
        "crown": {"a_in": 0.95, "points": POINTS},
        "baseline": {"a_in": 0.8, "points": [(k, t, a * 0.9) for k, t, a in POINTS]},
        "train_kernel": {
            "a_in": 0.9,
            "points": [(k, t, a * 0.95) for k, t, a in POINTS],
        },
        "down_formula": None,
        "operator": {"a_in": 0.93, "points": POINTS},
    }
    return {**base, **over}


SETTINGS = {
    "set_of": {"t1": 0, "t2": 0, "t3": 1},
    "floor_n": 3,
    "other_ood_enters": False,
    "registered_rule": {"kind": "weighted", "weight": 0.25},
    "seed": 3,
    "margin_n": 0.01,
}


def test_the_report_has_every_combination_the_class_table_and_the_ruled_verdict():
    out = an.report(_contenders(), **SETTINGS)
    assert out["contenders"]["down_formula"] == an.NOT_AVAILABLE
    crown = out["contenders"]["crown"]
    assert set(crown["A"]) == {
        "registered_pooled",
        "registered_balanced",
        "min_pooled",
        "min_balanced",
    }
    assert crown["A"]["min_balanced"] == pytest.approx(min(0.95, (0.7 + 0.2) / 2))
    assert crown["balanced_spread"]["replicates"] == an.DRAWS == 2000
    shell = out["per_class"]["crown"]["extended_shell"]
    assert shell["n"] == 6 and shell["minus_train_kernel"] == pytest.approx(0.2 - 0.19)
    assert out["per_class"]["crown"]["regime:side_x_high"]["indicative"] is True
    assert "in_train" not in out["per_class"]["crown"]
    assert out["crown_minus_baseline"]["min_balanced"] == pytest.approx(
        crown["A"]["min_balanced"] - out["contenders"]["baseline"]["A"]["min_balanced"]
    )
    sds = {r: out["contenders"][r]["balanced_spread"]["sd"] for r in an.GRADED}
    deciding = out["deciding_spread"]
    assert deciding["statistic"] == "bootstrap_sd" and deciding["per_contender"] == sds
    assert deciding["value"] == max(sds.values()) == sds[deciding["contender"]]
    assert out["verdict"] == ("min" if deciding["value"] < 0.01 else "mean_or_raise_n")
    assert out["settings"]["draws"] == 2000 and out["settings"]["seed"] == 3


def test_min_only_when_the_largest_graded_spread_is_below_margin_n():
    wide = an.report(_contenders(), **{**SETTINGS, "margin_n": 1.0})
    assert wide["verdict"] == "min"
    tight = an.report(_contenders(), **{**SETTINGS, "margin_n": 1e-9})
    assert tight["verdict"] == "mean_or_raise_n"
    # the operator's spread never decides: a noisy operator leaves the verdict as it was
    noisy = [(k, t, (i % 2) * 1.0) for i, (k, t, _a) in enumerate(POINTS)]
    same = an.report(
        _contenders(operator={"a_in": 0.9, "points": noisy}),
        **{**SETTINGS, "margin_n": 1.0},
    )
    assert same["verdict"] == "min"
    # a graded contender with no balanced A_gen (in-train points only) leaves no verdict
    flat = an.report(
        _contenders(baseline={"a_in": 0.8, "points": [("in_train", "t1", 0.5)] * 4}),
        **SETTINGS,
    )
    assert (
        flat["verdict"] is None
        and flat["verdict_reason"] == "no_balanced_a_gen:baseline"
    )


@pytest.mark.parametrize(
    "change, code",
    [
        ({"train_kernel": None}, "contender_required:train_kernel"),
        ({"crown": {"a_in": 0.9, "points": [("", "t", 0.5)]}}, "point_class_missing"),
        ({"crown": {"a_in": 0.9, "points": [("x", "", 0.5)]}}, "point_target_missing"),
        ({"crown": {"a_in": 0.9, "points": [("in_train", "t", 1.5)]}}, "point_atom"),
        ({"crown": {"a_in": 0.9}}, "contender_shape:crown"),
    ],
)
def test_bad_contenders_are_refused(change, code):
    with pytest.raises(an.AccNoiseRefused, match=code):
        an.report(_contenders(**change), **SETTINGS)


def test_every_unruled_setting_is_required_and_checked():
    for key, bad in (
        ("floor_n", 0),
        ("other_ood_enters", None),
        ("registered_rule", {"kind": "x"}),
        ("seed", 1.5),
        ("margin_n", 0),
    ):
        with pytest.raises(an.AccNoiseRefused):
            an.report(_contenders(), **{**SETTINGS, key: bad})
    with pytest.raises(TypeError):
        an.report(_contenders(), floor_n=3)  # no defaults


# --- the per-point class source (ruling (4)) ---------------------------------------------------------------------------------

REGION = {
    "base": {"a": [0.0, 1.0], "b": [0.0, 1.0]},
    "extended": {"a": [-1.0, 2.0], "b": [-1.0, 2.0]},
}


def _geometric(region, names, inputs):
    # a stand-in with geometric-v1's shape: in TRAIN, inner band (0.5 of the extension), one side, else shell
    out = [
        n
        for n in names
        if not region["base"][n][0] <= inputs[n] <= region["base"][n][1]
    ]
    if not out:
        return "in_train"
    if all(-0.5 <= inputs[n] <= 1.5 for n in names):
        return "regime:inner_band"
    if len(out) == 1:
        return f"regime:side_{out[0]}_{'high' if inputs[out[0]] > 1 else 'low'}"
    return "extended_shell"


def test_point_classes_follow_the_rule_inside_the_registered_plan():
    params = {
        "classes": [{"class": "regime:inner_band"}, {"class": "regime:side_a_high"}]
    }
    allowed = an.plan_class_names(params)
    assert allowed == {"in_train", "regime:inner_band", "regime:side_a_high"}
    rows = [{"a": 0.5, "b": 0.5}, {"a": 1.2, "b": 0.5}, {"a": 1.9, "b": 0.5}]
    kw = {
        "klass": _geometric,
        "region": REGION,
        "names": ("a", "b"),
        "allowed": allowed,
    }
    assert an.point_classes(rows, **kw) == [
        "in_train",
        "regime:inner_band",
        "regime:side_a_high",
    ]
    # a class the plan does not name STOPS (here the shell)
    with pytest.raises(
        an.AccNoiseRefused, match="point_class_not_in_the_coverage_plan:extended_shell"
    ):
        an.point_classes([{"a": 1.9, "b": 1.9}], **kw)
    # once the pack carries its own class, both must agree
    assert an.point_classes(
        rows, pack_classes=["in_train", "regime:inner_band", "regime:side_a_high"], **kw
    )
    with pytest.raises(an.AccNoiseRefused, match="point_class_disagrees_with_the_pack"):
        an.point_classes(
            rows, pack_classes=["in_train", "in_train", "regime:side_a_high"], **kw
        )
    # an official read refuses until the pack field exists
    with pytest.raises(
        an.AccNoiseRefused, match="point_class_field_required_for_an_official_read"
    ):
        an.point_classes(rows, official=True, **kw)
    with pytest.raises(an.AccNoiseRefused, match="coverage_plan_classes"):
        an.plan_class_names({"classes": []})


def test_the_rule_file_loads_only_under_its_pinned_sha(tmp_path):
    import hashlib

    rule = tmp_path / "rule.py"
    rule.write_text(
        'RULE = "geometric-v1"\n\ndef klass(region, names, inputs):\n    return "in_train"\n'
    )
    sha = hashlib.sha256(rule.read_bytes()).hexdigest()
    assert an.load_rule(rule, "sha256:" + sha)(REGION, ("a",), {"a": 0.5}) == "in_train"
    with pytest.raises(an.AccNoiseRefused, match="rule_file_sha256_mismatch"):
        an.load_rule(rule, "0" * 64)
    other = tmp_path / "other.py"
    other.write_text('RULE = "something-else"\n\ndef klass(*a):\n    return "x"\n')
    with pytest.raises(an.AccNoiseRefused, match="rule_is_not_geometric_v1"):
        an.load_rule(other, hashlib.sha256(other.read_bytes()).hexdigest())


def test_the_pooled_side_is_formed_per_set_as_measure_pool_does():
    out = an.report(_contenders(), **SETTINGS)
    crown = out["contenders"]["crown"]
    t1, t2, t3 = (4 * 0.9 + 3 * 0.8) / 7, (3 * 0.6 + 6 * 0.2) / 9, 0.5
    assert crown["a_gen_pooled_by_set"] == {
        0: pytest.approx((t1 + t2) / 2),
        1: pytest.approx(t3),
    }
    # measure_pool: A per set = combine_a(A_bank, that set's A_gen), then the mean over the sets
    want = ((0.75 * 0.95 + 0.25 * (t1 + t2) / 2) + (0.75 * 0.95 + 0.25 * t3)) / 2
    assert crown["A"]["registered_pooled"] == pytest.approx(want)
    assert crown["A"]["min_pooled"] == pytest.approx(
        (min(0.95, (t1 + t2) / 2) + min(0.95, t3)) / 2
    )
    with pytest.raises(an.AccNoiseRefused, match="target_has_no_set:t3"):
        an.report(_contenders(), **{**SETTINGS, "set_of": {"t1": 0, "t2": 0}})
