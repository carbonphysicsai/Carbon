# Refused-capability log (Graphite)

DEVELOPMENT, LOG ONLY. Each row is one refused proposal or one filed capability wish, keyed by Challenge and level. It widens nothing: no capability reaches any run. Names and out-of-range values only; no seed, key or hidden material. A wish is the Constructor's words, stored as data.

Rows are appended by `carbon/agent_campaign/graphite/capability_log.py` when `CARBON_CAPABILITY_LOG` names this file; earlier rows are backfilled from the cited sources.

| When (UTC) | Challenge | Level | Run | Proposal | Kind | Status | Code | Field | Requested | Optimisation | Needs | Expected gain | Evidence | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D2 | p-c41a9a1ebb82 | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | steps | 30000 |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D2 | p-8d5d61fc1308 | refusal | REFUSED_UNREBUILDABLE | parameter.dependency_unsatisfied | ensemble_members | 3 (steps 14000, not divisible) |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D3 | p-69268f1b74ec | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | weight_decay_mask | weights |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D3 | p-5a3b8fe3c06f | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | normalization | layer |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D3 | p-22e81b9d0595 | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | ensemble_members | 5 |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | E1 | p-1585ecbf838a | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | ensemble_members | 5 |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | E1 | p-37985e699fe3 | refusal | REFUSED_UNREBUILDABLE | parameter.domain_mismatch | steps | 24000 |  |  |  |  | stage A extract (backfill) |
| 2026-10-10 | battery-fastcharge-ageing-development-v1 | 0 | D3 | p-74b8c69ead59 | refusal | REFUSED_BACKEND_NOT_SERVED | backend_not_served:pytorch | backend | pytorch (backbone fno) |  |  |  |  | stage A extract (backfill) |
| 2026-10-11 | battery-fastcharge-ageing-development-v1 | 2 | L2 E | p-4e02e0f7c41a | refusal | REFUSED_UNREBUILDABLE |  |  |  |  |  |  | result digest only; cause not in the extract | executor report, 2026-10-12 (stage A L2-L4 extract, backfill) |
| 2026-10-11 | battery-fastcharge-ageing-development-v1 | 3 | L3 F | p-37985e699fe3 | refusal | REFUSED_UNREBUILDABLE |  |  |  |  |  |  | result digest only; cause not in the extract | executor report, 2026-10-12 (stage A L2-L4 extract, backfill) |
| 2026-10-11 | battery-fastcharge-ageing-development-v1 | 3 | L3 F s2 | p-8e47250e297c | refusal | REFUSED_UNREBUILDABLE |  |  |  |  |  |  | result digest only; cause not in the extract | executor report, 2026-10-12 (stage A L2-L4 extract, backfill) |
| 2026-10-11 | battery-fastcharge-ageing-development-v1 | 3 | L3 F s3 | p-891e0fd1ebdb | refusal | REFUSED_UNREBUILDABLE |  |  |  |  |  |  | result digest only; cause not in the extract | executor report, 2026-10-12 (stage A L2-L4 extract, backfill) |
| 2026-10-11 | battery-fastcharge-ageing-development-v1 | 4 | L4 G s2 | p-839de482ac6b | refusal | REFUSED_UNREBUILDABLE |  |  |  |  |  |  | result digest only; cause not in the extract | executor report, 2026-10-12 (stage A L2-L4 extract, backfill) |
