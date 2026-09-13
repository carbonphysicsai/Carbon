# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 109 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-04**. Last completed: **C-EP3** (`done`). Next selected: **none selected**. C-EP3 remains the last fully closed ticket. PR #148 supplied C-02's bounded lab/Foundax adapter prerequisite. PR #149 accepted the first C-03 public-DEVELOPMENT worker and PR #151 accepted its bounded streaming, validation, replay and recovery hardening at exact head abc490495528d8960ff8c66f50feabeae3affd34 in run 34778563403, merged as 2d5872aff89ca7bef3e3f062b293aeefe17769aa. OWNER-C1-BURGERS-ALPHA-01 now selects C-04 alone for role-explicit Burgers algorithms and public qualification-candidate evidence under that worker. No later ticket is selected while C-04 is active; C-05 is prospectively next after the bounded C-04 merge. The trusted single-tenant host model, three-replica working profile, reference roles and prospective archive targets grant no scientific sufficiency, independent security acceptance, protected admission, real archive acknowledgement, production, public network or LIVE authority. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
