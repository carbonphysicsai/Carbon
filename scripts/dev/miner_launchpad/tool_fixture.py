"""The demo's tool session: the real tools, synthetic answers (RSURF-D18).

SYNTHETIC FIXTURE. The tool set, argument validation and task projection are
the real ones (`standard_server._create_server`, `ResearchToolAdapter`). The
SDK under them has no connection, no composition and no ledger, so nothing
can be dispatched; its answers come from here:
- a small in-memory workspace a miner can read and edit (it never leaves this
  process);
- three finished `run_python` runs: one on CPU with stdout and a PNG plot
  drawn here, one tagged as run on the campaign's (synthetic) GPU, and one
  that failed, with the stdout and stderr it kept (RSURF-D20, D21);
- a `dry_validate`, which is the registry's own pure structural check;
- every start of new work (a run, a practice trial, a cancel) is refused as
  `fixture_read_only`.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import struct
import zlib

from carbon.development_session.profile import canonical, digest

EVIDENCE = "SYNTHETIC_FIXTURE"
TASK = "rtsk_" + hashlib.sha256(b"fixture-run-python").hexdigest()
GPU_TASK = "rtsk_" + hashlib.sha256(b"fixture-run-python-gpu").hexdigest()
FAILED_TASK = "rtsk_" + hashlib.sha256(b"fixture-run-python-failed").hexdigest()
#: Newest first, as the page lists them.
TASKS = (FAILED_TASK, GPU_TASK, TASK)
GPU_IMAGE = "fixture-gpu-worker-image"
GPU_STDOUT = (
    "SYNTHETIC FIXTURE: no program ran.\n"
    "jax default backend: gpu\n"
    "devices: [synthetic GPU 0]\n"
    "fit 2000 steps in 3.1 s\n"
)
FAILED_STDOUT = "SYNTHETIC FIXTURE: no program ran.\nloading train-summary.json\n"
FAILED_STDERR = (
    "Traceback (most recent call last):\n"
    '  File "/input/program.py", line 7, in <module>\n'
    '    print(summary["capacity_fade"])\n'
    "KeyError: 'capacity_fade'\n"
)
CREATED_MICROS = 1_790_000_000_000_000
REFUSED = {
    "status": "REJECTED_BEFORE_DISPATCH",
    "reason": "fixture_read_only",
    "detail": (
        "This synthetic fixture runs nothing. In a real campaign this starts "
        "the work, with its own limits and charge."
    ),
    "authority_granted": False,
}
SOURCE = """# Synthetic fixture source: the run below is made up, nothing ran.
import json
from pathlib import Path

