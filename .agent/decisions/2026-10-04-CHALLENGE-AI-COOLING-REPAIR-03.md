# CHALLENGE-AI-COOLING-REPAIR-03 — dependent evidence and campaign control

**Date:** 2026-10-04

**Status:** selected engineering repair; counted execution remains
owner-reserved

**Authority:** user-authorized repair of `CHALLENGE-AI-COOLING-FOUNDATION-01`;
scientific acceptance, compute/spend, customer acceptance and LIVE authority
remain reserved

## Decision

Keep the frozen periodic-cell 8-design × 6-condition study unchanged and make
its analysis and execution controls match the evidence actually available:

1. Treat the four arms as descriptive outcomes from one shared decision
   problem. Report 24 arm-condition uses as six unique selected
   design-condition cases plus 18 evidence reuses. Do not report a binomial
   confidence interval or population/generalisation reliability claim. A future
   uncertainty estimate requires an approved sampling design and justified
   independent observation unit.
2. Classify proposals as `CONFIRMED_INFEASIBLE`, `CONFIRMED_FEASIBLE`,
   `UNRESOLVED` or `ABSTAIN`. One confirmed violation is decisive even when
   other evidence is unavailable; reference completeness remains separate.
3. Distinguish the best observed reference-feasible design from the exact best
   in a sufficiently resolved complete set. Missing evidence on a candidate
   with no confirmed violation withholds exact regret. A confirmed-infeasible
   candidate can be excluded despite unrelated missing evidence.
4. Separate construction from evaluation. Freeze, reconstruct, search and
   persist all four commitments before a reference session can be created or
   imported. Bind reference plans and evaluation to the exact construction
   identity.
5. Enforce solver execution spending before dispatch with a durable SQLite
   campaign ledger. Reserve all cases atomically, allow 48 initial executions
   plus at most 12 registered retries, permit one retry per eligible case,
   preserve reservations across restarts, reject concurrent oversubscription,
   and bind each campaign attempt to its output directory.

## Compute interpretation

The 0.4 core-hour-per-case value is a planning estimate: 19.2 core-hours for 48
initial cases and 24.0 core-hours at 60 cases. It is not the enforced maximum.
At 2 CPUs and a 3600-second limit, configured allocation ceilings are 96 and
120 core-hours respectively. The CPU flag does not measure actual CPU use, and
orchestration, container, storage and artifact-processing overhead require
separate measurement.

No counted CFD is authorized by this record. The compute/spend owner must
explicitly approve the corrected 48+12 execution policy and 120 allocated-core-
hour hard ceiling; the science owner must approve the frozen synthetic
constraints, condition/design set, control assumption and comparator policy.

## Maturity ceiling

Implemented/tested DEVELOPMENT machinery and analytical fixture evidence only.
No population reliability, learned-model design-quality advantage, scientific
qualification, customer acceptance, production qualification or LIVE authority.
