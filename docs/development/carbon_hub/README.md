# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 126 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1**. Last completed: **C-10** (`done`). Next selected: **none selected**. PR #183 accepted exact C-W1-D1 foundation head 324a5276cd6a1ffdc491d04d08ef8b3282a060e8 in run 34927991086 and normally merged as bd7e5a5423d1148d340b3de3993068b66f5973d with matching tree 65e2a3d5abee97e5eaf1538050e0dcfab22cc649. The same selected ticket now has a closed controller source handoff, fixed run/status/resume and separate host/chain readiness reporting as a continuation candidate. Read-only public-testnet evidence still has no approved netuid or registration for the available hotkey, and the current Darwin arm64 host lacks Docker. No chain write, token spend, real archive acknowledgement, protected/official eligibility, science/security qualification or LIVE authority exists. AWS stays deferred and Hippius stays unverified. No later ticket is selected.

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
