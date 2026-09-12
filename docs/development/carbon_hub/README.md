# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 100 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-EP3**. Last completed: **C-EP2** (`done`). Next selected: **none selected**. C-EP2 is complete after corrected head 89f06eda74b15dd336e57a512f228c6b37cca77d passed RUNTIME_FULL run 34718392697 and merged in PR #144 as 96099aeac9e5022bda9d94730b1d7d955cb6c1d5. C-EP3 alone is selected for bounded public-reference input acquisition and one detached component probe; no later ticket is selected, and no real C1 or Variant-B implementation ticket is selected. C-03, C-08 and C-09 remain unselected and dependency-blocked; C-EA2 remains unselected and blocked on a real C1 path and eligible real archive profile. D6 canonical full/standard run 34518806217 remains the G2 evidence. No sharing, answers, real entropy/reference qualification, public network, reward change, scientific/security qualification, production or LIVE authority is created.

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
