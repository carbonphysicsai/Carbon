"""Launchpad fixes from the round-5 M1 E2E matrix (reports/E2E_RESULTS_20261022.md)."""

from scripts.dev.miner_launchpad import supervisor


def test_an_unreachable_construction_receiver_is_not_called_unconfigured():
    # R5-2: with the receiver down, submit was refused
    # construction_intake_unavailable, and the agent read it as "no validator
    # intake", although the profile names the receiver.
    entry = supervisor.refusal("construction_intake_unavailable", operation="submit")
    words = entry["next_action"]
    assert entry["code"] == "construction_intake_unavailable"
    assert words != supervisor.FALLBACK_ACTION
    assert "could not be reached" in words
    assert "configured" in words and "no validator" not in words
    assert "frozen candidate is kept" in words
