"""LEVEL-AWARE-PROOF-01: a panel member is verified at its OWN construction level.

The decision experiment's values are computed from retained prediction bundles and the
sealed references; this change only decides which recipe digest a level member's bundle
must carry (the level's own compile, then its Level 0 base). Level 0 is byte-for-byte the
old expression. Fixtures only: no solve, no sealed reference, no pod.
"""

from __future__ import annotations

import copy
import gzip
import json
from types import SimpleNamespace

import pytest

from carbon.battery import implementation_versions as iv
from carbon.battery.compile import compile_recipe
from carbon.battery.value import experiment as xp
from carbon.battery.value import level_compile as lc
from carbon.battery.value import panel as pn
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction.challenge_contracts import SubmissionRefused

BATTERY = pn.CHALLENGE_ID
SMALL = {"width": 16, "depth": 1, "steps": 48, "polish_steps": 6}


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {**SMALL, **parameters},
    }


L3 = strategy(quasi_newton_family="bfgs", line_search="backtracking")


@pytest.fixture
def levels_panel(tmp_path, monkeypatch):
    """A registered fixture panel with one Level 3 member and one Level 0 member."""
    monkeypatch.setattr(pn, "PANELS", dict(pn.PANELS))
    monkeypatch.setattr(pn, "LEVELS", dict(pn.LEVELS))
    monkeypatch.setattr(pn, "ATTACK_PANELS", list(pn.ATTACK_PANELS))
    path = tmp_path / "levels.json"
    path.write_text(
        json.dumps(
            {
                "members": [
                    {
                        "label": "fx-l3",
                        "level": 3,
                        "counts_for_level": True,
                        "seeds": [11],
                        "strategy": L3,
                    },
                    {
                        "label": "fx-l0",
                        "level": 0,
                        "counts_for_level": True,
                        "seeds": [12],
                        "strategy": strategy(),
                    },
                    {
                        "label": "fx-l4",
                        "level": 4,
                        "counts_for_level": False,
                        "seeds": [13],
                        "strategy": strategy(),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    # Rows only and no attack constructions: `members` builds those, slowly.
    assert pn.register_levels(path, name="fx-levels", base=None, attack=False) == (
        "fx-l3",
    )
    return "fx-levels"


def stub(panel):
    return SimpleNamespace(contract=lambda: {"panel": panel})


def test_level_zero_digests_are_byte_for_byte_the_old_expression():
    rows = pn.PANELS["ev4-dev-proof"][:6]
    for label, recipe, seeds in rows:
        member = f"{label}-s{seeds[0]}"
        old = {
            compile_recipe(recipe, implementation=version)[1].recipe_digest
            for version in iv.VERSIONS
        }
        assert lc.recipe_digests(recipe, versions=iv.VERSIONS) == old
        assert lc.recipe_digests(recipe, versions=iv.VERSIONS, level=0) == old
        assert (
            xp.Experiment._recipe_digests(stub("ev4-dev-proof"), member, recipe) == old
        )


def test_a_level_three_strategy_is_refused_at_level_zero_and_compiles_at_its_level():
    with pytest.raises((RecipeRejected, SubmissionRefused)):
        compile_recipe(L3)
    digests = lc.recipe_digests(L3, versions=iv.VERSIONS, level=3)
    base = strategy()
    assert digests == lc.recipe_digests(base, versions=iv.VERSIONS)
    assert lc.base_for(L3, 3)["parameters"] == base["parameters"]


def test_the_panel_names_each_members_level(levels_panel):
    levels = pn.levels(levels_panel)
    assert levels["fx-l3-s11"] == (3, None)
    assert "fx-l0-s12" not in levels and "fx-l4-s13" not in levels
    existing = pn.levels("ev4-dev-proof")  # the existing panel is all Level 0
    assert existing and {v for v in existing.values()} == {(0, None)}


def test_the_experiment_verifies_a_level_member_by_its_own_level(levels_panel):
    member = "fx-l3-s11"
    digests = xp.Experiment._recipe_digests(stub(levels_panel), member, L3)
    assert digests == lc.recipe_digests(strategy(), versions=iv.VERSIONS)
    assert (
        xp.Experiment._base_strategy(stub(levels_panel), member, L3)["parameters"]
        == strategy()["parameters"]
    )
    # The same strategy under a Level 0 label is refused, not silently accepted.
    with pytest.raises((RecipeRejected, SubmissionRefused)):
        xp.Experiment._recipe_digests(stub(levels_panel), "fx-l0-s12", L3)


def test_a_level_strategy_the_variant_refuses_is_a_typed_experiment_error(levels_panel):
    bad = copy.deepcopy(L3)
    bad["parameters"]["quasi_newton_family"] = "not_a_routine"
    with pytest.raises(xp.ExperimentError) as refused:
        xp.Experiment._recipe_digests(stub(levels_panel), "fx-l3-s11", bad)
    assert refused.value.code == lc.LEVEL_REFUSED


def test_import_predictions_accepts_a_level_bundle_and_refuses_a_wrong_digest(
    levels_panel, tmp_path, monkeypatch
):
    experiment = xp.Experiment(tmp_path / "root")
    monkeypatch.setattr(experiment, "contract", lambda: {"panel": levels_panel})
    good = lc.recipe_digests(strategy(), versions=[iv.VERSIONS[-1]])
    [digest] = good

    def bundle(member, recipe_digest, seed):
        body = {"member": member, "recipe_digest": recipe_digest, "seed": seed}
        return gzip.compress(json.dumps(body).encode(), mtime=0)

    source = tmp_path / "source"
    source.mkdir()
    (source / "fx-l3-s11.json.gz").write_bytes(bundle("fx-l3-s11", digest, 11))
    result = experiment.import_predictions(source)
    assert result["imported"] == ["fx-l3-s11"]
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    (wrong / "fx-l3-s11.json.gz").write_bytes(
        bundle("fx-l3-s11", "sha256:" + "0" * 64, 11)
    )
    other = xp.Experiment(tmp_path / "root2")
    monkeypatch.setattr(other, "contract", lambda: {"panel": levels_panel})
    with pytest.raises(xp.ExperimentError) as mismatch:
        other.import_predictions(wrong)
    assert mismatch.value.code == "artifact_mismatch"


def test_a_level_member_is_never_reconstructed_locally(
    levels_panel, tmp_path, monkeypatch
):
    experiment = xp.Experiment(tmp_path / "root")
    monkeypatch.setattr(experiment, "contract", lambda: {"panel": levels_panel})
    monkeypatch.setattr(xp, "panel_inputs", lambda *_a, **_k: {})
    with pytest.raises(xp.ExperimentError) as refused:
        experiment.panel(backend=object(), only={"fx-l3-s11"})
    assert refused.value.code == "level_member_not_reconstructed_here"


def test_no_panel_file_registers_nothing(tmp_path):
    assert pn.register_levels(tmp_path / "absent.json", name="fx-absent") == ()
    assert "fx-absent" not in pn.PANELS


def test_rows_that_do_not_count_for_their_level_stay_out_of_every_level(
    tmp_path, monkeypatch
):
    """Lane G's `l4v3-plain-*` rows carry counts_for_level false: never counted at
    Level 4 (and a Level 4 row is not a level-aware member here at all)."""
    monkeypatch.setattr(pn, "PANELS", dict(pn.PANELS))
    monkeypatch.setattr(pn, "LEVELS", dict(pn.LEVELS))
    monkeypatch.setattr(pn, "ATTACK_PANELS", list(pn.ATTACK_PANELS))
    rows = [
        {
            "label": "l4v3-plain-a",
            "level": 4,
            "counts_for_level": False,
            "seeds": [1],
            "strategy": strategy(),
        },
        {
            "label": "l4v3-plain-b",
            "level": 4,
            "counts_for_level": True,
            "seeds": [2],
            "strategy": strategy(),
        },
        {
            "label": "l2-plain",
            "level": 2,
            "counts_for_level": False,
            "seeds": [3],
            "strategy": strategy(),
        },
        {
            "label": "l2-counted",
            "level": 2,
            "counts_for_level": True,
            "seeds": [4],
            "strategy": strategy(),
        },
    ]
    path = tmp_path / "levels.json"
    path.write_text(json.dumps({"members": rows}), encoding="utf-8")
    assert pn.register_levels(path, name="fx-count", base=None, attack=False) == (
        "l2-counted",
    )
    levels = pn.levels("fx-count")
    assert [m for m in levels if m.startswith("l4v3-plain")] == []
    assert levels["l2-counted-s4"] == (2, None) and "l2-plain-s3" not in levels
    assert sum(1 for level, _arm in levels.values() if level == 4) == 0


def test_a_default_registration_carries_the_attack_constructions_like_the_proof_panel(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(pn, "PANELS", dict(pn.PANELS))
    monkeypatch.setattr(pn, "LEVELS", dict(pn.LEVELS))
    monkeypatch.setattr(pn, "ATTACK_PANELS", list(pn.ATTACK_PANELS))
    path = tmp_path / "levels.json"
    path.write_text(
        json.dumps(
            {
                "members": [
                    {
                        "label": "fx-l2",
                        "level": 2,
                        "counts_for_level": True,
                        "seeds": [5],
                        "strategy": strategy(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert pn.register_levels(path, name="fx-default") == ("fx-l2",)
    assert "fx-default" in pn.ATTACK_PANELS
    assert len(pn.PANELS["fx-default"]) == len(pn.PANELS["ev4-dev-proof"]) + 1
