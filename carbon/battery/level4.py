"""Battery's Level 4 adapter, the first (development only; public data only).

`carbon.level4` is Challenge-neutral; this module supplies what is battery's.

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
import sys
from pathlib import Path

from .level4_model import classic_fit  # one stageable copy
from .level4_model import dims as _dims

REPOSITORY = Path(__file__).resolve().parents[2]
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


def interface(strategy_):
    """The development interface for a recipe: the Level 0 network boundary,
    battery's features in and normalized outputs out, both float32 per case.

    Development only. Battery's Level 4 interface itself (raw inputs and
    trajectories with units, or this boundary with Carbon's featurization and
    decoding) is a Challenge design choice for Graphite's Level 4 proposal
    under the climb procedure; nothing here fixes it."""
    from ..level4.validate import Interface

    _, model = _model(strategy_, material().train)
    n_in, n_out = _dims(model)
    dtype = "float64" if model.settings["precision"] == "float64" else "float32"
    return Interface(
        inputs=(("inputs/features", dtype, (n_in,)),),
        outputs=((dtype, (n_out,)),),
    )


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


KNN_INPUTS = ["inputs/train_unit", "inputs/train_targets", "inputs/query_unit"]


def knn_interface(strategy_=None):
    """The kNN graph's development interface: TRAIN inputs in unit scale,
    TRAIN targets (normalized) and query inputs in unit scale in, normalized
    outputs out, all float64 with one leading batch (the query is TRAIN, as
    in Phase 0). Development only, like `interface`."""
    from ..level4.validate import Interface

    del strategy_
    m = material()
    d, c = m.train.x.shape[1], _knn_columns(m)
    return Interface(
        inputs=(
            ("inputs/train_unit", "float64", (d,)),
            ("inputs/train_targets", "float64", (c,)),
            ("inputs/query_unit", "float64", (d,)),
        ),
        outputs=(("float64", (c,)),),
    )


def lower_knn(strategy_, allowlist, *, max_bytes):
    """Miner side: battery's kNN predictor lowered to a forward graph at the
    TRAIN batch (float64). It has no parameters, so its init spec is empty.
    Carbon never trains it: a forward-only graph (its `gather` and `sort`
    are the review ops a GPU leg must exercise)."""
    import jax
    import jax.numpy as jnp

    from ..level4 import graph, initializers, submission, tooling

    m = material()
    n = batch(m)
    k = strategy_["parameters"]["neighbours"]
    with jax.enable_x64(True):
        u = jax.ShapeDtypeStruct((n, m.train.x.shape[1]), jnp.float64)
        y = jax.ShapeDtypeStruct((n, _knn_columns(m)), jnp.float64)
        _, forward, _ = tooling.through_bprime(
            knn_jax(k),
            (u, y, u),
            role="forward",
            allowlist=allowlist,
            input_names=KNN_INPUTS,
            max_bytes=max_bytes,
        )
    spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": [],
    }
    return submission.build(
        challenge=challenge_id(),
        interface=knn_interface().digest(),
        allowlist=allowlist,
        forward=forward,
        init_spec=spec,
    )


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

    from ..level4 import tooling

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
    net_b, _, net_raw = tooling.through_bprime(
        classic_net(),
        (example, f),
        role="forward",
        allowlist=allowlist,
        input_names=_flat_names(count) + ["inputs/features"],
        max_bytes=max_bytes,
    )
    init_b, _, init_raw = tooling.through_bprime(
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

    from ..level4 import tooling

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
        apply_b, doc, raw = tooling.through_bprime(
            apply,
            (example, f),
            role="forward",
            allowlist=allowlist,
            input_names=_flat_names(len(leaves)) + ["inputs/features"],
            max_bytes=max_bytes,
        )
        init_b, idoc, iraw = tooling.through_bprime(
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

    dtype = np.float64 if rebuilt.x64 else np.float32
    z = rebuilt._encode(rebuilt.layout.targets(m.train)).astype(dtype)
    gw = rebuilt._group_weights(z.shape[1]).astype(dtype)
    f = features(m.train.x, rebuilt.rich).astype(dtype)
    with jax.enable_x64(rebuilt.x64):
        _, p0 = documents["init_fn"](jax.random.PRNGKey(seed))
        zhat = np.asarray(documents["apply_fn"](p0, f))
    initial = float(np.mean((zhat - z) ** 2 * gw[None, :]) * gw.size)
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

    from ..level4 import tooling

    m = material()
    net = jax_network(strategy_, m.train)
    _, p = net["init"](jax.random.PRNGKey(7))
    leaves = jax.tree_util.tree_leaves(p)
    f = jnp.asarray(features(m.train.x, net["model"].rich).astype(net["dtype"]))
    one, _, _ = tooling.through_bprime(
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


def _choices(capability_id):
    document = json.loads((REPOSITORY / EXPANSION).read_text())["contract_document"]
    for capability in document["capabilities"]:
        if capability["id"] == capability_id:
            return capability["surface"][2]
    raise ValueError("battery declares no surface " + capability_id)


def _activations():
    return _choices("architecture.activation")


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

    from ..level4 import tooling

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
        rebuilt, _, raw = tooling.through_bprime(
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


# --- Phase 1 design: gradient matrix (Q1) and Carbon-built init (Q3) ----------


def _targets(model, m):
    """`fit`'s preprocessing: normalized targets and the group weights."""

    y = model.layout.targets(m.train)
    model.mu, model.sd = y.mean(0), y.std(0) + 1e-9
    z = model._encode(y)
    return z, model._group_weights(z.shape[1])


