"""The Updates page (#/updates): miners' recurring questions, answered once.

Its text is one file, carbon/dashboard/updates.json, written into the site by
`build.write_updates`. Claims: the file carries only what is already told to
miners: no date, no digest or long hex, no hidden value (a threshold, margin,
seed, bound, budget, weight or case count with a number) and no qualification
claim; it names exactly the launch Challenges; the build refuses markup or an
unknown field; and the page draws every section and every Challenge in Node
(tests/cpu/dashboard_updates_check.cjs), with each live version read from the
index, never from the file.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.dashboard import build, fixtures

ROOT = Path(__file__).resolve().parents[2]
NAMES = ROOT / "carbon" / "dashboard" / "names.static.json"
MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
DATE = re.compile(
    rf"\b(19|20)\d\d\b|\b\d{{1,2}}[/-]\d{{1,2}}([/-]\d{{2,4}})?\b|"
    rf"\b({MONTHS})[a-z]*\.?\s+\d|\b\d{{1,2}}(st|nd|rd|th)?\s+({MONTHS})\b|"
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\b(today|tomorrow|tonight|yesterday|this week|next week)\b",
    re.IGNORECASE,
)
HIDDEN = re.compile(r"sha256|digest|\b[0-9a-f]{12,}\b|\b[nk]\s*=", re.IGNORECASE)
#: A rule word that would be a hidden value with a number beside it.
RULE_WORD = re.compile(
    r"threshold|margin|seed|toleran|bound|floor|budget|weight|cutoff|case|count",
    re.IGNORECASE,
)
CLAIM_WORDS = re.compile(
    r"\b(qualified|validated|certified|production[- ]ready|matches reality|accurate)\b",
    re.IGNORECASE,
)


def _updates():
    return json.loads(build.UPDATES.read_text(encoding="utf-8"))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)


def test_the_updates_carry_no_date_digest_or_hidden_value():
    lines = list(_strings(_updates()))
    assert len(lines) > 20
    for line in lines:
        assert not DATE.search(line), line
        assert not HIDDEN.search(line), line
        assert not CLAIM_WORDS.search(line), line
        if RULE_WORD.search(line):
            assert not re.search(r"\d", line), line


def test_the_checks_catch_what_they_guard():
    """Each pattern refuses the shape it is for, so a passing file means something."""
    assert DATE.search("target about Nov 7") and DATE.search("2026-11-01")
    assert DATE.search("from 4/11") and DATE.search("next week")
    assert HIDDEN.search("sha256:ab") and HIDDEN.search("bank 8eb0aa23df557035")
    assert HIDDEN.search("N = 3 per class")
    assert RULE_WORD.search("a margin of 0.02") and re.search(r"\d", "0.02")
    assert not DATE.search("Ribbed Bracket 2.0") and not DATE.search("9 inputs")


def test_the_updates_name_exactly_the_launch_challenges_in_order():
    names = json.loads(NAMES.read_text(encoding="utf-8"))
    ids = [c["id"] for c in _updates()["challenges"]]
    assert ids == sorted(names, key=lambda i: names[i]["order"])
    for challenge in _updates()["challenges"]:
        assert challenge["next"], challenge["id"]


def test_the_build_writes_the_updates_and_refuses_anything_else(tmp_path):
    site = tmp_path / "site"
    build.build(site, fixtures.documents(), fixtures.fixture_trust())
    written = json.loads((site / "updates.json").read_text(encoding="utf-8"))
    assert written == _updates()
    bad = []
    for change in (
        lambda d: d["fixes"].append("<b>bold</b>"),
        lambda d: d["faq"][0]["a"].append("two\nlines"),
        lambda d: d.update(extra=[]),
        lambda d: d.update(schema="carbon.dashboard.updates.v0"),
        lambda d: d["challenges"][0]["next"][0].update(version="next"),
        lambda d: d["challenges"][0].update(live="1.5"),
        lambda d: d["challenges"][0]["next"][0].update(changes=[]),
        lambda d: d.update(challenges=[]),
    ):
        doc = copy.deepcopy(_updates())
        change(doc)
        bad.append(doc)
    for doc in bad:
        with pytest.raises(ValueError):
            build.write_updates(tmp_path / "refused", doc)
    assert not (tmp_path / "refused" / "updates.json").exists()


def test_the_nav_offers_the_updates_page():
    html = (ROOT / "carbon" / "dashboard" / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    assert '<a href="#/updates" data-view="updates">Updates</a>' in html


def test_the_updates_page_renders_in_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    site = tmp_path / "site"
    build.build(site, fixtures.documents(), fixtures.fixture_trust())
    check = Path(__file__).with_name("dashboard_updates_check.cjs")
    result = subprocess.run(
        [node, str(check), str(site)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["sections"] == [
        "challenges",
        "every-version",
        "fixes",
        "known-issues",
        "faq",
    ]
    assert out["challenges"] == 4
