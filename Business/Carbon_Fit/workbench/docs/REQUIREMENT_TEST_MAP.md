# EXAM-PROTECT-WORKBENCH-01 requirement-to-test map

This map describes focused application acceptance. It does not relabel the CPES study's historical 14/52/208 runs as workbench tests.

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
