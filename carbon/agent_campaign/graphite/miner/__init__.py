"""Graphite's miner edition: the Carbon agent a miner runs (OWNER-GRAPHITE-MINER-01).

One engine, two editions. The internal edition (`..provider`, `..phase3`) is
Carbon's testing agent and keeps its grants, Engy ladder, pods and next-level
store. This edition runs inside a miner's own Launchpad campaign, on the
miner's model, key, budget and compute, and uses none of them:

- `edition`: the published editions (`MINER_EDITIONS`). Each freezes its role
  prompts (Reader, Planner, Constructor) and tool manifests by digest; a
  published edition is never edited, and a campaign frozen under an edition
  this code does not hold is refused `graphite_edition_unknown` before any
  model call.
- `toolbox`: the `sdk` a role's research loop calls: the role's manifest gate,
  the per-stage workspace allowlist, the protected-material filter and the
  literature served as data, origin and UNCHECKED labels kept.
- `budget`: the research stages' share of the miner's provider ceilings
  (`StageLedger`), which stops a FULL campaign's research typed
  `research_share_reached` and never refuses a replayed call.
- `plan`: the miner plan (`carbon.graphite.miner-plan.v1`) and its checks.
- `driver`: `run(prepared)`, the RESEARCH / BUILD / FULL stages over the
  shared research loop, submitting through the campaign's own submit.

The literature modules (`pack`, `library`, `hunt`, `imports`, `focus`) are the
literature slice's; this package imports them only where a stage needs them.

Nothing here imports the internal edition's grant, pods, experiment,
delivery, triage, next-level or ladder modules, and nothing here reaches
hidden-test material, chain writes or weights.
"""

from __future__ import annotations

#: The edition a new Launchpad Graphite campaign freezes.
EDITION_ID = "carbon.graphite.miner-edition.v1"

__all__ = ["EDITION_ID"]
