"""The dashboard's door queue panel (owner 6 Nov: show miners the queue): the Worker reads each door's public queue
document (carbon.queue.public.v1) exactly in its closed shape, from the same door as the board's feed, and fails closed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed here")
MOTOR = "electric-motor-magnetics"
FEED = f"https://motor-door.example/carbon/v1/feed/{MOTOR}"


def _doc(**changes):
    body = {
        "schema": "carbon.queue.public.v1",
        "challenge_id": MOTOR,
        "challenge_version": "1.5",
        "door_state": "grading",
        "waiting_to_build": 3,
        "building_now": 1,
        "waiting_to_grade": 2,
        "grading_now": 1,
        "wait_24h": {"verdicts": 12, "median_s": 2460, "p90_s": 7300, "reason": None},
        "as_of": "2026-11-06T21:10:00Z",
    }
    body.update(changes)
    return body


def _run(payload):
    done = subprocess.run(
        [NODE, str(HERE / "dashboard_queue_check.mjs")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        cwd=HERE,
    )
    return json.loads(done.stdout)


def test_the_reader_accepts_exactly_the_closed_document():
    few = _doc(
        wait_24h={
            "verdicts": 3,
            "median_s": None,
            "p90_s": None,
            "reason": "fewer_than_5_verdicts_in_24h",
        }
    )
    got = _run(
        {
            "cases": [
                {"name": "good", "text": json.dumps(_doc()), "challenge": MOTOR},
                {"name": "few", "text": json.dumps(few), "challenge": MOTOR},
            ],
            "fetches": [],
        }
    )["checked"]
    assert got["good"] == {
        "ok": True,
        "value": {k: v for k, v in _doc().items() if k != "schema"},
    }
    assert got["few"]["ok"] is True


@pytest.mark.parametrize(
    "name, change, code",
    [
        ("extra", {"hotkey": "5F"}, "queue_fields"),
        ("schema", {"schema": "x"}, "queue_fields"),
        ("other_door", {"challenge_id": "f02"}, "queue_challenge"),
        ("state", {"door_state": "busy because of task rtsk_1"}, "queue_door_state"),
        ("negative", {"waiting_to_build": -1}, "queue_counts"),
        ("float_count", {"building_now": 1.5}, "queue_counts"),
        ("two_grading", {"grading_now": 2}, "queue_counts"),
        (
            "reason_with_numbers",
            {
                "wait_24h": {
                    "verdicts": 3,
                    "median_s": 10,
                    "p90_s": 20,
                    "reason": "fewer_than_5_verdicts_in_24h",
                }
            },
            "queue_wait",
        ),
        (
            "numbers_missing",
            {
                "wait_24h": {
                    "verdicts": 9,
                    "median_s": None,
                    "p90_s": None,
                    "reason": None,
                }
            },
            "queue_wait",
        ),
        ("time", {"as_of": "yesterday"}, "queue_time"),
    ],
)
def test_anything_outside_the_closed_shape_refuses(name, change, code):
    got = _run(
        {
            "cases": [
                {"name": name, "text": json.dumps(_doc(**change)), "challenge": MOTOR}
            ],
            "fetches": [],
        }
    )["checked"][name]
    assert got == {"ok": False, "code": code}


def test_a_large_or_non_json_body_refuses():
    got = _run(
        {
            "cases": [
                {"name": "big", "text": " " * 5000, "challenge": MOTOR},
                {"name": "html", "text": "<html>", "challenge": MOTOR},
            ],
            "fetches": [],
        }
    )["checked"]
    assert got["big"]["code"] == "queue_too_large"
    assert got["html"]["code"] == "queue_not_json"


def test_the_queue_comes_from_the_feeds_own_door_and_fails_closed():
    got = _run(
        {
            "cases": [],
            "urls": [FEED, "http://x/carbon/v1/feed/a", "https://x/other"],
            "fetches": [
                {"name": "ok", "feed": FEED, "status": 200, "body": json.dumps(_doc())},
                {"name": "not_served", "feed": FEED, "status": 404, "body": "{}"},
                {"name": "down", "feed": FEED, "status": 503, "body": "{}"},
                {
                    "name": "wrong",
                    "feed": FEED,
                    "status": 200,
                    "body": json.dumps(_doc(extra=1)),
                },
                {
                    "name": "unreachable",
                    "feed": FEED,
                    "status": 200,
                    "body": "",
                    "throws": True,
                },
            ],
        }
    )
    assert got["urls"][FEED] == {
        "url": f"https://motor-door.example/carbon/v1/queue/{MOTOR}",
        "challengeId": MOTOR,
    }
    assert got["urls"]["http://x/carbon/v1/feed/a"] is None  # https only
    assert got["urls"]["https://x/other"] is None
    fetched = got["fetched"]
    assert (
        fetched["ok"]["state"] == "ACCEPTED"
        and fetched["ok"]["queue"]["waiting_to_grade"] == 2
    )
    assert fetched["ok"]["asked"] == [
        f"https://motor-door.example/carbon/v1/queue/{MOTOR}"
    ]
    assert fetched["not_served"] == {
        "state": "NOT_SERVED",
        "code": None,
        "queue": None,
        "asked": fetched["not_served"]["asked"],
    }
    assert (
        fetched["down"]["state"] == "UNAVAILABLE"
        and fetched["down"]["code"] == "queue_http_503"
    )
    assert (
        fetched["wrong"]["state"] == "UNAVAILABLE" and fetched["wrong"]["queue"] is None
    )
    assert fetched["unreachable"]["code"] == "queue_unreachable"


def test_the_reader_accepts_what_the_doors_writer_writes():
    """Held equal to carbon/challenge_validator/queue_public.py (the TE's door side) once it is on this tree."""
    qp = pytest.importorskip("carbon.challenge_validator.queue_public")
    challenge = type("C", (), {"challenge_id": MOTOR, "version": "1.5"})()
    snapshots = [
        {
            "door_state": state,
            "waiting_to_build": 2,
            "building_now": 0,
            "waiting_to_grade": 5,
            "grading_now": 1,
            "waits_s": waits,
            "as_of_unix": 1_794_000_000,
        }
        for state in qp.DOOR_STATES
        for waits in ([], [30.0, 600.0, 1200.0, 4000.0, 9000.0, 61.5])
    ]
    cases = [
        {
            "name": str(i),
            "text": json.dumps(qp.document(s, challenge)),
            "challenge": MOTOR,
        }
        for i, s in enumerate(snapshots)
    ]
    got = _run({"cases": cases, "fetches": []})["checked"]
    assert all(v["ok"] for v in got.values()), got


# --- the per-submission rows (carbon.queue.public.v3; owner 14 Nov: "show the actual queue") --------------------------------


def _row(position, state="waiting to build", hotkey="5MMM…MMMM", in_queue_s=0):
    return {
        "position": position,
        "hotkey": hotkey,
        "state": state,
        "in_queue_s": in_queue_s,
    }


def _rows_doc(rows=None, **changes):
    body = {
        **{k: v for k, v in _doc().items() if k != "schema"},
        "schema": "carbon.queue.public.v3",
        "held_for_review": None,
        "rows": rows if rows is not None else [_row(1, "in grading", in_queue_s=600)],
        "more_rows": 0,
        "rows_as_of": "2026-11-14T13:00:00Z",
    }
    body.update(changes)
    return body


def test_the_rows_reader_accepts_exactly_the_closed_v3_document():
    rows = [
        _row(1, "in grading", in_queue_s=900),
        _row(2, "building", in_queue_s=300),
        _row(3, "waiting to build"),
        _row(4, "crown check", hotkey=None, in_queue_s=3000),
    ]
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "row_cases": [
                {
                    "name": "good",
                    "text": json.dumps(_rows_doc(rows)),
                    "challenge": MOTOR,
                },
                {
                    "name": "empty",
                    "text": json.dumps(_rows_doc([])),
                    "challenge": MOTOR,
                },
            ],
        }
    )["rowsChecked"]
    assert got["good"] == {
        "ok": True,
        "value": {"rows": rows, "more_rows": 0, "rows_as_of": "2026-11-14T13:00:00Z"},
    }
    assert got["empty"]["ok"] is True and got["empty"]["value"]["rows"] == []


