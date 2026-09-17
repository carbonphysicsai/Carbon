"""Prospective D4 recipe catalog, compiled by B-02B and executed by C-02.

This does not mutate the historical supervised-development.v2 catalog.
Only levers consumed by the selected installed architecture are applicable.
"""

from __future__ import annotations

import json
from dataclasses import replace

from carbon import construction as c
from carbon.construction.compiler import CompileAccepted
from carbon.reconstruction.profile import compile_development_profile

from .contracts import SessionContracts, build_contracts, semantic

CATALOG_VERSION = "carbon.burgers-autoresearch-recipes.v1"
# Bounds are engineering admission bounds, not quality or scientific claims.
# Actual CPU/memory/time admission is authoritative even inside these bounds.
# name: group, type, minimum/choices, maximum, default, architecture
SURFACES = {
    "steps": ("train", "uint", 2, 1000000, 512, None),
    "width": ("model", "uint", 2, 128, 24, None),
    "depth": ("model", "uint", 1, 8, 2, "fno"),
    "n_modes": ("model", "uint", 2, 64, 16, "fno"),
    "branch_points": ("model", "uint", 2, 64, 32, "deeponet"),
    "remat": ("model", "bool", None, None, False, "fno"),
    "hard_initial_condition": ("task", "bool", None, None, True, None),
    "enforce_mean": ("task", "bool", None, None, True, None),
    "batch_size": ("train", "uint", 1, 64, 8, None),
    "microbatches": ("train", "uint", 1, 8, 1, None),
    "learning_rate": ("train", "float", 0.000001, 0.05, 0.002, None),
    "min_learning_rate_ratio": ("train", "float", 0.0, 1.0, 0.1, None),
    "warmup_steps": ("train", "uint", 0, 100000, 0, None),
    "weight_decay": ("train", "float", 0.0, 0.1, 0.0001, None),
    "clip_norm": ("train", "float", 0.001, 100.0, 1.0, None),
    "beta1": ("train", "float", 0.0, 0.9999, 0.9, None),
    "beta2": ("train", "float", 0.0, 0.99999, 0.999, None),
    "adam_epsilon": ("train", "float", 1e-12, 0.01, 1e-8, None),
    "ema_decay": ("train", "float", 0.0, 0.99999, 0.99, None),
    "relative_loss": ("train", "bool", None, None, False, None),
    "h1_weight": ("train", "float", 0.0, 10.0, 0.0, None),
    "pde_weight": ("train", "float", 0.0, 10.0, 0.0, None),
    "physics_warmup_steps": ("train", "uint", 0, 100000, 0, None),
    "inference_weights": ("train", "choice", ("params", "ema"), None, "params", None),
}


def research_contracts() -> SessionContracts:
    old = build_contracts()
    assembly = replace(
        old.assembly, object_id="burgers_autoresearch_assembly", object_version="1.0"
    )
    template = next(e for e in old.catalog.entries if e.surface_id == "steps")
    entries = [e for e in old.catalog.entries if e.surface_id != "steps"]
    types = {
        "uint": c.SurfaceValueType.UINT64,
        "float": c.SurfaceValueType.FLOAT64,
        "bool": c.SurfaceValueType.BOOL,
        "choice": c.SurfaceValueType.CANONICAL_CHOICE,
    }
    for name, (group, kind, low, high, default, architecture) in SURFACES.items():
        value_type = types[kind]
        if kind == "uint":
            domain = c.UInt64RangeDomain(low, high)
        elif kind == "float":
            domain = c.Float64RangeDomain(low, high, True, True)
        elif kind == "bool":
            domain = c.BooleanDomain((False, True))
        else:
            domain = c.ChoiceDomain(low)
        applicability = template.applicability
        if architecture is not None:
            applicability = c.WhenSurfaceIn(
                semantic("applicability", "autoresearch_" + name),
                "strategy_backbone",
                (c.SurfaceValue(c.SurfaceValueType.BACKBONE_SELECTOR, architecture),),
                semantic("applicability_reason", "unused_by_other_architecture"),
            )
        entries.append(
            replace(
                template,
                surface_id=name,
                consumer_target=c.ConsumerTarget("carbon_jax_lab_" + group, name),
                value_type=value_type,
                domain=domain,
                applicability=applicability,
                dependency_surface_ids=("strategy_backbone",) if architecture else (),
                requirement=c.ExplicitDefaultSurface(
                    c.SurfaceValue(value_type, default)
                ),
            )
        )
    catalog = replace(
        old.catalog,
        object_id="burgers_autoresearch_parameters",
        object_version="1.0",
        candidate_assembly_ref=assembly.to_ref(),
        entries=tuple(entries),
    )
    return SessionContracts(assembly, catalog, old.origin, old.artifacts)


def compile_recipe(strategy):
    """Static compiler plus actual backend configuration checks; no training."""
    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )

    compiled = research_contracts().compile(strategy)
    if type(compiled) is not CompileAccepted:
        raise ValueError(
            "recipe rejected by B-02B: " + ",".join(i.code for i in compiled.issues)
        )
    profile = compile_development_profile(compiled.construction_plan)
    model, task, train = (
        json.loads(s)
        for s in (
            profile.model_config_json,
            profile.task_config_json,
            profile.train_config_json,
        )
    )
    ModelConfig(**model)
    TaskConfig(**task)
    TrainConfig(**train)
    # n_modes uses floor(n/2)+1: odd values alias the preceding even value.
    if model["kind"] == "fno1d" and model["n_modes"] % 2:
        raise ValueError(
            "FNO n_modes must be even; odd values would be an ignored degree of freedom"
        )
    return compiled, profile


def public_catalog():
    return {
        "version": CATALOG_VERSION,
        "backbones": ["fno", "deeponet"],
        "surfaces": {
            name: {
                "group": g,
                "type": t,
                "minimum_or_choices": lo,
                "maximum": hi,
                "default": d,
                "architecture": a,
            }
            for name, (g, t, lo, hi, d, a) in SURFACES.items()
        },
        "constraints": [
            "width is even (installed configuration requires divisibility by two)",
            "FNO n_modes is even; allocated Fourier modes=n_modes/2+1",
            "both warmup counts must be strictly below steps",
            "only architecture-applicable fields may be supplied",
            "actual 2-CPU/4-GiB/no-swap/600-second admission dominates parameter bounds",
        ],
        "training": "AdamW; linear warmup then cosine decay; uniform TRAIN cases then uniform supplied times; params or EMA at final step",
        "losses": {
            "data": "TRAIN RMS normalized squared error; relative_loss optionally divides by target energy with 1e-6 floor",
            "h1": "spectral spatial derivative error; extra differentiation; sampled/underresolved modes remain",
            "pde": "time autodiff and spectral spatial differential residual; higher compilation/memory cost; not the judge's weak diagnostic",
        },
        "prediction": "direct requested physical times; fixed population-wide time scale 27; no rollout adapter",
        "mean": "project prediction onto the permitted initial field's spatial mean; no accuracy or energy guarantee",
        "unavailable": [
            "other lab backbones not yet registered end to end",
            "Foundax selection in this research catalog",
            "custom optimizer/architecture submission",
            "arbitrary final evaluator code",
            "checkpoint selection by final labels",
            "adaptive sampling/curriculum not implemented by the installed training loop",
        ],
    }
