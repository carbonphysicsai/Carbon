# Runtime Julia Truth Oracle — Minimal Viable SciML Service

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Protocol Appendix — Infrastructure Appendix  
**Audience:** Julia Engineer, DevOps, Harshdeep (Tech Lead)  
**Status:** **Phase 0-1A: Mock Only** | **Phase 1A+: Real Service**  
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

---

### 2.2 Request/Response Schemas

#### `POST /solve_pde`
```json
// Request
{
  "action": "solve_pde",
  "pde_spec": {
    "type": "poisson|navier_stokes|heat|elasticity|reacting_ns|fsi",
    "dimension": "2D|3D",
    "pde": "poisson|navier_stokes|...",
    "parameters": { "mach": 0.8, "reynolds": 1e6, ... }
  },
  "params": { "mach": 0.8, "reynolds": 1e6, "aoa": 2.0 }
}

// Response
{
  "solution": [[...]],
  "coords": [[...]],
  "times": [0.0, 0.01, ...],
  "metadata": {
    "solver": "Vern9",
    "abstol": 1e-12,
    "reltol": 1e-12,
    "solve_time_seconds": 2.3
  }
}
```

#### `POST /adjoint`
```json
// Request
{
  "action": "adjoint_sensitivity",
  "initial_state": [[...]],
  "params": { "mach": 0.8, ... },
  "loss_function": "physics_residual"
}

// Response
{
  "adjoint_gradients": [[...]],
  "rel_error": 1.2e-12,
  "forward_time_seconds": 0.45,
  "adjoint_time_seconds": 0.12,
  "success": true
}
```

#### `POST /symbolic_loss`
```json
// Request
{
  "action": "symbolic_loss",
  "symbolic_expression": "λ₁ * (div(u))^2 + λ₂ * (dρ/dt + div(ρu))^2",
  "variables": ["u", "rho", "lambda1", "lambda2"]
}

// Response
{
  "jax_code": "def loss_fn(params, state): ...",
  "julia_expression": "λ₁ * (∇·u)^2 + λ₂ * (∂ρ/∂t + ∇·(ρu))^2"
}
```

#### `POST /validate`
```json
// Request
{
  "action": "validate_solution",
  "model_prediction": [[...]],
  "pde_spec": { ... },
  "params": { ... }
}

// Response
{
  "passes": true,
  "error_metrics": {
    "l2_relative": 0.0012,
    "linf": 0.0034,
    "conservation_error": 1.2e-7
  },
  "reference_solution": { ... },
  "passes_threshold": true
}
```

---

## 3. Julia Service Implementation

### 3.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    JULIA/SCIML SERVICE                        │
├─────────────────────────────────────────────────────────────┤
│  HTTP Server (HTTP.jl)  →  Router (HTTP.jl)                │
│         │                                                    │
│         ├─ /health          → Health check                   │
│         ├─ /solve_pde       → solve_pde_reference()          │
│         ├─ /adjoint         → compute_adjoint_sensitivity()  │
│         ├─ /symbolic_loss   → ModelingToolkit.jl bridge      │
│         └─ /validate        → Validation against reference  │
│                                                             │
│  SciML Stack:                                               │
│  • DifferentialEquations.jl  (Vern9, Tsit5, Rodas5)        │
│  • NeuralPDE.jl             (PINN/DeepONet baselines)      │
│  • ModelingToolkit.jl       (Symbolic → JAX loss terms)     │
│  • SciMLSensitivity.jl      (Adjoint: ReverseDiffVJP)       │
│  • MethodOfLines.jl         (PDE discretization)           │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Core Implementation

```julia
# julia/sciML_service.jl
using HTTP, JSON3, Sockets
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
using MethodOfLines, SciMLSensitivity, ModelingToolkit
using LinearAlgebra, Statistics, CUDA

const PORT = 8083

function start_server()
    HTTP.serve(Sockets.localhost, PORT) do http::HTTP.Messages.Request
        try
            request = JSON3.read(String(http.body))
            response = handle_request(request)
            return HTTP.Response(200, JSON3.write(response))
        catch e
            @error "Request failed" exception=e
            return HTTP.Response(500, JSON3.write(Dict("error" => string(e))))
        end
    end
end

function handle_request(request::Dict)
    action = get(request, "action", "")
    if action == "solve_pde"
        return solve_pde_reference(request["pde_spec"], request["params"])
    elseif action == "adjoint_sensitivity"
        return compute_adjoint_sensitivity(request)
    elseif action == "symbolic_loss"
        return generate_symbolic_loss(request)
    elseif action == "validate_solution"
        return validate_against_reference(request)
    else
        return Dict("error" => "Unknown action: $action")
    end
end

function solve_pde_reference(pde_spec::Dict, params::Dict)
    @variables t x y z
    @parameters p[1:length(params)]
    eqs = build_pde_system(pde_spec, params)
    prob = ODEProblem(eqs, u0, tspan, params)
    sol = solve(prob, Vern9(), abstol=1e-12, reltol=1e-12, saveat=0.01)
    return Dict(
        "solution" => Array(sol),
        "times" => sol.t,
        "success" => true
    )
end

function compute_adjoint_sensitivity(request::Dict)
    u0 = request["initial_state"]
    params = request["params"]
    loss_fn = request["loss_function"]
    prob = ODEProblem(ode_fn, u0, tspan, params)
    sol = solve(prob, Tsit5(), saveat=0.01)
    adj_sol = adjoint_sensitivities(sol, loss_fn,
        alg=InterpolatingAdjoint(autojacvec=ReverseDiffVJP()))
    return Dict("adjoint_gradients" => Array(adj_sol))
end

function generate_symbolic_loss(request::Dict)
    symbolic_expr = request["symbolic_expression"]
    vars = request["variables"]
    @variables vars...
    expr = Meta.parse(symbolic_expr)
    loss_fn = eval(build_function(expr, vars))
    return Dict(
        "julia_code" => string(loss_fn),
        "jax_translation" => translate_to_jax(loss_fn)
    )
end

function validate_against_reference(request::Dict)
    model_prediction = request["model_prediction"]
    pde_spec = request["pde_spec"]
    params = request["params"]
    reference = solve_pde_reference(pde_spec, params)
    error_metrics = compute_error_metrics(request["model_prediction"], reference["solution"])
    return Dict(
        "passes" => all(v < 1e-3 for v in error_metrics.values()),
        "error_metrics" => error_metrics,
        "reference_solution" => reference
    )
end
```

