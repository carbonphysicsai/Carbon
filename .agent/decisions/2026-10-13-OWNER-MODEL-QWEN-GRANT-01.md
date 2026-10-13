# OWNER-MODEL-QWEN-GRANT-01 — the qwen open-weight Constructor grant, and the 0.65/h ceiling for a non-stage family

Date: 2026-10-13
Status: APPROVED by the owner, confirmed directly in the PR Head session.
Authority: the owner. Not delegable, for two independent reasons recorded below.
Scope: **`GRAPHITE-GRANT-MODEL-QWEN-CONSTRUCTOR-1` only, including its 0.65/h
pod ceiling.** This approves no other grant and confers nothing on the
`GRAPHITE-GRANT-MODEL-` family as a family: a second model-family grant needs
its own figure and its own ceiling confirmed.
Maturity: DEVELOPMENT spend authority. No scientific or qualification authority
is created.

## What he approved

One short Constructor session at **Levels 0 to 3** whose ladder opens on
**qwen3.8-27b**, an open-weight model a miner might bring, on the Engy ladder
and under the same Engy key as every other run, from the **standing weekly test
grant** (`OWNER-TEST-GRANT-01`):

| field | value |
| --- | --- |
| `monetary_ceiling` | **USD 14.94** |
| `worst_case_run_cost` | USD 14.91 |
| `pod_rate_ceiling_usd_per_hr` | **0.65** (instead of the 0.49 default) |
| levels | `min_level` 0, `max_level` 3 |

These figures were read from the grant file itself at `a0d513da8`, not from a
report: `pod_rate_ceiling_usd_per_hr` `0.65`, `monetary_ceiling` `14.94`,
`worst_case_run_cost` `14.91`.

`start_model` is a **floor, not a pin**: the ladder's escalation rule is
unchanged, so a session may climb a rung on an observed research failure, and
each call records its model. The grant authorizes **spend, never a Level run**.

## Why this was the owner's decision and not a delegated one

Two independent reasons, either sufficient:

1. **The 0.65/h ceiling is an owner figure confirmed per scope.**
   `GRANT-POD-CEILING-01` records his words as a "ceiling for **all stages**",
   and a `GRAPHITE-GRANT-MODEL-` family is a model-comparison family, not a
   stage. The precedent is in the repository: when R4 wanted the same rate it
   required its own direct confirmation,
   `2026-10-11-OWNER-GRAPHITE-PHASE3-R4-CEILING-01.md`. Extending a confirmed
   figure to a scope he never named is how a figure quietly becomes general.
2. **`OWNER-POD-LAUNCH-DELEGATION-01` keeps "every new grant figure" with the
   owner**, so the USD 14.94 was not delegable either, independent of the rate.

A per-hour ceiling also binds spend **independently of** the 14.94 total, so it
is not merely a hardware-class preference inside an unchanged budget.

The change had been based on a **Test Lead engineering decision** recorded in a
test comment. That decision is taken as validly made while they held the role,
and the comment was explicit and honest — it stated "the effect is a raise from
0.49 to 0.65" and cited the two records as "the source of the 0.65 figure only,
not authority for this scope". But an engineering basis cannot confer either of
the two authorities above, and the Test Lead has since stood down.

## Distinguished from #1300

#1300 changed **no owner figure**: a bigger context window made each call's
hold larger, so an unchanged 10.99 share covered four full calls instead of
five. That is a call count under an unchanged cap. Here an owner figure is
applied to a scope he never named, which is a different question with a
different owner.

## Not covered by this record

- **Any other `GRAPHITE-GRANT-MODEL-` grant, and the family as a family.** This
  approves one grant and the 0.65/h ceiling **as applied to that grant**. A
  second model-family grant needs its own figure and its own ceiling confirmed,
  for the same reason this one did: a figure confirmed for one scope does not
  extend itself to the next.
- Consequently, the enforcement should bind the **named grant file** rather than
  the `GRAPHITE-GRANT-MODEL-` prefix. A prefix test would grant the ceiling to
  every future grant whose name happens to start that way, which is precisely
  the family-wide authority the owner was not asked for.
- Resolution of #1257's conflict with main in `grant_binding.py`. That conflict
  splits a `Phase3Grant(` entry and is for the lane to resolve, not to be
  reconstructed by the merge manager.
- Any scientific conclusion from the run. Coverage of an open-weight model is a
  spend authorization; what the run shows is decided under the registered
  contracts, not here.
