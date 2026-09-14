# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 114 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-06**. Last completed: **C-05** (`done`). Next selected: **none selected**. C-05 is the last bounded completed slice after PR #157 accepted exact head 8dbee54dcd5bdea3a76b22812955e31fbe95e8da in run 34789621325 and normally merged as e3324691666da6b8987764048d2bfff45e0578b4. OWNER-C1-BURGERS-ALPHA-01 now selects C-06 alone for signed non-official DEVELOPMENT evidence. No later ticket is selected while C-06 is active; C-07 is prospectively authorized only after C-06's bounded merge. The candidate binds exact reconstruction, inference, reference, measurement, Dossier and execution identities in an append-only Ed25519-signed record. It keeps uncertainty unresolved and every official, protected, score, archive, network and reward eligibility field false. The trusted single-tenant host model, three-replica working profile, candidate reference roles and prospective archive targets grant no scientific sufficiency, independent security acceptance, protected admission, real archive acknowledgement, production, public network or LIVE authority. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
