# Appendix C: Miner CLI Specification

**Purpose:** This document specifies the complete command-line interface for miners to interact with the Hydrogen subnet. It covers all commands, JSON schemas, configuration, Python SDK integration, and local validation tools. This is the primary interface for miners (human or agent) to participate in the subnet.

---

# Appendix C: Miner CLI Specification v2.1

---

## C.1 CLI Architecture

```bash
hydrogen-miner [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

**Global Options:**
| Flag | Short | Required | Default | Description |
|------|-------|----------|---------|-------------|
| `--wallet.name` | `-w` | Yes | — | Wallet name (registered on Bittensor) |
| `--wallet.hotkey` | `-k` | Yes | — | Hotkey name (registered on Bittensor) |
| `--netuid` | `-n` | Yes | `107` | Subnet UID |
| `--subtensor.network` | `-s` | No | `finney` | Subtensor network (finney/test/local) |
| `--subtensor.chain_endpoint` | `-e` | No | `wss://entrypoint-finney.opentensor.ai:443` | Subtensor RPC endpoint |
| `--api.url` | `-a` | No | `https://api.hydrogen.subnet` | Hydrogen API base URL |
| `--config` | `-c` | No | `~/.hydrogen/miner.yaml` | Config file path |
| `--verbose` | `-v` | No | `false` | Verbose logging |
| `--dry-run` | `-d` | No | `false` | Simulate without submitting |

---

## C.2 Commands

### C.2.1 `hydrogen-miner submit` — Submit Strategy or Specialist Pipeline

```bash
hydrogen-miner submit --challenge-id <ID> --strategy <FILE> [OPTIONS]
hydrogen-miner submit --challenge-id <ID> --pipeline <FILE> [OPTIONS]
```

**Options:**
| Flag | Required | Description |
|------|----------|-------------|
| `--challenge-id` | Yes | Challenge ID to submit to |
| `--strategy` | Yes* | Path to Strategy JSON file (Phase 0-1) |
| `--pipeline` | Yes* | Path to Specialist Pipeline JSON file (Phase 2+) |
| `--custom-data` | No | Path to custom data file (Phase 1+) |
| `--fee` | No | Override default 0.1 TAO fee |
| `--nonce` | No | Custom nonce for commit-reveal |

*Exactly one of `--strategy` or `--pipeline` required.*

**Examples:**
```bash
# Submit strategy
hydrogen-miner submit --challenge-id ns_2d_v1_0042 --strategy my_strategy.json

# Submit specialist pipeline
hydrogen-miner submit --challenge-id fsi_2d_v1_0012 --pipeline my_pipeline.json

# With custom data
hydrogen-miner submit --challenge-id darcy_2d_0003 --strategy strategy.json --custom-data my_data.npz
```

**Output:**
```json
{
  "submission_id": "sub_abc123",
  "challenge_id": "ns_2d_v1_0042",
  "status": "accepted",
  "commit_tx_hash": "0xabc123...",
  "reveal_deadline_block": 1234567,
  "fee_paid": "0.1 TAO"
}
```

---

### C.2.2 `hydrogen-miner challenges` — List Active Challenges

```bash
hydrogen-miner challenges [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--status` | Filter by status: `active`, `scoring`, `completed` |
| `--problem` | Filter by problem ID (1-7) |
| `--format` | Output format: `table`, `json`, `yaml` |
| `--watch` | Watch for new challenges (poll every 30s) |

**Output (table):**
```
┌──────────────────┬──────────────┬────────────┬──────────────┬────────────────────┬────────────┐
│ Challenge ID     │ Problem      │ Dimension  │ Status       │ Deadline (UTC)     │ Budget     │
├──────────────────┼──────────────┼────────────┼──────────────┼────────────────────┼────────────┤
│ ns_2d_v1_0042    │ Navier-Stokes│ 2D         │ active       │ 2026-07-15 20:00   │ 1240 TAO   │
│ darcy_3d_0012    │ Darcy 3D     │ 3D         │ active       │ 2026-07-15 22:00   │ 1240 TAO   │
│ thermo_el_0005   │ Thermo-elast │ 2D         │ scoring      │ 2026-07-15 18:00   │ 1240 TAO   │
└──────────────────┴──────────────┴────────────┴──────────────┴────────────────────┴────────────┘
```

---

