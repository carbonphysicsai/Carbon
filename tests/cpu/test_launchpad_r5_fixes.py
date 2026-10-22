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


def test_a_direct_challenge_without_a_capability_contract_has_a_toolbox():
    # R5-9: F08 1.4 and F02 2.3 read challenge_has_no_toolbox, since neither
    # has a construction capability contract; a miner had no example.
    import pytest

    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.direct_campaign.spec import SPECS
    from carbon.reconstruction.capability_registry import (
        UnknownChallenge,
        public_registry,
    )
    from scripts.dev.miner_launchpad import toolbox

    for challenge_id in SPECS:
        with pytest.raises(UnknownChallenge):
            public_registry(challenge_id)
        ref = challenge_ref(challenge_id)
        built = toolbox.build(ref, lanes={}, direct=True)
        assert built["examples"], challenge_id
        assert {e["schema"] for e in built["examples"]} == {
            "carbon.construction-recipe.v1"
        }
        assert all(e["challenge"]["id"] == challenge_id for e in built["examples"])


def test_an_unnamed_grade_is_never_any_submission_s_own(tmp_path):
    # R5-1: three submissions read "Graded 0.54"; the receiver graded one. A
    # Ladder document that names no submission is the mining key's latest
    # grade on the exam, shown apart and never ticked as this submit's.
    from pathlib import Path

    from scripts.dev.miner_launchpad import projection

    unnamed = {
        "schema": "carbon.private-exam.ladder-feedback.v1",
        "exam_version": "motor-1.3-dev",
        "status": "IMPROVED",
        "total": 0.5488,
        "A": 0.298,
        "D": 0.8,
        "gate_names": [],
    }
    for digest in ("a", "b", "c"):
        grade = projection._grade(
            {"best": unnamed, "latest": unnamed}, "sha256:" + digest * 64
        )
        assert grade["latest"] is None
        assert grade["exam_latest"]["total"] == 0.5488
    page = Path("scripts/dev/miner_launchpad")
    for name in ("app.js", "research_view.js"):
        text = (page / name).read_text(encoding="utf-8")
        assert "it is not this one's" in text
        assert "rebuilt, not graded yet" in text
        assert "may be from an earlier submission" not in text
