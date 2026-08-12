# OPERATIONS.md — Carbon Subnet Operations & Deployment Guide

## TL;DR

**Job:** Run the subnet day-to-day without breaking determinism, gate integrity, or the SciML oracle.

**What this document owns**
- Validator fleet + miner toolkit Docker/K8s
- Julia/SciML Ground Truth Oracle (port 8083) — reference solves, adjoints, symbolic losses
- Queue, monitoring, alerts, incident response, backups
- Capacity planning by phase
- **Job-class isolation:** lean emissions path vs Specialist Bank / product-battery path

**Job classes (ops-critical)**

| `job_class` | Trigger | Queue | Emissions? |
|-------------|---------|-------|------------|
| **`lean_eval`** | Full miner submission | Default validator queue | **Yes** |
| **`bank_retrain`** | Specialist opportunity promote | Bank workers / isolated pool | No |
| **`product_battery`** | After bank lean re-gate | Bank / off-peak / sponsored PB capacity | No |

**Non-negotiable ops rules**
1. Physics gates always run in **fp32** (validators that skip this get false fails and should be treated as faulty)
2. JAX determinism: pinned lockfile + `threefry` + persistent XLA compile cache volumes
3. SciML Oracle is on the critical path — if it is down, validation is degraded; treat as SEV-1 when oracle checks are required
4. Train ≠ eval seeds; stress tensors never leave the validator process; **PB seeds never on miner API**
5. Hard step + wall-clock kills on every **lean** evaluation (ignore runaway miner `epochs`)
6. **Product-battery GPU must not starve lean_eval SLO** (`JAX_Optimization.md`, `Compute_Optimization.md`)
7. No teacher-checkpoint “distill” jobs that bypass controlled retrain + PB (`Specialist_Bank.md`)

**Daily operator loop**
- Morning: pod health, SciML `/health`, **lean** queue depth, overnight submission count, bank/PB backlog if live
- Mid-day: GPU util / OOM, stuck lean submissions (>2 h), SciML latency
- Evening: reward snapshot, queue trend, backup verification

**Key services**
| Service | Port | Failure impact |
|---------|------|----------------|
| Validator (lean) | 8080/8081 | No scoring / emissions |
| SciML Oracle | 8083 | No reference/adjoint validation |
| Queue processor | — | Lean backlog → latency |
| Bank / PB workers (when live) | — | No commercial graduation; lean continues |

**Read deeper:** §0 job classes → §1 architecture → §4 validator ops → §5 SciML ops → §8 incident response → runbooks.  
**Canonical design refs:** `SPEC.md`, `Landscape_Agent.md`, `Specialist_Bank.md`, `JAX_Optimization.md`.

---

**Version:** 3.1 (July 2026)  
**Status:** Production Operations Manual  
**Audience:** DevOps Engineers, Validator Operators, Platform Engineers, On-Call Engineers  
**Purpose:** Day-to-day operations, deployment, incident response, and maintenance for Carbon — including Julia/SciML Ground Truth Oracle and **lean vs bank/PB capacity isolation**

---

# 0. WORKLOAD CLASSES (OPS CONTRACT)

Carbon has three GPU-consuming job classes. Operators must not merge them into one undifferentiated “validator load.”

```text
lean_eval  ──► emissions, Model Cards → Landscape D1
bank_retrain ──► controlled specialist candidate
product_battery ──► INV / deep ROLL / ADV / LAT / ART ──► ship or promotion_fail (D11)
```

| Ops concern | Lean | Bank / PB |
|-------------|------|-----------|
| SLO | p95 complete within policy (e.g. queue timeout ~2 h) | Best-effort / scheduled; may be overnight |
| Scaling signal | Miner submission rate | Opportunity queue depth |
| Alert priority | SEV on lean backlog / stuck eval | SEV only if bank pipeline is contracted SLA |
| Metrics labels | `job_class=lean_eval` | `job_class=bank_retrain\|product_battery` |

**Capacity planning:** size the **lean** fleet for Phase throughput targets first. Add **10–20%** headroom only after Bank is live — do not inflate per-submission cost models with PB.

