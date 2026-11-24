"""The published text follows the crown row: a menu-headroom version whose row says ``"score": "A"`` states accuracy alone; with
no such row every published block is the one it was (the committed rows name none, so this changes nothing today).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon.challenge_registry import published_exam as pe
from carbon.challenge_validator import crown_official

KEY = ("electric-motor-magnetics", "1.8")
#: The canonical block of Motor 1.8 on main fe148ac4, where its crown row names the total.
BLOCK_18 = "c68499439d0634288e700c4b59e7c032dc29caecc7e707a452e08f7e6f544080"


def _rows(tmp_path, monkeypatch, entry):
    document = json.loads(crown_official.REGISTRY.read_bytes())
    document["versions"]["electric-motor-magnetics 1.8"] = entry
    path = tmp_path / "crown_official_score.json"
    path.write_text(json.dumps(document))
    monkeypatch.setattr(pe, "_CROWN_ROWS", path)
    monkeypatch.setattr(crown_official, "REGISTRY", path)
    return path


def _digest(block):
    body = json.dumps(block, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode()).hexdigest()


def test_both_readers_read_the_same_rows():
    assert pe._CROWN_ROWS.resolve() == crown_official.REGISTRY.resolve()
    for key in pe.served():
        ranked = crown_official.score_of(*key) == crown_official.ACCURACY
        assert pe.ranked_by_accuracy(*key) == ranked


def test_a_row_that_names_the_total_changes_no_byte(tmp_path, monkeypatch):
    _rows(tmp_path, monkeypatch, {"margin": 0.0129})
    assert not pe.ranked_by_accuracy(*KEY)
    assert _digest(pe.for_version(*KEY)) == BLOCK_18


def test_a_row_that_names_accuracy_states_accuracy_alone(tmp_path, monkeypatch):
    _rows(tmp_path, monkeypatch, {"margin": 0.5, "score": "A"})
    assert crown_official.score_of(*KEY) == crown_official.ACCURACY
    block = pe.for_version(*KEY)
    assert set(block) <= pe.ALLOWED_FIELDS and "design_search" not in block
    assert block["score"]["formula"] == "TOTAL = A"
    assert block["score"]["weights"] == {"A": 1.0}
    assert [leg["id"] for leg in block["score"]["legs"]] == ["A_headroom"]
    lines = {line["id"]: line["text"] for line in block["how_you_are_tested"]}
    assert list(lines) == [
        "score",
        "optimizer",
        "out_of_range",
        "gates",
        "speed",
        "minimums",
        "practice",
        "registered_values",
    ]
    text = json.dumps([block["score"], block["how_you_are_tested"]]).lower()
    for word in (
        "0.5",
        "menu",
        "top five",
        "pick",
        "epoch",
        "rotat",
        "inverse design",
        "query budget",
    ):
        assert word not in text, word
    # what counts is unchanged: the same A, cells and in-range gate as before, word for word
    own = pe.registered_pool(*KEY)
    assert block["score"]["rule"]["A"] == pe._a_text(own)
    assert block["score"]["rule"]["gate"] == pe._gate_text(own)
    assert "practice total still holds a design value part" in block["practice_vs_exam"]
    assert block["practice_vs_exam"] == lines["practice"]
    # the row check still counts (`crown_official.row_check_unknown`), and each part keeps its minimum
    assert "whatever else is in the batch" in lines["score"]
    assert "Each score part also has a minimum" in lines["minimums"]


def test_the_row_check_sentence_is_the_crown_rules_own():
    passed = {"physics_benefit": 0.5, "design_benefit": 0.1}
    score = crown_official.ACCURACY
    assert crown_official.value(passed, score) == 0.5
    assert crown_official.value({**passed, "design_benefit": 0.0}, score) is None


@pytest.mark.parametrize(
    "entry",
    [
        {"margin": 0.5, "score": "total"},
        {"margin": 0.5, "score": "A", "other": 1},
        {"score": "A"},
        {"margin": 0.5},
    ],
)
def test_a_row_the_crown_rule_refuses_states_nothing_new(tmp_path, monkeypatch, entry):
    _rows(tmp_path, monkeypatch, entry)
    assert not pe.ranked_by_accuracy(*KEY)
    assert _digest(pe.for_version(*KEY)) == BLOCK_18


def test_everything_else_the_block_states_is_the_same(tmp_path, monkeypatch):
    before = pe.for_version(*KEY)
    _rows(tmp_path, monkeypatch, {"margin": 0.5, "score": "A"})
    after = pe.for_version(*KEY)
    changed = {"score", "how_you_are_tested", "practice_vs_exam", "design_search"}
    assert set(before) - set(after) == {"design_search"}
    for name in set(after) - changed:
        assert after[name] == before[name], name


def test_no_other_version_moves(tmp_path, monkeypatch):
    before = {key: _digest(pe.for_version(*key)) for key in pe.served()}
    _rows(tmp_path, monkeypatch, {"margin": 0.5, "score": "A"})
    after = {key: _digest(pe.for_version(*key)) for key in pe.served()}
    assert {key for key in before if before[key] != after[key]} == {KEY}


@pytest.mark.parametrize("raw", [None, b"not json", b"[]", b'{"versions": []}'])
def test_rows_that_cannot_be_read_state_the_total(tmp_path, monkeypatch, raw):
    path = tmp_path / "rows.json"
    if raw is not None:
        path.write_bytes(raw)
    monkeypatch.setattr(pe, "_CROWN_ROWS", path)
    assert _digest(pe.for_version(*KEY)) == BLOCK_18
