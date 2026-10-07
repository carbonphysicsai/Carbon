"""Battery, the first Level 4 spike adapter (public development data only).

Everything battery-specific lives here: the families (k-nearest-neighbour,
MLP, DeepONet in JAX; FNO in PyTorch), Level 0 recipes taken from battery's
own panels, the largest legitimate recipes read from the surface bounds of
battery's registered contract document (never typed here), public TRAIN v1,
the Level 1 loss terms, and the hooks that put a rebuilt graph into
battery's own declarative training path.

No battery source file is modified: `recipes.py` and `training.py` bytes
enter every Level 0 recipe digest.
"""

from __future__ import annotations

import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]
EXPANSION = "carbon/reconstruction/expansions/battery-fastcharge-ageing-development-v1/0001.json"
FAMILIES_JAX = ("mlp", "deeponet")


def challenge_id():
    from carbon.battery.value.panel import CHALLENGE_ID

    return CHALLENGE_ID


def strategy(backbone, parameters):
    from carbon.battery.value.panel import _strategy

    return _strategy(backbone, dict(parameters))


def level0_strategies():
    """Battery's Level 0 recipes, from its own panels and scaffold."""
    from carbon.battery.research import SCAFFOLD
    from carbon.battery.value import panel

    named = {label: s for label, s, _ in panel.RECIPES + panel.EV2_RECIPES}
    return {
        "scaffold_mlp": json.loads(json.dumps(SCAFFOLD)),
        "panel_mlp": named["mlp"],
        "panel_deeponet": named["deeponet"],
        "panel_knn": named["knn"],
        "default_fno": strategy("fno", {"backend": "pytorch"}),
    }


def surface_maxima(family):
    """Each architecture parameter at the maximum battery's contract admits."""
    document = json.loads((REPOSITORY / EXPANSION).read_text())["contract_document"]
    out = {}
    for capability in document["capabilities"]:
        surface = capability.get("surface")
        if (
            capability["id"].startswith("architecture.")
            and family in (capability.get("applies_to") or ())
            and surface
            and surface[1] == "uint"
        ):
            out[capability["id"].split(".", 1)[1]] = surface[3]
    return out


def largest_strategies():
    """The largest legitimate recipe per family: architecture surfaces at
    their maxima, rich inputs and full trajectory outputs (trajectory
    components at their maximum would shrink the output, so they stay off)."""
    rich = {"arrhenius_features": True, "ocv_initial_voltage": False}
    mlp = {**surface_maxima("mlp"), "trajectory_components": 0}
    return {
        "largest_mlp": strategy("mlp", {**mlp, **rich}),
        "largest_deeponet": strategy(
            "deeponet", {**surface_maxima("deeponet"), **rich}
        ),
        "largest_fno": strategy(
            "fno", {**surface_maxima("fno"), **rich, "backend": "pytorch"}
        ),
    }


def material():
    from carbon.battery.challenge import PublicMaterial

    return PublicMaterial.load(REPOSITORY)


def structure(m):
    import numpy as np

    from carbon.battery import recipes

    return recipes.Structure(np.asarray(m.ocv_soc), np.asarray(m.ocv_v))


def _model(strategy_, train):
    """The battery model a strategy compiles to, with its output layout set
    from TRAIN's shapes (what `fit` sets before building a network)."""
    from carbon.battery import recipes
    from carbon.battery.compile import build_model, compile_recipe

    _, recipe = compile_recipe(strategy_)
    model = build_model(recipe)
    if recipe.family != "knn":
        model.layout = recipes.Layout(
            train.v.shape[1],
            train.q.shape[1],
            bounded_v=model.bounded_v,
            predict_v0=model.predict_v0,
            fade=model.fade,
        )
    return recipe, model


def _dims(model):
    """Input width from battery's own `features`, and the output width."""
    import numpy as np

    from carbon.battery.recipes import BOUNDS, features

    lay = model.layout
    n_in = features(np.asarray(BOUNDS[:, :1].T, float), model.rich).shape[1]
    if model.pca:
        return n_in, 2 * model.pca + 1 + lay.k
    return n_in, lay.nv + lay.nt + 1 + lay.k


