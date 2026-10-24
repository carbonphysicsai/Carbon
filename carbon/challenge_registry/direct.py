"""Discovery for the direct-recipe-only versions: F08 (Ribbed Bracket) 1.4,
F02 (Burst Thermal) 2.3 and Battery 2.2.

A description names the registered interface, construction kit, served backbone
catalog and graph training adapter (each from its registered source), and a
ready catalog recipe and graph recipe template. The task wording, intended use
and interface conventions are the owner-approved facts
(`direct_campaign.facts`); what neither states - the exam, the per-case policy -
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
    """A graph recipe for the version's registered graph training adapter
    (`graph_adapters`) at `version`: the adapter's TRAIN use with its
    registered defaults and `training` (empty: every surface keeps its
    registered default). Without `submission_digest` it is an unfilled
    template (None): the miner's graph, staged in their workspace, names it.
    A graph route v2 version's template is its adapter v2's
    (`graph_adapters.graph_recipe`)."""
    from carbon.challenge_kit import version_registry
    from carbon.development_session.graph_adapters import for_version

    if version_registry.entry(spec.challenge_id, version).graph_adapter == "v2":
        from carbon.development_session import graph_adapters

        return graph_adapters.graph_recipe(
            spec.challenge_id,
            version,
            submission_digest,
            configuration={"training": dict(training or {})},
        )

    kit = _kit(spec, version)
    block = for_version(spec.challenge_id, version).adapter_block(
        spec.challenge_id, version
    )
    # Battery's adapter states its whole TRAIN use default; F08/F02's state
    # their dataset and train_fraction surface.
    train_use = block.get("train_use_default") or {
        "dataset": block["train_use_dataset"],
        "train_fraction": block["train_fraction"]["default"],
    }
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": submission_digest},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": dict(training or {})},
            "train_use": dict(train_use),
            "initial_state": None,
        },
        "output": {
            "format": block["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def _empty_catalog_note(adapter):
    """What a version with no catalog entry yet says, in plain words."""
    waiting = (
        "No backbone is installable yet: each catalog entry arrives after its "
        "own pair-identity check."
    )
    if adapter is not None:
        return (
            waiting + " Meanwhile, practise your own graph: stage it in your "
            "workspace and name its digest in graph_recipe_template's "
            "source.submission_digest."
        )
    return waiting + " Until one is added, the campaign refuses to start."


#: What a version's catalog example is (Validator, 2026-10-23: no card may
#: imply a catalog default grades valid; F02 2.3's FullyConnected default
#: fails verified_pick in practice and grades CANDIDATE_INVALID).
EXAMPLE_NOTE = (
    "The example is a catalog backbone at its tested default settings: a "
    "starting point to practise and tune, not a recipe tested to pass this "
    "Challenge's gates. Its practice result says whether it is eligible."
)


def _practice_labels(challenge_id, version):
    """The practice labels' miner-facing text: "not yet registered" where the
    Validator published this version's exam (never `HUMAN_INPUT`, ruling §3);
    the value itself stays unset internally."""
    from carbon.challenge_registry import published_exam

    if published_exam.for_version(challenge_id, version) is None:
        return HUMAN_INPUT
    return published_exam.NOT_REGISTERED


def _exam(challenge_id, version):
    """The exam block: from the published block where the Validator's
    exam-safety ruling published this version's gates and score
    (OWNER-PUBLISH-WHAT-IS-TESTED-01), otherwise `HUMAN_INPUT`."""
    from carbon.challenge_registry import published_exam

    published = published_exam.for_version(challenge_id, version)
    if published is None:
        return {
            "gates": HUMAN_INPUT,
            "components": HUMAN_INPUT,
            "rule": HUMAN_INPUT,
            "qualification": False,
        }
    return {
        "gates": [gate["id"] for gate in published["gates"]],
        "components": [leg["id"] for leg in published["score"]["legs"]],
        "rule": published["score"]["formula"],
        "qualification": False,
    }


def describe(spec, version):
    """The direct version's description, from its registrations only."""
    from carbon.backbone_catalog import served
    from carbon.direct_campaign import facts
    from carbon.direct_campaign.contracts import train_facts
    from carbon.direct_campaign.spec import key_for, keyed
    from carbon.reconstruction.served_recipe_contract import registered

    key = key_for(spec, version)
    public = spec.public()
    interface = public.interface_document(key.challenge_id, key.version)
    limits = public.construction_limits_document(key.challenge_id, key.version)
    with keyed(spec, key):
        train = train_facts(spec)
    catalog = served.document(key.challenge_id, key.version)
    # The graph route as miners are told about it: the limits' adapter block,
    # where the version's graph route is offered (`graph_adapters.graph_offered`;
    # Battery 2.2's waits on its graph screen, so it reads catalog-only).
    from carbon.development_session.graph_adapters import graph_offered

    adapter = (
        limits.get("graph_training_adapter")
        if graph_offered(spec.challenge_id, key.version)
        else None
    )
    outputs = {name: [] for name in interface["output"]["names"]}
    return {
        "identity": "carbon." + spec.challenge_id + "-direct." + version,
        "contract_digest": registered(key.challenge_id, key.version).digest,
        "task": facts.value(spec, key.version, "task"),
        "intended_use": facts.value(spec, key.version, "intended_use"),
        "interface": {
            "inputs": list(interface["input"]["names"]),
            "input_units": list(interface["input"]["units"]),
            "outputs": outputs,
            "output_units": list(interface["output"]["units"]),
            "dtype": interface["train_dtype"],
            "conventions": facts.value(spec, key.version, "interface_conventions"),
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
                "scaffold_recipe",
            ],
            "access": (
                "start_research_task kind=workspace action=public_material with "
                "arguments_json encoding one listed name"
            ),
            "train": {
                "cases": train["train_cases"],
                "dtype": train["train_dtype"],
                "sha256": public.construction_kit(key.challenge_id, key.version)[
                    "train_digest"
                ],
            },
            "practice": {
                "labels": _practice_labels(spec.challenge_id, version),
                "adaptively_seen": True,
            },
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
            "graph_training_adapter": adapter,
            "note": (
                (
                    "Choose a backbone by catalog_id, or stage a graph for "
                    "Carbon's graph training adapter."
                    if adapter is not None
                    else "Choose a backbone by catalog_id."
                )
                if catalog["entries"]
                else _empty_catalog_note(adapter)
            ),
        },
        "execution": {
            "worker_image": "the campaign's verified C-03 PyTorch CPU worker image",
            "gpu_lane": False,
            "recipe": (
                "carbon.construction-recipe.v1, source kind catalog or graph"
                if adapter is not None
                else "carbon.construction-recipe.v1, source kind catalog"
            ),
        },
        "workflow": {
            "practice": "Carbon rebuilds the recipe on public TRAIN as the receiver does",
            "freeze": "the campaign freezes one practised recipe",
            "submit": "the signed construction receiver rebuilds and judges it",
        },
        "exam": _exam(spec.challenge_id, version),
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
        # Never an empty list with no reason (round 8b): why there is no ready
        # recipe yet, and what this version can already practise; with
        # entries, what the example is, never a claim that it grades valid.
        "examples_note": (
            EXAMPLE_NOTE if catalog["entries"] else _empty_catalog_note(adapter)
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
