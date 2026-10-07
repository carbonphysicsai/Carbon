"""Parameter codecs: each allowlisted op declares its parameters by kind.

A kind turns a traced parameter into strict JSON (`encode`) and JSON back into
the exact value the op binds (`decode`). An unknown kind, a missing or extra
parameter, or a value outside its kind refuses: the allowlist bounds an op's
parameters as well as its name. `none` admits only null: sharding, layout,
precision overrides and accuracy hints stay at the framework default in v0.
"""

from __future__ import annotations

import math

from .graph import DTYPES, GraphRefused


def _ints(value):
    if type(value) not in (list, tuple) or not all(type(v) is int for v in value):
        raise GraphRefused("parameter_kind_mismatch")
    return [int(v) for v in value]


def _int_pairs(value):
    if type(value) not in (list, tuple):
        raise GraphRefused("parameter_kind_mismatch")
    return [_ints(pair) for pair in value]


def _dtype_name(value):
    import numpy as np

    name = str(np.dtype(value))
    if name not in DTYPES:
        raise GraphRefused("dtype_not_allowed")
    return name


def _default_call_metadata(value):
    """A nested call's metadata at its default: no donation, no sharding or
    layout, no mesh, no compiler options (XLA flags are Carbon's alone)."""
    if value is None or type(value) in (bool, str):
        return True
    if type(value) is tuple:
        return all(
            item is None or item is False or type(item).__name__ == "UnspecifiedValue"
            for item in value
        )
    if type(value).__name__ in ("AbstractMesh", "Mesh"):
        return not value.axis_names
    return False


def _encode(kind, value, lower_graph):
    if kind == "call_metadata":
        if not _default_call_metadata(value):
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
    if kind == "int":
        if type(value) is not int:
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "bool":
        if type(value) is not bool:
            raise GraphRefused("parameter_kind_mismatch")
        return value
    if kind == "int_tuple":
        return _ints(value)
    if kind == "int_tuple_or_none":
        return None if value is None else _ints(value)
    if kind == "int_pairs":
        return _int_pairs(value)
    if kind == "dtype":
        return _dtype_name(value)
    if kind == "dtype_or_none":
        return None if value is None else _dtype_name(value)
    if kind == "dot_dimension_numbers":
        (lc, rc), (lb, rb) = value
        return [[_ints(lc), _ints(rc)], [_ints(lb), _ints(rb)]]
    if kind == "padding_config":
        return [_ints(triple) for triple in value]
    if kind == "conv_dimension_numbers":
        return [_ints(value.lhs_spec), _ints(value.rhs_spec), _ints(value.out_spec)]
    if kind == "gather_dimension_numbers":
        return {
            name: _ints(getattr(value, name))
            for name in (
                "offset_dims",
                "collapsed_slice_dims",
                "start_index_map",
                "operand_batching_dims",
                "start_indices_batching_dims",
            )
        }
    if kind == "gather_mode":
        return value.name
    if kind == "fft_type":
        return value.name
    if kind == "prng_impl":
        if str(value) != "fry":
            raise GraphRefused("prng_impl_not_allowed")
        return "threefry2x32"
    if kind == "graph":
        return {"graph": lower_graph(value)}
    raise GraphRefused("parameter_kind_unknown")


def _decode(kind, value):
    if kind == "fill_value":
        if value is None or value == "nan":
            return None if value is None else float("nan")
        if type(value) not in (int, float):
            raise GraphRefused("parameter_kind_mismatch")
        return float(value)
    if kind in ("none", "call_metadata", "custom_rule_dropped"):
        if value is not None:
            raise GraphRefused("parameter_not_default")
        return None
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
            out[name] = _encode(spec[name], params[name], lower_graph)
        except GraphRefused as refused:
            if refused.where:
                raise
            # Lowering runs on the miner's machine: naming the parameter helps.
            raise GraphRefused(refused.code, f"parameter {name}") from None
    return out


def decode(spec, params):
    """Bind-ready parameters; graph references are left to the interpreter."""
    if type(params) is not dict or set(params) != set(spec):
        raise GraphRefused("parameters_not_allowlisted")
    return {
        name: (
            params[name] if spec[name] == "graph" else _decode(spec[name], params[name])
        )
        for name in spec
    }