**Node labels (when Bank is live):**
```text
carbon-role: validator | bank-worker | sciml-oracle | landscape-agent | miner-toolkit | airgapped-validator
carbon-job-capable: lean | bank | pb
```

**Config hints:**
```yaml
validator:
  max_concurrent_lean_evaluations: 3
  evaluation_timeout_seconds: 7200
  job_classes_enabled: ["lean_eval"]
bank:
  enabled: false
  max_concurrent_pb: 1
  isolate_from_lean_queue: true
```

**Alerting additions:**
```yaml
- alert: LeanQueueBacklog
  expr: carbon_queue_depth{job_class="lean_eval"} > 50
  for: 15m
  labels: { severity: warning }
- alert: ProductBatteryStarvingLean
  expr: |
    carbon_gpu_busy{job_class="product_battery"} > 0
    and carbon_queue_depth{job_class="lean_eval"} > 30
  for: 30m
  labels: { severity: warning }
  annotations:
    summary: "PB load concurrent with lean backlog — check isolation"
```

---

# TABLE OF CONTENTS

1. Infrastructure Overview
2. Docker & Container Operations
3. Kubernetes Deployment
4. Validator Operations
5. Julia/SciML Ground Truth Service Operations
6. Monitoring & Alerting
7. Miner Onboarding & Support
8. Incident Response
9. Maintenance Procedures
10. Backup & Disaster Recovery
11. Security Operations
12. Capacity Planning
13. Runbooks

---

# 1. INFRASTRUCTURE OVERVIEW

## 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CARBON INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────────┤
│  Validator Fleet (lean_eval)     │  Bank / PB workers (optional) │
│  + MCP Server                    │  isolated GPU quota           │
│  Julia/SciML Oracle :8083        │  Landscape batch jobs         │
│  Persistent: compile_cache, jax_cache, checkpoints, model_registry│
│  Bittensor: Subtensor / Metagraph / Dendrite                     │
└─────────────────────────────────────────────────────────────────┘
```

## 1.2 Environment Inventory

| Environment | Purpose | Validators | GPU Config | Network | Julia/SciML |
|-------------|---------|------------|------------|---------|-------------|
| **devnet** | Development/Testing | 2-3 | 1× A100 40GB | Testnet (Finney) | 1 replica, dev Julia |
| **staging** | Pre-production validation | 3-5 | 1× H100 | Testnet (Finney) | 2 replicas, staging Julia |
| **mainnet** | Production | 5-20 | H100/H200 | Mainnet | 3+ replicas, prod Julia |

When Specialist Bank is live, staging/mainnet should provision at least one **bank-capable** node or time-sliced quota so PB jobs do not sit on the lean critical path.

---

# 2. DOCKER & CONTAINER OPERATIONS

## 2.1 Base Images & Versioning

Pinned CUDA validator/miner images and `julia:1.10-bullseye` for SciML. Build with `CARBON_VERSION`, `BUILD_DATE`, `GIT_COMMIT` labels. Tag strategy: `v{major}.{minor}.{patch}-{phase}`.

## 2.2 Image Build Pipeline

GitHub Actions build-push for `ghcr.io/carbon/validator`, `ghcr.io/carbon/sciml-service`, `ghcr.io/carbon/miner-toolkit` on tags `v*` and workflow_dispatch. Trivy HIGH/CRITICAL gate; cosign sign/verify.

## 2.3 Container Runtime

**Validator:** nvidia runtime; env `JAX_COMPILATION_CACHE_DIR`, `JAX_CACHE_DIR`, `PYTHONHASHSEED=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `SCIMML_ENDPOINT=http://carbon-sciml:8083`; volumes for compile/jax caches, checkpoints, config; health on `:8080/health`.

**SciML Oracle:** port 8083; `JULIA_NUM_THREADS=16`; julia depot PVC; health `:8083/health`.

**Miner toolkit:** MCP endpoint + hotkey; strategies/configs mounts; GPU as needed for light training.

## 2.4 Image Lifecycle

