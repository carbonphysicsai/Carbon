"""Fixed hostile probes used only by required disposable service tests."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


def main(arguments: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if not values:
        return 2
    probe = values.pop(0)
    if probe == "connect" and len(values) == 2:
        try:
            with socket.create_connection((values[0], int(values[1])), timeout=1):
                return 0
        except OSError:
            return 10
    if probe == "paths" and not values:
        forbidden = (
            Path("/var/run/docker.sock"),
            Path("/run/docker.sock"),
            Path("/host-canary"),
            Path("/root/.ssh"),
        )
        if any(path.exists() for path in forbidden):
            return 11
        root_denied = input_denied = False
        try:
            Path("/root-write-probe").write_bytes(b"x")
        except OSError:
            root_denied = True
        try:
            Path("/input/write-probe").write_bytes(b"x")
        except OSError:
            input_denied = True
        scratch = Path("/scratch/probe")
        scratch.write_bytes(b"x")
        return (
            0 if root_denied and input_denied and scratch.read_bytes() == b"x" else 12
        )
    if probe == "pids" and len(values) == 1:
        children = []
        denied = False
        try:
            for _ in range(int(values[0])):
                try:
                    children.append(
                        subprocess.Popen(
                            [sys.executable, "-I", "-c", "import time;time.sleep(30)"],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    )
                except OSError:
                    denied = True
                    break
        finally:
            for child in children:
                child.terminate()
            for child in children:
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
        return 0 if denied else 12
    if probe == "scratch-bytes" and len(values) == 1:
        target = int(values[0])
        try:
            with Path("/scratch/bytes-probe").open("wb", buffering=0) as stream:
                for _ in range(target // (1024**2)):
                    stream.write(b"x" * 1024**2)
        except OSError:
            return 0
        return 12
    if probe == "scratch-inodes" and len(values) == 1:
        try:
            root = Path("/scratch/inode-probe")
            root.mkdir()
            for index in range(int(values[0])):
                (root / str(index)).touch()
        except OSError:
            return 0
        return 12
    if probe == "memory" and len(values) == 1:
        target = int(values[0])
        allocated = []
        try:
            while sum(len(item) for item in allocated) < target:
                allocated.append(bytearray(8 * 1024**2))
        except MemoryError:
            return 0
        return 12
    if probe == "blocked" and len(values) == 1:
        time.sleep(float(values[0]))
        return 12
    if probe == "descendant" and len(values) == 1:
        marker = Path(values[0])
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                "import pathlib,time;time.sleep(3);pathlib.Path('/scratch/late-write').write_text('late')",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        marker.write_text("parent-exited", encoding="ascii")
        time.sleep(30)
        return 12
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
