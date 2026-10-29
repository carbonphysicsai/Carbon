"""The practice-v2 curves job (scripts/dev/practice_v2_curves.py): it lists the
catalog entries each launch version offers, writes a floor row per Challenge
with no build, runs a candidate through the practice it is handed (a failure
is a row, not a stop), is resumable, and joins its rows for the curve step."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/practice_v2_curves.py"
spec = importlib.util.spec_from_file_location("practice_v2_curves", SCRIPT)
curves = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curves)


def test_every_target_lists_catalog_ids():
    for kind in curves.TARGETS:
        found = curves.candidates(kind)
        assert found == sorted(found)
        assert all(type(item) is str and item for item in found)


@pytest.mark.parametrize("kind", sorted(curves.TARGETS))
def test_the_floor_row_is_a_v2_practice_document(kind):
    document = curves.floor_row(kind)
    assert document["schema"] == "carbon.practice.dual-feedback.v2"
    assert document["available"] is True
    assert document["n_cases"] > 0
    assert set(document["accuracy_legs"]) and set(document["design_parts"]) == {
        "V_pair",
        "V_feas",
        "V_var",
        "C",
    }
    assert document["note"].startswith("Computed on the full public bank")


@pytest.mark.parametrize("kind", sorted(curves.TARGETS))
def test_the_floor_row_is_the_graders_train_mean(kind):
    from carbon.challenge_kit import physical_pack
    from carbon.challenge_validator import calibration_grade as grade
    from carbon.scoring import practice_grid

    _challenge_id, version = curves.TARGETS[kind]
    adapter = practice_grid.adapter(kind, version)
    public = physical_pack.public_roles(adapter.CHALLENGE, version)
    mean = curves.train_mean_row(public["train"], adapter)
    controlled = grade._train_mean(
        [[0.0] * len(mean)],
        None,
        {"_train_raw": public["train"], "_adapter": adapter},
    )
    assert controlled == [mean]


def _args(tmp_path, **extra):
    return SimpleNamespace(
        out_dir=tmp_path, only=extra.get("only"), floor_only=extra.get("floor_only")
    )


def test_a_failure_is_a_row_and_a_result_is_not_rerun(tmp_path, monkeypatch):
    kind = "motor"
    ids = curves.candidates(kind)
    assert ids, "the version offers at least one entry"
    seen = []

    def factory(kind_, args):
        def practice(identity, recipe):
            seen.append(recipe["source"]["catalog_id"])
            if recipe["source"]["catalog_id"] == ids[0]:
                raise ValueError("no docker here")
            return {
                "practice_dual": {"available": True, "total": 0.5},
                "fit": {"state_digest": "sha256:" + "a" * 64},
            }

        return practice

    joined = curves.run(_args(tmp_path, only=kind), practice_factory=factory)
    by = {r["catalog_id"]: r for r in joined["rows"]}
    assert by["ctrl.train_mean"]["practice_dual"]["available"] is True
    assert by[ids[0]]["status"] == "BUILD_FAILED"
    assert by[ids[0]]["reason_code"] == "ValueError"
    if len(ids) > 1:
        assert by[ids[1]]["status"] == "SCORED"
    assert joined["schema"] == curves.SCHEMA and "no registered value changed" in (
        joined["banner"]
    )
    first = list(seen)
    curves.run(_args(tmp_path, only=kind), practice_factory=factory)
    assert seen == first  # resumable: existing rows are not rebuilt
    on_disk = json.loads((tmp_path / "curves_input.json").read_bytes())
    assert on_disk["rows"] == joined["rows"]


def test_only_selects_one_entry_and_floor_only_builds_nothing(tmp_path):
    kind = "motor"
    ids = curves.candidates(kind)

    def never(kind_, args):
        raise AssertionError("a floor-only run builds nothing")

    joined = curves.run(
        _args(tmp_path / "a", floor_only=True, only=kind), practice_factory=never
    )
    assert [r["catalog_id"] for r in joined["rows"]] == ["ctrl.train_mean"]
    one = []

    def factory(kind_, args):
        def practice(identity, recipe):
            one.append(recipe["source"]["catalog_id"])
            return {"practice_dual": {"available": False}, "fit": {}}

        return practice

    curves.run(
        _args(tmp_path / "b", only=f"{kind}:{ids[-1]}"), practice_factory=factory
    )
    assert one == [ids[-1]]


def test_an_ids_file_restricts_the_candidates(tmp_path):
    kind = "motor"
    ids = curves.candidates(kind)
    listing = tmp_path / "ids.txt"
    listing.write_text(ids[0] + "\n\n")
    ran = []

    def factory(kind_, args):
        def practice(identity, recipe):
            ran.append(recipe["source"]["catalog_id"])
            return {"practice_dual": {"available": False}, "fit": {}}

        return practice

    args = SimpleNamespace(
        out_dir=tmp_path / "o", only=kind, floor_only=False, ids_file=listing
    )
    curves.run(args, practice_factory=factory)
    assert ran == [ids[0]]


def _parent_identity_file(tmp_path):
    path = tmp_path / "parent.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.c03.worker-image.v1",
                **{
                    key: "sha256:" + "0" * 64
                    for key in (
                        "image_id",
                        "config_digest",
                        "source_tree_digest",
                        "wheel_digest",
                        "lock_digest",
                        "base_image_digest",
                        "build_recipe_digest",
                        "entrypoint_digest",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("kind", sorted(curves.TARGETS))
def test_the_real_practice_object_constructs_over_a_frozen_ledger(tmp_path, kind):
    """The VM run crashed in `CampaignLedger.freeze` (an unversioned manifest)
    before any build; build the real practice object, no Docker, to catch that
    class of failure here."""
    args = SimpleNamespace(
        out_dir=tmp_path / "out",
        parent_identity=_parent_identity_file(tmp_path),
        cache_root=tmp_path / "cache",
    )
    practice = curves.practice_for(kind, args)
    assert callable(practice)
