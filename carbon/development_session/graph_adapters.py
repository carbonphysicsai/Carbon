"""The registered per-version graph training adapters the receiver can run.

Each adapter module declares the Challenge versions it serves (`SPECS`, by
(challenge id, version)) and its ids (`ADAPTER_IDS`), and builds the
`graph_training_adapter` block a served version's limits carry
(`adapter_block`). Callers find a version's adapter here, never by naming a
Challenge (OWNER-MODULAR-CHALLENGES-01). The synthetic 1.3 adapter keeps its
own path (`direct_graph_construction_worker`).
"""

from __future__ import annotations


def modules() -> tuple:
    """Every registered adapter module: F08/F02's, then Battery's."""
    from . import battery_graph_adapter, physical_graph_adapter

    return (physical_graph_adapter, battery_graph_adapter)


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


def adapter_ids() -> frozenset:
    return frozenset().union(*(module.ADAPTER_IDS for module in modules()))


def registered_train_use(challenge_id: str, version: str) -> str | None:
    """The TRAIN use id a graph recipe on the version names at
    procedure.train_use.dataset, or None."""
    module = for_version(challenge_id, version)
    if module is None:
        return None
    return module.adapter_block(challenge_id, version)["train_use_dataset"]
