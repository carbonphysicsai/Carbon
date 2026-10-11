## 2026-10-10 — MOTOR-NEURAL-01: Motor gains an MLP and a DeepONet through Carbon's shared trainers, fail closed where nothing serves them yet

**Authority.**
- **The direction.** The Test Lead, under OWNER-DEV-AUTONOMY-01. Motor's only
  family, the kernel ridge, is the same class as its cheap baseline, a
  Kriging/RBF response surface. A comparison against that baseline could not
  tell them apart.
- **The expansion.** It is recorded under OWNER-CHALLENGE-ADMISSION-01 §6.1
  as expansion record `electric-motor-magnetics/0001.json`.
- **Why Level 0.** A development variant cannot add a family: its base
  compile refuses a backbone the miner-facing contract lacks
  (`development_variants.compile_development`).
- **The scope.** DEVELOPMENT only. There is no tolerance, threshold,
  qualification or value claim, and no spend.

**Decision.**
- **Two neural families,** `mlp` and `deeponet` (`carbon.motor.neural`):
  - **inputs:** the eight registered inputs, scaled to [-1, 1] by their
    bounds, as the kernel ridge scales them;
  - **output:** the torque at the 60 angles of one period, standardized per
    angle over TRAIN;
  - **the DeepONet's trunk** runs over the angle, normalized to [0, 1).
- **One shared mechanism.** Both families train through Carbon's shared
  trainers, `carbon.battery.training.train` for JAX and
  `carbon.battery.torch_training.train` for PyTorch, with Carbon's
  reconstruction seed (backend parity).
  - Every trainer setting no motor surface sets is the battery default,
    copied into `TRAINER_FIXED`, so a battery change never moves motor
    silently.
  - Precision is float64, the motor envelope's.
  - Predictions keep the kernel ridge's output rule: a motoring curve's mean
    is not negative.
- **A finite Level-0 menu,** as motor's catalog requires:
  - width 64/128/256, depth 2/3/4, activation gelu/tanh/silu;
  - steps 500/1000/2000/4000, learning rate 5e-4/1e-3/2e-3/5e-3;
  - basis functions 8/16/32 (DeepONet only);
  - backend jax/pytorch.

  The defaults are width 128, depth 3, 2,000 steps, rate 2e-3, gelu, 16
  basis functions and jax. These are engineering choices, not quality
  claims.
- **The implementation.** Version 2.0 pins `neural.py` and both shared
  trainers. The kernel ridge's own sources and numerics are unchanged.
  `compile.rebuild` requires a seed for a neural family and refuses one for
  the kernel ridge.
- **Fail closed where nothing serves them yet:**
  - **Practice.** The research session's practice worker is the numpy image,
    so `MotorPractice.backend_refusal` refuses a neural recipe as
    `backend_not_served` before anything starts or is charged. The `session`
    lane stays `kernel_ridge`.
  - **The validator.** The public and hidden motor adapters refuse a neural
    recipe as `motor_neural_family_not_served` (`Unavailable`). It is never
    recorded against the miner, never a score, and uses no hotkey window.
    This is option A, the Test Lead's choice. Battery's validator already
    rebuilds through the same shared trainers, so the review is a delta
    review of their reuse for motor, not a new surface. The Test Lead
    schedules it with the Carbon Validator after motor's evidence lands
    (AGENTS.md §13).
- **The training budget adapter.** `carbon.motor.training_budget.MotorAdapter`
  is registered, and motor's gap is closed:
  - a neural recipe is one full-batch program;
  - the kernel ridge trains no program;
  - an equivalence margin, a finalist rule and a generator are named gaps.

**Evidence (practice, not a claim).** At the defaults, on public TRAIN (150)
scored on public PRACTICE (30), every family passes motor's exam gates:

| Family | Score |
|---|---|
| kernel ridge | 0.173 |
| MLP, JAX | 0.255 |
| MLP, PyTorch | 0.249 |
| DeepONet, JAX | 0.249 |
| DeepONet, PyTorch | 0.250 |

Lower is better. Each rebuild is bit-reproducible at its seed, and the two
backends have equal parameter counts. Graphite's lessons are separate.

**Next.**
- wire a JAX and PyTorch practice image for Motor and open the `session`
  lane (a new expansion record);
- review the validator's neural rebuild;
- add Graphite's motor scoring;
- an FNO over the angle.
