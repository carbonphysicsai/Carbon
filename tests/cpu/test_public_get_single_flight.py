"""Live 116, 19 Nov 2026 (py-spy 18:22Z: 23 of 37 request threads rebuilt the public info document's receipt readiness at
once): every requester-independent public GET (info, king v1-v3, queue v1-v4, launch board) is one shared answer per
path, rebuilt by one caller at a time off every request lock; others get the last good answer (<= 60 s old). Signed
POSTs (submit, status, feedback, uploads) never touch it. Fixture doubles only (a rebuild is a sleep).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from carbon.battery.intake import Answer
from carbon.challenge_validator import direct_intake as di
from carbon.challenge_validator import koth_public, queue_public

CHALLENGE = SimpleNamespace(challenge_id="electric-motor-magnetics", version="1.8")
KEYS = [
    di.INFO_PATH,
    koth_public.PATH + CHALLENGE.challenge_id,
    koth_public.PATH + CHALLENGE.challenge_id + koth_public.V3_SUFFIX,
    queue_public.PATH + CHALLENGE.challenge_id + queue_public.V4_SUFFIX,
    di.FEED_PATH + CHALLENGE.challenge_id,
]


def _door(delay=0.0, status=200):
    intake = object.__new__(di.DirectRecipeIntake)
    intake.challenge = CHALLENGE
    intake._write = threading.Lock()
    intake._note_recipe_digest = lambda result: None
    intake.door = SimpleNamespace(evaluate=lambda submitted: {"kind": "OUTCOME"})
    built = {"n": 0, "inside": 0, "most": 0, "delay": delay, "status": status}
    guard = threading.Lock()

    def answer(kind):
        def build(*_args):
            with guard:
                built["n"] += 1
                built["inside"] += 1
                built["most"] = max(built["most"], built["inside"])
                n = built["n"]
            time.sleep(built["delay"])
            with guard:
                built["inside"] -= 1
            return Answer(built["status"], {"doc": kind, "build": n, "signed": "sig-" + kind})

        return build

    intake.public = answer("info")
    intake._koth = answer("koth")
    intake._queue = answer("queue")
    intake._board = answer("board")
    return intake, built


def _get(intake, path):
    return di.DirectRecipeIntake.route(intake, "GET", path, {}, b"")


def test_a_flood_of_every_public_get_never_holds_a_submit():
    intake, built = _door()
    for key in KEYS:
        _get(intake, key)  # prime every shared answer
    primed = built["n"]
    for entry in intake._public_state.values():
        entry["at"] -= di.PUBLIC_GET_FRESH_S + 1  # every answer now due a rebuild (and fresh again once rebuilt)
    built["delay"] = 1.0
    done = {}

    def submit(i):
        di.DirectRecipeIntake._admit(intake, SimpleNamespace(hotkey=f"5Miner{i}"))
        done[i] = time.monotonic()

    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as pool:
        gets = [pool.submit(_get, intake, KEYS[i % len(KEYS)]) for i in range(100)]
        subs = [pool.submit(submit, i) for i in range(5)]
        for f in subs:
            f.result(20)
        answers = [g.result(20) for g in gets]
    assert max(done.values()) - began < 1.5  # submits never wait out a flood of rebuilds
    assert built["n"] - primed <= len(KEYS)  # at most one rebuild per path
    assert all(a.status == 200 and a.body["signed"].startswith("sig-") for a in answers)


def test_each_endpoint_serves_exactly_what_it_built_and_a_copy_per_caller():
    intake, built = _door()
    for key in KEYS:
        first = _get(intake, key)
        again = _get(intake, key)
        assert again == first  # same document (signed bytes included), served from the shared answer
        again.body["doc"] = "changed by a caller"
        assert _get(intake, key) == first  # a caller's copy never changes the shared one
    assert built["n"] == len(KEYS)


def test_a_quoted_path_is_the_same_document_and_an_unknown_one_is_never_cached():
    intake, built = _door()
    key = KEYS[1]
    assert _get(intake, key.replace("-", "%2D")) == _get(intake, key)
    assert built["n"] == 1
    for _ in range(3):
        _get(intake, koth_public.PATH + "another-challenge")  # answered live (a 404), never stored
    assert set(intake._public_state) == {key}


def test_a_failed_rebuild_keeps_the_last_good_answer_for_others(monkeypatch):
    intake, built = _door()
    good = _get(intake, KEYS[0])
    monkeypatch.setattr(di, "PUBLIC_GET_FRESH_S", 0.0)
    built["status"] = 503
    assert _get(intake, KEYS[0]).status == 503  # its own caller gets its own result
    monkeypatch.setattr(di, "PUBLIC_GET_FRESH_S", 10.0)
    assert _get(intake, KEYS[0]) == good  # the shared answer is still the good one


def test_a_copy_past_the_stale_bound_is_never_served(monkeypatch):
    intake, built = _door()
    _get(intake, KEYS[0])
    intake._public_state[KEYS[0]]["at"] -= di.PUBLIC_GET_STALE_MAX_S + 1  # the last copy is too old
    built["delay"] = 0.2
    with ThreadPoolExecutor(max_workers=4) as pool:
        out = [pool.submit(_get, intake, KEYS[0]) for _ in range(6)]
        docs = [f.result(10) for f in out]
    assert {d.body["build"] for d in docs} == {2}  # everyone got the rebuilt answer, nobody the old one
    assert di.PUBLIC_GET_STALE_MAX_S <= 60


def test_signed_posts_never_reach_the_shared_answers(monkeypatch):
    """Only a GET is shared: a POST (submit, status, feedback, an upload chunk: each signed by its own hotkey) never
    reads or fills the shared answers."""
    intake, _built = _door()

    def never(*_a, **_k):
        raise AssertionError("a POST reached the shared public answers")

    monkeypatch.setattr(di.DirectRecipeIntake, "_public_get", never)
    answer = di.DirectRecipeIntake.route(intake, "POST", di.FEED_PATH + "x", {}, b"")
    assert answer.status in (404, 405)
    assert "_public_state" not in intake.__dict__