def jax_network(strategy_, train):
    """`init(key) -> (key, params)`, `apply(params, f)` and sizes, exactly as
    `recipes.MLP._network` builds them for this recipe."""
    import jax
    import numpy as np

    recipe, model = _model(strategy_, train)
    dtype = np.float64 if model.settings["precision"] == "float64" else np.float32
    n_in, n_out = _dims(model)
    init, apply = model._network(jax, dtype, n_in, n_out)
    return {
        "family": recipe.family,
        "model": model,
        "init": init,
        "apply": apply,
        "n_in": n_in,
        "n_out": n_out,
        "dtype": dtype,
    }


def loss_function(model):
    """Battery's per-case Level 1 loss terms, summed (every term, so every
    loss primitive appears), over `(zhat, zt, gw)`."""
    import jax.numpy as jnp

    from carbon.battery import loss_terms

    nv, nt = model.layout.nv, model.layout.nt
    groups = (
        ("voltage", 0, nv),
        ("temperature", nv, nv + nt),
        ("plating", nv + nt, nv + nt + 1),
        ("capacity", nv + nt + 1, None),
    )

    def trajectory(z):
        return z[:, :nv], z[:, nv : nv + nt]

    def loss(zhat, zt, gw):
        terms = loss_terms.case_terms(jnp, zhat, zt, gw, trajectory, groups)
        timed = loss_terms.time_terms(jnp, zhat, zt, trajectory)
        total = sum(jnp.mean(v) for v in terms.values())
        for per in timed.values():
            total = total + sum(jnp.mean(v) for v in per.values())
        return total

    return loss


def knn_jax(neighbours):
    """Battery's kNN predictor as a JAX function of (TRAIN inputs in unit
    scale, TRAIN targets, query inputs in unit scale): `recipes.KNN.predict`
    in jax.numpy. TRAIN enters as named inputs, never constants."""
    import jax.numpy as jnp

    def predict(u_train, y_train, u):
        dist = jnp.linalg.norm(u[:, None, :] - u_train[None], axis=2)
        idx = jnp.argsort(dist, axis=1)[:, :neighbours]
        w = 1.0 / (jnp.take_along_axis(dist, idx, 1) + 1e-9)
        w = w / w.sum(1, keepdims=True)
        return jnp.einsum("nk,nkd->nd", w, y_train[idx])

    return predict


def knn_native(strategy_, m):
    """Native kNN outputs (normalized target space) on TRAIN, and its inputs."""
    import numpy as np

    from carbon.battery import recipes

    _, model = _model(strategy_, m.train)
    model.fit(m.train, structure(m), 7)
    u = recipes.unit(m.train.x)
    dist = np.linalg.norm(u[:, None, :] - model.u[None], axis=2)
    idx = np.argsort(dist, axis=1)[:, : model.k]
    w = 1.0 / (np.take_along_axis(dist, idx, 1) + 1e-9)
    w /= w.sum(1, keepdims=True)
    return model, model.u, model.y, u, np.einsum("nk,nkd->nd", w, model.y[idx])


# --- PyTorch -----------------------------------------------------------------


def torch_network(strategy_, train, seed=7):
    """`(params, apply, n_in)` for a PyTorch recipe, exactly as
    `torch_training.build_network` builds it."""
    import torch

    from carbon.battery import torch_training

    _, model = _model(strategy_, train)
    n_in, n_out = _dims(model)
    generator = torch.Generator().manual_seed(seed)
    network = torch_training.build_network(model, generator, n_in, n_out, torch.float32)
    return network.params, network, n_in


# --- Equivalence hooks: the rebuilt graph inside battery's own training ------


