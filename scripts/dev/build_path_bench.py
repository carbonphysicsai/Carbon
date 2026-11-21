"""Concurrent graph builds through the door's own build path, on a box with no door (S6c / P-10 Option 1).

DEVELOPMENT, public inputs only. Each build is the call a door's graph GPU lane makes
(`research_tasks._run_queued_task` -> `reconstruct_and_infer_graph_public` with `_graph_lane`'s arguments: the
build child in the JAX GPU worker on the GPU, the inference child in the CPU worker on the CPU), on the version's
served kit material (binding, limits document with its registered walls, public TRAIN, practice query, allowlist),
from a scratch campaign ledger whose workspace holds the graph exactly as a miner's upload does. Every build is bound
to one slot's cores (`grade_lanes.Lane`), so both of its containers take exactly that cpuset, as on a lane.

Per build it prints ONE JSON line: concurrency, build index, recipe name, seed, wall / build / inference seconds,
outcome ("OK" or the typed code) and the state digest; per concurrency level one summary line (p50 / p90 wall,
failures, builds per hour). No prediction, case value or path is printed. Nothing here grades, ranks or registers.

Input layout, one directory per recipe (``--recipe-dir``, repeatable; release writes it from public code):

    DIR/recipe.json   the canonical graph recipe (graph_adapters.graph_recipe at the starter's STEPS)
    DIR/graph/        the staged graph: level4 manifest + <hex>.json documents (carbon.level4.staging.write_directory)

The recipe names no seed: the build seed is the door's, so this tool gives build i the seed ``--seed-base + i``
(hybrid seeds 0, 1, 2 are three builds of ONE recipe file).

    python scripts/dev/build_path_bench.py --challenge electric-motor-magnetics --version 1.8 \\
        --recipe-dir R/hybrid --recipe-dir R/fit --recipe-dir R/mlp \\
        --gpu-image-identity jax-gpu.json --cpu-image-identity cpu.json \\
        --slot-cpusets 0-3,4-7,8-11,12-15 --concurrency 1,2,3,4 --work /scratch/bench

``--gpu-slot-values FILE`` runs every GPU build inside the door's GPU build slot pool for the Challenge, as the door's
graph GPU lane does (`remote_gpu_build.offered_for`): the values row in FILE names the class (device kind, slots,
memory mode) and this host's slot lane record (`<HOST_ROOT>/remote-gpu-build-lanes.json`, no docker_host: a LOCAL
lane on this GPU, beside its device record) gives each slot its cores, so N builds take N slots of ONE device. Without
it, a build uses the host's single miner GPU route, which admits one GPU launch per host (a second concurrent one is
`reconstruction.worker.launch.conflict`): concurrency above 1 then measures nothing (S6c, 21 Nov 2026).

``--cpu-build`` builds on the CPU worker instead (no GPU: the door's laneless graph route). Run it on the box (never on
the live door host, TEAM_RULES #15); v2 receipts the run line.
"""

from __future__ import annotations

import argparse
import json
import queue
import statistics
import sys
import threading
import time
from pathlib import Path

SCHEMA = "carbon.build-path-bench.v1"
OWNER = "bench"
_PHASES = threading.local()


def load_recipes(directories):
    """``[(name, recipe dict, raw_manifest, files)]``: each directory's recipe and its staged graph, the graph's
    submission digest checked against the one the recipe names."""
    from carbon.level4 import staging

    loaded = []
    for directory in directories:
        root = Path(directory)
        recipe = json.loads((root / "recipe.json").read_bytes())
        digest, raw_manifest, files = staging.read_directory(root / "graph")
        if recipe.get("source", {}).get("submission_digest") != digest:
            raise SystemExit(
                f"{root.name}: the graph's submission digest is not the recipe's"
            )
        loaded.append((root.name, recipe, raw_manifest, files))
    if len({name for name, *_ in loaded}) != len(loaded):
        raise SystemExit("recipe directory names must differ")
    return loaded


def scratch_ledger(path):
    """A frozen, uncapped development ledger (the `practice_v2_curves` shape), one per build."""
    from carbon.development_session.research_ledger import VERSION, CampaignLedger

    path.mkdir(parents=True, exist_ok=False)
    ledger = CampaignLedger(path, clock=lambda: int(time.time()))
    ledger.freeze(
        {
            "schema": VERSION,
            "campaign_id": "build-path-bench",
            "implementation": "build_path_bench",
            "objective": "build-path-bench-only",
            "sampling": "none",
            "control": "build-path-bench-only",
            "selection": "build-path-bench-only",
            "replica_policy": "none",
            "provider": "none",
            "owner": OWNER,
        }
    )
    return ledger


