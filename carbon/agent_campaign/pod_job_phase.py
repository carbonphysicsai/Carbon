"""The pod side of a shared pod job (`pod_jobs`): run the job's one module.

    python -m carbon.agent_campaign.pod_job_phase JOB_ID --out OUT

`bootstrap.py` runs this as the phase, from the hash-checked code at the
job's commit, with `JOB_CONFIG` = {module, args, collect, stop_epoch}. It
runs `python -m module args...` in the code root with no shell, `{out}`,
`{root}` and `{inputs}` in an argument replaced by the results, code and
uploaded-inputs directories (`INPUTS_DIR`), and everything under OUT is
served back by sha256. After the job, each `collect` path under the inputs
directory is copied to OUT/collected. `job.json` records the
command, the exit code and the wall time. A job still running at
`stop_epoch` is stopped, so the results can be fetched before the pod's
deadline; its exit is then `stopped_at_deadline`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_MODULE = re.compile(r"(carbon|scripts)(\.[A-Za-z_][A-Za-z0-9_]*)+")


def command(config, out, root, inputs=None):
    module, args = config.get("module"), config.get("args")
    if type(module) is not str or not _MODULE.fullmatch(module):
        raise SystemExit("refused: the job's module")
    if type(args) is not list or not all(type(a) is str for a in args):
        raise SystemExit("refused: the job's arguments")
    if inputs is None and any("{inputs}" in a for a in args):
        raise SystemExit("refused: {inputs} without uploaded inputs")
    filled = [
        a.replace("{out}", str(out))
        .replace("{root}", str(root))
        .replace("{inputs}", str(inputs))
        for a in args
    ]
    return [sys.executable, "-m", module, *filled]


def collect(paths, inputs, target):
    """Copy each path under `inputs` (a file or a directory, no link and
    nothing outside it) to `target`; the paths that were missing are listed."""
    missing = []
    for rel in paths:
        source = (inputs / rel) if inputs is not None else None
        if (
            source is None
            or ".." in Path(rel).parts
            or source.is_symlink()
            or not source.resolve().is_relative_to(inputs.resolve())
            or not source.exists()
        ):
            missing.append(rel)
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=False, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    return {"paths": list(paths), "missing": missing}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pod_job_phase")
    parser.add_argument("job_id")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(os.environ["JOB_CONFIG"])
    out, root = args.out, Path.cwd()
    inputs = Path(os.environ["INPUTS_DIR"]) if os.environ.get("INPUTS_DIR") else None
    argv_ = command(config, out, root, inputs)
    stop = float(config.get("stop_epoch", 0)) or None
    started = time.time()
    exit_code = None
    with open(out / "job.log", "wb") as log:
        process = subprocess.Popen(
            argv_, cwd=root, stdout=log, stderr=subprocess.STDOUT
        )
        try:
            exit_code = process.wait(
                timeout=None if stop is None else max(1.0, stop - time.time())
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            exit_code = "stopped_at_deadline"
    collected = collect(config.get("collect") or [], inputs, out / "collected")
    (out / "job.json").write_text(
        json.dumps(
            {
                "job_id": args.job_id,
                "command": argv_[1:],
                "exit": exit_code,
                "collected": collected,
                "wall_s": round(time.time() - started, 3),
            },
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
