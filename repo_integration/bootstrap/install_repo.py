#!/usr/bin/env python3
"""Apply one-time root policy links for the Carbon Development Hub."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AGENTS_MARKER = "# Carbon Development Hub maintenance"
AGENTS_SECTION = r'''

---

# Carbon Development Hub maintenance

`docs/development_hub/` is Carbon's required orientation and protocol-change map. It explains what, why, where, status, and dependency. Repository authority still controls how, exact semantics, implementation, review, evidence, and maturity.

For every ticket or material repository change:

1. locate the work's primary hub `map_ref` at ticket start;
2. compare the hub with `.agent/WAVE.md`, the active board, ticket, and owning specifications;
3. update map-visible state, dependencies, ownership, boundaries, routing, and primary links in the same pull request when they change;
4. append or supersede a concise change event for a material decision, adjustment, bug, blocker, risk, or evidence change;
5. include exactly one pull-request declaration: `HUB_UPDATE_REQUIRED: ...` or `HUB_IMPACT_NONE: ...`;
6. run the renderer and hub checks before merge.

A wave, ticket, Build Out, or master-plan structural change cannot use `HUB_IMPACT_NONE`. Follow `.agent/HUB_MAINTENANCE_POLICY.md` and the scoped `docs/development_hub/AGENTS.md`. Never place secrets or unearned maturity claims in the hub.
'''

EXEC_MARKER = "## Development Hub maintenance"
EXEC_SECTION = r'''

---

## Development Hub maintenance

At ticket start, locate the primary `map_ref` in `docs/development_hub/` and compare the orientation summary with the current wave board, active ticket, and owning specifications.

Before merge, the pull request must contain exactly one completed declaration:

```text
HUB_UPDATE_REQUIRED: <map refs and changed hub source paths>
```

or

```text
HUB_IMPACT_NONE: <specific reason purpose, placement, status, dependencies, boundaries, maturity, and primary links remain accurate>
```

When the hub changes, update its JSON sources, append or supersede the map-level event, regenerate outputs, and run the checks in `.agent/HUB_MAINTENANCE_POLICY.md`. Hub maintenance is documentation closeout. It does not grant protocol or qualification authority.
'''

DECISION_MARKER = "O-HUB-01"
DECISION_SECTION = r'''

## 2026-08-31 — O-HUB-01: Carbon Development Hub and mandatory maintenance loop

**Status:** OWNER-DIRECTED PROCESS DECISION.

**Decision.** Carbon maintains `docs/development_hub/` as the team's non-repository-facing orientation and protocol-change navigation layer. It explains what Carbon is building, why each wave and ticket exists, where a change belongs, current status and dependencies, and the repository record that owns detail. Every relevant pull request must classify its hub impact. Map-visible changes and material events update the hub in the same pull request.

**Reason.** New hires and active leads need one readable map before entering detailed tickets, decisions, pull requests, and evidence. The map also gives new Challenges, model architectures, miner priors, bugs, and protocol adjustments a consistent attachment point.

**Authority boundary.** The hub does not activate a wave or ticket, define scientific truth, approve security, change economics, qualify a system, or create production authority. The Constitution, domain specifications, active board, ticket, decisions, code, review, and evidence remain authoritative.

**Implementation.** `.agent/HUB_MAINTENANCE_POLICY.md`, root `AGENTS.md`, `agent_pack/EXECUTION_PROTOCOL.md`, the pull-request template, and the Development Hub CI check define and enforce the maintenance loop.
'''


def append_once(path: Path, marker: str, section: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + section + "\n", encoding="utf-8")


def main() -> None:
    append_once(ROOT / "AGENTS.md", AGENTS_MARKER, AGENTS_SECTION)
    append_once(ROOT / "agent_pack" / "EXECUTION_PROTOCOL.md", EXEC_MARKER, EXEC_SECTION)
    append_once(ROOT / ".agent" / "DECISIONS.md", DECISION_MARKER, DECISION_SECTION)
    print("Applied Development Hub policy links and owner decision record.")


if __name__ == "__main__":
    main()
