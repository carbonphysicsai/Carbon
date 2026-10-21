"""Battery's published scaffold, anchored so it can pass the initial-state and
voltage-limit gates (Test Lead and Validator, 2026-10-20).

Same network as the published scaffold (`carbon.battery.public_scaffold`:
unit(x) to the published input bounds, dense [4, 64, 64, 64, 247] with gelu),
with three fixed, non-trained pieces of public structure on its output, each
from the case's own inputs or a published protocol limit only (never a
reference or exam value):
- T(0) = the case's ambient temperature (input t_amb_c);
- V(0) = OCV(soc0) from the published OCV table (input soc0; the table is
  public material, pinned by its sha256), as the same piecewise-linear
  function the judge interpolates: a sum of relu hinges at the table's own
  knots on the published soc0 range;
- every voltage clamped into the published protocol window [V_MIN, V_MAX],
  a few microvolts inside it so float32 decoding cannot cross it.
The direct adapter standardizes each output over TRAIN and decodes
out * sd + mu, so the anchors are written in that normalized space with the
adapter's own TRAIN statistics (public TRAIN, train_fraction 1.0: the
recipe's default; a smaller fraction changes the statistics and the anchors).

python scripts/dev/battery_public_scaffold_build.py <out_dir>   (from the checkout root, JAX CPU)

Its output reproduces carbon/battery/public_scaffold/ byte for byte.
"""

import hashlib
import itertools
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")

import jax
import jax.numpy as jnp
import numpy as np

from carbon.battery import challenge, construction_kit, direct_graph, domain
from carbon.battery.scaffold import SCAFFOLD
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.level4 import allowlist, graph, initializers, intake, submission
from carbon.level4.tooling import through_bprime

#: Microvolts inside the protocol window, so float32 decoding stays inside it.
WINDOW_MARGIN_V = 5e-6

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
root = Path.cwd()
kit = construction_kit.construction_kit()
training = {"steps": SCAFFOLD["parameters"]["steps"]}


def recipe_for(graph_digest):
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": graph_digest},
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": training},
                "train_use": {
                    "dataset": direct_graph.TRAIN_USE,
                    "train_fraction": 1.0,
                    "curriculum": "none",
                },
                "initial_state": None,
            },
            "output": {
                "format": direct_graph.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )


settings = direct_graph.training_settings(recipe_for("sha256:" + "0" * 64))
assert (
    settings["precision"] == "float32" and settings["train_fraction"] == 1.0
), settings
interface = direct_graph.graph_interface(settings)
n_in = interface.inputs[0][2][0]
n_out = interface.outputs[0][1][0]
g = domain.GRID_POINTS
width, depth = SCAFFOLD["parameters"]["width"], SCAFFOLD["parameters"]["depth"]
sizes = [n_in] + [width] * depth + [n_out]
bounds = np.array([domain.INPUT_BOUNDS[k] for k in domain.INPUTS], dtype=np.float32)
low, span = bounds[:, 0], bounds[:, 1] - bounds[:, 0]
T_AMB, SOC0 = domain.INPUTS.index("t_amb_c"), domain.INPUTS.index("soc0")

# The adapter's own TRAIN statistics, computed exactly as DirectGraphModel.fit.
material = challenge.PublicMaterial.load(root)
y = direct_graph._targets(material.train).astype(np.float32)
mu = y.mean(axis=0)
sd = y.std(axis=0) + np.float32(1e-9)

# The published OCV table on the published soc0 range, as relu hinges.
table = json.loads((root / challenge.OCV_TABLE_PATH).read_bytes())
assert (
    hashlib.sha256((root / challenge.OCV_TABLE_PATH).read_bytes()).hexdigest()
    == challenge.OCV_TABLE_SHA256
)
soc, ocv = np.asarray(table["soc"], np.float64), np.asarray(table["ocv_v"], np.float64)
s_lo, s_hi = domain.INPUT_BOUNDS["soc0"]
inside = (soc > s_lo) & (soc < s_hi)
dense = np.concatenate([[s_lo], soc[inside], [s_hi]])
dense_v = np.interp(dense, soc, ocv)


