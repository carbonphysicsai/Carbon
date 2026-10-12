"""DASHBOARD-02 S1b: VALIDATOR-33 A's feed fields (#1143) in board.v2.

The Validator's feed (same schema, `carbon.validator.score-feed.v1`) adds the
chain time it was read at, the next rotation block, the king from the weights
publisher's winner ledger with its handovers, and the rule-tagged target to
beat. These tests hold the dashboard's reading of them: malformed values refuse
the whole document, absent ones are null with a reason (older feeds keep
working), the ledger king fills the board's king only when it is the released
incumbent, and the target's posted values show whatever the rules card's
status. Every value here is synthetic (fixtures.chain_documents, FIXTURE).
"""

from __future__ import annotations

import json

import pytest
from test_dashboard_board_v2 import (
    ALLOWED,
    CHAIN,
    FORBIDDEN,
    FUTURE,
    NOW,
    _alpha,
    _card,
    _nulls_have_reasons,
    _paths,
    _v2,
)

from carbon.dashboard import board_v2, feed, fixtures


def _chain(released_king=True):
    if released_king:
        return fixtures.chain_document(
            "fixture-challenge-eta", "gpu:FIXTURE-GPU", seed=8
        )
    return fixtures.chain_document(
        "fixture-challenge-theta", "cpu", seed=9, released_king=False
    )


def _chain_boards():
    return [
        _v2(d, now, card=card)
        for d in fixtures.chain_documents()
        for now in (NOW, NOW + 10**6)
        for card in ("match", None, _card(d, "sha256:" + "d" * 64))
    ]


def test_chain_fixtures_are_labelled_fixture():
    for document in fixtures.chain_documents():
        assert "FIXTURE" in document["labels"]
        assert document["king"]["hotkey"].startswith("fixture-")


def test_chain_boards_keep_the_contract():
    seen = set()
    for board in _chain_boards():
        _nulls_have_reasons(board)
        seen |= _paths(board)
        text = json.dumps(board)
        assert "qualified" not in text.lower()
        # The comparison's other keys never reach a board.
        assert "bootstrap_seed" not in text and "12345" not in text
    reasons = {p for p in seen if p.endswith("reasons.*")}
    assert seen - reasons <= ALLOWED | FUTURE, sorted(seen - reasons - ALLOWED - FUTURE)
    assert seen >= CHAIN, sorted(CHAIN - seen)
    assert not {s.rstrip("[]") for p in seen for s in p.split(".")} & FORBIDDEN


def test_the_ledger_king_fills_the_released_kings_fields():
    body = _chain()
    board = _v2(fixtures.sign(body))
    king, ledger = board["king"], body["king"]
    assert king["hotkey"] == ledger["hotkey"]
    assert king["hotkey"] == body["leaderboard"]["incumbent"]["hotkey"]
    assert king["uid"] == 7 and king["coldkey"] == "fixture-coldkey-07"
    assert king["submission_id"] == ledger["submission_id"]
    crowned = ledger["crowned_utc_ms"] // 1000
    assert king["crowned_utc"] == king["since_utc"] == board_v2.utc_text(crowned)
    assert board_v2.utc_seconds(king["crowned_utc"]) == crowned
    # Held at the feed's chain time, not the build's clock.
    as_of = body["as_of_block"]["timestamp_ms"]
    assert king["held_for"] == (as_of - ledger["crowned_utc_ms"]) // 1000
    assert king["share_now"] == 0.5
    assert king["next_halving_utc"] == board_v2.utc_text(
        ledger["next_halving_utc_ms"] // 1000
    )
    assert king["defences"] == ledger["challenges_survived"] == 2
    assert king["eligible"] is True
    assert king["eligibility_reason"] == "fixture-final"
    # The feed carries no epochs.
    for key in ("crowned_epoch", "next_halving_epoch"):
        assert king[key] is None and king["reasons"][key] == "not_in_feed"


def test_a_ledger_king_not_yet_released_fills_nothing():
    body = _chain(released_king=False)
    board = _v2(fixtures.sign(body))
    king = board["king"]
    assert king["hotkey"] == body["leaderboard"]["incumbent"]["hotkey"]
    assert king["hotkey"] != body["king"]["hotkey"]
    for key in (
        "uid",
        "coldkey",
        "since_utc",
        "crowned_utc",
        "held_for",
        "share_now",
        "next_halving_utc",
        "defences",
        "eligible",
        "eligibility_reason",
    ):
        assert king[key] is None, key
        assert king["reasons"][key] == "king_not_released", key
    # The handovers still name the new king, as the signed feed does.
    assert board["history"]["kings"][-1]["hotkey"] == body["king"]["hotkey"]


def test_an_unpaid_king_has_no_next_halving():
    body = _chain()
    body["king"].update(eligible=False, share_now=0.0, next_halving_utc_ms=None)
    king = _v2(fixtures.sign(body))["king"]
    assert king["share_now"] == 0.0 and king["eligible"] is False
    assert king["next_halving_utc"] is None
    assert king["reasons"]["next_halving_utc"] == "king_not_paid"


