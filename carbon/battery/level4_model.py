"""Battery's trained Level 4 graph, as a battery model (development only).

`GraphModel` is battery's MLP with its network replaced by a submission's
rebuilt forward graph (`carbon.level4`):

* **Carbon's key initializes it**, through the submission's init graph or
  its declared spec; the training key is Carbon's own (`train.keys`).
* **Battery's own loop trains it**: the classic written-out loop
  (`classic_fit`) or `training.train`, exactly as E1 showed
  bit-identical to the declarative recipe.
* **Battery's own decoding** turns its outputs into predictions.

Before training, the submission is verified (`submission.verify`) and
validated (G4, the owner's caps) against battery's development interface
at the recipe's training batch, before anything is built or trained. A
refusal there is the candidate's; an owner cap still unset (`HUMAN_INPUT`)
blocks as Carbon's (`CAPS_UNSET`), never trains.

It imports only battery's own recipe modules (relatively) and `carbon.level4`,
so a rebuild worker can stage it beside them.

Its state (`STATE_KIND`) is self-contained: the trained parameters,
battery's target statistics, the manifest and every document. Inference
rebuilds and re-validates the graph from the state alone; nothing is staged
at inference.

**A submitted loss graph (G6, `PHASE1_PLAN.md` section 4.5)** replaces
battery's loss only where the record's variant declares `loss_override:
graph` (battery-l4-graph-v3); anywhere else G4 refuses it
(`loss_not_permitted`). The graph is per case. Carbon maps it over the batch
and takes the plain mean (`carbon.level4.loss.per_case_mean`), so battery's
own loss terms, which weight, select or reshape cases, must stay at their
neutral values (`NEUTRAL`). Otherwise the submission is refused
(`LOSS_TERMS`), never silently ignored. The loss is the only thing that
changes:
* the classic path keeps its written-out loop (`classic_fit`, `objective=`);
* the general path keeps `training.train`'s optimizer, schedule, batch draw,
  microbatches, averaging and polish (`objective_fit`), pinned to it by a test.
Battery's implementation modules are not edited.
"""

from __future__ import annotations

import time

import numpy as np

from . import recipes

STATE_KIND = "level4_graph"
#: Battery's Challenge id (`level4.challenge_id()`, held equal by a test),
#: named here so the module stages without the capability registry.
CHALLENGE = "battery-fastcharge-ageing-development-v1"
#: Battery families whose network a Level 4 graph replaces; the
#: nearest-neighbour recipe has no trained network.
FAMILIES = ("mlp", "deeponet")
CAPS_UNSET = "level4_caps_human_input"
#: A loss graph beside one of battery's own loss terms (the candidate's).
LOSS_TERMS = "loss_graph_with_loss_terms"
#: Battery's loss-term settings at their neutral values (the catalog defaults):
#: under a loss graph the loss is the graph's, reduced by Carbon's plain mean.
NEUTRAL = {
    "important_region_weight": 1.0,
    "relative_loss": False,
    "time_weighting": "uniform",
    "h1_weight": 0.0,
    "h2_weight": 0.0,
    "spectral_weight": 0.0,
    "curriculum": "none",
    "hard_example_weight": 0.0,
}
_PCA_ARRAYS = ("vm", "tm", "pv", "pt", "zmu", "zsd")


def dims(model):
    """Input width from battery's own `features`, and the output width."""
    import numpy as np

    from .recipes import BOUNDS, features

    lay = model.layout
    n_in = features(np.asarray(BOUNDS[:, :1].T, float), model.rich).shape[1]
    if model.pca:
        return n_in, 2 * model.pca + 1 + lay.k
    return n_in, lay.nv + lay.nt + 1 + lay.k


