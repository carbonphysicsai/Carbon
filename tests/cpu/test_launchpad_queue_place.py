"""The Launchpad's "Your place in line" card (miner-ux item 2): the miner's own row, the door's state and the 24 h median
wait, read from the door's EXISTING public queue route. Nothing new is disclosed; the client imports no validator code
and these tests hold its constants to the feed's own."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from carbon.challenge_validator import queue_public
from scripts.dev.miner_launchpad import queue_place

CHALLENGE = "chip-cold-plate"
HOTKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
SHORT = HOTKEY[:4] + "…" + HOTKEY[-4:]
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def document(rows=None, *, schema=queue_public.SCHEMA_V4, more=0, state="grading", median=70200):
    rows = (
        [
            {"position": 1, "hotkey": queue_public.short_hotkey(OTHER), "state": "grading", "in_queue_s": 3600},
            {"position": 2, "hotkey": SHORT, "state": "waiting to build", "in_queue_s": 600},
        ]
        if rows is None
        else rows
    )
    body = {
        "schema": schema,
        "challenge_id": CHALLENGE,
        "challenge_version": "1.8",
        "door_state": state,
        "waiting_to_build": 1,
        "building_now": 0,
        "waiting_to_grade": 0,
        "grading_now": 1,
        "wait_24h": {
            "verdicts": 12 if median else 2,
            "median_s": median,
            "p90_s": 79200 if median else None,
            "reason": None if median else queue_public.TOO_FEW,
        },
        "as_of": "2026-11-20T01:00:00Z",
    }
    if schema != queue_public.SCHEMA:
        body.update(rows=rows, more_rows=more, rows_as_of="2026-11-20T01:00:00Z", held_for_review=None)
    return body


def test_the_constants_are_the_feeds_own():
    assert queue_place.PATH == queue_public.PATH
    assert queue_place.SCHEMA_V4 == queue_public.SCHEMA_V4
    assert queue_place.SCHEMA_V3 == queue_public.SCHEMA_V3
    assert queue_place.SCHEMA_V1 == queue_public.SCHEMA
    assert queue_place.V4_SUFFIX == queue_public.V4_SUFFIX
    assert queue_place.V3_SUFFIX == queue_public.V3_SUFFIX
    assert queue_place.ROWS_QUANTUM_S == queue_public.ROWS_QUANTUM_S
    assert queue_place.MAX_BYTES == queue_public.MAX_BYTES_V3
    assert set(queue_place.DOOR_STATES) == set(queue_public.DOOR_STATES)
    assert queue_place.short_hotkey(HOTKEY) == queue_public.short_hotkey(HOTKEY)
    assert queue_place.UPDATING == "updating"


def test_the_card_finds_the_miners_own_row_by_its_short_hotkey():
    answer = queue_place.parse(document(), CHALLENGE)
    text, state = queue_place.lines(answer, HOTKEY)
    assert state == "up"
    assert any(line.startswith("Your place: 2 of 2 (waiting to build;") for line in text)
    assert any("10 min" in line for line in text)
    # the other miner's row is never claimed
    other, _ = queue_place.lines(answer, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
    assert not any(line.startswith("Your place") for line in other)
    assert any("not in the line right now" in line for line in other)


def test_the_median_wait_is_in_hours_and_says_when_there_are_too_few_verdicts():
    text, _ = queue_place.lines(queue_place.parse(document(), CHALLENGE), HOTKEY)
    assert any("Typical wait, last 24 h: 19.5 h" in line for line in text)
    assert any("not a promise for your submission" in line for line in text)
    sparse, _ = queue_place.lines(queue_place.parse(document(median=None), CHALLENGE), HOTKEY)
    assert any("not enough verdicts yet" in line for line in sparse)


def test_a_door_that_lists_only_the_oldest_rows_says_a_later_one_may_not_show():
    answer = queue_place.parse(document(more=40), CHALLENGE)
    text, _ = queue_place.lines(answer, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
    assert any("42 waiting submissions" in line and "not shown here yet" in line for line in text)


def test_door_states_in_plain_words():
    for feed_state, card_state in (
        ("grading", "up"),
        ("re-measuring the king", "up"),
        ("paused", "paused"),
        ("draining for an update", "updating"),
    ):
        _, state = queue_place.lines(queue_place.parse(document(state=feed_state), CHALLENGE), HOTKEY)
        assert state == card_state


def test_a_v1_door_shows_the_state_and_the_wait_but_no_place():
    answer = queue_place.parse(document(schema=queue_public.SCHEMA), CHALLENGE)
    text, _ = queue_place.lines(answer, HOTKEY)
    assert any("does not list individual submissions" in line for line in text)
    assert not any(line.startswith("Your place") for line in text)


def test_no_registered_hotkey_still_shows_the_door():
    text, state = queue_place.lines(queue_place.parse(document(), CHALLENGE), None)
    assert state == "up" and queue_place.NO_HOTKEY in text


def test_the_reader_asks_v4_then_v3_then_v1_and_says_why_when_it_cannot():
    asked = []

    def opener(url, timeout):
        asked.append(url)
        return _Response(json.dumps(document()).encode())

    shown, why = queue_place.read("https://door.example/", CHALLENGE, opener=opener)
    assert why is None and shown["door_state"] == "grading"
    assert asked == ["https://door.example/carbon/v1/queue/chip-cold-plate/v4"]

    older = []

    def only_v1(url, timeout):
        older.append(url)
        if not url.endswith(CHALLENGE):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        return _Response(json.dumps(document(schema=queue_public.SCHEMA)).encode())

    shown, why = queue_place.read("https://door.example", CHALLENGE, opener=only_v1)
    assert why is None and shown["rows"] is None
    assert [url.rsplit("/", 1)[-1] for url in older] == ["v4", "v3", CHALLENGE]

    def missing(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))

    assert queue_place.read("https://door.example", CHALLENGE, opener=missing) == (
        None,
        ("unknown", queue_place.NO_ROUTE),
    )

    def down(url, timeout):
        raise urllib.error.URLError("refused")

    assert queue_place.read("https://door.example", CHALLENGE, opener=down) == (
        None,
        ("down", queue_place.WORDS_DOWN),
    )

    def updating(url, timeout):
        body = json.dumps({"status": "updating", "message": "x", "retry_after_s": 60}).encode()
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(body))

    assert queue_place.read("https://door.example", CHALLENGE, opener=updating) == (
        None,
        ("updating", queue_place.WORDS_UPDATING_ANSWER),
    )

    def huge(url, timeout):
        return _Response(b" " * (queue_place.MAX_BYTES + 1))

    assert queue_place.read("https://door.example", CHALLENGE, opener=huge)[1][0] == "unknown"
    assert queue_place.read("ftp://door.example", CHALLENGE, opener=opener) == (
        None,
        ("unknown", queue_place.NO_GRADER),
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(challenge_id="another"),
        lambda d: d.update(door_state="on fire"),
        lambda d: d.update(waiting_to_build=-1),
        lambda d: d["rows"][0].update(position=9),
        lambda d: d["rows"][0].update(hotkey=HOTKEY),
        lambda d: d.update(rows="all of them"),
        lambda d: d.update(schema="carbon.queue.public.v9"),
    ],
)
def test_an_answer_outside_the_feeds_shape_is_unreadable(mutate):
    bad = document()
    mutate(bad)
    with pytest.raises(queue_place.QueueUnreadable):
        queue_place.parse(bad, CHALLENGE)


def test_the_card_copies_only_the_fields_it_shows():
    bad = document()
    bad["recipe"] = "secret"
    bad["rows"][0]["task_id"] = "t-1"
    shown = queue_place.parse(bad, CHALLENGE)
    assert "recipe" not in shown
    assert set(shown["rows"][0]) == {"position", "hotkey", "state", "in_queue_s"}
    card = queue_place.card(
        {CHALLENGE: "https://door.example"},
        HOTKEY,
        read_one=lambda url, cid: (shown, None),
    )
    assert "secret" not in json.dumps(card) and "t-1" not in json.dumps(card)
    assert card["challenges"][0]["your_rows"] == [
        {"position": 2, "state": "waiting to build", "in_queue_s": 600}
    ]
    down = queue_place.card(
        {CHALLENGE: "https://door.example"},
        HOTKEY,
        read_one=lambda url, cid: (None, ("down", queue_place.WORDS_DOWN)),
    )
    assert down["challenges"][0]["door"] == "down"
    assert down["challenges"][0]["lines"] == [queue_place.WORDS_DOWN]
    assert queue_place.for_profile(None)["challenges"] == []


def test_the_page_reads_the_card_from_the_controller():
    root = Path(queue_place.__file__).parent
    assert '"/api/v1/page/queue"' in (root / "app.js").read_text(encoding="utf-8")
    assert 'id="overview-queue"' in (root / "index.html").read_text(encoding="utf-8")
    from scripts.dev.miner_launchpad import controller

    assert controller.QUEUE_ROUTE == "/api/v1/page/queue"
