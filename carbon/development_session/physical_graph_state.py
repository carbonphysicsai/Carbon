"""Inert graph state with Carbon's target decoder, for the F08/F02 graph adapter.

`bundle_graph_state` freezes a forward graph and its parameters. A graph the
F08/F02 adapter trained predicts standardised targets, so its state also binds
the per-column decoder (mean and deviation of the selected TRAIN rows), and
the separate inference worker applies `prediction * sd + mean`. The decoder is
numeric state, never code. `bundle_graph_state.load` refuses these bytes (an
extra header field and arrays), so the plain inference program cannot read a
decoded state as an undecoded one. This grants no judge admission.
"""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

from .bundle_graph_state import (
    GRAPH_SCHEMA,
    _canonical,
    _checked_graph,
    _digest,
    _limits,
    _preflight_npy,
    _source_header,
)
from .construction_recipe import ConstructionRecipe, RecipeRefused

DECODER_SCHEMA = "carbon.development.graph-target-decoder.v1"
__all__ = ("DECODER_SCHEMA", "GRAPH_SCHEMA", "freeze", "load")


def _decoder(mu, sd, width: int):
    mu, sd = np.asarray(mu), np.asarray(sd)
    if (
        type(width) is not int
        or width < 1
        or any(
            value.dtype != np.float32
            or value.shape != (width,)
            or not np.isfinite(value).all()
            for value in (mu, sd)
        )
        or not np.all(sd > 0)
    ):
        raise RecipeRefused("decoded_graph_state_decoder_invalid")
    return mu, sd


def _header(recipe, raw_graph, allowlist, count, width):
    return {
        **_source_header(recipe),
        "recipe_digest": recipe.digest,
        "train_digest": recipe.to_dict()["challenge"]["train_digest"],
        "interface_digest": recipe.to_dict()["challenge"]["interface_digest"],
        "graph_digest": _digest(raw_graph),
        "allowlist_digest": allowlist.digest,
        "parameter_count": count,
        "decoder": {"schema": DECODER_SCHEMA, "width": width},
    }


def _width(doc: dict) -> int:
    """The one output's per-case width, from the checked graph's declarations."""
    entry = doc["graphs"][doc["entry"]]
    values = {item["value"]: item for item in (*entry["inputs"], *entry["constants"])}
    for node in entry["nodes"]:
        for out in node["out"]:
            values[out["value"]] = out
    outputs = entry["outputs"]
    shape = values[outputs[0]]["shape"] if len(outputs) == 1 else None
    if type(shape) is not list or len(shape) != 2 or type(shape[1]) is not int:
        raise RecipeRefused("decoded_graph_state_output_invalid")
    return shape[1]


def freeze(
    recipe: ConstructionRecipe, doc: dict, parameters: list, allowlist, mu, sd
) -> bytes:
    """Freeze a validated forward graph, its parameters and its decoder."""
    # `bundle_graph_state`'s bounds for this allowlist: the fixed ones through
    # v6; under v7 (no model-size caps) no state ceiling or array count of
    # its own, and the graph document at the containment bound.
    state_bytes, _, parameter_limit = _limits(allowlist)
    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
        or type(parameters) is not list
        or (parameter_limit is not None and len(parameters) > parameter_limit)
    ):
        raise RecipeRefused("bundle_state_source_invalid")
    raw_graph = _checked_graph(doc, allowlist)
    width = _width(doc)
    mu, sd = _decoder(mu, sd, width)
    inputs = doc["graphs"][doc["entry"]]["inputs"]
    param_inputs = [i for i in inputs if i["name"].startswith("params/")]
    if [i["name"] for i in param_inputs] != [
        f"params/{i}" for i in range(len(parameters))
    ]:
        raise RecipeRefused("bundle_state_parameter_count_invalid")
    arrays = {}
    for index, (entry, value) in enumerate(zip(param_inputs, parameters)):
        array = np.asarray(value)
        if (
            array.dtype.kind not in "fiuc"
            or not np.isfinite(array).all()
            or str(array.dtype) != entry["dtype"]
            or list(array.shape) != entry["shape"]
        ):
            raise RecipeRefused("bundle_state_parameter_invalid")
        arrays[f"parameter{index:04d}"] = array
    header = _header(recipe, raw_graph, allowlist, len(parameters), width)
    arrays["__header__"] = np.frombuffer(_canonical(header), dtype=np.uint8)
    arrays["graph"] = np.frombuffer(raw_graph, dtype=np.uint8)
    arrays["decoder_mu"] = mu
    arrays["decoder_sd"] = sd
    out = io.BytesIO()
    np.savez(out, **arrays)
    body = out.getvalue()
    if state_bytes is not None and len(body) > state_bytes:
        raise RecipeRefused("bundle_state_oversized")
    return body


