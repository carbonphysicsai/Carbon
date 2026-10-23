"""Catalog trainer v2: every lever a miner might pull inside the build, with Carbon's own limits removed
(backbone-catalog lane, "No Carbon limits", step 3, 2026-10-23).

One backbone (named in the configuration, served by the packet's `backbones.py`), trained fresh from the fixed TRAIN the
worker gives (nothing downloaded or reused) and deterministic, so a second rebuild gives the same bytes. A lever this
file cannot express is not faked: it raises.

configuration:
  backbone       registry name
  arch           architecture settings for the backbones that expose them (see `ARCH` and `LIBRARY_ARCH`)
  learning_rate  default 1e-3

train_use (every key optional; `steps` default `DEFAULT_STEPS`, 300 unless the packet's registry says otherwise):
  loss           {"kind": mse|l1|huber|relative_l2|log_cosh, "delta", "smoothness", "output_weights": [w, ...]}
                 `output_weights`: one non-negative weight per output (not all zero); the per-sample error is the weighted
                 mean over outputs. `smoothness` adds a PINO-style penalty on the curve's second difference
  optimizer      {"name": adam|adamw|sgd|rmsprop|lbfgs|adagrad|nadam|radam, "weight_decay", "momentum"}
  schedule       {"name": none|cosine|step|onecycle|warmup_cosine|exponential|polynomial|cosine_restarts, "gamma",
                 "every", "warmup", "power"}
  data           {"subset", "batch", "order": random|easy_first, "curriculum": {"start", "ramp"},
                 "reweight": none|hard_mining, "mixup", "noise"}
  stages         [{"steps", "optimizer", "schedule", "learning_rate"}, ...]: multi-stage
  early_stopping {"validation", "every", "patience"}: restore the best weights
  averaging      {"kind": ema|swa, "decay", "start"}: weight averaging
  search         {"candidates": [{learning_rate | arch | optimizer | ...}], "trial_steps", "validation"}
  seeds          {"candidates": [int, ...], "trial_steps", "validation"}: seed search (integers 0 .. 2**64 - 1)
  ensemble       {"members": k | [{"outputs": [indices]}, ...], "combine": mean|stacking|stacking_per_output|
                 best_per_output|weights, "weights": [...], "validation"}
                 A member with `outputs` trains with its loss restricted to those outputs and is combined only on
                 them; every output must be covered by at least one member. `weights` (combine "weights"): one
                 weight per member, or one list of per-output weights per member
  distill        {"teacher": {arch...}, "teacher_steps", "alpha"}: self-distillation from a teacher trained fresh
  prune          {"fraction", "finetune_steps"}: global magnitude pruning
  quantize       {"bits"}: weights snapped to a symmetric per-tensor grid (bits >= 2); the graph still computes in float
  precision      bfloat16|float16|float32: mixed-precision training (autocast), or plain float32; trained weights stay
                 in the model's own dtype
"""

from __future__ import annotations

import math

import torch

from .common import DEVICE, check_seed, only, positive_int, prepare, rate

# The packet's own backbone registry, as carbon_candidate/backbones.py.
from . import backbones as _registry

build_backbone = _registry.build_backbone

#: Steps when `train_use.steps` is absent: the packet's registry may name its family's baseline (the DeepXDE and THUML
#: bundles trained 200 steps), otherwise 300.
DEFAULT_STEPS = getattr(_registry, "DEFAULT_STEPS", 300)

#: Levers a search candidate may set: they act inside one training run.
TRAIN_LEVERS = {
    "loss",
    "optimizer",
    "schedule",
    "data",
    "stages",
    "averaging",
    "precision",
}
LEVERS = {
    "steps",
    "loss",
    "optimizer",
    "schedule",
    "data",
    "stages",
    "early_stopping",
    "averaging",
    "search",
    "seeds",
    "ensemble",
    "distill",
    "prune",
    "quantize",
    "precision",
}
#: Hand-built backbones whose architecture the trainer wires itself.
ARCH = {
    "neuralop.FNO": {"modes": 16, "hidden": 32, "layers": 4},
    "neuralop.TFNO": {"modes": 16, "hidden": 32, "layers": 4, "rank": 0.42},
    "transolver": {"layers": 2, "hidden": 32, "heads": 4, "slices": 8},
}
#: Library arguments a registry entry of the THUML library (`ENTRIES`) takes as architecture settings: the
#: registry's `DEFAULTS` names, each a library constructor argument. An entry reads the ones its class uses.
LIBRARY_ARCH = (
    "n_hidden",
    "n_layers",
    "n_heads",
    "modes",
    "mlp_ratio",
    "slice_num",
    "mwt_k",
    "dropout",
)


