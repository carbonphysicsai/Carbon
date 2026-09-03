# Carbon Development Hub — scoped agent instructions

These instructions apply to every file under `docs/development/carbon_hub/`.
Repository-root `AGENTS.md`, `CONSTITUTION.md`, `.agent/INVARIANTS.md`, the
active wave register, and the selected ticket remain controlling authority.

## Read before changing the hub

1. `orientation/AGENT_MAINTENANCE_CONTRACT.md`;
2. current `.agent/WAVE.md` and its controlling wave board;
3. the affected ticket, decision, evidence, domain, business, or publication
   authority;
4. `data/hub_data_v2.json`, `data/change_events.json`, and `data/decisions.json`.

The hub explains what, why, where, status, dependency, and handoff. It cannot
activate a wave or ticket, change scientific meaning, grant maturity, or
substitute for repository code, review, decisions, tests, or evidence.

## Editable source

- `data/hub_data_v2.json`;
- `data/change_events.json`;
- `data/change_event_template.yaml`;
- `data/decisions.json` for the technical-lead Decision Console;
- `decisions.html` for the lightweight Decision Console presentation;
- `tools/render_hub.py` and `tools/templates/interactive_template.html` when
  changing presentation or generation behavior;
- `data/newcomer_projection_v1.json`, `data/newcomer_tickets_wave_a_v1.json`,
  and `data/newcomer_tickets_wave_b_v1.json` for newcomer-first Overview copy;
- `tools/render_newcomer.py` when changing newcomer presentation or generation
  behavior (imported by `tools/render_hub.py`; see
  `orientation/NEWCOMER_PRESENTATION_CONTRACT.md`);
- maintenance/orientation contracts and validation tools when their contract
  changes.

## Generated files — do not hand-edit

- `index.html`;
- `interactive.html`;
- `newcomer.html`;
- `technical.html`;
- `Carbon_Development_Hub_v2.md`;
- `README.md`;
- `data/hub_index_v2.yaml`;
- `orientation/START_HERE.md`;
- `orientation/CHANGE_ROUTING.md`;
- `orientation/GLOSSARY.md`;
- `explainers/waves/*.md`;
- `explainers/tickets/*.md`.

Run the renderer after editing the existing generated Hub source. Generated
outputs must be deterministic, UTF-8, LF-terminated, and committed with the
source change. `tools/render_hub.py` generates and checks `newcomer.html` and
`technical.html` in the same pass as the rest of the Hub (it imports
`tools/render_newcomer.py`); do not run `render_newcomer.py` in place of the
required `render_hub.py` commands below. A decision-only update to
`data/decisions.json` does not require regenerating the core Hub because
`decisions.html` reads that index directly.

## Stable placement and events

- Give each wave, ticket, route, event, and decision a stable unique ID.
- Give every event and decision exactly one primary `map_ref` and zero or more
  `affects`.
- Preserve prior events. A prospective correction uses `supersedes`; it does
  not rewrite history.
- Add an event only when team understanding, purpose, placement, status,
  dependency, boundary, maturity, material risk, evidence interpretation, or
  primary links change. Routine implementation detail belongs in the PR.
- Never invent a status, dependency, owner, reviewer, source link, decision,
  scientific value, qualification, or authority state. Mark unsupported
  information missing or future.

## Decision Console

When a material technical/SciML decision is posted to issue #42, create or
update its record in `data/decisions.json` in the same development change.
Every decision record must:

- use the exact repository decision ID;
- bind to one primary stable `WAVE-*` or `SYSTEM/*` `map_ref`;
- explain the question, why it matters, the agent recommendation, and the
  consequences of keeping or changing it;
- point to the exact durable GitHub response location and technical detail;
- use exactly one attention state: `NEEDS_REVIEW`, `HUMAN_REQUIRED`,
  `FOR_AWARENESS`, `OWNER_DEFERRED`, or `RESOLVED`.

Do not mark ordinary asynchronous visibility as `NEEDS_REVIEW` or
`HUMAN_REQUIRED`. Use those states only when the repository record supports the
need for Harsh's attention or a genuinely human-reserved decision. Harsh's
response remains durable in GitHub using `KEEP`, `CHANGE`, `BLOCKED`, or
`DEFER_TO_OWNER`; the Hub is the decision UX, not the authority record.

For a decision-only change, run the focused check:

```bash
python docs/development/carbon_hub/tools/test_decisions.py
```

## Prohibited content

Never place credentials, private keys, seed phrases, passwords, recovery
material, hidden-evaluation data, protected seeds or samples, private
operational data, or customer-confidential information in the hub. The hub is
designed to be safe for a public repository and possible public static hosting.

## Required checks

From repository root for normal Hub structural changes:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
git diff --check
```

For a focused Decision Console/data-only update, use:

```bash
python docs/development/carbon_hub/tools/test_decisions.py
git diff --check
```

The primary `index.html` must remain complete static semantic HTML with zero
scripts and no automatic remote resource. Failure of `interactive.html` or the
Decision Console must never remove access to the static hub. `newcomer.html`
(the newcomer-first Overview) must also remain complete static semantic HTML
with zero scripts; see `orientation/NEWCOMER_PRESENTATION_CONTRACT.md` for its
copy rules and data-binding requirements.
