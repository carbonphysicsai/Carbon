"""Prospective executable subset; never a qualification or comparison policy."""

from __future__ import annotations

import hashlib
import json
import math

from carbon.chain.models import CARBON_NETUID
from carbon.registry import ChallengeKey

CHALLENGE = ChallengeKey("burgers-dynamics-v1", "1.0")
SESSION_PROFILE = "carbon.burgers-supervised-development.v2"
TIME_SCALE = 27.0  # T=4*t_c <= 4/(A*k_rms) <= 4/0.15 < 27 for every V1 parent.


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def profile_document() -> dict[str, object]:
    """Return fresh data, so callers cannot mutate the session's contract."""
    return {
        "schema": SESSION_PROFILE,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "physics": {
            "law": "u_t + (u^2/2)_x = nu*u_xx",
            "domain_length": 2 * math.pi,
            "boundary": "periodic",
            "forcing": "none",
            "population_owner": "carbon.generators.burgers_dynamics",
            "families": ["harmonic", "localized_packet", "multiscale"],
            "reynolds_edges": [0.5, 1.0, 2.0, 4.0, 8.0],
            "amplitude_interval": [0.15, 0.35],
            "mean_over_amplitude_interval": [-1.0, 1.0],
            "modes": 12,
            "horizon_characteristic_times": 4,
        },
        "sampling": {
            "roles": ["TRAIN", "EVAL", "STRESS"],
            "cells_per_role": list(range(12)),
            "ordinal": 0,
            "build": 0,
            "counts": {"TRAIN": 12, "EVAL": 12, "STRESS": 12},
            "full_v1_counts": {"TRAIN": 72, "EVAL": 48, "STRESS": 120},
            "separation": "C-AUTH1 MockContext role-separated derivation; evaluator-only EVAL/STRESS realizations",
            "grid_points": 64,
            "intervals_per_phase": 4,
            "times_per_parent": 13,
            "coverage": "One parent per family/Re cell and role; one training build; reduced space/time resolution. No full V1, tail, repeat-build or population adequacy claim.",
        },
        "reconstruction": {
            "compiler": "B-02B",
            "adapter": "C-02 carbon_jax_lab 0.1.1",
            "backbones": ["fno", "deeponet"],
            "steps": {"minimum": 32, "maximum": 64},
            "replicas": 3,
            "selection": "all replicas retained; no best-replica selection",
            "training_labels": "C-04 candidate-primary reference for TRAIN only",
            "input_interface": ["initial", "viscosity", "requested_times", "positions"],
            "task_domain_length": 2 * math.pi,
            "task_time_scale": TIME_SCALE,
            "time_scale_basis": "Population-wide upper bound: 4/(minimum A 0.15 * minimum k_rms 1) < 27; no cohort or outcome fitting.",
            "task_velocity_scale": 1.0,
            "candidate_code": "none; registered declarative strategies only",
        },
        "reference": {
            "primary": "cole_hopf_fourier_quadrature",
            "witness_available_not_selected": "periodic_finite_volume_rusanov_ssprk3",
            "crosscheck_available_not_selected": "dealiased_fourier_etdrk4",
            "settings": "C-04 reference_settings(CANDIDATE_PRIMARY, 64)",
            "qualification": "unqualified; disagreement and reference uncertainty not measured by this subset",
        },
        "measurement": {
            "owner": "C-05",
            "field_phase_rms": True,
            "qoi": ["maximum_compression", "peak_dissipation", "energy_half_time"],
            "physics": [
                "initial_condition",
                "periodicity",
                "conserved_mean",
                "maximum_principle",
                "energy_dissipation_balance",
                "weak_local_pde",
            ],
            "scientific_limits": None,
            "uncertainty_limits": None,
            "score": None,
            "comparison": None,
            "decision": "UNRESOLVED_NO_QUALIFIED_LIMIT",
        },
        "feedback": {
            "policy": "development aggregate normalized errors and physics defects only",
            "excluded": [
                "reference values",
                "case coordinates",
                "parent IDs",
                "seeds",
                "labels",
                "evaluator paths",
                "credentials",
                "per-case diagnostics",
            ],
            "eligibility": {
                "protected": False,
                "official": False,
                "score": False,
                "reward": False,
            },
        },
        "budget": {
            "proposal_attempts": 3,
            "invalid_proposals_consume_attempt": True,
            "accepted_evaluations": 3,
            "training_runs_max": 9,
            "training_steps_max": 576,
            "reference_runs_max": 36,
            "measurement_runs_max": 216,
            "worker_cpu": 2,
            "worker_memory_bytes": 4 * 1024**3,
            "worker_swap_bytes": 0,
            "worker_deadline_seconds": 600,
            "session_worker_wall_seconds": 7200,
            "session_wall_seconds": 10800,
            "reserve_worst_case_before_each_worker": True,
            "automatic_retry": False,
        },
        "stop": [
            "proposal/evaluation/provider/worker/wall budget",
            "uncertain dispatch",
            "quarantine",
            "reference or infrastructure failure",
            "operator cancellation",
        ],
        "chain_profile": "carbon.public-synthetic-testnet.development.v1",
        "chain_netuid": CARBON_NETUID,
        "publication": "separately authorized all-burn only",
    }


def profile_digest() -> str:
    return digest(canonical(profile_document()))
