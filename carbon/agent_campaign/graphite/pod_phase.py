"""The `graphite_practice` pod phase: one proposal, trained and predicted on a pod.

Runs on the pod, from the hash-pinned code ship (`bootstrap.py` verified every
file against its sha256 before anything was imported), as

    python -m scripts.dev.exam_design.runner graphite_practice --out OUT

with its configuration in `PHASE_CONFIG` (`pods.PodJob.config`). It does what
a miner's practice trial does, with Carbon's own code:

1. compiles the strategy against its Challenge's recorded construction
   contract and builds the exact staged files of a practice trial, through
   that Challenge's `ChallengeScoring.built_record` (for battery: Carbon's
   recipe modules, public TRAIN v1, the OCV table, the public PRACTICE inputs
   and the compiled recipe with Carbon's practice randomness);
2. **refuses to run** unless the staged files and the program are exactly the
   ones Carbon pinned before launch (`expected`);
3. runs the Challenge's fixed practice program (for battery,
   `carbon.development_session.battery_gpu.GPU_PROGRAM`) in a fresh
   directory, bounded by the contract's worker deadline;
4. writes `built.json` (what was built: the recipe document and every digest),
   the program's `predictions.json`, `fit.json` and `runtime.json`, and
   `DONE.json`.

No label reaches the program, nothing is scored here, and the pod holds no
key. Carbon scores on its own host after fetching the files.

`failure.json` names the stage that failed. The program runs under this
process's own user and can reach this directory, so Carbon's host treats the
file as evidence only and types the outcome from its own observations
(`pod_outcome`, OWNER-GRAPHITE-TEST-WAVE-02 §3).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OUTPUTS = ("predictions.json", "fit.json", "runtime.json")


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True))


def built_record(strategy, contract_digest, seed, root=".", scoring=None):
    """What Carbon builds for `strategy`: the compiled recipe, the staged
    files' digests and the program's digest, from the Challenge's own
    `ChallengeScoring.built_record`. Used on the pod and, for the independent
    rebuild, on Carbon's host. With no scoring named, the strategy's own
    Challenge serves."""
    from carbon.challenge_validator import scoring as challenge_scoring

    if scoring is None:
        named = strategy.get("challenge_id") if type(strategy) is dict else None
        scoring = challenge_scoring.scoring_for(named)
    return scoring.built_record(strategy, contract_digest, seed, root)


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
