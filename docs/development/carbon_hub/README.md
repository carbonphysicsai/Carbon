# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 73 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 174 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **none active**. Last completed: **C-W1-D5** (`done`). Next selected: **none selected**. C-W1-D5 is complete in its bounded engineering scope. No ticket is currently active. PR #208 delivered autonomous research instructions and structured stops. All three authorized campaigns ended: one training trial and six final replicas, no admissible final model or accepted improvement. The final campaign stopped before training with resources remaining. Program totals: 15 provider calls, USD 0.01951925 usage-priced cost, 1339.179 numerical seconds, two rejected trial attempts and 288 reference calculations. No unresolved reservations remain. No research successor is selected; unused budget does not renew the program. Historical testnet 567 publication remains ROW_VERIFIED, exact row [[0, 65535]]; burn amounts, epoch effects and settlement remain unproven. No subsequent activation or weight transaction is authorized. C-MLP browser validation remains separate. AWS stays deferred; unrelated website and Workbench work/spending remain separate. Synthetic incentive scenarios are not results of the real agent. C-W1 DEVELOPMENT retains historical Subnet 567 creation at block 8010852. Hippius unverified; its provider integration remains deferred.

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
