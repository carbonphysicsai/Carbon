# Workbench v0.2 acceptance notes

Run from `Business/Carbon_Fit/workbench`:

```sh
python3 tools/import_cpes_evidence.py --check
python3 tools/build_schema.py
python3 tools/build.py
node --test tests/test_engine.cjs
python3 tests/test_sources.py
node tests/browser_smoke.cjs
python3 tools/package_release.py
```

Current focused results are recorded in the delivery PR and owner report. `browser_results.json` is machine-readable evidence from the actual standalone HTML. The screenshots cover Atlas desktop, Profile desktop, and Profile narrow layouts.

The browser run used installed Google Chrome (Chromium), navigated the generated `file://` artifact, blocked network after load, and inspected all four downloaded summary formats. A CUA walkthrough also exercised the documented `127.0.0.1` route. Safari/WebKit automation was unavailable and is not claimed.

The original v0.1 source input was independently verified before import: all 38 manifest payloads matched and its 39 Node tests passed. Those checks are input provenance, not v0.2 acceptance and are not added to current totals. The CPES PR's historical 14/52/208 sets likewise remain research provenance and are not application test counts.

Repository run `34789353024` on PR #156 candidate `71fcae5c64020d8e40675b4ebb5c4ba45981610a` passed Delivery preflight. It then exposed existing issue #141 in Hub validator fixtures and a current-main C-04 invariant import of NumPy in the contract-only environment; Merge gate failed accordingly. These are recorded blockers, not skipped or passed application tests, and this workstream does not modify their owning runtime/CI scope.
