# Legacy Code Index

**Decision:** B-01E-D1
**Quarantine date:** 2026-08-30
**Source main commit:** `4ee58d56862d0441d5d151d79db1fe3036f1025d`
**Source tree:** `9f767ea16ffb7185ab64acff2542c7a8dcc2e339`
**Immutable annotated tag:** `archive/pre-wave-b-legacy-2026-08-30`
**Browsable branch:** `archive/legacy-prototypes`

This index records the executable implementation quarantined by B-01E from
active main. The annotated tag and archive branch both identify the complete,
exact pre-quarantine repository—not a rewritten or partial copy. Archive
presence grants no current implementation authority, scientific authority,
security qualification, network authority, or production status.

Authoritative specifications and historical design evidence remain on main
when their authority notices are correct. B-01E targets superseded executable
bytes that otherwise confuse packaging, testing, and agent reasoning.

## Retrieval

Inspect one historical file without checking out the archive:

```bash
git show archive/pre-wave-b-legacy-2026-08-30:<old-location>
```

Browse the complete snapshot in a separate worktree:

```bash
git worktree add ../Carbon-legacy archive/legacy-prototypes
```

A future ticket must cite its current authority, port only the justified
component, and re-establish current tests and boundaries. It must not treat
archive existence as permission to restore the old implementation wholesale.

## Dependency proof

Before removal, the 169-file manifest was expanded from B-01's completed
30-component audit and checked against the exact base tree:

- no canonical `carbon/` root imports an archived namespace;
- no canonical CPU or invariant test positively imports archived code;
- no active fixture depends on archived code;
- no canonical script or default CI job executes it;
- default packaging did include 46 legacy `carbon/**` files only because the
  intentional package selector is `carbon*`; quarantine removes that accidental
  executable surface while preserving the selector;
- historical textual references do not require executable bytes on main and
  are redirected to this index where they might otherwise imply current use;
- `carbon/backbones/**` remains on main because current CPU/schema tests
  directly exercise that current lazy compatibility boundary.

B-01 row 30 remains `DEFER_OWNER_DECISION`: this quarantine preserves the old
bytes but does not adopt, bless, or reinterpret any historical population,
threshold, weight, qualification rule, or scientific value.

## Quarantine summary

| Component group | Files | Final action |
|---|---:|---|
| Legacy packaged `carbon/**` implementation | 46 | `ARCHIVE_REMOVE_MAIN` |
| Historical `poc/**` | 56 | `ARCHIVE_REMOVE_MAIN` |
| Retired `neurons/**` | 18 | `ARCHIVE_REMOVE_MAIN` |
| Old `Julia/**` | 24 | `ARCHIVE_REMOVE_MAIN` |
| Historical `tests/legacy/**` | 6 | `ARCHIVE_REMOVE_MAIN` |
| Retired scripts | 5 | `ARCHIVE_REMOVE_MAIN` |
| Stale executable examples | 2 | `ARCHIVE_REMOVE_MAIN` |
| Retired Docker/Kubernetes artifacts | 12 | `ARCHIVE_REMOVE_MAIN` |
| **Total** | **169** | |

Each exact old location below inherits its section's B-01 classification,
reason, possible future owner, archive refs, and `ARCHIVE_REMOVE_MAIN`
action.

### Legacy packaged Carbon implementation (46 files)

- B-01 classification: `REPLACE / REPAIR`
- Reason removed: Superseded or incomplete executable implementation with no positive dependency from canonical package roots, CPU/invariant tests, fixtures, active scripts, or default CI.
- Possible future owner: B-02A through B-07F or B-E2, according to the B-01 component row
- Archive: every path below is available at both archive refs named above.