def classic_fit(model, d, y, seed, net, make_params):
    """`recipes.MLP._fit_classic`'s loop with `net` and `make_params(key)`
    supplied: the Level 0 MLP's written-out full-batch Adam(W) with cosine
    decay, statement for statement (history recording off). Run with the
    native `net` it must reproduce `MLP.fit`'s digest exactly; that pins this
    copy to the declarative path before the rebuilt `net` is compared."""
    import hashlib

    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.battery.recipes import features

    z = model._encode(y).astype(np.float32)
    f = features(d.x, model.rich).astype(np.float32)
    sw = np.where(d.important, model.important_weight, 1.0).astype(np.float32)
    gw = model._group_weights(z.shape[1]).astype(np.float32)
    params = make_params(jax.random.PRNGKey(seed), f.shape[1], z.shape[1])

    def loss(p, xx, yy):
        r = (net(p, xx) - yy) ** 2
        return jnp.sum(sw[:, None] * r * gw[None, :]) / jnp.sum(sw)

    initial = float(jax.jit(loss)(params, f, z))

    steps, lr0, wd = model.steps, model.lr, model.wd
    b1, b2, eps = 0.9, 0.999, 1e-8

    @jax.jit
    def train(p, xx, yy):
        m = jax.tree_util.tree_map(jnp.zeros_like, p)
        v = jax.tree_util.tree_map(jnp.zeros_like, p)

        def step(c, i):
            p, m, v = c
            g = jax.grad(loss)(p, xx, yy)
            lr = lr0 * 0.5 * (1 + jnp.cos(jnp.pi * i / steps))
            m = jax.tree_util.tree_map(lambda a, b: b1 * a + (1 - b1) * b, m, g)
            v = jax.tree_util.tree_map(lambda a, b: b2 * a + (1 - b2) * b * b, v, g)
            t = i + 1.0
            p = jax.tree_util.tree_map(
                lambda w, a, b: (
                    w
                    - lr
                    * ((a / (1 - b1**t)) / (jnp.sqrt(b / (1 - b2**t)) + eps) + wd * w)
                ),
                p,
                m,
                v,
            )
            return (p, m, v), None

        (p, m, v), _ = jax.lax.scan(
            step, (p, m, v), jnp.arange(steps, dtype=jnp.float32)
        )
        return p, loss(p, xx, yy)

    p, final = train(params, f, z)
    leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(p)]
    blob = b"".join(a.tobytes() for a in leaves)
    out = np.asarray(jax.jit(net)(p, jnp.asarray(f)))
    return {
        "params_sha256": hashlib.sha256(blob).hexdigest(),
        "initial_loss": initial,
        "final_loss": float(final),
        "outputs_sha256": hashlib.sha256(out.tobytes()).hexdigest(),
    }


def classic_params(model):
    """`_fit_classic`'s parameter construction, as `make_params(key, n_in, n_out)`."""
    import itertools

    def make(key, n_in, n_out):
        import jax
        import jax.numpy as jnp

        sizes = [n_in] + [model.width] * model.depth + [n_out]
        params = []
        for a, b in itertools.pairwise(sizes):
            key, k1 = jax.random.split(key)
            params.append(
                (
                    jax.random.normal(k1, (a, b), jnp.float32) * jnp.sqrt(2.0 / a),
                    jnp.zeros((b,), jnp.float32),
                )
            )
        return params

    return make


def classic_net():
    from carbon.battery.recipes import _classic_net

    return _classic_net


def _steps(strategy_, steps):
    out = json.loads(json.dumps(strategy_))
    if steps is not None:
        out["parameters"]["steps"] = steps
    return out


def _digest(arrays):
    import hashlib

    import numpy as np

    return hashlib.sha256(b"".join(np.asarray(a).tobytes() for a in arrays)).hexdigest()


def _flat_names(count):
    return [f"params/{i}" for i in range(count)]


