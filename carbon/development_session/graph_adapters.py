"""The registered per-version graph training adapters the receiver can run.

Each adapter module declares the Challenge versions it serves (`SPECS`, by
(challenge id, version)) and its ids (`ADAPTER_IDS`), and builds the
`graph_training_adapter` block a served version's limits carry
(`adapter_block`). Callers find a version's adapter here, never by naming a
Challenge (OWNER-MODULAR-CHALLENGES-01). The synthetic 1.3 adapter keeps its
own path (`direct_graph_construction_worker`).

- `physical_graph_adapter` (v1): F08 1.4 and F02 2.3, byte for byte as the
  Validator approved them (2026-10-20);
- `physical_graph_adapter_v2`: every graph route v2 version, every Challenge
  (`version_registry`: `graph_adapter` "v2");
- `battery_graph_adapter`: Battery 2.2.

The version registry declares which adapter each version serves; a test holds
each module's `SPECS` equal to it.
"""

from __future__ import annotations


def modules() -> tuple:
    """Every registered adapter module: F08/F02's v1, graph route v2's, then
    Battery's."""
    from . import (
        battery_graph_adapter,
        physical_graph_adapter,
        physical_graph_adapter_v2,
    )

    return (physical_graph_adapter, physical_graph_adapter_v2, battery_graph_adapter)


def for_version(challenge_id: str, version: str):
    """The adapter module serving exactly (challenge_id, version), or None."""
    for module in modules():
        if (challenge_id, version) in module.SPECS:
            return module
    return None


def for_adapter(adapter_id: str):
    """The adapter module that registers `adapter_id`, or None."""
    for module in modules():
        if adapter_id in module.ADAPTER_IDS:
            return module
    return None


def graph_offered(challenge_id: str, version: str) -> bool:
    """Whether miners are told the version takes graph recipes: it has a
    registered adapter and that adapter offers it (`OFFERED`, where an
    adapter declares one; every served version otherwise)."""
    module = for_version(challenge_id, version)
    if module is None:
        return False
    offered = getattr(module, "OFFERED", None)
    return offered is None or (challenge_id, version) in offered or version in offered


def adapter_ids() -> frozenset:
    return frozenset().union(*(module.ADAPTER_IDS for module in modules()))


def registered_train_use(challenge_id: str, version: str) -> str | None:
    """The TRAIN use id a graph recipe on the version names at
    procedure.train_use.dataset, or None."""
    module = for_version(challenge_id, version)
    if module is None:
        return None
    return module.adapter_block(challenge_id, version)["train_use_dataset"]


# Graph route v2's names for the same lookups.
module_for = for_version
module_for_adapter = for_adapter
train_use = registered_train_use


def _v2():
    from . import physical_graph_adapter_v2

    return physical_graph_adapter_v2


def serves_graph(challenge_id: str, version: str) -> bool:
    return for_version(challenge_id, version) is not None


def adapter_block(challenge_id: str, version: str) -> dict:
    """The `graph_training_adapter` block of a served version's limits."""
    module = for_version(challenge_id, version)
    if module is None:
        raise ValueError("no graph training adapter for this version")
    return module.adapter_block(challenge_id, version)


def graph_recipe(
    challenge_id: str, version: str, submission_digest=None, *, configuration=None
):
    """A graph recipe for the version's graph training adapter: its kit, the
    adapter's TRAIN use at train_fraction 1.0 and `configuration` (empty: every
    surface keeps its registered default). Without `submission_digest` it is
    an unfilled template (None): the miner's graph, staged in their
    workspace, names it."""
    from carbon.challenge_kit import physical_material

    block = adapter_block(challenge_id, version)
    kit = physical_material.construction_kit(challenge_id, version)
    configuration = {"training": {}} if configuration is None else configuration
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": submission_digest},
        "procedure": {
            "entrypoint": None,
            "configuration": configuration,
            "train_use": {"dataset": block["train_use_dataset"], "train_fraction": 1.0},
            "initial_state": None,
        },
        "output": {
            "format": block["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def configuration_example(challenge_id: str, version: str) -> dict | None:
    """A graph route v2 configuration showing per-output loss weights and a
    two-member ensemble on a split of the outputs, or None where the version
    serves no v2 adapter (one output takes a one-member example)."""
    if module_for(challenge_id, version) is not _v2():
        return None
    width = adapter_block(challenge_id, version)["interface"]["output_shape"][0]
    half = max(1, width // 2)
    members = (
        [{"outputs": list(range(width))}]
        if width == 1
        else [
            {"outputs": list(range(half))},
            {"outputs": list(range(half, width)), "training": {"learning_rate": 0.001}},
        ]
    )
    return {
        "training": {"steps": 512, "loss": "mse", "optimizer_family": "adamw"},
        "output_weights": [1.0] * width,
        "ensemble": {"members": members},
    }


class GraphAdapterUnregistered(ValueError):
    """A version's limits carry no graph adapter block equal to its own."""


def practise(
    ledger,
    *,
    owner,
    parent,
    runner,
    recipe,
    binding,
    material,
    identity,
    inputs=None,
    expected_output_shape=None,
    measure_query=False,
    timing_optional=False,
):
    """Practise a graph recipe on the version's graph training adapter, one
    path for every Challenge: the limits must carry the adapter's exact block,
    the recipe is refused here by the adapter's own closed code before
    anything runs, then Carbon rebuilds and infers it in the isolated
    workers. `inputs` and `expected_output_shape` are the practice query
    (the material's development bank when omitted). Returns (result,
    backend)."""
    from .construction_recipe import graph_envelope_from_workspace
    from .direct_graph_construction_worker import reconstruct_and_infer_graph_public

    module = module_for(binding["challenge_id"], binding["challenge_version"])
    if module is None:
        raise GraphAdapterUnregistered("no graph training adapter for this version")
    spec = module.spec_for(binding["challenge_id"], binding["challenge_version"])
    limits = material["construction_limits_document"]
    if limits.get("graph_training_adapter") != module.adapter_block(
        spec.challenge_id, spec.version
    ):
        raise GraphAdapterUnregistered("graph adapter block differs")
    module.training_settings(recipe)
    envelope = graph_envelope_from_workspace(ledger, owner, recipe)
    result = reconstruct_and_infer_graph_public(
        ledger,
        owner=owner,
        identity=identity,
        image=parent,
        recipe=recipe,
        challenge_binding=dict(binding),
        limits_document=limits,
        source_envelope=envelope,
        train=material["train"],
        inputs=material["practice_inputs"] if inputs is None else inputs,
        expected_output_shape=(
            material["expected_output_shape"]
            if expected_output_shape is None
            else expected_output_shape
        ),
        allowlist_bytes=material["allowlist_bytes"],
        seed=0,
        measure_query=measure_query,
        timing_optional=timing_optional,
        runner=runner,
        adapter_id=spec.adapter_id,
    )
    return result, {"kind": "C03_DOCKER", "adapter": spec.adapter_id}