```text
carbon/base/miner.py
carbon/base/neuron.py
carbon/base/validator.py
carbon/challenges/__init__.py
carbon/challenges/base.py
carbon/challenges/burgers.py
carbon/challenges/darcy_2d.py
carbon/challenges/elasticity_2d.py
carbon/challenges/heat.py
carbon/challenges/navier_stokes_2d.py
carbon/challenges/poisson_2d.py
carbon/common/__init__.py
carbon/common/model_card.py
carbon/common/scoring.py
carbon/common/seeds.py
carbon/common/strategy_schema.py
carbon/data/__init__.py
carbon/data/benchmark_loader.py
carbon/data/download_pdebench.py
carbon/data/pdebench_loader.py
carbon/data/synthetic_loader.py
carbon/emission/__init__.py
carbon/emission/mechanics.py
carbon/landscape/__init__.py
carbon/landscape/agent.py
carbon/landscape/causal_knowledge_base.py
carbon/landscape/storage.py
carbon/miner/agent.py
carbon/miner/agent_tools.py
carbon/miner/client.py
carbon/miner/real_client.py
carbon/miner/strategy_generator.py
carbon/physics/gates.py
carbon/physics/stress.py
carbon/protocol.py
carbon/sciml/client.py
carbon/specialist/__init__.py
carbon/specialist/bank.py
carbon/specialist/distillation.py
carbon/symbolic/__init__.py
carbon/symbolic/pysr_evolver.py
carbon/training/__init__.py
carbon/training/physicsnemo_trainer.py
carbon/training/trainer.py
carbon/validator/sciml_validation.py
carbon/validator/validator.py
```

### Historical proof of concept (56 files)

- B-01 classification: `WRAP / REPAIR`
- Reason removed: The optional and partly broken PoC is not a current acceptance lane; future tickets may deliberately port justified ideas.
- Possible future owner: B-02B, B-03, B-04, B-05, or B-07F
- Archive: every path below is available at both archive refs named above.

```text
poc/README.md
poc/__init__.py
poc/configs/challenge_burgers1d.yaml
poc/configs/gates_burgers1d.yaml
poc/configs/scoring_burgers1d.yaml
poc/configs/validator_limits.yaml
poc/eval/__init__.py
poc/eval/fp32_context.py
poc/eval/gates.py
poc/eval/metrics.py
poc/eval/null_baseline.py
poc/eval/oracle_check.py
poc/eval/score.py
poc/fixtures/strategy_broken.json
poc/fixtures/strategy_data_only.json
poc/fixtures/strategy_gold.json
poc/fixtures/strategy_physics.json
poc/generators/__init__.py
poc/generators/burgers1d.py
poc/generators/justification.py
poc/generators/label_checks.py
poc/generators/stress_categories.py
poc/models/__init__.py
poc/models/fno1d.py
poc/models/fno1d_jax.py
poc/requirements.txt
poc/schema/strategy_poc_v1.json
poc/scripts/smoke.sh
poc/tests/__init__.py
poc/tests/conftest.py
poc/tests/test_category_ablation.py
poc/tests/test_clamps.py
poc/tests/test_discrimination.py
poc/tests/test_full_loop.py
poc/tests/test_gate_fail.py
poc/tests/test_gold_optional.py
poc/tests/test_handoff.py
poc/tests/test_loop_wiring.py
poc/tests/test_multiseed_variance.py
poc/tests/test_null_and_labels.py
poc/tests/test_oracle_ci.py
poc/tests/test_reproducibility.py
poc/tests/test_schema.py
poc/tests/test_score_pack.py
poc/tests/test_seed_separation.py
poc/tests/test_strategy_discrimination.py
poc/tests/test_stress_and_seeds.py
poc/tests/test_train_quality.py
poc/train/__init__.py
poc/train/loop.py
poc/train/losses.py
poc/train/losses_jax.py
poc/validator/__init__.py
poc/validator/handoff.py
poc/validator/run_once.py
poc/validator/schema_check.py
```

### Retired neuron and network implementation (18 files)

- B-01 classification: `REPLACE / explicit excluded`
- Reason removed: Obsolete Bittensor, simulated-scoring, miner, validator, and stress code has no current network authority.
- Possible future owner: A later explicitly authorized network ticket
- Archive: every path below is available at both archive refs named above.