summary = json.loads(Path("train-summary.json").read_text())
fade = [1.0 - 0.0021 * c for c in range(0, 400, 25)]
print("cases:", summary["cases"])
print("capacity fade at cycle 375:", round(fade[-1], 4))
Path("/scratch/output/capacity_fade.json").write_text(json.dumps(fade))
# A plot written to /scratch/output appears with this run's output.
"""
STDOUT = (
    "SYNTHETIC FIXTURE: no program ran.\n"
    "cases: 128\n"
    "capacity fade at cycle 375: 0.2125\n"
    "<b>output is text</b>, never HTML\n"
)
WORKSPACE_MAX = 32
FILE_MAX = 24 * 1024


def plot_png(width=360, height=220):
    """A small line plot, drawn here: synthetic capacity fade."""
    background, axis, line = (250, 248, 244), (90, 90, 90), (217, 72, 15)
    pixels = [[background] * width for _ in range(height)]
    left, bottom, top, right = 32, height - 24, 16, width - 12

    def put(x, y, colour):
        if 0 <= x < width and 0 <= y < height:
            pixels[y][x] = colour

    for x in range(left, right + 1):
        put(x, bottom, axis)
    for y in range(top, bottom + 1):
        put(left, y, axis)
    previous = None
    for x in range(left + 1, right):
        t = (x - left) / (right - left)
        value = 1.0 - 0.55 * t - 0.3 * t * t
        y = int(bottom - (bottom - top) * (0.1 + 0.85 * value))
        if previous is not None:
            for yy in range(min(previous, y), max(previous, y) + 1):
                put(x, yy, line)
                put(x, yy + 1, line)
        previous = y
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _exports(task=TASK):
    if task == GPU_TASK:
        return [GPU_TASK[-20:] + "-timing.json"]
    if task == FAILED_TASK:
        return []
    return [
        TASK[-20:] + "-capacity_fade.png",
        TASK[-20:] + "-capacity_fade.json",
    ]


def initial_workspace():
    fade = [round(1.0 - 0.0021 * c, 4) for c in range(0, 400, 25)]
    plot, values = _exports()
    return {
        "analyse_capacity.py": SOURCE.encode(),
        "notes.md": (
            b"# Synthetic fixture notes\n\nCapacity moved least in epoch 1. "
            b"Try a wider capacity head next.\n"
        ),
        "train-summary.json": canonical({"cases": 128, "fixture": True}),
        plot: plot_png(),
        values: json.dumps(fade).encode(),
        _exports(GPU_TASK)[0]: canonical({"fit_seconds": 3.1, "fixture": True}),
    }


def _view(task_id, state="SUCCEEDED"):
    return {
        "task_id": {"value": task_id},
        "state": state,
        "created_at_micros": CREATED_MICROS,
        "updated_at_micros": CREATED_MICROS + 4_000_000,
        "evidence": EVIDENCE,
    }


class FixtureTools:
    """What the fixture's SDK answers. It holds no connection, composition
    or ledger, and refuses every start of new work."""

    def __init__(self, runner):
        self.runner = runner
        self.files = initial_workspace()

    # -- the envelope the real SDK returns

    def _envelope(self, operation, reply, *, task=None, result=None):
        public = None
        if task is not None:
            public = {
                "schema": "carbon.autoresearch.public-result.v1",
                "task_id": task,
                "result": result,
                "evidence": EVIDENCE,
                "official_eligible": False,
            }
        from carbon import research

        return {
            "protocol": research.RESEARCH_NAMESPACE,
            "operation": operation,
            "reply": reply,
            "terminal_task": None if task is None else _view(task),
            "public_result": public,
            "requires_reconciliation": False,
        }

    async def call(self, name, args, identity, *, transport_request_id=None):
        from carbon.development_session.research_tools import PREFIX

        operation = name.removeprefix(PREFIX)
        ok = {"status": "OK", "evidence": EVIDENCE}
        if operation in {"dry_validate", "compile_strategy", "inspect_resources"}:
            return self._envelope(
                operation, {**ok, "result": self._validated(args, operation)}
            )
        if operation == "forecast_resources":
            return self._envelope(
                operation,
                {
                    **ok,
                    "result": {
                        **self._validated(args, operation),
                        "forecast": {
                            "seconds": args["seconds"],
                            "research_trials": 1,
                            "basis": "synthetic fixture estimate, not a forecast",
                        },
                    },
                },
            )
        if operation == "inspect_prior_alignment":
            return {
                "operation": operation,
                "status": "UNAVAILABLE",
                "reason": "missing_data_support",
                "detail": "No registered public prior pack; nothing computed.",
                "authority_granted": False,
            }
        if operation in {
            "get_challenge_info",
            "get_interaction_manifest",
            "get_prior",
            "get_mock_scaffold",
        }:
            challenge = self.runner.challenge or {}
            return self._envelope(
                operation,
                {
                    **ok,
                    "result": {
                        "challenge": challenge.get("id"),
                        "version": challenge.get("version"),
                        "note": "Synthetic fixture: a real campaign answers this.",
                    },
                },
            )
        if operation == "get_research_result":
            return self._task(args["task_id"], operation)
        if operation == "cancel_research_task":
            return dict(REFUSED)
        if operation == "start_research_task":
            return self._start(args, identity)
        return dict(REFUSED)

    async def task_call(self, mode, args, identity):
        if mode == "start":
            return dict(REFUSED)
        # Observe, or cancel: the one task is already finished, so a cancel
        # changes nothing and reports it as it is.
        return {
            **self._task(args["task_id"], "start_research_task"),
            "original_operation_id": "fixture-run-python-0001",
        }

    # -- answers

    def _validated(self, args, operation):
        from carbon.reconstruction.challenge_contracts import validate_for_challenge

        try:
            strategy = json.loads(args["strategy_json"])
        except (TypeError, ValueError):
            strategy = None
        checked = validate_for_challenge(strategy)
        issues = [{"code": i.code, "path": i.path} for i in checked.errors]
        return {
            "valid": not issues,
            "issues": issues,
            "checked_by": "the registry's structural and Challenge contract check",
            "note": (
                None
                if operation == "dry_validate"
                else "Synthetic fixture: shown as validation only."
            ),
        }

    def _task(self, task_id, operation):
        if task_id not in TASKS:
            return self._envelope(
                operation, {"status": "ERROR", "result": {"code": "TASK_UNKNOWN"}}
            )
        return self._envelope(
            operation,
            {"status": "OK", "evidence": EVIDENCE},
            task=task_id,
            result=self.finished_run(task_id),
        )

    def finished_run(self, task=TASK):
        worker = {
            "schema": "carbon.autoresearch.worker-result.v1",
            "operation": "fixture-operation",
            "files": {
                "capacity_fade.png": "synthetic",
                "capacity_fade.json": "synthetic",
            },
            "scientific_qualification": False,
            "official_eligible": False,
        }
        result = {
            "provenance": "MINER_SELF_REPORTED",
            "worker": worker,
            "workspace_exports": _exports(task),
            "evidence": EVIDENCE,
        }
        if task == GPU_TASK:
            # As a GPU code cell records the device it ran on (RSURF-D20).
            result["worker"] = {**worker, "files": {"timing.json": "synthetic"}}
            result["device"] = {
                "kind": "local_gpu",
                "label": "your GPU (this machine)",
                "device_kind": "synthetic GPU",
                "image": GPU_IMAGE,
            }
        if task == FAILED_TASK:
            result["outcome"] = "MINER_PROGRAM_FAILED"
            result["worker"] = {
                "schema": "carbon.autoresearch.miner-program-failure.v1",
                "operation": "fixture-failed-operation",
                "state": "FAILED_MINER",
                "failure_code": "RUNTIME",
                "observation": "NONZERO_EXIT",
                "scientific_qualification": False,
                "official_eligible": False,
            }
        return result

    def _start(self, args, identity):
        if args["kind"] != "workspace" or args["action"] in {"run_python", "run_julia"}:
            return dict(REFUSED)
        try:
            arguments = json.loads(args["arguments_json"])
            result = self._workspace(args["action"], arguments)
        except (ValueError, KeyError, TypeError) as exc:
            return {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason": "contract_incompatibility",
                "detail": "Synthetic fixture: " + str(exc)[:200],
                "authority_granted": False,
            }
        task = "rtsk_" + hashlib.sha256(identity.encode()).hexdigest()
        return self._envelope(
            "start_research_task",
            {"status": "OK", "evidence": EVIDENCE},
            task=task,
            result=result,
        )

    def _workspace(self, action, arguments):
        from carbon.development_session.research_workspace import ResearchWorkspace

        if action == "inventory":
            return {
                "files": [
                    {"name": name, "bytes": len(body), "digest": digest(body)}
                    for name, body in sorted(self.files.items())
                ]
            }
        if action == "read_file":
            body = self.files[ResearchWorkspace.name(arguments["name"])]
            offset, count = arguments["offset"], arguments["count"]
            if type(offset) is not int or offset < 0 or not 1 <= count <= 4096:
                raise ValueError("bounded byte range required")
            return {
                "name": arguments["name"],
                "digest": digest(body),
                "bytes": len(body),
                "offset": offset,
                "content_base64": base64.b64encode(
                    body[offset : offset + count]
                ).decode(),
            }
        if action == "write_file":
            name = ResearchWorkspace.name(arguments["name"])
            body = base64.b64decode(arguments["content_base64"], validate=True)
            old = self.files.get(name)
            if (None if old is None else digest(old)) != arguments["expected_digest"]:
                raise ValueError("workspace compare-and-swap conflict")
            if len(body) > FILE_MAX or (
                old is None and len(self.files) >= WORKSPACE_MAX
            ):
                raise ValueError("the fixture keeps small files only")
            self.files[name] = body
            return {"name": name, "digest": digest(body), "kept": "in memory only"}
        if action == "notebook":
            if arguments["kind"] not in {"hypothesis", "decision", "notebook"}:
                raise ValueError("miner notebook kind unavailable")
            return {"retained": True, "kept": "nowhere: a synthetic fixture"}
        if action == "public_material":
            return {
                "name": arguments["name"],
                "note": "Synthetic fixture: a real campaign returns the public document.",
            }
        if action == "check_design":
            from carbon.development_session.design_check import check_design

            return check_design(arguments["design"])
        if action == "roadmap":
            from carbon.development_session.capability_demand import public_roadmap

            return public_roadmap(None)
        if action == "capability_request":
            return {
                **arguments["request"],
                "disposition": "investigate",
                "authority_granted": False,
                "kept": "nowhere: a synthetic fixture",
            }
        raise ValueError("unknown workspace action")

    def run_output(self, task):
        from scripts.dev.miner_launchpad.controller import Rejected
        from scripts.dev.miner_launchpad.run_output import check_task, document

        if check_task(task) not in TASKS:
            raise Rejected("run_output_unavailable", 404)
        stdout, stderr = {
            TASK: (STDOUT, ""),
            GPU_TASK: (GPU_STDOUT, ""),
            FAILED_TASK: (FAILED_STDOUT, FAILED_STDERR),
        }[task]
        return {
            **document(
                task,
                self.finished_run(task),
                stdout=stdout.encode(),
                stderr=stderr.encode(),
                exports=[(name, self.files.get(name)) for name in _exports(task)],
            ),
            "evidence": EVIDENCE,
        }


def fixture_adapter(tools, principal):
    """A real `ResearchToolAdapter` over an SDK with no connection,
    composition or ledger, answered by `tools`."""
    from types import SimpleNamespace

    from carbon.development_session.gpu_code_cell import GpuLane
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.miner_mcp.standard import ResearchToolAdapter

    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=SimpleNamespace(
            executor=SimpleNamespace(
                owner=principal,
                julia_image=None,
                # The campaign's (synthetic) GPU lane, so the code cell offers
                # the choice; every run is still refused (RSURF-D18, D20).
                gpu=GpuLane(image=SimpleNamespace(image_id=GPU_IMAGE)),
            )
        ),
        ledger=None,
        owner=principal,
    )
    sdk.call = tools.call
    sdk.task_call = tools.task_call
    return ResearchToolAdapter(sdk, principal=principal)


def fixture_opener(runner, tools):
    @contextlib.asynccontextmanager
    async def opener(campaign):
        runner.owned_campaign(campaign)
        yield fixture_adapter(tools, runner.principal)

    return opener
