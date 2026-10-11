# EQUAL-BUDGET-V1 — prospective development comparison budgets

The [digest-bound registration](equal-budget-registration-v1.json) fixes the
resource allowance **before** a Challenge's equal-budget evidence is run. It
applies to battery v3, revised motor 10p/12s, the adopted f02 finite menu, and
the original offset f13 silencer. Every number is an **ASSUMPTION** about a
competent buyer's possible design-search allocation. The
[#1014 realism review](../../../Business/research/equal-budget-realism/SPECIFICATION.md)
documents method classes and historical cost anchors but does not measure the
exact buyer-job budgets. Challenge-specific rationales and source anchors are
stored beside each row in the JSON. These numbers do not qualify any Challenge.

| Decision | Complete solver panels, half/base/double | Wall hours, half/base/double | CPU core-hours, half/base/double |
| --- | ---: | ---: | ---: |
| Battery v3, five ambient bands | 12 / 24 / 48 | 4 / 8 / 16 | 12 / 24 / 48 |
| Motor 10p/12s, whole command/angle/skew panel | 6 / 12 / 24 | 12 / 24 / 48 | 48 / 96 / 192 |
| f02, adopted nine-action menu | 5 / 9 / 18 | 1 / 2 / 4 | 1 / 2 / 4 |
| f13, original offset full frequency curve | 4 / 8 / 16 | 8 / 16 / 32 | 16 / 32 / 64 |

One solver evaluation is a **complete mandatory condition panel** for one
candidate, including registered refinement. Infeasible designs and failed
solver attempts spend an evaluation. Screening, acquisition, fitting, search,
startup, and retries spend wall time and CPU time. A search stops before a
complete panel whose planning bound cannot fit. A half tier rounds an odd
evaluation count up, so f02 uses 5 rather than 4.5. The f02 double tier may
saturate the discrete menu; it does not authorize unregistered new actions.
The conditional f13 coaxial reframe is outside this registration.

The base tier is the VALUE-BAR-V1 item-5 gate. The half and double tiers are
sensitivity diagnostics on the same evidence, and all three appear on the
owner page. The evaluator still requires measured *execution costs*, settled
solver values and independent bank clusters. An assumed budget is not a
substitute for measured costs. When a complete solve exceeds an allowance, the
arm stops; the cap cannot be enlarged after seeing a result.

## Shared accounting contract

`carbon.design_search.budget_registration.validate` returns the same
`BudgetCap` for every comparison arm at a given Challenge and tier.
`BudgetLedger.charge_overhead` and `charge_solver_attempt` enforce that cap.
The existing fixed-order solver, model-screen, and cheap-baseline arms use it.
The future ADAPTIVE-SOLVER-ARM-01 adaptive solver and ordinary surrogate arms
must receive the same `BudgetCap` and charge every attempt through the same
ledger. Those two arms are not yet implemented; this registration does not
claim a four- or five-arm empirical comparison.

The development panel's `budgets` must exactly equal the registered
half/base/double wall/core ladder, and `registrations.cost_plan` must be
`EQUAL-BUDGET-V1`. The report repeats the registration digest, each tier name,
and the solver-evaluation cap. The VALUE-BAR-V1 evaluator refuses a different
digest or cap, and requires all three tier curves. A self-digest records the
content; producer custody must establish that the registration preceded the
evidence run.

```text
python -m carbon.design_search.equal_budget PANEL.json \
  --budget-registration docs/development/challenge_pipeline/equal-budget-registration-v1.json \
  --bootstrap-replicates 2000 --confidence 0.95 --seed 17

python -m carbon.development_comparison.value_bar \
  --evidence DEVELOPMENT-value-pack.json \
  --rule docs/development/challenge_pipeline/value-bar-v1.json \
  --budget-registration docs/development/challenge_pipeline/equal-budget-registration-v1.json \
  --bootstrap-replicates 2000 --seed 17 \
  --output-json new-value-report.json --output-page new-owner-page.md
```

These commands read registered development files. They do not run a solver or
make a LIVE policy decision. The Test Lead owns prospective budget revisions
under the owner's value-bar delegation; a revision needs a new identity and
does not reinterpret earlier evidence.
