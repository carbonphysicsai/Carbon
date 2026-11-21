"""Inert ensemble graph state of a SELF-TRUST version (SELF_TRUST DESIGN_v2 section 8, H3d-2a).

`physical_graph_state_v2` freezes an ensemble whose graph, decoder and combination all share ONE output width. A trust
candidate's graph returns `W + k` columns (the W physics columns and k trust columns, see `carbon.level4.trust_head`), while
Carbon's target decoder and the per-output combination only exist for the W physics columns: the trust columns are not
standardised targets and are not combined (the ONE trust member, member 0, owns them). This state records exactly that:

* the graph's output is `W + k` wide, `decoder_mu` / `decoder_sd` and `combine` are `W` wide;
* the header names the trust block: `{"trust": {"member": 0, "width": k}}`, and carries its OWN schema string
  (`TRUST_STATE_SCHEMA`), so `physical_graph_state_v2.load` (header equality) and every older loader refuse these bytes, and
  this loader refuses every older state: no program can read one kind as the other;
* `load` returns the same 5-tuple as v2's (graph, members, mean, deviation, combination), so the trust inference program only
  swaps the loader import.

Everything is numeric state, never code. The checks are v2's, copied rather than imported (v2's module is staged into every
v2 inference container, so editing it would move every other version's staged bytes); only its small pure helpers are reused.
This grants no judge admission.
"""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

from .bundle_graph_state import (
    _canonical,
    _checked_graph,
    _limits,
    _preflight_npy,
)
from .construction_recipe import ConstructionRecipe, RecipeRefused
from .physical_graph_state import DECODER_SCHEMA, _width
from .physical_graph_state_v2 import (
    _checked_parameters,
    _combine,
    _decoder,
    _header as _v2_header,
    _name,
    _param_inputs,
)

TRUST_STATE_SCHEMA = "carbon.development.graph-ensemble-trust-state.v1"
#: The member that owns the trust columns (door-code 04:34:35Z: exactly ONE named member, combine weight 1).
TRUST_MEMBER = 0
__all__ = ("DECODER_SCHEMA", "TRUST_MEMBER", "TRUST_STATE_SCHEMA", "freeze", "load", "validate")


def _trust_width(value) -> int:
    if type(value) is not int or value < 1:
        raise RecipeRefused("trust_graph_state_width_invalid")
    return value


def _physics_width(doc: dict, trust_width: int) -> int:
    """W = the graph's output width less the trust block; at least one physics column must remain."""
    width = _width(doc) - trust_width
    if width < 1:
        raise RecipeRefused("trust_graph_state_width_invalid")
    return width


def _header(recipe, raw_graph, allowlist, members, count, width, trust_width):
    return {
        **_v2_header(recipe, raw_graph, allowlist, members, count, width),
        "schema": TRUST_STATE_SCHEMA,
        "trust": {"member": TRUST_MEMBER, "width": trust_width},
    }


def freeze(
    recipe: ConstructionRecipe,
    doc: dict,
    members: list,
    allowlist,
    mu,
    sd,
    combine,
    *,
    trust_width: int,
) -> bytes:
    """Freeze a validated trust forward graph (output W + k), every member's parameters, the W-wide decoder and the
    W-wide per-output combination."""
    state_bytes, _, parameter_limit = _limits(allowlist)
    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
        or type(members) is not list
        or not members
        or any(type(member) is not list for member in members)
    ):
        raise RecipeRefused("bundle_state_source_invalid")
    trust_width = _trust_width(trust_width)
    raw_graph = _checked_graph(doc, allowlist)
    width = _physics_width(doc, trust_width)
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
    header = _header(recipe, raw_graph, allowlist, len(members), count, width, trust_width)
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


def _load(raw: bytes, recipe: ConstructionRecipe, allowlist, *, materialize):
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
            trust = header.get("trust")
            if (
                type(members) is not int
                or members < 1
                or type(count) is not int
                or count < 0
                or (parameter_limit is not None and members * count > parameter_limit)
                or type(trust) is not dict
                or set(trust) != {"member", "width"}
                or trust["member"] != TRUST_MEMBER
                or type(trust["width"]) is not int
                or trust["width"] < 1
            ):
                raise RecipeRefused("bundle_state_header_invalid")
            trust_width = trust["width"]
            expected = {"__header__", "graph", "decoder_mu", "decoder_sd", "combine"}
            if count:
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
            width = _physics_width(doc, trust_width)
            if header != _header(
                recipe, graph_raw, allowlist, members, count, width, trust_width
            ):
                raise RecipeRefused("bundle_state_header_invalid")
            entries = _param_inputs(doc)
            if [i["name"] for i in entries] != [f"params/{i}" for i in range(count)]:
                raise RecipeRefused("bundle_state_parameter_count_invalid")
            if materialize:
                loaded = [
                    [
                        array.copy()
                        for array in _checked_parameters(
                            entries, [state[_name(m, i)] for i in range(count)]
                        )
                    ]
                    for m in range(members)
                ]
            elif count:
                for member in range(members):
                    _checked_parameters(
                        entries, [state[_name(member, i)] for i in range(count)]
                    )
            mu, sd = _decoder(state["decoder_mu"], state["decoder_sd"], width)
            combine = _combine(state["combine"], members, width, mu.dtype)
            if not materialize:
                return None
            return doc, loaded, mu.copy(), sd.copy(), combine.copy()
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused("bundle_state_archive_invalid") from None


def load(raw: bytes, recipe: ConstructionRecipe, allowlist):
    """Recheck every inert byte; returns (graph, members, mean, deviation, combination) exactly as v2's `load`, the graph's
    output `W + k` wide and the decoder and combination `W` wide."""
    return _load(raw, recipe, allowlist, materialize=True)


def validate(raw: bytes, recipe: ConstructionRecipe, allowlist) -> None:
    """Apply exactly load's checks without retaining parameter/member copies (custody needs validation, not a model)."""
    _load(raw, recipe, allowlist, materialize=False)
