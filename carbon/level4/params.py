"""Parameter codecs: each allowlisted op declares its parameters by kind.

A kind turns a traced parameter into strict JSON (`encode`) and JSON back into
the exact value the op binds (`decode`). An unknown kind, a missing or extra
parameter, or a value outside its kind refuses: the allowlist bounds an op's
parameters as well as its name. `none` admits only null: sharding, layout,
precision overrides and accuracy hints stay at the framework default in v0.
"""

from __future__ import annotations

import math
import re

from .graph import DTYPES, GraphRefused

_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


def _ints(value):
    if type(value) not in (list, tuple) or not all(type(v) is int for v in value):
        raise GraphRefused("parameter_kind_mismatch")
    return [int(v) for v in value]


def _trace_ints(value):
    """Normalize JAX/NumPy integer scalars only at the trusted trace boundary.

    Public graph decoding still uses ``_ints`` and requires exact JSON ints.
    In particular, booleans, floats and arbitrary ``__int__`` objects are not
    accepted as dimensions or padding values.
    """
    import numpy as np

    if type(value) not in (list, tuple) or not all(
        type(v) is int or isinstance(v, np.integer) for v in value
    ):
        raise GraphRefused("parameter_kind_mismatch")
    return [int(v) for v in value]


def _int_pairs(value):
    if type(value) not in (list, tuple):
        raise GraphRefused("parameter_kind_mismatch")
    return [_ints(pair) for pair in value]


def _trace_int_pairs(value):
    if type(value) not in (list, tuple):
        raise GraphRefused("parameter_kind_mismatch")
    return [_trace_ints(pair) for pair in value]


_SCATTER_FIELDS = (
    "update_window_dims",
    "inserted_window_dims",
    "scatter_dims_to_operand_dims",
    "operand_batching_dims",
    "scatter_indices_batching_dims",
)


def _scatter_dims(value, *, traced):
    if traced:
        if type(value).__name__ != "ScatterDimensionNumbers" or not type(
            value
        ).__module__.startswith("jax."):
            raise GraphRefused("parameter_kind_mismatch")
        dims = {field: _trace_ints(getattr(value, field)) for field in _SCATTER_FIELDS}
    else:
        if type(value) is not dict or set(value) != set(_SCATTER_FIELDS):
            raise GraphRefused("parameter_kind_mismatch")
        dims = {field: _ints(value[field]) for field in _SCATTER_FIELDS}
    if any(n < 0 for values in dims.values() for n in values) or any(
        len(values) != len(set(values)) for values in dims.values()
    ):
        raise GraphRefused("parameter_kind_mismatch")
    if dims["update_window_dims"] != sorted(dims["update_window_dims"]):
        raise GraphRefused("parameter_kind_mismatch")
    if len(dims["operand_batching_dims"]) != len(dims["scatter_indices_batching_dims"]):
        raise GraphRefused("parameter_kind_mismatch")
    return dims


def _dtype_name(value):
    import numpy as np

    name = str(np.dtype(value))
    if name not in DTYPES:
        raise GraphRefused("dtype_not_allowed")
    return name


def _owned_single_device_sharding(value):
    """Erase only inert placement from a trusted one-device JAX trace.

    The graph is mathematical; the isolated worker owns its target device.
    A partition axis, multiple devices, remote placement, or host memory is
    not representable as the framework-default ``None`` parameter.
    """
    if value is None:
        return
    from jax.sharding import AbstractMesh, Mesh, NamedSharding

    if (
        type(value) is not NamedSharding
        or value.mesh.size != 1
        or not value.is_fully_replicated
        or any(axis is not None for axis in value.spec)
    ):
        raise GraphRefused("parameter_not_default")
    if type(value.mesh) is AbstractMesh:
        # JAX replaces a concrete one-device mesh with AbstractMesh in a
        # traced equation. It has no device_set/addressability to inspect.
        # One logical slot, no partition, and default memory carry no target.
        if value.memory_kind is not None:
            raise GraphRefused("parameter_not_default")
    elif type(value.mesh) is Mesh:
        if (
            len(value.device_set) != 1
            or not value.is_fully_addressable
            or value.memory_kind != "device"
        ):
            raise GraphRefused("parameter_not_default")
    else:
        raise GraphRefused("parameter_not_default")
    return