def stage(ledger, raw_manifest, files):
    """The graph in the scratch owner's workspace under the names a miner's upload uses."""
    from carbon.development_session.research_workspace import ResearchWorkspace
    from carbon.level4 import staging

    workspace = ResearchWorkspace(ledger, OWNER)
    for name, body in staging.workspace(raw_manifest, files).items():
        workspace.put(name, body)


def _timed(name, function):
    """``function`` with its wall seconds kept for this thread's build (`_PHASES`); behaviour unchanged."""

    def timed(*args, **kwargs):
        began = time.monotonic()
        try:
            return function(*args, **kwargs)
        finally:
            phases = getattr(_PHASES, "seconds", None)
            if phases is not None:
                phases[name] = phases.get(name, 0.0) + time.monotonic() - began

    return timed


def instrument():
    """Time the build child and the inference child inside the door's own entry (module attributes it calls)."""
    from carbon.development_session import direct_graph_construction_worker as worker

    worker.reconstruct_public_graph = _timed("build", worker.reconstruct_public_graph)
    worker._infer_state = _timed("inference", worker._infer_state)


def gpu_offer(args, context):
    """The door's GPU slot pool offer for one build (`remote_gpu_build.offered_for`, the call `research_tasks` makes), or
    a no-op without `--gpu-slot-values` (the host's single miner GPU route)."""
    from contextlib import nullcontext

    from carbon.reconstruction import remote_gpu_build

    if context.get("gpu_values") is None:
        return nullcontext()
    return remote_gpu_build.offered_for(
        args.challenge,
        args.version,
        values=context["gpu_values"],
        image_id=context["gpu_image"].image_id,
    )


def gpu_pool(args):
    """The pinned slot pool for `--gpu-slot-values` (its header fields), or None without it; SystemExit when the values
    row or this host's slot lane is missing, or a concurrency level exceeds its slots.
    """
    from carbon.reconstruction import remote_gpu_build

    if args.gpu_slot_values is None:
        return None
    try:
        pool = remote_gpu_build.door_pool(
            args.challenge, args.version, values=Path(args.gpu_slot_values)
        )
    except (ValueError, OSError) as error:
        raise SystemExit(f"GPU slot pool refused: {error}") from None
    if pool is None or pool.local is None:
        raise SystemExit(
            "no GPU slot pool: the values file needs this Challenge's row and this host a local slot lane record"
        )
    if max(args.concurrency) > pool.slots:
        raise SystemExit("a --concurrency level exceeds the pool's slots")
    remote_gpu_build.pin(args.challenge, args.version, pool)
    return {"kind": pool.kind, "slots": pool.slots, "memory": pool.memory}


def one_build(job, args, context):
    """One build through `reconstruct_and_infer_graph_public`, bound to its slot's lane; its printed record."""
    from carbon.development_session import graph_adapters
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        graph_envelope_from_workspace,
    )
    from carbon.development_session.direct_graph_construction_worker import (
        reconstruct_and_infer_graph_public,
    )
    from carbon.development_session.research_carrier import MINER_GPU
    from carbon.reconstruction import grade_lanes

    n, index, slot, (name, recipe_value, raw_manifest, files) = job
    seed = args.seed_base + index
    material, kit = context["material"], context["material"]["construction_kit"]
    record = {"n": n, "build": index, "recipe": name, "seed": seed}
    _PHASES.seconds = {}
    began = time.monotonic()
    try:
        ledger = scratch_ledger(Path(args.work) / f"n{n}" / f"b{index}")
        stage(ledger, raw_manifest, files)
        recipe = ConstructionRecipe.from_dict(recipe_value)
        envelope = graph_envelope_from_workspace(ledger, OWNER, recipe)
        spec = graph_adapters.module_for(args.challenge, args.version).spec_for(
            args.challenge, args.version
        )
        lane_args = (
            {"image": context["cpu_image"]}
            if args.cpu_build
            else {
                "image": context["gpu_image"],
                "accelerator": MINER_GPU,
                "inference_image": context["cpu_image"],
                "inference_accelerator": None,
            }
        )
        lane = grade_lanes.Lane(slot, args.slot_cpusets[slot], str(context["locks"]))
        with grade_lanes.bound(lane), gpu_offer(args, context):
            result = reconstruct_and_infer_graph_public(
                ledger,
                owner=OWNER,
                identity=f"bench-n{n}-b{index}",
                **lane_args,
                recipe=recipe,
                challenge_binding={
                    "challenge_id": kit["id"],
                    "challenge_version": kit["version"],
                    "train_digest": kit["train_digest"],
                    "interface_digest": kit["interface_digest"],
                    "construction_limits_digest": kit["construction_limits_digest"],
                },
                limits_document=material["construction_limits_document"],
                source_envelope=envelope,
                train=material["train"],
                seed=seed,
                inputs=material["practice_inputs"],
                expected_output_shape=material["expected_output_shape"],
                allowlist_bytes=material["allowlist_bytes"],
                adapter_id=spec.adapter_id,
            )
        build = getattr(result, "build", None)
        record["outcome"] = "OK" if build is not None else type(result).__name__
        record["state_digest"] = None if build is None else build.state_digest
    # A build that fails is a row with its typed code, not a stop.
    except Exception as failure:  # noqa: BLE001
        record["outcome"] = getattr(failure, "code", None) or type(failure).__name__
        record["state_digest"] = None
    record["wall_s"] = round(time.monotonic() - began, 1)
    phases = _PHASES.seconds
    record["build_s"] = round(phases["build"], 1) if "build" in phases else None
    record["inference_s"] = (
        round(phases["inference"], 1) if "inference" in phases else None
    )
    return record


