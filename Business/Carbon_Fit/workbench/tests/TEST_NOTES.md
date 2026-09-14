# Workbench v0.4 acceptance notes

GOAL-WORKBENCH-04 adds 25 focused C-05 adapter/workflow checks and one built-artifact Chrome import check. The added closeout check rejects rebinding registered numerical bytes to an unrelated compatible-looking case family. The source fixture generator ran on Python 3.11.11 with the exact pinned C-04/C-05 dependency identities. These results demonstrate read-only DEVELOPMENT evidence integration only; they are not scientific qualification, security acceptance, score validation, or Wave C runtime evidence.

Run from `Business/Carbon_Fit/workbench`:

```sh
python3 tools/import_cpes_evidence.py --check
python3 tools/build_schema.py
python3 tools/build_goal_schema.py
python3 tools/build.py
node --test tests/test_engine.cjs tests/test_workflow.cjs
python3 -m pytest tests/test_authoring_bridge.py ../../../../tests/cpu/test_cauth1_goal_authoring.py -q
python3 tests/test_sources.py
node tests/browser_smoke.cjs
node tests/browser_goal_smoke.cjs
python3 tools/package_release.py
```

Current focused results are recorded in the delivery PR and owner report. `browser_results.json` preserves the accepted CPES route; `browser_goal_results.json` covers direct intake, exact native authoring and closed-loop return in the actual standalone HTML. The screenshots cover desktop and narrow layouts.

The final local v0.3 candidate ran 65 inherited pure-engine checks, 21 goal-workflow checks, 24 focused Python authoring/bridge checks, 15 source/schema/build/package checks, 105 Hub decision-record checks, 40 inherited Chrome checks, and 27 goal-flow Chrome checks, all passing. These suites have different scopes and are reported separately rather than added into a scientific, security, or qualification total. The outside-tree package check built `carbon-0.9.0`, installed it into a fresh Python 3.11 environment without a source-tree `PYTHONPATH`, and returned `INTENT_PRESERVED / Dynamics / scientifically_qualified=false` through the fixed bridge.

The browser runs use installed Google Chrome (Chromium), navigate the generated `file://` artifact, block network after load, and inspect actual downloaded bytes. The goal journey invokes the fixed local source-owned authoring CLI, reimports its result, and inspects the downloaded source-owner numerical-diagnostic request. Safari/WebKit automation is unavailable and is not claimed.

The original v0.1 source input was independently verified before import: all 38 manifest payloads matched and its 39 Node tests passed. Those checks are input provenance, not v0.2 acceptance and are not added to current totals. The CPES PR's historical 14/52/208 sets likewise remain research provenance and are not application test counts.

Repository runs `34789353024` and `34789634638` on earlier PR #156 candidates remain failed history. Their Hub fixture and dependency-boundary defects were repaired in separate maintenance PRs #159 and #160. After both repairs merged, PR #156 was reconciled with main `1a1a5ad4585caebd168725451ca255e06561f693`; the same 65 engine, 14 source/evidence/schema/build/package, and 40 actual-Chrome checks passed again. Final exact-head repository acceptance is recorded on PR #156 rather than retroactively attributed to an earlier artifact.
