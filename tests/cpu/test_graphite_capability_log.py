"""The refused-capability log: log only, opt-in, and it changes nothing about a run.

A refused proposal and a filed capability wish become rows in one Markdown log, keyed by
Challenge and level. These tests keep it that way: the grammar parses, hidden material is
withheld, a run without the opt-in is byte-identical, and the backfilled stage A rows are
in the committed log with their source.
"""

from __future__ import annotations

import json
from pathlib import Path

import graphite_phase3_fixtures as p3f
import pytest
from graphite_phase3_fixtures import BASELINE, propose, session, steps, text

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import capability_log as cl
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3
from carbon.development_session.profile import canonical, digest

REPOSITORY = Path(__file__).resolve().parents[2]
LOG = REPOSITORY / cl.DEFAULT_LOG
BACKFILL = (
    REPOSITORY / "docs/development/graphite/level4/refused_capability_backfill.json"
)


# -- the wish grammar ---------------------------------------------------------------------------
def test_a_wish_line_parses_into_its_four_fields():
    wish = cl.parse_wish(
        "Try a deeper net.\nWISH: optimisation=fuse the loss and backward; "
        "needs=a Triton fused op; expected_gain=2x step speed; evidence=profile shows 60% in loss"
    )
    assert wish == {
        "optimisation": "fuse the loss and backward",
        "needs": "a Triton fused op",
        "expected_gain": "2x step speed",
        "evidence": "profile shows 60% in loss",
    }


def test_a_malformed_wish_is_kept_as_written_and_no_wish_is_none():
    assert cl.parse_wish("WISH: just a hope") == {"raw": "just a hope"}
    assert cl.parse_wish("an ordinary hypothesis") is None
    assert cl.parse_wish(None) is None


# -- rows ---------------------------------------------------------------------------------------
def test_a_row_is_sanitised_and_bounded():
    line = cl.row({"kind": "wish", "optimisation": "a | b\nc" + "x" * 500})
    assert line.count("|") == len(cl.COLUMNS) + 1 and line.endswith("|\n")
    assert "\n" not in line[:-1] and len(line) < 1200


def test_append_writes_the_header_once_then_rows_and_is_off_without_a_path(
    tmp_path, monkeypatch
):
    path = tmp_path / "log.md"
    entry = {"kind": "refusal", "challenge": "c", "level": 0, "code": "x"}
    assert cl.append([entry], path) == 1 and cl.append([entry], path) == 1
    body = path.read_bytes().decode("utf-8")
    assert body.startswith(cl.HEADER) and body.count(cl.HEADER) == 1
    assert body.count("\n| ") == 3  # header row plus two entries
    monkeypatch.delenv(cl.LOG_ENV, raising=False)
    assert cl.append([entry]) == 0


def test_protected_text_is_withheld_not_written(tmp_path):
    path = tmp_path / "log.md"
    entry = {
        "kind": "wish",
        "challenge": "c",
        "level": 0,
        "needs": "read the official_seed to tune",
    }
    cl.append([entry], path)
    body = path.read_text(encoding="utf-8")
    assert "official_seed" not in body and cl.WITHHELD in body


# -- the hook in a real session -----------------------------------------------------------------
def _refused():
    return {**BASELINE, "parameters": {**BASELINE["parameters"], "ensemble_members": 5}}


def _run(tmp_path, strategy, hypothesis="a recipe that may fit better"):
    account = p3f.ScriptedPods(steps=steps(1.0))
    _result, graphite, _ = session(
        tmp_path, [propose(strategy, hypothesis), text("done")], account
    )
    [record] = graphite.experiment(p3f.run_id()).records("proposal")
    return record, graphite


def test_a_refused_proposal_is_logged_with_challenge_level_code_field_and_value(
    tmp_path, monkeypatch
):
    path = tmp_path / "log.md"
    monkeypatch.setenv(cl.LOG_ENV, str(path))
    record, _ = _run(tmp_path / "s", _refused())
    assert record["status"] == "REFUSED_UNREBUILDABLE"
    rows = [
        r for r in path.read_text(encoding="utf-8").splitlines() if r.startswith("| 20")
    ]
    assert len(rows) == 1
    cells = [c.strip() for c in rows[0].strip("|").split("|")]
    assert cells[1] == p3f.SCORING.challenge_id and cells[2] == "0"
    assert cells[5] == "refusal" and cells[6] == "REFUSED_UNREBUILDABLE"
    assert cells[7] == "parameter.domain_mismatch"
    assert cells[8] == "ensemble_members" and cells[9] == "5"


