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

from . import listing, settings
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
            for item in listing.entries(challenge_id, version)
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


def refuse_unreproducible_runtime(bundle_ref):
    """Refuse (typed GAP `catalog_runtime_not_reproducible`) a recipe whose `source.bundle_ref` is a GPU build the
    official route cannot rebuild reproducibly: a smoke-only entry's GPU build, or any GPU build without an
    official-grade receipt (pinned GPU worker image digest, the full determinism environment, a registered host
    class: `gpu_receipt.official_grade_problem`). A recipe names its bundle_ref directly, so the receiver's recipe
    screen looks the digest up here, before anything is reserved. The CPU build is always the official one.
    """
    from . import gpu_receipt

    wanted = bundle_ref.get("bundle_digest")
    for item in listing.load()["entries"]:
        for runtime, ref in (item.get("bundle_refs") or {}).items():
            if ref["bundle_digest"] != wanted:
                continue
            try:
                problem = gpu_receipt.official_grade_problem(
                    gpu_receipt.load(item["catalog_id"], runtime), runtime
                )
            except gpu_receipt.GpuReceiptBroken:
                problem = "its receipt is invalid"
            if problem is None:
                continue
            base = item["bundle_ref"]
            raise CatalogRefused(
                "catalog_runtime_not_reproducible",
                f"{item['catalog_id']!r} {runtime} is not officially gradable: {problem}; "
                f"{gpu_receipt.CARD_NOTE}; use the {base['runtime_profile_id']} build {base['bundle_digest']}",
            )


def runtime_bundle_ref(item, runtime, *, official):
    """The bundle ref of the runtime a recipe names for `item`; `official` is the grading rebuild.

    The CPU build is always the official one. A GPU build needs its valid receipt (`gpu_receipt`); a smoke-only
    GPU build is practice only, so the official route refuses it with the typed GAP `catalog_runtime_not_reproducible`
    and names the CPU build, which keeps its CPU pair-identity receipt (Validator ruling, 2026-10-22).
    """
    from . import gpu_receipt

    base = item["bundle_ref"]
    if runtime == base["runtime_profile_id"]:
        return dict(base)
    ref = (item.get("bundle_refs") or {}).get(runtime)
    if ref is None:
        raise CatalogRefused(
            "catalog_entry_unknown", f"{item['catalog_id']!r} has no {runtime} build"
        )
    receipt = gpu_receipt.load(item["catalog_id"], runtime)
    if receipt is None:
        raise CatalogRefused(
            "catalog_entry_unknown",
            f"{item['catalog_id']!r} {runtime} build has no receipt yet",
        )
    if official:
        refuse_unreproducible_runtime(ref)
    return dict(ref)


def expand(recipe, runtime=None):
    """The Carbon bundle recipe an admitted catalog recipe stands for.

    `recipe` is a parsed `ConstructionRecipe` dict whose identity fields were
    already bound to its Challenge. Raises `CatalogRefused`.

    `runtime` (miner GPU practice only) asks for the entry's build for that
    bundle runtime (`bundle_refs`); `catalog_gpu_build_missing` when it has
    none (`GpuBuildMissing`). None, as every receiver and CPU practice asks,
    is the entry's own
    `bundle_ref`, exactly as before."""
    challenge = recipe["challenge"]
    source = recipe["source"]
    if source.get("kind") != "catalog":
        raise ValueError("a catalog recipe is required")
    if source["catalog_digest"] != digest(challenge["id"], challenge["version"]):
        raise CatalogRefused(
            "catalog_entry_unknown",
            "catalog_digest is not the catalog this Challenge version serves",
        )
    item = listing.entry(source["catalog_id"], challenge["id"], challenge["version"])
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
        "source": {"kind": "bundle", "bundle_ref": dict(_bundle_ref(item, runtime))},
        "procedure": {
            "entrypoint": dict(item["entrypoint"]),
            "configuration": configuration,
            "train_use": train_use,
            "initial_state": None,
        },
        "output": dict(recipe["output"]),
    }


def _bundle_ref(item, runtime):
    if runtime is None:
        return item["bundle_ref"]
    builds = item.get("bundle_refs")
    built = builds.get(runtime) if type(builds) is dict else None
    if type(built) is not dict or built.get("runtime_profile_id") != runtime:
        raise GpuBuildMissing(item["catalog_id"], runtime)
    # Practice serves a GPU build only when it is offered: a valid receipt of its kind (smoke or repeat, any
    # image). A build that was never shown to run on a GPU is not served; the typed GAP names the CPU build (Validator,
    # 2026-10-22). The official route is separate and stricter (`runtime_bundle_ref`).
    from . import gpu_receipt

    if runtime not in gpu_receipt.offered_runtimes(item):
        raise GpuBuildNotOffered(item, runtime)
    return built


class GpuBuildMissing(ValueError):
    """Miner GPU practice only: the entry has no build for the asked runtime,
    so it practises on CPU. Not a catalog refusal: no receiver screens it."""

    code = "catalog_gpu_build_missing"

    def __init__(self, catalog_id, runtime):
        super().__init__(f"{catalog_id!r} has no {runtime} build yet")


class GpuBuildNotOffered(GpuBuildMissing):
    """Miner GPU practice only: the entry has the build but it is not offered (no valid receipt, or the owner's
    confirmation is pending), so it practises on CPU. A `GpuBuildMissing` handler catches it too; the typed code
    differs and the message names the CPU build."""

    code = "catalog_gpu_build_not_offered"

    def __init__(self, item, runtime):
        base = item["bundle_ref"]
        ValueError.__init__(
            self,
            f"{item['catalog_id']!r} {runtime} build is not offered yet (no valid receipt for it); practise on the "
            f"{base.get('runtime_profile_id')} build {base.get('bundle_digest')}",
        )
