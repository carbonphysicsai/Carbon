"""G3's isolated parse: one submission from stdin, one JSON line to stdout.

Run by `intake` as a separate process with the limits it passes. It parses
and verifies only; it holds no secret, reads no file and opens nothing.
"""

from __future__ import annotations

import base64
import json
import resource
import sys


def _limits(cpu_seconds, memory_bytes):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def main():
    request = json.loads(sys.stdin.buffer.read())
    _limits(int(request["cpu_seconds"]), int(request["memory_bytes"]))
    try:
        from carbon.level4 import graph, submission
        from carbon.level4.allowlist import Allowlist
    except Exception:  # noqa: BLE001 - Carbon's environment, not the submission
        print(json.dumps({"state": "FAILED_INFRA"}))
        return 0
    files = {k: base64.b64decode(v) for k, v in request["files"].items()}
    try:
        submission.verify(
            base64.b64decode(request["manifest"]),
            files,
            allowlist=Allowlist(base64.b64decode(request["allowlist"])),
            challenge=request["challenge"],
            interface=request["interface"],
            max_bytes=int(request["max_bytes"]),
        )
    except graph.GraphRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 0
    print(json.dumps({"ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