@pytest.mark.parametrize(
    "name, doc, code",
    [
        ("v1", _doc(), "rows_fields"),
        ("schema", _rows_doc(schema="carbon.queue.public.v2"), "rows_fields"),
        ("extra_field", _rows_doc(task_ids=["rtsk_1"]), "rows_fields"),
        ("other_door", _rows_doc(challenge_id="f02"), "rows_challenge"),
        ("as_of", _rows_doc(rows_as_of="soon"), "rows_time"),
        ("more", _rows_doc(more_rows=-1), "rows_count"),
        ("not_a_list", _rows_doc(rows="rows"), "rows_count"),
        ("1001_rows", _rows_doc([_row(i + 1) for i in range(1001)]), "rows_count"),
        ("extra_row_field", _rows_doc([{**_row(1), "score": 0.5}]), "rows_row"),
        (
            "missing_row_field",
            _rows_doc([{"position": 1, "state": "building", "hotkey": None}]),
            "rows_row",
        ),
        ("position", _rows_doc([_row(2)]), "rows_row"),
        ("state", _rows_doc([_row(1, "waiting to grade")]), "rows_row"),
        ("old_state", _rows_doc([_row(1, "grading")]), "rows_row"),
        ("hotkey_long", _rows_doc([_row(1, hotkey="5" + "M" * 47)]), "rows_row"),
        ("hotkey_shape", _rows_doc([_row(1, hotkey="5MMM-MMMM")]), "rows_row"),
        ("not_a_quantum", _rows_doc([_row(1, in_queue_s=301)]), "rows_row"),
        ("negative", _rows_doc([_row(1, in_queue_s=-300)]), "rows_row"),
        ("float_time", _rows_doc([_row(1, in_queue_s=300.5)]), "rows_row"),
    ],
)
def test_anything_outside_the_closed_rows_shape_refuses(name, doc, code):
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "row_cases": [{"name": name, "text": json.dumps(doc), "challenge": MOTOR}],
        }
    )["rowsChecked"][name]
    assert got == {"ok": False, "code": code}


