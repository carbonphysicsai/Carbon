"""The code cell on the miner's own GPU (RSURF-D20, owner, 2026-10-03).

"Same isolation, network and file rules as today, with the GPU you set up
attached. You choose CPU or GPU per run, and it runs on your machine and your
bill. The validator stays on CPU."

`run_python` takes an optional `device`: `cpu` (the default, and what every
request without it has always meant) or `gpu`, offered only when the
campaign's frozen runtime has a GPU lane:
- **This machine's GPU.** The miner lane's own isolated container
  (`miner_container`), with the host's installed device attached and nothing
  else added, running the campaign's pinned GPU worker image (the CPU
  analysis image has no CUDA). The same device lease as GPU practice.
- **The miner's remote GPU.** Their own route (ssh-docker or ssh-container),
  the same pinned GPU worker and their own SSH, as remote practice uses them.
  Carbon starts, stops and bills nothing (OWNER-MINER-COMPUTE-LINK-ONLY-01).
  The job server in the pinned image is unchanged; Carbon's fixed wrapper
  runs the miner's program and returns its stdout as a file.

A program finds its outputs at `../output` in every lane. Each run records
the device it ran on. `run_julia` takes the same argument, but the pinned
Julia environments carry no CUDA packages, so `gpu` is refused for it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

DEVICES = ("cpu", "gpu")
#: The miner's program as staged on a remote setup, and the file the wrapper
#: returns its stdout in.
WRAPPED = "carbon-miner-program.py"
STDOUT_EXPORT = "carbon-stdout.txt"
#: What the remote job server returns beside the program's own outputs.
JOB_FILES = frozenset(
    {"carbon-job-result.json", "carbon-job-stderr.txt", STDOUT_EXPORT}
)
#: The remote route's job has a lifetime, so a remote run names its wall
#: allowance within the route's own bounds.
REMOTE_SECONDS = (40, 3600)
#: Carbon's fixed wrapper on a remote setup: it runs the miner's program as
#: `__main__` and keeps the last 64 KiB of what it prints.
WRAPPER = r'''"""Carbon's remote code-cell wrapper (RSURF-D20): runs the miner's program."""
import runpy
import sys
from pathlib import Path

KEEP = 64 * 1024
OUTPUT = Path("..").resolve() / "output"


class Tail:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, text):
        data = text.encode("utf-8", "replace") if isinstance(text, str) else bytes(text)
        self.buffer += data
        if len(self.buffer) > 2 * KEEP:
            del self.buffer[:-KEEP]
        return len(text)

    def flush(self):
        pass


tail = Tail()
sys.stdout = tail
try:
    runpy.run_path("carbon-miner-program.py", run_name="__main__")
finally:
    sys.stdout = sys.__stdout__
    (OUTPUT / "carbon-stdout.txt").write_bytes(bytes(tail.buffer[-KEEP:]))
'''


@dataclass(frozen=True)
class GpuLane:
    """A campaign's GPU lane: its pinned GPU worker, and its remote runner
    when the lane is the miner's remote setup (None: this machine)."""

    image: object
    remote: object = None

    def describe(self):
        if self.remote is None:
            return {
                "kind": "local_gpu",
                "label": "your GPU (this machine)",
                "image": self.image.image_id,
            }
        return {
            "kind": "remote_gpu",
            "label": "your remote GPU",
            "transport": getattr(getattr(self.remote, "transport", None), "name", None),
            "image": self.image.image_id,
            "seconds": list(REMOTE_SECONDS),
        }


def refusal(action, arguments, lane):
    """The registered correction for a device choice that cannot run, or
    None. Checked before dispatch, so nothing starts and nothing is charged."""
    device = arguments.get("device", "cpu")
    if device not in DEVICES:
        return "device_choice_invalid"
    if device == "cpu":
        return None
    if action == "run_julia":
        return "julia_gpu_unavailable"
    if lane is None:
        return "gpu_lane_not_configured"
    seconds = arguments.get("seconds")
    if lane.remote is not None and (
        type(seconds) is not int
        or not REMOTE_SECONDS[0] <= seconds <= REMOTE_SECONDS[1]
    ):
        return "remote_gpu_seconds_required"
    return None


def run(executor, *, identity, args, files):
    """Run one GPU code cell for `executor` and return its public result."""
    from .research_carrier import (
        KEPT_BYTES,
        MINER_GPU,
        PRECHARGED_TRIAL,
        STDERR_FILE,
        STDOUT_FILE,
        MinerProgramFailure,
        run_script,
    )

    lane = executor.gpu
    code = refusal("run_python", args, lane)
    if code is not None:
        raise ValueError(code)
    if lane.remote is None:
        from .research_carrier import _gpu_device

        device = _gpu_device()
        ran = {
            **lane.describe(),
            "device_kind": device.device_kind,
            "device_record_digest": device.digest,
        }
        try:
            result = run_script(
                executor.ledger,
                owner=executor.owner,
                identity=identity,
                source=args["source"],
                files=files,
                image=lane.image,
                seconds=args.get("seconds"),
                accelerator=MINER_GPU,
            )
        except MinerProgramFailure as failure:
            return {
                "provenance": "MINER_SELF_REPORTED",
                "outcome": "MINER_PROGRAM_FAILED",
                "worker": failure.result,
                "workspace_exports": [],
                "device": ran,
            }
        return {
            "provenance": "MINER_SELF_REPORTED",
            "worker": result,
            "workspace_exports": executor.export(identity, result),
            "device": ran,
        }
    if WRAPPED in files:
        raise ValueError(WRAPPED + " is the wrapper's own name")
    result = lane.remote(
        executor.ledger,
        owner=executor.owner,
        identity=identity,
        source=WRAPPER,
        files={**files, WRAPPED: args["source"].encode()},
        image=lane.image,
        seconds=args["seconds"],
        provenance="MINER_SELF_REPORTED",
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
    )
    operation = executor.ledger.root / result["operation"]
    snapshot = operation / "snapshot"

    def returned(name):
        path = snapshot / name
        if name not in result["files"] or path.is_symlink() or not path.is_file():
            return b""
        return path.read_bytes()

    # The job's own stdout and stderr, kept as the local lane keeps them.
    for name, body in (
        (STDOUT_FILE, returned(STDOUT_EXPORT)),
        (STDERR_FILE, returned("carbon-job-stderr.txt")),
    ):
        path = operation / name
        if not path.exists():
            path.write_bytes(body[-KEPT_BYTES:])
    try:
        job = json.loads(returned("carbon-job-result.json") or b"{}")
    except ValueError:
        job = {}
    ran = {**lane.describe(), "remote": result.get("remote")}
    if job.get("returncode") != 0:
        return {
            "provenance": "MINER_SELF_REPORTED",
            "outcome": "MINER_PROGRAM_FAILED",
            "worker": {
                **result,
                "failure_code": "DEADLINE" if job.get("timed_out") else "RUNTIME",
                "observation": "OWN_ALLOWANCE_ELAPSED"
                if job.get("timed_out")
                else "NONZERO_EXIT",
            },
            "workspace_exports": [],
            "device": ran,
        }
    return {
        "provenance": "MINER_SELF_REPORTED",
        "worker": result,
        "workspace_exports": executor.export(identity, result, skip=JOB_FILES),
        "device": ran,
    }