# --- models -------------------------------------------------------------------


def _library_entry(name):
    entries = getattr(_registry, "ENTRIES", None)
    return entries.get(name) if entries else None


def arch_keys(name):
    """The architecture settings a backbone takes (what the settings Schema mirrors)."""
    if name in ARCH:
        return tuple(ARCH[name])
    return LIBRARY_ARCH if _library_entry(name) is not None else ()


def make_model(configuration, n_in):
    name = configuration["backbone"]
    arch = dict(configuration.get("arch") or {})
    if name not in ARCH:
        entry = _library_entry(name)
        if entry is None:
            if arch:
                raise ValueError(f"{name}: arch settings are not supported")
            return build_backbone(name, n_in)
        only(arch, set(LIBRARY_ARCH), "arch")
        for key, value in arch.items():
            if key == "dropout":
                if type(value) not in (int, float) or not 0 <= value < 1:
                    raise ValueError("dropout must be in [0, 1)")
            else:
                positive_int(value, key, 1)
        model, geotype, overrides = entry
        return _registry._library(model, n_in, geotype, **{**overrides, **arch})
    only(arch, set(ARCH[name]), "arch")
    a = {**ARCH[name], **arch}
    for key in ("modes", "hidden", "layers", "heads", "slices"):
        if key in a:
            positive_int(a[key], key, 1)
    if name == "transolver":
        if (
            a["hidden"] % a["heads"]
        ):  # external fact: the block's dim_head = hidden // heads, inner_dim = dim_head * heads
            raise ValueError("hidden must be a multiple of heads")
        from .s7_transolver import CurveTransolver, _model_class

        model = _model_class()(
            space_dim=1,
            fun_dim=n_in,
            out_dim=1,
            n_layers=a["layers"],
            n_hidden=a["hidden"],
            n_head=a["heads"],
            slice_num=a["slices"],
            dropout=0.0,
            Time_Input=False,
            unified_pos=False,
        )
        return CurveTransolver(model, _registry.POINTS).float()
    extra = (
        {"factorization": "tucker", "rank": float(a["rank"])}
        if name == "neuralop.TFNO"
        else {}
    )
    return _registry.OnGrid(
        _registry._neuralop(
            name.split(".")[1],
            n_in,
            n_modes=(a["modes"],),
            hidden_channels=a["hidden"],
            in_channels=n_in + 1,
            out_channels=1,
            n_layers=a["layers"],
            **extra,
        ),
        n_in,
    )


class Ensemble(torch.nn.Module):
    """Members combined per output: `weights` is (members, outputs), a member's weight on an output it does not cover
    is zero. With all members covering all outputs and equal weights this is the v1 mean.
    """

    def __init__(self, members, weights):
        super().__init__()
        self.members = torch.nn.ModuleList(members)
        self.register_buffer("weights", torch.as_tensor(weights, dtype=torch.float32))

    def forward(self, x):
        out = self.members[0](x) * self.weights[0]
        for w, member in zip(self.weights[1:], self.members[1:]):
            out = out + member(x) * w
        return out


def _precision(model):
    dtype = next(
        (p.dtype for p in model.parameters() if p.is_floating_point()), torch.float32
    )
    return torch.float32 if dtype.is_complex else dtype


# --- one training run ----------------------------------------------------------


def output_weights(spec, n_out, mask=None):
    """The per-output loss weights of a run: the loss spec's `output_weights` times a member's output `mask`, or None
    when neither narrows the loss (then the loss is the plain mean over outputs, as in v1).
    """
    given = spec.get("output_weights")
    if given is None and mask is None:
        return None
    if given is None:
        w = torch.ones(n_out, dtype=torch.float64)
    else:
        if type(given) is not list or len(given) != n_out:
            raise ValueError(
                f"loss.output_weights must list one weight per output ({n_out})"
            )
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in given
        ):
            raise ValueError("loss.output_weights must be finite and not negative")
        w = torch.tensor([float(v) for v in given], dtype=torch.float64)
    if mask is not None:
        w = w * torch.as_tensor(mask, dtype=torch.float64)
    if not bool((w > 0).any()):
        raise ValueError("loss.output_weights leave no output with a positive weight")
    return w


