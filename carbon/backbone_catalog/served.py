"""The catalog a Challenge version serves, and how a catalog recipe runs.

A catalog recipe names `source: {kind: "catalog", catalog_id, catalog_digest}`
with the entry's settings in `procedure.configuration` / `procedure.train_use`
(`carbon.development_session.construction_recipe`). `catalog_digest` is this
module's `digest` for the recipe's Challenge version, which the version's
construction limits document also carries, so a recipe binds the exact
catalog it was written against.

`expand` turns an admitted catalog recipe into the Carbon bundle recipe it
stands for: the entry's tested bundle, its entrypoint, and the settings
resolved over the baseline's defaults. That bundle recipe then runs through
the existing bundle build and inference, unchanged. Only Carbon's own tested
bundles resolve here; miner bundles stay closed.
"""

from __future__ import annotations

import hashlib
import json

from . import pipeline, settings
from .entries import CatalogRefused

SCHEMA = "carbon.backbone-catalog.served.v1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def document(challenge_id, version):
    """What a version serves: every entry offered on it, with its settings."""
    return {
        "schema": SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "entries": {
            item["catalog_id"]: {
                "backbone": item["backbone"],
                "bundle_ref": item["bundle_ref"],
                "output_format": item["output_format"],
                "settings": settings.document(item),
            }
            for item in pipeline.entries(challenge_id, version)
        },
        "source_kind": "catalog",
        "defaults": "the tested baseline's settings; unset settings keep them",
    }


def digest(challenge_id, version):
    return (
        "sha256:"
        + hashlib.sha256(_canonical(document(challenge_id, version))).hexdigest()
    )


SUBMISSION_SCHEMA = "carbon.backbone-catalog.submission.v1"


def submission_document(catalog_recipe, bundle_recipe):
    """The canonical record of a catalog submission: the miner's recipe (the
    submission identity, with its catalog_digest) and the digest of the Carbon
    bundle recipe it expanded to."""
    from carbon.development_session.construction_recipe import ConstructionRecipe

    miner = ConstructionRecipe.from_dict(catalog_recipe)
    bundle = ConstructionRecipe.from_dict(bundle_recipe)
    source = miner.to_dict()["source"]
    if source["kind"] != "catalog":
        raise ValueError("a catalog recipe is required")
    return _canonical(
        {
            "schema": SUBMISSION_SCHEMA,
            "recipe": miner.to_dict(),
            "recipe_digest": miner.digest,
            "catalog_id": source["catalog_id"],
            "catalog_digest": source["catalog_digest"],
            "bundle_recipe_digest": bundle.digest,
        }
    )


def check_reexpansion(document_bytes, bundle_recipe_digest):
    """Re-expand a retained catalog submission; raise ValueError unless it
    gives exactly the retained bundle recipe (regrade and retention)."""
    from carbon.development_session.construction_recipe import ConstructionRecipe

    document = json.loads(document_bytes)
    if type(document) is not dict or document.get("schema") != SUBMISSION_SCHEMA:
        raise ValueError("catalog submission malformed")
    if document.get("bundle_recipe_digest") != bundle_recipe_digest:
        raise ValueError("catalog submission names another bundle recipe")
    again = ConstructionRecipe.from_dict(expand(document["recipe"])).digest
    if again != bundle_recipe_digest:
        raise ValueError("catalog re-expansion differs")
    return document


def expand(recipe):
    """The Carbon bundle recipe an admitted catalog recipe stands for.

    `recipe` is a parsed `ConstructionRecipe` dict whose identity fields were
    already bound to its Challenge. Raises `CatalogRefused`."""
    challenge = recipe["challenge"]
    source = recipe["source"]
    if source.get("kind") != "catalog":
        raise ValueError("a catalog recipe is required")
    if source["catalog_digest"] != digest(challenge["id"], challenge["version"]):
        raise CatalogRefused(
            "catalog_entry_unknown",
            "catalog_digest is not the catalog this Challenge version serves",
        )
    item = pipeline.entry(source["catalog_id"], challenge["id"], challenge["version"])
    if item is None:
        raise CatalogRefused(
            "catalog_entry_unknown",
            f"{source['catalog_id']!r} is not in this Challenge version's catalog",
        )
    procedure = recipe["procedure"]
    if recipe["output"]["format"] != item["output_format"]:
        raise CatalogRefused(
            "catalog_settings_inconsistent",
            f"output.format is {item['output_format']} for {item['catalog_id']}",
        )
    configuration, train_use = settings.resolve(
        item, procedure["configuration"], procedure["train_use"]
    )
    return {
        "schema": recipe["schema"],
        "challenge": dict(challenge),
        "source": {"kind": "bundle", "bundle_ref": dict(item["bundle_ref"])},
        "procedure": {
            "entrypoint": dict(item["entrypoint"]),
            "configuration": configuration,
            "train_use": train_use,
            "initial_state": None,
        },
        "output": dict(recipe["output"]),
    }
