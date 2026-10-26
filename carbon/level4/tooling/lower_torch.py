"""Lower a `torch.export` program (Core ATen) into the Carbon graph format.

In B' this, like `lower_jax`, runs on the miner's machine. It reads the
exported program in memory: no `torch.export` archive is ever deserialized
on a Carbon host. Each Core ATen op the allowlist's `aten_core` section admits
is written as Carbon ops (the same vocabulary JAX lowers to), so PyTorch and
JAX share one validator and one interpreter. An op without an emitter here is
refused (`aten_op_not_lowered`), and so is one the allowlist refuses.

Parameters become named graph inputs (Carbon feeds them); buffers and lifted
tensor constants become counted constants.

Limits a miner may meet (allowlist v6):

- `max_pool2d` is supported only with non-overlapping windows (stride equal
  to the kernel), 4-D input, no padding, dilation or `ceil_mode`, and no
  indices output. Anything else, `MaxPool2d(3, 2)` for one, is refused as
  `aten_arguments_not_supported`, a Carbon capability gap that does not count
  against the miner.
- Its gradients at exact ties inside a window are split as in JAX, not given
  to the first index as in torch. Carbon's rebuild trains through its own
  `reduce_max` on both backends, so this differs only from a miner's local
  torch training.
"""

from __future__ import annotations

import collections
import contextvars
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
#: Carbon dtypes the floating-only emitters (floor, fmod) admit.
_FLOATS = frozenset({"float32", "float64"})
#: Dtypes only the allowlist versions in `_WIDE_VERSIONS` admit (v8): the
#: narrow storage types graph.py carries. Older versions keep refusing them.
_WIDE_DTYPES = {
    "torch.float16": "float16",
    "torch.bfloat16": "bfloat16",
    "torch.int8": "int8",
    "torch.int16": "int16",
    "torch.uint8": "uint8",
}
_WIDE_VERSIONS = frozenset({"level4-allowlist-v8"})
#: Whether the program being lowered is for a version in `_WIDE_VERSIONS`;
#: set by `lower` for the span of one lowering.
_WIDE = contextvars.ContextVar("carbon_lower_torch_wide", default=False)
_HALVES = frozenset({"float16", "bfloat16"})
_INTS = frozenset({"int8", "int16", "int32", "uint8"})


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
    if name is None and _WIDE.get():
        name = _WIDE_DTYPES.get(str(value))
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

    def emit_many(self, op, ins, outs, /, **params):
        """One node with several results, `outs` a list of (dtype, shape)."""
        self.allowlist.admit(op, "forward", f"aten->{op}")
        values = [self._id(dtype, shape) for dtype, shape in outs]
        self.nodes.append(
            {
                "op": op,
                "in": list(ins),
                "out": [
                    {"value": value, "dtype": dtype, "shape": list(shape)}
                    for value, (dtype, shape) in zip(values, outs)
                ],
                "params": params,
            }
        )
        return values

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
        if _v8(b):
            # v8: any window (stride, padding, dilation, ceil mode) is a
            # reduce_window_max; the indices output stays refused.
            return _max_pool_window(b, node, env, 2)
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


def _area_scale(np_type, size_in, size_out, align_corners, scale):
    """torch's `area_pixel_compute_scale` in the op's scalar type."""
    if align_corners:
        return (
            np_type(size_in - 1) / np_type(size_out - 1) if size_out > 1 else np_type(0)
        )
    if scale is not None and scale > 0:
        return np_type(1.0 / scale)
    return np_type(size_in) / np_type(size_out)


def _aa_bicubic_matrix(b, dtype, size_in, size_out, scale):
    """The (size_out, size_in) antialiased bicubic weights of torch's
    `_compute_weights_aa` (Keys a = -0.5, support 2 * scale when shrinking),
    built in the graph from iota so no weight constant is embedded. Each row
    is the filter over its window [xmin, xmax), normalized by its sum."""
    import numpy as np

    key = (dtype, size_in, size_out, float(scale))
    cache = b.__dict__.setdefault("aa_bicubic", {})
    if key in cache:
        return cache[key]
    np_type = np.dtype(dtype).type
    # Both are computed in double and stored in the scalar type, as torch's.
    support = np_type(2.0 * float(scale)) if scale >= 1 else np_type(2.0)
    invscale = np_type(1.0 / float(scale)) if scale >= 1 else np_type(1.0)
    shape = [size_out, size_in]
    filled = {}

    def k(value, of=dtype):
        if (value, of) not in filled:
            filled[(value, of)] = b.broadcast(b.scalar(value, of), shape)
        return filled[(value, of)]

    def emit(op, ins, of=dtype, **params):
        return b.emit(op, ins, of, shape, **params)

    def ramp(axis):
        return emit("iota", [], dtype=dtype, dimension=axis, shape=shape, sharding=None)

    i, j = ramp(0), ramp(1)
    # center = scale * (i + 0.5): i + 0.5 is exact and the product of two
    # scalar-type values rounds once, as torch's double product stored back.
    center = emit("mul", [emit("add", [i, k(0.5)]), k(float(scale))], out_dtype=None)

    def truncated(op):
        # static_cast<int64_t>(center -+ support + 0.5), computed exactly in
        # the scalar type: floor(c) + (frac(c) >= 0.5). A negative sum gives
        # at most 0, which xmin's max with 0 then makes 0, as torch's.
        edge = emit(op, [center, k(support)])
        whole = emit("floor", [edge])
        up = emit("ge", [emit("sub", [edge, whole]), k(0.5)], "bool")
        return emit("add", [whole, emit("select_n", [up, k(0.0), k(1.0)])])

    xmin = emit("max", [truncated("sub"), k(0.0)])
    xmax = emit("min", [truncated("add"), k(float(size_in))])
    inside = emit(
        "and",
        [emit("ge", [j, xmin], "bool"), emit("lt", [j, xmax], "bool")],
        "bool",
    )
    # filter((j - center + 0.5) * invscale), in the scalar type; torch forms
    # the last two steps in double, so this argument may differ by an ulp
    # where the filter is smooth (its branches meet at |t| = 1 and 2).
    offset = emit("add", [emit("sub", [j, center]), k(0.5)])
    offset = emit("mul", [offset, k(float(invscale))], out_dtype=None)
    t = emit("abs", [offset])
    a = -0.5

    def mul(p, q):
        return emit("mul", [p, q], out_dtype=None)

    near = emit(
        "add",
        [mul(mul(emit("sub", [mul(k(a + 2), t), k(a + 3)]), t), t), k(1.0)],
    )
    far = emit(
        "sub",
        [
            mul(
                emit("add", [mul(emit("sub", [mul(k(a), t), k(5 * a)]), t), k(8 * a)]),
                t,
            ),
            k(4 * a),
        ],
    )
    value = emit(
        "select_n",
        [
            emit("lt", [t, k(1.0)], "bool"),
            emit("select_n", [emit("lt", [t, k(2.0)], "bool"), k(0.0), far]),
            near,
        ],
    )
    weight = emit("select_n", [inside, k(0.0), value])
    spec = b.allowlist.ops["reduce_sum"]["params"]
    total = b.emit(
        "reduce_sum",
        [weight],
        dtype,
        [size_out],
        axes=[1],
        **({"out_sharding": None} if "out_sharding" in spec else {}),
    )
    total = b.broadcast(
        b.emit(
            "reshape",
            [total],
            dtype,
            [size_out, 1],
            dimensions=None,
            new_sizes=[size_out, 1],
            sharding=None,
        ),
        shape,
    )
    # A row whose weights sum to 0 keeps them (torch skips the division).
    safe = emit("select_n", [emit("eq", [total, k(0.0)], "bool"), total, k(1.0)])
    cache[key] = emit("div", [weight, safe])
    return cache[key]