def test_a_wish_in_a_hypothesis_is_logged_beside_the_refusal(tmp_path, monkeypatch):
    path = tmp_path / "log.md"
    monkeypatch.setenv(cl.LOG_ENV, str(path))
    wish = (
        "Five members.\nWISH: optimisation=more ensemble members; needs=cap above 4; "
        "expected_gain=lower variance; evidence=members 3 to 4 helped"
    )
    _run(tmp_path / "s", _refused(), wish)
    body = path.read_text(encoding="utf-8")
    assert "| wish |" in body and "cap above 4" in body and "| refusal |" in body


def test_an_accepted_proposal_logs_no_refusal(tmp_path, monkeypatch):
    path = tmp_path / "log.md"
    monkeypatch.setenv(cl.LOG_ENV, str(path))
    record, _ = _run(tmp_path / "s", BASELINE)
    assert not record["status"].startswith("REFUSED")
    assert not path.exists() or "| refusal |" not in path.read_text(encoding="utf-8")


def test_a_run_without_the_opt_in_is_byte_identical_and_writes_nothing(
    tmp_path, monkeypatch
):
    monkeypatch.delenv(cl.LOG_ENV, raising=False)
    off, _ = _run(tmp_path / "off", _refused())
    path = tmp_path / "log.md"
    monkeypatch.setenv(cl.LOG_ENV, str(path))
    on, _ = _run(tmp_path / "on", _refused())
    assert digest(canonical(off)) == digest(canonical(on))
    assert not (tmp_path / "off" / "log.md").exists()


def test_a_log_that_cannot_be_written_never_affects_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv(cl.LOG_ENV, str(tmp_path))  # a directory: not writable as a file
    record, _ = _run(tmp_path / "s", _refused())
    assert record["status"] == "REFUSED_UNREBUILDABLE"


# -- the brief ------------------------------------------------------------------------------------
def _brief(**options):
    budget = ex.phase3_budget(
        SpendingGrant.from_document(phase3.DRY_RUN_GRANT), p3f.SCORING
    )
    return phase3.session_brief(
        checkout_commit="0" * 40, budget=budget, scoring=p3f.SCORING, **options
    )


def test_the_brief_offers_the_wish_channel_only_when_asked():
    plain = _brief().initial_observation
    assert "capability_wish" not in plain
    asked = _brief(capability_wish_text=True).initial_observation
    assert asked["capability_wish"]["line"].startswith("WISH: optimisation=")
    assert "WISH line" in asked["instructions"] and "widens nothing" in (
        asked["capability_wish"]["effect"]
    )


# -- the committed log ----------------------------------------------------------------------------
def test_the_committed_log_starts_with_the_backfilled_stage_a_refusals():
    document = json.loads(BACKFILL.read_text(encoding="utf-8"))
    assert (
        len(document["rows"]) == 8
        and "GRAPHITE_STAGE_A_REFUSALS.md" in document["source"]
    )
    text_ = LOG.read_bytes().decode("utf-8")
    assert text_.startswith(cl.HEADER)
    for item in document["rows"]:
        assert item["proposal"] in text_ and item["code"] in text_
    assert text_.count("stage A extract (backfill)") == 8
    assert "official_seed" not in text_ and "draw_id" not in text_


def test_the_committed_log_holds_the_l2_l4_backfill_with_no_invented_cause():
    document = json.loads(
        (
            REPOSITORY
            / "docs/development/graphite/level4/refused_capability_backfill_l2_l4.json"
        ).read_text(encoding="utf-8")
    )
    text_ = LOG.read_bytes().decode("utf-8")
    assert len(document["rows"]) == 5
    assert "executor report, 2026-10-12" in document["source"]
    for item in document["rows"]:
        assert set(item) == {"level", "run", "proposal", "status"}
        line = next(
            r
            for r in text_.splitlines()
            if item["proposal"] in r and (f"| {item['level']} | {item['run']} |" in r)
        )
        # code, field and requested were not in the extract: empty cells
        assert "| REFUSED_UNREBUILDABLE |  |  |  |" in line
    assert text_.count("(stage A L2-L4 extract, backfill)") == 5
    assert "official_seed" not in text_ and "draw_id" not in text_


