# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 68 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 105 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-03**. Last completed: **C-EP3** (`done`). Next selected: **none selected**. C-EP3 completed after head ff1d4603cf6889bb3e9cf7f4a589524ade5c6b8c passed run 34721794618 and merged in PR #145. PR #148 then accepted C-02 head 5e3d47039a52f601789f0495f8c3127f8b4a3cf4 in run 34758720071 and merged its exact Python-3.11 CPU environment, physical scaling and Foundax profile as 83186be004a4087b27b07278da490dad36785acb. OWNER-C03-DEV-ISOLATION-01 now selects C-03's first public-data DEVELOPMENT isolation slice around that merged adapter. The immutable Docker image, exact B-02C resource envelope, C-01 launch/recovery binding, bounded output stream/validation and hostile service tests are implemented; run 34769816925 passed all seven service tests and all three owner commands. Final exact-head CI and merge remain pending. C-02 stays open for production repeat/science and protected composition. Global MQ-015, the absent/deferred v0.2 source, protected execution, official science, archive, reward, public network, production and LIVE authority remain open. D6 canonical full/standard run 34518806217 remains historical evidence, and G2 is LOCALNET_READY only for its exact disposable standard-profile localnet. C-EA2 remains blocked; an implementation or test cannot fill an evidence gap owned by later authority. No later ticket is selected.

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