def gradient_cases():
    """Every trainable JAX family at every surface activation and
    normalization, in float32, plus float64 for each family."""
    level0 = level0_strategies()
    bases = {"mlp": level0["scaffold_mlp"], "deeponet": level0["panel_deeponet"]}
    for family, base in bases.items():
        for act in _activations():
            for norm in _choices("architecture.normalization"):
                parameters = {
                    **base["parameters"],
                    "activation": act,
                    "normalization": norm,
                }
                yield f"{family}/{act}/{norm}", strategy(family, parameters)
        parameters = {
            **base["parameters"],
            "precision": "float64",
            "activation": "relu",
        }
        yield f"{family}/relu/none/float64", strategy(family, parameters)


def training_equivalence(allowlist, strategy_, *, steps=None, max_bytes):
    """B' inside whichever path battery itself trains the recipe through."""
    s = _steps(strategy_, steps)
    m = material()
    _, model = _model(s, m.train)
    if model.family == "mlp" and model._classic(batch(m)):
        result = equivalence_classic(allowlist, s, max_bytes=max_bytes)
    else:
        result = equivalence_general(allowlist, s, max_bytes=max_bytes)
    return {k: result[k] for k in ("path", "steps", "bprime_matches_native", "loss")}


def gradient_equivalence(allowlist, strategy_, *, max_bytes):
    """Gradients of battery's training loss and of every Level 1 loss term,
    native against B', bit for bit; and the rebuilt init."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.battery.recipes import features

    from ..level4 import tooling

    m = material()
    x64 = strategy_["parameters"].get("precision") == "float64"
    with jax.enable_x64(x64):
        net = jax_network(strategy_, m.train)
        model, dtype = net["model"], net["dtype"]
        z, gw = _targets(model, m)
        z, gw = jnp.asarray(z.astype(dtype)), jnp.asarray(gw.astype(dtype))
        f = jnp.asarray(features(m.train.x, model.rich).astype(dtype))
        key = jax.random.PRNGKey(7)
        _, p = net["init"](key)
        leaves = jax.tree_util.tree_leaves(p)
        rebuilt, doc, _ = tooling.through_bprime(
            net["apply"],
            (p, f),
            role="forward",
            allowlist=allowlist,
            input_names=_flat_names(len(leaves)) + ["inputs/features"],
            max_bytes=max_bytes,
        )
        rinit, _, _ = tooling.through_bprime(
            net["init"],
            (key,),
            role="init",
            allowlist=allowlist,
            input_names=["carbon/key"],
            max_bytes=max_bytes,
        )
        terms = loss_function(model)

        def native(q):
            return net["apply"](q, f)

        def graph_(q):
            return rebuilt(*q, f)[0]

        def train_loss(forward, q):
            return jnp.mean(jnp.sum((forward(q) - z) ** 2 * gw[None, :], axis=1))

        def term_loss(forward, q):
            return terms(forward(q), z, gw)

        out = {
            "named_functions": sorted(
                {
                    n["params"]["name"]
                    for g in doc["graphs"].values()
                    for n in g["nodes"]
                    if n["op"] == "named_function"
                }
            )
        }
        for label, loss in (("training_loss", train_loss), ("level1_terms", term_loss)):
            gn = jax.jit(jax.grad(lambda q, _l=loss: _l(native, q)))(p)
            gb = jax.jit(jax.grad(lambda q, _l=loss: _l(graph_, q)))(leaves)
            out[label] = all(
                np.array_equal(np.asarray(a), np.asarray(b))
                for a, b in zip(jax.tree_util.tree_leaves(gn), gb)
            )
        init_leaves = jax.tree_util.tree_leaves(net["init"](key))
        out["init"] = all(
            np.array_equal(np.asarray(a), np.asarray(b))
            for a, b in zip(init_leaves, rinit(key))
        )
    return out


def torch_init_spec(doc):
    """A declaration a miner might write for battery's PyTorch families:
    dense weights (in, out) he_normal over axis 0; convolution weights
    (out, in, k) he_normal over (in, k); spectral weights held as real views
    (in, out, modes, 2) glorot_normal over (in) and (out); vectors zeros."""
    from ..level4 import graph, initializers

    entries = []
    for i in doc["graphs"][doc["entry"]]["inputs"]:
        if not i["name"].startswith("params/"):
            continue
        rank = len(i["shape"])
        fan_in, fan_out, name = {
            1: ([], [], "zeros"),
            2: ([0], [1], "he_normal"),
            3: ([1, 2], [0], "he_normal"),
            4: ([0], [1], "glorot_normal"),
        }[rank]
        entries.append(
            {
                "input": i["name"],
                "initializer": name,
                "fan_in_axes": fan_in,
                "fan_out_axes": fan_out,
            }
        )
    return {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(doc),
        "parameters": entries,
    }


def torch_carbon_init(allowlist, strategy_, *, steps, max_bytes):
    """Q3: a PyTorch-authored graph initialized by Carbon and trained by
    Carbon's own `jax.grad`, with the module's own initialization unable to
    reach the document."""
    import hashlib

    import jax
    import jax.numpy as jnp
    import numpy as np
    import optax
    import torch

    from carbon.battery.recipes import features

    from ..level4 import graph, initializers, interpret
    from ..level4.tooling import lower_torch

    m = material()
    documents = []
    for seed in (7, 8):
        params, net, _ = torch_network(strategy_, m.train, seed=seed)
        _, model = _model(strategy_, m.train)
        f = torch.tensor(features(m.train.x, model.rich).astype(np.float32))
        _, core = lower_torch.export(net, params, f)
        doc, _ = lower_torch.lower(core, allowlist=allowlist)
        documents.append(graph.parse(graph.dumps(doc), max_bytes=max_bytes))
    doc = documents[0]
    raw_spec = graph.dumps(torch_init_spec(doc))
    init = initializers.build(initializers.parse(raw_spec, max_bytes=max_bytes), doc)
    rebuilt = interpret.rebuild(doc, allowlist)
    z, gw = _targets(model, m)
    z, gw = jnp.asarray(z.astype(np.float32)), jnp.asarray(gw.astype(np.float32))
    jf = jnp.asarray(f.numpy())

    def loss(q):
        return jnp.mean(jnp.sum((rebuilt(*q, jf)[0] - z) ** 2 * gw[None, :], axis=1))

    tx = optax.adam(1e-3)
    p = init(jax.random.PRNGKey(7))
    again = init(jax.random.PRNGKey(7))
    state = tx.init(p)

    @jax.jit
    def step(q, s):
        value, g = jax.value_and_grad(loss)(q)
        updates, s = tx.update(g, s, q)
        return optax.apply_updates(q, updates), s, value

    first = float(jax.jit(loss)(p))
    for _ in range(steps):
        p, state, _ = step(p, state)
    blob = b"".join(np.asarray(a).tobytes() for a in again)
    return {
        "document_independent_of_module_init": graph.digest(documents[0])
        == graph.digest(documents[1]),
        "init_deterministic": all(
            np.array_equal(np.asarray(a), np.asarray(b))
            for a, b in zip(init(jax.random.PRNGKey(7)), again)
        ),
        "init_sha256": hashlib.sha256(blob).hexdigest(),
        "parameters": len(again),
        "carbon_training": {
            "optimizer": "optax.adam (spike demonstration only)",
            "steps": steps,
            "loss": [first, float(jax.jit(loss)(p))],
        },
    }


# --- Phase 1: the graph path through G3, G4 and G6 -----------------------------


def _is_classic(model, m):
    return model.family == "mlp" and model._classic(batch(m))


def e1_cases():
    """Battery's trainable Level 0 recipes, for E1 (kNN is not trained; the
    FNO is PyTorch-only and has no JAX declarative path to compare)."""
    level0 = level0_strategies()
    for label in ("scaffold_mlp", "panel_mlp", "panel_deeponet"):
        yield label, level0[label]


def training_batch(strategy_):
    """The batch a recipe trains at: its batch size, capped at TRAIN's size."""
    m = material()
    _, model = _model(strategy_, m.train)
    return min(model.settings["batch_size"], batch(m))


