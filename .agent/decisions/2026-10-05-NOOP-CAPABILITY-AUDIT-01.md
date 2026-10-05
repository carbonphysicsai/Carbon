## 2026-10-05 — NOOP-CAPABILITY-AUDIT-01: `capacity_fade_head` was never dropped, and a standing audit holds every rebuildable capability to change the trained artifact

**Authority.**
- The Test Lead approved this as its own small PR, inside the owner-approved
  Graphite test wave (OWNER-GRAPHITE-TEST-WAVE-04, -05 and -06).
- The construction contract's own rule, in `carbon/battery/compile.py`
  (`rebuild_issues`) and `carbon/development_session/research_catalog.py`
  (`rebuild_issues`): a supplied field must change what Carbon rebuilds, and
  one the rest of the recipe would ignore is refused by name.

Everything below is an engineering choice within that delegated authority.
No construction contract, expansion record, admission rule, scientific value,
gate, score or tolerance changes. There is no live run and no spend.

**The finding.** Two run-5 battery DeepONet recipes went through Carbon's real
path on CPU (`experiment.admit`, then `pod_phase.built_record`, then the GPU
practice program with `JAX_PLATFORMS=cpu`). They differed only by
`"capacity_fade_head": true`, yet produced the same parameter digest and
byte-identical `predictions.json`.

**Decisions.**

1. **Diagnosis: the flag is not dropped anywhere. `true` is its default.**
   - **The default.** The battery contract registers `capacity_fade_head` as a
     bool with default `True` (`carbon/reconstruction/capability_registry.py`,
     the `physical_structure.capacity_fade_head` entry).
   - **What compiles.** Recipe 1 omits the field, so the compiler resolves it
     to `True`. Recipe 2 supplies `true`. Both compile to the same `settings`.
     Their recipe digests differ only through `strategy_hash` and
     `plan_digest`, which are the strategy's textual identity.
   - **The CPU path.** `compile.rebuild` calls `recipes.build(family,
     settings)`.
   - **The GPU pod path.** `BatteryScoring.built_from` stages `recipe.json`
     with the same `settings`. `GPU_PROGRAM` is the practice `PROGRAM` plus a
     runtime probe, and it calls the same `recipes.build`.
   - **The model.** `recipes.MLP.__init__` reads `capacity_fade_head` into
     `Layout(fade=...)`, which `targets` and `split` use. That holds in the
     classic JAX loop, in `training.train` and in the PyTorch trainer.
   - **Measured.** Supplying `false` changes DeepONet's trained parameters on
     a 48-case, 32-step CPU fit.

2. **Neither wired nor refused, because neither applies.**
   - **Not wired.** The field is already wired for every learned family and
     backend.
   - **Not refused.** It applies to DeepONet, so a "not applicable" refusal
     would be wrong.
   - **No default-value refusal.** Refusing a supplied field because it equals
     its default would change admission for recipes Carbon has already
     admitted. Recipe 1 itself supplies two defaults (`bounded_voltage_head:
     true`, `ocv_initial_voltage: true`). **Declined by the Test Lead
     (2026-10-05), status quo, so no owner decision is needed:** identity by
     rebuilt artifact (WAVE-04 §1) already makes such recipes count as one, so
     refusing them adds nothing and would narrow freedom for admitted recipes.
     Revisit only if a real attack depends on it.
   - **KNN state digest, queued (Test Lead, 2026-10-05).** A new versioned KNN
     state digest covering `k`, `train_fraction`, inputs and targets, with
     `params_sha256` kept for replay (invariant 10). It matters under §1 in the
     opposite direction from aliasing: two genuinely different KNNs share one
     artifact identity today. `KNOWN_NO_OPS` loses the entry when it lands.
   - **Impact.** No contract change, no expansion record, and no change in how
     any existing recipe rebuilds or is admitted.

3. **Why this was harmless for counting: OWNER-GRAPHITE-TEST-WAVE-04 §1.**
   - A construction is identified by its rebuilt artifact, never by its recipe
     text. The two recipes rebuild the same artifact, so they are one
     construction.
   - Their recipe digests differ. A count keyed on the recipe digest would
     have counted them twice. That is the identity aliasing §1 forbids.

