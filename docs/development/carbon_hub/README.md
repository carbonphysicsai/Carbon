# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 111 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-05**. Last completed: **C-04** (`done`). Next selected: **none selected**. C-04 is the last bounded completed slice after PR #154 accepted exact head 32fa87f0f4947b8fbae9b2b73e5fa875a73de175 in run 34784739423 and normally merged as 0cd91bfa6d30f81739ff75e46888f6f1387bd1de. OWNER-C1-BURGERS-ALPHA-01 now selects C-05 alone for real measurement algorithms and public qualification-candidate evidence under a distinct C-03 worker. No later ticket is selected while C-05 is active; C-06 is prospectively authorized only after C-05's bounded merge. The candidate binds C-02 artifact and C-04 candidate-primary reference identities, emits four measurements and six physics diagnostics, and keeps every limit and decision unresolved. The trusted single-tenant host model, three-replica working profile, candidate reference roles and prospective archive targets grant no scientific sufficiency, independent security acceptance, protected admission, real score, archive acknowledgement, production, public network or LIVE authority. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
