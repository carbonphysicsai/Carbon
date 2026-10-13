# OPT-15c synthetic campaign CPU job specification (not launched)

Development only. Data Collection owns any launch and cost authorization. The
job may use only `physics-example.json`, a prospectively fixed synthetic axes
file, and the Validator's registered candidate-file digest. It must not mount
EV4, a solved bank, the Test Engineer's final holdout, AX42 paths, or secrets.

## Measured sizing and cap

One local WSL toy profile across the ten candidate proxies took 24.28 CPU-s
and 25.84 wall-s (2026-10-13, `campaign-run`, seven physics-switch rows per
candidate, four value strata). At that observed rate, 5,000 profiles cost about
33.7 CPU-hours before overhead; 20,000 cost about 134.9 CPU-hours. This is a
size estimate from one profile, not a throughput guarantee. The owner supplied
a planning price of $1.76/h for a 32-vCPU RunPod CPU host on 2026-10-10; Data
Collection must verify the actual price and available host before launch.

Start with a **100-profile pilot**. The launcher records measured CPU-s,
wall-s, host type, hourly price, and peak RAM. Launch the 5,000-profile tranche
only if its refreshed estimate plus startup/teardown reserve fits a strict
**$10 total cap**, including the pilot. Stop and report if it does not. Do not
start the 20,000-profile tranche under this cap without a fresh estimate and
separate authorization. The cost ledger must terminate remaining shards before
the cap, never merely warn after crossing it.

## Shards and receipts

Use 32 disjoint deterministic shards. For each shard, run `campaign-plan` from
the same fixed base config and axes with `--count 5000 --seed <registered seed>
--shard <0..31> --shards 32`, then `campaign-run --plan <that shard's JSON>
--candidates <digest-checked candidate module> --out <shard-result JSON>`.
Checkpoint each shard result by `(plan_sha256, candidate_sha256, shard, shards)`;
resume skips only matching completed receipts. Reject duplicate or overlapping
row indices. Preserve all typed refusals and cost records. Gathered output is
aggregate synthetic development evidence only; no winner is selected by the
launcher.

This specification is **not launch-ready** until the full §2 A–G toy lever
grammar, candidate digest, host price, and launcher cap binding are registered.
The current eight-axis example exercises a subset and is for fixture/pilot
sizing only. D3-dependent EV4 fitting and the final held holdout are separate
later runs and cannot enter this CPU job.