4. **Run 5: the two DeepONet "variants" were the same model.**
   - They differed only by restating a default, so any run-5 comparison
     between them compared a model with itself. The comparison shows nothing
     about a capacity-fade head.
   - The repository holds no run-5 record or summary to annotate. In
     `docs/development/graphite`, `TEST_WAVE_MATRIX.md` has only a status cell
     and `grants/README.md` only a cost line. `carbon/challenge_pipeline` has
     no run-5 entry. This decision and the lesson entry
     `2026-10-05-noop-capability-audit` carry the note.

5. **A standing audit: `tests/cpu/test_construction_noop_audit.py`.**
   - **Scope.** It iterates `capability_registry.CONTRACTS` and covers every
     REBUILDABLE_DEVELOPMENT capability of every contract.
   - **The rule.** On each base recipe, moving a field to a value taken from
     its own Surface must either:
     - change the rebuild identity (family and settings) AND the
       trained-parameter digest of a small CPU fit; or
     - be refused at compile time with a typed code.
   - **Bases.** One per rebuildable family and, where the contract offers it,
     per backend.
   - **Probe values.**
     - bool: the negation;
     - choice: every value is exercised;
     - uint and float: values from the Surface's bounds, tried until one
       changes the artifact.
   - **Families.** Every family must build parameters distinct from every
     other family's.
   - **Adapters.** Battery uses `compile.rebuild`. Cold plate and Motor use
     the closed-form kernel-ridge `compile.rebuild`, digesting the dual
     coefficients and target scaling.
   - **Retired contracts.** Burgers is RETIRED, and the Challenge registry
     refuses its selection, so it is audited at compile level only.
   - **New contracts.** A newly registered contract fails the audit until it
     has an adapter.
   - **Known no-ops.** The test asserts the exact set in `KNOWN_NO_OPS`. A new
     no-op fails, and a fixed one fails until it is removed.
   - **Mutation check.** Pinning `self.fade = True` in `recipes.MLP` makes the
     audit fail and name `physical_structure.capacity_fade_head`.

6. **Findings of the audit.**
   - **Battery `architecture.neighbours` on KNN (no-op, not fixed here).**
     - **The defect.** `recipes.KNN.fit` reports `params_sha256` as the
       digest of the stored TRAIN targets only (`carbon/battery/recipes.py`,
       `KNN.fit`). The neighbour count changes predictions but not that
       digest. Two KNN recipes that predict differently therefore share one
       "trained-parameter" identity.
     - **Why not fixed here.** The digest is held bit-identical to the
       exam-design campaign's research KNN
       (`scripts/dev/exam_design/recipes.py`, `KNN.fit`;
       `test_promoted_recipes_match_the_campaign_recipes_bit_for_bit`).
       Changing what it binds changes a recorded statistic's meaning, which
       invariant 10 requires to be versioned.
     - **Proposed fix.** Add a new, versioned KNN state digest that binds
       `k`, `train_fraction`, the unit inputs and the targets, and leave
       `params_sha256` unchanged. Alternatively, have every WAVE-04 §1 counter
       key non-parametric families on the built-record digest, which binds
       the settings.
   - **Every other capability** changes the trained artifact: every battery
     field on MLP and DeepONet (JAX), and both kernel-ridge choices on Cold
     plate and Motor. Burgers changes the compiled profile for every field.
   - **Torch bases not run here.** The PyTorch bases (FNO, and MLP and
     DeepONet on the PyTorch backend) are fitted only where torch and
     neuraloperator are installed. That includes CI's canonical lane, but not
     the host this was built on. Their first run is in CI.
   - **Observation, not a no-op: battery `microbatches`.** With uniform case
     weights, gradient accumulation over equal microbatches is mathematically
     the full-batch update. It differs only by floating-point summation order.
     It differs in substance once case weights are non-uniform (important
     region, curriculum, hard examples).
   - **Observation: Burgers GINO.** The registry defaults (16 modes on a
     12-point latent grid) are refused by Burgers' own rebuild rule
     (`parameter.dependency_unsatisfied` at `n_modes`), so the default GINO
     recipe does not compile. Burgers is retired, and nothing changes here.

**No execution.** This record dispatches, provisions and spends nothing.
