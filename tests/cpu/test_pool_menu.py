"""Menu D on the door grade path (Graphite-B design GRAPHITE_B_MENU_DOOR_D_DESIGN_20261107; Validator-2B 7 Nov
rulings (a) menu rows in the bank, (b) draw after the predictions, (c) declared change).

Claims:
1. A version without a ``menu`` block never reaches the menu path (registration absent -> None, no new kwargs).
2. The registration has no default: HUMAN_INPUT, nulls and a malformed block refuse.
3. The sealed tasks load only against the registration (every registered task, no other, each record's sha).
4. The menu rows are plain pool rows of the bank; a record design the bank does not hold refuses (Carbon's code).
5. D is the menu D (draw after the predictions), capped by C; the custody record keeps the full-pool predictions and
   never the drawn ids; nothing of it reaches `public`.
6. The SE basis holds the menu D fixed, so the resample recomposes the graded total exactly.
7. The draw key exists only once installed from K_crown; without it a menu version refuses (Carbon's gap).

Every task, record, key and value here is a SYNTHETIC fixture (the analytic toy of test_menu_score).
"""

from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_menu_score import _document as menu_document
from test_menu_score import _problem as menu_problem
from test_pool_exam import (
    ARGUMENTS,
    CEILING,
    FAST,
    POLICIES,
    exam_rows,
    sets,
    toy_binding,
)
from test_pool_plugin import U, fake_measure, good_serve, truth

from carbon.scoring import (
    crown_d,
    menu_score,
    pool_exam,
    pool_menu,
    pool_version,
)

KEY = b"k" * 32  # synthetic custody draw key
FIXED = {"cond": 1.0}
PROBLEM_DOC = {
    "target_id": "task-1",
    "outputs": ["f", "g"],
    "objective": "f",
    "sense": "max",
    "limits": [{"output": "g", "kind": "<=", "bound": 0.5}],
    "u": {"f": U, "g": U},
    "box": [[0.0, 1.0], [0.0, 1.0]],
}


def _record_sha(document):
    return menu_score.menu_record(document, menu_problem()).sha256


def _material(document=None):
    document = menu_document() if document is None else document
    return {
        "tasks": [
            {
                "problem": copy.deepcopy(PROBLEM_DOC),
                "duties": [["", dict(FIXED)]],
                "record": document,
            }
        ]
    }


def _rule(document=None, epoch="fixture-epoch-1"):
    document = menu_document() if document is None else document
    return pool_menu.MenuRule(
        records_sha256=(("task-1", _record_sha(document)),),
        epoch=epoch,
        aggregate="mean",
    )


def _tasks(document=None):
    return pool_menu.load_tasks(
        _material(document),
        _rule(document),
        input_names=("cond", "x", "y"),
        design_names=("x", "y"),
    )


def _truth_predict(rows):
    return [dict(zip(("f", "g"), truth(r), strict=True)) for r in rows]


def _constant_predict(rows):
    return [{"f": 1.0, "g": 0.1} for _ in rows]


# ---------------------------------------------------------------- 1-2. registration


