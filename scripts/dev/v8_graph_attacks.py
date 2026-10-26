"""Pre-mainnet attacks on the v8 graph route (Level 4 allowlist v8, OWNER-GRAPH-OPS-OPEN-01), run offline against the
checked-out build's own lowering, validation and interpreter. Lead scenarios plus the Validator's six (GRAPHITE_TEST.md,
2026-10-26).

    python -m scripts.dev.v8_graph_attacks [--json out.json] [--markdown out.md] [--fast]

Needs the pinned JAX (CPU). No network, no GPU, no container, no key, no sealed material. Scenarios that need the real
worker or a GPU are reported as NOT RUN HERE with what they need; nothing is claimed for them.

Verdicts as in `mainnet_attack_tests`: PASS (protection held), FAIL (an attack succeeded), RISK (admitted by design or
by ruling, with a measured exposure for a decision), INFO (a measurement), NOT_RUN (needs the worker or a GPU).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from scripts.dev.mainnet_attack_tests import Result

ALLOWLIST_V8 = (
    Path(__file__).resolve().parents[2] / "carbon" / "level4" / "allowlist_v8.json"
)


class Lab:
    """Lowering and validation under the v8 allowlist, as the intake does them."""

    def __init__(self):
        import jax  # noqa: F401  (import errors surface here, once)

        from carbon.level4 import allowlist, graph, interpret, validate
        from carbon.level4.tooling import lower_jax

        self.allowlist_module, self.graph = allowlist, graph
        self.interpret, self.validate, self.lower_jax = interpret, validate, lower_jax
        self.al = allowlist.load(ALLOWLIST_V8)
        self.caps = allowlist.caps_for(self.al)

    def doc(self, fn, args, role="forward"):
        closed = self.lower_jax.trace(fn, *args)
        names = (
            ["carbon/key"]
            if role == "init"
            else [f"inputs/{i}" for i in range(len(closed.jaxpr.invars))]
        )
        return self.lower_jax.lower(
            closed, role=role, allowlist=self.al, input_names=names
        )

    def check(self, fn, args, role="forward"):
        """`(status, detail, document bytes, doc)`: status is "admitted" or "refused:<code>"."""
        try:
            doc = self.doc(fn, args, role)
            raw = self.graph.dumps(doc)
            verdict = self.validate.validate(
                self.graph.parse(raw, max_bytes=1 << 27), self.al, caps=self.caps
            )
            return "admitted", verdict, len(raw), doc
        except self.graph.GraphRefused as refused:
            return f"refused:{refused.code}", getattr(refused, "where", ""), 0, None
        except (RecursionError, MemoryError, ValueError, TypeError) as error:
            # Failed before Carbon saw a document: the miner's own tracing, not a gate.
            return f"client_error:{type(error).__name__}", str(error)[:80], 0, None


def _measure(verdict):
    return verdict["measurements"] if isinstance(verdict, dict) else {}


# ------------------------------------------------------------------------------------------------ scenario 1


def s1_platform_branching(lab):
    """A graph that branches on the device platform or on the batch/data shape."""
    import jax.numpy as jnp
    from jax import lax

    x = jnp.ones((4, 3), jnp.float32)
    rows = {}
    for label, fn in {
        "platform_dependent (cpu vs default)": lambda v: lax.platform_dependent(
            v, cpu=lambda a: a * 2.0, default=lambda a: a * 3.0
        ),
        "cond on a data value": lambda v: lax.cond(
            v.sum() > 5.0, lambda a: a * 2.0, lambda a: a * 3.0, v
        ),
        "python branch on the traced shape": lambda v: v
        * (2.0 if v.shape[0] > 3 else 3.0),
    }.items():
        status, verdict, _, doc = lab.check(fn, (x,))
        ops = sorted(_measure(verdict).get("op_counts", {})) if doc else []
        rows[label] = {"status": status, "ops": ops}
    admitted = [k for k, v in rows.items() if v["status"] == "admitted"]
    return Result(
        "V1",
        "platform branching",
        "A graph whose output differs by device platform (GPU vs CPU) or by batch shape (practice query vs grade rows)",
        "caught at lowering/validation, or harmless: the grade device and shape fixed by Carbon",
        f"{len(admitted)} of {len(rows)} variants ADMITTED at validation: {', '.join(admitted)}",
        "RISK" if admitted else "PASS",
        {
            "variants": rows,
            "meaning": "validation does not stop a platform or data branch; what stops it mattering is where Carbon runs the grade "
            "(one fixed device, one case per call, row 0 plus zero filler: direct_graph_construction_worker) and the CPU/GPU "
            "bit-identical specimen rule. NOT RUN HERE: a GPU, so no CPU-vs-GPU output difference was observed. Validator: say which "
            "rule is meant to catch this on a GPU practice host.",
        },
    )


# ------------------------------------------------------------------------------------------------ scenario 2/3


def s2_compute_bombs_pass_validation(lab):
    """Compile/scan/window bombs inside the intake caps: what validation admits and what it measures."""
    import functools

    import jax.numpy as jnp
    from jax import lax

    x = jnp.ones((4, 3), jnp.float32)
    big = jnp.ones((4096, 4096), jnp.float32)
    cases = {
        "scan of 1e9 steps": (
            lambda v: lax.scan(
                lambda c, _: (c * 1.0000001, None), v, None, length=10**9
            )[0],
            (x,),
        ),
        "static fori_loop of 2e8 steps": (
            lambda v: lax.fori_loop(0, 10**8 * 2, lambda i, c: c * 1.0000001, v),
            (x,),
        ),
        "data-dependent while_loop": (
            lambda v: lax.while_loop(lambda c: c.sum() < 1e6, lambda c: c * 2.0, v),
            (x,),
        ),
        "broadcast to 2^34 elements (64 GiB)": (
            lambda v: jnp.broadcast_to(v[:1, :1], (1 << 17, 1 << 17)).sum(),
            (x,),
        ),
        "reduce_window with a 4096x4096 window over 8192x8192": (
            lambda v: lax.reduce_window(
                jnp.broadcast_to(v[:1, :1], (8192, 8192)),
                0.0,
                lax.add,
                (4096, 4096),
                (1, 1),
                "VALID",
            ).sum(),
            (x,),
        ),
        "50 chained 4096x4096 matmuls": (
            lambda v: functools.reduce(lambda a, _: a @ a * 1e-3, range(50), v),
            (big,),
        ),
        "nested jit depth 40": (_nested(40), (x,)),
    }
    rows = {}
    for label, (fn, args) in cases.items():
        status, verdict, nbytes, _ = lab.check(fn, args)
        m = _measure(verdict)
        rows[label] = {
            "status": status,
            "nodes_executed": m.get("nodes_executed"),
            "largest_intermediate_bytes": m.get("largest_intermediate_bytes"),
            "document_bytes": nbytes or None,
        }
    admitted = [k for k, v in rows.items() if v["status"] == "admitted"]
    return Result(
        "V2",
        "compute bombs",
        "Compile/scan/window/memory bombs that are small documents: admitted by validation, left to the runtime walls",
        "refused statically, or bounded at runtime by a typed CANDIDATE failure (never FAILED_INFRA, never a stalled queue)",
        f"{len(admitted)} of {len(cases)} admitted at validation: {', '.join(admitted)}; only the data-dependent while is refused",
        "RISK",
        {
            "rows": rows,
            "v8_caps": lab.caps,
            "meaning": "nodes_executed and largest_intermediate_bytes are measured but uncapped in v7/v8 (only constants and containment "
            "bound). The protection is the build wall (648 s on the old routes, 30 min on graph route v2), the inference wall, the "
            "16 GiB memory limit and the compile gate (120 s, compile_deadline). NOT RUN HERE: the worker. Phase 2 sends these through "
            "the real graph route on the 32 GB host and records the typed outcome.",
        },
    )


def _nested(depth):
    def build(v):
        import jax

        f = lambda a: a + 1.0
        for _ in range(depth):
            f = jax.jit(lambda a, _f=f: _f(a) * 1.0)
        return f(v)

    return build


def s2b_scan_cost_per_step(lab):
    """Measured interpreter cost of one scan step, to size a wall-evading loop."""
    import jax.numpy as jnp
    from jax import lax

    x = jnp.ones((4, 3), jnp.float32)
    steps = 200_000
    fn = lambda v: lax.scan(lambda c, _: (c * 1.0000001, None), v, None, length=steps)[
        0
    ]
    status, _, _, doc = lab.check(fn, (x,))
    if doc is None:
        return Result(
            "V2b",
            "compute bombs",
            "Interpreter cost per scan step",
            "recorded",
            status,
            "INFO",
        )
    rebuilt = lab.interpret.rebuild(doc, lab.al)
    rebuilt(x)[0].block_until_ready()  # compile
    t0 = time.perf_counter()
    rebuilt(x)[0].block_until_ready()
    per_step = (time.perf_counter() - t0) / steps
    return Result(
        "V2b",
        "compute bombs",
        "Cost of one scan step in the rebuilt graph (CPU), to size a loop that evades the build wall",
        "recorded",
        f"{per_step * 1e9:.0f} ns per step; a 648 s wall allows about {648 / per_step:.2e} steps, a 1800 s wall {1800 / per_step:.2e}",
        "INFO",
        {"steps_measured": steps},
    )


# ------------------------------------------------------------------------------------------------ scenario 5


def _hidden_table(n, seed):
    import numpy as np

    return np.random.default_rng(seed).integers(0, 65536, size=n)


def s5a_structure_smuggling(lab, n=24000):
    """Arbitrary data hidden in slice start indices: no constant is added, so the 16 KiB cap sees nothing."""
    import jax.numpy as jnp
    import numpy as np
    from jax import lax

    secret = _hidden_table(n, 1)
    x = jnp.ones((2, n), jnp.float32)

    def forward(v):
        base = lax.iota(jnp.float32, 65536) / 65536.0
        cells = [lax.slice(base, (int(k),), (int(k) + 1,)) for k in secret]
        return v * jnp.concatenate(cells)[None, :]

    status, verdict, nbytes, doc = lab.check(forward, (x,))
    recovered = None
    if doc is not None:
        out = np.asarray(lab.interpret.rebuild(doc, lab.al)(x)[0])
        recovered = bool(np.array_equal(np.rint(out[0] * 65536).astype(int), secret))
    m = _measure(verdict)
    cap = lab.caps["constant_bytes"]
    hidden = n * 2
    return Result(
        "V5a",
        "constant smuggling",
        f"{hidden} bytes of arbitrary data hidden in {n} slice start indices (no constant carries them)",
        f"refused, or counted against the {cap}-byte constants cap",
        f"{status}; constant_info_bytes {m.get('constant_info_bytes')} against {hidden} bytes hidden; "
        f"recovered exactly by the rebuilt graph: {recovered}; document {nbytes} bytes",
        "FAIL" if status == "admitted" and recovered else "PASS",
        {
            "cap_bytes": cap,
            "hidden_bytes": hidden,
            "multiple_of_cap": round(hidden / cap, 2),
            "capacity": "each node carries up to ~16 bits in a static index; the v8 document cap is "
            f"{lab.caps['document_bytes']} bytes (about 150 bytes a node), so the structure channel is worth hundreds of KB",
            "suggest": "charge the information in static integer params (slice/gather indices, shapes, iota sizes) under the same cap "
            "(accounting v5), or cap nodes_stored as v6 did",
        },
    )


def s5b_wide_float_charging(lab):
    """float64 and complex128 constants are charged 4 bytes a value but hold 8 (16)."""
    import jax
    import numpy as np

    cap = lab.caps["constant_bytes"]
    rows, wins = {}, []
    for dtype, per_value_held in (("float64", 8), ("complex128", 16)):
        n = cap // (4 if dtype == "float64" else 8)  # exactly the cap by the v4 rule
        rng = np.random.default_rng(2)
        table = rng.standard_normal(n).astype(dtype)
        if dtype == "complex128":
            table = table + 1j * rng.standard_normal(n)
        import jax.numpy as jnp

        with jax.enable_x64(True):
            x = jnp.ones((2, n), jnp.float64 if dtype == "float64" else jnp.complex128)
            status, verdict, _, _ = lab.check(
                lambda v, t=table: v * jnp.asarray(t)[None, :], (x,)
            )
        m = _measure(verdict)
        held = n * per_value_held
        rows[dtype] = {
            "status": status,
            "values": n,
            "constant_info_bytes": m.get("constant_info_bytes"),
            "bytes_held": held,
            "multiple": round(held / cap, 2),
        }
        if status == "admitted":
            wins.append(dtype)
    return Result(
        "V5b",
        "constant smuggling",
        "float64 / complex128 constants at the cap: charged by the v4 rule, holding twice that",
        "charged what they hold ('never more than the value holds', accounting v4)",
        "; ".join(
            f"{d}: {r['status']}, charged {r['constant_info_bytes']} B, holds {r['bytes_held']} B ({r['multiple']}x)"
            for d, r in rows.items()
        ),
        "FAIL" if wins else "PASS",
        {
            "rows": rows,
            "rule": "graph.float_value_bits caps every float at VALUE_BYTES = 4, complex at two components",
        },
    )


def s5c_arithmetic_table_control(lab):
    """A table rebuilt from iota arithmetic plus few constants: carries only its formula (control)."""
    import jax.numpy as jnp
    from jax import lax

    n = 20000
    x = jnp.ones((2, n), jnp.float32)
    fn = lambda v: v * jnp.sin(lax.iota(jnp.float32, n) * 0.001)[None, :]
    status, verdict, nbytes, _ = lab.check(fn, (x,))
    m = _measure(verdict)
    return Result(
        "V5c",
        "constant smuggling",
        "A 20000-value table from iota arithmetic and one constant (control: honest structured weights)",
        "admitted, charged for its one constant",
        f"{status}; constant_info_bytes {m.get('constant_info_bytes')}; document {nbytes} bytes",
        (
            "PASS"
            if status == "admitted" and m.get("constant_info_bytes", 99999) <= 16
            else "INFO"
        ),
    )


def s5d_half_precision_and_integer_packing(lab):
    """fp16/bf16, int packing and bool tables are charged what they hold."""
    import jax.numpy as jnp
    import numpy as np

    cap = lab.caps["constant_bytes"]
    out = {}
    rng = np.random.default_rng(3)
    for dtype, per_value_bits in (
        ("float16", 16),
        ("bfloat16", 16),
        ("int8", 8),
        ("uint8", 8),
    ):
        n = (cap * 8) // per_value_bits
        if dtype in ("int8", "uint8"):
            low, high = (0, 256) if dtype == "uint8" else (-128, 128)
            table = rng.integers(low, high, size=n).astype(
                dtype
            )  # the full range, so 8 bits are really held
        else:
            table = rng.standard_normal(n).astype("float32")
        arr = jnp.asarray(table).astype(dtype)
        x = jnp.ones((2, n), jnp.float32)
        status, verdict, _, _ = lab.check(
            lambda v, a=arr: v * a.astype(jnp.float32)[None, :], (x,)
        )
        m = _measure(verdict)
        out[dtype] = {
            "values": n,
            "status": status,
            "constant_info_bytes": m.get("constant_info_bytes"),
            "bytes_held": (n * per_value_bits) // 8,
        }
    leaks = {
        d: r
        for d, r in out.items()
        if r["status"] == "admitted"
        and (r["constant_info_bytes"] or 0) < r["bytes_held"] * 0.99
    }
    return Result(
        "V5d",
        "constant smuggling",
        "A cap-sized table packed as fp16 / bf16 / int8 / uint8: charged by real storage",
        "charged what it holds",
        "undercharged: "
        + (", ".join(leaks) or "none")
        + "; "
        + "; ".join(
            f"{d}: charged {r['constant_info_bytes']} holds {r['bytes_held']}"
            for d, r in out.items()
        ),
        "FAIL" if leaks else "PASS",
        {"rows": out},
    )


# ------------------------------------------------------------------------------------------------ scenario 6


def s6_identical_copies(lab):
    """Identical big constants are counted once; the same bytes under another dtype/shape are not merged."""
    import jax.numpy as jnp
    import numpy as np

    table = np.arange(4000, dtype=np.float32) * 0.37
    x = jnp.ones((2, 4000), jnp.float32)
    t = jnp.asarray(table)
    once = lab.check(lambda v: v * t[None, :], (x,))
    many = lab.check(
        lambda v: v * (t[None, :] + t[None, :] * 0.0 + t[None, :] * 0.0), (x,)
    )
    as_uint = jnp.asarray(table.view(np.uint32))
    asint = lab.check(
        lambda v: v * t[None, :] + as_uint.astype(jnp.float32)[None, :] * 0.0, (x,)
    )
    info = lambda r: _measure(r[1]).get("constant_info_bytes", r[0])
    return Result(
        "V6",
        "constant smuggling",
        "Identical-copy tricks: the same table referenced many times, and the same bytes under another dtype",
        "counted once for identical copies; not merged across dtypes (no under-charge)",
        f"one use {info(once)} B; three uses {info(many)} B; the same bytes also as a uint32 table: {info(asint)} B (the float table plus the uint32 table)",
        "PASS" if info(once) is not None and info(many) == info(once) else "INFO",
    )


# ------------------------------------------------------------------------------------------------ scenario 7/8


def s7_nondeterministic_ops(lab):
    """Admitted ops whose results can differ between CPU and GPU (or between runs) and how v8 treats them."""
    doc = json.loads(ALLOWLIST_V8.read_text())
    ops = doc["carbon_ops"]
    suspect_names = (
        "scatter",
        "sort",
        "approx_top_k",
        "cumsum",
        "cumprod",
        "cummax",
        "cumlogsumexp",
        "reduce_precision",
        "rng",
        "random",
        "argmax",
        "argmin",
        "top_k",
        "segment",
        "reduce_sum",
        "dot_general",
        "conv",
        "fft",
    )
    rows = {}
    for name, entry in sorted(ops.items()):
        if any(s in name for s in suspect_names):
            rows[name] = {
                "default": entry.get("default"),
                "category": entry.get("category"),
            }
    admitted = {n: r for n, r in rows.items() if r["default"] != "refuse"}
    review = {n: r for n, r in rows.items() if r["default"] == "review"}
    return Result(
        "V7",
        "nondeterminism",
        "Admitted ops whose CPU and GPU results (or two runs on one device) can differ: scatter-add, sort, top-k, reductions, matmul/conv/fft",
        "each is either refused, flagged for review, or covered by the bit-identical CPU/GPU specimen rule",
        f"{len(admitted)} candidate ops admitted ({len(review)} flagged review): {', '.join(sorted(admitted))[:300]}",
        "RISK",
        {
            "admitted": admitted,
            "unseeded_rng": {
                n: ops[n]["default"] for n in ops if ops[n].get("category") == "rng"
            },
            "meaning": "v8 admits these by ruling (every pure deterministic array op); 'deterministic' on one device is not 'bit-identical across "
            "CPU and GPU'. NOT RUN HERE: a GPU. The Validator's specimen rule is the control; it should list which of these it covers.",
        },
    )


def s8_init_misuse(lab):
    """Init graphs: ignoring the key, a constant key, returning the key, and structure smuggling in init."""
    import jax
    import jax.numpy as jnp
    from jax import lax

    k0 = jnp.zeros(2, jnp.uint32)
    n = 24000
    secret = _hidden_table(n, 4)

    def smuggled(key):
        base = lax.iota(jnp.float32, 65536) / 65536.0
        return jnp.concatenate(
            [lax.slice(base, (int(v),), (int(v) + 1,)) for v in secret]
        )

    rows = {
        "ignore the key, fixed arithmetic table": lab.check(
            lambda k: jnp.arange(9.0).reshape(3, 3), (k0,), role="init"
        )[0],
        "constant-key RNG (no Carbon key)": lab.check(
            lambda k: jax.random.normal(jax.random.PRNGKey(0), (3, 3)),
            (k0,),
            role="init",
        )[0],
        "return the key": lab.check(lambda k: k, (k0,), role="init")[0],
        f"{n * 2}-byte table hidden in slice indices": lab.check(
            smuggled, (k0,), role="init"
        )[0],
    }
    smuggle_ok = rows[f"{n * 2}-byte table hidden in slice indices"] == "admitted"
    return Result(
        "V8",
        "init graph misuse",
        "Init-graph RNG misuse: a constant key, ignoring Carbon's key, returning the key, a pretrained table hidden in structure",
        "constant-key RNG and key return refused; key-ignoring structured init admitted by ruling; a hidden pretrained table refused",
        "; ".join(f"{k}: {v}" for k, v in rows.items()),
        "FAIL" if smuggle_ok else "PASS",
        {
            "rows": rows,
            "ruling": "VALIDATOR_GRAPH_OPS_V8_RULINGS row 2 removed the keyed-or-fill rule on the strength of the constants cap, which V5a bypasses",
        },
    )


def s11_structure_only_capacity(lab):
    """The smallest graph that carries a 1,000-float table through structure alone (no constant, no static parameter):
    measured as op-and-wiring chains of N nodes, with the information each node can carry and what N it takes.
    """
    import math
    import random

    import jax.numpy as jnp
    from jax import lax

    ops = (jnp.add, jnp.subtract, jnp.multiply, jnp.maximum, jnp.minimum)
    rows = []
    for n in (1000, 4000, 16000):
        rng = random.Random(n)
        plan = [
            (rng.randrange(len(ops)), rng.randrange(max(1, k + 1))) for k in range(n)
        ]

        def forward(v, plan=plan):
            vals = [lax.iota(jnp.float32, 1000) / 1000.0]
            for op_index, wire in plan:
                vals.append(ops[op_index](vals[-1], vals[wire]))
            return v * vals[-1][None, :]

        x = jnp.ones((2, 1000), jnp.float32)
        t0 = time.perf_counter()
        status, verdict, nbytes, doc = lab.check(forward, (x,))
        t_check = time.perf_counter() - t0
        compile_s = None
        if doc is not None:
            rebuilt = lab.interpret.rebuild(doc, lab.al)
            t1 = time.perf_counter()
            rebuilt(x)[0].block_until_ready()
            compile_s = time.perf_counter() - t1
        m = _measure(verdict)
        bits_per_node = math.log2(len(ops)) + math.log2(
            max(2, n / 2)
        )  # op choice plus a wiring choice into the earlier nodes
        rows.append(
            {
                "nodes": n,
                "status": status,
                "document_bytes": nbytes,
                "bytes_per_node": round(nbytes / n, 1) if nbytes else None,
                "constant_info_bytes": m.get("constant_info_bytes"),
                "lower_and_validate_s": round(t_check, 1),
                "first_call_compile_s": (
                    None if compile_s is None else round(compile_s, 1)
                ),
                "info_bits_per_node_upper": round(bits_per_node, 1),
            }
        )
    last = rows[-1]
    need_bits = 1000 * 24
    nodes_needed = (
        int(need_bits / last["info_bits_per_node_upper"])
        if last["info_bits_per_node_upper"]
        else None
    )
    doc_estimate = (
        None
        if not last["bytes_per_node"]
        else int(nodes_needed * last["bytes_per_node"])
    )
    return Result(
        "V11",
        "constant smuggling",
        "Structure-only capacity: op-and-wiring chains with no constant and no static parameter; how big a graph carries a 1,000-float table",
        "recorded (accounting v5 charges constants and static parameters, not topology)",
        "; ".join(
            f"{r['nodes']} nodes: {r['status']}, {r['document_bytes']} B ({r['bytes_per_node']} B/node), compile {r['first_call_compile_s']} s, constants charged {r['constant_info_bytes']} B"
            for r in rows
        )
        + f". Capacity bound, not a constructed decoder: 1,000 floats at 24 bits need at least {nodes_needed} nodes, about {doc_estimate} document bytes",
        "INFO",
        {
            "rows": rows,
            "assumption": "each node carries at most log2(ops) + log2(wiring choices) bits; a decoder that reaches an arbitrary table needs more nodes, never fewer",
            "reading": "the structure channel is not closed by accounting v5; it is made expensive: a 16 KiB table costs this many nodes of document and compile time",
        },
    )


# ------------------------------------------------------------------------------------------------ scenario 4/9/10 (static)

CODE = re.compile(r'GraphRefused\(\s*"([a-z0-9_]+)"')


def s4_refusal_codes_closed(lab):
    """Every refusal code the graph route can emit is a fixed identifier; none embeds a measured value."""
    root = Path(__file__).resolve().parents[2] / "carbon"
    codes, dynamic = set(), []
    for path in list((root / "level4").glob("*.py")) + [
        root / "development_session" / "build_refusal_v2.py"
    ]:
        text = path.read_text(encoding="utf-8")
        codes.update(CODE.findall(text))
        dynamic += [
            f"{path.name}: {m.group(0)}"
            for m in re.finditer(r'GraphRefused\(\s*f"[^"]*\{[^"]*"', text)
        ]
    numeric = [c for c in codes if re.search(r"\d", c)]
    return Result(
        "V4",
        "refusal oracle",
        "Refusal/reason codes of the graph route: closed identifiers, nothing about the sealed set",
        "closed code set; no interpolated measurement",
        f"{len(codes)} fixed codes; {len(dynamic)} refusals build their code with an f-string; {len(numeric)} codes contain digits",
        "PASS" if not dynamic else "INFO",
        {
            "dynamic": dynamic[:10],
            "numeric_codes": numeric[:10],
            "where": "the 'where' part names a node/output position in the miner's OWN document, never sealed material",
            "note": "grade replies (Ladder, king document, comparator, cap refusals) are covered by G5d/G6a; practice replies and the live refusal text need the worker (NOT RUN HERE)",
        },
    )


def s10_timing_run_static(lab):
    """The practice timing run: read the code path for what data it uses and what it returns."""
    root = Path(__file__).resolve().parents[2] / "carbon" / "development_session"
    text = (root / "direct_graph_construction_worker.py").read_text(encoding="utf-8")
    uses_inputs = "timed_query" in text and '"inputs": inputs' in text
    graded_one_case = "per_case=True" in text and "measure_query=False" in text
    return Result(
        "V10",
        "timing side channel",
        "The practice timing run: which data it times and whether grade timing can leak",
        "times only public practice inputs; the grade call is a separate per-case run that is not timed or returned",
        f"timed query shares the build's `inputs` argument: {uses_inputs}; the graded inference runs per case with measure_query False: {graded_one_case}",
        "INFO",
        {
            "needs": "who passes `inputs` on the grade path (receiver) vs the practice path (Launchpad) and whether measure_query=True can ever reach a receiver grade; "
            "direct_receiver.py:402/1227/1294 read measure_query from the task config, so the receiver decides. Static review only; NOT RUN HERE."
        },
    )


def run(fast=False):
    lab = Lab()
    steps = [
        s1_platform_branching,
        s2_compute_bombs_pass_validation,
        s2b_scan_cost_per_step,
        s4_refusal_codes_closed,
        s5a_structure_smuggling,
        s5b_wide_float_charging,
        s5c_arithmetic_table_control,
        s5d_half_precision_and_integer_packing,
        s6_identical_copies,
        s7_nondeterministic_ops,
        s8_init_misuse,
        s11_structure_only_capacity,
        s10_timing_run_static,
    ]
    results = []
    for step in steps:
        try:
            results.append(step(lab))
        # A crashing scenario is a finding about the harness, never a silent pass.
        except Exception as error:  # noqa: BLE001
            results.append(
                Result(
                    step.__name__,
                    "harness",
                    step.__doc__.split(".")[0],
                    "runs",
                    f"{type(error).__name__}: {str(error)[:200]}",
                    "INFO",
                )
            )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args(argv)
    results = run(args.fast)
    lines = ["| id | area | verdict | attack | observed |", "|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.id} | {r.area} | **{r.verdict}** | {r.title} | {r.observed} |"
        )
    text = "\n".join(lines) + "\n"
    print(text)
    if args.json:
        args.json.write_text(
            json.dumps([r.__dict__ for r in results], indent=1, default=str),
            encoding="utf-8",
        )
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    return 1 if any(r.verdict == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
