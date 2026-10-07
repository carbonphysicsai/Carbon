"""Phase 0 probes: D6 measurements and serialization safety. Challenge-neutral.

Every number here is a measurement of a legitimate graph. None is compared
against a cap: the caps stay `HUMAN_INPUT` (`allowlist.CAPS`).
"""

from __future__ import annotations

import io
import resource
import time
import zipfile

from . import graph, lower_jax


def _rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def compile_measure(fn, args):
    """XLA compile time and the compiled program's own memory and cost."""
    import jax

    lowered = jax.jit(fn).lower(*args)
    started = time.perf_counter()
    compiled = lowered.compile()
    seconds = time.perf_counter() - started
    memory = compiled.memory_analysis()
    cost = compiled.cost_analysis() or {}
    if isinstance(cost, list):
        cost = cost[0] if cost else {}
    hlo = lowered.as_text()
    return {
        "compile_seconds": round(seconds, 3),
        "argument_bytes": int(memory.argument_size_in_bytes),
        "output_bytes": int(memory.output_size_in_bytes),
        "temp_bytes": int(memory.temp_size_in_bytes),
        "generated_code_bytes": int(memory.generated_code_size_in_bytes),
        "flops": float(cost.get("flops", 0.0)),
        "bytes_accessed": float(cost.get("bytes accessed", 0.0)),
        "stablehlo_text_bytes": len(hlo.encode()),
        "process_peak_rss_mb": round(_rss_mb(), 1),
    }


def jax_graph_measure(fn, args, *, role, allowlist, input_names):
    """Inventory and Carbon-graph counts for `fn` at `args`."""
    closed = lower_jax.trace(fn, *args)
    inventory = lower_jax.inventory(closed)
    doc = lower_jax.lower(
        closed, role=role, allowlist=allowlist, input_names=input_names
    )
    return inventory, graph.measure(doc), doc


# --- Serialization -------------------------------------------------------------


def jax_export_probe(fn, args):
    """What the pinned JAX can do with an exported StableHLO artifact."""
    import jax
    from jax._src.interpreters import mlir
    from jax._src.lib.mlir import ir

    out = {}
    exported = jax.export.export(jax.jit(fn))(*args)
    try:
        blob = exported.serialize()
        out["serialize"] = {"available": True, "bytes": len(blob)}
    except ImportError as missing:
        out["serialize"] = {"available": False, "reason": str(missing)}
    text = exported.mlir_module()
    ops = set()
    with mlir.make_ir_context():
        module = ir.Module.parse(text)

        def walk(op):
            ops.add(op.operation.name)
            for region in op.regions:
                for block in region.blocks:
                    for inner in block.operations:
                        walk(inner)

        walk(module.operation)
    out["stablehlo_text"] = {
        "bytes": len(text.encode()),
        "parsed_by": "MLIR C++ parser in jaxlib (ir.Module.parse)",
        "ops": sorted(ops),
    }
    out["in_memory_has_vjp"] = exported.has_vjp()
    callback = jax.export.export(
        jax.jit(
            lambda x: jax.pure_callback(
                lambda v: v, jax.ShapeDtypeStruct(x.shape, x.dtype), x
            )
        )
    )
    try:
        callback(*args[-1:])
        out["export_of_pure_callback"] = "allowed"
    except Exception as refused:  # noqa: BLE001 - recorded, not handled
        out["export_of_pure_callback"] = f"refused: {type(refused).__name__}"
    return out


def torch_export_probe(program):
    """The contents of a `torch.export.save` archive, and what loading it runs."""
    import torch

    from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

    buffer = io.BytesIO()
    torch.export.save(program, buffer)
    raw = buffer.getvalue()
    entries = []
    archive = zipfile.ZipFile(io.BytesIO(raw))
    for info in archive.infolist():
        data = archive.read(info.filename)
        kind = "json" if data[:1] == b"{" else "zip" if data[:2] == b"PK" else "bytes"
        if kind == "zip":
            inner = zipfile.ZipFile(io.BytesIO(data))
            pickles = [
                i.filename
                for i in inner.infolist()
                if inner.read(i.filename)[:1] == b"\x80"
            ]
            entries.append(
                {
                    "name": info.filename,
                    "bytes": info.file_size,
                    "kind": "zip",
                    "pickle_members": pickles,
                }
            )
            continue
        entry = {"name": info.filename, "bytes": info.file_size, "kind": kind}
        if kind == "json":
            try:
                parse_strategy(data, max_bytes=len(data))
                entry["strict_json"] = "ok"
            except MalformedStrategy as refused:
                entry["strict_json"] = refused.code
        entries.append(entry)
    calls = []
    original = torch.load

    def spy(*args, **kwargs):
        calls.append({"weights_only": kwargs.get("weights_only", "default")})
        return original(*args, **kwargs)

    torch.load = spy
    try:
        torch.export.load(io.BytesIO(raw))
    finally:
        torch.load = original
    return {
        "archive_bytes": len(raw),
        "entries": entries,
        "torch_load_calls_on_load": calls,
    }
