"""Miner feedback: three refusals say what to do next, and the docs say the two
facts miners tripped on (submit is only queued; practice runs on this machine)."""

from __future__ import annotations

from pathlib import Path

from scripts.dev.miner_launchpad import supervisor

MINING = (Path(__file__).resolve().parents[2] / "docs" / "MINING.md").read_text(
    encoding="utf-8"
)


def test_a_graph_not_staged_says_to_stage_it_first():
    text = supervisor.NEXT_ACTIONS["construction_recipe_graph_workspace_missing"]
    assert "stage" in text.lower() and "submit again" in text
    assert "Nothing was submitted" in text


def test_the_idempotency_conflict_names_the_field_to_pass():
    text = supervisor.NEXT_ACTIONS["construction_source_idempotency_conflict"]
    assert "expected_manifest_digest" in text and "stage again" in text


def test_the_signer_text_says_to_keep_it_up_until_reconstructed():
    text = supervisor.NEXT_ACTIONS["signer_not_running"]
    assert "Start carbon-miner-signer" in text
    assert "until your result shows reconstructed" in text


def test_the_guide_says_where_practice_runs_and_that_submit_is_queued():
    assert "**Where a practice runs.**" in MINING
    assert "practice_candidate_failed" in MINING
    assert "never on a validator's" in MINING
    assert "RTX 4090-class" in MINING
    assert "shown for each Challenge in its kit document" in MINING
    assert "Keep your signer running until the result shows reconstructed" in MINING