def _percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def summary(n, records, seconds):
    walls = [r["wall_s"] for r in records if r["outcome"] == "OK"]
    return {
        "summary": True,
        "n": n,
        "builds": len(records),
        "failed": sum(r["outcome"] != "OK" for r in records),
        "wall_p50_s": statistics.median(walls) if walls else None,
        "wall_p90_s": _percentile(walls, 0.9) if walls else None,
        "builds_per_hour": round(len(walls) * 3600 / seconds, 1) if seconds else None,
    }


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--recipe-dir", action="append", required=True)
    parser.add_argument("--gpu-image-identity")
    parser.add_argument("--cpu-image-identity", required=True)
    parser.add_argument("--cpu-build", action="store_true")
    parser.add_argument(
        "--slot-cpusets", required=True, type=lambda v: v.split(","), help="0-3,4-7,..."
    )
    parser.add_argument(
        "--concurrency",
        default="1",
        type=lambda v: [int(x) for x in v.split(",")],
        help="levels N to run in turn, e.g. 1,2,3,4",
    )
    parser.add_argument(
        "--builds-per-slot", type=int, default=2, help="builds per level = this x N"
    )
    parser.add_argument("--seed-base", type=int, default=0)
    parser.add_argument(
        "--gpu-slot-values",
        help="a remote_gpu_build values file: run each GPU build in the door's slot pool (see the docstring)",
    )
    parser.add_argument("--work", required=True, help="an empty scratch directory")
    args = parser.parse_args(argv)
    if not args.cpu_build and not args.gpu_image_identity:
        parser.error("--gpu-image-identity is required unless --cpu-build")
    if args.cpu_build and args.gpu_slot_values:
        parser.error("--gpu-slot-values is for GPU builds only")
    if any(n < 1 or n > len(args.slot_cpusets) for n in args.concurrency):
        parser.error("each --concurrency level needs that many --slot-cpusets")
    if args.builds_per_slot < 1:
        parser.error("--builds-per-slot must be at least 1")
    return args


def main(argv=None):
    args = parse(argv)
    from carbon.challenge_kit import physical_material
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit(
            "--work must be empty (each build gets a fresh scratch ledger)"
        )
    locks = work / "locks"
    locks.mkdir()
    recipes = load_recipes(args.recipe_dir)
    context = {
        "material": physical_material.bundle_material(args.challenge, args.version),
        "cpu_image": load_image_identity(Path(args.cpu_image_identity)),
        "gpu_image": (
            None
            if args.cpu_build
            else load_image_identity(Path(args.gpu_image_identity))
        ),
        "locks": locks,
    }
    context["gpu_values"] = (
        None if args.gpu_slot_values is None else Path(args.gpu_slot_values)
    )
    pool = gpu_pool(args)
    instrument()
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "challenge": args.challenge,
                "version": args.version,
                "device": "cpu" if args.cpu_build else "gpu",
                # the door's own recipe digest of each file (what a v2 receipt names)
                "recipes": {
                    name: ConstructionRecipe.from_dict(recipe).digest
                    for name, recipe, _m, _f in recipes
                },
                "slot_cpusets": args.slot_cpusets,
                "gpu_pool": pool,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    index = 0
    for n in args.concurrency:
        pending = queue.Queue()
        for _ in range(args.builds_per_slot * n):
            pending.put((index, recipes[index % len(recipes)]))
            index += 1
        records, printing = [], threading.Lock()

        def slot_loop(slot, n=n, pending=pending, records=records, printing=printing):
            # one thread per slot, its builds one after another: N builds in flight, never two on one slot's cores
            while True:
                try:
                    build_index, recipe = pending.get_nowait()
                except queue.Empty:
                    return
                record = one_build((n, build_index, slot, recipe), args, context)
                with printing:
                    print(json.dumps(record, sort_keys=True), flush=True)
                    records.append(record)

        began = time.monotonic()
        threads = [
            threading.Thread(target=slot_loop, args=(slot,)) for slot in range(n)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        print(
            json.dumps(summary(n, records, time.monotonic() - began), sort_keys=True),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
