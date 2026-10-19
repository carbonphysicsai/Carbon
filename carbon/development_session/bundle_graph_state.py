"""Inert graph and numeric state emitted by an isolated library build.

The construction source never enters this representation. Both the build and
the separate inference worker call these checks; the controller only copies
bounded bytes and verifies their digest. This grants no judge admission.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import re
import struct
import zipfile

import numpy as np

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

from .construction_recipe import ConstructionRecipe, RecipeRefused


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


SCHEMA = "carbon.development.bundle-graph-state.v1"
GRAPH_SCHEMA = "carbon.development.graph-source-state.v1"
MAX_BYTES = 64 * 1024**2
MAX_GRAPH_BYTES = 1024**2
MAX_PARAMETERS = 4096
_NPY_DTYPE = re.compile(r"[<>=|]?[fiuc][0-9]{1,2}")


def _preflight_npy(archive: zipfile.ZipFile, member: zipfile.ZipInfo):
    """Check a stored numeric member's exact payload before NumPy loads it."""
    with archive.open(member) as stream:
        if stream.read(6) != b"\x93NUMPY":
            raise RecipeRefused("bundle_state_archive_invalid")
        version = stream.read(2)
        if version == b"\x01\x00":
            width = 2
            encoding = "latin1"
        elif version == b"\x02\x00":
            width = 4
            encoding = "latin1"
        elif version == b"\x03\x00":
            width = 4
            encoding = "utf-8"
        else:
            raise RecipeRefused("bundle_state_archive_invalid")
        size = stream.read(width)
        if len(size) != width:
            raise RecipeRefused("bundle_state_archive_invalid")
        header_size = struct.unpack("<H" if width == 2 else "<I", size)[0]
        if not 1 <= header_size <= 4096:
            raise RecipeRefused("bundle_state_archive_invalid")
        header_raw = stream.read(header_size)
        if len(header_raw) != header_size:
            raise RecipeRefused("bundle_state_archive_invalid")
        try:
            header = ast.literal_eval(header_raw.decode(encoding).strip())
        except (RecursionError, SyntaxError, ValueError, UnicodeError):
            raise RecipeRefused("bundle_state_archive_invalid") from None
        if (
            type(header) is not dict
            or set(header) != {"descr", "fortran_order", "shape"}
            or type(header["descr"]) is not str
            or _NPY_DTYPE.fullmatch(header["descr"]) is None
            or type(header["fortran_order"]) is not bool
            or type(header["shape"]) is not tuple
            or len(header["shape"]) > 32
            or any(
                type(dim) is not int or not 0 <= dim <= MAX_BYTES
                for dim in header["shape"]
            )
        ):
            raise RecipeRefused("bundle_state_archive_invalid")
        try:
            dtype = np.dtype(header["descr"])
        except (TypeError, ValueError):
            raise RecipeRefused("bundle_state_archive_invalid") from None
        payload = math.prod(header["shape"]) * dtype.itemsize
        if dtype.kind not in "fiuc" or stream.tell() + payload != member.file_size:
            raise RecipeRefused("bundle_state_archive_invalid")
        return header["shape"], dtype


def _source_header(recipe: ConstructionRecipe) -> dict:
    """Keep historical bundle headers exact; bind new graph state separately."""
    source = recipe.to_dict()["source"]
    if source["kind"] == "bundle":
        return {
            "schema": SCHEMA,
            "bundle_digest": source["bundle_ref"]["bundle_digest"],
        }
    if source["kind"] == "graph":
        return {
            "schema": GRAPH_SCHEMA,
            "submission_digest": source["submission_digest"],
        }
    raise RecipeRefused("bundle_state_source_invalid")


def _checked_graph(doc: dict, allowlist) -> bytes:
    if type(doc) is not dict or type(allowlist) is not allowlist_module.Allowlist:
        raise RecipeRefused("bundle_graph_invalid")
    raw = graph.dumps(doc)
    if not 0 < len(raw) <= MAX_GRAPH_BYTES:
        raise RecipeRefused("bundle_graph_oversized")
    graph.check_structure(doc)
    allowlist.check(doc)
    if any(
        verdict != "pass"
        for verdict in allowlist_module.check_caps(graph.measure(doc)).values()
    ):
        raise RecipeRefused("bundle_graph_caps_refused")
    return raw


