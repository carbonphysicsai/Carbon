# Appendix B: Validator Runtime Specification (Merged)

**Purpose:** This document specifies the complete validator runtime environment, including Docker images, entrypoint execution, determinism requirements, I/O contracts, and the integration contract between the chain, API, and validator. It is the single source of truth for how validators execute, how they interface with the chain and API, and how determinism is enforced. This is the "runtime contract" that ensures reproducible, verifiable physics-informed neural operator training and evaluation.

---

# Appendix B: Validator Runtime Specification (Merged) v2.1

---

## B.1 Docker Image Specification

### Base Image
```dockerfile
FROM nvcr.io/nvidia/pytorch:24.09-py3

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenmpi-dev openmpi-bin \
    git wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# PhysicsNeMo + NeuralOperator (pinned to spec versions)
RUN pip install --no-cache-dir \
    physicsnemo==0.4.0 \
    neural-operator==0.3.0 \
    hydra-core \
    omegaconf \
    pyyaml \
    boto3 \
    requests \
    pyyaml

# Hydrogen validator code
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

# Non-root user for security
RUN useradd -m -u 1000 validator && chown -R validator:validator /workspace
USER validator

ENTRYPOINT ["python", "entrypoint.py"]
```

### Build Tags (Per Backbone)
| Image Tag | Backbone | Size Estimate |
|-----------|----------|---------------|
| `hydrogen/validator:fno-v24.09` | FNO | ~12 GB |
| `hydrogen/validator:pino-v24.09` | PINO | ~12 GB |
| `hydrogen/validator:deeponet-v24.09` | DeepONet | ~12 GB |
| `hydrogen/validator:gno-v24.09` | GNO | ~13 GB |
| `hydrogen/validator:oformer-v24.09` | OFormer | ~13 GB |

**Build Command:**
```bash
docker build --target fno -t hydrogen/validator:fno-v24.09 .
docker build --target pino -t hydrogen/validator:pino-v24.09 .
# ... etc
```

---

## B.2 Entrypoint & Execution Interface