def classic_fit(model, d, y, seed, net, make_params, objective=None):
    """`recipes.MLP._fit_classic`'s loop with `net` and `make_params(key)`
    supplied: the Level 0 MLP's written-out full-batch Adam(W) with cosine
    decay, statement for statement (history recording off). Run with the
    native `net` it must reproduce `MLP.fit`'s digest exactly; that pins this
    copy to the declarative path before the rebuilt `net` is compared.

    `objective(pred, target, x)`, when given, is the loss instead of
    battery's (an admitted loss graph's, `Prepared.loss`); each argument is a
    list of arrays with the cases leading."""
    import hashlib

    import jax
    import jax.numpy as jnp
    import numpy as np

    from .recipes import features

    z = model._encode(y).astype(np.float32)
    f = features(d.x, model.rich).astype(np.float32)
    sw = np.where(d.important, model.important_weight, 1.0).astype(np.float32)
    gw = model._group_weights(z.shape[1]).astype(np.float32)
    params = make_params(jax.random.PRNGKey(seed), f.shape[1], z.shape[1])

    if objective is None:

        def loss(p, xx, yy):
            r = (net(p, xx) - yy) ** 2
            return jnp.sum(sw[:, None] * r * gw[None, :]) / jnp.sum(sw)

    else:

        def loss(p, xx, yy):
            return objective([net(p, xx)], [yy], [xx])

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
        "params": leaves,
    }


def objective_train(*, init, apply, f, z, settings, seed, objective):
    """`training.train` with its loss replaced by `objective(pred, target,
    x)`, Carbon's mean over the drawn cases (an admitted loss graph's,
    `Prepared.loss`). Everything else is `training.train`'s, statement for
    statement: the optimizer menu (`training.optimizer`), the step count, the
    batch draw from Carbon's key, microbatches, plateau, EMA, tail averaging,
    schedule-free evaluation, polish and history recording. The case
    weighting `training.train` applies (`sw`, curriculum, hard examples) is
    absent: under a loss graph those settings are refused at their
    non-neutral values (`NEUTRAL`). A test pins this copy: with battery's own
    case loss as `objective` it reproduces `training.train`'s parameters."""
    import jax
    import jax.numpy as jnp
    import optax

    from . import training

    s = settings
    n = f.shape[0]
    steps = s["steps"] - s["polish_steps"]
    batch = min(s["batch_size"], n)
    micro = s["microbatches"]
    key = jax.random.PRNGKey(seed)
    key, params = init(key)
    f, z = jnp.asarray(f), jnp.asarray(z)
    tx = training.optimizer(jax, optax, s, steps)

    def loss(p, idx):
        return objective([apply(p, f[idx])], [z[idx]], [f[idx]])

    def gradient(p, idx):
        if micro == 1:
            return jax.value_and_grad(loss)(p, idx)
        chunks = idx.reshape(micro, -1)
        total = None
        for c in range(micro):
            v, g = jax.value_and_grad(loss)(p, chunks[c])
            if total is None:
                total = (v, g)
            else:
                total = (
                    total[0] + v,
                    jax.tree_util.tree_map(jnp.add, total[1], g),
                )
        return total[0] / micro, jax.tree_util.tree_map(lambda g: g / micro, total[1])

    tail = int(steps * (1.0 - s["tail_averaging"])) if s["tail_averaging"] else steps
    decay = s["ema_decay"]
    use_ema = s["inference_weights"] == "ema"
    plateau = s["learning_rate_curve"] == "train_loss_plateau"
    everything = jnp.arange(n)
    recording = training.recording_history()

    def step_fn(carry, i):
        p, state, ema, avg, k = carry
        k, sub = jax.random.split(k)
        idx = everything if batch >= n else jax.random.permutation(sub, n)[:batch]
        value, g = gradient(p, idx)
        if plateau:
            updates, state = tx.update(g, state, p, value=value)
        else:
            updates, state = tx.update(g, state, p)
        p = optax.apply_updates(p, updates)
        if use_ema:
            ema = jax.tree_util.tree_map(
                lambda e, x: decay * e + (1 - decay) * x, ema, p
            )
        if s["tail_averaging"]:
            count = jnp.maximum(i - tail + 1, 1).astype(f.dtype)
            avg = jax.tree_util.tree_map(
                lambda a, x: jnp.where(i >= tail, a + (x - a) / count, a), avg, p
            )
        return (p, state, ema, avg, k), (value if recording else None)

    @jax.jit
    def run(params, key):
        carry = (params, tx.init(params), params, params, key)
        (p, state, ema, avg, _), values = jax.lax.scan(
            step_fn, carry, jnp.arange(steps, dtype=f.dtype)
        )
        return p, state, ema, avg, values

    p, state, ema, avg, values = run(params, key)
    if recording:
        training.keep_history(enumerate(np.asarray(values).tolist()), steps)
    if s["optimizer_family"] == "free_adamw":
        from optax.contrib import schedule_free_eval_params

        p = schedule_free_eval_params(state, p)
    if use_ema:
        p = ema
    elif s["tail_averaging"]:
        p = avg
    if s["polish_steps"]:
        p = training.polish(
            jax, optax, p, lambda q: loss(q, everything), s["polish_steps"]
        )
    return jax.block_until_ready(p)


