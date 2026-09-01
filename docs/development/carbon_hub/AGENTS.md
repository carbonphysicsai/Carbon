# Carbon Development Hub — scoped agent instructions

These instructions apply to every file under `docs/development/carbon_hub/`.
Repository-root `AGENTS.md`, `CONSTITUTION.md`, `.agent/INVARIANTS.md`, the
active wave register, and the selected ticket remain controlling authority.

## Read before changing the hub

1. `orientation/AGENT_MAINTENANCE_CONTRACT.md`;
2. current `.agent/WAVE.md` and its controlling wave board;
3. the affected ticket, decision, evidence, domain, business, or publication
   authority;
4. `data/hub_data_v2.json` and `data/change_events.json`.

The hub explains what, why, where, status, dependency, and handoff. It cannot
activate a wave or ticket, change scientific meaning, grant maturity, or
substitute for repository code, review, decisions, tests, or evidence.

## Editable source

- `data/hub_data_v2.json`;
- `data/change_events.json`;
- `data/change_event_template.yaml`;
- `tools/render_hub.py` and `tools/templates/interactive_template.html` when
  changing presentation or generation behavior;
- maintenance/orientation contracts and validation tools when their contract
  changes.

## Generated files — do not hand-edit

- `index.html`;
- `interactive.html`;
- `Carbon_Development_Hub_v2.md`;
- `README.md`;
- `data/hub_index_v2.yaml`;
- `orientation/START_HERE.md`;
- `orientation/CHANGE_ROUTING.md`;
- `orientation/GLOSSARY.md`;
- `explainers/waves/*.md`;
- `explainers/tickets/*.md`.

Run the renderer after editing source. Generated outputs must be deterministic,
UTF-8, LF-terminated, and committed with the source change.

## Stable placement and events

- Give each wave, ticket, route, and event a stable unique ID.
- Give every event exactly one primary `map_ref` and zero or more `affects`.
- Preserve prior events. A prospective correction uses `supersedes`; it does
  not rewrite history.
- Add an event only when team understanding, purpose, placement, status,
  dependency, boundary, maturity, material risk, evidence interpretation, or
  primary links change. Routine implementation detail belongs in the PR.
- Never invent a status, dependency, owner, reviewer, source link, decision,
  scientific value, qualification, or authority state. Mark unsupported
  information missing or future.

## Prohibited content

Never place credentials, private keys, seed phrases, passwords, recovery
material, hidden-evaluation data, protected seeds or samples, private
operational data, or customer-confidential information in the hub. The hub is
designed to be safe for a public repository and possible public static hosting.

## Required checks

From repository root:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
git diff --check
```

The primary `index.html` must remain complete static semantic HTML with zero
scripts and no automatic remote resource. Failure of `interactive.html` must
never remove access to the static hub.