### C.2.3 `hydrogen-miner baseline` — Get Current Baseline

```bash
hydrogen-miner baseline --challenge-id <ID> [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--output` | Output file path (default: stdout) |
| `--format` | `json` or `yaml` |

**Output:**
```json
{
  "challenge_id": "ns_2d_v1_0042",
  "problem_id": 4,
  "baseline": {
    "backbone": "PINO",
    "resolution": [128, 128],
    "pino": {
      "loss_vector": {"pde_residual": 1.5, "conservation": 0.8, "boundary": 0.5, "symmetry": 0.3},
      "physics_loss_type": "pde_residual",
      "boundary_handling": "ghost_cells"
    },
    "optimizer": "AdamW",
    "learning_rate": 0.001,
    "scheduler": "CosineAnnealingLR",
    "batch_size": 32,
    "epochs": 150,
    "physics_informed": true,
    "curriculum_learning": {"enabled": true, "start_resolution": [64, 64], "end_resolution": [128, 128], "ramp_epochs": 50},
    "uq_config": {"method": "deep_ensemble", "num_members": 4, "calibration_target": 0.90}
  },
  "last_updated": "2026-07-14T14:30:00Z",
  "version": 42
}
```

---

### C.2.4 `hydrogen-miner priors` — Get Landscape Priors

```bash
hydrogen-miner priors --challenge-id <ID> [OPTIONS]
```

**Output:**
```json
{
  "challenge_id": "ns_2d_v1_0042",
  "priors": [
    {
      "parameter": "pino.loss_vector.pde_residual",
      "recommended_range": [1.2, 2.0],
      "causal_effect": "+0.015 improvement",
      "confidence": 0.92,
      "supporting_fragments": 87,
      "condition": "when physics_loss_type == 'pde_residual'"
    },
    {
      "parameter": "curriculum_learning.enabled",
      "recommended_range": [true],
      "causal_effect": "+0.008 improvement",
      "confidence": 0.78,
      "supporting_fragments": 45
    },
    {
      "parameter": "optimizer",
      "recommended_range": ["AdamW"],
      "causal_effect": "+0.003 vs Adam",
      "confidence": 0.65,
      "supporting_fragments": 23
    }
  ],
  "last_updated": "2026-07-14T14:30:00Z"
}
```

---

### C.2.5 `hydrogen-miner specialists` — List Available Specialists

```bash
hydrogen-miner specialists [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--problem` | Filter by problem ID |
| `--phase` | Filter by phase compatibility |
| `--format` | `table`, `json`, `yaml` |

**Output (table):**
```
┌─────────────────────┬──────────────┬──────────────────────────────────────┬────────────┐
│ Specialist ID       │ Problem      │ Validity Domain                      │ Version    │
├─────────────────────┼──────────────┼──────────────────────────────────────┼────────────┤
│ ns_2d_v4            │ Navier-Stokes│ Re≤500, structured grid, 128²        │ v4         │
│ darcy_2d_v3         │ Darcy 2D     │ contrast≤10⁴, log-perm, structured   │ v3         │
│ elasticity_2d_v2    │ Elasticity   │ λ/μ≤100, mixed BC, 128²              │ v2         │
└─────────────────────┴──────────────┴──────────────────────────────────────┴────────────┘
```

---

### C.2.6 `hydrogen-miner submit-data` — Submit Custom Data (Phase 1+)

```bash
hydrogen-miner submit-data --challenge-id <ID> --file <PATH> [OPTIONS]
```

**Options:**
| Flag | Required | Description |
|------|----------|-------------|
| `--challenge-id` | Yes | Challenge ID |
| `--file` | Yes | Path to data file (.npz, .h5, .npz) |
| `--usage` | No | `augment`, `curriculum`, `label_only` (default: `augment`) |
| `--weight` | No | Mixing weight 0-1 (default: 0.25) |
| `--encrypt` | No | Encrypt with landscape public key |

**Output:**
```json
{
  "data_id": "data_abc123",
  "challenge_id": "darcy_2d_0003",
  "checksum": "sha256:abc123...",
  "size_bytes": 10485760,
  "status": "accepted",
  "royalty_eligible": true
}
```

---

### C.2.7 `hydrogen-miner validate` — Local Validation (Pre-Submit Check)

