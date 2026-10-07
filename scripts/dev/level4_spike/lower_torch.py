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

from . import graph

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


def _emit(b, node, env):
    """The Carbon value for one Core ATen call, or `GraphRefused`."""
    target = str(node.target)
    args, kw = node.args, node.kwargs
    entry = b.allowlist.aten.get(target)
    if entry is None or entry["default"] == "refuse":
        raise graph.GraphRefused("aten_op_not_allowlisted", target)
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
    if target == "aten.mul.Tensor":
        return b.binary("mul", args[0], args[1], env, node)
    if target == "aten.div.Tensor":
        return b.binary("div", args[0], args[1], env, node)
    if target in (
        "aten.lt.Scalar",
        "aten.lt.Tensor",
        "aten.gt.Scalar",
        "aten.gt.Tensor",
    ):
        op = "lt" if ".lt." in target else "gt"
        operand_dtype = b.avals[env[args[0]]][0]
        return b.binary(op, args[0], args[1], env, node, out_dtype=operand_dtype)
    if target == "aten.where.self":
        cond = b.operand(args[0], env, "bool", shape)
        yes = b.operand(args[1], env, dtype, shape)
        no = b.operand(args[2], env, dtype, shape)
        return b.emit("select_n", [cond, no, yes], dtype, shape)
    if target == "aten.gelu.default":
        return _gelu(b, x, kw.get("approximate", "none"))
    if target == "aten.tanh.default":
        return b.unary("tanh", x, accuracy=None)
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
    if target == "aten._fft_r2c.default":
        dims = [_norm(d, len(b.avals[x][1])) for d in args[1]]
        normalization, onesided = args[2], args[3]
        have = b.avals[x][1]
        if not onesided or dims != list(range(len(have) - len(dims), len(have))):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        lengths = [have[d] for d in dims]
        out = b.emit("fft", [x], dtype, shape, fft_lengths=lengths, fft_type="RFFT")
        return _fft_scale(b, out, normalization, math.prod(lengths), 1.0)
    if target == "aten._fft_c2r.default":
        dims = [_norm(d, len(b.avals[x][1])) for d in args[1]]
        normalization, last = args[2], args[3]
        have = b.avals[x][1]
        if dims != list(range(len(have) - len(dims), len(have))):
            raise graph.GraphRefused("aten_arguments_not_supported", target)
        lengths = [have[d] for d in dims[:-1]] + [last]
        out = b.emit("fft", [x], dtype, shape, fft_lengths=lengths, fft_type="IRFFT")
        n = math.prod(lengths)
        return _fft_scale(b, out, normalization, n, 1 / n)
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
