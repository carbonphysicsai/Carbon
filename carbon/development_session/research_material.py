"""Allowlisted task mathematics and reproducible recipe documentation."""

from __future__ import annotations

from carbon.research import RESEARCH_NAMESPACE, SUPPORTED_OPERATIONS

from .profile import canonical, digest
from .research_catalog import public_catalog
from .research_profile import document


def objective():
    profile = document()
    return {
        "schema": "carbon.autoresearch.public-objective.v1",
        "profile": profile["schema"],
        "physics": profile["physics"],
        "units": "nondimensional x, t, u and viscosity; no industrial unit calibration",
        "input": [
            "initial field on 64 periodic spatial points",
            "positive viscosity",
            "requested times",
        ],
        "output": "u(t,x) on the requested grid; float predictions measured independently",
        "initial_field": "mean + sum(a_k*cos(k*x)+b_k*sin(k*x)), k=1..12",
        "generator_laws": {
            "amplitude": "uniform [0.15,0.35); coefficients normalized to fluctuation RMS amplitude",
            "mean": "amplitude * uniform [-1,1)",
            "reynolds": "log-uniform within fixed [0.5,1),[1,2),[2,4),[4,8) strata",
            "viscosity": "amplitude / (Re * k_rms)",
            "characteristic_time": "min(1/(amplitude*k_rms),1/(nu*k_rms^2))",
            "horizon": "4 characteristic times",
            "harmonic": "integer carrier 1..3 plus second harmonic ratio uniform [0.1,0.3), phase uniform [0,2pi)",
            "localized_packet": "exp(kappa*(cos(x)-1))*sin(carrier*x), carrier 3..5, kappa uniform [2,5); 4096-point projection onto 12 Fourier modes",
            "multiscale": "mode^-exponent * uniform [0.5,1.5), exponent uniform [0.8,1.6), independent uniform phases",
        },
        "sampling": profile["sampling"],
        "score_rule": profile["objective_math"],
        "score_rule_digest": profile["objective_math_digest"],
        "active_rule_scope": profile["rule_scope_binding"],
        "limits": {
            "development_subset": True,
            "qualification": False,
            "case_and_replica_dependence": "three construction replicas do not establish population generalization",
            "reference_uncertainty": "refinement indicator is not a certified truth error bound",
            "practice": "adaptive selection material, not final confirmation",
        },
        "budgets": profile["budgets"],
        "elapsed_seconds": profile["elapsed_seconds"],
        "worker": profile["final_worker"],
        "final_feedback": "authorized aggregate measurements, physical gate dispositions and comparison only; no final realized cases, labels or identities",
    }


def capabilities():
    from carbon.reference_runtime.model import RUNTIME_DEPENDENCIES

    return {
        "schema": "carbon.autoresearch.capabilities.v1",
        "namespace": RESEARCH_NAMESPACE,
        "operations": list(SUPPORTED_OPERATIONS),
        "recipes": public_catalog(),
        "installed_pinned_dependencies": dict(RUNTIME_DEPENDENCIES),
        "python": "3.11.16",
        "public_npz_fields": {
            "initial": "case,x",
            "viscosity": "case",
            "times": "case,t",
            "solution": "case,t,x",
            "positions": "x",
            "metadata": "JSON scalar: schema, role, provenance, domain_length, fingerprint",
        },
        "prediction_contract": "direct u(initial,nu,t,x); no registered rollout or arbitrary submitted code",
        "parameter_notes": {
            "applicability": "which families accept each field is recipes.surfaces[field].architecture (null = every family); a field another family owns is refused by name",
            "width": "channel width. FNO, DeepONet, Haar, GNO and GINO: even, since the installed configuration fixes two heads. transolver: divisible by heads. Actual memory/time admission applies",
            "n_modes": "spectral modes (n_modes/2+1 allocated); even only, since odd values alias. GINO's modes must also fit its latent grid",
            "depth_remat": "number of stacked blocks, and whether to rematerialize them",
            "branch_points": "DeepONet sensor count",
            "transolver": "Carbon's Transolver: the lab's physics_attention1d slice/attention/deslice blocks, adapted from THUML/Transolver with declared departures (softplus-parameterized temperature, optional quadrature weights, dropout fixed at zero). The meaning is Carbon's implementation, not any other library's model of the same name",
            "heads": "attention heads; width must divide evenly across them",
            "slices": "learned physical-state slices each head attends over",
            "expansion": "width multiplier of each block's feed-forward layer",
            "wavelet_levels": "Haar decomposition levels; the 64-point TRAIN grid must halve that many times",
            "neighborhood_radius": "radius of each point's graph neighbourhood in periodic unit coordinates (the lab's graph_radius)",
            "latent_points": "points on GINO's latent grid, where its spectral blocks run",
            "hard_initial_condition": "u0 + (t/27)*raw output",
            "enforce_mean": "project each predicted spatial field to the permitted initial mean; no accuracy credit by itself",
            "h1_weight": "spatial-derivative training error; requires additional derivative work",
            "pde_weight": "autodifferential Burgers residual training loss, not a weak-form evaluator; additional derivative cost",
            "inference_weights": "params or EMA; selected weights retained in frozen reconstruction. Supplying ema_decay requires EMA inference, since otherwise it would change nothing",
            "steps": "target updates; choose a recipe that completes within the operative final limit. Incomplete reconstruction is retained and cannot be accepted",
            "warmup_steps_physics_warmup_steps": "each must be strictly less than steps; supplying physics_warmup_steps requires a positive pde_weight, since the ramp scales only the PDE term. A recipe Carbon cannot rebuild exactly as submitted is refused with each field and rule named",
        },
        "workspace_actions": [
            "public_material",
            "inventory",
            "read_file",
            "write_file",
            "notebook",
            "capability_request",
            "run_python",
        ],
        "unsupported": [
            "registered public prior packs",
            "checkpoint resume",
            "novel submitted architectures/optimizers",
            "custom training sampler/curriculum",
            "GPU",
        ],
        "prohibited": [
            "final cases or labels",
            "evaluator edits",
            "repository/home mounts",
            "network access inside numerical workers",
            "Docker control",
            "credentials",
            "chain writes",
        ],
        "forecasts": "unresolved until observed; static resource metadata is not a calibrated forecast",
        "capability_requests": "record purpose, hypothesis, evidence, unavailable reason, expected benefit, cost, safe design and verification; requests grant no authority",
    }


class PublicMaterial:
    def __init__(self, data):
        self.data = data

    def __call__(self, name, workspace):
        if name == "training_data":
            return self.data.disclose("research-train", workspace)
        if name == "practice_data":
            return self.data.disclose("research-validation", workspace)
        if name == "objective":
            value = objective()
        elif name == "capabilities":
            value = capabilities()
        elif name == "reference_method":
            value = {
                "method": "C-04 Cole-Hopf Fourier quadrature 1.0",
                "primary_internal_grid": 1024,
                "output_grid": 64,
                "times_per_parent": 13,
                "precision": "float64",
                "primary_calls_per_trajectory": 1,
                "research_refinements": 0,
                "reference_failure": "stop; never replace a difficult case",
                "final_reference_check": "separate controller-owned refinement indicators required by balanced-v2",
                "quality": "unqualified numerical reference; primary-only practice has no measured uncertainty bound",
            }
        else:
            raise ValueError("material outside public allowlist")
        payload = canonical(value)
        workspace.put(name + ".json", payload)
        return {"document": value, "file": name + ".json", "digest": digest(payload)}
