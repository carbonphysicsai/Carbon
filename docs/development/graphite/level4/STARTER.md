# Level 4 starter: a model spec that lowers and stages (GRAPHITE-L4-STARTER-01)

The lane G rerun of 2026-10-13 spent all 19 of its model calls learning how a Level 4 model spec is written and never
staged a submission. The stage tool's interface reply now carries a known-good starter. This page is the same starter, for a
person or a Launchpad option page; a test keeps it equal to what the tool returns.

## The spec (battery: one input of 4 features, one output of 245 values)
```python
import jax
import jax.numpy as jnp

FRAMEWORK = "jax"
# name -> (per-case shape, dtype); the interface reply lists [name, dtype, shape].
INPUTS = {"inputs/features": ((4,), "float32")}
N_IN, WIDTH, N_OUT = 4, 32, 245


def init(key):
    k1, k2 = jax.random.split(key)
    return [
        jax.random.normal(k1, (N_IN, WIDTH), jnp.float32) * 0.5,
        jnp.zeros((WIDTH,), jnp.float32),
        jax.random.normal(k2, (WIDTH, N_OUT), jnp.float32) * 0.1,
        jnp.zeros((N_OUT,), jnp.float32),
    ]


def forward(params, x0):
    w1, b1, w2, b2 = params
    x = jnp.concatenate([x0.reshape(x0.shape[0], -1)], axis=-1)
    return jnp.tanh(x @ w1 + b1) @ w2 + b2
```

spec.py defines FRAMEWORK = 'jax'; INPUTS = {name: (per-case shape tuple, dtype name)}, the interface's inputs in order (note the order: the interface reply lists [name, dtype, shape], INPUTS wants (shape, dtype)); init(key) -> the parameters, a list or tree of arrays; and forward(params, *inputs) -> one array of shape (batch, *output shape). Carbon supplies the key. Only operations on the Level 4 allowlist lower (dot, add, tanh, exp, log, max, min, concatenate, reshape and slicing among them); a refused operation is named in the lowering error.

## The commands (the interface reply gives them with your interface digest)
```
python -m carbon.level4.tooling lower spec.py lowered --challenge <challenge id> --interface <interface digest> --batch <batch>
python -m carbon.level4.tooling envelope lowered /scratch/output/level4-envelope.json.gz
```

## The two stage calls
1. `graphite_level4_stage` with `{"strategy_json": "<the recipe as a JSON string>", "task_id": ""}` returns the interface, the
   commands, the starter spec and `example_run_python`.
2. Run `example_run_python` as it stands in a workspace task: `kind` workspace, `strategy_json` null, `action` `run_python`,
   `arguments_json` that object (with `hypothesis` and `expected_effect` inside it). Note the finished task's id.
3. `graphite_level4_stage` again with the same recipe and `"task_id": "<that task id>"` returns `LEVEL4_STAGED` and the
   submission digest. Put it in the recipe's `parameters.composition_graphs` and call `graphite_run_proposal`.

Steps, as the reply lists them:
- 1. Call graphite_level4_stage with the recipe and task_id empty: you are reading that reply.
- 2. Run example_run_python as it stands in a workspace run_python task (kind=workspace, action=run_python, arguments_json = that object, including hypothesis and expected_effect inside it). It writes spec.py, lowers it and packs /scratch/output/level4-envelope.json.gz. Note the finished task's id.
- 3. Call graphite_level4_stage again with the same recipe and that task_id: the reply is LEVEL4_STAGED and names the submission digest.
- 4. Put the digest in the recipe's parameters.composition_graphs and call graphite_run_proposal.
- 5. To change the model, edit the spec text inside example_run_python (width, layers, activation); keep the commands as they are.
