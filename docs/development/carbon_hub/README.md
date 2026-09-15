# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 124 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-EA1**. Last completed: **C-10** (`done`). Next selected: **none selected**. PR #177 accepted exact C-EA1-D3 head a4d23361b501240e16aff23464950597bf8e0368 in run 34900578390 and normally merged as 86f3a02485a2522dd4c7fa839a34872508746607 with matching tree 439785f4b496f94d5a5a7c04bec7d45261fbccd3. C-EA1-D4 alone is selected for prospective AWS v2 custody, IAM, private-network, retention, full-watermark recovery and account-bound handoff repair. No later ticket is selected. Actual account/network/principals, USD 175/month and USD 5 rehearsal approval, provisioning, recovery rehearsal, security acceptance and signer authorization remain absent. No real acknowledgement, C-EA2, protected execution, public network or LIVE authority exists. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
