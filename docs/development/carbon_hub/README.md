# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 42 captured tickets across Wave A and Wave B
- 7 protocol-change routes
- 64 map-level change events
- 8 independent maturity states

## Captured current position

Wave **B**; current ticket: **B-E4**. Last completed: **B-E2** (`done`). Next selected: **none selected**. Wave B remains active in bounded development scope. B-E4 remains selected and in progress. PR #110 merged the frozen 25-block/100-run full-lifecycle calibration. The current candidate repairs policy-exhaustion and reserve integrity and records a conditional endpoint-headroom blocker. Deterministic zero-SD repeats, non-positive v2 contrasts, three global lineage roots, an 11.2928 percent failure-rate upper bound, and absent autonomous-agent and shadow evidence keep v4 STILL_BLOCKED. All eight inputs remain PROPOSED; no pilot, qualifying, shadow, or attack campaign ran; no later ticket is selected; and B-GATE remains unstarted.

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
