"""A known-good Level 4 starter for a development session's Constructor (GRAPHITE-L4-STARTER-01).

Why: the lane G rerun of 2026-10-13 spent all 19 of its model calls learning how a Level 4 model spec is written,
reading the lowering tool's source through `run_python` (which the protected-material guard refuses), and never staged
a submission. The spec contract is documented only in the tooling module's own docstring, which the agent cannot
read. This module gives the stage tool's interface reply a worked example it can run unchanged and then edit.

The example is data, built from the recipe's own interface (`level4_admission.interface_and_batch`): one JAX
multilayer perceptron from the declared inputs to the declared outputs. `example_run_python` is a complete
`arguments_json` for a workspace `run_python` task that writes the spec, lowers it with the registered tooling and
packs the envelope at the export path the stage tool reads. Nothing here runs the agent's code or grants authority; the
stage tool still admits the envelope through G0, G3 and G4.
"""

from __future__ import annotations

import math

#: The model the example builds: one hidden layer, tanh. The agent changes this (width, depth, activation); the
#: lowering refuses an operation outside the Level 4 allowlist and names it.
EXAMPLE_WIDTH = 32
#: Seconds the example's run asks for; the lowering is a few seconds of CPU.
EXAMPLE_SECONDS = 300

SPEC_CONTRACT = (
    "spec.py defines FRAMEWORK = 'jax'; INPUTS = {name: (per-case shape tuple, dtype name)}, the interface's "
    "inputs in order (note the order: the interface reply lists [name, dtype, shape], INPUTS wants (shape, dtype)); "
    "init(key) -> the parameters, a list or tree of arrays; and forward(params, *inputs) -> one array of shape "
    "(batch, *output shape). Carbon supplies the key. Only operations on the Level 4 allowlist lower (dot, add, "
    "tanh, exp, log, max, min, concatenate, reshape and slicing among them); a refused operation is named in the "
    "lowering error."
)
WORKFLOW = (
    "1. Call graphite_level4_stage with the recipe and task_id empty: you are reading that reply.",
    (
        "2. Run example_run_python as it stands in a workspace run_python task: kind=workspace, "
        "strategy_json=null, action=run_python, arguments_json = that object (it already carries hypothesis and "
        "expected_effect), and hypothesis and expected_effect again at the top level of the call (copy the same "
        "two strings). It writes spec.py, lowers it and packs /scratch/output/level4-envelope.json.gz. The task id "
        "(rtsk_ and 64 hex digits) is public_result.task_id in the reply (also reply.result.task.task_id.value, "
        "which is there even while public_result is null: a task not yet finished, or failed); poll "
        "get_research_result with it until the task has finished."
    ),
    (
        "3. Call graphite_level4_stage again with the same recipe and that task_id: the reply is LEVEL4_STAGED and "
        "names the submission digest."
    ),
    "4. Put the digest in the recipe's parameters.composition_graphs and call graphite_run_proposal.",
    (
        "5. To change the model, edit the spec text inside example_run_python (width, layers, activation); keep the "
        "commands as they are."
    ),
)


def _count(shape):
    return int(math.prod(shape))


def example_spec(inputs, outputs):
    """The text of a known-good `spec.py` for an interface: `inputs` is `[[name, dtype, shape], ...]` and
    `outputs` is `[[dtype, shape], ...]` (one output)."""
    if len(outputs) != 1:
        raise ValueError("the starter builds one output")
    n_in = sum(_count(shape) for _, _, shape in inputs)
    n_out = _count(outputs[0][1])
    table = ", ".join(
        f'"{name}": ({tuple(shape)!r}, "{dtype}")' for name, dtype, shape in inputs
    )
    args = ", ".join(f"x{i}" for i in range(len(inputs)))
    flat = ", ".join(f"x{i}.reshape(x{i}.shape[0], -1)" for i in range(len(inputs)))
    return (
        "import jax\n"
        "import jax.numpy as jnp\n"
        "\n"
        'FRAMEWORK = "jax"\n'
        "# name -> (per-case shape, dtype); the interface reply lists [name, dtype, shape].\n"
        f"INPUTS = {{{table}}}\n"
        f"N_IN, WIDTH, N_OUT = {n_in}, {EXAMPLE_WIDTH}, {n_out}\n"
        "\n"
        "\n"
        "def init(key):\n"
        "    k1, k2 = jax.random.split(key)\n"
        "    return [\n"
        "        jax.random.normal(k1, (N_IN, WIDTH), jnp.float32) * 0.5,\n"
        "        jnp.zeros((WIDTH,), jnp.float32),\n"
        "        jax.random.normal(k2, (WIDTH, N_OUT), jnp.float32) * 0.1,\n"
        "        jnp.zeros((N_OUT,), jnp.float32),\n"
        "    ]\n"
        "\n"
        "\n"
        f"def forward(params, {args}):\n"
        "    w1, b1, w2, b2 = params\n"
        f"    x = jnp.concatenate([{flat}], axis=-1)\n"
        "    return jnp.tanh(x @ w1 + b1) @ w2 + b2\n"
    )


def example_run_python(spec_text, commands):
    """A complete `arguments_json` object for a `run_python` workspace task that writes `spec_text`, then runs the two
    registered `commands` (the interface reply's own)."""
    source = (
        "import pathlib, shlex, subprocess, sys\n"
        f"SPEC = {spec_text!r}\n"
        'pathlib.Path("spec.py").write_text(SPEC)\n'
        f"for command in {list(commands)!r}:\n"
        '    argv = shlex.split(command.replace("python ", sys.executable + " ", 1))\n'
        "    subprocess.run(argv, check=True)\n"
    )
    return {
        "source": source,
        "files": [],
        "seconds": EXAMPLE_SECONDS,
        "hypothesis": "The starter spec lowers and packs into a Level 4 envelope.",
        "expected_effect": "A level4-envelope.json.gz export the stage tool can read.",
    }
