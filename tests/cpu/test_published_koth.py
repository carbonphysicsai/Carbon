"""The published king-of-the-hill section reads the crown row of a version under the confirmation line (miner-ux 8683 X3)."""

from __future__ import annotations

import json

from carbon.challenge_registry import published_exam as pe


def _rows(tmp_path, versions):
    path = tmp_path / "crown_official_score.json"
    path.write_text(
        json.dumps({"schema": "carbon.crown-official-score.v1", "versions": versions})
    )
    return path


def test_a_version_under_the_confirmation_line_shows_its_margin_and_the_rule(
    tmp_path, monkeypatch
):
    path = _rows(
        tmp_path,
        {
            "zz-family 2.0": {
                "confirmation": {"tie": "not_confirmed"},
                "margin": 0.0086,
                "records": "all",
            }
        },
    )
    monkeypatch.setattr(pe, "_CROWN_ROWS", path)
    section = pe.koth("zz-family", "2.0")
    assert section["margin"] == 0.0086
    assert section["note"] == pe._KOTH_CONFIRMED_NOTE
    assert "confirmation set" in section["note"] and "tie" in section["note"]
    assert section["rule"] == pe._KOTH["rule"]
    assert pe._KOTH["margin"] == pe.NOT_REGISTERED  # the shared text is not changed


def test_a_version_without_the_confirmation_line_keeps_the_shared_text_byte_for_byte(
    tmp_path, monkeypatch
):
    path = _rows(tmp_path, {"zz-family 1.8": {"margin": 0.0129, "score": "A"}})
    monkeypatch.setattr(pe, "_CROWN_ROWS", path)
    assert pe.koth("zz-family", "1.8") is pe._KOTH
    assert pe.koth("zz-family", "9.9") is pe._KOTH


def test_a_row_the_receiver_would_refuse_states_nothing(tmp_path, monkeypatch):
    path = _rows(
        tmp_path,
        {
            "zz-family 2.0": {"confirmation": {}, "margin": 1.5},
            "zz-family 2.1": {"confirmation": {}, "margin": True},
            "zz-family 2.2": {"confirmation": {}, "margin": 0.01, "extra": 1},
        },
    )
    monkeypatch.setattr(pe, "_CROWN_ROWS", path)
    for version in ("2.0", "2.1", "2.2"):
        assert pe.koth("zz-family", version) is pe._KOTH


def test_the_committed_rows_give_motor_1_9_and_rb_2_0_their_margin():
    for key in (("electric-motor-magnetics", "1.9"), ("f08-ribbed-bracket", "2.0")):
        assert pe.koth(*key)["margin"] == 0.0086
    assert pe.koth("electric-motor-magnetics", "1.8") is pe._KOTH
