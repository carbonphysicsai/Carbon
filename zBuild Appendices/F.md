# Appendix F: Testing & CI/CD Specification

**Purpose:** This document specifies the complete testing strategy, CI/CD pipelines, and quality gates for the Hydrogen subnet. It covers unit testing, integration testing, end-to-end testing, determinism validation, physics regression testing, performance benchmarks, and the complete CI/CD pipeline configuration. This ensures the subnet meets the highest standards of correctness, determinism, and physics fidelity.

---

# Appendix F: Testing & CI/CD Specification v2.1

---

## F.1 Testing Strategy Overview

```yaml
# testing_strategy.yaml

testing_pyramid:
  unit_tests:
    target_coverage: 90%
    frameworks: ["pytest", "pytest-asyncio", "pytest-cov"]
    speed_target: "< 30 seconds"
    
  integration_tests:
    target_coverage: 70%
    frameworks: ["pytest", "docker-compose", "testcontainers"]
    speed_target: "< 10 minutes"
    
  end_to_end_tests:
    target_coverage: 50% of critical paths
    frameworks: ["pytest", "docker-compose", "subtensor-local"]
    speed_target: "< 30 minutes"
    
  determinism_tests:
    coverage: 100% of validator images
    frequency: every image build
    tolerance: bitwise identical outputs
    
  physics_regression_tests:
    coverage: 100% of stress test gates
    frequency: every specialist promotion
    tolerance: physics gates must pass

testing_environments:
  - local_dev: "docker-compose up (CPU mode)"
  - ci: "GitHub Actions with self-hosted GPU runners"
  - staging: "Testnet (testnet.finney)"
  - production: "Mainnet (finney)"

quality_gates:
  pr_checks:
    - unit_tests_pass
    - type_check_pass (mypy/pyright)
    - lint_pass (ruff)
    - security_scan (bandit, safety)
    - docker_build_success
    
  merge_requirements:
    - all_pr_checks_pass
    - integration_tests_pass
    - determinism_test_pass (for validator changes)
    - physics_regression_pass (for validator/landscape changes)
    - code_review_approved (2 reviewers)
    
  release_gates:
    - all_merge_requirements_pass
    - e2e_tests_pass
    - determinism_test_pass (all validator images)
    - physics_regression_pass (all gates)
    - performance_benchmarks_within_threshold
    - security_audit_pass
```

---

## F.2 Unit Test Specification

```yaml
# tests/unit/README.md

unit_test_structure:
  chain_pallet:
    path: "pallets/hydrogen/tests/"
    coverage_targets:
      - challenge_management: 95%
      - submission_handling: 95%
      - scoring_consensus: 95%
      - emission_distribution: 95%
      - slashing_conditions: 90%
      - baseline_updates: 90%
      - specialist_registry: 90%
    test_categories:
      - happy_path: "Normal operation flows"
      - edge_cases: "Boundary conditions, limits"
      - error_conditions: "Invalid inputs, unauthorized access"
      - invariants: "Emission conservation, stake conservation"
      - migration: "Storage migrations between versions"
      
  validator_pipeline:
    path: "validator/tests/"
    coverage_targets:
      - train_backbone: 90%
      - execute_specialist_pipeline: 90%
      - physics_gates: 95%
      - uq_evaluation: 90%
      - stress_test_runner: 90%
      - scoring_formula: 95%
      - determinism: 100%
    test_categories:
      - algorithmic_correctness: "Known inputs → expected outputs"
      - physics_gate_correctness: "Known violations → hard failures"
      - uq_calibration: "Synthetic data → expected calibration"
      - stress_test_generation: "Seeded RNG → deterministic output"
      - adapter_application: "LoRA application correctness"
      
  landscape_agent:
    path: "landscape/tests/"
    coverage_targets:
      - dml_causal_inference: 90%
      - baseline_proposal: 85%
      - distillation_pipeline: 85%
      - specialist_gauntlet: 90%
      - causal_graph_operations: 85%
    test_categories:
      - causal_identification: "Known causal effects recovered"
      - counterfactual_reasoning: "Intervention effects estimated"
      - distillation_fidelity: "Student matches teacher ensemble"
      - specialist_gauntlet_correctness: "Grounding/decontamination logic"
      
  api_layer:
    path: "api/tests/"
    coverage_targets:
      - graphql_resolvers: 90%
      - rest_endpoints: 90%
      - authentication: 95%
      - validation: 90%
      - webhook_handlers: 90%
    test_categories:
      - schema_validation: "Invalid inputs rejected"
      - authorization: "Hotkey permissions enforced"
      - rate_limiting: "Quotas enforced"
      - webhook_verification: "Signatures validated"
      
  indexer:
    path: "indexer/tests/"
    coverage_targets:
      - block_processing: 90%
      - event_decoding: 95%
      - state_consistency: 90%
      - reorg_handling: 85%
    test_categories:
      - event_decoding: "All event types decoded correctly"
      - state_reconciliation: "Indexer state matches chain"
      - reorg_recovery: "State rolls back correctly"
      - performance: "Sync speed within SLA"

test_utilities:
  fixtures:
    - sample_challenges: "All 7 Phase 0 problems"
    - sample_strategies: "Valid/invalid strategies per problem"
    - sample_specialists: "Valid specialists per problem"
    - sample_fragments: "DML-ready fragment collections"
    - physics_gate_cases: "Passing/failing gate test cases"
    - well_slices: "Sample Well data slices"
    - miner_hotkeys: "Test hotkey pairs"
    - challenge_metadata: "Complete challenge metadata"
    
  mocks:
    - subtensor_client: "Mock substrate interface"
    - physicsnemo_model: "Deterministic mock model"
    - well_dataset: "In-memory Well data slices"
    - tee_client: "Mock TEE for fine-tuning API"
    - ipfs_client: "In-memory IPFS"
```

