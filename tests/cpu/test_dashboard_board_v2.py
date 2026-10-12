"""DASHBOARD-02 S1: the board.v2 data contract.

board.v2 is projected from the verified board.v1 model only. These tests hold
it to its contract: each phase, a reason for every null, no key outside the
allow-list, canaries only as a count, one era per rule digest, and FIXTURE
kept apart from production.
"""

from __future__ import annotations

import copy
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.dashboard import board_v2, build, feed, fixtures

NOW = fixtures.FIXTURE_NOW

# Every key path a board.v2 may hold. `*` is a data key (a hotkey, a gate name,
# a field a reason is given for); `[]` is a list item.
ALLOWED = {
    "schema",
    "source_schema",
    "fixture",
    "labels",
    "labels[]",
    "challenge",
    "challenge.id",
    "challenge.version",
    "challenge.rule",
    "challenge.rule_digest",
    "era",
    "device_class",
    "slug",
    "version",
    "generated_at",
    "feed",
    "feed.key_id",
    "feed.digest",
    "feed_state",
    "feed_state.state",
    "feed_state.code",
    "phase",
    "freshness",
    "freshness.age_seconds",
    "freshness.stale_after_seconds",
    "block_seconds",
    "ranking_section",
    "ranking_section.name",
    "ranking_section.display",
    "ranking_section.unit",
    "ranking_section.sense",
    "ranking_section.label",
    "king",
    "king.hotkey",
    "king.uid",
    "king.submission_id",
    "king.section",
    "king.value",
    "king.registered_score",
    "king.since_block",
    "king.since_utc",
    "king.margin",
    "king.runner_up",
    "king.challenger_state",
    "king.gates",
    "king.gates.*",
    "king.crowned_epoch",
    "king.share_now",
    "king.next_halving_epoch",
    "king.defences",
    "target_to_beat",
    "target_to_beat.value",
    "target_to_beat.posted_margin",
    "target_to_beat.noise_guard",
    "championship",
    "championship.rounds",
    "championship.entry",
    "championship.entry.trigger_bar",
    "championship.entry.king_screening_display",
    "championship.entry.coldkeys",
    "rules",
    "rules.status",
    "rules.card_digest",
    "eligible_leaderboard.label",
    "eligible_leaderboard",
    "eligible_leaderboard.section",
    "eligible_leaderboard.release_lag",
    "eligible_leaderboard.release_lag.blocks",
    "eligible_leaderboard.release_lag.seconds",
    "eligible_leaderboard.release_lag.hours",
    "eligible_leaderboard.entries",
    "eligible_leaderboard.entries[]",
    "eligible_leaderboard.entries[].rank",
    "eligible_leaderboard.entries[].hotkey",
    "eligible_leaderboard.entries[].uid",
    "eligible_leaderboard.entries[].screening_value",
    "eligible_leaderboard.entries[].registered_score",
    "eligible_leaderboard.entries[].best_at_block",
    "eligible_leaderboard.entries[].challenger_state",
    "eligible_leaderboard.entries[].is_king",
    "eligible_leaderboard.grain_pct",
    "eligible_leaderboard.coldkeys",
    "eligible_leaderboard.coldkeys[]",
    "eligible_leaderboard.coldkeys[].coldkey",
    "eligible_leaderboard.coldkeys[].rank",
    "eligible_leaderboard.coldkeys[].displayed_score",
    "eligible_leaderboard.coldkeys[].status",
    "eligible_leaderboard.coldkeys[].hotkeys",
    "eligible_leaderboard.coldkeys[].hotkeys[]",
    "eligible_leaderboard.coldkeys[].best_submission_id",
    "eligible_leaderboard.coldkeys[].displayed_at_block",
    "history",
    "history.era",
    "history.section",
    "history.kings",
    "history.points",
    "history.points.*",
    "history.points.*[]",
    "history.points.*[].receipt_block",
    "history.points.*[].value",
    "next_round",
    "next_round.every",
    "next_round.every.blocks",
    "next_round.every.seconds",
    "next_round.every.hours",
    "next_round.next_block",
    "next_round.next_utc",
    "next_release",
    "next_release.predicate",
    "next_release.retire_at",
    "next_release.lag",
    "next_release.lag.blocks",
    "next_release.lag.seconds",
    "next_release.lag.hours",
    "next_release.next_block",
    "next_release.next_utc",
    "next_release.released_windows",
    "gates",
    "gates.display",
    "gates.unit",
    "gates.king",
    "gates.king.*",
    "gates.names",
    "gates.names[]",
    "gates.submissions_with_gates",
    "gates.failing",
    "gates.failing.*",
    "excluded_canaries",
}
# The championship's documented shape (VALIDATOR-32 rev 7 §5): allowed, but
# not emitted until the feed carries it.
FUTURE = {
    *(f"championship.rounds[].{k}" for k in board_v2.CHAMPIONSHIP_ROUND_KEYS),
    "championship.rounds[]",
    "championship.rounds[].entrants[]",
    *(
        f"championship.rounds[].entrants[].{k}"
        for k in board_v2.CHAMPIONSHIP_ENTRANT_KEYS
    ),
    "championship.entry.coldkeys[]",
    "championship.entry.coldkeys[].coldkey",
    *(
        f"championship.entry.coldkeys[].{k}"
        for k in board_v2.CHAMPIONSHIP_ENTRY_COLDKEY_KEYS
    ),
}
# Per-case, input and prediction data never appear in a board.v2, at any depth.
FORBIDDEN = {
    "case",
    "cases",
    "case_id",
    "case_ids",
    "detail",
    "error",
    "input",
    "inputs",
    "prediction",
    "predictions",
    "outputs",
    "seed",
    "seeds",
    "draws",
}
DATA_KEYED = {"king.gates", "gates.king", "gates.failing", "history.points"}