### Entrypoint Script (`entrypoint.py`)
```python
#!/usr/bin/env python3
"""
Validator Entrypoint
Environment variables control all behavior (no CLI args).
"""
import os, json, math, torch, numpy as np
import sys, traceback

# Determinism - MUST BE FIRST
seed = int(os.environ.get("HYDROGEN_SEED", "42"))
torch.manual_seed(seed)
np.random.seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
torch.use_deterministic_algorithms(True)

# Imports after determinism
from validator.train import train_backbone, execute_specialist_pipeline
from validator.eval import evaluate, run_stress_test
from validator.uq import evaluate_uq
from validator.io import load_challenge_data, load_baseline_error, save_result

def main():
    try:
        # Required environment variables
        challenge_id = os.environ["CHALLENGE_ID"]
        submission_json = json.loads(os.environ["SUBMISSION_JSON"])
        challenge_data_path = os.environ["CHALLENGE_DATA_PATH"]
        challenge_phase = int(os.environ.get("CHALLENGE_PHASE", "0"))
        
        # Load challenge metadata
        with open(f"{challenge_data_path}/metadata.json") as f:
            challenge = json.load(f)
        
        # Load data splits
        train_data, holdout_data, stress_data = load_challenge_data(challenge_data_path)
        
        # Parse submission
        submission = json.loads(os.environ["SUBMISSION_JSON"])
        
        # Execute
        if "specialist_pipeline" in submission:
            model = execute_specialist_pipeline(
                pipeline=submission["specialist_pipeline"],
                challenge=challenge,
                train_data=train_data,  # For adapter training if present
                seed=int(os.environ["HYDROGEN_SEED"])
            )
        else:
            # Load training data
            train_data, holdout_data, stress_data = load_challenge_data(challenge_data_path)
            
            # Handle custom data if present
            custom_data = submission.get("custom_data")
            if custom_data:
                custom_data = resolve_custom_data(custom_data, challenge_data_path)
            
            model = train_backbone(
                config=submission,
                train_data=train_data,
                custom_data=custom_data,
                seed=int(os.environ["HYDROGEN_SEED"])
            )
        
        # Evaluate on public holdout
        E_baseline = load_baseline_error(challenge_id)
        E_submission = evaluate(model, holdout_data, challenge_phase)
        improvement = math.log(E_baseline) - log(E_submission)
        
        # Hidden stress test + physics gates
        stress_result = run_stress_test(model, stress_data, challenge)
        
        # UQ calibration check
        uq_metrics = evaluate_uq(model, stress_data, submission.get("uq_config", {}))
        
        # Compute score
        if stress_result.hard_failure:
            score = 0.0
            reason = stress_result.failure_reason
        else:
            base_score = max(0.0, improvement)
            soft_penalty = stress_result.soft_penalty
            uq_bonus = uq_calibration_bonus(uq_metrics, challenge_phase)
            score = (base_score * soft_penalty) + uq_bonus
        
        # Build result
        result = {
            "score": score,
            "improvement": improvement,
            "stress_passed": not stress_result.hard_failure,
            "uq_calibrated": uq_metrics.calibrated,
            "physics_gates": stress_result.gates,
            "stress_details": stress_result.details,
            "uq_metrics": {
                "coverage": uq_metrics.coverage,
                "calibration_error": uq_metrics.calibration_error,
                "sharpness": uq_metrics.sharpness
            }
        }
        
        # Save result
        save_result("/workspace/output/result.json", result)
        print(json.dumps({"status": "success", "score": score}))
        
    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        with open("/workspace/output/result.json", "w") as f:
            json.dump({"status": "error", "error": str(e)}, f)
        print(json.dumps({"status": "error", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## B.2 Environment Variables (Complete Contract)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `CHALLENGE_ID` | Yes | Unique challenge identifier | `ns_2d_v1_0042` |
| `SUBMISSION_JSON` | Yes | Miner's full submission as JSON string | `{"backbone":"PINO",...}` |
| `CHALLENGE_DATA_PATH` | Yes | Path to mounted challenge data | `/data/challenge` |
| `CHALLENGE_PHASE` | Yes | Current subnet phase (0-3) | `0` |
| `HYDROGEN_SEED` | Yes | Deterministic seed for reproducibility | `42` |
| `SUBMISSION_JSON` | Yes | Miner's full submission as JSON string | `{"backbone":"PINO",...}` |
| `SUBMISSION_TYPE` | No | `strategy` or `specialist_pipeline` | `strategy` |
| `CUSTOM_DATA_PATH` | No | Path to custom data if mounted | `/data/custom` |

---

## B.3 Docker Runtime Configuration

| Parameter | Phase 0-2 | Phase 3 (3D) |
|-----------|-----------|--------------|
| **GPU** | `--gpus all` (1 GPU) | `--gpus all` (1 GPU, 24GB+) |
| **Memory** | `--memory=16g` | `--memory=48g` |
| **Shared Memory** | `--shm-size=8g` | `--shm-size=16g` |
| **CPU** | `--cpus=8` | `--cpus=16` |
| **Timeout** | 7200s (2hr) | 14400s (4hr) |
| **Volumes** | `-v /host/data:/data:ro -v /host/output:/workspace/output:rw` | Same |
| **IPC** | `--ipc=host` | Same |
| **ULimits** | `--ulimit memlock=-1 --ulimit stack=67108864` | Same |

### Docker Compose Snippet (Local Dev)
```yaml
services:
  validator:
    image: hydrogen/validator:pino-v24.09
    environment:
      - CHALLENGE_ID=ns_2d_v1_0042
      - SUBMISSION_JSON=${SUBMISSION_JSON}
      - CHALLENGE_DATA_PATH=/data/challenge
      - CHALLENGE_PHASE=0
      - HYDROGEN_SEED=42
    volumes:
      - ./data:/data:ro
      - ./output:/workspace/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    shm_size: 8g
    mem_limit: 16g
    cpus: '8'
