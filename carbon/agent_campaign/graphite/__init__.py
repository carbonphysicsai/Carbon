"""Graphite: Carbon's in-house research and testing agent (GRAPHITE-01).

OWNER-GRAPHITE-01 (2026-10-02). Internal development tooling under
OWNER-CHALLENGE-ADMISSION-01: never mainnet, never shown to miners, not a
qualification gate, no evaluator authority. **Graphite proposes; Carbon's
verifier decides.**

Phase 1 is the harness; phase 2 adds the literature layer. Nothing is sent to
a live model, and nothing is spent, without an owner spending grant; the tests
drive everything with a scripted model.

- `roles`: the six roles (Planner, Constructor, Attacker, Optimizer
  researcher, Reader, Writer), each a frozen record with its prompt (by
  digest), a closed tool manifest and a starting rung on the owner's Engy
  ladder.
- `ladder`: the escalation rule. One rung, only on a recorded typed research
  failure; never a skipped rung; never above the top.
- `literature`: `lit.search` / `lit.card` over a small synthetic fixture
  index. Card content is returned as data.
- `tools`: the role's closed toolbox. Calls outside the manifest, and requests
  that name confirmation or official material, are refused with a typed
  refusal; nothing a tool returns changes a role, tool, budget or authority.
- `model`: the injected model access. `ScriptedModel` replays a script;
  `LiveModel` refuses to exist without an owner spending grant.
- `literature_fetch`, `method_cards`, `triage`, `phase2` (phase 2): the arXiv
  fetch for a registered query set, the Reader's method-card extraction
  under a grant, human checks, deterministic snapshots that `literature`
  serves, and the runner (`python -m carbon.agent_campaign.graphite.phase2`).
- `provider`: `GraphiteProvider`, a second provider behind the #475 campaign
  controller. It drives the existing research loop
  (`carbon.development_session.research_loop`) with metering, replay and
  typed failures from `research_agent`, and keeps a deterministic session
  record per run.
"""

from .ladder import Ladder, LadderError
from .literature import FIXTURE_INDEX, LiteratureIndex
from .model import LiveModel, ScriptedModel
from .provider import PROVIDER, GraphiteProvider, SessionBrief
from .roles import ROLES, GraphiteRole

__all__ = [
    "FIXTURE_INDEX",
    "PROVIDER",
    "ROLES",
    "GraphiteProvider",
    "GraphiteRole",
    "Ladder",
    "LadderError",
    "LiteratureIndex",
    "LiveModel",
    "ScriptedModel",
    "SessionBrief",
]
