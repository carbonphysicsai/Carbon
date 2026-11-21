"""Motor Specialist Bank PATH B v0 (`scripts/dev/bank_retrain.py`): a seed-0 bank retrain of an original recipe
reproduces the OFFICIAL isolated build's state digest bit for bit; bank seeds are the only other seeds; arms change
only the recipe document; the local scorer's own seed default is restored; the report carries no per-design row.
Synthetic graph and verify set (test_kit_local_scorer's): no Carbon data, pack, seed or custody path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bank_retrain as bank
import test_kit_local_scorer as kls

from carbon.challenge_kit import local_scorer

RECIPE = {
    "procedure": {
        "configuration": {
            "training": {"steps": 8, "learning_rate": 0.001},
            "ensemble": {
                "members": [{"outputs": [0], "training": {"learning_rate": 0.0005}}]
            },
        }
    }
}


@pytest.mark.parametrize("seed", [0, 900_000_000, 900_009_999])
def test_the_official_seed_and_the_bank_range_are_accepted(seed):
    assert bank.check_seed(seed) == seed


@pytest.mark.parametrize(
    "seed", [1, -1, 899_999_999, 900_010_000, 2**31 - 2, "0", 0.0, True]
)
def test_every_other_seed_is_refused(seed):
    with pytest.raises(bank.BankRefused, match="seed_not_bank"):
        bank.check_seed(seed)


def test_arms_change_only_the_recipe_document_and_never_the_input():
    before = json.dumps(RECIPE, sort_keys=True)
    assert bank.arm_recipe(RECIPE, "original") == RECIPE
    single = bank.arm_recipe(RECIPE, "single_member")
    assert "ensemble" not in single["procedure"]["configuration"]
    plain = bank.arm_recipe(RECIPE, "defaults_all")
    assert plain["procedure"]["configuration"]["training"] == {}
    assert (
        "training" not in plain["procedure"]["configuration"]["ensemble"]["members"][0]
    )
    lr = bank.arm_recipe(RECIPE, "default:learning_rate")
    assert lr["procedure"]["configuration"]["training"] == {"steps": 8}
    assert lr["procedure"]["configuration"]["ensemble"]["members"][0]["training"] == {}
    assert json.dumps(RECIPE, sort_keys=True) == before


@pytest.mark.parametrize(
    "arm,code",
    [
        ("default:polish_steps", "arm_no_change"),
        ("default:", "arm_unknown"),
        ("zero_weights", "arm_unknown"),
        ("teacher", "arm_unknown"),
    ],
)
def test_an_arm_that_changes_nothing_or_is_not_named_is_refused(arm, code):
    with pytest.raises(bank.BankRefused, match=code):
        bank.arm_recipe(RECIPE, arm)
    with pytest.raises(bank.BankRefused, match="arm_no_change"):
        bank.arm_recipe(
            {"procedure": {"configuration": {"training": {}}}}, "single_member"
        )


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    verify_raw, _doc, query = kls._verify_set()
    with kls._x64():
        raw_manifest, files, digest = kls._graph()
        recipe = kls._recipe({"training": {"steps": kls.STEPS}}, digest)
        official = kls._official(
            tmp_path_factory.mktemp("official"), recipe, raw_manifest, files, query
        )
        doc = recipe.to_dict()
        sha = kls._sha(verify_raw)
        reports = {
            "zero": bank.retrain(
                doc,
                raw_manifest,
                files,
                verify_raw,
                sha,
                seed=0,
                arm="original",
                expect_state_digest=official.build.state_digest,
            ),
            "bank": bank.retrain(
                doc,
                raw_manifest,
                files,
                verify_raw,
                sha,
                seed=900_000_000,
                arm="original",
                expect_state_digest=official.build.state_digest,
            ),
        }
    return official, reports


@kls.posix
def test_a_seed_zero_retrain_reproduces_the_official_build_bit_for_bit(built):
    official, reports = built
    zero = reports["zero"]
    assert zero["admission"]["state"] == "ADMITTED"
    assert zero["state_digest"] == official.build.state_digest
    assert zero["reproduced"] is True
    assert local_scorer.OFFICIAL_SEED == 0


@kls.posix
def test_a_bank_seed_retrain_is_its_own_build_and_makes_no_reproduction_claim(built):
    official, reports = built
    other = reports["bank"]
    assert other["admission"]["state"] == "ADMITTED"
    assert other["seed"] == 900_000_000 and other["reproduced"] is None
    assert other["state_digest"] != official.build.state_digest
    assert local_scorer.OFFICIAL_SEED == 0


@kls.posix
def test_the_report_is_public_signals_only_with_no_per_design_row(built):
    _official, reports = built
    report = reports["zero"]
    assert set(report) == {
        "schema",
        "label",
        "arm",
        "seed",
        "recipe_digest",
        "arm_recipe_digest",
        "code",
        "wall_s",
        "admission",
        "challenge",
        "fit",
        "state_digest",
        "reproduced",
        "verify",
        "predictions_sha256",
    }
    assert set(report["verify"]) == {"sha256", "designs", "aggregate"}
    text = json.dumps(report, sort_keys=True).lower()
    for word in kls.FORBIDDEN + ("synthetic-0", "case_id"):
        assert word not in text


def test_the_scorer_seed_is_restored_when_the_build_raises(monkeypatch):
    def boom(*_a, **_k):
        assert local_scorer.OFFICIAL_SEED == 900_000_001
        raise RuntimeError("build failed")

    monkeypatch.setattr(local_scorer, "build_and_predict", boom)
    monkeypatch.setattr(local_scorer, "_input_names", lambda _b: [])
    monkeypatch.setattr(local_scorer, "load_verify_set", lambda *_a: {"designs": []})
    doc = kls.graph_adapters.graph_recipe(*kls.KEY, "sha256:" + "0" * 64)
    with pytest.raises(RuntimeError, match="build failed"):
        bank.retrain(doc, b"", {}, b"{}", "0" * 64, seed=900_000_001, arm="original")
    assert local_scorer.OFFICIAL_SEED == 0


def test_a_malformed_recipe_is_a_typed_refusal():
    with pytest.raises(bank.BankRefused, match="construction_recipe"):
        bank.retrain({"schema": "x"}, b"", {}, b"{}", "0" * 64, seed=0, arm="original")