```

---

## B.4 Determinism Requirements (Enforced in Container)

| Setting | Value | Enforcement |
|---------|-------|-------------|
| `torch.manual_seed` | `HYDROGEN_SEED` | Entrypoint |
| `numpy.random.seed` | `HYDROGEN_SEED` | Entrypoint |
| `torch.cuda.manual_seed_all` | `HYDROGEN_SEED` | Entrypoint |
| `torch.backends.cudnn.deterministic` | `True` | Entrypoint |
| `torch.backends.cudnn.benchmark` | `False` | Entrypoint |
| `torch.use_deterministic_algorithms` | `True` | Entrypoint |
| `CUBLAS_WORKSPACE_CONFIG` | `:4096:8` | Dockerfile ENV |
| `PYTHONHASHSEED` | `HYDROGEN_SEED` | Dockerfile ENV |
| `OMP_NUM_THREADS` | `1` | Dockerfile ENV |
| `MKL_NUM_THREADS` | `1` | Dockerfile ENV |

**Validation**: Container must pass determinism test — same seed + same input = bitwise identical output.

---

## B.5 Input/Output Contract

### Input: Challenge Data Structure (Mounted at `/data/challenge`)
```
/data/challenge/
├── metadata.json          # Challenge metadata (see below)
├── train/
│   ├── inputs.npy         # Training inputs [N, ...]
│   └── targets.npy        # Training targets [N, ...]
├── holdout/
│   ├── inputs.npy         # Holdout inputs [M, ...]
│   └── targets.npy        # Holdout targets [M, ...]
├── stress/
│   ├── procedural/        # Procedural variants
│   │   ├── inputs.npy
│   │   └── targets.npy
│   └── well_slices/       # The Well dataset slices
│       ├── slice_001.npz
│       └── ...
└── baseline_error.json    # {"error": 0.0123, "phase": 0}
```

### `metadata.json`
```json
{
  "challenge_id": "ns_2d_v1_0042",
  "problem_id": 4,
  "problem_name": "navier_stokes_2d",
  "phase": 0,
  "physics_class": "incompressible_fluid",
  "dimension": 2,
  "resolution": [128, 128],
  "stress_floors": {
    "mass_conservation": 1e-3,
    "energy_dissipation": 1e-4,
    "boundary": 1e-3,
    "rollout_steps": 100,
    "uq_target": 0.90
  },
  "well_mapping": ["turbulence", "mhd"],
  "coupling_spec": null
}
```

### Output: `/workspace/output/result.json`
```json
{
  "status": "success",
  "score": 0.047,
  "improvement": 0.0123,
  "stress_passed": true,
  "uq_calibrated": true,
  "physics_gates": {
    "mass_conservation": {"passed": true, "value": 4.2e-4, "threshold": 1e-3},
    "energy_dissipation": {"passed": true, "value": 8.1e-5, "threshold": 1e-4},
    "boundary_satisfaction": {"passed": true, "value": 3.1e-4, "threshold": 1e-3},
    "rollout_stability": {"passed": true, "value": 0.005, "threshold": 0.01},
    "uq_calibration": {"passed": true, "value": 0.012, "threshold": 0.02}
  },
  "stress_details": {
    "procedural_passed": 45,
    "procedural_failed": 0,
    "well_slices_passed": 48,
    "well_slices_failed": 2,
    "worst_case_degradation": 0.18
  },
  "uq_metrics": {
    "coverage": 0.912,
    "calibration_error": 0.012,
    "sharpness": 0.045
  }
}
```

**Error Output:**
```json
{
  "status": "error",
  "error": "OOM during training",
  "traceback": "..."
}
```

---

## B.6 Determinism Validation Test

**Required CI test for every validator image build:**

```bash
#!/bin/bash
# determinism_test.sh
set -e

IMAGE=$1
CHALLENGE_ID="determinism_test"
SEED=42

# Run 1
docker run --rm --gpus all \
  -e CHALLENGE_ID=$CHALLENGE_ID \
  -e SUBMISSION_JSON='{"backbone":"PINO","physics_informed":true}' \
  -e CHALLENGE_DATA_PATH=/data \
  -e CHALLENGE_PHASE=0 \
  -e HYDROGEN_SEED=$SEED \
  -v $(pwd)/test_data:/data:ro \
  -v $(pwd)/output1:/workspace/output \
  $IMAGE

# Run 2
docker run --rm --gpus all \
  -e CHALLENGE_ID=$CHALLENGE_ID \
  -e SUBMISSION_JSON='{"backbone":"PINO","physics_informed":true}' \
  -e CHALLENGE_DATA_PATH=/data \
  -e CHALLENGE_PHASE=0 \
  -e HYDROGEN_SEED=$SEED \
  -v $(pwd)/test_data:/data:ro \
  -v $(pwd)/output2:/workspace/output \
  $IMAGE