Promote `main-{sha}` → staging → release tag → `:latest`. Weekly prune unused images (keep labeled).

---

# 3. KUBERNETES DEPLOYMENT

## 3.1 Cluster Requirements

| Phase | Nodes (order) | GPU |
|-------|---------------|-----|
| 0–1B | 5 | 1× H100 class |
| 2A–2B | 6–8 | 1–2× H100 |
| 3 | 10–15 | 2× H100 |
| 4 | 20+ | 2× H200 class |

**Node labels:**
```text
carbon-phase: 0|1a|1b|2a|2b|3|4
carbon-role: validator|bank-worker|miner-toolkit|airgapped-validator|landscape-agent|sciml-oracle
gpu-type: a100-80gb|h100-80gb|h200-141gb
carbon-phase-capable: 0|1a|1b|2a|2b|3|4
carbon-job-capable: lean|bank|pb
```

## 3.2 Manifests (summary)

- **Deployment `carbon-validator`:** replicas ≥5; PriorityClass `carbon-validator-high`; GPU + memory requests; compile/jax/checkpoint PVCs; probes on `/health` `/ready`; anti-affinity across nodes.
- **CronJob `validator-queue-processor`:** every minute; `Forbid` concurrency; Redis-backed; `MAX_CONCURRENT=3`, `QUEUE_DEPTH=100`, `SUBMISSION_TIMEOUT=7200` (lean).
- **Deployment `carbon-sciml-service`:** replicas ≥3; GPU; julia-depot PVC; Service ClusterIP `:8083`.
- **Optional `carbon-bank-worker`:** `carbon-job-capable=bank,pb`; `job_classes_enabled` includes bank_retrain/product_battery; lower PriorityClass than lean validators.
- **PVCs:** compile-cache 500Gi, jax-cache 200Gi, checkpoints 500Gi, model-registry 1Ti, julia-depot 100Gi (nvme-fast, RWX where needed).
- **ConfigMap `validator-config`:** netuid, timeouts, gates path, landscape flags, sciml endpoint, `job_classes_enabled: [lean_eval]`, `bank.enabled: false` until live.
- **Secrets:** validator hotkeys, redis URL, MCP endpoint.

## 3.3 GPU Resource Management

NVIDIA device plugin required. Prometheus/DCGM rules: GPU memory >95%, util <10% for 30m, temp >85°C, SciML `up==0`.

---

# 4. VALIDATOR OPERATIONS

## 4.1 Daily Checklist

**Morning:** validator pods Running; SciML pods; **lean** queue depth; overnight submission count; α/TAO floor; rewards; `curl` SciML `/health`; if Bank live — bank worker Ready + PB backlog.

**Mid-day:** queue rate; `kubectl top`; stuck lean jobs >2h; SciML latency; diagnostics quality.

**Evening:** metrics snapshot; reward distribution; queue trend; backup verification; SciML metrics.

## 4.2 Lifecycle

Add validator: new hotkeys → subnet register → K8s secret → scale deployment → verify metagraph.  
Rotate keys: new hotkey → replace secret → rolling restart.  
Graceful remove: cordon/drain → scale down → confirm remaining healthy.

## 4.3 Health Metrics (lean-labeled)

```promql
up{job="carbon-validator"}
rate(carbon_submissions_evaluated_total{job_class="lean_eval"}[5m])
histogram_quantile(0.95, rate(carbon_evaluation_duration_seconds_bucket{job_class="lean_eval"}[5m]))
carbon_queue_depth{job_class="lean_eval"}
sum(rate(carbon_gate_pass_total[5m])) / sum(rate(carbon_gate_total[5m]))
```

**Alerts:** ValidatorDown; lean p95 latency >30m; lean queue >50 for 15m; GPU OOM; stuck submission >2h; SciML down/high latency; **ProductBatteryStarvingLean** (§0).

---

# 5. JULIA/SCIML GROUND TRUTH SERVICE OPERATIONS

## 5.1 Role

Julia SciML oracle: DifferentialEquations.jl, ModelingToolkit.jl, SciMLSensitivity.jl, NeuralPDE/MethodOfLines as needed. Validators call via `SciMLClient`.