def _loss(pred, y, spec, weights=None, out_w=None):
    only(spec, {"kind", "delta", "smoothness", "output_weights"}, "loss")
    kind = spec.get("kind", "mse")
    w = (
        None
        if out_w is None
        else (out_w / out_w.sum()).to(device=pred.device, dtype=pred.dtype)
    )
    if kind == "mse":
        e = (pred - y) ** 2
    elif kind == "l1":
        e = (pred - y).abs()
    elif kind == "huber":
        e = torch.nn.functional.huber_loss(
            pred, y, reduction="none", delta=float(spec.get("delta", 1.0))
        )
    elif kind == "log_cosh":
        d = pred - y
        e = d.abs() + torch.nn.functional.softplus(-2 * d.abs()) - math.log(2.0)
    elif kind == "relative_l2":
        e = None
        if w is None:
            per = ((pred - y) ** 2).sum(1) / ((y**2).sum(1) + 1e-6)
        else:
            per = (((pred - y) ** 2) * w).sum(1) / (((y**2) * w).sum(1) + 1e-6)
    else:
        raise ValueError(f"loss kind {kind!r} is not supported")
    if e is not None:
        per = e.mean(1) if w is None else (e * w).sum(1)
    total = per.mean() if weights is None else (per * weights).sum() / weights.sum()
    sm = float(spec.get("smoothness", 0.0))
    if sm:
        total = (
            total + sm * ((pred[:, 2:] - 2 * pred[:, 1:-1] + pred[:, :-2]) ** 2).mean()
        )
    return total


def _optimizer(params, spec, lr):
    only(spec, {"name", "weight_decay", "momentum"}, "optimizer")
    name, wd = spec.get("name", "adam"), float(spec.get("weight_decay", 0.0))
    if name == "adam":
        return torch.optim.Adam(params, lr=lr, weight_decay=wd)
    if name == "adamw":
        return torch.optim.AdamW(params, lr=lr, weight_decay=wd or 1e-2)
    if name == "sgd":
        return torch.optim.SGD(
            params,
            lr=lr,
            momentum=float(spec.get("momentum", 0.9)),
            nesterov=True,
            weight_decay=wd,
        )
    if name == "rmsprop":
        return torch.optim.RMSprop(params, lr=lr, weight_decay=wd)
    if name == "adagrad":
        return torch.optim.Adagrad(params, lr=lr, weight_decay=wd)
    if name == "nadam":
        return torch.optim.NAdam(params, lr=lr, weight_decay=wd)
    if name == "radam":
        return torch.optim.RAdam(params, lr=lr, weight_decay=wd)
    if name == "lbfgs":
        return torch.optim.LBFGS(
            params, lr=lr, max_iter=5, history_size=10, line_search_fn="strong_wolfe"
        )
    raise ValueError(f"optimizer {name!r} is not supported")


