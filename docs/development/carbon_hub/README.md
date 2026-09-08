# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 42 captured tickets across Wave A and Wave B
- 7 protocol-change routes
- 66 map-level change events
- 8 independent maturity states

## Captured current position

Wave **B**; current ticket: **B-E4**. Last completed: **B-E2** (`done`). Next selected: **none selected**. Wave B remains active in bounded development scope. B-E4 remains selected and in progress. PR #112 merged historical pilot v1. The current correction candidate pre-binds genuine failure evidence to one campaign/run/session, enforces one-use replacement, records predicted/reserved/confirmed/unreconciled resources prospectively, and proposes strict pilot v2. Pilot v2 keeps one common Terra model across five policies, defines 12 prospective task cells, 40 development plus 240 calibration runs and 20 reserves, and retains the $98.304 hard ceiling. Its five grouped decisions remain PROPOSED; it has no provider adapter, approval, execution authorization, or run evidence, and no inference, pilot, qualifying, shadow, or attack campaign ran. V4 remains STILL_BLOCKED; no later ticket is selected and B-GATE remains unstarted.

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
