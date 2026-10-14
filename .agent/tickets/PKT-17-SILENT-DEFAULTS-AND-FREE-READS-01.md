# PKT-17 — Silent defaults and free reads

Authority: owner-delegated Packets3 queue assignment of 2026-10-13.
Starting base: `bf2494ef4` on `main`. One item, one PR; no merge authority.

## Working contract and plan

KEEP the research executor, ledger, battery catalog, compiler and registered
implementation snapshots. Add tests and miner-facing documentation only.

1. Exercise chunked reads through the public research task lifecycle and the
   real campaign ledger, including a `run_python` charged control and a
   refusal before dispatch. Replace only the sandbox worker with a fixture.
2. Compile omitted and explicit battery MLP architecture fields. Check the
   actual constructed parameter shapes, not only a catalog description.
3. State the read accounting and applicable architecture defaults in the
   miner FAQ and Level 4 starter. Distinguish the submitted graph's architecture
   from catalog fields; retain all other Level 4 recipe controls.
4. Run canonical focused regressions and formatting checks, then submit the
   bounded candidate for Launchpad/Test Lead review and exact-head CI.

Expected manifest: this ticket, a new CPU regression test, `MINER_FAQ.md`,
and `graphite/level4/STARTER.md`. Live open PRs checked before implementation;
none changes these paths. No thresholds, accounting, defaults, pinned modules,
public tool descriptions, schemas, grants or protected material may change.

## Evidence and limits

Canonical command: `CARBON_UV_GROUPS=science-jax ./scripts/dev/canonical.sh
--focused tests/cpu/test_miner_read_accounting_and_defaults.py
tests/cpu/test_research_surface_costs.py tests/cpu/test_cw1_research_tasks.py
tests/cpu/test_battery_construction_contract.py
tests/cpu/test_graphite_level4_starter.py`.

Fixtures prove task/accounting and reconstruction wiring, not host execution,
containment, scientific validity or qualification. Reads consume no research
trial; that does not imply provider calls or arbitrary compute are free.
Relevant invariants: private/public isolation, non-authoritative practice,
historical contract preservation and human-owned qualification.

Hub map_ref: `WAVE-C/C-W1-D4` (research task surface). This change documents
existing behavior and adds tests; it changes no placement, dependencies,
authority boundary or runtime maturity. Hub/delivery policy reconciliation
is held for Test Lead/owner disposition; no Hub or delivery override is made.
Completion is conditional on canonical tests, exact-head CI, required lane
review and resolution of applicable delivery holds. Stop after this item.
