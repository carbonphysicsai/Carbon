"""Battery's published scaffold as a ready direct recipe to edit.

Every new Launchpad campaign is direct, so practice takes a construction
recipe; an agent that cannot lower a graph could not practise at all
(BUG_GRAPHITE_PRACTICE_CALL_REFUSED_20261020). This serves only what is
already public (Test Lead, and the Validator's option A, 2026-10-20): the
published scaffold (`scaffold.SCAFFOLD`: mlp, width 64, depth 3, 2000 steps)
lowered against the direct graph interface, and a recipe whose training block
names only the scaffold's own published field. Never Carbon's leg-minimum,
agent-tested or retained recipes.

The graph is Carbon's own lowering (`unit(x)` to the published input bounds,
dense [4, 64, 64, 64, 247] with gelu), traced at the registered default batch
(400, full batch) under the graph path's allowlist v1, and kept here as bytes
pinned by their digests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import construction_kit, direct_graph
from .scaffold import SCAFFOLD

ROOT = Path(__file__).with_name("public_scaffold")
#: The scaffold graph's submission digest (its manifest's sha256).
GRAPH_DIGEST = "sha256:c3ff680d66501fa9fab2a0b2d9c5f5aee2199aa4155a070d7d96af737b5e64d6"
DOCUMENTS = {
    "forward": "sha256:ee5beeff6ed6116fe3332861c297c9b6dbcf37c7e948c902428914fb23279fe1",
    "init_spec": "sha256:c917c2e43b1933e5943c4e2e26bac24d39629ea7f9199b30bc2cc7e267ac0d21",
}


def _pinned(name: str, expected: str) -> bytes:
    raw = (ROOT / name).read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("published scaffold graph bytes differ")
    return raw


def graph() -> tuple[bytes, dict[str, bytes]]:
    """The scaffold graph's manifest bytes and its digest-named documents."""
    manifest = _pinned("manifest.json", GRAPH_DIGEST)
    if json.loads(manifest).get("documents") != DOCUMENTS:
        raise ValueError("published scaffold graph manifest differs")
    files = {d: _pinned(d[7:] + ".json", d) for d in DOCUMENTS.values()}
    return manifest, files


def recipe() -> dict:
    """The ready direct recipe: the kit, the scaffold graph, and a training
    block naming only the scaffold's published steps (everything else at the
    registered defaults)."""
    kit = construction_kit.construction_kit()
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": GRAPH_DIGEST},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": {"steps": SCAFFOLD["parameters"]["steps"]}},
            "train_use": {
                "dataset": direct_graph.TRAIN_USE,
                "train_fraction": 1.0,
                "curriculum": "none",
            },
            "initial_state": None,
        },
        "output": {
            "format": direct_graph.OUTPUT_FORMAT,
            "interface_digest": kit["interface_digest"],
        },
    }
