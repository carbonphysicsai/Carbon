"""A displayed ss58 is always a "mining key address", never a bare "mining key"
(Validator, port receipt; E10: a field that says "key" invites pasting a secret).

Reads the page's own source: every string literal naming a mining key that is
joined straight to a hotkey or ss58 value says "address"."""

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "miner_launchpad"
JOINED = re.compile(
    r'"([^"]*mining key[^"]*)"\s*\+\s*[\w.?()]*(?:hotkey|ss58)', re.IGNORECASE
)


def test_no_displayed_ss58_follows_mining_key_without_address():
    found = []
    for name in ("app.js", "research_view.js"):
        for literal in JOINED.findall((PAGE / name).read_text(encoding="utf-8")):
            if not re.search(r"mining key address\W*$", literal, re.IGNORECASE):
                found.append((name, literal))
    assert found == []


def test_the_check_sees_the_two_displays_it_guards():
    text = (PAGE / "app.js").read_text(encoding="utf-8")
    assert len(JOINED.findall(text)) >= 2