def _paths(value, path="", out=None):
    out = set() if out is None else out
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "reasons":
                out.add(f"{path}.reasons".lstrip(".") + ".*")
                continue
            step = "*" if path in DATA_KEYED else key
            here = f"{path}.{step}" if path else step
            out.add(here)
            _paths(child, here, out)
    elif isinstance(value, list):
        out.add(path + "[]")
        for child in value:
            _paths(child, path + "[]", out)
    return out


def _nulls_have_reasons(value, path="", data=False):
    if isinstance(value, list):
        for child in value:
            _nulls_have_reasons(child, path + "[]")
        return
    if not isinstance(value, dict):
        return
    reasons = value.get("reasons", {})
    for key, child in value.items():
        if key == "reasons":
            continue
        here = f"{path}.{key}" if path else key
        if child is None and not data and here not in ("feed_state.code",):
            assert reasons.get(key) in board_v2.REASONS, here
        _nulls_have_reasons(child, here, data=here in DATA_KEYED)
    for key in reasons:
        assert value.get(key, "absent") is None, f"{path}.reasons.{key}"


CARD_DIGEST = "sha256:" + "c" * 64


def _card(document, rule_digest=None):
    """A verified rules card's summary for the document's rule (synthetic)."""
    digest = rule_digest or document["challenge"]["rule_digest"]
    return {"digest": CARD_DIGEST, "rule": {"digest": digest}}


def _v2(document, now=NOW, trust=None, card="match"):
    card = _card(document) if card == "match" else card
    return board_v2.project(
        feed.project(document, trust or fixtures.fixture_trust()), now, card
    )


def _alpha():
    return fixtures.board_document("fixture-challenge-alpha", "gpu:FIXTURE-GPU", seed=1)


def _all_fixture_boards():
    return [
        _v2(d, now, card=card)
        for d in fixtures.documents() + fixtures.phase_documents()
        for now in (NOW, NOW + 10**6)
        for card in ("match", None, _card(d, "sha256:" + "d" * 64))
    ]


RULE_STATEMENTS = (
    ("challenge", "rule"),
    ("next_round", "every"),
    ("next_release", "predicate"),
    ("next_release", "retire_at"),
    ("next_release", "lag"),
    ("eligible_leaderboard", "release_lag"),
)


