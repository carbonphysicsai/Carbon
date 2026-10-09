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

**The Level 4 B′ leg** (`level4/PHASE1_PLAN.md` §3, plan PR 9) is opt-in. A
record without it runs exactly as above.

- **Before any spend, on the CPU.** `level4-lower` lowers each pick and the
  coverage recipe (a relu MLP, so a named function runs on the GPU) into
  `carbon.level4.staging` directories under
  `docs/development/graphite/level4/a40_leg/`. Commit them and push.
- **Seal.** `select --level4 --record R` pins each recipe's submission digest,
  files and review ops in the record. A missing directory is a refusal.
- **On the pods.** JAX pods only. The coverage recipe joins the native
  recipes, and each recipe gets ONE B′ rebuild in a fresh interpreter, from
  the committed documents (shipped as data, refused unless the digest is the
  record's): verify, G4 under the owner's caps, Carbon's own training loop.
- **Smoke.** The smoke measures the leg on the same pick
  (`level4_wall_seconds`), and the deadline counts the leg's rebuilds at that
  measurement.
- **Compare.** `compare` adds a `level4` section, digest equality only:
  - same host, B′ `params_sha256` against the native rebuild;
  - across hosts, B′ against B′ (`params_sha256`, `outputs_sha256`), refused
    on a driver mismatch.

  A mismatch is a recorded R1 finding, not a harness failure.
- **Forward-only kNN.** `gather` and `sort` appear only in the
  nearest-neighbour graph, which Carbon does not train, so it runs
  forward-only (`level4_knn_forward`). Its same-host check is inside the one
  rebuild: the rebuilt graph against the JAX function it was lowered from,
  both jitted. Battery's NumPy kNN differs at 1e-15 (Phase 0); that
  difference is recorded, never compared.
- **Spend.** The leg runs only under a grant that names it.

Credentials: `--key-file` is a path; the key is read only by the operator
adapter into its request header, never printed or put in an environment.

Assumptions to confirm: the torch-gpu image has `/opt/carbon-worker/bin/python`
(the accelerator image's start command is reused); the smoke measures the jax
largest pick, so the PyTorch fno at default settings may run longer than the
x1.5 margin; six pods at the grant's 2.0 h do not fit USD 4.25, so the measured
deadline must be under about 1.35 h.

Rulings applied (Test Lead on #739): every pod waits at a barrier (POST /go on
port 8001, per-pod token) until both pods of a backend have recorded identity and
a good probe and their driver builds match; a persistent mismatch releases no
rebuild. Deadlines are per backend: `smoke --backend jax` and `smoke --backend
pytorch` (one fno rebuild); `run` takes `--smoke-record` and
`--smoke-record-pytorch`, and the cap gate applies per backend with the
4 pods + 2 replacements arithmetic. The run record states the skip directions.
