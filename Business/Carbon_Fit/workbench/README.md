# Carbon Opportunity Workbench v0.2

Open `Carbon_Opportunity_Workbench.html` in a modern browser. It is a browser-local decision-support tool: no install, credentials, worker, wallet, JAX, Docker, network service, analytics, submission, or public deployment is needed. If a browser blocks `file://` pages, use an approved loopback-only host:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
# open http://127.0.0.1:8765/Carbon_Opportunity_Workbench.html
```

## Owner walkthrough

1. Open the Atlas, choose one of the 64 source opportunities, and create its Challenge Profile.
2. Read the result card: Variant A remains the DEVELOPMENT baseline; protection begins `UNASSESSED` and the five study blockers remain visible.
3. In Conditional reference economics, choose “Expensive compatible burst.” The synthetic `b=3`, `R=40`, `H=4` example displays A=120, B=44 and group saving=76 while A remains selected and runtime sharing remains unavailable.
4. Inspect the detached dynamic examples and six-condition evidence checklist. “Slow or unresolved member” shows lower work alongside fewer completed comparisons.
5. Open Preview and export, add client context, inspect both projections, and download JSON or Markdown. Nothing is sent.

## What v0.2 adds

- CPES evidence in the existing Challenge Profile, Exam review, Compare, References/studies, calculations, and exports.
- Eight P1–P8 controls, the five named unresolved claims, and separate review completeness/blocker state. No fit or security average is calculated.
- Immutable `RETAIN_A` research recommendation and Variant A DEVELOPMENT baseline. B is scenario exploration and a possible future research-review packet; C remains a research sensitivity view.
- Conditional fixed-group arithmetic with explicit units, scope, provenance status, unknown propagation, completion accounting, and separately displayed upfront burden.
- The pinned detached dynamic replay output, including endogenous grouping and slow-member regressions. The browser does not contain a scheduler or solver.
- Additive v0.1 draft/workspace migration with raw-input digest status, visible semantic receipt, preserved legacy cohort inputs, and recomputed derived outputs.
- Closed, bounded evidence claims. Browser imports remain user-supplied even when Web Crypto verifies their bytes; they cannot overwrite the built-in study or grant authority.
- Client and Engineering projections of one deterministic planning record, both with scenario basis, missing evidence, provenance, and authority limitations.

## Provenance and authority

The built-in study is derived only from the eight public-safe files indexed by CPES evidence index SHA-256 `4565995a98fe8f238ca88b44e418e6c7da2954de9dca577b80968854bad34ba7` at research packaging head `ca904dfee93d3574df4e56b99981a6ed3b138e80`. Its research baseline, missing implementation identity, packaging revision, delivery state, and integration provenance remain separate fields.

Those pinned bytes were accepted after issue #153's separate test-only correction: reconciled research head `0a5690270dc449ea19c941280203987d37db5283`, acceptance run `34786945000`, merge commit `2ac835d1dd55deb9c99e493f3615143efa2e51e0`. Historical failed run `34778525936` remains recorded rather than overwritten.

The source precedence is: current repository contracts for authority; pinned research for displayed findings; EXAM-PROTECT-WORKBENCH-01 for this bounded UI; user inputs for unreviewed scenarios. The tool does not qualify an official exam, approve protected workloads, authorize reference sharing, publish answers, grant rights, activate runtime behavior, create a submission, or infer a production Strategy/profile.

Exports are unencrypted files. Keep input high-level and non-sensitive. Client exports omit the private contact field, raw traces, paths, seeds, and answers.

## Maintained files

- `src/engine.js`: pure deterministic planning, migration, validation, analysis, and export projections.
- `src/app.js`, `src/shell.html`, `src/styles.css`: the existing five-view browser application.
- `data/cpes_study_v1.json`: generated public-safe browser adapter.
- `evidence/cpes_reference_reuse_v2/`: exact eight-member pinned evidence input plus its index.
- `tools/import_cpes_evidence.py`: hash, schema, disposition, quantity, and cross-consistency validator.
- `tools/build_schema.py`: closed v0.2 schema/constant generator.
- `tools/build.py`: deterministic standalone HTML build with hash-based CSP and script-safe embedded JSON.
- `tools/package_release.py`: deterministic complete source/test/evidence ZIP and checksum manifest.
- `docs/REQUIREMENT_TEST_MAP.md`: acceptance mapping.
- `docs/OWNER_REPORT.md`: capability, assumptions, blockers, measurements, and delivery state.

## Reproduce

Build uses Python's standard library. Re-extracting the atlas needs `python-docx`. The browser test needs Node Playwright and a local Chrome-compatible executable; it navigates the real generated file and inspects downloaded bytes.

```sh
python3 tools/import_cpes_evidence.py --check
python3 tools/build_schema.py
python3 tools/build.py
node --test tests/test_engine.cjs
python3 tests/test_sources.py
node tests/browser_smoke.cjs
python3 tools/package_release.py
```

The canonical Engineering environment determines repository acceptance. Local browser coverage recorded here is Chromium/Google Chrome at desktop and narrow widths. Safari/WebKit was not available to the automated runner and is not claimed.
