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
    assert "never graded twice" in words
    assert "frozen candidate is kept" in words


def test_a_direct_challenge_without_a_capability_contract_has_a_toolbox():
    # R5-9: F08 1.4 and F02 2.3 read challenge_has_no_toolbox, since neither
    # has a construction capability contract; a miner had no example.
    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.direct_campaign.spec import SPECS
    from carbon.reconstruction.capability_registry import (
        UnknownChallenge,
        public_registry,
    )
    from scripts.dev.miner_launchpad import toolbox

    without = set()
    for challenge_id in SPECS:
        # A direct Challenge may or may not have a capability contract
        # (Battery 2.2 does); this is about the ones that have none.
        try:
            public_registry(challenge_id)
            continue
        except UnknownChallenge:
            without.add(challenge_id)
        ref = challenge_ref(challenge_id)
        built = toolbox.build(ref, lanes={}, direct=True)
        assert built["examples"], challenge_id
        assert {e["schema"] for e in built["examples"]} == {
            "carbon.construction-recipe.v1"
        }
        assert all(e["challenge"]["id"] == challenge_id for e in built["examples"])
    assert {"f08-ribbed-bracket", "f02"} <= without


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
        assert grade["other_submission_latest"]["total"] == 0.5488
    page = Path("scripts/dev/miner_launchpad")
    for name in ("app.js", "research_view.js"):
        text = (page / name).read_text(encoding="utf-8")
        assert "it is not this one's" in text
        assert "rebuilt, not graded yet" in text
        assert "may be from an earlier submission" not in text


def test_a_v3_grade_is_this_submission_s_by_its_recipe_whatever_the_epoch_units():
    # Validator note on R5-1: v3 names the epoch as well as the recipe.
    from scripts.dev.miner_launchpad import projection

    digest = "sha256:" + "a" * 64
    earlier = {
        "schema": "carbon.private-exam.ladder-feedback.v3",
        "exam_version": "motor-1.3-dev",
        "status": "IMPROVED",
        "total": 0.5,
        "A": 0.3,
        "D": 0.7,
        "gate_names": [],
        "recipe_digest": digest,
        "epoch": 1,
    }
    # M1 E2E R10-2: the Ladder's epoch is the chain epoch (exam_cap.epoch_of,
    # e.g. 23009), the projection's is the campaign's own index (FINAL_EPOCHS),
    # so the two were never equal and every v3 grade read "not graded yet".
    # The recipe digest names the submission; a same-recipe resubmit returns
    # its earlier grade (exam cap), so that grade is this submission's too.
    for campaign_epoch in (0, 1, 2):
        grade = projection._grade(
            {"best": earlier, "latest": earlier}, digest, campaign_epoch
        )
        assert grade["this_submission"] == "graded"
        assert (
            grade["latest"]["epoch"] == 1 and grade["other_submission_latest"] is None
        )
    other = projection._grade(
        {"best": earlier, "latest": earlier}, "sha256:" + "b" * 64, 1
    )
    assert other["latest"] is None and other["other_submission_latest"]["epoch"] == 1
