# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 130 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1**. Last completed: **C-10** (`done`). Next selected: **none selected**. C-W1: PR #188 merged the supervised session. Distinct miner UID 1 finalized on subnet 567 at block 8013851 for 0.005426933 test TAO. Four real model calls cost USD 0.0019395 and proposed FNO-32, then stopped on malformed dry-validation arguments before submission or evaluation. The selected continuation repairs strict agent tool framing; a new bounded model session needs separate approval. Activation and publication remain separately gated. Earlier engineering validation completed three real JAX replicas and 72 measurements; those are not results of the real agent. No activation or all-burn publication occurred. AWS stays deferred, Hippius unverified, and protected/production/scientific qualification remains unearned. No later ticket is selected.

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
