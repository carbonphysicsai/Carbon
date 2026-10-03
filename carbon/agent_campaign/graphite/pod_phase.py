"""The `graphite_practice` pod phase: one proposal, trained and predicted on a pod.

Runs on the pod, from the hash-pinned code ship (`bootstrap.py` verified every
file against its sha256 before anything was imported), as

    python -m scripts.dev.exam_design.runner graphite_practice --out OUT

with its configuration in `PHASE_CONFIG` (`pods.PodJob.config`). It does what
a miner's practice trial does, with Carbon's own code:

1. compiles the strategy against the recorded battery construction contract
   (`compile_submission`, refused by name if Carbon cannot rebuild it);
2. builds the exact staged files of a practice trial
   (`carbon.battery.practice.staged_files`: Carbon's recipe modules, public
   TRAIN v1, the OCV table, the public PRACTICE inputs and the compiled
   recipe with Carbon's practice randomness);
3. **refuses to run** unless the staged files and the program are exactly the
   ones Carbon pinned before launch (`expected`);
4. runs the fixed GPU practice program
   (`carbon.development_session.battery_gpu.GPU_PROGRAM`) in a fresh
   directory, bounded by the contract's worker deadline;
5. writes `built.json` (what was built: the recipe document and every digest),
   the program's `predictions.json`, `fit.json` and `runtime.json`, and
   `DONE.json`.

No label reaches the program, nothing is scored here, and the pod holds no
key. Carbon scores on its own host after fetching the files.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BUILT_SCHEMA = "carbon.graphite.pod-built.v1"
OUTPUTS = ("predictions.json", "fit.json", "runtime.json")


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True))


def built_record(strategy, contract_digest, seed, root="."):
    """What Carbon builds for `strategy`: the compiled recipe, the staged
    files' digests and the program's digest. Used on the pod and, for the
    independent rebuild, on Carbon's host."""
    from carbon.battery.practice import PracticeSet, staged_files
    from carbon.development_session.battery_gpu import GPU_PROGRAM
    from carbon.development_session.profile import digest
    from carbon.reconstruction.challenge_contracts import compile_submission

    admitted = compile_submission(strategy, contract_digest=contract_digest)
    recipe = admitted.construction
    plan = admitted.compiled.construction_plan
    files = staged_files(root, PracticeSet.load(root), recipe, seed)
    record = {
        "schema": BUILT_SCHEMA,
        "challenge": recipe.document()["challenge"],
        "contract_digest": admitted.contract_digest,
        "recipe": recipe.document(),
        "recipe_digest": recipe.recipe_digest,
        "strategy_hash": plan.strategy_hash.value,
        "plan_digest": plan.to_ref().content_digest,
        "staged": {name: digest(body) for name, body in sorted(files.items())},
        "program": digest(GPU_PROGRAM.encode()),
        "seed": seed,
    }
    return record, files, GPU_PROGRAM


def pinned(record, expected):
    """The staged files and program are exactly the ones Carbon pinned."""
    return (
        record["staged"] == expected["files"]
        and record["program"] == expected["program"]
    )


def run(cfg, out, *, root="."):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        record, files, program = built_record(
            cfg["strategy"], cfg["contract_digest"], cfg["seed"], root
        )
    except Exception as failure:  # noqa: BLE001 -- typed, never echoed
        _write(
            out / "failure.json", {"stage": "compile", "error": type(failure).__name__}
        )
        return 2
    _write(out / "built.json", record)
    if not pinned(record, cfg["expected"]):
        _write(out / "failure.json", {"stage": "verification", "error": "digest"})
        return 3
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "work"
        output = Path(directory) / "output"
        work.mkdir()
        output.mkdir()
        for name, body in files.items():
            (work / name).write_bytes(body)
        try:
            with open(out / "program.log", "wb") as log:
                code = subprocess.run(
                    [sys.executable, "-I", "-c", program],
                    cwd=work,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=int(cfg["seconds"]),
                    check=False,
                ).returncode
        except subprocess.TimeoutExpired:
            _write(out / "failure.json", {"stage": "timeout", "error": "deadline"})
            return 4
        for name in OUTPUTS:
            if (output / name).is_file():
                shutil.copyfile(output / name, out / name)
    if code != 0:
        _write(out / "failure.json", {"stage": "program", "error": f"exit {code}"})
        return 5
    _write(out / "DONE.json", {"phase": "graphite_practice", "exit": 0})
    return 0