def lower_recipe(strategy_, allowlist, *, max_bytes):
    """Miner side: a declarative recipe's network lowered into a Level 4
    submission (`(manifest, files)`) at the recipe's training batch. The init
    graph returns parameters only (no key)."""
    import jax

    from ..level4 import submission, tooling

    m = material()
    _, model = _model(strategy_, m.train)
    n = training_batch(strategy_)
    x64 = model.settings["precision"] == "float64"
    with jax.enable_x64(x64):
        if _is_classic(model, m):
            n_in, n_out = _dims(model)
            make = classic_params(model)
            example = make(jax.random.PRNGKey(0), n_in, n_out)
            forward_fn, dtype = classic_net(), "float32"

            def init_fn(key):
                return jax.tree_util.tree_leaves(make(key, n_in, n_out))

        else:
            net = jax_network(strategy_, m.train)
            _, example = net["init"](jax.random.PRNGKey(0))
            forward_fn, n_in, dtype = net["apply"], net["n_in"], net["dtype"]

            def init_fn(key, _init=net["init"]):
                return jax.tree_util.tree_leaves(_init(key)[1])

        count = len(jax.tree_util.tree_leaves(example))
        f = jax.ShapeDtypeStruct((n, n_in), dtype)
        names = [f"params/{i}" for i in range(count)] + ["inputs/features"]
        _, forward, _ = tooling.through_bprime(
            forward_fn,
            (example, f),
            role="forward",
            allowlist=allowlist,
            input_names=names,
            max_bytes=max_bytes,
        )
        _, init, _ = tooling.through_bprime(
            init_fn,
            (jax.random.PRNGKey(0),),
            role="init",
            allowlist=allowlist,
            input_names=["carbon/key"],
            max_bytes=max_bytes,
        )
    return submission.build(
        challenge=challenge_id(),
        interface=interface(strategy_).digest(),
        allowlist=allowlist,
        forward=forward,
        init=init,
    )