class GraphModel(recipes.MLP):
    """Battery's MLP whose network is a submission's rebuilt graph."""

    STATE_KIND = STATE_KIND

    def __init__(
        self, family, settings, files, raw_manifest, submission, loss_override="none"
    ):
        if family not in FAMILIES:
            raise ImportError("level4_family_not_served:" + str(family))
        # Carbon trains every graph in JAX, whatever framework authored it.
        super().__init__(family, {**settings, "backend": "jax"})
        self.files = dict(files)
        self.raw_manifest = raw_manifest
        self.submission = submission
        #: The variant's declaration, from the record (`RECORD_BOUNDS`); a
        #: record without one admits no loss graph.
        self.loss_override = loss_override
        self.prepared = None

    # -- the submission, verified and validated --------------------------------------
    def _interface(self):
        from carbon.level4.validate import Interface

        n_in, n_out = dims(self)
        dtype = "float64" if self.settings["precision"] == "float64" else "float32"
        return Interface(
            inputs=(("inputs/features", dtype, (n_in,)),), outputs=((dtype, (n_out,)),)
        )

    def _prepare(self, batch):
        from carbon.level4 import allowlist as allowlist_module
        from carbon.level4 import graph, intake, submission, train, validate

        allowlist = allowlist_module.load()
        interface = self._interface()
        _, parsed = submission.verify(
            self.raw_manifest,
            self.files,
            allowlist=allowlist,
            challenge=CHALLENGE,
            interface=interface.digest(),
            max_bytes=intake.BOUNDS["document_bytes"],
        )
        verdict = validate.validate_submission(
            parsed,
            allowlist,
            interface=interface,
            batch=batch,
            loss_override=self.loss_override,
        )
        if verdict["status"] != "admitted":
            # An unset owner cap blocks; it never trains. The value is the
            # owner's to set, so the failure is Carbon's, not the candidate's.
            raise ImportError(CAPS_UNSET)
        if "loss" in parsed:
            terms = sorted(k for k, v in NEUTRAL.items() if self.settings[k] != v)
            if terms:
                raise graph.GraphRefused(LOSS_TERMS, ",".join(terms))
        return train.prepare(parsed, allowlist, verdict=verdict)

    # -- training ------------------------------------------------------------------
    def fit(self, d, structure, seed):
        subset = recipes.train_subset(d, self.fraction, seed)
        # `MLP.fit` sets the same layout again; the interface needs it first.
        self.layout = recipes.Layout(
            subset.v.shape[1],
            subset.q.shape[1],
            bounded_v=self.bounded_v,
            predict_v0=self.predict_v0,
            fade=self.fade,
        )
        batch = min(self.settings["batch_size"], len(subset.case_ids))
        self.prepared = self._prepare(batch)
        return super().fit(d, structure, seed)

    def _forward(self):
        prepared = self.prepared

        def forward(p, f):
            if f.shape[0] == prepared.batch:
                return prepared.apply(list(p), f)[0]
            return prepared.predict(list(p), f)[0]

        return forward

    def _network(self, jax, dtype, n_in, n_out):
        from carbon.level4 import train

        prepared = self.prepared

        def init(key):
            # `training.train` passes the Carbon seed's key; the training key
            # it then uses is Carbon's own, never one a graph returns.
            return jax.random.fold_in(key, train.TRAIN_KEY_FOLD), prepared.init(key)

        return init, self._forward()

    def _fit_classic(self, d, y, seed):
        started = time.perf_counter()
        result = classic_fit(
            self,
            d,
            y,
            seed,
            self._forward(),
            lambda key, _n_in, _n_out: self.prepared.init(key),
            objective=self.prepared.loss,
        )
        self.params, self.x64 = list(result["params"]), False
        return {
            "compile_s": 0.0,
            "train_s": time.perf_counter() - started,
            "final_loss": result["final_loss"],
            "params_sha256": result["params_sha256"],
            "n_params": int(sum(np.size(a) for a in self.params)),
        }

    def _fit_general(self, d, y, seed):
        """Battery's `training.train` (`recipes.MLP._fit_general`, unchanged)
        with no loss graph; `objective_train` with one."""
        objective = self.prepared.loss
        if objective is None:
            return super()._fit_general(d, y, seed)
        import hashlib

        import jax
        import jax.numpy as jnp

        from .training import take_history

        self.x64 = self.settings["precision"] == "float64"
        dtype = np.float64 if self.x64 else np.float32
        started = time.perf_counter()
        with jax.enable_x64(self.x64):
            z = self._encode(y).astype(dtype)
            f = recipes.features(d.x, self.rich).astype(dtype)
            init, apply = self._network(jax, dtype, f.shape[1], z.shape[1])
            params = objective_train(
                init=init,
                apply=apply,
                f=f,
                z=z,
                settings=self.settings,
                seed=seed,
                objective=objective,
            )
            leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
            zz, ff = jnp.asarray(z), jnp.asarray(f)
            final = float(objective([apply(params, ff)], [zz], [ff]))
        self.params, self._apply = params, apply
        blob = b"".join(a.tobytes() for a in leaves)
        return recipes._with_history(
            {
                "compile_s": 0.0,
                "train_s": time.perf_counter() - started,
                "final_loss": final,
                "params_sha256": hashlib.sha256(blob).hexdigest(),
                "n_params": int(sum(a.size for a in leaves)),
            },
            take_history(),
        )

    # -- inference -----------------------------------------------------------------
    def _leaves(self):
        import jax

        return [np.asarray(a) for a in jax.tree_util.tree_leaves(self.params)]

    def predict(self, x):
        import jax
        import jax.numpy as jnp

        x64 = bool(getattr(self, "x64", False))
        with jax.enable_x64(x64):
            dtype = np.float64 if x64 else np.float32
            f = recipes.features(x, self.rich).astype(dtype)
            out = self.prepared.predict(
                [jnp.asarray(a) for a in self._leaves()], jnp.asarray(f)
            )
            z = np.asarray(out[0], float)
        return self.s.apply(
            x, *self.layout.split(self._decode(z)), predict_v0=self.predict_v0
        )

    # -- state -----------------------------------------------------------------------
    def export_state(self):
        """`(header, arrays)` without the schema, layout and OCV table, which
        `state_bytes` adds as `recipes.export_state` does for every battery
        model."""
        arrays = {}
        for name in ("mu", "sd") + (_PCA_ARRAYS if self.pca else ()):
            arrays[name] = np.asarray(getattr(self, name))
        leaves = self._leaves()
        for i, leaf in enumerate(leaves):
            arrays[f"leaf{i:04d}"] = leaf
        arrays["manifest"] = np.frombuffer(self.raw_manifest, np.uint8)
        names = sorted(self.files)
        for k, name in enumerate(names):
            arrays[f"document{k:02d}"] = np.frombuffer(self.files[name], np.uint8)
        header = {
            "kind": STATE_KIND,
            "family": self.family,
            "settings": self.settings,
            "submission": self.submission,
            "documents": names,
            "classic": bool(self.classic),
            "x64": bool(getattr(self, "x64", False)),
            "leaves": len(leaves),
            "batch": self.prepared.batch,
            "loss_override": self.loss_override,
        }
        return header, arrays


