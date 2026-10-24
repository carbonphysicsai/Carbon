"""The pool grader's practice result (carbon.pool-grade.practice.v1) as the miner
sees it: read from the practice doc only, allow-listed field by field, labelled
practice, and never a source of anything the exam withholds."""

from __future__ import annotations

from scripts.dev.miner_launchpad import campaign_view as cv

DIGEST = "sha256:" + "ab" * 32


def _target(**over):
    row = {
        "target_id": "pub-1",
        "d": 0.42,
        "closeness": 0.6,
        "honesty": 0.7,
        "error_in_u": 3.1,
        "feasible": True,
        "queries": 40,
        "reached_reference": False,
        "reason": "graded",
        # Material a grader result must never carry into a miner view.
        "pick": [1.0, 2.0],
        "pool_points": [[1, 2]],
        "seed": 7,
    }
    row.update(over)
    return row


def _pool(**over):
    block = {
        "schema": cv.POOL_GRADE_SCHEMA,
        "pool_digests": [DIGEST],
        "legs": {"A": 0.8, "A_gen": 0.5, "A_combined": 0.5, "D_opt": 0.42, "C": 0.9},
        "total": 0.46,
        "gates": [{"code": "paired_repeat", "passed": True}],
        "minimums": None,
        "targets": [_target()],
        "secret": "x",
    }
    block.update(over)
    return block


def _doc(schema=cv.DUAL_FEEDBACK_SCHEMA_V3, **over):
    doc = {
        "schema": schema,
        "available": True,
        "gates": {"paired_repeat": True},
        "eligible": True,
        "total": 0.46,
        "accuracy": 0.8,
        "design_value": 0.42,
        "pool_grade": _pool(),
    }
    doc.update(over)
    return doc


def _view(doc):
    return cv.dual_feedback({"practice_dual": doc})


def test_a_v3_doc_carries_the_allow_listed_pool_grade():
    pool = _view(_doc())["pool_grade"]
    assert pool["scope"] == "practice (public pool)"
    assert pool["pool_digests"] == [DIGEST]
    assert pool["legs"] == {
        "A": 0.8,
        "A_gen": 0.5,
        "A_combined": 0.5,
        "D_opt": 0.42,
        "C": 0.9,
    }
    assert pool["total"] == 0.46
    (row,) = pool["targets"]
    assert row["target_id"] == "pub-1" and row["feasible"] is True
    assert set(row) == {
        "target_id",
        "d",
        "closeness",
        "honesty",
        "error_in_u",
        "feasible",
        "queries",
        "reached_reference",
        "reason",
    }


def test_nothing_outside_the_allow_list_reaches_the_view():
    text = repr(_view(_doc()))
    for withheld in ("pick", "pool_points", "seed", "secret"):
        assert withheld not in repr(_view(_doc())["pool_grade"]), withheld
    assert "pool_points" not in text


def test_older_schemas_never_gain_a_pool_grade():
    for schema in (cv.DUAL_FEEDBACK_SCHEMA, cv.DUAL_FEEDBACK_SCHEMA_V2):
        assert "pool_grade" not in _view(_doc(schema=schema))


def test_a_pool_grade_with_the_wrong_schema_is_dropped():
    assert _view(_doc(pool_grade=_pool(schema="carbon.pool-grade.exam.v1")))[
        "pool_grade"
    ] is None
    assert _view(_doc(pool_grade="not a dict"))["pool_grade"] is None


def test_the_reason_is_a_closed_code_and_bad_types_become_none():
    bad = _target(reason="because", feasible="yes", queries=-1, d=float("nan"))
    (row,) = _view(_doc(pool_grade=_pool(targets=[bad, "junk"])))["pool_grade"][
        "targets"
    ]
    assert row["reason"] is None
    assert row["feasible"] is None
    assert row["queries"] is None
    assert row["d"] is None


def test_every_closed_reason_passes_through():
    rows = [_target(target_id=f"t{i}", reason=r) for i, r in enumerate(cv.POOL_TARGET_REASONS)]
    out = _view(_doc(pool_grade=_pool(targets=rows)))["pool_grade"]["targets"]
    assert [row["reason"] for row in out] == list(cv.POOL_TARGET_REASONS)


def test_targets_and_digests_are_capped():
    rows = [_target(target_id=f"t{i}") for i in range(40)]
    pool = _view(_doc(pool_grade=_pool(targets=rows, pool_digests=[DIGEST] * 40)))[
        "pool_grade"
    ]
    assert len(pool["targets"]) == 16
    assert len(pool["pool_digests"]) == 16


def test_an_unavailable_doc_shows_no_pool_grade():
    view = _view({"schema": cv.DUAL_FEEDBACK_SCHEMA_V3, "available": False, "reason": "x"})
    assert view == {"available": False, "reason": "x"}