def load(raw: bytes, recipe: ConstructionRecipe, allowlist):
    """Recheck every inert byte; returns (graph, parameters, mean, deviation)."""
    if type(allowlist) is not allowlist_module.Allowlist:
        raise RecipeRefused("bundle_state_invalid")
    state_bytes, graph_bytes, parameter_limit = _limits(allowlist)
    if (
        type(raw) is not bytes
        or not 0 < len(raw)
        or (state_bytes is not None and len(raw) > state_bytes)
        or type(recipe) is not ConstructionRecipe
    ):
        raise RecipeRefused("bundle_state_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            names = [entry.filename for entry in members]
            if (
                len(names) != len(set(names))
                or (parameter_limit is not None and len(names) > parameter_limit + 4)
                or any(not name.endswith(".npy") for name in names)
                or any(entry.compress_type != zipfile.ZIP_STORED for entry in members)
                or any(entry.flag_bits & 1 for entry in members)
                or (
                    state_bytes is not None
                    and sum(entry.file_size for entry in members) > state_bytes
                )
            ):
                raise RecipeRefused("bundle_state_archive_invalid")
            descriptors = {
                member.filename: _preflight_npy(archive, member) for member in members
            }
            for name, limit in (
                ("__header__.npy", 65536),
                ("graph.npy", graph_bytes),
            ):
                shape, dtype = descriptors.get(name, (None, None))
                if (
                    dtype != np.dtype("uint8")
                    or shape is None
                    or len(shape) != 1
                    or not 0 < shape[0] <= limit
                ):
                    raise RecipeRefused("bundle_state_archive_invalid")
        with np.load(io.BytesIO(raw), allow_pickle=False) as state:
            if "__header__" not in state or "graph" not in state:
                raise RecipeRefused("bundle_state_archive_invalid")
            header_array, graph_array = state["__header__"], state["graph"]
            if header_array.dtype != np.uint8 or graph_array.dtype != np.uint8:
                raise RecipeRefused("bundle_state_archive_invalid")
            header = json.loads(header_array.tobytes())
            count = header.get("parameter_count") if type(header) is dict else None
            if (
                type(count) is not int
                or count < 0
                or (parameter_limit is not None and count > parameter_limit)
            ):
                raise RecipeRefused("bundle_state_header_invalid")
            expected = {"__header__", "graph", "decoder_mu", "decoder_sd"} | {
                f"parameter{i:04d}" for i in range(count)
            }
            if (
                set(state.files) != expected
                or {name.removesuffix(".npy") for name in names} != expected
            ):
                raise RecipeRefused("bundle_state_archive_invalid")
            graph_raw = graph_array.tobytes()
            if not 0 < len(graph_raw) <= graph_bytes:
                raise RecipeRefused("bundle_graph_oversized")
            doc = graph.parse(graph_raw, max_bytes=graph_bytes)
            _checked_graph(doc, allowlist)
            width = _width(doc)
            if header != _header(recipe, graph_raw, allowlist, count, width):
                raise RecipeRefused("bundle_state_header_invalid")
            inputs = doc["graphs"][doc["entry"]]["inputs"]
            param_inputs = [i for i in inputs if i["name"].startswith("params/")]
            if [i["name"] for i in param_inputs] != [
                f"params/{i}" for i in range(count)
            ]:
                raise RecipeRefused("bundle_state_parameter_count_invalid")
            parameters = []
            for index, entry in enumerate(param_inputs):
                array = state[f"parameter{index:04d}"]
                if (
                    array.dtype.kind not in "fiuc"
                    or not np.isfinite(array).all()
                    or str(array.dtype) != entry["dtype"]
                    or list(array.shape) != entry["shape"]
                ):
                    raise RecipeRefused("bundle_state_parameter_invalid")
                parameters.append(array.copy())
            mu, sd = _decoder(state["decoder_mu"], state["decoder_sd"], width)
            return doc, parameters, mu.copy(), sd.copy()
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused("bundle_state_archive_invalid") from None
