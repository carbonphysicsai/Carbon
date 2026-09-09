# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 42 captured tickets across Wave A and Wave B
- 7 protocol-change routes
- 67 map-level change events
- 8 independent maturity states

## Captured current position

Wave **B**; current ticket: **B-E4**. Last completed: **B-E2** (`done`). Next selected: **none selected**. Wave B remains active in bounded development scope. B-E4 remains selected and in progress. PR #113 merged the strict pilot-v2 correction. The current candidate implements one sequential 5-profile x 4-arm x 2-task DEVELOPMENT runner over Carbon's B-07S/B-07C and A7/A8 TEST_ONLY fixture services, a strict real-but-disabled Responses adapter, and a durable intent/result journal. The frozen proposed request binds exact source, prompt, corpus, treatment, task/seed-commitment, payload, provider-control, and resource identities; its all-input-cache-write maximum is $14.41792 and its owner request is $14.42 under the unchanged proposed $98.304 pilot ceiling. The deterministic transport completed all 40 slots with zero provider inference and zero paid execution. Population/task/resource/egress/evidence approvals, authenticated role assignments, security-approved provider-project retention controls, and a separately verified one-use DEVELOPMENT authorization remain absent, so real transport fails before dispatch. No calibration, shadow, attack, or qualifying campaign ran; v4 remains STILL_BLOCKED, no later ticket is selected, and B-GATE remains unstarted.

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