def train_graph(strategy_, prepared, *, seed):
    """Battery's own Carbon training loop over a prepared graph (G6): the
    classic written-out loop for the Level 0 MLP, `training.train` otherwise.
    Initialization and the training key come from `carbon.level4.train`."""
    import jax
    import numpy as np

    from ..level4 import train as level4_train

    m = material()
    _, model = _model(strategy_, m.train)
    x64 = model.settings["precision"] == "float64"

    def forward(p, f):
        if f.shape[0] == prepared.batch:
            return prepared.apply(list(p), f)[0]
        return prepared.predict(list(p), f)[0]

    if _is_classic(model, m):
        _targets(model, m)  # `fit`'s target scaling, which `classic_fit` reads
        y = model.layout.targets(m.train)
        result = classic_fit(
            model, m.train, y, seed, forward, lambda key, _a, _b: prepared.init(key)
        )
        return {"path": "classic", **result}

    def swap(_init, _apply, _n_in, _n_out, _dtype):
        def init(key):
            # `training.train` passes the Carbon seed's key; the training key
            # it then uses is Carbon's own, never one a graph returns.
            return jax.random.fold_in(key, level4_train.TRAIN_KEY_FOLD), prepared.init(
                key
            )

        return init, forward

    graph_model = general_path_model(strategy_, swap)
    with jax.enable_x64(x64):
        stats = graph_model.fit(m.train, structure(m), seed)
    out = graph_model.predict(m.train.x)
    return {
        "path": "general",
        "params_sha256": stats["params_sha256"],
        "final_loss": stats["final_loss"],
        "predictions_sha256": _digest(np.asarray(out[k]) for k in sorted(out)),
        "params": [np.asarray(a) for a in graph_model.params],
    }