def test_rules_ok_when_the_card_matches_the_feed_rule():
    board = _v2(fixtures.sign(_alpha()))
    assert board["rules"]["status"] == "OK"
    assert board["rules"]["card_digest"] == CARD_DIGEST
    for part, key in RULE_STATEMENTS:
        assert board[part][key] is not None, (part, key)


@pytest.mark.parametrize(
    ("card", "status", "reason"),
    [
        (None, "UNAVAILABLE", "rules_unavailable"),
        (
            {"digest": CARD_DIGEST, "rule": {"digest": "sha256:" + "d" * 64}},
            "DIGEST_MISMATCH",
            "rules_digest_mismatch",
        ),
    ],
)
def test_rule_statements_are_withheld_without_a_matching_card(card, status, reason):
    good = _v2(fixtures.sign(_alpha()))
    board = _v2(fixtures.sign(_alpha()), card=card)
    assert board["rules"]["status"] == status
    if card is None:
        assert board["rules"]["card_digest"] is None
        assert board["rules"]["reasons"]["card_digest"] == "rules_unavailable"
    else:
        assert board["rules"]["card_digest"] == CARD_DIGEST
    for part, key in RULE_STATEMENTS:
        assert board[part][key] is None, (part, key)
        assert board[part]["reasons"][key] == reason, (part, key)
    # Numbers measured in the feed stay.
    assert board["king"] == good["king"]
    entries, kept = board["eligible_leaderboard"], good["eligible_leaderboard"]
    assert entries["entries"] == kept["entries"]
    assert board["history"] == good["history"]
    assert board["challenge"]["rule_digest"] == good["challenge"]["rule_digest"]


@pytest.mark.parametrize(
    "card",
    [
        {"rule": {"digest": "x"}},
        {"digest": "sha256:short", "rule": {"digest": "x"}},
        {"digest": CARD_DIGEST},
        "card",
    ],
)
def test_a_malformed_rules_card_summary_is_an_error(card):
    with pytest.raises(ValueError):
        _v2(fixtures.sign(_alpha()), card=card)


def test_builds_have_no_rules_card_configured(tmp_path):
    build.build(tmp_path / "site", fixtures.documents(), fixtures.fixture_trust())
    for path in (tmp_path / "site" / "data" / "v2").glob("*.json"):
        board = json.loads(path.read_text(encoding="utf-8"))
        assert board["rules"]["status"] == "UNAVAILABLE"


def test_every_fixture_phase_is_covered():
    phases = [_v2(d)["phase"] for d in fixtures.documents()]
    assert phases == ["LIVE"] * 3
    cutover, stale, shown, sealed = (_v2(d) for d in fixtures.phase_documents())
    assert cutover["phase"] == "PRE_FIRST_RELEASE"
    assert stale["phase"] == "STALE"
    assert shown["phase"] == sealed["phase"] == "LIVE"
    for board in (cutover, stale, shown, sealed):
        assert board["fixture"] is True and "FIXTURE" in board["labels"]


def _ladder_boards():
    return [_v2(d)["eligible_leaderboard"] for d in fixtures.phase_documents()[2:]]


def test_ladder_fixtures_cover_every_coldkey_status():
    shown, sealed = _ladder_boards()
    statuses = {r["status"] for r in shown["coldkeys"] + sealed["coldkeys"]}
    assert statuses == {"SHOWN", "NO_IMPROVEMENT_BEYOND_GRAIN", "SEALED_UNTIL_GRAIN"}
    assert [r["rank"] for r in shown["coldkeys"]] == list(
        range(1, len(shown["coldkeys"]) + 1)
    )
    for row in shown["coldkeys"]:
        assert row["displayed_score"] is not None and row["hotkeys"]
    for row in sealed["coldkeys"]:
        assert row["displayed_score"] is None
        assert row["reasons"]["displayed_score"] == "sealed_until_grain"
    assert shown["grain_pct"] == 0.5
    no_card = _v2(fixtures.phase_documents()[2], card=None)["eligible_leaderboard"]
    assert no_card["grain_pct"] is None
    assert no_card["reasons"]["grain_pct"] == "rules_unavailable"


