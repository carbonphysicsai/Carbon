# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 101 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-02**. Last completed: **C-EP3** (`done`). Next selected: **none selected**. C-EP3 completed after head ff1d4603cf6889bb3e9cf7f4a589524ade5c6b8c passed RUNTIME_FULL run 34721794618 and merged in PR #145 as a02ca5f46eda2283db7808d9646c1ef24715ec4a. The owner supplied an immutable JAX source/interface bundle and selected C-02 alone for bounded DEVELOPMENT integration. FNO and DeepONet share one compiler-plan adapter; all official science, protected execution, C-03 and later C1/C2 tickets remain unselected. D6 canonical full/standard run 34518806217 remains G2 evidence only for its exact disposable standard-profile localnet. No sharing, official answers, reward change, public network, scientific/security qualification, production or LIVE authority is created.

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
