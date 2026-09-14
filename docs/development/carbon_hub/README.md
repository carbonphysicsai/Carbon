# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 121 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-EA1**. Last completed: **C-08** (`done`). Next selected: **none selected**. C-08 is the last bounded completed slice after PR #167 accepted exact head 17e72cfd97c12512dd9a6a08a6b8329974422328 in run 34816242461 and normally merged as ed6047d03cf60db6ce52f03e63040d95c1ea78e4. OWNER-C1-BURGERS-ALPHA-01 now selects C-EA1 alone for fail-closed private-alpha archive preparation. No later ticket is selected while C-EA1 is active. The candidate preserves the accepted synthetic acknowledgement, freezes the prospective alpha policy, requires exact external provider/custody/recovery/security/deployment references, and tests only a dedicated non-secret service preflight. It issues no real archive acknowledgement and cannot satisfy C-EA2. No provider resources, spend, protected admission, independent security acceptance, public network or LIVE authority exist. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
