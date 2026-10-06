## 2026-10-05 — GRAPHITE-L1-BUILD-01: battery Level 1 (loss expressions) built as development-only variants, with an attack adapter and a climb

**Authority.**
- OWNER-GRAPHITE-TEST-WAVE-03 §1 and OWNER-GRAPHITE-DEV-LEVELS-01 F1 ("Drafted
  surfaces OK").
- The Test Lead's review of the Level-1 packet (00fc2fe2), recorded verbatim
  in `docs/development/graphite/reviews/L1_LOSS_EXPRESSIONS_TEST_LEAD_REVIEW.md`:
  APPROVED to build, with answers Q1–Q6 and the signed arm.
- OWNER-GRAPHITE-TEST-WAVE-04 §1 (identity by rebuilt artifact) and §2 (the
  frozen rule's tail coverage accepted for testing U1/U2).
- B1 (#596), the typed-refusal hardening this build is stacked on.

Everything below is an engineering choice within that authority. No
scientific value, threshold, gate, score or tolerance changes. No
miner-facing contract widens: battery's contract still excludes
`objective.loss_expressions`, and every miner door refuses both variants by
name. There are no weights, no chain writes, no live run, no pod, no GPU and
no spend.

**Decisions.**

1. **The language (version 2 of `carbon.loss-expression`).**
   - `carbon/reconstruction/loss_expressions.py` gains:
     - two sorts, case and time;
     - the operations max, min, cap, excess, expm1 (capped), mean_t and
       max_t (with `over`);
     - for the signed arm only, sub, neg, exp and constant leaves.
   - **Version 1 is untouched.** A set that uses none of this keeps version
     1's schemas, documents and digests, byte for byte. B1's pin test holds.
   - **`OperationSet.from_document`** rebuilds a set from its canonical
     document. That is how the worker recompiles an expression.

2. **Two registered variants, one an arm.**
   - **The valid surface, `battery-l1-loss-expressions-v1`,** is the level's
     own variant. It widens:
     - `objective.loss_expressions`, the GA-D6 core and the one field a
       strategy supplies;
     - one permission per operation family (Q2): time reductions;
       max/min/cap/excess; expm1; component terms; wider constants.
   - **The signed arm, `battery-l1-loss-expressions-signed-v1`,** widens the
     core plus `objective.loss_signed_operations`. It is registered as arm
     `signed` and used in the attack panel only.
   - **Built from the code.** Both documents are built by
     `carbon.battery.level1.variant_document`, so the registered policy and
     the code cannot drift. A test compares them.
   - **Records.** Both are pinned in `registry.json` and recorded as
     development expansion records 0000 and 0001.

3. **Arms in W1's registry.**
   - **The registry.** A `current` entry may carry `arm`, a lower-case name.
     `capability_registry.development_variant_registry` admits the key and
     fails closed on anything else.
   - **Selection.** `development_variants.variant(challenge, level, arm)`
     selects an arm by name. `DEV_VARIANTS` and `--level` still resolve only
     the level's own variant.
   - **Running.** `registered(digest)` finds any current variant, the level's
     own or an arm, so a climb or a pod job can run an arm.
   - **Records.** A development record for an arm carries `arm`.
     `newest_record`, `recorded_variant` and `dev_unrecorded` match on level
     and arm.

4. **Permission-only capabilities and ablation.**
   - **No fields.** The five family permissions have no field. A value
     supplied under a family's name is refused
     (`development.permission_only`).
   - **The ablation parameter.** `compile_development(strategy, variant,
     without=...)` leaves capabilities out: the climb's single-permission
     ablation.
   - **The reconstruction signature.** Reconstructions are called as
     `build(value, admitted, granted)`. The expression compiles against the
     operation set its granted permissions define
     (`level1.operation_set(granted)`). Removing a family therefore refuses
     every expression that uses it.
   - **The binding.** It records `without` when an ablation was applied.

5. **The reconstruction (`carbon.battery.level1.reconstruct`), on Carbon's
   host.**
   - **It refuses by code:** a family outside `applies_to` (mlp, deeponet,
     Q5), a backend other than JAX, a menu field beside an expression, and
     any expression refusal (`development.loss_expression.<code>`).
   - **Its record holds:**
     - the canonical bytes and the operation set's document and digest;
     - the families used;
     - the static no-op diagnostics (Q3; never a refusal);
     - the identity rule (WAVE-04 §1: the expression digest is a diagnostic
       only);
     - the label `rebuild: CPU-verified only` (Q6).
   - **Registration.** `development_variants` registers battery's entries at
     import.

6. **Trainer and pod wiring: Level 0 byte for byte main's.**
   - **The modules Level 1 must not touch.** `recipes.py` and `training.py`
     are battery's implementation modules
     (`contracts.IMPLEMENTATION_MODULES`). Their bytes enter every Level-0
     recipe digest, staged file and rebuild digest. They are left exactly as
     on main.
   - **What happened.** A first version edited them to take an optional loss.
     That moved every Level-0 recipe digest, and Data Collection's run-5 pin
     caught it (#611 CI shard 1). Invariant 10 forbids silently
     reinterpreting past evidence.
   - **The Level-1 trainer is its own module, `carbon/battery/level1_training.py`.**
     - Its `train` is `training.train` line for line, except for the
       signature, the docstring and the per-case loss. A test rebuilds it
       from `training.train`'s source with that one edit and compares, so it
       cannot drift.
     - `LossMLP` and `LossEnsemble` subclass `recipes.MLP` and
       `recipes.Ensemble`. They never use the classic loop, and they refuse
       the PyTorch backend.
     - `build` refuses the knn and fno families.
   - **The pin test.** `tests/cpu/test_battery_level1.py::test_level0_rebuild_artifacts_are_mains`
     pins Level 0's identities as computed on main 74ef52882:
     - the implementation digest;
     - the scaffold and run-5 baseline recipe digest;
     - a Level-0 built record's digest;
     - the program digest.

     It also checks that no Level-1 field or file appears at Level 0, not
     even as null.
   - **`BatteryScoring.built_from`:** for a development construction whose
     reconstruction carries an expression, it stages:
     - the expression's canonical bytes;
     - the operation set's document;
     - `loss_expressions.py`, `loss_terms.py` and `level1_training.py`.

     It also selects the Level-1 program and labels the record.
   - **The Level-1 program** is the Level-0 GPU program with its build line
     replaced (`carbon.battery.level1_worker`). The worker recompiles the
     expression from bytes and trains with `level1_training` in JAX only
     (R2).
   - **No other changes.** `pod_phase.py` and `experiment.py` are untouched.

7. **The attack adapter (battery, 1).**
   - **Registration.** It lives in `carbon/agent_campaign/attack/adapters/battery_level1.py`.
     Its `contract_digest` is the valid variant's digest, read from the
     registry as data, so a registry problem never breaks adapter import.
   - **Families:**
     - `l1_permission_ablation`;
     - `l1_expression_surface`;
     - `l1_degenerate_losses` (Q3);
     - `l1_nonfinite_typing` (R1, with the signed arm);
     - `l1_rebuild_identity` (R2);
     - `l1_declarative_only`.
   - **Seams** cover feedback paths, fresh cases, and U1/U2 alignment
     (WAVE-04 §2: a testing acceptance, not a scientific qualification).
   - **Controls.** Trained controls are MLPs. Held-out controls are DeepONets,
     so they are canonically distinct.
   - **The Level-0 seam** `level_1_loss_expressions` is retired.
   - **The CPU trial.** Two families use a CPU practice trial: Carbon's pod
     phase run locally for 32 steps and scored by the frozen rule. No pod,
     GPU or spend.

8. **The climb.**
   - **What `battery_level1.climb_report` runs:** the valid panel against the
     attack panel under Level 0 and Level 1; one ablation per Level-1
     permission; combined attacks pairing an all-families expression with
     ten Level-0 permissions; and a clean rebuild.
   - **The signed arm** has its own plan: a baseline panel and its attacks,
     with negative loss under hard-example weighting as the combined attack.
   - **Evidence.** `scripts/dev/l1_climb_report.py` writes the evidence
     report, `docs/development/graphite/L1_CLIMB_REPORT.json`.
   - **What the report claims.** No level TESTED, nothing open.

9. **The must-prove obligations, each with a test and a mutation**
   (`tests/cpu/test_battery_level1.py`):
   - **R1.** Non-finite training is GATE_FAILED, never FAILED_INFRA. The
     mutation is a worker that drops non-finite predictions.
   - **R2.** JAX only, and two fresh processes rebuild the same parameters.
     The mutation is a numpy-tolerant factory.
   - **R3.** Every compile refusal is typed on the host before any pod. The
     mutation is an unchecked reconstruction.
   - **Q3.** Degenerate losses run as the candidate's own result. The
     mutation is a reconstruction that refuses no-ops.

10. **B10, the 1024-node measurement (Q1).**
    - **The script.** `scripts/dev/l1_rebuild_measure.py` measures 512 and
      1024 nodes with the shipped code on public TRAIN v1. For each it checks
      bit identity across fresh processes and times the fit against the
      600 s deadline.
    - **The method.** Each run takes random expressions of exactly the node
      limit over the full valid set and recompiles them from canonical bytes.
      Carbon's MLP recipe trains on them (the pinned scaffold, width 64).
    - **The result**, in `docs/development/graphite/L1_REBUILD_MEASUREMENT.json`:

      | Node limit | Parameters identical (3 expressions, 64 steps, two fresh processes) | 2000-step fit |
      |---|---|---|
      | 512 | 3/3 | 18.9 s |
      | 1024 | 3/3 | 69.7 s |

      Both fits are inside the 600 s deadline. Measured on CPU, so this is
      not a GPU or deadline-under-load claim. A larger recipe (width up to
      512, up to 20 000 steps) scales the time.
    - **1024 is not enabled.** The registered limit is 512. Widening is a
      later version, as the Test Lead asked.
    - **The climb evidence** is `docs/development/graphite/L1_CLIMB_REPORT.json`.
      Both arms COMPLETED with 0 findings and 0 infrastructure failures. The
      trial-judged attacks ran real CPU trials.

**Maturity.** Implemented and tested on CPU against the registered variants.
Not scientifically or security qualified. GPU identity is not measured, so
every Level-1 result carries `rebuild: CPU-verified only` (Q6). Until both
the RTX 3060 and one-pod measurements pass, no Level-1 pod result is cited.

**Open.**
- GPU identity: the local RTX 3060, then one pod inside an existing grant.
- Torch wiring with its own rebuild evidence (Q5, later).
- Widening to 1024 nodes in a later version if B10 holds.
- U1/U2 alignment metrics in a live climb.