def grade_graph(strategy_, prepared, params, *, seed):
    """G7's exam for battery: the trained graph predicts the public PRACTICE
    inputs (never hidden cases) through Carbon's padded inference, and
    battery's exam code, unchanged (`practice.score_practice`: the exam's own
    gates, TRAIN scales and frozen tolerances), gates and scores them."""
    del seed  # inference draws nothing at random
    import jax
    import numpy as np

    from .domain import INPUTS
    from .practice import PracticeSet, score_practice
    from .recipes import features, to_predictions

    m = material()
    practice = PracticeSet.load(REPOSITORY)
    _, model = _model(strategy_, m.train)
    _targets(model, m)
    model.s = structure(m)
    x = np.array([[r["inputs"][k] for k in INPUTS] for r in practice.records], float)
    x64 = model.settings["precision"] == "float64"
    dtype = np.float64 if x64 else np.float32
    f = features(x, model.rich).astype(dtype)
    with jax.enable_x64(x64):
        z = np.asarray(prepared.predict(list(params), f)[0])
    out = model.s.apply(
        x,
        *model.layout.split(model._decode(z.astype(float))),
        predict_v0=model.predict_v0,
    )
    rows, summary = score_practice(
        to_predictions(out, practice.case_ids), practice, m, REPOSITORY
    )
    return {
        "summary": summary,
        "rows": rows,
        "outputs": [z],
        "inputs": [f],
        "case_ids": practice.case_ids,
    }


def graph_equivalence(
    allowlist, strategy_, *, steps=None, seed=7, max_bytes, caps=None
):
    """E1: a recipe trained by its declarative path, then lowered and run
    through G3 (`submission.verify`), G4 (`validate_submission`) and G6."""
    import numpy as np

    from ..level4 import submission, validate
    from ..level4 import train as level4_train

    s = _steps(strategy_, steps)
    m = material()
    _, native = _model(s, m.train)
    declared = native.fit(m.train, structure(m), seed)
    manifest, files = lower_recipe(s, allowlist, max_bytes=max_bytes)
    _, parsed = submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge=challenge_id(),
        interface=interface(s).digest(),
        max_bytes=max_bytes,
    )
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface(s), batch=training_batch(s), caps=caps
    )
    prepared = level4_train.prepare(parsed, allowlist, verdict=verdict)
    result = level4_train.train(sys.modules[__name__], s, prepared, seed=seed)
    out = {
        "path": result["path"],
        "steps": native.steps,
        "status": verdict["status"],
        "batch": verdict["batch"],
        "submission": submission.digest(manifest),
        "declarative_params_sha256": declared["params_sha256"],
        "graph_params_sha256": result["params_sha256"],
        "identical": declared["params_sha256"] == result["params_sha256"],
    }
    if result["path"] == "general":
        native_out = native.predict(m.train.x)
        native_digest = _digest(np.asarray(native_out[k]) for k in sorted(native_out))
        out["predictions_identical"] = native_digest == result["predictions_sha256"]
        out["identical"] = out["identical"] and out["predictions_identical"]
    return out


# --- The development-only Level 4 variant (LEVEL4-DEV-VARIANT-01) -------------

LEVEL = 4
#: v2 carries the owner's caps and G5's accepted status (OWNER-L4-VALUES-01);
#: v3 declares `loss_override: graph` (LEVEL4-LOSS-OVERRIDE-01). v1 and v2
#: stay registered as history.
VERSION = "battery-l4-graph-v3"
#: The G6 loss slot this development variant admits (`carbon.level4.loss`):
#: a submitted per-case loss graph may replace battery's loss. Development
#: only; battery's frozen and live rules declare no override.
LOSS_OVERRIDE = "graph"
CAPABILITY = "hybrid.composition_graphs"
FIELD = "composition_graphs"
AUTHORITY = (
    "OWNER-LEVEL4-GRAPH-ONLY-01 (D1); OWNER-GRAPHITE-TEST-WAVE-03 section 1; "
    "OWNER-GRAPHITE-DEV-LEVELS-01 F1; LEVEL4-DEV-VARIANT-01; "
    "OWNER-L4-G5-COMPILE-ISOLATION-01; OWNER-L4-VALUES-01; LEVEL4-LOSS-OVERRIDE-01"
)
REVIEW = {
    "reviewer": "Test Lead",
    "record": (
        "Test Lead ruling 2026-10-08 (Level 4 PR 8): the Level 4 surface is the "
        "allowlist, the constant caps, the compute budget and gates G0-G7, at "
        "maximum freedom; the drafted surface is "
        "docs/development/graphite/level4/LEVEL4_CAPABILITY_DRAFT.md. "
        "Test Lead decision 2026-10-09 (LEVEL4-LOSS-OVERRIDE-01): this "
        "development variant declares loss_override: graph"
    ),
}
_SUMMARY = (
    "A graph-only submission: the math graph a miner's JAX or PyTorch model "
    "lowers to (carbon.level4 format), admitted only through gates G0-G7; "
    "Carbon initializes, trains and grades it, and no miner code runs"
)
_GATES = [
    "G0 intake (carbon.level4.intake)",
    "G3 isolated parse (carbon.level4._parse_worker)",
    "G4 validation (carbon.level4.validate)",
    (
        "G5 compile in isolation (carbon.level4.compile): accepted for development "
        "and testnet (OWNER-L4-G5-COMPILE-ISOLATION-01)"
    ),
    "G6 Carbon trains (carbon.level4.train)",
    "G7 Carbon grades (carbon.level4.grade)",
]


