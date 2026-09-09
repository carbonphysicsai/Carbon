# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 43 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 73 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **NET-1**. Last completed: **B-GATE** (`done`). Next selected: **none selected**. Wave C/C0 has NET-1 selected as its one active ticket. OWNER-C0-REWARD-01 authorizes sequential implementation through NET-6, with C-REWARD after NET-3 and before intent/publication consumers. The complete default is direct winner plus burn with treasury absent. NET-0 is a development boundary disposition; actual localnet and later ticket implementations remain unverified/unstarted. C1/C2 scientific/evidence requirements remain intact. B-01G remains unfinished/non-blocking. B-E4 remains OPTIONAL / DEFERRED / NON-BLOCKING and empirical prior effectiveness UNMEASURED. No later ticket is selected.

## Maintain

Read `orientation/AGENT_MAINTENANCE_CONTRACT.md`. Semantic map updates use
`data/hub_data_v2.json` and `data/change_events.json`; the event template,
renderer, and interactive template are maintained sources for their respective
schema or presentation behavior. Never hand-edit generated outputs. Then run:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/test_newcomer.py
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
```

The hub explains and routes; repository authority controls implementation and evidence. Manual Pages publication is available to authorized maintainers, but the workflow does not itself enforce owner approval. A required reviewer on the `github-pages` environment, if desired, is a separate human-controlled repository setting. Pages is public when enabled; this integration does not enable it or change settings.
