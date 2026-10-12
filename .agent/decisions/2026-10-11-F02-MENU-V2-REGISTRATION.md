# F02-MENU-V2-REGISTRATION — prospective development budget

**Authority:** Test Lead's f02 menu-v2 decision (16 actions × 24 contexts,
continuous disjoint public TRAIN), relayed in F02-MENU-V2-REGISTRATION;
`docs/development/evidence/reference-packages-01/f02-menu-v2/registry.json`
and `train-registry.json`; Test Lead's value-bar delegation of 2026-10-10.
This is DEVELOPMENT planning, not measured buyer spend or a qualified result.

**Decision:** Keep `EQUAL-BUDGET-V1` and its nine-action f02 row unchanged as
history. Publish digest-bound `EQUAL-BUDGET-V2-F02-MENU` with the same schema
and the 16-action finite menu. Only f02 changes. Its per-context
half/base/double assumption is 8/16/32 solver evaluations and 2/4/8 wall
and CPU core-hours. Historical 2–3 CPU-minutes per waveform is only a lower
timing anchor; setup, refinement and failed attempts need allowance. The 24
contexts form the registered panel, not 24 independent buyer jobs. Public
continuous TRAIN is separate from the held-out finite menu.

The adaptive direct finite-enumeration and ordinary-surrogate arms both use
`BudgetLedger` under the same validated registration. The registration ID
selects nine versus sixteen actions; the panel's cost-plan ID and complete
budget ladder must match. Half and double remain sensitivity budgets. None is
selected after an evidence outcome. The V1 registration is retained because
past records bind its digest; per the Test Lead, no f02 evidence run used it.

**Alternatives rejected:** Mutating V1 would silently reinterpret past
registrations. Reusing a nine-action check on the V2 menu would refuse the
adopted finite action set. Treating the 960 continuous TRAIN decks as decision
menu actions would mix training and held-out roles.

**Reversibility and owner boundary:** The new JSON and version-aware validation
can be removed without changing V1 evidence. Actual buyer workflow cost,
Challenge qualification and any frozen rule adoption remain human decisions.
