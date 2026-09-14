# GOAL-WORKBENCH-02 / EXAM-PROTECT-WORKBENCH-01 requirement-to-test map

This map describes focused application acceptance. It does not relabel the CPES study's historical 14/52/208 runs as workbench tests.

| v0.3 requirement | UI / data | Native owner / adapter | Automated evidence | Current limitation |
|---|---|---|---|---|
| Direct intake, multiple jobs/alternatives, optional Atlas, immutable revisions | Client jobs; v0.3 job/design schemas | Business/WAVE-G planning owner | `test_workflow.cjs`; `browser_goal_smoke.cjs` | Browser-local manual persistence; no live intake/CRM |
| Preserve original requirement and link score/cases/reference | Requirement trace, score plan, case families, reference plan, diagnostic-request export | Measurement/ScorePack, generator, reference owners | workflow coverage/mandatory-failure/diagnostic-request tests; browser source-bound case trace and downloaded request | Structural coverage is not numerical or scientific adequacy; request status stays `NOT_EXECUTED` |
| Exact supported Burgers compilation and semantic agreement | Authoring request/result/receipt | C-AUTH1; `tools/authoring_bridge.py` fixed CLI | bridge Python tests; actual CLI round trip in browser journey | DEVELOPMENT Dynamics only; not qualification/registration |
| Same-PDE incompatible goal and non-Burgers/rights gaps | Extension request retained in design | C-AUTH1 source owner | Front Resolution and extension tests | Source owner must implement/accept any new capability |
| Design-bound CPES and stale impact | CPES binding + change log | CPES research and domain owners | favorable-B/stale-economics workflow tests; browser journey | A remains baseline; five claims and adequate R/demand/H/service unknowns remain |
| Bidirectional idempotent handoffs | handoff/response v1 arrays | Named S1/R1/owner/executor/launch owner | duplicate/conflict/stale/wrong-task/forgery tests; browser ack cycle | Actual route is manual; no Grok/CRM/message connector |
| Least-privilege client/N1/Engineering views | projections and downloads | Business/account and Engineering owners | projection unit tests; parsed browser downloads | Files are unencrypted and not transmitted |
| Launch candidate and truthful native status | launch-candidate v1 | Launch/registration owner | forged status and candidate export tests | Native launch interface unavailable; no actual launch |
| Additive v0.1/v0.2/v0.3 migration | outer v0.3 closed schema + receipt | Workbench owner | workflow migration/authority tests; browser migrate/export/reload | No science inferred for migrated component-only sessions |
| C-PILOT-01 operating projection | read-only v1.9 projection | R1 lead, S1 support, optional H1 | workflow projection test | Grok plan artifact not located; no account integration or training run |

| Requirement | Automated evidence |
|---|---|
| Exact source archive, 64 opportunities, source wording/ratings, MMS and role distinctions | `tests/test_sources.py`: atlas hash/re-extraction, 64 IDs/groups, reference/MMS/experiment tables, source hypotheses; `tests/test_engine.cjs`: all-ID migration and role preservation |
| All eight indexed CPES members, exact hashes, schemas, 30 attacks, 17/8/5 layers, five blockers | `tools/import_cpes_evidence.py --check`; `tests/test_sources.py`: member/schema/cross-consistency and public adapter tests |
| Baseline A cannot be changed by scenarios/imports; B conditional; C sensitivity; negative control never an option | `tests/test_engine.cjs`: fixed-group, authority-forgery, C, export tests; `tests/browser_smoke.cjs`: baseline immutability, disabled activation, library layers/control |
| P1–P8 inside Exam; `UNASSESSED`, `PROTECTION_BLOCKED`, `READY_FOR_DOMAIN_REVIEW`; completeness independent of blockers | `tests/test_engine.cjs`: five protection-state cases; browser checks P1–P8 and five source claims |
| Conditional economics, unknowns, singleton/equality/sign, field dependence, incomplete/zero completion | `tests/test_engine.cjs`: fixed-group and aggregate cases, exact b=3/R=40/H=4 vector |
| No cross-unit/cross-host/wall-vs-occupancy composition; upfront cost separate | `tests/test_engine.cjs`: scoped quantity composition and upfront-invariance tests |
| Dynamic grouping recomputed and slow-member completion/service caveat | `tests/test_engine.cjs`: exact 38/39 vs 36/36 vector and slow row; browser dynamic table/caveat |
| Six deterministic next-evidence conditions and review-only packet | `tests/test_engine.cjs`: projections; browser profile and actual Engineering download bytes |
| Additive v0.1 migration; no data loss or authority promotion; invalid import atomic | `tests/test_engine.cjs`: substantive migration, 64 identities, round trip, schema/authority rejection; browser migrate/edit/export/reload path |
| Closed parser: duplicates, dangerous keys, depth, overflow, booleans, unknown fields | `tests/test_engine.cjs`: strict parser/schema cases; browser duplicate-member rejection |
| Safe text rendering, no breakout/navigation/request, CSP, offline operation | `tests/test_sources.py`: CSP and embedded JSON build; browser malicious text, page errors, outbound requests, network-blocked flow |
| Client and Engineering JSON/Markdown preview/download with caveats | `tests/test_engine.cjs`: deterministic projections; browser saves and parses all four downloaded artifacts |
| Keyboard, labels, live status, desktop/narrow render | Browser focus/label/live-region/overflow checks and three screenshots in `tests/` |
| Reproducible standalone HTML and complete bundle | `tests/test_sources.py`: double build and manifest/bundle reproduction; `tools/package_release.py` |

## Browser coverage

The recorded automated run uses the actual generated `file://` artifact in installed Google Chrome (Chromium), desktop 1440×1050 and narrow 390×844. A separate CUA owner walk-through uses the supported `127.0.0.1` route. Safari/WebKit automation was unavailable locally and is not counted as passed.