def test_coldkeys_are_null_until_the_feed_carries_a_ladder():
    board = _v2(fixtures.sign(_alpha()))["eligible_leaderboard"]
    assert board["coldkeys"] is None
    assert board["reasons"]["coldkeys"] == "not_in_feed"


def _laddered():
    return fixtures.ladder_document(
        "fixture-challenge-epsilon", "gpu:FIXTURE-GPU", seed=6, sealed=False
    )


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"status": "SEALED_UNTIL_GRAIN"}, "ladder_sealed_value"),
        ({"displayed_score": None}, "ladder_invalid"),
        ({"status": "QUALIFIED"}, "ladder_invalid"),
        ({"displayed_score": 0.12345}, "unrounded_value"),
        ({"hotkeys": "fixture-miner-01"}, "ladder_invalid"),
        ({"coldkey": "<b>"}, "hotkey_invalid"),
        ({"best_submission_id": "<b>x</b>"}, "ladder_invalid"),
        ({"displayed_at_block": 1.5}, "ladder_invalid"),
        ({"displayed_at_block": -1}, "ladder_invalid"),
    ],
)
def test_a_malformed_ladder_is_refused_whole(change, code):
    body = _laddered()
    body["leaderboard"]["ladder"]["coldkeys"][0].update(change)
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert caught.value.code == code


@pytest.mark.parametrize(
    ("grain", "code"),
    [(None, "ladder_grain_unposted"), (0, "ladder_invalid"), ("2%", "ladder_invalid")],
)
def test_a_shown_score_needs_a_posted_grain(grain, code):
    body = _laddered()
    body["leaderboard"]["ladder"]["grain_pct"] = grain
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert caught.value.code == code


@pytest.mark.parametrize("status", ["SHOWN", "NO_IMPROVEMENT_BEYOND_GRAIN"])
def test_only_sealed_entries_while_the_grain_is_unposted(status):
    body = _laddered()
    body["leaderboard"]["ladder"]["grain_pct"] = None
    for row in body["leaderboard"]["ladder"]["coldkeys"]:
        row["status"] = status
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert caught.value.code == "ladder_grain_unposted"


def test_a_list_shaped_ladder_is_refused():
    body = _laddered()
    body["leaderboard"]["ladder"] = body["leaderboard"]["ladder"]["coldkeys"]
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert caught.value.code == "ladder_invalid"


def test_ladder_grain_and_coldkey_fields_in_v2():
    shown = _v2(fixtures.sign(_laddered()))["eligible_leaderboard"]
    assert shown["grain_pct"] == 0.5
    for row in shown["coldkeys"]:
        assert row["best_submission_id"] and type(row["displayed_at_block"]) is int
    sealed_doc = fixtures.phase_documents()[3]
    sealed = _v2(sealed_doc)["eligible_leaderboard"]
    assert sealed["grain_pct"] is None
    assert sealed["reasons"]["grain_pct"] == "grain_human_input"
    for row in sealed["coldkeys"]:
        assert row["reasons"]["displayed_at_block"] == "not_in_feed"
    assert _v2(fixtures.sign(_alpha()))["eligible_leaderboard"]["reasons"][
        "grain_pct"
    ] == ("not_in_feed")


def test_a_ladder_shows_only_the_pooled_score():
    body = _laddered()
    row = body["leaderboard"]["ladder"]["coldkeys"][0]
    row["cases"] = [{"case_id": "c-1", "error": 0.5}]
    row["grain"] = 0.0225
    text = json.dumps(_v2(fixtures.sign(body)))
    assert '"cases"' not in text and "c-1" not in text and "0.0225" not in text


