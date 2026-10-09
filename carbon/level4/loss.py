"""The G6 loss slot, v1 (development only; the working contract is
`docs/development/graphite/level4/PHASE1_PLAN.md` section 4.4).

A submission may carry a `loss` graph only where its Challenge declares
`loss_override: graph`. Under `none` or `terms` (Level 1's loss terms), a
loss document is refused (`loss_not_permitted`), never ignored. An unknown
or unset declaration permits nothing.

The loss graph is declared **per case**: its inputs are one case each
(leading dimension 1) and its single output is that case's loss, shape
`[1]`. Carbon maps it over the batch and owns the reduction, a mean
(`per_case_mean`), so a loss graph never sees another case and cannot
weight, select or compare cases. Its inputs, by name and in this order:

* `loss/pred/<k>`: the Challenge's declared outputs (the interface's);
* `loss/target/<k>`: TRAIN targets, in the same layout as `pred`;
* `loss/x/<name>`: the TRAIN inputs (the interface's, without `inputs/`);
* `loss/aux/<k>`: optional auxiliary outputs the forward graph declares
  after the interface's outputs, at most `AUX_LIMIT` (HUMAN_INPUT: unset,
  no auxiliary output is admitted).

No parameter input (regularisation is the optimizer menu's) and no key (the
allowlist admits RNG only in init). Carbon differentiates it. A non-finite
loss is the candidate's own training failure, never FAILED_INFRA.
"""

from __future__ import annotations

from . import graph
from .allowlist import HUMAN_INPUT

OVERRIDES = ("none", "terms", "graph")
PRED, TARGET, X, AUX = "loss/pred/", "loss/target/", "loss/x/", "loss/aux/"
#: The most auxiliary outputs a forward graph may declare for the loss.
AUX_LIMIT = HUMAN_INPUT
_FLOATS = ("float32", "float64")


def gate(slots, loss_override):
    """Refuse a loss document unless the Challenge declares `graph`."""
    if "loss" not in slots:
        return
    if loss_override not in OVERRIDES or loss_override != "graph":
        raise graph.GraphRefused("loss_not_permitted", str(loss_override))


def aux_outputs(forward, interface, aux_limit=AUX_LIMIT):
    """The forward graph's auxiliary outputs, `[(dtype, per-case shape)]`:
    those after the interface's, refused beyond `aux_limit` (an unset limit
    admits none)."""
    entry = forward["graphs"][forward["entry"]]
    extra = entry["outputs"][len(interface.outputs) :]
    if not extra:
        return []
    if aux_limit == HUMAN_INPUT or aux_limit is None or len(extra) > aux_limit:
        raise graph.GraphRefused("loss_aux_not_admitted", str(len(extra)))
    values = {}
    for node in entry["nodes"]:
        for out in node["out"]:
            values[out["value"]] = out
    for item in entry["inputs"] + entry["constants"]:
        values[item["value"]] = item
    return [(values[v]["dtype"], tuple(values[v]["shape"][1:])) for v in extra]


def expected_inputs(interface, aux=()):
    """`[(name, dtype, shape)]` the loss graph must take, per case."""
    out = []
    for k, (dtype, case) in enumerate(interface.outputs):
        out.append((f"{PRED}{k}", dtype, [1, *case]))
    for k, (dtype, case) in enumerate(interface.outputs):
        out.append((f"{TARGET}{k}", dtype, [1, *case]))
    for name, dtype, case in interface.inputs:
        out.append((X + name.split("/", 1)[1], dtype, [1, *case]))
    for k, (dtype, case) in enumerate(aux):
        out.append((f"{AUX}{k}", dtype, [1, *case]))
    return out


def check(doc, interface, aux=()):
    """The loss graph's slot contract, or `GraphRefused`."""
    if doc["role"] != "loss":
        raise graph.GraphRefused("role_mismatch")
    entry = doc["graphs"][doc["entry"]]
    got = [(i["name"], i["dtype"], list(i["shape"])) for i in entry["inputs"]]
    wanted = expected_inputs(interface, aux)
    names = {n for n, _, _ in wanted}
    for name, _, _ in got:
        if name not in names:
            raise graph.GraphRefused("loss_input_unexpected", name)
    if [n for n, _, _ in got] != [n for n, _, _ in wanted]:
        raise graph.GraphRefused("loss_input_missing")
    for (name, dtype, shape), (_, want_dtype, want_shape) in zip(got, wanted):
        if (dtype, shape) != (want_dtype, want_shape):
            raise graph.GraphRefused("loss_input_shape", name)
    values = {}
    for node in entry["nodes"]:
        for out in node["out"]:
            values[out["value"]] = out
    for item in entry["inputs"] + entry["constants"]:
        values[item["value"]] = item
    if len(entry["outputs"]) != 1:
        raise graph.GraphRefused("loss_output")
    out = values[entry["outputs"][0]]
    if out["dtype"] not in _FLOATS or list(out["shape"]) != [1]:
        raise graph.GraphRefused("loss_output")


def per_case_mean(rebuilt):
    """`loss(pred, target, x, aux) -> scalar`: the rebuilt per-case graph
    mapped over the batch (each case alone), then Carbon's mean. Each
    argument is a list of arrays with the batch leading."""
    import jax
    import jax.numpy as jnp

    def one(*case):
        (value,) = rebuilt(*[a[None] for a in case])
        return value[0]

    def loss(pred, target, x, aux=()):
        flat = [*pred, *target, *x, *aux]
        return jnp.mean(jax.vmap(one)(*flat))

    return loss
