# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 71 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 142 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1-D3**. Last completed: **C-W1-D2** (`done`). Next selected: **none selected**. C-W1-D3 implements balanced-v2 DEVELOPMENT acceptance and non-paying reward simulation. Two bounded design iterations and analytic verification completed; retained FNO results are retrospective diagnostic ranks and fail mandatory conditions. No fresh training, model charge, real winner, payment or public-network transaction. Required CI and normal merge close engineering only. Historical testnet 567 exact row [[0, 65535]] remains ROW_VERIFIED; burn amounts, epoch effects, miner payment and settlement remain unproven. Distinct miner UID 1 finalized in the earlier setup; no identities were registered here. No later ticket is selected. Synthetic controls are not results of the real agent. No subsequent activation or weight transaction is authorized. Subnet 567 creation finalized at block 8010852 in the earlier C-W1 DEVELOPMENT setup. AWS stays deferred; Hippius unverified. Owner-approved bounded DEVELOPMENT CI retains all invariants and affected subsystem, package, quality and Hub acceptance; official/shared runtime changes still require full regression.

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
