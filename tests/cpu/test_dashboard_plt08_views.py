"""LP-02: the public attempt counts, sealed ladder and rules-card disclosure."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.dashboard import board_v2, feed, fixtures

HOTKEY = "fixture-miner-99"
CHECK = Path(__file__).with_name("dashboard_plt08_check.cjs")
STATUS = {
    "hotkey": HOTKEY,
    "received": 12,
    "scored": 4,
    "refused": {
        "malformed_submission": 2,
        "fixture_unknown_refusal_canary": 3,
        "unclassified_refusal": 1,
    },
    "score": 918273.125,
    "case_id": "fixture_case_payload_canary",
    "window": "fixture_window_payload_canary",
}


def _document():
    return fixtures.board_document("fixture-challenge-alpha", "cpu", seed=1)


def _project(body, *, rules=False):
    verified = feed.project(fixtures.sign(body), fixtures.fixture_trust())
    card = (
        {
            "digest": "sha256:" + "a" * 64,
            "rule": {"digest": body["challenge"]["rule_digest"]},
        }
        if rules
        else None
    )
    return board_v2.project(verified, fixtures.FIXTURE_NOW, rules_card=card)


def test_status_refusals_match_the_producer_without_importing_it_in_the_reader():
    from carbon.challenge_validator.dispatch import SCREEN_REFUSALS

    assert feed.STATUS_REFUSALS == {
        *SCREEN_REFUSALS,
        "hotkey_window_used",
        "receipt_block_missing",
        "level4_envelope_incomplete",
        "unclassified_refusal",
    }


@pytest.mark.parametrize("present", [False, True])
def test_absent_or_null_status_stays_unknown(present):
    body = _document()
    if present:
        body["miner_status"] = None
    verified = feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert "miner_status" not in verified
    projected = board_v2.project(verified, fixtures.FIXTURE_NOW)
    assert "miner_status" not in projected


def test_status_projection_keeps_only_counts_and_closes_unknown_codes():
    body = {**_document(), "miner_status": [copy.deepcopy(STATUS)]}
    expected = [
        {
            "hotkey": HOTKEY,
            "received": 12,
            "scored": 4,
            "refused": {"malformed_submission": 2, "other": 4},
        }
    ]
    verified = feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert verified["miner_status"] == expected
    assert _project(body)["miner_status"] == expected
    text = json.dumps(_project(body)["miner_status"])
    for forbidden in (
        "score",
        "case",
        "window",
        "918273",
        "fixture_unknown_refusal_canary",
        "unclassified_refusal",
    ):
        # "scored" is the authorized count; no scalar score field is allowed.
        assert (f'"{forbidden}"' if forbidden == "score" else forbidden) not in text


def test_v2_status_is_a_count_only_copy_of_the_verified_model():
    verified = feed.project(
        fixtures.sign({**_document(), "miner_status": [copy.deepcopy(STATUS)]}),
        fixtures.fixture_trust(),
    )
    verified["miner_status"][0]["score"] = "fixture_scalar_canary"
    projected = board_v2.project(verified, fixtures.FIXTURE_NOW)
    assert "score" not in projected["miner_status"][0]
    verified["miner_status"][0]["refused"]["other"] = 99
    assert projected["miner_status"][0]["refused"]["other"] == 4


@pytest.mark.parametrize(
    "raw",
    [
        {},
        "not a status list",
        [None],
        [{}],
        [{**STATUS, "received": True}],
        [{**STATUS, "received": -1}],
        [{**STATUS, "scored": 0.5}],
        [{**STATUS, "refused": []}],
        [{**STATUS, "refused": {"malformed_submission": "2"}}],
        [{**STATUS, "received": 2**53}],
        [{**STATUS, "refused": {"malformed_submission": 2**53 - 1, "other": 1}}],
        [STATUS, STATUS],
    ],
)
def test_malformed_status_refuses_the_whole_feed(raw):
    with pytest.raises(feed.FeedRefused, match="^miner_status_invalid$"):
        feed.project(
            fixtures.sign({**_document(), "miner_status": raw}),
            fixtures.fixture_trust(),
        )


def test_renderer_contracts_in_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    body = {**_document(), "miner_status": [copy.deepcopy(STATUS)]}
    shown = fixtures.ladder_document(
        "fixture-challenge-alpha", "cpu", seed=1, sealed=False
    )
    sealed = fixtures.ladder_document(
        "fixture-challenge-alpha", "cpu", seed=1, sealed=True
    )
    empty = copy.deepcopy(sealed)
    empty["leaderboard"]["ladder"]["coldkeys"] = []
    prerelease = {
        **fixtures.post_cutover_document(),
        "miner_status": [copy.deepcopy(STATUS)],
    }
    cases = {
        "hotkey": HOTKEY,
        "now": fixtures.FIXTURE_NOW,
        "with_status": _project(body, rules=True),
        "without_status": _project(_document()),
        "prerelease": _project(prerelease),
        "shown": _project(shown, rules=True),
        "sealed": _project(sealed, rules=True),
        "sealed_without_rules": _project(sealed),
        "empty_sealed": _project(empty, rules=True),
        "closed_codes": sorted(feed.STATUS_REFUSALS | {"other"}),
    }
    case_path = tmp_path / "cases.json"
    case_path.write_text(json.dumps(cases), encoding="utf-8")
    result = subprocess.run(
        [node, str(CHECK), str(case_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "status": "counts_only",
        "sealed": "no_values",
        "rules": "fail_closed",
    }