def test_the_checklist_names_this_log_as_the_only_one():
    checklist = (
        REPOSITORY / "docs/development/graphite/GRAPHITE_LADDER_STAGE_A_CHECKLIST.md"
    ).read_text(encoding="utf-8")
    assert "REFUSED_CAPABILITY_LOG.md" in checklist
    flat = " ".join(checklist.split())
    assert "there is no second file" in flat


# -- the wish may sit anywhere in the text, in common markup ------------------------------------------
BODY = (
    "optimisation=a monotone head; needs=structure_layers; expected_gain=monotone capacity; "
    "evidence=the level refused it"
)
FIELDS = {
    "optimisation": "a monotone head",
    "needs": "structure_layers",
    "expected_gain": "monotone capacity",
    "evidence": "the level refused it",
}


@pytest.mark.parametrize(
    "text",
    [
        f"WISH: {BODY}",
        f"A sentence first.\nWISH: {BODY}",
        f"   WISH: {BODY}",
        f"Error should drop with averaging. WISH: {BODY}",
        f"- WISH: {BODY}",
        f"* WISH: {BODY}",
        f"> WISH: {BODY}",
        f"> - WISH: {BODY}",
        f"`WISH:` {BODY}",
        f"**WISH:** {BODY}",
        f"**WISH**: {BODY}",
        f"Averaging helps (see below) - **WISH:** {BODY}",
        f"WISH:{BODY}",
    ],
)
def test_a_wish_parses_wherever_it_sits_and_in_common_markup(text):
    assert cl.parse_wish(text) == FIELDS


def test_the_old_line_start_forms_give_the_same_results_as_before():
    old = (
        "Try a deeper net.\nWISH: optimisation=fuse the loss and backward; "
        "needs=a Triton fused op; expected_gain=2x step speed; evidence=profile shows 60% in loss"
    )
    assert cl.parse_wish(old) == {
        "optimisation": "fuse the loss and backward",
        "needs": "a Triton fused op",
        "expected_gain": "2x step speed",
        "evidence": "profile shows 60% in loss",
    }
    assert cl.parse_wish("WISH: just words, no fields") == {
        "raw": "just words, no fields"
    }
    assert cl.parse_wish("no wish here") is None
    assert cl.parse_wish(None) is None


@pytest.mark.parametrize(
    "text",
    [
        "I wish this were possible.",
        "wish: optimisation=x",
        "SWISH: optimisation=x; needs=y",
        "a WISHLIST: optimisation=x",
        "WISHES are welcome",
    ],
)
def test_text_that_is_not_a_wish_line_is_still_none(text):
    assert cl.parse_wish(text) is None


def test_an_inline_malformed_wish_is_kept_as_written_not_dropped():
    wish = cl.parse_wish("Some reasoning. WISH: I would like a monotone head")
    assert wish == {"raw": "I would like a monotone head"}


def test_an_inline_wish_in_a_hypothesis_is_logged_and_protected_text_is_withheld(
    tmp_path,
):
    entry = cl.wish_entry(
        challenge="c",
        level=2,
        run="r",
        proposal="p-1",
        hypothesis=f"Reasoning first. WISH: {BODY}",
        when="2026-10-12",
    )
    assert entry["kind"] == "wish" and entry["needs"] == "structure_layers"
    log = tmp_path / "log.md"
    assert cl.append([entry], log) == 1
    assert "structure_layers" in log.read_text(encoding="utf-8")


# -- the four wishes the hunt filed inline -------------------------------------------------------------
HUNT_WISHES = (
    REPOSITORY
    / "docs/development/graphite/level4/refused_capability_backfill_hunt_wishes.json"
)


def test_the_hunt_wishes_are_in_the_committed_log_via_the_fixed_parser():
    document = json.loads(HUNT_WISHES.read_text(encoding="utf-8"))
    text_ = LOG.read_bytes().decode("utf-8")
    assert len(document["rows"]) == 4
    assert {r["hunt"] for r in document["rows"]} == {"H1", "H2", "H3"}
    for item in document["rows"]:
        wish = cl.parse_wish(item["wish"])
        assert wish and "raw" not in wish and all(wish[k] for k in cl.WISH_KEYS)
        assert item["proposal"] in text_ and item["run"] in text_
        assert cl._cell(wish["needs"]) in text_
    assert text_.count("hunt wish backfill") == 4
    assert "official_seed" not in text_ and "draw_id" not in text_
