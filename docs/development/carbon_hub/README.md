# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 107 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-03**. Last completed: **C-EP3** (`done`). Next selected: **none selected**. C-EP3 remains the last fully closed ticket. PR #148 supplied C-02's bounded lab/Foundax adapter prerequisite. PR #149 then accepted C-03 head ef4d5e336c942b7ff40856fcfee03f522ef2d1d5 in required run 34770761721 and normally merged its bounded worker as d94a22bb3c09089e01402db9e7ebf6eb3c662966 with image/config sha256:dae4717ae00d3174b8644159934eb4edbe94c0ad125549f6ade570a6f4c7e630. OWNER-C1-BURGERS-ALPHA-01 now selects only C-03 prerequisite hardening. No later ticket is selected while C-03 hardening is active; C-04 is prospectively authorized after its normal tested merge. The owner selected a trusted single-tenant host model, a separate three-replica working profile, explicit reference roles and prospective real-archive targets, without granting scientific sufficiency, independent security acceptance, protected admission, real archive acknowledgement, production, public network or LIVE authority. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
