"""Lower a `torch.export` program (Core ATen) into the Carbon graph format.

In B' this, like `lower_jax`, runs on the miner's machine. It reads the
exported program in memory: no `torch.export` archive is ever deserialized
on a Carbon host. Each Core ATen op the allowlist's `aten_core` section admits
is written as Carbon ops (the same vocabulary JAX lowers to), so PyTorch and
JAX share one validator and one interpreter. An op without an emitter here is
refused (`aten_op_not_lowered`), and so is one the allowlist refuses.

Parameters become named graph inputs (Carbon feeds them); buffers and lifted
tensor constants become counted constants.
"""

from __future__ import annotations

import collections
import math
import operator

from .. import allowlist as allowlist_module
from .. import graph

#: Torch dtypes to Carbon dtypes. `int64` narrows to `int32`: Carbon's JAX
#: runs without x64, and in every family traced in Phase 0 int64 only carries
#: index arithmetic on static shapes (FNO's grid embedding). A constant
#: outside int32 is refused by `_Builder.const`.
_DTYPES = {
    "torch.float32": "float32",
    "torch.float64": "float64",
    "torch.complex64": "complex64",
    "torch.int64": "int32",
    "torch.int32": "int32",
    "torch.bool": "bool",
}


def export(apply, params, example):
    """The Core ATen program of `apply(params, x)` with `params` as module
    parameters (so they surface as named inputs) and `x` the user input."""
    import torch

    class Wrapper(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.p = torch.nn.ParameterList(
                [torch.nn.Parameter(p.detach().clone()) for p in params]
            )

        def forward(self, x):
            return apply(list(self.p), x)

    program = torch.export.export(Wrapper(), (example,))
    return program, program.run_decompositions()


def inventory(program):
    counts = collections.Counter(
        str(n.target) for n in program.graph.nodes if n.op == "call_function"
    )
    return dict(sorted(counts.items()))


def _dtype(value):
    name = _DTYPES.get(str(value))
    if name is None:
        raise graph.GraphRefused("dtype_not_allowed")
    return name


def _aval(node):
    val = node.meta["val"]
    return _dtype(val.dtype), [int(d) for d in val.shape]


class _Builder:
    def __init__(self, allowlist):
        self.allowlist = allowlist
        self.inputs, self.constants, self.nodes = [], [], []
        self.avals, self.count = {}, 0

    def _id(self, dtype, shape):
        value = self.count
        self.count += 1
        self.avals[value] = (dtype, list(shape))
        return value

    def input(self, name, dtype, shape):
        value = self._id(dtype, shape)
        self.inputs.append(
            {"value": value, "name": name, "dtype": dtype, "shape": shape}
        )
        return value

    def const(self, array):
        import numpy as np

        array = np.asarray(array)
        if array.dtype == np.int64:
            if array.size and (array.min() < -(2**31) or array.max() >= 2**31):
                raise graph.GraphRefused("integer_constant_out_of_range")
            array = array.astype(np.int32)
        entry = graph.encode_array(array)
        value = self._id(entry["dtype"], entry["shape"])
        self.constants.append({"value": value, **entry})
        return value

    def emit(self, op, ins, out_dtype, out_shape, /, **params):
        # Positional-only: op parameters include `dtype` and `shape`.
        self.allowlist.admit(op, "forward", f"aten->{op}")
        value = self._id(out_dtype, out_shape)
        self.nodes.append(
            {
                "op": op,
                "in": list(ins),
                "out": [{"value": value, "dtype": out_dtype, "shape": list(out_shape)}],
                "params": params,
            }
        )
        return value

    # -- helpers ---------------------------------------------------------
    def scalar(self, value, dtype):
        import numpy as np

        return self.const(np.asarray(value, dtype=dtype))

    def to(self, value, dtype):
        if self.avals[value][0] == dtype:
            return value
        return self.emit(
            "convert_element_type",
            [value],
            dtype,
            self.avals[value][1],
            new_dtype=dtype,
            sharding=None,
            weak_type=False,
        )

    def broadcast(self, value, shape):
        dtype, have = self.avals[value]
        if have == list(shape):
            return value
        offset = len(shape) - len(have)
        return self.emit(
            "broadcast_in_dim",
            [value],
            dtype,
            shape,
            broadcast_dimensions=list(range(offset, len(shape))),
            shape=list(shape),
            sharding=None,
        )

    def operand(self, arg, env, dtype, shape):
        """An fx argument or Python scalar as a value of `dtype` and `shape`."""
        if hasattr(arg, "op"):
            return self.broadcast(self.to(env[arg], dtype), shape)
        return self.broadcast(self.scalar(arg, dtype), shape)

    def binary(self, op, a, b, env, node, out_dtype=None):
        dtype, shape = _aval(node)
        operand_dtype = out_dtype or dtype
        x = self.operand(a, env, operand_dtype, shape)
        y = self.operand(b, env, operand_dtype, shape)
        params = {"out_dtype": None} if op == "mul" else {}
        return self.emit(op, [x, y], dtype, shape, **params)

    def unary(self, op, x, **params):
        dtype, shape = self.avals[x]
        return self.emit(op, [x], dtype, shape, **params)


def _norm(dim, rank):
    return dim + rank if dim < 0 else dim


def _gelu(b, x, approximate):
    dtype, shape = b.avals[x]

    def k(v):
        return b.broadcast(b.scalar(v, dtype), shape)

    def mul(p, q):
        return b.emit("mul", [p, q], dtype, shape, out_dtype=None)

    def add(p, q):
        return b.emit("add", [p, q], dtype, shape)

    if approximate == "tanh":
        cube = b.emit("integer_pow", [x], dtype, shape, y=3)
        inner = mul(k(math.sqrt(2 / math.pi)), add(x, mul(k(0.044715), cube)))
        t = b.unary("tanh", inner, accuracy=None)
    else:
        t = b.unary("erf", mul(x, k(1 / math.sqrt(2))))
    return mul(mul(x, k(0.5)), add(k(1.0), t))


def _fft_scale(b, value, normalization, n, xla_scale):
    """Multiply `value` so XLA's convention (`xla_scale` times the plain sum)
    matches torch's normalization code (0 none, 1 1/sqrt(n), 2 1/n)."""
    want = {0: 1.0, 1: 1 / math.sqrt(n), 2: 1 / n}[normalization]
    factor = want / xla_scale
    if factor == 1.0:
        return value
    dtype, shape = b.avals[value]
    k = b.broadcast(
        b.scalar(factor, "float32" if dtype == "complex64" else dtype), shape
    )
    k = b.to(k, dtype)
    return b.emit("mul", [value, k], dtype, shape, out_dtype=None)


def _native_batch_norm(b, node, env):
    """Batch norm over channel dim 1: inference mode with running statistics
    (`_native_batch_norm_legit_no_training`, U-shaped operators), or statistics
    of the batch itself without running ones (`_native_batch_norm_legit.no_stats`,
    instance norm). Only the normalized result is differentiable, as in torch."""
    target = str(node.target)
    args = node.args
    inference = target == "aten._native_batch_norm_legit_no_training.default"
    if node.kwargs or len(args) != (7 if inference else 6):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x_arg, weight_arg, bias_arg = args[:3]
    epsilon = args[-1]
    if not hasattr(x_arg, "op"):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[x_arg]
    dtype, shape = b.avals[x]
    if (
        dtype not in ("float32", "float64")
        or len(shape) < 2
        or type(epsilon) not in (int, float)
        or not math.isfinite(epsilon)
        or epsilon < 0
        or (not inference and args[3] is not True)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    channels = shape[1]
    stats_shape = [1, channels] + [1] * (len(shape) - 2)
    vectors = [weight_arg, bias_arg] + (list(args[3:5]) if inference else [])
    for vector in vectors:
        if vector is not None and (
            not hasattr(vector, "op") or b.avals[env[vector]] != (dtype, [channels])
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
    if inference and (args[3] is None or args[4] is None):
        raise graph.GraphRefused("aten_arguments_not_supported", target)

    def per_channel(value):
        return b.emit(
            "reshape",
            [value],
            dtype,
            stats_shape,
            dimensions=None,
            new_sizes=stats_shape,
            sharding=None,
        )

    def mean_over_batch(value):
        axes = [0] + list(range(2, len(shape)))
        total = b.emit(
            "reduce_sum", [value], dtype, [channels], axes=axes, out_sharding=None
        )
        count = math.prod(shape) // channels
        total = b.emit(
            "div",
            [total, b.broadcast(b.scalar(count, dtype), [channels])],
            dtype,
            [channels],
        )
        return per_channel(total)

    if inference:
        mean, variance = per_channel(env[args[3]]), per_channel(env[args[4]])
        centered = b.emit("sub", [x, b.broadcast(mean, shape)], dtype, shape)
    else:
        mean = mean_over_batch(x)
        centered = b.emit("sub", [x, b.broadcast(mean, shape)], dtype, shape)
        squared = b.emit("integer_pow", [centered], dtype, shape, y=2)
        variance = mean_over_batch(squared)
    variance = b.emit(
        "add",
        [variance, b.broadcast(b.scalar(epsilon, dtype), stats_shape)],
        dtype,
        stats_shape,
    )
    rstd = b.unary("rsqrt", variance, accuracy=None)
    result = b.emit(
        "mul", [centered, b.broadcast(rstd, shape)], dtype, shape, out_dtype=None
    )
    if weight_arg is not None:
        weight = b.broadcast(per_channel(env[weight_arg]), shape)
        result = b.emit("mul", [result, weight], dtype, shape, out_dtype=None)
    if bias_arg is not None:
        bias = b.broadcast(per_channel(env[bias_arg]), shape)
        result = b.emit("add", [result, bias], dtype, shape)
    if inference:
        # Torch returns empty saved statistics here; selecting them is refused.
        return (result, None, None)

    def flat(value):
        return b.emit(
            "reshape",
            [b.unary("stop_gradient", value)],
            dtype,
            [channels],
            dimensions=None,
            new_sizes=[channels],
            sharding=None,
        )

    return (result, flat(mean), flat(rstd))


def _split_with_sizes(b, node, env):
    """One static slice per part (a tuple result, selected by getitem)."""
    target = str(node.target)
    args, kw = node.args, node.kwargs
    if not hasattr(args[0], "op"):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[args[0]]
    have = b.avals[x][1]
    sizes = list(args[1])
    dim = _norm(args[2] if len(args) > 2 else kw.get("dim", 0), len(have))
    if sum(sizes) != have[dim] or any(type(n) is not int or n < 0 for n in sizes):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    parts, start = [], 0
    for n in sizes:
        begin = [0] * len(have)
        end = list(have)
        begin[dim], end[dim] = start, start + n
        part_shape = list(have)
        part_shape[dim] = n
        parts.append(
            b.emit(
                "slice",
                [x],
                b.avals[x][0],
                part_shape,
                limit_indices=end,
                start_indices=begin,
                strides=None,
            )
        )
        start += n
    return tuple(parts)


def _max_pool2d(b, node, env):
    """Non-overlapping 2-D max pooling (kernel = stride, no padding or dilation),
    as U-Net-style encoders use it: crop to whole windows (floor mode), reshape
    so each window is two axes, and reduce_max over them. Only the values are
    selectable; the indices output is refused. Gradients match torch's except
    at exact ties inside a window (JAX's reduce_max shares them)."""
    target = str(node.target)
    args = list(node.args) + [None] * (6 - len(node.args))
    x_arg, kernel, stride, padding, dilation, ceil_mode = args[:6]
    kw = node.kwargs
    stride = kw.get("stride", stride) or kernel
    padding = kw.get("padding", padding) or [0, 0]
    dilation = kw.get("dilation", dilation) or [1, 1]
    ceil_mode = kw.get("ceil_mode", ceil_mode) or False
    if not hasattr(x_arg, "op"):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[x_arg]
    dtype, shape = b.avals[x]
    kernel = list(kernel) * (2 if len(kernel) == 1 else 1)
    stride = list(stride) * (2 if len(stride) == 1 else 1)
    if (
        len(shape) != 4
        or kernel != stride
        or any(int(p) != 0 for p in padding)
        or any(int(d) != 1 for d in dilation)
        or ceil_mode
        or any(type(k) is not int or k < 1 for k in kernel)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    (n, c, h, w), (kh, kw_) = shape, kernel
    oh, ow = h // kh, w // kw_
    if oh < 1 or ow < 1:
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    if (oh * kh, ow * kw_) != (h, w):
        x = b.emit(
            "slice",
            [x],
            dtype,
            [n, c, oh * kh, ow * kw_],
            limit_indices=[n, c, oh * kh, ow * kw_],
            start_indices=[0, 0, 0, 0],
            strides=None,
        )
    windows = [n, c, oh, kh, ow, kw_]
    x = b.emit(
        "reshape",
        [x],
        dtype,
        windows,
        dimensions=None,
        new_sizes=windows,
        sharding=None,
    )
    spec = b.allowlist.ops["reduce_max"]["params"]
    values = b.emit(
        "reduce_max",
        [x],
        dtype,
        [n, c, oh, ow],
        axes=[3, 5],
        **({"out_sharding": None} if "out_sharding" in spec else {}),
    )
    return (values, None)


def _native_layer_norm(b, node, env):
    """Lower all three results of Core ATen layer norm from trusted metadata."""
    target = str(node.target)
    args = node.args
    if len(args) != 5 or node.kwargs:
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x_arg, normalized_shape, weight_arg, bias_arg, epsilon = args
    if not hasattr(x_arg, "op") or not isinstance(normalized_shape, (list, tuple)):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[x_arg]
    dtype, shape = b.avals[x]
    if dtype not in ("float32", "float64"):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    if (
        not normalized_shape
        or any(type(d) is not int or d <= 0 for d in normalized_shape)
        or list(normalized_shape) != shape[-len(normalized_shape) :]
        or len(normalized_shape) > len(shape)
        or type(epsilon) not in (int, float)
        or not math.isfinite(epsilon)
        or epsilon < 0
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    for affine in (weight_arg, bias_arg):
        if affine is not None and (
            not hasattr(affine, "op")
            or b.avals[env[affine]] != (dtype, list(normalized_shape))
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
    rank = len(shape)
    axes = list(range(rank - len(normalized_shape), rank))
    prefix = shape[: -len(normalized_shape)]
    stats_shape = prefix + [1] * len(normalized_shape)
    count = math.prod(normalized_shape)

    def mean_of(value):
        reduced = b.emit(
            "reduce_sum", [value], dtype, prefix, axes=axes, out_sharding=None
        )
        reduced = b.emit(
            "div",
            [reduced, b.broadcast(b.scalar(count, dtype), prefix)],
            dtype,
            prefix,
        )
        return b.emit(
            "reshape",
            [reduced],
            dtype,
            stats_shape,
            dimensions=None,
            new_sizes=stats_shape,
            sharding=None,
        )

    mean = mean_of(x)
    centered = b.emit("sub", [x, b.broadcast(mean, shape)], dtype, shape)
    squared = b.emit("integer_pow", [centered], dtype, shape, y=2)
    variance = mean_of(squared)
    variance = b.emit(
        "add",
        [variance, b.broadcast(b.scalar(epsilon, dtype), stats_shape)],
        dtype,
        stats_shape,
    )
    rstd = b.unary("rsqrt", variance, accuracy=None)
    result = b.emit(
        "mul", [centered, b.broadcast(rstd, shape)], dtype, shape, out_dtype=None
    )
    if weight_arg is not None:
        result = b.emit(
            "mul",
            [result, b.broadcast(env[weight_arg], shape)],
            dtype,
            shape,
            out_dtype=None,
        )
    if bias_arg is not None:
        result = b.emit(
            "add", [result, b.broadcast(env[bias_arg], shape)], dtype, shape
        )
    # Core ATen exposes mean and rstd for callers, but Torch's native op
    # marks both auxiliary outputs nondifferentiable. Keep the internal
    # statistics above on the differentiable path for the normalized result.
    outputs = (
        result,
        b.unary("stop_gradient", mean),
        b.unary("stop_gradient", rstd),
    )
    metadata = node.meta.get("val")
    if not isinstance(metadata, (tuple, list)) or len(metadata) != 3:
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    for output, meta in zip(outputs, metadata):
        if b.avals[output] != (_dtype(meta.dtype), [int(d) for d in meta.shape]):
            raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    return outputs


def _softmax(b, node, env):
    """Lower Core ATen softmax using the existing stable reduction primitives."""
    target = str(node.target)
    args = node.args
    if (
        len(args) != 3
        or node.kwargs
        or not hasattr(args[0], "op")
        or type(args[1]) is not int
        or type(args[2]) is not bool
        or args[2]
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[args[0]]
    dtype, shape = b.avals[x]
    rank = len(shape)
    dim = _norm(args[1], rank)
    if (
        dtype not in ("float32", "float64")
        or rank == 0
        or not 0 <= dim < rank
        or any(size <= 0 for size in shape)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    if _aval(node) != (dtype, shape):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)

    reduced_shape = shape[:dim] + shape[dim + 1 :]
    kept_shape = shape[:dim] + [1] + shape[dim + 1 :]

    def keep_dim(value):
        return b.emit(
            "reshape",
            [value],
            dtype,
            kept_shape,
            dimensions=None,
            new_sizes=kept_shape,
            sharding=None,
        )

    # The shift leaves softmax unchanged, so its derivative is identically
    # irrelevant. Stop the input path before JAX's reduce_max primitive.
    spec = b.allowlist.ops["reduce_max"]["params"]
    maximum = b.emit(
        "reduce_max",
        [b.unary("stop_gradient", x)],
        dtype,
        reduced_shape,
        axes=[dim],
        # v5 lists out_sharding; v6 does not (JAX 0.10.2's reduce_max has none).
        **({"out_sharding": None} if "out_sharding" in spec else {}),
    )
    shifted = b.emit("sub", [x, b.broadcast(keep_dim(maximum), shape)], dtype, shape)
    exponentials = b.unary("exp", shifted, accuracy=None)
    total = b.emit(
        "reduce_sum",
        [exponentials],
        dtype,
        reduced_shape,
        axes=[dim],
        out_sharding=None,
    )
    return b.emit(
        "div", [exponentials, b.broadcast(keep_dim(total), shape)], dtype, shape
    )


def _sum_dim(b, node, env):
    """Lower a static Core ATen dimensioned sum with its declared dtype."""
    target = str(node.target)
    args, kw = node.args, node.kwargs
    if (
        len(args) not in (2, 3)
        or not hasattr(args[0], "op")
        or (args[1] is not None and not isinstance(args[1], (list, tuple)))
        or (args[1] is not None and any(type(axis) is not int for axis in args[1]))
        or set(kw) - {"keepdim", "dtype"}
        or (len(args) == 3 and "keepdim" in kw)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    keepdim = args[2] if len(args) == 3 else kw.get("keepdim", False)
    if type(keepdim) is not bool:
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[args[0]]
    input_dtype, shape = b.avals[x]
    output_dtype = (
        input_dtype if kw.get("dtype") is None else _DTYPES.get(str(kw["dtype"]))
    )
    rank = len(shape)
    requested_axes = args[1]
    if requested_axes is None or not requested_axes:
        axes = list(range(rank))
    else:
        # Torch treats a scalar as logical rank one for axis validation,
        # while its result remains a scalar even with keepdim=True.
        axes = [_norm(axis, rank or 1) for axis in requested_axes]
    if (
        input_dtype not in ("float32", "float64")
        or output_dtype not in ("float32", "float64")
        or any(not 0 <= axis < (rank or 1) for axis in axes)
        or len(set(axes)) != len(axes)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    axes.sort()
    reduced_shape = [size for axis, size in enumerate(shape) if axis not in axes]
    expected_shape = (
        [1 if axis in axes else size for axis, size in enumerate(shape)]
        if keepdim
        else reduced_shape
    )
    if _aval(node) != (output_dtype, expected_shape):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    if rank == 0:
        return b.to(x, output_dtype)
    reduced = b.emit(
        "reduce_sum",
        [b.to(x, output_dtype)],
        output_dtype,
        reduced_shape,
        axes=axes,
        out_sharding=None,
    )
    if not keepdim:
        return reduced
    return b.emit(
        "reshape",
        [reduced],
        output_dtype,
        expected_shape,
        dimensions=None,
        new_sizes=expected_shape,
        sharding=None,
    )


#: Ops that only reshape, broadcast or convert a value: a static index may reach
#: a static-index emitter through them (`dst.view(1, -1, 1).expand(...)`).
_SHAPE_ONLY = ("reshape", "broadcast_in_dim", "convert_element_type")

#: Exactly rounded elementwise ops a static index may also be computed with
#: (interpolation's `(arange(n) * scale).clamp(0)`): evaluated here in the
#: node's own dtype, they give the interpreter's result bit for bit.
_FOLDABLE = ("add", "sub", "mul", "max", "min", "lt", "gt")


def _static_array(b, value):
    """The array `value` holds when it is a captured constant, or one computed
    from constants and iotas only through shape-only and exactly rounded
    elementwise ops; otherwise None (input-derived)."""
    import numpy as np

    for entry in b.constants:
        if entry["value"] == value:
            return graph.decode_array(entry)
    producer = next(
        (n for n in reversed(b.nodes) if n["out"][0]["value"] == value), None
    )
    if producer is None:
        return None
    out = producer["out"][0]
    if producer["op"] == "iota":
        dim = producer["params"]["dimension"]
        axis = np.arange(out["shape"][dim], dtype=out["dtype"])
        kept = [-1 if i == dim else 1 for i in range(len(out["shape"]))]
        return np.broadcast_to(axis.reshape(kept), out["shape"]).copy()
    if producer["op"] in _FOLDABLE or producer["op"] == "select_n":
        operands = [_static_array(b, v) for v in producer["in"]]
        if any(o is None for o in operands):
            return None
        if producer["op"] == "select_n":
            which, no, yes = operands
            return np.where(which, yes, no).astype(out["dtype"])
        fold = {
            "add": np.add,
            "sub": np.subtract,
            "mul": np.multiply,
            "max": np.maximum,
            "min": np.minimum,
            "lt": np.less,
            "gt": np.greater,
        }[producer["op"]]
        return np.asarray(fold(*operands)).astype(out["dtype"])
    if producer["op"] not in _SHAPE_ONLY:
        return None
    source = _static_array(b, producer["in"][0])
    if source is None:
        return None
    if producer["op"] == "reshape":
        return source.reshape(out["shape"])
    if producer["op"] == "convert_element_type":
        return source.astype(out["dtype"])
    dims = list(producer["params"]["broadcast_dimensions"])
    kept = [
        source.shape[dims.index(axis)] if axis in dims else 1
        for axis in range(len(out["shape"]))
    ]
    return np.broadcast_to(source.reshape(kept), out["shape"]).copy()


def _scatter_add_static(b, node, env):
    """Order static-index updates without a GPU atomic scatter primitive.

    Only a prospective allowlist admitting this ATen op can reach this emitter;
    pinned v5 bytes remain unchanged. Input-derived indices are refused:
    Carbon's graph interpreter has no typed runtime index-bounds refusal yet.
    Each source position contributes in increasing order, including repeats.
    """
    target = str(node.target)
    args = node.args
    if (
        len(args) != 4
        or node.kwargs
        or not hasattr(args[0], "op")
        or type(args[1]) is not int
        or not hasattr(args[2], "op")
        or not hasattr(args[3], "op")
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    base, index_value, source = env[args[0]], env[args[2]], env[args[3]]
    dtype, shape = b.avals[base]
    source_dtype, source_shape = b.avals[source]
    index_dtype, index_shape = b.avals[index_value]
    rank = len(shape)
    dim = _norm(args[1], rank)
    if (
        rank == 0
        or not 0 <= dim < rank
        or dtype not in ("float32", "float64")
        or source_dtype != dtype
        or index_dtype != "int32"
        or str(getattr(args[2].meta.get("val"), "dtype", None)) != "torch.int64"
        or index_shape != source_shape
        or len(source_shape) != rank
        or any(source_shape[axis] != shape[axis] for axis in range(rank) if axis != dim)
    ):
        raise graph.GraphRefused("aten_scatter_shape_or_dtype_not_supported", target)
    if _aval(node) != (dtype, shape):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    index = _static_array(b, index_value)
    if index is None:
        raise graph.GraphRefused("aten_scatter_index_not_static", target)
    if (index < 0).any() or (index >= shape[dim]).any():
        raise graph.GraphRefused("aten_scatter_index_out_of_bounds", target)
    if index.size == 0:
        return base

    import numpy as np

    count = source_shape[dim]
    # Each position's index slice; a graph network's aggregation index is the
    # same along every other axis, so that slice is one scalar, broadcast.
    slices = [np.take(index, position, axis=dim) for position in range(count)]
    uniform = [bool((part == part.flat[0]).all()) for part in slices]
    emitted_values = sum(
        1 if same else part.size for part, same in zip(slices, uniform)
    )
    # One iota and one zero broadcast, then seven existing primitive nodes
    # per ordered update. The byte cap measures one emitted output, not the
    # sum of all outputs; graph.measure applies that same registered meaning.
    nodes = 2 + 7 * count
    bytes_per_result = math.prod(shape) * max(graph.itemsize(dtype), 4)
    # The miner's own tensor first (a candidate refusal), then what only Carbon's
    # unrolling adds (a Carbon capability gap; Validator classes, 5cc80cbe8).
    if bytes_per_result > allowlist_module.CAPS["largest_intermediate_bytes"]:
        raise graph.GraphRefused("aten_scatter_registered_resource_bound", target)
    if (
        len(b.nodes) + nodes > allowlist_module.CAPS["nodes_executed"]
        or graph.VALUE_BYTES
        * (graph.unique_constant_values(b.constants) + emitted_values)
        > allowlist_module.CAPS["constant_bytes"]
    ):
        raise graph.GraphRefused("aten_scatter_lowering_expansion_bound", target)

    coordinates = b.emit(
        "iota",
        [],
        "int32",
        shape,
        dimension=dim,
        dtype="int32",
        shape=shape,
        sharding=None,
    )
    zero = b.broadcast(b.scalar(0, dtype), shape)
    other_axes = [axis for axis in range(rank) if axis != dim]
    without_dim = [shape[axis] for axis in other_axes]
    result = base
    for position in range(count):
        if uniform[position]:
            selected_index = b.broadcast(
                b.scalar(int(slices[position].flat[0]), "int32"), shape
            )
        else:
            selected_index = b.emit(
                "broadcast_in_dim",
                [b.const(slices[position])],
                "int32",
                shape,
                broadcast_dimensions=other_axes,
                shape=shape,
                sharding=None,
            )
        matches = b.emit("eq", [coordinates, selected_index], "bool", shape)
        starts = [position if axis == dim else 0 for axis in range(rank)]
        limits = [
            position + 1 if axis == dim else size for axis, size in enumerate(shape)
        ]
        sliced_shape = list(source_shape)
        sliced_shape[dim] = 1
        selected_source = b.emit(
            "slice",
            [source],
            dtype,
            sliced_shape,
            start_indices=starts,
            limit_indices=limits,
            strides=None,
        )
        selected_source = b.emit(
            "reshape",
            [selected_source],
            dtype,
            without_dim,
            dimensions=None,
            new_sizes=without_dim,
            sharding=None,
        )
        selected_source = b.emit(
            "broadcast_in_dim",
            [selected_source],
            dtype,
            shape,
            broadcast_dimensions=other_axes,
            shape=shape,
            sharding=None,
        )
        update = b.emit("select_n", [matches, zero, selected_source], dtype, shape)
        result = b.emit("add", [result, update], dtype, shape)
    return result


def _index_static(b, node, env):
    """`x[..., index, ...]` for one static int64 index on one dimension.

    Only a prospective allowlist admitting this ATen op reaches this emitter.
    The index must be a captured constant (a graph network's fixed edge list):
    Torch's negative indices wrap, then every index is bounds-checked. It lowers
    to one `slice` per run of consecutive indices and one `concatenate`, not a
    gather primitive, so neither inference nor a rebuild's gradient needs a
    nondeterministic scatter. Input-derived indices refuse.
    """
    target = str(node.target)
    args = node.args
    if (
        len(args) != 2
        or node.kwargs
        or not hasattr(args[0], "op")
        or not isinstance(args[1], (list, tuple))  # torch.fx immutable_list
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    given = [(axis, index) for axis, index in enumerate(args[1]) if index is not None]
    if len(given) != 1 or not hasattr(given[0][1], "op"):
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    dim, index_node = given[0]
    x = env[args[0]]
    dtype, shape = b.avals[x]
    index_value = env[index_node]
    index_dtype, index_shape = b.avals[index_value]
    if (
        not 0 <= dim < len(shape)
        or len(index_shape) != 1
        or index_shape[0] < 1
        or index_dtype != "int32"
        or str(getattr(index_node.meta.get("val"), "dtype", None)) != "torch.int64"
    ):
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    expected = list(shape)
    expected[dim] = index_shape[0]
    if _aval(node) != (dtype, expected):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    static = _static_array(b, index_value)
    if static is None:
        raise graph.GraphRefused("aten_index_not_static", target)
    size = shape[dim]
    index = [int(i) for i in static]
    index = [i + size if i < 0 else i for i in index]
    if any(not 0 <= i < size for i in index):
        raise graph.GraphRefused("aten_index_out_of_bounds", target)
    runs = []  # [start, stop) of each run of consecutive indices
    for i in index:
        if runs and i == runs[-1][1]:
            runs[-1][1] += 1
        else:
            runs.append([i, i + 1])
    bytes_per_result = math.prod(expected) * max(graph.itemsize(dtype), 4)
    if bytes_per_result > allowlist_module.CAPS["largest_intermediate_bytes"]:
        raise graph.GraphRefused("aten_index_registered_resource_bound", target)
    if len(b.nodes) + len(runs) + 1 > allowlist_module.CAPS["nodes_executed"]:
        raise graph.GraphRefused("aten_index_lowering_expansion_bound", target)
    pieces = []
    for start, stop in runs:
        piece_shape = list(shape)
        piece_shape[dim] = stop - start
        pieces.append(
            b.emit(
                "slice",
                [x],
                dtype,
                piece_shape,
                start_indices=[
                    start if axis == dim else 0 for axis in range(len(shape))
                ],
                limit_indices=[
                    stop if axis == dim else extent for axis, extent in enumerate(shape)
                ],
                strides=None,
            )
        )
    if len(pieces) == 1:
        return pieces[0]
    return b.emit("concatenate", pieces, dtype, expected, dimension=dim)


def _emit(b, node, env):
    """The Carbon value for one Core ATen call, or `GraphRefused`."""
    target = str(node.target)
    args, kw = node.args, node.kwargs
    if node.target is operator.getitem:
        if (
            len(args) != 2
            or kw
            or not hasattr(args[0], "op")
            or not isinstance(env.get(args[0]), tuple)
            or type(args[1]) is not int
            or not 0 <= args[1] < len(env[args[0]])
            or env[args[0]][args[1]] is None
        ):
            raise graph.GraphRefused("aten_tuple_index_not_supported", target)
        selected = env[args[0]][args[1]]
        if b.avals[selected] != _aval(node):
            raise graph.GraphRefused("aten_result_metadata_not_supported", target)
        return selected
    entry = b.allowlist.aten.get(target)
    if entry is None or entry["default"] == "refuse":
        raise graph.GraphRefused("aten_op_not_allowlisted", target)
    if target == "aten.native_layer_norm.default":
        return _native_layer_norm(b, node, env)
    if target in (
        "aten._native_batch_norm_legit_no_training.default",
        "aten._native_batch_norm_legit.no_stats",
    ):
        return _native_batch_norm(b, node, env)
    if target == "aten._softmax.default":
        return _softmax(b, node, env)
    if target == "aten.sum.dim_IntList":
        return _sum_dim(b, node, env)
    if target == "aten.scatter_add.default":
        return _scatter_add_static(b, node, env)
    if target == "aten.index.Tensor":
        return _index_static(b, node, env)
    if target == "aten.split_with_sizes.default":
        return _split_with_sizes(b, node, env)
    if target == "aten.max_pool2d_with_indices.default":
        return _max_pool2d(b, node, env)
    dtype, shape = (
        _aval(node)
        if "val" in node.meta and node.meta["val"] is not None
        else (None, None)
    )
    rank = len(shape) if shape is not None else 0
    x = env.get(args[0]) if args and hasattr(args[0], "op") else None

    if target in ("aten.add.Tensor", "aten.sub.Tensor"):
        other = args[1]
        alpha = kw.get("alpha", 1)
        op = "add" if target == "aten.add.Tensor" else "sub"
        if alpha != 1:
            y = b.operand(other, env, dtype, shape)
            other_scaled = b.emit(
                "mul",
                [y, b.operand(alpha, env, dtype, shape)],
                dtype,
                shape,
                out_dtype=None,
            )
            return b.emit(
                op, [b.operand(args[0], env, dtype, shape), other_scaled], dtype, shape
            )
        return b.binary(op, args[0], other, env, node)
    if target in ("aten.mul.Tensor", "aten.mul.Scalar"):
        return b.binary("mul", args[0], args[1], env, node)
    if target == "aten.reciprocal.default":
        return b.binary("div", 1, args[0], env, node)
    if target == "aten.div.Tensor":
        return b.binary("div", args[0], args[1], env, node)
    if target in (
        "aten.lt.Scalar",
        "aten.lt.Tensor",
        "aten.gt.Scalar",
        "aten.gt.Tensor",
        "aten.eq.Scalar",
        "aten.ge.Scalar",
        "aten.ge.Tensor",
        "aten.le.Scalar",
        "aten.le.Tensor",
    ):
        op = target.split(".")[1]
        operand_dtype = b.avals[env[args[0]]][0]
        return b.binary(op, args[0], args[1], env, node, out_dtype=operand_dtype)
    if target == "aten.where.self":
        cond = b.operand(args[0], env, "bool", shape)
        yes = b.operand(args[1], env, dtype, shape)
        no = b.operand(args[2], env, dtype, shape)
        return b.emit("select_n", [cond, no, yes], dtype, shape)
    if target == "aten.bitwise_and.Tensor":
        # Boolean masks only (KAN's spline interval test): Carbon's `and`.
        if dtype != "bool" or any(b.avals[env[a]][0] != "bool" for a in args[:2]):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.binary("and", args[0], args[1], env, node)
    if target in ("aten.abs.default", "aten.sign.default"):
        # Both have derivative sign(x) and 0 at zero, as torch's.
        return b.unary(target.split(".")[1], x)
    if target == "aten.gelu.default":
        return _gelu(b, x, kw.get("approximate", "none"))
    if target == "aten.tanh.default":
        return b.unary("tanh", x, accuracy=None)
    if target in ("aten.cos.default", "aten.sin.default"):
        return b.unary(target.split(".")[1], x, accuracy=None)
    if target == "aten.logical_not.default":
        if b.avals[x][0] != "bool" or dtype != "bool":
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.unary("not", x)
    if target == "aten.sigmoid.default":
        return b.unary("logistic", x, accuracy=None)
    if target in ("aten.exp.default", "aten.log1p.default", "aten.sqrt.default"):
        return b.unary(target.split(".")[1], x, accuracy=None)
    if target in ("aten.mean.dim", "aten.var.correction"):
        have = b.avals[x][1]
        dims = args[1] if len(args) > 1 and args[1] is not None else kw.get("dim")
        dims = (
            list(range(len(have)))
            if dims is None
            else [_norm(d, len(have)) for d in dims]
        )
        keep = kw.get(
            "keepdim", args[2] if target == "aten.mean.dim" and len(args) > 2 else False
        )
        n = math.prod(have[d] for d in dims)
        kept = [1 if i in dims else d for i, d in enumerate(have)]
        reduced = [d for i, d in enumerate(have) if i not in dims]

        def mean_kept(value):
            s = b.emit(
                "reduce_sum", [value], dtype, reduced, axes=dims, out_sharding=None
            )
            s = b.emit(
                "div", [s, b.broadcast(b.scalar(n, dtype), reduced)], dtype, reduced
            )
            return b.emit(
                "reshape",
                [s],
                dtype,
                kept,
                dimensions=None,
                new_sizes=kept,
                sharding=None,
            )

        if target == "aten.mean.dim":
            out = mean_kept(x)
        else:
            correction = kw.get("correction", 1)
            centred = b.emit("sub", [x, b.broadcast(mean_kept(x), have)], dtype, have)
            sq = b.emit("integer_pow", [centred], dtype, have, y=2)
            s = b.emit("reduce_sum", [sq], dtype, reduced, axes=dims, out_sharding=None)
            s = b.emit(
                "div",
                [s, b.broadcast(b.scalar(n - correction, dtype), reduced)],
                dtype,
                reduced,
            )
            out = b.emit(
                "reshape",
                [s],
                dtype,
                kept,
                dimensions=None,
                new_sizes=kept,
                sharding=None,
            )
        if not keep:
            out = b.emit(
                "reshape",
                [out],
                dtype,
                shape,
                dimensions=None,
                new_sizes=shape,
                sharding=None,
            )
        return out
    if target == "aten.relu.default":
        if "relu" in b.allowlist.named:
            # Carbon's relu and its rule (zero gradient at zero, as torch).
            b.allowlist.admit_named("relu", "forward", target)
            return b.emit("named_function", [x], dtype, shape, name="relu")
        return b.emit("max", [x, b.broadcast(b.scalar(0, dtype), shape)], dtype, shape)
    if target == "aten.mm.default":
        y = env[args[1]]
        return b.emit(
            "dot_general",
            [x, y],
            dtype,
            shape,
            dimension_numbers=[[[1], [0]], [[], []]],
            out_sharding=None,
            precision=None,
            preferred_element_type=dtype,
        )
    if target == "aten.bmm.default":
        y = env[args[1]]
        return b.emit(
            "dot_general",
            [x, y],
            dtype,
            shape,
            dimension_numbers=[[[2], [1]], [[0], [0]]],
            out_sharding=None,
            precision=None,
            preferred_element_type=dtype,
        )
    if target == "aten.addmm.default":
        a, m2 = env[args[1]], env[args[2]]
        if kw.get("beta", 1) != 1 or kw.get("alpha", 1) != 1:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        product = b.emit(
            "dot_general",
            [a, m2],
            dtype,
            shape,
            dimension_numbers=[[[1], [0]], [[], []]],
            out_sharding=None,
            precision=None,
            preferred_element_type=dtype,
        )
        return b.emit(
            "add", [product, b.operand(args[0], env, dtype, shape)], dtype, shape
        )
    if target in ("aten.permute.default",):
        perm = [_norm(d, rank) for d in args[1]]
        return b.emit("transpose", [x], dtype, shape, permutation=perm)
    if target == "aten.t.default":
        return b.emit("transpose", [x], dtype, shape, permutation=[1, 0])
    if target in (
        "aten.view.default",
        "aten._unsafe_view.default",
        "aten.reshape.default",
        "aten.unsqueeze.default",
        "aten.squeeze.dim",
        "aten.squeeze.dims",
    ):
        if b.avals[x][1] == shape:
            return x
        return b.emit(
            "reshape",
            [x],
            dtype,
            shape,
            dimensions=None,
            new_sizes=shape,
            sharding=None,
        )
    if target == "aten.expand.default":
        return b.broadcast(x, shape)
    if target in ("aten.alias.default", "aten.clone.default"):
        return x
    if target == "aten.copy.default":
        return b.operand(args[1], env, dtype, shape)
    if target == "aten._to_copy.default":
        return b.to(x, dtype)
    if target == "aten.cat.default":
        dim = _norm(args[1] if len(args) > 1 else kw.get("dim", 0), rank)
        parts = [b.to(env[t], dtype) for t in args[0]]
        return b.emit("concatenate", parts, dtype, shape, dimension=dim)
    if target in ("aten.slice.Tensor", "aten.select.int"):
        have = b.avals[x][1]
        dim = _norm(args[1] if len(args) > 1 else 0, len(have))
        if target == "aten.select.int":
            index = args[2] % have[dim]
            start, step, length = index, 1, 1
        else:
            start_, end_ = (list(args[2:4]) + [None, None])[:2]
            step = args[4] if len(args) > 4 else 1
            start, _, step = slice(start_, end_, step).indices(have[dim])
            length = shape[dim]
        starts = [0] * len(have)
        limits = list(have)
        strides = [1] * len(have)
        starts[dim], limits[dim], strides[dim] = (
            start,
            start + (length - 1) * step + 1,
            step,
        )
        sliced_shape = list(have)
        sliced_shape[dim] = length
        out = b.emit(
            "slice",
            [x],
            dtype,
            sliced_shape,
            limit_indices=limits,
            start_indices=starts,
            strides=strides if step != 1 else None,
        )
        if sliced_shape != shape:
            out = b.emit(
                "reshape",
                [out],
                dtype,
                shape,
                dimensions=None,
                new_sizes=shape,
                sharding=None,
            )
        return out
    if target == "aten.slice_scatter.default":
        base, src = env[args[0]], env[args[1]]
        have = b.avals[base][1]
        dim = _norm(args[2] if len(args) > 2 else 0, len(have))
        start = args[3] if len(args) > 3 and args[3] is not None else 0
        step = args[5] if len(args) > 5 else 1
        if step != 1:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        indices = [
            b.scalar(start % have[dim] if d == dim else 0, "int32")
            for d in range(len(have))
        ]
        return b.emit(
            "dynamic_update_slice", [base, b.to(src, dtype), *indices], dtype, shape
        )
    if target == "aten.repeat.default":
        have = b.avals[x][1]
        reps = list(args[1])
        have = [1] * (len(reps) - len(have)) + have
        x = (
            b.emit(
                "reshape",
                [x],
                dtype,
                have,
                dimensions=None,
                new_sizes=have,
                sharding=None,
            )
            if have != b.avals[x][1]
            else x
        )
        inter_in = [v for d in have for v in (1, d)]
        inter = [v for r, d in zip(reps, have) for v in (r, d)]
        x = b.emit(
            "reshape",
            [x],
            dtype,
            inter_in,
            dimensions=None,
            new_sizes=inter_in,
            sharding=None,
        )
        x = b.emit(
            "broadcast_in_dim",
            [x],
            dtype,
            inter,
            broadcast_dimensions=list(range(len(inter))),
            shape=inter,
            sharding=None,
        )
        return b.emit(
            "reshape",
            [x],
            dtype,
            shape,
            dimensions=None,
            new_sizes=shape,
            sharding=None,
        )
    if target == "aten.full.default":
        return b.broadcast(
            b.scalar(args[1], dtype if dtype != "complex64" else "complex64"), shape
        )
    if target == "aten.full_like.default":
        # `torch.zeros_like` and friends: the fill at the result's own declared
        # dtype and shape (prospective v6; graph networks allocate this way).
        if (
            len(args) != 2
            or isinstance(args[1], bool)
            or not isinstance(args[1], (int, float))
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.broadcast(b.scalar(args[1], dtype), shape)
    if target == "aten.arange.start_step":
        start = args[0]
        step = args[2] if len(args) > 2 else kw.get("step", 1)
        out = b.emit(
            "iota",
            [],
            dtype,
            shape,
            dimension=0,
            dtype=dtype,
            shape=shape,
            sharding=None,
        )
        if step != 1:
            out = b.emit(
                "mul",
                [out, b.broadcast(b.scalar(step, dtype), shape)],
                dtype,
                shape,
                out_dtype=None,
            )
        if start != 0:
            out = b.emit(
                "add", [out, b.broadcast(b.scalar(start, dtype), shape)], dtype, shape
            )
        return out
    if target == "aten.view_as_complex.default":
        have = b.avals[x][1]
        parts = []
        for k in (0, 1):
            s = b.emit(
                "slice",
                [x],
                b.avals[x][0],
                have[:-1] + [1],
                limit_indices=have[:-1] + [k + 1],
                start_indices=[0] * (len(have) - 1) + [k],
                strides=None,
            )
            parts.append(
                b.emit(
                    "reshape",
                    [s],
                    b.avals[x][0],
                    have[:-1],
                    dimensions=None,
                    new_sizes=have[:-1],
                    sharding=None,
                )
            )
        return b.emit("complex", parts, dtype, shape)
    if target == "aten.view_as_real.default":
        # (..., 2) with the real part at index 0, as torch: the inverse of
        # view_as_complex above (AFNO's spectral blocks).
        have = b.avals[x][1]
        parts = []
        for op in ("real", "imag"):
            part = b.emit(op, [x], dtype, have)
            parts.append(
                b.emit(
                    "reshape",
                    [part],
                    dtype,
                    have + [1],
                    dimensions=None,
                    new_sizes=have + [1],
                    sharding=None,
                )
            )
        return b.emit("concatenate", parts, dtype, shape, dimension=len(have))
    if target == "aten.clamp.default":
        # Selects, not max/min, so the gradient passes where low <= x <= high
        # (torch's rule) rather than splitting at a tie (JAX's max/min rule).
        low = args[1] if len(args) > 1 else kw.get("min")
        high = args[2] if len(args) > 2 else kw.get("max")
        if low is None and high is None:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        out = x
        for bound, op in ((low, "lt"), (high, "gt")):
            if bound is None:
                continue
            if isinstance(bound, bool) or not isinstance(bound, (int, float)):
                raise graph.GraphRefused("aten_arguments_not_supported", target)
            limit = b.broadcast(b.scalar(bound, dtype), shape)
            beyond = b.emit(op, [out, limit], "bool", shape)
            out = b.emit("select_n", [beyond, out, limit], dtype, shape)
        return out
    if target in ("aten._fft_r2c.default", "aten._fft_c2r.default"):
        have = b.avals[x][1]
        dims = [_norm(d, len(have)) for d in args[1]]
        normalization = args[2]
        if len(set(dims)) != len(dims) or (
            target.endswith("r2c.default") and not args[3]
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        # Transforms over non-trailing dims (channels-last layouts such as
        # AFNO's rfft2 over H, W): move them last, transform, move them back.
        perm = [axis for axis in range(len(have)) if axis not in dims] + dims
        inverse = [perm.index(axis) for axis in range(len(have))]
        moved = perm != list(range(len(have)))
        if moved:
            x = b.emit(
                "transpose",
                [x],
                b.avals[x][0],
                [have[axis] for axis in perm],
                permutation=perm,
            )
        work = [shape[axis] for axis in perm]
        if target == "aten._fft_r2c.default":
            lengths = [have[d] for d in dims]
            out = b.emit("fft", [x], dtype, work, fft_lengths=lengths, fft_type="RFFT")
            out = _fft_scale(b, out, normalization, math.prod(lengths), 1.0)
        else:
            lengths = [have[d] for d in dims[:-1]] + [args[3]]
            out = b.emit("fft", [x], dtype, work, fft_lengths=lengths, fft_type="IRFFT")
            n = math.prod(lengths)
            out = _fft_scale(b, out, normalization, n, 1 / n)
        if moved:
            out = b.emit("transpose", [out], dtype, shape, permutation=inverse)
        return out
    if target == "aten.constant_pad_nd.default":
        # F.pad(x, pad, value): `pad` lists (low, high) per dim from the last
        # one inwards; negative entries crop, as lax.pad allows.
        pad, value = list(args[1]), args[2] if len(args) > 2 else 0
        have = b.avals[x][1]
        if len(pad) % 2 or len(pad) // 2 > len(have) or isinstance(value, bool):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        config = [[0, 0, 0] for _ in have]
        for i in range(len(pad) // 2):
            config[len(have) - 1 - i] = [int(pad[2 * i]), int(pad[2 * i + 1]), 0]
        return b.emit(
            "pad", [x, b.scalar(value, dtype)], dtype, shape, padding_config=config
        )
    if target == "aten.convolution.default":
        w = env[args[1]]
        bias, stride, padding, dilation, transposed, _, groups = args[2:9]
        if transposed:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        spatial = len(shape) - 2
        spec = list(range(spatial + 2))
        out = b.emit(
            "conv_general_dilated",
            [x, w],
            dtype,
            shape,
            batch_group_count=1,
            dimension_numbers=[spec, spec, spec],
            feature_group_count=groups,
            lhs_dilation=[1] * spatial,
            out_sharding=None,
            padding=[[p, p] for p in padding],
            precision=None,
            preferred_element_type=None,
            rhs_dilation=list(dilation),
            window_strides=list(stride),
        )
        if bias is not None:
            bvalue = b.emit(
                "broadcast_in_dim",
                [env[bias]],
                dtype,
                shape,
                broadcast_dimensions=[1],
                shape=shape,
                sharding=None,
            )
            out = b.emit("add", [out, bvalue], dtype, shape)
        return out
    raise graph.GraphRefused("aten_op_not_lowered", target)


def lower(program, *, allowlist):
    """The Carbon forward-graph document for a Core ATen program, and what
    lowering dropped (assertions with no result) and pruned (values no output
    depends on, such as constants that only those assertions read)."""
    import numpy as np
    from torch.export.graph_signature import InputKind

    b = _Builder(allowlist)
    specs = {s.arg.name: s for s in program.graph_signature.input_specs}
    state = {**program.state_dict, **program.constants}
    env, dropped, parameter_index = {}, collections.Counter(), 0
    for node in program.graph.nodes:
        if node.op == "placeholder":
            spec = specs[node.name]
            dtype, shape = _aval(node)
            if spec.kind == InputKind.PARAMETER:
                env[node] = b.input(f"params/{parameter_index}", dtype, shape)
                parameter_index += 1
            elif spec.kind == InputKind.USER_INPUT:
                env[node] = b.input(f"inputs/{node.name}", dtype, shape)
            elif spec.kind in (InputKind.BUFFER, InputKind.CONSTANT_TENSOR):
                env[node] = b.const(
                    np.asarray(state[spec.target].detach().cpu().numpy())
                )
            else:
                raise graph.GraphRefused("aten_input_kind_not_supported")
        elif node.op == "call_function":
            target = str(node.target)
            if allowlist.aten.get(target, {}).get("lowering") == "dropped":
                dropped[target] += 1
                continue
            env[node] = _emit(b, node, env)
        elif node.op == "output":
            outputs = [env[o] for o in node.args[0]]
        else:
            raise graph.GraphRefused("aten_node_kind_not_supported")
    doc = {
        "schema": graph.SCHEMA,
        "allowlist": allowlist.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": b.inputs,
                "constants": b.constants,
                "nodes": b.nodes,
                "outputs": outputs,
            }
        },
    }
    pruned = graph.prune(doc)
    graph.check_structure(doc)
    return doc, {"dropped_ops": dict(dropped), "pruned": pruned}