---

## F.2.1 Example Unit Tests

```python
# tests/unit/test_physics_gates.py
import pytest
import torch
import numpy as np
from validator.physics_gates import (
    check_mass_conservation,
    check_energy_dissipation,
    check_boundary_satisfaction,
    check_rollout_stability,
    check_uq_calibration,
    check_spectral_fidelity,
    check_q_criterion,
    check_wall_shear,
    check_nu_distribution,
    check_added_mass_tensor
)

class TestMassConservation:
    """Test mass conservation gate (incompressible flow)."""
    
    def test_divergence_free_passes(self):
        """Divergence-free field should pass."""
        u = torch.zeros(1, 2, 32, 32)
        u[0, 0] = torch.sin(torch.linspace(0, 2*np.pi, 32)).repeat(32, 1)
        u[0, 1] = torch.cos(torch.linspace(0, 2*np.pi, 32)).repeat(32, 1).T
        # ∇·u = 0 by construction
        assert check_mass_conservation(u, threshold=1e-3).passed
    
    def test_nonzero_divergence_fails(self):
        """Non-zero divergence should fail."""
        u = torch.ones(1, 2, 32, 32)  # ∇·u = 2
        assert not check_mass_conservation(u, threshold=1e-3).passed
    
    def test_threshold_boundary(self):
        """Value at threshold should pass."""
        u = torch.zeros(1, 2, 32, 32)
        u[0, 0, 0, 0] = 1e-3  # Exactly at threshold
        assert check_mass_conservation(u, threshold=1e-3).passed


class TestEnergyDissipation:
    """Test energy dissipation gate (dE/dt ≤ 0)."""
    
    def test_dissipative_system_passes(self):
        """Energy decreasing should pass."""
        energy = torch.tensor([1.0, 0.9, 0.81, 0.73, 0.66])  # Exponential decay
        assert check_energy_dissipation(energy, threshold=1e-4).passed
    
    def test_energy_increase_fails(self):
        """Energy increasing should fail."""
        energy = torch.tensor([1.0, 1.1, 1.2, 1.3])  # Energy growth
        assert not check_energy_dissipation(energy, threshold=1e-4).passed


class TestUQCalibration:
    """Test UQ calibration gate."""
    
    def test_well_calibrated_passes(self):
        """Well-calibrated predictions should pass."""
        np.random.seed(42)
        y_true = np.random.randn(1000)
        y_pred = y_true + np.random.randn(1000) * 0.1
        # 90% PI should cover ~90%
        y_std = np.ones_like(y_true) * 0.165  # 90% PI ≈ 1.645 * 0.1
        result = check_uq_calibration(y_true, y_pred, y_std, target=0.90)
        assert result.passed
        assert abs(result.coverage - 0.90) < 0.02
    
    def test_underconfident_fails(self):
        """Underconfident (too wide) should fail calibration."""
        y_true = np.zeros(100)
        y_pred = np.zeros(100)
        y_std = np.ones(100) * 10.0  # Way too wide
        result = check_uq_calibration(y_true, y_pred, y_std, target=0.90)
        # Overly wide intervals fail sharpness
        assert not result.passed or result.sharpness > 1.0


class TestSpectralFidelity:
    """Test spectral fidelity gate (3D turbulence)."""
    
    def test_kolmogorov_spectrum_passes(self):
        """k^(-5/3) spectrum should pass."""
        k = np.arange(1, 64)
        E_true = k**(-5/3)
        E_pred = E_true * (1 + np.random.normal(0, 0.05, len(k)))  # 5% noise
        result = check_spectral_fidelity(E_pred, E_true)
        assert result.passed
    
    def test_wrong_spectrum_fails(self):
        """k^(-3) spectrum should fail for 3D turbulence."""
        k = np.arange(1, 64)
        E_true = k**(-5/3)
        E_pred = k**(-3)  # 2D spectrum
        result = check_spectral_fidelity(E_pred, E_true)
        assert not result.passed


class TestQCriterion:
    """Test Q-criterion vortex identification."""
    
    def test_vortex_ring_passes(self):
        """Vortex ring should have correct Q-criterion."""
        # Generate vortex ring velocity field
        u = generate_vortex_ring(64)
        Q_true = compute_q_criterion(u)
        Q_pred = Q_true + np.random.normal(0, 0.05, Q_true.shape)
        result = check_q_criterion(Q_pred, Q_true)
        assert result.passed


class TestRolloutStability:
    """Test rollout stability gate."""
    
    def test_stable_rollout_passes(self):
        """Stable energy over 100 steps should pass."""
        energy = np.ones(100) * (1 + np.random.normal(0, 0.001, 100))
        assert check_rollout_stability(energy, steps=100, threshold=0.01).passed
    
    def test_energy_explosion_fails(self):
        """Exploding energy should fail."""
        energy = np.exp(np.linspace(0, 1, 100))  # Exponential growth
        assert not check_rollout_stability(energy, steps=100, threshold=0.01).passed


class Test3DSpecificGates:
    """Test 3D-specific physics gates."""
    
    def test_q_criterion_3d(self):
        """3D Q-criterion vortex identification."""
        u = generate_3d_turbulence(64)
        Q_true = compute_q_criterion_3d(u)
        Q_pred = Q_true * (1 + np.random.normal(0, 0.1, Q_true.shape))
        result = check_q_criterion_3d(Q_pred, Q_true)
        assert result.passed
    
    def test_wall_shear_stress(self):
        """Wall shear stress distribution in 3D."""
        tau_true = compute_wall_shear(generate_channel_flow(64))
        tau_pred = tau_true * (1 + np.random.normal(0, 0.05, tau_true.shape))
        result = check_wall_shear(tau_pred, tau_true)
        assert result.passed
    
    def test_nu_distribution_corners(self):
        """Nusselt number in 3D corners."""
        Nu_true = compute_nusselt_3d(generate_heated_cavity(64))
        Nu_pred = Nu_true * (1 + np.random.normal(0, 0.1, Nu_true.shape))
        result = check_nu_distribution(Nu_pred, Nu_true)
        assert result.passed
    
    def test_added_mass_tensor(self):
        """Added mass tensor symmetry in 3D FSI."""
        A_true = compute_added_mass_tensor(generate_fsi_geometry())
        A_pred = A_true + np.random.normal(0, 0.05, A_true.shape)
        result = check_added_mass_tensor(A_pred, A_true)
        assert result.passed


class TestThermoElasticityCoupling:
    """Test bidirectional thermo-elasticity coupling terms."""
    
    def test_thermal_strain_coupling(self):
        """Thermal → mechanical coupling."""
        thermal_strain = compute_thermal_strain(temperature_field)
        mechanical_strain = compute_mechanical_strain(displacement)
        # Coupling term: α * ΔT * I
        coupling = compute_coupling_thermal_strain(thermal_strain, mechanical_strain)
        assert coupling > 0  # Thermal expansion increases strain
    
    def test_heat_source_coupling(self):
        """Mechanical → thermal coupling."""
        strain_rate = compute_strain_rate(velocity)
        # Coupling term: β * ∂(∇·u)/∂t
        heat_source = compute_coupling_heat_source(strain_rate)
        assert heat_source > 0  # Compression generates heat
```

