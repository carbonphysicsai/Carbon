# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 117 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-07**. Last completed: **C-06** (`done`). Next selected: **none selected**. C-06 is the last bounded completed slice after PR #161 accepted exact head bad0b05c7683af67caa5fbd9fe9a8e11fda588da in run 34797587027 and normally merged as 0c00350b98b9a0062006f5bd2ce50c20aff37b3c. OWNER-C1-BURGERS-ALPHA-01 now selects C-07 alone for durable non-official DEVELOPMENT orchestration. No later ticket is selected while C-07 is active; C-08 is prospectively authorized only after C-07's bounded merge. The candidate reuses C-01 durability and source-owned generator, reconstruction, prediction, reference, measurement and C-06 receipt identities. It retains typed failures, explicit same-claim reconciliation and digest-only projections while every official, protected, score, archive, network and reward eligibility field remains false. The trusted single-tenant host model, three-replica working profile, candidate reference roles and prospective archive targets grant no scientific sufficiency, independent security acceptance, protected admission, real archive acknowledgement, production, public network or LIVE authority. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