def test_live_board_carries_king_leaderboard_and_history():
    board = _v2(fixtures.sign(_alpha()))
    v1 = feed.project(fixtures.sign(_alpha()), fixtures.fixture_trust())
    assert board["phase"] == "LIVE" and board["freshness"]["age_seconds"] == 3600
    king = board["king"]
    assert king["hotkey"] == v1["incumbent"]["hotkey"]
    assert king["since_block"] == v1["incumbent"]["since_block"]
    assert king["value"] == v1["incumbent"]["sections"]["accuracy"]
    assert king["section"] == "accuracy"
    runner = next(r for r in v1["standing"] if r["hotkey"] != king["hotkey"])
    assert king["runner_up"] == runner["hotkey"]
    assert king["margin"] == round(runner["best"]["accuracy"] - king["value"], 3)
    entries = board["eligible_leaderboard"]["entries"]
    assert [e["rank"] for e in entries] == [r["rank"] for r in v1["standing"]]
    assert [e["screening_value"] for e in entries] == [
        r["best"]["accuracy"] for r in v1["standing"]
    ]
    assert sum(e["is_king"] for e in entries) == 1
    assert board["eligible_leaderboard"]["release_lag"] == {
        "blocks": 36_000,
        "seconds": 432_000,
        "hours": 120.0,
    }
    assert board["next_round"]["every"] == {
        "blocks": 7_200,
        "seconds": 86_400,
        "hours": 24.0,
    }
    assert board["history"]["points"] and board["history"]["era"] == board["era"]
    assert board["next_release"]["released_windows"] == len(v1["released_windows"])


def test_ranking_section_is_labelled_by_name_and_sense_never_score():
    board = _v2(fixtures.sign(_alpha()))
    assert board["ranking_section"]["label"] == "accuracy (lower is better)"
    assert "score" not in board["ranking_section"]["label"]
    assert board["eligible_leaderboard"]["label"] == "Eligible for the championship"


def test_contract_says_eligible_never_qualified():
    for board in _all_fixture_boards():
        assert "qualified" not in json.dumps(board).lower()


def test_margin_follows_the_feed_sense():
    v1 = feed.project(fixtures.sign(_alpha()), fixtures.fixture_trust())
    v1 = copy.deepcopy(v1)
    king = v1["incumbent"]["hotkey"]
    v1["incumbent"]["sections"]["accuracy"] = 0.2
    v1["standing"] = [
        {"rank": 1, "hotkey": king, "best": {"accuracy": 0.2}, "best_at_block": 1},
        {
            "rank": 2,
            "hotkey": "fixture-miner-99",
            "best": {"accuracy": 0.25},
            "best_at_block": 2,
        },
    ]
    assert board_v2.project(v1, NOW)["king"]["margin"] == 0.05
    v1["section_meta"]["accuracy"]["sense"] = "higher_is_better"
    assert board_v2.project(v1, NOW)["king"]["margin"] == -0.05
    v1["standing"] = v1["standing"][:1]
    king_view = board_v2.project(v1, NOW)["king"]
    assert king_view["margin"] is None
    assert king_view["reasons"]["margin"] == "no_runner_up"


def test_post_cutover_board_is_an_empty_new_era():
    board = _v2(fixtures.phase_documents()[0])
    assert board["phase"] == "PRE_FIRST_RELEASE"
    assert board["era"] == board["challenge"]["rule_digest"]
    assert board["challenge"]["rule"] == "fixture-rule-v3"
    assert board["king"] is None
    assert board["reasons"]["king"] == "no_released_incumbent"
    assert board["ranking_section"] is None
    assert board["reasons"]["ranking_section"] == "no_standing"
    assert board["eligible_leaderboard"]["entries"] == []
    assert board["history"]["points"] == {}
    assert board["next_release"]["released_windows"] == 0
    assert board["eligible_leaderboard"]["release_lag"]["blocks"] == 36_000


@pytest.mark.parametrize(
    ("age", "phase"), [(0, "LIVE"), (7_200, "LIVE"), (7_201, "STALE")]
)
def test_stale_after_the_engineering_default(age, phase):
    stamp = board_v2.utc_seconds("2026-10-08T00:00:00Z")
    assert _v2(fixtures.sign(_alpha()), now=stamp + age)["phase"] == phase
    assert board_v2.STALE_AFTER_SECONDS == 7_200


