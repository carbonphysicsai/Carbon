"""A catalog submission's identity across retention and regrade (Validator,
2026-10-20): the miner's catalog recipe (with its catalog_digest) is kept as
the submission identity beside the expanded bundle's digest, and a regrade
rebuilds the retained bundle only while re-expansion gives exactly it."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.backbone_catalog import listing, served
from carbon.challenge_registry.motor import catalog_recipe
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session.construction_recipe import ConstructionRecipe

ROOT = Path(__file__).resolve().parents[2]


def expanded_digest(recipe):
    return ConstructionRecipe.from_dict(served.expand(recipe)).digest


def test_expansion_is_deterministic_in_process_and_across_processes():
    recipe = catalog_recipe("neuralop.TFNO")
    recipe["procedure"]["train_use"] = {"steps": 900, "averaging": {"kind": "ema"}}
    first, second = expanded_digest(recipe), expanded_digest(copy.deepcopy(recipe))
    program = (
        f"import json, sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "from carbon.backbone_catalog import served\n"
        "from carbon.development_session.construction_recipe import ConstructionRecipe\n"
        f"recipe = json.loads({json.dumps(json.dumps(recipe))})\n"
        "print(ConstructionRecipe.from_dict(served.expand(recipe)).digest)\n"
    )
    fresh = subprocess.run(
        [sys.executable, "-I", "-c", program],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    assert first == second == fresh.stdout.strip().splitlines()[-1]


def test_a_retained_submission_reexpands_to_its_bundle():
    recipe = catalog_recipe("transolver")
    bundle = served.expand(recipe)
    document = served.submission_document(recipe, bundle)
    kept = served.check_reexpansion(
        document, ConstructionRecipe.from_dict(bundle).digest
    )
    assert kept["recipe"] == ConstructionRecipe.from_dict(recipe).to_dict()
    assert kept["catalog_digest"] == recipe["source"]["catalog_digest"]


def test_a_regrade_refuses_when_reexpansion_gives_another_bundle(monkeypatch):
    recipe = catalog_recipe("neuralop.FNO")
    bundle = served.expand(recipe)
    document = served.submission_document(recipe, bundle)
    digest = ConstructionRecipe.from_dict(bundle).digest
    with pytest.raises(ValueError, match="another bundle"):
        served.check_reexpansion(document, "sha256:" + "0" * 64)
    # The catalog moved under the retained submission: its defaults changed.
    original = listing.entry

    def moved(catalog_id, *args):
        item = copy.deepcopy(original(catalog_id, *args))
        item["defaults"]["configuration"]["learning_rate"] = 0.004
        return item

    monkeypatch.setattr(listing, "entry", moved)
    with pytest.raises(ValueError, match="re-expansion differs"):
        served.check_reexpansion(document, digest)


def test_the_ledger_keeps_a_catalog_submission_create_only(tmp_path):
    ledger = AttemptLedger(tmp_path / "ledger.sqlite3")
    document = served.submission_document(
        catalog_recipe(), served.expand(catalog_recipe())
    )
    ledger.record_catalog_submission("sha256:" + "c" * 64, "rtsk_" + "1" * 64, document)
    ledger.record_catalog_submission("sha256:" + "c" * 64, "rtsk_" + "1" * 64, document)
    assert (
        ledger.catalog_submission("sha256:" + "c" * 64, "rtsk_" + "1" * 64) == document
    )
    assert ledger.catalog_submission("sha256:" + "c" * 64, "rtsk_" + "2" * 64) is None
    with pytest.raises(ValueError, match="conflict"):
        ledger.record_catalog_submission(
            "sha256:" + "c" * 64, "rtsk_" + "1" * 64, document + b" "
        )
