# Motor pilot v1: what ran

**Run.** 2026-10-02 05:04-08:04 UTC, on the owner's local host.
- Six cases ran in parallel, each in its own container with no network, two
  CPUs and one BLAS thread.
- The run was attempt 3. Attempts 1 and 2 were stopped and left no records
  (ticket D3, D3a).
- `run.log` lists the SHA-256 of every source and of the frozen plan at
  start. Two edits make it acceptable to the repository: its one host path
  is shortened to `<host>/`, and trailing spaces are removed. Nothing else
  in it is edited.

**The image** is `carbon-motor-reference:dev`, local ID
`sha256:85c337abf8e2ae83e8a347977aa1b5c9ab965df98ca6340b32cdc435227feaed`,
built from `scripts/dev/motor/reference/Dockerfile`. That Dockerfile is
byte-identical to the one the pilot used.

**The committed sources differ from those that ran only in form.** Three
steps applied to the run-time sources (`run.log` hashes) give the committed
files byte for byte:
1. strip carriage returns (`sed -i 's/\r$//'`). The run-time `getdp.py`,
   `run_batch.py`, `run_sweep.py` and `pilot_plan.py` had CRLF line endings
   from an editor on another host;
2. `ruff format` (ruff 0.16.3, the repository's configuration);
3. in `mesh.py`, rename the unused unpacked name `opening` to `_opening`
   (Ruff RUF059).

This was checked for `domain.py`, `getdp.py`, `mesh.py`, `analytic.py`,
`population.py`, `run_batch.py`, `run_sweep.py`, `pilot_plan.py` and the
Dockerfile. None of the three steps changes behaviour, and the pools ran
on the committed form.

**The plan.** `plan.json` is the runner's copy of the frozen plan
(`run.log`: `plan.frozen.json`, SHA-256 `853c17d2…`). It holds 8 ordinary,
4 difficult, 4 refined and 1 angle-resolution case, all from public draws.
