"""The one error table (miner-ux item 4): docs/MINING.md carries exactly what `error_table.render()` produces, every row's
words come from the code's own source, and the table says "Not stated" rather than guess."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import error_table, projection, supervisor

MINING = Path(__file__).resolve().parents[2] / "docs" / "MINING.md"


def test_the_document_carries_exactly_the_generated_table():
    block = error_table.document_block(MINING.read_text(encoding="utf-8"))
    assert block is not None, "docs/MINING.md lost its error-table markers"
    assert block == error_table.render(), (
        "docs/MINING.md differs from the table: run "
        "python -m scripts.dev.miner_launchpad.error_table --write docs/MINING.md"
    )


def test_every_row_reads_its_words_from_the_code_source():
    for source, code, side, charged in error_table.ROWS:
        table = supervisor.NEXT_ACTIONS if source == "next" else projection.GRADE_STATE_WORDS
        assert code in table, code
        assert side and charged
    codes = [code for _, code, _, _ in error_table.ROWS]
    assert len(codes) == len(set(codes))


def test_the_codes_miners_quote_are_in_the_table():
    # miner-x, 20 Nov 2026: what miners actually quoted to us.
    quoted = {
        "TRANSPORT_STALE",
        "TRANSPORT_CAPACITY",
        "hotkey_submission_waiting",
        "coldkey_submission_waiting",
        "epoch_limit_reached",
        "exam_daily_allowance_reached",
        "rate",
        "intake_busy",
        "FAILED_INFRA",
        "fitted_info_over_budget",
        "candidate_build_refused",
        "door_updating",
        "version_closed",
    }
    assert quoted <= {code for _, code, _, _ in error_table.ROWS}


def test_the_table_leaks_no_placeholder_and_cells_hold_no_pipe():
    text = error_table.render()
    assert "HUMAN_INPUT" not in text
    for line in text.splitlines():
        if line.startswith("| `"):
            assert line.count("|") == 5, line


def test_a_refusal_that_does_not_say_whether_it_charged_says_not_stated():
    # A row says "No" only when its own words say so: each such sentence names it.
    said = ("charged", "allowance", "unused", "slot", "admitting")
    for source, code, _, charged in error_table.ROWS:
        if not charged.startswith("No"):
            continue
        words = (
            supervisor.NEXT_ACTIONS[code]
            if source == "next"
            else projection.GRADE_STATE_WORDS[code]
        ).lower()
        assert any(term in words for term in said), (code, charged)


@pytest.mark.parametrize(
    "stale",
    ["hotkey registered on subnet 567.**", "mainnet opens on **HUMAN_INPUT**"],
)
def test_the_stale_lines_are_gone_from_the_miner_page(stale):
    assert stale.lower() not in MINING.read_text(encoding="utf-8").lower()


def test_the_dashboards_getting_started_does_not_call_itself_the_test_network():
    page = (
        Path(__file__).resolve().parents[2] / "carbon" / "dashboard" / "web" / "dashboard.js"
    ).read_text(encoding="utf-8")
    assert "This is the test network (subnet 567)" not in page
    assert "Motor runs on mainnet (subnet 116)" in page
