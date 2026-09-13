"""Closed research configurations. No production-policy or qualification fields."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass

SUPPORTED_MODELS = (
    "fno1d",
    "physics_attention1d",
    "haar_operator1d",
    "gno1d",
    "gino1d",
    "deeponet1d",
)


@dataclass(frozen=True)
class ModelConfig:
    kind: str = "fno1d"
    width: int = 24
    depth: int = 2
    n_modes: int = 16  # PR40 semantics: allocated rfft modes = n_modes//2+1
    heads: int = 4
    slices: int = 8
    wavelet_levels: int = 2
    graph_radius: float = 0.2
    latent_points: int = 24
    branch_points: int = 32
    expansion: int = 2
    remat: bool = False

    def __post_init__(self):
        if type(self.remat) is not bool:
            raise ValueError("remat must be Boolean")
        if self.kind not in SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model {self.kind!r}. No alias to another backbone is allowed."
            )
        for n in (
            "width",
            "depth",
            "n_modes",
            "heads",
            "slices",
            "wavelet_levels",
            "latent_points",
            "branch_points",
            "expansion",
        ):
            v = getattr(self, n)
            if type(v) is not int or v < 1:
                raise ValueError(f"{n} must be a positive integer")
        if self.width < 2 or self.width % self.heads:
            raise ValueError("width must be >=2 and divisible by heads")
        if not math.isfinite(self.graph_radius) or not 0 < self.graph_radius <= 0.5:
            raise ValueError(
                "graph_radius must lie in (0, .5] in periodic unit coordinates"
            )


@dataclass(frozen=True)
class TaskConfig:
    domain_length: float = 1.0
    time_scale: float = 0.3
    nu_scale: float = 0.05
    hard_initial_condition: bool = True
    enforce_mean: bool = False

    def __post_init__(self):
        if (
            type(self.hard_initial_condition) is not bool
            or type(self.enforce_mean) is not bool
        ):
            raise ValueError("task constraint flags must be Boolean")
        for name in ("domain_length", "time_scale", "nu_scale"):
            v = getattr(self, name)
            if not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be positive and finite")


@dataclass(frozen=True)
class TrainConfig:
    steps: int = 300
    batch_size: int = 8
    microbatches: int = 1
    seed: int = 42
    learning_rate: float = 0.002
    min_learning_rate_ratio: float = 0.1
    warmup_steps: int = 10
    weight_decay: float = 1e-4
    clip_norm: float = 1.0
    beta1: float = 0.9
    beta2: float = 0.999
    adam_epsilon: float = 1e-8
    ema_decay: float = 0.99
    relative_loss: bool = False
    h1_weight: float = 0.0
    pde_weight: float = 0.0
    physics_warmup_steps: int = 0
    inference_weights: str = "params"

    def __post_init__(self):
        if type(self.relative_loss) is not bool:
            raise ValueError("relative_loss must be Boolean")
        for n in ("steps", "batch_size", "microbatches"):
            if type(getattr(self, n)) is not int or getattr(self, n) < 1:
                raise ValueError(f"{n} must be a positive integer")
        if type(self.seed) is not int or not 0 <= self.seed < 2**31:
            raise ValueError("seed must be an integer in [0,2**31)")
        for n in ("warmup_steps", "physics_warmup_steps"):
            if (
                type(getattr(self, n)) is not int
                or not 0 <= getattr(self, n) < self.steps
            ):
                raise ValueError(f"{n} must be in [0,steps)")
        for n in ("learning_rate", "clip_norm", "adam_epsilon"):
            if not math.isfinite(getattr(self, n)) or getattr(self, n) <= 0:
                raise ValueError(n)
        for n in ("weight_decay", "h1_weight", "pde_weight"):
            if not math.isfinite(getattr(self, n)) or getattr(self, n) < 0:
                raise ValueError(n)
        for n in ("beta1", "beta2", "ema_decay"):
            if not 0 <= getattr(self, n) < 1:
                raise ValueError(n)
        if not 0 <= self.min_learning_rate_ratio <= 1:
            raise ValueError("min_learning_rate_ratio")
        if self.inference_weights not in ("params", "ema"):
            raise ValueError("inference_weights")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(model, task, train):
    return hashlib.sha256(
        canonical_json(
            {"model": asdict(model), "task": asdict(task), "train": asdict(train)}
        ).encode()
    ).hexdigest()