def _default_call_metadata(name, value):
    """Only inert defaults of a nested JAX call may be discarded.

    The interpreter executes nested graphs inline. These fields therefore
    cannot silently donate buffers, change placement or set compiler flags.
    """
    if name in ("inline", "keep_unused"):
        return value is False
    if name == "compiler_options_kvs":
        return value is None or (type(value) is tuple and not value)
    if name == "donated_invars":
        return type(value) is tuple and all(item is False for item in value)
    if name in ("in_layouts", "out_layouts", "in_shardings", "out_shardings"):
        return type(value) is tuple and all(
            item is None
            or (
                type(item).__name__ == "UnspecifiedValue"
                and type(item).__module__.startswith("jax.")
            )
            for item in value
        )
    if name == "ctx_mesh":
        return value is None or (
            type(value).__name__ in ("AbstractMesh", "Mesh")
            and type(value).__module__.startswith("jax.")
            and not value.axis_names
        )
    if name == "name":
        return type(value) is str and len(value) <= 128
    return False


def _encode(kind, value, lower_graph, name=None):
    if kind == "call_metadata":
        if not _default_call_metadata(name, value):
            raise GraphRefused("parameter_not_default")
        return None
    if kind == "custom_rule_dropped":
        return None
    if kind == "fill_value":
        # Strict JSON has no NaN: an out-of-bounds fill is null, "nan" or finite.
        if value is None:
            return None
        if type(value) is float and math.isnan(value):
            return "nan"
        if type(value) not in (int, float) or not math.isfinite(value):
            raise GraphRefused("parameter_kind_mismatch")
        return float(value)
    if kind == "none":
        if value is not None:
            raise GraphRefused("parameter_not_default")
        return None
    if kind == "owned_single_device_sharding":
        return _owned_single_device_sharding(value)
    if kind == "empty_tuple":
        if type(value) is not tuple or value:
            raise GraphRefused("parameter_not_default")
        return []
    if kind == "int":
        import numpy as np

        if type(value) is not int and not isinstance(value, np.integer):
            raise GraphRefused("parameter_kind_mismatch")
        return int(value)
    if kind == "bool":
        if type(value) is not bool:
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "int_tuple":
        return _trace_ints(value)
    if kind == "int_tuple_or_none":
        return None if value is None else _trace_ints(value)
    if kind == "int_pairs":
        return _trace_int_pairs(value)
    if kind == "dtype":
        return _dtype_name(value)
    if kind == "dtype_or_none":
        return None if value is None else _dtype_name(value)
    if kind == "dot_dimension_numbers":
        (lc, rc), (lb, rb) = value
        return [[_trace_ints(lc), _trace_ints(rc)], [_trace_ints(lb), _trace_ints(rb)]]
    if kind == "padding_config":
        triples = [_trace_ints(triple) for triple in value]
        if any(len(triple) != 3 for triple in triples):
            raise GraphRefused("parameter_kind_mismatch")
        return triples
    if kind == "conv_dimension_numbers":
        return [
            _trace_ints(value.lhs_spec),
            _trace_ints(value.rhs_spec),
            _trace_ints(value.out_spec),
        ]
    if kind == "gather_dimension_numbers":
        return {
            name: _trace_ints(getattr(value, name))
            for name in (
                "offset_dims",
                "collapsed_slice_dims",
                "start_index_map",
                "operand_batching_dims",
                "start_indices_batching_dims",
            )
        }
    if kind == "scatter_dimension_numbers":
        return _scatter_dims(value, traced=True)
    if kind == "gather_mode":
        return value.name
    if kind == "fft_type":
        return value.name
    if kind == "rounding_method":
        return value.name
    if kind == "precision":
        # None, or the (lhs, rhs) pair of matmul precisions JAX records.
        if value is None:
            return None
        if (
            type(value) is not tuple
            or len(value) != 2
            or any(type(v).__name__ != "Precision" for v in value)
        ):
            raise GraphRefused("parameter_not_default")
        return [v.name for v in value]
    if kind == "prng_impl":
        if str(value) != "fry":
            raise GraphRefused("prng_impl_not_allowed")
        return "threefry2x32"
    if kind == "graph":
        return {"graph": lower_graph(value)}
    if kind == "graph_or_none":
        return None if value is None else {"graph": lower_graph(value)}
    raise GraphRefused("parameter_kind_unknown")