def test_a_large_or_non_json_rows_body_refuses():
    # the door and the Worker hold the same caps (all rows, Lead 15 Nov)
    queue_public = pytest.importorskip("carbon.challenge_validator.queue_public")
    text = (
        HERE.parents[1] / "carbon" / "dashboard" / "worker" / "queue.mjs"
    ).read_text(encoding="utf-8")
    assert f"MAX_ROWS = {queue_public.MAX_ROWS};" in text
    assert f"MAX_ROWS_BYTES = {queue_public.MAX_BYTES_V3};" in text
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "row_cases": [
                {"name": "big", "text": " " * 140000, "challenge": MOTOR},
                {"name": "html", "text": "<html>", "challenge": MOTOR},
            ],
        }
    )["rowsChecked"]
    assert got["big"]["code"] == "rows_too_large"
    assert got["html"]["code"] == "rows_not_json"


def test_the_rows_come_from_the_feeds_own_door_at_the_v3_path_and_fail_closed():
    got = _run(
        {
            "cases": [],
            "urls": [FEED, "http://x/carbon/v1/feed/a", "https://x/other"],
            "fetches": [],
            "row_fetches": [
                {
                    "name": "ok",
                    "feed": FEED,
                    "status": 200,
                    "body": json.dumps(_rows_doc()),
                },
                {"name": "not_served", "feed": FEED, "status": 404, "body": "{}"},
                {"name": "down", "feed": FEED, "status": 503, "body": "{}"},
                {
                    "name": "wrong",
                    "feed": FEED,
                    "status": 200,
                    "body": json.dumps(_doc()),
                },
                {
                    "name": "unreachable",
                    "feed": FEED,
                    "status": 200,
                    "body": "",
                    "throws": True,
                },
            ],
        }
    )
    assert got["rowUrls"][FEED] == {
        "url": f"https://motor-door.example/carbon/v1/queue/{MOTOR}/v3",
        "challengeId": MOTOR,
    }
    assert got["rowUrls"]["http://x/carbon/v1/feed/a"] is None
    assert got["rowUrls"]["https://x/other"] is None
    fetched = got["rowsFetched"]
    assert (
        fetched["ok"]["state"] == "ACCEPTED" and len(fetched["ok"]["rows"]["rows"]) == 1
    )
    assert fetched["ok"]["asked"] == [
        f"https://motor-door.example/carbon/v1/queue/{MOTOR}/v3"
    ]
    assert (
        fetched["not_served"]["state"] == "NOT_SERVED"
        and fetched["not_served"]["rows"] is None
    )
    assert (
        fetched["down"]["code"] == "rows_http_503" and fetched["down"]["rows"] is None
    )
    assert (
        fetched["wrong"]["state"] == "UNAVAILABLE" and fetched["wrong"]["rows"] is None
    )
    assert fetched["unreachable"]["code"] == "rows_unreachable"


