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

It is anchored so it can pass the initial-state and voltage-limit gates
(Test Lead and Validator, 2026-10-20; the unanchored scaffold failed them on
every PRACTICE case, so no edit of its training could score). Three fixed,
untrained pieces of public structure on the output, each from the case's own
inputs or a published protocol limit, never a reference or exam value:
T(0) = the input t_amb_c; V(0) = OCV(soc0) from the published OCV table (the
judge's own piecewise-linear curve, as relu hinges at a thinned set of the
table's knots, within 50 uV of it); every later voltage clamped into the
published [V_MIN, V_MAX] window, 5 uV inside. The direct adapter decodes
out * sd + mu over TRAIN, so the anchors are written in that normalized space
with the adapter's TRAIN statistics at train_fraction 1.0 (this recipe's).
Built by scripts/dev/battery_public_scaffold_build.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import construction_kit, direct_graph
from .scaffold import SCAFFOLD

ROOT = Path(__file__).with_name("public_scaffold")
#: The scaffold graph's submission digest (its manifest's sha256).
GRAPH_DIGEST = "sha256:b370bbfc6c300c56d390fb531adfc4e0f783fda26ef84b67c87dbd70e5824b36"
DOCUMENTS = {
    "forward": "sha256:2b834aa74b01a17623b36edff7a6f73f50b7e9f1d8e1e578e8fce92ef57847cc",
    "init_spec": "sha256:aabc059e6cb7ef8bd58521725a00c84f1392f51bcc7dcb285be52c7cd4a013c2",
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