def thin(xs, ys, budget):
    """Douglas-Peucker: the fewest table knots whose piecewise-linear curve
    stays within `budget` volts of the table's own on the range."""
    keep = {0, len(xs) - 1}
    stack = [(0, len(xs) - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        line = ys[i] + (ys[j] - ys[i]) * (xs[i + 1 : j] - xs[i]) / (xs[j] - xs[i])
        k = int(np.argmax(np.abs(ys[i + 1 : j] - line))) + i + 1
        if abs(ys[k] - line[k - i - 1]) > budget:
            keep.add(k)
            stack += [(i, k), (k, j)]
    idx = sorted(keep)
    return xs[idx], ys[idx]


#: Volts the thinned OCV may differ from the table's curve: 1/20 of tau_v0.
OCV_BUDGET_V = 5e-5
knots, values = thin(dense, dense_v, OCV_BUDGET_V)
slopes = np.diff(values) / np.diff(knots)
hinge_at = knots[1:-1]
hinge_c = np.diff(slopes)
base_v, base_slope = values[0], slopes[0]


def ocv_numpy(s):
    return (
        base_v
        + base_slope * (s - s_lo)
        + np.sum(hinge_c * np.maximum(s[:, None] - hinge_at, 0.0), axis=1)
    )


check = np.linspace(s_lo, s_hi, 50001)
ocv_err = float(np.abs(ocv_numpy(check) - np.interp(check, soc, ocv)).max())

# Normalized-space constants (float32, as the graph computes).
v0_mu, v0_sd, t0_mu, t0_sd = (np.float32(a) for a in (mu[0], sd[0], mu[g], sd[g]))
v_hi = ((domain.V_MAX - WINDOW_MARGIN_V) - mu[1:g]) / sd[1:g]
v_lo = ((domain.V_MIN + WINDOW_MARGIN_V) - mu[1:g]) / sd[1:g]
const = {
    k: jnp.asarray(v, jnp.float32)
    for k, v in {
        "low": low,
        "span": span,
        "v_hi": v_hi,
        "v_lo": v_lo,
        "hinge_at": hinge_at,
        "hinge_c": hinge_c,
    }.items()
}


def forward(*args):
    *params, x = args
    h = (x - const["low"]) / const["span"]
    pairs = list(zip(params[0::2], params[1::2]))
    for w, b in pairs[:-1]:
        h = jax.nn.gelu(h @ w + b)
    w, b = pairs[-1]
    raw = h @ w + b
    s = x[:, SOC0 : SOC0 + 1]
    t_amb = x[:, T_AMB : T_AMB + 1]
    ocv0 = (
        base_v
        + base_slope * (s - s_lo)
        + jax.nn.relu(s - const["hinge_at"]) @ const["hinge_c"][:, None]
    )
    v0 = (ocv0 - v0_mu) / v0_sd
    t0 = (t_amb - t0_mu) / t0_sd
    # Voltage after t=0 into [V_MIN, V_MAX] (normalized); V(0) and T(0) are
    # the anchors; everything else is the network's.
    v = raw[:, 1:g]
    v = const["v_hi"] - jax.nn.relu(const["v_hi"] - v)
    v = const["v_lo"] + jax.nn.relu(v - const["v_lo"])
    return jnp.concatenate([v0, v, t0, raw[:, g + 1 :]], axis=1)


batch = 400  # the validator binds the traced batch to the registered default
example, names = [], []
for i, (a, b) in enumerate(itertools.pairwise(sizes)):
    example += [jnp.ones((a, b), jnp.float32), jnp.zeros((b,), jnp.float32)]
    names += [f"params/{2 * i}", f"params/{2 * i + 1}"]
example.append(jnp.ones((batch, n_in), jnp.float32))
names.append("inputs/features")
registry = allowlist.load()
_, lowered, _ = through_bprime(
    forward,
    tuple(example),
    role="forward",
    allowlist=registry,
    input_names=names,
    max_bytes=intake.BOUNDS["document_bytes"],
)
spec = []
for i in range(len(sizes) - 1):
    spec.append(
        {
            "input": f"params/{2 * i}",
            "initializer": "he_normal",
            "fan_in_axes": [0],
            "fan_out_axes": [1],
        }
    )
    spec.append(
        {
            "input": f"params/{2 * i + 1}",
            "initializer": "zeros",
            "fan_in_axes": [],
            "fan_out_axes": [],
        }
    )
init_spec = {
    "schema": initializers.SCHEMA,
    "graph": graph.digest(lowered),
    "parameters": spec,
}
manifest, files = submission.build(
    challenge=challenge.CHALLENGE.challenge_id,
    interface=interface.digest(),
    allowlist=registry,
    forward=lowered,
    init_spec=init_spec,
)
raw_manifest = submission.canonical(manifest)
graph_digest = submission.digest(manifest)
recipe = recipe_for(graph_digest)
direct_graph.build_validated_graph(
    recipe,
    raw_manifest,
    files,
    max_bytes=intake.BOUNDS["submission_bytes"],
    train_cases=challenge.TRAIN_V1_CASES,
)
(out / "graph-manifest.json").write_bytes(raw_manifest)
(out / "files").mkdir()
for name, data in sorted(files.items()):
    (out / "files" / name.replace(":", "_")).write_bytes(data)
(out / "recipe.json").write_bytes(
    json.dumps(recipe.to_dict(), sort_keys=True, separators=(",", ":")).encode()
)
summary = {
    "graph_digest": graph_digest,
    "recipe_digest": recipe.digest,
    "allowlist": registry.version if hasattr(registry, "version") else None,
    "ocv_hinges": len(hinge_at),
    "ocv_budget_v": OCV_BUDGET_V,
    "ocv_max_error_vs_judge_interp_v": ocv_err,
    "graph_bytes": len(raw_manifest) + sum(len(d) for d in files.values()),
    "files_sha256": {
        n: "sha256:" + hashlib.sha256(d).hexdigest() for n, d in sorted(files.items())
    },
}
(out / "BUILD.json").write_text(
    json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(summary, sort_keys=True))
