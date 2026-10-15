"""Agent selection under the controller's immutable construction contract.

The model supplies a recipe, never a binding or host path. Graph documents
come from its own flat workspace and pass the existing freeze checks.
"""

from __future__ import annotations

import json
import re
import tempfile

from . import construction_level as cl
from .profile import canonical, digest


def campaign_binding(ledger, owner):
    """Read the frozen ledger, rather than the model's observation or arguments."""
    with ledger.db() as db:
        row = db.execute("SELECT manifest,digest FROM campaign WHERE id=1").fetchone()
    if row is None:
        raise ValueError("a frozen campaign is required for agent selection")
    manifest = json.loads(row[0])
    if manifest.get("owner") != owner or digest(canonical(manifest)) != row[1]:
        raise ValueError("agent selection campaign binding differs")
    if cl.MANIFEST_KEY not in manifest:
        return None
    found = manifest[cl.MANIFEST_KEY]
    if (
        type(found) is not dict
        or not {"challenge", "variant", "digest", "scope", "level"} <= set(found)
        or found.get("challenge") != (manifest.get("challenge") or {}).get("id")
    ):
        raise ValueError("agent selection construction binding is malformed")
    return found


def observation(found):
    """Public construction context; descriptive levels never require their use."""
    from carbon.level4 import staging

    return {
        "digest": found["digest"],
        "variant": found["variant"],
        "scope": found["scope"],
        "kind": found.get("kind", "variant"),
        "basis": (
            "Every selected recipe is compiled and frozen under this immutable "
            "contract. Levels describe actual recipe changes, not permissions. "
            "A base recipe within this contract remains admissible."
        ),
        "graph_documents": {
            "when": "Only when the recipe uses parameters.composition_graphs",
            "manifest": staging.WORKSPACE_MANIFEST,
            "documents": staging.WORKSPACE_PREFIX + "<document sha256 hex>.json",
            "basis": (
                "Put the lowered manifest and documents in your own workspace. "
                "The manifest's digest must equal composition_graphs. Existing "
                "compiler, envelope, interface and resource checks still apply."
            ),
        },
    }


def candidate(ledger, owner, found, strategy, reason, used_feedback):
    """Return a compiled contract-bound record and its validated envelope."""
    from carbon.level4 import graph, staging

    from .research_workspace import ResearchWorkspace

    parameters = strategy.get("parameters") if type(strategy) is dict else None
    if type(parameters) is not dict or "composition_graphs" not in parameters:
        compiled, envelope = cl.check_freeze(found, strategy)
    else:
        # No model-authored host path. Only flat, content-addressed workspace
        # documents enter a private temporary directory for the existing check.
        workspace = ResearchWorkspace(ledger, owner)
        try:
            raw_manifest = workspace.get(staging.WORKSPACE_MANIFEST)
            document = json.loads(raw_manifest)
            names = document["documents"]
            if type(names) is not dict or not set(names) <= {
                "forward",
                "loss",
                "init",
                "init_spec",
            }:
                raise ValueError("graph document names are malformed")
            files = {}
            for name in names.values():
                if type(name) is not str or not re.fullmatch(
                    "sha256:[0-9a-f]{64}", name
                ):
                    raise ValueError("graph document identity is malformed")
                files[name] = workspace.get(
                    staging.WORKSPACE_PREFIX + name[7:] + ".json"
                )
            if staging.check(raw_manifest, files) != parameters["composition_graphs"]:
                raise ValueError("graph submission differs from the selected recipe")
        except (ValueError, KeyError, TypeError, OSError, graph.GraphRefused):
            raise cl.LevelRefused("level4_submission_refused") from None
        with tempfile.TemporaryDirectory(
            prefix="agent-graph-", dir=ledger.root
        ) as path:
            staging.write_directory(path, raw_manifest, files)
            compiled, envelope = cl.check_freeze(found, strategy, path)
    return (
        cl.candidate_record(found, strategy, reason, used_feedback, compiled),
        envelope,
    )
