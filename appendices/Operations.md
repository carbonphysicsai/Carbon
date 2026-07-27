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
1. Physics gates always run in **fp32** (validators that skip this are faulty)
2. JAX determinism: pinned lockfile + `threefry` + persistent XLA compile cache volumes
3. SciML Oracle is on the critical path for oracle-enabled checks — if down, treat as SEV-1 when required
4. Train ≠ eval seeds; stress tensors never leave the validator process; **PB seeds never on miner API**
5. Hard step + wall-clock kills on every **lean** evaluation
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
| SciML Oracle | 8083 | Degraded reference/adjoint validation |
| Queue processor | — | Lean backlog → latency |
| Bank / PB workers (when live) | — | No commercial graduation; lean continues |

**Read deeper:** §1 architecture → §4 validator ops → §5 SciML ops → §8 incident response → runbooks at end.  
**Canonical design refs:** `SPEC.md` (dual threshold), `Landscape_Agent.md`, `Specialist_Bank.md`, `JAX_Optimization.md` (job classes).

---

**Version:** 3.1 (July 2026)  
**Status:** Production Operations Manual  
**Audience:** DevOps, Validator Operators, Platform, On-Call  
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

Node labels (recommended when Bank is live):

```text
carbon-role: validator | bank-worker | sciml-oracle | landscape-agent
carbon-job-capable: lean | bank | pb
```

---

# TABLE OF CONTENTS

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Docker & Container Operations](#2-docker--container-operations)
3. [Kubernetes Deployment](#3-kubernetes-deployment)
4. [Validator Operations](#4-validator-operations)
5. [Julia/SciML Ground Truth Service Operations](#5-juliasciml-ground-truth-service-operations)
6. [Monitoring & Alerting](#6-monitoring--alerting)
7. [Miner Onboarding & Support](#7-miner-onboarding--support)
8. [Incident Response](#8-incident-response)
9. [Maintenance Procedures](#9-maintenance-procedures)
10. [Backup & Disaster Recovery](#10-backup--disaster-recovery)
11. [Security Operations](#11-security-operations)
12. [Capacity Planning](#12-capacity-planning)
13. [Runbooks](#13-runbooks)

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
| **devnet** | Development/Testing | 2-3 | 1× A100 40GB | Testnet | 1 replica |
| **staging** | Pre-production | 3-5 | 1× H100 | Testnet | 2 replicas |
| **mainnet** | Production | 5-20 | H100/H200 | Mainnet | 3+ replicas |

When Specialist Bank is live, staging/mainnet should provision at least one **bank-capable** node or time-sliced quota so PB jobs do not sit on the lean critical path.

---

# 2–3. DOCKER, K8s, SCI ML, VALIDATOR OPS (BODY)

The production body of this manual (Docker images, compose, K8s manifests, SciML deployment, validator lifecycle, Prometheus rules, miner onboarding, incident SEVs, maintenance, backup, capacity tables, runbooks) remains as previously specified in Operations v3.0.

**Implementers / on-call:** apply §0 job-class contract on top of those procedures:

- Label metrics and logs with `job_class`
- Alert lean backlog separately from bank backlog
- Never drain lean replicas exclusively into PB without a documented maintenance window
- Miner support: priors are **noisy-only**; full SKUs are commercial — do not “send the specialist ONNX” as support for competition

### Validator config hints (ConfigMap)

```yaml
validator:
  max_concurrent_lean_evaluations: 3
  evaluation_timeout_seconds: 7200
  job_classes_enabled: ["lean_eval"]   # add bank_retrain/product_battery on bank workers
bank:
  enabled: false                      # flip when Specialist Bank workers deploy
  max_concurrent_pb: 1
  isolate_from_lean_queue: true
```

### Alerting additions

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

# 4. VALIDATOR OPERATIONS (LEAN FOCUS)

Daily checklist remains: pod health, SciML health, **lean** queue depth, stuck submissions >2h, rewards, backups.

When Bank is enabled, add:
- [ ] Bank worker pods Ready
- [ ] PB queue depth / oldest opportunity age
- [ ] Confirm no `job_class=product_battery` on lean-only nodes

---

# 5+. SCI ML, MONITORING, INCIDENT, MAINTENANCE, DR

Unchanged operational detail from v3.0 for SciML oracle, Julia depot, GPU alerts, SEV runbooks, and backup procedures. SciML remains shared infrastructure for lean (and optionally bank) reference checks — size replicas for **lean** demand first.

---

*v3.1: job-class isolation for lean_eval vs bank_retrain/product_battery. Full K8s/SciML body retained from v3.0; operators must enforce §0 so productization compute cannot silently tax emissions throughput.*
