"""Battery's Level 4 development record, for the shared dispatch.

`development_rebuild` asks this module whether a construction carries a
Level 4 graph record and how to stage or build it. A Level 4 construction is
a graph-only submission (OWNER-LEVEL4-GRAPH-ONLY-01): its record names the
submission's digest and the allowlist it was admitted under. Compiling or
training a submitted graph runs Carbon's program over hostile data, which is
G5's profile; that waits for the security owner (D3). Until then every
rebuild of a Level 4 record fails closed as Carbon's environment, never the
candidate's: the staged program raises `ImportError`, and so does an
in-process build (LEVEL4-DEV-VARIANT-01).

Imports nothing beyond the standard library: the validator and daemon reach
this module, and must never reach the variant mechanism.
"""

from __future__ import annotations

import json

SCHEMA = "carbon.battery.level4-graph.v1"
CAPABILITY = "hybrid.composition_graphs"
#: Why every Level 4 rebuild stops today.
BLOCKED = "level4_requires_security_owner_g5_acceptance_d3"
REBUILD_LABEL = "rebuild: blocked until the security owner accepts the G5 profile (D3)"
STAGED = "level4-graph.json"


def graph_record(reconstruction):
    """A construction's Level 4 graph record, or None."""
    if not isinstance(reconstruction, dict):
        return None
    found = reconstruction.get(CAPABILITY)
    if isinstance(found, dict) and found.get("schema") == SCHEMA:
        return dict(found)
    return None


def is_graph(found):
    return isinstance(found, dict) and found.get("schema") == SCHEMA


def program(base):
    """The staged program for a Level 4 record: it refuses as Carbon's
    environment before anything is built (`base` is not run)."""
    del base
    return f"raise ImportError({BLOCKED!r})\n"


def staged(found):
    return {STAGED: json.dumps(found, sort_keys=True, separators=(",", ":")).encode()}


def build_in_process(recipe, found):
    del recipe, found
    raise ImportError(BLOCKED)
