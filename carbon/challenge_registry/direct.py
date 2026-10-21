"""Discovery for the direct-recipe-only versions: F08 (Ribbed Bracket) 1.4 and
F02 (Burst Thermal) 2.3.

A description names the registered interface, construction kit, served backbone
catalog and graph training adapter (each from its registered source), and a
ready catalog recipe and graph recipe template. What the registration does
not state - the task wording, the intended use, the exam, the per-case policy -
is `HUMAN_INPUT`. Practice reports aggregate errors on the registered scale
(Validator, 2026-10-21). Miner source bundles stay closed.
"""

from __future__ import annotations

from carbon.direct_campaign.spec import HUMAN_INPUT


def _kit(spec, version):
    from carbon.direct_campaign.spec import key_for

    key = key_for(spec, version)
    return spec.public().construction_kit(key.challenge_id, key.version)


def catalog_recipe(spec, catalog_id=None, *, version):
    """A ready catalog recipe for `spec` at `version` (no default): the
    version's kit, one catalog entry (`catalog_id`, or the first the version
    offers) and its tested baseline settings (empty: unset settings keep the
    baseline's).

    While the version's catalog is empty and no id is named, this is an
    unfilled template whose `catalog_id` and `output.format` are None: an
    explicit gap, never a recipe that runs. A named id the version does not
    offer is refused (`catalog_entry_unknown`).
    """
    from carbon.backbone_catalog import listing, served
    from carbon.backbone_catalog.entries import CatalogRefused

    kit = _kit(spec, version)
    if catalog_id is None:
        offered = listing.entries(spec.challenge_id, version)
        item = offered[0] if offered else None
    else:
        item = listing.entry(catalog_id, spec.challenge_id, version)
        if item is None:
            raise CatalogRefused(
                "catalog_entry_unknown",
                f"{catalog_id!r} is not in this Challenge version's catalog",
            )
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {
            "kind": "catalog",
            "catalog_id": None if item is None else item["catalog_id"],
            "catalog_digest": served.digest(spec.challenge_id, version),
        },
        "procedure": {
            "entrypoint": None,
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {
            "format": None if item is None else item["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def graph_recipe(spec, submission_digest=None, *, version, training=None):
    """A graph recipe for Carbon's registered graph training adapter at
    `version`: the adapter's dataset, `train_fraction` 1.0 (its registered
    default) and `training` (empty: every surface keeps its registered
    default). Without `submission_digest` it is an unfilled template (None):
    the miner's graph, staged in their workspace, names it."""
    from carbon.development_session import physical_graph_adapter as adapter

    kit = _kit(spec, version)
    block = adapter.adapter_block(spec.challenge_id, version)
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": submission_digest},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": dict(training or {})},
            "train_use": {
                "dataset": block["train_use_dataset"],
                "train_fraction": block["train_fraction"]["default"],
            },
            "initial_state": None,
        },
        "output": {
            "format": block["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def describe(spec, version):
    """The direct version's description, from its registrations only."""
    from carbon.backbone_catalog import served
    from carbon.direct_campaign.spec import key_for
    from carbon.reconstruction.served_recipe_contract import registered

    key = key_for(spec, version)
    public = spec.public()
    interface = public.interface_document(key.challenge_id, key.version)
    limits = public.construction_limits_document(key.challenge_id, key.version)
    catalog = served.document(key.challenge_id, key.version)
    outputs = {name: [] for name in interface["output"]["names"]}
    return {
        "identity": "carbon." + spec.challenge_id + "-direct." + version,
        "contract_digest": registered(key.challenge_id, key.version).digest,
        "task": HUMAN_INPUT,
        "intended_use": HUMAN_INPUT,
        "interface": {
            "inputs": list(interface["input"]["names"]),
            "input_units": list(interface["input"]["units"]),
            "outputs": outputs,
            "output_units": list(interface["output"]["units"]),
            "dtype": interface["train_dtype"],
            "conventions": HUMAN_INPUT,
        },
        "public_material": {
            "names": [
                "objective",
                "capabilities",
                "training_data",
                "practice_data",
                "reference_method",
                "catalog",
                "construction_kit",
            ],
            "access": (
                "start_research_task kind=workspace action=public_material with "
                "arguments_json encoding one listed name"
            ),
            "train": {
                "cases": limits["train_cases"],
                "dtype": limits["train_dtype"],
                "sha256": public.construction_kit(key.challenge_id, key.version)[
                    "train_digest"
                ],
            },
            "practice": {"labels": HUMAN_INPUT, "adaptively_seen": True},
        },
        "models": {
            "rebuildable": [
                {
                    "id": "catalog." + catalog_id,
                    "selector": catalog_id,
                    "summary": "Carbon's tested " + entry["backbone"] + " bundle",
                }
                for catalog_id, entry in catalog["entries"].items()
            ],
            "catalog": catalog,
            "graph_training_adapter": limits["graph_training_adapter"],
            "note": (
                "Choose a backbone by catalog_id, or stage a graph for Carbon's "
                "graph training adapter."
                if catalog["entries"]
                else "No backbone is tested for this version yet: each entry "
                "needs its own pair-identity receipt, so the campaign refuses "
                "to start until one is added."
            ),
        },
        "execution": {
            "worker_image": "the campaign's verified C-03 PyTorch CPU worker image",
            "gpu_lane": False,
            "recipe": "carbon.construction-recipe.v1, source kind catalog or graph",
        },
        "workflow": {
            "practice": "Carbon rebuilds the recipe on public TRAIN as the receiver does",
            "freeze": "the campaign freezes one practised recipe",
            "submit": "the signed construction receiver rebuilds and judges it",
        },
        "exam": {
            "gates": HUMAN_INPUT,
            "components": HUMAN_INPUT,
            "rule": HUMAN_INPUT,
            "qualification": False,
        },
        "feedback": {
            # Validator, 2026-10-21: aggregate errors on the registered scale
            # (`direct_campaign.practice.error_scale`), no per-case value.
            "practice": "aggregate public-practice errors on the registered scale",
            "evaluation": "the receiver's judged feedback",
        },
        "examples": (
            [{"recipe": catalog_recipe(spec, version=version)}]
            if catalog["entries"]
            else []
        ),
        "unsupported": [
            {
                "id": "source.bundle",
                "status": "closed",
                "blocker": "miner source bundles stay closed",
                "summary": "A miner-authored source bundle is not served.",
            }
        ],
        "exclusion_scope": {
            "catalog": "Carbon's tested bundles only; miner source stays closed",
            "excluded": [
                "participant code or weights",
                "private or counted evidence",
            ],
        },
    }