```text
neurons/challenge/generator.py
neurons/miner.py
neurons/scoring/carbon_scorer.py
neurons/scoring/challenge_winner_tracker.py
neurons/strategy/strategy_store.py
neurons/stress/__init__.py
neurons/stress/base_generator.py
neurons/stress/procedural_generator.py
neurons/stress/stress_evaluator.py
neurons/stress/stress_models.py
neurons/stress/well_generator.py
neurons/symbolic/__init__.py
neurons/symbolic/extractor.py
neurons/symbolic/pysr_runner.py
neurons/symbolic/symbolic_models.py
neurons/utils/determinism.py
neurons/validator.py
neurons/validator_config.py
```

### Old Julia implementation (24 files)

- B-01 classification: `REPAIR`
- Reason removed: No near-term ticket is authorized to repair this incomplete prototype in place, and Julia is not part of the canonical environment.
- Possible future owner: B-04, B-E2, or their authorized successor
- Archive: every path below is available at both archive refs named above.

```text
Julia/Project.toml
Julia/docker/Dockerfile.sciml
Julia/docker/Dockerfile.sciml.build
Julia/docker/Dockerfile.sciml.dev
Julia/docker/docker-compose.sciml.dev.yml
Julia/docker/docker-compose.sciml.yml
Julia/scripts/build_sysimage.jl
Julia/scripts/deploy.sh
Julia/scripts/precompile.jl
Julia/scripts/test_service.jl
Julia/src/CarbonSciML.jl
Julia/src/handlers/adjoint.jl
Julia/src/handlers/health.jl
Julia/src/handlers/solve_pde.jl
Julia/src/handlers/symbolic.jl
Julia/src/handlers/validate.jl
Julia/src/solvers/adjoint.jl
Julia/src/solvers/reference.jl
Julia/src/solvers/symbolic.jl
Julia/src/utils/reproducibility.jl
Julia/src/utils/serialization.jl
Julia/start_server.jl
Julia/test/runtests.jl
Julia/test/test_solvers.jl
```

### Historical tests (6 files)

- B-01 classification: `Explicit historical`
- Reason removed: These tests exercise retired namespaces and must not be discovered by normal validation.
- Possible future owner: Archive only unless an explicit ticket ports a current test
- Archive: every path below is available at both archive refs named above.

```text
tests/legacy/conftest.py
tests/legacy/test_physics_gates.py
tests/legacy/test_reproducibility.py
tests/legacy/test_scorer.py
tests/legacy/test_scoring_spec.py
tests/legacy/test_tracker.py
```

### Retired scripts (5 files)

- B-01 classification: `REPLACE`
- Reason removed: These entry points execute retired landscape, scoring, miner, or validator semantics.
- Possible future owner: A later owner-specific replacement ticket
- Archive: every path below is available at both archive refs named above.

```text
scripts/generate_leaderboard.py
scripts/generate_score_data.py
scripts/local_validate.py
scripts/publish_daily_priors.py
scripts/run_landscape_daily.py
```

### Stale executable examples (2 files)

- B-01 classification: `REPLACE`
- Reason removed: The examples invoke retired MCP/miner behavior and are not valid current examples.
- Possible future owner: A later ticket that owns a current example
- Archive: every path below is available at both archive refs named above.

```text
examples/mcp_client_example.py
examples/run_agentic_miner.py
```

### Retired deployment artifacts (12 files)

- B-01 classification: `REPLACE / explicit excluded`
- Reason removed: These artifacts deploy obsolete miner, validator, SciML, and network implementations and have no current production authority.
- Possible future owner: A later qualified runtime or network ticket
- Archive: every path below is available at both archive refs named above.

```text
docker/docker-compose.sciml.yml
docker/docker-compose.yml
docker/miner/.env.example
docker/miner/Dockerfile
docker/miner/README.md
docker/miner/entrypoint.sh
docker/validator/Dockerfile
k8s/README.md
k8s/sciml-configmap.yaml
k8s/sciml-deployment.yaml
k8s/validator-deployment.yaml
k8s/validator-service.yaml
```
