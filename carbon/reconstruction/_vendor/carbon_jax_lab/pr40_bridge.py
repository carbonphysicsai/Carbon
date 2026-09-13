"""Array-only bridge for PR40's Flax parameter layout; no Flax import required.

Forward-equation scope: dense real 1D FNO, postactivation, grid embedding,
linear/soft-gating skips. Source revision in docs/SOURCES.md.
Initialization/training/checkpoint parity with the unavailable package is NOT claimed.
"""

import jax.numpy as jnp


def from_flax_params(variables, depth):
    p = variables.get("params", variables)

    def convert_mlp(q):
        layers = []
        i = 0
        while f"weight_{i}" in q:
            layers.append(
                {"w": jnp.asarray(q[f"weight_{i}"]).T, "b": jnp.asarray(q[f"bias_{i}"])}
            )
            i += 1
        if not layers:
            raise ValueError("empty PR40 MLP")
        return tuple(layers)

    blocks = []
    q = p["fno_blocks"]
    for i in range(depth):
        spec = q[f"convs_{i}"]
        blocks.append(
            {
                "spectral": {
                    "real": jnp.asarray(spec["weight_real"]),
                    "imag": jnp.asarray(spec["weight_imag"]),
                    "bias": jnp.asarray(spec["bias"]),
                },
                "skip": {"w": jnp.asarray(q[f"fno_skip_weight_{i}"]).T},
                "gate": jnp.asarray(q[f"channel_mlp_skip_weight_{i}"]),
                "mlp": convert_mlp(q[f"channel_mlp_{i}"]),
            }
        )
    return {
        "lift": convert_mlp(p["lifting"]),
        "blocks": tuple(blocks),
        "projection": convert_mlp(p["projection"]),
    }


def to_flax_params(p):
    def convert_mlp(q):
        result = {}
        for i, v in enumerate(q):
            result.update({f"weight_{i}": v["w"].T, f"bias_{i}": v["b"]})
        return result

    q = {}
    for i, b in enumerate(p["blocks"]):
        q[f"convs_{i}"] = {
            "weight_real": b["spectral"]["real"],
            "weight_imag": b["spectral"]["imag"],
            "bias": b["spectral"]["bias"],
        }
        q[f"fno_skip_weight_{i}"] = b["skip"]["w"].T
        q[f"channel_mlp_skip_weight_{i}"] = b["gate"]
        q[f"channel_mlp_{i}"] = convert_mlp(b["mlp"])
    return {
        "params": {
            "lifting": convert_mlp(p["lift"]),
            "fno_blocks": q,
            "projection": convert_mlp(p["projection"]),
        }
    }
