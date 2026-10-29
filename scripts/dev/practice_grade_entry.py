"""Grade one catalog entry through the practice a miner uses and print its deterministic grade (public data only).

This is the grading entrypoint for the 4090 class probes `grade_repeat` and `parity` (kit4090 `s3_class_probes`):
the entry is built by the practice (on the GPU when `--gpu-image` names the GPU worker image and the entry's GPU twin is
installed), inferred on the CPU worker, and graded by the exam's own practice-v2 grader on the full public bank. It
reads no sealed material, no seed and no key; it is feedback, never an exam grade.

    practice_grade_entry.py grade  --kind K --entry CATALOG_ID --parent-identity ID.json --cache-root DIR
                                   [--gpu-image GPU_ID.json] [--work-dir DIR]
    practice_grade_entry.py parity --kind K --entry CATALOG_ID --gpu-image GPU_ID.json (same other flags)

On a host with a recorded install, give the GPU leg a SCRATCH cache so no image or tag of the install is built,
created or moved: `python -m scripts.dev.stage_scratch_twin --scratch-state-dir DIR --torch-gpu-manifest M ENTRY`
prints its cache root; pass it as --gpu-cache-root (the CPU leg keeps --cache-root, the install's own cache).

`grade` prints one canonical JSON line (sorted keys, no timings, no wall clock): the legs, the design parts, the gates,
`total` = 0.5 * accuracy + 0.5 * design_value, the state digest and where it ran. Two runs with the same inputs and
pinned BLAS/OMP threads print the same bytes, so `grade_repeat --cmd` hashes that line. `parity` runs the entry on the
CPU and on the GPU and prints {entry: {"gpu_total", "cpu_total"}}, the file `s3_class_probes parity --totals` reads.

Exit 0 a grade; 1 the entry did not score (a gate failed or no document: no total to compare); 3 a GPU run was asked
for but the practice ran the CPU build (`gpu_note` says why), which is not a GPU datum. Needs `practice_v2_curves.py`
beside it (same directory).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import practice_v2_curves as curves

GRADE_KEYS = (
    "accuracy",
    "accuracy_legs",
    "decision_outcome",
    "design_parts",
    "design_value",
    "eligible",
    "failed_legs",
    "gates",
    "gates_failed_laws",
    "n_cases",
)


def _deterministic(document):
    return {key: document.get(key) for key in GRADE_KEYS if key in document}


def grade_one(kind, entry, args, *, factory=None, load_identity=None):
    """One entry's deterministic grade on the device `args.gpu_image` selects (GPU when named, else CPU)."""
    factory = factory or curves.practice_for
    practice = factory(kind, args)
    if getattr(args, "gpu_image", None):
        if load_identity is None:
            from carbon.reconstruction.worker.docker_runtime import load_image_identity

            def load_identity(path):
                return load_image_identity(Path(path))

        practice.gpu_image = load_identity(args.gpu_image)
    record = curves.one_result(kind, entry, practice)
    document = record.get("practice_dual") or {}
    backend = record.get("backend") or {}
    accuracy, design = document.get("accuracy"), document.get("design_value")
    grade = {
        "catalog_id": entry,
        "challenge": record["challenge"],
        "kind": kind,
        "status": record["status"],
        "device": "gpu" if str(backend.get("kind", "")).endswith("GPU") else "cpu",
        "backend_kind": backend.get("kind"),
        "gpu_note": backend.get("gpu_note"),
        "state_digest": record.get("state_digest"),
        "total": (
            None
            if accuracy is None or design is None
            else 0.5 * accuracy + 0.5 * design
        ),
        **_deterministic(document),
    }
    if record["status"] != "SCORED":
        grade["reason_code"] = record.get("reason_code") or document.get("reason")
    return grade


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _args(ns, work_dir, gpu_image):
    return SimpleNamespace(
        out_dir=str(work_dir),
        parent_identity=ns.parent_identity,
        # The GPU leg may use its own (scratch) cache, where only the twin material is staged
        # (stage_scratch_twin.py); the CPU leg reads the install's cache.
        cache_root=(
            ns.gpu_cache_root if gpu_image and ns.gpu_cache_root else ns.cache_root
        ),
        gpu_image=gpu_image,
    )


def main(argv=None, *, factory=None, load_identity=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("grade", "parity"))
    parser.add_argument("--kind", required=True, choices=sorted(curves.TARGETS))
    parser.add_argument("--entry", required=True)
    parser.add_argument("--parent-identity", required=True)
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--gpu-image")
    parser.add_argument(
        "--gpu-cache-root",
        help="the library cache for the GPU leg (a scratch cache from stage_scratch_twin.py); the CPU leg uses --cache-root",
    )
    parser.add_argument("--work-dir")
    ns = parser.parse_args(argv)
    if ns.mode == "parity" and not ns.gpu_image:
        parser.error("parity needs --gpu-image")
    sys.path.insert(0, str(curves.ROOT))
    base = Path(ns.work_dir) if ns.work_dir else Path(tempfile.mkdtemp(prefix="grade-"))

    def run(device, gpu_image):
        work = base / device
        work.mkdir(parents=True, exist_ok=True)
        return grade_one(
            ns.kind,
            ns.entry,
            _args(ns, work, gpu_image),
            factory=factory,
            load_identity=load_identity,
        )

    if ns.mode == "grade":
        grade = run("gpu" if ns.gpu_image else "cpu", ns.gpu_image)
        print(_canonical(grade))
        if grade["status"] != "SCORED" or grade["total"] is None:
            return 1
        if ns.gpu_image and grade["device"] != "gpu":
            return 3
        return 0
    cpu, gpu = run("cpu", None), run("gpu", ns.gpu_image)
    if gpu["device"] != "gpu":
        print(_canonical({"entry": ns.entry, "gpu_run": gpu}))
        return 3
    if cpu["total"] is None or gpu["total"] is None:
        print(_canonical({"entry": ns.entry, "cpu_run": cpu, "gpu_run": gpu}))
        return 1
    print(
        _canonical({ns.entry: {"gpu_total": gpu["total"], "cpu_total": cpu["total"]}})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
