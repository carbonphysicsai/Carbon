# STRATEGY.md — Miner Strategy Guide for Hydrogen

This guide explains how to write effective strategies for the Hydrogen subnet. The goal is to **democratize access** — you don’t need to be an expert to compete.

## What is a Strategy?

A strategy is a JSON file that describes **how** to train your model. You submit the recipe, not the weights. The validator trains a model using your configuration and evaluates it under hidden stress conditions with hard physics constraints.

---

## Using Symbolically Recommended Configurations (Recommended Starting Point)

One of the best ways to create a strong strategy quickly is to start with **symbolically and causally recommended configurations** provided by the system.

### Why This Matters

The Landscape Agent continuously analyzes past submissions using causal inference. It discovers which design choices (loss weights, curriculum settings, etc.) actually improve performance. These insights are turned into **priors** that are published for all miners.

Using these priors gives you a strong, evidence-based starting point instead of guessing.

### How to Get Recommended Configurations

```bash
# See the current baseline performance for a challenge
hydrogen-miner baseline poisson_2d_v1

# Get symbolically/causally recommended priors
hydrogen-miner priors poisson_2d_v1
```

The `priors` command returns suggested values such as:
- Recommended `loss_vector` weights
- Curriculum settings that have shown positive causal effects
- Other features discovered by the Landscape

### How to Use Them in Your Strategy

```json
{
  "backbone": "fno",
  "pino": {
    "loss_vector": {
      "pde_residual": 1.0,
      "conservation_mass": 1.3,      // from priors
      "boundary": 0.7                    // from priors
    }
  },
  "curriculum_learning": {
    "enabled": true,
    "start_resolution": [64, 64],
    "ramp_epochs": 45
  }
}
```

**Tip:** Always start with the priors and then make small, thoughtful adjustments. This is the fastest way to produce competitive strategies.

---

## Full Strategy Fields Reference

### Core Fields

| Field              | Type     | Description                                      | Recommended / Notes                        |
|--------------------|----------|--------------------------------------------------|--------------------------------------------|
| `backbone`         | string   | Neural operator to use                           | `fno`, `deeponet`, `uno`, `physicsnemo_fno` |
| `resolution`       | list     | Spatial/temporal resolution                      | Match challenge default                    |

### Loss & Physics

| Field                    | Type   | Description                                      | Notes                                      |
|--------------------------|--------|--------------------------------------------------|--------------------------------------------|
| `pino.loss_vector`       | dict   | Per-term loss weights                            | Strongly recommended to start from priors  |
| `physics_loss_weight`    | float  | Global multiplier on all physics losses          | 0.6 – 1.5 (start near 1.0)                 |

### Optimizer & Learning

| Field                | Type   | Description                           | Recommended Values                  |
|----------------------|--------|---------------------------------------|-------------------------------------|
| `optimizer`          | str    | Optimizer                             | `AdamW` (default), `Adam`, `SGD`    |
| `learning_rate`      | float  | Learning rate                         | 3e-4 – 2e-3                         |
| `weight_decay`       | float  | L2 regularization                     | 1e-5 – 5e-4                         |
| `scheduler`          | str    | LR scheduler                          | `CosineAnnealingLR` (recommended)   |

### Advanced Controls

| Field                    | Type    | Description                                      | Notes                                      |
|--------------------------|---------|--------------------------------------------------|--------------------------------------------|
| `weight_init`            | str     | Weight initialization scheme                     | `kaiming_normal`, `xavier_uniform`         |
| `grad_clip_norm`         | float   | Max gradient norm (clipping)                     | 0.5 – 2.0                                  |
| `accumulation_steps`     | int     | Gradient accumulation steps                      | 1 – 8                                      |
| `use_amp`                | bool    | Enable mixed precision                           | `true` on modern GPUs                      |
| `early_stop_patience`    | int     | Stop if no validation improvement                | 10 – 25                                    |

### Curriculum Learning

Highly recommended for most PDE problems.

```json
"curriculum_learning": {
  "enabled": true,
  "start_resolution": [64, 64],
  "ramp_epochs": 40
}
```

### Uncertainty Quantification (UQ)

```json
"uq_config": {
  "enabled": true,
  "method": "deep_ensemble",
  "num_members": 4,
  "calibration_target": 0.90
}
```

### Model-Specific Parameters

Pass extra arguments to the backbone via `model_kwargs`:

```json
"model_kwargs": {
  "modes": 32,
  "width": 64
}
```

---

## Example Strategies

### Simple Strong Strategy (Start Here)

```json
{
  "backbone": "fno",
  "optimizer": "AdamW",
  "learning_rate": 0.0008,
  "weight_decay": 1e-4,
  "scheduler": "CosineAnnealingLR",
  "use_amp": true,
  "curriculum_learning": {
    "enabled": true,
    "start_resolution": [64, 64],
    "ramp_epochs": 40
  }
}
```

### Advanced / Experimental Strategy

```json
{
  "backbone": "fno",
  "optimizer": "AdamW",
  "learning_rate": 0.0007,
  "weight_decay": 1e-4,
  "weight_init": "kaiming_normal",
  "grad_clip_norm": 1.0,
  "accumulation_steps": 4,
  "use_amp": true,
  "physics_loss_weight": 0.85,
  "early_stop_patience": 18,
  "curriculum_learning": {
    "enabled": true,
    "start_resolution": [64, 64],
    "ramp_epochs": 50
  },
  "uq_config": {
    "enabled": true,
    "method": "deep_ensemble",
    "num_members": 4
  },
  "model_kwargs": {
    "modes": 32,
    "width": 64
  }
}
```

---

## Recommended Workflow

1. Run `hydrogen-miner priors <challenge>` to get symbolically recommended values.
2. Copy the suggested `loss_vector` and curriculum settings into your strategy.
3. Make small, intentional changes (e.g., slightly increase one loss term).
4. Test locally with `hydrogen-miner validate`.
5. Submit when you’re confident.

This workflow lets you leverage the collective causal knowledge discovered by the Landscape Agent.

---

## Common Pitfalls

- Ignoring the priors and guessing loss weights from scratch.
- Setting learning rate too high → unstable training.
- Turning off curriculum too aggressively.
- Over-complicating the strategy early (start simple, then iterate).

---

## Philosophy

Hydrogen is designed to be **democratized**. You don’t need a PhD or a giant GPU cluster to compete effectively. By starting with the symbolically and causally recommended configurations and then making thoughtful adjustments, almost anyone can produce competitive strategies.

The Landscape Agent exists to surface what actually works. Your job is to propose good ideas and let the system learn from them.
