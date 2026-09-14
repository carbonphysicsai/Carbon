# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 123 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-EA1**. Last completed: **C-10** (`done`). Next selected: **none selected**. PR #173 accepted exact C-10 head 82073ae2d5cc8504b7e77a9824642f98f0827526 in run 34882900413 and normally merged as d7ef7270eeb3b9a5594704efe0876ff3fb5ded49. C-EA1-D3 alone is selected for an unprovisioned AWS private-alpha package over the accepted PR #168 policy: exact provider adapters, immutable version receipts, atomic retained-byte capacity, private infrastructure/roles, recovery procedure and priced decision support. No later ticket is selected. Actual account/network/principals, provisioning, recovery rehearsal, security acceptance and deployment authorization remain absent. No real acknowledgement, C-EA2, protected execution, public network or LIVE authority exists. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
