# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 137 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1**. Last completed: **C-10** (`done`). Next selected: **none selected**. C-W1 DEVELOPMENT: the real agent evaluation's signed source completed the separately authorized all-burn testnet path. Subnet 567 activation finalized at 8017622, commitment at 8017643, reveal at 8017851 and exact row [[0, 65535]] at 8017916; the checked journal reached ROW_VERIFIED without resubmission. PR #194's zero-fee guard is merged. C-W1-REVEAL-01 repairs SDK tuple event decoding and provides bounded walletless rescan recovery for a previously missed reveal. Creation at 8010852 and distinct miner UID 1 registration remain historical setup evidence. The numerical result remains COMPLETE_UNRESOLVED; no score, accepted improvement, winner, miner payment, burn amount or epoch effect is inferred. No subsequent activation or weight transaction is authorized by the consumed approvals. AWS stays deferred, Hippius unverified and scientific/security/network/production qualification unearned. Official C-W1 and C-EA2 remain blocked. No later ticket is selected; the next proposed milestone is a non-paying DEVELOPMENT comparison bridge with prospective rules and C-10 quarantine. Earlier deterministic engineering scaffold measurements are not results of the real agent.

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