---

## F.3 Integration Test Specification

```yaml
# tests/integration/README.md

integration_test_suites:
  validator_pipeline_e2e:
    description: "Full validator pipeline: submit → train → evaluate → stress test → score"
    scenario: "Submit valid PINO strategy for 2D NS → expect score > 0"
    steps:
      1. Start validator container (PINO)
      2. Load NS 2D challenge data
      3. Submit valid PINO strategy JSON
      2. Train on public train split
      3. Evaluate on public holdout
      3. Run hidden stress test (procedural + Well)
      4. Compute score with physics gates
      5. Verify score > 0 for valid strategy
    success_criteria:
      - Pipeline completes without error
      - Score > 0 for valid strategy
      - All physics gates pass
      - Output format matches specification
    timeout: 300 seconds
    
  specialist_distillation_e2e:
    description: "Full distillation pipeline: top fragments → specialist → gauntlet → promotion"
    steps:
      1. Ingest 100 StrategyFragments for NS 2D
      2. Select top-5 by score
      3. Multi-teacher distillation → Student (same backbone, 50% width)
      3. Regression test against stress tests
      4. 3-judge panel evaluation (different backbones)
      4. Grounding gate check
      6. Decontamination check
      7. Triple Crown consistency
      8. Publish to Specialist Bank
    success_criteria:
      - Specialist passes all stress tests
      - All 3 judges pass
      - Grounding gate: lineage traceable
      - Decontamination: no memorization
      - ONNX export valid
    timeout: 1800 seconds
    
  three_track_leaderboard:
    description: "Three-track leaderboard on multi-physics challenge"
    scenario: "FSI challenge with Monolith, Composition, Specialist-Only tracks"
    steps:
      1. Submit Monolith strategy for FSI
      2. Submit Composition pipeline (ns_2d + elasticity_2d + adapter)
      3. Submit Specialist-Only (ns_2d_v4)
      4. Run all through same stress test
      4. Compute three parallel leaderboards
    success_criteria:
      - Three independent leaderboards produced
      - Same stress test used for all
      - Composition track can win
    timeout: 600 seconds
    
  challenge_lifecycle:
    description: "Full challenge lifecycle: create → open → submit → score → reward"
    steps:
      1. Create challenge via owner extrinsic
      2. Miners submit strategies (commit-reveal)
      2. Validators score submissions
      2. Consensus reached (median)
      2. Rewards distributed (40/30/20/10)
      2. Landscape updates baseline
      2. Next challenge generated
    success_criteria:
      - Challenge created on-chain
      - Submissions accepted during commit phase
      - Reveal phase works
      - Validators submit scores
      - Median consensus computed
      - Rewards distributed correctly
      - Baseline updated
    timeout: 600 seconds
    
  specialist_gauntlet:
    description: "Full specialist promotion gauntlet"
    steps:
      1. Distill candidate specialist
      2. Regression test (stress tests)
      2. Judge panel (3 judges, different backbones)
      2. Repair loop if any judge fails
      2. Grounding gate (lineage check)
      2. Decontamination check (Well holdout)
      2. Triple Crown consistency
    success_criteria:
      - Only specialists passing all gates promoted
      - Failed judges trigger repair loop
      - Grounding gate enforces lineage
      - Decontamination catches memorization
    timeout: 1800 seconds
    
  agent_participation:
    description: "Autonomous agent participates end-to-end"
    steps:
      1. Agent discovers challenges via API
      2. Agent fetches baseline + priors
      2. Agent generates strategy (using priors)
      2. Agent validates locally
      2. Agent submits strategy
      2. Agent receives structured feedback
      2. Agent learns from feedback
    success_criteria:
      - Agent completes full cycle autonomously
      - Feedback is structured and actionable
      - Agent improves over iterations
    timeout: 600 seconds
    
  phase_transition:
    description: "Phase 0 → Phase 1 → Phase 2 transitions"
    steps:
      1. Phase 0 exit criteria met
      2. Phase 1 features enabled (LoRA, custom data)
      2. Phase 1 exit criteria met
      2. Phase 2 features enabled (specialist pipelines, three-track)
      2. Phase 2C Go/No-Go gate evaluated
    success_criteria:
      - Features unlock at correct phase
      - Data migrations successful
      - No data loss during transition
    timeout: 300 seconds

test_data_management:
  fixtures:
    - minimal_challenge_set: "1 challenge per problem type"
    - full_challenge_set: "All 7 Phase 0 problems"
    - multi_physics_challenges: "FSI, CHT, Thermo-elasticity"
    - 3d_challenges: "3D Poisson, Darcy, NS"
    - well_slices: "Sample slices per problem type"
  data_isolation:
    - Each test gets fresh database
    - Docker volumes cleaned between tests
    - Deterministic seeds for reproducibility
```