def _schedule(optimizer, spec, steps, lr):
    only(spec, {"name", "gamma", "every", "warmup", "power"}, "schedule")
    name = spec.get("name", "none")
    if name == "none":
        return None
    if name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=steps)
    if name == "step":
        return torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=int(spec.get("every", max(1, steps // 3))),
            gamma=float(spec.get("gamma", 0.5)),
        )
    if name == "onecycle":
        return torch.optim.lr_scheduler.OneCycleLR(
            optimizer, max_lr=lr, total_steps=steps
        )
    if name == "warmup_cosine":
        warm = int(spec.get("warmup", max(1, steps // 10)))
        return torch.optim.lr_scheduler.LambdaLR(
            optimizer,
            lambda k: (
                (k + 1) / warm
                if k < warm
                else 0.5 * (1 + math.cos(math.pi * (k - warm) / max(1, steps - warm)))
            ),
        )
    if name == "exponential":
        return torch.optim.lr_scheduler.ExponentialLR(
            optimizer, gamma=float(spec.get("gamma", 0.99))
        )
    if name == "polynomial":
        return torch.optim.lr_scheduler.PolynomialLR(
            optimizer, total_iters=steps, power=float(spec.get("power", 2.0))
        )
    if name == "cosine_restarts":
        return torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=int(spec.get("every", max(1, steps // 3)))
        )
    raise ValueError(f"schedule {name!r} is not supported")


class _Averager:
    def __init__(self, model, spec, steps):
        only(spec, {"kind", "decay", "start"}, "averaging")
        self.kind = spec.get("kind", "ema")
        if self.kind not in ("ema", "swa"):
            raise ValueError("averaging kind must be ema or swa")
        self.decay = float(spec.get("decay", 0.99))
        self.start = int(float(spec.get("start", 0.75)) * steps)
        self.avg, self.count = None, 0

    def update(self, model, step):
        state = _snapshot(model)
        if self.kind == "swa" and step < self.start:
            return
        if self.avg is None:
            self.avg, self.count = state, 1
            return
        self.count += 1
        for k, v in state.items():
            if not v.is_floating_point() and not v.is_complex():
                self.avg[k] = v
            elif self.kind == "ema":
                self.avg[k].mul_(self.decay).add_(v, alpha=1 - self.decay)
            else:
                self.avg[k].add_((v - self.avg[k]) / self.count)

    def apply(self, model):
        if self.avg is not None:
            _restore(model, self.avg)


def _data_plan(n, spec, gen):
    only(
        spec,
        {"subset", "batch", "order", "curriculum", "reweight", "mixup", "noise"},
        "data",
    )
    order = torch.randperm(n, generator=gen)
    subset = float(spec.get("subset", 1.0))
    if not 0 < subset <= 1:
        raise ValueError("data.subset must be in (0, 1]")
    return order[: max(2, round(subset * n))]


def train(
    model,
    x,
    y,
    *,
    steps,
    lr,
    train_use,
    gen,
    val=None,
    teacher=None,
    masks=None,
    out_mask=None,
):
    """`model` trained on (x, y) with the levers in `train_use`; deterministic. `out_mask` restricts the loss to the
    outputs a member covers."""
    loss_spec = dict(train_use.get("loss") or {})
    out_w = output_weights(loss_spec, y.shape[1], out_mask)
    data = dict(train_use.get("data") or {})
    keep = _data_plan(len(x), data, gen)
    x, y = x[keep], y[keep]
    if data.get("order", "random") == "easy_first":
        rank = torch.argsort((y**2).mean(1), stable=True)
        x, y = x[rank], y[rank]
    elif data.get("order", "random") != "random":
        raise ValueError("data.order must be random or easy_first")
    curriculum = dict(data.get("curriculum") or {})
    only(curriculum, {"start", "ramp"}, "data.curriculum")
    batch = data.get("batch")
    reweight = data.get("reweight", "none")
    if reweight not in ("none", "hard_mining"):
        raise ValueError("data.reweight must be none or hard_mining")
    mixup, noise = float(data.get("mixup", 0.0)), float(data.get("noise", 0.0))
    precision = train_use.get("precision")
    if precision not in (None, "bfloat16", "float16", "float32"):
        raise ValueError("precision must be bfloat16, float16 or float32")
    autocast_dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(
        precision
    )
    scaler = (
        torch.amp.GradScaler("cuda")
        if precision == "float16" and DEVICE.type == "cuda"
        else None
    )
    early = dict(train_use.get("early_stopping") or {}) if val is not None else {}
    stages = train_use.get("stages") or [
        {
            "steps": steps,
            "optimizer": train_use.get("optimizer") or {},
            "schedule": train_use.get("schedule") or {},
        }
    ]
    averager = (
        _Averager(model, dict(train_use["averaging"]), steps)
        if train_use.get("averaging")
        else None
    )
    alpha = float((train_use.get("distill") or {}).get("alpha", 0.5))
    best, best_loss, stale = None, math.inf, 0
    weights = (
        torch.ones(len(x), device=x.device, dtype=y.dtype)
        if reweight == "hard_mining"
        else None
    )
    total = sum(positive_int(s.get("steps"), "stage steps", steps) for s in stages)
    done = 0
    model.train()
    for stage in stages:
        only(stage, {"steps", "optimizer", "schedule", "learning_rate"}, "stage")
        n_steps = positive_int(stage.get("steps"), "stage steps", steps)
        stage_lr = rate(stage.get("learning_rate"), lr)
        optimizer = _optimizer(
            model.parameters(), dict(stage.get("optimizer") or {}), stage_lr
        )
        scheduler = _schedule(
            optimizer, dict(stage.get("schedule") or {}), n_steps, stage_lr
        )
        for _ in range(n_steps):
            seen = len(x)
            if curriculum:
                start, ramp = float(curriculum.get("start", 0.3)), float(
                    curriculum.get("ramp", 0.5)
                )
                seen = max(
                    2,
                    round(
                        len(x)
                        * min(1.0, start + (1 - start) * done / max(1, ramp * total))
                    ),
                )
            idx = torch.arange(seen, device=x.device)
            if batch:
                idx = idx[
                    torch.randperm(seen, generator=gen)[
                        : positive_int(batch, "batch", 1)
                    ].to(x.device)
                ]
            xb, yb = x[idx], y[idx]
            wb = None if weights is None else weights[idx]
            if mixup:
                lam = _beta(gen, mixup)
                perm = torch.randperm(len(idx), generator=gen).to(x.device)
                xb, yb = (
                    lam * xb + (1 - lam) * xb[perm],
                    lam * yb + (1 - lam) * yb[perm],
                )
            if noise:
                xb = xb + noise * torch.randn(
                    xb.shape, generator=gen, dtype=xb.dtype
                ).to(x.device)

            def closure():
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(
                    DEVICE.type,
                    dtype=autocast_dtype,
                    enabled=autocast_dtype is not None,
                ):
                    pred = model(xb).to(yb.dtype)
                    loss = _loss(pred, yb, loss_spec, wb, out_w)
                    if teacher is not None:
                        with torch.no_grad():
                            target = teacher(xb).to(yb.dtype)
                        loss = alpha * loss + (1 - alpha) * torch.mean(
                            (pred - target) ** 2
                        )
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError("nonfinite TRAIN loss")
                (scaler.scale(loss) if scaler else loss).backward()
                return loss

            if scaler:
                closure()
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step(closure)
            if masks is not None:
                _apply_masks(model, masks)
            if scheduler is not None:
                scheduler.step()
            done += 1
            if averager is not None:
                averager.update(model, done)
            if weights is not None and done % 25 == 0:
                with torch.no_grad():
                    per = ((model(x).to(y.dtype) - y) ** 2).mean(1)
                    weights = 1.0 + per / (per.mean() + 1e-12)
            if early and done % int(early.get("every", 10)) == 0:
                score = evaluate(model, *val)
                if score < best_loss:
                    best_loss, stale = score, 0
                    best = _snapshot(model)
                else:
                    stale += 1
                    if stale >= int(early.get("patience", 5)):
                        break
                model.train()
        else:
            continue
        break  # early stopping ended this stage: skip the remaining stages
    if averager is not None:
        averager.apply(model)
    if best is not None:
        _restore(model, best)
    return model.eval()


def _snapshot(model):
    """Parameters and buffers by name (some libraries add non-tensor entries to
    `state_dict`, e.g. neuralop's `_metadata`)."""
    return {
        n: v.detach().clone()
        for n, v in [*model.named_parameters(), *model.named_buffers()]
    }


def _restore(model, snapshot):
    tensors = dict([*model.named_parameters(), *model.named_buffers()])
    with torch.no_grad():
        for n, v in snapshot.items():
            tensors[n].copy_(v)


def _beta(gen, a):
    """One Beta(a, a) draw, seeded from `gen` (torch's Beta takes no generator)."""
    import numpy as np

    return float(
        np.random.default_rng(int(torch.randint(2**31, (1,), generator=gen))).beta(a, a)
    )


def evaluate(model, x, y):
    model.eval()
    with torch.no_grad():
        return float(torch.mean((model(x).to(y.dtype) - y) ** 2))


def _apply_masks(model, masks):
    with torch.no_grad():
        for p, m in zip(model.parameters(), masks):
            if m is not None:
                p.mul_(m)


# --- levers that wrap training ----------------------------------------------------


def _split(n, fraction, gen):
    fraction = float(fraction)
    if not 0 < fraction < 1:
        raise ValueError("validation must be in (0, 1)")
    order = torch.randperm(n, generator=gen)
    k = max(1, round(fraction * n))
    return order[k:], order[:k]


#: Configuration keys a search candidate may set; a different `backbone` is an
#: architecture search across registry entries (fixed-configuration libraries).
CONFIG_KEYS = ("learning_rate", "arch", "backbone")


def _with(config, candidate):
    out = {**config, **{k: v for k, v in candidate.items() if k in CONFIG_KEYS}}
    if "backbone" in candidate and "arch" not in candidate:
        out.pop(
            "arch", None
        )  # another backbone's architecture settings do not carry over
    if not out.get("arch"):
        out.pop("arch", None)
    return out


def _fresh(configuration, n_in, seed):
    torch.manual_seed(seed % (2**63))
    return make_model(configuration, n_in).to(DEVICE)


# --- ensembles, per output -----------------------------------------------------------


def _members(spec, n_out):
    """(coverage matrix (k, n_out) of 0/1, whether any member narrows its outputs) from `ensemble.members`."""
    members = spec.get("members", 3)
    if type(members) is int:
        return (
            torch.ones(positive_int(members, "members", 3), n_out, dtype=torch.float64),
            False,
        )
    if type(members) is not list or not members:
        raise ValueError(
            "ensemble.members must be a whole number or a non-empty list of member specs"
        )
    cover = torch.zeros(len(members), n_out, dtype=torch.float64)
    for i, member in enumerate(members):
        only(member, {"outputs"}, f"ensemble.members[{i}]")
        outputs = member.get("outputs")
        if outputs is None:
            cover[i] = 1.0
            continue
        if (
            type(outputs) is not list
            or not outputs
            or any(type(o) is not int or not 0 <= o < n_out for o in outputs)
        ):
            raise ValueError(
                f"ensemble.members[{i}].outputs must list output indices from 0 to {n_out - 1}"
            )
        cover[i, outputs] = 1.0
    uncovered = [j for j in range(n_out) if not bool((cover[:, j] > 0).any())]
    if uncovered:
        raise ValueError(f"output {uncovered[0]} is covered by no ensemble member")
    return cover, bool((cover == 0).any())


COMBINES = ("mean", "stacking", "stacking_per_output", "best_per_output", "weights")


def mask_of(row):
    """A member's output mask for its loss, or None when it covers every output (then its loss is the plain v1 one)."""
    return None if bool((row > 0).all()) else row


def _combination(combine, spec, cover, members, vx, vy):
    """The (k, n_out) weight matrix for `combine`; only covering members get weight on an output."""
    k, n_out = cover.shape
    if combine == "mean":
        return cover / cover.sum(0, keepdim=True)
    if combine == "weights":
        given = spec.get("weights")
        if type(given) is not list or len(given) != k:
            raise ValueError("ensemble.weights must list one entry per member")
        rows = []
        for entry in given:
            if type(entry) is list:
                if len(entry) != n_out:
                    raise ValueError(
                        "a per-output member weight list must have one weight per output"
                    )
                rows.append(
                    torch.tensor([float(v) for v in entry], dtype=torch.float64)
                )
            else:
                rows.append(torch.full((n_out,), float(entry), dtype=torch.float64))
        w = torch.stack(rows)
        if not bool(torch.isfinite(w).all()):
            raise ValueError("ensemble.weights must be finite")
        return w * cover
    with torch.no_grad():
        preds = torch.stack([m(vx).to(torch.float64) for m in members])  # (k, n, n_out)
    target = vy.to(torch.float64)
    if combine == "stacking":
        mask = cover[:, None, :].expand_as(preds)
        flat_p = (preds * mask).reshape(k, -1)
        flat_t = target.reshape(-1)
        gram = flat_p @ flat_p.T + 1e-6 * torch.eye(k, dtype=torch.float64)
        w = torch.linalg.solve(gram, flat_p @ flat_t)
        return w[:, None] * cover
    if combine == "stacking_per_output":
        out = torch.zeros(k, n_out, dtype=torch.float64)
        for j in range(n_out):
            idx = [i for i in range(k) if cover[i, j] > 0]
            p = preds[idx, :, j]
            gram = p @ p.T + 1e-6 * torch.eye(len(idx), dtype=torch.float64)
            out[idx, j] = torch.linalg.solve(gram, p @ target[:, j])
        return out
    if combine == "best_per_output":
        out = torch.zeros(k, n_out, dtype=torch.float64)
        for j in range(n_out):
            idx = [i for i in range(k) if cover[i, j] > 0]
            errors = [
                float(torch.mean((preds[i, :, j] - target[:, j]) ** 2)) for i in idx
            ]
            out[idx[min(range(len(idx)), key=errors.__getitem__)], j] = 1.0
        return out
    raise ValueError(
        "ensemble.combine must be mean, stacking, stacking_per_output, best_per_output or weights"
    )


# --- the build ------------------------------------------------------------------------


def build(train_inputs, train_targets, *, seed, configuration, train_use):
    only(configuration, {"backbone", "arch", "learning_rate"}, "configuration")
    only(train_use, LEVERS, "train_use")
    z, t, stats = prepare(train_inputs, train_targets, seed)
    n_in, n_out = z.shape[1], t.shape[1]
    probe = make_model(configuration, n_in)
    precision = _precision(probe)
    x, y = z.to(precision), t.to(precision)
    lr = rate(configuration.get("learning_rate"), 1e-3)
    steps = positive_int(train_use.get("steps"), "steps", DEFAULT_STEPS)
    gen = torch.Generator().manual_seed(seed)
    base = {
        k: v
        for k, v in train_use.items()
        if k not in ("search", "seeds", "ensemble", "distill", "prune", "quantize")
    }

    def run(
        config,
        use,
        run_seed,
        xs,
        ys,
        *,
        run_steps=steps,
        val=None,
        teacher=None,
        out_mask=None,
    ):
        model = _fresh(config, n_in, run_seed)
        return train(
            model,
            xs,
            ys,
            steps=run_steps,
            lr=rate(config.get("learning_rate"), lr),
            train_use=use,
            gen=torch.Generator().manual_seed(run_seed % (2**63)),
            val=val,
            teacher=teacher,
            out_mask=out_mask,
        )

    def held_out(spec):
        fit_idx, val_idx = _split(len(x), spec.get("validation", 0.2), gen)
        return (x[fit_idx], y[fit_idx]), (x[val_idx], y[val_idx])

    early = train_use.get("early_stopping")
    val_for_early = held_out(dict(early)) if early else None

    # Search over candidate settings (hyperparameters, architecture, optimizer...).
    config, use, run_seed = dict(configuration), dict(base), seed
    for lever in ("search", "seeds"):
        spec = train_use.get(lever)
        if not spec:
            continue
        only(spec, {"candidates", "trial_steps", "validation"}, lever)
        (fx, fy), (vx, vy) = held_out(spec)
        trial = positive_int(spec.get("trial_steps"), "trial_steps", max(1, steps // 4))
        scores = []
        for candidate in spec["candidates"]:
            if lever == "seeds":
                check_seed(candidate, "seed candidate")
                c_config, c_use, c_seed = config, use, candidate
            else:
                only(candidate, set(CONFIG_KEYS) | TRAIN_LEVERS, "candidate")
                c_config = _with(config, candidate)
                c_use = {
                    **use,
                    **{k: v for k, v in candidate.items() if k not in CONFIG_KEYS},
                }
                c_seed = run_seed
            scores.append(
                evaluate(run(c_config, c_use, c_seed, fx, fy, run_steps=trial), vx, vy)
            )
        winner = spec["candidates"][min(range(len(scores)), key=scores.__getitem__)]
        if lever == "seeds":
            run_seed = winner
        else:
            config = _with(config, winner)
            use = {**use, **{k: v for k, v in winner.items() if k not in CONFIG_KEYS}}

    fit_x, fit_y = val_for_early[0] if val_for_early else (x, y)
    teacher = None
    if train_use.get("distill"):
        spec = dict(train_use["distill"])
        only(spec, {"teacher", "teacher_steps", "alpha"}, "distill")
        teacher_spec = dict(spec.get("teacher") or {})
        if "backbone" in teacher_spec:  # a different backbone as the teacher
            teacher_config = _with(
                config, {"backbone": teacher_spec.pop("backbone"), "arch": teacher_spec}
            )
        else:
            teacher_config = {
                **config,
                "arch": {**(config.get("arch") or {}), **teacher_spec},
            }
        teacher = run(
            teacher_config,
            use,
            run_seed + 1,
            fit_x,
            fit_y,
            run_steps=positive_int(spec.get("teacher_steps"), "teacher_steps", steps),
        )

    if train_use.get("ensemble"):
        spec = dict(train_use["ensemble"])
        only(spec, {"members", "combine", "weights", "validation"}, "ensemble")
        cover, _ = _members(spec, n_out)
        k = cover.shape[0]
        combine = spec.get("combine", "mean")
        if combine not in COMBINES:
            raise ValueError(
                "ensemble.combine must be mean, stacking, stacking_per_output, best_per_output or weights"
            )
        needs_held_out = combine in (
            "stacking",
            "stacking_per_output",
            "best_per_output",
        )
        if needs_held_out:
            (sx_, sy_), (vx, vy) = held_out(spec)
            members = [
                run(
                    config,
                    use,
                    run_seed + 10 + i,
                    sx_,
                    sy_,
                    teacher=teacher,
                    out_mask=mask_of(cover[i]),
                )
                for i in range(k)
            ]
        else:
            vx = vy = None
            members = [
                run(
                    config,
                    use,
                    run_seed + 10 + i,
                    fit_x,
                    fit_y,
                    val=val_for_early[1] if val_for_early else None,
                    teacher=teacher,
                    out_mask=mask_of(cover[i]),
                )
                for i in range(k)
            ]
        model = Ensemble(members, _combination(combine, spec, cover, members, vx, vy))
    else:
        model = run(
            config,
            use,
            run_seed,
            fit_x,
            fit_y,
            val=val_for_early[1] if val_for_early else None,
            teacher=teacher,
        )

    if train_use.get("prune"):
        spec = dict(train_use["prune"])
        only(spec, {"fraction", "finetune_steps"}, "prune")
        fraction = float(spec.get("fraction", 0.5))
        if not 0 < fraction < 1:
            raise ValueError("prune.fraction must be in (0, 1)")
        weights = [p for p in model.parameters() if p.dim() >= 2]
        magnitudes = torch.cat(
            [p.detach().abs().reshape(-1).to(torch.float64) for p in weights]
        )
        threshold = (
            torch.quantile(magnitudes, fraction)
            if len(magnitudes) <= 2**24
            else magnitudes.kthvalue(max(1, int(fraction * len(magnitudes)))).values
        )
        masks = [
            (
                (p.detach().abs() > threshold).to(
                    p.real.dtype if p.is_complex() else p.dtype
                )
                if p.dim() >= 2
                else None
            )
            for p in model.parameters()
        ]
        _apply_masks(model, masks)
        finetune = int(spec.get("finetune_steps", 100))
        if finetune:
            model = train(
                model.train(),
                fit_x,
                fit_y,
                steps=finetune,
                lr=lr * 0.1,
                train_use=use,
                gen=torch.Generator().manual_seed((run_seed + 99) % (2**63)),
                masks=masks,
            )

    if train_use.get("quantize"):
        spec = dict(train_use["quantize"])
        only(spec, {"bits"}, "quantize")
        bits = positive_int(spec.get("bits"), "bits", 8)
        if bits < 2:
            raise ValueError("quantize.bits must be at least 2")
        levels = float(2 ** (bits - 1) - 1)
        with torch.no_grad():
            for p in model.parameters():
                parts = (p.real, p.imag) if p.is_complex() else (p,)
                for part in parts:
                    scale = part.abs().max() / levels
                    if scale > 0:
                        part.copy_(torch.round(part / scale) * scale)

    return _product(model, stats, precision)


def _product(model, stats, precision):
    model = model.cpu().eval()
    named = list(model.named_parameters())
    names = tuple(n for n, _ in named)
    buffers = {n: b.detach().clone() for n, b in model.named_buffers()}
    parameters = [p.detach().clone() for _, p in named]
    if not all(bool(torch.isfinite(p).all()) for p in parameters):
        raise RuntimeError("nonfinite trained state")
    mx, sx, my, sy = (stats[k] for k in ("mx", "sx", "my", "sy"))

    def apply(params, inputs):
        q = ((torch.as_tensor(inputs) - mx) / sx).to(precision)
        out = torch.func.functional_call(
            model, (dict(zip(names, params)), buffers), (q,)
        )
        return out.to(torch.float64) * sy + my

    return {"framework": "torch", "apply": apply, "parameters": parameters}
