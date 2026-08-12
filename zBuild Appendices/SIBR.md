# Carbon DoD GTM Strategy — Upgraded & Production-Ready
**Version 2.0 | Incorporating Technical, Compliance & Business Reality**

---

## 🎯 EXECUTIVE POSITIONING

> **Carbon is a Verification Engine, Not a Model Vendor.**
> 
> We produce **auditable, physics-gated evidence packages** that defense primes ingest into air-gapped enclaves for classified fine-tuning and IV&V/ATO accreditation.
> 
> **We do not:** Classify data, grant ATOs, generate SysML, guarantee target latency, or handle classified data.
> 
> **We do:** Discover robust architectures on public baselines → Export standardized evidence (Model Card + residuals + gate proofs + generator provenance) → Accelerate prime's IV&V by 6-12 months.

---

## 📋 TABLE OF CONTENTS

1. [Strategic Architecture — Dual-Regime Model Supply](#1-strategic-architecture--dual-regime-model-supply)
2. [Carbon's Evidence Package — Technical Specification](#2-carbons-evidence-package--technical-specification)
3. [DI-SESS-82483 Mapping — Schema-Aligned Output](#3-di-sess-82483-mapping--schema-aligned-output)
4. [IV&V Evidence Mapping — DOT&E Gap Coverage](#4-ivv-evidence-mapping--dote-gap-coverage)
5. [ATO/RMF Readiness — What Carbon Feeds](#5-atomrf-readiness--what-carbon-feeds)
6. [Phase 0.5: Defense-Relevant Benchmarks](#6-phase-05-defense-relevant-benchmarks)
7. [Go-to-Market Motion — Prime Partnership Model](#7-go-to-market-motion--prime-partnership-model)
8. [SBIR/Contract Vehicle Strategy](#8-sbircontract-vehicle-strategy)
9. [Technical Implementation Plan — Export Pipeline](#9-technical-implementation-plan--export-pipeline)
10. [Risk Register & Mitigations](#10-risk-register--mitigations)
11. [90-Day Execution Plan](#11-90-day-execution-plan)

---

## 1. STRATEGIC ARCHITECTURE — DUAL-REGIME MODEL SUPPLY

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PUBLIC REGIME (Carbon Subnet)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MINERS / AGENTS                                                    │   │
│  │  ├─ Explore: Loss schedules, curricula, architectures              │   │
│  │  ├─ Train: On PUBLIC baselines (Phase 0 + Phase 0.5 PDEs)          │   │
│  │  └─ Compete: Hidden adversarial stress + physics gates             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LANDSCAPE AGENT                                                    │   │
│  │  ├─ PySR → Symbolic conservation laws                              │   │
│  │  ├─ Double ML → Causal strategy→robustness effects                 │   │
│  │  └─ Specialist Bank → Reusable architecture components             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CARBON EVIDENCE PACKAGE (Export)                                   │   │
│  │  ├─ Model Card (deterministic config, training dynamics)           │   │
│  │  ├─ Physics Gate Ledger (residuals, thresholds, pass/fail)         │   │
│  │  ├─ Stress Test Provenance (generator version, seeds, variants)    │   │
│  │  ├─ Validator Attestation (validator set, consensus weights)       │   │
│  │  └─ Export Manifest (DI-SESS-82483 schema-aligned JSON)            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    CROSS-DOMAIN SOLUTION / SECURE TRANSFER
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CLASSIFIED REGIME (Prime Enclave IL5/IL6)              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PRIME CONTRACTOR / GOVERNMENT LAB                                  │   │
│  │  ├─ Ingest: Architecture blueprint (strategy.json)                 │   │
│  │  ├─ Ingest: Evidence package (informs IV&V test plan)              │   │
│  │  ├─ Apply: Classified telemetry / proprietary geometry             │   │
│  │  ├─ Fine-tune: Local weights on secret data (Carbon Toolkit)       │   │
│  │  ├─ Benchmark: Target hardware latency (HIL rig / FPGA / edge)     │   │
│  │  ├─ Classify: ITAR/EAR determination (Prime's ECO)                 │   │
│  │  ├─ Package: DI-SESS-82483 deliverable + RMF/ATO artifacts         │   │
│  │  └─ Deploy: Weapon system / HIL / Digital Twin                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Boundary Rules

| Carbon (Public) | Prime (Classified) |
|-----------------|-------------------|
| Discovers **architectures** | Trains **weights** |
| Generates **evidence** | Grants **accreditation** |
| Public PDEs + synthetic | Classified telemetry + geometry |
| No data classification | ITAR/EAR/CUI marking |
| No SysML generation | MBSE integration |
| No ATO | RMF/ATO authority |

---

## 2. CARBON'S EVIDENCE PACKAGE — TECHNICAL SPECIFICATION

### 2.1 Model Card Schema (Carbon Native → Prime Ingestible)

```json
{
  "$schema": "https://carbonsubnet.org/schemas/model-card/v1.0.json",
  "model_card_version": "1.0",
  "carbon_provenance": {
    "subnet": "carbon",
    "generator_version": "v1.3.2",
    "challenge_id": "navier-stokes-laminar-3d-v2",
    "bittensor_block_height": 3840212,
    "validator_set": [
      {"hotkey": "5Grwva...", "stake": 12500, "consensus_weight": 0.987},
      {"hotkey": "5FHneW...", "stake": 8900, "consensus_weight": 0.982}
    ],
    "consensus_mechanism": "Yuma Consensus (Bittensor)",
    "reproducibility": {
      "docker_image": "carbon/validator:v1.3.2",
      "seed_derivation": "hash(challenge_id + block_hash + run_nonce)",
      "deterministic_training": true
    }
  },
  "architecture": {
    "backbone": "FNO",
    "config": {
      "modes": 32,
      "width": 64,
      "depth": 4,
      "activation": "gelu",
      "lifting_dim": 128,
      "projection_dim": 128
    },
    "strategy_json_hash": "sha256-a1b2c3d4...",
    "parameter_count": 2.4e6
  },
  "training_dynamics": {
    "epochs": 500,
    "optimizer": "AdamW",
    "lr_schedule": "cosine_warm_restarts",
    "loss_formulation": {
      "data_mse": 1.0,
      "physics_residual": 0.5,
      "boundary_mse": 0.3,
      "conservation_penalty": 0.2,
      "adaptive_reweighting": {
        "enabled": true,
        "bounds": {"physics_residual": [0.1, 2.0]}
      }
    },
    "curriculum": [
      {"phase": 1, "reynolds": [100, 500], "epochs": 100},
      {"phase": 2, "reynolds": [500, 2000], "epochs": 200},
      {"phase": 3, "reynolds": [2000, 5000], "epochs": 200}
    ],
    "compute": {"gpu_hours": 120, "gpu_type": "H100"}
  },
  "physics_gate_results": {
    "methodology": "Carbon Tier 2 Hidden Adversarial Evaluation",
    "generator_version": "v1.3.2",
    "stress_variants_tested": 247,
    "gates": [
      {
        "gate_id": "mass_conservation",
        "pde": "∂ρ/∂t + ∇·(ρu) = 0",
        "metric": "max_continuity_residual_L2",
        "threshold": 1.0e-6,
        "result": 4.12e-7,
        "status": "PASS",
        "worst_case_variant": "transonic_shock_042"
      },
      {
        "gate_id": "energy_stability",
        "pde": "ρ·De/Dt = -∇·q - p∇·u + Φ",
        "metric": "energy_dissipation_violation",
        "threshold": 1.0e-6,
        "result": 8.89e-7,
        "status": "PASS",
        "worst_case_variant": "high_mach_shear_118"
      },
      {
        "gate_id": "boundary_satisfaction",
        "pde": "u|_∂Ω = g_D, (σ·n)|_∂Ω = g_N",
        "metric": "max_boundary_residual_Linf",
        "threshold": 1.0e-5,
        "result": 2.34e-6,
        "status": "PASS"
      },
      {
        "gate_id": "rollout_stability",
        "protocol": "10,000 step autoregressive + 1% Gaussian perturbation",
        "metric": "blowup_detection",
        "threshold": "zero blowups",
        "result": "0 blowups",
        "status": "PASS"
      },
      {
        "gate_id": "uq_calibration",
        "method": "conformal_prediction",
        "metric": "coverage_probability",
        "threshold": "≥0.95 at 95% confidence",
        "result": 0.953,
        "status": "PASS"
      }
    ],
    "overall_score": {
      "physics_fidelity": 43,
      "robustness": 26,
      "accuracy": 23,
      "total": 92,
      "threshold": 85
    }
  },
  "failure_diagnostics": {
    "uncertainty_hotspots": [
      {"region": "leading_edge_shock", "condition": "Mach > 3.2", "degradation": "+15% residual"}
    ],
    "spectral_limits": {
      "max_resolved_wavenumber": 32,
      "aliasing_risk_above": 28
    },
    "operational_envelope": {
      "mach": [0.8, 3.5],
      "angle_of_attack": [-10, 20],
      "reynolds": [100, 5000],
      "thermal_gradient_limit_k_per_m": 1400
    }
  },
  "export_artifacts": {
    "onnx_model": {
      "path": "model.onnx",
      "opset": 18,
      "dynamic_axes": {"batch": 0, "spatial": [2,3,4]},
      "sha256": "sha256-e5f6g7h8..."
    },
    "weights_only": {
      "path": "model_weights.safetensors",
      "sha256": "sha256-i9j0k1l2..."
    },
    "strategy_json": {
      "path": "strategy.json",
      "description": "Complete training configuration for air-gapped reproduction"
    }
  }
}
```

### 2.2 What This Gives the Prime

| Evidence | IV&V Use | ATO Use |
|----------|----------|---------|
| `validator_set` + `consensus_weight` | Proves independent, competitive evaluation | Supply chain provenance |
| `generator_version` + `seed_derivation` | Proves no data contamination | Reproducibility evidence |
| `physics_gate_results` with thresholds | **Core VV&A evidence** | Safety case foundation |
| `failure_diagnostics` | Defines operational envelope | Risk acceptance boundaries |
| `strategy_json` | Enables air-gapped reproduction | Configuration control |
| `onnx_model` + `sha256` | Binary reproducibility | Integrity verification |

---

## 3. DI-SESS-82483 MAPPING — SCHEMA-ALIGNED OUTPUT

### 3.1 Mapping Table

| DI-SESS-82483 Section | Carbon Evidence Package Field | Prime Action Required |
|----------------------|------------------------------|----------------------|
| **1. Model Geometry & Functions** | `architecture`, `training_dynamics`, `operational_envelope` | Map to system geometry; add classified geometry |
| **2. Interface & Interoperability** | `export_artifacts.onnx_model` (input/output tensors) | Wrap in SysML v2 / UAF; add HIL timing |
| **3. Synchronization & History** | `carbon_provenance` (block height, validator set) | Extend with classified training history |
| **4. Verification & Validation** | `physics_gate_results` + `failure_diagnostics` | **Core evidence** — extend with classified test data |
| **5. Security & Classification** | `carbon_classification: "PUBLIC_BASELINE"` | **Prime applies ITAR/EAR/CUI markings** |
| **6. Lifecycle Management** | `strategy_json` (reproduction config) | Add change classification framework |

### 3.2 Carbon's Export Manifest (DI-SESS-82483 Schema-Aligned)

```json
{
  "document_control": {
    "data_item_description_id": "DI-SESS-82483",
    "compliance_status": "SCHEMA_ALIGNED_EVIDENCE_PACKAGE",
    "generation_timestamp": "2026-07-22T12:25:00Z",
    "carbon_package_version": "1.0",
    "provenance_hash": "sha256-a1b2c3d4...",
    "carbon_classification": "PUBLIC_BASELINE_ARCHITECTURE",
    "prime_review_required": [
      "ITAR_CLASSIFICATION",
      "CUI_MARKING", 
      "ATO_RMF_PACKAGE",
      "TARGET_HARDWARE_BENCHMARK",
      "SYSML_WRAPPER_GENERATION"
    ]
  },
  "system_under_test": {
    "nomenclature": "CCA-Aero-Thermal-Surrogate-v4",
    "domain": "Aerospace / Next-Gen Flight Dynamics",
    "authoritative_source_of_truth_id": "ASOT-CCA-2026-04A",
    "carbon_challenge_id": "navier-stokes-laminar-3d-v2"
  },
  "interface_and_interoperability": {
    "framework_compatibility": ["ONNX_1.15", "Opset_18", "PyTorch_2.3", "TensorRT_8.6"],
    "input_vectors": [
      {"name": "mach_number", "type": "float32", "unit": "dimensionless", "valid_range": [0.8, 3.5]},
      {"name": "angle_of_attack", "type": "float32", "unit": "degrees", "valid_range": [-10.0, 20.0]},
      {"name": "reynolds_number", "type": "float32", "unit": "dimensionless", "valid_range": [100, 5000]}
    ],
    "output_vectors": [
      {"name": "surface_pressure_field", "type": "tensor_4d", "shape": "[batch, 128, 128, 128]", "unit": "Pa"},
      {"name": "surface_heat_flux", "type": "tensor_4d", "shape": "[batch, 128, 128, 128]", "unit": "W/m²"}
    ],
    "latency_characterization": {
      "note": "PRIME MUST BENCHMARK ON TARGET HARDWARE",
      "carbon_reference": {
        "hardware": "NVIDIA H100 80GB",
        "runtime": "TensorRT 8.6 FP16",
        "batch_size": 1,
        "measured_latency_ms": 3.2,
        "throughput_hz": 312
      }
    }
  },
  "physical_conservation_audit_ledger": {
    "verification_methodology": "Carbon Physics Gated Subnet Consensus",
    "generator_version": "v1.3.2",
    "validator_attestation": {
      "validator_count": 5,
      "consensus_weights": [0.987, 0.982, 0.979, 0.975, 0.971],
      "block_height_range": [3840210, 3840215]
    },
    "physics_gates_enforced": [
      {
        "gate_name": "Mass Conservation (Continuity Equation)",
        "governing_pde": "∂ρ/∂t + ∇·(ρu) = 0",
        "maximum_residual_detected": 4.12e-7,
        "pass_fail_threshold": 1.0e-6,
        "status": "PASS",
        "worst_case_stress_variant": "transonic_shock_042"
      },
      {
        "gate_name": "Energy Conservation (First Law of Thermodynamics)",
        "governing_pde": "ρ·De/Dt = -∇·q - p∇·u + Φ",
        "maximum_residual_detected": 8.89e-7,
        "pass_fail_threshold": 1.0e-6,
        "status": "PASS",
        "worst_case_stress_variant": "high_mach_shear_118"
      },
      {
        "gate_name": "Boundary Condition Satisfaction",
        "governing_pde": "u|_∂Ω = g_D, (σ·n)|_∂Ω = g_N",
        "maximum_residual_detected": 2.34e-6,
        "pass_fail_threshold": 1.0e-5,
        "status": "PASS"
      },
      {
        "gate_name": "Extended Rollout Stability",
        "protocol": "10,000 step autoregressive with 1% Gaussian state perturbation",
        "blowup_events": 0,
        "status": "PASS"
      },
      {
        "gate_name": "Uncertainty Quantification Calibration",
        "method": "Conformal Prediction (split conformal, calibration set n=500)",
        "coverage_at_95_percent": 0.953,
        "status": "PASS"
      }
    ]
  },
  "traceability_and_lifecycle_tracking": {
    "bittensor_block_height": 3840212,
    "validator_consensus_weight": 0.987,
    "generator_version": "v1.3.2",
    "reproducibility_package": {
      "docker_image": "carbon/validator:v1.3.2",
      "strategy_json": "strategy.json",
      "generator_source": "https://github.com/carbon-subnet/generators/releases/tag/v1.3.2"
    },
    "change_classification_framework": {
      "level_1_weight_update": "Same architecture, new classified weights → Rapid re-test (subset of gates)",
      "level_2_architecture_change": "New backbone/loss → Full IV&V re-run",
      "level_3_gate_change": "Physics gate threshold change → New accreditation"
    }
  }
}
```

---

## 4. IV&V EVIDENCE MAPPING — DOT&E GAP COVERAGE

### 4.1 VV&A Breakdown for AI/ML Surrogates

| Traditional VV&A (1990s) | AI/ML Failure Mode | Carbon Evidence |
|--------------------------|-------------------|-----------------|
| **Verification** — Code correctly implements math | Architecture ≠ math (black box) | `strategy_json` + `architecture` = white box |
| **Validation** — Math matches reality | Training distribution ≠ operational | `physics_gate_results` on *hidden* adversarial stress |
| **Accreditation** — Official approval for use | No framework for probabilistic models | `failure_diagnostics` defines operational envelope |

### 4.2 Carbon → Agile VV&A Mapping

| DOT&E Agile Validation Requirement | Carbon Deliverable | Prime Integration |
|-----------------------------------|-------------------|-------------------|
| **Model Documentation** | Model Card (complete) | Section 1 of IV&V report |
| **Verification Evidence** | Gate residuals + thresholds | Section 2: Verification |
| **Validation Evidence** | Hidden stress results + UQ | Section 3: Validation |
| **Operational Envelope** | `failure_diagnostics.operational_envelope` | Section 4: Limitations |
| **Sensitivity Analysis** | `failure_diagnostics.uncertainty_hotspots` | Section 5: Risk |
| **Reproducibility** | Docker + seed + strategy.json | Appendix: Reproducibility |
| **Supply Chain Provenance** | Validator set + block height + generator version | Appendix: Supply Chain |

### 4.3 What Carbon *Enables* (Not Replaces)

> **Carbon provides the *evidence backbone*. The Prime provides:**
> - Classified test data validation
> - Target hardware benchmarking
> - Safety case argumentation
> - Accreditation authority signature

---

## 5. ATO/RMF READINESS — WHAT CARBON FEEDS

### 5.1 RMF Control Mapping (NIST 800-53 Rev 5)

| RMF Control | Carbon Evidence Contribution | Prime Responsibility |
|-------------|------------------------------|---------------------|
| **SA-10** Developer Config Mgmt | `strategy_json` + `docker_image` + `generator_version` | Classified config control |
| **SA-11** Developer Testing | `physics_gate_results` (independent, adversarial) | Classified environment testing |
| **SA-15** Dev Process/Standards | Carbon subnet consensus = decentralized standard | Process tailoring |
| **SI-7** Software Integrity | `sha256` hashes on all artifacts | Runtime integrity monitoring |
| **AT-3** Role-Based Training | Model Card = operator documentation | Classified operator training |
| **PL-8** Security Architecture | `failure_diagnostics` = threat model input | Full system threat model |

### 5.2 ATO Package — Carbon's Contribution

```
PRIME'S ATO PACKAGE
├── System Security Plan (SSP)                    ← Prime writes
├── Security Assessment Report (SAR)              ← Assessor writes
│   └── Carbon feeds: Physics gate residuals, UQ calibration
├── Plan of Action & Milestones (POA&M)           ← Prime writes
│   └── Carbon feeds: Operational envelope limits, hotspots
├── Supply Chain Risk Assessment                  ← Prime writes
│   └── Carbon feeds: Validator set, generator version, reproducibility
├── Continuous Monitoring Strategy                ← Prime writes
│   └── Carbon feeds: Change classification framework
└── Authorization Decision                        ← AO signs
```

**Carbon does not produce the ATO package.** We produce the **technical evidence appendices** that make the assessor's job possible.

---

## 6. PHASE 0.5: DEFENSE-RELEVANT BENCHMARKS

### 6.1 The Problem
Current Phase 0 PDEs (Poisson, Darcy, Burgers, NS-laminar, Heat, Elasticity, Thermo-Elasticity) are **academic baselines** — not weapon-relevant.

### 6.2 Phase 0.5 Scope (Add to Roadmap: Months 4-8)

| Benchmark | Source | Physics Relevance | Carbon Challenge Design |
|-----------|--------|-------------------|------------------------|
| **NACA 0012 Transonic Flutter** | NASA TP-2001-211214 | Shock-boundary layer interaction, flutter onset | NS + Structural coupling (preCICE-lite) |
| **NASA CRM Wing-Body** | AIAA CFD Drag Prediction Workshop | Transonic separation, buffet | 3D RANS + turbulence (SA/κ-ω) |
| **HIFiRE-1 Scramjet Forebody** | AFRL/Boeing | Hypersonic boundary layer transition | NS + finite-rate chemistry (5-species) |
| **Turek/Hron FSI 3D** | FSI Benchmark | Fluid-structure interaction | NS + Elasticity (preCICE) |
| **Store Separation (6-DOF)** | AF SEEK EAGLE | Moving boundaries, dynamic mesh | NS + rigid body dynamics |
| **Turbine Blade Heat Transfer** | NASA C3X | Conjugate heat transfer, film cooling | NS + Heat + film cooling models |

### 6.3 Implementation

```python
# Phase 0.5 Generator Additions
class DefenseBenchmarkGenerator:
    """
    Generators for defense-relevant physics.
    Each includes:
    - Geometry (STL/STEP import)
    - Boundary conditions (flight envelope)
    - Reference solutions (CFD/FEA) for validation
    - Physics gates specific to regime
    """
    
    benchmarks = {
        "naca0012_transonic": {
            "pde": "compressible_navier_stokes",
            "turbulence": "sa",
            "mach_range": [0.8, 1.2],
            "reynolds_range": [1e6, 10e6],
            "gates": ["mass", "energy", "boundary", "shock_capture", "rollout"],
            "reference": "NASA_TP_2001_211214"
        },
        "crm_wingbody": {
            "pde": "rans_3d",
            "turbulence": "komega_sst",
            "mach_range": [0.85, 0.95],
            "gates": ["mass", "energy", "boundary", "separation_capture"],
            "reference": "DPW_WG5"
        },
        "hifire1_forebody": {
            "pde": "reacting_navier_stokes",
            "chemistry": "5_species_air",
            "mach_range": [5, 8],
            "gates": ["mass", "energy", "species", "boundary", "thermal"],
            "reference": "AFRL_HIFIRE"
        }
    }
```

### 6.4 Value Proposition to Primes

> **"Carbon has already adversarially validated architectures on the physics regimes your program cares about — before you spend a dollar on classified fine-tuning."**

---

## 7. GO-TO-MARKET MOTION — PRIME PARTNERSHIP MODEL

### 7.1 Why Not Direct Prime Sales

| Barrier | Reality |
|---------|---------|
| **Facility Clearance (FCL)** | 12-18 months, requires sponsorship |
| **Past Performance** | Primes require 3+ relevant contracts |
| **Accounting Systems** | DCAA-compliant, $200k+ setup |
| **Contract Vehicles** | SEWP, GSA, OTA — all require history |
| **Relationship Access** | Program Managers buy from known entities |

### 7.2 The Partnership Model

```
CARBON LABS (Subcontractor / Technology Provider)
       │
       ├── Technical: Subnet, Evidence Pipeline, Toolkit
       ├── IP: Architecture blueprints, verification methodology
       └── Team: SciML, distributed systems, export engineering
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  DEFENSE AI PRIME (Shield AI, Anduril, EpiSci,         │
│  Applied Intuition, or Tier 2: Kratos, Mercury, etc.)  │
├─────────────────────────────────────────────────────────┤
│  ├── Contract Vehicle: Prime's SEWP/GSA/OTA            │
│  ├── FCL & Facility: Prime's existing clearance        │
│  ├── Past Performance: Prime's portfolio               │
│  ├── Customer Access: Prime's PM relationships         │
│  ├── ATO Authority: Prime's accreditation experience   │
│  └── Integration: Prime's MBSE/HIL/Deployment stack    │
└─────────────────────────────────────────────────────────┘
       │
       ▼
GOVERNMENT CUSTOMER (AFRL, ARL, ONR, DIU, CDAO, PEOs)
```

### 7.3 Partnership Structures

| Model | Carbon Role | Prime Role | Revenue Split | Best For |
|-------|-------------|------------|---------------|----------|
| **Subcontract** | Tech provider, fixed deliverables | Prime, integration, delivery | 30-40% to Carbon | SBIR Phase II/III, BAAs |
| **Teaming Agreement** | Co-proposal, shared technical | Prime, contract mgmt, compliance | 40-50% to Carbon | New program starts |
| **Technology License** | Annual license + support | Prime, unlimited internal use | License fee | Scale phase |
| **Joint Venture** | Shared entity for defense | Prime, gov't relations | 50/50 | Long-term strategic |

### 7.4 Target Prime Partners (Priority Order)

| Tier | Companies | Why |
|------|-----------|-----|
| **1A** | **Shield AI, Anduril, EpiSci, Applied Intuition** | AI-native, need verification, have contract vehicles, understand decentralized |
| **1B** | **Kratos, Mercury Systems, Red 6** | Hardware+HIL focus, need surrogate layer |
| **2** | **Lockheed, Northrop, Boeing, Raytheon (via innovation cells)** | Massive scale, but slow procurement; target DIU/AFWERX paths |
| **3** | **Boutique SBIR houses** (TSC, Intelligent Automation, etc.) | Pure SBIR factories, need technical differentiator |

---

## 8. SBIR/CONTRACT VEHICLE STRATEGY

### 8.1 Realistic SBIR Pathway

| Phase | Vehicle | Carbon Role | Timeline | Funding |
|-------|---------|-------------|----------|---------|
| **Phase 0** | **Internal R&D** | Build Phase 0.5 benchmarks, evidence pipeline | Months 0-6 | Self-funded |
| **Phase I** | **SBIR via Prime** (AF261, AFRL, AFWERX) | Subcontractor: "Verification Engine for Physics Surrogates" | Months 6-12 | $250k (Prime gets ~$50k mgmt) |
| **Phase II** | **SBIR Phase II / STTR** | Subcontractor: Deploy evidence pipeline on Prime program | Months 12-30 | $1.5-2M |
| **Phase III** | **BAA / OTAs / Direct** | Subcontractor / Licensee: Production deployment | Month 30+ | $10M+ |

### 8.2 Phase I Proposal — Corrected Scope

**Title**: *Adversarial Verification Engine for Physics-Informed Neural Operator Surrogates in Weapon System Digital Twins*

**Technical Objectives (6 months, $250k):**
1. **Demonstrate** Carbon evidence pipeline on **NACA 0012 transonic benchmark** (public)
2. **Export** DI-SESS-82483 schema-aligned package + ONNX model
3. **Prime integrates** into air-gapped enclave, fine-tunes on **classified CRM data**
4. **Measure**: Fine-tune epoch reduction vs. baseline (target: 50% fewer epochs)
5. **Deliver**: IV&V evidence appendix for Prime's test report

**Success Criteria:**
- Carbon evidence package accepted by Prime's IV&V team without revision
- Fine-tune achieves target accuracy in ≤50% epochs of from-scratch training
- Model passes Prime's internal physics gates on classified test set

### 8.3 Alternative Vehicles

| Vehicle | Target | Carbon Fit |
|---------|--------|------------|
| **AFWERX SBIR/STRATFI** | AFRL/ACC | Fast, dual-use friendly |
| **DIU CSO** | Combatant Commands | Commercial tech insertion |
| **CDAO T&E** | AI Assurance | Directly aligned |
| **DARPA AI Forward** | High-risk/high-reward | Landscape Agent = novel |
| **OTA Consortia** (NSTXL, ATARC) | Rapid procurement | Sub via Prime |

---

## 9. TECHNICAL IMPLEMENTATION PLAN — EXPORT PIPELINE

### 9.1 Carbon Compliance Compiler (Production Version)

```python
# carbon/compliance/compiler.py
"""
Production Carbon → DI-SESS-82483 Evidence Package Compiler
Run in Prime's environment (public or air-gapped) after model export.
"""

import json
import hashlib
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import onnx
import onnxruntime as ort

@dataclass
class CarbonEvidencePackage:
    """Complete evidence package for Prime ingestion."""
    model_card_path: Path
    onnx_model_path: Path
    strategy_json_path: Path
    output_dir: Path
    
    # Prime-provided metadata
    prime_program_id: str
    prime_classification: str  # Prime determines: "ITAR", "CUI", "UNCLASS"
    target_hardware: str       # e.g., "H100_TensorRT_FP16", "FPGA_Xilinx_Versal"
    
    def compile(self) -> Path:
        """Generate complete evidence package."""
        # 1. Load and validate Model Card
        model_card = self._load_model_card()
        
        # 2. Validate ONNX model + extract interface
        interface = self._extract_onnx_interface()
        
        # 3. Benchmark on target hardware (if available)
        latency = self._benchmark_latency()
        
        # 4. Build DI-SESS-82483 manifest
        manifest = self._build_manifest(model_card, interface, latency)
        
        # 5. Write package
        package_dir = self.output_dir / f"carbon_evidence_{model_card['carbon_provenance']['challenge_id']}"
        package_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy artifacts
        for src, name in [
            (self.model_card_path, "model_card.json"),
            (self.onnx_model_path, "model.onnx"),
            (self.strategy_json_path, "strategy.json"),
        ]:
            subprocess.run(["cp", str(src), str(package_dir / name)], check=True)
        
        # Write manifest
        manifest_path = package_dir / "di_sess_82483_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Generate SHA256 manifest
        self._write_integrity_manifest(package_dir)
        
        return package_dir
    
    def _load_model_card(self) -> dict:
        with open(self.model_card_path) as f:
            card = json.load(f)
        # Validate required fields
        required = ['carbon_provenance', 'architecture', 'physics_gate_results', 'failure_diagnostics']
        for field in required:
            if field not in card:
                raise ValueError(f"Model Card missing required field: {field}")
        return card
    
    def _extract_onnx_interface(self) -> dict:
        model = onnx.load(str(self.onnx_model_path))
        inputs = []
        for inp in model.graph.input:
            shape = [d.dim_value if d.dim_value > 0 else -1 for d in inp.type.tensor_type.shape.dim]
            inputs.append({
                "name": inp.name,
                "type": onnx.TensorProto.DataType.Name(inp.type.tensor_type.elem_type),
                "shape": shape
            })
        outputs = []
        for out in model.graph.output:
            shape = [d.dim_value if d.dim_value > 0 else -1 for d in out.type.tensor_type.shape.dim]
            outputs.append({
                "name": out.name,
                "type": onnx.TensorProto.DataType.Name(out.type.tensor_type.elem_type),
                "shape": shape
            })
        return {"inputs": inputs, "outputs": outputs}
    
    def _benchmark_latency(self) -> dict:
        """Run actual inference benchmark. Returns measured values or 'NOT_MEASURED'."""
        try:
            sess = ort.InferenceSession(str(self.onnx_model_path), providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
            # Generate dummy input matching interface
            input_data = {}
            for inp in sess.get_inputs():
                shape = [1 if d <= 0 else d for d in inp.shape]
                input_data[inp.name] = np.random.randn(*shape).astype(np.float32)
            
            # Warmup
            for _ in range(10):
                sess.run(None, input_data)
            
            # Benchmark
            import time
            times = []
            for _ in range(100):
                start = time.perf_counter()
                sess.run(None, input_data)
                times.append((time.perf_counter() - start) * 1000)  # ms
            
            return {
                "measured": True,
                "hardware": self.target_hardware,
                "provider": sess.get_providers()[0],
                "batch_size": 1,
                "latency_ms": {
                    "mean": float(np.mean(times)),
                    "std": float(np.std(times)),
                    "p99": float(np.percentile(times, 99)),
                    "max": float(np.max(times))
                },
                "throughput_hz": 1000 / float(np.mean(times))
            }
        except Exception as e:
            return {
                "measured": False,
                "reason": str(e),
                "note": "PRIME MUST RUN BENCHMARK ON TARGET HARDWARE"
            }
    
    def _build_manifest(self, card: dict, interface: dict, latency: dict) -> dict:
        prov = card['carbon_provenance']
        gates = card['physics_gate_results']['gates']
        diag = card['failure_diagnostics']
        
        return {
            "document_control": {
                "data_item_description_id": "DI-SESS-82483",
                "compliance_status": "SCHEMA_ALIGNED_EVIDENCE_PACKAGE",
                "generation_timestamp": datetime.utcnow().isoformat() + "Z",
                "carbon_package_version": "1.0",
                "provenance_hash": self._hash_file(self.model_card_path),
                "carbon_classification": "PUBLIC_BASELINE_ARCHITECTURE",
                "prime_classification": self.prime_classification,
                "prime_program_id": self.prime_program_id,
                "prime_review_required": [
                    "ITAR_CLASSIFICATION_CONFIRMATION",
                    "CUI_MARKING_APPLICATION",
                    "TARGET_HARDWARE_BENCHMARK_VALIDATION",
                    "SYSML_WRAPPER_GENERATION",
                    "ATO_RMF_EVIDENCE_INTEGRATION"
                ]
            },
            "system_under_test": {
                "nomenclature": card.get('model_name', 'UNNAMED'),
                "domain": "Aerospace / Physics-Informed Neural Operator",
                "carbon_challenge_id": prov['challenge_id'],
                "authoritative_source_of_truth_id": self.prime_program_id
            },
            "interface_and_interoperability": {
                "framework_compatibility": ["ONNX_1.15+", "PyTorch_2.0+", "TensorRT_8.0+"],
                "onnx_interface": interface,
                "latency_characterization": latency,
                "deterministic_execution": card['carbon_provenance'].get('reproducibility', {}).get('deterministic_training', False)
            },
            "physical_conservation_audit_ledger": {
                "verification_methodology": "Carbon Physics Gated Subnet Consensus",
                "generator_version": prov.get('generator_version', 'UNKNOWN'),
                "validator_attestation": {
                    "validator_count": len(prov.get('validator_set', [])),
                    "validator_hotkeys": [v['hotkey'][:16] + '...' for v in prov.get('validator_set', [])],
                    "consensus_weights": [v['consensus_weight'] for v in prov.get('validator_set', [])],
                    "block_height": prov.get('bittensor_block_height')
                },
                "physics_gates_enforced": [
                    {
                        "gate_name": g['gate_name'],
                        "governing_pde": g.get('pde', g.get('governing_partial_differential_equation', 'UNKNOWN')),
                        "metric": g.get('metric', 'UNKNOWN'),
                        "threshold": g.get('threshold', g.get('pass_fail_threshold', 'UNKNOWN')),
                        "result": g.get('result', g.get('maximum_residual_detected', 'UNKNOWN')),
                        "status": g['status'],
                        "worst_case_variant": g.get('worst_case_variant', g.get('worst_case_stress_variant', 'N/A'))
                    }
                    for g in gates
                ]
            },
            "operational_envelope_and_limitations": {
                "validated_ranges": diag.get('operational_envelope', {}),
                "uncertainty_hotspots": diag.get('uncertainty_hotspots', []),
                "spectral_limits": diag.get('spectral_limits', {}),
                "change_classification": {
                    "level_1_weight_update": "Same architecture, new classified weights → Rapid re-test (subset of gates)",
                    "level_2_architecture_change": "New backbone/loss formulation → Full IV&V re-run required",
                    "level_3_gate_change": "Physics gate threshold modification → New accreditation cycle"
                }
            },
            "traceability_and_reproducibility": {
                "bittensor_block_height": prov.get('bittensor_block_height'),
                "generator_version": prov.get('generator_version'),
                "docker_image": prov.get('reproducibility', {}).get('docker_image'),
                "strategy_json_hash": self._hash_file(self.strategy_json_path),
                "onnx_model_hash": self._hash_file(self.onnx_model_path),
                "reproducibility_package_url": f"https://github.com/carbon-subnet/releases/tag/{prov.get('generator_version', 'latest')}"
            }
        }
    
    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return f"sha256-{hasher.hexdigest()}"
    
    def _write_integrity_manifest(self, package_dir: Path):
        """Write SHA256 manifest for all files in package."""
        manifest = {}
        for file_path in package_dir.rglob('*'):
            if file_path.is_file():
                rel = file_path.relative_to(package_dir)
                manifest[str(rel)] = self._hash_file(file_path)
        with open(package_dir / "INTEGRITY_MANIFEST.sha256", 'w') as f:
            json.dump(manifest, f, indent=2)
```

### 9.2 SysML v2 Template (Prime Customizes)

```sysml
/* 
 * CARBON SYSML v2 TEMPLATE — PRIME CUSTOMIZES
 * Auto-populated fields marked with <<CARBON>>
 * Prime must: classify, add HIL timing, connect to system model
 */

package CarbonSurrogateInterfaces {
    
    doc <<CARBON:DI_SESS_82483_EVIDENCE_PACKAGE>>
    
    /* Value Types — Prime adjusts ranges per operational envelope */
    attribute def MachNumber {
        attribute value : ScalarValues::Real;
        doc <<CARBON:VALID_RANGE [0.8, 3.5] — PRIME VERIFY>>
    }
    
    attribute def AngleOfAttack {
        attribute value : ScalarValues::Real;
        doc <<CARBON:VALID_RANGE [-10.0, 20.0] — PRIME VERIFY>>
    }
    
    attribute def ReynoldsNumber {
        attribute value : ScalarValues::Real;
        doc <<CARBON:VALID_RANGE [100, 5000] — PRIME VERIFY>>
    }
    
    attribute def PressureField3D {
        attribute value : ScalarValues::Real[128, 128, 128];
        doc <<CARBON:OUTPUT_UNITS Pa — PRIME CONFIRM GRID>>
    }
    
    attribute def HeatFlux3D {
        attribute value : ScalarValues::Real[128, 128, 128];
        doc <<CARBON:OUTPUT_UNITS W/m² — PRIME CONFIRM GRID>>
    }
    
    /* HIL Timing Constraint — PRIME MUST VALIDATE ON TARGET */
    value def MaxLatencyMicroseconds {
        attribute value : ScalarValues::Real;
        doc <<CARBON:REFERENCE_H100_TENSORRT 3200µs — PRIME BENCHMARK>>
    }
    
    /* Surrogate Model Block */
    part def AerothermalSurrogateModel {
        /* Input Ports — Air Data Computer / INS */
        port machInput {
            in attribute mach : MachNumber;
        }
        
        port aoaInput {
            in attribute aoa : AngleOfAttack;
        }
        
        port reynoldsInput {
            in attribute re : ReynoldsNumber;
        }
        
        /* Output Ports — Structural/Thermal Solvers */
        port pressureOutput {
            out attribute pressure : PressureField3D;
        }
        
        port heatFluxOutput {
            out attribute heatFlux : HeatFlux3D;
        }
        
        /* Execution Constraint — PRIME VALIDATES */
        constraint hilExecutionConstraint {
            doc "Max end-to-end latency must not exceed <<PRIME_DEFINED>> microseconds on target hardware <<TARGET_HARDWARE>>"
        }
        
        /* Carbon Provenance Metadata */
        annotation carbonProvenance {
            doc <<CARBON:CHALLENGE_ID>>
            doc <<CARBON:GENERATOR_VERSION>>
            doc <<CARBON:VALIDATOR_SET_HASH>>
            doc <<CARBON:BLOCK_HEIGHT>>
        }
    }
}
```

### 9.3 Miner Toolkit — Air-Gapped Mode

```python
# carbon/toolkit/airgapped.py
"""
Air-gapped Miner Toolkit for Prime enclave deployment.
No network dependencies. Runs entirely offline.
"""

class AirgappedMinerToolkit:
    """
    Usage in IL5/IL6 enclave:
    
    1. Prime receives: strategy.json, noisy_prior.pt, Model Card
    2. Prime loads into air-gapped toolkit
    3. Prime runs fine-tuning on classified data
    4. Prime exports ONNX + updated Model Card
    """
    
    def __init__(self, strategy_json_path: Path, prior_weights_path: Path):
        self.strategy = self._load_strategy(strategy_json_path)
        self.prior_weights = self._load_weights(prior_weights_path)
        self.device = self._detect_device()  # CPU/CUDA/ROCm
    
    def fine_tune(self, 
                  classified_dataset: Path,
                  epochs: int = 100,
                  lr: float = 1e-4,
                  physics_gates: bool = True) -> FineTuneResult:
        """
        Fine-tune on classified data with optional physics gate monitoring.
        """
        # Load classified data (Prime's format)
        train_loader, val_loader = self._load_classified_data(classified_dataset)
        
        # Initialize model from strategy + prior weights
        model = self._build_model()
        model.load_state_dict(self.prior_weights, strict=False)
        
        # Training loop with physics residual monitoring
        for epoch in range(epochs):
            train_loss = self._train_epoch(model, train_loader, lr)
            
            if physics_gates and epoch % 10 == 0:
                gate_results = self._run_physics_gates(model, val_loader)
                if not all(g['status'] == 'PASS' for g in gate_results):
                    warnings.warn(f"Physics gate regression at epoch {epoch}: {gate_results}")
        
        # Export
        onnx_path = self._export_onnx(model)
        model_card = self._generate_updated_model_card(model, gate_results)
        
        return FineTuneResult(
            onnx_path=onnx_path,
            model_card=model_card,
            final_weights=model.state_dict(),
            gate_history=gate_history
        )
```

---

## 10. RISK REGISTER & MITIGATIONS

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|------------|
| **R1** | **Prime partner walks / delays** | High | Critical | Multi-prime strategy (3+ LOIs before Series A); OTA/DIU direct paths |
| **R2** | **Phase 0.5 benchmarks not credible** | Medium | High | Co-develop with Prime; publish generator validation vs. NASA/AFRL refs |
| **R3** | **Model Card evidence rejected by IV&V** | Medium | High | Early engagement with DOT&E/AFRL test community; pilot IV&V in Phase I |
| **R4** | **Bittensor/subnet instability** | Medium | High | Fallback: Centralized validator pool (Carbon Labs) for Phase I delivery |
| **R5** | **ITAR classification blocks public subnet** | Low | Critical | Legal opinion: Architecture ≠ technical data; only weights are controlled |
| **R6** | **ATO timeline exceeds contract** | High | Medium | Change classification framework; version-lock for deployment |
| **R7** | **Competitor (PhysicsX/NVIDIA) gets Prime lock-in** | Medium | High | Speed: Evidence pipeline + Phase 0.5 benchmarks = first-mover |
| **R8** | **Talent: DoD BD + SciML + Distributed Systems** | High | Critical | Hire DoD BD first; SciML = Harshdeep; Distributed = dedicated hire |
| **R9** | **Export control on strategy.json** | Low | Medium | Legal review: Architecture configs typically EAR99; weights = controlled |
| **R10** | **Subnet token volatility hurts validator economics** | Medium | Medium | Team 18% subsidizes early validators; revenue buyback floor |

---

## 11. 90-DAY EXECUTION PLAN

### Month 1: Foundation & Partnerships

| Week | Technical (Harshdeep + Team) | Business (Founder + BD) |
|------|------------------------------|-------------------------|
| 1 | JAX backbone audit (FNO/GINO/WNO); Generator v1.0 for 7 PDEs | Incorporate Carbon Labs Inc.; Hire DoD BD Lead |
| 2 | Physics gates 1-3 (mass, energy, boundary); FEniCS validation harness | 10 Prime discovery calls; Target 3 LOI conversations |
| 3 | Training pipeline + Model Card generator; ONNX export test | Draft Teaming Agreement template; Legal review (ITAR/export) |
| 4 | MCP server v0; Miner Toolkit skeleton | Submit AFWERX/STRATFI abstract; DIU CSO application |

**Month 1 Gate**: 3 Prime LOIs + Testnet validator running + 3 PDE generators validated

### Month 2: Phase 0.5 + Evidence Pipeline

| Week | Technical | Business |
|------|-----------|----------|
| 5-6 | **Phase 0.5 Generators**: NACA 0012, CRM, HIFiRE-1 | Sign 1 Teaming Agreement; Prime co-writes SBIR Phase I |
| 7-8 | **Evidence Compiler**: DI-SESS-82483 manifest + ONNX benchmark | Draft Phase I proposal (Prime lead, Carbon sub) |
| 9 | **SysML Template** + Air-gapped Toolkit v0 | Submit SBIR Phase I; Engage DOT&E/AFRL test liaison |
| 10 | **Integration Test**: Full pipeline — Model Card → Manifest → SysML | Prime technical review of evidence package |

**Month 2 Gate**: Evidence package accepted by Prime technical lead; SBIR submitted

### Month 3: Hardening & Revenue

| Week | Technical | Business |
|------|-----------|----------|
| 11-12 | Gate calibration audit (third party); Generator version lock | Phase I award decision (if fast) / OTA fallback |
| 13 | **Model Zoo API v1**: 7 Phase 0 + 3 Phase 0.5 specialists | Commercial Tier 1 subscriptions (non-DoD) |
| 14 | **Sponsored Challenge Factory**: Prime can launch custom challenges | 2 Sponsored Challenge LOIs (commercial + defense) |
| 15 | **Documentation**: Prime onboarding guide, compliance cookbook | Series A deck with DoD traction |

**Month 3 Gate**: $100k ARR (commercial) + 1 Prime partner + SBIR/OTA in pipeline

---

## 🎯 NEW INNOVATIONS ADDED IN V2

### 1. **Change Classification Framework**
Solves the "continuous retraining = re-accreditation" problem. Primes can now do Level 1 weight updates rapidly.

### 2. **Phase 0.5 Defense Benchmarks**
Bridges the "toy problem" credibility gap. NACA 0012, CRM, HIFiRE are *real* validation targets.

### 3. **Air-Gapped Miner Toolkit as Product**
Not just a subnet feature — a **licensable product** for Prime enclaves. Recurring revenue.

### 4. **Validator Attestation in Evidence**
`validator_set` + `consensus_weights` + `block_height` = supply chain provenance for RMF.

### 5. **Prime-Centric GTM (Not Direct)**
Realistic path: Subcontract → Teaming → License → JV. Avoids FCL/past performance trap.

### 6. **Explicit "Carbon Does Not" List**
Builds trust. Primes appreciate vendors who know their boundaries.

---

## 📌 FINAL POSITIONING FOR PRIME CONVERSATIONS

> **"We don't sell you a model. We sell you a verification engine that cuts your IV&V timeline in half."**
> 
> - **Input**: Your classified geometry + telemetry
> - **Carbon provides**: Pre-validated architecture + physics gate evidence + reproduction kit
> - **You do**: Fine-tune, classify, benchmark, accredit, deploy
> - **Contract**: Subcontract on your vehicle. We're a technology provider, not a prime.

---

**This is buildable, defensible, and fundable. The technical work aligns with Harshdeep's expertise. The business model aligns with how DoD actually buys. The compliance mapping is accurate. Let's execute.**