---

## F.3 End-to-End Test Specification

```yaml
# tests/e2e/README.md

e2e_test_scenarios:
  full_phase_0_cycle:
    description: "Complete Phase 0 cycle from launch to Phase 1 readiness"
    duration: "3 months simulated (accelerated)"
    steps:
      1. Deploy subnet (chain + API + indexer + 5 validators)
      2. Launch 7 Phase 0 challenges
      2. Simulate 50 miners submitting over 30 days
      3. Validators score, Landscape updates baseline daily
      3. Track: baseline improvement, miner diversity, validator uptime
      4. Phase 0 exit criteria evaluation
    success_criteria:
      - Baseline log-improvement > 0.02/challenge avg
      - ≥30 unique miners
      - ≥5 validators operational
      - Landscape proposing improving baselines
    duration: "2 hours (accelerated)"
    
  full_phase_1_cycle:
    description: "Phase 1 with adapters, custom data, specialist distillation"
    duration: "2 months simulated"
    steps:
      1. Enable LoRA adapters and custom data
      2. Miners submit adapters + custom data
      2. Data royalty pool activates
      2. First ONNX specialists distilled
      2. Specialist Bank reaches 20+ specialists
    success_criteria:
      - ≥20 specialists in bank
      - Data royalties >5% emissions
      - Specialist reuse >80%
    duration: "3 hours (accelerated)"
    
  full_phase_2_cycle:
    description: "Phase 2 composition engine + marketplace"
    duration: "4 months simulated"
    steps:
      1. Launch FSI/CHT challenges (verified benchmarks)
      2. Three-track leaderboard active
      2. Thermo-elasticity added (generated data)
      2. Variant expansion
      2. Composition win rate >60% achieved
    success_criteria:
      - Composition win rate >60%
      - Specialist reuse >80%
      - Go/No-Go gate for 3D passed
    duration: "4 hours (accelerated)"
    
  phase_3_turbulence_bridge:
    description: "Phase 3.1 3D Turbulence Bridge"
    duration: "3 months simulated"
    steps:
      1. 3D single-physics specialists exist
      2. 3D Spectral Initialization Protocol developed
      2. 3D Turbulence Curriculum (Re=50→500)
      2. ns_3d_turbulent_v1 trained
      2. 3D-specific stress gates: energy spectrum, Q-criterion, wall shear, Nu distribution
      2. Gate passed → 3D multi-physics opens
    success_criteria:
      - ns_3d_turbulent_v1 passes k^(-5/3), Q-criterion, wall shear, Nu
      - 3D FSI/CHT/Thermo-elasticity challenges open
    duration: "6 hours (accelerated)"
    
  disaster_recovery:
    description: "Subnet recovery from various failure modes"
    scenarios:
      - validator_crash: "50% validators offline → remaining handle load"
      - chain_reorg: "100-block reorg → indexer recovers"
      - api_outage: "API down 1 hour → miners use cached baselines"
      - physics_gate_bug: "Bug in mass conservation → slashing triggers"
      - well_data_corruption: "Corrupt Well slice → decontamination catches"
    success_criteria:
      - No data loss
      - Automatic recovery within SLA
      - Slashing correctly applied
    duration: "30 minutes"

performance_benchmarks:
  validator_throughput:
    target: "≥15 submissions/hour/validator (Phase 0)"
    measurement: "Submissions processed per hour per GPU"
    
  indexer_sync_speed:
    target: "≥100 blocks/second"
    measurement: "Blocks processed per second during sync"
    
  api_latency:
    targets:
      - GET /challenges: < 100ms p99
      - GET /baseline: < 50ms p99
      - POST /submit: < 500ms p99
      - GraphQL queries: < 200ms p99
    
  landscape_agent_speed:
    targets:
      - Daily causal update: < 30 minutes
      - Weekly distillation: < 2 hours
      - Baseline proposal: < 5 minutes
    
  specialist_distillation_time:
    target: "< 30 minutes per specialist"
    measurement: "Wall time for multi-teacher distillation"

resource_limits:
  validator_memory: "≤16GB (Phase 0-2), ≤48GB (Phase 3)"
  validator_gpu_utilization: "≥80% during training"
  api_memory: "≤2GB"
  indexer_memory: "≤4GB"
  postgres_storage: "≤100GB (Year 1)"
  redis_memory: "≤256MB"
```

