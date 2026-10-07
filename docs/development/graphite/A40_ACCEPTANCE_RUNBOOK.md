# A40 acceptance harness: runbook

Harness for `A40_ACCEPTANCE_BRIEF.md` under `OWNER-A40-ACCEPTANCE-GRANT-01`.
Code: `scripts/dev/exam_design/runpod/a40_acceptance.py` (operator side) and
`a40_pod_phase.py` (pod phase, shipped through the bootstrap code manifest,
`PHASE_MODULE`). Digest equality only; no tolerance; DEVELOPMENT evidence, not
`validator_launch`. Entry conditions in the grant (decision record on main,
released images, pinned PyTorch GPU configuration, brief section 3 checks) still
apply before any spend. Spend is booked privately, never in the repository.

1. `select --record R` (no spend; needs the science stacks): analytic `n_params`
   for the EV4 neural pool, picks (smallest, lower median, largest; ties by id;
   skip to the next eligible in the rule's direction), the contract-default
   PyTorch-only fno, a cross-check against an actual CPU count on both backends
   (nonzero exit on mismatch), written with `R.sha256` before any rebuild.
   `--stdout` prints the record where files do not persist.
2. `run --record R --local-cpu-dry-run [--backends jax] [--no-docker]`: the same
   per-repeat flow on CPU in a local c03 image if present (nothing pulled), else
   in-process.
3. `smoke --record R --smoke-record S --code-ref SHA --key-file F --work-dir D`:
   one rebuild (the largest pick, jax by default) on one A40 pod; records
   measured start-up and wall seconds.
4. `run ... --dry-run`: prints the plan, deadline (measured x 1.5) and the budget
   gate; creates no pod.
5. `run` (without dry-run flags): 2 hosts per backend, jax then pytorch, via the
   operator layer. Refuses unless (4 pods + 2 replacements) x deadline x
   0.492739726 + 0.25 (+ the smoke reservation) <= cap (`--cap`, default 4.25).
   A failed GPU probe is FAILED_INFRA (one replacement); differing driver builds
   replace the second host once and are otherwise recorded as
   REFUSED_DRIVER_MISMATCH. Every pod is terminated with verified absence and
   both reconcilers must be clean.
6. `compare --results flat.json [--deviation D] [--cpu C]`: offline comparison.

Credentials: `--key-file` is a path; the key is read only by the operator
adapter into its request header, never printed or put in an environment.

Assumptions to confirm: the torch-gpu image has `/opt/carbon-worker/bin/python`
(the accelerator image's start command is reused); the smoke measures the jax
largest pick, so the PyTorch fno at default settings may run longer than the
x1.5 margin; six pods at the grant's 2.0 h do not fit USD 4.25, so the measured
deadline must be under about 1.35 h.