**Endpoints:** `GET /health`, `POST /solve_pde`, `POST /adjoint_sensitivity`, `POST /symbolic_loss`, `POST /validate_solution`.

## 5.2 Deploy / Update / Depot

`kubectl apply` sciml deployment; rolling image updates; depot on PVC; weekly `Pkg.update` + precompile on one replica (shared depot); verify all replicas load DE/MT/SciMLSensitivity.

## 5.3 Monitoring

Solve/adjoint latency histograms; validation pass rate; Julia GC pressure; solver divergence counters. Alerts: service down (SEV-1), high latency, divergence, GC >50% CPU, unexpected depot checksum change.

## 5.4 SEV Procedures

**SEV-1 SciML down:** assess pods/nodes; OOM/depot/driver checks; optional temporary `sciml_oracle.enabled=false` on validators (internal gates only); restart; smoke solve.  
**SEV-2 latency/divergence:** metrics + GC; memory/threads; solver fallback; scale replicas.

## 5.5 Backup / DR

Daily julia-depot tarball to versioned S3/GCS (90d); Manifest in GitOps; restore via new PVC + attach + status/import verify.

## 5.6 Runbooks

Deploy new SciML version: staging test → set image → rollout status → health + smoke solve → watch metrics 30m → undo if needed.  
Restore depot: provision PVC → extract backup → patch volume → verify packages + health.

---

# 6. MONITORING & ALERTING

Scrape validators `:8082`, SciML metrics, DCGM. Separate lean vs bank series with `job_class`. Page on lean path failures; ticket bank path unless commercial SLA.

---

# 7. MINER ONBOARDING & SUPPORT

Wallet register; toolkit Docker; MCP `get_noisy_prior` / submit / diagnostics. **Support rule:** priors are noisy-only; do not distribute full specialist ONNX as competition help. Point commercial SKU requests to product channel.

---

# 8. INCIDENT RESPONSE

| SEV | Examples |
|-----|----------|
| 1 | All lean validators down; SciML required and down; chain disconnect blocking weights |
| 2 | Lean backlog > SLA; widespread gate infra failure; PB starving lean |
| 3 | Single validator unhealthy; non-critical SciML latency |

Always preserve train≠eval and fp32 gate invariants during emergency mitigations.

---

# 9. MAINTENANCE

Weekly: image prune, Julia depot update, cert/secret rotation check.  
Monthly: kernel/driver on staging first; capacity review (lean GPU util vs PB quota); DR restore drill.

---

# 10. BACKUP & DISASTER RECOVERY

| Asset | Cadence | Retention |
|-------|---------|-----------|
| Julia depot | Daily | 90d |
| Model registry / cards | Daily | Policy |
| ConfigMaps / GitOps | On change | Permanent |
| Compile caches | Rebuildable | Optional |

---

# 11. SECURITY OPERATIONS

Image scan/sign; secret rotation; no stress/PB seeds in logs or miner APIs; network policies isolating bank workers from public MCP if co-located.

---

# 12. CAPACITY PLANNING

1. Size **lean** fleet to challenge throughput targets and emission latency.  
2. After Bank live, add isolated **10–20%** GPU headroom for bank_retrain/PB — not multiplied into per-submission unit cost.  
3. Sponsored T3/T4 may fund dedicated PB capacity (`Compute_Optimization.md`).

---

# 13. RUNBOOKS (INDEX)

- Deploy validator / SciML / bank-worker release  
- Rotate validator hotkey  
- Drain node / scale lean fleet  
- SciML down / high latency  
- Lean queue backlog  
- PB starving lean  
- Restore julia depot  
- Disable oracle temporarily  

Detailed SciML deploy/restore steps: §5.6.

---

*v3.1: full ops manual retained in compressed operational form with explicit job-class contract. Docker/K8s/SciML procedures and SEV paths preserved; lean path is the default production SLO; product battery is isolated promotion work. Aligns with SPEC dual threshold, Specialist Bank, and JAX workload classes.*