---

## F.4 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml

name: Hydrogen CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * 0'  # Weekly full test suite

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ============================================================
  # Code Quality (Fast, runs on every PR)
  # ============================================================
  code-quality:
    name: Code Quality
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install --no-cache-dir ruff mypy bandit safety
      
      - name: Lint (ruff)
        run: ruff check .
      
      - name: Type check (mypy)
        run: mypy --strict .
      
      - name: Security scan (bandit)
        run: bandit -r . -f json -o bandit-report.json || true
      
      - name: Dependency scan (safety)
        run: safety check --json --output safety-report.json || true

  # ============================================================
  # Unit Tests (Fast, runs on every PR)
  # ============================================================
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30
    strategy:
      matrix:
        python-version: ['3.11']
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install --no-cache-dir pytest pytest-asyncio pytest-cov pytest-xdist
          pip install -e .[test]
      
      - name: Run unit tests
        run: |
          pytest tests/unit \
            --cov=chain --cov=validator --cov=landscape --cov=api --cov=indexer \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=90 \
            -n auto \
            --timeout=60
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests

  # ============================================================
  # Docker Build (Every PR)
  # ============================================================
  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    strategy:
      matrix:
        target: [fno, pino, deeponet, gno, oformer, api, indexer, miner]
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/validator.Dockerfile
          target: ${{ matrix.target }}
          load: true
          tags: hydrogen/validator:${{ matrix.target }}-test
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Test image runs
        run: |
          docker run --rm hydrogen/validator:${{ matrix.target }}-test \
            python -c "import physicsnemo; import neuralop; print('OK')"

  # ============================================================
  # Determinism Test (Validator Changes)
  # ============================================================
  determinism-test:
    name: Determinism Test
    runs-on: [self-hosted, gpu, linux]
    if: |
      github.event_name == 'pull_request' && 
      contains(github.event.pull_request.files, 'validator/') ||
      github.event_name == 'push' && 
      contains(github.event.commits[0].modified, 'validator/')
    timeout-minutes: 30
    needs: docker-build
    steps:
      - uses: actions/checkout@v4
      - name: Run determinism test
        run: |
          ./scripts/determinism_test.sh hydrogen/validator:pino-test
        env:
          CHALLENGE_ID: determinism_test
          HYDROGEN_SEED: 42

  # ============================================================
  # Physics Regression Tests
  # ============================================================
  physics-regression:
    name: Physics Regression Tests
    runs-on: [self-hosted, gpu, linux]
    if: |
      github.event_name == 'pull_request' && 
      (contains(github.event.pull_request.files, 'validator/') ||
       contains(github.event.pull_request.files, 'landscape/'))
    timeout-minutes: 60
    needs: docker-build
    steps:
      - uses: actions/checkout@v4
      - name: Run physics regression suite
        run: |
          pytest tests/integration/physics_regression.py \
            -v --tb=short --timeout=300

  # ============================================================
  # Integration Tests (Nightly/On Merge)
  # ============================================================
  integration-tests:
    name: Integration Tests
    runs-on: [self-hosted, gpu, linux]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    timeout-minutes: 60
    needs: [docker-build, determinism-test, physics-regression]
    steps:
      - uses: actions/checkout@v4
      - name: Start local testnet
        run: |
          docker compose -f docker-compose.testnet.yml up -d
          sleep 30
      - name: Run integration test suite
        run: |
          pytest tests/integration/ -v --tb=short --timeout=600
      - name: Cleanup
        run: docker compose -f docker-compose.testnet.yml down -v

  # ============================================================
  # E2E Tests (Weekly/Release)
  # ============================================================
  e2e-tests:
    name: E2E Tests
    runs-on: [self-hosted, gpu, linux]
    if: github.event_name == 'schedule' || github.event.inputs.run_e2e == 'true'
    timeout-minutes: 180
    needs: [docker-build]
    steps:
      - uses: actions/checkout@v4
      - name: Start full testnet
        run: |
          docker compose -f docker-compose.e2e.yml up -d
          sleep 60
      - name: Run E2E test suite
        run: |
          pytest tests/e2e/ -v --tb=short --timeout=3600
      - name: Cleanup
        run: docker compose -f docker-compose.e2e.yml down -v

  # ============================================================
  # Performance Benchmarks (Weekly)
  # ============================================================
  performance-benchmarks:
    name: Performance Benchmarks
    runs-on: [self-hosted, gpu, linux]
    if: github.event_name == 'schedule'
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - name: Run benchmarks
        run: |
          pytest tests/performance/ -v --benchmark-only
      - name: Compare with baseline
        run: |
          python scripts/compare_benchmarks.py
      - name: Alert on regression
        if: failure()
        run: |
          echo "Performance regression detected!" | slack-webhook

  # ============================================================
  # Determinism Test (Weekly - All Validator Images)
  # ============================================================
  weekly-determinism:
    name: Weekly Determinism Test (All Images)
    runs-on: [self-hosted, gpu, linux]
    if: github.event_name == 'schedule'
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - name: Build all validator images
        run: ./scripts/build_validator_images.sh
      - name: Run determinism test on all images
        run: |
          for img in fno pino deeponet gno oformer; do
            ./scripts/determinism_test.sh hydrogen/validator:$img-latest
          done

  # ============================================================
  # Release (Tagged Commits)
  # ============================================================
  release:
    name: Release
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
    needs: [code-quality, unit-tests, docker-build, determinism-test, physics-regression]
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and Push All Images
        run: |
          for target in fno pino deeponet gno oformer api indexer miner; do
            docker buildx build \
              --target $target \
              --platform linux/amd64 \
              -t ghcr.io/${{ github.repository }}/validator:$target-${{ github.ref_name }} \
              -t ghcr.io/${{ github.repository }}/validator:$target-latest \
              --push .
          done
          
          docker buildx build \
            --target api \
            --platform linux/amd64 \
            -t ghcr.io/${{ github.repository }}/api:${{ github.ref_name }} \
            -t ghcr.io/${{ github.repository }}/api:latest \
            --push .
      
      - name: Generate Release Notes
        run: |
          cat <<EOF > RELEASE_NOTES.md
          # Hydrogen ${{ github.ref_name }}
          
          ## Changes
          $(git log --oneline --grep="^[A-Z]+" --since="$(git describe --tags --abbrev=0 HEAD^)"..HEAD)
          
          ## Images
          - ghcr.io/${{ github.repository }}/validator:{fno,pino,deeponet,gno,oformer}-${{ github.ref_name }}
          - ghcr.io/${{ github.repository }}/api:${{ github.ref_name }}
          - ghcr.io/${{ github.repository }}/indexer:${{ github.ref_name }}
          - ghcr.io/${{ github.repository }}/miner:${{ github.ref_name }}
          EOF
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: RELEASE_NOTES.md
          generate_release_notes: true

  # ============================================================
  # Security Audit (Monthly)
  # ============================================================
  security-audit:
    name: Security Audit
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - name: Run security scans
        run: |
          bandit -r . -f json -o bandit-report.json
          safety check --json --output safety-report.json
          trivy fs --severity HIGH,CRITICAL --format json --output trivy-report.json .
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: *-report.json
```

---

## F.5 Quality Gates Summary

```markdown
## Quality Gates Checklist

### Pre-Merge (Every PR)
- [ ] Code quality: lint, type-check, security scan pass
- [ ] Unit tests: ≥90% coverage, all pass
- [ ] Docker images build successfully
- [ ] Determinism test passes (if validator changes)
- [ ] Physics regression tests pass (if validator/landscape changes)

### Pre-Release (Every Tag)
- [ ] All pre-merge gates pass
- [ ] Integration tests pass on testnet
- [ ] E2E tests pass on full testnet
- [ ] Determinism test passes for ALL validator images
- [ ] Physics regression tests pass for ALL gates
- [ ] Performance benchmarks within thresholds
- [ ] Security audit passes
- [ ] Documentation updated

### Post-Release Monitoring
- [ ] Validator uptime > 99%
- [ ] Challenge completion rate > 95%
- [ ] Median consensus deviation < 0.05
- [ ] Specialist promotion rate > 80%
- [ ] Novelty bonus distribution healthy (>10% of rewards)
```

---

*End of Appendix F: Testing & CI/CD Specification v2.1*