```bash
hydrogen-miner validate --challenge-id <ID> --strategy <FILE> [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--local` | Run validation locally (requires GPU) |
| `--quick` | Quick validation (1 epoch, reduced data) |
| `--full` | Full validation (matches validator) |

**Output:**
```json
{
  "valid": true,
  "estimated_score": 0.035,
  "estimated_improvement": 0.012,
  "physics_gates_check": {
    "mass_conservation": "likely_pass",
    "energy_dissipation": "likely_pass",
    "uq_calibration": "likely_pass"
  },
  "warnings": [
    "learning_rate 0.01 may be unstable; suggested ≤ 0.005"
  ],
  "estimated_cost_tao": 0.08
}
```

---

### C.2.8 `hydrogen-miner rewards` — Check Rewards & History

```bash
hydrogen-miner rewards [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--challenge` | Filter by challenge ID |
| `--days` | History window (default: 30) |
| `--format` | `table`, `json`, `csv` |

**Output (table):**
```
┌──────────────────┬────────┬────────────┬─────────────┬────────────┐
│ Challenge ID     │ Rank   │ Score      │ Improvement │ Reward     │
├──────────────────┼────────┼────────────┼─────────────┼────────────┤
│ ns_2d_v1_0042    │ 1      │ 0.047      │ +0.012      │ 496 TAO    │
│ darcy_2d_0003    │ 2      │ 0.031      │ +0.008      │ 372 TAO    │
│ burgers_0015     │ 4      │ 0.015      │ +0.003      │ 124 TAO    │
└──────────────────┴────────┴────────────┴─────────────┴────────────┘
Total: 992 TAO (30 days)
```

---

### C.2.9 `hydrogen-miner config` — Manage Configuration

```bash
hydrogen-miner config [get|set|show] [KEY] [VALUE]
```

**Examples:**
```bash
hydrogen-miner config show                           # Show all config
hydrogen-miner config get wallet.name                # Get single value
hydrogen-miner config set wallet.name my_wallet      # Set value
hydrogen-miner config set api.url https://api.myhydrogen.com  # Custom API
```

---

## C.3 Configuration File (`~/.hydrogen/miner.yaml`)

```yaml
wallet:
  name: "my_wallet"
  hotkey: "my_hotkey"
  path: "~/.bittensor/wallets"

network:
  netuid: 107
  subtensor:
    network: "finney"
    chain_endpoint: "wss://entrypoint-finney.opentensor.ai:443"

api:
  url: "https://api.hydrogen.subnet"
  timeout: 30

submission:
  default_fee: 0.1  # TAO
  auto_reveal: true
  commit_reveal: true

validation:
  local_enabled: true
  quick_mode_default: true

logging:
  level: "INFO"
  file: "~/.hydrogen/logs/miner.log"
  max_size_mb: 100
```

---

## C.4 Python SDK Integration (`hydrogen_miner` package)

```python
from hydrogen_miner import MinerClient, Strategy, SpecialistPipeline

client = MinerClient(
    wallet_name="my_wallet",
    hotkey="my_hotkey",
    netuid=107,
    network="finney"
)

# Get challenges
challenges = client.list_challenges(status="active")

# Get baseline + priors
baseline = client.get_baseline("ns_2d_v1_0042")
priors = client.get_priors("ns_2d_v1_0042")

# Generate strategy (your logic)
strategy = Strategy(
    backbone="PINO",
    resolution=[128, 128],
    pino={"loss_vector": {"pde_residual": 1.8, "conservation": 1.0}},
    optimizer="AdamW",
    learning_rate=0.001,
    # ... priors-informed values
)

# Local validation (optional)
local_result = client.validate_locally(strategy, "ns_2d_v1_0042", quick=True)
if local_result.valid:
    # Submit
    result = client.submit_strategy("ns_2d_v1_0042", strategy)
    print(f"Rank: {result.rank}, Score: {result.score}, Reward: {result.emission_reward}")

# Check rewards
rewards = client.get_rewards(days=30)
print(f"Total 30-day rewards: {sum(r.reward for r in rewards)} TAO")
```

---