def test_the_rows_reader_accepts_what_the_doors_writer_writes():
    """Held equal to carbon/challenge_validator/queue_public.py document_v3 once the door side is on this tree."""
    qp = pytest.importorskip("carbon.challenge_validator.queue_public")
    if not hasattr(qp, "document_v3"):
        pytest.skip("the door's v3 writer is not on this tree yet")
    challenge = type("C", (), {"challenge_id": MOTOR, "version": "1.8"})()
    q = qp.ROWS_QUANTUM_S
    rows = [
        {
            "position": 1,
            "hotkey": qp.short_hotkey("5Grw" + "A" * 40 + "utQY"),
            "state": state,
            "in_queue_s": i * q,
        }
        for i, state in enumerate(qp.ROW_STATES)
    ]
    for i, row in enumerate(rows):
        row["position"] = i + 1
    snapshot = {
        "door_state": "grading",
        "waiting_to_build": 1,
        "building_now": 1,
        "waiting_to_grade": 1,
        "grading_now": 0,
        "waits_s": [],
        "as_of_unix": 1_800_000_000.0,
        "held_for_review": None,
        "rows": {"rows": rows, "as_of_unix": 1_799_999_700.0},
    }
    text = json.dumps(qp.document_v3(snapshot, challenge))
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "row_cases": [{"name": "door", "text": text, "challenge": MOTOR}],
        }
    )["rowsChecked"]["door"]
    assert got["ok"] is True and [r["state"] for r in got["value"]["rows"]] == list(
        qp.ROW_STATES
    )


# --- the page: the rows table under the counts -----------------------------------------------------------------------------


