# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 67 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 99 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-EP2**. Last completed: **C-EP1** (`done`). Next selected: **none selected**. C-EP1 is the last completed ticket after PR #143's accepted RUNTIME_FULL run and normal merge. C-EP2 alone is selected for bounded DEVELOPMENT measurement of that Variant-A fixture path and a detached, uncalibrated Variant-B replay; no later ticket is selected. The study recommends COLLECT MISSING INPUTS FIRST because physical reference cost, compatibility demand and B overhead remain unknown. C-03, C-08 and C-09 remain unselected and dependency-blocked; C-EA2 remains unselected and blocked on a real C1 path and eligible real archive profile. D6 canonical full/standard run 34518806217 remains the G2 evidence, and G2 is LOCALNET_READY only for the exact standard-profile disposable v445 localnet. No sharing, answers, real entropy/reference, public network, reward change, scientific/security qualification, production or LIVE authority is created.

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