def freeze(recipe: ConstructionRecipe, doc: dict, parameters: list, allowlist) -> bytes:
    """Freeze a validated forward graph and numeric arrays, never Python code."""
    if (
        type(recipe) is not ConstructionRecipe
        or type(parameters) is not list
        or len(parameters) > MAX_PARAMETERS
    ):
        raise RecipeRefused("bundle_state_source_invalid")
    raw_graph = _checked_graph(doc, allowlist)
    expected_inputs = doc["graphs"][doc["entry"]]["inputs"]
    param_inputs = [i for i in expected_inputs if i["name"].startswith("params/")]
    if len(param_inputs) != len(parameters) or [i["name"] for i in param_inputs] != [
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
    header = {
        **_source_header(recipe),
        "recipe_digest": recipe.digest,
        "train_digest": recipe.to_dict()["challenge"]["train_digest"],
        "interface_digest": recipe.to_dict()["challenge"]["interface_digest"],
        "graph_digest": _digest(raw_graph),
        "allowlist_digest": allowlist.digest,
        "parameter_count": len(parameters),
    }
    arrays["__header__"] = np.frombuffer(_canonical(header), dtype=np.uint8)
    arrays["graph"] = np.frombuffer(raw_graph, dtype=np.uint8)
    out = io.BytesIO()
    np.savez(out, **arrays)
    body = out.getvalue()
    if len(body) > MAX_BYTES:
        raise RecipeRefused("bundle_state_oversized")
    return body


def load(raw: bytes, recipe: ConstructionRecipe, allowlist):
    """Recheck all inert bytes inside the separate inference worker."""
    if (
        type(raw) is not bytes
        or not 0 < len(raw) <= MAX_BYTES
        or type(recipe) is not ConstructionRecipe
        or type(allowlist) is not allowlist_module.Allowlist
    ):
        raise RecipeRefused("bundle_state_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            names = [entry.filename for entry in members]
            if (
                len(names) != len(set(names))
                or len(names) > MAX_PARAMETERS + 2
                or any(not name.endswith(".npy") for name in names)
                or any(entry.compress_type != zipfile.ZIP_STORED for entry in members)
                or any(entry.flag_bits & 1 for entry in members)
                or sum(entry.file_size for entry in members) > MAX_BYTES
            ):
                raise RecipeRefused("bundle_state_archive_invalid")
            descriptors = {
                member.filename: _preflight_npy(archive, member) for member in members
            }
            for name, limit in (
                ("__header__.npy", 65536),
                ("graph.npy", MAX_GRAPH_BYTES),
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
            count = header.get("parameter_count")
            if type(count) is not int or not 0 <= count <= MAX_PARAMETERS:
                raise RecipeRefused("bundle_state_header_invalid")
            expected = {"__header__", "graph"} | {
                f"parameter{i:04d}" for i in range(count)
            }
            if (
                set(state.files) != expected
                or {name.removesuffix(".npy") for name in names} != expected
            ):
                raise RecipeRefused("bundle_state_archive_invalid")
            graph_raw = graph_array.tobytes()
            if not 0 < len(graph_raw) <= MAX_GRAPH_BYTES:
                raise RecipeRefused("bundle_graph_oversized")
            if header != {
                **_source_header(recipe),
                "recipe_digest": recipe.digest,
                "train_digest": recipe.to_dict()["challenge"]["train_digest"],
                "interface_digest": recipe.to_dict()["challenge"]["interface_digest"],
                "graph_digest": _digest(graph_raw),
                "allowlist_digest": allowlist.digest,
                "parameter_count": count,
            }:
                raise RecipeRefused("bundle_state_header_invalid")
            doc = graph.parse(graph_raw, max_bytes=MAX_GRAPH_BYTES)
            _checked_graph(doc, allowlist)
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
            return doc, parameters
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused("bundle_state_archive_invalid") from None