def _page(panel, queries=(), **extra):
    done = subprocess.run(
        [NODE, str(HERE / "dashboard_queue_rows_check.cjs")],
        input=json.dumps({"panel": panel, "queries": list(queries), **extra}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        cwd=HERE,
    )
    return json.loads(done.stdout)


def _panel(rows_panel):
    queue = {k: v for k, v in _doc().items() if k != "schema"}
    return {"state": "ACCEPTED", "code": None, "queue": queue, "rows_panel": rows_panel}


def test_the_page_shows_one_row_per_submission_and_says_what_it_does_not_show():
    rows = [
        _row(1, "in grading", in_queue_s=900),
        _row(2, "building", in_queue_s=300),
        _row(3, "waiting to build"),
        _row(4, "crown check", hotkey=None, in_queue_s=3600),
    ]
    got = _page(
        _panel(
            {
                "state": "ACCEPTED",
                "code": None,
                "rows": {
                    "rows": rows,
                    "more_rows": 7,
                    "rows_as_of": "2026-11-14T13:00:00Z",
                },
            }
        )
    )
    assert got["tables"] == 1
    assert got["rows"] == [
        ["1", "5MMM…MMMM", "in grading", "15 min"],
        ["2", "5MMM…MMMM", "building", "5 min"],
        ["3", "5MMM…MMMM", "waiting to build", "under 5 min"],
        ["4", "unknown", "crown check", "1 h 0 min"],
    ]
    text = got["text"]
    assert "and 7 more" in text and "rounded down to 5 minutes" in text
    assert "crown check row means the grade beat the king's screening" in text
    assert "recipe, score or the exam is shown" in text
    assert "2026-11-14 13:00:00 UTC" in text
    assert got["inQueue"] == [
        "under 5 min",
        "under 5 min",
        "5 min",
        "15 min",
        "1 h 0 min",
        "1 h 30 min",
        "",
    ]


def test_the_find_box_filters_the_queue_rows_by_a_full_or_short_hotkey_and_says_what_is_not_listed():
    """Lead 15 Nov (miner question): the "Find a hotkey or coldkey" box also filters the door's rows; a full hotkey finds
    its row, which the door shows shortened; a submission beyond the listed rows cannot be found yet, and the page says so.
    """
    full = "5C4hRk8vzV2SMeTqF7aBq9yXcHgJuNw3LpDsEo6KtYiAZDGCJ"
    rows = [_row(i, "waiting to build") for i in range(1, 8)]
    rows.append({**_row(8, "waiting to build"), "hotkey": full[:4] + "…" + full[-4:]})
    short = (full[:4] + "…" + full[-4:]).lower()
    got = _page(
        _panel(
            {
                "state": "ACCEPTED",
                "code": None,
                "rows": {
                    "rows": rows,
                    "more_rows": 117,
                    "rows_as_of": "2026-11-15T07:40:00Z",
                },
            }
        ),
        queries=[
            [short, full.lower()],  # the full hotkey finds its shortened row
            [short, short],  # so does the short form as shown
            [short, "5c4h"],  # and a prefix
            ["5mmm…mmmm", full.lower()],  # another key's row is not matched
            [short, ""],  # an empty box hides nothing
        ],
    )
    assert got["finders"] == [
        "queue-rows ladder"
    ]  # this box filters the rows AND the ladder
    assert got["finds"][-1] == short and len(got["finds"]) == 8
    assert got["matched"] == [True, True, True, False, True]
    text = got["text"]
    assert "and 117 more, not listed yet" in text
    assert (
        "only the oldest 8 waiting submissions are shown, so a later one cannot be found here"
        in text
    )
    # a short list needs no box
    few = _page(
        _panel(
            {
                "state": "ACCEPTED",
                "code": None,
                "rows": {
                    "rows": rows[:3],
                    "more_rows": 0,
                    "rows_as_of": "2026-11-15T07:40:00Z",
                },
            }
        )
    )
    assert few["finders"] == [] and "not listed yet" not in few["text"]


def test_the_rows_come_in_pages_of_50_and_a_find_searches_every_page():
    """Lead 15 Nov (miner question, part 2): with every waiting submission listed (up to the door's 1000), the page shows
    50 rows at a time with Previous / Next; the find box matches rows on every page, so a miner at row 120 finds theirs.
    """
    rows = [_row(i, "waiting to build") for i in range(1, 121)]
    rows[119] = {**rows[119], "hotkey": "5Abc…WXYZ"}
    panel = _panel(
        {
            "state": "ACCEPTED",
            "code": None,
            "rows": {
                "rows": rows,
                "more_rows": 0,
                "rows_as_of": "2026-11-15T09:00:00Z",
            },
        }
    )
    got = _page(
        panel,
        shown=[
            [0, 0, "5mmm…mmmm", ""],  # page 0 shows at first
            [2, 0, "5abc…wxyz", ""],  # page 2 is hidden at first
            [2, 2, "5abc…wxyz", ""],  # and shown after two "Next"
            [2, 0, "5abc…wxyz", "5abc"],  # a find shows its match from any page
            [0, 0, "5mmm…mmmm", "5abc"],  # and hides the rest of the current page
            [
                None,
                0,
                "5mmm…mmmm",
                "",
            ],  # a table without pages (the ladder) shows every row
        ],
        pagerTexts=[[0, 120, None], [2, 120, None], [1, 120, 3]],
    )
    assert (
        got["page"] == 50 and len(got["rows"]) == 120
    )  # every row is in the page; only the view is paged
    assert got["hidden"] == [
        i >= 50 for i in range(120)
    ]  # the first page shows before any script runs
    assert got["pagers"] == [
        {
            "id": "queue-rows-pager",
            "text": "Previous Rows 1–50 of 120 Next",
            "disabled": [True, False],
        }
    ]
    assert got["shown"] == [True, False, True, True, False, True]
    assert got["pagerTexts"] == [
        "Rows 1–50 of 120",
        "Rows 101–120 of 120",
        "3 found of 120",
    ]
    assert "not listed yet" not in got["text"]
    # 50 rows or fewer: no pager, nothing hidden
    one = _page(
        _panel(
            {
                "state": "ACCEPTED",
                "code": None,
                "rows": {
                    "rows": rows[:50],
                    "more_rows": 0,
                    "rows_as_of": "2026-11-15T09:00:00Z",
                },
            }
        )
    )
    assert one["pagers"] == [] and not any(one["hidden"])


def test_the_page_says_so_when_nothing_is_waiting_or_the_list_is_unavailable_and_nothing_when_not_served():
    nothing = _page(
        _panel(
            {
                "state": "ACCEPTED",
                "code": None,
                "rows": {
                    "rows": [],
                    "more_rows": 0,
                    "rows_as_of": "2026-11-14T13:00:00Z",
                },
            }
        )
    )
    assert nothing["tables"] == 0 and "Nothing is waiting right now." in nothing["text"]
    down = _page(
        _panel({"state": "UNAVAILABLE", "code": "rows_http_503", "rows": None})
    )
    assert (
        down["tables"] == 0
        and "The submission list is not available right now." in down["text"]
    )
    for panel in ({"state": "NOT_SERVED", "code": None, "rows": None}, None):
        plain = _page(_panel(panel))
        assert plain["tables"] == 0 and "submission list" not in plain["text"]
        assert "Waiting to build" in plain["text"]  # the counts panel is unchanged


# --- v4: the counts of what actually runs (owner Q15, 18 Nov 2026: "grading now" showed none while 4 grades ran) ------------


def _v4_doc(**changes):
    body = {
        **_rows_doc([_row(1, "waiting to grade", in_queue_s=600)]),
        "schema": "carbon.queue.public.v4",
        "building_now": 2,
        "waiting_to_build": 10,
        "grading_now": 4,
    }
    body.update(changes)
    return body


def test_the_v4_reader_accepts_a_grading_count_and_the_rows_in_one_document():
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "v4_cases": [
                {"name": "good", "text": json.dumps(_v4_doc()), "challenge": MOTOR},
                {"name": "v3", "text": json.dumps(_rows_doc()), "challenge": MOTOR},
                {
                    "name": "extra",
                    "text": json.dumps(_v4_doc(owed=1)),
                    "challenge": MOTOR,
                },
                {
                    "name": "other",
                    "text": json.dumps(_v4_doc()),
                    "challenge": "cooling",
                },
                {
                    "name": "negative",
                    "text": json.dumps(_v4_doc(grading_now=-1)),
                    "challenge": MOTOR,
                },
                {
                    # a door before the v4 row fix: its rows say "in grading" (refused; the board falls back)
                    "name": "old_rows",
                    "text": json.dumps(
                        _v4_doc(rows=[_row(1, "in grading", in_queue_s=600)])
                    ),
                    "challenge": MOTOR,
                },
            ],
        }
    )["v4Checked"]
    assert got["good"]["ok"] is True
    assert got["good"]["value"]["queue"]["grading_now"] == 4
    assert got["good"]["value"]["queue"]["building_now"] == 2
    assert got["good"]["value"]["rows"]["rows"][0]["state"] == "waiting to grade"
    assert got["old_rows"] == {"ok": False, "code": "rows_row"}
    assert got["v3"] == {"ok": False, "code": "v4_fields"}
    assert got["extra"] == {"ok": False, "code": "v4_fields"}
    assert got["other"]["ok"] is False
    assert got["negative"] == {"ok": False, "code": "queue_counts"}
    # v1 still refuses a count above 1: the old reader and the old door are untouched
    assert _run(
        {
            "cases": [
                {
                    "name": "v1",
                    "text": json.dumps(_doc(grading_now=4)),
                    "challenge": MOTOR,
                }
            ],
            "fetches": [],
        }
    )["checked"]["v1"] == {"ok": False, "code": "queue_counts"}


