# EVIDENCE-PRODUCER-STAGES-01: Data Collection's campaign stages (frozen v1)

The campaign runner (EVIDENCE-CAMPAIGN-RUNNER-01, #1080) calls one pinned
stage module per task. This document freezes the producer side for battery
v3, motor 10p/12s and f02: the `reference` and `train` stages, their outputs
and receipts. The optimizer builds the `assemble` stage against it (Test Lead,
2026-10-11). This is DEVELOPMENT orchestration only. It grants no spend,
scientific qualification, security acceptance or LIVE use.

## Module and context

`carbon.development_comparison.campaign_adapters.producer` (plan rows pin its
bytes) serves every `reference` and `train` task of the three families. It
refuses (exit 2, `failure.json` with a typed `code`) unless:

- the context is the runner's closed `…v1.stage-context`, scope
  `PUBLIC_DEVELOPMENT`, phase `reference` or `train`, `shard` 0 of `shards` 1
  (sharding is not registered in v1);
- its `entrypoint_registration_digest` equals `campaign_entrypoints.digest()`,
  the family/phase row is registered and `inspect()` finds its module and plan
  bytes unchanged;
- every helper file in `producer.PINNED` has its pinned sha256;
- the vCPU allotment, read from the runner's `OMP_NUM_THREADS`, is at least
  2 (battery, f02) or 3 (motor). *Optimizer follow-up:* put `vcpus` in the
  context so this stops relying on the environment.

Inputs are refused unless registered. The only registered input is a reuse
bundle for a battery (required) or motor (optional) `reference` stage:
`reuse_records_NNN`, role `HELDOUT_REFERENCE`, each a
`carbon.development-evidence-campaign.producer-records.v1` document
`{schema, family, chunk, records: [{dir, record}]}`. `dir` must be a
registered run directory (battery: tiers 1–4, `bfeas-t6r3`, `bmid-a`,
`bmid-r2`, `bmid-r3`). Bundles are chunked because the runner reads every
input and output as one JSON document of at most 32 MB.

Exit 1 (`FAILED_INFRA` to the runner) is an infrastructure or reference
failure: a step that exits non-zero, a plan job without a record, an export
that main refuses, or a missing meter. It is never a candidate result.

## Steps (registered entrypoints and pinned helpers only)

| Family | `reference` | `train` |
|---|---|---|
| battery-v3 | overlay from the lock (`truth_env.materialize`/`verify`); `battery_v3 check/solve --kind panel-a` into `bmid-a`; #965 rung-2 then rung-3 plans (`middle_bands_refine.py`) solved into `bmid-r2`/`bmid-r3`; `v3_panel_export.py --campaign` | overlay; `battery_v3 check/solve/export-train --kind train` |
| motor | not registered yet: refused `ENTRYPOINT_NOT_REGISTERED` until the reference-panel plan lands after amendment 4 | `motor_10p12s check/solve/export-train --kind train-stage1` (two CPUs per case) |
| f02 | `f02 plan/solve --kind menu`; `f02_menu.py plan-refine` and `run` (the registry's mesh-2 and dt/2 re-solves within 1 C of 95 C); `f02_export.py` | `f02 plan/solve/export-train --kind train` |

Battery and f02 solvers get `vcpus − 1` CPUs and motor gets
`(vcpus − 1) // 2` cases at two CPUs each, leaving one CPU for host work.
Every plan job must end with a record (any status). Non-OK solver records are
reference results that stay in the return; the export decides what they
mean.

## Outputs (artifact names are the receipt keys)

| Phase | Artifact | Role | Content |
|---|---|---|---|
| reference | `panel-export` | HELDOUT_REFERENCE | the sealed `carbon.design-search.solved-panel-export.v1`; `producer_panels.adapt_export` on current main accepts it |
| reference | `reference-records-NNN` | HELDOUT_REFERENCE | `producer-records.v1` chunks: every raw record behind the export (battery: reused + new run records by directory; f02: the solve ledger) |
| train | `train` | PUBLIC_TRAIN | `carbon.development-evidence-campaign.producer-train.v1`: `{schema, family, record_schema, jsonl_sha256, records, export}`. `records` are the kit TRAIN rows. The kit's JSONL bytes are `"".join(json.dumps(r, sort_keys=True) + "\n")`, and `jsonl_sha256` is their sha256 |
| train | `train-records-NNN` | PUBLIC_TRAIN | raw solver records (f02: the ledger) as `producer-records.v1` chunks |
| train (f02) | `train-diagnostics-NNN` | PUBLIC_TRAIN | crossing times and histories, never in a row's values |
| both | `stage-summary` | ANALYSIS | `producer-summary.v1`: entrypoint row, vCPUs, every step's argv/exit/wall, counts (plan sha256s of refinement rungs, export digest), meter detail |

The receipt is the runner's `…v1.stage-result`: `status` OK, `core_s`,
`peak_ram_bytes` and the artifact pins above.

**Record schemas** pass through unchanged: `carbon.battery.feasibility02-record.v1`,
`carbon.motor.feasibility02-record.v1`, the f02 ledger rows, and the kit
TRAIN rows `carbon.battery-v3.train-record.v1`,
`carbon.motor-10p12s.train-record.v1` and `carbon.f02.train-record.v1`.

## Metering

The stage starts a sentinel container under a new cgroup-v2 parent
(`--cgroup-parent`). Every solver container joins that parent through
`CARBON_STAGE_CGROUP_PARENT`, which the three runners read; unset, their
docker command is unchanged. `core_s` = the parent's `cpu.stat usage_usec` +
this process's host children (`RUSAGE_CHILDREN`). `peak_ram_bytes` = the
parent's `memory.peak` + the largest host child's maxrss. Both are
conservative sums. A host without cgroup v2 or `memory.peak` fails the stage.

**Runner note.** The runner SIGKILLs the stage's process group at its wall or
euro cap, so the stage cannot clean up. Containers are not in that group. A
detached watchdog therefore stops every container under the stage's parent
once the stage process is gone. *Optimizer follow-up:* send SIGTERM with a
short grace before SIGKILL.

## Working decisions (Data Collection; Test Lead notified)

1. **f02 contract.** Menu v2 (16 actions × 24 contexts), per the Test Lead's
   2026-10-11 decision (b). The optimizer revises the equal-budget
   registration and `adaptive_arms` prospectively.
2. **f02 export.** One plain question per context, as the f02 kit (#1036)
   expects: condition = context id; bank = the 16 menu actions; objective =
   most `extra_energy_j`; limit `peak_top_c` ≤ 95 C with the registry's 0.5 C
   band. The f02-round2 question law is HUMAN_INPUT: no variant is drawn, and
   context mass is uniform (UNREGISTERED). E = 5 and k = 8 are the law's
   development recommendations.
3. **Settlement.** The producer computes per-candidate verdicts
   (`scripts/dev/evidence_runs/settlement.py`, method
   `two-rungs-same-side-change-below-band.v1`) and seals them with an
   export-level `refinement_rule`.
   - Battery uses the two finest rungs (Test Lead ruling (a)).
   - f02 needs every rung on one side and a spread below the band (the
     registry's all-rungs rule plus the method's change test).
   - A question keeps `refinement_demand` true while an in-band candidate is
     unsettled.
   - `v3_panel_export.build()` without `settle` reproduces the historical
     export unchanged.
4. **Battery #965 refinement.** Section 7 of
   `question-laws/battery-v3-middle-bands-panel.md`, applied to the drawn
   requirement range:
   - **Relevance:** a standard result within two working bands of any drawn
     limit, i.e. 41.5–46.0 C or −4 to 6 mV.
   - **Rung 2:** one per relevant tuple without a reused rung 2.
   - **Rung 3:** only where standard and rung 2 straddle a drawn limit or
     differ by at least the band. Ranked by rung-2 distance to nominal, with
     the stage-A ceiling of 60.
   - Stage B (frontier fill) is not part of this stage; it needs its own
     accepted plan.
5. **Reuse** of host records is by pinned bundle, never by host path. A
   server stage without a bundle re-solves the registered plan.

## Motor (pending)

The motor reference stage needs a committed reference-panel plan covering the
complete command-angle-skew panel. That plan follows the amendment-4 skew and
bisection results, plus per-candidate settlement in `panel_export.py`. Until
then the stage refuses, and #1080's inventory keeps `motor/reference`
`NOT_REGISTERED`.