def state_bytes(model):
    """A trained graph model's self-describing state, in battery's state
    format (`recipes.state_bytes`): the header, the layout, the OCV table and
    every array. Kept here, not in `recipes`, so battery's implementation
    modules (and so every recipe digest) are unchanged by Level 4."""
    import io
    import json

    header, arrays = model.export_state()
    header["schema"] = recipes.STATE_SCHEMA
    header["layout"] = recipes._layout_state(model.layout)
    arrays["ocv_soc"], arrays["ocv_v"] = model.s.ocv_soc, model.s.ocv_v
    buffer = io.BytesIO()
    np.savez(
        buffer,
        __header__=np.frombuffer(json.dumps(header, sort_keys=True).encode(), np.uint8),
        **arrays,
    )
    return buffer.getvalue()


def model_from_bytes(body):
    """The trained graph model a `state_bytes` state describes; never trains.
    Any other state kind is refused: it is `recipes.model_from_bytes`'s."""
    import io
    import json

    with np.load(io.BytesIO(body), allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files if k != "__header__"}
        header = json.loads(bytes(data["__header__"]).decode())
    if header.get("schema") != recipes.STATE_SCHEMA or header.get("kind") != STATE_KIND:
        raise ValueError("not a Level 4 graph model state")
    layout = recipes.Layout(
        header["layout"]["g"],
        header["layout"]["k"],
        bounded_v=header["layout"]["bounded_v"],
        predict_v0=header["layout"]["predict_v0"],
        fade=header["layout"]["fade"],
    )
    structure = recipes.Structure(arrays["ocv_soc"], arrays["ocv_v"])
    return import_state(header, arrays, layout, structure)