def _upsample_bicubic2d_aa(b, node, env):
    """Antialiased bicubic resize of an (N, C, H, W) floating tensor (CNO's
    up/down sampling): the separable weights of torch's AA kernel applied by
    dot_general along W, then H, as torch's separable kernel orders them. An
    axis whose size is unchanged is skipped, as torch skips it."""
    import numpy as np

    target = str(node.target)
    args = list(node.args) + [None] * (5 - len(node.args))
    x_arg, size, align_corners, scale_h, scale_w = args[:5]
    kw = node.kwargs
    align_corners = kw.get("align_corners", align_corners)
    scale_h, scale_w = kw.get("scales_h", scale_h), kw.get("scales_w", scale_w)
    if not hasattr(x_arg, "op") or type(align_corners) is not bool:
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    x = env[x_arg]
    dtype, have = b.avals[x]
    if (
        dtype not in _FLOATS
        or len(have) != 4
        or not isinstance(size, (list, tuple))
        or len(size) != 2
        or any(type(s) is not int or s < 1 for s in size)
        or any(
            s is not None and (type(s) not in (int, float) or not math.isfinite(s))
            for s in (scale_h, scale_w)
        )
        or _aval(node) != (dtype, have[:2] + list(size))
        # torch 2.13's kernel returns its first output row for every row when
        # it resizes H at width 1, unlike its own weights: refused, not copied.
        or (size[0] != have[2] and size[1] == 1)
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    np_type = np.dtype(dtype).type
    out = x
    for axis, size_out, given in ((3, size[1], scale_w), (2, size[0], scale_h)):
        size_in = b.avals[out][1][axis]
        if size_in == size_out:
            continue
        scale = _area_scale(np_type, size_in, size_out, align_corners, given)
        matrix = _aa_bicubic_matrix(b, dtype, size_in, size_out, scale)
        current = b.avals[out][1]
        free = [d for i, d in enumerate(current) if i != axis]
        out = b.emit(
            "dot_general",
            [out, matrix],
            dtype,
            free + [size_out],
            dimension_numbers=[[[axis], [1]], [[], []]],
            out_sharding=None,
            precision=None,
            preferred_element_type=dtype,
        )
        if axis != 3:
            order = list(range(axis)) + [3] + list(range(axis, 3))
            placed = list(current)
            placed[axis] = size_out
            out = b.emit("transpose", [out], dtype, placed, permutation=order)
    return out


def _slice_scatter_strided(b, node, env, dim, step):
    """slice_scatter with step > 1 (v7 form `strided`, MWT's even/odd
    interleave): the source placed every `step` along `dim` by an interior
    pad, and a padded mask selecting it over the base. Gradients: the base's
    outside the slice, the source's a strided slice of the result's."""
    target = str(node.target)
    args = node.args
    base, src = env[args[0]], env[args[1]]
    dtype, have = b.avals[base]
    start = args[3] if len(args) > 3 else None
    end = args[4] if len(args) > 4 else None
    if any(v is not None and type(v) is not int for v in (start, end)):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    first, _, _ = slice(start, end, step).indices(have[dim])
    count = len(range(*slice(start, end, step).indices(have[dim])))
    want = list(have)
    want[dim] = count
    if b.avals[src][1] != want or _aval(node) != (dtype, have):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    if count == 0:
        return base
    config = [[0, 0, 0] for _ in have]
    config[dim] = [first, have[dim] - first - (count - 1) * step - 1, step - 1]
    placed = b.emit(
        "pad",
        [b.to(src, dtype), b.scalar(0, dtype)],
        dtype,
        have,
        padding_config=config,
    )
    ones = b.broadcast(b.scalar(1, "int32"), want)
    mask = b.emit(
        "pad", [ones, b.scalar(0, "int32")], "int32", have, padding_config=config
    )
    mask = b.emit("gt", [mask, b.broadcast(b.scalar(0, "int32"), have)], "bool", have)
    return b.emit("select_n", [mask, base, placed], dtype, have)


def _convolution_transposed(b, node, env):
    """A transposed convolution (v7 form `transposed`, WNO-style): the direct
    convolution with lhs_dilation = stride, padding d * (k - 1) - p (plus the
    output padding on the high side), and the kernel flipped spatially with
    its input and output channels swapped within each group."""
    target = str(node.target)
    args = node.args
    x, w = env[args[0]], env[args[1]]
    bias, stride, padding, dilation, _, output_padding, groups = args[2:9]
    dtype, shape = _aval(node)
    wdtype, wshape = b.avals[w]
    spatial = len(shape) - 2
    if (
        wdtype != dtype
        or b.avals[x][0] != dtype
        or len(wshape) != spatial + 2
        or type(groups) is not int
        or groups < 1
        or wshape[0] % groups
        or any(
            len(v) != spatial or any(type(i) is not int for i in v)
            for v in (stride, padding, dilation, output_padding)
        )
        or any(s < 1 for s in stride)
        or any(d < 1 for d in dilation)
        or any(
            o < 0 or o >= max(s, d) for o, s, d in zip(output_padding, stride, dilation)
        )
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    c_in, c_out_group, kernel = wshape[0], wshape[1], wshape[2:]
    in_group = c_in // groups
    grouped = [groups, in_group, c_out_group, *kernel]
    w = b.emit(
        "reshape",
        [w],
        dtype,
        grouped,
        dimensions=None,
        new_sizes=grouped,
        sharding=None,
    )
    swapped = [groups, c_out_group, in_group, *kernel]
    w = b.emit(
        "transpose", [w], dtype, swapped, permutation=[0, 2, 1, *range(3, 3 + spatial)]
    )
    direct = [groups * c_out_group, in_group, *kernel]
    w = b.emit(
        "reshape", [w], dtype, direct, dimensions=None, new_sizes=direct, sharding=None
    )
    w = b.emit("rev", [w], dtype, direct, dimensions=list(range(2, 2 + spatial)))
    pads = [
        [d * (k - 1) - p, d * (k - 1) - p + o]
        for k, p, d, o in zip(kernel, padding, dilation, output_padding)
    ]
    spec = list(range(spatial + 2))
    out = b.emit(
        "conv_general_dilated",
        [x, w],
        dtype,
        shape,
        batch_group_count=1,
        dimension_numbers=[spec, spec, spec],
        feature_group_count=groups,
        lhs_dilation=list(stride),
        out_sharding=None,
        padding=pads,
        precision=None,
        preferred_element_type=None,
        rhs_dilation=list(dilation),
        window_strides=[1] * spatial,
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
    # v7 form `complex` (CODANO's spectral contraction): a complex sum in
    # its own dtype.
    complex_ok = (
        "complex" in _forms(b, target)
        and input_dtype == output_dtype
        and input_dtype in ("complex64", "complex128")
    )
    if (
        not complex_ok
        and (
            input_dtype not in ("float32", "float64")
            or output_dtype not in ("float32", "float64")
        )
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


def _over(b, cap, value):
    """Whether ``value`` exceeds ``b``'s allowlist cap ``cap``; an uncapped
    version has no node or intermediate cap (`allowlist.caps_for`), so the
    tooling's pre-checks mirror exactly what the validator will measure."""
    limit = allowlist_module.caps_for(b.allowlist).get(cap)
    return type(limit) is int and value > limit


def _constants_over(b, emitted_values, *, bits):
    """Whether the constants so far plus ``emitted_values`` more integers of
    ``bits`` bits each exceed the version's constants cap, measured as the
    validator will measure (`allowlist.accounting_for`): by information under
    accounting v4 (the emitted indices are below the scattered dimension's
    size), by value count under v3."""
    limit = allowlist_module.caps_for(b.allowlist).get("constant_bytes")
    if type(limit) is not int:
        return False
    accounting, _ = allowlist_module.accounting_for(b.allowlist)
    if accounting == allowlist_module.CONSTANT_ACCOUNTING_V4:
        extra = -(-emitted_values * bits // 8)
        return graph.constant_info_bytes(b.constants) + extra > limit
    return (
        graph.VALUE_BYTES * (graph.unique_constant_values(b.constants) + emitted_values)
        > limit
    )


def _forms(b, target):
    """The argument forms `b`'s allowlist admits for `target` (v7 on)."""
    return frozenset((b.allowlist.aten.get(target) or {}).get("forms", ()))


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
    if producer["op"] == "rem" and "integer" in _forms(b, "aten.fmod.Scalar"):
        # C-style integer remainder (v7), exact: np.fmod truncates as lax.rem.
        operands = [_static_array(b, v) for v in producer["in"]]
        if any(o is None for o in operands) or out["dtype"] != "int32":
            return None
        return np.fmod(*operands).astype(out["dtype"])
    if producer["op"] == "floor" and "static_outer" in _forms(b, "aten.index.Tensor"):
        # Exact; v7 on (the form's indices are floor(arange * scale) - k).
        source = _static_array(b, producer["in"][0])
        return None if source is None else np.floor(source).astype(out["dtype"])
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
    if index is None and _v8(b):
        # v8: indices that are an input run through the scatter_add primitive
        # (deterministic under the pinned GPU flags); one outside the tensor
        # is dropped, where torch raises.
        coords = _coordinates(b, index_value, dim, rank)
        dnums = _scatter_dnums([], range(rank), range(rank))
        return _scatter(b, "scatter_add", base, coords, source, dnums)
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
    bytes_per_result = math.prod(shape) * graph.itemsize(dtype)
    # The miner's own tensor first (a candidate refusal), then what only Carbon's
    # unrolling adds (a Carbon capability gap; Validator classes, 5cc80cbe8).
    if _over(b, "largest_intermediate_bytes", bytes_per_result):
        raise graph.GraphRefused("aten_scatter_registered_resource_bound", target)
    if _over(b, "nodes_executed", len(b.nodes) + nodes) or _constants_over(
        b, emitted_values, bits=max(1, (shape[dim] - 1).bit_length())
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
    if len(given) > 1 and "static_outer" in _forms(b, target):
        return _index_static_outer(b, node, env, given)
    if len(given) != 1 or not hasattr(given[0][1], "op"):
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    dim, index_node = given[0]
    return _take_static(b, node, env, args[0], dim, index_node, wrap=True)


def _index_static_outer(b, node, env, given):
    """`x[..., i0, i1, ...]` with several static int64 indices on adjacent
    dims that broadcast as an outer product (v7 form `static_outer`: index k
    varies only along broadcast axis k, as neuralop's grid interpolation
    `x[..., iy[:, None], ix]`). Torch places the broadcast shape where the
    indexed dims were; that is one static take per dim, in order, never a
    gather primitive."""
    import numpy as np

    target = str(node.target)
    x = env[node.args[0]]
    dtype, shape = b.avals[x]
    dims = [axis for axis, _ in given]
    if (
        any(not hasattr(i, "op") for _, i in given)
        or dims != list(range(dims[0], dims[0] + len(dims)))
        or dims[-1] >= len(shape)
    ):
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    arrays = []
    for dim, index_node in given:
        value = env[index_node]
        if (
            b.avals[value][0] != "int32"
            or str(getattr(index_node.meta.get("val"), "dtype", None)) != "torch.int64"
        ):
            raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
        static = _static_array(b, value)
        if static is None:
            raise graph.GraphRefused("aten_index_not_static", target)
        arrays.append(np.asarray(static, dtype=np.int64))
    try:
        broadcast = list(np.broadcast_shapes(*(a.shape for a in arrays)))
    except ValueError:
        raise graph.GraphRefused(
            "aten_index_shape_or_dtype_not_supported", target
        ) from None
    if len(broadcast) != len(arrays):
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    vectors = []
    for k, array in enumerate(arrays):
        full = np.broadcast_to(array, broadcast)
        line = np.moveaxis(full, k, 0).reshape(broadcast[k], -1)
        if not (line == line[:, :1]).all():  # varies along another axis
            raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
        size = shape[dims[k]]
        vector = [int(i) + size if int(i) < 0 else int(i) for i in line[:, 0]]
        if any(not 0 <= i < size for i in vector):
            raise graph.GraphRefused("aten_index_out_of_bounds", target)
        vectors.append(vector)
    expected = shape[: dims[0]] + broadcast + shape[dims[-1] + 1 :]
    if _aval(node) != (dtype, expected):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    out = x
    for k, vector in enumerate(vectors):
        partial = list(b.avals[out][1])
        partial[dims[k]] = len(vector)
        out = _take_runs(b, target, out, dims[k], vector, partial)
    return out


def _index_select(b, node, env):
    """`torch.index_select(x, dim, index)`: the same static take as
    `aten.index.Tensor` on one dimension (CODANO), with its bounds check and
    refusals. Unlike `x[index]`, torch refuses a negative index here, so it
    refuses as out of bounds instead of wrapping. Input-derived indices refuse."""
    target = str(node.target)
    args = node.args
    if (
        len(args) != 3
        or node.kwargs
        or not hasattr(args[0], "op")
        or type(args[1]) is not int
        or not hasattr(args[2], "op")
    ):
        raise graph.GraphRefused("aten_arguments_not_supported", target)
    rank = len(b.avals[env[args[0]]][1])
    if not -rank <= args[1] < rank:
        raise graph.GraphRefused("aten_index_shape_or_dtype_not_supported", target)
    return _take_static(
        b, node, env, args[0], _norm(args[1], rank), args[2], wrap=False
    )


def _take_static(b, node, env, x_node, dim, index_node, *, wrap):
    """`x` indexed by one captured int64 index on `dim`: one `slice` per run
    of consecutive indices and one `concatenate` (see `_index_static`).
    ``wrap`` admits torch's negative indices, as `x[index]` does."""
    target = str(node.target)
    x = env[x_node]
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
    if wrap:
        index = [i + size if i < 0 else i for i in index]
    if any(not 0 <= i < size for i in index):
        raise graph.GraphRefused("aten_index_out_of_bounds", target)
    return _take_runs(b, target, x, dim, index, expected)


def _take_runs(b, target, x, dim, index, expected):
    """`x` taken at the in-bounds static `index` on `dim`: one `slice` per run
    of consecutive indices and one `concatenate`."""
    dtype, shape = b.avals[x]
    runs = []  # [start, stop) of each run of consecutive indices
    for i in index:
        if runs and i == runs[-1][1]:
            runs[-1][1] += 1
        else:
            runs.append([i, i + 1])
    bytes_per_result = math.prod(expected) * graph.itemsize(dtype)
    if _over(b, "largest_intermediate_bytes", bytes_per_result):
        raise graph.GraphRefused("aten_index_registered_resource_bound", target)
    if "static_outer" in _forms(b, "aten.index.Tensor"):
        # v7 on: the slices and concatenates every take adds stay in the
        # graph, so they alone are held to the node cap here (v7 has none:
        # no model-size caps, so this guard is v7's only where a cap exists);
        # the static index arithmetic before them is pruned.
        added = b.__dict__.get("take_nodes", 0) + len(runs) + 1
        if _over(b, "nodes_executed", added):
            raise graph.GraphRefused("aten_index_lowering_expansion_bound", target)
        b.take_nodes = added
    elif _over(b, "nodes_executed", len(b.nodes) + len(runs) + 1):
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


# -- allowlist v8: the Core ATen forms the PyTorch route was missing ------------
#
# Every lowering below is reached only through an `aten_core` entry of an
# allowlist that lists the target (`_emit` refuses an unlisted one first), so
# v6 and v7, which list none of these targets, keep refusing them. Each is
# written in the Carbon ops the JAX route already uses; none adds a primitive.

#: Lowerings registered by `@_lowers`, keyed by ATen target.
_V8_LOWERINGS = {}


def _lowers(*targets):
    def register(function):
        for target in targets:
            _V8_LOWERINGS[target] = function
        return function

    return register


def _v8(b):
    """Whether `b`'s allowlist is one of the versions that widen the route."""
    return b.allowlist.version in _WIDE_VERSIONS


def _refuse(target, code="aten_arguments_not_supported"):
    raise graph.GraphRefused(code, target)


def _isfloat(dtype):
    return dtype in _FLOATS or (_WIDE.get() and dtype in _HALVES)


def _isint(dtype):
    return dtype in _INTS


def _arg(node, index, name, default=None):
    """Positional argument `index`, else keyword `name`, else `default`."""
    if len(node.args) > index:
        return node.args[index]
    return node.kwargs.get(name, default)


def _tensor(b, env, arg, target):
    if not hasattr(arg, "op"):
        _refuse(target)
    return env[arg]


def _avals(node):
    """(dtype, shape) of each result of `node` (a tuple result has several)."""
    val = node.meta["val"]
    items = val if isinstance(val, (tuple, list)) else (val,)
    return [(_dtype(v.dtype), [int(d) for d in v.shape]) for v in items]


#: Parameter kinds whose only value is the framework default.
_NULL_KINDS = frozenset({"none", "owned_single_device_sharding", "precision"})


def _fill_params(b, op, params):
    spec = b.allowlist.admit(op, "forward", f"aten->{op}")
    full = {name: None for name, kind in spec.items() if kind in _NULL_KINDS}
    full.update(params)
    return full


def _op(b, op, ins, dtype, shape, /, **params):
    """One node, with the op's inert defaults (sharding, accuracy) filled in."""
    return b.emit(op, ins, dtype, shape, **_fill_params(b, op, params))


def _op_many(b, op, ins, outs, /, **params):
    return b.emit_many(op, ins, outs, **_fill_params(b, op, params))


def _shape(b, value):
    return b.avals[value][1]


def _dt(b, value):
    return b.avals[value][0]


def _reshape(b, x, shape):
    dtype, have = b.avals[x]
    shape = [int(d) for d in shape]
    if have == shape:
        return x
    return _op(b, "reshape", [x], dtype, shape, dimensions=None, new_sizes=shape)


def _fill(b, value, dtype, shape):
    return b.broadcast(b.scalar(value, dtype), shape)


def _like(b, value, x):
    """A constant `value` in `x`'s dtype and shape."""
    dtype, shape = b.avals[x]
    return _fill(b, value, dtype, shape)


def _cmp(b, op, x, y):
    return _op(b, op, [x, y], "bool", _shape(b, x))


def _where(b, pred, yes, no):
    """`select_n` in torch's argument order (condition, true branch, false)."""
    return _op(b, "select_n", [pred, no, yes], _dt(b, yes), _shape(b, yes))


def _arith(b, op, x, y):
    return _op(b, op, [x, y], _dt(b, x), _shape(b, x))


def _times(b, x, y):
    return _op(b, "mul", [x, y], _dt(b, x), _shape(b, x))


def _iota(b, dtype, shape, dim):
    return _op(
        b, "iota", [], dtype, shape, dimension=dim, dtype=dtype, shape=list(shape)
    )


def _reduce(b, op, x, axes, keepdim=False):
    """`op` (reduce_sum, reduce_max, ...) over `axes`, optionally kept as 1."""
    dtype, shape = b.avals[x]
    axes = sorted(axes)
    kept = [d for i, d in enumerate(shape) if i not in axes]
    out = _op(b, op, [x], dtype, kept, axes=axes)
    if keepdim:
        out = _reshape(b, out, [1 if i in axes else d for i, d in enumerate(shape)])
    return out


def _slice(b, x, begin, end, strides=None):
    dtype, shape = b.avals[x]
    step = strides or [1] * len(shape)
    out = [max(0, -(-(e - s) // k)) for s, e, k in zip(begin, end, step)]
    return _op(
        b,
        "slice",
        [x],
        dtype,
        out,
        start_indices=list(begin),
        limit_indices=list(end),
        strides=None if strides is None else list(strides),
    )


def _slice_axis(b, x, axis, start, stop, step=1):
    shape = _shape(b, x)
    begin, end = [0] * len(shape), list(shape)
    begin[axis], end[axis] = start, stop
    strides = None
    if step != 1:
        strides = [1] * len(shape)
        strides[axis] = step
    return _slice(b, x, begin, end, strides)


def _concat(b, parts, axis):
    if len(parts) == 1:
        return parts[0]
    dtype, shape = b.avals[parts[0]]
    total = sum(_shape(b, p)[axis] for p in parts)
    out = list(shape)
    out[axis] = total
    return _op(b, "concatenate", parts, dtype, out, dimension=axis)


def _transpose(b, x, perm):
    dtype, shape = b.avals[x]
    if list(perm) == list(range(len(shape))):
        return x
    return _op(
        b, "transpose", [x], dtype, [shape[i] for i in perm], permutation=list(perm)
    )


def _bcast_dims(b, x, shape, dims):
    """`broadcast_in_dim` of `x` into `shape`, its axes landing on `dims`."""
    dtype, _ = b.avals[x]
    return _op(
        b,
        "broadcast_in_dim",
        [x],
        dtype,
        list(shape),
        broadcast_dimensions=list(dims),
        shape=list(shape),
    )


def _convert(b, x, dtype):
    return b.to(x, dtype)


def _dims_arg(dims, rank, target):
    """Normalized, distinct reduction axes (`None` or empty means all)."""
    if dims is None or isinstance(dims, int):
        dims = [] if dims is None else [dims]
    dims = list(dims)
    if any(type(d) is not int for d in dims):
        _refuse(target)
    if not dims:
        return list(range(rank))
    axes = [_norm(d, rank or 1) for d in dims]
    if any(not 0 <= a < max(rank, 1) for a in axes) or len(set(axes)) != len(axes):
        _refuse(target)
    return sorted(axes)


#: Order of dtypes for torch's result-type promotion of two tensors.
_RANK = {
    "bool": 0,
    "uint8": 1,
    "int8": 1,
    "int16": 2,
    "int32": 3,
    "float16": 4,
    "bfloat16": 4,
    "float32": 5,
    "float64": 6,
    "complex64": 7,
    "complex128": 8,
}


def _promote(*dtypes):
    best = dtypes[0]
    for dtype in dtypes[1:]:
        if _RANK[dtype] > _RANK[best]:
            best = dtype
        elif _RANK[dtype] == _RANK[best] and dtype != best:
            best = "float32" if dtype in _HALVES else "int16"
    return best


def _with_scalar(dtype, scalar, target):
    """The dtype torch compares or computes in when a Python scalar meets a
    tensor of `dtype`: the tensor's, unless the scalar is of a higher category."""
    if isinstance(scalar, bool):
        return dtype
    if isinstance(scalar, int):
        return dtype if dtype != "bool" else "int32"
    if isinstance(scalar, float):
        return dtype if _RANK[dtype] >= 4 else "float32"
    _refuse(target)


# -- elementwise ----------------------------------------------------------------

_UNARY_FLOAT = {
    "aten.erf.default": "erf",
    "aten.expm1.default": "expm1",
    "aten.rsqrt.default": "rsqrt",
    "aten.tan.default": "tan",
    "aten.asin.default": "asin",
    "aten.acos.default": "acos",
    "aten.atan.default": "atan",
    "aten.asinh.default": "asinh",
    "aten.acosh.default": "acosh",
    "aten.atanh.default": "atanh",
    "aten.sinh.default": "sinh",
    "aten.cosh.default": "cosh",
}


@_lowers(*_UNARY_FLOAT)
def _unary_float(b, node, env):
    """A floating elementwise function Carbon already has as one primitive
    (an integer input is promoted to the result's float dtype, as torch does)."""
    target = str(node.target)
    dtype, shape = _aval(node)
    if not _isfloat(dtype) or not hasattr(node.args[0], "op"):
        _refuse(target)
    x = b.to(env[node.args[0]], dtype)
    return _op(b, _UNARY_FLOAT[target], [x], dtype, shape)


@_lowers("aten.log2.default", "aten.log10.default")
def _log_base(b, node, env):
    """log(x) / log(base). torch's log2/log10 are their own kernels, so the
    last bits may differ (a few ulp)."""
    target = str(node.target)
    dtype, shape = _aval(node)
    if not _isfloat(dtype) or not hasattr(node.args[0], "op"):
        _refuse(target)
    x = b.to(env[node.args[0]], dtype)
    natural = _op(b, "log", [x], dtype, shape)
    base = 2.0 if target == "aten.log2.default" else 10.0
    return _arith(b, "div", natural, _fill(b, math.log(base), dtype, shape))


@_lowers("aten.atan2.default")
def _atan2(b, node, env):
    dtype, _ = _aval(node)
    if not _isfloat(dtype):
        _refuse(str(node.target))
    return b.binary("atan2", node.args[0], node.args[1], env, node)


@_lowers("aten.maximum.default", "aten.minimum.default")
def _maximum_minimum(b, node, env):
    """max / min: both propagate NaN, and a tie splits the gradient in half, as
    torch's maximum and minimum do."""
    target = str(node.target)
    dtype, _ = _aval(node)
    if dtype == "bool" or not all(hasattr(a, "op") for a in node.args[:2]):
        _refuse(target)
    op = "max" if target == "aten.maximum.default" else "min"
    return b.binary(op, node.args[0], node.args[1], env, node)


@_lowers("aten.ceil.default", "aten.trunc.default", "aten.round.default")
def _round_family(b, node, env):
    target = str(node.target)
    dtype, shape = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = env[arg]
    if _isint(dtype) and b.avals[x][0] == dtype:
        return x  # integers are already whole
    if not _isfloat(dtype) or b.avals[x][0] != dtype:
        _refuse(target)
    if target == "aten.ceil.default":
        return _op(b, "ceil", [x], dtype, shape)
    if target == "aten.round.default":
        return _op(b, "round", [x], dtype, shape, rounding_method="TO_NEAREST_EVEN")
    below = _cmp(b, "lt", x, _like(b, 0, x))
    # trunc: toward zero, as floor for x >= 0 and ceil for x < 0 (-0.0 stays).
    return _where(
        b,
        below,
        _op(b, "ceil", [x], dtype, shape),
        _op(b, "floor", [x], dtype, shape),
    )


@_lowers("aten.round.decimals")
def _round_decimals(b, node, env):
    """torch's own rule: round(x * 10**d) / 10**d, or for d < 0 the same with
    the scale on the other side, rounding half to even."""
    import numpy as np

    target = str(node.target)
    dtype, shape = _aval(node)
    decimals = _arg(node, 1, "decimals")
    if (
        not _isfloat(dtype)
        or not hasattr(node.args[0], "op")
        or type(decimals) is not int
        or b.avals[env[node.args[0]]][0] != dtype
    ):
        _refuse(target)
    x = env[node.args[0]]
    scale = float(np.power(np.dtype(dtype).type(10), abs(decimals)))
    k = _fill(b, scale, dtype, shape)
    if decimals < 0:
        scaled = _op(b, "div", [x, k], dtype, shape)
    else:
        scaled = _times(b, x, k)
    rounded = _op(b, "round", [scaled], dtype, shape, rounding_method="TO_NEAREST_EVEN")
    if decimals < 0:
        return _times(b, rounded, k)
    return _op(b, "div", [rounded, k], dtype, shape)


@_lowers("aten.isnan.default", "aten.isinf.default")
def _isnan_isinf(b, node, env):
    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = env[arg]
    dtype = _dt(b, x)
    if dtype.startswith("complex"):
        _refuse(target)
    if not _isfloat(dtype):
        return _fill(b, False, "bool", shape)
    if target == "aten.isnan.default":
        return _cmp(b, "ne", x, x)
    magnitude = _op(b, "abs", [x], dtype, shape)
    return _cmp(b, "eq", magnitude, _like(b, math.inf, x))


@_lowers("aten.eq.Tensor", "aten.ne.Scalar", "aten.ne.Tensor")
def _compare(b, node, env):
    target = str(node.target)
    op = target.split(".")[1]
    x_arg, y_arg = node.args[:2]
    if not hasattr(x_arg, "op"):
        _refuse(target)
    first = _dt(b, env[x_arg])
    if hasattr(y_arg, "op"):
        operand = _promote(first, _dt(b, env[y_arg]))
    else:
        operand = _with_scalar(first, y_arg, target)
    return b.binary(op, x_arg, y_arg, env, node, out_dtype=operand)


def _bool_mask(b, x):
    """`x != 0` (a bool tensor is its own mask)."""
    if _dt(b, x) == "bool":
        return x
    return _cmp(b, "ne", x, _like(b, 0, x))


@_lowers(
    "aten.logical_and.default", "aten.logical_or.default", "aten.logical_xor.default"
)
def _logical(b, node, env):
    target = str(node.target)
    _, shape = _aval(node)
    if not all(hasattr(a, "op") for a in node.args[:2]):
        _refuse(target)
    op = target.split(".")[1].split("_")[1]  # logical_and -> and
    x, y = (_bool_mask(b, b.broadcast(env[a], shape)) for a in node.args[:2])
    return _op(b, op, [x, y], "bool", shape)


@_lowers(
    "aten.bitwise_and.Scalar",
    "aten.bitwise_or.Tensor",
    "aten.bitwise_or.Scalar",
    "aten.bitwise_xor.Tensor",
    "aten.bitwise_xor.Scalar",
)
def _bitwise_binary(b, node, env):
    return _bitwise(b, node, env, str(node.target).split(".")[1].split("_")[1])


def _bitwise(b, node, env, name):
    """`and`, `or`, `xor` of two integer or boolean operands."""
    target = str(node.target)
    dtype, _ = _aval(node)
    if (dtype != "bool" and not _isint(dtype)) or not hasattr(node.args[0], "op"):
        _refuse(target)
    first = _dt(b, env[node.args[0]])
    if first != dtype:
        _refuse(target)
    return b.binary(name, node.args[0], node.args[1], env, node)


@_lowers("aten.bitwise_not.default")
def _bitwise_not(b, node, env):
    target = str(node.target)
    dtype, shape = _aval(node)
    if (dtype != "bool" and not _isint(dtype)) or not hasattr(node.args[0], "op"):
        _refuse(target)
    return _op(b, "not", [env[node.args[0]]], dtype, shape)


@_lowers(
    "aten.__lshift__.Scalar",
    "aten.__lshift__.Tensor",
    "aten.__rshift__.Scalar",
    "aten.__rshift__.Tensor",
)
def _shifts(b, node, env):
    """Left shift, and right shift that keeps the sign (logical on unsigned);
    a count beyond the width gives 0 (or the sign fill), as in torch."""
    target = str(node.target)
    dtype, _ = _aval(node)
    if not _isint(dtype) or not hasattr(node.args[0], "op"):
        _refuse(target)
    if "lshift" in target:
        op = "shift_left"
    else:
        op = (
            "shift_right_logical"
            if dtype.startswith("uint")
            else "shift_right_arithmetic"
        )
    return b.binary(op, node.args[0], node.args[1], env, node)


@_lowers("aten.clamp.Tensor")
def _clamp_tensor(b, node, env):
    """clamp with tensor bounds: selects, not max/min, so the gradient reaches
    x where low <= x <= high (torch's rule); the bounds get theirs where they
    clamp."""
    target = str(node.target)
    dtype, shape = _aval(node)
    low, high = _arg(node, 1, "min"), _arg(node, 2, "max")
    if (low is None and high is None) or not hasattr(node.args[0], "op"):
        _refuse(target)
    out = b.operand(node.args[0], env, dtype, shape)
    for bound, op in ((low, "lt"), (high, "gt")):
        if bound is None:
            continue
        limit = b.operand(bound, env, dtype, shape)
        out = _where(b, _cmp(b, op, out, limit), limit, out)
    return out


@_lowers("aten.hardtanh.default")
def _hardtanh(b, node, env):
    """clamp(x, low, high) whose gradient is 0 at the bounds (torch's
    hardtanh backward is strict), so relu6 and hardtanh agree with torch."""
    target = str(node.target)
    dtype, shape = _aval(node)
    low, high = _arg(node, 1, "min_val", -1.0), _arg(node, 2, "max_val", 1.0)
    if (
        not _isfloat(dtype)
        or not hasattr(node.args[0], "op")
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in (low, high)
        )
    ):
        _refuse(target)
    out = b.to(env[node.args[0]], dtype)
    for bound, op in ((low, "le"), (high, "ge")):
        out = _where(
            b,
            _cmp(b, op, out, _fill(b, bound, dtype, shape)),
            _fill(b, bound, dtype, shape),
            out,
        )
    return out


@_lowers("aten.fill.Scalar")
def _fill_scalar(b, node, env):
    target = str(node.target)
    dtype, shape = _aval(node)
    value = node.args[1]
    if isinstance(value, bool) is False and not isinstance(value, (int, float)):
        _refuse(target)
    return _fill(b, value, dtype, shape)


@_lowers("aten.scalar_tensor.default")
def _scalar_tensor(b, node, env):
    target = str(node.target)
    dtype, shape = _aval(node)
    value = node.args[0]
    if shape or not isinstance(value, (bool, int, float)):
        _refuse(target)
    return b.scalar(value, dtype)


@_lowers(
    "aten.remainder.Scalar", "aten.remainder.Tensor", "aten.remainder.Scalar_Tensor"
)
def _remainder(b, node, env):
    """Python-style modulo (the divisor's sign): C-style `rem`, plus the
    divisor where the remainder is nonzero and its sign differs from the
    divisor's. d/dx = 1; d/dy = -floor(x / y), as torch's."""
    target = str(node.target)
    dtype, shape = _aval(node)
    if dtype == "bool" or not (_isfloat(dtype) or _isint(dtype)):
        _refuse(target)
    x = b.operand(node.args[0], env, dtype, shape)
    y = b.operand(node.args[1], env, dtype, shape)
    mod = _arith(b, "rem", x, y)
    zero = _fill(b, 0, dtype, shape)
    differ = _cmp(b, "ne", _cmp(b, "lt", y, zero), _cmp(b, "lt", mod, zero))
    fix = _op(b, "and", [_cmp(b, "ne", mod, zero), differ], "bool", shape)
    return _where(b, fix, _arith(b, "add", mod, y), mod)


@_lowers("aten.div.Tensor_mode", "aten.div.Scalar_mode")
def _div_mode(b, node, env):
    """Division rounded toward zero (`trunc`) or down (`floor`). Float floor
    follows c10's own sequence (fmod, then a correction), not floor(x / y),
    which can round the quotient across an integer. An integer divisor of 0 is
    not checked (XLA gives -1; torch raises)."""
    target = str(node.target)
    dtype, shape = _aval(node)
    mode = node.kwargs.get(
        "rounding_mode", node.args[2] if len(node.args) > 2 else None
    )
    if mode not in ("floor", "trunc") or not (_isfloat(dtype) or _isint(dtype)):
        _refuse(target)
    x = b.operand(node.args[0], env, dtype, shape)
    y = b.operand(node.args[1], env, dtype, shape)
    quotient = _arith(b, "div", x, y)
    zero = _fill(b, 0, dtype, shape)
    if _isint(dtype):
        if mode == "trunc":
            return quotient
        remainder = _arith(b, "rem", x, y)
        differ = _cmp(b, "ne", _cmp(b, "lt", remainder, zero), _cmp(b, "lt", y, zero))
        adjust = _op(b, "and", [_cmp(b, "ne", remainder, zero), differ], "bool", shape)
        return _where(
            b, adjust, _arith(b, "sub", quotient, _fill(b, 1, dtype, shape)), quotient
        )
    if mode == "trunc":
        return _where(
            b,
            _cmp(b, "lt", quotient, zero),
            _op(b, "ceil", [quotient], dtype, shape),
            _op(b, "floor", [quotient], dtype, shape),
        )
    one = _fill(b, 1, dtype, shape)
    mod = _arith(b, "rem", x, y)
    div = _arith(b, "div", _arith(b, "sub", x, mod), y)
    differ = _cmp(b, "ne", _cmp(b, "lt", y, zero), _cmp(b, "lt", mod, zero))
    fix = _op(b, "and", [_cmp(b, "ne", mod, zero), differ], "bool", shape)
    div = _where(b, fix, _arith(b, "sub", div, one), div)
    floored = _op(b, "floor", [div], dtype, shape)
    up = _cmp(b, "gt", _arith(b, "sub", div, floored), _fill(b, 0.5, dtype, shape))
    floored = _where(b, up, _arith(b, "add", floored, one), floored)
    signed_zero = _times(b, quotient, zero)  # copysign(0, x / y)
    result = _where(b, _cmp(b, "ne", div, zero), floored, signed_zero)
    return _where(b, _cmp(b, "eq", y, zero), quotient, result)


@_lowers("aten.pow.Tensor_Scalar", "aten.pow.Scalar", "aten.pow.Tensor_Tensor")
def _pow(b, node, env):
    """x ** y. A whole-number exponent of a float is `integer_pow` (torch
    multiplies for 2 and 3 too); any other exponent is the `pow` primitive, so
    a negative base with a fractional exponent is NaN in both."""
    target = str(node.target)
    dtype, shape = _aval(node)
    base, exponent = node.args[:2]
    if not (_isfloat(dtype) or _isint(dtype)):
        _refuse(target)
    if target == "aten.pow.Tensor_Scalar":
        if isinstance(exponent, bool) or not isinstance(exponent, (int, float)):
            _refuse(target)
        x = b.operand(base, env, dtype, shape)
        whole = float(exponent).is_integer() and abs(exponent) <= 16
        if whole and (_isfloat(dtype) or exponent >= 0):
            return _op(b, "integer_pow", [x], dtype, shape, y=int(exponent))
        if not _isfloat(dtype):
            _refuse(target)
        return _arith(b, "pow", x, _fill(b, exponent, dtype, shape))
    if not _isfloat(dtype):
        _refuse(target)
    return _arith(
        b,
        "pow",
        b.operand(base, env, dtype, shape),
        b.operand(exponent, env, dtype, shape),
    )


@_lowers("aten.elu.default")
def _elu(b, node, env):
    """scale * x for x > 0, else scale * alpha * expm1(input_scale * x); the
    gradient at 0 takes the negative branch, as torch's."""
    target = str(node.target)
    dtype, shape = _aval(node)
    alpha = _arg(node, 1, "alpha", 1.0)
    scale = _arg(node, 2, "scale", 1.0)
    input_scale = _arg(node, 3, "input_scale", 1.0)
    if (
        not _isfloat(dtype)
        or not hasattr(node.args[0], "op")
        or any(
            not isinstance(v, (int, float)) or isinstance(v, bool)
            for v in (alpha, scale, input_scale)
        )
    ):
        _refuse(target)
    x = b.to(env[node.args[0]], dtype)

    def scaled(value, factor):
        return (
            value if factor == 1 else _times(b, value, _fill(b, factor, dtype, shape))
        )

    negative = scaled(
        _op(b, "expm1", [scaled(x, input_scale)], dtype, shape), alpha * scale
    )
    return _where(b, _cmp(b, "gt", x, _like(b, 0, x)), scaled(x, scale), negative)


# -- reductions ---------------------------------------------------------------


@_lowers("aten.amax.default", "aten.amin.default")
def _amax_amin(b, node, env):
    """reduce_max / reduce_min; a tie shares the gradient evenly (torch's amax
    rule). An empty `dim` reduces every axis."""
    target = str(node.target)
    dtype, _ = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op") or dtype == "bool" or dtype.startswith("complex"):
        _refuse(target)
    x = env[arg]
    rank = len(_shape(b, x))
    keepdim = _arg(node, 2, "keepdim", False)
    if type(keepdim) is not bool or rank == 0:
        _refuse(target)
    axes = _dims_arg(_arg(node, 1, "dim", []), rank, target)
    op = "reduce_max" if target == "aten.amax.default" else "reduce_min"
    return _reduce(b, op, x, axes, keepdim)


@_lowers("aten.max.default", "aten.min.default")
def _max_min_all(b, node, env):
    target = str(node.target)
    arg = node.args[0]
    if (
        not hasattr(arg, "op")
        or _dt(b, env[arg]) in ("bool",)
        or node.meta["val"].shape != ()
    ):
        _refuse(target)
    x = env[arg]
    op = "reduce_max" if target == "aten.max.default" else "reduce_min"
    return _reduce(b, op, x, list(range(len(_shape(b, x)))))


@_lowers("aten.any.default", "aten.any.dims")
def _any(b, node, env):
    """Any nonzero element: reduce_or of the mask."""
    target = str(node.target)
    dtype, _ = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = env[arg]
    rank = len(_shape(b, x))
    keepdim = _arg(node, 2, "keepdim", False) if target.endswith("dims") else False
    if type(keepdim) is not bool or rank == 0:
        _refuse(target)
    dims = _arg(node, 1, "dim", None) if target.endswith("dims") else None
    axes = _dims_arg(dims, rank, target)
    out = _reduce(b, "reduce_or", _bool_mask(b, x), axes, keepdim)
    return b.to(out, dtype)


@_lowers("aten.argmax.default", "aten.argmin.default")
def _argmax_argmin(b, node, env):
    """Index of the first extreme (a NaN is the largest, as in torch). `dim`
    None looks at the flattened tensor."""
    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = env[arg]
    xd, have = b.avals[x]
    keepdim = _arg(node, 2, "keepdim", False)
    dim = _arg(node, 1, "dim", None)
    if type(keepdim) is not bool or not (_isfloat(xd) or _isint(xd)) or 0 in have:
        _refuse(target)
    if dim is None:
        x, axis = _reshape(b, x, [math.prod(have)]), 0
    elif type(dim) is int and have and -len(have) <= dim < len(have):
        axis = _norm(dim, len(have))
    else:
        _refuse(target)
    op = "argmax" if target == "aten.argmax.default" else "argmin"
    kept = [d for i, d in enumerate(_shape(b, x)) if i != axis]
    out = _op(b, op, [x], "int32", kept, axes=[axis], index_dtype="int32")
    return _reshape(b, out, shape)


@_lowers("aten.max.dim", "aten.min.dim")
def _max_min_dim(b, node, env):
    """(values, indices) along one dim. The values are reduce_max/min, so a
    tie shares the gradient (torch gives it to the chosen index)."""
    target = str(node.target)
    arg = node.args[0]
    if not hasattr(arg, "op") or type(node.args[1]) is not int:
        _refuse(target)
    x = env[arg]
    xd, have = b.avals[x]
    keepdim = _arg(node, 2, "keepdim", False)
    if (
        type(keepdim) is not bool
        or not have
        or xd == "bool"
        or xd.startswith("complex")
    ):
        _refuse(target)
    if not -len(have) <= node.args[1] < len(have) or 0 in have:
        _refuse(target)
    axis = _norm(node.args[1], len(have))
    op = "reduce_max" if target == "aten.max.dim" else "reduce_min"
    values = _reduce(b, op, x, [axis], keepdim)
    arg_op = "argmax" if target == "aten.max.dim" else "argmin"
    kept = [d for i, d in enumerate(have) if i != axis]
    index = _op(b, arg_op, [x], "int32", kept, axes=[axis], index_dtype="int32")
    if keepdim:
        index = _reshape(b, index, [1 if i == axis else d for i, d in enumerate(have)])
    return (values, index)


@_lowers("aten.prod.default", "aten.prod.dim_int")
def _prod(b, node, env):
    """reduce_prod; a zero in the product keeps a finite gradient, as torch's."""
    target = str(node.target)
    dtype, _ = _aval(node)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = b.to(env[arg], dtype)
    rank = len(_shape(b, x))
    if dtype.startswith("complex") or dtype == "bool" or rank == 0:
        _refuse(target)
    keepdim = False
    axes = list(range(rank))
    if target.endswith("dim_int"):
        keepdim = _arg(node, 2, "keepdim", False)
        dim = node.args[1]
        if type(keepdim) is not bool or type(dim) is not int or not -rank <= dim < rank:
            _refuse(target)
        axes = [_norm(dim, rank)]
    return _reduce(b, "reduce_prod", x, axes, keepdim)


@_lowers("aten.cumsum.default", "aten.cumprod.default", "aten.logcumsumexp.default")
def _cumulative(b, node, env):
    """A running sum / product / log-sum-exp along one dim, in the result's
    dtype (an integer or boolean input becomes int, as torch's)."""
    target = str(node.target)
    dtype, shape = _aval(node)
    arg = node.args[0]
    dim = node.args[1] if len(node.args) > 1 else node.kwargs.get("dim")
    if not hasattr(arg, "op") or type(dim) is not int or dtype.startswith("complex"):
        _refuse(target)
    x = b.to(env[arg], dtype)
    rank = len(shape)
    if rank == 0:
        return x
    if not -rank <= dim < rank:
        _refuse(target)
    op = {"cumsum": "cumsum", "cumprod": "cumprod", "logcumsumexp": "cumlogsumexp"}[
        target.split(".")[1]
    ]
    return _op(b, op, [x], dtype, shape, axis=_norm(dim, rank), reverse=False)


@_lowers("aten.var.dim")
def _var_dim(b, node, env):
    """var(x, dim, unbiased, keepdim): the correction form's arithmetic."""
    target = str(node.target)
    dtype, _ = _aval(node)
    arg = node.args[0]
    unbiased = _arg(node, 2, "unbiased", True)
    keepdim = _arg(node, 3, "keepdim", False)
    if (
        not hasattr(arg, "op")
        or type(unbiased) is not bool
        or type(keepdim) is not bool
        or not _isfloat(dtype)
    ):
        _refuse(target)
    x = env[arg]
    rank = len(_shape(b, x))
    axes = _dims_arg(_arg(node, 1, "dim", None), rank, target)
    count = math.prod(_shape(b, x)[a] for a in axes)
    centred = _arith(b, "sub", x, b.broadcast(_mean_kept(b, x, axes), _shape(b, x)))
    squares = _op(b, "integer_pow", [centred], dtype, _shape(b, x), y=2)
    total = _reduce(b, "reduce_sum", squares, axes, keepdim)
    divisor = count - (1 if unbiased else 0)
    return _arith(b, "div", total, _fill(b, divisor, dtype, _shape(b, total)))


def _mean_kept(b, x, axes):
    dtype = _dt(b, x)
    total = _reduce(b, "reduce_sum", x, axes, keepdim=True)
    count = math.prod(_shape(b, x)[a] for a in axes)
    return _arith(b, "div", total, _fill(b, count, dtype, _shape(b, total)))


# -- shapes, selection and indexing ---------------------------------------------


@_lowers("aten.flip.default")
def _flip(b, node, env):
    target = str(node.target)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    x = env[arg]
    dtype, shape = b.avals[x]
    dims = _dims_arg(list(node.args[1]), len(shape), target) if node.args[1] else []
    if not dims:
        return x
    return _op(b, "rev", [x], dtype, shape, dimensions=dims)


@_lowers("aten.diagonal.default")
def _diagonal(b, node, env):
    """The diagonal as the last axis: transpose the two dims last, flatten
    them, and take one strided slice (stride width + 1) from the offset."""
    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    offset = _arg(node, 1, "offset", 0)
    if not hasattr(arg, "op") or type(offset) is not int:
        _refuse(target)
    x = env[arg]
    have = _shape(b, x)
    rank = len(have)
    d1, d2 = _arg(node, 2, "dim1", 0), _arg(node, 3, "dim2", 1)
    if rank < 2 or any(type(d) is not int or not -rank <= d < rank for d in (d1, d2)):
        _refuse(target)
    d1, d2 = _norm(d1, rank), _norm(d2, rank)
    if d1 == d2 or not shape or shape[-1] < 1:
        _refuse(target)
    rest = [i for i in range(rank) if i not in (d1, d2)]
    moved = _transpose(b, x, rest + [d1, d2])
    rows, cols = have[d1], have[d2]
    batch = [have[i] for i in rest]
    flat = _reshape(b, moved, batch + [rows * cols])
    start = offset if offset >= 0 else -offset * cols
    length = shape[-1]
    last = start + (length - 1) * (cols + 1) + 1
    if last > rows * cols:
        _refuse(target)
    axis = len(batch)
    out = _slice_axis(b, flat, axis, start, last, cols + 1)
    return _reshape(b, out, shape)


@_lowers("aten.select_scatter.default")
def _select_scatter(b, node, env):
    """`base` with the slice at `index` of `dim` replaced by `src`."""
    target = str(node.target)
    dtype, shape = _aval(node)
    base, src, dim, index = node.args[:4]
    if not (hasattr(base, "op") and hasattr(src, "op")) or type(dim) is not int:
        _refuse(target)
    rank = len(shape)
    if not -rank <= dim < rank or type(index) is not int:
        _refuse(target)
    dim = _norm(dim, rank)
    if not -shape[dim] <= index < shape[dim]:
        _refuse(target)
    index = index % shape[dim]
    mask = _cmp(
        b,
        "eq",
        _iota(b, "int32", shape, dim),
        _fill(b, index, "int32", shape),
    )
    kept = [i for i in range(rank) if i != dim]
    placed = _bcast_dims(b, b.to(env[src], dtype), shape, kept)
    return _where(b, mask, placed, b.to(env[base], dtype))


def _coordinates(b, index, dim, rank):
    """int32 `index.shape + [rank]`: each element's position in a tensor of
    `rank` axes whose `dim` coordinate is the element itself (torch's
    gather/scatter addressing)."""
    shape = _shape(b, index)
    parts = []
    for axis in range(rank):
        piece = index if axis == dim else _iota(b, "int32", shape, axis)
        parts.append(_reshape(b, piece, shape + [1]))
    return _concat(b, parts, rank)


def _gather_dnums(offset, collapsed, start_map, operand_batch=(), indices_batch=()):
    return {
        "offset_dims": list(offset),
        "collapsed_slice_dims": list(collapsed),
        "start_index_map": list(start_map),
        "operand_batching_dims": list(operand_batch),
        "start_indices_batching_dims": list(indices_batch),
    }


def _scatter_dnums(window, inserted, to_operand):
    return {
        "update_window_dims": list(window),
        "inserted_window_dims": list(inserted),
        "scatter_dims_to_operand_dims": list(to_operand),
        "operand_batching_dims": [],
        "scatter_indices_batching_dims": [],
    }


def _fill_for(dtype):
    """What an out-of-range gather reads in FILL_OR_DROP mode: NaN for a float,
    the minimum for an integer (JAX's own default, which the primitive needs
    spelled out)."""
    import numpy as np

    if dtype in _FLOATS or dtype in _HALVES:
        return "nan"
    if dtype in ("bool", "complex64", "complex128"):
        _refuse("aten.gather")
    return int(np.iinfo(dtype).min)


def _gather(b, operand, indices, dnums, slice_sizes, out_shape, mode):
    dtype = _dt(b, operand)
    return _op(
        b,
        "gather",
        [operand, indices],
        dtype,
        out_shape,
        dimension_numbers=dnums,
        fill_value=_fill_for(dtype) if mode == "FILL_OR_DROP" else None,
        indices_are_sorted=False,
        mode=mode,
        slice_sizes=list(slice_sizes),
        unique_indices=False,
    )


def _scatter(b, op, operand, indices, updates, dnums, mode="FILL_OR_DROP"):
    params = {
        "dimension_numbers": dnums,
        "indices_are_sorted": False,
        "mode": mode,
        "unique_indices": False,
        "update_consts": [],
        "update_jaxpr": None,
    }
    dtype, shape = b.avals[operand]
    return _op(b, op, [operand, indices, updates], dtype, shape, **params)


def _index_arg(b, env, arg, target):
    """An int index tensor (torch's int64 is int32 here)."""
    value = _tensor(b, env, arg, target)
    if _dt(b, value) != "int32":
        _refuse(target)
    return value


def _element_scatter(b, node, env, op, source):
    """The scatter/gather of `dim` addressing: `self[index] = source` (source
    given as updates already shaped like `index`). An index outside the
    tensor is dropped, never wrapped; torch raises."""
    target = str(node.target)
    dtype, shape = _aval(node)
    rank = len(shape)
    dim = node.args[1]
    if type(dim) is not int or rank == 0 or not -rank <= dim < rank:
        _refuse(target)
    dim = _norm(dim, rank)
    index = _index_arg(b, env, node.args[2], target)
    ishape = _shape(b, index)
    if len(ishape) != rank or any(
        ishape[a] > shape[a] for a in range(rank) if a != dim
    ):
        _refuse(target)
    updates = source(ishape)
    coords = _coordinates(b, index, dim, rank)
    dnums = _scatter_dnums([], range(rank), range(rank))
    base = b.to(env[node.args[0]], dtype)
    return _scatter(b, op, base, coords, updates, dnums)


@_lowers("aten.scatter.src")
def _scatter_src(b, node, env):
    target = str(node.target)
    dtype, _ = _aval(node)
    if not hasattr(node.args[3], "op") or not hasattr(node.args[0], "op"):
        _refuse(target)
    src = b.to(env[node.args[3]], dtype)

    def updates(ishape):
        have = _shape(b, src)
        if len(have) != len(ishape) or any(h < i for h, i in zip(have, ishape)):
            _refuse(target)
        return _slice(b, src, [0] * len(ishape), ishape) if have != ishape else src

    return _element_scatter(b, node, env, "scatter", updates)


@_lowers("aten.scatter.value")
def _scatter_value(b, node, env):
    target = str(node.target)
    dtype, _ = _aval(node)
    value = node.args[3]
    if not hasattr(node.args[0], "op") or not isinstance(value, (bool, int, float)):
        _refuse(target)
    return _element_scatter(
        b, node, env, "scatter", lambda ishape: _fill(b, value, dtype, ishape)
    )


@_lowers("aten.gather.default")
def _gather_element(b, node, env):
    """`out[i][j][k] = self[index[i][j][k]][j][k]` (for dim 0). An index
    outside the tensor reads NaN (integers: the minimum), never wraps; torch
    raises."""
    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    dim = node.args[1]
    if not hasattr(arg, "op") or type(dim) is not int:
        _refuse(target)
    x = env[arg]
    have = _shape(b, x)
    rank = len(have)
    if rank == 0 or not -rank <= dim < rank:
        _refuse(target)
    index = _index_arg(b, env, node.args[2], target)
    dim = _norm(dim, rank)
    if len(_shape(b, index)) != rank or any(
        i > h for a, (i, h) in enumerate(zip(_shape(b, index), have)) if a != dim
    ):
        _refuse(target)
    coords = _coordinates(b, index, dim, rank)
    dnums = _gather_dnums([], range(rank), range(rank))
    return _gather(b, x, coords, dnums, [1] * rank, shape, "FILL_OR_DROP")


def _take_axis(b, x, axis, index, mode="PROMISE_IN_BOUNDS"):
    """`x` indexed by the 1-D int32 `index` along `axis`."""
    _, have = b.avals[x]
    count = _shape(b, index)[0]
    out = list(have)
    out[axis] = count
    sizes = list(have)
    sizes[axis] = 1
    dnums = _gather_dnums([i for i in range(len(have)) if i != axis], [axis], [axis])
    return _gather(b, x, _reshape(b, index, [count, 1]), dnums, sizes, out, mode)


@_lowers("aten.embedding.default")
def _embedding(b, node, env):
    """Rows of `weight` for each index. An index outside the table reads NaN
    rows; a `padding_idx` row gets no gradient, as torch's."""
    target = str(node.target)
    dtype, shape = _aval(node)
    weight = _tensor(b, env, node.args[0], target)
    index = _index_arg(b, env, node.args[1], target)
    padding = _arg(node, 2, "padding_idx", -1)
    wshape = _shape(b, weight)
    if len(wshape) != 2 or type(padding) is not int or not _isfloat(dtype):
        _refuse(target)
    ishape = _shape(b, index)
    dnums = _gather_dnums([len(ishape)], [0], [0])
    rows = _gather(
        b,
        weight,
        _reshape(b, index, ishape + [1]),
        dnums,
        [1, wshape[1]],
        ishape + [wshape[1]],
        "FILL_OR_DROP",
    )
    if padding < 0:
        return rows
    hit = _cmp(
        b,
        "eq",
        _bcast_dims(b, index, shape, range(len(ishape))),
        _fill(b, padding, "int32", shape),
    )
    return _where(b, hit, _op(b, "stop_gradient", [rows], dtype, shape), rows)


@_lowers("aten.index_put.default")
def _index_put(b, node, env):
    """`self[i0, i1, ...] = values` (or `+=` with accumulate) for index tensors
    on adjacent dims. Negative indices wrap; one outside the tensor is dropped.
    Repeated indices without accumulate leave the winner unspecified, as in
    torch."""
    target = str(node.target)
    dtype, shape = _aval(node)
    base_arg, indices, values = node.args[:3]
    accumulate = _arg(node, 3, "accumulate", False)
    if (
        not hasattr(base_arg, "op")
        or not hasattr(values, "op")
        or not isinstance(indices, (list, tuple))
        or type(accumulate) is not bool
    ):
        _refuse(target)
    given = [(d, i) for d, i in enumerate(indices) if i is not None]
    dims = [d for d, _ in given]
    if not given or dims != list(range(dims[0], dims[0] + len(dims))):
        _refuse(target)
    base = b.to(env[base_arg], dtype)
    arrays = []
    for dim, arg in given:
        value = _index_arg(b, env, arg, target)
        size = shape[dim]
        negative = _cmp(b, "lt", value, _like(b, 0, value))
        arrays.append(
            _where(b, negative, _arith(b, "add", value, _like(b, size, value)), value)
        )
    broadcast = []
    for array in arrays:
        broadcast = _broadcast_shapes(broadcast, _shape(b, array), target)
    parts = [_reshape(b, b.broadcast(a, broadcast), broadcast + [1]) for a in arrays]
    coords = _concat(b, parts, len(broadcast))
    first = dims[0]
    updates_shape = shape[:first] + broadcast + shape[first + len(dims) :]
    updates = b.broadcast(b.to(env[values], dtype), updates_shape)
    window = list(range(first)) + list(
        range(first + len(broadcast), len(updates_shape))
    )
    dnums = _scatter_dnums(window, dims, dims)
    return _scatter(
        b, "scatter_add" if accumulate else "scatter", base, coords, updates, dnums
    )


def _broadcast_shapes(a, c, target):
    """The numpy-style broadcast of two shapes, or a refusal."""
    n = max(len(a), len(c))
    a, c = [1] * (n - len(a)) + list(a), [1] * (n - len(c)) + list(c)
    out = []
    for x, y in zip(a, c):
        if x != y and 1 not in (x, y):
            _refuse(target)
        out.append(y if x == 1 else x)
    return out


@_lowers("aten.as_strided.default")
def _as_strided(b, node, env):
    """A strided view of a contiguous tensor read by static arithmetic: the
    flat element each output takes is offset + sum(i_k * stride_k), computed in
    the graph and gathered. A tensor that is not contiguous in storage order
    is refused (its logical layout is not the storage the view addresses)."""
    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    size, stride = node.args[1], node.args[2]
    offset = _arg(node, 3, "storage_offset", None) or 0
    if not hasattr(arg, "op"):
        _refuse(target)
    val = arg.meta.get("val")
    if (
        val is None
        or not val.is_contiguous()
        or val.storage_offset() != 0
        or [int(s) for s in size] != shape
        or any(type(v) is not int or v < 0 for v in [*stride, offset])
        or len(size) != len(stride)
        or not shape
        or 0 in shape
    ):
        _refuse(target)
    x = env[arg]
    flat_size = math.prod(_shape(b, x))
    if offset + sum((n - 1) * s for n, s in zip(shape, stride)) >= flat_size:
        _refuse(target, "aten_as_strided_out_of_bounds")
    index = _fill(b, offset, "int32", shape)
    for axis, step in enumerate(stride):
        if step and shape[axis] > 1:
            ramp = _times(
                b, _iota(b, "int32", shape, axis), _fill(b, step, "int32", shape)
            )
            index = _arith(b, "add", index, ramp)
    flat = _reshape(b, x, [flat_size])
    dnums = _gather_dnums([], [0], [0])
    return _gather(
        b, flat, _reshape(b, index, shape + [1]), dnums, [1], shape, "PROMISE_IN_BOUNDS"
    )


def _edge_pad(b, x, axis, low, high, mode, target):
    """`x` extended by `low` / `high` entries along `axis`: the reflection of
    the interior (edge not repeated) or the repeated edge."""
    size = _shape(b, x)[axis]
    if low < 0 or high < 0 or (mode == "reflect" and (low >= size or high >= size)):
        _refuse(target)
    parts = []
    _, _ = b.avals[x]
    if low:
        if mode == "reflect":
            edge = _op_rev(b, _slice_axis(b, x, axis, 1, low + 1), axis)
        else:
            edge = _repeat_edge(b, _slice_axis(b, x, axis, 0, 1), axis, low)
        parts.append(edge)
    parts.append(x)
    if high:
        if mode == "reflect":
            edge = _op_rev(b, _slice_axis(b, x, axis, size - 1 - high, size - 1), axis)
        else:
            edge = _repeat_edge(b, _slice_axis(b, x, axis, size - 1, size), axis, high)
        parts.append(edge)
    return _concat(b, parts, axis)


def _op_rev(b, x, axis):
    dtype, shape = b.avals[x]
    if shape[axis] == 1:
        return x
    return _op(b, "rev", [x], dtype, shape, dimensions=[axis])


def _repeat_edge(b, x, axis, count):
    _, shape = b.avals[x]
    out = list(shape)
    out[axis] = count
    return _bcast_dims(b, x, out, range(len(shape)))


@_lowers(
    "aten.reflection_pad1d.default",
    "aten.reflection_pad2d.default",
    "aten.reflection_pad3d.default",
    "aten.replication_pad1d.default",
    "aten.replication_pad2d.default",
    "aten.replication_pad3d.default",
)
def _padding_modes(b, node, env):
    target = str(node.target)
    arg = node.args[0]
    padding = list(node.args[1])
    spatial = int(target.split("_pad")[1][0])
    mode = "reflect" if "reflection" in target else "edge"
    if (
        not hasattr(arg, "op")
        or len(padding) != 2 * spatial
        or any(type(p) is not int for p in padding)
    ):
        _refuse(target)
    out = env[arg]
    rank = len(_shape(b, out))
    if rank not in (spatial + 1, spatial + 2):
        _refuse(target)
    for i in range(spatial):
        out = _edge_pad(
            b, out, rank - 1 - i, padding[2 * i], padding[2 * i + 1], mode, target
        )
    return out


@_lowers("aten.upsample_nearest2d.vec")
def _upsample_nearest2d(b, node, env):
    """Nearest-neighbour resize of (N, C, H, W): source = min(floor(i * scale),
    in - 1) in float32, as torch's, per axis by a gather."""
    import numpy as np

    target = str(node.target)
    _, shape = _aval(node)
    arg = node.args[0]
    scale_factors = _arg(node, 2, "scale_factors", None)
    if not hasattr(arg, "op") or len(shape) != 4:
        _refuse(target)
    out = env[arg]
    have = _shape(b, out)
    scales = list(scale_factors) if scale_factors is not None else [None, None]
    if len(scales) != 2:
        _refuse(target)
    for axis, given in ((2, scales[0]), (3, scales[1])):
        size_in, size_out = have[axis], shape[axis]
        if size_in == size_out:
            continue
        scale = _area_scale(np.float32, size_in, size_out, False, given)
        ramp = _iota(b, "float32", [size_out], 0)
        source = _times(b, ramp, _fill(b, float(scale), "float32", [size_out]))
        floor = _op(b, "floor", [source], "float32", [size_out])
        index = _op(
            b,
            "min",
            [b.to(floor, "int32"), _fill(b, size_in - 1, "int32", [size_out])],
            "int32",
            [size_out],
        )
        out = _take_axis(b, out, axis, index)
    return out


# -- ordering, scatter-reduce and norms ---------------------------------------------


@_lowers("aten.sort.default", "aten.sort.stable")
def _sort(b, node, env):
    """(values, indices) sorted along `dim`, ties in index order, NaN last
    (largest). Descending sorts on (value, -index) and reverses, so ties keep
    their index order there too. Gradients follow the returned indices."""
    target = str(node.target)
    arg = node.args[0]
    if not hasattr(arg, "op"):
        _refuse(target)
    if target.endswith("stable"):
        dim, descending = node.kwargs.get("dim", -1), node.kwargs.get(
            "descending", False
        )
    else:
        dim, descending = _arg(node, 1, "dim", -1), _arg(node, 2, "descending", False)
    x = env[arg]
    dtype, shape = b.avals[x]
    rank = len(shape)
    if (
        type(dim) is not int
        or type(descending) is not bool
        or dtype.startswith("complex")
    ):
        _refuse(target)
    if rank == 0:
        return (x, _fill(b, 0, "int32", []))
    if not -rank <= dim < rank:
        _refuse(target)
    dim = _norm(dim, rank)
    ramp = _iota(b, "int32", shape, dim)
    outs = [(dtype, shape), ("int32", shape)]
    if not descending:
        values, index = _op_many(
            b, "sort", [x, ramp], outs, dimension=dim, is_stable=True, num_keys=1
        )
        return (values, index)
    values, minus = _op_many(
        b,
        "sort",
        [x, _op(b, "neg", [ramp], "int32", shape)],
        outs,
        dimension=dim,
        is_stable=True,
        num_keys=2,
    )
    values = _op(b, "rev", [values], dtype, shape, dimensions=[dim])
    minus = _op(b, "rev", [minus], "int32", shape, dimensions=[dim])
    return (values, _op(b, "neg", [minus], "int32", shape))


@_lowers("aten.topk.default")
def _topk(b, node, env):
    """The k largest (or smallest) along `dim`, sorted: values and indices.
    Largest is the `top_k` primitive; smallest is a stable ascending sort cut
    at k, so a NaN is never among the smallest."""
    target = str(node.target)
    arg = node.args[0]
    k = node.args[1]
    dim, largest = _arg(node, 2, "dim", -1), _arg(node, 3, "largest", True)
    if not hasattr(arg, "op") or type(k) is not int or type(dim) is not int:
        _refuse(target)
    x = env[arg]
    dtype, shape = b.avals[x]
    rank = len(shape)
    if rank == 0 or not -rank <= dim < rank or type(largest) is not bool:
        _refuse(target)
    dim = _norm(dim, rank)
    if not 0 < k <= shape[dim] or dtype == "bool" or dtype.startswith("complex"):
        _refuse(target)
    out_shape = list(shape)
    out_shape[dim] = k
    if largest:
        # JAX's top_k works on the last axis: move `dim` there and back.
        order = [i for i in range(rank) if i != dim] + [dim]
        moved = _transpose(b, x, order)
        mshape = [shape[i] for i in order]
        mout = mshape[:-1] + [k]
        values, index = _op_many(
            b, "top_k", [moved], [(dtype, mout), ("int32", mout)], k=k, axis=rank - 1
        )
        back = [order.index(i) for i in range(rank)]
        return (_transpose(b, values, back), _transpose(b, index, back))
    values, index = _op_many(
        b,
        "sort",
        [x, _iota(b, "int32", shape, dim)],
        [(dtype, shape), ("int32", shape)],
        dimension=dim,
        is_stable=True,
        num_keys=1,
    )
    return (_slice_axis(b, values, dim, 0, k), _slice_axis(b, index, dim, 0, k))


@_lowers("aten.scatter_reduce.two")
def _scatter_reduce(b, node, env):
    """`self[index] <reduce>= src` along `dim` (sum, prod, mean, amax, amin),
    with or without `self` in each reduction. An index outside the tensor is
    dropped; torch raises. prod has a gradient for src only when the indices do
    not repeat (JAX's rule), the others always."""
    target = str(node.target)
    dtype, shape = _aval(node)
    reduce_name = node.args[4]
    include_self = _arg(node, 5, "include_self", True)
    if (
        not _isfloat(dtype)
        or reduce_name not in ("sum", "prod", "mean", "amax", "amin")
        or type(include_self) is not bool
        or not hasattr(node.args[0], "op")
        or not hasattr(node.args[3], "op")
    ):
        _refuse(target)
    rank = len(shape)
    dim = node.args[1]
    if type(dim) is not int or rank == 0 or not -rank <= dim < rank:
        _refuse(target)
    dim = _norm(dim, rank)
    index = _index_arg(b, env, node.args[2], target)
    ishape = _shape(b, index)
    src = b.to(env[node.args[3]], dtype)
    have = _shape(b, src)
    if len(ishape) != rank or any(
        i > s for a, (i, s) in enumerate(zip(ishape, shape)) if a != dim
    ):
        _refuse(target)
    if len(have) != rank or any(h < i for h, i in zip(have, ishape)):
        _refuse(target)
    if have != ishape:
        src = _slice(b, src, [0] * rank, ishape)
    coords = _coordinates(b, index, dim, rank)
    dnums = _scatter_dnums([], range(rank), range(rank))
    base = b.to(env[node.args[0]], dtype)
    original = base
    identity = {
        "sum": 0.0,
        "mean": 0.0,
        "prod": 1.0,
        "amax": -math.inf,
        "amin": math.inf,
    }[reduce_name]
    if not include_self:
        # Each touched position starts from the reduction's identity.
        base = _scatter(
            b, "scatter", base, coords, _fill(b, identity, dtype, ishape), dnums
        )
    op = {
        "sum": "scatter_add",
        "mean": "scatter_add",
        "prod": "scatter_mul",
        "amax": "scatter_max",
        "amin": "scatter_min",
    }[reduce_name]
    total = _scatter(b, op, base, coords, src, dnums)
    if reduce_name != "mean":
        return total
    ones = _fill(b, 1, dtype, ishape)
    start = _fill(b, 1 if include_self else 0, dtype, shape)
    count = _scatter(b, "scatter_add", start, coords, ones, dnums)
    safe = _where(
        b, _cmp(b, "eq", count, _like(b, 0, count)), _like(b, 1, count), count
    )
    mean = _arith(b, "div", total, safe)
    # An untouched position keeps `self` exactly (with self excluded).
    return _where(b, _cmp(b, "eq", count, _like(b, 0, count)), original, mean)


@_lowers("aten._log_softmax.default")
def _log_softmax(b, node, env):
    """x - max - log(sum(exp(x - max))), the shift outside the derivative."""
    target = str(node.target)
    dtype, shape = _aval(node)
    arg, dim, half = node.args[:3]
    if (
        not hasattr(arg, "op")
        or type(dim) is not int
        or half is not False
        or not _isfloat(dtype)
        or not shape
        or not -len(shape) <= dim < len(shape)
    ):
        _refuse(target)
    x = env[arg]
    axis = _norm(dim, len(shape))
    peak = _reduce(
        b, "reduce_max", _op(b, "stop_gradient", [x], dtype, shape), [axis], True
    )
    shifted = _arith(b, "sub", x, b.broadcast(peak, shape))
    total = _reduce(
        b, "reduce_sum", _op(b, "exp", [shifted], dtype, shape), [axis], True
    )
    logged = _op(b, "log", [total], dtype, _shape(b, total))
    return _arith(b, "sub", shifted, b.broadcast(logged, shape))


@_lowers("aten.native_group_norm.default")
def _native_group_norm(b, node, env):
    """Group norm over (N, C, ...): statistics per (sample, group), then the
    per-channel weight and bias. Outputs the normalized result, the mean and
    the reciprocal standard deviation (both without gradient, as torch's)."""
    target = str(node.target)
    arg, weight_arg, bias_arg, n, c, hxw, groups, epsilon = node.args[:8]
    if not hasattr(arg, "op") or any(type(v) is not int for v in (n, c, hxw, groups)):
        _refuse(target)
    x = env[arg]
    dtype, shape = b.avals[x]
    if (
        not _isfloat(dtype)
        or len(shape) < 2
        or shape[0] != n
        or shape[1] != c
        or math.prod(shape[2:]) != hxw
        or groups < 1
        or c % groups
        or type(epsilon) not in (int, float)
        or not math.isfinite(epsilon)
        or epsilon < 0
    ):
        _refuse(target)
    grouped = [n, groups, (c // groups) * hxw]
    xg = _reshape(b, x, grouped)
    count = grouped[2]
    mean = _arith(
        b,
        "div",
        _reduce(b, "reduce_sum", xg, [2], True),
        _fill(b, count, dtype, [n, groups, 1]),
    )
    centred = _arith(b, "sub", xg, b.broadcast(mean, grouped))
    squares = _op(b, "integer_pow", [centred], dtype, grouped, y=2)
    variance = _arith(
        b,
        "div",
        _reduce(b, "reduce_sum", squares, [2], True),
        _fill(b, count, dtype, [n, groups, 1]),
    )
    variance = _arith(b, "add", variance, _fill(b, epsilon, dtype, [n, groups, 1]))
    rstd = _op(b, "rsqrt", [variance], dtype, [n, groups, 1])
    result = _reshape(b, _times(b, centred, b.broadcast(rstd, grouped)), shape)
    for affine, op in ((weight_arg, "mul"), (bias_arg, "add")):
        if affine is None:
            continue
        if not hasattr(affine, "op") or b.avals[env[affine]] != (dtype, [c]):
            _refuse(target)
        per_channel = _bcast_dims(b, env[affine], shape, [1])
        result = _arith(b, op, result, per_channel)
    stats = [n, groups]
    return (
        result,
        _reshape(b, _op(b, "stop_gradient", [mean], dtype, [n, groups, 1]), stats),
        _reshape(b, _op(b, "stop_gradient", [rstd], dtype, [n, groups, 1]), stats),
    )


class _Unselectable:
    """A result of a multi-result op that Carbon does not produce; selecting it
    refuses with `code` (a named reason rather than a missing value)."""

    def __init__(self, code):
        self.code = code


@_lowers("aten._native_batch_norm_legit_functional.default")
def _batch_norm_functional(b, node, env):
    """Training batch norm with running statistics, functional form: only the
    statistics-only part lowers (the normalized result and the batch's own
    mean and reciprocal std). The updated running statistics are a state
    update, not a pure value, so selecting them refuses by name."""
    target = str(node.target)
    args = node.args
    x_arg, weight_arg, bias_arg = args[:3]
    training, epsilon = args[5], args[7]
    if (
        len(args) != 8
        or node.kwargs
        or not hasattr(x_arg, "op")
        or training is not True
        or type(epsilon) not in (int, float)
    ):
        _refuse(target)
    x = env[x_arg]
    dtype, shape = b.avals[x]
    if (
        not _isfloat(dtype)
        or len(shape) < 2
        or not math.isfinite(epsilon)
        or epsilon < 0
    ):
        _refuse(target)
    channels = shape[1]
    axes = [0] + list(range(2, len(shape)))
    kept = [1, channels] + [1] * (len(shape) - 2)
    count = math.prod(shape) // channels
    total = _reduce(b, "reduce_sum", x, axes)
    mean = _arith(b, "div", total, _fill(b, count, dtype, [channels]))
    mean_k = _reshape(b, mean, kept)
    centred = _arith(b, "sub", x, b.broadcast(mean_k, shape))
    squares = _op(b, "integer_pow", [centred], dtype, shape, y=2)
    variance = _arith(
        b,
        "div",
        _reduce(b, "reduce_sum", squares, axes),
        _fill(b, count, dtype, [channels]),
    )
    variance = _arith(b, "add", variance, _fill(b, epsilon, dtype, [channels]))
    rstd = _op(b, "rsqrt", [variance], dtype, [channels])
    result = _times(b, centred, b.broadcast(_reshape(b, rstd, kept), shape))
    for affine, op in ((weight_arg, "mul"), (bias_arg, "add")):
        if affine is None:
            continue
        if not hasattr(affine, "op") or b.avals[env[affine]] != (dtype, [channels]):
            _refuse(target)
        result = _arith(b, op, result, _bcast_dims(b, env[affine], shape, [1]))
    marker = _Unselectable("aten_batch_norm_running_stats_update")
    return (
        result,
        _op(b, "stop_gradient", [mean], dtype, [channels]),
        _op(b, "stop_gradient", [rstd], dtype, [channels]),
        marker,
        marker,
    )


# -- distances ------------------------------------------------------------------


def _pairwise(b, x1, x2, p, target):
    """||x1_i - x2_j||_p for rows of (..., P, M) against (..., R, M): the
    direct difference form (torch switches to a matmul form past 25 rows, which
    differs by rounding). A zero distance has gradient 0, as torch's."""
    dtype, s1 = b.avals[x1]
    s2 = _shape(b, x2)
    if len(s1) < 2 or len(s2) < 2 or s1[-1] != s2[-1] or not _isfloat(dtype):
        _refuse(target)
    batch = _broadcast_shapes(s1[:-2], s2[:-2], target)
    rows, cols, width = s1[-2], s2[-2], s1[-1]
    full = batch + [rows, cols, width]
    nb = len(batch)
    a = _bcast_dims(b, x1, full, list(range(nb - (len(s1) - 2), nb)) + [nb, nb + 2])
    c = _bcast_dims(b, x2, full, list(range(nb - (len(s2) - 2), nb)) + [nb + 1, nb + 2])
    diff = _arith(b, "sub", a, c)
    axis = [nb + 2]
    out = batch + [rows, cols]
    if p == 0:
        mask = b.to(_cmp(b, "ne", diff, _like(b, 0, diff)), dtype)
        return _reduce(b, "reduce_sum", mask, axis)
    magnitude = _op(b, "abs", [diff], dtype, full)
    if p == 1:
        return _reduce(b, "reduce_sum", magnitude, axis)
    if p == math.inf:
        return _reduce(b, "reduce_max", magnitude, axis)
    if p == 2:
        squares = _op(b, "integer_pow", [diff], dtype, full, y=2)
        total = _reduce(b, "reduce_sum", squares, axis)
    else:
        total = _reduce(
            b, "reduce_sum", _arith(b, "pow", magnitude, _fill(b, p, dtype, full)), axis
        )
    zero = _cmp(b, "eq", total, _like(b, 0, total))
    safe = _where(b, zero, _like(b, 1, total), total)
    if p == 2:
        root = _op(b, "sqrt", [safe], dtype, out)
    else:
        root = _arith(b, "pow", safe, _fill(b, 1.0 / p, dtype, out))
    return _where(b, zero, _like(b, 0, total), root)


@_lowers("aten._cdist_forward.default")
def _cdist_forward(b, node, env):
    target = str(node.target)
    x1, x2 = node.args[:2]
    p = _arg(node, 2, "p", 2.0)
    if not (hasattr(x1, "op") and hasattr(x2, "op")) or not isinstance(p, (int, float)):
        _refuse(target)
    if isinstance(p, bool) or p < 0 or (p != math.inf and not math.isfinite(p)):
        _refuse(target)
    out = _pairwise(b, env[x1], env[x2], float(p), target)
    if b.avals[out] != _aval(node):
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    return out


@_lowers("aten._pdist_forward.default")
def _pdist_forward(b, node, env):
    """Distances between the rows i < j of (N, M), row-major: slices of the
    pairwise matrix, one per row."""
    target = str(node.target)
    arg = node.args[0]
    p = _arg(node, 1, "p", 2.0)
    if not hasattr(arg, "op") or isinstance(p, bool) or not isinstance(p, (int, float)):
        _refuse(target)
    if p < 0 or (p != math.inf and not math.isfinite(p)):
        _refuse(target)
    x = env[arg]
    shape = _shape(b, x)
    if len(shape) != 2 or not 2 <= shape[0] <= 512:
        _refuse(target)
    full = _pairwise(b, x, x, float(p), target)
    n = shape[0]
    rows = []
    for i in range(n - 1):
        piece = _slice(b, full, [i, i + 1], [i + 1, n])
        rows.append(_reshape(b, piece, [n - 1 - i]))
    return _concat(b, rows, 0)


# -- pooling and resizing -----------------------------------------------------------


def _pool_vector(value, nd, default, target):
    value = list(value) if isinstance(value, (list, tuple)) else [value]
    if not value:
        value = list(default)
    if len(value) == 1:
        value = value * nd
    if len(value) != nd or any(type(v) is not int for v in value):
        _refuse(target)
    return value


def _pool_geometry(sizes, kernel, stride, padding, dilation, ceil_mode, target):
    """Output sizes and (low, high) padding of torch's pooling windows."""
    out, pads = [], []
    for n, k, s, p, d in zip(sizes, kernel, stride, padding, dilation):
        span = d * (k - 1) + 1
        if k < 1 or s < 1 or d < 1 or p < 0:
            _refuse(target)
        numerator = n + 2 * p - span
        if numerator < 0:
            _refuse(target)
        o = (numerator + (s - 1 if ceil_mode else 0)) // s + 1
        if ceil_mode and (o - 1) * s >= n + p:
            o -= 1
        hi = max((o - 1) * s + span - n - p, 0) if ceil_mode else p
        if (n + p + hi - span) // s + 1 != o:
            _refuse(target)
        out.append(o)
        pads.append((p, hi))
    return out, pads


def _window_reduce(b, op, x, nd, kernel, stride, pads, dilation, out_sizes):
    dtype, shape = b.avals[x]
    lead = len(shape) - nd
    return _op(
        b,
        op,
        [x],
        dtype,
        shape[:lead] + out_sizes,
        window_dimensions=[1] * lead + kernel,
        window_strides=[1] * lead + stride,
        padding=[[0, 0]] * lead + [list(p) for p in pads],
        base_dilation=[1] * len(shape),
        window_dilation=[1] * lead + dilation,
    )


@_lowers("aten.avg_pool2d.default", "aten.avg_pool3d.default")
def _avg_pool(b, node, env):
    """Window sums (zero padding) divided by each window's own count: the
    window clipped to the padded extent when padding counts, to the input when
    it does not. A ceil_mode window that runs past the padding is shortened
    the same way as torch's."""
    target = str(node.target)
    nd = 2 if "2d" in target else 3
    dtype, shape = _aval(node)
    arg = node.args[0]
    kernel_arg = node.args[1]
    stride_arg = _arg(node, 2, "stride", [])
    padding_arg = _arg(node, 3, "padding", 0)
    ceil_mode = _arg(node, 4, "ceil_mode", False)
    include_pad = _arg(node, 5, "count_include_pad", True)
    override = _arg(node, 6, "divisor_override", None)
    if (
        not hasattr(arg, "op")
        or not _isfloat(dtype)
        or type(ceil_mode) is not bool
        or type(include_pad) is not bool
        or (override is not None and (type(override) is not int or override == 0))
    ):
        _refuse(target)
    x = env[arg]
    have = _shape(b, x)
    if len(have) not in (nd + 1, nd + 2):
        _refuse(target)
    sizes = have[-nd:]
    kernel = _pool_vector(kernel_arg, nd, [], target)
    stride = _pool_vector(stride_arg, nd, kernel, target)
    padding = _pool_vector(padding_arg, nd, [0] * nd, target)
    if any(2 * p > k for p, k in zip(padding, kernel)):
        _refuse(target)
    out_sizes, pads = _pool_geometry(
        sizes, kernel, stride, padding, [1] * nd, ceil_mode, target
    )
    if shape[-nd:] != out_sizes:
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    total = _window_reduce(
        b, "reduce_window_sum", x, nd, kernel, stride, pads, [1] * nd, out_sizes
    )
    if override is not None:
        return _arith(b, "div", total, _like(b, override, total))
    if all(p == 0 for p in padding) and not ceil_mode:
        return _arith(b, "div", total, _like(b, math.prod(kernel), total))
    # Per-window element counts from a tensor of ones in the same windows.
    if include_pad:
        extent = [n + p + min(hi, p) for n, (p, hi) in zip(sizes, pads)]
        spill = [(0, max(hi - p, 0)) for p, hi in pads]
    else:
        extent = list(sizes)
        spill = list(pads)
    ones = _fill(b, 1, dtype, [1] * (len(have) - nd) + extent)
    counts = _window_reduce(
        b, "reduce_window_sum", ones, nd, kernel, stride, spill, [1] * nd, out_sizes
    )
    counts = b.broadcast(counts, shape)
    return _arith(b, "div", total, counts)


def _max_pool_window(b, node, env, nd):
    """Max pooling over arbitrary windows (reduce_window_max, -inf padding).
    Only the values are selectable: the indices output is refused."""
    target = str(node.target)
    arg = node.args[0]
    dtype, shape = _avals(node)[0]
    kernel_arg = node.args[1]
    stride_arg = _arg(node, 2, "stride", [])
    padding_arg = _arg(node, 3, "padding", 0)
    dilation_arg = _arg(node, 4, "dilation", 1)
    ceil_mode = _arg(node, 5, "ceil_mode", False)
    if not hasattr(arg, "op") or not _isfloat(dtype) or type(ceil_mode) is not bool:
        _refuse(target)
    x = env[arg]
    have = _shape(b, x)
    if len(have) not in (nd + 1, nd + 2):
        _refuse(target)
    kernel = _pool_vector(kernel_arg, nd, [], target)
    stride = _pool_vector(stride_arg, nd, kernel, target)
    padding = _pool_vector(padding_arg, nd, [0] * nd, target)
    dilation = _pool_vector(dilation_arg, nd, [1] * nd, target)
    if any(2 * p > k for p, k in zip(padding, kernel)) or any(d != 1 for d in dilation):
        # JAX has no derivative for a dilated window (select_and_gather_add),
        # so a dilated max pool could not be trained: refused up front.
        _refuse(target)
    out_sizes, pads = _pool_geometry(
        have[-nd:], kernel, stride, padding, dilation, ceil_mode, target
    )
    if shape[-nd:] != out_sizes:
        raise graph.GraphRefused("aten_result_metadata_not_supported", target)
    values = _window_reduce(
        b, "reduce_window_max", x, nd, kernel, stride, pads, dilation, out_sizes
    )
    return (values, None)


@_lowers("aten.max_pool3d_with_indices.default")
def _max_pool3d(b, node, env):
    return _max_pool_window(b, node, env, 3)


def _adaptive_sum(b, x, axis, n_out, target):
    """Window sums along `axis` for torch's adaptive windows [floor(o * n / m),
    ceil((o + 1) * n / m)), and each window's length."""
    shape = _shape(b, x)
    n_in = shape[axis]
    if n_out < 1 or n_in < 1:
        _refuse(target)
    if n_in == n_out:
        return x, [1] * n_out
    if n_in % n_out == 0:
        k = n_in // n_out
        split = shape[:axis] + [n_out, k] + shape[axis + 1 :]
        return _reduce(b, "reduce_sum", _reshape(b, x, split), [axis + 1]), [k] * n_out
    if n_out > 256:
        _refuse(target, "aten_lowering_expansion_bound")
    pieces, lengths = [], []
    for o in range(n_out):
        start = (o * n_in) // n_out
        end = -(-((o + 1) * n_in) // n_out)
        pieces.append(
            _reduce(b, "reduce_sum", _slice_axis(b, x, axis, start, end), [axis], True)
        )
        lengths.append(end - start)
    return _concat(b, pieces, axis), lengths


@_lowers("aten._adaptive_avg_pool2d.default", "aten._adaptive_avg_pool3d.default")
def _adaptive_avg_pool(b, node, env):
    """Mean over each adaptive window, one axis at a time (a mean of means,
    which equals the window mean; the rounding order differs from torch's)."""
    import numpy as np

    target = str(node.target)
    nd = 2 if "2d" in target else 3
    dtype, _ = _aval(node)
    arg = node.args[0]
    size = list(node.args[1])
    if (
        not hasattr(arg, "op")
        or not _isfloat(dtype)
        or len(size) != nd
        or any(type(s) is not int for s in size)
    ):
        _refuse(target)
    out = env[arg]
    rank = len(_shape(b, out))
    if rank not in (nd + 1, nd + 2):
        _refuse(target)
    for i in range(nd):
        axis = rank - nd + i
        summed, lengths = _adaptive_sum(b, out, axis, size[i], target)
        have = _shape(b, summed)
        if len(set(lengths)) == 1:
            divisor = _fill(b, lengths[0], dtype, have)
        else:
            vector = b.const(np.asarray(lengths, dtype=dtype))
            divisor = _bcast_dims(b, vector, have, [axis])
        out = _arith(b, "div", summed, divisor)
    return out


def _lerp_axis(b, x, axis, size_out, align_corners, given):
    """Linear interpolation along `axis`, torch's source index and weight in
    the data's own float type: i0 = min(floor(src), n - 1), i1 = i0 + (i0 <
    n - 1), lambda = clamp(src - i0, 0, 1)."""
    import numpy as np

    dtype, have = b.avals[x]
    size_in = have[axis]
    np_type = np.dtype(dtype).type
    scale = _area_scale(np_type, size_in, size_out, align_corners, given)
    ramp = _iota(b, dtype, [size_out], 0)
    if align_corners:
        source = _times(b, ramp, _fill(b, float(scale), dtype, [size_out]))
    else:
        half = _arith(b, "add", ramp, _fill(b, 0.5, dtype, [size_out]))
        shifted = _arith(
            b,
            "sub",
            _times(b, half, _fill(b, float(scale), dtype, [size_out])),
            _fill(b, 0.5, dtype, [size_out]),
        )
        zero = _fill(b, 0.0, dtype, [size_out])
        source = _where(b, _cmp(b, "lt", shifted, zero), zero, shifted)
    last = _fill(b, size_in - 1, "int32", [size_out])
    lower = _op(
        b,
        "min",
        [b.to(_op(b, "floor", [source], dtype, [size_out]), "int32"), last],
        "int32",
        [size_out],
    )
    more = b.to(_cmp(b, "lt", lower, last), "int32")
    upper = _arith(b, "add", lower, more)
    frac = _arith(b, "sub", source, b.to(lower, dtype))
    zero, one = _fill(b, 0.0, dtype, [size_out]), _fill(b, 1.0, dtype, [size_out])
    frac = _where(b, _cmp(b, "lt", frac, zero), zero, frac)
    frac = _where(b, _cmp(b, "gt", frac, one), one, frac)
    rest = _arith(b, "sub", one, frac)
    shape = _shape(b, x)
    out_shape = list(shape)
    out_shape[axis] = size_out
    w_hi = _bcast_dims(b, frac, out_shape, [axis])
    w_lo = _bcast_dims(b, rest, out_shape, [axis])
    low = _take_axis(b, x, axis, lower)
    high = _take_axis(b, x, axis, upper)
    return _arith(b, "add", _times(b, low, w_lo), _times(b, high, w_hi))


@_lowers("aten.upsample_bilinear2d.vec")
def _upsample_bilinear2d(b, node, env):
    """Bilinear resize of (N, C, H, W): width first, then height (torch's
    order), each by two gathers and torch's own source index and weights. The
    arithmetic order differs from torch's fused kernel by rounding."""
    target = str(node.target)
    dtype, shape = _aval(node)
    arg = node.args[0]
    align_corners = _arg(node, 2, "align_corners", None)
    scale_factors = _arg(node, 3, "scale_factors", None)
    if (
        not hasattr(arg, "op")
        or not _isfloat(dtype)
        or len(shape) != 4
        or type(align_corners) is not bool
    ):
        _refuse(target)
    scales = list(scale_factors) if scale_factors is not None else [None, None]
    if len(scales) != 2:
        _refuse(target)
    out = b.to(env[arg], dtype)
    have = _shape(b, out)
    for axis, given in ((3, scales[1]), (2, scales[0])):
        if have[axis] != shape[axis]:
            out = _lerp_axis(b, out, axis, shape[axis], align_corners, given)
    return out


@_lowers("aten.col2im.default")
def _col2im(b, node, env):
    """Fold sliding-window columns back into an image, summing overlaps: each
    kernel offset's block is placed by one `pad` (interior padding = stride,
    negative low/high = the image padding cropped) and the blocks are added."""
    target = str(node.target)
    dtype, shape = _aval(node)
    arg = node.args[0]
    size, kernel, dilation, padding, stride = (list(v) for v in node.args[1:6])
    if (
        not hasattr(arg, "op")
        or not _isfloat(dtype)
        or any(
            len(v) != 2 or any(type(i) is not int for i in v)
            for v in (size, kernel, dilation, padding, stride)
        )
        or any(s < 1 for s in stride)
        or any(d < 1 for d in dilation)
        or any(p < 0 for p in padding)
    ):
        _refuse(target)
    x = env[arg]
    have = _shape(b, x)
    if len(have) not in (2, 3):
        _refuse(target)
    batched = len(have) == 3
    kh, kw = kernel
    positions = [
        (n + 2 * p - d * (k - 1) - 1) // s + 1
        for n, p, d, k, s in zip(size, padding, dilation, kernel, stride)
    ]
    lh, lw = positions
    c, rows = (shape[1], have[1]) if batched else (shape[0], have[0])
    if rows != c * kh * kw or have[-1] != lh * lw or lh < 1 or lw < 1:
        _refuse(target)
    if kh * kw > 1024:
        _refuse(target, "aten_lowering_expansion_bound")
    n = have[0] if batched else 1
    blocks = _reshape(b, x, [n, c, kh, kw, lh, lw])
    out_shape = [n, c, size[0], size[1]]
    total = None
    for i in range(kh):
        for j in range(kw):
            piece = _slice(b, blocks, [0, 0, i, j, 0, 0], [n, c, i + 1, j + 1, lh, lw])
            piece = _reshape(b, piece, [n, c, lh, lw])
            config = [[0, 0, 0], [0, 0, 0]]
            for axis, (offset, extent, stride_, pad, dil, count) in enumerate(
                zip((i, j), size, stride, padding, dilation, (lh, lw))
            ):
                low = offset * dil - pad
                high = extent - low - ((count - 1) * stride_ + 1)
                config.append([low, high, stride_ - 1])
            placed = _op(
                b,
                "pad",
                [piece, b.scalar(0, dtype)],
                dtype,
                out_shape,
                padding_config=config,
            )
            total = placed if total is None else _arith(b, "add", total, placed)
    return _reshape(b, total, shape)


@_lowers("aten.masked_scatter.default")
def _masked_scatter(b, node, env):
    """Fill the true positions of `mask` (row-major) with consecutive elements
    of `source`. A source shorter than the true count reads NaN; torch raises."""
    target = str(node.target)
    dtype, shape = _aval(node)
    base_arg, mask_arg, source_arg = node.args[:3]
    if not (
        hasattr(base_arg, "op")
        and hasattr(mask_arg, "op")
        and hasattr(source_arg, "op")
    ):
        _refuse(target)
    base = b.to(env[base_arg], dtype)
    mask = b.broadcast(env[mask_arg], shape)
    if _dt(b, mask) != "bool" or not shape:
        _refuse(target)
    source = env[source_arg]
    flat_source = _reshape(b, b.to(source, dtype), [math.prod(_shape(b, source))])
    total = math.prod(shape)
    counts = _op(
        b,
        "cumsum",
        [b.to(_reshape(b, mask, [total]), "int32")],
        "int32",
        [total],
        axis=0,
        reverse=False,
    )
    position = _arith(b, "sub", counts, _fill(b, 1, "int32", [total]))
    dnums = _gather_dnums([], [0], [0])
    taken = _gather(
        b,
        flat_source,
        _reshape(b, position, [total, 1]),
        dnums,
        [1],
        [total],
        "FILL_OR_DROP",
    )
    return _where(b, mask, _reshape(b, taken, shape), base)


# -- sampling and bags --------------------------------------------------------------


def _clip_open(b, v, size):
    """min(size - 1, max(v, 0)) whose gradient is 0 at and beyond the bounds
    (torch's clip_coordinates), by selects."""
    dtype, shape = b.avals[v]
    low = _fill(b, 0, dtype, shape)
    high = _fill(b, size - 1, dtype, shape)
    v = _where(b, _cmp(b, "le", v, low), low, v)
    return _where(b, _cmp(b, "ge", v, high), high, v)


@_lowers("aten.grid_sampler_2d.default")
def _grid_sampler_2d(b, node, env):
    """F.grid_sample on (N, C, H, W) with a (N, Ho, Wo, 2) grid: bilinear or
    nearest, zeros or border padding. Bicubic and reflection padding are
    refused. The four taps are gathered with in-bounds indices and masked by
    selects (a masked NaN does not leak); the gradient reaches the grid
    through the bilinear weights, as torch's."""
    target = str(node.target)
    dtype, shape = _aval(node)
    arg, grid_arg, mode, padding_mode, align = node.args[:5]
    if (
        not (hasattr(arg, "op") and hasattr(grid_arg, "op"))
        or mode not in (0, 1)
        or padding_mode not in (0, 1)
        or type(align) is not bool
        or not _isfloat(dtype)
    ):
        _refuse(target)
    x, grid = env[arg], b.to(env[grid_arg], dtype)
    n, c, h, w = _shape(b, x)
    gshape = _shape(b, grid)
    if len(gshape) != 4 or gshape[3] != 2 or gshape[0] != n:
        _refuse(target)
    ho, wo = gshape[1], gshape[2]
    plane = [n, ho, wo]

    def channel(k):
        part = _slice(b, grid, [0, 0, 0, k], [n, ho, wo, k + 1])
        return _reshape(b, part, plane)

    def source(coord, size):
        one = _fill(b, 1, dtype, plane)
        if align:
            value = _times(
                b,
                _arith(
                    b, "div", _arith(b, "add", coord, one), _fill(b, 2, dtype, plane)
                ),
                _fill(b, size - 1, dtype, plane),
            )
        else:
            scaled = _arith(
                b,
                "sub",
                _times(b, _arith(b, "add", coord, one), _fill(b, size, dtype, plane)),
                one,
            )
            value = _arith(b, "div", scaled, _fill(b, 2, dtype, plane))
        return _clip_open(b, value, size) if padding_mode == 1 else value

    ix, iy = source(channel(0), w), source(channel(1), h)
    dnums = _gather_dnums([1], [2, 3], [2, 3], [0], [0])

    def tap(yi, xi):
        """Pixel values at integer (yi, xi) (float tensors), zero outside."""
        inside = _op(
            b,
            "and",
            [
                _op(
                    b,
                    "and",
                    [
                        _cmp(b, "ge", xi, _fill(b, 0, dtype, plane)),
                        _cmp(b, "le", xi, _fill(b, w - 1, dtype, plane)),
                    ],
                    "bool",
                    plane,
                ),
                _op(
                    b,
                    "and",
                    [
                        _cmp(b, "ge", yi, _fill(b, 0, dtype, plane)),
                        _cmp(b, "le", yi, _fill(b, h - 1, dtype, plane)),
                    ],
                    "bool",
                    plane,
                ),
            ],
            "bool",
            plane,
        )
        xs = _op(
            b,
            "min",
            [
                _op(
                    b,
                    "max",
                    [b.to(xi, "int32"), _fill(b, 0, "int32", plane)],
                    "int32",
                    plane,
                ),
                _fill(b, w - 1, "int32", plane),
            ],
            "int32",
            plane,
        )
        ys = _op(
            b,
            "min",
            [
                _op(
                    b,
                    "max",
                    [b.to(yi, "int32"), _fill(b, 0, "int32", plane)],
                    "int32",
                    plane,
                ),
                _fill(b, h - 1, "int32", plane),
            ],
            "int32",
            plane,
        )
        coords = _concat(
            b, [_reshape(b, ys, plane + [1]), _reshape(b, xs, plane + [1])], 3
        )
        values = _gather(
            b, x, coords, dnums, [1, c, 1, 1], [n, c, ho, wo], "PROMISE_IN_BOUNDS"
        )
        keep = _bcast_dims(b, inside, shape, [0, 2, 3])
        return _where(b, keep, values, _fill(b, 0, dtype, shape))

    def weight_of(value):
        return _bcast_dims(b, value, shape, [0, 2, 3])

    if mode == 1:
        nearest_x = _op(
            b, "round", [ix], dtype, plane, rounding_method="TO_NEAREST_EVEN"
        )
        nearest_y = _op(
            b, "round", [iy], dtype, plane, rounding_method="TO_NEAREST_EVEN"
        )
        return tap(nearest_y, nearest_x)
    x0 = _op(b, "floor", [ix], dtype, plane)
    y0 = _op(b, "floor", [iy], dtype, plane)
    one = _fill(b, 1, dtype, plane)
    x1, y1 = _arith(b, "add", x0, one), _arith(b, "add", y0, one)
    wx0, wx1 = _arith(b, "sub", x1, ix), _arith(b, "sub", ix, x0)
    wy0, wy1 = _arith(b, "sub", y1, iy), _arith(b, "sub", iy, y0)
    out = None
    for yi, xi, wy, wx in (
        (y0, x0, wy0, wx0),
        (y0, x1, wy0, wx1),
        (y1, x0, wy1, wx0),
        (y1, x1, wy1, wx1),
    ):
        term = _times(b, tap(yi, xi), weight_of(_times(b, wx, wy)))
        out = term if out is None else _arith(b, "add", out, term)
    return out


@_lowers("aten._embedding_bag.default", "aten._embedding_bag_forward_only.default")
def _embedding_bag(b, node, env):
    """Sum, mean or max of the rows of `weight` in each bag. Bag membership is
    read from `offsets` in the graph (an offset compared with each position),
    so the offsets may be an input. Only the pooled result is selectable (the
    auxiliary outputs refuse by name). An index outside the table reads NaN
    rows; padding_idx rows are left out."""
    target = str(node.target)
    dtype, shape = _avals(node)[0]
    weight_arg, index_arg, offsets_arg = node.args[:3]
    mode = _arg(node, 4, "mode", 0)
    weights_arg = _arg(node, 6, "per_sample_weights", None)
    last = _arg(node, 7, "include_last_offset", False)
    padding = _arg(node, 8, "padding_idx", -1)
    if (
        not all(hasattr(a, "op") for a in (weight_arg, index_arg, offsets_arg))
        or mode not in (0, 1, 2)
        or type(last) is not bool
        or (padding is not None and type(padding) is not int)
        or not _isfloat(dtype)
        or (weights_arg is not None and (mode != 0 or not hasattr(weights_arg, "op")))
    ):
        _refuse(target)
    weight = env[weight_arg]
    index = _index_arg(b, env, index_arg, target)
    offsets = _index_arg(b, env, offsets_arg, target)
    wshape, ishape, oshape = _shape(b, weight), _shape(b, index), _shape(b, offsets)
    if len(wshape) != 2 or len(ishape) != 1 or len(oshape) != 1:
        _refuse(target)
    length, bags, width = ishape[0], oshape[0] - (1 if last else 0), wshape[1]
    if bags < 1 or length < 1 or shape != [bags, width]:
        _refuse(target)
    starts = _slice(b, offsets, [0], [bags]) if last else offsets
    grid = [length, bags]
    started = _cmp(
        b, "le", _bcast_dims(b, starts, grid, [1]), _iota(b, "int32", grid, 0)
    )
    bag = _arith(
        b,
        "sub",
        _reduce(b, "reduce_sum", b.to(started, "int32"), [1]),
        _fill(b, 1, "int32", [length]),
    )
    rows = _gather(
        b,
        weight,
        _reshape(b, index, [length, 1]),
        _gather_dnums([1], [0], [0]),
        [1, width],
        [length, width],
        "FILL_OR_DROP",
    )
    live = (
        _cmp(b, "ne", index, _fill(b, padding, "int32", [length]))
        if padding is not None and padding >= 0
        else _fill(b, True, "bool", [length])
    )
    live_rows = _bcast_dims(b, live, [length, width], [0])
    where_bag = _reshape(b, bag, [length, 1])
    into_rows = _scatter_dnums([1], [0], [0])
    into_bags = _scatter_dnums([], [0], [0])
    if mode == 2:
        low = _fill(b, -math.inf, dtype, [length, width])
        out = _scatter(
            b,
            "scatter_max",
            _fill(b, -math.inf, dtype, [bags, width]),
            where_bag,
            _where(b, live_rows, rows, low),
            into_rows,
        )
    else:
        if weights_arg is not None:
            rows = _times(
                b,
                rows,
                _bcast_dims(b, b.to(env[weights_arg], dtype), [length, width], [0]),
            )
        out = _scatter(
            b,
            "scatter_add",
            _fill(b, 0, dtype, [bags, width]),
            where_bag,
            _where(b, live_rows, rows, _fill(b, 0, dtype, [length, width])),
            into_rows,
        )
    counts = _scatter(
        b,
        "scatter_add",
        _fill(b, 0, dtype, [bags]),
        where_bag,
        b.to(live, dtype),
        into_bags,
    )
    empty = _cmp(b, "eq", counts, _like(b, 0, counts))
    empty_rows = _bcast_dims(b, empty, shape, [0])
    if mode == 1:
        safe = _where(b, empty, _like(b, 1, counts), counts)
        out = _arith(b, "div", out, _bcast_dims(b, safe, shape, [0]))
    elif mode == 2:
        out = _where(b, empty_rows, _fill(b, 0, dtype, shape), out)
    marker = _Unselectable("aten_embedding_bag_auxiliary_output")
    return (out, marker, marker, marker)


# -- linear algebra ---------------------------------------------------------------------


def _batch_matrix(b, node, value, target, square=True):
    dtype, shape = b.avals[value]
    if len(shape) < 2 or not _isfloat(dtype) or (square and shape[-1] != shape[-2]):
        _refuse(target)
    return dtype, shape


def _triangle_mask(b, shape, lower, strict=False):
    rows = _iota(b, "int32", shape, len(shape) - 2)
    cols = _iota(b, "int32", shape, len(shape) - 1)
    op = ("gt" if strict else "ge") if lower else ("lt" if strict else "le")
    return _cmp(b, op, rows, cols)


def _symmetrized(b, x, lower):
    """The symmetric matrix read from one triangle of `x`, as LAPACK does."""
    dtype, shape = b.avals[x]
    rank = len(shape)
    perm = list(range(rank - 2)) + [rank - 1, rank - 2]
    zero = _fill(b, 0, dtype, shape)
    kept = _where(b, _triangle_mask(b, shape, lower), x, zero)
    strict = _where(b, _triangle_mask(b, shape, lower, True), x, zero)
    return _arith(b, "add", kept, _transpose(b, strict, perm))


@_lowers("aten.linalg_cholesky_ex.default")
def _cholesky_ex(b, node, env):
    """The Cholesky factor of the symmetric matrix read from one triangle of A
    (lower by default). A matrix that is not positive definite gives NaN; the
    `info` output is not computed (selecting it refuses by name)."""
    target = str(node.target)
    upper = node.kwargs.get("upper", False)
    arg = node.args[0]
    if not hasattr(arg, "op") or type(upper) is not bool or len(node.args) != 1:
        _refuse(target)
    x = env[arg]
    dtype, shape = _batch_matrix(b, node, x, target)
    sym = _symmetrized(b, x, lower=not upper)
    if upper:
        rank = len(shape)
        sym = _transpose(b, sym, list(range(rank - 2)) + [rank - 1, rank - 2])
    factor = _op(b, "cholesky", [sym], dtype, shape)
    zero = _fill(b, 0, dtype, shape)
    factor = _where(b, _triangle_mask(b, shape, True), factor, zero)
    if upper:
        rank = len(shape)
        factor = _transpose(b, factor, list(range(rank - 2)) + [rank - 1, rank - 2])
    return (factor, _Unselectable("aten_linalg_info_not_computed"))


@_lowers("aten.linalg_solve_triangular.default")
def _solve_triangular(b, node, env):
    target = str(node.target)
    dtype, shape = _aval(node)
    a_arg, b_arg = node.args[:2]
    upper = node.kwargs.get("upper")
    left = node.kwargs.get("left", True)
    unit = node.kwargs.get("unitriangular", False)
    if (
        not (hasattr(a_arg, "op") and hasattr(b_arg, "op"))
        or type(upper) is not bool
        or type(left) is not bool
        or type(unit) is not bool
        or not _isfloat(dtype)
    ):
        _refuse(target)
    a, rhs = b.to(env[a_arg], dtype), b.to(env[b_arg], dtype)
    sa, sb = _shape(b, a), _shape(b, rhs)
    if len(sa) < 2 or len(sb) < 2 or sa[-1] != sa[-2]:
        _refuse(target)
    batch = _broadcast_shapes(sa[:-2], sb[:-2], target)
    a = b.broadcast(a, batch + sa[-2:])
    rhs = b.broadcast(rhs, batch + sb[-2:])
    return _op(
        b,
        "triangular_solve",
        [a, rhs],
        dtype,
        shape,
        left_side=left,
        lower=not upper,
        transpose_a=False,
        conjugate_a=False,
        unit_diagonal=unit,
    )


@_lowers("aten._linalg_eigh.default")
def _linalg_eigh(b, node, env):
    """Eigenvalues (ascending) and eigenvectors of the symmetric matrix read
    from one triangle (UPLO). Eigenvector signs are a gauge: compare
    reconstructions, not vectors."""
    target = str(node.target)
    arg = node.args[0]
    uplo = _arg(node, 1, "UPLO", "L")
    compute_v = _arg(node, 2, "compute_v", True)
    if not hasattr(arg, "op") or uplo not in ("L", "U") or compute_v is not True:
        _refuse(target)
    x = env[arg]
    dtype, shape = _batch_matrix(b, node, x, target)
    sym = _symmetrized(b, x, lower=uplo == "L")
    vectors, values = _op_many(
        b,
        "eigh",
        [sym],
        [(dtype, shape), (dtype, shape[:-1])],
        lower=True,
        sort_eigenvalues=True,
    )
    return (values, vectors)


@_lowers("aten.linalg_qr.default")
def _linalg_qr(b, node, env):
    """Householder QR: (Q, R) with R's signs as LAPACK leaves them (a gauge:
    compare Q @ R and Q^T Q)."""
    target = str(node.target)
    arg = node.args[0]
    mode = _arg(node, 1, "mode", "reduced")
    if not hasattr(arg, "op") or mode not in ("reduced", "complete"):
        _refuse(target)
    x = env[arg]
    _, _ = _batch_matrix(b, node, x, target, square=False)
    (qd, qs), (rd, rs) = _avals(node)
    q, r = _op_many(
        b,
        "qr",
        [x],
        [(qd, qs), (rd, rs)],
        full_matrices=mode == "complete",
        pivoting=False,
    )
    return (q, r)


@_lowers("aten._linalg_svd.default")
def _linalg_svd(b, node, env):
    """Singular values (descending) and, when asked, U and Vh (signs are a
    gauge: compare reconstructions)."""
    target = str(node.target)
    arg = node.args[0]
    full = _arg(node, 1, "full_matrices", False)
    compute_uv = _arg(node, 2, "compute_uv", True)
    if not hasattr(arg, "op") or type(full) is not bool or type(compute_uv) is not bool:
        _refuse(target)
    x = env[arg]
    _batch_matrix(b, node, x, target, square=False)
    (ud, us), (sd, ss), (vd, vs) = _avals(node)
    if compute_uv:
        s, u, vh = _op_many(
            b,
            "svd",
            [x],
            [(sd, ss), (ud, us), (vd, vs)],
            full_matrices=full,
            compute_uv=True,
        )
        return (u, s, vh)
    (s,) = _op_many(b, "svd", [x], [(sd, ss)], full_matrices=full, compute_uv=False)
    marker = _Unselectable("aten_linalg_svd_vectors_not_computed")
    return (marker, s, marker)


@_lowers("aten._linalg_solve_ex.default")
def _linalg_solve_ex(b, node, env):
    """Solve A X = B by LU with partial pivoting: X = U^-1 L^-1 P B. The packed
    LU, pivots and `info` outputs are not computed (selecting them refuses by
    name); a singular A gives inf or NaN."""
    target = str(node.target)
    dtype, _ = _avals(node)[0]
    a_arg, b_arg = node.args[:2]
    left = _arg(node, 2, "left", True)
    if not (hasattr(a_arg, "op") and hasattr(b_arg, "op")) or left is not True:
        _refuse(target)
    a, rhs = env[a_arg], env[b_arg]
    sa, sb = _batch_matrix(b, node, a, target)[1], _shape(b, rhs)
    if (
        len(sb) != len(sa)
        or sb[:-2] != sa[:-2]
        or sb[-2] != sa[-1]
        or not _isfloat(dtype)
    ):
        _refuse(target)
    lu, _, perm = _op_many(
        b,
        "lu",
        [a],
        [(dtype, sa), ("int32", sa[:-1]), ("int32", sa[:-1])],
    )
    batch = len(sa) - 2
    n = sa[-1]
    # Rows of B in the pivoted order: one gather with the batch dims batched.
    dnums = _gather_dnums(
        [batch + 1], [batch], [batch], list(range(batch)), list(range(batch))
    )
    permuted = _gather(
        b,
        rhs,
        _reshape(b, perm, sa[:-2] + [n, 1]),
        dnums,
        [1] * batch + [1, sb[-1]],
        sb,
        "PROMISE_IN_BOUNDS",
    )
    common = {"left_side": True, "transpose_a": False, "conjugate_a": False}
    forward = _op(
        b,
        "triangular_solve",
        [lu, permuted],
        dtype,
        sb,
        lower=True,
        unit_diagonal=True,
        **common,
    )
    result = _op(
        b,
        "triangular_solve",
        [lu, forward],
        dtype,
        sb,
        lower=False,
        unit_diagonal=False,
        **common,
    )
    marker = _Unselectable("aten_linalg_solve_auxiliary_output")
    return (result, marker, marker, marker)


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
        ):
            raise graph.GraphRefused("aten_tuple_index_not_supported", target)
        selected = env[args[0]][args[1]]
        if isinstance(selected, _Unselectable):
            raise graph.GraphRefused(selected.code, target)
        if selected is None:
            raise graph.GraphRefused("aten_tuple_index_not_supported", target)
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
    if target in _V8_LOWERINGS:
        return _V8_LOWERINGS[target](b, node, env)
    if target == "aten.sum.dim_IntList":
        return _sum_dim(b, node, env)
    if target == "aten.scatter_add.default":
        return _scatter_add_static(b, node, env)
    if target == "aten.index.Tensor":
        return _index_static(b, node, env)
    if target == "aten.index_select.default":
        return _index_select(b, node, env)
    if target == "aten.split_with_sizes.default":
        return _split_with_sizes(b, node, env)
    if target == "aten.max_pool2d_with_indices.default":
        return _max_pool2d(b, node, env)
    if target == "aten._upsample_bicubic2d_aa.default":
        return _upsample_bicubic2d_aa(b, node, env)
    # Argument forms an allowlist admits beyond an op's base form (v7 on).
    forms = frozenset(entry.get("forms", ()))
    dtype, shape = (
        _aval(node)
        if "val" in node.meta and node.meta["val"] is not None
        else (None, None)
    )
    rank = len(shape) if shape is not None else 0
    x = env.get(args[0]) if args and hasattr(args[0], "op") else None

    if target in (
        "aten.add.Tensor",
        "aten.sub.Tensor",
        "aten.add.Scalar",
        "aten.sub.Scalar",
    ):
        other = args[1]
        alpha = args[2] if len(args) > 2 else kw.get("alpha", 1)
        op = "add" if target.startswith("aten.add") else "sub"
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
    if target in ("aten.div.Tensor", "aten.div.Scalar"):
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
        if _v8(b):
            return _bitwise(b, node, env, "and")  # integers too (v8)
        # Boolean masks only (KAN's spline interval test): Carbon's `and`.
        if dtype != "bool" or any(b.avals[env[a]][0] != "bool" for a in args[:2]):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.binary("and", args[0], args[1], env, node)
    if target == "aten.floor.default":
        # Floating inputs only; its gradient is 0 everywhere, as torch's.
        if dtype not in _FLOATS or b.avals[x][0] != dtype:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.unary("floor", x)
    if target in ("aten.fmod.Scalar", "aten.fmod.Tensor"):
        # C-style, the dividend's sign: Carbon's rem (lax.rem), never mapped
        # from aten.remainder (Python-style, the divisor's sign), which stays
        # refused. Gradients d/dx = 1, d/dy = -trunc(x / y), as torch's.
        if (
            target == "aten.fmod.Scalar"
            and "integer" in forms
            and dtype == "int32"
            and b.avals[x][0] == "int32"
            and type(args[1]) is int
            and args[1] != 0
        ):
            # v7 form `integer` (CODANO's (arange + k) fmod n roll index): a
            # nonzero integer divisor, so no division by zero; C-style as
            # torch's integer fmod.
            return b.binary("rem", args[0], args[1], env, node)
        if dtype not in _FLOATS or any(
            hasattr(a, "op") and b.avals[env[a]][0] not in _FLOATS for a in args[:2]
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.binary("rem", args[0], args[1], env, node)
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
    if target == "aten.neg.default":
        if b.avals[x][0] != dtype or dtype == "bool":
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.unary("neg", x)
    if target == "aten.log.default":
        if dtype not in _FLOATS or b.avals[x][0] != dtype:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        return b.unary("log", x, accuracy=None)
    if target == "aten.leaky_relu.default":
        # x where x > 0, else slope * x: the gradient at 0 is the slope, as
        # torch's (its backward tests x > 0).
        slope = args[1] if len(args) > 1 else kw.get("negative_slope", 0.01)
        if (
            dtype not in _FLOATS
            or b.avals[x][0] != dtype
            or type(slope) not in (int, float)
            or not math.isfinite(slope)
        ):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        positive = b.emit(
            "gt", [x, b.broadcast(b.scalar(0, dtype), shape)], "bool", shape
        )
        scaled = b.emit(
            "mul",
            [x, b.broadcast(b.scalar(slope, dtype), shape)],
            dtype,
            shape,
            out_dtype=None,
        )
        return b.emit("select_n", [positive, scaled, x], dtype, shape)
    if target == "aten.any.dim":
        # Boolean masks only: any is the int32 mask's reduce_max, then > 0.
        have = b.avals[x][1]
        if b.avals[x][0] != "bool" or dtype != "bool" or not have:
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        dim = args[1] if len(args) > 1 else kw.get("dim")
        keepdim = args[2] if len(args) > 2 else kw.get("keepdim", False)
        dim = _norm(dim, len(have)) if type(dim) is int else -1
        if type(keepdim) is not bool or not 0 <= dim < len(have):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        reduced = [d for i, d in enumerate(have) if i != dim]
        spec = b.allowlist.ops["reduce_max"]["params"]
        out = b.emit(
            "reduce_max",
            [b.to(x, "int32")],
            "int32",
            reduced,
            axes=[dim],
            **({"out_sharding": None} if "out_sharding" in spec else {}),
        )
        out = b.emit(
            "gt", [out, b.broadcast(b.scalar(0, "int32"), reduced)], "bool", reduced
        )
        if reduced != shape:
            out = b.emit(
                "reshape",
                [out],
                "bool",
                shape,
                dimensions=None,
                new_sizes=shape,
                sharding=None,
            )
        return out
    if target == "aten.sigmoid.default":
        return b.unary("logistic", x, accuracy=None)
    if target in ("aten.exp.default", "aten.log1p.default", "aten.sqrt.default"):
        return b.unary(target.split(".")[1], x, accuracy=None)
    if target in ("aten.mean.dim", "aten.mean.default", "aten.var.correction"):
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

        if target in ("aten.mean.dim", "aten.mean.default"):
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
            if "strided" not in forms or type(step) is not int or step < 1:
                raise graph.GraphRefused("aten_arguments_not_supported", target)
            return _slice_scatter_strided(b, node, env, dim, step)
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
            if "transposed" not in forms:
                raise graph.GraphRefused("aten_arguments_not_supported", target)
            return _convolution_transposed(b, node, env)
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
    token = _WIDE.set(allowlist.version in _WIDE_VERSIONS)
    try:
        return _lower(program, allowlist)
    finally:
        _WIDE.reset(token)


def _lower(program, allowlist):
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