def test_handovers_and_reigns_come_from_the_feed():
    body = _chain()
    history = _v2(fixtures.sign(body))["history"]
    handovers = body["handovers"]
    assert [h["to_hotkey"] for h in history["handovers"]] == [
        h["to_hotkey"] for h in handovers
    ]
    first, last = history["handovers"]
    assert first["from_hotkey"] is None
    assert first["reasons"]["from_hotkey"] == "not_in_feed"
    assert last["from_hotkey"] == handovers[0]["to_hotkey"]
    assert last["kind"] == "FINAL" and last["eligible"] is True
    assert last["utc"] == board_v2.utc_text(handovers[1]["utc_ms"] // 1000)
    reigns = history["kings"]
    assert reigns[0]["until_utc"] == reigns[1]["crowned_utc"] == last["utc"]
    assert reigns[1]["until_utc"] is None
    assert reigns[1]["reasons"]["until_utc"] == "reigning"
    # A hotkey the feed does not name (a canary) stays null.
    body["handovers"][1]["to_hotkey"] = None
    named = _v2(fixtures.sign(body))["history"]
    assert named["handovers"][1]["to_hotkey"] is None
    assert named["kings"][1]["reasons"]["hotkey"] == "not_in_feed"


@pytest.mark.parametrize("card", ["match", None])
def test_the_target_is_the_validators_posted_values_whatever_the_card(card):
    body = _chain()
    target = _v2(fixtures.sign(body), card=card)["target_to_beat"]
    posted = body["target_to_beat"]
    assert target["kind"] == posted["kind"]
    assert target["posted_margin"] == posted["final_margin_rel"]
    assert target["screening_margin"] == posted["screening_margin_rel"]
    guard = {k: v for k, v in target["noise_guard"].items() if k != "reasons"}
    assert guard == {
        k: posted["final_comparison"][k] for k in board_v2.NOISE_GUARD_KEYS
    }
    score = target["registered_score"]
    assert score["candidate"] == posted["score"]["candidate"]
    assert score["decision"] == posted["score"]["decision"]
    assert target["gates"] == posted["gates"]
    assert target["value"] is None and target["reasons"]["value"] == "not_in_feed"


def test_a_target_without_a_registered_score_says_so():
    body = _chain()
    body["target_to_beat"].update(kind="accuracy_margin_then_final", score=None)
    target = _v2(fixtures.sign(body))["target_to_beat"]
    assert target["registered_score"] is None
    assert target["reasons"]["registered_score"] == "no_registered_score"


def test_the_next_release_is_the_next_rotation_estimated_from_chain_time():
    body = _chain()
    board = _v2(fixtures.sign(body))
    as_of = body["as_of_block"]
    block = body["release"]["next_rotation_block"]
    assert board["next_release"]["next_block"] == block
    want = as_of["timestamp_ms"] // 1000 + (block - as_of["number"]) * 12
    assert board["next_release"]["next_utc"] == board_v2.utc_text(want)
    assert board["as_of_block"] == {
        "number": as_of["number"],
        "hash": as_of["hash"],
        "timestamp_utc": board_v2.utc_text(as_of["timestamp_ms"] // 1000),
    }
    # The round period stays the rules card's; the next round has no feed field.
    no_card = _v2(fixtures.sign(body), card=None)
    assert no_card["next_round"]["every"] is None
    assert no_card["next_round"]["reasons"]["every"] == "rules_unavailable"
    for key in ("next_block", "next_utc"):
        assert no_card["next_round"]["reasons"][key] == "not_in_feed"
    # Without chain time the block stays and its time is null.
    del body["as_of_block"]
    board = _v2(fixtures.sign(body))
    assert board["next_release"]["next_block"] == block
    assert board["next_release"]["next_utc"] is None
    assert board["next_release"]["reasons"]["next_utc"] == "not_in_feed"


@pytest.mark.parametrize(
    ("chain_age", "generated_age", "phase"),
    [(600, 10**6, "LIVE"), (7_201, 0, "STALE"), (7_200, 10**6, "LIVE")],
)
def test_the_age_is_measured_from_chain_time(chain_age, generated_age, phase):
    body = _chain()
    body["as_of_block"]["timestamp_ms"] = (NOW - chain_age) * 1000
    body["generated_at"] = board_v2.utc_text(NOW - generated_age)
    board = _v2(fixtures.sign(body))
    assert board["phase"] == phase
    assert board["freshness"]["age_seconds"] == chain_age
    assert board["freshness"]["basis"] == "as_of_block"
    # restamp keeps measuring from the chain time.
    later = board_v2.restamp(board, NOW + 10)
    assert later["freshness"]["age_seconds"] == chain_age + 10
    assert _v2(fixtures.sign(_alpha()))["freshness"]["basis"] == "generated_at"


@pytest.mark.parametrize(
    "drop", ["as_of_block", "king", "handovers", "target_to_beat", "release"]
)
def test_an_older_feed_without_a_field_keeps_working(drop):
    body = _chain()
    if drop == "release":
        del body["release"]["next_rotation_block"]
    else:
        del body[drop]
    board = _v2(fixtures.sign(body))
    _nulls_have_reasons(board)
    if drop == "as_of_block":
        assert board["as_of_block"] is None
        assert board["reasons"]["as_of_block"] == "not_in_feed"
        assert board["king"]["held_for"] is None
        assert board["freshness"]["basis"] == "generated_at"
    elif drop == "king":
        for key in ("uid", "share_now", "next_halving_utc", "defences"):
            assert board["king"]["reasons"][key] == "not_in_feed"
    elif drop == "handovers":
        assert board["history"]["handovers"] is None
        assert board["history"]["reasons"]["kings"] == "not_in_feed"
    elif drop == "target_to_beat":
        target = board["target_to_beat"]
        for key in ("kind", "posted_margin", "noise_guard", "registered_score"):
            assert target[key] is None and target["reasons"][key] == "not_in_feed"
    else:
        assert board["next_release"]["next_block"] is None
        assert board["next_release"]["reasons"]["next_utc"] == "not_in_feed"


def _set(body, path, value):
    *parents, last = path
    here = body
    for key in parents:
        here = here[key]
    here[last] = value


#: (path, value, refusal code): each refuses the whole document.
MALFORMED = [
    (("as_of_block",), [], "as_of_block_invalid"),
    (("as_of_block", "number"), -1, "as_of_block_invalid"),
    (("as_of_block", "number"), 1.5, "as_of_block_invalid"),
    (("as_of_block", "hash"), "0xabc", "as_of_block_invalid"),
    (("as_of_block", "timestamp_ms"), None, "as_of_block_invalid"),
    (("as_of_block", "timestamp_ms"), 1.0e12, "as_of_block_invalid"),
    (("as_of_block", "timestamp_ms"), 10**15, "as_of_block_invalid"),
    (("release", "next_rotation_block"), "soon", "release_invalid"),
    (("king",), "fixture-miner-01", "king_invalid"),
    (("king", "hotkey"), "<b>", "hotkey_invalid"),
    (("king", "coldkey"), "5bad", "hotkey_invalid"),
    (("king", "uid"), -3, "king_invalid"),
    (("king", "share_now"), 0.1234567, "unrounded_value"),
    (("king", "share_now"), 1.5, "king_invalid"),
    (("king", "share_now"), "0.5", "king_invalid"),
    (("king", "share_now"), True, "king_invalid"),
    (("king", "eligible"), 1, "king_invalid"),
    (("king", "crowned_utc_ms"), -1, "king_invalid"),
    (("king", "next_halving_utc_ms"), 1.5, "king_invalid"),
    (("king", "challenges_survived"), 2.0, "king_invalid"),
    (("king", "reason"), "<script>", "king_invalid"),
    (("handovers",), {}, "handovers_invalid"),
    (("handovers", 0), "x", "handovers_invalid"),
    (("handovers", 0, "utc_ms"), "yesterday", "handovers_invalid"),
    (("handovers", 0, "to_hotkey"), "<b>", "hotkey_invalid"),
    (("handovers", 0, "eligible"), "yes", "handovers_invalid"),
    (("target_to_beat",), [], "target_invalid"),
    (("target_to_beat", "kind"), "Margin <b>", "target_invalid"),
    (("target_to_beat", "kind"), None, "target_invalid"),
    (("target_to_beat", "final_margin_rel"), -0.01, "target_invalid"),
    (("target_to_beat", "screening_margin_rel"), "5%", "target_invalid"),
    (("target_to_beat", "final_comparison"), "paired", "target_invalid"),
    (("target_to_beat", "final_comparison", "alpha"), 1.5, "target_invalid"),
    (("target_to_beat", "final_comparison", "n_min"), 2.5, "target_invalid"),
    (("target_to_beat", "score"), "registered", "target_invalid"),
    (("target_to_beat", "score", "candidate"), "<b>", "target_invalid"),
    (("target_to_beat", "score", "registry_sha256"), "abc", "target_invalid"),
    (("target_to_beat", "gates"), "eligibility", "target_invalid"),
    (("target_to_beat", "gates"), ["Eligibility!"], "target_invalid"),
]


@pytest.mark.parametrize(("path", "value", "code"), MALFORMED)
def test_a_malformed_chain_field_is_refused_whole(path, value, code):
    body = _chain()
    _set(body, path, value)
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert caught.value.code == code


def test_a_production_feed_with_chain_fields_projects():
    """The same fields under a production key and SS58-shaped keys."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )
    text = json.dumps(_chain()).replace("fixture-miner-0", "5" + "G" * 44 + "A")
    text = text.replace("fixture-coldkey-0", "5" + "C" * 44 + "A")
    body = json.loads(text)
    body["labels"] = ["DEVELOPMENT", "TESTNET"]
    trust = feed.Trust(keys=frozenset({public}))
    board = board_v2.project(feed.project(fixtures.sign(body, key), trust), NOW)
    assert board["fixture"] is False
    assert board["king"]["coldkey"] == "5" + "C" * 44 + "A7"
    assert board["king"]["share_now"] == 0.5