def import_state(header, arrays, layout, structure):
    """The trained graph model a `level4_graph` state describes, its
    submission verified and validated again; never trains."""
    from carbon.level4 import submission

    raw_manifest = bytes(arrays["manifest"])
    if submission.name(raw_manifest) != header["submission"]:
        raise ValueError("model state submission is not its manifest")
    files = {
        name: bytes(arrays[f"document{k:02d}"])
        for k, name in enumerate(header["documents"])
    }
    model = GraphModel(
        header["family"],
        header["settings"],
        files,
        raw_manifest,
        header["submission"],
        loss_override=header["loss_override"],
    )
    model.layout, model.s = layout, structure
    model.classic, model.x64 = header["classic"], header["x64"]
    for name in ("mu", "sd") + (_PCA_ARRAYS if model.pca else ()):
        setattr(model, name, arrays[name])
    model.prepared = model._prepare(header["batch"])
    model.params = [arrays[f"leaf{i:04d}"] for i in range(header["leaves"])]
    return model


def _recipe(recipe):
    """`(family, settings)` from a compiled recipe or its staged JSON."""
    if isinstance(recipe, dict):
        return recipe["family"], recipe["settings"]
    return recipe.family, recipe.settings


def build(recipe, found, workspace):
    """The untrained graph model for a Level 4 record, from the files a
    rebuild worker was staged with. A workspace that is not the record's
    submission is Carbon's own fault (`StagingCorrupt`), raised as an
    environment failure, never the candidate's."""
    from carbon.level4 import staging

    try:
        raw_manifest, files = staging.from_workspace(workspace, found["submission"])
    except staging.StagingCorrupt as corrupt:
        raise ImportError("level4_staging_corrupt:" + str(corrupt)) from None
    family, settings = _recipe(recipe)
    return GraphModel(
        family,
        settings,
        files,
        raw_manifest,
        found["submission"],
        # The variant's declaration, carried by the record; none admits no loss.
        loss_override=found.get("loss_override", "none"),
    )


def build_from_work(recipe, work):
    """`build` inside a rebuild worker: the record and the submission's
    staged files from the worker's directory. With no staged manifest the
    rebuild fails closed as Carbon's environment."""
    import json

    from carbon.level4 import staging

    found = json.loads((work / "level4-graph.json").read_text(encoding="utf-8"))
    if not (work / staging.WORKSPACE_MANIFEST).is_file():
        raise ImportError("level4_submission_documents_not_staged")
    workspace = {
        path.name: path.read_bytes()
        for path in work.iterdir()
        if path.name == staging.WORKSPACE_MANIFEST
        or path.name.startswith(staging.WORKSPACE_PREFIX)
    }
    return build(recipe, found, workspace)
