# CONSTRUCTION-CONTRACT-01-S1-REVIEW-REPAIR

Status: IN_PROGRESS; bounded engineering repair of merged S1 #1295.
Builder: Platform3. Reconstruction boundary: WAVE-C/C-02 (historical routing only; Hub maintenance retired by the direct owner decision on 2026-10-13).
Base: 07c950acbddc30ce31ab76f14a7e11ecd4156c2e, the normal S1 merge.
Reviewed S1 head: c30992915164bce7ee4557bc73d0eae0dd312115.
Review: TEST-LEAD-CONSTRUCTION-S1-20261013; REQUEST_CHANGES, S1-R1/R2/R3.

## Working contract

- R1: authenticate an explicitly supplied exact Composition descriptor against its registered version/digest and complete immutable variant descriptors before use. A valid but altered descriptor, including the separately registered signed L1 arm, must not claim the registered composition binding. The default loader remains authenticated. Explicit fixture directories are test-only inputs to the same resolution/check, not a skipped validation path.
- R2: load each immutable composition variant pin through the authentic historical version/digest registry, checking challenge, level, base digest and record sequence. Do not broaden ordinary dv.registered/current admission. Budget measurement must use the selected authenticated composition, not silently select the newest one.
- R3: compile full recipes and independently remove loss_expressions, muon_spectral, pool_selection, quasi_newton_family and line_search. Rebuild through development_rebuild; assert determinism, each field's effect, selected pool identity/content and staged/in-process parity. Exercise deliberately broken record/choice/pool controls so the assertions fail on an ignored or misrouted field.
- Preserve all registered documents/pins, base contract, per-field gates, graph-combination refusal, CPU_ONLY_DEV and isolation/import boundaries. No S2 graph integration, S3 wiring, thresholds, loss precedence, historical rescore, spend, host execution, deployment or qualification.

## Reuse and manifest

KEEP variant registry authentication and ordinary admission, single-level routes, composed trainers, staged programs and containment tests. REPAIR composition authentication/historical resolution and the adapter's selected-composition dispatch. Extend compiled-route tests without replacing the working numerical implementation.

Expected runtime/test paths: carbon/reconstruction/development_composition.py; carbon/battery/training_budget.py; tests/cpu/test_construction_contract.py; tests/cpu/test_battery_composed_training.py (only if needed). This ticket and .agent/decisions/CONSTRUCTION-S1-REPAIR-D1.md carry the working contract/decision. No Hub edits are retained: the owner directly retired maintenance during this repair. Refresh overlap checks for any new path.

Start evidence: 16 open PRs inspected, no proposed core repair/contract path overlap. Canonical baseline via CARBON_UV_GROUPS="science-jax chain archive" ./scripts/dev/canonical.sh python -m pytest tests/cpu/test_construction_contract.py tests/cpu/test_battery_composed_training.py tests/cpu/test_battery_development_rebuild.py -q: 33 passed. Windows output is never canonical acceptance.

## Plan and validation

1. Commit this bounded working contract and decision before implementation.
2. Add authentic descriptor/pin tests; implement registered resolution and selected-composition budget binding.
3. Add compiled rebuild ablations and assertion-sensitivity controls; retain existing single-part and staged parity tests.
4. Run focused and related composition/rebuild/variant/budget tests and all invariants through scripts/dev/canonical.sh. Run pinned Black/Ruff, delivery hygiene, encoding and changed-path scope-required acceptance. Use actual test results; no fixture claim establishes live or host behavior.
5. Follow current DELIVERY_PROTOCOL under the direct owner decision on 2026-10-13: "Scrap hub maintenance and human/GPT receipts.Follow how Claude was merging." Earlier stronger delivery/Hub requirements are prospectively superseded for this assignment; this correction adds no merge or deployment authority. Remove only this ticket's Hub edits; retain the local history of prior attempts.
6. Open one non-draft corrective PR to main, separate from closed #1295. Request fresh complete-diff exact-head rereview of the repair; reviewer is Test Review, with Test Lead routing and Carbon Validator for any reserved scientific seam. Attach the PR. No merge by Platform3.

## Conditional completion and maturity

The direct owner decision resolves the prior policy seam in favor of current DELIVERY_PROTOCOL. Completion requires actual applicable automated acceptance and successful Merge gate on the exact candidate head (skipped/absent is not success), disposition of concrete review findings, normal expected-head-guarded merge and confirmation by PR Head, and a brief completion comment/report with tests and limitations. No mandatory Hub maintenance, human/GPT approval/receipt ceremony, receipt-based GPT gate or post-merge full-CI receipt wait remains. Team scope/assertion/maturity review and the requested fresh review of this corrective diff remain; no repeated clean-pass quota. Platform3 does not merge or release.

Earned ceiling: bounded DEVELOPMENT implementation/test evidence. No scientific, security, network, production, LIVE, frontier, settlement or deployment authority. PLT-25 remains blocked until this repair lands. One-item cadence: stop at the required handoff/blocker, never start S2 in parallel.
