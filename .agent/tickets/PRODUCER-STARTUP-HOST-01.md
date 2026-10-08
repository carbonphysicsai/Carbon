# PRODUCER-STARTUP-HOST-01: a dedicated startup host for bank fills

**Status:** plan. Security-sensitive (AGENTS.md §13): it moves hidden cases to
a second host. It needs a dedicated review, and an owner custody record
confirmed directly in the Carbon Validator session before any export runs.

**Authority:**
- the owner, 2026-10-08, relayed by the Test Lead: "I want a dedicated server
  for bank start up on all 8 challenges and all future challenges … I can't
  be waiting 6 days.";
- OWNER-BANK-ARCHITECTURE-01;
- OWNER-SHARED-ANSWER-KEY-01.

The server choice is the owner's and the Test Lead's.

**Executor:** the Carbon Validator session.

## The gate: custody, first

The startup host holds hidden cases while it solves them, which extends the
AX42's custody domain. That is a security acceptance, so it is the owner's.
- `shard export` refuses (`startup_custody_unrecorded`) unless a decision
  record, **OWNER-STARTUP-HOST-CUSTODY-01**, names the host (by its SSH
  host-key fingerprint) and its scope.
- The owner confirms that record directly in this session; a relay is not
  enough.
- The record is drafted with slice 2's runbook.

## Design

### Slice 1: the sharded solve (`challenge_validator/startup_shard.py`, producer-only, Challenge-neutral)

It works at the level every solve already shares: a work directory's
`jobs.json` (`{fingerprint, jobs: [{case_id, ...}]}`) and its
`records.jsonl`. That covers battery pool and bank tranches, the Q3 lattice
and its refine, tuning and study sets, and motor and cooling sources.

**`split --work W --shards N --out D [--challenge C]`**
- **What it writes:** shard `k` gets `D/shard-k/jobs.json`, holding only
  jobs with no terminal record in `W` yet. Every job is in exactly one
  shard, and shards are balanced by count.
- **Each shard's manifest:** the work fingerprint, the shard index and
  count, a digest over its jobs, the code commit, the truth image digest and
  the overlay digest. Its `jobs.json` also carries a `shard` field: the
  manifest's digest.
- **The journal:** `W/startup-journal.jsonl` gets `shard_written`.
- **Idempotent:** a re-split of the same `W` writes the same shards.
- **Whole-startup mode:** `--shards 1`, where the host solves everything.

**Solving on the startup host:** each Challenge's existing solve command,
unchanged, with the same pinned image, code tag and overlay:
- battery: `tuning solve --work shard-k --overlay O --workers N`;
- motor: its source's `run_batch`.

It is resumable, as those already are.

**`merge --work W --shard D/shard-k [--challenge C]`** accepts a shard's
records only if:
- the shard's manifest is the one `split` journaled for `W`: same digest,
  same code, image and overlay;
- every record's `case_id` is one of that shard's jobs, its inputs equal the
  job's, and its status is one of the Challenge's terminal statuses.
  `FAILED_INFRA` is skipped, and left for a re-split.

It is **duplicate-safe:**
- a case already holding an identical terminal record is skipped;
- a different terminal record for the same case is **refused**
  (`startup_record_mismatch`), and nothing from that shard is appended.

Accepted records are appended to `W/records.jsonl`, and the merge is
journaled (`shard_merged`: count and records digest). Then the normal
`seal` or `ingest` runs, so nothing downstream changes.

**`status --work W`** shows public counts per shard: jobs, merged, pending.

### Slice 2: the custody runbook (owner-run; no agent access to either host)

The startup host is set up like the AX42:
- the `carbon-producer` account, an owner-only 0700 state directory;
- ufw SSH-only, fail2ban, key-only SSH;
- the released code tag and worker image, pulled by digest.

**Transfers.** Each one is an owner-run `rsync` over SSH between the
`carbon-producer` accounts, pinned by host key. Each is journaled on the
AX42 (`startup-journal.jsonl`: direction, shard digest, byte count).
1. **AX42 → host:** the shard directories, and the truth overlay, only for
   the duration of a startup.
2. **Host → AX42:** `records.jsonl` per shard.
3. **After merge:** the host's shard directories and its overlay copy are
   wiped (`shred`), and the wipe is journaled.

**Backups:** the startup host holds nothing between startups, so it needs
none. The AX42's Ops 1 backup covers the merged records.

### Slice 3: workers and measurement

- `tuning solve`, `study_sets solve` and `producer solve` take
  `--workers auto`, which is `os.cpu_count()` minus a headroom (default 2,
  `--headroom H`). An explicit number is unchanged, and the default stays 7
  unless `auto` is asked for.
- **Measurement before trusting capacity:**
  - `startup_shard status` reports each merged shard's per-solve wall-time
    p50 and p95, computed from the records' own `wall_s` (public numbers);
  - the runbook's first startup is a timed 200-case battery shard;
  - its numbers replace the estimates in the capacity model.

### Slice 4: capacity

`CAPACITY_MODEL_8_CHALLENGES.md` gains the startup-host term: each
Challenge's (1) startup CPU-h ÷ (host threads − headroom) × measured
slowdown, as wall-days. Today's known terms:
- battery ~620 CPU-h with Q3 (~130 with coarse-then-refine);
- motor ~219;
- the cooling cell ~135;
- photonic ≈ 0;
- f02, f08, f13 and the micromixer stay null until their panels are
  measured.

The server's size is then set by the owner's "not 6 days" target.

## Tests (slice 1)

- **Split:** it covers every unsolved job exactly once, is deterministic,
  skips solved jobs, and records the manifest pins.
- **Merge accepts** a shard's terminal records and skips `FAILED_INFRA`. A
  re-merge appends nothing.
- **Merge refuses:**
  - a record for a case outside the shard;
  - changed inputs;
  - a different terminal record for an already-solved case (nothing
    appended);
  - a shard from another split, or another code, image or overlay.
- **Split → solve (scripted) → merge → seal** equals a single-host solve of
  the same work, byte for byte in `records.jsonl` order-independence and in
  the sealed references digest.
- `shard export` refuses without the custody record.

## Out of scope

- Choosing or renting the server (the owner).
- Any change to what is solved or how it is sealed.