def equivalence_classic(allowlist, strategy_, *, steps=None, seed=7, max_bytes):
    """The Level 0 MLP's classic path, three ways: battery's declarative
    `MLP.fit`, the pinned copy of its loop with the native net and
    initializer, and the same loop with both rebuilt through B'."""
    import jax
    import numpy as np

    from carbon.battery.recipes import features

    from .. import interpret

    s = _steps(strategy_, steps)
    m = material()
    _, model = _model(s, m.train)
    declared = model.fit(m.train, structure(m), seed)
    if not model.classic:
        raise ValueError("this recipe does not train through the classic path")
    y = model.layout.targets(m.train)
    native = classic_fit(model, m.train, y, seed, classic_net(), classic_params(model))
    f = features(m.train.x, model.rich).astype(np.float32)
    n_in, n_out = f.shape[1], y.shape[1]
    make = classic_params(model)
    example = make(jax.random.PRNGKey(0), n_in, n_out)
    count = len(jax.tree_util.tree_leaves(example))
    net_b, _, net_raw = interpret.through_bprime(
        classic_net(),
        (example, f),
        role="forward",
        allowlist=allowlist,
        input_names=_flat_names(count) + ["inputs/features"],
        max_bytes=max_bytes,
    )
    init_b, _, init_raw = interpret.through_bprime(
        lambda key: make(key, n_in, n_out),
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=max_bytes,
    )

    def rebuilt_net(p, xx):
        return net_b(*jax.tree_util.tree_leaves(p), xx)[0]

    def rebuilt_make(key, _n_in, _n_out):
        leaves = init_b(key)
        return [(leaves[2 * i], leaves[2 * i + 1]) for i in range(len(leaves) // 2)]

    rebuilt = classic_fit(model, m.train, y, seed, rebuilt_net, rebuilt_make)
    return {
        "path": "classic (recipes.MLP._fit_classic)",
        "steps": model.steps,
        "declarative_params_sha256": declared["params_sha256"],
        "native_copy_params_sha256": native["params_sha256"],
        "bprime_params_sha256": rebuilt["params_sha256"],
        "copy_matches_declarative": native["params_sha256"]
        == declared["params_sha256"],
        "bprime_matches_native": rebuilt["params_sha256"] == native["params_sha256"]
        and rebuilt["outputs_sha256"] == native["outputs_sha256"],
        "loss": {
            "native": [native["initial_loss"], native["final_loss"]],
            "bprime": [rebuilt["initial_loss"], rebuilt["final_loss"]],
        },
        "graph_bytes": {"forward": len(net_raw), "init": len(init_raw)},
    }


def equivalence_general(allowlist, strategy_, *, steps=None, seed=7, max_bytes):
    """A family that trains through `recipes.MLP._fit_general` and
    `training.train`: native, then with `init` and `apply` both rebuilt
    through B' (parameters as Carbon's flat, named list)."""
    import jax
    import numpy as np

    from .. import interpret

    s = _steps(strategy_, steps)
    m = material()
    _, native = _model(s, m.train)
    native_stats = native.fit(m.train, structure(m), seed)
    native_out = native.predict(m.train.x)
    documents = {}

    def swap(init, apply, n_in, n_out, dtype):
        _, example = init(jax.random.PRNGKey(0))
        leaves = jax.tree_util.tree_leaves(example)
        f = np.zeros((len(m.train.case_ids), n_in), dtype)
        apply_b, doc, raw = interpret.through_bprime(
            apply,
            (example, f),
            role="forward",
            allowlist=allowlist,
            input_names=_flat_names(len(leaves)) + ["inputs/features"],
            max_bytes=max_bytes,
        )
        init_b, idoc, iraw = interpret.through_bprime(
            init,
            (jax.random.PRNGKey(0),),
            role="init",
            allowlist=allowlist,
            input_names=["carbon/key"],
            max_bytes=max_bytes,
        )
        documents.update(
            forward=doc, init=idoc, bytes={"forward": len(raw), "init": len(iraw)}
        )

        def rebuilt_init(k):
            outs = init_b(k)
            return outs[0], list(outs[1:])

        def rebuilt_apply(p, ff):
            return apply_b(*p, ff)[0]

        documents.update(init_fn=rebuilt_init, apply_fn=rebuilt_apply)
        return rebuilt_init, rebuilt_apply

    rebuilt = general_path_model(s, swap)
    rebuilt_stats = rebuilt.fit(m.train, structure(m), seed)
    rebuilt_out = rebuilt.predict(m.train.x)
    same_predictions = all(
        np.array_equal(native_out[k], rebuilt_out[k]) for k in native_out
    )
    # `_fit_general`'s final-loss measure, at the B' initial parameters.
    from carbon.battery.recipes import features

    z = rebuilt._encode(rebuilt.layout.targets(m.train)).astype(np.float32)
    gw = rebuilt._group_weights(z.shape[1]).astype(np.float32)
    f = features(m.train.x, rebuilt.rich).astype(np.float32)
    _, p0 = documents["init_fn"](jax.random.PRNGKey(seed))
    initial = float(
        np.mean((np.asarray(documents["apply_fn"](p0, f)) - z) ** 2 * gw[None, :])
        * gw.size
    )
    review = {}
    for name in ("forward", "init"):
        for g in documents[name]["graphs"].values():
            for node in g["nodes"]:
                if allowlist.ops[node["op"]]["default"] == "review":
                    review[node["op"]] = review.get(node["op"], 0) + 1
    return {
        "path": "general (recipes.MLP._fit_general -> training.train)",
        "steps": rebuilt.steps,
        "native_params_sha256": native_stats["params_sha256"],
        "bprime_params_sha256": rebuilt_stats["params_sha256"],
        "bprime_matches_native": native_stats["params_sha256"]
        == rebuilt_stats["params_sha256"]
        and same_predictions,
        "predictions_identical": same_predictions,
        "loss": {
            "native_final": native_stats["final_loss"],
            "bprime": [initial, rebuilt_stats["final_loss"]],
        },
        "review_ops_in_graphs": review,
        "graph_bytes": documents["bytes"],
        "predictions_sha256": {
            "native": _digest(native_out[k] for k in sorted(native_out)),
            "bprime": _digest(rebuilt_out[k] for k in sorted(rebuilt_out)),
        },
    }


def per_case_vmap(allowlist, strategy_, *, max_bytes):
    """Batch-dimension question: a graph lowered for ONE case and batched by
    Carbon's `vmap`, against the native batched forward, bit for bit."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.battery.recipes import features

    from .. import interpret

    m = material()
    net = jax_network(strategy_, m.train)
    _, p = net["init"](jax.random.PRNGKey(7))
    leaves = jax.tree_util.tree_leaves(p)
    f = jnp.asarray(features(m.train.x, net["model"].rich).astype(net["dtype"]))
    one, _, _ = interpret.through_bprime(
        net["apply"],
        (p, f[:1]),
        role="forward",
        allowlist=allowlist,
        input_names=_flat_names(len(leaves)) + ["inputs/features"],
        max_bytes=max_bytes,
    )
    batched = jax.jit(jax.vmap(lambda row: one(*leaves, row[None])[0][0]))(f)
    native = jax.jit(net["apply"])(p, f)
    diff = np.abs(np.asarray(batched, float) - np.asarray(native, float))
    return {
        "bit_identical": bool(np.array_equal(np.asarray(batched), np.asarray(native))),
        "max_abs_difference": float(diff.max()),
    }


def general_path_model(strategy_, swap):
    """A battery model whose `_network` passes through `swap(init, apply,
    n_in, n_out, dtype) -> (init, apply)` and otherwise trains through
    `recipes.MLP._fit_general` and `training.train` unchanged."""
    from carbon.battery import recipes
    from carbon.battery.compile import compile_recipe

    _, recipe = compile_recipe(strategy_)

    class Swapped(recipes.MLP):
        def _network(self, jax, dtype, n_in, n_out):
            init, apply = super()._network(jax, dtype, n_in, n_out)
            return swap(init, apply, n_in, n_out, dtype)

    return Swapped(recipe.family, recipe.settings)


# --- What the shared spike runs for battery ------------------------------------


def batch(m):
    """The TRAIN batch every battery training step sees (`batch_size` at its
    maximum equals TRAIN v1's case count)."""
    return len(m.train.case_ids)


def _activations():
    document = json.loads((REPOSITORY / EXPANSION).read_text())["contract_document"]
    for capability in document["capabilities"]:
        if capability["id"] == "architecture.activation":
            return capability["surface"][2]
    raise ValueError("battery declares no activation surface")


def _knn_columns(m):
    from carbon.battery import recipes

    lay = recipes.Layout(
        m.train.v.shape[1],
        m.train.q.shape[1],
        bounded_v=False,
        predict_v0=False,
        fade=True,
    )
    return lay.nv + lay.nt + 1 + lay.k


def jax_cases():
    """Every JAX graph traced: `(label, role, fn, args, input_names, extra)`.

    Forward graphs at the TRAIN batch; init graphs from a key; battery's
    Level 1 loss terms over the outputs; each activation on the surface once;
    Carbon's own train step for the largest recipes (role
    `carbon_train_step`, measured only: it is Carbon's, never validated)."""
    import jax
    import jax.numpy as jnp

    m = material()
    n = batch(m)
    for label, s in {**level0_strategies(), **largest_strategies()}.items():
        if s["backbone"] not in FAMILIES_JAX:
            continue
        variants = [(label, s)]
        if label == "scaffold_mlp":
            for act in _activations():
                if act != "gelu":
                    parameters = {
                        **s["parameters"],
                        "activation": act,
                        "normalization": "layer_norm",
                    }
                    variants.append(
                        (f"{label}+{act}+layer_norm", strategy("mlp", parameters))
                    )
        for vlabel, vs in variants:
            net = jax_network(vs, m.train)
            shapes = jax.eval_shape(net["init"], jax.random.PRNGKey(0))[1]
            count = len(jax.tree_util.tree_leaves(shapes))
            f = jax.ShapeDtypeStruct((n, net["n_in"]), net["dtype"])
            names = _flat_names(count) + ["inputs/features"]
            largest = label.startswith("largest")
            yield vlabel, "forward", net["apply"], (shapes, f), names, {
                "largest": largest
            }
            if vlabel != label:
                continue
            yield label, "init", net["init"], (jax.random.PRNGKey(0),), [
                "carbon/key"
            ], {}
            if net["model"].pca:
                continue
            loss = loss_function(net["model"])
            z = jax.ShapeDtypeStruct((n, net["n_out"]), net["dtype"])
            gw = jax.ShapeDtypeStruct((net["n_out"],), net["dtype"])
            yield label, "loss", loss, (z, z, gw), ["outputs", "targets", "weights"], {}
            if largest:

                def step(p, ff, zz, ww, _apply=net["apply"], _loss=loss):
                    value, g = jax.value_and_grad(
                        lambda q: _loss(_apply(q, ff), zz, ww)
                    )(p)
                    return value, jax.tree_util.tree_map(
                        lambda a, b: a - 1e-3 * b, p, g
                    )

                yield label, "carbon_train_step", step, (shapes, f, z, gw), None, {}
    k = level0_strategies()["panel_knn"]["parameters"]["neighbours"]
    u = jax.ShapeDtypeStruct((n, m.train.x.shape[1]), jnp.float64)
    y = jax.ShapeDtypeStruct((n, _knn_columns(m)), jnp.float64)
    names = ["inputs/train_unit", "inputs/train_targets", "inputs/query_unit"]
    yield "panel_knn", "forward", knn_jax(k), (u, y, u), names, {"x64": True}


def torch_cases():
    """`(label, strategy, largest)` for each PyTorch recipe exported."""
    level0 = level0_strategies()
    yield "default_fno", level0["default_fno"], False
    yield "torch_mlp", strategy("mlp", {"backend": "pytorch"}), False
    yield "torch_deeponet", strategy("deeponet", {"backend": "pytorch"}), False
    for act in _activations():
        if act != "gelu":
            parameters = {
                "backend": "pytorch",
                "activation": act,
                "normalization": "layer_norm",
            }
            yield f"torch_mlp+{act}+layer_norm", strategy("mlp", parameters), False
    yield "largest_fno", largest_strategies()["largest_fno"], True


def torch_build(strategy_):
    """Two identically seeded builds, one to export and one to compare with
    (exporting leaves neuraloperator's captured module traced), and TRAIN's
    features."""
    import numpy as np
    import torch

    from carbon.battery.recipes import features

    m = material()
    exported = torch_network(strategy_, m.train)
    reference = torch_network(strategy_, m.train)
    _, model = _model(strategy_, m.train)
    f = torch.tensor(features(m.train.x, model.rich).astype(np.float32))
    return exported, reference, f


def equivalence(allowlist, *, steps=None, max_bytes):
    """Deliverable 5: battery's Level 0 families rebuilt through B'."""
    import jax
    import numpy as np

    from .. import interpret

    level0 = level0_strategies()
    out = {
        label: equivalence_classic(
            allowlist, level0[label], steps=steps, max_bytes=max_bytes
        )
        for label in ("scaffold_mlp", "panel_mlp")
    }
    out["panel_deeponet"] = equivalence_general(
        allowlist, level0["panel_deeponet"], steps=steps, max_bytes=max_bytes
    )
    for act in _activations():
        if act != "gelu":
            s = strategy(
                "mlp", {**level0["scaffold_mlp"]["parameters"], "activation": act}
            )
            out[f"scaffold_mlp+{act} (general path)"] = equivalence_general(
                allowlist, s, steps=steps, max_bytes=max_bytes
            )
    out["batch_by_vmap"] = {
        label: per_case_vmap(allowlist, level0[label], max_bytes=max_bytes)
        for label in ("scaffold_mlp", "panel_deeponet")
    }
    m = material()
    model, u_train, y_train, u, native = knn_native(level0["panel_knn"], m)
    with jax.enable_x64(True):
        rebuilt, _, raw = interpret.through_bprime(
            knn_jax(model.k),
            (u_train, y_train, u),
            role="forward",
            allowlist=allowlist,
            input_names=[
                "inputs/train_unit",
                "inputs/train_targets",
                "inputs/query_unit",
            ],
            max_bytes=max_bytes,
        )
        got = np.asarray(
            jax.jit(lambda a, b, c: rebuilt(a, b, c)[0])(u_train, y_train, u)
        )
    out["panel_knn"] = {
        "path": "recipes.KNN.predict arithmetic (numpy float64) vs B' graph (JAX x64)",
        "bit_identical": bool(np.array_equal(got, native)),
        "max_abs_difference": float(np.max(np.abs(got - native))),
        "train_as_named_inputs_bytes": int(u_train.nbytes + y_train.nbytes),
        "graph_bytes": len(raw),
    }
    return out
