"""Inert ensemble graph state for graph route v2 (`physical_graph_adapter_v2`).

`physical_graph_state` freezes one graph, its parameters and Carbon's target
decoder. A v2 build trains an ensemble: several parameter sets of the same
validated graph, each on its own output subset, combined per output. Its
state binds the graph once, every member's parameters, the decoder and the
per-output combination (members x outputs, each column summing to one), and
the v2 inference program applies `sum_m combine[m] * prediction_m`, then the
decoder. Everything is numeric state, never code. `physical_graph_state.load`
and `bundle_graph_state.load` refuse these bytes (a different header schema
and arrays), so no older program can read an ensemble as one graph. This
grants no judge admission.
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
from .physical_graph_state import DECODER_SCHEMA, _width

ENSEMBLE_SCHEMA = "carbon.development.graph-ensemble-state.v1"
__all__ = ("DECODER_SCHEMA", "ENSEMBLE_SCHEMA", "GRAPH_SCHEMA", "freeze", "load")


#: The interface dtypes a graph route v2 output, decoder and combination take.
DTYPES = ("float32", "float64")


def _decoder(mu, sd, width: int):
    """The decoder in one of `DTYPES`, both arrays the same dtype."""
    mu, sd = np.asarray(mu), np.asarray(sd)
    if (
        type(width) is not int
        or width < 1
        or str(mu.dtype) not in DTYPES
        or sd.dtype != mu.dtype
        or any(
            value.shape != (width,) or not np.isfinite(value).all()
            for value in (mu, sd)
        )
        or not np.all(sd > 0)
    ):
        raise RecipeRefused("decoded_graph_state_decoder_invalid")
    return mu, sd


def _combine(value, members: int, width: int, dtype) -> np.ndarray:
    combine = np.asarray(value)
    if (
        combine.dtype != dtype
        or combine.shape != (members, width)
        or not np.isfinite(combine).all()
        or np.any(combine < 0)
        or not np.allclose(combine.sum(axis=0), 1.0, rtol=0, atol=1e-5)
    ):
        raise RecipeRefused("ensemble_graph_state_combine_invalid")
    return combine


def _header(recipe, raw_graph, allowlist, members, count, width):
    return {
        **_source_header(recipe),
        "schema": ENSEMBLE_SCHEMA,
        "recipe_digest": recipe.digest,
        "train_digest": recipe.to_dict()["challenge"]["train_digest"],
        "interface_digest": recipe.to_dict()["challenge"]["interface_digest"],
        "graph_digest": _digest(raw_graph),
        "allowlist_digest": allowlist.digest,
        "members": members,
        "parameter_count": count,
        "decoder": {"schema": DECODER_SCHEMA, "width": width},
    }


def _name(member: int, index: int) -> str:
    return f"member{member:06d}_parameter{index:04d}"


def _param_inputs(doc: dict) -> list:
    inputs = doc["graphs"][doc["entry"]]["inputs"]
    return [i for i in inputs if i["name"].startswith("params/")]


def _checked_parameters(entries: list, values) -> list:
    if len(values) != len(entries):
        raise RecipeRefused("bundle_state_parameter_count_invalid")
    checked = []
    for entry, value in zip(entries, values):
        array = np.asarray(value)
        if (
            array.dtype.kind not in "fiuc"
            or not np.isfinite(array).all()
            or str(array.dtype) != entry["dtype"]
            or list(array.shape) != entry["shape"]
        ):
            raise RecipeRefused("bundle_state_parameter_invalid")
        checked.append(array)
    return checked


def freeze(
    recipe: ConstructionRecipe,
    doc: dict,
    members: list,
    allowlist,
    mu,
    sd,
    combine,
) -> bytes:
    """Freeze a validated forward graph, every member's parameters, the
    decoder and the per-output combination."""
    state_bytes, _, parameter_limit = _limits(allowlist)
    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
        or type(members) is not list
        or not members
        or any(type(member) is not list for member in members)
    ):
        raise RecipeRefused("bundle_state_source_invalid")
    raw_graph = _checked_graph(doc, allowlist)
    width = _width(doc)
    mu, sd = _decoder(mu, sd, width)
    combine = _combine(combine, len(members), width, mu.dtype)
    entries = _param_inputs(doc)
    if [i["name"] for i in entries] != [f"params/{i}" for i in range(len(entries))]:
        raise RecipeRefused("bundle_state_parameter_count_invalid")
    count = len(entries)
    if parameter_limit is not None and count * len(members) > parameter_limit:
        raise RecipeRefused("bundle_state_source_invalid")
    arrays = {}
    for member, values in enumerate(members):
        for index, array in enumerate(_checked_parameters(entries, values)):
            arrays[_name(member, index)] = array
    header = _header(recipe, raw_graph, allowlist, len(members), count, width)
    arrays["__header__"] = np.frombuffer(_canonical(header), dtype=np.uint8)
    arrays["graph"] = np.frombuffer(raw_graph, dtype=np.uint8)
    arrays["decoder_mu"] = mu
    arrays["decoder_sd"] = sd
    arrays["combine"] = combine
    out = io.BytesIO()
    np.savez(out, **arrays)
    body = out.getvalue()
    if state_bytes is not None and len(body) > state_bytes:
        raise RecipeRefused("bundle_state_oversized")
    return body


def load(raw: bytes, recipe: ConstructionRecipe, allowlist):
    """Recheck every inert byte; returns (graph, members, mean, deviation,
    combination), `members` one parameter list per member."""
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
            entries_ = archive.infolist()
            names = [entry.filename for entry in entries_]
            if (
                len(names) != len(set(names))
                or any(not name.endswith(".npy") for name in names)
                or any(entry.compress_type != zipfile.ZIP_STORED for entry in entries_)
                or any(entry.flag_bits & 1 for entry in entries_)
                or (
                    state_bytes is not None
                    and sum(entry.file_size for entry in entries_) > state_bytes
                )
            ):
                raise RecipeRefused("bundle_state_archive_invalid")
            descriptors = {
                entry.filename: _preflight_npy(archive, entry) for entry in entries_
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
            if type(header) is not dict:
                raise RecipeRefused("bundle_state_header_invalid")
            members, count = header.get("members"), header.get("parameter_count")
            if (
                type(members) is not int
                or members < 1
                or type(count) is not int
                or count < 0
                or (parameter_limit is not None and members * count > parameter_limit)
            ):
                raise RecipeRefused("bundle_state_header_invalid")
            expected = {"__header__", "graph", "decoder_mu", "decoder_sd", "combine"}
            expected |= {_name(m, i) for m in range(members) for i in range(count)}
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
            if header != _header(recipe, graph_raw, allowlist, members, count, width):
                raise RecipeRefused("bundle_state_header_invalid")
            entries = _param_inputs(doc)
            if [i["name"] for i in entries] != [f"params/{i}" for i in range(count)]:
                raise RecipeRefused("bundle_state_parameter_count_invalid")
            loaded = [
                [
                    array.copy()
                    for array in _checked_parameters(
                        entries, [state[_name(m, i)] for i in range(count)]
                    )
                ]
                for m in range(members)
            ]
            mu, sd = _decoder(state["decoder_mu"], state["decoder_sd"], width)
            combine = _combine(state["combine"], members, width, mu.dtype)
            return doc, loaded, mu.copy(), sd.copy(), combine.copy()
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused("bundle_state_archive_invalid") from None