---

## 3. Minimal Phase 1A Service (Adjoint Only)

### 3.1 Minimal Service Scope (Phase 1A)

```julia
# julia/sciML_service_minimal.jl
# Phase 1A: ONLY adjoint_consistency gate needed

using HTTP, JSON3, Sockets
using DifferentialEquations, SciMLSensitivity, ReverseDiff
using LinearAlgebra, Statistics

const PORT = 8083

function start_server()
    HTTP.serve(Sockets.localhost, PORT) do http::HTTP.Messages.Request
        try
            request = JSON3.read(String(http.body))
            if request["action"] == "adjoint_sensitivity"
                response = compute_adjoint_sensitivity(request)
                return HTTP.Response(200, JSON3.write(response))
            elseif request["action"] == "health"
                return HTTP.Response(200, JSON3.write(Dict("status" => "ok")))
            else
                return HTTP.Response(404, JSON3.write(Dict("error" => "Not implemented in minimal service")))
            end
        catch e
            @error "Request failed" exception=e
            return HTTP.Response(500, JSON3.write(Dict("error" => string(e))))
        end
    end
end

function compute_adjoint_sensitivity(request::Dict)
    u0 = request["initial_state"]
    params = request["params"]
    loss_fn_str = request["loss_function"]
    loss_fn = build_loss_function(loss_fn_str)
    prob = ODEProblem(ode_fn, u0, tspan, params)
    sol = solve(prob, Tsit5(), saveat=0.01, abstol=1e-12, reltol=1e-12)
    adj_sol = adjoint_sensitivities(sol, loss_fn,
        alg=InterpolatingAdjoint(autojacvec=ReverseDiffVJP()))
    adj_grad = Array(adj_sol)
    fd_grad = finite_difference_gradient(loss_fn, sol.u[end])
    rel_error = norm(adj_grad - fd_grad) / norm(fd_grad)
    return Dict(
        "adjoint_gradients" => adj_grad,
        "rel_error" => rel_error,
        "forward_time_seconds" => 0.0,
        "adjoint_time_seconds" => 0.0,
        "success" => true
    )
end
```

---

## 3. Mock Client (Phase 0-1A)

```python
# carbon/sciml/mock_client.py
class MockSciMLClient:
    """Zero-dependency mock for Phase 0-1A. Analytic solutions only."""

    ANALYTIC_SOLUTIONS = {
        "poisson": lambda params: analytic_poisson(params),
        "burgers": lambda params: analytic_burgers(params),
        "darcy": lambda params: analytic_darcy(params),
        "heat": lambda params: analytic_heat(params),
        "elasticity": lambda params: analytic_elasticity(params),
        "thermo_elasticity": lambda params: analytic_thermo_elasticity(params),
    }

    async def solve_pde_reference(self, pde_spec: Dict, params: Dict) -> Dict:
        solver = self.ANALYTIC_SOLUTIONS.get(pde_spec["type"])
        if not solver:
            raise ValueError(f"No analytic solution for {pde_spec['type']}")
        return {"solution": solver(params), "times": [0.0, 1.0], "success": True}

    async def compute_adjoint_sensitivity(self, initial_state, params, loss_fn):
        return {"adjoint_gradients": analytic_adjoint(params), "rel_error": 1e-12}

    async def validate_against_reference(self, model_prediction, pde_spec, params):
        return {"passes": True, "error_metrics": {"l2": 1e-10}}
```

---

## 4. Deployment Specification

### 4.1 Dockerfile (Minimal)