def test_the_panels_use_v4_when_served_and_fall_back_to_v1_and_v3_otherwise():
    v1 = {"status": 200, "body": json.dumps(_doc())}
    v3 = {"status": 200, "body": json.dumps(_rows_doc())}
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "urls": [FEED],
            "panel_fetches": [
                {
                    "name": "v4",
                    "feed": FEED,
                    "responses": {
                        "/v4": {"status": 200, "body": json.dumps(_v4_doc())}
                    },
                },
                {
                    "name": "old_door",
                    "feed": FEED,
                    "responses": {
                        "/v4": {"status": 404, "body": "{}"},
                        "": v1,
                        "/v3": v3,
                    },
                },
                {
                    "name": "v4_down",
                    "feed": FEED,
                    "responses": {
                        "/v4": {"status": 503, "body": "{}"},
                        "": v1,
                        "/v3": v3,
                    },
                },
                {
                    "name": "v4_bad",
                    "feed": FEED,
                    "responses": {
                        "/v4": {"status": 200, "body": json.dumps(_v4_doc(owed=1))},
                        "": v1,
                        "/v3": v3,
                    },
                },
            ],
        }
    )
    assert got["v4Urls"][FEED] == {
        "url": f"https://motor-door.example/carbon/v1/queue/{MOTOR}/v4",
        "challengeId": MOTOR,
    }
    panels = got["panels"]
    v4 = panels["v4"]
    assert v4["state"] == "ACCEPTED" and v4["counts"] == "running"
    assert v4["queue"]["grading_now"] == 4 and v4["rows_panel"]["state"] == "ACCEPTED"
    assert v4["asked"] == [
        f"https://motor-door.example/carbon/v1/queue/{MOTOR}/v4"
    ]  # one fetch for both panels
    for name in ("old_door", "v4_down", "v4_bad"):
        old = panels[name]
        assert old["state"] == "ACCEPTED" and old["counts"] == "tasks", name
        assert (
            old["queue"]["grading_now"] == 1
            and old["rows_panel"]["state"] == "ACCEPTED"
        ), name


