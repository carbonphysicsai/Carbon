"""M1 E2E round 10 fixes in Launchpad's own projection."""

from __future__ import annotations

import json

from scripts.dev.miner_launchpad import projection

MOTOR = "electric-motor-magnetics"


def _catalog_recipe():
    from carbon.backbone_catalog import listing
    from scripts.dev.miner_launchpad.toolbox import _catalog_recipe

    first, *_ = listing.entries(MOTOR, "1.3")
    return _catalog_recipe(MOTOR, "1.3", first["catalog_id"])


def _epoch(tmp_path, strategy):
    folder = tmp_path / "epoch-0"
    folder.mkdir()
    (folder / "selected-recipe.json").write_text(json.dumps({"strategy": strategy}))
    return folder / "permitted-final-feedback.json"


def _ladder(recipe_digest):
    latest = {
        "status": "IMPROVED",
        "total": 0.56,
        "exam_version": "motor-exam",
        "recipe_digest": recipe_digest,
        # The receiver's chain epoch (block // 360), never the campaign's own
        # epoch index the projection is given.
        "epoch": 23009,
    }
    return {"latest": latest, "best": latest}


def test_a_catalog_submission_reads_its_grade_under_the_bundle_recipe_it_names(
    tmp_path,
):
    # R10-2: the receiver graded a Motor catalog submission (0.56), but its
    # Ladder names the bundle recipe the catalog recipe expands to, so the
    # page read every auto-graded catalog submission as not graded.
    from carbon.backbone_catalog.served import expand
    from carbon.development_session.construction_recipe import ConstructionRecipe

    strategy = _catalog_recipe()
    submitted = ConstructionRecipe.from_dict(strategy).digest
    graded_as = ConstructionRecipe.from_dict(expand(strategy)).digest
    assert graded_as != submitted
    path = _epoch(tmp_path, strategy)
    also = projection._graded_digests(path, submitted)
    assert also == (graded_as,)
    grade = projection._grade(_ladder(graded_as), submitted, 0, also=also)
    assert grade["this_submission"] == "graded"
    assert grade["latest"]["total"] == 0.56
    # Without the mapping it was another submission's grade.
    old = projection._grade(_ladder(graded_as), submitted, 0)
    assert old["this_submission"] == "not_graded_yet"


def test_no_mapping_unless_the_frozen_selection_is_the_submitted_catalog_recipe(
    tmp_path,
):
    from carbon.development_session.construction_recipe import ConstructionRecipe

    strategy = _catalog_recipe()
    submitted = ConstructionRecipe.from_dict(strategy).digest
    path = _epoch(tmp_path, strategy)
    assert projection._graded_digests(path, "sha256:" + "0" * 64) == ()
    assert projection._graded_digests(path, None) == ()
    (path.parent / "selected-recipe.json").write_text("not json")
    assert projection._graded_digests(path, submitted) == ()
    (path.parent / "selected-recipe.json").unlink()
    assert projection._graded_digests(path, submitted) == ()


def test_an_ungraded_submission_says_check_result_reads_the_latest_grade():
    # R11: observe and wait kept "not_graded_yet" for 12 minutes after the
    # receiver graded it; only check_result (a signed read) fetches it.
    ungraded = projection._grade(_ladder("sha256:" + "b" * 64), "sha256:" + "a" * 64)
    assert ungraded["this_submission"] == "not_graded_yet"
    assert "check_result" in ungraded["refresh"]
    graded = projection._grade(_ladder("sha256:" + "a" * 64), "sha256:" + "a" * 64)
    assert "refresh" not in graded
