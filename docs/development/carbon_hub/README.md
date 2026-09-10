# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 50 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 83 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **none active**. Last completed: **NET-6** (`done`). Next selected: **none selected**. NET-1 through NET-6 and C-REWARD are merged in bounded engineering scope. Actual all-burn and operator recovery work with treasury absent. Required shielded miner registration and shared-winner/recycled-UID runtime proof remain unresolved; G2 is NOT_READY. NET-6 is the last completed ticket (PR #127). No implementation ticket is currently active. No later ticket is selected. C-01 and C-W1 preserve the concrete C1/C2/archive handoff. B-E4 remains OPTIONAL / DEFERRED / NON-BLOCKING and effectiveness UNMEASURED; B-01G remains unfinished/non-blocking.

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
