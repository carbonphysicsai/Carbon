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


# --- an OFFICIAL grade retains the entry's GPU twin (the grading rebuild), not its CPU build -------------------


GPU_RUNTIME = "torch-cu130-py311"


def _official_bundle(monkeypatch, catalog_id="neuralop.FNO"):
    """The bundle recipe the official route retains for a catalog recipe: `expand_official`'s GPU twin build."""
    recipe = catalog_recipe(catalog_id)
    item = listing.entry(
        catalog_id, recipe["challenge"]["id"], recipe["challenge"]["version"]
    )
    twin = item["bundle_refs"][GPU_RUNTIME]
    monkeypatch.setattr(
        served,
        "runtime_bundle_ref",
        lambda item, runtime, *, official, store=None: dict(
            item["bundle_refs"][runtime]
        ),
    )
    bundle, runtime = served.expand_official(recipe, (GPU_RUNTIME,))
    assert runtime == GPU_RUNTIME and bundle["source"]["bundle_ref"] == twin
    assert (
        bundle["source"]["bundle_ref"] != served.expand(recipe)["source"]["bundle_ref"]
    )
    return recipe, bundle


def test_an_official_gpu_catalog_submission_reexpands_to_its_retained_twin(monkeypatch):
    """Regression: retention/regrade re-expanded with the CPU build only, so every official GPU catalog grade failed
    with catalog_reexpansion_differs."""
    recipe, bundle = _official_bundle(monkeypatch)
    document = served.submission_document(recipe, bundle)
    digest = ConstructionRecipe.from_dict(bundle).digest
    kept = served.check_reexpansion(document, digest, bundle)
    assert kept["recipe"] == ConstructionRecipe.from_dict(recipe).to_dict()
    # Without the retained recipe the check is what it was: the CPU build only.
    with pytest.raises(ValueError, match="re-expansion differs"):
        served.check_reexpansion(document, digest)


def test_a_tampered_official_submission_still_fails_reexpansion(monkeypatch):
    recipe, bundle = _official_bundle(monkeypatch)

    def refused(retained):
        document = served.submission_document(recipe, retained)
        digest = ConstructionRecipe.from_dict(retained).digest
        with pytest.raises(ValueError, match="re-expansion differs"):
            served.check_reexpansion(document, digest, retained)

    # a changed procedure setting
    changed = copy.deepcopy(bundle)
    changed["procedure"]["configuration"]["learning_rate"] = 0.123
    refused(changed)
    # a runtime the entry does not pin
    other_runtime = copy.deepcopy(bundle)
    other_runtime["source"]["bundle_ref"]["runtime_profile_id"] = "jax-cuda13-py311"
    refused(other_runtime)
    # the pinned runtime with another entry's twin digest
    other = listing.entry(
        "transolver", recipe["challenge"]["id"], recipe["challenge"]["version"]
    )
    swapped = copy.deepcopy(bundle)
    swapped["source"]["bundle_ref"] = dict(other["bundle_refs"][GPU_RUNTIME])
    refused(swapped)
    # a retained recipe that names no bundle at all
    malformed = copy.deepcopy(bundle)
    del malformed["source"]["bundle_ref"]
    document = served.submission_document(recipe, bundle)
    with pytest.raises(ValueError):
        served.check_reexpansion(
            document, ConstructionRecipe.from_dict(bundle).digest, malformed
        )


def test_the_retention_and_regrade_checks_pass_the_retained_recipe():
    source = (ROOT / "carbon/challenge_validator/lean_recipe_retention.py").read_text(
        encoding="utf-8"
    )
    assert "check_reexpansion(catalog, recipe.digest, recipe.to_dict())" in source
    assert 'files["catalog-submission.json"], recipe.digest, recipe.to_dict()' in source


def _retained_official_origin(tmp_path, monkeypatch, tamper=False):
    """A retained official GPU catalog grade on disk exactly as `_regrade_origin` reads it (the bank entry, its
    custody receipt name, the task's retained files and their roles manifest)."""
    import hashlib
    from types import SimpleNamespace

    def sha(raw):
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    recipe, bundle = _official_bundle(monkeypatch)
    retained = ConstructionRecipe.from_dict(bundle)
    if tamper:
        recipe = copy.deepcopy(recipe)
        recipe["procedure"]["configuration"]["learning_rate"] = 0.987
    document = served.submission_document(recipe, bundle)
    origin = "rtsk_" + "1" * 64
    base, entries = tmp_path / "artifacts", tmp_path / "entries"
    for directory in (base, base / origin, entries):
        directory.mkdir(mode=0o700)
    state = b"retained state bytes"
    files = {
        "state.npz": state,
        "recipe.json": retained.canonical_bytes,
        "catalog-submission.json": document,
    }
    for name, raw in files.items():
        (base / origin / name).write_bytes(raw)
    (base / (origin + ".roles.json")).write_text(
        json.dumps({"retained_files": {n: sha(r) for n, r in files.items()}})
    )
    entry_id = "sha256:" + "a" * 64
    (entries / ("a" * 64 + ".json")).write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "custody_receipt": {"file": origin + ".custody.json"},
                "state_digest": sha(state),
                "recipe_digest": retained.digest,
            }
        )
    )
    adapter = SimpleNamespace(
        ledger=SimpleNamespace(owned_outcome=lambda contract, task: "hotkey"),
        contract_digest="sha256:" + "c" * 64,
    )
    return adapter, base, entries, entry_id, retained


def test_the_regrade_and_repeat_origin_accepts_a_retained_official_gpu_catalog_grade(
    tmp_path, monkeypatch
):
    """`regrade_retained_entry` and `repeat_grade` (the KOTH repeat) both open a retained task through
    `_regrade_origin`; an official GPU catalog grade must pass its re-expansion there.
    """
    from carbon.challenge_validator import lean_recipe_retention as retention

    adapter, base, entries, entry_id, retained = _retained_official_origin(
        tmp_path, monkeypatch
    )
    *_, recipe = retention._regrade_origin(adapter, base, entries, entry_id)
    assert recipe.digest == retained.digest


def test_the_regrade_origin_refuses_a_retained_catalog_submission_that_no_longer_expands_to_it(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    adapter, base, entries, entry_id, _retained = _retained_official_origin(
        tmp_path, monkeypatch, tamper=True
    )
    with pytest.raises(
        retention.RetentionUnavailable, match="regrade_catalog_reexpansion_differs"
    ):
        retention._regrade_origin(adapter, base, entries, entry_id)
