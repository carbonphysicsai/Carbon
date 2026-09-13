# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 103 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-02**. Last completed: **C-EP3** (`done`). Next selected: **none selected**. C-EP3 completed after head ff1d4603cf6889bb3e9cf7f4a589524ade5c6b8c passed its recorded acceptance and merged in PR #145. PR #146 merged the initial bounded C-02 adapter, and PR #147 accepted head 72608d589582707955943345bc1308017e9650dc in run 34750621646 before merging its v2 hardening and frozen DEVELOPMENT repeats as dbd7e255f8a1d507b924bd1f82d309007b201b0b. The current owner-directed v3 continuation upgrades the exact Python-3.11 CPU environment, binds physical scaling, adds manufactured verification and provides one source-pinned Foundax FNO implementation profile. C-02 remains in progress because the separately described v0.2 research archive is absent, owner-selected repeat policy and C-03 isolation remain absent, and no later ticket is selected. Official science, protected execution, archive, reward, public network, production and LIVE authority remain absent. D6 canonical full/standard run 34518806217 remains historical evidence, and G2 is LOCALNET_READY only for its exact disposable standard-profile localnet. C-EA2 remains blocked; an implementation or test cannot fill an evidence gap owned by a later authority.

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