def test_an_absent_block_is_no_menu_and_the_block_has_no_default():
    assert pool_version._menu(pool_version._ABSENT) is None
    good = {"records_sha256": {"task-1": "a" * 64}, "epoch": "e1", "aggregate": "mean"}
    rule = pool_version._menu(good)
    assert rule == pool_menu.MenuRule((("task-1", "a" * 64),), "e1", "mean")
    for bad in (
        pool_version.HUMAN_INPUT,
        {**good, "epoch": pool_version.HUMAN_INPUT},
        {**good, "aggregate": pool_version.HUMAN_INPUT},
        {**good, "records_sha256": {"task-1": pool_version.HUMAN_INPUT}},
    ):
        with pytest.raises(
            pool_version.PoolConstantsNotRegistered, match="not_registered"
        ):
            pool_version._menu(bad)
    for bad in (
        None,
        {**good, "epoch": None},
        {**good, "aggregate": "median"},
        {**good, "records_sha256": {}},
        {**good, "records_sha256": {"task-1": "not-a-sha"}},
        {k: v for k, v in good.items() if k != "epoch"},
        {**good, "extra": 1},
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._menu(bad)


def test_every_registered_version_has_no_menu_block():
    document = json.loads(Path(pool_version.CONSTANTS).read_bytes())
    assert all("menu" not in entry for entry in document["versions"].values())


# ---------------------------------------------------------------- 3. tasks against the registration


def test_tasks_load_only_against_the_registration():
    (task,) = _tasks()
    assert task.problem.target_id == "task-1" and task.duties == (("", FIXED),)
    names = {"input_names": ("cond", "x", "y"), "design_names": ("x", "y")}
    other = menu_document()
    other["s_zero"] = 0.5
    cases = [
        (_material(), _rule(other), "menu_record_sha256_not_registered"),
        (
            _material(),
            pool_menu.MenuRule(
                (("task-1", _record_sha(menu_document())), ("task-2", "b" * 64)),
                "e",
                "mean",
            ),
            "menu_registered_task_missing",
        ),
        (
            _material(),
            pool_menu.MenuRule(
                (("task-9", _record_sha(menu_document())),), "e", "mean"
            ),
            "menu_task_not_registered",
        ),
        ({"tasks": []}, _rule(), "menu_material_malformed"),
    ]
    for material, rule, code in cases:
        with pytest.raises(pool_exam.ExamRefused) as caught:
            pool_menu.load_tasks(material, rule, **names)
        assert caught.value.code == code
    material = _material()
    material["tasks"][0]["duties"] = [
        ["", {"x": 1.0}]
    ]  # a duty may not fix a design input
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.load_tasks(material, _rule(), **names)
    assert caught.value.code == "menu_duty_inputs_do_not_complete_the_model_row"
    material = _material()
    material["tasks"][0]["duties"] = [["a", dict(FIXED)], ["b", {"cond": 2.0}]]
    with pytest.raises(
        pool_exam.ExamRefused
    ) as caught:  # two duties need per-duty output names
        pool_menu.load_tasks(material, _rule(), **names)
    assert caught.value.code == "menu_problem_outputs_not_per_duty"


def test_rows_cover_every_pool_design_times_duty_inputs_only():
    (task,) = _tasks()
    rows = pool_menu.bank_rows((task,), ("x", "y"))
    assert len(rows) == len(task.record.pool)
    assert all(
        set(r) == {"cond", "x", "y"} for r in rows
    )  # no id, stratum, task or truth
    two = dataclasses.replace(task, duties=(("a", FIXED), ("b", {"cond": 2.0})))
    assert len(pool_menu.task_rows(two, ("x", "y"))[0]) == 2 * len(task.record.pool)


# ---------------------------------------------------------------- 5. scoring


def test_a_truthful_model_scores_one_a_constant_zero_and_the_record_keeps_no_drawn_ids():
    tasks = _tasks()
    good = pool_menu.score(
        tasks, _rule(), _truth_predict, key=KEY, design_names=("x", "y")
    )
    flat = pool_menu.score(
        tasks, _rule(), _constant_predict, key=KEY, design_names=("x", "y")
    )
    assert good["D"] == pytest.approx(1.0) and flat["D"] == pytest.approx(0.0)
    record = good["record"]
    assert (
        record["epoch"] == "fixture-epoch-1"
        and record["tasks"][0]["record_sha256"] == tasks[0].record.sha256
    )
    # the FULL pool's predictions (a king re-scores on a later draw without inference), never the drawn menu
    assert set(record["predictions"]["task-1"]) == set(tasks[0].record.pool)
    drawn = set(menu_score.draw_menu(tasks[0].record, KEY, epoch="fixture-epoch-1"))
    assert drawn < set(tasks[0].record.pool)
    assert "menu" not in record["tasks"][0] and "ids" not in json.dumps(record["tasks"])


def test_a_derive_missing_a_task_output_is_carbons_wiring():
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.score(
            _tasks(),
            _rule(),
            lambda rows: [{"f": 1.0} for _ in rows],
            key=KEY,
            design_names=("x", "y"),
        )
    assert caught.value.code == "menu_derived_outputs_do_not_cover_the_task"


# ---------------------------------------------------------------- 7. the key


def test_the_draw_key_exists_only_once_installed_from_k_crown():
    pool_menu.install_key(None)
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.active_key()
    assert caught.value.code == "menu_draw_unavailable"
    with pytest.raises(pool_exam.ExamRefused):
        pool_menu.install_key(b"short")
    try:
        pool_menu.install_key(b"c" * 32)
        assert pool_menu.active_key() == crown_d.derive_key(b"c" * 32, "d-menu-sample")
    finally:
        pool_menu.install_key(None)


# ---------------------------------------------------------------- 4-6. the official grade


def _menu_grade(
    *, drop_menu_rows=False, policies=None, tasks="default", key=KEY, serve=good_serve
):
    the_sets = sets()
    tasks = _tasks() if tasks == "default" else tasks
    rows = exam_rows(the_sets)
    if tasks and not drop_menu_rows:
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
        policies=(
            dataclasses.replace(POLICIES, menu=_rule())
            if policies is None
            else policies
        ),
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        menu_tasks=tasks,
        menu_key=key,
    )
    return result, capture


