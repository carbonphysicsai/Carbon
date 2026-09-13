"""Independent NumPy adapter for the pinned Transolver attention equations.

This is a new Carbon test adapter, not copied upstream code.  It implements the
slice/attend/deslice equations from THUML/Transolver commit
75e0f67643806a81cd1d3f6adc88dd8c02416fe7 under the bundled MIT notice.
"""

from __future__ import annotations

import math

import numpy as np


def _dense(parameters: dict[str, np.ndarray], value: np.ndarray) -> np.ndarray:
    result = value @ parameters["w"]
    return result + parameters["b"] if "b" in parameters else result


def _softmax(value: np.ndarray, axis: int) -> np.ndarray:
    shifted = value - np.max(value, axis=axis, keepdims=True)
    exponential = np.exp(shifted)
    return exponential / np.sum(exponential, axis=axis, keepdims=True)


def physics_attention_reference(
    parameters: dict[str, object], value: np.ndarray, heads: int
) -> np.ndarray:
    batch, points, channels = value.shape
    dimension = channels // heads

    def split(array: np.ndarray) -> np.ndarray:
        return array.reshape(batch, points, heads, dimension).transpose(0, 2, 1, 3)

    features = split(_dense(parameters["project_f"], value))
    projected = split(_dense(parameters["project_x"], value))
    raw = np.asarray(parameters["raw_temperature"])
    temperature = np.log1p(np.exp(raw))[None, :, None, None] + 1e-6
    assignment = _softmax(_dense(parameters["slice"], projected) / temperature, -1)
    tokens = np.einsum("bhnd,bhnm->bhmd", features, assignment) / (
        assignment.sum(2)[..., None] + 1e-5
    )
    query, key, payload = (_dense(parameters[name], tokens) for name in ("q", "k", "v"))
    attention = _softmax(
        np.einsum("bhmd,bhkd->bhmk", query, key) / math.sqrt(dimension), -1
    )
    result = np.einsum("bhmk,bhkd->bhmd", attention, payload)
    result = np.einsum("bhmd,bhnm->bhnd", result, assignment)
    result = result.transpose(0, 2, 1, 3).reshape(batch, points, channels)
    return _dense(parameters["out"], result)


__all__ = ["physics_attention_reference"]
