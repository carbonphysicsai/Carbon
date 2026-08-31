# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

Open **`index.html`** first. It contains the complete core hub as semantic HTML, has no script element or automatic remote resource, and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 39 captured Wave A/B tickets
- 7 protocol-change routes
- 3 map-level change events
- 8 independent maturity states

## Captured current position

Wave **B**, ticket **B-03** (`in_progress`). The working engineering contract merged in PR #67 and exact-main CI passed; runtime implementation remains selected and had not started in the captured repository state.

## Maintain

Read `orientation/AGENT_MAINTENANCE_CONTRACT.md`. Semantic map updates use
`data/hub_data_v2.json` and `data/change_events.json`; the event template,
renderer, and interactive template are maintained sources for their respective
schema or presentation behavior. Never hand-edit generated outputs. Then run:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
```

The hub explains and routes; repository authority controls implementation and evidence. GitHub Pages is owner-controlled and public when enabled.
