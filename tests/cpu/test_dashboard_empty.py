"""`build --empty`: the honest "launching soon" site before any board is published."""

from __future__ import annotations

import json

from carbon.dashboard import __main__ as cli
from carbon.dashboard import build


def test_the_empty_site_has_no_board_no_showcase_and_is_not_a_fixture(tmp_path):
    out = tmp_path / "site"
    assert cli.main(["build", "--empty", "--out", str(out)]) == 0
    index = json.loads((out / "data" / "index.json").read_text(encoding="utf-8"))
    assert (
        index["boards"] == []
        and index["fixture"] is False
        and index["showcase"] is False
    )
    assert not (out / "showcase").exists() and not (out / "data" / "boards").exists()
    assert (out / "_headers").read_text(encoding="utf-8") == build.STATIC_HEADERS
    assert "default-src 'self'" in build.STATIC_HEADERS
    assert not (out / "data" / "names.json").exists()


def test_the_empty_site_takes_names_for_its_launching_cards(tmp_path):
    names = tmp_path / "names.json"
    names.write_text(json.dumps({"f02": "Burst Thermal"}), encoding="utf-8")
    out = tmp_path / "site"
    assert cli.main(["build", "--empty", "--names", str(names), "--out", str(out)]) == 0
    written = json.loads((out / "data" / "names.json").read_text(encoding="utf-8"))
    assert written["names"] == {"f02": "Burst Thermal"}
    index = json.loads((out / "data" / "index.json").read_text(encoding="utf-8"))
    assert index["boards"] == [] and index["fixture"] is False


def test_the_empty_site_takes_no_key(tmp_path, capsys):
    try:
        cli.main(
            ["build", "--empty", "--trust-key", "00" * 32, "--out", str(tmp_path / "s")]
        )
    except SystemExit as stop:
        assert stop.code == 2
    else:
        raise AssertionError("expected a refusal")