# Compare outputs (must be bitwise identical)
diff output1/result.json output2/result.json
echo "✅ Determinism verified: bitwise identical outputs"
```

---

## B.7 Integration Contract (Chain ↔ API ↔ Validator)

```yaml
# integration_contract.yaml

chain:
  challenge_metadata_onchain:
    - challenge_id: ChallengeId
    - problem_id: ProblemId
    - baseline_config_hash: Hash
    - stress_floors: PDESpecificFloors
    - emission_budget: Balance
    - submission_deadline: BlockNumber
    - status: Enum[Active, Scoring, Completed]
  
  submission_commitment:
    scheme: "commit-reveal-v2"
    commit_phase_blocks: 100
    reveal_phase_blocks: 50
    commitment_hash: "blake2b256(COMMITMENT_DOMAIN || canonical_json || nonce || challenge_id || miner)"
    canonical_serialization: "JCS (RFC 8785)"
    nonce_requirements:
      min_entropy_bits: 128
      uniqueness: "per_challenge_per_miner"
    commit_phase_blocks: 100
    reveal_phase_blocks: 50
    canonical_serialization: "JCS (RFC 8785)"
    late_reveal_penalty: "score=0, fee_burned"
    front_running_mitigation: "commitment_hides_strategy_until_reveal"
  
  validator_assignment:
    method: "stake_weighted_vrf"
    min_validators: 3
    max_validators: 7
    selection_block: "challenge_start_block + 10"
    min_stake: 10000  # TAO
    max_validators_per_entity: 2
    performance_weight: 0.3
    geographic_diversity: true
    vrf_key_registration: required
  
  scoring_window:
    start_block: "submission_deadline_block"
    end_block: "submission_deadline_block + 200"
    min_validator_submissions: 3
  
  consensus:
    method: "median"
    max_deviation: 0.1
    audit_trigger: 0.15
    min_validators_for_consensus: 3
  
  reward_distribution:
    trigger: "any_caller"
    splitter: "challenge_pallet"
    novelty_bonus_pool: "0.05 * challenge_budget"
  
  baseline_update:
    proposer: "owner_account"
    frequency: "daily"
    approval: "owner_signature"
  
  specialist_promotion:
    proposer: "owner_account"
    gauntlet_result_hash: Hash
    specialist_onnx_hash: Hash
    validity_domain: JSON

api:
  endpoints:
    GET /challenges:
      response: ChallengeList
    GET /challenges/{id}:
      response: ChallengeDetail
    GET /challenges/{id}/baseline:
      response: StrategyJSON
    GET /challenges/{id}/priors:
      response: PriorList
    GET /specialists:
      response: SpecialistList
    POST /submit:
      request: SubmitRequest
      response: SubmitResponse
    GET /submissions/{id}:
      response: ValidationResult
  
  authentication:
    method: "hotkey_signature"
    payload: "challenge_id + submission_json + nonce"
    header: "X-Hotkey-Signature"

validator:
  docker_image: "hydrogen/validator:{backbone}-v24.09"
  env_vars:
    CHALLENGE_ID: "string"
    SUBMISSION_JSON: "string"
    CHALLENGE_DATA_PATH: "/data/challenge"
    HYDROGEN_SEED: "int"
    SUBMISSION_TYPE: "strategy|specialist_pipeline"
  volumes:
    - "/host/data:/data:ro"
    - "/host/output:/workspace/output:rw"
  gpus: "all"
  memory: "16g"
  timeout: "7200"
  output: "/workspace/output/result.json"
  determinism:
    torch_seed: "HYDROGEN_SEED"
    numpy_seed: "HYDROGEN_SEED"
    cuda_deterministic: true
    cudnn_benchmark: false
```

---

## B.7 Determinism Validation (CI Gate)

**Required in CI pipeline for every validator image build:**

```yaml
# .github/workflows/validator-determinism.yml
name: Validator Determinism Test
on: [push, pull_request]
jobs:
  determinism:
    runs-on: [self-hosted, gpu, linux]
    steps:
      - uses: actions/checkout@v4
      - name: Build validator images
        run: ./scripts/build_validator_images.sh
      - name: Run determinism test
        run: ./scripts/determinism_test.sh hydrogen/validator:pino-v24.09
      - name: Upload result artifact
        uses: actions/upload-artifact@v4
        with:
          name: determinism-result
          path: determinism_report.json
```

---

*End of Appendix B: Validator Runtime Specification v2.1*
