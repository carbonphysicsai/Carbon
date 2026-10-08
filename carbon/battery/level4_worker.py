"""Battery's Level 4 development record, for the shared dispatch.

`development_rebuild` asks this module whether a construction carries a
Level 4 graph record and how to stage or build it. A Level 4 construction is
a graph-only submission (OWNER-LEVEL4-GRAPH-ONLY-01): its record names the
submission's digest and the allowlist it was admitted under. G5's profile,
compiling a checked graph in the C-03 lane, is accepted for development and
testnet (OWNER-L4-G5-COMPILE-ISOLATION-01). What still stops a rebuild is
the transport: the record names only the submission's digest, and no path
yet stages the submission's documents into the rebuild worker. Until one
does, every rebuild of a Level 4 record fails closed as Carbon's
environment, never the candidate's: the staged program raises
`ImportError`, and so does an in-process build (LEVEL4-DEV-VARIANT-01).

Imports nothing beyond the standard library: the validator and daemon reach
this module, and must never reach the variant mechanism.
"""

from __future__ import annotations

import json

SCHEMA = "carbon.battery.level4-graph.v1"
CAPABILITY = "hybrid.composition_graphs"
#: Why every Level 4 rebuild stops today.
BLOCKED = "level4_submission_documents_not_staged"
REBUILD_LABEL = (
    "rebuild: blocked until the submission's documents reach the rebuild "
    "worker; G5 accepted for development and testnet only"
)
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


_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'


def program(base):
    """`base` (a Level-0 program) with its one build line replaced by a raise
    of `ImportError(BLOCKED)`, at the same indent, so it lands inside the
    program's `try:` and its `except ImportError` records the failure as
    Carbon's environment (`failure.json`, stage `environment`), typed and
    never retried as an unexplained infrastructure fault."""
    for indent in ("    ", ""):
        line = indent + _BUILD
        if base.count(line) == 1:
            return base.replace(line, f"{indent}raise ImportError({BLOCKED!r})\n")
    raise RuntimeError("the program's build line moved")


def staged(found):
    return {STAGED: json.dumps(found, sort_keys=True, separators=(",", ":")).encode()}


def build_in_process(recipe, found):
    del recipe, found
    raise ImportError(BLOCKED)
