"""Launchpad fixes from the round-6 M1 E2E smoke (reports/E2E_RESULTS_20261022.md)."""

from scripts.dev.miner_launchpad import setup_operations, supervisor


def test_the_review_confirm_field_says_what_it_confirms():
    # R6-4: agents read `confirm` as undocumented; its description was "true".
    for name in ("review", "recheck"):
        for door in ("mcp", "page"):
            try:
                schema = setup_operations.schema(name, door)
            except (KeyError, ValueError):
                continue
            text = repr(schema)
            assert "Must be true" in text and "runner profile" in text


def test_an_intake_mismatch_points_at_a_read_only_check():
    # R6-5: the refusal sent agents to carbon_setup_review, which writes and
    # loads the profile; agents rightly refused to run it unasked.
    for code in (
        "construction_intake_challenge_mismatch",
        "intake_receiver_mismatch",
    ):
        words = supervisor.next_action(code)
        assert "carbon_setup_status" in words and "changes nothing" in words
        assert "carbon_setup_review" not in words
    assert "no receiver serves it" in supervisor.next_action(
        "construction_intake_challenge_mismatch"
    )