@pytest.mark.parametrize(
    ("generated_at", "reason"),
    [
        (None, "not_in_feed"),
        ("yesterday", "generated_at_unparseable"),
        ("2026-02-30T00:00:00Z", "generated_at_unparseable"),
    ],
)
def test_unknown_age_is_stale_with_a_reason(generated_at, reason):
    body = {**_alpha(), "generated_at": generated_at}
    board = _v2(fixtures.sign(body))
    assert board["phase"] == "STALE"
    assert board["freshness"]["age_seconds"] is None
    assert board["freshness"]["reasons"]["age_seconds"] == reason


def test_fields_not_in_the_feed_are_null_with_reasons():
    body = _alpha()
    del body["leaderboard"]["incumbent"]["since_block"]  # the v1 builder's shape
    board = _v2(fixtures.sign(body))
    for where, key in (
        (board["target_to_beat"], "value"),
        (board["target_to_beat"], "posted_margin"),
        (board["target_to_beat"], "noise_guard"),
        (board["championship"], "rounds"),
        (board["championship"]["entry"], "trigger_bar"),
        (board["championship"]["entry"], "king_screening_display"),
        (board["championship"]["entry"], "coldkeys"),
        (board["king"], "crowned_epoch"),
        (board["king"], "share_now"),
        (board["king"], "next_halving_epoch"),
        (board["king"], "defences"),
        (board["king"], "uid"),
        (board["king"], "registered_score"),
        (board["king"], "since_block"),
        (board["king"], "since_utc"),
        (board["history"], "kings"),
        (board["next_round"], "next_block"),
        (board["next_round"], "next_utc"),
        (board["next_release"], "next_block"),
        (board["next_release"], "next_utc"),
        (board["eligible_leaderboard"]["entries"][0], "uid"),
        (board["eligible_leaderboard"]["entries"][0], "registered_score"),
    ):
        assert where[key] is None and where["reasons"][key] == "not_in_feed", key
    body["release"] = None
    board = _v2(fixtures.sign(body))
    assert board["eligible_leaderboard"]["release_lag"] is None
    assert board["eligible_leaderboard"]["reasons"]["release_lag"] == "not_in_feed"
    assert board["next_round"]["every"] is None


def test_every_null_has_a_registered_reason():
    for board in _all_fixture_boards():
        _nulls_have_reasons(board)


def test_no_key_outside_the_allow_list(tmp_path):
    seen = set()
    for board in _all_fixture_boards():
        seen |= _paths(board)
    build.build(
        tmp_path / "site",
        fixtures.documents() + fixtures.phase_documents(),
        fixtures.fixture_trust(),
        now=NOW,
    )
    for path in (tmp_path / "site" / "data" / "v2").glob("*.json"):
        seen |= _paths(json.loads(path.read_text(encoding="utf-8")))
    reasons = {p for p in seen if p.endswith("reasons.*")}
    assert seen - reasons <= ALLOWED | FUTURE, sorted(seen - reasons - ALLOWED)
    segments = {s.rstrip("[]") for p in ALLOWED | FUTURE | seen for s in p.split(".")}
    assert not segments & FORBIDDEN, sorted(segments & FORBIDDEN)
    # The fixtures exercise nearly the whole contract.
    assert len(ALLOWED - seen) <= 3, sorted(ALLOWED - seen)


def test_fields_outside_the_allow_list_never_reach_v2():
    body = _alpha()
    body["operator_note"] = "private-note"
    body["leaderboard"]["incumbent"]["uid"] = 7
    body["leaderboard"]["incumbent"]["seed"] = "sealed-seed-1"
    body["leaderboard"]["standing"][0]["uid"] = 3
    body["release"]["next_window"] = "sha256:" + "a" * 64
    body["championship"] = {"day": "fixture"}
    board = _v2(fixtures.sign(body))
    text = json.dumps(board)
    for leaked in ("private-note", "sealed-seed-1", "a" * 64, '"day"'):
        assert leaked not in text
    assert board["king"]["uid"] is None
    assert board["championship"]["rounds"] is None


