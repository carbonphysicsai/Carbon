"""Battery's Level 4 lowering with graph ensembles and kit inputs, beside the
pinned `level4.py`.

`level4.py` keeps its pinned bytes (historical v3 evidence;
`test_battery_level4_v4.test_historical_v3_and_pinned_implementation_bytes`).
This module carries the miner-side functions that changed after the pin: a
graph ensemble lowers at one identical member's interface
(`level4_model.interface_model`, LAUNCHPAD-BATTERY-L4-ENSEMBLE-01), and the
interface registers battery's published kit inputs
(OWNER-L4-CONSTANT-ACCOUNTING-02). For every Level 0 strategy that lowers, the
submission and interface digests equal the pinned module's. Everything else is
the pinned module's own helpers, imported when called.
"""

from __future__ import annotations


def _model(strategy_, train):
    """The native battery model; a single model gets TRAIN's layout early.

    Ensemble wrappers stay intact for training. Interface and graph lowering
    explicitly use one identical member's metadata instead.
    """
    from carbon.battery import recipes
    from carbon.battery.compile import build_model, compile_recipe

    from .level4_model import interface_model

    _, recipe = compile_recipe(strategy_)
    model = build_model(recipe)
    if recipe.family != "knn" and not isinstance(model, recipes.Ensemble):
        interface_model(model, train)
    return recipe, model


def interface(strategy_):
    """The development interface for a recipe: the Level 0 network boundary,
    battery's features in and normalized outputs out, at the recipe's
    precision, with battery's published kit inputs registered."""
    from ..level4.validate import Interface
    from . import level4
    from .level4_model import interface_model, published_kit

    _, model = _model(strategy_, level4.material().train)
    n_in, n_out = level4._dims(interface_model(model, level4.material().train))
    dtype = "float64" if model.settings["precision"] == "float64" else "float32"
    return Interface(
        inputs=(("inputs/features", dtype, (n_in,)),),
        outputs=((dtype, (n_out,)),),
        kit=published_kit(dtype)[0],
    )


def jax_network(strategy_, train):
    """`init(key) -> (key, params)`, `apply(params, f)` and sizes, exactly as
    `recipes.MLP._network` builds them for this recipe (one ensemble member)."""
    import jax
    import numpy as np

    from . import level4
    from .level4_model import interface_model

    recipe, model = _model(strategy_, train)
    model = interface_model(model, train)
    dtype = np.float64 if model.settings["precision"] == "float64" else np.float32
    n_in, n_out = level4._dims(model)
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


def training_batch(strategy_):
    """The batch a recipe trains at: its batch size, capped at TRAIN's size."""
    from . import level4

    m = level4.material()
    _, model = _model(strategy_, m.train)
    return min(model.settings["batch_size"], level4.batch(m))


def lower_recipe(strategy_, allowlist, *, max_bytes):
    """Miner side: a declarative recipe's network lowered into a Level 4
    submission (`(manifest, files)`) at the recipe's training batch. The init
    graph returns parameters only (no key)."""
    import jax

    from ..level4 import submission, tooling
    from . import level4
    from .level4_model import interface_model

    m = level4.material()
    _, model = _model(strategy_, m.train)
    model = interface_model(model, m.train)
    n = training_batch(strategy_)
    x64 = model.settings["precision"] == "float64"
    with jax.enable_x64(x64):
        if level4._is_classic(model, m):
            n_in, n_out = level4._dims(model)
            make = level4.classic_params(model)
            example = make(jax.random.PRNGKey(0), n_in, n_out)
            forward_fn, dtype = level4.classic_net(), "float32"

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
        challenge=level4.challenge_id(),
        interface=interface(strategy_).digest(),
        allowlist=allowlist,
        forward=forward,
        init=init,
    )
