# Runtime Julia Truth Oracle — Minimal Viable SciML Service

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Protocol Appendix — Infrastructure Appendix  
**Audience:** Julia Engineer, DevOps, Tech Lead  
**Phase:** **Phase 0-1A: Mock Only** | **Phase 1A+: Real Service**  
**Related:** `SPEC.md` §15, `IMPLEMENTATION.md` §11-13, `OPERATIONS.md` §5

---

## TL;DR

**Job:** Provide validators a **ground-truth oracle** for reference PDE solves, adjoints, and (later) symbolic losses — so physics gates can check against something other than the generator’s own numerical path.

**Phase policy**
| Phase | Mode |
|-------|------|
| **0–1A** | Mock client + analytic solutions (no live Julia service required) |
| **1A+** | Real Julia/SciML service for reference solves and adjoints |
| **2A+** | Symbolic loss path via ModelingToolkit where enabled |

**Endpoints (v1):** `GET /health`, `POST /solve_pde`, `POST /adjoint`, `POST /symbolic_loss`, optional `POST /validate`.

**Ops note:** When oracle checks are required, oracle downtime is validation-degraded (treat as high severity). See `Operations.md`.

**Non-goals:** Not the miner training loop; not the Score Pack; not Landscape.

---

## 1. Purpose

This document specifies the **minimal viable Julia/SciML Ground Truth Oracle** — a dedicated Julia service providing mathematically rigorous reference solutions and exact adjoint sensitivities for Carbon's physics gate validation.

**Scope:** Phase 1A+ (Adjoint Consistency Gate) → Phase 4 (3D Turbulence)  
**Phase 0-1A:** Mock client with analytic solutions (no Julia service required)

---

## 2. Service Interface (v1.0)

### 2.1 API Endpoints (HTTP/JSON)

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `GET /health` | GET | Liveness/readiness probe | All |
| `POST /solve_pde` | POST | High-fidelity reference solution | All |
| `POST /adjoint` | POST | Exact adjoint gradients (SciMLSensitivity.jl) | 1A+ |
| `POST /symbolic_loss` | POST | Symbolic loss from ModelingToolkit.jl | 2A+ |
| `POST /validate` | POST | Validate model vs reference | Optional |

### 2.2 Request/Response Schemas

#### `POST /solve_pde`
```json
{
  "action": "solve_pde",
  "pde_spec": {
    "type": "poisson|navier_stokes|heat|elasticity|reacting_ns|fsi",
    "dimension": "2D|3D",
    "pde": "poisson|navier_stokes|...",
    "parameters": { "mach": 0.8, "reynolds": 1e6 }
  },
  "params": { "mach": 0.8, "reynolds": 1e6, "aoa": 2.0 }
}
```

#### `POST /adjoint`
```json
{
  "action": "adjoint_sensitivity",
  "initial_state": [[...]],
  "params": { "mach": 0.8 },
  "loss_function": "physics_residual"
}
```

#### `POST /symbolic_loss`
```json
{
  "action": "symbolic_loss",
  "pde_spec": { "type": "navier_stokes" },
  "model_state": [[...]]
}
```

---

## 3. Phase rollout

| Phase | Requirement |
|-------|-------------|
| 0 | Mock only; POC may use analytic references |
| 1A | Live `/solve_pde` when reference agreement is required beyond generator path |
| 1A+ | `/adjoint` for adjoint-consistency gates |
| 2A+ | `/symbolic_loss` when ModelingToolkit losses are in the pack |

---

## 4. Ops coupling

- Health checks on the oracle when oracle-backed gates are active
- Lean eval SLO must not be blocked indefinitely by oracle latency — timeouts and fail-closed policy per `Operations.md`
- Do not expose oracle endpoints to miners
- Deployment (Dockerfile, K8s, `SciMLClient`) as previously specified under `IMPLEMENTATION.md` §11–13 and `Operations.md`

---

*Canonical runtime contract for the Julia/SciML ground-truth path. Keep Phase 0 mock path valid until 1A requires the live service.*
