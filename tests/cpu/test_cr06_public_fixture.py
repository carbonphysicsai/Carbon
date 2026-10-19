"""The public CR06 graph fixture is whole and bound to its public Challenge."""

import hashlib
import json
from pathlib import Path

import pytest

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    bind_recipe,
    graph_workspace,
)
from carbon.development_session.synthetic_graph_adapter import graph_interface
from carbon.level4 import graph, intake, staging, submission
from carbon.level4.allowlist import Allowlist

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cr06_public"
RECIPE_SHA256 = "6ada6144b8e7cc76de32e1e4f3dc0727fdcf701f83ec93c4cacfe01caff817e2"
ENVELOPE_SHA256 = "a8d97ad8512fafe6bdb7e6bca569e3ee1ed2639627ceacbe45975ab05ed20f50"


def _fixture(name: str, expected_sha256: str) -> bytes:
    raw = (FIXTURE / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha256
    return raw


def test_cr06_public_graph_fixture_has_complete_bound_document_closure():
    recipe = ConstructionRecipe.from_bytes(_fixture("cr06_recipe.json", RECIPE_SHA256))
    envelope = json.loads(_fixture("cr06_envelope.json", ENVELOPE_SHA256))
    material = bundle_material_v5()
    kit = material["construction_kit"]
    assert (
        bind_recipe(
            recipe.to_dict(),
            challenge_id=kit["id"],
            challenge_version=kit["version"],
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        ).digest
        == recipe.digest
    )

    digest, raw_manifest, files = staging.from_envelope(envelope)
    assert digest == recipe.to_dict()["source"]["submission_digest"]
    staged = graph_workspace(
        recipe, raw_manifest, files, max_bytes=intake.BOUNDS["submission_bytes"]
    )
    assert staging.from_workspace(staged, digest) == (raw_manifest, files)

    allowed = Allowlist(material["allowlist_bytes"])
    manifest, documents = submission.verify(
        raw_manifest,
        files,
        allowlist=allowed,
        challenge=kit["id"],
        interface=graph_interface().digest(),
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    assert set(files) == set(manifest["documents"].values())
    assert set(documents) == {"forward", "init_spec"}
    assert documents["init_spec"]["graph"] == manifest["documents"]["forward"]
    allowed.check(documents["forward"])


def test_cr06_public_graph_fixture_refuses_missing_or_wrong_graph_bytes():
    recipe = ConstructionRecipe.from_bytes(_fixture("cr06_recipe.json", RECIPE_SHA256))
    envelope = json.loads(_fixture("cr06_envelope.json", ENVELOPE_SHA256))
    _, raw_manifest, files = staging.from_envelope(envelope)
    missing = dict(files)
    missing.pop(next(iter(missing)))
    with pytest.raises(graph.GraphRefused, match="submission_documents"):
        submission.verify(
            raw_manifest,
            missing,
            allowlist=Allowlist(bundle_material_v5()["allowlist_bytes"]),
            challenge=recipe.to_dict()["challenge"]["id"],
            interface=graph_interface().digest(),
            max_bytes=intake.BOUNDS["document_bytes"],
        )
    changed = recipe.to_dict()
    changed["source"]["submission_digest"] = "sha256:" + "0" * 64
    with pytest.raises(
        RecipeRefused, match="construction_recipe_graph_digest_mismatch"
    ):
        graph_workspace(
            ConstructionRecipe.from_dict(changed),
            raw_manifest,
            files,
            max_bytes=intake.BOUNDS["submission_bytes"],
        )