## C.5 Strategy JSON Schema (Phase 0-1)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["backbone", "loss_vector", "optimizer", "curriculum_learning", "uq_config"],
  "properties": {
    "backbone": { "enum": ["FNO", "PINO", "DeepONet", "GNO", "OFormer"] },
    "resolution": { "type": "array", "items": { "type": "integer" }, "minItems": 2, "maxItems": 3 },
    "pino": {
      "type": "object",
      "properties": {
        "loss_vector": {
          "type": "object",
          "properties": {
            "pde_residual": { "type": "number", "minimum": 0 },
            "conservation": { "type": "number", "minimum": 0 },
            "boundary": { "type": "number", "minimum": 0 },
            "symmetry": { "type": "number", "minimum": 0 },
            "coupling_thermal_strain": { "type": "number", "minimum": 0 },
            "coupling_heat_source": { "type": "number", "minimum": 0 }
          }
        },
        "physics_loss_type": { "enum": ["pde_residual", "conservation", "symmetry"] },
        "boundary_handling": { "enum": ["ghost_cells", "penalty", "lagrange", "none"] }
      },
    "optimizer": { "enum": ["Adam", "AdamW", "SGD"] },
    "learning_rate": { "type": "number", "minimum": 1e-6, "maximum": 1 },
    "scheduler": { "enum": ["None", "StepLR", "CosineAnnealingLR", "ReduceLROnPlateau"] },
    "batch_size": { "type": "integer", "minimum": 1, "maximum": 256 },
    "epochs": { "type": "integer", "minimum": 1, "maximum": 500 },
    "physics_informed": { "type": "boolean" },
    "curriculum_learning": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "start_resolution": { "type": "array", "items": { "type": "integer" } },
        "end_resolution": { "type": "array", "items": { "type": "integer" } },
        "ramp_epochs": { "type": "integer", "minimum": 1 }
      }
    },
    "uq_config": {
      "type": "object",
      "properties": {
        "method": { "enum": ["deep_ensemble", "conformal", "evidential"] },
        "num_members": { "type": "integer", "minimum": 2, "maximum": 10 },
        "calibration_target": { "type": "number", "minimum": 0.8, "maximum": 0.99 }
      }
    },
    "custom_data": {
      "type": "object",
      "properties": {
        "data_uri": { "type": "string" },
        "data_type": { "enum": ["npy_fields", "csv", "hdf5", "generator"] },
        "usage": { "enum": ["augment", "curriculum", "label_only"] },
        "weight": { "type": "number", "minimum": 0, "maximum": 0.5 },
        "checksum": { "type": "string" },
        "encryption": {
          "type": "object",
          "properties": {
            "algorithm": { "enum": ["RSA-OAEP"] },
            "key_id": { "type": "string" }
          }
        }
      }
    }
  }
}
```

---

## C.6 Specialist Pipeline JSON Schema (Phase 2+)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["specialist_pipeline", "execution_schedule"],
  "properties": {
    "specialist_pipeline": {
      "type": "array",
      "minItems": 2,
      "maxItems": 5,
      "items": {
        "type": "object",
        "required": ["specialist_id", "role", "inputs"],
        "properties": {
          "specialist_id": { "type": "string" },
          "role": { "enum": ["primary", "secondary", "coupling"] },
          "inputs": { "type": "array", "items": { "type": "string" } }
        }
      },
      "adapter": {
        "type": "object",
        "properties": {
          "adapter_id": { "type": "string" },
          "role": { "enum": ["coupling", "preprocessing", "postprocessing"] },
          "params": { "type": "object" }
        }
      },
      "execution_schedule": { "enum": ["staggered", "monolithic"] },
      "max_coupling_iterations": { "type": "integer", "minimum": 1, "maximum": 20 },
      "coupling_tolerance": { "type": "number", "minimum": 1e-6, "maximum": 1e-2 }
    }
  }
}
```

---

## C.7 Custom Data Schema (Phase 1+)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["data_uri", "checksum", "usage", "weight"],
  "properties": {
    "data_uri": { "type": "string", "format": "uri" },
    "data_type": { "enum": ["npy_fields", "csv", "hdf5", "generator"] },
    "usage": { "enum": ["augment", "curriculum", "label_only"] },
    "weight": { "type": "number", "minimum": 0, "maximum": 0.5 },
    "checksum": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" },
    "encryption": {
      "type": "object",
      "properties": {
        "algorithm": { "enum": ["RSA-OAEP"] },
        "key_id": { "type": "string" }
      }
    }
  }
}
```

---

*End of Appendix C: Miner CLI Specification*
