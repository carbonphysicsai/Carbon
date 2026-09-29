# Battery journey H: what the validator observed

**What this is.** It is the validator's half of the evidence for H, the live
battery miner journey through the Control Center browser UI.
- Launchpad ran H and records the miner side.
- This document records what the battery validator daemon did, **in its own
  terms**. It is read from the daemon's state and event log, read-only.
- The Control Center consumes the deployment and never writes to its state.
  Neither did this lane.

**Maturity.** A completed journey is engineering evidence only. It is not a
qualified Challenge, and it grants no scientific, security or production
qualification.

**Not published here.** Private operator evidence keeps:
- the rebuild seed, which is validator-chosen randomness;
- the miner hotkey;
- the score values.

## Before H

A read-only snapshot was taken at 12:00:42Z on 2026-09-29. H launched at
12:00:41Z and had not submitted.

| | State |
|---|---|
| Pool | version 0, `OPEN`, 3 `ACTIVE` screening batches with `COMPLETE` references, **admitted 2** |
| Submissions | 2, both `SCORED`, from tier 3A (`BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`) |
| Finalist set | the only one, `pfinal-T00`, `CONSUMED` by 3A's final |
| Events | 20 |

**H's stated preconditions no longer held.** The handoff said "admitted 0"
and "`pfinal-T00` PREPARED". Tier 3A had changed both before H ran. Nothing
was re-prepared or re-ingested.

## What happened

H made one `battery_submit`, signed by the registered UID 1 miner hotkey.

| Event | Time (UTC) | Kind | What it means |
|---|---|---|---|
| 21 | 12:11:48 | `admitted` | The daemon admitted the submission after authenticating the transport. It recorded no refusal and no failure. |
| 22 | — | `state: RECONSTRUCTED` | The recipe was rebuilt through the validator path, with the validator's own seed |
| 23 | 12:14:34 | `scored` | Scored on **pool version 0**, 163 s after admission |
| 24 | — | `final_frozen` | Nominated against the incumbent. The final is frozen. |
| 25 | — | `rotation_pending` | Rotation was due and no screening batch is prepared |

### Admission

**It was admitted, not refused.** The submission was recorded with state
`ADMITTED` and `failure: null`. What the binding records:
- the Challenge and contract digest;
- the recipe and strategy hashes;
- the rule, calibration, OCV-table and TRAIN v1 digests;
- the implementation and plan digests;
- the transport receipt;
- the envelope: 400 TRAIN cases, float32, 2 worker CPUs, 4 GiB memory, no
  swap, and a 600 s deadline.

### `commitment: null`, and why

The binding records `"commitment": null`. **This is not a commitment path
that happens to be empty. No commitment path exists.**
- The daemon's admission check (`carbon/battery/daemon.py:400-418`) reads a
  chain commitment only when `require_commitment` is on and a reader is
  present.
- The deployment builder always passes `commitments=None`
  (`carbon/battery/deployment.py:152`), so the live deployment runs
  `require_commitment: false`.
- **A successful H submission therefore does not show that a miner's
  on-chain commitment was checked.** The chain path, OD-7(a), is not built.
  See `BATTERY_MINER_SUBMISSION_PATHS.md`.

### Where it was signed and evaluated

**Submission signs in-process today.** The miner's hotkey is opened, and
`battery_submit` is signed, inside the Control Center process
(`carbon/battery/campaign.py:343-347` and `:625-627`).

**Evaluation runs in the same process.** The call goes through
`gateway.receive` to the evaluation (`:628-632`), on the host that holds the
validator's secrets.

So H demonstrates the journey **on this host**. A miner on their own machine
cannot yet reach this validator (`BATTERY_MINER_SUBMISSION_PATHS.md`).

### What was rebuilt

| | |
|---|---|
| Backend | `ISOLATED_CARRIER`, `validator_path: true` |
| Worker image | `sha256:f33ce0053adef1dad94db7d2fa7d58f4cf3915fc2dce426c7337732317f43014` |
| Seed | chosen by the validator; recorded in the daemon's model row and private evidence, not published |
| Retained model | its state digest, the recipe digest and a fit record (compile and train time, parameter count and digest, final loss) |

### What was scored

| | |
|---|---|
| Eligible | yes |
| Gates failed | none |
| Cases | 300 scored, 0 reference-invalid, 0 infrastructure-failed |
| Pool version | 0 |
| Score values | recorded by the daemon; not published here |

**No infrastructure failure occurred.** Had one occurred, the daemon would
have typed it as `FAILED_INFRA`, never as a score (M3-D14).

### After scoring

- **Final.** The submission was nominated against the incumbent.
  - `final-2a26393aaaca42575c31ca85` is `FROZEN`, with no finalist set.
  - The only finalist set was consumed by 3A's final. So when the daemon
    processes this final, it reports `WAITING_FOR_FINALIST_SET`
    (`daemon.py:715-730`).
  - This is a typed waiting state, not a failure.
- **Pool.** It is `ROTATION_PENDING`: admitted is 3, and no screening batch
  is `PREPARED` (`pool_store.py:458-470`). The next submission queues and is
  not scored until a batch is prepared.

### What the validator retained

Relative to the 12:00:42Z snapshot:
- one submission row;
- one model;
- **300 predictions** (1,000 → 1,300);
- one score record;
- one frozen final;
- two worker operations;
- **five events** (20 → 25).

## What unblocks the next step

**Preparing new batches is the owner's call.** Scoring anything further, or
deciding H's final, needs:
- a prepared screening batch with complete references, for the pool;
- a prepared finalist set, for the final.
