"""A card's status line and door link, set in the names file (or the Worker's CHALLENGE_NAMES).

An entry is a plain name, or `{"name", "status", "door"}`: while the Challenge has no board its
card shows the status in place of "Launching soon", links the validator door (https only), "How to
mine" and the guide. Nothing signed, no score. The build, the page (tests/cpu/dashboard_check.cjs)
and the Worker check the same patterns, and a bad entry is refused or dropped, never drawn.
"""

from __future__ import annotations

import json

import pytest

from carbon.dashboard import __main__ as cli
from carbon.dashboard import build
from tests.cpu.test_dashboard_names import _serve

STATUS_NAMES = {
    "f08-ribbed-bracket": {
        "name": "Ribbed Bracket",
        "status": "Open: crowns live",
        "door": "https://ribbed-bracket-door.carbonphysics.ai",
    },
    "chip-cold-plate": {"name": "Cooling", "status": "Open: crowns open in week 1"},
    "f02": "Burst Thermal",
}


def test_an_entry_may_carry_a_status_and_a_door_beside_plain_names(tmp_path):
    build.write_names(tmp_path, STATUS_NAMES)
    written = json.loads((tmp_path / "data" / "names.json").read_text(encoding="utf-8"))
    assert written["names"] == dict(sorted(STATUS_NAMES.items()))


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "Cooling", "status": "<b>Open</b>"},
        {"name": "Cooling", "status": ""},
        {"name": "Cooling", "status": "x" * 61},
        {"name": "Cooling", "door": "http://door.example"},
        {"name": "Cooling", "door": "https://door.example/a?x=1"},
        {"name": "Cooling", "door": "javascript:alert(1)"},
        {"name": "Cooling", "door": 7},
        {"name": "Cooling", "score": 0.9},
        {"status": "Open"},
        {"name": "<b>", "status": "Open"},
    ],
)
def test_an_entry_with_a_bad_status_door_or_field_refuses_the_build(tmp_path, entry):
    with pytest.raises(ValueError):
        build.write_names(tmp_path, {"chip-cold-plate": entry})
    assert not (tmp_path / "data" / "names.json").exists()


def test_the_command_takes_status_entries(tmp_path):
    names = tmp_path / "names.json"
    names.write_text(json.dumps(STATUS_NAMES), encoding="utf-8")
    out = tmp_path / "site"
    assert cli.main(["build", "--empty", "--names", str(names), "--out", str(out)]) == 0
    written = json.loads((out / "data" / "names.json").read_text(encoding="utf-8"))
    assert written["names"]["f08-ribbed-bracket"]["status"] == "Open: crowns live"


def test_the_worker_serves_status_entries_from_the_var(tmp_path):
    answer = _serve(tmp_path, json.dumps(STATUS_NAMES), None)
    assert answer["status"] == 200
    assert json.loads(answer["body"])["names"] == STATUS_NAMES


@pytest.mark.parametrize(
    "bad",
    [
        {"f02": {"name": "Burst Thermal", "door": "http://x.example"}},
        {"f02": {"name": "Burst Thermal", "status": "<i>"}},
        {"f02": {"name": "Burst Thermal", "score": 1}},
    ],
)
def test_the_worker_ignores_a_var_with_a_bad_entry(tmp_path, bad):
    assert _serve(tmp_path, json.dumps(bad), None)["status"] == 404