```dockerfile
# julia/Dockerfile.sciml
FROM julia:1.10-bullseye

RUN apt-get update && apt-get install -y \
    python3 python3-pip curl git && \
    rm -rf /var/lib/apt/lists/*

RUN julia --project -e '
    using Pkg
    Pkg.add([
        "DifferentialEquations", "NeuralPDE", "ModelingToolkit",
        "SciMLSensitivity", "MethodOfLines",
        "Symbolics", "Optimization", "OptimizationOptimizers",
        "HTTP", "JSON3", "Sockets", "CUDA", "ReverseDiff"
    ])
    Pkg.precompile()
'

RUN pip install --no-cache-dir httpx numpy

COPY julia/sciML_service.jl /app/sciML_service.jl
COPY julia/start_server.jl /app/start_server.jl

EXPOSE 8083
CMD ["julia", "--project", "/app/start_server.jl"]
```

### 4.2 Kubernetes Deployment (Phase 1A: 1 Spot H100)

```yaml
# k8s/sciml-deployment-phase1a.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: carbon-sciml-service
  namespace: carbon
spec:
  replicas: 1
  selector:
    matchLabels:
      app: carbon-sciml
  template:
    metadata:
      labels:
        app: carbon-sciml
    spec:
      runtimeClassName: nvidia
      containers:
      - name: sciml-service
        image: ghcr.io/carbon/sciml-service:v2.1.0-phase1a
        ports:
        - containerPort: 8083
        env:
        - name: JULIA_NUM_THREADS
          value: "16"
        - name: JULIA_DEPOT_PATH
          value: "/opt/julia/depot"
        - name: MOCK_FALLBACK
          value: "true"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
          limits:
            nvidia.com/gpu: 1
            memory: "64Gi"
            cpu: "16"
        volumeMounts:
        - name: julia-depot
          mountPath: /opt/julia/depot
        livenessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: julia-depot
        persistentVolumeClaim:
          claimName: carbon-julia-depot
---
apiVersion: v1
kind: Service
metadata:
  name: carbon-sciml
  namespace: carbon
spec:
  selector:
    app: carbon-sciml
  ports:
  - protocol: TCP
    port: 8083
    targetPort: 8083
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-julia-depot
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  storageClassName: nvme-fast
```

---

## 5. Mock Fallback Strategy (Phase 1A)

```python
# carbon/validator/sciml_validation.py

class SciMLValidationMixin:
    def __init__(self, config: Dict):
        self.config = config
        self.sciml_client = self._create_client()

    def _create_client(self) -> SciMLClient:
        endpoint = self.config.get("sciml_endpoint", "http://carbon-sciml:8083")
        use_mock = self.config.get("sciml_mock_fallback", True)
        return SciMLClient(endpoint, mock_fallback=use_mock)

    async def _run_adjoint_gate(self, state: TrainState) -> GateResult:
        try:
            adjoint_result = await self.sciml_client.compute_adjoint_sensitivity(
                model_fn=self.model_apply_fn,
                params=state.params,
                loss_fn="physics_residual"
            )
            rel_error = adjoint_result["rel_error"]
            score = 1.0 / (1.0 + jnp.exp(20.0 * (rel_error - 1e-4) / 1e-4))
            return GateResult(
                gate_id="adjoint_consistency",
                threshold=1e-4,
                result=rel_error,
                score=float(score),
                status="PASS" if score > 0.5 else "FAIL"
            )
        except Exception as e:
            logger.warning(f"SciML adjoint failed: {e}, using mock")
            return GateResult(
                gate_id="adjoint_consistency",
                threshold=1e-4,
                result=0.0,
                score=0.0,
                status="FAIL",
                details={"fallback": "sciml_unavailable", "error": str(e)}
            )
```

---

## 5. Cost Summary (Minimal Phase 1A)

| Component | Spec | Monthly Cost |
|-----------|--------|--------------|
| **GPU** | 1× H100 Spot | ~$800/mo |
| **Julia Depot PVC** | 50GiB NVMe | $75/mo |
| **Network** | 10TB/mo | $50/mo |
| **Total** | | **~$850/mo** |

**With mock fallback:** Spot preemption → automatic fallback to mock client. Zero downtime.

---

## 5. Decision Checklist

| Decision | Status | Owner |
|----------|--------|-------|
| Phase 0: Mock only | ✅ Decided | You |
| Phase 1A: 1 Spot H100 + mock fallback | ✅ Decided | You |
| Julia dev hire | Month 2 | You |
| Real Julia service deploy | Month 4 | You |
| Phase 1B+ full Julia | Deferred to Phase 1B | You |

---

## Summary

| What | Phase | Cost | Complexity |
|------|-------|------|------------|
| **Mock Client** | Phase 0-1A | $0 | Trivial |
| **Minimal Julia (Adjoint only)** | Phase 1A | ~$800/mo | Low (single endpoint) |
| **Full Julia Service** | Phase 1B+ | ~$2.4k/mo | Medium |
| **Full HA (3 replicas)** | Phase 3+ | ~$8.5k/mo | High |

**Decision:** Start with mock. Deploy minimal Julia (adjoint only) at Phase 1A. Full service at Phase 1B.
