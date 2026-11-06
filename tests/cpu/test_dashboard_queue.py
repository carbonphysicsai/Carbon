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