def test_the_v4_reader_accepts_what_the_doors_writer_writes():
    """Held equal to carbon/challenge_validator/queue_public.py document_v4 once the door side is on this tree."""
    qp = pytest.importorskip("carbon.challenge_validator.queue_public")
    if not hasattr(qp, "document_v4"):
        pytest.skip("the door's v4 writer is not on this tree yet")
    challenge = type("C", (), {"challenge_id": MOTOR, "version": "1.8"})()
    snapshot = {
        "door_state": "grading",
        "waiting_to_build": 12,
        "building_now": 12,
        "waiting_to_grade": 15,
        "grading_now": 1,
        "waits_s": [],
        "as_of_unix": 1_800_000_000.0,
        "held_for_review": None,
        "rows": {"rows": [], "as_of_unix": 1_799_999_700.0},
        "rows_v4": {
            "rows": [
                {
                    "position": i + 1,
                    "hotkey": None,
                    "state": state,
                    "in_queue_s": i * qp.ROWS_QUANTUM_S,
                }
                for i, state in enumerate(qp.ROW_STATES_V4)
            ],
            "as_of_unix": 1_799_999_700.0,
        },
        "running": {
            "waiting_to_build": 22,
            "building_now": 2,
            "waiting_to_grade": 7,
            "grading_now": 8,
        },
    }
    text = json.dumps(qp.document_v4(snapshot, challenge))
    got = _run(
        {
            "cases": [],
            "fetches": [],
            "v4_cases": [{"name": "door", "text": text, "challenge": MOTOR}],
        }
    )
    door = got["v4Checked"]["door"]
    assert door["ok"] is True
    assert [r["state"] for r in door["value"]["rows"]["rows"]] == list(qp.ROW_STATES_V4)
    assert {
        k: door["value"]["queue"][k]
        for k in ("waiting_to_build", "building_now", "waiting_to_grade", "grading_now")
    } == {
        "waiting_to_build": 22,
        "building_now": 2,
        "waiting_to_grade": 7,
        "grading_now": 8,
    }


def test_the_page_shows_how_many_grade_now_and_what_running_counts_mean():
    queue = {k: v for k, v in _v4_doc().items() if k in _doc()}
    queue.pop("schema")
    shown = _page(
        {
            "state": "ACCEPTED",
            "code": None,
            "queue": queue,
            "counts": "running",
            "rows_panel": None,
        }
    )["text"]
    assert "Grading now4" in shown.replace(" ", "") or "Grading now 4" in shown
    assert "a build waiting for a machine counts as waiting to build" in shown
    old = _page(_panel(None))["text"]
    assert (
        "a build waiting for a machine" not in old
    )  # a v1 door's counts are not described as running counts