def test_canaries_stay_excluded_and_only_counted():
    body = _alpha()
    body["excluded"] = {"canary_hotkeys": 2, "hotkeys": ["fixture-canary-1"]}
    board = _v2(fixtures.sign(body))
    assert board["excluded_canaries"] == 2
    assert "fixture-canary" not in json.dumps(board)
    shown = {e["hotkey"] for e in board["eligible_leaderboard"]["entries"]}
    shown |= set(board["history"]["points"]) | {board["king"]["hotkey"]}
    listed = {r["hotkey"] for r in body["leaderboard"]["standing"]}
    listed |= set(body["leaderboard"]["history"])
    assert shown <= listed


def _public(key):
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


def test_fixture_build_is_refused_for_production(tmp_path):
    trust = feed.Trust(keys=frozenset({_public(Ed25519PrivateKey.generate())}))
    index = build.build(tmp_path / "site", fixtures.documents(), trust, now=NOW)
    assert {b["state"] for b in index["boards"]} == {"REFUSED"}
    assert not (tmp_path / "site" / "data" / "v2").exists()
    with pytest.raises(ValueError):
        feed.Trust(keys=frozenset({feed.FIXTURE_PUBLIC_KEY}))


def test_production_v2_board_is_not_fixture(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    text = json.dumps(_alpha()).replace("fixture-miner-0", "5" + "G" * 44 + "A")
    body = json.loads(text)
    body["labels"] = ["DEVELOPMENT", "TESTNET"]
    build.build(tmp_path / "site", [fixtures.sign(body, key)], trust, now=NOW)
    (path,) = (tmp_path / "site" / "data" / "v2").glob("*.json")
    board = json.loads(path.read_text(encoding="utf-8"))
    assert board["fixture"] is False and "FIXTURE" not in board["labels"]
    assert board["feed_state"] == {"state": "ACCEPTED", "code": None}


def test_a_new_rule_digest_never_splices_history(tmp_path):
    old = fixtures.sign(_alpha())
    build.build(tmp_path / "site", [old], fixtures.fixture_trust(), now=NOW)
    cutover = fixtures.post_cutover_document()
    cutover = {
        **cutover,
        "challenge": {**cutover["challenge"], "id": "fixture-challenge-alpha"},
    }
    build.build(
        tmp_path / "site", [fixtures.sign(cutover)], fixtures.fixture_trust(), now=NOW
    )
    (path,) = (tmp_path / "site" / "data" / "v2").glob("*.json")
    board = json.loads(path.read_text(encoding="utf-8"))
    assert board["era"] == cutover["challenge"]["rule_digest"]
    assert board["era"] != old["challenge"]["rule_digest"]
    assert board["history"]["points"] == {} and board["king"] is None
    assert board["phase"] == "PRE_FIRST_RELEASE"


def test_a_refused_feed_keeps_the_last_v2_board_restamped(tmp_path):
    good = fixtures.sign(_alpha())
    build.build(tmp_path / "site", [good], fixtures.fixture_trust(), now=NOW)
    bad = copy.deepcopy(good)
    bad["version"] = 99
    later = NOW + 86_400
    build.build(tmp_path / "site", [bad], fixtures.fixture_trust(), now=later)
    (path,) = (tmp_path / "site" / "data" / "v2").glob("*.json")
    board = json.loads(path.read_text(encoding="utf-8"))
    assert board["feed_state"] == {"state": "REFUSED", "code": "signature_invalid"}
    assert board["version"] == good["version"]
    assert board["phase"] == "STALE"


def test_v1_boards_are_unchanged_by_v2(tmp_path):
    """board.v2 is additive: data/boards/<slug>.json stays the v1 model."""
    build.build(tmp_path / "site", fixtures.documents(), fixtures.fixture_trust())
    for document in fixtures.documents():
        v1 = feed.project(document, fixtures.fixture_trust())
        stored = json.loads(
            (tmp_path / "site" / "data" / "boards" / f"{v1['slug']}.json").read_text(
                encoding="utf-8"
            )
        )
        assert stored["schema"] == feed.BOARD_SCHEMA
        assert set(stored) == set(v1) | {"feed_state"}
