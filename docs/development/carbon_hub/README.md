# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 72 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 147 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1-D4**. Last completed: **C-W1-D3** (`done`). Next selected: **none selected**. C-W1-D4 implements authenticated local miner research, real isolated practice, a bounded workspace and fresh final reconstruction/comparison. Focused engineering checks passed; required delivery acceptance and the finite real campaign remain pending. No campaign inference, provider charge, accepted winner or new network transaction has occurred. Historical testnet 567 exact row [[0, 65535]] remains ROW_VERIFIED; burn amounts, epoch effects and settlement remain unproven. AWS stays deferred and Hippius unverified. Website and Workbench work and spending are separate. No later ticket is selected. Distinct miner UID 1 finalized in the earlier setup; no identities were registered here. Synthetic controls are not results of the real agent. No subsequent activation or weight transaction is authorized. Subnet 567 creation finalized at block 8010852 in the earlier C-W1 DEVELOPMENT setup.

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