def test_the_official_grade_scores_the_menu_d_capped_by_c_and_keeps_it_in_custody():
    result, capture = _menu_grade()
    assert all(result["gates"].values())
    menu = result["pool"]["menu"]
    assert menu is capture["menu"]
    expected = pool_menu.score(
        _tasks(),
        _rule(),
        lambda rows: [
            toy_binding().derive(r, out)
            for r, out in zip(rows, good_serve(rows), strict=True)
        ],
        key=KEY,
        design_names=("x", "y"),
    )["D"]
    c = result["design_fidelity"]["C"]
    assert result["D"] == pytest.approx(min(expected, c), abs=1e-15)
    assert result["pool"]["set_totals"] == pytest.approx(
        [0.5 * result["A"] + 0.5 * result["D"]] * result["pool"]["sets"]
    )
    shown = json.dumps(pool_exam.public(result))
    assert (
        "menu" not in shown
        and "predictions" not in shown
        and "fixture-epoch" not in shown
    )
    basis = capture["se_basis"]
    assert basis["menu_d"] == menu_d_of(result)
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        0.5 * result["A"] + 0.5 * result["D"], abs=1e-12
    )


def menu_d_of(result):
    return pool_menu.score(
        _tasks(),
        _rule(),
        lambda rows: [
            toy_binding().derive(r, out)
            for r, out in zip(rows, good_serve(rows), strict=True)
        ],
        key=KEY,
        design_names=("x", "y"),
    )["D"]


def test_a_menu_design_the_bank_does_not_hold_refuses_with_carbons_code():
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _menu_grade(drop_menu_rows=True)
    assert caught.value.code == "menu_rows_differ_from_the_bank"


def test_menu_material_must_match_the_registration_exactly():
    for kwargs in (
        {"tasks": None},  # registered, no tasks
        {"key": None},  # registered, no key
        {"policies": POLICIES},  # tasks + key without a registration
    ):
        with pytest.raises(pool_exam.ExamRefused) as caught:
            _menu_grade(**kwargs)
        assert caught.value.code == "menu_material_does_not_match_the_registration"


def test_a_version_without_menu_grades_exactly_as_before():
    the_sets = sets()
    rows = exam_rows(the_sets)
    outputs = good_serve([r["inputs"] for r in rows])
    arguments = {
        "binding": toy_binding(),
        "sets": the_sets,
        "policies": POLICIES,
        "bank_rows": rows,
        "outputs": outputs,
        "repeats": [outputs, outputs],
        "base_measure": fake_measure,
        "base_arguments": ARGUMENTS,
        "speed_call_seconds": FAST,
        "ceiling_seconds": CEILING,
    }
    before, after = {}, {}
    plain = pool_exam.measure_pool(**arguments, capture=before)
    explicit = pool_exam.measure_pool(
        **arguments, capture=after, menu_tasks=None, menu_key=None
    )
    assert plain == explicit and "menu" not in plain["pool"]
    assert "menu_d" not in before["se_basis"] and "menu" not in before


def test_receiver_start_installs_the_menu_key_only_from_its_section(tmp_path):
    import os

    from carbon.challenge_validator import crown_average as ca
    from carbon.challenge_validator import crown_average_host as host

    try:
        host.install({})
        with pytest.raises(pool_exam.ExamRefused):
            pool_menu.active_key()
        for bad in (
            {"menu_draw": []},
            {"menu_draw": {}},
            {"menu_draw": {"key_file": "x", "n": 1}},
        ):
            with pytest.raises(ca.CrownAverageInvalid):
                host.install(bad)
        if os.name != "nt":  # POSIX owner-only modes
            key = tmp_path / "k"
            key.write_bytes(b"c" * 32)
            key.chmod(0o600)
            host.install({"menu_draw": {"key_file": str(key)}})
            assert pool_menu.active_key() == crown_d.derive_key(
                b"c" * 32, "d-menu-sample"
            )
            assert ca.ACTIVE is None  # the menu key does not turn the crown average on
    finally:
        host.install({})
