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

A submission carrying a loss graph is not trained here yet: training on a
submitted loss is the next slice (`PHASE1_PLAN.md` section 4.5). Until then
it fails closed as Carbon's environment, never ignored.
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
LOSS_NOT_BUILT = "level4_loss_graph_training_not_built"
CAPS_UNSET = "level4_caps_human_input"
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

    from .recipes import features

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
        "params": leaves,
    }


class GraphModel(recipes.MLP):
    """Battery's MLP whose network is a submission's rebuilt graph."""

    STATE_KIND = STATE_KIND

    def __init__(self, family, settings, files, raw_manifest, submission):
        if family not in FAMILIES:
            raise ImportError("level4_family_not_served:" + str(family))
        # Carbon trains every graph in JAX, whatever framework authored it.
        super().__init__(family, {**settings, "backend": "jax"})
        self.files = dict(files)
        self.raw_manifest = raw_manifest
        self.submission = submission
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
        from carbon.level4 import intake, submission, train, validate

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
        if "loss" in parsed:
            raise ImportError(LOSS_NOT_BUILT)
        verdict = validate.validate_submission(
            parsed, allowlist, interface=interface, batch=batch
        )
        if verdict["status"] != "admitted":
            # An unset owner cap blocks; it never trains. The value is the
            # owner's to set, so the failure is Carbon's, not the candidate's.
            raise ImportError(CAPS_UNSET)
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
        )
        self.params, self.x64 = list(result["params"]), False
        return {
            "compile_s": 0.0,
            "train_s": time.perf_counter() - started,
            "final_loss": result["final_loss"],
            "params_sha256": result["params_sha256"],
            "n_params": int(sum(np.size(a) for a in self.params)),
        }

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
        `recipes.export_state` adds as for every battery model."""
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
        }
        return header, arrays


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
        header["family"], header["settings"], files, raw_manifest, header["submission"]
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
    return GraphModel(family, settings, files, raw_manifest, found["submission"])


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