def _bounds(allowlist):
    from ..level4 import allowlist as allowlist_module
    from ..level4 import submission

    return {
        "admission": "graph_only",
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
        "submission_schema": submission.SCHEMA,
        "gates": list(_GATES),
        "caps": {name: value for name, value in allowlist_module.CAPS.items()},
        "compute_budget": (
            "one budget with Level 0, no separate Level 4 share (OWNER-L4-VALUES-01 "
            "section 5); binds only once the TRAINING-BUDGET-01 cost calculator "
            "costs development recipes"
        ),
        "interface": "the Level 0 network boundary in development (battery.level4.interface)",
        "training": "Carbon's key, battery's own loop and optimizer menu, TRAIN v1 only",
        "loss_override": LOSS_OVERRIDE,
        "loss_slot": (
            "a per-case loss graph (carbon.level4.loss, PHASE1_PLAN section 4.5) "
            "may replace battery's loss; Carbon maps it over the batch and takes "
            "the mean; G7's exam is unchanged"
        ),
    }


def variant_document(version=VERSION, *, base=None):
    """Battery's Level 4 variant document, built from the shipped allowlist
    and gates so the registered policy and the code cannot drift apart."""
    from ..level4 import allowlist as allowlist_module
    from ..reconstruction import expansion_record
    from ..reconstruction.capability_registry import contract

    challenge = challenge_id()
    if base is None:
        records = expansion_record.records(challenge)
        base = {
            "digest": contract(challenge).digest,
            "record_sequence": records[-1]["sequence"],
        }
    return {
        "schema": "carbon.construction-development-variant.v1",
        "version": version,
        "challenge": challenge,
        "level": LEVEL,
        "scope": "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS",
        "status": "REGISTERED_DEVELOPMENT_POLICY",
        "authority": AUTHORITY,
        "review": dict(REVIEW),
        "base_contract": dict(base),
        "participant_code": False,
        "widened": [
            {
                "id": CAPABILITY,
                "summary": _SUMMARY,
                "surface": None,
                "applies_to": None,
                "bounds": _bounds(allowlist_module.load()),
            }
        ],
    }


def reconstruct(value, admitted, granted):
    """Carbon's reconstruction of `hybrid.composition_graphs`
    (`development_variants.RECONSTRUCTIONS`): the submission's digest, pinned
    with the allowlist it is judged under. The documents themselves arrive
    through the Launchpad slot and are verified by `carbon.level4.intake`."""
    del admitted, granted
    from ..level4 import allowlist as allowlist_module
    from ..reconstruction import development_variants as dv
    from . import level4_worker

    if not (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(c in "0123456789abcdef" for c in value[7:])
    ):
        raise dv.VariantRefused(
            dv.PARAMETER_REFUSED,
            issues=[("development.level4.submission_digest", "/parameters/" + FIELD)],
        )
    allowlist = allowlist_module.load()
    return {
        "schema": level4_worker.SCHEMA,
        "submission": value,
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
        "lane": level4_worker.BLOCKED,
    }


def _reconstructions():
    from ..reconstruction.capability_registry import BATTERY_CHALLENGE

    return {(BATTERY_CHALLENGE, CAPABILITY): reconstruct}


RECONSTRUCTIONS = _reconstructions()


def _record_bounds():
    from ..reconstruction.capability_registry import BATTERY_CHALLENGE

    return {(BATTERY_CHALLENGE, CAPABILITY): ("loss_override",)}


#: The variant's bounds a Level 4 record carries
#: (`development_variants.RECORD_BOUNDS`): v3's `loss_override`, so the
#: rebuild admits a loss graph only under the variant that declares it.
RECORD_BOUNDS = _record_bounds()