def _decode(kind, value):
    if kind == "fill_value":
        if value is None or value == "nan":
            return None if value is None else float("nan")
        if type(value) not in (int, float):
            raise GraphRefused("parameter_kind_mismatch")
        return float(value)
    if kind in (
        "none",
        "graph_or_none",
        "call_metadata",
        "custom_rule_dropped",
        "owned_single_device_sharding",
    ):
        if value is not None:
            raise GraphRefused("parameter_not_default")
        return None
    if kind == "empty_tuple":
        if type(value) is not list or value:
            raise GraphRefused("parameter_not_default")
        return ()
    if kind == "name":
        # Membership is the allowlist's check; the kind bounds the string.
        if type(value) is not str or not _NAME.match(value):
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "int":
        if type(value) is not int:
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "bool":
        if type(value) is not bool:
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "int_tuple":
        return tuple(_ints(value))
    if kind == "int_tuple_or_none":
        return None if value is None else tuple(_ints(value))
    if kind == "int_pairs":
        return tuple(tuple(p) for p in _int_pairs(value))
    if kind in ("dtype", "dtype_or_none"):
        import numpy as np

        if value is None and kind == "dtype_or_none":
            return None
        if value not in DTYPES:
            raise GraphRefused("dtype_not_allowed")
        return np.dtype(value)
    if kind == "dot_dimension_numbers":
        if type(value) is not list or len(value) != 2:
            raise GraphRefused("parameter_kind_mismatch")
        (lc, rc), (lb, rb) = value
        return (
            (tuple(_ints(lc)), tuple(_ints(rc))),
            (tuple(_ints(lb)), tuple(_ints(rb))),
        )
    if kind == "padding_config":
        triples = [tuple(_ints(t)) for t in value]
        if any(len(t) != 3 for t in triples):
            raise GraphRefused("parameter_kind_mismatch")
        return tuple(triples)
    if kind == "conv_dimension_numbers":
        from jax.lax import ConvDimensionNumbers

        lhs, rhs, out = (tuple(_ints(v)) for v in value)
        return ConvDimensionNumbers(lhs, rhs, out)
    if kind == "gather_dimension_numbers":
        from jax.lax import GatherDimensionNumbers

        if type(value) is not dict:
            raise GraphRefused("parameter_kind_mismatch")
        return GatherDimensionNumbers(**{k: tuple(_ints(v)) for k, v in value.items()})
    if kind == "scatter_dimension_numbers":
        from jax.lax import ScatterDimensionNumbers

        dims = _scatter_dims(value, traced=False)
        return ScatterDimensionNumbers(
            **{field: tuple(dims[field]) for field in _SCATTER_FIELDS}
        )
    if kind == "gather_mode":
        from jax.lax import GatherScatterMode

        if value not in ("CLIP", "FILL_OR_DROP", "PROMISE_IN_BOUNDS"):
            raise GraphRefused("parameter_kind_mismatch")
        return GatherScatterMode[value]
    if kind == "fft_type":
        from jax.lax import FftType

        if value not in ("FFT", "IFFT", "RFFT", "IRFFT"):
            raise GraphRefused("parameter_kind_mismatch")
        return FftType[value]
    if kind == "precision":
        if value is None:
            return None
        if type(value) is not list or len(value) != 2:
            raise GraphRefused("parameter_kind_mismatch")
        from jax.lax import Precision

        if any(v not in ("DEFAULT", "HIGH", "HIGHEST") for v in value):
            raise GraphRefused("parameter_kind_mismatch")
        return tuple(Precision[v] for v in value)
    if kind == "rounding_method":
        from jax.lax import RoundingMethod

        if value not in ("AWAY_FROM_ZERO", "TO_NEAREST_EVEN"):
            raise GraphRefused("parameter_kind_mismatch")
        return RoundingMethod[value]
    if kind == "prng_impl":
        if value != "threefry2x32":
            raise GraphRefused("prng_impl_not_allowed")
        from jax.extend.random import threefry_prng_impl

        return threefry_prng_impl
    raise GraphRefused("parameter_kind_unknown")


def encode(spec, params, lower_graph):
    """JSON parameters for an op whose allowlist entry declares `spec`."""
    if set(params) != set(spec):
        raise GraphRefused("parameters_not_allowlisted")
    out = {}
    for name in sorted(spec):
        try:
            out[name] = _encode(spec[name], params[name], lower_graph, name)
        except GraphRefused as refused:
            if refused.where:
                raise
            # Lowering runs on the miner's machine: naming the parameter helps.
            raise GraphRefused(refused.code, f"parameter {name}") from None
    return out


def _nested(value):
    """A nested-graph reference, exactly `{"graph": "<name>"}`."""
    if type(value) is not dict or set(value) != {"graph"} or type(value["graph"]) is not str:
        raise GraphRefused("parameter_kind_mismatch")
    return value


def decode(spec, params):
    """Bind-ready parameters; graph references are left to the interpreter."""
    if type(params) is not dict or set(params) != set(spec):
        raise GraphRefused("parameters_not_allowlisted")
    return {
        name: (
            _nested(params[name])
            if spec[name] == "graph"
            or (spec[name] == "graph_or_none" and params[name] is not None)
            else _decode(spec[name], params[name])
        )
        for name in spec
    }
